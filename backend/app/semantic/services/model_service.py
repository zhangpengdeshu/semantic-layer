"""语义模型服务：模型、粒度与可问数状态派生。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, page_params, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError


def _binding_summary(model_id: int) -> dict[str, Any]:
    summary = one(
        """
        SELECT
          (SELECT count(*) FROM t_sem_binding b
            WHERE b.model_id = :model_id AND b.status = 'certified' AND b.verified) AS certified_bindings,
          (SELECT count(*) FROM t_sem_binding b
            WHERE b.model_id = :model_id AND b.status <> 'disabled' AND b.is_primary) AS primary_bindings,
          (SELECT count(*) FROM t_sem_field f WHERE f.model_id = :model_id) AS field_total,
          (SELECT count(*) FROM t_sem_field f
            WHERE f.model_id = :model_id AND f.is_hidden = FALSE) AS visible_fields
        """,
        {"model_id": model_id},
    ) or {}
    primary = one(
        """
        SELECT * FROM t_sem_binding
        WHERE model_id = :model_id AND status = 'certified' AND verified AND is_primary
        ORDER BY priority, binding_id LIMIT 1
        """,
        {"model_id": model_id},
    )
    mapped = 0
    if primary:
        mapped = one(
            """
            SELECT count(*) AS total
            FROM t_sem_field_binding fb
            JOIN t_sem_field f ON f.field_id = fb.field_id
            WHERE fb.binding_id = :binding_id AND f.is_hidden = FALSE
            """,
            {"binding_id": primary["binding_id"]},
        )["total"]
    total = int(summary.get("visible_fields") or 0)
    if not primary:
        binding_status = "unbound"
    elif mapped < total:
        binding_status = "partial"
    else:
        binding_status = "ready"
    return {
        "binding_status": binding_status,
        "field_total": int(summary.get("field_total") or 0),
        "visible_fields": total,
        "mapped_fields": int(mapped),
        "coverage": (mapped / total) if total else 0.0,
        "primary_binding_id": int(primary["binding_id"]) if primary else None,
        "primary_query_ref": primary["query_ref"] if primary else None,
    }


def _enrich(model: dict[str, Any]) -> dict[str, Any]:
    summary = _binding_summary(int(model["model_id"]))
    model.update(summary)
    model["queryable"] = model.get("status") == "certified" and summary["binding_status"] == "ready"
    return model


def list_models(
    domain_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    queryable: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page, page_size = page_params(page, page_size)
    where = ["1=1"]
    params: dict[str, Any] = {}
    if domain_id:
        where.append("m.domain_id = :domain_id")
        params["domain_id"] = domain_id
    if status:
        where.append("m.status = :status")
        params["status"] = status
    if q:
        where.append("(m.name ILIKE :q OR m.business_name ILIKE :q OR m.description ILIKE :q)")
        params["q"] = f"%{q}%"
    clause = " AND ".join(where)
    total = one(f"SELECT count(*) AS total FROM t_sem_model m WHERE {clause}", params)["total"]
    items = rows(
        f"""
        SELECT m.*, d.name AS domain_name,
               (SELECT string_agg(f.name, ' + ' ORDER BY g.position)
                  FROM t_sem_model_grain g
                  JOIN t_sem_field f ON f.field_id = g.field_id
                 WHERE g.model_id = m.model_id) AS grain_text
        FROM t_sem_model m
        JOIN t_sem_domain d ON d.domain_id = m.domain_id
        WHERE {clause}
        ORDER BY m.model_id DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    )
    enriched = [_enrich(item) for item in items]
    if queryable is not None:
        enriched = [item for item in enriched if bool(item["queryable"]) == bool(queryable)]
    return {"items": enriched, "total": total, "page": page, "page_size": page_size}


def get_model(model_id: int) -> dict[str, Any]:
    model = one(
        """
        SELECT m.*, d.name AS domain_name
        FROM t_sem_model m JOIN t_sem_domain d ON d.domain_id = m.domain_id
        WHERE m.model_id = :id
        """,
        {"id": model_id},
    )
    if not model:
        raise NotFoundError("语义模型不存在", code="model_not_found")
    _enrich(model)
    fields = rows("SELECT * FROM t_sem_field WHERE model_id = :id ORDER BY field_id", {"id": model_id})
    grain = rows(
        """
        SELECT g.field_id, g.position, f.name, f.business_name, f.semantic_type, f.data_type
        FROM t_sem_model_grain g
        JOIN t_sem_field f ON f.field_id = g.field_id
        WHERE g.model_id = :id ORDER BY g.position
        """,
        {"id": model_id},
    )
    dimensions = rows("SELECT * FROM t_sem_dimension WHERE model_id = :id ORDER BY dimension_id", {"id": model_id})
    measures = rows("SELECT * FROM t_sem_measure WHERE model_id = :id ORDER BY measure_id", {"id": model_id})
    relationships = rows(
        "SELECT * FROM t_sem_join_edge WHERE from_model_id = :id OR to_model_id = :id ORDER BY edge_id",
        {"id": model_id},
    )
    bindings = rows("SELECT * FROM t_sem_binding WHERE model_id = :id ORDER BY priority, binding_id", {"id": model_id})
    model.update(
        {
            "fields": fields,
            "grain": grain,
            "dimensions": dimensions,
            "measures": measures,
            "relationships": relationships,
            "bindings": bindings,
        }
    )
    return model


def create_model(payload: dict[str, Any]) -> dict[str, Any]:
    domain = one("SELECT domain_id FROM t_sem_domain WHERE domain_id = :id", {"id": payload["domain_id"]})
    if not domain:
        raise ValidationFailedError("domain_id 不存在", code="domain_not_found")
    exists = one("SELECT model_id FROM t_sem_model WHERE name = :name", {"name": payload["name"]})
    if exists:
        raise ConflictError("模型名称已存在", code="model_name_exists")
    model = insert(
        """
        INSERT INTO t_sem_model (domain_id, name, business_name, description, owner, max_hops)
        VALUES (:domain_id, :name, :business_name, :description, :owner, :max_hops)
        RETURNING model_id
        """,
        {
            "domain_id": payload["domain_id"],
            "name": payload["name"],
            "business_name": payload.get("business_name"),
            "description": payload.get("description"),
            "owner": payload.get("owner"),
            "max_hops": payload.get("max_hops", 3),
        },
    )
    return get_model(int(model["model_id"]))


def update_model(model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_model(model_id)
    expected_version = payload.get("version")
    if expected_version is not None and int(expected_version) != int(current["version"]):
        raise ConflictError(
            "模型已被他人修改，请刷新后重试",
            code="version_conflict",
            detail={"expected": int(expected_version), "current": int(current["version"])},
        )
    allowed = {"name", "business_name", "description", "owner", "status", "max_hops", "domain_id"}
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "name" in fields and fields["name"] != current["name"]:
        exists = one("SELECT model_id FROM t_sem_model WHERE name = :name", {"name": fields["name"]})
        if exists:
            raise ConflictError("模型名称已存在", code="model_name_exists")
    if "status" in fields and fields["status"] not in {"draft", "certified", "deprecated"}:
        raise ValidationFailedError("非法状态", code="invalid_status")
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_model SET {sets}, version = version + 1, updated_at = now() WHERE model_id = :model_id",
            {**fields, "model_id": model_id},
        )
    return get_model(model_id)


def delete_model(model_id: int) -> None:
    get_model(model_id)
    references = one(
        """
        SELECT
          (SELECT count(*) FROM t_sem_metric WHERE model_id = :id) AS metrics,
          (SELECT count(*) FROM t_sem_join_edge
            WHERE from_model_id = :id OR to_model_id = :id) AS relationships
        """,
        {"id": model_id},
    ) or {}
    if any(int(value or 0) for value in references.values()):
        raise ConflictError(
            "模型仍被指标或关系引用，请先解除引用",
            code="model_in_use",
            detail=references,
        )
    execute("DELETE FROM t_sem_model WHERE model_id = :id", {"id": model_id})


def set_grain(model_id: int, field_ids: list[int]) -> dict[str, Any]:
    get_model(model_id)
    if not field_ids:
        raise ValidationFailedError("粒度不能为空", code="grain_missing")
    placeholders = ", ".join(str(int(item)) for item in field_ids)
    owned = rows(
        f"SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND field_id IN ({placeholders})",
        {"model_id": model_id},
    )
    if len(owned) != len(set(field_ids)):
        raise ValidationFailedError("粒度字段必须属于当前模型", code="grain_field_invalid")
    execute("DELETE FROM t_sem_model_grain WHERE model_id = :id", {"id": model_id})
    for position, field_id in enumerate(field_ids, start=1):
        execute(
            "INSERT INTO t_sem_model_grain (model_id, field_id, position) VALUES (:model_id, :field_id, :position)",
            {"model_id": model_id, "field_id": field_id, "position": position},
        )
    execute("UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id", {"id": model_id})
    return get_model(model_id)