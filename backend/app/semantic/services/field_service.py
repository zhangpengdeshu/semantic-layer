"""语义字段服务。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

SEMANTIC_TYPES = {"key", "dimension", "time", "measure", "unknown"}
DATA_TYPES = {"string", "number", "date", "boolean", "unknown"}


def _ensure_model(model_id: int) -> None:
    if not one("SELECT model_id FROM t_sem_model WHERE model_id = :id", {"id": model_id}):
        raise NotFoundError("语义模型不存在", code="model_not_found")


def list_fields(model_id: int) -> list[dict[str, Any]]:
    _ensure_model(model_id)
    return rows("SELECT * FROM t_sem_field WHERE model_id = :id ORDER BY field_id", {"id": model_id})


def get_field(field_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_field WHERE field_id = :id", {"id": field_id})
    if not item:
        raise NotFoundError("语义字段不存在", code="field_not_found")
    return item


def _validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("semantic_type") and payload["semantic_type"] not in SEMANTIC_TYPES:
        raise ValidationFailedError("非法 semantic_type", code="invalid_semantic_type")
    if payload.get("data_type") and payload["data_type"] not in DATA_TYPES:
        raise ValidationFailedError("非法 data_type", code="invalid_data_type")


def create_field(model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_model(model_id)
    _validate_payload(payload)
    exists = one(
        "SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND name = :name",
        {"model_id": model_id, "name": payload["name"]},
    )
    if exists:
        raise ConflictError("字段名称已存在", code="field_name_exists")
    item = insert(
        """
        INSERT INTO t_sem_field
          (model_id, name, business_name, synonyms, semantic_type, data_type, description, expression, is_hidden, sensitivity)
        VALUES
          (:model_id, :name, :business_name, CAST(:synonyms AS TEXT[]), :semantic_type, :data_type, :description, :expression, :is_hidden, :sensitivity)
        RETURNING *
        """,
        {
            "model_id": model_id,
            "name": payload["name"],
            "business_name": payload.get("business_name"),
            "synonyms": payload.get("synonyms") or [],
            "semantic_type": payload.get("semantic_type", "unknown"),
            "data_type": payload.get("data_type", "unknown"),
            "description": payload.get("description"),
            "expression": payload.get("expression"),
            "is_hidden": bool(payload.get("is_hidden", False)),
            "sensitivity": payload.get("sensitivity", "internal"),
        },
    )
    execute("UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id", {"id": model_id})
    return item


def batch_create_fields(model_id: int, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [create_field(model_id, item) for item in fields]


def update_field(field_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_field(field_id)
    _validate_payload(payload)
    allowed = {
        "name",
        "business_name",
        "synonyms",
        "semantic_type",
        "data_type",
        "description",
        "expression",
        "is_hidden",
        "sensitivity",
    }
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "name" in fields and fields["name"] != current["name"]:
        exists = one(
            "SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND name = :name AND field_id <> :field_id",
            {"model_id": current["model_id"], "name": fields["name"], "field_id": field_id},
        )
        if exists:
            raise ConflictError("字段名称已存在", code="field_name_exists")
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_field SET {sets}, updated_at = now() WHERE field_id = :field_id",
            {**fields, "field_id": field_id},
        )
        execute(
            "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
            {"id": current["model_id"]},
        )
    return get_field(field_id)


def delete_field(field_id: int) -> None:
    current = get_field(field_id)
    references = one(
        """
        SELECT
          (SELECT count(*) FROM t_sem_model_grain WHERE field_id = :id) AS grain_refs,
          (SELECT count(*) FROM t_sem_dimension WHERE field_id = :id) AS dimension_refs,
          (SELECT count(*) FROM t_sem_measure WHERE field_id = :id) AS measure_refs,
          (SELECT count(*) FROM t_sem_join_edge WHERE from_field_id = :id OR to_field_id = :id) AS edge_refs
        """,
        {"id": field_id},
    ) or {}
    if any(int(value or 0) for value in references.values()):
        raise ConflictError("字段已被粒度、维度、度量或关系引用", code="field_in_use", detail=references)
    execute("DELETE FROM t_sem_field WHERE field_id = :id", {"id": field_id})
    execute(
        "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
        {"id": current["model_id"]},
    )