"""API 错误处理。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.semantic.compiler.contracts import CompileError
from app.semantic.services.errors import ServiceError

logger = logging.getLogger(__name__)


def _body(code: str, message: str, request: Request, detail: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, str(exc), request, exc.detail),
        )

    @app.exception_handler(CompileError)
    async def compile_error_handler(request: Request, exc: CompileError) -> JSONResponse:
        """编译期语义错误属于请求问题，统一返回 422 而不是 500。"""
        return JSONResponse(
            status_code=422,
            content=_body(exc.code, exc.message, request, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_body("validation_error", "请求参数校验失败", request, exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_body("internal_error", "服务内部错误", request, None),
        )