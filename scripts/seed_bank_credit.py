"""银行场景 1/5：信贷经营分析写入语义层。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_credit.py

覆盖文档 9.1：公共维度（11 个）+ 信贷经营（bank_loan、loan_daily），
并完成指标、绑定、知识、校验、认证、快照与问数验证。
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
    publish,
    run_ask,
    set_grains,
    step,
    sync_datasets,
    validate_all,
)


def f(name, business, semantic_type, data_type, synonyms=None, sensitivity=None):
    item = {
        "name": name,
        "business_name": business,
        "semantic_type": semantic_type,
        "data_type": data_type,
    }
    if synonyms:
        item["synonyms"] = synonyms
    if sensitivity:
        item["sensitivity"] = sensitivity
    return item


DIM_MODELS = {
    "dim_customer": {
        "domain": "dim",
        "name": "dim_customer",
        "business_name": "客户维度",
        "description": "客户主数据，粒度 customer_id",
        "table": "dim_customer",
        "grain": "customer_id",
        "fields": [
            f("customer_id", "客户号", "key", "string"),
            f("customer_name", "客户名称", "dimension", "string", sensitivity="pii"),
            f("gender", "性别", "dimension", "string"),
            f("birth_date", "出生日期", "time", "date"),
            f("region_id", "区域号", "key", "string"),
            f("industry_id", "行业号", "key", "string"),
            f("level_id", "客户等级号", "key", "string"),
            f("open_date", "开户日期", "time", "date"),
        ],
        "dimensions": [
            ("性别", "gender", "categorical", {}),
            ("出生日期", "birth_date", "time", {"time_granularity": "year"}),
        ],
    },
    "dim_org": {
        "domain": "dim",
        "name": "dim_org",
        "business_name": "机构维度",
        "description": "机构主数据，粒度 org_id",
        "table": "dim_org",
        "grain": "org_id",
        "fields": [
            f("org_id", "机构号", "key", "string"),
            f("org_name", "机构名称", "dimension", "string"),
            f("city_id", "城市号", "key", "string"),
            f("org_type", "机构类型", "dimension", "string"),
        ],
        "dimensions": [
            ("机构", "org_name", "categorical", {}),
            ("机构类型", "org_type", "categorical", {}),
        ],
    },
    "dim_product": {
        "domain": "dim",
        "name": "dim_product",
        "business_name": "产品维度",
        "description": "产品主数据，粒度 product_id",
        "table": "dim_product",
        "grain": "product_id",
        "fields": [
            f("product_id", "产品号", "key", "string"),
            f("product_name", "产品名称", "dimension", "string"),
            f("product_line_id", "产品线号", "key", "string"),
            f("product_line", "产品线", "dimension", "string"),
            f("product_type", "产品类型", "dimension", "string"),
        ],
        "dimensions": [
            ("产品线", "product_line", "categorical", {}),
            ("产品类型", "product_type", "categorical", {}),
        ],
    },
    "dim_customer_level": {
        "domain": "dim",
        "name": "dim_customer_level",
        "business_name": "客户等级维度",
        "description": "客户等级码表",
        "table": "dim_customer_level",
        "grain": "customer_level_id",
        "fields": [
            f("customer_level_id", "等级号", "key", "string"),
            f("customer_level_name", "等级名称", "dimension", "string"),
            f("level_rank", "等级序号", "dimension", "number"),
        ],
        "dimensions": [("客户等级", "customer_level_name", "categorical", {})],
    },
    "dim_region": {
        "domain": "dim",
        "name": "dim_region",
        "business_name": "区域维度",
        "description": "区域码表",
        "table": "dim_region",
        "grain": "region_id",
        "fields": [
            f("region_id", "区域号", "key", "string"),
            f("region_name", "区域名称", "dimension", "string"),
            f("status", "状态", "dimension", "string"),
        ],
        "dimensions": [("区域", "region_name", "categorical", {})],
    },
    "dim_city": {
        "domain": "dim",
        "name": "dim_city",
        "business_name": "城市维度",
        "description": "城市码表",
        "table": "dim_city",
        "grain": "city_id",
        "fields": [
            f("city_id", "城市号", "key", "string"),
            f("city_name", "城市名称", "dimension", "string"),
            f("province_id", "省份号", "key", "string"),
        ],
        "dimensions": [("城市", "city_name", "categorical", {})],
    },
    "dim_industry": {
        "domain": "dim",
        "name": "dim_industry",
        "business_name": "行业维度",
        "description": "行业码表",
        "table": "dim_industry",
        "grain": "industry_id",
        "fields": [
            f("industry_id", "行业号", "key", "string"),
            f("industry_name", "行业名称", "dimension", "string"),
            f("status", "状态", "dimension", "string"),
        ],
        "dimensions": [("行业", "industry_name", "categorical", {})],
    },
    "dim_channel": {
        "domain": "dim",
        "name": "dim_channel",
        "business_name": "渠道维度",
        "description": "渠道码表",
        "table": "dim_channel",
        "grain": "channel_id",
        "fields": [
            f("channel_id", "渠道号", "key", "string"),
            f("channel_name", "渠道名称", "dimension", "string"),
            f("status", "渠道类型", "dimension", "string"),
        ],
        "dimensions": [
            ("渠道", "channel_name", "categorical", {}),
            ("渠道类型", "status", "categorical", {}),
        ],
    },
    "dim_risk_type": {
        "domain": "dim",
        "name": "dim_risk_type",
        "business_name": "风险类型维度",
        "description": "风险类型码表",
        "table": "dim_risk_type",
        "grain": "risk_type_id",
        "fields": [
            f("risk_type_id", "风险类型号", "key", "string"),
            f("risk_type_name", "风险类型名称", "dimension", "string"),
            f("status", "状态", "dimension", "string"),
        ],
        "dimensions": [("风险类型", "risk_type_name", "categorical", {})],
    },
    "dim_risk_level": {
        "domain": "dim",
        "name": "dim_risk_level",
        "business_name": "风险等级维度",
        "description": "风险等级码表：RL001 高、RL002 中、RL003 低",
        "table": "dim_risk_level",
        "grain": "risk_level_id",
        "fields": [
            f("risk_level_id", "风险等级号", "key", "string"),
            f("risk_level_name", "风险等级名称", "dimension", "string"),
            f("status", "状态", "dimension", "string"),
        ],
        "dimensions": [
            (
                "风险等级",
                "risk_level_name",
                "categorical",
                {"code_mapping": {"RL001": "高", "RL002": "中", "RL003": "低"}},
            )
        ],
    },
    "dim_product_line": {
        "domain": "dim",
        "name": "dim_product_line",
        "business_name": "产品线维度",
        "description": "产品线码表",
        "table": "dim_product_line",
        "grain": "product_line_id",
        "fields": [
            f("product_line_id", "产品线号", "key", "string"),
            f("product_line_name", "产品线名称", "dimension", "string"),
            f("status", "状态", "dimension", "string"),
        ],
        "dimensions": [],
    },
}


CREDIT_MODELS = {
    "bank_loan": {
        "domain": "credit",
        "name": "bank_loan",
        "business_name": "贷款明细",
        "description": "一行一笔贷款，余额为贷款级未偿本金",
        "table": "dwd_loan",
        "grain": "loan_id",
        "max_hops": 3,
        "fields": [
            f("loan_id", "贷款号", "key", "string"),
            f("customer_id", "客户号", "key", "string"),
            f("product_id", "产品号", "key", "string"),
            f("org_id", "机构号", "key", "string"),
            f("stat_date", "放款日期", "time", "date", ["贷款日期"]),
            f("loan_amount", "合同金额", "measure", "number"),
            f("balance", "贷款余额", "measure", "number", sensitivity="confidential"),
            f("interest_rate", "执行利率", "measure", "number"),
            f("overdue_days", "逾期天数", "measure", "number"),
            f("status", "贷款状态", "dimension", "string"),
        ],
        "dimensions": [
            ("放款日期", "stat_date", "time", {"time_granularity": "month"}),
            ("贷款状态", "status", "categorical", {}),
        ],
        "measures": [
            {"name": "balance_sum", "business_name": "贷款余额求和", "field": "balance", "agg": "sum", "unit": "CNY"},
            {"name": "loan_amount_sum", "business_name": "合同金额求和", "field": "loan_amount", "agg": "sum", "unit": "CNY"},
            {
                "name": "overdue_balance_sum",
                "business_name": "逾期贷款余额",
                "field": "balance",
                "agg": "sum",
                "filter": "status = '逾期'",
                "unit": "CNY",
            },
            {"name": "loan_cnt", "business_name": "贷款笔数", "field": "loan_id", "agg": "count_distinct", "unit": "笔"},
            {
                "name": "loan_customer_cnt",
                "business_name": "贷款客户数",
                "field": "customer_id",
                "agg": "count_distinct",
                "unit": "户",
            },
            {
                "name": "avg_interest_rate",
                "business_name": "平均执行利率",
                "field": "interest_rate",
                "agg": "avg",
                "additivity": "non_additive",
                "unit": "%",
            },
        ],
        "metrics": [
            {
                "name": "loan_balance",
                "business_name": "贷款余额",
                "synonyms": ["信贷余额"],
                "definition": "正常和逾期贷款的未偿本金之和",
                "metric_type": "simple",
                "filter": "status in ('正常','逾期')",
                "unit": "CNY",
                "inputs": [("measure", "balance_sum", "input")],
            },
            {
                "name": "disbursed_amount",
                "business_name": "合同放款金额",
                "synonyms": ["合同金额", "放款额"],
                "definition": "按放款日期统计的合同放款金额",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [("measure", "loan_amount_sum", "input")],
            },
            {
                "name": "overdue_balance",
                "business_name": "逾期余额",
                "definition": "状态为逾期的贷款未偿本金之和",
                "metric_type": "simple",
                "filter": "status = '逾期'",
                "unit": "CNY",
                "inputs": [("measure", "overdue_balance_sum", "input")],
            },
            {
                "name": "npl_rate",
                "business_name": "不良率",
                "synonyms": ["逾期率"],
                "definition": "逾期余额 / 贷款余额",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "overdue_balance", "numerator"),
                    ("metric", "loan_balance", "denominator"),
                ],
            },
            {
                "name": "loan_count",
                "business_name": "贷款笔数",
                "synonyms": ["贷款数"],
                "definition": "正常和逾期贷款的笔数",
                "metric_type": "simple",
                "filter": "status in ('正常','逾期')",
                "unit": "笔",
                "inputs": [("measure", "loan_cnt", "input")],
            },
            {
                "name": "loan_customer_count",
                "business_name": "贷款客户数",
                "synonyms": ["借款客户数"],
                "definition": "持有正常或逾期贷款的客户数",
                "metric_type": "simple",
                "filter": "status in ('正常','逾期')",
                "unit": "户",
                "inputs": [("measure", "loan_customer_cnt", "input")],
            },
            {
                "name": "avg_loan_balance",
                "business_name": "户均贷款余额",
                "synonyms": ["户均贷款"],
                "definition": "贷款余额 / 贷款客户数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "loan_balance", "numerator"),
                    ("metric", "loan_customer_count", "denominator"),
                ],
            },
        ],
    },
    "loan_daily": {
        "domain": "credit",
        "name": "loan_daily",
        "business_name": "贷款日汇总",
        "description": "日 × 机构 × 产品线的放款与逾期汇总",
        "table": "dws_loan_daily",
        "grain": ["stat_date", "org_id", "product_line"],
        "max_hops": 3,
        "fields": [
            f("stat_date", "统计日期", "time", "date"),
            f("org_id", "机构号", "key", "string"),
            f("product_line", "产品线", "dimension", "string"),
            f("loan_cnt", "放款笔数", "measure", "number"),
            f("loan_amount", "放款金额", "measure", "number"),
            f("overdue_amount", "逾期金额", "measure", "number"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("产品线", "product_line", "categorical", {}),
        ],
        "measures": [
            {"name": "daily_loan_amount_sum", "business_name": "放款金额求和", "field": "loan_amount", "agg": "sum", "unit": "CNY"},
            {"name": "daily_loan_cnt_sum", "business_name": "放款笔数求和", "field": "loan_cnt", "agg": "sum", "unit": "笔"},
            {
                "name": "daily_overdue_amount_sum",
                "business_name": "逾期金额求和",
                "field": "overdue_amount",
                "agg": "sum",
                "unit": "CNY",
            },
        ],
        "metrics": [
            {
                "name": "daily_loan_amount",
                "business_name": "贷款投放金额",
                "synonyms": ["放款金额", "投放金额", "贷款投放"],
                "definition": "统计期内贷款产品的放款金额",
                "metric_type": "simple",
                "filter": "product_line = '贷款'",
                "unit": "CNY",
                "inputs": [("measure", "daily_loan_amount_sum", "input")],
            },
            {
                "name": "daily_loan_count",
                "business_name": "贷款投放笔数",
                "synonyms": ["投放笔数"],
                "definition": "统计期内贷款产品的放款笔数",
                "metric_type": "simple",
                "filter": "product_line = '贷款'",
                "unit": "笔",
                "inputs": [("measure", "daily_loan_cnt_sum", "input")],
            },
            {
                "name": "loan_overdue_amount",
                "business_name": "贷款逾期金额",
                "synonyms": ["日汇总逾期金额"],
                "definition": "贷款产品的逾期金额",
                "metric_type": "simple",
                "filter": "product_line = '贷款'",
                "unit": "CNY",
                "inputs": [("measure", "daily_overdue_amount_sum", "input")],
            },
            {
                "name": "mtd_loan_amount",
                "business_name": "当月累计放款",
                "synonyms": ["累计放款", "当月累计投放"],
                "definition": "按自然月累计的贷款投放金额",
                "metric_type": "cumulative",
                "grain_to_date": "month",
                "unit": "CNY",
                "inputs": [("metric", "daily_loan_amount", "input")],
            },
        ],
    },
}


MODELS = {**DIM_MODELS, **CREDIT_MODELS}

RELATIONSHIPS = [
    {"name": "customer_region", "from": "dim_customer", "from_field": "region_id", "to": "dim_region", "to_field": "region_id"},
    {"name": "customer_industry", "from": "dim_customer", "from_field": "industry_id", "to": "dim_industry", "to_field": "industry_id"},
    {"name": "customer_level", "from": "dim_customer", "from_field": "level_id", "to": "dim_customer_level", "to_field": "customer_level_id"},
    {"name": "org_city", "from": "dim_org", "from_field": "city_id", "to": "dim_city", "to_field": "city_id"},
    {"name": "product_line", "from": "dim_product", "from_field": "product_line_id", "to": "dim_product_line", "to_field": "product_line_id"},
    {"name": "loan_customer", "from": "bank_loan", "from_field": "customer_id", "to": "dim_customer", "to_field": "customer_id"},
    {"name": "loan_org", "from": "bank_loan", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
    {"name": "loan_product", "from": "bank_loan", "from_field": "product_id", "to": "dim_product", "to_field": "product_id"},
    {"name": "daily_org", "from": "loan_daily", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
]

TERMS = [
    {
        "name": "不良贷款",
        "synonyms": ["逾期贷款"],
        "definition": "状态为逾期的贷款；不良率 = 逾期余额 / 贷款余额",
    },
    {
        "name": "贷款余额",
        "synonyms": ["未偿本金"],
        "definition": "贷款尚未偿还的本金，不是合同金额，不能跨期相加",
    },
    {
        "name": "投放金额",
        "synonyms": ["放款金额"],
        "definition": "按放款日期统计的贷款发放金额",
    },
    {
        "name": "同比",
        "synonyms": ["较去年同期", "比去年同期"],
        "definition": "与去年同期比较；由查询层平移基期，不新建指标",
    },
    {
        "name": "环比",
        "synonyms": ["较上月", "比上月"],
        "definition": "与上一期比较；由查询层平移基期，不新建指标",
    },
    {
        "name": "基期",
        "definition": "对比的基准期间，同比按自然年、环比按自然月对齐；基期缺失返回 NULL",
    },
]

RULES = [
    {
        "name": "排除结清贷款",
        "target_model": "bank_loan",
        "rule_type": "filter",
        "condition": "status = '结清'",
        "action": "exclude",
        "priority": 10,
    }
]

CONTEXTS = {
    "loan_balance": {
        "business_name": "贷款余额",
        "synonyms": ["贷款余额", "信贷余额"],
        "definition": "正常和逾期贷款的未偿本金之和，结清贷款不计入",
        "examples": [
            {"question": "各区域的贷款余额和不良率"},
            {"question": "各机构类型的贷款余额"},
        ],
        "negative_examples": [{"question": "各渠道的贷款余额（贷款明细没有渠道维度）"}],
    },
    "npl_rate": {
        "business_name": "不良率",
        "synonyms": ["不良率", "逾期率"],
        "definition": "逾期余额 / 贷款余额，分子分母共享过滤和维度",
        "examples": [{"question": "上季度各区域不良率"}],
        "negative_examples": [{"question": "各渠道不良率（贷款明细没有渠道维度）"}],
    },
    "daily_loan_amount": {
        "business_name": "贷款投放金额",
        "synonyms": ["放款金额", "投放金额"],
        "definition": "统计期内贷款产品的放款金额；同比/环比是查询修饰符，不新建指标",
        "examples": [
            {"question": "2026年9月贷款投放金额同比是多少"},
            {"question": "2026年9月贷款投放金额环比是多少"},
            {"question": "2026年9月各机构类型的贷款投放金额同比"},
        ],
        "negative_examples": [{"question": "各渠道贷款投放同比（loan_daily 没有渠道维度）"}],
    },
}


def main() -> None:
    model_names = list(MODELS)
    metric_names = [item["name"] for spec in MODELS.values() for item in spec.get("metrics", [])]

    step("1. 清理上一轮信贷示例数据")
    cleanup_scope(
        model_names,
        metric_names,
        [item["name"] for item in TERMS],
        [item["name"] for item in RULES],
        permission_subjects=["bank_analyst"],
    )

    step("2. 同步数据集目录")
    sync_datasets(MODELS)

    step("3. 主题域")
    domain_ids = {
        "dim": ensure_domain("银行公共维度", "客户、机构、产品、渠道、区域、风险等共享维度", "data-platform"),
        "credit": ensure_domain("信贷经营", "贷款投放、余额、逾期与机构/客户结构分析", "credit-data"),
    }
    print(f"主题域：银行公共维度({domain_ids['dim']})、信贷经营({domain_ids['credit']})")

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
    create_permission("bank_loan", "bank_analyst", "status in ('正常','逾期')", created)

    step("7. 校验、认证")
    validate_all(MODELS, created, bindings, metric_ids)

    step("8. 发布语义快照")
    publish()

    step("9. 问数验证")
    run_ask("各区域的贷款余额和不良率")
    run_ask("各机构类型的贷款余额")
    run_ask("各产品线的贷款余额")
    run_ask("2026年9月贷款投放金额")
    run_ask("2026年9月贷款投放金额同比是多少")
    run_ask("2026年9月贷款投放金额环比是多少")
    run_ask("2026年9月各机构类型的贷款投放金额同比")

    print("\n完成：信贷经营场景已跑通（公共维度 + 贷款明细/日汇总 → 指标 → 绑定 → 知识 → 校验 → 发布 → 问数）")


if __name__ == "__main__":
    main()