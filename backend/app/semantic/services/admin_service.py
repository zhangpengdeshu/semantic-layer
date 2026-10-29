"""工作台统计、用户角色、审计与问数日志。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import one, rows


def workbench() -> dict[str, Any]:
    stats = one(
        """
        SELECT
          (SELECT count(*) FROM t_sem_domain) AS domains,
          (SELECT count(*) FROM t_sem_model) AS models,
          (SELECT count(*) FROM t_sem_metric) AS metrics,
          (SELECT count(*) FROM t_sem_model m
            WHERE NOT EXISTS (
              SELECT 1 FROM t_sem_binding b
              WHERE b.model_id = m.model_id AND b.status = 'certified' AND b.verified AND b.is_primary
            )) AS unbound_models,
          (SELECT count(*) FROM t_sem_certification WHERE status = 'pending') AS pending_certifications,
          (SELECT count(*) FROM t_query_log WHERE created_at >= now() - interval '24 hours') AS queries_24h,
          (SELECT count(*) FROM t_sem_validation_run WHERE status = 'failed' AND created_at >= now() - interval '24 hours') AS failed_validations_24h,
          (SELECT count(*) FROM t_sem_model WHERE status = 'certified') AS certified_models
        """
    ) or {}
    recent_models = rows(
        """
        SELECT m.model_id, m.name, m.business_name, m.status, m.updated_at, d.name AS domain_name
        FROM t_sem_model m JOIN t_sem_domain d ON d.domain_id = m.domain_id
        ORDER BY m.updated_at DESC LIMIT 8
        """
    )
    recent_queries = rows(
        """
        SELECT query_id, request_id, question, status, row_count, elapsed_ms, created_at
        FROM t_query_log ORDER BY query_id DESC LIMIT 8
        """
    )
    pending = rows(
        """
        SELECT certification_id, asset_type, asset_id, status, requested_by, created_at
        FROM t_sem_certification WHERE status = 'pending' ORDER BY certification_id DESC LIMIT 8
        """
    )
    return {"stats": stats, "recent_models": recent_models, "recent_queries": recent_queries, "pending_certifications": pending}


def list_users() -> list[dict[str, Any]]:
    return rows("SELECT * FROM t_user ORDER BY user_id")


def list_roles() -> list[dict[str, Any]]:
    return rows("SELECT * FROM t_role ORDER BY role_id")


def list_permissions() -> list[dict[str, Any]]:
    return rows("SELECT * FROM t_permission ORDER BY permission_id DESC LIMIT 200")


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    return rows("SELECT * FROM t_audit_event ORDER BY event_id DESC LIMIT :limit", {"limit": min(max(limit, 1), 200)})


def list_queries(limit: int = 100) -> list[dict[str, Any]]:
    return rows(
        "SELECT query_id, request_id, user_id, question, status, error_code, row_count, elapsed_ms, created_at FROM t_query_log ORDER BY query_id DESC LIMIT :limit",
        {"limit": min(max(limit, 1), 200)},
    )