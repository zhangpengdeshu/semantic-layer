"""真实数据集场景：把 ChatBI 数据集“存款余额快照”接入语义层并建模。

数据来源（真实数据集，非本地造数）：
    dsetId = 39aa2246aa5443e6bdddab008249bafb
    name   = deposit_balance_snapshot
    table  = ceshi.f1_deposit_balance_snapshot（GBASE，2193 行）

做法：
1. 通过 ChatBI 网关读取数据集定义与全部明细；
2. 在本地 PG 建同名镜像表并装载真实明细（语义层 SQL 执行落在本地 PG）；
3. 把数据集元数据同步进语义目录（external_dataset_id 就是 dsetId）；
4. 按“存款余额（时点快照）”建模并完成绑定、校验、认证、发布；
5. 用真实问题跑通问数，并与手写 SQL 对账。

用法（在 semantic-layer 目录执行）：
    .venv/bin/python scripts/seed_chatbi_deposit_balance.py

可用环境变量覆盖网关地址：
    CHATBI_GATEWAY=http://127.0.0.1:8080/yusp-vip-manager
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "backend"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from sqlalchemy import bindparam, text  # noqa: E402

from bank_demo_common import HEADERS, api, certify, client, field, publish, step  # noqa: E402
from shared.db import read_session, write_session  # noqa: E402

DSET_ID = "39aa2246aa5443e6bdddab008249bafb"
GATEWAY = os.getenv("CHATBI_GATEWAY", "http://127.0.0.1:8080/yusp-vip-manager")
SOURCE_SYSTEM = "yusp_chatbi"
SCHEMA = "ceshi"
TABLE = "f1_deposit_balance_snapshot"
MODEL_NAME = "deposit_balance_snapshot"
DOMAIN_ID = 41  # 存款与财富

FIELD_SPECS = [
    field("data_dt", "数据日期", "time", "string"),
    field("branch", "支行", "dimension", "string"),
    field("product_category", "存款产品大类", "dimension", "string"),
    field("product_name", "存款产品名称", "dimension", "string"),
    field("rm", "客户经理", "dimension", "string"),
    field("customer_name", "客户名称", "key", "string", sensitivity="pii"),
    field("customer_type", "客户类型", "dimension", "string"),
    field("customer_level", "客户分层", "dimension", "string"),
    field("deposit_balance", "存款余额", "measure", "number", sensitivity="confidential"),
    field("daily_inflow", "当日流入", "measure", "number"),
    field("daily_outflow", "当日流出", "measure", "number"),
    field("daily_net_inflow", "当日净流入", "measure", "number"),
]

DIMENSIONS = [
    ("数据日期", "data_dt", "time", {"time_granularity": "month"}),
    ("支行", "branch", "categorical", {}),
    ("存款产品大类", "product_category", "categorical", {}),
    ("存款产品名称", "product_name", "categorical", {}),
    ("客户类型", "customer_type", "categorical", {}),
    ("客户分层", "customer_level", "categorical", {}),
    ("客户经理", "rm", "categorical", {}),
]

MEASURES = [
    {
        "name": "snapshot_deposit_balance_sum",
        "business_name": "存款余额求和",
        "field": "deposit_balance",
        "agg": "sum",
        "additivity": "semi_additive",
        "window_choice": "max",
        "time_field": "data_dt",
        "unit": "CNY",
    },
    {"name": "snapshot_daily_inflow_sum", "business_name": "当日流入求和", "field": "daily_inflow", "agg": "sum", "unit": "CNY"},
    {"name": "snapshot_daily_outflow_sum", "business_name": "当日流出求和", "field": "daily_outflow", "agg": "sum", "unit": "CNY"},
    {"name": "snapshot_daily_net_inflow_sum", "business_name": "当日净流入求和", "field": "daily_net_inflow", "agg": "sum", "unit": "CNY"},
    {
        "name": "snapshot_deposit_customer_cnt",
        "business_name": "存款客户数",
        "field": "customer_name",
        "agg": "count_distinct",
        "unit": "户",
    },
]

METRICS = [
    {
        "name": "deposit_balance_snapshot",
        "business_name": "存款时点余额",
        "synonyms": ["时点余额"],
        "definition": "存款余额日/月末快照，按日汇总后取期间最大值，不能跨期累加；查询需限定统计期间",
        "metric_type": "simple",
        "unit": "CNY",
        "inputs": [("measure", "snapshot_deposit_balance_sum", "input")],
    },
    {
        "name": "term_deposit_balance_snapshot",
        "business_name": "定期存款时点余额",
        "definition": "存款产品大类为定期存款的时点余额",
        "metric_type": "simple",
        "filter": "product_category = '定期存款'",
        "unit": "CNY",
        "inputs": [("measure", "snapshot_deposit_balance_sum", "input")],
    },
    {
        "name": "deposit_customer_count_snapshot",
        "business_name": "存款时点客户数",
        "definition": "有存款余额的客户数，按客户名称去重",
        "metric_type": "simple",
        "unit": "户",
        "inputs": [("measure", "snapshot_deposit_customer_cnt", "input")],
    },
    {
        "name": "avg_deposit_balance_snapshot",
        "business_name": "时点户均余额",
        "definition": "存款时点余额 / 存款时点客户数",
        "metric_type": "ratio",
        "unit": "CNY",
        "inputs": [
            ("metric", "deposit_balance_snapshot", "numerator"),
            ("metric", "deposit_customer_count_snapshot", "denominator"),
        ],
    },
    {
        "name": "term_deposit_ratio_snapshot",
        "business_name": "定期存款时点占比",
        "definition": "定期存款时点余额 / 存款时点余额",
        "metric_type": "ratio",
        "unit": "%",
        "inputs": [
            ("metric", "term_deposit_balance_snapshot", "numerator"),
            ("metric", "deposit_balance_snapshot", "denominator"),
        ],
    },
    {
        "name": "daily_inflow_snapshot",
        "business_name": "当日流入",
        "definition": "统计日当天流入金额之和",
        "metric_type": "simple",
        "unit": "CNY",
        "inputs": [("measure", "snapshot_daily_inflow_sum", "input")],
    },
    {
        "name": "daily_outflow_snapshot",
        "business_name": "当日流出",
        "definition": "统计日当天流出金额之和",
        "metric_type": "simple",
        "unit": "CNY",
        "inputs": [("measure", "snapshot_daily_outflow_sum", "input")],
    },
    {
        "name": "daily_net_inflow_snapshot",
        "business_name": "当日净流入",
        "definition": "统计日当天流入减流出，可跨期累加",
        "metric_type": "simple",
        "unit": "CNY",
        "inputs": [("measure", "snapshot_daily_net_inflow_sum", "input")],
    },
]

TERMS = [
    {
        "name": "存款时点余额",
        "synonyms": ["时点余额"],
        "definition": "某一快照日的存款余额，不能跨期累加；跨期查询取期间内最大值",
    },
    {
        "name": "当日净流入",
        "synonyms": ["净流入"],
        "definition": "统计日当天流入减流出，可跨期累加",
    },
    {
        "name": "客户分层",
        "synonyms": ["客户层级"],
        "definition": "核心客户、成长客户、维持客户、新客户、待提升客户",
    },
]

RULES = [
    {
        "name": "存款余额剔除理财",
        "target_type": "model",
        "rule_type": "filter",
        "condition": "product_category = '理财'",
        "action": "exclude",
        "priority": 10,
        "status": "active",
    },
]

CONTEXTS = {
    "deposit_balance_snapshot": {
        "business_name": "存款时点余额",
        "synonyms": ["存款时点余额", "时点余额"],
        "definition": "日/月末存款余额快照，按日汇总后取期间最大值，不跨期累加；理财不计入存款",
        "examples": [
            {"question": "2025年5月各客户分层的存款时点余额"},
            {"question": "2025年5月各存款产品大类的存款时点余额"},
        ],
        "negative_examples": [
            {"question": "不限定期间的存款时点余额（快照需限定统计期间）"},
            {"question": "各渠道的存款时点余额（数据集没有渠道维度）"},
        ],
    },
    "daily_net_inflow_snapshot": {
        "business_name": "当日净流入",
        "synonyms": ["当日净流入"],
        "definition": "流入减流出，可跨日累加",
        "examples": [{"question": "2025年5月各客户类型的当日净流入"}],
        "negative_examples": [{"question": "各渠道的当日净流入（数据集没有渠道维度）"}],
    },
}

ASK_QUESTIONS = [
    "2025年5月各客户分层的存款时点余额",
    "2025年5月各存款产品大类的存款时点余额",
    "2025年5月各客户分层的存款时点客户数",
    "2025年5月各客户类型的当日净流入",
    "2025年6月各客户分层的存款时点余额",
]


# --------------------------------------------------------------------------- 真实数据


def _gateway_get(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{GATEWAY}{path}", timeout=60) as response:
        return json.load(response)


def _gateway_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{GATEWAY}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def fetch_dataset() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    detail = _gateway_get(f"/api/unified/dataset/{DSET_ID}")["data"]
    collected: list[dict[str, Any]] = []
    page = 1
    while True:
        data = _gateway_post("/api/unified/dataset/preview", {"dsetId": DSET_ID, "page": page, "size": 1000})["data"]
        batch = data.get("dataList") or []
        collected.extend(batch)
        if not batch or len(collected) >= int(data.get("total") or 0):
            break
        page += 1
    return detail, collected


def load_mirror(rows: list[dict[str, Any]]) -> None:
    with write_session() as session:
        session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE} (
                  data_dt        VARCHAR(20)  NOT NULL,
                  branch         VARCHAR(255),
                  product_category VARCHAR(255),
                  product_name   VARCHAR(255),
                  rm             VARCHAR(255),
                  customer_name  VARCHAR(255),
                  customer_type  VARCHAR(255),
                  customer_level VARCHAR(255),
                  deposit_balance BIGINT NOT NULL DEFAULT 0,
                  daily_inflow   BIGINT,
                  daily_outflow  BIGINT,
                  daily_net_inflow BIGINT
                )
                """
            )
        )
        session.execute(text(f"TRUNCATE {SCHEMA}.{TABLE}"))
        session.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.{TABLE}
                  (data_dt, branch, product_category, product_name, rm, customer_name,
                   customer_type, customer_level, deposit_balance, daily_inflow, daily_outflow, daily_net_inflow)
                VALUES
                  (:data_dt, :branch, :product_category, :product_name, :rm, :customer_name,
                   :customer_type, :customer_level, :deposit_balance, :daily_inflow, :daily_outflow, :daily_net_inflow)
                """
            ),
            rows,
        )
        session.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_dt ON {SCHEMA}.{TABLE} (data_dt)"))
    print(f"镜像表：{SCHEMA}.{TABLE}，装载 {len(rows)} 行真实明细")


def sync_catalog(detail: dict[str, Any], rows: list[dict[str, Any]]) -> int:
    sample = rows[0] if rows else {}
    columns = []
    for item in detail["fieldList"]:
        name = item["name"]
        columns.append(
            {
                "column_name": name,
                "column_type": (item.get("fieldTableType") or "varchar").lower(),
                "business_name": item.get("dispName") or name,
                "sample_value": None if sample.get(name) is None else str(sample.get(name))[:64],
                "nullable": True,
            }
        )
    payload = {
        "source_system": SOURCE_SYSTEM,
        "datasets": [
            {
                "external_dataset_id": DSET_ID,
                "dataset_code": detail.get("name"),
                "dataset_name": "存款余额快照",
                "schema_name": detail["fieldList"][0].get("schemaDb") or SCHEMA,
                "table_name": detail.get("primaryTable") or TABLE,
                "description": detail.get("dsetDes"),
                "source_version": f"v{detail.get('version') or 1}",
                "columns": columns,
            }
        ],
    }
    result = api("post", "/catalog/datasets:sync", payload)
    print(f"目录同步：{result.get('synced')} 个数据集，{len(columns)} 列（external_dataset_id={DSET_ID}）")
    return result.get("synced", 0)


# --------------------------------------------------------------------------- 清理


def cleanup() -> None:
    metric_names = [item["name"] for item in METRICS]
    term_names = [item["name"] for item in TERMS]
    rule_names = [item["name"] for item in RULES]
    with write_session() as session:
        model_id = session.execute(
            text("SELECT model_id FROM t_sem_model WHERE name = :name"), {"name": MODEL_NAME}
        ).scalar()
        metric_ids = [
            int(row[0])
            for row in session.execute(
                text("SELECT metric_id FROM t_sem_metric WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
                {"names": metric_names},
            )
        ]
        if metric_ids:
            for table, column in (("t_sem_asset_context", "asset_id"), ("t_sem_certification", "asset_id")):
                session.execute(
                    text(f"DELETE FROM {table} WHERE asset_type = 'metric' AND {column} IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": metric_ids},
                )
            session.execute(
                text("DELETE FROM t_sem_metric WHERE metric_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": metric_ids},
            )
        if model_id:
            binding_ids = [
                int(row[0])
                for row in session.execute(
                    text("SELECT binding_id FROM t_sem_binding WHERE model_id = :id"), {"id": model_id}
                )
            ]
            if binding_ids:
                session.execute(
                    text("DELETE FROM t_sem_certification WHERE asset_type = 'binding' AND asset_id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": binding_ids},
                )
            session.execute(
                text("DELETE FROM t_sem_certification WHERE asset_type = 'model' AND asset_id = :id"), {"id": model_id}
            )
            session.execute(text("DELETE FROM t_sem_binding WHERE model_id = :id"), {"id": model_id})
            session.execute(text("DELETE FROM t_sem_asset_context WHERE asset_type = 'model' AND asset_id = :id"), {"id": model_id})
            session.execute(text("DELETE FROM t_sem_model WHERE model_id = :id"), {"id": model_id})
        if term_names:
            session.execute(
                text("DELETE FROM t_term WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
                {"names": term_names},
            )
        if rule_names:
            session.execute(
                text("DELETE FROM t_business_rule WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
                {"names": rule_names},
            )
    print("已清理上一轮同名模型/指标/术语/规则（未触碰其他场景）")


# --------------------------------------------------------------------------- 建模


def build_semantics() -> tuple[dict[str, Any], dict[str, int], dict[str, int]]:
    model = api(
        "post",
        "/models",
        {
            "domain_id": DOMAIN_ID,
            "name": MODEL_NAME,
            "business_name": "存款余额快照",
            "description": "接入 ChatBI 数据集 deposit_balance_snapshot：按客户/产品/快照日的存款余额，含流入流出",
            "owner": "demo-modeler",
            "max_hops": 3,
        },
    )
    model_id = int(model["model_id"])

    created_fields = api("post", f"/models/{model_id}/fields:batch", {"fields": FIELD_SPECS})
    field_ids = {item["name"]: int(item["field_id"]) for item in created_fields}

    api(
        "put",
        f"/models/{model_id}/grain",
        {"field_ids": [field_ids["data_dt"], field_ids["customer_name"], field_ids["product_name"]]},
    )

    for name, field_name, dimension_type, extra in DIMENSIONS:
        api(
            "post",
            f"/models/{model_id}/dimensions",
            {"name": name, "field_id": field_ids[field_name], "dimension_type": dimension_type, **extra},
        )

    measure_ids: dict[str, int] = {}
    for item in MEASURES:
        payload = {
            "name": item["name"],
            "business_name": item["business_name"],
            "field_id": field_ids[item["field"]],
            "agg": item["agg"],
            "additivity": item.get("additivity", "additive"),
            "unit": item.get("unit"),
        }
        if item.get("window_choice"):
            payload["window_choice"] = item["window_choice"]
        if item.get("time_field"):
            payload["agg_time_dimension"] = field_ids[item["time_field"]]
        measure_ids[item["name"]] = int(api("post", f"/models/{model_id}/measures", payload)["measure_id"])

    metric_ids: dict[str, int] = {}
    for item in METRICS:
        inputs = []
        for input_type, ref, role in item.get("inputs", []):
            ref_id = measure_ids[ref] if input_type == "measure" else metric_ids[ref]
            inputs.append({"input_type": input_type, "input_ref": ref_id, "role": role})
        metric = api(
            "post",
            "/metrics",
            {
                "model_id": model_id,
                "domain_id": DOMAIN_ID,
                "owner": "demo-modeler",
                "name": item["name"],
                "business_name": item["business_name"],
                "synonyms": item.get("synonyms", []),
                "definition": item["definition"],
                "metric_type": item["metric_type"],
                "filter": item.get("filter"),
                "unit": item.get("unit"),
                "inputs": inputs,
            },
        )
        metric_ids[item["name"]] = int(metric["metric_id"])

    for term in TERMS:
        api("post", "/terms", {"scope_type": "domain", **term})
    for rule in RULES:
        api("post", "/rules", {**rule, "target_id": model_id})
    for metric_name, context in CONTEXTS.items():
        api("put", f"/context/metric/{metric_ids[metric_name]}", context)

    print(
        f"模型：{MODEL_NAME}({model_id})，字段 {len(field_ids)}、维度 {len(DIMENSIONS)}、"
        f"度量 {len(measure_ids)}、指标 {len(metric_ids)}"
    )
    print("指标：" + "、".join(f"{key}({value})" for key, value in metric_ids.items()))
    return model, field_ids, metric_ids


def create_binding(model_id: int, field_ids: dict[str, int]) -> dict[str, Any]:
    datasets = api(
        "get",
        "/catalog/datasets",
        params={"source_system": SOURCE_SYSTEM, "page_size": 100},
    )["items"]
    dataset = next(item for item in datasets if item["external_dataset_id"] == DSET_ID)
    detail = api("get", f"/catalog/datasets/{dataset['dataset_id']}")
    column_ids = {item["column_name"]: int(item["column_id"]) for item in detail["columns"]}

    binding = api(
        "post",
        f"/models/{model_id}/bindings",
        {
            "binding_type": "dataset",
            "source_system": SOURCE_SYSTEM,
            "external_dataset_id": DSET_ID,
            "query_ref": f"{SCHEMA}.{TABLE}",
            "is_primary": True,
            "status": "draft",
            "source_version": f"v1",
        },
    )
    binding_id = int(binding["binding_id"])
    api(
        "put",
        f"/bindings/{binding_id}/field-mappings",
        {
            "items": [
                {
                    "field_id": field_ids[item["name"]],
                    "column_id": column_ids[item["name"]],
                    "column_name": item["name"],
                    "transform": "TO_DATE(data_dt, 'YYYYMMDD')" if item["name"] == "data_dt" else None,
                    "status": "draft",
                }
                for item in FIELD_SPECS
            ]
        },
    )
    api("post", f"/bindings/{binding_id}:set-primary")
    binding = api("get", f"/bindings/{binding_id}")
    print(f"绑定：{binding_id} → {SCHEMA}.{TABLE}，覆盖率 {round(binding['coverage'] * 100)}%")
    return binding


def validate_and_certify(model: dict[str, Any], binding: dict[str, Any], metric_ids: dict[str, int]) -> None:
    certify("binding", int(binding["binding_id"]), "ChatBI 真实数据集字段映射完整")

    semantic = api("post", f"/models/{model['model_id']}/validation", {"level": "semantic"})
    if semantic["status"] != "passed":
        raise RuntimeError(f"语义校验未通过：{json.dumps(semantic['issues'], ensure_ascii=False)}")
    for name, metric_id in metric_ids.items():
        result = api("post", f"/metrics/{metric_id}/validation")
        if result["status"] != "passed":
            raise RuntimeError(f"指标 {name} 校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")
    certify("model", int(model["model_id"]), "存款余额快照语义定义确认")
    for name, metric_id in metric_ids.items():
        certify("metric", metric_id, f"{name} 口径确认")

    queryable = api("post", f"/models/{model['model_id']}/validation", {"level": "queryable"})
    if queryable["status"] != "passed":
        raise RuntimeError(f"可问数校验未通过：{json.dumps(queryable['issues'], ensure_ascii=False)}")
    warnings = [item["code"] for item in queryable["issues"] if item["level"] == "warning"]
    print(f"校验：semantic/queryable 均 passed，可问数={queryable.get('queryable')}，warning={warnings}")


# --------------------------------------------------------------------------- 问数


def ask(question: str) -> dict[str, Any]:
    response = client.post("/api/ask", json={"question": question, "domain_id": DOMAIN_ID}, headers=HEADERS)
    body = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"问数失败 {response.status_code}: {body}")
    response = body.get("data", body)
    print(f"\n问数：{question}")
    if response["status"] != "ok":
        print(f"  状态：{response['status']}，澄清：{json.dumps(response.get('clarification'), ensure_ascii=False)}")
        return response
    result = response["result"]
    print(f"  状态：ok，快照：{result['snapshot_version']}，行数：{result['row_count']}，列：{result['columns']}")
    for row in result["rows"][:8]:
        print(f"    {row}")
    print(f"  SQL：{result['sql']}")
    return response


def verify_with_raw_sql() -> None:
    with read_session() as session:
        levels = session.execute(
            text(
                f"""
                SELECT customer_level, MAX(bal) AS balance
                FROM (
                  SELECT customer_level, data_dt, SUM(deposit_balance) AS bal
                  FROM {SCHEMA}.{TABLE}
                  WHERE data_dt >= '20250501' AND data_dt < '20250601'
                    AND product_category <> '理财'
                  GROUP BY customer_level, data_dt
                ) t
                GROUP BY customer_level
                ORDER BY customer_level
                """
            )
        ).fetchall()
        total = session.execute(
            text(
                f"""
                SELECT MAX(bal) FROM (
                  SELECT data_dt, SUM(deposit_balance) AS bal
                  FROM {SCHEMA}.{TABLE}
                  WHERE data_dt >= '20250501' AND data_dt < '20250601'
                    AND product_category <> '理财'
                  GROUP BY data_dt
                ) t
                """
            )
        ).scalar()
    print("\n原始 SQL 对账（2025年5月，剔除理财）：")
    for level, balance in levels:
        print(f"  {level}: {balance}")
    print(f"  合计: {total}")


def main() -> None:
    step("1. 读取真实数据集定义与明细")
    detail, rows = fetch_dataset()
    print(
        f"数据集：{detail.get('name')}（{detail.get('dsetDes')}），"
        f"{detail.get('datasourceTypeDesc')} {detail['fieldList'][0].get('schemaDb')}.{detail.get('primaryTable')}，"
        f"共 {len(rows)} 行 / {len({row['data_dt'] for row in rows})} 个快照日"
    )

    step("2. 建本地镜像表并装载真实数据")
    load_mirror(rows)

    step("3. 清理同名资产并同步数据集目录")
    cleanup()
    sync_catalog(detail, rows)

    step("4. 建立语义模型、字段、维度、度量、指标、知识")
    model, field_ids, metric_ids = build_semantics()

    step("5. 数据绑定与字段映射")
    binding = create_binding(int(model["model_id"]), field_ids)

    step("6. 校验、认证、发布")
    validate_and_certify(model, binding, metric_ids)
    snapshot = publish()

    step("7. 真实问数")
    for question in ASK_QUESTIONS:
        ask(question)

    step("8. 与原始 SQL 对账")
    verify_with_raw_sql()
    print(f"\n完成：数据集 {DSET_ID} 已接入语义层，快照 {snapshot['version']}")


if __name__ == "__main__":
    main()