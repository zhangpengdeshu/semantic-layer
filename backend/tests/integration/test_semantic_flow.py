"""集成用例：建模 → 校验 → 绑定 → 认证 → 快照 → 问数（真实数据库与物理表）。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.support.workspace import SemanticWorkspace

API = "/api/semantic/v1"


def _data(response) -> Any:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0
    return body["data"]


def _issue_codes(item: dict[str, Any]) -> set[str]:
    return {issue["code"] for issue in item["issues"]}


def _build_model(client: TestClient, workspace: SemanticWorkspace) -> dict[str, Any]:
    """创建主题域、模型、字段、粒度、度量、维度、指标与主绑定。"""
    domain = _data(
        client.post(
            f"{API}/domains",
            json={"name": f"{workspace.prefix}-domain", "description": "pytest 集成用例"},
        )
    )
    model = _data(
        client.post(
            f"{API}/models",
            json={"domain_id": domain["domain_id"], "name": f"{workspace.prefix}-order", "business_name": "pytest 订单"},
        )
    )
    model_id = model["model_id"]
    fields = _data(
        client.post(
            f"{API}/models/{model_id}/fields:batch",
            json={
                "fields": [
                    {"name": "order_id", "business_name": "订单号", "semantic_type": "key", "data_type": "string"},
                    {"name": "order_date", "business_name": "下单日期", "semantic_type": "time", "data_type": "date"},
                    {"name": "order_amount", "business_name": "订单金额", "semantic_type": "measure", "data_type": "number"},
                    {"name": "channel", "business_name": "渠道", "semantic_type": "dimension", "data_type": "string"},
                ]
            },
        )
    )
    field_ids = {item["name"]: item["field_id"] for item in fields}

    _data(client.put(f"{API}/models/{model_id}/grain", json={"field_ids": [field_ids["order_id"]]}))
    measure = _data(
        client.post(
            f"{API}/models/{model_id}/measures",
            json={"name": "gmv_sum", "field_id": field_ids["order_amount"], "agg": "sum", "verified": True},
        )
    )
    _data(
        client.post(
            f"{API}/models/{model_id}/dimensions",
            json={"name": "渠道", "field_id": field_ids["channel"], "dimension_type": "categorical", "verified": True},
        )
    )
    metric = _data(
        client.post(
            f"{API}/metrics",
            json={
                "model_id": model_id,
                "name": f"{workspace.prefix} GMV",
                "metric_type": "simple",
                "unit": "CNY",
                "inputs": [{"input_type": "measure", "input_ref": measure["measure_id"], "role": "input"}],
            },
        )
    )
    binding = _data(
        client.post(
            f"{API}/models/{model_id}/bindings",
            json={
                "binding_type": "table",
                "query_ref": workspace.query_ref,
                "is_primary": True,
                "status": "certified",
                "verified": True,
            },
        )
    )
    return {
        "domain_id": domain["domain_id"],
        "model_id": model_id,
        "metric_id": metric["metric_id"],
        "metric_name": metric["name"],
        "binding_id": binding["binding_id"],
        "field_ids": field_ids,
    }


def _map_fields(client: TestClient, binding_id: int, field_ids: dict[str, int]) -> None:
    _data(
        client.put(
            f"{API}/bindings/{binding_id}/field-mappings",
            json={
                "items": [
                    {"field_id": field_ids["order_id"], "column_name": "order_no"},
                    {"field_id": field_ids["order_date"], "column_name": "dt"},
                    {"field_id": field_ids["order_amount"], "column_name": "amt"},
                    {"field_id": field_ids["channel"], "column_name": "channel_code"},
                ]
            },
        )
    )


def _approve(client: TestClient, asset_type: str, asset_id: int) -> dict[str, Any]:
    certification = _data(
        client.post(f"{API}/certifications", json={"asset_type": asset_type, "asset_id": asset_id})
    )
    return _data(
        client.post(
            f"{API}/certifications/{certification['certification_id']}/decision",
            json={"approve": True, "comment": "pytest"},
        )
    )


def test_model_to_ask_flow(client: TestClient, workspace: SemanticWorkspace) -> None:
    ids = _build_model(client, workspace)
    model_id = ids["model_id"]

    semantic = _data(client.post(f"{API}/models/{model_id}/validation", json={"level": "semantic"}))
    assert semantic["status"] == "passed", semantic

    queryable = _data(client.post(f"{API}/models/{model_id}/validation", json={"level": "queryable"}))
    assert queryable["status"] == "failed"
    assert "binding_missing" in _issue_codes(queryable) or "field_mapping_missing" in _issue_codes(queryable)

    _map_fields(client, ids["binding_id"], ids["field_ids"])
    queryable = _data(client.post(f"{API}/models/{model_id}/validation", json={"level": "queryable"}))
    assert queryable["status"] == "passed", queryable

    _approve(client, "model", model_id)
    _approve(client, "metric", ids["metric_id"])
    assert _data(client.get(f"{API}/models/{model_id}"))["status"] == "certified"

    snapshot = _data(client.post(f"{API}/snapshots"))
    assert snapshot["status"] == "active"
    assert _data(client.get(f"{API}/snapshots/active"))["version"] == snapshot["version"]

    answer = _data(
        client.post(
            "/api/ask",
            json={"question": f"{ids['metric_name']} 按渠道", "domain_id": ids["domain_id"]},
        )
    )
    assert answer["status"] == "ok", answer
    result = answer["result"]
    assert result["snapshot_version"] == snapshot["version"]
    assert workspace.table in result["sql"]
    assert result["metric_ids"] == [ids["metric_id"]]
    values = {row["渠道"]: float(row[ids["metric_name"]]) for row in result["rows"]}
    assert values == {"online": 400.0, "offline": 250.0}

    explain = _data(client.get(f"/api/ask/{answer['request_id']}/explain"))
    assert explain["snapshot_version"] == snapshot["version"]
    assert explain["status"] == "ok"


def test_model_update_rejects_stale_version(client: TestClient, workspace: SemanticWorkspace) -> None:
    ids = _build_model(client, workspace)
    model = _data(client.get(f"{API}/models/{ids['model_id']}"))
    response = client.patch(
        f"{API}/models/{ids['model_id']}",
        json={"business_name": "并发修改", "version": model["version"] + 1},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"


def test_certification_rejects_changed_asset(client: TestClient, workspace: SemanticWorkspace) -> None:
    ids = _build_model(client, workspace)
    certification = _data(
        client.post(f"{API}/certifications", json={"asset_type": "model", "asset_id": ids["model_id"]})
    )
    _data(client.patch(f"{API}/models/{ids['model_id']}", json={"business_name": "认证后又被改动"}))
    response = client.post(
        f"{API}/certifications/{certification['certification_id']}/decision",
        json={"approve": True},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "certification_stale"


def test_snapshot_rollback_restores_previous_version(client: TestClient, workspace: SemanticWorkspace) -> None:
    first = _data(client.post(f"{API}/snapshots"))
    _data(client.patch(f"{API}/models/{_build_model(client, workspace)['model_id']}", json={"description": "变更"}))
    second = _data(client.post(f"{API}/snapshots"))
    assert second["version"] != first["version"]

    rolled = _data(client.post(f"{API}/snapshots/{first['version']}/rollback"))
    assert rolled["status"] == "active"
    assert _data(client.get(f"{API}/snapshots/active"))["version"] == first["version"]

    diff = _data(client.get(f"{API}/snapshots/diff", params={"left": first["version"], "right": second["version"]}))
    assert diff["left"]["version"] == first["version"]
    assert diff["right"]["version"] == second["version"]
    assert diff["changed"]