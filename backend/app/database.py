from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings
from .observability import instrument_database_engine

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    url = database_url or settings.database_url
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update({"pool_size": 5, "max_overflow": 5, "pool_recycle": 300})
    engine = create_async_engine(url, **kwargs)
    instrument_database_engine(engine)
    if url.startswith("sqlite"):
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def create_schema(target_engine: AsyncEngine | None = None) -> None:
    from . import models  # noqa: F401

    selected = target_engine or engine
    async with selected.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_schema(target_engine: AsyncEngine | None = None) -> None:
    from . import models  # noqa: F401

    selected = target_engine or engine
    async with selected.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
