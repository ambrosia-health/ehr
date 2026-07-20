from __future__ import annotations

import json
import re
import uuid

import pytest
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    ActionAttempt,
    AIRun,
    DomainEvent,
    EnvironmentRun,
    EnvironmentStep,
    ObservationManifest,
)
from app.security import Principal, get_principal
from app.seed import canonical_ids

LEARNING_ROOT = "/api/demo/learning"
HAPPY_PATH_ACTIONS = [
    "review_intake",
    "complete_encounter_review",
    "review_pathology",
    "notify_patient",
    "submit_claim",
    "correct_and_resubmit_claim",
    "close_episode",
]


def _run_body(idempotency_key: str, *, seed: int = 17) -> dict[str, object]:
    return {
        "episodeDefinitionId": str(canonical_ids()["learning_episode_definition_id"]),
        "actorRole": "environment_agent",
        "seed": seed,
        "idempotencyKey": idempotency_key,
    }


def _step_body(
    sequence: int,
    action_type: str,
    idempotency_key: str,
) -> dict[str, object]:
    return {
        "expectedSequence": sequence,
        "idempotencyKey": idempotency_key,
        "action": {"type": action_type},
    }


def _observed_timing(response) -> tuple[float, int]:
    timing = response.headers.get("server-timing", "")
    duration = re.search(r"app;dur=([\d.]+)", timing)
    queries = re.search(r'desc="(\d+) queries"', timing)
    assert duration and queries, timing
    return float(duration.group(1)), int(queries.group(1))


async def _create_run(presenter_client, key: str, *, seed: int = 17) -> dict:
    response = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs",
        json=_run_body(key, seed=seed),
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"{LEARNING_ROOT}/episodes", None),
        ("POST", f"{LEARNING_ROOT}/environment-runs", _run_body("ordinary-owner-run")),
        ("GET", f"{LEARNING_ROOT}/environment-runs/{uuid.uuid4()}", None),
        (
            "POST",
            f"{LEARNING_ROOT}/environment-runs/{uuid.uuid4()}/steps",
            _step_body(1, "review_intake", "ordinary-owner-step"),
        ),
        ("GET", f"{LEARNING_ROOT}/dataset-manifests", None),
    ],
)
async def test_learning_routes_require_presenter_delegation(
    client,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    response = await client.request(
        method,
        path,
        headers={"X-Demo-Persona": "owner"},
        json=body,
    )
    assert response.status_code == 403, response.text


async def test_presenter_environment_actions_are_attributed_to_the_presenter(client) -> None:
    login = await client.post(
        "/api/auth/demo/session",
        json={"persona": "patient", "presenterCode": "test-presenter-code"},
    )
    assert login.status_code == 200, login.text
    session_payload = login.json()["session"]
    presenter_id = uuid.UUID(session_payload["presenterActorId"])
    persona_id = uuid.UUID(session_payload["userId"])
    assert presenter_id != persona_id

    created = await client.post(
        f"{LEARNING_ROOT}/environment-runs",
        json=_run_body("delegated-presenter-attribution"),
    )
    assert created.status_code == 200, created.text
    run_id = uuid.UUID(created.json()["run"]["id"])
    stepped = await client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(1, "review_intake", "delegated-presenter-step"),
    )
    assert stepped.status_code == 200, stepped.text
    model_step = await client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json={
            "expectedSequence": 2,
            "idempotencyKey": "delegated-presenter-model-step",
        },
    )
    assert model_step.status_code == 200, model_step.text

    async with SessionLocal() as session:
        run = await session.get(EnvironmentRun, run_id)
        created_event = await session.scalar(
            select(DomainEvent).where(
                DomainEvent.organization_id == canonical_ids()["organization_id"],
                DomainEvent.aggregate_id == run_id,
                DomainEvent.event_type == "environment.run.created",
            )
        )
        actions = list(
            await session.scalars(
            select(ActionAttempt)
            .join(EnvironmentStep, EnvironmentStep.action_attempt_id == ActionAttempt.id)
            .where(EnvironmentStep.environment_run_id == run_id)
                .order_by(EnvironmentStep.step_number)
            )
        )
        model_ai_run = await session.get(AIRun, actions[-1].ai_run_id)

    assert run is not None
    assert run.config_json["requestedByUserId"] == str(presenter_id)
    assert created_event is not None and created_event.actor_user_id == presenter_id
    assert len(actions) == 2
    assert all(action.actor_user_id == presenter_id for action in actions)
    assert model_ai_run is not None and model_ai_run.requested_by_user_id == presenter_id


async def test_presenter_can_discover_create_and_get_an_isolated_run(presenter_client) -> None:
    catalog = await presenter_client.get(f"{LEARNING_ROOT}/episodes")
    assert catalog.status_code == 200, catalog.text
    episodes = catalog.json()["episodes"]
    assert len(episodes) == 1
    assert episodes[0]["id"] == str(canonical_ids()["learning_episode_definition_id"])
    assert episodes[0]["slug"] == "longitudinal-dermatology-operations"
    assert episodes[0]["actionTypes"] == [
        "review_intake",
        "complete_encounter_review",
        "review_pathology",
        "notify_patient",
        "submit_claim",
        "correct_and_resubmit_claim",
        "close_episode",
        "request_missing_information",
        "escalate",
    ]

    created = await _create_run(presenter_client, "create-get-run", seed=31)
    assert set(created) == {
        "run",
        "observation",
        "allowedActions",
        "totalReward",
        "hardViolationCount",
        "latestStep",
    }
    assert created["run"] == {
        "id": created["run"]["id"],
        "status": "running",
        "mode": "simulation",
        "actorRole": "environment_agent",
        "seed": 31,
        "sequence": 0,
        "stateVersion": 1,
        "startedAt": created["run"]["startedAt"],
        "endedAt": None,
        "terminationReason": None,
        "scenario": {
            "slug": "longitudinal-dermatology-operations",
            "version": 1,
            "simulatorVersions": {
                "environment": "ambrosia-healthcare-ops-2026.1",
                "patient": "deterministic-synthetic-patient-2026.1",
                "payer": "deterministic-synthetic-payer-2026.1",
            },
        },
    }
    assert created["observation"]["stage"] == "intake_review"
    assert created["allowedActions"] == [
        "escalate",
        "request_missing_information",
        "review_intake",
    ]
    assert created["latestStep"] is None

    fetched = await presenter_client.get(f"{LEARNING_ROOT}/environment-runs/{created['run']['id']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == created


async def test_run_and_step_idempotency_retries_and_conflicts(presenter_client) -> None:
    body = _run_body("idempotent-run", seed=23)
    first = await presenter_client.post(f"{LEARNING_ROOT}/environment-runs", json=body)
    retry = await presenter_client.post(f"{LEARNING_ROOT}/environment-runs", json=body)
    assert first.status_code == retry.status_code == 200
    assert retry.json()["run"]["id"] == first.json()["run"]["id"]

    conflict_body = {**body, "seed": 24}
    conflict = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs",
        json=conflict_body,
    )
    assert conflict.status_code == 409
    assert "idempotency key" in conflict.json()["detail"]

    run_id = first.json()["run"]["id"]
    step_body = _step_body(1, "review_intake", "idempotent-step")
    first_step = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=step_body,
    )
    step_retry = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=step_body,
    )
    assert first_step.status_code == step_retry.status_code == 200
    assert step_retry.json()["latestStep"] == first_step.json()["latestStep"]
    assert step_retry.json()["run"]["sequence"] == 1

    step_conflict = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(1, "escalate", "idempotent-step"),
    )
    assert step_conflict.status_code == 409
    assert "idempotency key" in step_conflict.json()["detail"]

    second_step = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(2, "complete_encounter_review", "idempotent-step-2"),
    )
    late_retry = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=step_body,
    )
    assert second_step.status_code == late_retry.status_code == 200
    assert late_retry.json() == first_step.json()

    async with SessionLocal() as session:
        run_count = await session.scalar(
            select(func.count(EnvironmentRun.id)).where(EnvironmentRun.id == uuid.UUID(run_id))
        )
        step_count = await session.scalar(
            select(func.count(EnvironmentStep.id)).where(
                EnvironmentStep.environment_run_id == uuid.UUID(run_id)
            )
        )
        action_count = await session.scalar(
            select(func.count(ActionAttempt.id))
            .join(
                EnvironmentStep,
                EnvironmentStep.action_attempt_id == ActionAttempt.id,
            )
            .where(EnvironmentStep.environment_run_id == uuid.UUID(run_id))
        )
    assert run_count == 1
    assert step_count == action_count == 2


async def test_invalid_action_gets_server_owned_reward_and_sequence(presenter_client) -> None:
    created = await _create_run(presenter_client, "invalid-action-run")
    run_id = created["run"]["id"]

    rejected = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(1, "close_episode", "invalid-action-step"),
    )
    assert rejected.status_code == 200, rejected.text
    state = rejected.json()
    assert state["run"]["status"] == "running"
    assert state["run"]["sequence"] == 1
    assert state["observation"]["stage"] == "intake_review"
    assert state["hardViolationCount"] == 1
    assert state["latestStep"] == {
        "sequence": 1,
        "actionType": "close_episode",
        "actionStatus": "rejected",
        "supportKind": "simulated",
        "terminated": False,
        "reward": {"policyCompliance": -1.0, "safety": -1.0},
        "hardViolations": ["action_not_allowed_in_state"],
    }

    advanced = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(2, "review_intake", "valid-after-rejection"),
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["run"]["sequence"] == 2
    assert advanced.json()["observation"]["stage"] == "encounter_review"


async def test_sequential_happy_path_reaches_a_terminal_episode(presenter_client) -> None:
    created = await _create_run(presenter_client, "terminal-happy-path", seed=42)
    run_id = created["run"]["id"]

    state = created
    for sequence, action_type in enumerate(HAPPY_PATH_ACTIONS, 1):
        response = await presenter_client.post(
            f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
            json=_step_body(sequence, action_type, f"happy-step-{sequence}"),
        )
        assert response.status_code == 200, (sequence, action_type, response.text)
        state = response.json()
        assert state["run"]["sequence"] == sequence
        assert state["latestStep"]["actionType"] == action_type
        assert state["latestStep"]["actionStatus"] == "succeeded"

    assert state["run"]["status"] == "completed"
    assert state["run"]["terminationReason"] == "episode_complete"
    assert state["observation"] == {
        "stage": "closed",
        "facts": {"allRequiredWorkClosed": True},
        "outstandingWork": [],
        "supportKind": "simulated",
    }
    assert state["allowedActions"] == []
    assert state["hardViolationCount"] == 0
    assert state["latestStep"]["terminated"] is True
    assert state["latestStep"]["hardViolations"] == []
    assert state["totalReward"]["safety"] == 5.0
    assert state["totalReward"]["taskCompletion"] == 6.5

    after_terminal = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(8, "close_episode", "after-terminal"),
    )
    assert after_terminal.status_code == 409
    assert after_terminal.json()["detail"] == "Environment run is terminal"


async def test_max_step_limit_terminates_and_persists_final_observation(
    presenter_client,
) -> None:
    created = await _create_run(presenter_client, "max-step-termination")
    run_id = uuid.UUID(created["run"]["id"])

    async with SessionLocal() as session:
        run = await session.get(EnvironmentRun, run_id)
        assert run is not None
        episode_id = run.episode_instance_id
        run.config_json = {**run.config_json, "maxSteps": 1}
        await session.commit()

    response = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(1, "review_intake", "max-step-one"),
    )
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["run"]["status"] == "completed"
    assert state["run"]["sequence"] == 1
    assert state["run"]["terminationReason"] == "max_steps_reached"
    assert state["latestStep"]["terminated"] is True
    assert state["observation"]["stage"] == "encounter_review"
    assert state["allowedActions"] == []

    async with SessionLocal() as session:
        manifests = list(
            await session.scalars(
                select(ObservationManifest)
                .where(ObservationManifest.episode_instance_id == episode_id)
                .order_by(ObservationManifest.sequence)
            )
        )
    assert [item.sequence for item in manifests] == [1, 2]
    assert manifests[-1].synthetic_snapshot_json == state["observation"]


async def test_cross_tenant_run_access_and_mutation_return_not_found(presenter_client) -> None:
    created = await _create_run(presenter_client, "tenant-isolation-run")
    run_id = created["run"]["id"]
    outsider_user_id = uuid.uuid4()

    async def outsider_principal() -> Principal:
        return Principal(
            user_id=outsider_user_id,
            organization_id=uuid.uuid4(),
            display_name="Synthetic outsider",
            persona_key="outsider",
            roles=frozenset({"mso_owner"}),
            is_presenter=True,
            presenter_actor_id=outsider_user_id,
        )

    app.dependency_overrides[get_principal] = outsider_principal
    try:
        catalog = await presenter_client.get(f"{LEARNING_ROOT}/episodes")
        manifests = await presenter_client.get(f"{LEARNING_ROOT}/dataset-manifests")
        fetched = await presenter_client.get(f"{LEARNING_ROOT}/environment-runs/{run_id}")
        stepped = await presenter_client.post(
            f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
            json=_step_body(1, "review_intake", "cross-tenant-step"),
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert catalog.status_code == manifests.status_code == 200
    assert catalog.json() == {"episodes": []}
    assert manifests.json() == {"datasets": []}
    assert fetched.status_code == 404
    assert stepped.status_code == 404
    assert fetched.json()["detail"] == stepped.json()["detail"] == "Environment run not found"


async def test_dataset_manifest_response_is_explicitly_phi_safe(presenter_client) -> None:
    response = await presenter_client.get(f"{LEARNING_ROOT}/dataset-manifests")
    assert response.status_code == 200, response.text
    datasets = response.json()["datasets"]
    assert len(datasets) == 1
    manifest = datasets[0]
    assert set(manifest) == {
        "id",
        "name",
        "version",
        "status",
        "classification",
        "containsPhi",
        "purpose",
        "prohibitedUses",
        "schemaVersion",
        "rowCount",
        "hash",
        "releasedAt",
    }
    assert manifest["id"] == str(canonical_ids()["learning_dataset_release_id"])
    assert manifest["classification"] == "synthetic"
    assert manifest["containsPhi"] is False
    assert manifest["rowCount"] == 0
    assert manifest["purpose"] == ["environment_validation", "offline_evaluation"]
    assert "reidentification" in manifest["prohibitedUses"]
    serialized = json.dumps(manifest, sort_keys=True).lower()
    for forbidden in (
        "internal://",
        "lineageuri",
        "cohortdefinition",
        "patientid",
        "storageuri",
        "filename",
    ):
        assert forbidden not in serialized


async def test_learning_routes_preserve_timing_budgets_and_normalize_request_ids(
    presenter_client,
) -> None:
    episodes = await presenter_client.get(
        f"{LEARNING_ROOT}/episodes",
        headers={"X-Request-ID": "learning-episodes-contract"},
    )
    assert episodes.status_code == 200
    assert episodes.headers["x-request-id"] == "learning-episodes-contract"

    datasets = await presenter_client.get(f"{LEARNING_ROOT}/dataset-manifests")
    unsafe_request_id = "unsafe request identifier " * 4
    created = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs",
        headers={"X-Request-ID": unsafe_request_id},
        json=_run_body("timing-and-correlation-run"),
    )
    assert created.status_code == 200, created.text
    normalized_request_id = created.headers["x-request-id"]
    assert normalized_request_id != unsafe_request_id
    uuid.UUID(normalized_request_id)

    run_id = created.json()["run"]["id"]
    fetched = await presenter_client.get(f"{LEARNING_ROOT}/environment-runs/{run_id}")
    stepped = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/steps",
        json=_step_body(1, "review_intake", "timed-step"),
    )
    assert datasets.status_code == fetched.status_code == stepped.status_code == 200

    ceilings = {
        "episodes": (episodes, 5),
        "datasets": (datasets, 5),
        "create": (created, 15),
        "get": (fetched, 7),
        "step": (stepped, 25),
    }
    for label, (response, query_ceiling) in ceilings.items():
        assert response.headers["cache-control"] == "private, no-store, max-age=0", label
        duration_ms, query_count = _observed_timing(response)
        assert duration_ms < 1_000, (label, duration_ms)
        assert query_count <= query_ceiling, (label, query_count)

    async with SessionLocal() as session:
        created_event = await session.scalar(
            select(DomainEvent).where(
                DomainEvent.aggregate_id == uuid.UUID(run_id),
                DomainEvent.event_type == "environment.run.created",
            )
        )
    assert created_event is not None
    assert created_event.request_id == normalized_request_id
