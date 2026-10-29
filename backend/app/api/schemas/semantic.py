"""API 请求模型。"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class MemberIn(BaseModel):
    user_id: str
    role: str = "modeler"


class DomainCreate(BaseModel):
    name: str
    description: str | None = None
    owner: str | None = None
    members: list[MemberIn] = Field(default_factory=list)


class DomainUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    owner: str | None = None
    status: str | None = None
    members: list[MemberIn] | None = None


class ModelCreate(BaseModel):
    domain_id: int
    name: str
    business_name: str | None = None
    description: str | None = None
    owner: str | None = None
    max_hops: int = 3


class ModelUpdate(BaseModel):
    domain_id: int | None = None
    name: str | None = None
    business_name: str | None = None
    description: str | None = None
    owner: str | None = None
    status: str | None = None
    max_hops: int | None = None
    version: int | None = None


class GrainUpdate(BaseModel):
    field_ids: list[int] = Field(default_factory=list)


class FieldCreate(BaseModel):
    name: str
    business_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    semantic_type: str = "unknown"
    data_type: str = "unknown"
    description: str | None = None
    expression: str | None = None
    is_hidden: bool = False
    sensitivity: str = "internal"


class FieldUpdate(BaseModel):
    name: str | None = None
    business_name: str | None = None
    synonyms: list[str] | None = None
    semantic_type: str | None = None
    data_type: str | None = None
    description: str | None = None
    expression: str | None = None
    is_hidden: bool | None = None
    sensitivity: str | None = None


class FieldBatch(BaseModel):
    fields: list[FieldCreate] = Field(default_factory=list)


class DimensionCreate(BaseModel):
    name: str
    field_id: int
    dimension_type: str = "categorical"
    time_granularity: str | None = None
    hierarchy: str | None = None
    code_mapping: dict[str, Any] = Field(default_factory=dict)
    default_filter: str | None = None
    filterable: bool = True
    verified: bool = False


class DimensionUpdate(BaseModel):
    name: str | None = None
    field_id: int | None = None
    dimension_type: str | None = None
    time_granularity: str | None = None
    hierarchy: str | None = None
    code_mapping: dict[str, Any] | None = None
    default_filter: str | None = None
    filterable: bool | None = None
    verified: bool | None = None


class MeasureCreate(BaseModel):
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


class MeasureUpdate(BaseModel):
    name: str | None = None
    business_name: str | None = None
    field_id: int | None = None
    expr: str | None = None
    filter: str | None = None
    agg: str | None = None
    agg_param: float | None = None
    agg_time_dimension: int | None = None
    additivity: str | None = None
    window_choice: str | None = None
    unit: str | None = None
    verified: bool | None = None


class MetricInputIn(BaseModel):
    input_type: str
    input_ref: int
    role: str
    position: int = 1


class MetricCreate(BaseModel):
    model_id: int | None = None
    name: str
    business_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    definition: str | None = None
    metric_type: str = "simple"
    filter: str | None = None
    window_spec: str | None = None
    grain_to_date: str | None = None
    unit: str | None = None
    scale: int = 2
    domain_id: int | None = None
    owner: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    inputs: list[MetricInputIn] = Field(default_factory=list)


class MetricUpdate(BaseModel):
    model_id: int | None = None
    name: str | None = None
    business_name: str | None = None
    synonyms: list[str] | None = None
    definition: str | None = None
    metric_type: str | None = None
    filter: str | None = None
    window_spec: str | None = None
    grain_to_date: str | None = None
    unit: str | None = None
    scale: int | None = None
    domain_id: int | None = None
    owner: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: str | None = None
    inputs: list[MetricInputIn] | None = None


class RelationshipCreate(BaseModel):
    name: str
    from_model_id: int | None = None
    from_field_id: int
    to_model_id: int
    to_field_id: int
    cardinality: str
    join_type: str = "inner"
    join_predicate: str | None = None
    priority: int = 100
    verified: bool = False


class RelationshipUpdate(BaseModel):
    name: str | None = None
    from_model_id: int | None = None
    from_field_id: int | None = None
    to_model_id: int | None = None
    to_field_id: int | None = None
    cardinality: str | None = None
    join_type: str | None = None
    join_predicate: str | None = None
    priority: int | None = None
    verified: bool | None = None


class BindingCreate(BaseModel):
    binding_type: str = "dataset"
    source_system: str | None = None
    external_dataset_id: str | None = None
    table_id: int | None = None
    query_ref: str
    alias: str | None = None
    is_primary: bool = False
    priority: int = 100
    row_filter: str | None = None
    status: str = "draft"
    source_version: str | None = None
    verified: bool = False


class BindingUpdate(BaseModel):
    binding_type: str | None = None
    source_system: str | None = None
    external_dataset_id: str | None = None
    table_id: int | None = None
    query_ref: str | None = None
    alias: str | None = None
    is_primary: bool | None = None
    priority: int | None = None
    row_filter: str | None = None
    status: str | None = None
    source_version: str | None = None
    verified: bool | None = None


class FieldMappingIn(BaseModel):
    field_id: int
    column_id: int | None = None
    column_name: str
    transform: str | None = None
    status: str = "draft"


class FieldMappingsUpdate(BaseModel):
    items: list[FieldMappingIn] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    level: str = "semantic"


class BatchValidationRequest(BaseModel):
    model_ids: list[int] = Field(default_factory=list)
    level: str = "semantic"


class CertificationCreate(BaseModel):
    asset_type: str
    asset_id: int


class CertificationDecision(BaseModel):
    approve: bool
    comment: str | None = None


class TermCreate(BaseModel):
    name: str
    synonyms: list[str] = Field(default_factory=list)
    definition: str | None = None
    scope_type: str = "global"
    scope_id: int | None = None
    status: str = "active"
    owner: str | None = None


class TermUpdate(BaseModel):
    name: str | None = None
    synonyms: list[str] | None = None
    definition: str | None = None
    scope_type: str | None = None
    scope_id: int | None = None
    status: str | None = None
    owner: str | None = None


class SynonymCreate(BaseModel):
    synonym: str
    standard_name: str
    target_type: str = "global"


class SynonymUpdate(BaseModel):
    synonym: str | None = None
    standard_name: str | None = None
    target_type: str | None = None


class RuleCreate(BaseModel):
    name: str
    rule_type: str = "filter"
    target_type: str = "global"
    target_id: int | None = None
    condition: str
    action: str = "exclude"
    priority: int = 100
    status: str = "active"


class RuleUpdate(BaseModel):
    name: str | None = None
    rule_type: str | None = None
    target_type: str | None = None
    target_id: int | None = None
    condition: str | None = None
    action: str | None = None
    priority: int | None = None
    status: str | None = None


class ContextUpdate(BaseModel):
    business_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    definition: str | None = None
    examples: list[Any] = Field(default_factory=list)
    negative_examples: list[Any] = Field(default_factory=list)


class DatasetSyncRequest(BaseModel):
    source_system: str
    datasets: list[dict[str, Any]] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    domain_id: int | None = None
    query_ir: dict[str, Any] | None = None


class CompileRequest(BaseModel):
    question: str | None = None
    domain_id: int | None = None
    query_ir: dict[str, Any] | None = None