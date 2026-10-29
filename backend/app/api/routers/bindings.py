"""绑定 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok
from app.api.schemas.semantic import BindingUpdate, FieldMappingsUpdate
from app.platform import audit
from app.semantic.services import binding_service

router = APIRouter(prefix="/bindings", tags=["bindings"])


@router.get("/{binding_id}")
def get_binding(binding_id: int, request: Request):
    return ok(binding_service.get_binding(binding_id), request)


@router.patch("/{binding_id}")
def update_binding(
    binding_id: int,
    payload: BindingUpdate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    before = binding_service.get_binding(binding_id)
    item = binding_service.update_binding(binding_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "binding.update", "binding", binding_id, before=before, after=item)
    return ok(item, request)


@router.delete("/{binding_id}")
def delete_binding(binding_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = binding_service.get_binding(binding_id)
    binding_service.delete_binding(binding_id)
    audit.record(user.user_id, "binding.delete", "binding", binding_id, before=before)
    return ok({"deleted": True}, request)


@router.post("/{binding_id}:set-primary")
def set_primary(binding_id: int, request: Request, user: UserContext = Depends(writer_user)):
    item = binding_service.set_primary(binding_id)
    audit.record(user.user_id, "binding.set_primary", "binding", binding_id, after=item)
    return ok(item, request)


@router.get("/{binding_id}/field-mappings")
def get_field_mappings(binding_id: int, request: Request):
    return ok(binding_service.get_field_mappings(binding_id), request)


@router.get("/{binding_id}/columns")
def available_columns(binding_id: int, request: Request):
    return ok(binding_service.available_columns(binding_id), request)


@router.put("/{binding_id}/field-mappings")
def put_field_mappings(
    binding_id: int,
    payload: FieldMappingsUpdate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    item = binding_service.put_field_mappings(binding_id, [row.model_dump() for row in payload.items])
    audit.record(user.user_id, "binding.field_mappings.update", "binding", binding_id, after={"count": len(payload.items)})
    return ok(item, request)


@router.post("/{binding_id}/auto-map")
def auto_map(binding_id: int, request: Request, user: UserContext = Depends(writer_user)):
    item = binding_service.auto_map(binding_id)
    audit.record(user.user_id, "binding.auto_map", "binding", binding_id, after={"mapped": item.get("mapped", 0)})
    return ok(item, request)


@router.get("/{binding_id}/drift")
def drift(binding_id: int, request: Request):
    return ok(binding_service.drift_check(binding_id), request)