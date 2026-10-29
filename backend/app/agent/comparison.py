"""同环比：识别对比修饰符、平移基期、合并两期结果。

指标只定义口径；同比/环比属于查询层能力，不新增 `_yoy`/`_mom` 指标。
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from app.semantic.compiler.contracts import CompareSpec, CompileError, TimeRange

RATIO_TYPES = {"ratio", "conversion"}


def detect_compare(question: str) -> CompareSpec | None:
    if any(key in question for key in ("同比", "较去年同期", "比去年同期", "相比去年同期")):
        return CompareSpec(type="yoy", offset=1, unit="year", label="同比")
    if any(key in question for key in ("环比", "较上月", "比上月", "较上个月", "比上个月")):
        return CompareSpec(type="mom", offset=1, unit="month", label="环比")
    return None


def _shift_date(value: date, unit: str, offset: int) -> date:
    if unit == "year":
        try:
            return value.replace(year=value.year - offset)
        except ValueError:
            # 2 月 29 日平移到平年时取 2 月 28 日
            return value.replace(year=value.year - offset, day=28)
    total = value.year * 12 + (value.month - 1) - offset
    year, month = divmod(total, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def shift_time(time_range: TimeRange | None, compare: CompareSpec) -> TimeRange:
    if not time_range or not time_range.start or not time_range.end:
        raise CompileError(
            "compare_time_missing",
            "同比/环比需要明确的时间范围，请先给出月份或年份",
            detail={"compare": compare.model_dump()},
        )
    return time_range.model_copy(
        update={
            "start": _shift_date(time_range.start, compare.unit, compare.offset),
            "end": _shift_date(time_range.end, compare.unit, compare.offset),
        }
    )


def _key(row: dict[str, Any], dimensions: list[str]) -> tuple[Any, ...]:
    return tuple(row.get(name) for name in dimensions)


def merge_comparison(
    current_columns: list[str],
    current_rows: list[dict[str, Any]],
    base_rows: list[dict[str, Any]],
    dimensions: list[str],
    metrics: list[str],
    metric_types: dict[str, str],
) -> tuple[list[str], list[dict[str, Any]], int]:
    """按维度对齐两期结果，追加基期值、变化量与变化率。

    比率/转化指标输出百分点差，不输出百分比增长，避免口径误读。
    """
    base_index = {_key(row, dimensions): row for row in base_rows}
    columns = list(current_columns)
    for name in metrics:
        columns.append(f"{name}_基期")
        if metric_types.get(name) in RATIO_TYPES:
            columns.append(f"{name}_百分点")
        else:
            columns.extend([f"{name}_变化", f"{name}_变化率"])

    merged_rows: list[dict[str, Any]] = []
    missing_base = 0
    for row in current_rows:
        base = base_index.get(_key(row, dimensions))
        if base is None:
            missing_base += 1
        merged = dict(row)
        for name in metrics:
            current_value = row.get(name)
            base_value = base.get(name) if base else None
            ratio_type = metric_types.get(name) in RATIO_TYPES
            merged[f"{name}_基期"] = base_value
            changed_key = f"{name}_百分点" if ratio_type else f"{name}_变化"
            if current_value is None or base_value is None:
                merged[changed_key] = None
                if not ratio_type:
                    merged[f"{name}_变化率"] = None
                continue
            diff = current_value - base_value
            if ratio_type:
                merged[changed_key] = diff * 100
            else:
                merged[changed_key] = diff
                merged[f"{name}_变化率"] = diff / base_value if base_value != 0 else None
        merged_rows.append(merged)
    return columns, merged_rows, missing_base
