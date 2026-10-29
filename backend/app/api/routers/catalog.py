"""数据集 / 物理目录 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok, paged
from app.api.schemas.semantic import DatasetSyncRequest
from app.platform import audit
from app.semantic.services import catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/datasets")
def list_datasets(
    request: Request,
    q: str | None = None,
    source_system: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    data = catalog_service.list_datasets(q=q, source_system=source_system, page=page, page_size=page_size)
    return paged(data["items"], data["total"], data["page"], data["page_size"], request)


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, request: Request):
    return ok(catalog_service.get_dataset(dataset_id), request)


@router.get("/datasets/{dataset_id}/columns")
def get_dataset_columns(dataset_id: int, request: Request):
    data = catalog_service.get_dataset(dataset_id)
    return ok(data["columns"], request)


@router.post("/datasets:sync")
def sync_datasets(payload: DatasetSyncRequest, request: Request, user: UserContext = Depends(writer_user)):
    item = catalog_service.sync_datasets(payload.model_dump())
    audit.record(user.user_id, "catalog.datasets.sync", "catalog", None, after=item)
    return ok(item, request)


@router.get("/tables")
def list_tables(
    request: Request,
    q: str | None = None,
    source_system: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    data = catalog_service.list_tables(q=q, source_system=source_system, page=page, page_size=page_size)
    return paged(data["items"], data["total"], data["page"], data["page_size"], request)


@router.get("/tables/{table_id}")
def get_table(table_id: int, request: Request):
    return ok(catalog_service.get_table(table_id), request)