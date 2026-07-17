from __future__ import annotations

import uuid

import pytest
from fastapi import Response
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.seed as seed_module
from app.cli import verify
from app.config import Settings
from app.database import Base, SessionLocal, engine
from app.main import clear_session_cookie
from app.models import Membership, Organization, Patient, Role, User
from app.seed import canonical_ids, seed_database


async def _bootstrap(client, persona: str):
    response = await client.get("/api/demo/bootstrap", headers={"X-Demo-Persona": persona})
    assert response.status_code == 200, response.text
    return response.json()


async def test_seed_is_idempotent_for_every_table_and_verify_is_executable() -> None:
    async with SessionLocal() as session:
        before = {
            table.name: int(await session.scalar(select(func.count()).select_from(table)) or 0)
            for table in Base.metadata.sorted_tables
        }
        await seed_database(session)
        after = {
            table.name: int(await session.scalar(select(func.count()).select_from(table)) or 0)
            for table in Base.metadata.sorted_tables
        }
    assert before == after
    assert before["patients"] == 41
    assert before["appointments"] == 42
    assert before["encounters"] == 37
    await verify()


async def test_reset_seed_has_a_fixed_flush_budget(monkeypatch) -> None:
    """Prevent remote round trips from growing once per synthetic patient."""

    flush_calls = 0
    original_flush = AsyncSession.flush

    async def counted_flush(self, *args, **kwargs):
        nonlocal flush_calls
        flush_calls += 1
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", counted_flush)
    async with SessionLocal() as session:
        await seed_module.reset_demo_database(session)

    # The former cohort loop issued more than 400 flushes. The remaining
    # ceiling covers fixed hero-graph boundaries plus six cohort FK stages.
    assert flush_calls <= 50


@pytest.mark.parametrize("environment", ["production", "prod", "staging", "stage"])
def test_deployed_environments_require_postgres_and_force_safe_runtime_settings(
    environment: str,
) -> None:
    local = Settings(
        _env_file=None,
        DATABASE_URL="sqlite+aiosqlite:///./ambrosia.db",
    )
    assert local.database_url == "sqlite+aiosqlite:///./ambrosia.db"

    deployed = {
        "APP_ENV": environment,
        "AUTH_SESSION_SECRET": "production-session-secret-32-characters",
        "DEMO_PRESENTER_SECRET": "production-presenter-secret",
        "SESSION_COOKIE_SECURE": True,
    }
    with pytest.raises(ValidationError, match="must use PostgreSQL/Neon"):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite+aiosqlite:///unsafe-production.db",
            **deployed,
        )
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://localhost/ambrosia",
        auto_create_schema=True,
        auto_seed=True,
        **deployed,
    )
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.secure_cookies is True
    assert settings.session_cookie_name == "__Host-ambrosia_session"
    assert settings.auto_create_schema is False
    assert settings.auto_seed is False
    neon = Settings(
        _env_file=None,
        DATABASE_URL=(
            "postgresql://demo:secret@example.neon.tech/ambrosia"
            "?channel_binding=require&sslmode=require&application_name=ambrosia"
        ),
    )
    assert neon.database_url == (
        "postgresql+asyncpg://demo:secret@example.neon.tech/ambrosia"
        "?ssl=require&application_name=ambrosia"
    )


def test_zero_configuration_database_uses_managed_local_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite+aiosqlite:///./.ambrosia/ambrosia.db"


def test_production_logout_expires_host_cookie_with_matching_security_attributes() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        DATABASE_URL="postgresql://localhost/ambrosia",
        AUTH_SESSION_SECRET="production-session-secret-32-characters",
        DEMO_PRESENTER_SECRET="production-presenter-secret",
        SESSION_COOKIE_SECURE=True,
    )
    response = Response()

    clear_session_cookie(response, settings)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-ambrosia_session=")
    assert "Max-Age=0" in cookie
    assert "Path=/" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie
    assert "Domain=" not in cookie


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://ambrosia-ehr.vercel.app, https://preview.example.test",
            ["https://ambrosia-ehr.vercel.app", "https://preview.example.test"],
        ),
        (
            '["https://ambrosia-ehr.vercel.app","https://preview.example.test"]',
            ["https://ambrosia-ehr.vercel.app", "https://preview.example.test"],
        ),
    ],
)
def test_cors_origins_accept_documented_env_formats(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)
    settings = Settings(_env_file=None)
    assert settings.cors_origins == expected


async def test_reset_refuses_non_demo_org_with_canonical_slug() -> None:
    async with SessionLocal() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == seed_module.DEMO_ORG_SLUG)
        )
        organization.demo_mode = False
        await session.commit()
    try:
        async with SessionLocal() as session:
            with pytest.raises(RuntimeError, match="non-demo"):
                await seed_module.reset_demo_database(session)
        async with SessionLocal() as session:
            organization = await session.scalar(
                select(Organization).where(Organization.slug == seed_module.DEMO_ORG_SLUG)
            )
            assert organization and organization.demo_mode is False
            assert await session.scalar(
                select(func.count(Patient.id)).where(
                    Patient.organization_id == organization.id
                )
            ) == 41
    finally:
        async with SessionLocal() as session:
            organization = await session.scalar(
                select(Organization).where(Organization.slug == seed_module.DEMO_ORG_SLUG)
            )
            organization.demo_mode = True
            await session.commit()


async def test_reset_rolls_back_delete_when_reseed_fails(monkeypatch) -> None:
    ids = canonical_ids()

    async def fail_seed(*_args, **_kwargs):
        raise RuntimeError("injected seed failure")

    monkeypatch.setattr(seed_module, "seed_database", fail_seed)
    async with SessionLocal() as session:
        with pytest.raises(RuntimeError, match="injected seed failure"):
            await seed_module.reset_demo_database(session)
    async with SessionLocal() as session:
        organization = await session.get(Organization, ids["organization_id"])
        patient_count = await session.scalar(
            select(func.count(Patient.id)).where(
                Patient.organization_id == ids["organization_id"]
            )
        )
    assert organization and organization.demo_mode is True
    assert patient_count == 41


async def test_bootstrap_serialization_and_role_scope(client) -> None:
    top_level = {
        "session",
        "organization",
        "scenario",
        "personas",
        "intake",
        "commandCenter",
        "patient",
        "schedule",
        "queues",
        "encounter",
        "pathology",
        "conversations",
        "claims",
        "financialContext",
        "metrics",
        "health",
        "triggerIds",
    }
    provider = await _bootstrap(client, "provider")
    assert set(provider) == top_level
    assert provider["session"]["persona"] == "provider"
    assert [item["id"] for item in provider["personas"]] == ["provider"]
    assert provider["claims"] == []
    assert provider["triggerIds"] is None
    assert provider["health"] == []
    assert provider["pathology"]["id"] is None
    assert provider["intake"]["eligibility"] == {
        "payer": "Blue Horizon PPO",
        "plan": "Preferred PPO",
        "status": "active",
        "network": "in_network",
        "specialistCopay": 45.0,
        "deductibleRemaining": 420.0,
        "estimatedResponsibility": 85.0,
        "checkedAt": provider["intake"]["eligibility"]["checkedAt"],
        "memberId": "BHP74209183",
    }
    assert provider["intake"]["draft"]["firstNoticed"] == "3–6 months ago"
    assert provider["intake"]["draft"]["change"] == [
        "Wider or larger",
        "Darker color",
    ]
    assert provider["intake"]["draft"]["symptoms"] == ["Itching"]
    slots = provider["intake"]["availableSlots"]
    assert len(slots) == 6
    assert len({slot["id"] for slot in slots}) == 6
    assert len({slot["startsAt"] for slot in slots}) == len(slots)
    assert len({slot["providerId"] for slot in slots}) == 1
    assert all(
        set(slot)
        >= {
            "id",
            "startsAt",
            "providerId",
            "locationId",
            "provider",
            "location",
        }
        for slot in slots
    )
    lesion = provider["patient"]["lesion"]
    for key in ("overviewImage", "dermoscopyImage"):
        assert set(lesion[key]) == {
            "id",
            "url",
            "name",
            "size",
            "type",
            "sha256",
            "capturedAt",
        }
        assert len(lesion[key]["sha256"]) == 64
    assert set(provider["encounter"]) >= {"id", "noteId", "draftNote", "proposals"}
    assert set(provider["encounter"]["draftNote"]) == {
        "chiefConcern",
        "historyOfPresentIllness",
        "focusedExam",
        "assessmentPlan",
    }
    assert len(provider["encounter"]["proposals"]) == 8
    assert all(uuid.UUID(item["id"]) for item in provider["encounter"]["proposals"])
    assert all(
        set(metric) >= {"tone", "supportingCount", "assumption", "source"}
        for metric in provider["metrics"]
    )

    patient = await _bootstrap(client, "patient")
    assert set(patient) == top_level
    assert patient["commandCenter"] is None
    assert patient["queues"] == []
    assert patient["encounter"] is None
    assert patient["pathology"] is None
    assert patient["claims"] == []
    assert patient["metrics"] == []
    assert patient["health"] == []
    assert patient["triggerIds"] is None
    assert {item["patient"] for item in patient["schedule"]} <= {"Sarah Mitchell"}
    assert all(
        not message.get("aiDraft", False)
        for conversation in patient["conversations"]
        for message in conversation["messages"]
    )

    biller = await _bootstrap(client, "biller")
    assert biller["patient"] is None
    assert biller["intake"] is None
    assert biller["commandCenter"] is None
    assert biller["schedule"] == []
    assert biller["encounter"] is None
    assert biller["pathology"] is None
    assert biller["conversations"] == []
    assert biller["claims"] and all(item["status"] == "denied" for item in biller["claims"])
    assert len(biller["claims"]) == 2
    assert biller["claims"][0]["denial"]["status"] == "open"
    actionable_denials = [
        item
        for item in biller["claims"]
        if (item.get("denial") or {}).get("status") == "open"
    ]
    assert len(actionable_denials) == 1
    assert actionable_denials[0]["denial"]["assignedTaskId"]
    assert biller["financialContext"]["estimate"]["patientResponsibility"] == 85.0
    biller_metrics = {item["id"]: item for item in biller["metrics"]}
    assert set(biller_metrics) == {
        "accept",
        "denial",
        "ar",
        "revenue",
    }
    assert biller_metrics["accept"]["score"] == 90
    assert biller_metrics["accept"]["tone"] == "info"

    owner = await _bootstrap(client, "owner")
    assert owner["intake"] is None
    assert owner["patient"] is None
    assert owner["schedule"] == []
    assert owner["encounter"] is None
    assert owner["pathology"] is None
    assert owner["conversations"] == []
    assert owner["claims"] == []
    assert owner["financialContext"] is None
    assert owner["metrics"]


async def test_owner_is_not_superuser_and_presenter_delegation_is_explicit(client) -> None:
    login = await client.post("/api/auth/demo/session", json={"persona": "owner"})
    assert login.status_code == 200
    assert login.json()["session"]["presenter"] is False
    assert (await client.get("/api/demo/health")).status_code == 403
    ids = canonical_ids()
    note_edit = await client.patch(
        f"/api/notes/{ids['sarah_note_id']}",
        json={"content": "forbidden", "structuredContent": {}, "reason": "forbidden"},
    )
    assert note_edit.status_code == 403
    pathology_review = await client.post(f"/api/pathology/results/{uuid.uuid4()}/review", json={})
    assert pathology_review.status_code == 403
    claim_mutation = await client.post(
        f"/api/claims/{uuid.uuid4()}/correct-and-resubmit",
        json={"appealBody": "x", "correction": "x"},
    )
    assert claim_mutation.status_code == 403

    delegated = await client.post(
        "/api/auth/demo/session",
        json={"persona": "owner", "presenterCode": "test-presenter-code"},
    )
    assert delegated.status_code == 200
    assert delegated.json()["session"]["presenter"] is True
    health = await client.get("/api/demo/health")
    assert health.status_code == 200
    expected_database = "sqlite_local" if engine.dialect.name == "sqlite" else "neon_postgres"
    expected_database_service = (
        "SQLite local source of truth"
        if engine.dialect.name == "sqlite"
        else "Neon Postgres source of truth"
    )
    assert health.json()["database"] == expected_database
    assert health.json()["aiProvider"] == "local_deterministic_fallback"
    presenter_bootstrap = (await client.get("/api/demo/bootstrap")).json()
    assert presenter_bootstrap["triggerIds"]["pathologyResultId"] is None
    assert presenter_bootstrap["triggerIds"]["claimId"] is None
    assert presenter_bootstrap["patient"]["name"] == "Sarah Mitchell"
    assert presenter_bootstrap["claims"][0]["denial"]["status"] == "open"
    assert any(
        (item.get("denial") or {}).get("status") == "open"
        for item in presenter_bootstrap["claims"]
    )
    assert any(
        item["service"] == expected_database_service for item in presenter_bootstrap["health"]
    )
    switched = await client.post("/api/auth/switch", json={"persona": "provider"})
    assert switched.status_code == 200
    assert switched.json()["session"]["presenter"] is True
    assert switched.json()["session"]["isPresenter"] is True


async def test_bootstrap_uses_membership_roles_not_persona_label(client) -> None:
    async with SessionLocal() as session:
        provider_user = await session.scalar(select(User).where(User.persona_key == "provider"))
        membership = await session.scalar(
            select(Membership).where(
                Membership.organization_id == provider_user.organization_id,
                Membership.user_id == provider_user.id,
            )
        )
        original_role_id = membership.role_id
        biller_role_id = await session.scalar(select(Role.id).where(Role.name == "biller"))
        membership.role_id = biller_role_id
        await session.commit()
    try:
        response = await client.get(
            "/api/demo/bootstrap", headers={"X-Demo-Persona": "provider"}
        )
        assert response.status_code == 200, response.text
        workspace = response.json()
        assert workspace["session"]["persona"] == "provider"
        assert workspace["session"]["roles"] == ["biller"]
        assert workspace["patient"] is None
        assert workspace["encounter"] is None
        assert workspace["pathology"] is None
        assert workspace["claims"]
        forbidden = await client.patch(
            f"/api/notes/{canonical_ids()['sarah_note_id']}",
            headers={"X-Demo-Persona": "provider"},
            json={"content": "forbidden", "structuredContent": {}, "reason": "forbidden"},
        )
        assert forbidden.status_code == 403
    finally:
        async with SessionLocal() as session:
            membership = await session.scalar(
                select(Membership).where(Membership.user_id == provider_user.id)
            )
            membership.role_id = original_role_id
            await session.commit()


async def test_public_personas_never_disclose_another_tenant(client) -> None:
    outsider_org_id = uuid.uuid4()
    outsider_user_id = uuid.uuid4()
    async with SessionLocal() as session:
        patient_role = await session.scalar(select(Role).where(Role.name == "patient"))
        outsider = Organization(
            id=outsider_org_id,
            name="Outside Dermatology",
            slug="outside-dermatology",
            timezone="America/Chicago",
            demo_mode=True,
        )
        user = User(
            id=outsider_user_id,
            organization_id=outsider_org_id,
            email="outsider@example.test",
            display_name="Outside Tenant Person",
            persona_key="outside-persona",
            is_active=True,
            is_presenter=False,
        )
        session.add(outsider)
        await session.flush()
        session.add(user)
        await session.flush()
        session.add(
            Membership(
                organization_id=outsider_org_id,
                user_id=outsider_user_id,
                role_id=patient_role.id,
            )
        )
        await session.commit()
    try:
        response = await client.get("/api/personas")
        assert response.status_code == 200
        names = {item["name"] for item in response.json()["personas"]}
        assert "Outside Tenant Person" not in names
        forged = await client.get(
            "/api/demo/bootstrap", headers={"X-Demo-Persona": "outside-persona"}
        )
        assert forged.status_code == 401
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Organization).where(Organization.id == outsider_org_id))
            await session.commit()
