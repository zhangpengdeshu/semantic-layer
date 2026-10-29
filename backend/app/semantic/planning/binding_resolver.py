"""绑定解析：模型 → 主绑定，语义字段 → 物理列。"""

from __future__ import annotations

import re

from app.semantic.domain.entities import Binding, Field, SemanticCatalog
from app.semantic.planning.errors import PlanError
from app.semantic.planning.join_planner import distances


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def alias_for(model_id: int) -> str:
    return f"m{model_id}"


def primary_binding(model_id: int, catalog: SemanticCatalog) -> Binding:
    binding = catalog.primary_binding(model_id)
    if not binding:
        raise PlanError(
            "binding_missing",
            f"模型 {model_id} 没有已认证主绑定",
            detail={"model_id": model_id},
        )
    return binding


def table_ref(binding: Binding) -> str:
    if not binding.query_ref:
        raise PlanError("binding_query_ref_missing", f"绑定 {binding.binding_id} 缺少 query_ref")
    return binding.query_ref


def field_expr(model_id: int, field_id: int, alias: str, catalog: SemanticCatalog) -> str:
    field = catalog.fields.get(field_id)
    if not field or field.model_id != model_id:
        raise PlanError(
            "field_not_in_model",
            f"字段 {field_id} 不属于模型 {model_id}",
            detail={"model_id": model_id, "field_id": field_id},
        )
    binding = primary_binding(model_id, catalog)
    mapping = catalog.field_binding(binding.binding_id, field_id)
    if not mapping:
        raise PlanError(
            "field_unmapped",
            f"字段 {field.name} 在主绑定中没有物理列映射",
            detail={"model_id": model_id, "field_id": field_id, "binding_id": binding.binding_id},
        )
    column = f"{alias}.{quote_ident(mapping.column_name)}"
    if field.expression:
        return _apply_transform(field.expression, mapping.column_name, alias)
    if mapping.transform:
        return _apply_transform(mapping.transform, mapping.column_name, alias)
    return column


def _apply_transform(template: str, column_name: str, alias: str) -> str:
    column = f"{alias}.{quote_ident(column_name)}"
    if "{col}" in template:
        return template.replace("{col}", column)
    pattern = re.compile(rf"(?<![\w\"]){re.escape(column_name)}(?![\w\"])")
    if pattern.search(template):
        return pattern.sub(column, template)
    return template


def resolve_field_name(model_id: int, name: str, alias: str, catalog: SemanticCatalog) -> str:
    field = catalog.field_by_name(model_id, name)
    if not field:
        raise PlanError(
            "field_not_found",
            f"模型 {model_id} 中不存在字段 {name}",
            detail={"model_id": model_id, "field": name},
        )
    return field_expr(model_id, field.field_id, alias, catalog)


def resolve_semantic_name(name: str, model_id: int, alias: str, catalog: SemanticCatalog) -> str:
    """把维度名 / 字段名 / 业务名解析为物理表达式。"""
    dimension = catalog.dimension_by_name(name)
    if dimension and dimension.model_id == model_id:
        return field_expr(model_id, dimension.field_id, alias, catalog)
    for field in catalog.model_fields(model_id):
        if name in {field.name, field.business_name} or name in field.synonyms:
            return field_expr(model_id, field.field_id, alias, catalog)
    raise PlanError(
        "dimension_not_found",
        f"模型 {model_id} 中不存在维度或字段 {name}",
        detail={"model_id": model_id, "name": name},
    )


def resolve_filter_expr(expression: str, model_id: int, alias: str, catalog: SemanticCatalog) -> str:
    """把过滤表达式中的语义字段名替换为物理列。

    只在单引号字符串之外替换，避免误改字面量。
    """
    fields = sorted(
        [item for item in catalog.model_fields(model_id)],
        key=lambda item: len(item.name),
        reverse=True,
    )
    segments = expression.split("'")
    for index in range(0, len(segments), 2):
        text = segments[index]
        for field in fields:
            pattern = re.compile(rf"(?<![\w\"]){re.escape(field.name)}(?![\w\"])")
            if pattern.search(text):
                text = pattern.sub(field_expr(model_id, field.field_id, alias, catalog), text)
        segments[index] = text
    return "'".join(segments)


def _nearest_model(model_ids: list[int], base_model_id: int, catalog: SemanticCatalog, name: str) -> int | None:
    """在同名维度/字段的多个来源中选离 base 模型最近的一个。

    多主题域共存时极易出现同名维度（零售的「区域」和银行的「区域」），
    只按名称全局取第一个会跨域误连。这里用认证关系图的跳数消歧：
    取可达且最短的来源；同距离仍视为歧义，交给建模者改用限定名。
    """
    ordered = list(dict.fromkeys(model_ids))
    reachable = distances(base_model_id, catalog)
    scored = [(reachable.get(model_id, 10**6), model_id) for model_id in ordered]
    best = min(score for score, _ in scored)
    if best == 10**6:
        return None if len(ordered) > 1 else ordered[0]
    nearest = [model_id for score, model_id in scored if score == best]
    if len(nearest) > 1:
        raise PlanError("dimension_ambiguous", f"维度 {name} 在多个模型中存在，请使用限定名")
    return nearest[0]


def resolve_dimension(name: str, base_model_id: int, catalog: SemanticCatalog) -> tuple[int, Field]:
    """返回维度所属模型与字段。优先 base 模型，其次离 base 最近的同名维度。

    不同模型允许存在同名维度（如各事实表都有「渠道」），因此必须先看 base 模型自身，
    避免误把其他模型的同名维度当成跨模型引用，从而规划出无意义的 JOIN。
    """
    for dimension in catalog.dimensions.values():
        if dimension.model_id == base_model_id and dimension.name == name:
            field = catalog.fields.get(dimension.field_id)
            if not field:
                raise PlanError("dimension_field_missing", f"维度 {name} 的字段不存在")
            return base_model_id, field
    for item in catalog.model_fields(base_model_id):
        if name in {item.name, item.business_name} or name in item.synonyms:
            return base_model_id, item

    matches = [item for item in catalog.dimensions.values() if item.name == name]
    if matches:
        model_id = _nearest_model([item.model_id for item in matches], base_model_id, catalog, name)
        if model_id is not None:
            dimension = next(item for item in matches if item.model_id == model_id)
            field = catalog.fields.get(dimension.field_id)
            if not field:
                raise PlanError("dimension_field_missing", f"维度 {name} 的字段不存在")
            return dimension.model_id, field
        raise PlanError("dimension_ambiguous", f"维度 {name} 在多个模型中存在，请使用限定名")

    fields = [
        field
        for field in catalog.fields.values()
        if name in {field.name, field.business_name} or name in field.synonyms
    ]
    if fields:
        model_id = _nearest_model([item.model_id for item in fields], base_model_id, catalog, name)
        if model_id is not None:
            field = next(item for item in fields if item.model_id == model_id)
            return field.model_id, field
        raise PlanError("dimension_ambiguous", f"维度 {name} 在多个模型中存在，请使用限定名")
    raise PlanError("dimension_not_found", f"维度 {name} 不存在")