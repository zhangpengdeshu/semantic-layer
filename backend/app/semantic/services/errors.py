"""服务层异常：API 层统一转换为 HTTP 错误。"""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, detail: Any = None):
        super().__init__(message)
        if code:
            self.code = code
        self.detail = detail


class NotFoundError(ServiceError):
    status_code = 404
    code = "not_found"


class ConflictError(ServiceError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(ServiceError):
    status_code = 422
    code = "validation_failed"


class PermissionDeniedError(ServiceError):
    status_code = 403
    code = "permission_denied"