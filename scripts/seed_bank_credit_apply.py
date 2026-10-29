"""银行场景 4/5：信贷审批转化分析写入语义层。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_credit_apply.py

覆盖文档 9.4：申请量、审批通过率、金额通过率与 conversion 转化率。
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
    "bank_credit_apply": {
        "domain": "approval",
        "name": "bank_credit_apply",
        "business_name": "信贷申请",
        "description": "一行一笔信贷申请，粒度 credit_apply_id",
        "table": "dwd_credit_apply",
        "grain": "credit_apply_id",
        "max_hops": 3,
        "fields": [
            field("credit_apply_id", "申请号", "key", "string"),
            field("customer_id", "客户号", "key", "string"),
            field("product_id", "产品号", "key", "string"),
            field("channel_id", "渠道号", "key", "string"),
            field("apply_amount", "申请金额", "measure", "number"),
            field("stat_date", "申请日期", "time", "date"),
            field("status", "审批状态", "dimension", "string"),
        ],
        "dimensions": [
            ("申请日期", "stat_date", "time", {"time_granularity": "month"}),
            ("审批状态", "status", "categorical", {}),
        ],
        "measures": [
            {"name": "apply_cnt", "business_name": "申请笔数", "field": "credit_apply_id", "agg": "count_distinct", "unit": "笔"},
            {
                "name": "pass_cnt",
                "business_name": "通过笔数",
                "field": "credit_apply_id",
                "agg": "count_distinct",
                "filter": "status = '通过'",
                "unit": "笔",
            },
            {
                "name": "decided_cnt",
                "business_name": "已决策笔数",
                "field": "credit_apply_id",
                "agg": "count_distinct",
                "filter": "status in ('通过','拒绝')",
                "unit": "笔",
            },
            {
                "name": "pending_cnt",
                "business_name": "审批中笔数",
                "field": "credit_apply_id",
                "agg": "count_distinct",
                "filter": "status = '审批中'",
                "unit": "笔",
            },
            {"name": "apply_amount_sum", "business_name": "申请金额求和", "field": "apply_amount", "agg": "sum", "unit": "CNY"},
            {
                "name": "pass_amount_sum",
                "business_name": "通过金额",
                "field": "apply_amount",
                "agg": "sum",
                "filter": "status = '通过'",
                "unit": "CNY",
            },
        ],
        "metrics": [
            {
                "name": "credit_apply_count",
                "business_name": "申请笔数",
                "synonyms": ["申请量"],
                "definition": "统计期内的信贷申请笔数",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "apply_cnt", "input")],
            },
            {
                "name": "credit_decided_count",
                "business_name": "已决策笔数",
                "definition": "状态为通过或拒绝的申请笔数，不含审批中",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "decided_cnt", "input")],
            },
            {
                "name": "credit_pass_count",
                "business_name": "通过笔数",
                "synonyms": ["通过量"],
                "definition": "状态为通过的申请笔数",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "pass_cnt", "input")],
            },
            {
                "name": "credit_pass_rate",
                "business_name": "审批通过率",
                "definition": "通过笔数 / 已决策笔数，分母不含审批中",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "credit_pass_count", "numerator"),
                    ("metric", "credit_decided_count", "denominator"),
                ],
            },
            {
                "name": "credit_apply_amount",
                "business_name": "申请金额",
                "definition": "信贷申请金额之和",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [("measure", "apply_amount_sum", "input")],
            },
            {
                "name": "credit_pass_amount",
                "business_name": "通过金额",
                "definition": "审批通过申请的金额之和",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [("measure", "pass_amount_sum", "input")],
            },
            {
                "name": "credit_amount_pass_rate",
                "business_name": "金额通过率",
                "definition": "通过金额 / 申请金额",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "credit_pass_amount", "numerator"),
                    ("metric", "credit_apply_amount", "denominator"),
                ],
            },
            {
                "name": "credit_conversion_rate",
                "business_name": "申请转化率",
                "synonyms": ["转化率"],
                "definition": "通过笔数 / 全部申请笔数，分母包含审批中",
                "metric_type": "conversion",
                "unit": "%",
                "inputs": [
                    ("metric", "credit_apply_count", "base"),
                    ("metric", "credit_pass_count", "conversion"),
                ],
            },
            {
                "name": "avg_apply_amount",
                "business_name": "件均申请金额",
                "synonyms": ["件均金额"],
                "definition": "申请金额 / 申请笔数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "credit_apply_amount", "numerator"),
                    ("metric", "credit_apply_count", "denominator"),
                ],
            },
            {
                "name": "credit_pending_count",
                "business_name": "审批中笔数",
                "synonyms": ["审批中"],
                "definition": "状态为审批中的申请笔数",
                "metric_type": "simple",
                "unit": "笔",
                "inputs": [("measure", "pending_cnt", "input")],
            },
        ],
    }
}

RELATIONSHIPS = [
    {
        "name": "apply_customer",
        "from": "bank_credit_apply",
        "from_field": "customer_id",
        "to": "dim_customer",
        "to_field": "customer_id",
    },
    {
        "name": "apply_product",
        "from": "bank_credit_apply",
        "from_field": "product_id",
        "to": "dim_product",
        "to_field": "product_id",
    },
    {
        "name": "apply_channel",
        "from": "bank_credit_apply",
        "from_field": "channel_id",
        "to": "dim_channel",
        "to_field": "channel_id",
    },
]

TERMS = [
    {
        "name": "审批通过率",
        "definition": "通过笔数 /（通过 + 拒绝），分母不含审批中",
    },
    {
        "name": "申请转化率",
        "synonyms": ["转化率"],
        "definition": "通过笔数 / 全部申请笔数，分母包含审批中",
    },
    {
        "name": "件均申请金额",
        "definition": "申请金额 / 申请笔数",
    },
    {
        "name": "审批中",
        "definition": "已提交但尚未给出审批结论的申请，不计入通过率分母",
    },
]

RULES = [
    {
        "name": "排除测试申请",
        "target_model": "bank_credit_apply",
        "rule_type": "filter",
        "condition": "credit_apply_id like 'TEST%'",
        "action": "exclude",
        "priority": 10,
    }
]

CONTEXTS = {
    "credit_pass_rate": {
        "business_name": "审批通过率",
        "synonyms": ["审批通过率"],
        "definition": "通过笔数 /（通过 + 拒绝），分母不含审批中",
        "examples": [
            {"question": "各渠道的审批通过率"},
            {"question": "各产品线的审批通过率"},
        ],
        "negative_examples": [{"question": "各机构的审批通过率（申请表没有机构字段）"}],
    },
    "credit_conversion_rate": {
        "business_name": "申请转化率",
        "synonyms": ["申请转化率", "转化率"],
        "definition": "通过笔数 / 全部申请笔数，分母包含审批中",
        "examples": [{"question": "申请到通过的转化率是多少"}],
        "negative_examples": [{"question": "各机构转化率（申请表没有机构字段）"}],
    },
    "avg_apply_amount": {
        "business_name": "件均申请金额",
        "synonyms": ["件均申请金额", "件均金额"],
        "definition": "申请金额 / 申请笔数",
        "examples": [{"question": "各渠道的件均申请金额"}],
        "negative_examples": [{"question": "件均放款金额（应使用贷款投放指标）"}],
    },
}


def main() -> None:
    model_names = list(MODELS)
    metric_names = [item["name"] for spec in MODELS.values() for item in spec.get("metrics", [])]

    step("1. 清理上一轮信贷审批示例数据")
    cleanup_scope(
        model_names,
        metric_names,
        [item["name"] for item in TERMS],
        [item["name"] for item in RULES],
        permission_subjects=["bank_analyst_credit"],
        clear_datasets=False,
    )

    step("2. 同步数据集目录")
    sync_datasets(MODELS)

    step("3. 主题域")
    domain_ids = {
        "approval": ensure_domain("信贷审批", "申请量、通过率、金额通过率与渠道/产品结构", "credit-ops"),
    }
    print(f"主题域：信贷审批({domain_ids['approval']})")

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
    create_permission("bank_credit_apply", "bank_analyst_credit", "status in ('通过','拒绝','审批中')", created)

    step("7. 校验、认证")
    validate_all(MODELS, created, bindings, metric_ids)

    step("8. 发布语义快照")
    publish()

    step("9. 问数验证")
    run_ask("各渠道的审批通过率")
    run_ask("各产品线的申请笔数和通过笔数")
    run_ask("各渠道的申请量和金额通过率")
    run_ask("审批中的申请有多少笔")
    run_ask("申请到通过的转化率是多少")

    print("\n完成：信贷审批场景已跑通（含 conversion 转化率）")


if __name__ == "__main__":
    main()