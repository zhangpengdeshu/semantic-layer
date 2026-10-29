"""编译器输入输出契约。"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    field: str | None = None
    start: date | None = None
    end: date | None = None
    grain: str | None = None


class CompareSpec(BaseModel):
    """时间对比：同比/环比。指标口径不变，对比期由查询层平移。"""

    type: Literal["yoy", "mom"] = "yoy"
    offset: int = 1
    unit: Literal["year", "month"] = "year"
    label: str = "同比"
    defaulted_time: bool = False


class Filter(BaseModel):
    field: str
    op: str = "="
    value: Any = None


class QueryIR(BaseModel):
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    time: TimeRange | None = None
    compare: CompareSpec | None = None
    limit: int = 1000
    order_by: list[str] = Field(default_factory=list)


class PermissionContext(BaseModel):
    """编译期注入的行/列权限。"""

    row_filters: list[str] = Field(default_factory=list)
    column_masks: dict[str, str] = Field(default_factory=dict)


class PlanJoin(BaseModel):
    model_id: int
    table: str
    alias: str
    on: str
    join_type: str = "inner"


class PlanColumn(BaseModel):
    expr: str
    alias: str
    kind: str = "dimension"
    field_id: int | None = None
    field_name: str | None = None
    sensitivity: str = "internal"


class PlanOrder(BaseModel):
    expr: str
    desc: bool = False


class PhysicalPlan(BaseModel):
    """QueryIR 的物理落点：表、别名、列、JOIN、过滤与聚合。"""

    base_model_id: int
    base_table: str
    base_alias: str
    joins: list[PlanJoin] = Field(default_factory=list)
    columns: list[PlanColumn] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    order_by: list[PlanOrder] = Field(default_factory=list)
    limit: int = 1000
    dialect: str = "postgres"
    metric_ids: list[int] = Field(default_factory=list)
    model_ids: list[int] = Field(default_factory=list)
    binding_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    # 半加性度量：内层按 粒度 + 时间 聚合，外层按请求维度取 MAX/MIN
    nested: bool = False
    inner_columns: list[PlanColumn] = Field(default_factory=list)
    inner_group_by: list[str] = Field(default_factory=list)
    outer_columns: list[PlanColumn] = Field(default_factory=list)
    outer_group_by: list[str] = Field(default_factory=list)


class CompiledQuery(BaseModel):
    sql: str
    columns: list[str]
    metric_ids: list[int]
    model_ids: list[int]
    binding_ids: list[int]
    warnings: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    pii_columns: list[str] = Field(default_factory=list)


class CompileError(Exception):
    def __init__(self, code: str, message: str, *, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail