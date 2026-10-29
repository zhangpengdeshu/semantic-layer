"""方言适配器注册表：编译期按目标方言选择 sqlglot 方言。"""

from __future__ import annotations

from dataclasses import dataclass

from app.semantic.compiler.contracts import CompileError


@dataclass(frozen=True, slots=True)
class DialectAdapter:
    name: str
    sqlglot_dialect: str
    supports_qualify: bool = False


_ADAPTERS: dict[str, DialectAdapter] = {
    "postgres": DialectAdapter("postgres", "postgres"),
    "postgresql": DialectAdapter("postgresql", "postgres"),
    "mysql": DialectAdapter("mysql", "mysql"),
    "duckdb": DialectAdapter("duckdb", "duckdb"),
    "trino": DialectAdapter("trino", "trino"),
    "presto": DialectAdapter("presto", "presto"),
    "clickhouse": DialectAdapter("clickhouse", "clickhouse"),
    "bigquery": DialectAdapter("bigquery", "bigquery"),
}


def get_adapter(dialect: str | None) -> DialectAdapter:
    key = (dialect or "postgres").strip().lower()
    adapter = _ADAPTERS.get(key)
    if not adapter:
        raise CompileError(
            "dialect_unsupported",
            f"不支持的方言 {dialect}",
            detail={"supported": sorted({item.name for item in _ADAPTERS.values()})},
        )
    return adapter


def register(adapter: DialectAdapter) -> None:
    _ADAPTERS[adapter.name.lower()] = adapter