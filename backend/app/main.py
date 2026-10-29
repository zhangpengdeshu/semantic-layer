"""FastAPI 应用入口（语义层 v3）。"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import install_error_handlers
from app.api.routers import (
    admin,
    ask,
    assets,
    bindings,
    catalog,
    domains,
    knowledge,
    metrics,
    models,
    release,
    validation,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    yield


app = FastAPI(
    title="语义层 API",
    version="3.0.0",
    description="语义模型层：语义建模、绑定、校验、编译、问数与发布",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


install_error_handlers(app)

SEMANTIC_PREFIX = "/api/semantic/v1"
for router in (
    domains.router,
    models.router,
    assets.router,
    metrics.router,
    bindings.router,
    catalog.router,
    validation.router,
    release.router,
    knowledge.router,
    admin.router,
):
    app.include_router(router, prefix=SEMANTIC_PREFIX)
app.include_router(ask.router)


@app.get("/health", tags=["health"])
def health():
    return JSONResponse({"status": "ok", "service": "semantic-layer", "version": "3.0.0"})