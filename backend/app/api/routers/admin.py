"""工作台与平台管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.response import ok
from app.semantic.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/workbench")
def workbench(request: Request):
    return ok(admin_service.workbench(), request)


@router.get("/users")
def list_users(request: Request):
    return ok(admin_service.list_users(), request)


@router.get("/roles")
def list_roles(request: Request):
    return ok(admin_service.list_roles(), request)


@router.get("/permissions")
def list_permissions(request: Request):
    return ok(admin_service.list_permissions(), request)


@router.get("/audit")
def list_audit(request: Request, limit: int = 100):
    return ok(admin_service.list_audit(limit), request)


@router.get("/queries")
def list_queries(request: Request, limit: int = 100):
    return ok(admin_service.list_queries(limit), request)