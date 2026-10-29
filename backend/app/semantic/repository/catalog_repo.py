"""语义目录装配：live 表与认证快照 payload 共用同一套装配逻辑。"""

from __future__ import annotations

from typing import Any

from app.semantic.domain.entities import (
    Binding,
    BusinessRule,
    CatalogColumn,
    Dimension,
    Field,
    FieldBinding,
    GrainField,
    JoinEdge,
    Measure,
    Metric,
    MetricInput,
    Model,
    PermissionPolicy,
    SemanticCatalog,
)
from app.semantic.repository.db import rows

LIVE_TABLES = [
    "t_sem_model",
    "t_sem_field",
    "t_sem_model_grain",
    "t_sem_dimension",
    "t_sem_measure",
    "t_sem_metric",
    "t_sem_metric_input",
    "t_sem_join_edge",
    "t_sem_binding",
    "t_sem_field_binding",
    "t_ext_dataset",
    "t_ext_column",
    "t_meta_column",
    "t_permission",
    "t_business_rule",
]


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _assemble(tables: dict[str, list[dict[str, Any]]]) -> SemanticCatalog:
    catalog = SemanticCatalog()

    for item in tables.get("t_sem_model", []):
        catalog.models[int(item["model_id"])] = Model(
            model_id=int(item["model_id"]),
            domain_id=int(item["domain_id"]),
            name=item["name"],
            business_name=item.get("business_name"),
            description=item.get("description"),
            owner=item.get("owner"),
            status=item.get("status") or "draft",
            max_hops=int(item.get("max_hops") or 3),
            version=int(item.get("version") or 1),
        )

    for item in tables.get("t_sem_field", []):
        catalog.fields[int(item["field_id"])] = Field(
            field_id=int(item["field_id"]),
            model_id=int(item["model_id"]),
            name=item["name"],
            business_name=item.get("business_name"),
            synonyms=list(item.get("synonyms") or []),
            semantic_type=item.get("semantic_type") or "unknown",
            data_type=item.get("data_type") or "unknown",
            description=item.get("description"),
            expression=item.get("expression"),
            is_hidden=bool(item.get("is_hidden")),
            sensitivity=item.get("sensitivity") or "internal",
        )

    for item in tables.get("t_sem_model_grain", []):
        catalog.grains.append(
            GrainField(
                model_id=int(item["model_id"]),
                field_id=int(item["field_id"]),
                position=int(item.get("position") or 1),
            )
        )

    for item in tables.get("t_sem_dimension", []):
        catalog.dimensions[int(item["dimension_id"])] = Dimension(
            dimension_id=int(item["dimension_id"]),
            model_id=int(item["model_id"]),
            name=item["name"],
            field_id=int(item["field_id"]),
            dimension_type=item.get("dimension_type") or "categorical",
            time_granularity=item.get("time_granularity"),
            hierarchy=item.get("hierarchy"),
            code_mapping=item.get("code_mapping") or {},
            default_filter=item.get("default_filter"),
            filterable=bool(item.get("filterable", True)),
            verified=bool(item.get("verified")),
        )

    for item in tables.get("t_sem_measure", []):
        catalog.measures[int(item["measure_id"])] = Measure(
            measure_id=int(item["measure_id"]),
            model_id=int(item["model_id"]),
            name=item["name"],
            business_name=item.get("business_name"),
            field_id=int(item["field_id"]) if item.get("field_id") else None,
            expr=item.get("expr"),
            filter=item.get("filter"),
            agg=item.get("agg") or "sum",
            agg_param=float(item["agg_param"]) if item.get("agg_param") is not None else None,
            agg_time_dimension=int(item["agg_time_dimension"]) if item.get("agg_time_dimension") else None,
            additivity=item.get("additivity") or "additive",
            window_choice=item.get("window_choice"),
            unit=item.get("unit"),
            verified=bool(item.get("verified")),
        )

    for item in tables.get("t_sem_metric", []):
        catalog.metrics[int(item["metric_id"])] = Metric(
            metric_id=int(item["metric_id"]),
            model_id=int(item["model_id"]) if item.get("model_id") else None,
            name=item["name"],
            business_name=item.get("business_name"),
            synonyms=list(item.get("synonyms") or []),
            definition=item.get("definition"),
            metric_type=item.get("metric_type") or "simple",
            filter=item.get("filter"),
            window_spec=item.get("window_spec"),
            grain_to_date=item.get("grain_to_date"),
            unit=item.get("unit"),
            scale=int(item.get("scale") or 2),
            domain_id=int(item["domain_id"]) if item.get("domain_id") else None,
            owner=item.get("owner"),
            status=item.get("status") or "draft",
            version=int(item.get("version") or 1),
        )

    for item in tables.get("t_sem_metric_input", []):
        metric_id = int(item["metric_id"])
        metric = catalog.metrics.get(metric_id)
        if metric is None:
            continue
        metric.inputs.append(
            MetricInput(
                metric_id=metric_id,
                input_type=item["input_type"],
                input_ref=int(item["input_ref"]),
                role=item["role"],
                position=int(item.get("position") or 1),
            )
        )

    for item in tables.get("t_sem_join_edge", []):
        catalog.join_edges[int(item["edge_id"])] = JoinEdge(
            edge_id=int(item["edge_id"]),
            name=item["name"],
            from_model_id=int(item["from_model_id"]),
            from_field_id=int(item["from_field_id"]),
            to_model_id=int(item["to_model_id"]),
            to_field_id=int(item["to_field_id"]),
            cardinality=item["cardinality"],
            join_type=item.get("join_type") or "inner",
            join_predicate=item.get("join_predicate"),
            priority=int(item.get("priority") or 100),
            verified=bool(item.get("verified")),
        )

    for item in tables.get("t_sem_binding", []):
        catalog.bindings[int(item["binding_id"])] = Binding(
            binding_id=int(item["binding_id"]),
            model_id=int(item["model_id"]),
            binding_type=item["binding_type"],
            query_ref=item["query_ref"],
            source_system=item.get("source_system"),
            external_dataset_id=_text(item.get("external_dataset_id")),
            table_id=int(item["table_id"]) if item.get("table_id") else None,
            alias=item.get("alias"),
            is_primary=bool(item.get("is_primary")),
            priority=int(item.get("priority") or 100),
            row_filter=item.get("row_filter"),
            status=item.get("status") or "draft",
            source_version=item.get("source_version"),
            verified=bool(item.get("verified")),
        )

    for item in tables.get("t_sem_field_binding", []):
        key = (int(item["binding_id"]), int(item["field_id"]))
        catalog.field_bindings[key] = FieldBinding(
            binding_id=int(item["binding_id"]),
            field_id=int(item["field_id"]),
            column_name=item["column_name"],
            column_id=int(item["column_id"]) if item.get("column_id") else None,
            transform=item.get("transform"),
            status=item.get("status") or "draft",
        )

    for item in tables.get("t_ext_dataset", []):
        dataset_id = int(item["dataset_id"])
        catalog.dataset_ids[str(item["external_dataset_id"])] = dataset_id
        catalog.dataset_versions[dataset_id] = item.get("source_version")

    for item in tables.get("t_ext_column", []):
        dataset_id = int(item["dataset_id"])
        catalog.dataset_columns.setdefault(dataset_id, []).append(
            CatalogColumn(
                dataset_id=dataset_id,
                column_name=item["column_name"],
                column_type=item.get("column_type"),
                business_name=item.get("business_name"),
            )
        )

    for item in tables.get("t_meta_column", []):
        table_id = int(item["table_id"])
        catalog.table_columns.setdefault(table_id, []).append(
            CatalogColumn(
                dataset_id=table_id,
                column_name=item["column_name"],
                column_type=item.get("data_type"),
                business_name=item.get("business_name"),
            )
        )

    for item in tables.get("t_permission", []):
        catalog.permissions.append(
            PermissionPolicy(
                permission_id=int(item["permission_id"]),
                subject_type=item.get("subject_type") or "role",
                subject_id=str(item["subject_id"]),
                asset_type=item["asset_type"],
                asset_id=int(item["asset_id"]) if item.get("asset_id") else None,
                effect=item.get("effect") or "allow",
                row_filter=item.get("row_filter"),
                column_mask=item.get("column_mask") or {},
            )
        )

    for item in tables.get("t_business_rule", []):
        catalog.business_rules.append(
            BusinessRule(
                rule_id=int(item["rule_id"]),
                name=item["name"],
                rule_type=item.get("rule_type") or "filter",
                target_type=item.get("target_type") or "global",
                target_id=int(item["target_id"]) if item.get("target_id") else None,
                condition=item.get("condition") or "",
                action=item.get("action") or "exclude",
                priority=int(item.get("priority") or 100),
                status=item.get("status") or "active",
            )
        )

    return catalog


def load_catalog() -> SemanticCatalog:
    """从 live 表装配目录，供建模台预览、校验与管理端使用。"""
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in LIVE_TABLES:
        tables[table] = rows(f"SELECT * FROM {table} ORDER BY 1")
    return _assemble(tables)


def load_catalog_from_snapshot(payload: dict[str, Any] | None, version: str | None = None) -> SemanticCatalog:
    """从 active 快照 payload 装配目录，供问数读路径使用。"""
    tables = {key: value for key, value in (payload or {}).items() if isinstance(value, list)}
    catalog = _assemble(tables)
    catalog.snapshot_version = version
    return catalog
