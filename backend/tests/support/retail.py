"""零售经营语义目录样例：单元、golden、集成测试共用的内存目录。"""

from __future__ import annotations

from app.semantic.domain.entities import (
    Binding,
    Dimension,
    Field,
    FieldBinding,
    GrainField,
    JoinEdge,
    Measure,
    Metric,
    MetricInput,
    Model,
    SemanticCatalog,
)


def retail_catalog() -> SemanticCatalog:
    catalog = SemanticCatalog()
    catalog.models = {
        1: Model(model_id=1, domain_id=1, name="order", business_name="订单", status="certified"),
        2: Model(model_id=2, domain_id=1, name="store", business_name="门店", status="certified"),
        3: Model(model_id=3, domain_id=1, name="product", business_name="商品", status="certified"),
        4: Model(model_id=4, domain_id=1, name="customer", business_name="客户", status="certified"),
    }
    order_fields = [
        (1, "order_id", "订单号", "key", "string"),
        (2, "customer_id", "客户号", "key", "string"),
        (3, "store_id", "门店号", "key", "string"),
        (4, "product_id", "商品号", "key", "string"),
        (5, "order_date", "下单日期", "time", "date"),
        (6, "order_amount", "订单金额", "measure", "number"),
        (7, "refund_amount", "退款金额", "measure", "number"),
        (8, "status", "订单状态", "dimension", "string"),
        (9, "channel", "渠道", "dimension", "string"),
        (10, "quantity", "商品件数", "measure", "number"),
    ]
    store_fields = [
        (11, "store_id", "门店号", "key", "string"),
        (12, "store_name", "门店名称", "dimension", "string"),
        (13, "region", "区域", "dimension", "string"),
        (14, "city", "城市", "dimension", "string"),
    ]
    product_fields = [
        (15, "product_id", "商品号", "key", "string"),
        (16, "product_name", "商品名称", "dimension", "string"),
        (17, "category", "品类", "dimension", "string"),
    ]
    customer_fields = [
        (18, "customer_id", "客户号", "key", "string"),
        (19, "customer_level", "客户等级", "dimension", "string"),
    ]
    for model_id, items in ((1, order_fields), (2, store_fields), (3, product_fields), (4, customer_fields)):
        for field_id, name, business_name, semantic_type, data_type in items:
            catalog.fields[field_id] = Field(
                field_id=field_id,
                model_id=model_id,
                name=name,
                business_name=business_name,
                semantic_type=semantic_type,
                data_type=data_type,
            )
    catalog.grains = [GrainField(model_id=1, field_id=1, position=1)]
    catalog.dimensions = {
        1: Dimension(dimension_id=1, model_id=1, name="下单日期", field_id=5, dimension_type="time", time_granularity="day", verified=True),
        2: Dimension(dimension_id=2, model_id=1, name="渠道", field_id=9, verified=True),
        3: Dimension(dimension_id=3, model_id=2, name="区域", field_id=13, verified=True),
        4: Dimension(dimension_id=4, model_id=3, name="品类", field_id=17, verified=True),
        5: Dimension(dimension_id=5, model_id=4, name="客户等级", field_id=19, verified=True),
    }
    catalog.measures = {
        1: Measure(measure_id=1, model_id=1, name="order_amount_sum", field_id=6, agg="sum", verified=True),
        2: Measure(measure_id=2, model_id=1, name="order_cnt", field_id=1, agg="count_distinct", verified=True),
        3: Measure(measure_id=3, model_id=1, name="refund_amount_sum", field_id=7, agg="sum", verified=True),
        4: Measure(measure_id=4, model_id=1, name="quantity_sum", field_id=10, agg="sum", verified=True),
    }
    catalog.metrics = {
        1: Metric(
            metric_id=1,
            model_id=1,
            name="GMV",
            business_name="GMV",
            metric_type="simple",
            filter="status in ('paid','shipped','completed')",
            unit="CNY",
            status="certified",
            inputs=[MetricInput(metric_id=1, input_type="measure", input_ref=1, role="input")],
        ),
        2: Metric(
            metric_id=2,
            model_id=1,
            name="订单数",
            metric_type="simple",
            filter="status in ('paid','shipped','completed')",
            unit="单",
            status="certified",
            inputs=[MetricInput(metric_id=2, input_type="measure", input_ref=2, role="input")],
        ),
        3: Metric(
            metric_id=3,
            model_id=1,
            name="退款金额",
            metric_type="simple",
            filter="status = 'refunded'",
            unit="CNY",
            status="certified",
            inputs=[MetricInput(metric_id=3, input_type="measure", input_ref=3, role="input")],
        ),
        4: Metric(
            metric_id=4,
            model_id=1,
            name="客单价",
            metric_type="ratio",
            unit="CNY",
            status="certified",
            inputs=[
                MetricInput(metric_id=4, input_type="metric", input_ref=1, role="numerator", position=1),
                MetricInput(metric_id=4, input_type="metric", input_ref=2, role="denominator", position=2),
            ],
        ),
        5: Metric(
            metric_id=5,
            model_id=1,
            name="退款率",
            metric_type="ratio",
            unit="%",
            status="certified",
            inputs=[
                MetricInput(metric_id=5, input_type="metric", input_ref=3, role="numerator", position=1),
                MetricInput(metric_id=5, input_type="metric", input_ref=1, role="denominator", position=2),
            ],
        ),
        6: Metric(
            metric_id=6,
            model_id=1,
            name="净 GMV",
            metric_type="derived",
            definition="GMV - 退款金额",
            unit="CNY",
            status="certified",
        ),
    }
    catalog.join_edges = {
        1: JoinEdge(edge_id=1, name="order_store", from_model_id=1, from_field_id=3, to_model_id=2, to_field_id=11, cardinality="N:1", verified=True),
        2: JoinEdge(edge_id=2, name="order_product", from_model_id=1, from_field_id=4, to_model_id=3, to_field_id=15, cardinality="N:1", verified=True),
        3: JoinEdge(edge_id=3, name="order_customer", from_model_id=1, from_field_id=2, to_model_id=4, to_field_id=18, cardinality="N:1", verified=True),
    }
    catalog.bindings = {
        1: Binding(binding_id=1, model_id=1, binding_type="dataset", query_ref="dataset.ds_order_detail", source_system="chatbi_dataset", external_dataset_id="ds_order_detail", is_primary=True, status="certified", verified=True),
        2: Binding(binding_id=2, model_id=2, binding_type="dataset", query_ref="dataset.ds_store", source_system="chatbi_dataset", external_dataset_id="ds_store", is_primary=True, status="certified", verified=True),
        3: Binding(binding_id=3, model_id=3, binding_type="dataset", query_ref="dataset.ds_product", source_system="chatbi_dataset", external_dataset_id="ds_product", is_primary=True, status="certified", verified=True),
        4: Binding(binding_id=4, model_id=4, binding_type="dataset", query_ref="dataset.ds_customer", source_system="chatbi_dataset", external_dataset_id="ds_customer", is_primary=True, status="certified", verified=True),
    }
    order_columns = {
        1: "order_no",
        2: "cust_no",
        3: "store_no",
        4: "sku_no",
        5: "dt",
        6: "amt",
        7: "refund_amt",
        8: "order_status",
        9: "channel_code",
        10: "qty",
    }
    for field_id, column in order_columns.items():
        catalog.field_bindings[(1, field_id)] = FieldBinding(binding_id=1, field_id=field_id, column_name=column, status="certified")
    catalog.field_bindings[(2, 11)] = FieldBinding(binding_id=2, field_id=11, column_name="store_no", status="certified")
    catalog.field_bindings[(2, 13)] = FieldBinding(binding_id=2, field_id=13, column_name="region", status="certified")
    catalog.field_bindings[(3, 15)] = FieldBinding(binding_id=3, field_id=15, column_name="sku_no", status="certified")
    catalog.field_bindings[(3, 17)] = FieldBinding(binding_id=3, field_id=17, column_name="category", status="certified")
    catalog.field_bindings[(4, 18)] = FieldBinding(binding_id=4, field_id=18, column_name="cust_no", status="certified")
    catalog.field_bindings[(4, 19)] = FieldBinding(binding_id=4, field_id=19, column_name="customer_level", status="certified")
    return catalog


def with_cumulative_metric(catalog: SemanticCatalog) -> SemanticCatalog:
    """在零售目录上追加一个按月累计的 GMV 指标。"""
    catalog.metrics[7] = Metric(
        metric_id=7,
        model_id=1,
        name="GMV 月累计",
        metric_type="cumulative",
        grain_to_date="month",
        unit="CNY",
        status="certified",
        inputs=[MetricInput(metric_id=7, input_type="metric", input_ref=1, role="input")],
    )
    return catalog


def with_semi_additive_metric(catalog: SemanticCatalog) -> SemanticCatalog:
    """在零售目录上追加一个半加性度量（期末库存口径）。"""
    catalog.measures[5] = Measure(
        measure_id=5,
        model_id=1,
        name="ending_quantity",
        field_id=10,
        agg="sum",
        additivity="semi_additive",
        window_choice="max",
        agg_time_dimension=5,
        verified=True,
    )
    catalog.metrics[8] = Metric(
        metric_id=8,
        model_id=1,
        name="期末库存件数",
        metric_type="simple",
        unit="件",
        status="certified",
        inputs=[MetricInput(metric_id=8, input_type="measure", input_ref=5, role="input")],
    )
    return catalog