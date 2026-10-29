"""语义层领域对象与内存目录。

编译器、校验器只依赖本模块，不依赖 FastAPI / SQLAlchemy / 数据库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Domain:
    domain_id: int
    name: str
    description: str | None = None
    owner: str | None = None
    status: str = "active"


@dataclass(slots=True)
class Model:
    model_id: int
    domain_id: int
    name: str
    business_name: str | None = None
    description: str | None = None
    owner: str | None = None
    status: str = "draft"
    max_hops: int = 3
    version: int = 1


@dataclass(slots=True)
class Field:
    field_id: int
    model_id: int
    name: str
    business_name: str | None = None
    synonyms: list[str] = field(default_factory=list)
    semantic_type: str = "unknown"
    data_type: str = "unknown"
    description: str | None = None
    expression: str | None = None
    is_hidden: bool = False
    sensitivity: str = "internal"


@dataclass(slots=True)
class GrainField:
    model_id: int
    field_id: int
    position: int = 1


@dataclass(slots=True)
class Dimension:
    dimension_id: int
    model_id: int
    name: str
    field_id: int
    dimension_type: str = "categorical"
    time_granularity: str | None = None
    hierarchy: str | None = None
    code_mapping: dict[str, Any] = field(default_factory=dict)
    default_filter: str | None = None
    filterable: bool = True
    verified: bool = False


@dataclass(slots=True)
class Measure:
    measure_id: int
    model_id: int
    name: str
    business_name: str | None = None
    field_id: int | None = None
    expr: str | None = None
    filter: str | None = None
    agg: str = "sum"
    agg_param: float | None = None
    agg_time_dimension: int | None = None
    additivity: str = "additive"
    window_choice: str | None = None
    unit: str | None = None
    verified: bool = False


@dataclass(slots=True)
class MetricInput:
    metric_id: int
    input_type: str
    input_ref: int
    role: str
    position: int = 1


@dataclass(slots=True)
class Metric:
    metric_id: int
    name: str
    metric_type: str
    model_id: int | None = None
    business_name: str | None = None
    synonyms: list[str] = field(default_factory=list)
    definition: str | None = None
    filter: str | None = None
    window_spec: str | None = None
    grain_to_date: str | None = None
    unit: str | None = None
    scale: int = 2
    domain_id: int | None = None
    owner: str | None = None
    status: str = "draft"
    version: int = 1
    inputs: list[MetricInput] = field(default_factory=list)


@dataclass(slots=True)
class JoinEdge:
    edge_id: int
    name: str
    from_model_id: int
    from_field_id: int
    to_model_id: int
    to_field_id: int
    cardinality: str
    join_type: str = "inner"
    join_predicate: str | None = None
    priority: int = 100
    verified: bool = False


@dataclass(slots=True)
class Binding:
    binding_id: int
    model_id: int
    binding_type: str
    query_ref: str
    source_system: str | None = None
    external_dataset_id: str | None = None
    table_id: int | None = None
    alias: str | None = None
    is_primary: bool = False
    priority: int = 100
    row_filter: str | None = None
    status: str = "draft"
    source_version: str | None = None
    verified: bool = False


@dataclass(slots=True)
class FieldBinding:
    binding_id: int
    field_id: int
    column_name: str
    column_id: int | None = None
    transform: str | None = None
    status: str = "draft"


@dataclass(slots=True)
class CatalogColumn:
    dataset_id: int
    column_name: str
    column_type: str | None = None
    business_name: str | None = None


@dataclass(slots=True)
class PermissionPolicy:
    """t_permission 行：行级过滤与列级掩码。"""

    permission_id: int
    subject_type: str
    subject_id: str
    asset_type: str
    asset_id: int | None = None
    effect: str = "allow"
    row_filter: str | None = None
    column_mask: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BusinessRule:
    rule_id: int
    name: str
    rule_type: str = "filter"
    target_type: str = "global"
    target_id: int | None = None
    condition: str = ""
    action: str = "exclude"
    priority: int = 100
    status: str = "active"


@dataclass(slots=True)
class SemanticCatalog:
    """一次编译/校验所需的语义快照（内存对象）。"""

    models: dict[int, Model] = field(default_factory=dict)
    fields: dict[int, Field] = field(default_factory=dict)
    grains: list[GrainField] = field(default_factory=list)
    dimensions: dict[int, Dimension] = field(default_factory=dict)
    measures: dict[int, Measure] = field(default_factory=dict)
    metrics: dict[int, Metric] = field(default_factory=dict)
    join_edges: dict[int, JoinEdge] = field(default_factory=dict)
    bindings: dict[int, Binding] = field(default_factory=dict)
    field_bindings: dict[tuple[int, int], FieldBinding] = field(default_factory=dict)
    dataset_columns: dict[int, list[CatalogColumn]] = field(default_factory=dict)
    table_columns: dict[int, list[CatalogColumn]] = field(default_factory=dict)
    dataset_ids: dict[str, int] = field(default_factory=dict)
    dataset_versions: dict[int, str | None] = field(default_factory=dict)
    permissions: list[PermissionPolicy] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    snapshot_version: str | None = None

    # ---------------------------------------------------------------- 查询
    def model_fields(self, model_id: int) -> list[Field]:
        return [f for f in self.fields.values() if f.model_id == model_id]

    def grain_field_ids(self, model_id: int) -> list[int]:
        return [
            g.field_id
            for g in sorted(self.grains, key=lambda item: (item.model_id, item.position))
            if g.model_id == model_id
        ]

    def field_by_name(self, model_id: int, name: str) -> Field | None:
        for item in self.fields.values():
            if item.model_id == model_id and item.name == name:
                return item
        return None

    def any_field_by_name(self, name: str) -> Field | None:
        for item in self.fields.values():
            if item.name == name:
                return item
        return None

    def dimension_by_name(self, name: str) -> Dimension | None:
        for item in self.dimensions.values():
            if item.name == name:
                return item
        return None

    def any_dimension_by_name(self, name: str) -> Dimension | None:
        for item in self.dimensions.values():
            if item.name == name:
                return item
        return None

    def measure_by_name(self, model_id: int, name: str) -> Measure | None:
        for item in self.measures.values():
            if item.model_id == model_id and item.name == name:
                return item
        return None

    def metric_by_name(self, name: str) -> Metric | None:
        for item in self.metrics.values():
            if item.name == name or item.business_name == name:
                return item
            if name in item.synonyms:
                return item
        return None

    def metric_inputs(self, metric_id: int) -> list[MetricInput]:
        metric = self.metrics.get(metric_id)
        return list(metric.inputs) if metric else []

    def primary_binding(self, model_id: int) -> Binding | None:
        """只返回已认证、已验证且被标记为主绑定的唯一绑定（架构 §6.3）。"""
        candidates = [
            b
            for b in self.bindings.values()
            if b.model_id == model_id and b.is_primary and b.status == "certified" and b.verified
        ]
        candidates.sort(key=lambda b: (b.priority, b.binding_id))
        return candidates[0] if candidates else None

    def model_has_bindings(self, model_id: int) -> bool:
        return any(item.model_id == model_id for item in self.bindings.values())

    def binding_columns(self, binding: Binding) -> list[CatalogColumn] | None:
        """返回绑定对应的物理列；目录不可用时返回 None。"""
        if binding.external_dataset_id:
            dataset_id = self.dataset_ids.get(binding.external_dataset_id)
            if dataset_id and dataset_id in self.dataset_columns:
                return self.dataset_columns[dataset_id]
        if binding.table_id and binding.table_id in self.table_columns:
            return self.table_columns[binding.table_id]
        return None

    def binding_source_version(self, binding: Binding) -> str | None:
        if not binding.external_dataset_id:
            return None
        dataset_id = self.dataset_ids.get(binding.external_dataset_id)
        return self.dataset_versions.get(dataset_id) if dataset_id else None

    def field_binding(self, binding_id: int, field_id: int) -> FieldBinding | None:
        return self.field_bindings.get((binding_id, field_id))

    def binding_model(self, binding_id: int) -> Model | None:
        binding = self.bindings.get(binding_id)
        return self.models.get(binding.model_id) if binding else None

    def verified_edges(self) -> list[JoinEdge]:
        return [e for e in self.join_edges.values() if e.verified]