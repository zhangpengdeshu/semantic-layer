"""仓储基础设施：薄封装 SQLAlchemy Session，统一读写入口。"""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import text

from shared.db import read_session, write_session


def rows(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with read_session() as session:
        return [dict(item) for item in session.execute(text(sql), params or {}).mappings().all()]


def one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with read_session() as session:
        row = session.execute(text(sql), params or {}).mappings().one_or_none()
        return dict(row) if row else None


def insert(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with write_session() as session:
        row = session.execute(text(sql), params or {}).mappings().one_or_none()
        return dict(row) if row else None


def execute(sql: str, params: dict[str, Any] | None = None) -> int:
    with write_session() as session:
        result = session.execute(text(sql), params or {})
        return result.rowcount or 0


def execute_many(statements: Iterable[tuple[str, dict[str, Any]]]) -> None:
    with write_session() as session:
        for sql, params in statements:
            session.execute(text(sql), params or {})


def jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def pg_array(values: Iterable[str]) -> list[str]:
    return list(values)


def page_params(page: int, page_size: int) -> tuple[int, int]:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 200)
    return page, page_size