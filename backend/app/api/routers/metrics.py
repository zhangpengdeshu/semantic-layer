"""指标 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok, paged
from app.api.schemas.semantic import MetricCreate, MetricUpdate
from app.platform import audit
from app.semantic.services import metric_service, validation_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def list_metrics(
    request: Request,
    q: str | None = None,
    metric_type: str | None = None,
    status: str | None = None,
    domain_id: int | None = None,
    model_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    data = metric_service.list_metrics(
        q=q,
        metric_type=metric_type,
        status=status,
        domain_id=domain_id,
        model_id=model_id,
        page=page,
        page_size=page_size,
    )
    return paged(data["items"], data["total"], data["page"], data["page_size"], request)


@router.post("")
def create_metric(payload: MetricCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = metric_service.create_metric(payload.model_dump())
    audit.record(user.user_id, "metric.create", "metric", item["metric_id"], after=item)
    return ok(item, request)


@router.get("/{metric_id}")
def get_metric(metric_id: int, request: Request):
    return ok(metric_service.get_metric(metric_id), request)


@router.patch("/{metric_id}")
def update_metric(metric_id: int, payload: MetricUpdate, request: Request, user: UserContext = Depends(writer_user)):
    before = metric_service.get_metric(metric_id)
    item = metric_service.update_metric(metric_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "metric.update", "metric", metric_id, before=before, after=item)
    return ok(item, request)


@router.delete("/{metric_id}")
def delete_metric(metric_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = metric_service.get_metric(metric_id)
    metric_service.delete_metric(metric_id)
    audit.record(user.user_id, "metric.delete", "metric", metric_id, before=before)
    return ok({"deleted": True}, request)


@router.get("/{metric_id}/dependency-graph")
def dependency_graph(metric_id: int, request: Request):
    return ok(metric_service.dependency_graph(metric_id), request)


@router.get("/{metric_id}/fingerprint")
def fingerprint(metric_id: int, request: Request):
    return ok({"metric_id": metric_id, "fingerprint": metric_service.fingerprint(metric_id)}, request)


@router.post("/{metric_id}/validation")
def validate_metric(metric_id: int, request: Request, user: UserContext = Depends(writer_user)):
    item = validation_service.run_metric(metric_id, "semantic", user.user_id)
    audit.record(user.user_id, "metric.validate", "metric", metric_id, after={"status": item["status"]})
    return ok(item, request)