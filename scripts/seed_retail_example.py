"""按《语义建模示例-零售经营》一键跑通语义层全链路。

用法（在 semantic-layer 目录执行）：

    .venv/bin/python scripts/seed_retail_example.py

执行内容：
1. 重建 4 张零售样例物理表，并写入 2026-08 ~ 2026-10 的样例数据；
2. 通过 FastAPI TestClient 走真实 API：主题域 → 模型 → 字段 → 粒度 → 维度 → 度量 → 关系 → 指标；
3. 同步数据集目录 → 创建绑定 → 字段映射 → 认证；
4. 写入知识上下文（术语 / 业务规则 / 资产上下文）与权限策略；
5. 执行 semantic / queryable 校验、资产认证、发布语义快照；
6. 用「上月华东地区各渠道的 GMV 和客单价」验证问数结果。

脚本可重复执行：每次都会先清理上一轮零售示例数据再重建。
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import bindparam, text  # noqa: E402

from app.main import app  # noqa: E402
from shared.db import write_session  # noqa: E402

API = "/api/semantic/v1"
HEADERS = {"X-User-Id": "demo-modeler", "X-Roles": "admin,modeler,engineer,reviewer"}
client = TestClient(app)

DOMAIN_NAME = "零售经营"
MODEL_NAMES = ["retail_order", "retail_customer", "retail_store", "retail_product"]
METRIC_NAMES = ["gmv", "order_count", "refund_amount", "aov", "refund_rate", "net_gmv"]
TERM_NAMES = ["GMV", "客单价", "净 GMV"]
RULE_NAMES = ["排除无效订单"]
DATASET_IDS = {
    "order": "retail.ds_order_detail",
    "customer": "retail.ds_customer",
    "store": "retail.ds_store",
    "product": "retail.ds_product",
}
QUERY_REFS = {
    "order": "public.retail_order_detail",
    "customer": "public.retail_customer",
    "store": "public.retail_store",
    "product": "public.retail_product",
}


# --------------------------------------------------------------------------- 工具


def api(method: str, path: str, payload: Any = None, params: Any = None) -> Any:
    """调用语义层 API，失败时抛出带响应体的异常。"""
    kwargs: dict[str, Any] = {"headers": HEADERS}
    if payload is not None:
        kwargs["json"] = payload
    if params is not None:
        kwargs["params"] = params
    response = getattr(client, method)(f"{API}{path}", **kwargs)
    try:
        body = response.json()
    except ValueError:  # pragma: no cover - 网关异常页
        raise RuntimeError(f"{method.upper()} {path} -> {response.status_code}: {response.text}")
    if response.status_code >= 400:
        raise RuntimeError(f"{method.upper()} {path} -> {response.status_code}: {body}")
    return body.get("data", body)


def step(title: str) -> None:
    print(f"\n=== {title}")


# --------------------------------------------------------------------------- 物理样例表


def create_physical_tables() -> None:
    rng = random.Random(20261028)
    stores = [
        ("S001", "上海旗舰店", "华东", "上海", "直营", date(2018, 5, 1)),
        ("S002", "杭州湖滨店", "华东", "杭州", "直营", date(2019, 9, 12)),
        ("S003", "北京国贸店", "华北", "北京", "直营", date(2017, 3, 8)),
        ("S004", "天津滨海店", "华北", "天津", "加盟", date(2020, 6, 18)),
        ("S005", "广州天河店", "华南", "广州", "直营", date(2018, 11, 2)),
        ("S006", "深圳南山店", "华南", "深圳", "加盟", date(2021, 4, 26)),
    ]
    levels = ["普通", "银卡", "金卡", "白金"]
    customers = [
        (
            f"C{index:04d}",
            f"客户{index:03d}",
            levels[index % len(levels)],
            date(2020, 1, 1) + timedelta(days=index * 37),
            stores[index % len(stores)][2],
        )
        for index in range(1, 21)
    ]
    products = [
        ("P1001", "智能电视", "家电", "星辰", 3299.00),
        ("P1002", "空气净化器", "家电", "星辰", 1299.00),
        ("P1003", "蓝牙耳机", "数码", "云海", 499.00),
        ("P1004", "机械键盘", "数码", "云海", 399.00),
        ("P1005", "坚果礼盒", "食品", "晨光", 129.00),
        ("P1006", "精品咖啡豆", "食品", "晨光", 89.00),
        ("P1007", "轻羽绒外套", "服饰", "云海", 699.00),
        ("P1008", "运动跑鞋", "服饰", "星辰", 559.00),
        ("P1009", "厨房刀具套装", "家电", "晨光", 899.00),
        ("P1010", "保温杯", "服饰", "晨光", 159.00),
    ]

    orders = []
    order_seq = 0
    start, end = date(2026, 8, 1), date(2026, 10, 27)
    day = start
    while day <= end:
        for _ in range(6):
            order_seq += 1
            store = stores[rng.randrange(len(stores))]
            customer = customers[rng.randrange(len(customers))]
            product = products[rng.randrange(len(products))]
            status = rng.choices(
                ["paid", "shipped", "completed", "refunded"], weights=[35, 20, 35, 10], k=1
            )[0]
            amount = round(float(product[4]) * rng.choice([1, 1, 1, 2]), 2)
            refund = round(amount * rng.uniform(0.3, 1.0), 2) if status == "refunded" else 0.0
            orders.append(
                (
                    f"O{day.strftime('%Y%m%d')}{order_seq:05d}",
                    customer[0],
                    store[0],
                    product[0],
                    day,
                    amount,
                    refund,
                    status,
                    str(rng.choice([1, 2, 3])),
                    rng.randint(1, 5),
                )
            )
        day += timedelta(days=1)

    ddl = """
    DROP TABLE IF EXISTS public.retail_order_detail;
    DROP TABLE IF EXISTS public.retail_customer;
    DROP TABLE IF EXISTS public.retail_store;
    DROP TABLE IF EXISTS public.retail_product;

    CREATE TABLE public.retail_store (
      store_no   VARCHAR(32) PRIMARY KEY,
      store_name VARCHAR(128) NOT NULL,
      region     VARCHAR(32)  NOT NULL,
      city       VARCHAR(64)  NOT NULL,
      store_type VARCHAR(32)  NOT NULL,
      open_date  DATE         NOT NULL
    );

    CREATE TABLE public.retail_customer (
      cust_no       VARCHAR(32) PRIMARY KEY,
      cust_name     VARCHAR(128) NOT NULL,
      cust_level    VARCHAR(32)  NOT NULL,
      register_date DATE         NOT NULL,
      region        VARCHAR(32)  NOT NULL
    );

    CREATE TABLE public.retail_product (
      sku_no   VARCHAR(32) PRIMARY KEY,
      sku_name VARCHAR(128)  NOT NULL,
      category VARCHAR(32)   NOT NULL,
      brand    VARCHAR(64)   NOT NULL,
      price    NUMERIC(18,2) NOT NULL
    );

    CREATE TABLE public.retail_order_detail (
      order_no     VARCHAR(32) PRIMARY KEY,
      cust_no      VARCHAR(32) NOT NULL,
      store_no     VARCHAR(32) NOT NULL,
      sku_no       VARCHAR(32) NOT NULL,
      dt           DATE        NOT NULL,
      amt          NUMERIC(18,2) NOT NULL,
      refund_amt   NUMERIC(18,2) NOT NULL DEFAULT 0,
      order_status VARCHAR(16) NOT NULL,
      channel_code VARCHAR(8)  NOT NULL,
      qty          INT         NOT NULL
    );
    """

    with write_session() as session:
        for statement in [item.strip() for item in ddl.split(";") if item.strip()]:
            session.execute(text(statement))
        session.execute(
            text(
                "INSERT INTO public.retail_store (store_no, store_name, region, city, store_type, open_date) "
                "VALUES (:store_no, :store_name, :region, :city, :store_type, :open_date)"
            ),
            [
                {
                    "store_no": item[0],
                    "store_name": item[1],
                    "region": item[2],
                    "city": item[3],
                    "store_type": item[4],
                    "open_date": item[5],
                }
                for item in stores
            ],
        )
        session.execute(
            text(
                "INSERT INTO public.retail_customer (cust_no, cust_name, cust_level, register_date, region) "
                "VALUES (:cust_no, :cust_name, :cust_level, :register_date, :region)"
            ),
            [
                {
                    "cust_no": item[0],
                    "cust_name": item[1],
                    "cust_level": item[2],
                    "register_date": item[3],
                    "region": item[4],
                }
                for item in customers
            ],
        )
        session.execute(
            text(
                "INSERT INTO public.retail_product (sku_no, sku_name, category, brand, price) "
                "VALUES (:sku_no, :sku_name, :category, :brand, :price)"
            ),
            [
                {"sku_no": item[0], "sku_name": item[1], "category": item[2], "brand": item[3], "price": item[4]}
                for item in products
            ],
        )
        session.execute(
            text(
                """
                INSERT INTO public.retail_order_detail
                  (order_no, cust_no, store_no, sku_no, dt, amt, refund_amt, order_status, channel_code, qty)
                VALUES
                  (:order_no, :cust_no, :store_no, :sku_no, :dt, :amt, :refund_amt, :order_status, :channel_code, :qty)
                """
            ),
            [
                {
                    "order_no": item[0],
                    "cust_no": item[1],
                    "store_no": item[2],
                    "sku_no": item[3],
                    "dt": item[4],
                    "amt": item[5],
                    "refund_amt": item[6],
                    "order_status": item[7],
                    "channel_code": item[8],
                    "qty": item[9],
                }
                for item in orders
            ],
        )

    print(f"物理表就绪：门店 {len(stores)}、客户 {len(customers)}、商品 {len(products)}、订单 {len(orders)}")


# --------------------------------------------------------------------------- 清理


def cleanup() -> None:
    with write_session() as session:
        def ids(sql: str, names: list[str]) -> list[int]:
            statement = text(sql).bindparams(bindparam("names", expanding=True))
            return [int(row[0]) for row in session.execute(statement, {"names": names})]

        model_ids = ids("SELECT model_id FROM t_sem_model WHERE name IN :names", MODEL_NAMES)
        metric_ids = ids("SELECT metric_id FROM t_sem_metric WHERE name IN :names", METRIC_NAMES)

        if model_ids:
            statement = text(
                "DELETE FROM t_sem_join_edge WHERE from_model_id IN :ids OR to_model_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True))
            session.execute(statement, {"ids": model_ids})

        if metric_ids:
            session.execute(
                text("DELETE FROM t_sem_metric WHERE metric_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": metric_ids},
            )

        if model_ids:
            session.execute(
                text("DELETE FROM t_sem_binding WHERE model_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": model_ids},
            )
            session.execute(
                text("DELETE FROM t_sem_model WHERE model_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": model_ids},
            )
            for asset_type, asset_ids in (("model", model_ids), ("metric", metric_ids)):
                if not asset_ids:
                    continue
                session.execute(
                    text(
                        "DELETE FROM t_sem_asset_context WHERE asset_type = :asset_type AND asset_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"asset_type": asset_type, "ids": asset_ids},
                )
                session.execute(
                    text(
                        "DELETE FROM t_sem_certification WHERE asset_type = :asset_type AND asset_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"asset_type": asset_type, "ids": asset_ids},
                )

        session.execute(text("DELETE FROM t_sem_certification WHERE asset_type = 'binding'"))
        session.execute(text("DELETE FROM t_ext_dataset WHERE source_system = 'retail_demo'"))
        session.execute(
            text("DELETE FROM t_term WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
            {"names": TERM_NAMES},
        )
        session.execute(
            text("DELETE FROM t_business_rule WHERE name IN :names").bindparams(
                bindparam("names", expanding=True)
            ),
            {"names": RULE_NAMES},
        )
        session.execute(text("DELETE FROM t_permission WHERE subject_id = 'analyst'"))
        session.execute(text("DELETE FROM t_sem_snapshot"))
        session.execute(text("DELETE FROM t_query_log"))

    print("已清理上一轮零售示例数据（物理样例表将在下一步重建）")


# --------------------------------------------------------------------------- 目录 / 建模


def sync_catalog() -> None:
    datasets = [
        {
            "external_dataset_id": DATASET_IDS["order"],
            "dataset_code": "ds_order_detail",
            "dataset_name": "订单明细",
            "schema_name": "public",
            "table_name": "retail_order_detail",
            "description": "零售订单明细，一行一个订单",
            "source_version": "v1",
            "columns": [
                {"column_name": "order_no", "column_type": "varchar(32)", "business_name": "订单号", "sample_value": "O2026090100001"},
                {"column_name": "cust_no", "column_type": "varchar(32)", "business_name": "客户号", "sample_value": "C0001"},
                {"column_name": "store_no", "column_type": "varchar(32)", "business_name": "门店号", "sample_value": "S001"},
                {"column_name": "sku_no", "column_type": "varchar(32)", "business_name": "商品号", "sample_value": "P1001"},
                {"column_name": "dt", "column_type": "date", "business_name": "下单日期", "sample_value": "2026-09-01"},
                {"column_name": "amt", "column_type": "numeric(18,2)", "business_name": "订单金额", "sample_value": "3299.00"},
                {"column_name": "refund_amt", "column_type": "numeric(18,2)", "business_name": "退款金额", "sample_value": "0.00"},
                {"column_name": "order_status", "column_type": "varchar(16)", "business_name": "订单状态", "sample_value": "paid"},
                {"column_name": "channel_code", "column_type": "varchar(8)", "business_name": "渠道", "sample_value": "1"},
                {"column_name": "qty", "column_type": "int4", "business_name": "商品件数", "sample_value": "2"},
            ],
        },
        {
            "external_dataset_id": DATASET_IDS["customer"],
            "dataset_code": "ds_customer",
            "dataset_name": "客户",
            "schema_name": "public",
            "table_name": "retail_customer",
            "description": "客户维度表",
            "source_version": "v1",
            "columns": [
                {"column_name": "cust_no", "column_type": "varchar(32)", "business_name": "客户号", "sample_value": "C0001"},
                {"column_name": "cust_name", "column_type": "varchar(128)", "business_name": "客户名称", "sample_value": "客户001"},
                {"column_name": "cust_level", "column_type": "varchar(32)", "business_name": "客户等级", "sample_value": "金卡"},
                {"column_name": "register_date", "column_type": "date", "business_name": "注册日期", "sample_value": "2020-01-01"},
                {"column_name": "region", "column_type": "varchar(32)", "business_name": "所属区域", "sample_value": "华东"},
            ],
        },
        {
            "external_dataset_id": DATASET_IDS["store"],
            "dataset_code": "ds_store",
            "dataset_name": "门店",
            "schema_name": "public",
            "table_name": "retail_store",
            "description": "门店维度表",
            "source_version": "v1",
            "columns": [
                {"column_name": "store_no", "column_type": "varchar(32)", "business_name": "门店号", "sample_value": "S001"},
                {"column_name": "store_name", "column_type": "varchar(128)", "business_name": "门店名称", "sample_value": "上海旗舰店"},
                {"column_name": "region", "column_type": "varchar(32)", "business_name": "区域", "sample_value": "华东"},
                {"column_name": "city", "column_type": "varchar(64)", "business_name": "城市", "sample_value": "上海"},
                {"column_name": "store_type", "column_type": "varchar(32)", "business_name": "门店类型", "sample_value": "直营"},
                {"column_name": "open_date", "column_type": "date", "business_name": "开业日期", "sample_value": "2018-05-01"},
            ],
        },
        {
            "external_dataset_id": DATASET_IDS["product"],
            "dataset_code": "ds_product",
            "dataset_name": "商品",
            "schema_name": "public",
            "table_name": "retail_product",
            "description": "商品维度表",
            "source_version": "v1",
            "columns": [
                {"column_name": "sku_no", "column_type": "varchar(32)", "business_name": "商品号", "sample_value": "P1001"},
                {"column_name": "sku_name", "column_type": "varchar(128)", "business_name": "商品名称", "sample_value": "智能电视"},
                {"column_name": "category", "column_type": "varchar(32)", "business_name": "品类", "sample_value": "家电"},
                {"column_name": "brand", "column_type": "varchar(64)", "business_name": "品牌", "sample_value": "星辰"},
                {"column_name": "price", "column_type": "numeric(18,2)", "business_name": "标准单价", "sample_value": "3299.00"},
            ],
        },
    ]
    result = api("post", "/catalog/datasets:sync", {"source_system": "retail_demo", "datasets": datasets})
    print(f"数据集目录同步：{result.get('synced')} 个")


def ensure_domain() -> int:
    page = api("get", "/domains", params={"q": DOMAIN_NAME, "page_size": 50})
    for item in page.get("items", []):
        if item["name"] == DOMAIN_NAME:
            return int(item["domain_id"])
    item = api(
        "post",
        "/domains",
        {
            "name": DOMAIN_NAME,
            "description": "订单、客户、门店、商品的经营分析",
            "owner": "data-team",
            "members": [{"user_id": "demo-modeler", "role": "modeler"}],
        },
    )
    return int(item["domain_id"])


def build_models(domain_id: int) -> dict[str, dict[str, Any]]:
    definitions = [
        ("order", "retail_order", "订单", "一行一个订单，粒度 order_id"),
        ("customer", "retail_customer", "客户", "一行一个客户，粒度 customer_id"),
        ("store", "retail_store", "门店", "一行一个门店，粒度 store_id"),
        ("product", "retail_product", "商品", "一行一个商品，粒度 product_id"),
    ]
    models: dict[str, dict[str, Any]] = {}
    for key, name, business_name, description in definitions:
        item = api(
            "post",
            "/models",
            {
                "domain_id": domain_id,
                "name": name,
                "business_name": business_name,
                "description": description,
                "owner": "demo-modeler",
            },
        )
        models[key] = item
    print("模型：" + "、".join(f"{item['business_name']}({item['model_id']})" for item in models.values()))
    return models


FIELDS: dict[str, list[dict[str, Any]]] = {
    "order": [
        {"name": "order_id", "business_name": "订单号", "semantic_type": "key", "data_type": "string", "synonyms": ["订单编号"]},
        {"name": "customer_id", "business_name": "客户号", "semantic_type": "key", "data_type": "string"},
        {"name": "store_id", "business_name": "门店号", "semantic_type": "key", "data_type": "string"},
        {"name": "product_id", "business_name": "商品号", "semantic_type": "key", "data_type": "string"},
        {"name": "order_date", "business_name": "下单日期", "semantic_type": "time", "data_type": "date", "synonyms": ["订单日期"]},
        {"name": "order_amount", "business_name": "订单金额", "semantic_type": "measure", "data_type": "number"},
        {"name": "refund_amount", "business_name": "退款金额", "semantic_type": "measure", "data_type": "number"},
        {"name": "status", "business_name": "订单状态", "semantic_type": "dimension", "data_type": "string"},
        {"name": "channel", "business_name": "渠道", "semantic_type": "dimension", "data_type": "string"},
        {"name": "quantity", "business_name": "商品件数", "semantic_type": "measure", "data_type": "number"},
    ],
    "customer": [
        {"name": "customer_id", "business_name": "客户号", "semantic_type": "key", "data_type": "string"},
        {"name": "customer_name", "business_name": "客户名称", "semantic_type": "dimension", "data_type": "string", "sensitivity": "pii"},
        {"name": "customer_level", "business_name": "客户等级", "semantic_type": "dimension", "data_type": "string"},
        {"name": "register_date", "business_name": "注册日期", "semantic_type": "time", "data_type": "date"},
        {"name": "region", "business_name": "所属区域", "semantic_type": "dimension", "data_type": "string"},
    ],
    "store": [
        {"name": "store_id", "business_name": "门店号", "semantic_type": "key", "data_type": "string"},
        {"name": "store_name", "business_name": "门店名称", "semantic_type": "dimension", "data_type": "string"},
        {"name": "region", "business_name": "区域", "semantic_type": "dimension", "data_type": "string"},
        {"name": "city", "business_name": "城市", "semantic_type": "dimension", "data_type": "string"},
        {"name": "store_type", "business_name": "门店类型", "semantic_type": "dimension", "data_type": "string"},
        {"name": "open_date", "business_name": "开业日期", "semantic_type": "time", "data_type": "date"},
    ],
    "product": [
        {"name": "product_id", "business_name": "商品号", "semantic_type": "key", "data_type": "string"},
        {"name": "product_name", "business_name": "商品名称", "semantic_type": "dimension", "data_type": "string"},
        {"name": "category", "business_name": "品类", "semantic_type": "dimension", "data_type": "string"},
        {"name": "brand", "business_name": "品牌", "semantic_type": "dimension", "data_type": "string"},
        {"name": "price", "business_name": "标准单价", "semantic_type": "measure", "data_type": "number"},
    ],
}


def create_fields(models: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for key, fields in FIELDS.items():
        model_id = int(models[key]["model_id"])
        items = api("post", f"/models/{model_id}/fields:batch", {"fields": fields})
        result[key] = {item["name"]: int(item["field_id"]) for item in items}
    print("字段：" + "、".join(f"{key}={len(value)}" for key, value in result.items()))
    return result


def set_grains(models: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> None:
    grains = {"order": "order_id", "customer": "customer_id", "store": "store_id", "product": "product_id"}
    for key, field_name in grains.items():
        model_id = int(models[key]["model_id"])
        api("put", f"/models/{model_id}/grain", {"field_ids": [fields[key][field_name]]})
    print("粒度已声明：" + "、".join(value for value in grains.values()))


def create_dimensions(models: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> None:
    dimensions = [
        ("order", "下单日期", "order_date", "time", {"time_granularity": "day"}),
        (
            "order",
            "渠道",
            "channel",
            "categorical",
            {"code_mapping": {"1": "APP", "2": "小程序", "3": "门店"}},
        ),
        ("store", "区域", "region", "categorical", {}),
        ("store", "城市", "city", "categorical", {}),
        ("store", "门店", "store_name", "categorical", {}),
        ("product", "品类", "category", "categorical", {}),
        ("product", "品牌", "brand", "categorical", {}),
        ("customer", "客户等级", "customer_level", "categorical", {}),
        ("customer", "客户名称", "customer_name", "categorical", {}),
    ]
    for key, name, field_name, dimension_type, extra in dimensions:
        model_id = int(models[key]["model_id"])
        api(
            "post",
            f"/models/{model_id}/dimensions",
            {"name": name, "field_id": fields[key][field_name], "dimension_type": dimension_type, **extra},
        )
    print(f"维度：{len(dimensions)} 个")


def create_measures(models: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> dict[str, int]:
    model_id = int(models["order"]["model_id"])
    definitions = [
        ("order_amount_sum", "订单金额求和", "order_amount", "sum", "CNY"),
        ("order_cnt", "订单数", "order_id", "count_distinct", "单"),
        ("refund_amount_sum", "退款金额求和", "refund_amount", "sum", "CNY"),
        ("quantity_sum", "商品件数求和", "quantity", "sum", "件"),
    ]
    result: dict[str, int] = {}
    for name, business_name, field_name, agg, unit in definitions:
        item = api(
            "post",
            f"/models/{model_id}/measures",
            {
                "name": name,
                "business_name": business_name,
                "field_id": fields["order"][field_name],
                "agg": agg,
                "additivity": "additive",
                "unit": unit,
            },
        )
        result[name] = int(item["measure_id"])
    print("度量：" + "、".join(result))
    return result


def create_metrics(
    models: dict[str, dict[str, Any]],
    measures: dict[str, int],
    domain_id: int,
) -> dict[str, int]:
    order_model_id = int(models["order"]["model_id"])
    paid_filter = "status in ('paid','shipped','completed')"

    def create(payload: dict[str, Any]) -> int:
        item = api("post", "/metrics", {"domain_id": domain_id, "owner": "demo-modeler", **payload})
        return int(item["metric_id"])

    gmv = create(
        {
            "model_id": order_model_id,
            "name": "gmv",
            "business_name": "GMV",
            "synonyms": ["成交总额", "交易额", "成交金额"],
            "definition": "已支付订单金额之和",
            "metric_type": "simple",
            "filter": paid_filter,
            "unit": "CNY",
            "inputs": [{"input_type": "measure", "input_ref": measures["order_amount_sum"], "role": "input"}],
        }
    )
    order_count = create(
        {
            "model_id": order_model_id,
            "name": "order_count",
            "business_name": "订单数",
            "synonyms": ["订单量", "单量"],
            "definition": "已支付订单去重计数",
            "metric_type": "simple",
            "filter": paid_filter,
            "unit": "单",
            "inputs": [{"input_type": "measure", "input_ref": measures["order_cnt"], "role": "input"}],
        }
    )
    refund_amount = create(
        {
            "model_id": order_model_id,
            "name": "refund_amount",
            "business_name": "退款金额",
            "definition": "已退款订单的退款金额之和",
            "metric_type": "simple",
            "filter": "status = 'refunded'",
            "unit": "CNY",
            "inputs": [{"input_type": "measure", "input_ref": measures["refund_amount_sum"], "role": "input"}],
        }
    )
    aov = create(
        {
            "model_id": order_model_id,
            "name": "aov",
            "business_name": "客单价",
            "synonyms": ["平均订单金额"],
            "definition": "GMV / 订单数",
            "metric_type": "ratio",
            "unit": "CNY",
            "inputs": [
                {"input_type": "metric", "input_ref": gmv, "role": "numerator"},
                {"input_type": "metric", "input_ref": order_count, "role": "denominator"},
            ],
        }
    )
    refund_rate = create(
        {
            "model_id": order_model_id,
            "name": "refund_rate",
            "business_name": "退款率",
            "definition": "退款金额 / GMV",
            "metric_type": "ratio",
            "unit": "%",
            "inputs": [
                {"input_type": "metric", "input_ref": refund_amount, "role": "numerator"},
                {"input_type": "metric", "input_ref": gmv, "role": "denominator"},
            ],
        }
    )
    net_gmv = create(
        {
            "model_id": order_model_id,
            "name": "net_gmv",
            "business_name": "净 GMV",
            "definition": "gmv - refund_amount",
            "metric_type": "derived",
            "unit": "CNY",
        }
    )
    result = {
        "gmv": gmv,
        "order_count": order_count,
        "refund_amount": refund_amount,
        "aov": aov,
        "refund_rate": refund_rate,
        "net_gmv": net_gmv,
    }
    print("指标：" + "、".join(result))
    return result


def create_relationships(models: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> None:
    order_model_id = int(models["order"]["model_id"])
    definitions = [
        ("order_customer", "customer", "customer_id"),
        ("order_store", "store", "store_id"),
        ("order_product", "product", "product_id"),
    ]
    for name, target, field_name in definitions:
        api(
            "post",
            f"/models/{order_model_id}/relationships",
            {
                "name": name,
                "from_field_id": fields["order"][field_name],
                "to_model_id": int(models[target]["model_id"]),
                "to_field_id": fields[target][field_name],
                "cardinality": "N:1",
                "join_type": "left",
                "priority": 100,
                "verified": True,
            },
        )
    print("关系：订单→客户 / 门店 / 商品（N:1，已认证）")


BINDING_MAPPINGS: dict[str, dict[str, tuple[str, str | None]]] = {
    "order": {
        "order_id": ("order_no", None),
        "customer_id": ("cust_no", None),
        "store_id": ("store_no", None),
        "product_id": ("sku_no", None),
        "order_date": ("dt", "CAST(dt AS DATE)"),
        "order_amount": ("amt", None),
        "refund_amount": ("refund_amt", None),
        "status": ("order_status", None),
        "channel": ("channel_code", None),
        "quantity": ("qty", None),
    },
    "customer": {
        "customer_id": ("cust_no", None),
        "customer_name": ("cust_name", None),
        "customer_level": ("cust_level", None),
        "register_date": ("register_date", None),
        "region": ("region", None),
    },
    "store": {
        "store_id": ("store_no", None),
        "store_name": ("store_name", None),
        "region": ("region", None),
        "city": ("city", None),
        "store_type": ("store_type", None),
        "open_date": ("open_date", None),
    },
    "product": {
        "product_id": ("sku_no", None),
        "product_name": ("sku_name", None),
        "category": ("category", None),
        "brand": ("brand", None),
        "price": ("price", None),
    },
}


def create_bindings(
    models: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, int]],
) -> dict[str, dict[str, Any]]:
    datasets = {
        item["external_dataset_id"]: item
        for item in api("get", "/catalog/datasets", params={"source_system": "retail_demo", "page_size": 50})["items"]
    }
    bindings: dict[str, dict[str, Any]] = {}
    for key, mappings in BINDING_MAPPINGS.items():
        model_id = int(models[key]["model_id"])
        external_id = DATASET_IDS[key]
        dataset = api("get", f"/catalog/datasets/{datasets[external_id]['dataset_id']}")
        column_ids = {item["column_name"]: int(item["column_id"]) for item in dataset["columns"]}
        binding = api(
            "post",
            f"/models/{model_id}/bindings",
            {
                "binding_type": "dataset",
                "source_system": "retail_demo",
                "external_dataset_id": external_id,
                "query_ref": QUERY_REFS[key],
                "is_primary": True,
                "status": "draft",
                "source_version": "v1",
            },
        )
        binding_id = int(binding["binding_id"])
        api(
            "put",
            f"/bindings/{binding_id}/field-mappings",
            {
                "items": [
                    {
                        "field_id": fields[key][field_name],
                        "column_id": column_ids[column_name],
                        "column_name": column_name,
                        "transform": transform,
                        "status": "draft",
                    }
                    for field_name, (column_name, transform) in mappings.items()
                ]
            },
        )
        api("post", f"/bindings/{binding_id}:set-primary")
        binding["coverage"] = api("get", f"/bindings/{binding_id}")["coverage"]
        bindings[key] = binding
    print(
        "绑定："
        + "、".join(
            f"{models[key]['business_name']}→{QUERY_REFS[key]}(覆盖率 {round(item['coverage'] * 100)}%)"
            for key, item in bindings.items()
        )
    )
    return bindings


def create_knowledge(metrics: dict[str, int], models: dict[str, dict[str, Any]]) -> None:
    terms = [
        {
            "name": "GMV",
            "synonyms": ["成交总额", "交易额", "成交金额"],
            "definition": "已支付订单金额之和，排除退款订单",
        },
        {
            "name": "客单价",
            "synonyms": ["平均订单金额"],
            "definition": "GMV 除以订单数，分子分母共享过滤条件",
        },
        {
            "name": "净 GMV",
            "synonyms": ["净成交额"],
            "definition": "GMV 扣除退款金额后的净成交额",
        },
    ]
    for term in terms:
        api("post", "/terms", {**term, "scope_type": "domain"})

    api(
        "post",
        "/rules",
        {
            "name": "排除无效订单",
            "rule_type": "filter",
            "target_type": "model",
            "target_id": int(models["order"]["model_id"]),
            "condition": "quantity <= 0",
            "action": "exclude",
            "priority": 10,
            "status": "active",
        },
    )

    api(
        "put",
        f"/context/metric/{metrics['gmv']}",
        {
            "business_name": "GMV",
            "synonyms": ["成交总额", "交易额"],
            "definition": "已支付订单金额之和，按订单状态过滤 paid/shipped/completed",
            "examples": [
                {"question": "上月华东地区各渠道的 GMV 和客单价"},
                {"question": "今年各品类的 GMV 排名"},
            ],
            "negative_examples": [{"question": "退款金额是多少"}],
        },
    )
    print("知识上下文：3 条术语、1 条业务规则、1 份指标上下文")


def create_permissions(models: dict[str, dict[str, Any]]) -> None:
    """演示角色级行列权限：按角色 analyst 注入行过滤与客户名称掩码。"""
    with write_session() as session:
        session.execute(
            text(
                """
                INSERT INTO t_permission
                  (subject_type, subject_id, asset_type, asset_id, effect, row_filter, column_mask)
                VALUES
                  ('role', 'analyst', 'model', :order_model_id, 'allow', :row_filter, '{}'::jsonb),
                  ('role', 'analyst', 'model', :customer_model_id, 'allow', NULL,
                   CAST(:column_mask AS JSONB))
                """
            ),
            {
                "order_model_id": int(models["order"]["model_id"]),
                "customer_model_id": int(models["customer"]["model_id"]),
                "row_filter": "status <> 'refunded'",
                "column_mask": json.dumps({"customer_name": "CONCAT(LEFT({col}, 1), '***')"}),
            },
        )
    print("权限策略：角色 analyst 行过滤 status <> 'refunded'，客户名称列掩码")


# --------------------------------------------------------------------------- 校验 / 认证 / 发布


def certify(asset_type: str, asset_id: int, comment: str) -> None:
    item = api("post", "/certifications", {"asset_type": asset_type, "asset_id": asset_id})
    api("post", f"/certifications/{item['certification_id']}/decision", {"approve": True, "comment": comment})


def validate_all(
    models: dict[str, dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    metrics: dict[str, int],
) -> None:
    for key, item in bindings.items():
        certify("binding", int(item["binding_id"]), "零售示例：字段映射完整")

    for key, item in models.items():
        model_id = int(item["model_id"])
        result = api("post", f"/models/{model_id}/validation", {"level": "semantic"})
        if result["status"] != "passed":
            raise RuntimeError(f"模型 {key} 语义校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")

    for name, metric_id in metrics.items():
        result = api("post", f"/metrics/{metric_id}/validation")
        if result["status"] != "passed":
            raise RuntimeError(f"指标 {name} 校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")

    for key, item in models.items():
        certify("model", int(item["model_id"]), "零售示例：语义定义确认")

    for name, metric_id in metrics.items():
        certify("metric", metric_id, f"零售示例：{name} 口径确认")

    queryable_summary = []
    for key, item in models.items():
        result = api("post", f"/models/{item['model_id']}/validation", {"level": "queryable"})
        if result["status"] != "passed":
            raise RuntimeError(f"模型 {key} 可问数校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")
        queryable_summary.append(f"{key}={result.get('queryable')}")

    print("校验：semantic 全部 passed，queryable 全部 passed")
    print("认证：模型 4 个、指标 6 个、绑定 4 个均已认证")
    print("可问数：" + "、".join(queryable_summary))


def publish() -> dict[str, Any]:
    snapshot = api("post", "/snapshots")
    print(f"快照发布：{snapshot['version']}（{snapshot['status']}）")
    return snapshot


def run_ask(question: str) -> dict[str, Any]:
    response = client.post("/api/ask", json={"question": question}, headers=HEADERS)
    body = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"问数失败 {response.status_code}: {body}")
    data = body.get("data", body)
    print(f"\n问数：{question}")
    print(f"  状态：{data['status']}，快照：{(data.get('result') or {}).get('snapshot_version')}")
    if data["status"] != "ok":
        print(f"  澄清：{json.dumps(data.get('clarification'), ensure_ascii=False)}")
        return data
    result = data["result"]
    print(f"  SQL：{result['sql']}")
    print(f"  列：{result['columns']}，行数：{result['row_count']}")
    for row in result["rows"][:6]:
        print(f"    {row}")
    return data


def main() -> None:
    step("1. 重建零售样例物理表")
    create_physical_tables()

    step("2. 清理上一轮零售示例数据")
    cleanup()

    step("3. 同步数据集目录")
    sync_catalog()

    step("4. 主题域与语义模型")
    domain_id = ensure_domain()
    print(f"主题域：{DOMAIN_NAME}({domain_id})")
    models = build_models(domain_id)
    fields = create_fields(models)
    set_grains(models, fields)

    step("5. 维度、度量、指标、关系")
    create_dimensions(models, fields)
    measures = create_measures(models, fields)
    metrics = create_metrics(models, measures, domain_id)
    create_relationships(models, fields)

    step("6. 数据绑定与字段映射")
    bindings = create_bindings(models, fields)

    step("7. 知识上下文与权限")
    create_knowledge(metrics, models)
    create_permissions(models)

    step("8. 校验、认证")
    validate_all(models, bindings, metrics)

    step("9. 发布语义快照")
    publish()

    step("10. 问数验证")
    run_ask("上月华东地区各渠道的 GMV 和客单价")
    run_ask("今年各品类的 GMV")
    run_ask("上月净 GMV 是多少")

    print("\n完成：零售经营示例已跑通（主题域 → 模型 → 指标 → 绑定 → 知识 → 校验 → 发布 → 问数）")


if __name__ == "__main__":
    main()