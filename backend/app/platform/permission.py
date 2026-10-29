"""权限解析：用户角色 → 行级过滤与列级掩码（编译期注入）。"""

from __future__ import annotations

from app.semantic.compiler.contracts import PermissionContext
from app.semantic.repository.db import rows


def roles_for(user_id: str | None) -> list[str]:
    if not user_id:
        return []
    items = rows(
        """
        SELECT r.code FROM t_user_role ur
        JOIN t_role r ON r.role_id = ur.role_id
        WHERE ur.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    return [str(item["code"]) for item in items]


def effective_roles(user_id: str | None, fallback: list[str] | None = None) -> list[str]:
    discovered = roles_for(user_id)
    return discovered or list(fallback or [])


def context_for(user_id: str | None, roles: list[str] | None = None) -> PermissionContext:
    """汇总当前用户命中的角色/用户级策略，产出编译期权限上下文。"""
    role_set = set(roles or []) | set(roles_for(user_id))
    policies = rows("SELECT * FROM t_permission ORDER BY permission_id")
    row_filters: list[str] = []
    column_masks: dict[str, str] = {}
    for policy in policies:
        subject_type = policy.get("subject_type") or "role"
        subject_id = str(policy.get("subject_id") or "")
        matched = (
            subject_type == "role" and subject_id in role_set
        ) or (subject_type == "user" and subject_id == (user_id or ""))
        if not matched:
            continue
        condition = policy.get("row_filter")
        if condition:
            if (policy.get("effect") or "allow") == "deny":
                row_filters.append(f"NOT ({condition})")
            else:
                row_filters.append(str(condition))
        for key, value in (policy.get("column_mask") or {}).items():
            column_masks[str(key)] = str(value)
    return PermissionContext(row_filters=row_filters, column_masks=column_masks)