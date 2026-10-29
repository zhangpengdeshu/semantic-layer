"""知识上下文 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import UserContext, writer_user
from app.api.response import ok
from app.api.schemas.semantic import (
    ContextUpdate,
    RuleCreate,
    RuleUpdate,
    SynonymCreate,
    SynonymUpdate,
    TermCreate,
    TermUpdate,
)
from app.platform import audit
from app.semantic.services import knowledge_service

router = APIRouter(tags=["knowledge"])


@router.get("/terms")
def list_terms(request: Request, q: str | None = None):
    return ok(knowledge_service.list_terms(q), request)


@router.post("/terms")
def create_term(payload: TermCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.create_term(payload.model_dump())
    audit.record(user.user_id, "term.create", "term", item["term_id"], after=item)
    return ok(item, request)


@router.patch("/terms/{term_id}")
def update_term(term_id: int, payload: TermUpdate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.update_term(term_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "term.update", "term", term_id, after=item)
    return ok(item, request)


@router.delete("/terms/{term_id}")
def delete_term(term_id: int, request: Request, user: UserContext = Depends(writer_user)):
    knowledge_service.delete_term(term_id)
    audit.record(user.user_id, "term.delete", "term", term_id)
    return ok({"deleted": True}, request)


@router.get("/synonyms")
def list_synonyms(request: Request, q: str | None = None):
    return ok(knowledge_service.list_synonyms(q), request)


@router.post("/synonyms")
def create_synonym(payload: SynonymCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.create_synonym(payload.model_dump())
    audit.record(user.user_id, "synonym.create", "synonym", item["synonym_id"], after=item)
    return ok(item, request)


@router.patch("/synonyms/{synonym_id}")
def update_synonym(synonym_id: int, payload: SynonymUpdate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.update_synonym(synonym_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "synonym.update", "synonym", synonym_id, after=item)
    return ok(item, request)


@router.delete("/synonyms/{synonym_id}")
def delete_synonym(synonym_id: int, request: Request, user: UserContext = Depends(writer_user)):
    knowledge_service.delete_synonym(synonym_id)
    audit.record(user.user_id, "synonym.delete", "synonym", synonym_id)
    return ok({"deleted": True}, request)


@router.get("/rules")
def list_rules(request: Request):
    return ok(knowledge_service.list_rules(), request)


@router.post("/rules")
def create_rule(payload: RuleCreate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.create_rule(payload.model_dump())
    audit.record(user.user_id, "rule.create", "rule", item["rule_id"], after=item)
    return ok(item, request)


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleUpdate, request: Request, user: UserContext = Depends(writer_user)):
    item = knowledge_service.update_rule(rule_id, payload.model_dump(exclude_unset=True))
    audit.record(user.user_id, "rule.update", "rule", rule_id, after=item)
    return ok(item, request)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, request: Request, user: UserContext = Depends(writer_user)):
    knowledge_service.delete_rule(rule_id)
    audit.record(user.user_id, "rule.delete", "rule", rule_id)
    return ok({"deleted": True}, request)


@router.get("/context/{asset_type}/{asset_id}")
def get_context(asset_type: str, asset_id: int, request: Request):
    return ok(knowledge_service.get_context(asset_type, asset_id), request)


@router.put("/context/{asset_type}/{asset_id}")
def put_context(
    asset_type: str,
    asset_id: int,
    payload: ContextUpdate,
    request: Request,
    user: UserContext = Depends(writer_user),
):
    item = knowledge_service.put_context(asset_type, asset_id, payload.model_dump())
    audit.record(user.user_id, "context.update", asset_type, asset_id, after=item)
    return ok(item, request)


@router.post("/recall-test")
def recall_test(request: Request, question: str):
    return ok(knowledge_service.recall_test(question), request)