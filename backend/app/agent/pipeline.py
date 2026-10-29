"""规则版问数流水线：语义命中 → 绑定解析 → JOIN 规划 → 编译 → 执行 → 解释。

一期不引入 LLM；意图识别使用指标/维度/术语词典与时间表达规则。
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from shared.config import settings
from shared.db import read_session

from app.agent.comparison import detect_compare, merge_comparison, shift_time
from app.platform import permission
from app.semantic.compiler.contracts import CompileError, QueryIR, TimeRange
from app.semantic.compiler.sql import compile_query
from app.semantic.domain.entities import Metric, SemanticCatalog
from app.semantic.repository.catalog_repo import load_catalog, load_catalog_from_snapshot
from app.semantic.repository.db import execute, jsonb
from app.semantic.services import release_service

REGIONS = ["华东", "华北", "华南", "华中", "西南", "西北", "东北"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _match_metrics(question: str, catalog: SemanticCatalog, domain_id: int | None) -> list[Metric]:
    matches: list[tuple[int, Metric]] = []
    for metric in catalog.metrics.values():
        if metric.status != "certified":
            continue
        if domain_id and metric.domain_id and metric.domain_id != domain_id:
            continue
        names = {metric.name, metric.business_name, *metric.synonyms}
        hits = [name for name in names if name and name in question]
        if hits:
            matches.append((max(len(item) for item in hits), metric))
    matches.sort(key=lambda item: (-item[0], item[1].metric_id))
    return [item[1] for item in matches]


def _match_dimensions(question: str, catalog: SemanticCatalog) -> list[Any]:
    matches = []
    for dimension in catalog.dimensions.values():
        field = catalog.fields.get(dimension.field_id)
        names = {dimension.name}
        if field:
            names.update({field.name, field.business_name})
        hit = any(name and name in question for name in names)
        if not hit:
            # 单字标签（如风险等级的「高/中/低」）极易误命中，只匹配 2 字以上标签
            labels = {str(label) for label in (dimension.code_mapping or {}).values() if len(str(label)) >= 2}
            hit = any(label and label in question for label in labels)
        if not hit and dimension.name in {"区域", "region", "大区"}:
            hit = any(region in question for region in REGIONS)
        if hit:
            matches.append(dimension)
    # 「机构类型」会同时命中「机构」，「渠道类型」会同时命中「渠道」，
    # 这里去掉被更长维度名包含的短名，避免多分一组维度。
    unique = {item.name: item for item in matches}
    return [
        item
        for name, item in unique.items()
        if not any(name != other and name in other for other in unique)
    ]


def _match_filters(question: str, catalog: SemanticCatalog, dimensions: list[Any]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for dimension in dimensions:
        for code, label in (dimension.code_mapping or {}).items():
            if len(str(label)) >= 2 and str(label) in question:
                filters.append({"field": dimension.name, "op": "=", "value": code})
        for region in REGIONS:
            if region in question and dimension.name in {"区域", "region", "大区"}:
                filters.append({"field": dimension.name, "op": "=", "value": region})
    # 去重
    seen = set()
    result = []
    for item in filters:
        key = (item["field"], item["op"], str(item["value"]))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _detect_time(question: str) -> TimeRange | None:
    today = _now().date()
    if "上月" in question or "上个月" in question:
        first = today.replace(day=1)
        previous_end = first
        previous_start = (first - timedelta(days=1)).replace(day=1)
        return TimeRange(start=previous_start, end=previous_end, grain="day")
    if "本月" in question or "这个月" in question:
        start, end = _month_range(today.year, today.month)
        return TimeRange(start=start, end=end, grain="day")
    if "今年" in question or "本年" in question:
        return TimeRange(start=date(today.year, 1, 1), end=date(today.year + 1, 1, 1), grain="month")
    if "去年" in question:
        return TimeRange(start=date(today.year - 1, 1, 1), end=date(today.year, 1, 1), grain="month")
    match = re.search(r"(\d{4})[-年](\d{1,2})月?", question)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            start, end = _month_range(year, month)
            return TimeRange(start=start, end=end, grain="day")
    match = re.search(r"(\d{4})年", question)
    if match:
        year = int(match.group(1))
        return TimeRange(start=date(year, 1, 1), end=date(year + 1, 1, 1), grain="month")
    return None


def build_query_ir(question: str, catalog: SemanticCatalog, domain_id: int | None = None) -> QueryIR:
    metrics = _match_metrics(question, catalog, domain_id)
    if not metrics:
        raise CompileError(
            "metric_not_found",
            "没有识别到已认证指标，请补充指标名称或先完成指标认证",
            detail={"question": question},
        )
    dimensions = _match_dimensions(question, catalog)
    # 同名维度可能来自多个模型，按名称去重，交给编译器优先解析 base 模型
    dimension_names = list(dict.fromkeys(item.name for item in dimensions))
    filters = _match_filters(question, catalog, dimensions)
    time_range = _detect_time(question)
    compare = detect_compare(question)
    if compare and not time_range:
        today = _now().date()
        start, end = _month_range(today.year, today.month)
        time_range = TimeRange(start=start, end=end, grain="day")
        compare.defaulted_time = True
    return QueryIR(
        metrics=[item.name for item in metrics],
        dimensions=dimension_names,
        filters=filters,
        time=time_range,
        compare=compare,
        limit=settings.max_result_rows,
    )


def _execute(sql: str, limit: int | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    row_limit = int(limit or settings.max_result_rows)
    with read_session() as session:
        session.execute(text(f"SET LOCAL statement_timeout = {int(settings.query_timeout_ms)}"))
        result = session.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchmany(row_limit)]
    return columns, rows


def _mask_value(value: Any) -> Any:
    if value is None:
        return None
    text_value = str(value)
    if len(text_value) <= 2:
        return "**"
    if len(text_value) <= 6:
        return text_value[0] + "*" * (len(text_value) - 2) + text_value[-1]
    return text_value[:2] + "*" * (len(text_value) - 4) + text_value[-2:]


def _mask_rows(rows: list[dict[str, Any]], pii_columns: list[str]) -> list[dict[str, Any]]:
    if not pii_columns:
        return rows
    for row in rows:
        for column in pii_columns:
            if column in row:
                row[column] = _mask_value(row[column])
    return rows


def _catalog_for_ask() -> tuple[SemanticCatalog, str | None, bool]:
    """问数读路径：优先 active 快照，缺失时回退 live 并标记。"""
    snapshot = release_service.active_snapshot()
    if snapshot:
        payload = release_service.get_snapshot(snapshot["version"])["payload"]
        return load_catalog_from_snapshot(payload, snapshot["version"]), snapshot["version"], False
    return load_catalog(), None, True


def _log(
    request_id: str,
    user_id: str | None,
    question: str,
    query_ir: dict[str, Any] | None,
    compiled: Any,
    snapshot_version: str | None,
    row_count: int | None,
    elapsed_ms: int | None,
    status: str,
    error_code: str | None = None,
) -> None:
    try:
        # 日志表无 RETURNING，必须用 execute；insert() 期望返回行会抛错
        execute(
            """
            INSERT INTO t_query_log
              (request_id, user_id, question, normalized_question, metric_ids, model_ids, binding_ids,
               query_ir, sql, snapshot_version, row_count, elapsed_ms, status, error_code)
            VALUES
              (:request_id, :user_id, :question, :normalized_question, CAST(:metric_ids AS BIGINT[]), CAST(:model_ids AS BIGINT[]), CAST(:binding_ids AS BIGINT[]),
               CAST(:query_ir AS JSONB), :sql, :snapshot_version, :row_count, :elapsed_ms, :status, :error_code)
            """,
            {
                "request_id": request_id,
                "user_id": user_id,
                "question": question,
                "normalized_question": question.strip(),
                "metric_ids": compiled.metric_ids if compiled else [],
                "model_ids": compiled.model_ids if compiled else [],
                "binding_ids": compiled.binding_ids if compiled else [],
                "query_ir": jsonb(query_ir or {}),
                "sql": compiled.sql if compiled else None,
                "snapshot_version": snapshot_version,
                "row_count": row_count,
                "elapsed_ms": elapsed_ms,
                "status": status,
                "error_code": error_code,
            },
        )
    except Exception:
        # 日志失败不影响问数结果
        return


def ask(
    question: str,
    user_id: str | None = None,
    domain_id: int | None = None,
    roles: list[str] | None = None,
) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    started = _now()
    catalog, snapshot_version, live_fallback = _catalog_for_ask()
    permissions = permission.context_for(user_id, roles)
    query_ir: QueryIR | None = None
    try:
        query_ir = build_query_ir(question, catalog, domain_id)
        compiled = compile_query(query_ir, catalog, permissions=permissions)
        if live_fallback:
            compiled.warnings.append("没有 active 快照，本次问数回退到 live 目录")
        columns, rows = _execute(compiled.sql)
        rows = _mask_rows(rows, compiled.pii_columns)
        comparison_payload = None
        if query_ir.compare:
            base_ir = query_ir.model_copy(update={"time": shift_time(query_ir.time, query_ir.compare)})
            base_compiled = compile_query(base_ir, catalog, permissions=permissions)
            _, base_rows = _execute(base_compiled.sql)
            base_rows = _mask_rows(base_rows, base_compiled.pii_columns)
            metric_types = {}
            for name in query_ir.metrics:
                metric = catalog.metric_by_name(name)
                if metric:
                    metric_types[name] = metric.metric_type
            columns, rows, missing_base = merge_comparison(
                columns,
                rows,
                base_rows,
                query_ir.dimensions,
                query_ir.metrics,
                metric_types,
            )
            if query_ir.compare.defaulted_time:
                compiled.warnings.append("未指定时间范围，同比/环比默认使用本月")
            if missing_base:
                compiled.warnings.append(f"{missing_base} 个维度组合在基期没有数据")
            comparison_payload = {
                "type": query_ir.compare.type,
                "label": query_ir.compare.label,
                "base_start": base_ir.time.start.isoformat() if base_ir.time and base_ir.time.start else None,
                "base_end": base_ir.time.end.isoformat() if base_ir.time and base_ir.time.end else None,
                "sql": base_compiled.sql,
                "base_row_count": len(base_rows),
            }
        elapsed = int((_now() - started).total_seconds() * 1000)
        _log(request_id, user_id, question, query_ir.model_dump(), compiled, snapshot_version, len(rows), elapsed, "ok")
        return {
            "request_id": request_id,
            "status": "ok",
            "mode": "semantic",
            "clarification": None,
            "result": {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "sql": compiled.sql,
                "metric_ids": compiled.metric_ids,
                "model_ids": compiled.model_ids,
                "binding_ids": compiled.binding_ids,
                "warnings": compiled.warnings,
                "explanation": compiled.explanation,
                "snapshot_version": snapshot_version,
                "elapsed_ms": elapsed,
                "comparison": comparison_payload,
            },
        }
    except CompileError as exc:
        elapsed = int((_now() - started).total_seconds() * 1000)
        _log(request_id, user_id, question, query_ir.model_dump() if query_ir else None, None, snapshot_version, None, elapsed, "clarification", exc.code)
        return {
            "request_id": request_id,
            "status": "clarification",
            "mode": "semantic",
            "clarification": {"code": exc.code, "message": exc.message, "detail": exc.detail},
            "result": None,
        }
    except Exception as exc:
        elapsed = int((_now() - started).total_seconds() * 1000)
        _log(request_id, user_id, question, query_ir.model_dump() if query_ir else None, None, snapshot_version, None, elapsed, "failed", "query_execution_failed")
        return {
            "request_id": request_id,
            "status": "failed",
            "mode": "semantic",
            "clarification": {"code": "query_execution_failed", "message": str(exc), "detail": None},
            "result": None,
        }


def compile_preview(question: str | None = None, query_ir: QueryIR | None = None, domain_id: int | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    ir = query_ir or build_query_ir(question or "", catalog, domain_id)
    compiled = compile_query(ir, catalog)
    payload = {"query_ir": ir.model_dump(), "compiled": compiled.model_dump()}
    if ir.compare and ir.time:
        base_ir = ir.model_copy(update={"time": shift_time(ir.time, ir.compare)})
        base_compiled = compile_query(base_ir, catalog)
        payload["comparison"] = {
            "type": ir.compare.type,
            "label": ir.compare.label,
            "base_start": base_ir.time.start.isoformat() if base_ir.time.start else None,
            "base_end": base_ir.time.end.isoformat() if base_ir.time.end else None,
            "compiled": base_compiled.model_dump(),
        }
    return payload