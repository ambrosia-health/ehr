from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select

from app import main as app_main
from app.database import SessionLocal
from app.models import ActionAttempt, AIInput, AIRun, EnvironmentStep
from app.seed import canonical_ids

LEARNING_ROOT = "/api/demo/learning"


def _query_count(response) -> int:
    match = re.search(r'desc="(\d+) queries"', response.headers.get("server-timing", ""))
    assert match, response.headers.get("server-timing")
    return int(match.group(1))


def _run_body(idempotency_key: str) -> dict[str, object]:
    return {
        "episodeDefinitionId": str(canonical_ids()["learning_episode_definition_id"]),
        "actorRole": "environment_agent",
        "seed": 17,
        "idempotencyKey": idempotency_key,
    }


async def _create_run(presenter_client, key: str) -> dict:
    response = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs",
        json=_run_body(key),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_console_feed_is_bounded_safe_and_observable(presenter_client) -> None:
    response = await presenter_client.get(f"{LEARNING_ROOT}/console")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert set(payload) == {
        "datasets",
        "episodeDefinitions",
        "limit",
        "overview",
        "recentAiRuns",
        "recentEnvironmentRuns",
        "recentEpisodes",
    }
    assert payload["overview"]["episodeCount"] >= 1
    assert payload["overview"]["aiRunCount"] >= 1
    assert payload["episodeDefinitions"][0]["id"] == str(
        canonical_ids()["learning_episode_definition_id"]
    )

    def all_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(all_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(all_keys(item) for item in value))
        return set()

    assert all_keys(payload).isdisjoint(
        {
            "contentJson",
            "lineageUri",
            "patientId",
            "patientName",
            "resourceId",
            "runKey",
            "snapshotRef",
        }
    )
    assert _query_count(response) <= 20


async def test_model_step_is_idempotent_and_visible_in_run_history(presenter_client) -> None:
    created = await _create_run(presenter_client, "console-model-step")
    run_id = created["run"]["id"]
    run_uuid = uuid.UUID(run_id)
    body = {"expectedSequence": 1, "idempotencyKey": "console-model-step-1"}

    first = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json=body,
    )
    retry = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json=body,
    )
    assert first.status_code == retry.status_code == 200
    first_payload = first.json()
    assert retry.json() == first_payload
    assert first_payload["run"]["sequence"] == 1
    assert first_payload["model"] == {
        "aiRunId": first_payload["model"]["aiRunId"],
        "provider": "deterministic_fallback",
        "model": "ambrosia-fixture-2026.1",
        "fallbackUsed": True,
        "latencyMs": first_payload["model"]["latencyMs"],
        "errorCode": "model_fallback",
    }
    assert _query_count(first) <= 60

    history = await presenter_client.get(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/history"
    )
    assert history.status_code == 200, history.text
    history_payload = history.json()
    assert len(history_payload["steps"]) == 1
    action = history_payload["steps"][0]["action"]
    assert action["aiProvenance"]["fallbackUsed"] is True
    assert action["aiProvenance"]["capability"] == "environment_action"
    assert history_payload["steps"][0]["hardViolations"] == []
    assert _query_count(history) <= 16

    async with SessionLocal() as session:
        ai_runs = int(
            await session.scalar(
                select(func.count(AIRun.id)).where(AIRun.capability == "environment_action")
            )
            or 0
        )
        steps = int(
            await session.scalar(
                    select(func.count(EnvironmentStep.id)).where(
                        EnvironmentStep.environment_run_id == run_uuid
                    )
            )
            or 0
        )
        action_attempt = await session.scalar(
            select(ActionAttempt).where(ActionAttempt.ai_run_id.is_not(None))
        )
        ai_input = await session.scalar(
            select(AIInput)
            .join(AIRun, AIRun.id == AIInput.ai_run_id)
            .where(AIRun.capability == "environment_action")
        )
    assert ai_runs == 1
    assert steps == 1
    assert action_attempt is not None
    assert ai_input is not None
    assert ai_input.content_json["contentStored"] is False
    assert "observation" not in ai_input.content_json


async def test_model_can_drive_a_synthetic_run_to_terminal_state(presenter_client) -> None:
    current = await _create_run(presenter_client, "console-model-terminal")
    run_id = current["run"]["id"]

    for expected_sequence in range(1, 11):
        response = await presenter_client.post(
            f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
            json={
                "expectedSequence": expected_sequence,
                "idempotencyKey": f"console-model-terminal-{expected_sequence}",
            },
        )
        assert response.status_code == 200, response.text
        current = response.json()
        if current["run"]["status"] != "running":
            break

    assert current["run"]["status"] == "completed"
    assert current["run"]["terminationReason"] == "episode_complete"
    assert current["hardViolationCount"] == 0
    assert current["run"]["sequence"] == 7

    history = await presenter_client.get(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/history"
    )
    assert history.status_code == 200
    assert len(history.json()["steps"]) == 7


async def test_stale_model_step_is_rejected_before_inference(
    presenter_client,
    monkeypatch,
) -> None:
    created = await _create_run(presenter_client, "console-model-stale")
    called = False

    async def unexpected_inference(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("stale model step reached inference")

    monkeypatch.setattr(app_main, "choose_environment_action", unexpected_inference)
    response = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{created['run']['id']}/model-step",
        json={"expectedSequence": 2, "idempotencyKey": "console-model-stale-2"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Expected environment step 1"
    assert called is False
    async with SessionLocal() as session:
        model_runs = await session.scalar(
            select(func.count(AIRun.id)).where(AIRun.capability == "environment_action")
        )
    assert model_runs == 0


async def test_model_step_receipt_stays_stable_after_the_run_advances(
    presenter_client,
) -> None:
    created = await _create_run(presenter_client, "console-model-late-retry")
    run_id = created["run"]["id"]
    first_body = {
        "expectedSequence": 1,
        "idempotencyKey": "console-model-late-retry-1",
    }
    first = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json=first_body,
    )
    second = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json={
            "expectedSequence": 2,
            "idempotencyKey": "console-model-late-retry-2",
        },
    )
    late_retry = await presenter_client.post(
        f"{LEARNING_ROOT}/environment-runs/{run_id}/model-step",
        json=first_body,
    )

    assert first.status_code == second.status_code == late_retry.status_code == 200
    assert second.json()["run"]["sequence"] == 2
    assert late_retry.json() == first.json()


async def test_console_detail_routes_hide_cross_tenant_or_missing_records(
    presenter_client,
) -> None:
    missing_episode = await presenter_client.get(
        f"{LEARNING_ROOT}/episodes/00000000-0000-0000-0000-000000000001/trajectory"
    )
    missing_run = await presenter_client.get(
        f"{LEARNING_ROOT}/environment-runs/00000000-0000-0000-0000-000000000001/history"
    )
    assert missing_episode.status_code == 404
    assert missing_run.status_code == 404
