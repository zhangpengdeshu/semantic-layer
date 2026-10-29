"""度量服务。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

AGGS = {"sum", "count", "count_distinct", "avg", "min", "max", "median", "percentile"}
ADDITIVITY = {"additive", "semi_additive", "non_additive"}


def _ensure_model(model_id: int) -> None:
    if not one("SELECT model_id FROM t_sem_model WHERE model_id = :id", {"id": model_id}):
        raise NotFoundError("语义模型不存在", code="model_not_found")


def _validate(model_id: int, payload: dict[str, Any]) -> None:
    if payload.get("agg") and payload["agg"] not in AGGS:
        raise ValidationFailedError("非法聚合方式", code="invalid_agg")
    if payload.get("additivity") and payload["additivity"] not in ADDITIVITY:
        raise ValidationFailedError("非法可加性", code="invalid_additivity")
    if not payload.get("field_id") and not payload.get("expr"):
        raise ValidationFailedError("度量必须指定 field_id 或 expr", code="measure_source_missing")
    if payload.get("field_id"):
        if not one(
            "SELECT field_id FROM t_sem_field WHERE model_id = :model_id AND field_id = :field_id",
            {"model_id": model_id, "field_id": payload["field_id"]},
        ):
            raise ValidationFailedError("度量字段必须属于当前模型", code="measure_field_invalid")
    if payload.get("additivity") == "semi_additive" and not payload.get("window_choice"):
        raise ValidationFailedError("半加性度量必须声明 window_choice", code="window_choice_missing")


def list_measures(model_id: int) -> list[dict[str, Any]]:
    _ensure_model(model_id)
    return rows(
        """
        SELECT m.*, f.name AS field_name, f.business_name AS field_business_name
        FROM t_sem_measure m LEFT JOIN t_sem_field f ON f.field_id = m.field_id
        WHERE m.model_id = :id ORDER BY m.measure_id
        """,
        {"id": model_id},
    )


def get_measure(measure_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_measure WHERE measure_id = :id", {"id": measure_id})
    if not item:
        raise NotFoundError("度量不存在", code="measure_not_found")
    return item


def create_measure(model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_model(model_id)
    _validate(model_id, payload)
    if one(
        "SELECT measure_id FROM t_sem_measure WHERE model_id = :model_id AND name = :name",
        {"model_id": model_id, "name": payload["name"]},
    ):
        raise ConflictError("度量名称已存在", code="measure_name_exists")
    item = insert(
        """
        INSERT INTO t_sem_measure
          (model_id, name, business_name, field_id, expr, filter, agg, agg_param, agg_time_dimension,
           additivity, window_choice, unit, verified)
        VALUES
          (:model_id, :name, :business_name, :field_id, :expr, :filter, :agg, :agg_param, :agg_time_dimension,
           :additivity, :window_choice, :unit, :verified)
        RETURNING *
        """,
        {
            "model_id": model_id,
            "name": payload["name"],
            "business_name": payload.get("business_name"),
            "field_id": payload.get("field_id"),
            "expr": payload.get("expr"),
            "filter": payload.get("filter"),
            "agg": payload.get("agg", "sum"),
            "agg_param": payload.get("agg_param"),
            "agg_time_dimension": payload.get("agg_time_dimension"),
            "additivity": payload.get("additivity", "additive"),
            "window_choice": payload.get("window_choice"),
            "unit": payload.get("unit"),
            "verified": bool(payload.get("verified", False)),
        },
    )
    execute("UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id", {"id": model_id})
    return get_measure(int(item["measure_id"]))


def update_measure(measure_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_measure(measure_id)
    merged = {**current, **{key: value for key, value in payload.items() if value is not None}}
    _validate(int(current["model_id"]), merged)
    allowed = {
        "name",
        "business_name",
        "field_id",
        "expr",
        "filter",
        "agg",
        "agg_param",
        "agg_time_dimension",
        "additivity",
        "window_choice",
        "unit",
        "verified",
    }
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "name" in fields and fields["name"] != current["name"]:
        if one(
            "SELECT measure_id FROM t_sem_measure WHERE model_id = :model_id AND name = :name AND measure_id <> :id",
            {"model_id": current["model_id"], "name": fields["name"], "id": measure_id},
        ):
            raise ConflictError("度量名称已存在", code="measure_name_exists")
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_measure SET {sets}, updated_at = now() WHERE measure_id = :id",
            {**fields, "id": measure_id},
        )
        execute(
            "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
            {"id": current["model_id"]},
        )
    return get_measure(measure_id)


def delete_measure(measure_id: int) -> None:
    current = get_measure(measure_id)
    refs = one(
        "SELECT count(*) AS total FROM t_sem_metric_input WHERE input_type = 'measure' AND input_ref = :id",
        {"id": measure_id},
    )["total"]
    if refs:
        raise ConflictError("度量已被指标引用", code="measure_in_use", detail={"metric_inputs": refs})
    execute("DELETE FROM t_sem_measure WHERE measure_id = :id", {"id": measure_id})
    execute(
        "UPDATE t_sem_model SET version = version + 1, updated_at = now() WHERE model_id = :id",
        {"id": current["model_id"]},
    )