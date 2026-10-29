"""校验编排与校验历史。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.catalog_repo import load_catalog
from app.semantic.repository.db import insert, jsonb, one, rows
from app.semantic.validation.issues import has_errors
from app.semantic.validation.queryable import validate_queryable
from app.semantic.validation.semantic import validate_metric, validate_model


def _store(object_type: str, object_id: int, level: str, issues: list[Any], actor: str | None) -> dict[str, Any]:
    status = "failed" if has_errors(issues) else "passed"
    item = insert(
        """
        INSERT INTO t_sem_validation_run (object_type, object_id, level, status, issues, created_by)
        VALUES (:object_type, :object_id, :level, :status, CAST(:issues AS JSONB), :created_by)
        RETURNING run_id, created_at
        """,
        {
            "object_type": object_type,
            "object_id": object_id,
            "level": level,
            "status": status,
            "issues": jsonb([item.to_dict() for item in issues]),
            "created_by": actor,
        },
    )
    return {
        "run_id": int(item["run_id"]),
        "object_type": object_type,
        "object_id": object_id,
        "level": level,
        "status": status,
        "issues": [item.to_dict() for item in issues],
        "created_at": item["created_at"],
    }


def run_model(model_id: int, level: str, actor: str | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    issues = validate_queryable(model_id, catalog) if level == "queryable" else validate_model(model_id, catalog)
    result = _store("model", model_id, level, issues, actor)
    model = catalog.models.get(model_id)
    result["queryable"] = bool(model and model.status == "certified" and level == "queryable" and result["status"] == "passed")
    return result


def run_metric(metric_id: int, level: str, actor: str | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    metric = catalog.metrics.get(metric_id)
    if not metric:
        from app.semantic.services.errors import NotFoundError

        raise NotFoundError("指标不存在", code="metric_not_found")
    issues = validate_metric(metric, catalog)
    return _store("metric", metric_id, level, issues, actor)


def batch(models: list[int], level: str, actor: str | None = None) -> dict[str, Any]:
    results = [run_model(model_id, level, actor) for model_id in models]
    return {
        "items": results,
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
    }


def list_runs(object_type: str | None = None, object_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: dict[str, Any] = {"limit": min(max(limit, 1), 200)}
    if object_type:
        where.append("object_type = :object_type")
        params["object_type"] = object_type
    if object_id:
        where.append("object_id = :object_id")
        params["object_id"] = object_id
    return rows(
        f"""
        SELECT * FROM t_sem_validation_run
        WHERE {' AND '.join(where)}
        ORDER BY run_id DESC LIMIT :limit
        """,
        params,
    )


def impact(asset_type: str, asset_id: int) -> dict[str, Any]:
    """轻量影响分析：模型 → 指标 / 绑定；指标 → 输入指标。"""
    result: dict[str, Any] = {"asset_type": asset_type, "asset_id": asset_id, "metrics": [], "bindings": [], "dependents": []}
    if asset_type == "model":
        result["metrics"] = rows("SELECT metric_id, name, status FROM t_sem_metric WHERE model_id = :id", {"id": asset_id})
        result["bindings"] = rows("SELECT binding_id, query_ref, status FROM t_sem_binding WHERE model_id = :id", {"id": asset_id})
        result["dependents"] = rows(
            """
            SELECT DISTINCT m.metric_id, m.name
            FROM t_sem_metric m
            JOIN t_sem_metric_input i ON i.metric_id = m.metric_id AND i.input_type = 'metric'
            WHERE i.input_ref IN (SELECT metric_id FROM t_sem_metric WHERE model_id = :id)
            """,
            {"id": asset_id},
        )
    elif asset_type == "metric":
        result["dependents"] = rows(
            "SELECT DISTINCT metric_id, name FROM t_sem_metric WHERE metric_id IN (SELECT metric_id FROM t_sem_metric_input WHERE input_type = 'metric' AND input_ref = :id)",
            {"id": asset_id},
        )
        result["bindings"] = rows(
            """
            SELECT b.binding_id, b.query_ref FROM t_sem_binding b
            WHERE b.model_id = (SELECT model_id FROM t_sem_metric WHERE metric_id = :id)
            """,
            {"id": asset_id},
        )
    return result


def latest_status(object_type: str, object_id: int, level: str) -> str | None:
    item = one(
        """
        SELECT status FROM t_sem_validation_run
        WHERE object_type = :object_type AND object_id = :object_id AND level = :level
        ORDER BY run_id DESC LIMIT 1
        """,
        {"object_type": object_type, "object_id": object_id, "level": level},
    )
    return item["status"] if item else None