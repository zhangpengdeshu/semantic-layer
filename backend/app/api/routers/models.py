"""语义模型 API（含字段、粒度、维度、度量、关系、绑定、校验子资源）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok, paged
from app.api.schemas.semantic import (
    BindingCreate,
    DimensionCreate,
    FieldBatch,
    FieldCreate,
    GrainUpdate,
    MeasureCreate,
    ModelCreate,
    ModelUpdate,
    RelationshipCreate,
    ValidationRequest,
)
from app.platform import audit
from app.semantic.services import (
    binding_service,
    dimension_service,
    field_service,
    measure_service,
    model_service,
    relationship_service,
    validation_service,
)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_models(
    request: Request,
    domain_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    queryable: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    data = model_service.list_models(
        domain_id=domain_id, status=status, q=q, queryable=queryable, page=page, page_size=page_size
    )
    return paged(data["items"], data["total"], data["page"], data["page_size"], request)


@router.post("")
def create_model(payload: ModelCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = model_service.create_model(payload.model_dump())
    audit.record(user.user_id, "model.create", "model", item["model_id"], after=item)
    return ok(item, request)


@router.get("/{model_id}")
def get_model(model_id: int, request: Request):
    return ok(model_service.get_model(model_id), request)


@router.patch("/{model_id}")
def update_model(model_id: int, payload: ModelUpdate, request: Request, user: UserContext = Depends(writer_user)):
    before = model_service.get_model(model_id)
    item = model_service.update_model(model_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "model.update", "model", model_id, before=before, after=item)
    return ok(item, request)


@router.delete("/{model_id}")
def delete_model(model_id: int, request: Request, user: UserContext = Depends(writer_user)):
    before = model_service.get_model(model_id)
    model_service.delete_model(model_id)
    audit.record(user.user_id, "model.delete", "model", model_id, before=before)
    return ok({"deleted": True}, request)


@router.put("/{model_id}/grain")
def set_grain(model_id: int, payload: GrainUpdate, request: Request, user: UserContext = Depends(writer_user)):
    item = model_service.set_grain(model_id, payload.field_ids)
    audit.record(user.user_id, "model.grain.update", "model", model_id, after=item.get("grain"))
    return ok(item, request)


@router.get("/{model_id}/fields")
def list_fields(model_id: int, request: Request):
    return ok(field_service.list_fields(model_id), request)


@router.post("/{model_id}/fields")
def create_field(model_id: int, payload: FieldCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = field_service.create_field(model_id, payload.model_dump())
    audit.record(user.user_id, "field.create", "field", item["field_id"], after=item)
    return ok(item, request)


@router.post("/{model_id}/fields:batch")
def batch_create_fields(model_id: int, payload: FieldBatch, request: Request, user: UserContext = Depends(writer_user)):
    items = field_service.batch_create_fields(model_id, [item.model_dump() for item in payload.fields])
    audit.record(user.user_id, "field.batch_create", "model", model_id, after={"count": len(items)})
    return ok(items, request)


@router.get("/{model_id}/dimensions")
def list_dimensions(model_id: int, request: Request):
    return ok(dimension_service.list_dimensions(model_id), request)


@router.post("/{model_id}/dimensions")
def create_dimension(model_id: int, payload: DimensionCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = dimension_service.create_dimension(model_id, payload.model_dump())
    audit.record(user.user_id, "dimension.create", "dimension", item["dimension_id"], after=item)
    return ok(item, request)


@router.get("/{model_id}/measures")
def list_measures(model_id: int, request: Request):
    return ok(measure_service.list_measures(model_id), request)


@router.post("/{model_id}/measures")
def create_measure(model_id: int, payload: MeasureCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = measure_service.create_measure(model_id, payload.model_dump())
    audit.record(user.user_id, "measure.create", "measure", item["measure_id"], after=item)
    return ok(item, request)


@router.get("/{model_id}/relationships")
def list_relationships(model_id: int, request: Request):
    return ok(relationship_service.list_relationships(model_id), request)


@router.post("/{model_id}/relationships")
def create_relationship(
    model_id: int,
    payload: RelationshipCreate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    data = payload.model_dump()
    data["from_model_id"] = model_id
    item = relationship_service.create_relationship(data)
    audit.record(user.user_id, "relationship.create", "relationship", item["edge_id"], after=item)
    return ok(item, request)


@router.get("/{model_id}/relationship-suggestions")
def relationship_suggestions(model_id: int, request: Request):
    return ok(relationship_service.suggestions(model_id), request)


@router.get("/{model_id}/bindings")
def list_bindings(model_id: int, request: Request):
    return ok(binding_service.list_bindings(model_id), request)


@router.post("/{model_id}/bindings")
def create_binding(
    model_id: int,
    payload: BindingCreate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    item = binding_service.create_binding(model_id, payload.model_dump())
    audit.record(user.user_id, "binding.create", "binding", item["binding_id"], after=item)
    return ok(item, request)


@router.get("/{model_id}/validation")
def list_validation(model_id: int, request: Request):
    return ok(validation_service.list_runs("model", model_id), request)


@router.post("/{model_id}/validation")
def run_validation(
    model_id: int,
    payload: ValidationRequest,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    if payload.level not in {"semantic", "queryable"}:
        from app.semantic.services.errors import ValidationFailedError

        raise ValidationFailedError("level 只能是 semantic 或 queryable", code="invalid_validation_level")
    item = validation_service.run_model(model_id, payload.level, user.user_id)
    audit.record(user.user_id, f"model.validate.{payload.level}", "model", model_id, after={"status": item["status"]})
    return ok(item, request)