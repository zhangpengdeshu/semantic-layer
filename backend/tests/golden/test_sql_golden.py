"""SQL golden 用例：固化编译器输出，防止语义口径被无意改动。"""

from __future__ import annotations

from datetime import date

import pytest

from app.semantic.compiler.contracts import CompileError, PermissionContext, QueryIR, TimeRange
from app.semantic.compiler.sql import compile_query
from tests.support.retail import retail_catalog, with_cumulative_metric, with_semi_additive_metric


def _sql(value: str) -> str:
    return " ".join(value.split())


def test_gmv_by_region_and_channel() -> None:
    compiled = compile_query(
        QueryIR(
            metrics=["GMV"],
            dimensions=["区域", "渠道"],
            time=TimeRange(start=date(2026, 9, 1), end=date(2026, 10, 1)),
        ),
        retail_catalog(),
    )
    assert _sql(compiled.sql) == _sql(
        """
        SELECT m2."region" AS "区域", m1."channel_code" AS "渠道",
               SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END) AS "GMV"
        FROM dataset.ds_order_detail AS m1
        JOIN dataset.ds_store AS m2 ON m1."store_no" = m2."store_no"
        WHERE m1."dt" >= CAST('2026-09-01' AS DATE) AND m1."dt" < CAST('2026-10-01' AS DATE)
        GROUP BY m2."region", m1."channel_code"
        LIMIT 1000;
        """
    )
    assert compiled.columns == ["区域", "渠道", "GMV"]
    assert compiled.metric_ids == [1]
    assert compiled.model_ids == [1, 2]
    assert compiled.binding_ids == [1, 2]


def test_aov_ratio_uses_nullif() -> None:
    compiled = compile_query(QueryIR(metrics=["客单价"], dimensions=["区域"]), retail_catalog())
    assert _sql(compiled.sql) == _sql(
        """
        SELECT m2."region" AS "区域",
               (SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END))
               / NULLIF(CAST((COUNT(DISTINCT CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed')
               THEN m1."order_no" END)) AS DOUBLE PRECISION), 0) AS "客单价"
        FROM dataset.ds_order_detail AS m1
        JOIN dataset.ds_store AS m2 ON m1."store_no" = m2."store_no"
        GROUP BY m2."region"
        LIMIT 1000;
        """
    )


def test_derived_net_gmv_expands_inputs() -> None:
    compiled = compile_query(QueryIR(metrics=["净 GMV"]), retail_catalog())
    assert _sql(compiled.sql) == _sql(
        """
        SELECT ((SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END))
                - (SUM(CASE WHEN m1."order_status" = 'refunded' THEN m1."refund_amt" END))) AS "净 GMV"
        FROM dataset.ds_order_detail AS m1
        LIMIT 1000;
        """
    )


def test_cumulative_grain_to_date_adds_partition() -> None:
    compiled = compile_query(
        QueryIR(
            metrics=["GMV 月累计"],
            dimensions=["下单日期"],
            time=TimeRange(start=date(2026, 1, 1), end=date(2026, 4, 1)),
        ),
        with_cumulative_metric(retail_catalog()),
    )
    assert _sql(compiled.sql) == _sql(
        """
        SELECT m1."dt" AS "下单日期",
               SUM(SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END))
               OVER (PARTITION BY DATE_TRUNC('MONTH', m1."dt")
                     ORDER BY m1."dt" ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "GMV 月累计"
        FROM dataset.ds_order_detail AS m1
        WHERE m1."dt" >= CAST('2026-01-01' AS DATE) AND m1."dt" < CAST('2026-04-01' AS DATE)
        GROUP BY m1."dt"
        LIMIT 1000;
        """
    )


def test_semi_additive_uses_two_level_aggregation() -> None:
    compiled = compile_query(
        QueryIR(
            metrics=["期末库存件数"],
            dimensions=["渠道"],
            time=TimeRange(start=date(2026, 9, 1), end=date(2026, 10, 1)),
        ),
        with_semi_additive_metric(retail_catalog()),
    )
    assert _sql(compiled.sql) == _sql(
        """
        SELECT "渠道" AS "渠道", MAX("__m_0") AS "期末库存件数"
        FROM (SELECT m1."channel_code" AS "渠道", SUM(m1."qty") AS "__m_0", m1."dt" AS "__grain"
        FROM dataset.ds_order_detail AS m1
        WHERE m1."dt" >= CAST('2026-09-01' AS DATE) AND m1."dt" < CAST('2026-10-01' AS DATE)
        GROUP BY m1."channel_code", m1."dt"
        LIMIT 1000) AS _t
        GROUP BY "渠道"
        LIMIT 1000;
        """
    )
    assert compiled.columns == ["渠道", "期末库存件数"]


def test_permission_injection_applies_row_filter_and_column_mask() -> None:
    compiled = compile_query(
        QueryIR(metrics=["GMV"], dimensions=["渠道"]),
        retail_catalog(),
        permissions=PermissionContext(
            row_filters=["channel = 'online'"],
            column_masks={"channel": "CASE WHEN {col} IS NULL THEN 'unknown' ELSE {col} END"},
        ),
    )
    assert _sql(compiled.sql) == _sql(
        """
        SELECT CASE WHEN m1."channel_code" IS NULL THEN 'unknown' ELSE m1."channel_code" END AS "渠道",
               SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END) AS "GMV"
        FROM dataset.ds_order_detail AS m1
        WHERE (m1."channel_code" = 'online')
        GROUP BY CASE WHEN m1."channel_code" IS NULL THEN 'unknown' ELSE m1."channel_code" END
        LIMIT 1000;
        """
    )


def test_order_by_and_limit() -> None:
    compiled = compile_query(
        QueryIR(metrics=["GMV"], dimensions=["品类"], order_by=["-GMV"], limit=10),
        retail_catalog(),
    )
    assert _sql(compiled.sql) == _sql(
        """
        SELECT m3."category" AS "品类",
               SUM(CASE WHEN m1."order_status" IN ('paid', 'shipped', 'completed') THEN m1."amt" END) AS "GMV"
        FROM dataset.ds_order_detail AS m1
        JOIN dataset.ds_product AS m3 ON m1."sku_no" = m3."sku_no"
        GROUP BY m3."category"
        ORDER BY "GMV" DESC NULLS LAST
        LIMIT 10;
        """
    )


def test_pii_column_is_reported_for_masking() -> None:
    catalog = retail_catalog()
    catalog.fields[19].sensitivity = "pii"
    compiled = compile_query(QueryIR(metrics=["GMV"], dimensions=["客户等级"]), catalog)
    assert compiled.pii_columns == ["客户等级"]
    assert 'm4."customer_level" AS "客户等级"' in compiled.sql


def test_order_by_unknown_field_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        compile_query(QueryIR(metrics=["GMV"], order_by=["不存在的字段"]), retail_catalog())
    assert excinfo.value.code == "order_by_field_not_found"