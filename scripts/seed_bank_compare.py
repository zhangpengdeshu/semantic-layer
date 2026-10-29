"""把 9.6 同环比演示补充到系统（不重建已有模型）。

场景 1 已建好 `loan_daily`、`dim_org`、`dim_city` 与 `daily_loan_amount`，
本脚本只补齐同环比知识、指标上下文并发布快照，然后跑三条对比问数。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_bank_compare.py
"""

from __future__ import annotations

from bank_demo_common import api, publish, run_ask, step

TERMS = [
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

CONTEXT = {
    "business_name": "贷款投放金额",
    "synonyms": ["放款金额", "投放金额"],
    "definition": "统计期内贷款产品的放款金额；同比/环比是查询修饰符，不新建指标",
    "examples": [
        {"question": "2026年9月贷款投放金额同比是多少"},
        {"question": "2026年9月贷款投放金额环比是多少"},
        {"question": "2026年9月各机构类型的贷款投放金额同比"},
    ],
    "negative_examples": [{"question": "各渠道贷款投放同比（loan_daily 没有渠道维度）"}],
}


def find_metric(name: str) -> int:
    page = api("get", "/metrics", params={"page_size": 200})
    for item in page.get("items", []):
        if item["name"] == name:
            return int(item["metric_id"])
    raise RuntimeError(f"指标不存在：{name}，请先执行 seed_bank_credit.py")


def upsert_term(term: dict) -> None:
    existing = next((item for item in api("get", "/terms") if item["name"] == term["name"]), None)
    if existing:
        api("patch", f"/terms/{existing['term_id']}", term)
        print(f"术语已更新：{term['name']}")
    else:
        api("post", "/terms", {"scope_type": "domain", **term})
        print(f"术语已创建：{term['name']}")


def main() -> None:
    step("1. 补齐同环比术语")
    for term in TERMS:
        upsert_term(term)

    step("2. 更新贷款投放金额的指标上下文")
    metric_id = find_metric("daily_loan_amount")
    api("put", f"/context/metric/{metric_id}", CONTEXT)
    print(f"指标上下文已更新：daily_loan_amount({metric_id})")

    step("3. 发布语义快照")
    publish()

    step("4. 同环比问数")
    run_ask("2026年9月贷款投放金额同比是多少")
    run_ask("2026年9月贷款投放金额环比是多少")
    run_ask("2026年9月各机构类型的贷款投放金额同比")

    print("\n完成：同环比场景已补充到系统（工作台可看到最近问数）")


if __name__ == "__main__":
    main()