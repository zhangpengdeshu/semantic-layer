"""主题域服务。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, page_params, rows
from app.semantic.services.errors import ConflictError, NotFoundError


def list_domains(q: str | None = None, status: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page, page_size = page_params(page, page_size)
    where = ["1=1"]
    params: dict[str, Any] = {}
    if q:
        where.append("(name ILIKE :q OR description ILIKE :q)")
        params["q"] = f"%{q}%"
    if status:
        where.append("status = :status")
        params["status"] = status
    clause = " AND ".join(where)
    total = one(f"SELECT count(*) AS total FROM t_sem_domain WHERE {clause}", params)["total"]
    items = rows(
        f"""
        SELECT d.*,
               (SELECT count(*) FROM t_sem_model m WHERE m.domain_id = d.domain_id) AS model_count
        FROM t_sem_domain d
        WHERE {clause}
        ORDER BY d.domain_id DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_domain(domain_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_domain WHERE domain_id = :id", {"id": domain_id})
    if not item:
        raise NotFoundError("主题域不存在", code="domain_not_found")
    item["members"] = rows(
        "SELECT user_id, role FROM t_sem_domain_member WHERE domain_id = :id ORDER BY user_id",
        {"id": domain_id},
    )
    item["model_count"] = one(
        "SELECT count(*) AS total FROM t_sem_model WHERE domain_id = :id", {"id": domain_id}
    )["total"]
    return item


def create_domain(payload: dict[str, Any]) -> dict[str, Any]:
    item = insert(
        """
        INSERT INTO t_sem_domain (name, description, owner)
        VALUES (:name, :description, :owner)
        RETURNING *
        """,
        {
            "name": payload["name"],
            "description": payload.get("description"),
            "owner": payload.get("owner"),
        },
    )
    for member in payload.get("members") or []:
        execute(
            """
            INSERT INTO t_sem_domain_member (domain_id, user_id, role)
            VALUES (:domain_id, :user_id, :role)
            ON CONFLICT (domain_id, user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            {"domain_id": item["domain_id"], "user_id": member["user_id"], "role": member.get("role", "modeler")},
        )
    return get_domain(int(item["domain_id"]))


def update_domain(domain_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    get_domain(domain_id)
    allowed = {"name", "description", "owner", "status"}
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_domain SET {sets}, updated_at = now() WHERE domain_id = :domain_id",
            {**fields, "domain_id": domain_id},
        )
    if payload.get("members") is not None:
        execute("DELETE FROM t_sem_domain_member WHERE domain_id = :id", {"id": domain_id})
        for member in payload["members"]:
            execute(
                """
                INSERT INTO t_sem_domain_member (domain_id, user_id, role)
                VALUES (:domain_id, :user_id, :role)
                """,
                {"domain_id": domain_id, "user_id": member["user_id"], "role": member.get("role", "modeler")},
            )
    return get_domain(domain_id)


def delete_domain(domain_id: int) -> None:
    get_domain(domain_id)
    count = one("SELECT count(*) AS total FROM t_sem_model WHERE domain_id = :id", {"id": domain_id})["total"]
    if count:
        raise ConflictError("主题域下仍有语义模型，不能删除", code="domain_in_use", detail={"model_count": count})
    execute("DELETE FROM t_sem_domain WHERE domain_id = :id", {"id": domain_id})