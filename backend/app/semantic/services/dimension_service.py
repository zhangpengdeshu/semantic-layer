"""维度服务。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, jsonb, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

DIMENSION_TYPES = {"categorical", "time"}
TIME_GRAINS = {"day", "week", "month", "quarter", "year"}


def _ensure_model(model_id: int) -> None:
    if not one("SELECT model_id FROM t_sem_model WHERE model_id = :id", {"id": model_id}):
        raise NotFoundError("语义模型不存在", code="model_not_found")


def _ensure_field(model_id: int, field_id: int) -> None:
    if not one(
        "SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND field_id = :field_id",
        {"model_id": model_id, "field_id": field_id},
    ):
        raise ValidationFailedError("维度字段必须属于当前模型", code="dimension_field_invalid")


def list_dimensions(model_id: int) -> list[dict[str, Any]]:
    _ensure_model(model_id)
    return rows(
        """
        SELECT d.*, f.name AS field_name, f.business_name AS field_business_name
        FROM t_sem_dimension d JOIN t_sem_field f ON f.field_id = d.field_id
        WHERE d.model_id = :id ORDER BY d.dimension_id
        """,
        {"id": model_id},
    )


def get_dimension(dimension_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_dimension WHERE dimension_id = :id", {"id": dimension_id})
    if not item:
        raise NotFoundError("维度不存在", code="dimension_not_found")
    return item


def create_dimension(model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_model(model_id)
    _ensure_field(model_id, payload["field_id"])
    dimension_type = payload.get("dimension_type", "categorical")
    if dimension_type not in DIMENSION_TYPES:
        raise ValidationFailedError("非法 dimension_type", code="invalid_dimension_type")
    grain = payload.get("time_granularity")
    if grain and grain not in TIME_GRAINS:
        raise ValidationFailedError("非法 time_granularity", code="invalid_time_granularity")
    if one(
        "SELECT dimension_id FROM t_sem_dimension WHERE model_id = :model_id AND name = :name",
        {"model_id": model_id, "name": payload["name"]},
    ):
        raise ConflictError("维度名称已存在", code="dimension_name_exists")
    item = insert(
        """
        INSERT INTO t_sem_dimension
          (model_id, name, field_id, dimension_type, time_granularity, hierarchy, code_mapping, default_filter, filterable, verified)
        VALUES
          (:model_id, :name, :field_id, :dimension_type, :time_granularity, :hierarchy, CAST(:code_mapping AS JSONB), :default_filter, :filterable, :verified)
        RETURNING *
        """,
        {
            "model_id": model_id,
            "name": payload["name"],
            "field_id": payload["field_id"],
            "dimension_type": dimension_type,
            "time_granularity": grain,
            "hierarchy": payload.get("hierarchy"),
            "code_mapping": jsonb(payload.get("code_mapping") or {}),
            "default_filter": payload.get("default_filter"),
            "filterable": bool(payload.get("filterable", True)),
            "verified": bool(payload.get("verified", False)),
        },
    )
    execute("UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id", {"id": model_id})
    return get_dimension(int(item["dimension_id"]))


def update_dimension(dimension_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_dimension(dimension_id)
    if payload.get("field_id"):
        _ensure_field(int(current["model_id"]), int(payload["field_id"]))
    if payload.get("dimension_type") and payload["dimension_type"] not in DIMENSION_TYPES:
        raise ValidationFailedError("非法 dimension_type", code="invalid_dimension_type")
    if payload.get("time_granularity") and payload["time_granularity"] not in TIME_GRAINS:
        raise ValidationFailedError("非法 time_granularity", code="invalid_time_granularity")
    allowed = {
        "name",
        "field_id",
        "dimension_type",
        "time_granularity",
        "hierarchy",
        "code_mapping",
        "default_filter",
        "filterable",
        "verified",
    }
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "code_mapping" in fields:
        fields["code_mapping"] = jsonb(fields["code_mapping"])
    if "name" in fields and fields["name"] != current["name"]:
        if one(
            "SELECT dimension_id FROM t_sem_dimension WHERE model_id = :model_id AND name = :name AND dimension_id <> :id",
            {"model_id": current["model_id"], "name": fields["name"], "id": dimension_id},
        ):
            raise ConflictError("维度名称已存在", code="dimension_name_exists")
    if fields:
        sets = ", ".join(
            f"{key} = CAST(:{key} AS JSONB)" if key == "code_mapping" else f"{key} = :{key}"
            for key in fields
        )
        execute(
            f"UPDATE t_sem_dimension SET {sets}, updated_at = now() WHERE dimension_id = :id",
            {**fields, "id": dimension_id},
        )
        execute(
            "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
            {"id": current["model_id"]},
        )
    return get_dimension(dimension_id)


def delete_dimension(dimension_id: int) -> None:
    current = get_dimension(dimension_id)
    execute("DELETE FROM t_sem_dimension WHERE dimension_id = :id", {"id": dimension_id})
    execute(
        "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
        {"id": current["model_id"]},
    )