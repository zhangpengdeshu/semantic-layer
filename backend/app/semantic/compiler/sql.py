"""确定性 SQL 编译器：PhysicalPlan → SQL（sqlglot AST 组装，不做字符串拼接）。"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.semantic.compiler.contracts import (
    CompiledQuery,
    CompileError,
    PermissionContext,
    PhysicalPlan,
    PlanColumn,
    QueryIR,
)
from app.semantic.compiler.dialects import DialectAdapter, get_adapter
from app.semantic.compiler.physical import build_physical_plan
from app.semantic.domain.entities import SemanticCatalog

FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.TruncateTable,
)
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "mysql", "system", "performance_schema"}
# sqlglot 新版本把 Select 的 FROM 参数名改为 from_（旧版本为 from）
FROM_KEY = "from_" if "from_" in exp.Select.arg_types else "from"


def _parse(fragment: str, adapter: DialectAdapter) -> exp.Expression:
    try:
        statements = sqlglot.parse(fragment, read=adapter.sqlglot_dialect)
    except Exception as exc:  # pragma: no cover - sqlglot 错误类型随版本变化
        raise CompileError("sql_fragment_invalid", f"SQL 片段无法解析：{exc}", detail={"fragment": fragment}) from exc
    if len(statements) != 1 or statements[0] is None:
        raise CompileError(
            "sql_fragment_invalid",
            "SQL 片段必须且只能包含一条语句",
            detail={"fragment": fragment, "statements": len(statements)},
        )
    node = statements[0]
    _assert_readonly(node)
    return node


def _assert_readonly(node: exp.Expression) -> None:
    for item in node.walk():
        if isinstance(item, FORBIDDEN_NODES):
            raise CompileError("read_only_violation", f"只读守卫拒绝 {type(item).__name__} 语句")
        if isinstance(item, exp.Table):
            schema = (item.db or "").lower()
            if schema in SYSTEM_SCHEMAS:
                raise CompileError("read_only_violation", f"只读守卫拒绝访问系统表 {item.sql()}")


def _table(ref: str, adapter: DialectAdapter, alias: str | None = None) -> exp.Expression:
    node = _parse(f"SELECT * FROM {ref}", adapter)
    from_clause = node.args.get(FROM_KEY)
    if not from_clause:
        raise CompileError("table_ref_invalid", f"无法解析物理表引用 {ref}")
    table = from_clause.this.copy()
    if alias:
        table.set("alias", exp.TableAlias(this=exp.to_identifier(alias)))
    return table


def _select(
    plan: PhysicalPlan,
    columns: list[PlanColumn],
    group_by: list[str],
    adapter: DialectAdapter,
    *,
    from_expr: exp.Expression | None = None,
    with_joins: bool = True,
    with_where: bool = True,
) -> exp.Select:
    select = exp.Select()
    select.set("expressions", [exp.alias_(_parse(item.expr, adapter), item.alias, quoted=True) for item in columns])
    select.set(
        FROM_KEY,
        exp.From(
            this=from_expr if from_expr is not None else _table(plan.base_table, adapter, plan.base_alias)
        ),
    )
    if with_joins and plan.joins:
        joins = []
        for item in plan.joins:
            join = exp.Join(this=_table(item.table, adapter, item.alias), on=_parse(item.on, adapter))
            if item.join_type != "inner":
                join.set("kind", item.join_type.upper())
            joins.append(join)
        select.set("joins", joins)
    if with_where and plan.where:
        conditions = [_parse(item, adapter) for item in plan.where]
        select.set("where", exp.Where(this=exp.and_(*conditions)))
    if group_by:
        select.set("group", exp.Group(expressions=[_parse(item, adapter) for item in group_by]))
    if plan.order_by:
        select.set(
            "order",
            exp.Order(
                expressions=[exp.Ordered(this=_parse(item.expr, adapter), desc=item.desc) for item in plan.order_by]
            ),
        )
    select.set("limit", exp.Limit(expression=exp.Literal.number(plan.limit)))
    return select


def compile_physical_plan(plan: PhysicalPlan) -> str:
    adapter = get_adapter(plan.dialect)
    if plan.nested:
        inner = _select(plan, plan.inner_columns, plan.inner_group_by, adapter)
        outer = _select(
            plan,
            plan.outer_columns,
            plan.outer_group_by,
            adapter,
            from_expr=exp.Subquery(this=inner, alias=exp.TableAlias(this=exp.to_identifier("_t"))),
            with_joins=False,
            with_where=False,
        )
        node = outer
    else:
        node = _select(plan, plan.columns, plan.group_by, adapter)
    _assert_readonly(node)
    sql = node.sql(dialect=adapter.sqlglot_dialect)
    return sql if sql.rstrip().endswith(";") else sql + ";"


def compile_query(
    query: QueryIR,
    catalog: SemanticCatalog,
    dialect: str = "postgres",
    permissions: PermissionContext | None = None,
) -> CompiledQuery:
    adapter = get_adapter(dialect)
    plan = build_physical_plan(query, catalog, permissions=permissions, dialect=adapter.name)
    sql = compile_physical_plan(plan)
    columns = [item.alias for item in (plan.outer_columns if plan.nested else plan.columns)]
    pii_columns = [
        item.alias
        for item in (plan.outer_columns if plan.nested else plan.columns)
        if item.sensitivity == "pii"
    ]
    return CompiledQuery(
        sql=sql,
        columns=columns,
        metric_ids=plan.metric_ids,
        model_ids=plan.model_ids,
        binding_ids=plan.binding_ids,
        warnings=plan.warnings,
        explanation=plan.explanation,
        pii_columns=pii_columns,
    )


def compile_plan_dump(plan: PhysicalPlan) -> dict:
    return plan.model_dump()