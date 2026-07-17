from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DIRECTORY = tempfile.mkdtemp(prefix="ambrosia-backend-tests-")
explicit_database_url = os.environ.get("DATABASE_URL")
allow_explicit_test_database = (
    os.environ.get("APP_ENV", "").lower() == "test"
    and os.environ.get("ALLOW_TEST_DATABASE_RESET", "").lower() == "true"
)
if explicit_database_url and allow_explicit_test_database:
    parsed_database_url = urlparse(explicit_database_url)
    if not explicit_database_url.startswith("sqlite") and parsed_database_url.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise RuntimeError("Tests may reset only a local disposable database")
else:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DIRECTORY}/test.db"
os.environ["APP_ENV"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ["AUTO_CREATE_SCHEMA"] = "false"
os.environ["AUTO_SEED"] = "false"
os.environ["AUTH_SESSION_SECRET"] = "test-session-secret-not-for-production"
os.environ["DEMO_PRESENTER_SECRET"] = "test-presenter-code"
os.environ["MODAL_INTERNAL_AUTH_SECRET"] = "test-modal-internal-secret"
os.environ["EXECUTION_PLATFORM"] = "local"

from app.database import SessionLocal, create_schema, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import reset_demo_database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def schema() -> AsyncIterator[None]:
    expected_dialect = (
        "postgresql"
        if explicit_database_url
        and allow_explicit_test_database
        and not explicit_database_url.startswith("sqlite")
        else "sqlite"
    )
    assert engine.dialect.name == expected_dialect
    print(f"backend contract tests use {engine.dialect.name}")
    await create_schema()
    yield


@pytest.fixture(autouse=True)
async def canonical_seed(schema: None) -> AsyncIterator[None]:
    async with SessionLocal() as session:
        await reset_demo_database(session)
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
async def presenter_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        response = await test_client.post(
            "/api/auth/demo/session",
            json={"persona": "owner", "presenterCode": "test-presenter-code"},
        )
        assert response.status_code == 200, response.text
        yield test_client
