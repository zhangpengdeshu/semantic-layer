"""queryable 级校验：在 semantic 通过后检查绑定与物理目录的可执行性。"""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from app.semantic.domain.entities import Binding, SemanticCatalog
from app.semantic.validation.issues import Issue, error, warning
from app.semantic.validation.semantic import validate_model

TYPE_GROUPS: dict[str, set[str]] = {
    "string": {"varchar", "text", "char", "character", "bpchar", "uuid", "name", "string", "enum", "json", "jsonb"},
    "number": {
        "int", "int2", "int4", "int8", "integer", "bigint", "smallint", "numeric", "decimal",
        "float", "float4", "float8", "double", "real", "number", "money",
    },
    "date": {
        "date", "time", "timetz", "timestamp", "timestamptz", "datetime",
        "timestamp without time zone", "timestamp with time zone",
    },
    "boolean": {"bool", "boolean"},
}


def _base_type(value: str | None) -> str:
    if not value:
        return ""
    return re.split(r"[\s(]", value.strip().lower(), maxsplit=1)[0]


def _type_compatible(field_type: str | None, column_type: str | None) -> bool:
    if not field_type or field_type == "unknown" or not column_type:
        return True
    group = TYPE_GROUPS.get(field_type)
    if not group:
        return True
    return _base_type(column_type) in group


def _policy_issues(binding: Binding, model_id: int, catalog: SemanticCatalog) -> list[Issue]:
    issues: list[Issue] = []
    fields = catalog.model_fields(model_id)
    field_names = {item.name for item in fields}
    physical = {
        mapping.column_name
        for (binding_id, _), mapping in catalog.field_bindings.items()
        if binding_id == binding.binding_id
    }
    allowed = field_names | physical
    for policy in catalog.permissions:
        if policy.asset_type != "model" or policy.asset_id != model_id:
            continue
        if policy.row_filter:
            try:
                parsed = sqlglot.parse_one(policy.row_filter, read="postgres")
            except Exception:
                issues.append(
                    error(
                        "permission_filter_unresolvable",
                        f"权限策略 {policy.permission_id} 的行级过滤无法解析",
                        object_type="permission",
                        object_id=policy.permission_id,
                        path="row_filter",
                        suggestion="修正权限策略表达式，确保使用模型字段或已映射物理列",
                    )
                )
                continue
            unknown = {column.name for column in parsed.find_all(exp.Column)} - allowed
            if unknown:
                issues.append(
                    error(
                        "permission_filter_unresolvable",
                        "权限策略引用了未知字段：" + "、".join(sorted(unknown)),
                        object_type="permission",
                        object_id=policy.permission_id,
                        path="row_filter",
                        context={"unknown": sorted(unknown)},
                    )
                )
        if policy.column_mask:
            unknown_masks = [key for key in policy.column_mask if key not in allowed]
            if unknown_masks:
                issues.append(
                    error(
                        "permission_mask_field_missing",
                        "列级掩码引用了未知字段：" + "、".join(sorted(unknown_masks)),
                        object_type="permission",
                        object_id=policy.permission_id,
                        path="column_mask",
                        context={"unknown": sorted(unknown_masks)},
                    )
                )
    return issues


def validate_queryable(model_id: int, catalog: SemanticCatalog) -> list[Issue]:
    issues = validate_model(model_id, catalog)
    model = catalog.models.get(model_id)
    if not model:
        return issues

    binding = catalog.primary_binding(model_id)
    if not binding:
        if catalog.model_has_bindings(model_id):
            issues.append(
                error(
                    "binding_primary_missing",
                    "模型存在绑定，但没有 certified + verified + is_primary 的主绑定",
                    object_type="binding",
                    object_id=model_id,
                    path="bindings",
                    suggestion="在数据绑定页将目标绑定设为主绑定，并完成认证",
                )
            )
        else:
            issues.append(
                error(
                    "binding_missing",
                    "模型没有已认证的主绑定，不能参与问数",
                    object_type="binding",
                    object_id=model_id,
                    path="bindings",
                    suggestion="在数据绑定页创建绑定、完成字段映射并认证",
                )
            )
        return issues

    if not binding.query_ref:
        issues.append(
            error(
                "binding_query_ref_missing",
                "主绑定缺少 query_ref",
                object_type="binding",
                object_id=binding.binding_id,
                path="query_ref",
            )
        )

    fields = [item for item in catalog.model_fields(model_id) if not item.is_hidden]
    missing = [
        item.name
        for item in fields
        if not catalog.field_binding(binding.binding_id, item.field_id)
    ]
    if missing:
        issues.append(
            error(
                "field_mapping_missing",
                "主绑定存在未映射字段：" + "、".join(missing),
                object_type="binding",
                object_id=binding.binding_id,
                path="field_mappings",
                suggestion="重新执行自动映射或手工补齐字段映射",
                context={"fields": missing},
            )
        )

    columns = catalog.binding_columns(binding)
    known_columns = {item.column_name: item for item in columns} if columns is not None else None

    for item in fields:
        mapping = catalog.field_binding(binding.binding_id, item.field_id)
        if mapping and not mapping.column_name:
            issues.append(
                error(
                    "field_mapping_invalid",
                    f"字段 {item.name} 的映射缺少物理列",
                    object_type="binding",
                    object_id=binding.binding_id,
                    path=f"field_mappings.{item.field_id}",
                )
            )
            continue
        if not mapping or known_columns is None:
            continue
        column = known_columns.get(mapping.column_name)
        if column is None:
            issues.append(
                error(
                    "binding_column_missing",
                    f"字段 {item.name} 映射的物理列 {mapping.column_name} 在目录中不存在",
                    object_type="binding",
                    object_id=binding.binding_id,
                    path=f"field_mappings.{item.field_id}",
                    suggestion="重新执行漂移检测并重新映射或换绑",
                    context={"field": item.name, "column": mapping.column_name},
                )
            )
            continue
        if not _type_compatible(item.data_type, column.column_type):
            issues.append(
                error(
                    "binding_type_mismatch",
                    f"字段 {item.name} 的语义类型 {item.data_type} 与物理列类型 {column.column_type} 不兼容",
                    object_type="binding",
                    object_id=binding.binding_id,
                    path=f"field_mappings.{item.field_id}",
                    suggestion="调整字段类型或在映射中配置转换表达式",
                    context={"field": item.name, "field_type": item.data_type, "column_type": column.column_type},
                )
            )

    current_version = catalog.binding_source_version(binding)
    if not binding.source_version:
        issues.append(
            warning(
                "binding_source_version_missing",
                "主绑定未记录外部版本，漂移检测能力受限",
                object_type="binding",
                object_id=binding.binding_id,
                path="source_version",
            )
        )
    elif current_version and current_version != binding.source_version:
        issues.append(
            warning(
                "binding_source_version_drift",
                f"主绑定记录的版本 {binding.source_version} 与目录当前版本 {current_version} 不一致",
                object_type="binding",
                object_id=binding.binding_id,
                path="source_version",
                context={"binding": binding.source_version, "catalog": current_version},
            )
        )

    issues.extend(_policy_issues(binding, model_id, catalog))
    return issues


def is_queryable(model_id: int, catalog: SemanticCatalog) -> bool:
    return not any(item.level == "error" for item in validate_queryable(model_id, catalog))