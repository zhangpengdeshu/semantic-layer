"""数据库连接。

分层约束：
- `read_session()` 供问数、校验、编译读取语义目录；
- `write_session()` 仅供 backend service 使用；
- 只读不是靠调用方自觉，而是靠 PostgreSQL `default_transaction_read_only=on`。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import settings

READ_ONLY_OPTIONS = "-c default_transaction_read_only=on"


def dsn() -> str:
    return settings.database_url


@lru_cache(maxsize=2)
def get_engine(readonly: bool = True) -> Engine:
    connect_args: dict[str, object] = {
        "connect_timeout": 10,
        "application_name": "semantic-layer-readonly" if readonly else "semantic-layer-write",
    }
    if readonly:
        connect_args["options"] = READ_ONLY_OPTIONS
    return create_engine(
        dsn(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        connect_args=connect_args,
    )


@lru_cache(maxsize=2)
def get_session_factory(readonly: bool = True) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(readonly), expire_on_commit=False)


@contextmanager
def read_session() -> Iterator[Session]:
    session = get_session_factory(True)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def write_session() -> Iterator[Session]:
    session = get_session_factory(False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping() -> bool:
    from sqlalchemy import text

    with read_session() as session:
        return session.execute(text("SELECT 1")).scalar_one() == 1