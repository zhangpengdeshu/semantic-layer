"""编译器与校验器单元测试（不依赖数据库）。"""

from __future__ import annotations

from datetime import date

from app.semantic.compiler.contracts import QueryIR, TimeRange
from app.semantic.compiler.sql import compile_query
from app.agent.pipeline import build_query_ir
from app.semantic.domain.entities import Metric, MetricInput
from app.semantic.validation.queryable import validate_queryable
from app.semantic.validation.semantic import validate_metric, validate_model
from tests.support.retail import retail_catalog


def test_compile_gmv_by_region_channel() -> None:
    catalog = retail_catalog()
    query = QueryIR(
        metrics=["GMV"],
        dimensions=["区域", "渠道"],
        time=TimeRange(start=date(2026, 9, 1), end=date(2026, 10, 1)),
    )
    compiled = compile_query(query, catalog)
    sql = compiled.sql
    assert "SUM(CASE WHEN m1.\"order_status\" IN ('paid', 'shipped', 'completed') THEN m1.\"amt\" END) AS \"GMV\"" in sql
    assert 'FROM dataset.ds_order_detail AS m1 JOIN dataset.ds_store AS m2 ON m1."store_no" = m2."store_no"' in sql
    assert "CAST('2026-09-01' AS DATE)" in sql
    assert "CAST('2026-10-01' AS DATE)" in sql
    assert 'm2."region" AS "区域"' in sql
    assert 'm1."channel_code" AS "渠道"' in sql
    assert 'GROUP BY m2."region", m1."channel_code"' in sql
    assert compiled.metric_ids == [1]
    assert compiled.model_ids == [1, 2]


def test_compile_aov_ratio() -> None:
    catalog = retail_catalog()
    compiled = compile_query(QueryIR(metrics=["客单价"], dimensions=["区域"]), catalog)
    assert "NULLIF" in compiled.sql
    assert 'COUNT(DISTINCT CASE WHEN m1."order_status" IN' in compiled.sql
    assert 'GROUP BY m2."region"' in compiled.sql


def test_compile_derived_net_gmv() -> None:
    catalog = retail_catalog()
    compiled = compile_query(QueryIR(metrics=["净 GMV"]), catalog)
    assert "SUM(CASE WHEN m1.\"order_status\" IN ('paid', 'shipped', 'completed') THEN m1.\"amt\" END)" in compiled.sql
    assert "SUM(CASE WHEN m1.\"order_status\" = 'refunded' THEN m1.\"refund_amt\" END)" in compiled.sql


def test_semantic_validation_passes_for_retail_model() -> None:
    issues = validate_model(1, retail_catalog())
    assert not [item for item in issues if item.level == "error"]


def test_queryable_validation_requires_binding() -> None:
    catalog = retail_catalog()
    del catalog.bindings[1]
    issues = validate_queryable(1, catalog)
    assert any(item.code == "binding_missing" for item in issues)


def test_cycle_detection() -> None:
    catalog = retail_catalog()
    catalog.metrics[100] = Metric(
        metric_id=100,
        name="A",
        metric_type="derived",
        definition="B + 1",
        status="draft",
        inputs=[MetricInput(metric_id=100, input_type="metric", input_ref=101, role="input")],
    )
    catalog.metrics[101] = Metric(
        metric_id=101,
        name="B",
        metric_type="derived",
        definition="A + 1",
        status="draft",
        inputs=[MetricInput(metric_id=101, input_type="metric", input_ref=100, role="input")],
    )
    issues = validate_metric(catalog.metrics[100], catalog)
    assert any(item.code == "metric_cycle" for item in issues)


def test_build_query_ir_matches_retail_question() -> None:
    catalog = retail_catalog()
    query = build_query_ir("上月华东地区各渠道的 GMV 和客单价", catalog)
    assert "GMV" in query.metrics
    assert "客单价" in query.metrics
    assert "区域" in query.dimensions
    assert "渠道" in query.dimensions
    assert query.time is not None
    assert any(item.field == "区域" and item.value == "华东" for item in query.filters)