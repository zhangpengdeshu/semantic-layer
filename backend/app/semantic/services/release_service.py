"""认证、指纹与语义快照。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.semantic.repository.db import execute, execute_many, insert, jsonb, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError

SNAPSHOT_TABLES = [
    "t_sem_domain",
    "t_sem_model",
    "t_sem_field",
    "t_sem_model_grain",
    "t_sem_dimension",
    "t_sem_measure",
    "t_sem_metric",
    "t_sem_metric_input",
    "t_sem_join_edge",
    "t_sem_binding",
    "t_sem_field_binding",
    "t_term",
    "t_business_rule",
    "t_sem_asset_context",
]


def _hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _asset_fingerprint(asset_type: str, asset_id: int) -> str:
    if asset_type == "model":
        asset = one("SELECT * FROM t_sem_model WHERE model_id = :id", {"id": asset_id})
        fields = rows("SELECT * FROM t_sem_field WHERE model_id = :id ORDER BY field_id", {"id": asset_id})
        grain = rows("SELECT * FROM t_sem_model_grain WHERE model_id = :id ORDER BY position", {"id": asset_id})
        if not asset:
            raise NotFoundError("模型不存在", code="model_not_found")
        return _hash({"asset": asset, "fields": fields, "grain": grain})
    if asset_type == "metric":
        asset = one("SELECT * FROM t_sem_metric WHERE metric_id = :id", {"id": asset_id})
        inputs = rows("SELECT * FROM t_sem_metric_input WHERE metric_id = :id ORDER BY position", {"id": asset_id})
        if not asset:
            raise NotFoundError("指标不存在", code="metric_not_found")
        return _hash({"asset": asset, "inputs": inputs})
    if asset_type == "binding":
        asset = one("SELECT * FROM t_sem_binding WHERE binding_id = :id", {"id": asset_id})
        mappings = rows("SELECT * FROM t_sem_field_binding WHERE binding_id = :id ORDER BY field_id", {"id": asset_id})
        if not asset:
            raise NotFoundError("绑定不存在", code="binding_not_found")
        return _hash({"asset": asset, "mappings": mappings})
    raise ValidationFailedError("不支持的认证资产类型", code="certification_asset_invalid")


def create_certification(asset_type: str, asset_id: int, actor: str | None) -> dict[str, Any]:
    fingerprint = _asset_fingerprint(asset_type, asset_id)
    item = insert(
        """
        INSERT INTO t_sem_certification
          (asset_type, asset_id, fingerprint, status, requested_by)
        VALUES (:asset_type, :asset_id, :fingerprint, 'pending', :requested_by)
        RETURNING *
        """,
        {"asset_type": asset_type, "asset_id": asset_id, "fingerprint": fingerprint, "requested_by": actor},
    )
    return item


def list_certifications(asset_type: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: dict[str, Any] = {"limit": min(max(limit, 1), 200)}
    if asset_type:
        where.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if status:
        where.append("status = :status")
        params["status"] = status
    return rows(
        f"SELECT * FROM t_sem_certification WHERE {' AND '.join(where)} ORDER BY certification_id DESC LIMIT :limit",
        params,
    )


def decide_certification(certification_id: int, approve: bool, actor: str | None, comment: str | None = None) -> dict[str, Any]:
    certification = one("SELECT * FROM t_sem_certification WHERE certification_id = :id", {"id": certification_id})
    if not certification:
        raise NotFoundError("认证单不存在", code="certification_not_found")
    if certification["status"] != "pending":
        raise ConflictError("认证单已处理", code="certification_already_decided")
    current = _asset_fingerprint(certification["asset_type"], int(certification["asset_id"]))
    if current != certification["fingerprint"]:
        raise ConflictError("资产已变更，请重新提交认证", code="certification_stale")
    status = "approved" if approve else "rejected"
    execute(
        """
        UPDATE t_sem_certification
        SET status = :status, approved_by = :actor, approved_at = now(), comment = :comment, updated_at = now()
        WHERE certification_id = :id
        """,
        {"status": status, "actor": actor, "comment": comment, "id": certification_id},
    )
    if approve:
        if certification["asset_type"] == "model":
            execute(
                """
                UPDATE t_sem_model SET status = 'certified', certified_at = now(), semantic_hash = :hash, updated_at = now()
                WHERE model_id = :id
                """,
                {"hash": certification["fingerprint"], "id": certification["asset_id"]},
            )
        elif certification["asset_type"] == "metric":
            execute(
                """
                UPDATE t_sem_metric SET status = 'certified', certified_at = now(), certified_hash = :hash, updated_at = now()
                WHERE metric_id = :id
                """,
                {"hash": certification["fingerprint"], "id": certification["asset_id"]},
            )
        elif certification["asset_type"] == "binding":
            execute(
                """
                UPDATE t_sem_binding SET status = 'certified', verified = TRUE, certified_at = now(), updated_at = now()
                WHERE binding_id = :id
                """,
                {"id": certification["asset_id"]},
            )
    return one("SELECT * FROM t_sem_certification WHERE certification_id = :id", {"id": certification_id}) or {}


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = {"generated_at": datetime.utcnow().isoformat()}
    for table in SNAPSHOT_TABLES:
        payload[table] = rows(f"SELECT * FROM {table} ORDER BY 1")
    payload["fingerprint"] = _hash({key: value for key, value in payload.items() if key != "generated_at"})
    return payload


def build_snapshot(actor: str | None) -> dict[str, Any]:
    payload = _payload()
    version = datetime.utcnow().strftime("v%Y%m%d%H%M%S")
    existing = one("SELECT snapshot_id FROM t_sem_snapshot WHERE version = :version", {"version": version})
    if existing:
        version = f"{version}-{existing['snapshot_id']}"
    execute("UPDATE t_sem_snapshot SET status = 'archived' WHERE status = 'active'")
    item = insert(
        """
        INSERT INTO t_sem_snapshot (version, fingerprint, payload, status, published_by)
        VALUES (:version, :fingerprint, CAST(:payload AS JSONB), 'active', :published_by)
        RETURNING snapshot_id, version, fingerprint, status, published_at
        """,
        {"version": version, "fingerprint": payload["fingerprint"], "payload": jsonb(payload), "published_by": actor},
    )
    return item


def list_snapshots(limit: int = 50) -> list[dict[str, Any]]:
    return rows(
        "SELECT snapshot_id, version, fingerprint, status, published_by, published_at FROM t_sem_snapshot ORDER BY snapshot_id DESC LIMIT :limit",
        {"limit": min(max(limit, 1), 200)},
    )


def active_snapshot() -> dict[str, Any] | None:
    return one(
        "SELECT snapshot_id, version, fingerprint, status, published_at FROM t_sem_snapshot WHERE status = 'active' ORDER BY snapshot_id DESC LIMIT 1"
    )


def get_snapshot(version: str) -> dict[str, Any]:
    item = one("SELECT * FROM t_sem_snapshot WHERE version = :version", {"version": version})
    if not item:
        raise NotFoundError("快照不存在", code="snapshot_not_found")
    return item


def diff_snapshots(left_version: str, right_version: str) -> dict[str, Any]:
    left = get_snapshot(left_version)
    right = get_snapshot(right_version)
    left_payload = left["payload"] or {}
    right_payload = right["payload"] or {}
    changed = []
    for table in SNAPSHOT_TABLES:
        if json.dumps(left_payload.get(table), sort_keys=True, default=str) != json.dumps(
            right_payload.get(table), sort_keys=True, default=str
        ):
            changed.append(
                {
                    "table": table,
                    "left": len(left_payload.get(table) or []),
                    "right": len(right_payload.get(table) or []),
                }
            )
    return {
        "left": {"version": left_version, "fingerprint": left["fingerprint"]},
        "right": {"version": right_version, "fingerprint": right["fingerprint"]},
        "changed": changed,
    }


def rollback(version: str, actor: str | None) -> dict[str, Any]:
    target = get_snapshot(version)
    execute_many(
        [
            ("UPDATE t_sem_snapshot SET status = 'archived' WHERE status = 'active'", {}),
            (
                "UPDATE t_sem_snapshot SET status = 'active', published_by = :actor, published_at = now() WHERE snapshot_id = :id",
                {"actor": actor, "id": target["snapshot_id"]},
            ),
        ]
    )
    return get_snapshot(version)