"""语义关系服务：认证 JOIN 边与候选关系。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

CARDINALITIES = {"1:1", "N:1", "1:N", "N:N"}
JOIN_TYPES = {"inner", "left"}


def _edge(edge_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_join_edge WHERE edge_id = :id", {"id": edge_id})
    if not item:
        raise NotFoundError("语义关系不存在", code="relationship_not_found")
    return item


def _ensure_field(model_id: int, field_id: int, label: str) -> None:
    if not one(
        "SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND field_id = :field_id",
        {"model_id": model_id, "field_id": field_id},
    ):
        raise ValidationFailedError(f"{label}字段不属于对应模型", code="relationship_field_invalid")


def list_relationships(model_id: int | None = None) -> list[dict[str, Any]]:
    where = "1=1"
    params: dict[str, Any] = {}
    if model_id:
        where = "(e.from_model_id = :model_id OR e.to_model_id = :model_id)"
        params["model_id"] = model_id
    return rows(
        f"""
        SELECT e.*,
               fm.name AS from_model_name, tm.name AS to_model_name,
               ff.name AS from_field_name, tf.name AS to_field_name
        FROM t_sem_join_edge e
        JOIN t_sem_model fm ON fm.model_id = e.from_model_id
        JOIN t_sem_model tm ON tm.model_id = e.to_model_id
        JOIN t_sem_field ff ON ff.field_id = e.from_field_id
        JOIN t_sem_field tf ON tf.field_id = e.to_field_id
        WHERE {where}
        ORDER BY e.priority, e.edge_id
        """,
        params,
    )


def get_relationship(edge_id: int) -> dict[str, Any]:
    item = _edge(edge_id)
    item["from_model"] = one("SELECT name FROM t_sem_model WHERE model_id = :id", {"id": item["from_model_id"]})
    item["to_model"] = one("SELECT name FROM t_sem_model WHERE model_id = :id", {"id": item["to_model_id"]})
    return item


def create_relationship(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("from_model_id"):
        raise ValidationFailedError("from_model_id 不能为空", code="relationship_from_model_missing")
    cardinality = payload.get("cardinality")
    if cardinality not in CARDINALITIES:
        raise ValidationFailedError("非法基数", code="invalid_cardinality")
    join_type = payload.get("join_type", "inner")
    if join_type not in JOIN_TYPES:
        raise ValidationFailedError("非法 join_type", code="invalid_join_type")
    _ensure_field(payload["from_model_id"], payload["from_field_id"], "from")
    _ensure_field(payload["to_model_id"], payload["to_field_id"], "to")
    if payload["from_model_id"] == payload["to_model_id"]:
        raise ValidationFailedError("关系两端不能是同一模型", code="relationship_self")
    if one("SELECT edge_id FROM t_sem_join_edge WHERE name = :name", {"name": payload["name"]}):
        raise ConflictError("关系名称已存在", code="relationship_name_exists")
    if one(
        """
        SELECT edge_id FROM t_sem_join_edge
        WHERE from_model_id = :from_model_id AND from_field_id = :from_field_id
          AND to_model_id = :to_model_id AND to_field_id = :to_field_id
        """,
        payload,
    ):
        raise ConflictError("关系已存在", code="relationship_exists")
    item = insert(
        """
        INSERT INTO t_sem_join_edge
          (name, from_model_id, from_field_id, to_model_id, to_field_id, cardinality,
           join_type, join_predicate, priority, verified)
        VALUES
          (:name, :from_model_id, :from_field_id, :to_model_id, :to_field_id, :cardinality,
           :join_type, :join_predicate, :priority, :verified)
        RETURNING *
        """,
        {
            "name": payload["name"],
            "from_model_id": payload["from_model_id"],
            "from_field_id": payload["from_field_id"],
            "to_model_id": payload["to_model_id"],
            "to_field_id": payload["to_field_id"],
            "cardinality": cardinality,
            "join_type": join_type,
            "join_predicate": payload.get("join_predicate"),
            "priority": payload.get("priority", 100),
            "verified": bool(payload.get("verified", False)),
        },
    )
    return get_relationship(int(item["edge_id"]))


def update_relationship(edge_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = _edge(edge_id)
    if payload.get("cardinality") and payload["cardinality"] not in CARDINALITIES:
        raise ValidationFailedError("非法基数", code="invalid_cardinality")
    if payload.get("join_type") and payload["join_type"] not in JOIN_TYPES:
        raise ValidationFailedError("非法 join_type", code="invalid_join_type")
    from_model_id = payload.get("from_model_id", current["from_model_id"])
    to_model_id = payload.get("to_model_id", current["to_model_id"])
    from_field_id = payload.get("from_field_id", current["from_field_id"])
    to_field_id = payload.get("to_field_id", current["to_field_id"])
    _ensure_field(from_model_id, from_field_id, "from")
    _ensure_field(to_model_id, to_field_id, "to")
    allowed = {"name", "from_model_id", "from_field_id", "to_model_id", "to_field_id", "cardinality",
               "join_type", "join_predicate", "priority", "verified"}
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "name" in fields and fields["name"] != current["name"]:
        if one("SELECT edge_id FROM t_sem_join_edge WHERE name = :name AND edge_id <> :id", {"name": fields["name"], "id": edge_id}):
            raise ConflictError("关系名称已存在", code="relationship_name_exists")
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_join_edge SET {sets}, updated_at = now() WHERE edge_id = :id",
            {**fields, "id": edge_id},
        )
    return get_relationship(edge_id)


def delete_relationship(edge_id: int) -> None:
    _edge(edge_id)
    execute("DELETE FROM t_sem_join_edge WHERE edge_id = :id", {"id": edge_id})


def suggestions(model_id: int) -> list[dict[str, Any]]:
    """基于同名 key 字段生成候选关系，不做物理外键推断。"""
    fields = rows(
        """
        SELECT f.field_id, f.model_id, f.name, f.semantic_type, m.name AS model_name
        FROM t_sem_field f JOIN t_sem_model m ON m.model_id = f.model_id
        WHERE f.model_id = :model_id
        """,
        {"model_id": model_id},
    )
    result: list[dict[str, Any]] = []
    for field in fields:
        if field["semantic_type"] not in {"key", "unknown"}:
            continue
        candidates = rows(
            """
            SELECT f.field_id, f.model_id, f.name, f.semantic_type, m.name AS model_name
            FROM t_sem_field f JOIN t_sem_model m ON m.model_id = f.model_id
            WHERE f.name = :name AND f.model_id <> :model_id
            ORDER BY f.model_id
            """,
            {"name": field["name"], "model_id": model_id},
        )
        for candidate in candidates:
            existing = one(
                """
                SELECT edge_id FROM t_sem_join_edge
                WHERE (from_model_id = :from_model AND from_field_id = :from_field
                       AND to_model_id = :to_model AND to_field_id = :to_field)
                """,
                {
                    "from_model": model_id,
                    "from_field": field["field_id"],
                    "to_model": candidate["model_id"],
                    "to_field": candidate["field_id"],
                },
            )
            if existing:
                continue
            result.append(
                {
                    "from_model_id": model_id,
                    "from_model_name": field["model_name"],
                    "from_field_id": field["field_id"],
                    "from_field_name": field["name"],
                    "to_model_id": candidate["model_id"],
                    "to_model_name": candidate["model_name"],
                    "to_field_id": candidate["field_id"],
                    "to_field_name": candidate["name"],
                    "suggested_cardinality": "N:1",
                    "confidence": 0.9 if candidate["semantic_type"] == "key" else 0.6,
                    "reason": "同名 key 字段",
                }
            )
    return result