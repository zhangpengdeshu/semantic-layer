"""测试基座：仓库路径、数据库可用性、TestClient 与隔离工作区。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (str(ROOT), str(ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.db import ping  # noqa: E402
from tests.support.workspace import (  # noqa: E402
    SemanticWorkspace,
    cleanup_workspace,
    create_workspace,
)


@pytest.fixture(scope="session")
def db_ready() -> bool:
    """数据库不可用时跳过依赖 DB 的用例，而不是误报失败。"""
    try:
        ready = ping()
    except Exception:  # noqa: BLE001
        ready = False
    if not ready:
        pytest.skip("数据库不可用，先执行 scripts/init_db.sh")
    return True


@pytest.fixture()
def client():
    """进程内 FastAPI 客户端，不监听端口。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def workspace(db_ready) -> SemanticWorkspace:
    """创建独占的物理样例表，并在用例结束后清理语义资产与快照。"""
    item = create_workspace()
    try:
        yield item
    finally:
        cleanup_workspace(item)