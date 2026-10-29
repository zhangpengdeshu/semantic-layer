"""问数与编译 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agent import pipeline
from app.api.deps import UserContext, current_user
from app.api.response import ok
from app.api.schemas.semantic import AskRequest, CompileRequest
from app.semantic.compiler.contracts import QueryIR
from app.semantic.repository.db import one

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.post("")
def ask(payload: AskRequest, request: Request, user: UserContext = Depends(current_user)):
    return ok(pipeline.ask(payload.question, user.user_id, payload.domain_id, user.roles), request)


@router.post("/compile")
def compile_preview(payload: CompileRequest, request: Request):
    query_ir = QueryIR(**payload.query_ir) if payload.query_ir else None
    return ok(
        pipeline.compile_preview(question=payload.question, query_ir=query_ir, domain_id=payload.domain_id),
        request,
    )


@router.get("/{request_id}/explain")
def explain(request_id: str, request: Request):
    item = one(
        """
        SELECT request_id, question, metric_ids, model_ids, binding_ids, query_ir, sql,
               snapshot_version, row_count, elapsed_ms, status, error_code, created_at
        FROM t_query_log WHERE request_id = :request_id
        """,
        {"request_id": request_id},
    )
    return ok(item, request)