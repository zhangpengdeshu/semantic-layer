"""物理计划构建：QueryIR + 语义目录 + 权限上下文 → PhysicalPlan。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.config import settings

from app.semantic.compiler.contracts import (
    CompileError,
    PermissionContext,
    PhysicalPlan,
    PlanColumn,
    PlanJoin,
    PlanOrder,
    QueryIR,
)
from app.semantic.domain.entities import (
    Binding,
    Field,
    Measure,
    Metric,
    MetricInput,
    SemanticCatalog,
)
from app.semantic.planning.binding_resolver import (
    alias_for,
    field_expr,
    primary_binding,
    quote_ident,
    resolve_dimension,
    resolve_filter_expr,
    table_ref,
)
from app.semantic.planning.errors import PlanError
from app.semantic.planning.join_planner import Step, distances, plan as plan_joins

AGG_FUNCS = {"sum", "count", "count_distinct", "avg", "min", "max", "median", "percentile"}
TIME_GRAINS = {"day", "week", "month", "quarter", "year"}
WINDOW_SPEC = re.compile(r"^\s*(\d+)\s*(day|week|month|quarter|year)s?\s*$", re.IGNORECASE)


@dataclass(slots=True)
class WindowContext:
    time_expr: str
    partition_exprs: list[str]


def _metric_by_ref(ref: str | int, catalog: SemanticCatalog) -> Metric:
    if isinstance(ref, int) or str(ref).isdigit():
        metric = catalog.metrics.get(int(ref))
    else:
        metric = catalog.metric_by_name(str(ref))
    if not metric:
        raise CompileError("metric_not_found", f"指标 {ref} 不存在")
    return metric


def _metric_base_model(metric: Metric, catalog: SemanticCatalog, stack: tuple[int, ...] = ()) -> int:
    if metric.metric_id in stack:
        raise CompileError("metric_cycle", f"指标 {metric.name} 存在依赖环")
    if metric.model_id:
        return metric.model_id
    for item in metric.inputs:
        if item.input_type == "measure":
            measure = catalog.measures.get(int(item.input_ref))
            if measure:
                return measure.model_id
        elif item.input_type == "metric":
            child = catalog.metrics.get(int(item.input_ref))
            if child:
                return _metric_base_model(child, catalog, stack + (metric.metric_id,))
    raise CompileError("metric_model_missing", f"无法确定指标 {metric.name} 的归属模型")


def _collect_measure_models(metric: Metric, catalog: SemanticCatalog, result: set[int], stack: tuple[int, ...] = ()) -> None:
    if metric.metric_id in stack:
        return
    for item in metric.inputs:
        if item.input_type == "measure":
            measure = catalog.measures.get(int(item.input_ref))
            if measure:
                result.add(measure.model_id)
        elif item.input_type == "metric":
            child = catalog.metrics.get(int(item.input_ref))
            if child:
                _collect_measure_models(child, catalog, result, stack + (metric.metric_id,))


def _metric_measures(metric: Metric, catalog: SemanticCatalog, result: list[Measure], stack: tuple[int, ...] = ()) -> None:
    if metric.metric_id in stack:
        return
    for item in metric.inputs:
        if item.input_type == "measure":
            measure = catalog.measures.get(int(item.input_ref))
            if measure and measure not in result:
                result.append(measure)
        elif item.input_type == "metric":
            child = catalog.metrics.get(int(item.input_ref))
            if child:
                _metric_measures(child, catalog, result, stack + (metric.metric_id,))


def _measures_of(metric: Metric, catalog: SemanticCatalog) -> list[Measure]:
    result: list[Measure] = []
    _metric_measures(metric, catalog, result)
    return result


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return "'" + value.isoformat() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def _filter_sql(expr: str, op: str, value: Any) -> str:
    op = (op or "=").lower().strip()
    if op in {"is null", "is not null"}:
        return f"{expr} {op.upper()}"
    if op in {"in", "not in"}:
        values = value if isinstance(value, (list, tuple, set)) else [value]
        return f"{expr} {op.upper()} ({','.join(_literal(item) for item in values)})"
    if op == "like":
        return f"{expr} LIKE {_literal(value)}"
    if op not in {"=", "!=", "<>", ">", ">=", "<", "<="}:
        raise CompileError("filter_op_invalid", f"不支持的过滤操作符 {op}")
    return f"{expr} {op} {_literal(value)}"


def _time_grain_sql(expr: str, grain: str | None) -> str:
    if not grain or grain == "day":
        return expr
    if grain not in TIME_GRAINS:
        raise CompileError("time_grain_invalid", f"不支持的时间粒度 {grain}")
    return f"DATE_TRUNC('{grain}', {expr})"


def _metric_filter_sql(metric: Metric, model_id: int, alias: str, catalog: SemanticCatalog) -> str | None:
    if not metric.filter:
        return None
    try:
        return resolve_filter_expr(metric.filter, model_id, alias, catalog)
    except PlanError as exc:
        raise CompileError(exc.code, exc.message, detail=exc.detail) from exc


def _mask_expression(template: str, column_expr: str) -> str:
    if "{col}" in template:
        return template.replace("{col}", column_expr)
    return template


def _measure_sql(
    measure: Measure,
    alias: str,
    metric: Metric,
    catalog: SemanticCatalog,
    warnings: list[str],
    permissions: PermissionContext | None,
) -> str:
    if measure.field_id:
        arg = field_expr(measure.model_id, measure.field_id, alias, catalog)
        field = catalog.fields.get(measure.field_id)
        if field and permissions and field.name in permissions.column_masks:
            # 列级掩码只影响可读输出，不影响聚合口径
            warnings.append(f"度量 {measure.name} 的字段配置了列级掩码，聚合按原始值计算")
    elif measure.expr:
        arg = measure.expr
    else:
        raise CompileError("measure_source_missing", f"度量 {measure.name} 缺少字段或表达式")
    if measure.filter:
        try:
            condition = resolve_filter_expr(measure.filter, measure.model_id, alias, catalog)
        except PlanError as exc:
            raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
        arg = f"CASE WHEN {condition} THEN {arg} END"
    if metric.filter:
        try:
            condition = _metric_filter_sql(metric, measure.model_id, alias, catalog)
        except CompileError:
            condition = _metric_filter_sql(metric, metric.model_id or measure.model_id, alias, catalog)
        if condition:
            arg = f"CASE WHEN {condition} THEN {arg} END"
    agg = (measure.agg or "sum").lower()
    if agg not in AGG_FUNCS:
        raise CompileError("agg_unsupported", f"不支持的聚合方式 {agg}")
    if agg == "count_distinct":
        return f"COUNT(DISTINCT {arg})"
    if agg == "percentile":
        param = measure.agg_param if measure.agg_param is not None else 0.5
        return f"PERCENTILE_CONT({param}) WITHIN GROUP (ORDER BY {arg})"
    if agg == "median":
        return f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {arg})"
    return f"{agg.upper()}({arg})"


def _input_sql(
    item: MetricInput,
    metric: Metric,
    base_model_id: int,
    catalog: SemanticCatalog,
    aliases: dict[int, str],
    warnings: list[str],
    stack: tuple[int, ...],
    window_ctx: WindowContext | None,
    permissions: PermissionContext | None,
) -> str:
    if item.input_type == "measure":
        measure = catalog.measures.get(int(item.input_ref))
        if not measure:
            raise CompileError("measure_not_found", f"指标输入度量 {item.input_ref} 不存在")
        alias = aliases.get(measure.model_id)
        if not alias:
            raise CompileError("measure_model_unplanned", f"度量 {measure.name} 的模型未参与 JOIN 规划")
        return _measure_sql(measure, alias, metric, catalog, warnings, permissions)
    if item.input_type == "metric":
        child = catalog.metrics.get(int(item.input_ref))
        if not child:
            raise CompileError("metric_input_missing", f"指标输入 {item.input_ref} 不存在")
        return _metric_sql(child, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
    raise CompileError("metric_input_type_invalid", f"非法指标输入类型 {item.input_type}")


def _window_frame(metric: Metric, warnings: list[str]) -> str:
    if metric.grain_to_date:
        return "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
    if metric.window_spec:
        match = WINDOW_SPEC.match(metric.window_spec)
        if match:
            amount, unit = match.group(1), match.group(2).lower()
            return f"ROWS BETWEEN {int(amount) - 1} PRECEDING AND CURRENT ROW" if int(amount) > 1 else "ROWS BETWEEN CURRENT ROW AND CURRENT ROW"
        warnings.append(f"累计指标 {metric.name} 的窗口 {metric.window_spec} 无法解析，按全量累计编译")
    return "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"


def _cumulative_sql(
    metric: Metric,
    base_model_id: int,
    catalog: SemanticCatalog,
    aliases: dict[int, str],
    warnings: list[str],
    stack: tuple[int, ...],
    window_ctx: WindowContext | None,
    permissions: PermissionContext | None,
) -> str:
    if window_ctx is None:
        raise CompileError(
            "cumulative_time_dimension_missing",
            f"累计指标 {metric.name} 需要时间维度，请在查询中加入日期维度或指定 time.field",
        )
    inputs = metric.inputs or []
    if not inputs:
        raise CompileError("metric_input_missing", f"指标 {metric.name} 没有输入")
    value = _input_sql(inputs[0], metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
    partitions = list(window_ctx.partition_exprs)
    if metric.grain_to_date:
        grain = metric.grain_to_date if metric.grain_to_date in TIME_GRAINS else "month"
        partitions.append(f"DATE_TRUNC('{grain}', {window_ctx.time_expr})")
    over: list[str] = []
    if partitions:
        over.append("PARTITION BY " + ", ".join(partitions))
    over.append(f"ORDER BY {window_ctx.time_expr} {_window_frame(metric, warnings)}")
    return f"SUM({value}) OVER ({' '.join(over)})"


def _metric_sql(
    metric: Metric,
    base_model_id: int,
    catalog: SemanticCatalog,
    aliases: dict[int, str],
    warnings: list[str],
    stack: tuple[int, ...] = (),
    window_ctx: WindowContext | None = None,
    permissions: PermissionContext | None = None,
) -> str:
    if metric.metric_id in stack:
        raise CompileError("metric_cycle", f"指标 {metric.name} 存在依赖环")
    stack = stack + (metric.metric_id,)
    if metric.metric_type == "simple":
        inputs = metric.inputs or []
        if not inputs:
            raise CompileError("metric_input_missing", f"指标 {metric.name} 没有输入")
        preferred = next((item for item in inputs if item.role == "input"), inputs[0])
        return _input_sql(preferred, metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
    if metric.metric_type == "ratio":
        numerator = next((item for item in metric.inputs if item.role == "numerator"), None)
        denominator = next((item for item in metric.inputs if item.role == "denominator"), None)
        if not numerator or not denominator:
            raise CompileError("ratio_input_missing", f"指标 {metric.name} 缺少分子或分母")
        left = _input_sql(numerator, metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
        right = _input_sql(denominator, metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
        return f"({left}) / NULLIF(CAST(({right}) AS DOUBLE PRECISION), 0)"
    if metric.metric_type == "derived":
        expression = (metric.definition or "").strip()
        if not expression:
            raise CompileError("derived_expression_missing", f"派生指标 {metric.name} 缺少表达式")
        replacements: list[tuple[str, str]] = []
        for other in catalog.metrics.values():
            if other.metric_id == metric.metric_id:
                continue
            compiled = _metric_sql(other, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
            for name in {other.name, other.business_name, *other.synonyms}:
                if name:
                    replacements.append((name, compiled))
        for measure in catalog.measures.values():
            for name in {measure.name, measure.business_name}:
                if name:
                    replacements.append(
                        (
                            name,
                            _measure_sql(
                                measure,
                                aliases.get(measure.model_id, alias_for(base_model_id)),
                                metric,
                                catalog,
                                warnings,
                                permissions,
                            ),
                        )
                    )
        for name, compiled in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            expression = re.sub(rf"(?<![\w]){re.escape(name)}(?![\w])", f"({compiled})", expression)
        if not re.fullmatch(r"[\w\s()+\-*/.<>=!,:'\"%]+", expression):
            raise CompileError("derived_expression_invalid", f"派生指标 {metric.name} 的表达式包含非法字符")
        return f"({expression})"
    if metric.metric_type == "cumulative":
        return _cumulative_sql(metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
    if metric.metric_type == "conversion":
        base_input = next((item for item in metric.inputs if item.role == "base"), None)
        conversion_input = next((item for item in metric.inputs if item.role == "conversion"), None)
        if base_input is None or conversion_input is None:
            raise CompileError("conversion_input_missing", f"转化指标 {metric.name} 缺少 base 或 conversion 输入")
        base_value = _input_sql(base_input, metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions)
        conversion_value = _input_sql(
            conversion_input, metric, base_model_id, catalog, aliases, warnings, stack, window_ctx, permissions
        )
        if metric.window_spec:
            warnings.append(f"转化指标 {metric.name} 的窗口 {metric.window_spec} 按同窗口聚合近似")
        return f"({conversion_value}) / NULLIF(CAST(({base_value}) AS DOUBLE PRECISION), 0)"
    raise CompileError("metric_type_invalid", f"非法指标类型 {metric.metric_type}")


def _nearest_model_id(model_ids: list[int], base_model_id: int, catalog: SemanticCatalog, name: str) -> int | None:
    """同名过滤字段的多个来源中取离 base 最近的一个，避免跨主题域误连。"""
    ordered = list(dict.fromkeys(model_ids))
    reachable = distances(base_model_id, catalog)
    scored = [(reachable.get(model_id, 10**6), model_id) for model_id in ordered]
    best = min(score for score, _ in scored)
    if best == 10**6:
        return ordered[0] if len(ordered) == 1 else None
    nearest = [model_id for score, model_id in scored if score == best]
    if len(nearest) > 1:
        raise CompileError("filter_field_ambiguous", f"过滤字段 {name} 在多个模型中存在")
    return nearest[0]


def _resolve_filter_model(name: str, base_model_id: int, catalog: SemanticCatalog) -> tuple[int, Any]:
    # 先看 base 模型自身，避免误用其他模型的同名维度/字段
    for item in catalog.model_fields(base_model_id):
        if name in {item.name, item.business_name} or name in item.synonyms:
            return base_model_id, item
    dimensions = [item for item in catalog.dimensions.values() if item.name == name]
    if dimensions:
        model_id = _nearest_model_id([item.model_id for item in dimensions], base_model_id, catalog, name)
        if model_id is not None:
            dimension = next(item for item in dimensions if item.model_id == model_id)
            return dimension.model_id, catalog.fields.get(dimension.field_id)
        raise CompileError("filter_field_ambiguous", f"过滤字段 {name} 在多个模型中存在")
    matches = [item for item in catalog.fields.values() if name in {item.name, item.business_name} or name in item.synonyms]
    if matches:
        model_id = _nearest_model_id([item.model_id for item in matches], base_model_id, catalog, name)
        if model_id is not None:
            return model_id, next(item for item in matches if item.model_id == model_id)
        raise CompileError("filter_field_ambiguous", f"过滤字段 {name} 在多个模型中存在")
    raise CompileError("filter_field_not_found", f"过滤字段 {name} 不存在")


def _rule_applies(rule, base_model_id: int, metric_ids: set[int], joined_models: set[int], catalog: SemanticCatalog) -> bool:
    if rule.status != "active" or rule.rule_type not in {"filter", "exclude"}:
        return False
    if rule.target_type == "global":
        return True
    if rule.target_type == "model":
        return rule.target_id in joined_models
    if rule.target_type == "metric":
        return rule.target_id in metric_ids
    if rule.target_type == "domain":
        base_model = catalog.models.get(base_model_id)
        return bool(base_model and base_model.domain_id == rule.target_id)
    return False


def _rule_model(condition: str, base_model_id: int, joined_models: set[int], catalog: SemanticCatalog) -> int:
    tokens = set(re.findall(r"[A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*", condition))
    for model_id in [base_model_id, *sorted(item for item in joined_models if item != base_model_id)]:
        fields = catalog.model_fields(model_id)
        names = {item.name for item in fields} | {item.business_name for item in fields if item.business_name}
        if tokens & names:
            return model_id
    return base_model_id


def _dimension_column(
    name: str,
    model_id: int,
    field: Field,
    grain: str | None,
    alias: str,
    catalog: SemanticCatalog,
    permissions: PermissionContext | None,
) -> PlanColumn:
    expr = field_expr(model_id, field.field_id, alias, catalog)
    if permissions and field.name in permissions.column_masks:
        expr = _mask_expression(permissions.column_masks[field.name], expr)
    else:
        expr = _time_grain_sql(expr, grain)
    return PlanColumn(
        expr=expr,
        alias=name,
        kind="dimension",
        field_id=field.field_id,
        field_name=field.name,
        sensitivity=field.sensitivity,
    )


def _default_time_field(model_id: int, catalog: SemanticCatalog) -> Field | None:
    for dimension in catalog.dimensions.values():
        if dimension.model_id == model_id and dimension.dimension_type == "time":
            field = catalog.fields.get(dimension.field_id)
            if field:
                return field
    for field in catalog.model_fields(model_id):
        if field.semantic_type == "time":
            return field
    return None


def build_physical_plan(
    query: QueryIR,
    catalog: SemanticCatalog,
    permissions: PermissionContext | None = None,
    dialect: str = "postgres",
) -> PhysicalPlan:
    if not query.metrics:
        raise CompileError("metric_required", "至少需要一个指标")
    metrics = [_metric_by_ref(item, catalog) for item in query.metrics]
    base_models = {_metric_base_model(item, catalog) for item in metrics}
    if len(base_models) != 1:
        raise CompileError(
            "metric_model_conflict",
            "一次查询中的指标必须归属同一基础模型",
            detail={"models": sorted(base_models)},
        )
    base_model_id = next(iter(base_models))
    if base_model_id not in catalog.models:
        raise CompileError("model_not_found", f"模型 {base_model_id} 不存在")

    targets: set[int] = set()
    measure_models: set[int] = set()
    for metric in metrics:
        _collect_measure_models(metric, catalog, measure_models)
    targets.update(measure_models)

    dimension_info: list[dict[str, Any]] = []
    for name in query.dimensions:
        try:
            model_id, field = resolve_dimension(name, base_model_id, catalog)
        except PlanError as exc:
            raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
        targets.add(model_id)
        dimension = next(
            (
                item
                for item in catalog.dimensions.values()
                if item.model_id == model_id and item.name == name
            ),
            None,
        )
        # 时间粒度只作用于时间维度，避免把 DATE_TRUNC 套到分类维度上
        grain = dimension.time_granularity if dimension and dimension.dimension_type == "time" else None
        if query.time and query.time.grain and field.semantic_type == "time":
            grain = query.time.grain
        dimension_info.append({"name": name, "model_id": model_id, "field": field, "grain": grain})

    cumulative = any(item.metric_type == "cumulative" for item in metrics)
    has_time_dimension = any(item["field"].semantic_type == "time" for item in dimension_info)
    if cumulative and not has_time_dimension:
        if query.time and query.time.field:
            model_id, field = resolve_dimension(query.time.field, base_model_id, catalog)
        else:
            field = _default_time_field(base_model_id, catalog)
            model_id = base_model_id
            if not field:
                raise CompileError(
                    "cumulative_time_dimension_missing",
                    "累计指标需要时间维度，但模型没有时间类型字段",
                )
        targets.add(model_id)
        grain = query.time.grain if query.time and query.time.grain else "day"
        dimension_info.append({"name": field.name, "model_id": model_id, "field": field, "grain": grain})

    filter_info: list[dict[str, Any]] = []
    for item in query.filters:
        model_id, field = _resolve_filter_model(item.field, base_model_id, catalog)
        if not field:
            raise CompileError("filter_field_not_found", f"过滤字段 {item.field} 不存在")
        targets.add(model_id)
        filter_info.append({"model_id": model_id, "field": field, "op": item.op, "value": item.value})

    time_dimension = None
    if query.time:
        if query.time.field:
            try:
                model_id, field = resolve_dimension(query.time.field, base_model_id, catalog)
            except PlanError as exc:
                raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
            targets.add(model_id)
            time_dimension = (model_id, field)
        else:
            for item in catalog.dimensions.values():
                if item.model_id == base_model_id and item.dimension_type == "time":
                    time_dimension = (base_model_id, catalog.fields.get(item.field_id))
                    break
            if not time_dimension:
                field = _default_time_field(base_model_id, catalog)
                if field:
                    time_dimension = (base_model_id, field)

    try:
        paths = plan_joins(base_model_id, targets, catalog)
    except PlanError as exc:
        raise CompileError(exc.code, exc.message, detail=exc.detail) from exc

    aliases = {base_model_id: alias_for(base_model_id)}
    for path in paths.values():
        for step in path:
            aliases.setdefault(step.source_model_id, alias_for(step.source_model_id))
            aliases.setdefault(step.target_model_id, alias_for(step.target_model_id))

    base_binding = primary_binding(base_model_id, catalog)
    binding_ids = {base_binding.binding_id}
    warnings: list[str] = []
    explanation: list[str] = []

    dimension_columns = [
        _dimension_column(
            item["name"], item["model_id"], item["field"], item["grain"], aliases[item["model_id"]], catalog, permissions
        )
        for item in dimension_info
    ]
    for item in dimension_columns:
        explanation.append(f"维度 {item.alias} → 字段 {item.field_name or item.field_id}")
    for item in dimension_info:
        explanation.append(
            f"维度 {item['name']} → 模型 {catalog.models[item['model_id']].name}.{item['field'].name}"
        )

    time_expr = None
    if dimension_info:
        for info, column in zip(dimension_info, dimension_columns):
            if info["field"].semantic_type == "time" and not (permissions and info["field"].name in permissions.column_masks):
                time_expr = column.expr
                break
    window_ctx = None
    if cumulative and time_expr:
        window_ctx = WindowContext(
            time_expr=time_expr,
            partition_exprs=[item.expr for item in dimension_columns if item.expr != time_expr],
        )

    metric_columns: list[PlanColumn] = []
    for metric in metrics:
        expr = _metric_sql(metric, base_model_id, catalog, aliases, warnings, window_ctx=window_ctx, permissions=permissions)
        metric_columns.append(PlanColumn(expr=expr, alias=metric.name, kind="metric"))
        explanation.append(f"指标 {metric.name} → 模型 {catalog.models[base_model_id].name}")

    join_plans: list[PlanJoin] = []
    joined_models = {base_model_id}
    for target in sorted(paths, key=lambda item: len(paths[item])):
        for step in paths[target]:
            if step.target_model_id in joined_models:
                continue
            target_binding = primary_binding(step.target_model_id, catalog)
            binding_ids.add(target_binding.binding_id)
            left = field_expr(step.source_model_id, step.source_field_id, aliases[step.source_model_id], catalog)
            right = field_expr(step.target_model_id, step.target_field_id, aliases[step.target_model_id], catalog)
            on_expr = f"{left} = {right}"
            if step.join_predicate:
                on_expr += f" AND ({step.join_predicate})"
            join_plans.append(
                PlanJoin(
                    model_id=step.target_model_id,
                    table=table_ref(target_binding),
                    alias=aliases[step.target_model_id],
                    on=on_expr,
                    join_type="left" if step.join_type == "left" else "inner",
                )
            )
            joined_models.add(step.target_model_id)
            explanation.append(
                f"JOIN {catalog.models[step.source_model_id].name} → {catalog.models[step.target_model_id].name} "
                f"({step.cardinality})"
            )

    where_parts: list[str] = []
    for item in filter_info:
        expr = field_expr(item["model_id"], item["field"].field_id, aliases[item["model_id"]], catalog)
        where_parts.append(_filter_sql(expr, item["op"], item["value"]))

    if query.time and time_dimension:
        model_id, field = time_dimension
        if field:
            expr = field_expr(model_id, field.field_id, aliases[model_id], catalog)
            if query.time.start:
                where_parts.append(f"{expr} >= DATE {_literal(query.time.start)}")
            if query.time.end:
                where_parts.append(f"{expr} < DATE {_literal(query.time.end)}")
            explanation.append(f"时间过滤 {field.name} → {query.time.start or '...'} ~ {query.time.end or '...'}")

    for model_id in sorted(joined_models):
        binding = catalog.primary_binding(model_id)
        if binding and binding.row_filter:
            try:
                condition = resolve_filter_expr(binding.row_filter, model_id, aliases[model_id], catalog)
            except PlanError as exc:
                raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
            where_parts.append(f"({condition})")
            explanation.append(f"绑定行过滤 {catalog.models[model_id].name}: {binding.row_filter}")

    metric_ids = {item.metric_id for item in metrics}
    for rule in sorted(catalog.business_rules, key=lambda item: item.priority):
        if not _rule_applies(rule, base_model_id, metric_ids, joined_models, catalog):
            continue
        model_id = _rule_model(rule.condition, base_model_id, joined_models, catalog)
        try:
            condition = resolve_filter_expr(rule.condition, model_id, aliases[model_id], catalog)
        except PlanError as exc:
            raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
        where_parts.append(f"NOT ({condition})" if rule.action == "exclude" else f"({condition})")
        explanation.append(f"业务规则 {rule.name} 注入到模型 {catalog.models[model_id].name}")

    if permissions:
        for row_filter in permissions.row_filters:
            try:
                condition = resolve_filter_expr(row_filter, base_model_id, aliases[base_model_id], catalog)
            except PlanError as exc:
                raise CompileError(exc.code, exc.message, detail=exc.detail) from exc
            where_parts.append(f"({condition})")
            explanation.append(f"权限行过滤注入：{row_filter}")

    order_by: list[PlanOrder] = []
    output_aliases = {item.alias for item in dimension_columns} | {item.alias for item in metric_columns}
    for raw in query.order_by:
        name = raw[1:] if raw.startswith("-") else raw
        if name not in output_aliases:
            raise CompileError(
                "order_by_field_not_found",
                f"排序字段 {name} 不在查询输出中",
                detail={"available": sorted(output_aliases)},
            )
        order_by.append(PlanOrder(expr=quote_ident(name), desc=raw.startswith("-")))

    semi_metrics = [item for item in metrics if any(
        measure.additivity == "semi_additive" for measure in _measures_of(item, catalog)
    )]
    nested = bool(semi_metrics)
    if nested and cumulative:
        raise CompileError("semi_additive_cumulative_conflict", "半加性度量与累计指标暂不支持在同一次查询中混用")

    limit = max(1, min(int(query.limit or settings.max_result_rows), settings.max_result_rows))

    plan = PhysicalPlan(
        base_model_id=base_model_id,
        base_table=table_ref(base_binding),
        base_alias=aliases[base_model_id],
        joins=join_plans,
        columns=[*dimension_columns, *metric_columns],
        group_by=[item.expr for item in dimension_columns],
        where=where_parts,
        order_by=order_by,
        limit=limit,
        dialect=dialect,
        metric_ids=[item.metric_id for item in metrics],
        model_ids=sorted(joined_models),
        binding_ids=sorted(binding_ids),
        warnings=warnings,
        explanation=explanation,
    )

    if nested:
        _apply_semi_additive(plan, metrics, semi_metrics, catalog, aliases, base_model_id, query, dimension_columns)
    return plan


def _apply_semi_additive(
    plan: PhysicalPlan,
    metrics: list[Metric],
    semi_metrics: list[Metric],
    catalog: SemanticCatalog,
    aliases: dict[int, str],
    base_model_id: int,
    query: QueryIR,
    dimension_columns: list[PlanColumn],
) -> None:
    drivers: list[Measure] = []
    for metric in semi_metrics:
        _metric_measures(metric, catalog, drivers)
    semi_driver = next((item for item in drivers if item.additivity == "semi_additive"), None)

    time_field: Field | None = None
    time_model_id = base_model_id
    if semi_driver and semi_driver.agg_time_dimension:
        time_field = catalog.fields.get(semi_driver.agg_time_dimension)
        time_model_id = time_field.model_id if time_field else base_model_id
    if not time_field:
        time_field = _default_time_field(base_model_id, catalog)
        time_model_id = base_model_id
    if not time_field:
        raise CompileError(
            "semi_additive_time_missing",
            "半加性度量需要时间字段用于两级聚合，但模型没有时间类型字段",
        )

    grain = query.time.grain if query.time and query.time.grain else "day"
    time_expr = _time_grain_sql(
        field_expr(time_model_id, time_field.field_id, aliases[time_model_id], catalog), grain
    )

    inner_columns: list[PlanColumn] = [*dimension_columns]
    for index, metric in enumerate(metrics):
        expr = next(item.expr for item in plan.columns if item.alias == metric.name)
        inner_columns.append(PlanColumn(expr=expr, alias=f"__m_{index}", kind="metric"))
    inner_columns.append(PlanColumn(expr=time_expr, alias="__grain", kind="time"))

    outer_columns: list[PlanColumn] = [
        PlanColumn(expr=quote_ident(item.alias), alias=item.alias, kind=item.kind)
        for item in dimension_columns
    ]
    for index, metric in enumerate(metrics):
        choice = "max"
        for measure in _measures_of(metric, catalog):
            if measure.additivity == "semi_additive":
                choice = (measure.window_choice or "max").lower()
                break
        outer_columns.append(
            PlanColumn(
                expr=f"{choice.upper()}({quote_ident(f'__m_{index}')})",
                alias=metric.name,
                kind="metric",
            )
        )

    plan.nested = True
    plan.inner_columns = inner_columns
    plan.inner_group_by = [item.expr for item in dimension_columns] + [time_expr]
    plan.outer_columns = outer_columns
    plan.outer_group_by = [quote_ident(item.alias) for item in dimension_columns]
