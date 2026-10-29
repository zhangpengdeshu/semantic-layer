"""校验 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import UserContext, current_user
from app.api.response import ok
from app.api.schemas.semantic import BatchValidationRequest
from app.semantic.services import validation_service

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("")
def list_runs(request: Request, object_type: str | None = None, object_id: int | None = None, limit: int = 50):
    return ok(validation_service.list_runs(object_type, object_id, limit), request)


@router.post("/batch")
def batch_validate(payload: BatchValidationRequest, request: Request, user: UserContext = Depends(current_user)):
    return ok(validation_service.batch(payload.model_ids, payload.level, user.user_id), request)


@router.get("/impact")
def impact(request: Request, asset_type: str, asset_id: int):
    return ok(validation_service.impact(asset_type, asset_id), request)