"""端到端契约用例：响应包裹、路由存在性、角色守卫与错误码归一。"""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/semantic/v1"


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "3.0.0"


def test_request_id_header_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-Id": "trace-123"})
    assert response.headers["X-Request-Id"] == "trace-123"


def test_core_routes_are_registered(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/health",
        "/api/ask",
        "/api/ask/compile",
        f"{API}/domains",
        f"{API}/models",
        f"{API}/models/{{model_id}}/validation",
        f"{API}/metrics",
        f"{API}/bindings/{{binding_id}}/field-mappings",
        f"{API}/catalog/datasets",
        f"{API}/snapshots",
        f"{API}/snapshots/active",
    ):
        assert path in paths, f"缺少路由 {path}"


def test_paged_envelope_shape(client: TestClient, db_ready) -> None:
    body = client.get(f"{API}/domains").json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["request_id"]
    assert set(body["data"]) == {"items", "total", "page", "page_size"}


def test_invalid_payload_returns_422(client: TestClient) -> None:
    response = client.post(f"{API}/models", json={"name": "缺少主题域"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_missing_model_returns_404(client: TestClient, db_ready) -> None:
    response = client.get(f"{API}/models/999999999")
    assert response.status_code == 404
    assert response.json()["code"] == "model_not_found"


def test_compile_error_is_normalized_to_422(client: TestClient, db_ready) -> None:
    response = client.post("/api/ask/compile", json={"query_ir": {"metrics": []}})
    assert response.status_code == 422
    assert response.json()["code"] == "metric_required"


def test_reviewer_cannot_create_model(client: TestClient, db_ready) -> None:
    response = client.post(
        f"{API}/models",
        json={"domain_id": 1, "name": "role-guard"},
        headers={"X-Roles": "reviewer"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_engineer_cannot_build_snapshot(client: TestClient, db_ready) -> None:
    response = client.post(f"{API}/snapshots", headers={"X-Roles": "engineer"})
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_modeler_cannot_rollback_snapshot(client: TestClient, db_ready) -> None:
    response = client.post(f"{API}/snapshots/v0/rollback", headers={"X-Roles": "modeler"})
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"