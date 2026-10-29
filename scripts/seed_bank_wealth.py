"""银行场景 2/5：存款与财富管理写入语义层。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_wealth.py

覆盖文档 9.2：存款、理财与客户资产（AUM）。复用场景 1 已建好的公共维度，
重点验证半加性度量的两级聚合。
"""

from __future__ import annotations

from bank_demo_common import (
    build_models,
    cleanup_scope,
    create_bindings,
    create_dimensions,
    create_fields,
    create_knowledge,
    create_measures,
    create_metrics,
    create_permission,
    create_relationships,
    ensure_domain,
    field,
    publish,
    run_ask,
    set_grains,
    step,
    sync_datasets,
    validate_all,
)

MODELS = {
    "bank_deposit": {
        "domain": "wealth",
        "name": "bank_deposit",
        "business_name": "存款明细",
        "description": "一行一笔存款，余额为存款级余额",
        "table": "dwd_deposit",
        "grain": "deposit_id",
        "max_hops": 3,
        "fields": [
            field("deposit_id", "存款号", "key", "string"),
            field("customer_id", "客户号", "key", "string"),
            field("product_id", "产品号", "key", "string"),
            field("org_id", "机构号", "key", "string"),
            field("currency_id", "币种", "dimension", "string"),
            field("balance", "存款余额", "measure", "number", sensitivity="confidential"),
            field("interest_rate", "存款利率", "measure", "number"),
            field("term_months", "存款期限", "dimension", "number", ["期限"]),
            field("stat_date", "统计日期", "time", "date"),
            field("status", "存款状态", "dimension", "string"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("存款状态", "status", "categorical", {}),
            ("币种", "currency_id", "categorical", {}),
            ("存款期限", "term_months", "categorical", {}),
        ],
        "measures": [
            {"name": "deposit_balance_sum", "business_name": "存款余额求和", "field": "balance", "agg": "sum", "unit": "CNY"},
            {
                "name": "term_deposit_balance_sum",
                "business_name": "定期存款余额",
                "field": "balance",
                "agg": "sum",
                "filter": "term_months > 0",
                "unit": "CNY",
            },
            {"name": "deposit_cnt", "business_name": "存款笔数", "field": "deposit_id", "agg": "count_distinct", "unit": "笔"},
            {
                "name": "deposit_customer_cnt",
                "business_name": "存款客户数",
                "field": "customer_id",
                "agg": "count_distinct",
                "unit": "户",
            },
        ],
        "metrics": [
            {
                "name": "deposit_balance",
                "business_name": "存款余额",
                "synonyms": ["储蓄余额"],
                "definition": "正常和到期存款的余额之和",
                "metric_type": "simple",
                "filter": "status in ('正常','到期')",
                "unit": "CNY",
                "inputs": [("measure", "deposit_balance_sum", "input")],
            },
            {
                "name": "term_deposit_balance",
                "business_name": "定期存款余额",
                "synonyms": ["定期余额"],
                "definition": "存款期限大于 0 的存款余额",
                "metric_type": "simple",
                "filter": "status in ('正常','到期')",
                "unit": "CNY",
                "inputs": [("measure", "term_deposit_balance_sum", "input")],
            },
            {
                "name": "term_deposit_ratio",
                "business_name": "定期存款占比",
                "synonyms": ["定期占比"],
                "definition": "定期存款余额 / 存款余额",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "term_deposit_balance", "numerator"),
                    ("metric", "deposit_balance", "denominator"),
                ],
            },
            {
                "name": "deposit_customer_count",
                "business_name": "存款客户数",
                "synonyms": ["存款户数"],
                "definition": "持有正常或到期存款的客户数",
                "metric_type": "simple",
                "filter": "status in ('正常','到期')",
                "unit": "户",
                "inputs": [("measure", "deposit_customer_cnt", "input")],
            },
            {
                "name": "avg_deposit_balance",
                "business_name": "户均存款",
                "definition": "存款余额 / 存款客户数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "deposit_balance", "numerator"),
                    ("metric", "deposit_customer_count", "denominator"),
                ],
            },
        ],
    },
    "bank_wealth": {
        "domain": "wealth",
        "name": "bank_wealth",
        "business_name": "理财持仓",
        "description": "一行一笔理财持仓",
        "table": "dwd_wealth",
        "grain": "wealth_id",
        "max_hops": 3,
        "fields": [
            field("wealth_id", "持仓号", "key", "string"),
            field("customer_id", "客户号", "key", "string"),
            field("product_id", "产品号", "key", "string"),
            field("org_id", "机构号", "key", "string"),
            field("amount", "投入本金", "measure", "number"),
            field("market_value", "持仓市值", "measure", "number"),
            field("profit", "持仓收益", "measure", "number"),
            field("stat_date", "统计日期", "time", "date"),
            field("status", "理财状态", "dimension", "string"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("理财状态", "status", "categorical", {}),
        ],
        "measures": [
            {"name": "wealth_market_value_sum", "business_name": "理财市值求和", "field": "market_value", "agg": "sum", "unit": "CNY"},
            {"name": "wealth_profit_sum", "business_name": "理财收益求和", "field": "profit", "agg": "sum", "unit": "CNY"},
        ],
        "metrics": [
            {
                "name": "wealth_market_value",
                "business_name": "理财市值",
                "synonyms": ["理财规模"],
                "definition": "持有中理财持仓的市值之和",
                "metric_type": "simple",
                "filter": "status = '持有'",
                "unit": "CNY",
                "inputs": [("measure", "wealth_market_value_sum", "input")],
            },
            {
                "name": "wealth_profit",
                "business_name": "理财收益",
                "definition": "持有和赎回理财的收益之和",
                "metric_type": "simple",
                "filter": "status in ('持有','赎回')",
                "unit": "CNY",
                "inputs": [("measure", "wealth_profit_sum", "input")],
            },
        ],
    },
    "bank_asset": {
        "domain": "wealth",
        "name": "bank_asset",
        "business_name": "客户资产快照",
        "description": "客户资产日快照，同一客户多期；余额类指标按日两级聚合",
        "table": "dwd_customer_asset",
        "grain": "customer_asset_id",
        "max_hops": 3,
        "fields": [
            field("customer_asset_id", "资产快照号", "key", "string"),
            field("customer_id", "客户号", "key", "string"),
            field("org_id", "机构号", "key", "string"),
            field("total_asset", "客户总资产", "measure", "number", sensitivity="confidential"),
            field("cash_asset", "现金资产", "measure", "number"),
            field("stat_date", "统计日期", "time", "date"),
            field("status", "资产状态", "dimension", "string"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("资产状态", "status", "categorical", {}),
        ],
        "measures": [
            {
                "name": "asset_total_sum",
                "business_name": "客户总资产",
                "field": "total_asset",
                "agg": "sum",
                "additivity": "semi_additive",
                "window_choice": "max",
                "time_field": "stat_date",
                "unit": "CNY",
            },
            {
                "name": "asset_cash_sum",
                "business_name": "现金资产求和",
                "field": "cash_asset",
                "agg": "sum",
                "additivity": "semi_additive",
                "window_choice": "max",
                "time_field": "stat_date",
                "unit": "CNY",
            },
            {
                "name": "asset_customer_cnt",
                "business_name": "资产客户数",
                "field": "customer_id",
                "agg": "count_distinct",
                "unit": "户",
            },
            {
                "name": "high_value_customer_cnt",
                "business_name": "高净值客户数",
                "field": "customer_id",
                "agg": "count_distinct",
                "filter": "total_asset >= 5000000",
                "unit": "户",
            },
        ],
        "metrics": [
            {
                "name": "aum",
                "business_name": "AUM",
                "synonyms": ["管理资产", "客户总资产"],
                "definition": "客户总资产，按日快照两级聚合后取最大值，不跨期累加",
                "metric_type": "simple",
                "filter": "status = '正常'",
                "unit": "CNY",
                "inputs": [("measure", "asset_total_sum", "input")],
            },
            {
                "name": "asset_customer_count",
                "business_name": "资产客户数",
                "definition": "有正常资产快照的客户数",
                "metric_type": "simple",
                "filter": "status = '正常'",
                "unit": "户",
                "inputs": [("measure", "asset_customer_cnt", "input")],
            },
            {
                "name": "cash_asset",
                "business_name": "现金资产",
                "synonyms": ["现金类资产"],
                "definition": "客户资产中的现金类资产，按日快照两级聚合",
                "metric_type": "simple",
                "filter": "status = '正常'",
                "unit": "CNY",
                "inputs": [("measure", "asset_cash_sum", "input")],
            },
            {
                "name": "non_cash_asset",
                "business_name": "非现金资产",
                "definition": "aum - cash_asset",
                "metric_type": "derived",
                "unit": "CNY",
            },
            {
                "name": "cash_asset_ratio",
                "business_name": "现金资产占比",
                "synonyms": ["现金占比"],
                "definition": "现金资产 / AUM",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "cash_asset", "numerator"),
                    ("metric", "aum", "denominator"),
                ],
            },
            {
                "name": "aum_per_customer",
                "business_name": "户均 AUM",
                "synonyms": ["户均资产"],
                "definition": "AUM / 资产客户数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "aum", "numerator"),
                    ("metric", "asset_customer_count", "denominator"),
                ],
            },
            {
                "name": "high_value_customer_count",
                "business_name": "高净值客户数",
                "synonyms": ["高净值客户"],
                "definition": "资产大于等于 500 万的客户数",
                "metric_type": "simple",
                "filter": "status = '正常'",
                "unit": "户",
                "inputs": [("measure", "high_value_customer_cnt", "input")],
            },
        ],
    },
}

RELATIONSHIPS = [
    {"name": "deposit_customer", "from": "bank_deposit", "from_field": "customer_id", "to": "dim_customer", "to_field": "customer_id"},
    {"name": "deposit_org", "from": "bank_deposit", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
    {"name": "deposit_product", "from": "bank_deposit", "from_field": "product_id", "to": "dim_product", "to_field": "product_id"},
    {"name": "wealth_customer", "from": "bank_wealth", "from_field": "customer_id", "to": "dim_customer", "to_field": "customer_id"},
    {"name": "wealth_org", "from": "bank_wealth", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
    {"name": "wealth_product", "from": "bank_wealth", "from_field": "product_id", "to": "dim_product", "to_field": "product_id"},
    {"name": "asset_customer", "from": "bank_asset", "from_field": "customer_id", "to": "dim_customer", "to_field": "customer_id"},
    {"name": "asset_org", "from": "bank_asset", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
]

TERMS = [
    {
        "name": "存款余额",
        "synonyms": ["储蓄余额"],
        "definition": "状态为正常或到期的存款本金，支取不计",
    },
    {
        "name": "AUM",
        "synonyms": ["管理资产", "客户总资产"],
        "definition": "客户总资产，取快照值，不能跨期累加；查询需限定统计期间",
    },
    {
        "name": "定期存款占比",
        "synonyms": ["定期占比"],
        "definition": "定期存款余额 / 存款余额",
    },
    {
        "name": "高净值客户",
        "synonyms": ["高净值客户数"],
        "definition": "AUM 大于等于 500 万的客户",
    },
]

RULES = [
    {
        "name": "排除支取存款",
        "target_model": "bank_deposit",
        "rule_type": "filter",
        "condition": "status = '支取'",
        "action": "exclude",
        "priority": 10,
    },
    {
        "name": "排除失效资产快照",
        "target_model": "bank_asset",
        "rule_type": "filter",
        "condition": "status = '失效'",
        "action": "exclude",
        "priority": 10,
    },
]

CONTEXTS = {
    "deposit_balance": {
        "business_name": "存款余额",
        "synonyms": ["存款余额", "储蓄余额"],
        "definition": "正常和到期存款的余额之和，支取存款不计",
        "examples": [
            {"question": "各客户等级的存款余额和户均存款"},
            {"question": "各区域的存款余额"},
        ],
        "negative_examples": [{"question": "各渠道的存款余额（存款明细没有渠道维度）"}],
    },
    "aum": {
        "business_name": "AUM",
        "synonyms": ["AUM", "管理资产"],
        "definition": "客户总资产日快照按日汇总后取最大值，不跨期累加；查询应限定统计期间",
        "examples": [
            {"question": "2026年9月各客户等级的 AUM"},
            {"question": "2026年9月各资产状态的 AUM"},
        ],
        "negative_examples": [{"question": "上月 AUM 环比（需查询层支持对比修饰符）"}],
    },
    "wealth_market_value": {
        "business_name": "理财市值",
        "synonyms": ["理财市值", "理财规模"],
        "definition": "持有中理财持仓的市值之和",
        "examples": [{"question": "各客户等级的理财市值"}],
        "negative_examples": [{"question": "各渠道的理财市值（理财持仓没有渠道维度）"}],
    },
}


def main() -> None:
    model_names = list(MODELS)
    metric_names = [item["name"] for spec in MODELS.values() for item in spec.get("metrics", [])]

    step("1. 清理上一轮存款财富示例数据")
    cleanup_scope(
        model_names,
        metric_names,
        [item["name"] for item in TERMS],
        [item["name"] for item in RULES],
        permission_subjects=["bank_analyst_deposit"],
        clear_datasets=False,
    )

    step("2. 同步数据集目录")
    sync_datasets(MODELS)

    step("3. 主题域")
    domain_ids = {"wealth": ensure_domain("存款与财富", "存款、理财、客户资产（AUM）与客户结构分析", "retail-finance")}
    print(f"主题域：存款与财富({domain_ids['wealth']})")

    step("4. 语义模型、字段、粒度、维度、度量、指标、关系")
    created = build_models(MODELS, domain_ids)
    fields = create_fields(MODELS, created)
    set_grains(MODELS, created, fields)
    create_dimensions(MODELS, created, fields)
    measures = create_measures(MODELS, created, fields)
    metric_ids = create_metrics(MODELS, created, domain_ids, measures)
    create_relationships(RELATIONSHIPS, created, fields)

    step("5. 数据绑定与字段映射")
    bindings = create_bindings(MODELS, created, fields)

    step("6. 知识上下文与权限")
    create_knowledge(TERMS, RULES, CONTEXTS, created, metric_ids)
    create_permission("bank_deposit", "bank_analyst_deposit", "status in ('正常','到期')", created)

    step("7. 校验、认证")
    validate_all(MODELS, created, bindings, metric_ids)

    step("8. 发布语义快照")
    publish()

    step("9. 问数验证")
    run_ask("各客户等级的存款余额和户均存款")
    run_ask("各区域的存款余额")
    run_ask("2026年9月各客户等级的 AUM")
    run_ask("2026年9月各资产状态的 AUM")
    run_ask("各客户等级的理财市值")

    print("\n完成：存款与财富场景已跑通（含半加性 AUM 两级聚合）")


if __name__ == "__main__":
    main()