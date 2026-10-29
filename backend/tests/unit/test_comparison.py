"""同环比：识别、基期平移与结果合并。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.agent.comparison import detect_compare, merge_comparison, shift_time
from app.agent.pipeline import build_query_ir
from app.semantic.compiler.contracts import CompareSpec, TimeRange
from app.semantic.compiler.sql import compile_query

from tests.support.retail import retail_catalog


def test_detect_compare_variants():
    assert detect_compare("今年 GMV 同比").type == "yoy"
    assert detect_compare("本月 GMV 环比").type == "mom"
    assert detect_compare("本月 GMV 较上月").label == "环比"
    assert detect_compare("今年 GMV 较去年同期").label == "同比"
    assert detect_compare("今年 GMV") is None


def test_shift_time_month_and_year():
    month = TimeRange(start=date(2026, 9, 1), end=date(2026, 10, 1), grain="day")
    base = shift_time(month, CompareSpec(type="yoy", unit="year", offset=1))
    assert base.start == date(2025, 9, 1)
    assert base.end == date(2025, 10, 1)

    previous = shift_time(month, CompareSpec(type="mom", unit="month", offset=1))
    assert previous.start == date(2026, 8, 1)
    assert previous.end == date(2026, 9, 1)


def test_shift_time_handles_leap_day():
    time_range = TimeRange(start=date(2024, 2, 29), end=date(2024, 3, 1), grain="day")
    base = shift_time(time_range, CompareSpec(type="yoy", unit="year", offset=1))
    assert base.start == date(2023, 2, 28)


def test_merge_additive_and_ratio_metrics():
    columns = ["渠道", "GMV", "客单价"]
    current = [{"渠道": "APP", "GMV": Decimal("120"), "客单价": Decimal("1.2")}]
    base = [{"渠道": "APP", "GMV": Decimal("100"), "客单价": Decimal("1.0")}]
    merged_columns, rows, missing = merge_comparison(
        columns,
        current,
        base,
        ["渠道"],
        ["GMV", "客单价"],
        {"GMV": "simple", "客单价": "ratio"},
    )
    assert missing == 0
    assert merged_columns == ["渠道", "GMV", "客单价", "GMV_基期", "GMV_变化", "GMV_变化率", "客单价_基期", "客单价_百分点"]
    assert rows[0]["GMV_变化"] == Decimal("20")
    assert rows[0]["GMV_变化率"] == Decimal("0.2")
    assert rows[0]["客单价_百分点"] == Decimal("20.0")


def test_merge_marks_missing_base():
    columns = ["渠道", "GMV"]
    current = [{"渠道": "APP", "GMV": Decimal("120")}]
    _, rows, missing = merge_comparison(columns, current, [], ["渠道"], ["GMV"], {"GMV": "simple"})
    assert missing == 1
    assert rows[0]["GMV_基期"] is None
    assert rows[0]["GMV_变化率"] is None


def test_build_query_ir_sets_compare_and_compiles_base_period():
    catalog = retail_catalog()
    query_ir = build_query_ir("2026年9月各渠道 GMV 同比", catalog)
    assert query_ir.compare is not None
    assert query_ir.compare.type == "yoy"
    assert query_ir.time.start == date(2026, 9, 1)

    base_ir = query_ir.model_copy(update={"time": shift_time(query_ir.time, query_ir.compare)})
    base_sql = compile_query(base_ir, catalog).sql
    assert "2025-09-01" in base_sql
    assert "2025-10-01" in base_sql


def test_build_query_ir_defaults_to_current_month():
    catalog = retail_catalog()
    query_ir = build_query_ir("各渠道 GMV 环比", catalog)
    assert query_ir.compare is not None
    assert query_ir.compare.defaulted_time is True
    assert query_ir.time is not None
