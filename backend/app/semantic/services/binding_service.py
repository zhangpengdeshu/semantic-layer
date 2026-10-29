"""绑定服务：主绑定、字段映射、自动映射与漂移。"""

from __future__ import annotations

import difflib
import re
from typing import Any

from app.semantic.repository.db import execute, execute_many, insert, one, rows
from app.semantic.services import catalog_service
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

BINDING_TYPES = {"dataset", "table", "view", "subquery"}
BINDING_STATUSES = {"draft", "certified", "disabled"}


def _get(binding_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_binding WHERE binding_id = :id", {"id": binding_id})
    if not item:
        raise NotFoundError("数据绑定不存在", code="binding_not_found")
    return item


def _ensure_model(model_id: int) -> None:
    if not one("SELECT model_id FROM t_sem_model WHERE model_id = :id", {"id": model_id}):
        raise NotFoundError("语义模型不存在", code="model_not_found")


def _normalize(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", name).lower()


def _coverage(model_id: int, binding_id: int) -> dict[str, Any]:
    total = one(
        "SELECT count(*) AS total FROM t_sem_field WHERE model_id = :id AND is_hidden = FALSE",
        {"id": model_id},
    )["total"]
    mapped = one(
        """
        SELECT count(*) AS total FROM t_sem_field_binding fb
        JOIN t_sem_field f ON f.field_id = fb.field_id
        WHERE fb.binding_id = :binding_id AND f.is_hidden = FALSE
        """,
        {"binding_id": binding_id},
    )["total"]
    return {
        "visible_fields": int(total),
        "mapped_fields": int(mapped),
        "coverage": (int(mapped) / int(total)) if total else 0.0,
    }


def _enrich(binding: dict[str, Any]) -> dict[str, Any]:
    binding.update(_coverage(int(binding["model_id"]), int(binding["binding_id"])))
    drift = drift_check(int(binding["binding_id"]))
    binding["drifted"] = drift["drifted"]
    binding["drift"] = drift
    return binding


def list_bindings(model_id: int) -> list[dict[str, Any]]:
    _ensure_model(model_id)
    items = rows("SELECT * FROM t_sem_binding WHERE model_id = :id ORDER BY priority, binding_id", {"id": model_id})
    return [_enrich(item) for item in items]


def get_binding(binding_id: int) -> dict[str, Any]:
    return _enrich(_get(binding_id))


def create_binding(model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_model(model_id)
    binding_type = payload.get("binding_type", "dataset")
    if binding_type not in BINDING_TYPES:
        raise ValidationFailedError("非法 binding_type", code="invalid_binding_type")
    status = payload.get("status", "draft")
    if status not in BINDING_STATUSES:
        raise ValidationFailedError("非法绑定状态", code="invalid_binding_status")
    if not payload.get("query_ref"):
        raise ValidationFailedError("query_ref 不能为空", code="query_ref_missing")
    if one(
        """
        SELECT binding_id FROM t_sem_binding
        WHERE model_id = :model_id AND binding_type = :binding_type AND query_ref = :query_ref
        """,
        {"model_id": model_id, "binding_type": binding_type, "query_ref": payload["query_ref"]},
    ):
        raise ConflictError("绑定已存在", code="binding_exists")
    is_primary = bool(payload.get("is_primary", False))
    item = insert(
        """
        INSERT INTO t_sem_binding
          (model_id, binding_type, source_system, external_dataset_id, table_id, query_ref, alias,
           is_primary, priority, row_filter, status, source_version, verified)
        VALUES
          (:model_id, :binding_type, :source_system, :external_dataset_id, :table_id, :query_ref, :alias,
           :is_primary, :priority, :row_filter, :status, :source_version, :verified)
        RETURNING binding_id
        """,
        {
            "model_id": model_id,
            "binding_type": binding_type,
            "source_system": payload.get("source_system"),
            "external_dataset_id": payload.get("external_dataset_id"),
            "table_id": payload.get("table_id"),
            "query_ref": payload["query_ref"],
            "alias": payload.get("alias"),
            "is_primary": is_primary,
            "priority": payload.get("priority", 100),
            "row_filter": payload.get("row_filter"),
            "status": status,
            "source_version": payload.get("source_version"),
            "verified": bool(payload.get("verified", False)),
        },
    )
    binding_id = int(item["binding_id"])
    if is_primary:
        set_primary(binding_id)
    return get_binding(binding_id)


def update_binding(binding_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = _get(binding_id)
    if payload.get("binding_type") and payload["binding_type"] not in BINDING_TYPES:
        raise ValidationFailedError("非法 binding_type", code="invalid_binding_type")
    if payload.get("status") and payload["status"] not in BINDING_STATUSES:
        raise ValidationFailedError("非法绑定状态", code="invalid_binding_status")
    allowed = {
        "binding_type",
        "source_system",
        "external_dataset_id",
        "table_id",
        "query_ref",
        "alias",
        "is_primary",
        "priority",
        "row_filter",
        "status",
        "source_version",
        "verified",
    }
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_binding SET {sets}, updated_at = now() WHERE binding_id = :id",
            {**fields, "id": binding_id},
        )
    if payload.get("is_primary"):
        set_primary(binding_id)
    elif payload.get("is_primary") is False and current.get("is_primary"):
        execute("UPDATE t_sem_binding SET is_primary = FALSE WHERE binding_id = :id", {"id": binding_id})
    return get_binding(binding_id)


def delete_binding(binding_id: int) -> None:
    _get(binding_id)
    execute("DELETE FROM t_sem_binding WHERE binding_id = :id", {"id": binding_id})


def set_primary(binding_id: int) -> dict[str, Any]:
    current = _get(binding_id)
    execute_many(
        [
            (
                "UPDATE t_sem_binding SET is_primary = FALSE WHERE model_id = :model_id",
                {"model_id": current["model_id"]},
            ),
            (
                "UPDATE t_sem_binding SET is_primary = TRUE, updated_at = now() WHERE binding_id = :id",
                {"id": binding_id},
            ),
        ]
    )
    return get_binding(binding_id)


def available_columns(binding_id: int) -> list[dict[str, Any]]:
    binding = _get(binding_id)
    return catalog_service.columns_for_binding(binding)


def get_field_mappings(binding_id: int) -> dict[str, Any]:
    binding = _get(binding_id)
    fields = rows(
        "SELECT * FROM t_sem_field WHERE model_id = :id ORDER BY field_id",
        {"id": binding["model_id"]},
    )
    mappings = rows("SELECT * FROM t_sem_field_binding WHERE binding_id = :id", {"id": binding_id})
    by_field = {int(item["field_id"]): item for item in mappings}
    items = []
    for field in fields:
        mapping = by_field.get(int(field["field_id"]))
        items.append(
            {
                "field_id": field["field_id"],
                "field_name": field["name"],
                "business_name": field.get("business_name"),
                "semantic_type": field.get("semantic_type"),
                "data_type": field.get("data_type"),
                "is_hidden": field.get("is_hidden"),
                "column_name": (mapping or {}).get("column_name"),
                "column_id": (mapping or {}).get("column_id"),
                "transform": (mapping or {}).get("transform"),
                "status": (mapping or {}).get("status", "unmapped"),
            }
        )
    return {"binding": _enrich(binding), "items": items, **_coverage(int(binding["model_id"]), binding_id)}


def put_field_mappings(binding_id: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    binding = _get(binding_id)
    fields = {
        int(item["field_id"]): item
        for item in rows("SELECT * FROM t_sem_field WHERE model_id = :id", {"id": binding["model_id"]})
    }
    for item in items:
        field_id = int(item["field_id"])
        if field_id not in fields:
            raise ValidationFailedError("字段不属于当前模型", code="field_not_in_model", detail=item)
        if not item.get("column_name"):
            raise ValidationFailedError("column_name 不能为空", code="column_name_missing", detail=item)
        execute(
            """
            INSERT INTO t_sem_field_binding
              (binding_id, field_id, column_id, column_name, transform, status)
            VALUES
              (:binding_id, :field_id, :column_id, :column_name, :transform, :status)
            ON CONFLICT (binding_id, field_id) DO UPDATE SET
              column_id = EXCLUDED.column_id,
              column_name = EXCLUDED.column_name,
              transform = EXCLUDED.transform,
              status = EXCLUDED.status,
              updated_at = now()
            """,
            {
                "binding_id": binding_id,
                "field_id": field_id,
                "column_id": item.get("column_id"),
                "column_name": item["column_name"],
                "transform": item.get("transform"),
                "status": item.get("status", "draft"),
            },
        )
    return get_field_mappings(binding_id)


def auto_map(binding_id: int) -> dict[str, Any]:
    binding = _get(binding_id)
    fields = rows(
        "SELECT * FROM t_sem_field WHERE model_id = :id AND is_hidden = FALSE ORDER BY field_id",
        {"id": binding["model_id"]},
    )
    mapped_ids = {
        int(item["field_id"])
        for item in rows("SELECT field_id FROM t_sem_field_binding WHERE binding_id = :id", {"id": binding_id})
    }
    columns = catalog_service.columns_for_binding(binding)
    if not columns:
        return {"mapped": 0, "items": [], "message": "当前绑定没有可用的物理列，请先同步数据集目录"}

    used: set[str] = set()
    created: list[dict[str, Any]] = []
    for field in fields:
        if int(field["field_id"]) in mapped_ids:
            continue
        best: tuple[float, dict[str, Any]] | None = None
        for column in columns:
            if column["column_name"] in used:
                continue
            score = _score(field, column)
            if best is None or score > best[0]:
                best = (score, column)
        if not best or best[0] < 0.55:
            continue
        score, column = best
        used.add(column["column_name"])
        execute(
            """
            INSERT INTO t_sem_field_binding (binding_id, field_id, column_id, column_name, transform, status)
            VALUES (:binding_id, :field_id, :column_id, :column_name, NULL, 'draft')
            ON CONFLICT (binding_id, field_id) DO UPDATE SET
              column_id = EXCLUDED.column_id,
              column_name = EXCLUDED.column_name,
              status = EXCLUDED.status,
              updated_at = now()
            """,
            {
                "binding_id": binding_id,
                "field_id": field["field_id"],
                "column_id": column.get("column_id"),
                "column_name": column["column_name"],
            },
        )
        created.append(
            {
                "field_id": field["field_id"],
                "field_name": field["name"],
                "column_name": column["column_name"],
                "confidence": round(score, 2),
            }
        )
    return {"mapped": len(created), "items": created, **get_field_mappings(binding_id)}


def _score(field: dict[str, Any], column: dict[str, Any]) -> float:
    field_name = field["name"]
    column_name = column["column_name"]
    score = 0.0
    if field_name == column_name:
        score = 1.0
    elif field.get("business_name") and field["business_name"] == column.get("business_name"):
        score = 0.95
    elif column_name in (field.get("synonyms") or []):
        score = 0.9
    elif _normalize(field_name) == _normalize(column_name):
        score = 0.85
    else:
        score = difflib.SequenceMatcher(None, _normalize(field_name), _normalize(column_name)).ratio() * 0.8
    if score >= 0.85 and not _type_compatible(field.get("data_type"), column.get("column_type")):
        score -= 0.2
    return max(score, 0.0)


def _type_compatible(field_type: str | None, column_type: str | None) -> bool:
    if not field_type or field_type == "unknown" or not column_type:
        return True
    column_type = column_type.lower()
    if field_type == "number":
        return any(token in column_type for token in ("int", "numeric", "decimal", "float", "double", "real"))
    if field_type == "date":
        return any(token in column_type for token in ("date", "time"))
    if field_type == "boolean":
        return "bool" in column_type
    if field_type == "string":
        return any(token in column_type for token in ("char", "text", "string", "varchar"))
    return True


def drift_check(binding_id: int) -> dict[str, Any]:
    binding = _get(binding_id)
    columns = catalog_service.columns_for_binding(binding)
    if not columns:
        return {"drifted": False, "missing": [], "type_mismatch": [], "new_columns": [], "message": "目录暂不可用"}
    column_names = {item["column_name"] for item in columns}
    column_types = {item["column_name"]: item.get("column_type") for item in columns}
    mappings = rows(
        """
        SELECT fb.*, f.name AS field_name, f.data_type AS field_type
        FROM t_sem_field_binding fb
        JOIN t_sem_field f ON f.field_id = fb.field_id
        WHERE fb.binding_id = :id
        """,
        {"id": binding_id},
    )
    missing = [item["field_name"] for item in mappings if item["column_name"] not in column_names]
    type_mismatch = [
        {"field": item["field_name"], "column": item["column_name"], "field_type": item.get("field_type"), "column_type": column_types.get(item["column_name"])}
        for item in mappings
        if item["column_name"] in column_names and not _type_compatible(item.get("field_type"), column_types.get(item["column_name"]))
    ]
    mapped_names = {item["column_name"] for item in mappings}
    new_columns = [name for name in column_names if name not in mapped_names]
    return {
        "drifted": bool(missing or type_mismatch),
        "missing": missing,
        "type_mismatch": type_mismatch,
        "new_columns": new_columns,
        "message": "" if not (missing or type_mismatch) else "绑定与物理目录不一致",
    }