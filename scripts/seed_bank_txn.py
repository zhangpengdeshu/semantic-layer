"""银行场景 3/5：支付结算分析写入语义层。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_txn.py

覆盖文档 9.3：交易金额、成功率、活跃客户与大额交易。
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
    "bank_txn": {
        "domain": "payment",
        "name": "bank_txn",
        "business_name": "账户交易",
        "description": "一行一笔账户交易，粒度 account_txn_id",
        "table": "dwd_account_txn",
        "grain": "account_txn_id",
        "max_hops": 3,
        "fields": [
            field("account_txn_id", "交易流水号", "key", "string"),
            field("account_id", "账户号", "key", "string", sensitivity="confidential"),
            field("customer_id", "客户号", "key", "string"),
            field("org_id", "机构号", "key", "string"),
            field("trade_type_id", "交易类型", "dimension", "string"),
            field("txn_amount", "交易金额", "measure", "number"),
            field("balance_after", "交易后余额", "measure", "number"),
            field("stat_date", "交易日期", "time", "date"),
            field("status", "交易状态", "dimension", "string"),
        ],
        "dimensions": [
            ("交易日期", "stat_date", "time", {"time_granularity": "month"}),
            ("交易状态", "status", "categorical", {}),
            ("交易类型", "trade_type_id", "categorical", {}),
        ],
        "measures": [
            {"name": "txn_amount_sum", "business_name": "交易金额求和", "field": "txn_amount", "agg": "sum", "unit": "CNY"},
            {"name": "txn_cnt", "business_name": "交易笔数", "field": "account_txn_id", "agg": "count_distinct", "unit": "笔"},
            {
                "name": "success_txn_cnt",
                "business_name": "成功交易笔数",
                "field": "account_txn_id",
                "agg": "count_distinct",
                "filter": "status = '成功'",
                "unit": "笔",
            },
            {
                "name": "customer_cnt",
                "business_name": "交易客户数",
                "field": "customer_id",
                "agg": "count_distinct",
                "unit": "户",
            },
            {
                "name": "large_txn_cnt",
                "business_name": "大额交易笔数",
                "field": "account_txn_id",
                "agg": "count_distinct",
                "filter": "txn_amount >= 300000",
                "unit": "笔",
            },
        ],
        "metrics": [
            {
                "name": "txn_amount",
                "business_name": "交易金额",
                "synonyms": ["交易额"],
                "definition": "成功交易的金额之和",
                "metric_type": "simple",
                "filter": "status = '成功'",
                "unit": "CNY",
                "inputs": [("measure", "txn_amount_sum", "input")],
            },
            {
                "name": "txn_total_count",
                "business_name": "交易总笔数",
                "synonyms": ["交易笔数"],
                "definition": "全部交易笔数，包含失败交易",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "txn_cnt", "input")],
            },
            {
                "name": "txn_success_count",
                "business_name": "成功交易笔数",
                "definition": "状态为成功的交易笔数",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "success_txn_cnt", "input")],
            },
            {
                "name": "txn_success_rate",
                "business_name": "交易成功率",
                "synonyms": ["成功率"],
                "definition": "成功交易笔数 / 全部交易笔数",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "txn_success_count", "numerator"),
                    ("metric", "txn_total_count", "denominator"),
                ],
            },
            {
                "name": "fail_amount",
                "business_name": "失败交易金额",
                "synonyms": ["失败金额"],
                "definition": "状态为失败的交易金额之和",
                "metric_type": "simple",
                "filter": "status = '失败'",
                "unit": "CNY",
                "inputs": [("measure", "txn_amount_sum", "input")],
            },
            {
                "name": "avg_txn_amount",
                "business_name": "单笔交易金额",
                "synonyms": ["单笔平均交易金额", "笔均交易金额"],
                "definition": "交易金额 / 成功交易笔数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "txn_amount", "numerator"),
                    ("metric", "txn_success_count", "denominator"),
                ],
            },
            {
                "name": "active_customer_count",
                "business_name": "活跃客户数",
                "synonyms": ["活跃客户"],
                "definition": "统计期内有成功交易的客户数",
                "metric_type": "simple",
                "filter": "status = '成功'",
                "unit": "户",
                "inputs": [("measure", "customer_cnt", "input")],
            },
            {
                "name": "large_txn_count",
                "business_name": "大额交易笔数",
                "synonyms": ["大额交易"],
                "definition": "单笔金额大于等于 30 万的交易笔数",
                "metric_type": "simple",
                "filter": "status = '成功'",
                "unit": "笔",
                "inputs": [("measure", "large_txn_cnt", "input")],
            },
        ],
    }
}

RELATIONSHIPS = [
    {"name": "txn_customer", "from": "bank_txn", "from_field": "customer_id", "to": "dim_customer", "to_field": "customer_id"},
    {"name": "txn_org", "from": "bank_txn", "from_field": "org_id", "to": "dim_org", "to_field": "org_id"},
]

TERMS = [
    {
        "name": "交易金额",
        "synonyms": ["交易额"],
        "definition": "仅统计成功交易；失败交易不计入交易金额",
    },
    {
        "name": "交易成功率",
        "synonyms": ["成功率"],
        "definition": "成功交易笔数 / 全部交易笔数，分母包含失败交易",
    },
    {
        "name": "活跃客户",
        "synonyms": ["活跃客户数"],
        "definition": "统计期内有成功交易的客户",
    },
    {
        "name": "大额交易",
        "synonyms": ["大额交易笔数"],
        "definition": "单笔交易金额大于等于 30 万",
    },
]

RULES = [
    {
        "name": "排除测试账户交易",
        "target_model": "bank_txn",
        "rule_type": "filter",
        "condition": "account_id like 'TEST%'",
        "action": "exclude",
        "priority": 10,
    }
]

CONTEXTS = {
    "txn_amount": {
        "business_name": "交易金额",
        "synonyms": ["交易金额", "交易额"],
        "definition": "仅统计成功交易，失败交易不计入",
        "examples": [
            {"question": "各机构类型的交易金额和成功率"},
            {"question": "各客户等级的交易金额和活跃客户数"},
        ],
        "negative_examples": [{"question": "各渠道的交易金额（交易表没有渠道维度）"}],
    },
    "txn_success_rate": {
        "business_name": "交易成功率",
        "synonyms": ["交易成功率", "成功率"],
        "definition": "成功笔数 / 全部笔数，分母包含失败交易",
        "examples": [{"question": "各机构类型的交易笔数和成功率"}],
        "negative_examples": [{"question": "各渠道交易成功率（交易表没有渠道维度）"}],
    },
    "large_txn_count": {
        "business_name": "大额交易笔数",
        "synonyms": ["大额交易"],
        "definition": "成功交易中单笔金额大于等于 30 万的笔数",
        "examples": [{"question": "大额交易有多少笔"}],
        "negative_examples": [{"question": "大额交易金额占比（需新增比率指标）"}],
    },
}


def main() -> None:
    model_names = list(MODELS)
    metric_names = [item["name"] for spec in MODELS.values() for item in spec.get("metrics", [])]

    step("1. 清理上一轮支付结算示例数据")
    cleanup_scope(
        model_names,
        metric_names,
        [item["name"] for item in TERMS],
        [item["name"] for item in RULES],
        permission_subjects=["bank_analyst_txn"],
        clear_datasets=False,
    )

    step("2. 同步数据集目录")
    sync_datasets(MODELS)

    step("3. 主题域")
    domain_ids = {"payment": ensure_domain("支付结算", "账户交易量、成功率、活跃客户与大额交易监控", "payment-data")}
    print(f"主题域：支付结算({domain_ids['payment']})")

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
    create_permission("bank_txn", "bank_analyst_txn", "status in ('成功','失败')", created)

    step("7. 校验、认证")
    validate_all(MODELS, created, bindings, metric_ids)

    step("8. 发布语义快照")
    publish()

    step("9. 问数验证")
    run_ask("各机构类型的交易金额")
    run_ask("各客户等级的交易金额和活跃客户数")
    run_ask("各机构类型的交易笔数和成功率")
    run_ask("各交易类型的失败金额")
    run_ask("大额交易有多少笔")

    print("\n完成：支付结算场景已跑通")


if __name__ == "__main__":
    main()