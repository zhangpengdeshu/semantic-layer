"""指标服务：指标组合、输入解析、依赖环与指纹。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.semantic.repository.db import execute, insert, one, page_params, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

METRIC_TYPES = {"simple", "ratio", "derived", "cumulative", "conversion"}
INPUT_TYPES = {"metric", "measure"}
INPUT_ROLES = {"numerator", "denominator", "input", "base", "conversion"}


def _ensure_metric(metric_id: int) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_metric WHERE metric_id = :id", {"id": metric_id})
    if not item:
        raise NotFoundError("指标不存在", code="metric_not_found")
    return item


def _inputs(metric_id: int) -> list[dict[str, Any]]:
    return rows(
        "SELECT * FROM t_sem_metric_input WHERE metric_id = :id ORDER BY position, input_type, input_ref",
        {"id": metric_id},
    )


def _input_names(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        if item["input_type"] == "metric":
            ref = one(
                "SELECT name, business_name, metric_type FROM t_sem_metric WHERE metric_id = :id",
                {"id": item["input_ref"]},
            )
        else:
            ref = one(
                "SELECT name, business_name, agg FROM t_sem_measure WHERE measure_id = :id",
                {"id": item["input_ref"]},
            )
        result.append({**item, "input_name": (ref or {}).get("name"), "input_business_name": (ref or {}).get("business_name")})
    return result


def _validate_inputs(metric_type: str, inputs: list[dict[str, Any]], metric_id: int | None = None) -> None:
    seen: set[tuple[str, int, str]] = set()
    for item in inputs:
        if item["input_type"] not in INPUT_TYPES:
            raise ValidationFailedError("非法 input_type", code="invalid_metric_input_type")
        if item["role"] not in INPUT_ROLES:
            raise ValidationFailedError("非法 input role", code="invalid_metric_input_role")
        key = (item["input_type"], int(item["input_ref"]), item["role"])
        if key in seen:
            raise ValidationFailedError("指标输入重复", code="duplicate_metric_input")
        seen.add(key)
        table = "t_sem_metric" if item["input_type"] == "metric" else "t_sem_measure"
        id_col = "metric_id" if item["input_type"] == "metric" else "measure_id"
        if not one(f"SELECT {id_col} FROM {table} WHERE {id_col} = :id", {"id": item["input_ref"]}):
            raise ValidationFailedError("指标输入不存在", code="metric_input_missing", detail=item)
        if item["input_type"] == "metric" and int(item["input_ref"]) == (metric_id or 0):
            raise ValidationFailedError("指标不能引用自身", code="metric_cycle")

    roles = {item["role"] for item in inputs}
    if metric_type == "simple" and not inputs:
        raise ValidationFailedError("simple 指标至少需要一个输入", code="metric_input_missing")
    if metric_type == "ratio" and not {"numerator", "denominator"}.issubset(roles):
        raise ValidationFailedError("ratio 指标必须包含分子和分母", code="ratio_input_missing")
    if metric_type == "conversion" and not {"base", "conversion"}.issubset(roles):
        raise ValidationFailedError("conversion 指标必须包含 base 和 conversion", code="conversion_input_missing")


def _check_cycle(metric_id: int) -> None:
    """DFS 检查指标依赖环。"""
    state: dict[int, int] = {}

    def visit(current: int) -> None:
        if state.get(current) == 1:
            raise ValidationFailedError("指标依赖存在环", code="metric_cycle")
        if state.get(current) == 2:
            return
        state[current] = 1
        for item in _inputs(current):
            if item["input_type"] == "metric":
                visit(int(item["input_ref"]))
        state[current] = 2

    visit(metric_id)


def _replace_inputs(metric_id: int, inputs: list[dict[str, Any]]) -> None:
    execute("DELETE FROM t_sem_metric_input WHERE metric_id = :id", {"id": metric_id})
    for position, item in enumerate(inputs, start=1):
        execute(
            """
            INSERT INTO t_sem_metric_input (metric_id, input_type, input_ref, role, position)
            VALUES (:metric_id, :input_type, :input_ref, :role, :position)
            """,
            {
                "metric_id": metric_id,
                "input_type": item["input_type"],
                "input_ref": item["input_ref"],
                "role": item["role"],
                "position": item.get("position", position),
            },
        )


def get_metric(metric_id: int) -> dict[str, Any]:
    item = _ensure_metric(metric_id)
    item["inputs"] = _input_names(_inputs(metric_id))
    return item


def list_metrics(
    q: str | None = None,
    metric_type: str | None = None,
    status: str | None = None,
    domain_id: int | None = None,
    model_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page, page_size = page_params(page, page_size)
    where = ["1=1"]
    params: dict[str, Any] = {}
    if q:
        where.append("(m.name ILIKE :q OR m.business_name ILIKE :q OR m.definition ILIKE :q)")
        params["q"] = f"%{q}%"
    if metric_type:
        where.append("m.metric_type = :metric_type")
        params["metric_type"] = metric_type
    if status:
        where.append("m.status = :status")
        params["status"] = status
    if domain_id:
        where.append("m.domain_id = :domain_id")
        params["domain_id"] = domain_id
    if model_id:
        where.append("m.model_id = :model_id")
        params["model_id"] = model_id
    clause = " AND ".join(where)
    total = one(f"SELECT count(*) AS total FROM t_sem_metric m WHERE {clause}", params)["total"]
    items = rows(
        f"""
        SELECT m.*, d.name AS domain_name, sm.name AS model_name
        FROM t_sem_metric m
        LEFT JOIN t_sem_domain d ON d.domain_id = m.domain_id
        LEFT JOIN t_sem_model sm ON sm.model_id = m.model_id
        WHERE {clause}
        ORDER BY m.metric_id DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    )
    for item in items:
        item["inputs"] = _input_names(_inputs(int(item["metric_id"])))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def create_metric(payload: dict[str, Any]) -> dict[str, Any]:
    metric_type = payload.get("metric_type", "simple")
    if metric_type not in METRIC_TYPES:
        raise ValidationFailedError("非法 metric_type", code="invalid_metric_type")
    inputs = payload.get("inputs") or []
    _validate_inputs(metric_type, inputs)
    if one("SELECT metric_id FROM t_sem_metric WHERE name = :name", {"name": payload["name"]}):
        raise ConflictError("指标名称已存在", code="metric_name_exists")
    item = insert(
        """
        INSERT INTO t_sem_metric
          (model_id, name, business_name, synonyms, definition, metric_type, filter, window_spec,
           grain_to_date, unit, scale, domain_id, owner, valid_from, valid_to)
        VALUES
          (:model_id, :name, :business_name, CAST(:synonyms AS TEXT[]), :definition, :metric_type, :filter, :window_spec,
           :grain_to_date, :unit, :scale, :domain_id, :owner, :valid_from, :valid_to)
        RETURNING metric_id
        """,
        {
            "model_id": payload.get("model_id"),
            "name": payload["name"],
            "business_name": payload.get("business_name"),
            "synonyms": payload.get("synonyms") or [],
            "definition": payload.get("definition"),
            "metric_type": metric_type,
            "filter": payload.get("filter"),
            "window_spec": payload.get("window_spec"),
            "grain_to_date": payload.get("grain_to_date"),
            "unit": payload.get("unit"),
            "scale": payload.get("scale", 2),
            "domain_id": payload.get("domain_id"),
            "owner": payload.get("owner"),
            "valid_from": payload.get("valid_from"),
            "valid_to": payload.get("valid_to"),
        },
    )
    metric_id = int(item["metric_id"])
    _replace_inputs(metric_id, inputs)
    _check_cycle(metric_id)
    return get_metric(metric_id)


def update_metric(metric_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = _ensure_metric(metric_id)
    metric_type = payload.get("metric_type", current["metric_type"])
    if metric_type not in METRIC_TYPES:
        raise ValidationFailedError("非法 metric_type", code="invalid_metric_type")
    inputs = payload.get("inputs")
    if inputs is not None:
        _validate_inputs(metric_type, inputs, metric_id)
    allowed = {
        "model_id",
        "name",
        "business_name",
        "synonyms",
        "definition",
        "metric_type",
        "filter",
        "window_spec",
        "grain_to_date",
        "unit",
        "scale",
        "domain_id",
        "owner",
        "valid_from",
        "valid_to",
        "status",
    }
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if "name" in fields and fields["name"] != current["name"]:
        if one("SELECT metric_id FROM t_sem_metric WHERE name = :name AND metric_id <> :id", {"name": fields["name"], "id": metric_id}):
            raise ConflictError("指标名称已存在", code="metric_name_exists")
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(
            f"UPDATE t_sem_metric SET {sets}, version = version + 1, updated_at = now() WHERE metric_id = :id",
            {**fields, "id": metric_id},
        )
    if inputs is not None:
        _replace_inputs(metric_id, inputs)
    _check_cycle(metric_id)
    return get_metric(metric_id)


def delete_metric(metric_id: int) -> None:
    _ensure_metric(metric_id)
    refs = one(
        "SELECT count(*) AS total FROM t_sem_metric_input WHERE input_type = 'metric' AND input_ref = :id",
        {"id": metric_id},
    )["total"]
    if refs:
        raise ConflictError("指标被其他指标引用", code="metric_in_use", detail={"metric_inputs": refs})
    execute("DELETE FROM t_sem_metric WHERE metric_id = :id", {"id": metric_id})


def dependency_graph(metric_id: int) -> dict[str, Any]:
    _ensure_metric(metric_id)
    nodes: dict[int, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def visit(current: int) -> None:
        if current in nodes:
            return
        metric = one("SELECT metric_id, name, business_name, metric_type FROM t_sem_metric WHERE metric_id = :id", {"id": current})
        if not metric:
            return
        nodes[current] = dict(metric)
        for item in _inputs(current):
            if item["input_type"] == "metric":
                edges.append({"from": current, "to": int(item["input_ref"]), "role": item["role"]})
                visit(int(item["input_ref"]))

    visit(metric_id)
    return {"nodes": list(nodes.values()), "edges": edges}


def fingerprint(metric_id: int) -> str:
    metric = get_metric(metric_id)
    payload = {
        "metric": {key: metric.get(key) for key in ("metric_id", "name", "metric_type", "definition", "filter", "unit", "scale", "model_id")},
        "inputs": metric.get("inputs") or [],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()