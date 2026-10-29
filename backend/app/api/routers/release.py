"""认证与快照 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import UserContext, admin_user, reviewer_user, writer_user
from app.api.response import ok
from app.api.schemas.semantic import CertificationCreate, CertificationDecision
from app.platform import audit
from app.semantic.services import release_service

router = APIRouter(tags=["release"])


@router.get("/certifications")
def list_certifications(request: Request, asset_type: str | None = None, status: str | None = None, limit: int = 100):
    return ok(release_service.list_certifications(asset_type, status, limit), request)


@router.post("/certifications")
def create_certification(payload: CertificationCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = release_service.create_certification(payload.asset_type, payload.asset_id, user.user_id)
    audit.record(user.user_id, "certification.create", "certification", item["certification_id"], after=item)
    return ok(item, request)


@router.post("/certifications/{certification_id}/decision")
def decide_certification(
    certification_id: int,
    payload: CertificationDecision,
    request: Request,
    user: UserContext = Depends(reviewer_user),
):
    item = release_service.decide_certification(certification_id, payload.approve, user.user_id, payload.comment)
    audit.record(
        user.user_id,
        "certification.decision",
        "certification",
        certification_id,
        after={"approve": payload.approve, "status": item.get("status")},
    )
    return ok(item, request)


@router.get("/snapshots")
def list_snapshots(request: Request, limit: int = 50):
    return ok(release_service.list_snapshots(limit), request)


@router.post("/snapshots")
def build_snapshot(request: Request, user: UserContext = Depends(reviewer_user)):
    item = release_service.build_snapshot(user.user_id)
    audit.record(user.user_id, "snapshot.build", "snapshot", item["snapshot_id"], after=item)
    return ok(item, request)


@router.get("/snapshots/active")
def active_snapshot(request: Request):
    return ok(release_service.active_snapshot(), request)


@router.get("/snapshots/diff")
def diff_snapshots(request: Request, left: str, right: str):
    return ok(release_service.diff_snapshots(left, right), request)


@router.get("/snapshots/{version}")
def get_snapshot(version: str, request: Request):
    return ok(release_service.get_snapshot(version), request)


@router.post("/snapshots/{version}/rollback")
def rollback(version: str, request: Request, user: UserContext = Depends(admin_user)):
    item = release_service.rollback(version, user.user_id)
    audit.record(user.user_id, "snapshot.rollback", "snapshot", item["snapshot_id"], after={"version": version})
    return ok(item, request)