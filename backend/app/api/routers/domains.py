"""主题域 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok, paged
from app.api.schemas.semantic import DomainCreate, DomainUpdate
from app.platform import audit
from app.semantic.services import domain_service

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("")
def list_domains(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    data = domain_service.list_domains(q=q, status=status, page=page, page_size=page_size)
    return paged(data["items"], data["total"], data["page"], data["page_size"], request)


@router.post("")
def create_domain(payload: DomainCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = domain_service.create_domain(payload.model_dump())
    audit.record(user.user_id, "domain.create", "domain", item["domain_id"], after=item)
    return ok(item, request)


@router.get("/{domain_id}")
def get_domain(domain_id: int, request: Request):
    return ok(domain_service.get_domain(domain_id), request)


@router.patch("/{domain_id}")
def update_domain(domain_id: int, payload: DomainUpdate, request: Request, user: UserContext = Depends(writer_user)):
    before = domain_service.get_domain(domain_id)
    item = domain_service.update_domain(domain_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "domain.update", "domain", domain_id, before=before, after=item)
    return ok(item, request)


@router.delete("/{domain_id}")
def delete_domain(domain_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = domain_service.get_domain(domain_id)
    domain_service.delete_domain(domain_id)
    audit.record(user.user_id, "domain.delete", "domain", domain_id, before=before)
    return ok({"deleted": True}, request)