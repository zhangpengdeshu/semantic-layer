"""字段、维度、度量、关系的顶层 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok
from app.api.schemas.semantic import (
    DimensionUpdate,
    FieldUpdate,
    MeasureUpdate,
    RelationshipCreate,
    RelationshipUpdate,
)
from app.platform import audit
from app.semantic.services import (
    dimension_service,
    field_service,
    measure_service,
    relationship_service,
)

router = APIRouter(tags=["assets"])


@router.get("/fields/{field_id}")
def get_field(field_id: int, request: Request):
    return ok(field_service.get_field(field_id), request)


@router.patch("/fields/{field_id}")
def update_field(field_id: int, payload: FieldUpdate, request: Request, user: UserContext = Depends(writer_user)):
    before = field_service.get_field(field_id)
    item = field_service.update_field(field_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "field.update", "field", field_id, before=before, after=item)
    return ok(item, request)


@router.delete("/fields/{field_id}")
def delete_field(field_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = field_service.get_field(field_id)
    field_service.delete_field(field_id)
    audit.record(user.user_id, "field.delete", "field", field_id, before=before)
    return ok({"deleted": True}, request)


@router.get("/dimensions/{dimension_id}")
def get_dimension(dimension_id: int, request: Request):
    return ok(dimension_service.get_dimension(dimension_id), request)


@router.patch("/dimensions/{dimension_id}")
def update_dimension(
    dimension_id: int,
    payload: DimensionUpdate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    before = dimension_service.get_dimension(dimension_id)
    item = dimension_service.update_dimension(dimension_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "dimension.update", "dimension", dimension_id, before=before, after=item)
    return ok(item, request)


@router.delete("/dimensions/{dimension_id}")
def delete_dimension(dimension_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = dimension_service.get_dimension(dimension_id)
    dimension_service.delete_dimension(dimension_id)
    audit.record(user.user_id, "dimension.delete", "dimension", dimension_id, before=before)
    return ok({"deleted": True}, request)


@router.get("/measures/{measure_id}")
def get_measure(measure_id: int, request: Request):
    return ok(measure_service.get_measure(measure_id), request)


@router.patch("/measures/{measure_id}")
def update_measure(measure_id: int, payload: MeasureUpdate, request: Request, user: UserContext = Depends(writer_user)):
    before = measure_service.get_measure(measure_id)
    item = measure_service.update_measure(measure_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "measure.update", "measure", measure_id, before=before, after=item)
    return ok(item, request)


@router.delete("/measures/{measure_id}")
def delete_measure(measure_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = measure_service.get_measure(measure_id)
    measure_service.delete_measure(measure_id)
    audit.record(user.user_id, "measure.delete", "measure", measure_id, before=before)
    return ok({"deleted": True}, request)


@router.get("/relationships")
def list_relationships(request: Request, model_id: int | None = None):
    return ok(relationship_service.list_relationships(model_id), request)


@router.post("/relationships")
def create_relationship(payload: RelationshipCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = relationship_service.create_relationship(payload.model_dump())
    audit.record(user.user_id, "relationship.create", "relationship", item["edge_id"], after=item)
    return ok(item, request)


@router.get("/relationships/{edge_id}")
def get_relationship(edge_id: int, request: Request):
    return ok(relationship_service.get_relationship(edge_id), request)


@router.patch("/relationships/{edge_id}")
def update_relationship(
    edge_id: int,
    payload: RelationshipUpdate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    before = relationship_service.get_relationship(edge_id)
    item = relationship_service.update_relationship(edge_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "relationship.update", "relationship", edge_id, before=before, after=item)
    return ok(item, request)


@router.delete("/relationships/{edge_id}")
def delete_relationship(edge_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = relationship_service.get_relationship(edge_id)
    relationship_service.delete_relationship(edge_id)
    audit.record(user.user_id, "relationship.delete", "relationship", edge_id, before=before)
    return ok({"deleted": True}, request)