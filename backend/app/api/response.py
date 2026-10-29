"""统一响应包裹。"""

from __future__ import annotations

from typing import Any

from fastapi import Request


def ok(data: Any, request: Request) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ok",
        "data": data,
        "request_id": getattr(request.state, "request_id", None),
    }


def paged(items: list[Any], total: int, page: int, page_size: int, request: Request) -> dict[str, Any]:
    return ok(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        request,
    )