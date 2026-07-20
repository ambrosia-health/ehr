from __future__ import annotations

import uuid

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import SessionLocal, get_session
from app.main import app
from app.models import Denial, Patient, User
from app.seed import canonical_ids

EXPECTED_ENDPOINTS = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/personas"),
    ("POST", "/api/auth/demo/session"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/switch"),
    ("GET", "/api/patients/{patient_id}"),
    ("GET", "/api/appointments/availability"),
    ("POST", "/api/intake/submissions"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/encounters/{encounter_id}"),
    ("POST", "/api/encounters/{encounter_id}/ambient"),
    ("PATCH", "/api/notes/{note_id}"),
    ("POST", "/api/notes/{note_id}/amendments"),
    ("GET", "/api/lesions/{lesion_id}"),
    ("POST", "/api/lesions/observations"),
    ("POST", "/api/encounters/{encounter_id}/complete"),
    ("GET", "/api/pathology/results"),
    ("POST", "/api/pathology/results/{result_id}/review"),
    ("GET", "/api/messages"),
    ("POST", "/api/conversations/{conversation_id}/read"),
    ("POST", "/api/conversations/{conversation_id}/messages"),
    ("POST", "/api/messages/draft"),
    ("GET", "/api/rcm"),
    ("POST", "/api/rcm/claims/{claim_id}/advance"),
    ("POST", "/api/rcm/appeals"),
    ("POST", "/api/claims/{claim_id}/correct-and-resubmit"),
    ("GET", "/api/mso/metrics"),
    ("POST", "/api/ai/{capability}"),
    ("GET", "/api/demo/bootstrap"),
    ("GET", "/api/demo/health"),
    ("POST", "/api/demo/reset"),
    ("POST", "/api/demo/advance-time"),
    ("POST", "/api/demo/triggers/pathology"),
    ("POST", "/api/demo/triggers/claim-response"),
    ("GET", "/api/demo/learning/episodes"),
    ("GET", "/api/demo/learning/console"),
    ("GET", "/api/demo/learning/episodes/{episode_id}/trajectory"),
    ("POST", "/api/demo/learning/environment-runs"),
    ("GET", "/api/demo/learning/environment-runs/{run_id}"),
    ("GET", "/api/demo/learning/environment-runs/{run_id}/history"),
    ("POST", "/api/demo/learning/environment-runs/{run_id}/steps"),
    ("POST", "/api/demo/learning/environment-runs/{run_id}/model-step"),
    ("GET", "/api/demo/learning/dataset-manifests"),
}

PUBLIC_ENDPOINTS = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/personas"),
    ("POST", "/api/auth/demo/session"),
    ("POST", "/api/auth/logout"),
}


def _headers(persona: str) -> dict[str, str]:
    return {"X-Demo-Persona": persona}


def _concrete_path(path: str) -> str:
    ids = canonical_ids()
    replacements = {
        "{patient_id}": ids["sarah_patient_id"],
        "{encounter_id}": ids["sarah_encounter_id"],
        "{note_id}": ids["sarah_note_id"],
        "{lesion_id}": ids["sarah_lesion_id"],
        "{result_id}": uuid.uuid4(),
        "{conversation_id}": ids["sarah_conversation_id"],
        "{claim_id}": ids["sarah_claim_id"],
        "{capability}": "chart_summary",
        "{episode_id}": ids["learning_episode_id"],
        "{run_id}": uuid.uuid4(),
    }
    for marker, value in replacements.items():
        path = path.replace(marker, str(value))
    return path


def _observation_body(*, include_lesion: bool) -> dict[str, object]:
    body: dict[str, object] = {
        "encounterId": str(canonical_ids()["sarah_encounter_id"]),
        "site": "Left posterior shoulder",
        "view": "posterior",
        "lengthMm": 7.2,
        "widthMm": 5.1,
        "morphology": "asymmetric papule",
        "border": "irregular",
        "pigmentation": "variegated brown-black",
        "changeOverTime": "larger and darker over four months",
        "symptoms": ["itching"],
        "comparison": "Increased from prior image",
        "assessment": "Biopsy recommended",
    }
    if include_lesion:
        body["lesionId"] = str(canonical_ids()["sarah_lesion_id"])
    return body


def test_route_inventory_is_explicit_and_exhaustive() -> None:
    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert actual == EXPECTED_ENDPOINTS
    assert PUBLIC_ENDPOINTS < EXPECTED_ENDPOINTS


async def test_every_protected_endpoint_rejects_anonymous_requests(client) -> None:
    failures: list[tuple[str, str, int, str]] = []
    for method, path in sorted(EXPECTED_ENDPOINTS - PUBLIC_ENDPOINTS):
        response = await client.request(method, _concrete_path(path), json={})
        if response.status_code != 401:
            failures.append((method, path, response.status_code, response.text[:200]))
    assert failures == []


async def test_public_auth_discovery_health_docs_and_security_headers(client) -> None:
    for path in ("/", "/api/health", "/api/personas"):
        response = await client.get(path, headers={"X-Request-ID": "endpoint-contract"})
        assert response.status_code == 200, (path, response.text)
        if path.startswith("/api"):
            assert response.headers["cache-control"] == "private, no-store, max-age=0"
            assert response.headers["pragma"] == "no-cache"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["x-request-id"] == "endpoint-contract"

    for path in ("/api/docs", "/api/openapi.json"):
        response = await client.get(path)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "private, no-store, max-age=0"

    login = await client.post("/api/auth/demo/session", json={"persona": "patient"})
    assert login.status_code == 200, login.text
    assert "HttpOnly" in login.headers["set-cookie"]
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["session"]["persona"] == "patient"
    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.parametrize(
    ("path", "persona", "required_key"),
    [
        (f"/api/patients/{canonical_ids()['sarah_patient_id']}", "patient", "id"),
        ("/api/appointments/availability", "patient", "slots"),
        ("/api/dashboard", "provider", "schedule"),
        (f"/api/encounters/{canonical_ids()['sarah_encounter_id']}", "provider", "id"),
        (f"/api/lesions/{canonical_ids()['sarah_lesion_id']}", "patient", "lesion"),
        ("/api/pathology/results", "clinical", "results"),
        ("/api/messages", "patient", "conversations"),
        ("/api/rcm", "biller", "claims"),
        ("/api/mso/metrics", "owner", "patientSatisfactionIndicators"),
        ("/api/demo/bootstrap", "provider", "session"),
    ],
)
async def test_every_read_handler_has_a_direct_success_contract(
    client, path: str, persona: str, required_key: str
) -> None:
    response = await client.get(path, headers=_headers(persona))
    assert response.status_code == 200, (path, response.text)
    assert required_key in response.json()


async def test_presenter_health_has_a_direct_success_contract(presenter_client) -> None:
    response = await presenter_client.get("/api/demo/health")
    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"healthy", "degraded"}


@pytest.mark.parametrize(
    ("path", "persona", "body"),
    [
        ("/api/dashboard", "patient", None),
        (f"/api/patients/{canonical_ids()['sarah_patient_id']}", "owner", None),
        (
            f"/api/encounters/{canonical_ids()['sarah_encounter_id']}/ambient",
            "clinical",
            {"transcript": "Synthetic encounter transcript"},
        ),
        ("/api/rcm", "provider", None),
        ("/api/mso/metrics", "biller", None),
        (
            "/api/ai/chart_summary",
            "owner",
            {
                "patientId": str(canonical_ids()["sarah_patient_id"]),
                "context": {"patientName": "Sarah Mitchell"},
            },
        ),
        ("/api/demo/health", "provider", None),
    ],
)
async def test_role_boundaries_reject_valid_out_of_scope_requests(
    client, path: str, persona: str, body: dict | None
) -> None:
    method = "POST" if body is not None else "GET"
    response = await client.request(method, path, headers=_headers(persona), json=body)
    assert response.status_code == 403, response.text


async def test_uncovered_mutation_handlers_persist_and_return_contracts(client) -> None:
    ids = canonical_ids()
    ambient = await client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/ambient",
        headers=_headers("provider"),
        json={"transcript": "Synthetic transcript: changing shoulder lesion; plan shave biopsy."},
    )
    assert ambient.status_code == 200, ambient.text
    assert ambient.json()["requiresApproval"] is True

    observation = await client.post(
        "/api/lesions/observations",
        headers=_headers("provider"),
        json=_observation_body(include_lesion=True),
    )
    assert observation.status_code == 200, observation.text
    assert observation.json()["observationId"]

    conversation_message = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_headers("provider"),
        json={"body": "Please continue the approved wound-care instructions."},
    )
    assert conversation_message.status_code == 200, conversation_message.text
    assert conversation_message.json()["status"] == "sent"

    drafted = await client.post(
        "/api/messages/draft",
        headers=_headers("provider"),
        json={
            "conversationId": str(ids["sarah_conversation_id"]),
            "question": "Can I replace the bandage tomorrow?",
        },
    )
    assert drafted.status_code == 200, drafted.text
    assert drafted.json()["draft"]["status"] == "proposed"

    async with SessionLocal() as session:
        denial_id = await session.scalar(select(Denial.id).where(Denial.status == "open"))
    assert denial_id
    appeal = await client.post(
        "/api/rcm/appeals",
        headers=_headers("biller"),
        json={"denialId": str(denial_id)},
    )
    assert appeal.status_code == 200, appeal.text
    assert appeal.json()["appeal"]["status"] == "draft"


@pytest.mark.parametrize(
    ("capability", "persona", "patient_bound"),
    [
        ("chart_summary", "provider", True),
        ("ambient_note", "provider", True),
        ("coding_suggestions", "provider", True),
        ("patient_message", "clinical", True),
        ("pathology_summary", "provider", True),
        ("denial_recommendation", "biller", False),
        ("document_extraction", "provider", False),
    ],
)
async def test_every_ai_capability_endpoint_has_a_validated_fallback_contract(
    client, capability: str, persona: str, patient_bound: bool
) -> None:
    payload: dict[str, object] = {
        "context": {
            "patientName": "Sarah Mitchell",
            "documentType": "insurance_card",
            "uncertain": capability == "patient_message",
        }
    }
    if patient_bound:
        payload["patientId"] = str(canonical_ids()["sarah_patient_id"])
    response = await client.post(f"/api/ai/{capability}", headers=_headers(persona), json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["requiresApproval"] is True
    assert data["run"]["fallbackUsed"] is True
    assert data["run"]["provider"] == "deterministic_fallback"
    assert data["output"]


async def test_demo_reset_endpoint_is_presenter_gated_and_restores_state(
    client, presenter_client
) -> None:
    assert (await client.post("/api/demo/reset", headers=_headers("owner"))).status_code == 403
    reset = await presenter_client.post("/api/demo/reset")
    assert reset.status_code == 200, reset.text
    assert reset.json()["message"] == "Canonical synthetic scenario restored"


async def test_staging_reset_requires_an_explicit_runtime_opt_in(presenter_client) -> None:
    staging = Settings(
        _env_file=None,
        APP_ENV="staging",
        DATABASE_URL="postgresql://localhost/ambrosia",
        AUTH_SESSION_SECRET="test-session-secret-not-for-production",
        DEMO_PRESENTER_SECRET="test-presenter-code",
        SESSION_COOKIE_SECURE=True,
        ALLOW_SYNTHETIC_DEMO_RESET=False,
    )
    app.dependency_overrides[get_settings] = lambda: staging
    try:
        response = await presenter_client.post("/api/demo/reset")
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == 403


async def test_validation_method_and_unknown_route_failures_never_become_500s(
    client, presenter_client
) -> None:
    ids = canonical_ids()
    malformed = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers={**_headers("patient"), "Content-Type": "application/json"},
        content="{",
    )
    assert malformed.status_code == 422
    non_object = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_headers("patient"),
        json=["not", "an", "object"],
    )
    assert non_object.status_code == 422
    for body in (
        {"body": "   "},
        {"body": "valid", "unexpected": True},
        {"body": "x" * 5_001},
        {"body": "valid", "approveAiDraftId": "not-a-uuid"},
    ):
        response = await client.post(
            f"/api/conversations/{ids['sarah_conversation_id']}/messages",
            headers=_headers("provider"),
            json=body,
        )
        assert response.status_code == 422, response.text

    cases = [
        await client.post("/api/auth/demo/session", json={"persona": "patient", "extra": True}),
        await client.get("/api/patients/not-a-uuid", headers=_headers("provider")),
        await client.post(
            f"/api/encounters/{ids['sarah_encounter_id']}/ambient",
            headers=_headers("provider"),
            json={"transcript": "x" * 100_001},
        ),
        await client.post(
            "/api/ai/chart_summary",
            headers=_headers("provider"),
            json={"context": {"payload": "x" * 64_001}, "patientId": str(ids["sarah_patient_id"])},
        ),
        await client.post(
            "/api/ai/chart_summary",
            headers=_headers("provider"),
            json={"context": {}},
        ),
        await client.post("/api/ai/unknown", headers=_headers("provider"), json={"context": {}}),
        await presenter_client.post(
            "/api/demo/advance-time",
            json={"hours": 721},
        ),
        await client.post("/api/health"),
        await client.get("/api/does-not-exist"),
    ]
    assert [response.status_code for response in cases] == [
        422,
        422,
        422,
        413,
        422,
        404,
        422,
        405,
        404,
    ]
    assert all(response.status_code < 500 for response in cases)


async def test_every_route_rejects_the_wrong_method_with_allow_header(client) -> None:
    failures: list[tuple[str, str, int, str | None]] = []
    for _method, path in sorted(EXPECTED_ENDPOINTS):
        wrong_method = "DELETE"
        response = await client.request(wrong_method, _concrete_path(path), json={})
        allowed = response.headers.get("allow")
        if response.status_code != 405 or not allowed:
            failures.append((wrong_method, path, response.status_code, allowed))
    assert failures == []


async def test_openapi_exactly_documents_the_supported_surface_and_cookie_auth(client) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    documented = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PATCH"}
    }
    assert documented == EXPECTED_ENDPOINTS
    assert schema["components"]["securitySchemes"]["APIKeyCookie"] == {
        "type": "apiKey",
        "description": "Signed Ambrosia session cookie",
        "in": "cookie",
        "name": get_settings().session_cookie_name,
    }
    for method, path in EXPECTED_ENDPOINTS - PUBLIC_ENDPOINTS:
        operation = schema["paths"][path][method.lower()]
        assert {"APIKeyCookie": []} in operation.get("security", []), (method, path)
    for method, path in PUBLIC_ENDPOINTS:
        assert "security" not in schema["paths"][path][method.lower()], (method, path)
    request_schemas = {
        name: value
        for name, value in schema["components"]["schemas"].items()
        if name.endswith("Request")
    }
    assert request_schemas
    assert all(item.get("additionalProperties") is False for item in request_schemas.values())


async def test_api_body_limit_covers_declared_and_streamed_requests(client) -> None:
    declared = await client.post(
        "/api/auth/demo/session",
        headers={"Content-Length": str(256 * 1024 + 1)},
        content=b"{}",
    )
    assert declared.status_code == 413
    assert declared.headers["cache-control"] == "private, no-store, max-age=0"

    async def oversized_chunks():
        yield b"{" + (b" " * (256 * 1024)) + b"}"

    streamed = await client.post(
        "/api/auth/demo/session",
        headers={"Content-Type": "application/json"},
        content=oversized_chunks(),
    )
    assert streamed.status_code == 413


async def test_postgres_unsafe_nul_strings_are_rejected_before_persistence(client) -> None:
    response = await client.post(
        f"/api/conversations/{canonical_ids()['sarah_conversation_id']}/messages",
        headers=_headers("patient"),
        json={"body": "unsafe\u0000message"},
    )
    assert response.status_code == 422


async def test_health_returns_503_when_the_database_is_unavailable(client) -> None:
    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    try:
        response = await client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"
    assert response.json()["aiModel"] == "gpt-5.6-luna"
    assert response.json()["aiReasoningEffort"] == "low"


PERSONAS = {"patient", "provider", "clinical", "biller", "owner"}
ROLE_SCOPED_ENDPOINTS = {
    ("GET", f"/api/patients/{canonical_ids()['sarah_patient_id']}"): {
        "patient", "provider", "clinical"
    },
    ("GET", "/api/appointments/availability"): {"patient", "provider", "clinical"},
    ("POST", "/api/intake/submissions"): {"patient", "provider", "clinical"},
    ("GET", "/api/dashboard"): {"provider", "clinical", "owner"},
    ("GET", f"/api/encounters/{canonical_ids()['sarah_encounter_id']}"): {
        "provider", "clinical"
    },
    ("POST", f"/api/encounters/{canonical_ids()['sarah_encounter_id']}/ambient"): {
        "provider"
    },
    ("PATCH", f"/api/notes/{canonical_ids()['sarah_note_id']}"): {"provider"},
    ("POST", f"/api/notes/{canonical_ids()['sarah_note_id']}/amendments"): {"provider"},
    ("GET", f"/api/lesions/{canonical_ids()['sarah_lesion_id']}"): {
        "patient", "provider", "clinical"
    },
    ("POST", "/api/lesions/observations"): {"provider", "clinical"},
    ("POST", f"/api/encounters/{canonical_ids()['sarah_encounter_id']}/complete"): {
        "provider"
    },
    ("GET", "/api/pathology/results"): {"provider", "clinical"},
    ("POST", f"/api/pathology/results/{uuid.uuid4()}/review"): {"provider"},
    ("GET", "/api/messages"): {"patient", "provider", "clinical"},
    ("POST", f"/api/conversations/{canonical_ids()['sarah_conversation_id']}/read"): {
        "patient", "provider", "clinical"
    },
    ("POST", f"/api/conversations/{canonical_ids()['sarah_conversation_id']}/messages"): {
        "patient", "provider", "clinical"
    },
    ("POST", "/api/messages/draft"): {"provider", "clinical"},
    ("GET", "/api/rcm"): {"biller"},
    ("POST", f"/api/rcm/claims/{canonical_ids()['sarah_claim_id']}/advance"): {"biller"},
    ("POST", "/api/rcm/appeals"): {"biller"},
    ("POST", f"/api/claims/{canonical_ids()['sarah_claim_id']}/correct-and-resubmit"): {
        "biller"
    },
    ("GET", "/api/mso/metrics"): {"owner"},
    ("POST", "/api/ai/chart_summary"): {"provider", "clinical"},
}


async def test_every_role_scoped_route_rejects_every_disallowed_persona(client) -> None:
    failures: list[tuple[str, str, str, int]] = []
    for (method, path), allowed in ROLE_SCOPED_ENDPOINTS.items():
        for persona in PERSONAS - allowed:
            response = await client.request(method, path, headers=_headers(persona), json={})
            if response.status_code != 403:
                failures.append((method, path, persona, response.status_code))
    assert failures == []


async def test_presenter_routes_reject_every_ordinary_persona(client) -> None:
    paths = [
        ("POST", "/api/auth/switch"),
        ("GET", "/api/demo/health"),
        ("POST", "/api/demo/reset"),
        ("POST", "/api/demo/advance-time"),
        ("POST", "/api/demo/triggers/pathology"),
        ("POST", "/api/demo/triggers/claim-response"),
        ("GET", "/api/demo/learning/episodes"),
        ("GET", "/api/demo/learning/console"),
        (
            "GET",
            f"/api/demo/learning/episodes/{canonical_ids()['learning_episode_id']}/trajectory",
        ),
        ("POST", "/api/demo/learning/environment-runs"),
        ("GET", f"/api/demo/learning/environment-runs/{uuid.uuid4()}"),
        ("GET", f"/api/demo/learning/environment-runs/{uuid.uuid4()}/history"),
        ("POST", f"/api/demo/learning/environment-runs/{uuid.uuid4()}/steps"),
        ("POST", f"/api/demo/learning/environment-runs/{uuid.uuid4()}/model-step"),
        ("GET", "/api/demo/learning/dataset-manifests"),
    ]
    failures = []
    for method, path in paths:
        for persona in PERSONAS:
            response = await client.request(method, path, headers=_headers(persona), json={})
            if response.status_code != 403:
                failures.append((method, path, persona, response.status_code))
    assert failures == []


async def test_real_session_cookie_rejects_tampering_and_deactivated_users(client) -> None:
    cookie_name = get_settings().session_cookie_name
    login = await client.post("/api/auth/demo/session", json={"persona": "patient"})
    assert login.status_code == 200
    token = client.cookies[cookie_name]

    client.cookies.set(cookie_name, f"{token}tampered")
    assert (await client.get("/api/auth/me")).status_code == 401

    client.cookies.set(cookie_name, token)
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.persona_key == "patient"))
        assert user
        user.is_active = False
        await session.commit()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_patient_cannot_cross_patient_record_boundaries(client) -> None:
    async with SessionLocal() as session:
        other_patient_id = await session.scalar(
            select(Patient.id).where(Patient.id != canonical_ids()["sarah_patient_id"])
        )
    assert other_patient_id
    response = await client.get(
        f"/api/patients/{other_patient_id}", headers=_headers("patient")
    )
    assert response.status_code == 403
