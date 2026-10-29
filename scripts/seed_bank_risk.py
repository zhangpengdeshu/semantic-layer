"""银行场景 5/5：风险合规监控写入语义层。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_risk.py

覆盖文档 9.5：风险事件、风险金额、待处置、处置率与高风险占比。
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
    "bank_risk_event": {
        "domain": "risk",
        "name": "bank_risk_event",
        "business_name": "风险事件",
        "description": "一行一条风险预警事件，粒度 risk_event_id",
        "table": "dwd_risk_event",
        "grain": "risk_event_id",
        "max_hops": 3,
        "fields": [
            field("risk_event_id", "风险事件号", "key", "string"),
            field("customer_id", "客户号", "key", "string"),
            field("risk_type_id", "风险类型号", "key", "string"),
            field("risk_level_id", "风险等级号", "key", "string"),
            field("amount", "风险金额", "measure", "number"),
            field("stat_date", "统计日期", "time", "date"),
            field("status", "处置状态", "dimension", "string"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("处置状态", "status", "categorical", {}),
        ],
        "measures": [
            {
                "name": "event_cnt",
                "business_name": "风险事件数",
                "field": "risk_event_id",
                "agg": "count_distinct",
                "unit": "件",
            },
            {"name": "risk_amount_sum", "business_name": "风险金额求和", "field": "amount", "agg": "sum", "unit": "CNY"},
            {
                "name": "pending_cnt",
                "business_name": "待处置事件数",
                "field": "risk_event_id",
                "agg": "count_distinct",
                "filter": "status = '待处置'",
                "unit": "件",
            },
            {
                "name": "handled_cnt",
                "business_name": "已处置事件数",
                "field": "risk_event_id",
                "agg": "count_distinct",
                "filter": "status = '已处置'",
                "unit": "件",
            },
            {
                "name": "high_level_cnt",
                "business_name": "高风险事件数",
                "field": "risk_event_id",
                "agg": "count_distinct",
                "filter": "risk_level_id = 'RL001'",
                "unit": "件",
            },
        ],
        "metrics": [
            {
                "name": "risk_event_count",
                "business_name": "风险事件数",
                "definition": "统计期内的风险预警事件数，按 risk_event_id 去重",
                "metric_type": "simple",
                "unit": "件",
                "inputs": [("measure", "event_cnt", "input")],
            },
            {
                "name": "risk_amount",
                "business_name": "风险金额",
                "synonyms": ["事件金额"],
                "definition": "风险事件的涉及金额之和",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [("measure", "risk_amount_sum", "input")],
            },
            {
                "name": "pending_event_count",
                "business_name": "待处置事件数",
                "synonyms": ["待处置事件", "待处置"],
                "definition": "状态为待处置的风险事件数",
                "metric_type": "simple",
                "unit": "件",
                "inputs": [("measure", "pending_cnt", "input")],
            },
            {
                "name": "handled_event_count",
                "business_name": "已处置事件数",
                "synonyms": ["已处置"],
                "definition": "状态为已处置的风险事件数",
                "metric_type": "simple",
                "unit": "件",
                "inputs": [("measure", "handled_cnt", "input")],
            },
            {
                "name": "high_risk_event_count",
                "business_name": "高风险事件数",
                "definition": "风险等级为高的风险事件数",
                "metric_type": "simple",
                "unit": "件",
                "inputs": [("measure", "high_level_cnt", "input")],
            },
            {
                "name": "high_risk_ratio",
                "business_name": "高风险占比",
                "synonyms": ["高风险事件占比"],
                "definition": "高风险事件数 / 全部风险事件数",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "high_risk_event_count", "numerator"),
                    ("metric", "risk_event_count", "denominator"),
                ],
            },
            {
                "name": "disposal_rate",
                "business_name": "处置率",
                "definition": "已处置事件数 / 全部风险事件数",
                "metric_type": "ratio",
                "unit": "%",
                "inputs": [
                    ("metric", "handled_event_count", "numerator"),
                    ("metric", "risk_event_count", "denominator"),
                ],
            },
            {
                "name": "avg_risk_amount",
                "business_name": "件均风险金额",
                "synonyms": ["件均金额"],
                "definition": "风险金额 / 风险事件数",
                "metric_type": "ratio",
                "unit": "CNY",
                "inputs": [
                    ("metric", "risk_amount", "numerator"),
                    ("metric", "risk_event_count", "denominator"),
                ],
            },
        ],
    },
    "risk_daily": {
        "domain": "risk",
        "name": "risk_daily",
        "business_name": "风险日汇总",
        "description": "按日、风险类型、风险等级汇总的风险事件，多字段粒度",
        "table": "dws_risk_daily",
        "grain": ["stat_date", "risk_type", "risk_level"],
        "max_hops": 2,
        "fields": [
            field("stat_date", "统计日期", "time", "date"),
            field("risk_type", "风险类型", "dimension", "string"),
            field("risk_level", "风险等级", "dimension", "string"),
            field("event_cnt", "事件数", "measure", "number"),
            field("amount", "风险金额", "measure", "number"),
        ],
        "dimensions": [
            ("统计日期", "stat_date", "time", {"time_granularity": "month"}),
            ("风险类型", "risk_type", "categorical", {}),
            ("风险等级", "risk_level", "categorical", {}),
        ],
        "measures": [
            {"name": "daily_event_cnt", "business_name": "日风险事件数", "field": "event_cnt", "agg": "sum", "unit": "件"},
            {"name": "daily_amount_sum", "business_name": "日风险金额", "field": "amount", "agg": "sum", "unit": "CNY"},
        ],
        "metrics": [
            {
                "name": "risk_daily_event_count",
                "business_name": "风险日事件数",
                "definition": "风险日汇总表的事件数之和",
                "metric_type": "simple",
                "unit": "件",
                "inputs": [("measure", "daily_event_cnt", "input")],
            },
            {
                "name": "risk_daily_amount",
                "business_name": "风险日金额",
                "definition": "风险日汇总表的风险金额之和",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [("measure", "daily_amount_sum", "input")],
            },
        ],
    },
}

RELATIONSHIPS = [
    {
        "name": "risk_type",
        "from": "bank_risk_event",
        "from_field": "risk_type_id",
        "to": "dim_risk_type",
        "to_field": "risk_type_id",
    },
    {
        "name": "risk_level",
        "from": "bank_risk_event",
        "from_field": "risk_level_id",
        "to": "dim_risk_level",
        "to_field": "risk_level_id",
    },
    {
        "name": "risk_customer",
        "from": "bank_risk_event",
        "from_field": "customer_id",
        "to": "dim_customer",
        "to_field": "customer_id",
    },
]

TERMS = [
    {
        "name": "风险事件",
        "definition": "一条风险预警记录，按 risk_event_id 去重，不按客户去重",
    },
    {
        "name": "高风险",
        "definition": "risk_level_id = 'RL001'，即等级为高",
    },
    {
        "name": "处置率",
        "definition": "已处置事件数 / 全部事件数",
    },
    {
        "name": "待处置",
        "definition": "已预警但尚未处置的事件，属于处置状态，不是风险等级",
    },
]

RULES = [
    {
        "name": "排除测试风险事件",
        "target_model": "bank_risk_event",
        "rule_type": "filter",
        "condition": "risk_event_id like 'TEST%'",
        "action": "exclude",
        "priority": 10,
    }
]

CONTEXTS = {
    "high_risk_ratio": {
        "business_name": "高风险占比",
        "synonyms": ["高风险占比", "高风险事件占比"],
        "definition": "高风险事件数 / 全部风险事件数",
        "examples": [{"question": "高风险事件占比是多少"}],
        "negative_examples": [{"question": "各渠道高风险占比（风险事件没有渠道字段）"}],
    },
    "disposal_rate": {
        "business_name": "处置率",
        "synonyms": ["处置率"],
        "definition": "已处置事件数 / 全部风险事件数，待处置不计入分子",
        "examples": [{"question": "各风险等级的风险事件数和处置率"}],
        "negative_examples": [{"question": "各渠道处置率（风险事件没有渠道字段）"}],
    },
    "risk_amount": {
        "business_name": "风险金额",
        "synonyms": ["风险金额", "事件金额"],
        "definition": "风险事件涉及金额之和",
        "examples": [{"question": "各风险类型的事件金额"}],
        "negative_examples": [{"question": "各机构的风险金额（风险事件没有机构字段）"}],
    },
}


def main() -> None:
    model_names = list(MODELS)
    metric_names = [item["name"] for spec in MODELS.values() for item in spec.get("metrics", [])]

    step("1. 清理上一轮风险合规示例数据")
    cleanup_scope(
        model_names,
        metric_names,
        [item["name"] for item in TERMS],
        [item["name"] for item in RULES],
        permission_subjects=["bank_analyst_risk"],
        clear_datasets=False,
    )

    step("2. 同步数据集目录")
    sync_datasets(MODELS)

    step("3. 主题域")
    domain_ids = {"risk": ensure_domain("风险合规", "风险事件、等级、处置进度与类型结构", "risk-management")}
    print(f"主题域：风险合规({domain_ids['risk']})")

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
    create_permission("bank_risk_event", "bank_analyst_risk", "status in ('待处置','已处置')", created)

    step("7. 校验、认证")
    validate_all(MODELS, created, bindings, metric_ids)

    step("8. 发布语义快照")
    publish()

    step("9. 问数验证")
    run_ask("各风险等级的风险事件数、风险金额和处置率")
    run_ask("各风险类型的待处置事件有多少")
    run_ask("高风险事件占比是多少")
    run_ask("待处置事件有多少笔")
    run_ask("各风险类型的事件金额是多少")

    print("\n完成：风险合规场景已跑通")


if __name__ == "__main__":
    main()