"""semantic 级校验：不依赖数据集绑定。"""

from __future__ import annotations

from app.semantic.domain.entities import Metric, SemanticCatalog
from app.semantic.validation.issues import Issue, error, warning


def _metric_cycle(metric_id: int, catalog: SemanticCatalog, stack: tuple[int, ...] = ()) -> tuple[int, ...] | None:
    if metric_id in stack:
        return stack[stack.index(metric_id):] + (metric_id,)
    metric = catalog.metrics.get(metric_id)
    if not metric:
        return None
    for item in metric.inputs:
        if item.input_type == "metric":
            found = _metric_cycle(int(item.input_ref), catalog, stack + (metric_id,))
            if found:
                return found
    return None


def validate_metric(metric: Metric, catalog: SemanticCatalog, *, model_id: int | None = None) -> list[Issue]:
    issues: list[Issue] = []
    object_id = metric.metric_id
    if metric.model_id and metric.model_id not in catalog.models:
        issues.append(
            error(
                "metric_model_missing",
                "指标归属模型不存在",
                object_type="metric",
                object_id=object_id,
                path="model_id",
            )
        )
    if metric.metric_type == "simple" and not metric.inputs:
        issues.append(
            error("metric_input_missing", "simple 指标至少需要一个输入", object_type="metric", object_id=object_id, path="inputs")
        )
    roles = {item.role for item in metric.inputs}
    if metric.metric_type == "ratio" and not {"numerator", "denominator"}.issubset(roles):
        issues.append(
            error("ratio_input_missing", "ratio 指标必须包含 numerator 和 denominator", object_type="metric", object_id=object_id, path="inputs")
        )
    if metric.metric_type == "conversion" and not {"base", "conversion"}.issubset(roles):
        issues.append(
            error("conversion_input_missing", "conversion 指标必须包含 base 和 conversion", object_type="metric", object_id=object_id, path="inputs")
        )
    if metric.metric_type == "derived" and not (metric.definition or "").strip():
        issues.append(
            error("derived_expression_missing", "derived 指标必须提供表达式", object_type="metric", object_id=object_id, path="definition")
        )
    if metric.metric_type == "cumulative" and not (metric.window_spec or metric.grain_to_date):
        issues.append(
            error("cumulative_window_missing", "cumulative 指标必须提供 window_spec 或 grain_to_date", object_type="metric", object_id=object_id, path="window_spec")
        )
    for item in metric.inputs:
        if item.input_type == "measure":
            measure = catalog.measures.get(int(item.input_ref))
            if not measure:
                issues.append(
                    error(
                        "metric_input_measure_missing",
                        f"指标引用的度量 {item.input_ref} 不存在",
                        object_type="metric",
                        object_id=object_id,
                        path="inputs",
                    )
                )
            elif model_id and measure.model_id != model_id:
                issues.append(
                    warning(
                        "metric_input_cross_model",
                        "指标输入度量不属于当前模型，查询时需要 JOIN",
                        object_type="metric",
                        object_id=object_id,
                        path="inputs",
                    )
                )
        elif item.input_type == "metric":
            if int(item.input_ref) not in catalog.metrics:
                issues.append(
                    error(
                        "metric_input_metric_missing",
                        f"指标引用的指标 {item.input_ref} 不存在",
                        object_type="metric",
                        object_id=object_id,
                        path="inputs",
                    )
                )
        else:
            issues.append(
                error(
                    "metric_input_type_invalid",
                    f"非法输入类型 {item.input_type}",
                    object_type="metric",
                    object_id=object_id,
                    path="inputs",
                )
            )
    cycle = _metric_cycle(metric.metric_id, catalog)
    if cycle:
        issues.append(
            error(
                "metric_cycle",
                "指标依赖存在环：" + " -> ".join(str(item) for item in cycle),
                object_type="metric",
                object_id=object_id,
                path="inputs",
            )
        )
    return issues


def validate_model(model_id: int, catalog: SemanticCatalog) -> list[Issue]:
    issues: list[Issue] = []
    model = catalog.models.get(model_id)
    if not model:
        return [error("model_not_found", "语义模型不存在", object_type="model", object_id=model_id)]

    fields = catalog.model_fields(model_id)
    if not fields:
        issues.append(
            error("model_fields_empty", "模型至少需要一个语义字段", object_type="model", object_id=model_id, path="fields")
        )
    names = [item.name for item in fields]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        issues.append(
            error("field_name_duplicate", f"字段名重复：{name}", object_type="model", object_id=model_id, path="fields")
        )

    grain_ids = catalog.grain_field_ids(model_id)
    if not grain_ids:
        issues.append(
            error("grain_missing", "模型必须声明业务粒度", object_type="model", object_id=model_id, path="grain")
        )
    for field_id in grain_ids:
        field = catalog.fields.get(field_id)
        if not field or field.model_id != model_id:
            issues.append(
                error(
                    "grain_field_invalid",
                    f"粒度字段 {field_id} 不属于当前模型",
                    object_type="model",
                    object_id=model_id,
                    path="grain",
                )
            )
    if grain_ids and not any((catalog.fields.get(item) and catalog.fields[item].semantic_type == "key") for item in grain_ids):
        issues.append(
            warning(
                "grain_key_missing",
                "粒度字段中没有 key 字段，请确认主键口径",
                object_type="model",
                object_id=model_id,
                path="grain",
            )
        )

    for dimension in [item for item in catalog.dimensions.values() if item.model_id == model_id]:
        field = catalog.fields.get(dimension.field_id)
        if not field or field.model_id != model_id:
            issues.append(
                error(
                    "dimension_field_invalid",
                    f"维度 {dimension.name} 的字段不属于当前模型",
                    object_type="dimension",
                    object_id=dimension.dimension_id,
                    path="field_id",
                )
            )
        if dimension.dimension_type == "time" and field and field.data_type not in {"date", "unknown"}:
            issues.append(
                warning(
                    "time_dimension_type",
                    f"时间维度 {dimension.name} 的字段类型不是 date",
                    object_type="dimension",
                    object_id=dimension.dimension_id,
                    path="field_id",
                )
            )

    for measure in [item for item in catalog.measures.values() if item.model_id == model_id]:
        if measure.field_id:
            field = catalog.fields.get(measure.field_id)
            if not field or field.model_id != model_id:
                issues.append(
                    error(
                        "measure_field_invalid",
                        f"度量 {measure.name} 的字段不属于当前模型",
                        object_type="measure",
                        object_id=measure.measure_id,
                        path="field_id",
                    )
                )
        if not measure.field_id and not measure.expr:
            issues.append(
                error(
                    "measure_source_missing",
                    f"度量 {measure.name} 缺少字段或表达式",
                    object_type="measure",
                    object_id=measure.measure_id,
                    path="expr",
                )
            )
        if measure.additivity == "semi_additive" and not measure.window_choice:
            issues.append(
                error(
                    "window_choice_missing",
                    f"半加性度量 {measure.name} 必须声明 window_choice",
                    object_type="measure",
                    object_id=measure.measure_id,
                    path="window_choice",
                )
            )

    for edge in catalog.verified_edges() + [item for item in catalog.join_edges.values() if not item.verified]:
        if model_id not in {edge.from_model_id, edge.to_model_id}:
            continue
        if edge.from_field_id not in catalog.fields or catalog.fields[edge.from_field_id].model_id != edge.from_model_id:
            issues.append(
                error(
                    "relationship_from_field_invalid",
                    f"关系 {edge.name} 的 from 字段不属于对应模型",
                    object_type="relationship",
                    object_id=edge.edge_id,
                    path="from_field_id",
                )
            )
        if edge.to_field_id not in catalog.fields or catalog.fields[edge.to_field_id].model_id != edge.to_model_id:
            issues.append(
                error(
                    "relationship_to_field_invalid",
                    f"关系 {edge.name} 的 to 字段不属于对应模型",
                    object_type="relationship",
                    object_id=edge.edge_id,
                    path="to_field_id",
                )
            )
        if edge.from_model_id == edge.to_model_id:
            issues.append(
                error("relationship_self", f"关系 {edge.name} 两端不能是同一模型", object_type="relationship", object_id=edge.edge_id)
            )
        if edge.cardinality == "N:N":
            issues.append(
                warning(
                    "relationship_nn",
                    f"关系 {edge.name} 是 N:N，查询时必须经桥表模型",
                    object_type="relationship",
                    object_id=edge.edge_id,
                )
            )

    metric_ids = {
        item.metric_id
        for item in catalog.metrics.values()
        if item.model_id == model_id
        or any(
            inp.input_type == "measure"
            and catalog.measures.get(int(inp.input_ref))
            and catalog.measures[int(inp.input_ref)].model_id == model_id
            for inp in item.inputs
        )
    }
    for metric_id in sorted(metric_ids):
        issues.extend(validate_metric(catalog.metrics[metric_id], catalog, model_id=model_id))
    return issues