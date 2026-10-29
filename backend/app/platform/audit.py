"""审计日志写入。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, jsonb


def record(
    actor: str | None,
    action: str,
    object_type: str | None = None,
    object_id: int | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    execute(
        """
        INSERT INTO t_audit_event (actor, action, object_type, object_id, before, after)
        VALUES (:actor, :action, :object_type, :object_id, CAST(:before AS JSONB), CAST(:after AS JSONB))
        """,
        {
            "actor": actor,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "before": jsonb(before) if before is not None else None,
            "after": jsonb(after) if after is not None else None,
        },
    )