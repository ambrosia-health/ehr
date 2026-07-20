from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.learning import create_environment_run, step_environment
from app.learning_console import (
    learning_console_bootstrap,
    learning_console_environment_run_history,
    learning_console_episode_trajectory,
)
from app.models import (
    ActionAttempt,
    DecisionPoint,
    DomainEvent,
    EnvironmentStep,
    EpisodeEventLink,
    EpisodeInstance,
    ObservationManifest,
    ObservationResource,
    OutcomeObservation,
    RewardComponent,
)
from app.observability import begin_request, reset_request
from app.seed import canonical_ids, sid

FORBIDDEN_RESPONSE_KEYS = {
    "actor_user_id",
    "arguments_json",
    "content_json",
    "error_message",
    "expected_target_id",
    "human_edit_diff_json",
    "lineage_uri",
    "metadata_json",
    "patient_id",
    "payload_json",
    "requested_by_user_id",
    "resource_id",
    "resource_refs_json",
    "snapshot_ref",
}


def _response_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key for nested in value.values() for nested_key in _response_keys(nested)
        }
    if isinstance(value, list):
        return {nested_key for item in value for nested_key in _response_keys(item)}
    return set()


async def test_console_bootstrap_is_bounded_tenant_scoped_and_content_safe() -> None:
    ids = canonical_ids()
    async with SessionLocal() as session:
        metrics, token = begin_request("learning-console-bootstrap-test")
        try:
            response = await learning_console_bootstrap(
                session,
                organization_id=ids["organization_id"],
                limit=500,
            )
        finally:
            reset_request(token)
        empty_tenant = await learning_console_bootstrap(
            session,
            organization_id=uuid.uuid4(),
        )

    assert response["limit"] == 50
    assert metrics.query_count <= 8
    assert response["overview"]["episode_count"] >= 1
    assert response["overview"]["ai_run_count"] >= 1
    assert response["recent_episodes"]
    assert response["recent_ai_runs"]
    assert response["datasets"]
    assert all(
        "output_hash" in output for run in response["recent_ai_runs"] for output in run["outputs"]
    )
    assert not (_response_keys(response) & FORBIDDEN_RESPONSE_KEYS)
    assert empty_tenant["overview"] == {
        "episode_count": 0,
        "active_episode_count": 0,
        "environment_run_count": 0,
        "active_environment_run_count": 0,
        "ai_run_count": 0,
        "failed_ai_run_count": 0,
        "dataset_release_count": 0,
        "hard_violation_count": 0,
    }
    assert empty_tenant["recent_episodes"] == []
    assert empty_tenant["recent_environment_runs"] == []
    assert empty_tenant["recent_ai_runs"] == []
    assert empty_tenant["datasets"] == []


async def _create_live_redaction_fixture(secret: str) -> tuple[uuid.UUID, uuid.UUID]:
    ids = canonical_ids()
    now = datetime.now(UTC)
    episode_id = uuid.uuid4()
    manifest_id = uuid.uuid4()
    event_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    action_id = uuid.uuid4()
    slot_id = uuid.uuid4()
    alternate_slot_id = uuid.uuid4()
    async with SessionLocal() as session:
        episode = EpisodeInstance(
            id=episode_id,
            organization_id=ids["organization_id"],
            episode_definition_id=ids["learning_episode_definition_id"],
            episode_key=f"live-redaction-test:{episode_id}",
            source_kind="live",
            patient_id=ids["sarah_patient_id"],
            status="running",
            started_at=now,
            metadata_json={"raw": secret},
        )
        session.add(episode)
        await session.flush([episode])
        manifest = ObservationManifest(
            id=manifest_id,
            organization_id=ids["organization_id"],
            episode_instance_id=episode.id,
            sequence=1,
            as_of_at=now,
            recorded_cutoff_at=now,
            schema_version=1,
            manifest_hash="a" * 64,
            snapshot_ref=f"storage://{secret}",
            synthetic_snapshot_json={"raw": secret},
            sensitivity="restricted",
            purpose_of_use="care_operations",
        )
        session.add(manifest)
        await session.flush([manifest])
        session.add(
            ObservationResource(
                id=uuid.uuid4(),
                organization_id=ids["organization_id"],
                observation_manifest_id=manifest.id,
                sequence=1,
                resource_type="EncounterNote",
                resource_id=uuid.uuid4(),
                resource_version=3,
                recorded_at=now,
                content_hash="b" * 64,
                snapshot_ref=f"storage://{secret}",
            )
        )
        event = DomainEvent(
            id=event_id,
            organization_id=ids["organization_id"],
            event_type="test.live_decision",
            schema_version=1,
            aggregate_type="encounter_note",
            aggregate_id=uuid.uuid4(),
            aggregate_sequence=1,
            patient_id=ids["sarah_patient_id"],
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            actor_role="provider",
            occurred_at=now,
            recorded_at=now,
            payload_json={"raw": secret},
            payload_hash="c" * 64,
            sensitivity="restricted",
            purpose_of_use="care_operations",
        )
        session.add(event)
        await session.flush([event])
        decision = DecisionPoint(
            id=decision_id,
            organization_id=ids["organization_id"],
            episode_instance_id=episode.id,
            sequence=1,
            decision_type="patient_intake_submission",
            observation_manifest_id=manifest.id,
            trigger_event_id=event.id,
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            actor_role="provider",
            available_actions_json=[
                f"book_appointment_slot:{slot_id}",
                f"book_appointment_slot:{alternate_slot_id}",
            ],
            policy_refs_json=[{"contentHash": "d" * 64, "raw": secret}],
            status="decided",
            opened_at=now,
            decided_at=now,
        )
        session.add(decision)
        await session.flush([decision])
        action = ActionAttempt(
            id=action_id,
            organization_id=ids["organization_id"],
            decision_point_id=decision.id,
            sequence=1,
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            action_type=f"book_appointment_slot:{slot_id}",
            arguments_json={"raw": secret},
            expected_target_type=f"appointment_slot:{slot_id}",
            expected_target_id=uuid.uuid4(),
            expected_target_version=3,
            idempotency_key=f"live-redaction:{episode.id}",
            status="succeeded",
            attempted_at=now,
            executed_at=now,
            result_event_id=event.id,
            human_edit_diff_json={"raw": secret},
        )
        session.add(action)
        await session.flush([action])
        session.add_all(
            [
                EpisodeEventLink(
                    id=uuid.uuid4(),
                    organization_id=ids["organization_id"],
                    episode_instance_id=episode.id,
                    domain_event_id=event.id,
                    sequence=1,
                    role="decision_result",
                ),
                OutcomeObservation(
                    id=uuid.uuid4(),
                    organization_id=ids["organization_id"],
                    episode_instance_id=episode.id,
                    decision_point_id=decision.id,
                    action_attempt_id=action.id,
                    outcome_type="test.live_outcome",
                    value_json={"raw": secret},
                    provenance_kind="observed",
                    observed_at=now,
                    source_event_id=event.id,
                    confidence=Decimal("1.000"),
                    content_hash="e" * 64,
                ),
            ]
        )
        await session.commit()
    return episode_id, slot_id


async def _append_divergent_trajectory_page(
    episode_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    ids = canonical_ids()
    now = datetime.now(UTC)
    manifest_id = uuid.uuid4()
    trigger_event_id = uuid.uuid4()
    result_event_id = uuid.uuid4()
    second_decision_id = uuid.uuid4()
    second_action_id = uuid.uuid4()
    async with SessionLocal() as session:
        first_decision = await session.scalar(
            select(DecisionPoint).where(
                DecisionPoint.organization_id == ids["organization_id"],
                DecisionPoint.episode_instance_id == episode_id,
                DecisionPoint.sequence == 1,
            )
        )
        assert first_decision is not None
        manifest = ObservationManifest(
            id=manifest_id,
            organization_id=ids["organization_id"],
            episode_instance_id=episode_id,
            sequence=2,
            as_of_at=now,
            recorded_cutoff_at=now,
            schema_version=1,
            manifest_hash="1" * 64,
            sensitivity="restricted",
            purpose_of_use="care_operations",
        )
        trigger_event = DomainEvent(
            id=trigger_event_id,
            organization_id=ids["organization_id"],
            event_type="test.followup_opened",
            schema_version=1,
            aggregate_type="appointment",
            aggregate_id=uuid.uuid4(),
            aggregate_sequence=1,
            patient_id=ids["sarah_patient_id"],
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            actor_role="provider",
            occurred_at=now,
            recorded_at=now,
            payload_json={"phase": "trigger"},
            payload_hash="2" * 64,
            sensitivity="restricted",
            purpose_of_use="care_operations",
        )
        result_event = DomainEvent(
            id=result_event_id,
            organization_id=ids["organization_id"],
            event_type="test.followup_completed",
            schema_version=1,
            aggregate_type="appointment",
            aggregate_id=trigger_event.aggregate_id,
            aggregate_sequence=2,
            patient_id=ids["sarah_patient_id"],
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            actor_role="provider",
            occurred_at=now,
            recorded_at=now,
            payload_json={"phase": "result"},
            payload_hash="3" * 64,
            sensitivity="restricted",
            purpose_of_use="care_operations",
        )
        session.add_all([manifest, trigger_event, result_event])
        await session.flush()
        decision = DecisionPoint(
            id=second_decision_id,
            organization_id=ids["organization_id"],
            episode_instance_id=episode_id,
            sequence=2,
            decision_type="test.followup",
            observation_manifest_id=manifest.id,
            trigger_event_id=trigger_event.id,
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            actor_role="provider",
            available_actions_json=["complete_followup"],
            policy_refs_json=[],
            status="decided",
            opened_at=now,
            decided_at=now,
        )
        session.add(decision)
        await session.flush()
        action = ActionAttempt(
            id=second_action_id,
            organization_id=ids["organization_id"],
            decision_point_id=decision.id,
            sequence=1,
            actor_kind="human",
            actor_user_id=sid("user:provider"),
            action_type="complete_followup",
            arguments_json={},
            idempotency_key=f"divergent-page:{episode_id}",
            status="succeeded",
            attempted_at=now,
            executed_at=now,
            result_event_id=result_event.id,
        )
        session.add(action)
        await session.flush()
        session.add_all(
            [
                EpisodeEventLink(
                    id=uuid.uuid4(),
                    organization_id=ids["organization_id"],
                    episode_instance_id=episode_id,
                    domain_event_id=trigger_event.id,
                    sequence=2,
                    role="decision_trigger",
                ),
                EpisodeEventLink(
                    id=uuid.uuid4(),
                    organization_id=ids["organization_id"],
                    episode_instance_id=episode_id,
                    domain_event_id=result_event.id,
                    sequence=3,
                    role="decision_result",
                ),
                OutcomeObservation(
                    id=uuid.uuid4(),
                    organization_id=ids["organization_id"],
                    episode_instance_id=episode_id,
                    decision_point_id=decision.id,
                    action_attempt_id=action.id,
                    outcome_type="test.early_observation",
                    value_json={"result": "second"},
                    provenance_kind="observed",
                    observed_at=datetime(2000, 1, 1, tzinfo=UTC),
                    source_event_id=result_event.id,
                    confidence=Decimal("1.000"),
                    content_hash="4" * 64,
                ),
            ]
        )
        await session.commit()
        return first_decision.id, decision.id


async def test_episode_trajectory_redacts_live_content_and_rejects_cross_tenant_reads() -> None:
    ids = canonical_ids()
    secret = "must-never-leave-live-records"
    episode_id, slot_id = await _create_live_redaction_fixture(secret)

    async with SessionLocal() as session:
        metrics, token = begin_request("learning-console-trajectory-test")
        try:
            response = await learning_console_episode_trajectory(
                session,
                organization_id=ids["organization_id"],
                episode_id=episode_id,
                limit=500,
            )
        finally:
            reset_request(token)
        with pytest.raises(HTTPException) as cross_tenant:
            await learning_console_episode_trajectory(
                session,
                organization_id=uuid.uuid4(),
                episode_id=episode_id,
            )

    assert cross_tenant.value.status_code == 404
    assert metrics.query_count <= 7
    assert response["pagination"]["limit"] == 50
    assert response["episode"]["source_kind"] == "live"
    available_actions = response["decisions"][0]["available_actions"]
    assert [item["type"] for item in available_actions] == [
        "book_appointment_slot",
        "book_appointment_slot",
    ]
    assert len({item["action_hash"] for item in available_actions}) == 2
    assert "synthetic_snapshot" not in response["decisions"][0]["observation"]
    selected_action = response["decisions"][0]["selected_action"]
    assert selected_action["action_type"] == "book_appointment_slot"
    assert selected_action["action_type_hash"] == available_actions[0]["action_hash"]
    assert selected_action["expected_target_type"] == "appointment_slot"
    assert selected_action["expected_target_type_hash"]
    assert selected_action["arguments_hash"]
    assert response["events"][0]["payload_hash"] == "c" * 64
    assert "value" not in response["outcomes"][0]
    assert secret not in json.dumps(response, default=str)
    assert str(slot_id) not in json.dumps(response, default=str)
    assert not (_response_keys(response) & FORBIDDEN_RESPONSE_KEYS)


async def test_episode_trajectory_pages_decision_owned_events_and_delayed_outcomes() -> None:
    ids = canonical_ids()
    episode_id, _slot_id = await _create_live_redaction_fixture("page-owned-evidence")
    first_decision_id, second_decision_id = await _append_divergent_trajectory_page(
        episode_id
    )

    async with SessionLocal() as session:
        first_page = await learning_console_episode_trajectory(
            session,
            organization_id=ids["organization_id"],
            episode_id=episode_id,
            limit=1,
        )
        second_page = await learning_console_episode_trajectory(
            session,
            organization_id=ids["organization_id"],
            episode_id=episode_id,
            offset=first_page["pagination"]["next_offset"],
            limit=1,
        )

    assert first_page["pagination"]["next_offset"] == 1
    assert first_page["pagination"]["scope"] == "decision_page"
    assert first_page["pagination"]["has_more"] == {
        "decisions": True,
        "events": False,
        "outcomes": False,
    }
    assert first_page["decisions"][0]["id"] == first_decision_id
    assert {item["decision_point_id"] for item in first_page["outcomes"]} == {
        first_decision_id
    }
    assert [item["sequence"] for item in first_page["events"]] == [1]

    assert second_page["pagination"]["next_offset"] is None
    assert second_page["decisions"][0]["id"] == second_decision_id
    assert {item["decision_point_id"] for item in second_page["outcomes"]} == {
        second_decision_id
    }
    assert len(second_page["events"]) == 2
    assert {item["sequence"] for item in second_page["events"]} == {2}
    assert {item["association"] for item in second_page["events"]} == {
        "trigger",
        "result",
    }
    assert (
        first_page["outcomes"][0]["observed_at"]
        > second_page["outcomes"][0]["observed_at"]
    )
    assert first_page["decisions"][0]["outcomes"] == first_page["outcomes"]
    assert second_page["decisions"][0]["outcomes"] == second_page["outcomes"]


async def test_environment_history_pages_steps_rewards_and_safe_ai_provenance() -> None:
    ids = canonical_ids()
    async with SessionLocal() as session:
        run = await create_environment_run(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            episode_definition_id=ids["learning_episode_definition_id"],
            actor_role="environment_agent",
            seed=101,
            idempotency_key="learning-console-history",
        )
        await session.flush()
        await step_environment(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            run_id=run.id,
            expected_sequence=1,
            idempotency_key="learning-console-step-1",
            action_type="review_intake",
            reason_code=None,
        )
        first_step = await session.scalar(
            select(EnvironmentStep).where(
                EnvironmentStep.organization_id == ids["organization_id"],
                EnvironmentStep.environment_run_id == run.id,
                EnvironmentStep.step_number == 1,
            )
        )
        assert first_step and first_step.decision_point_id
        ai_action = ActionAttempt(
            id=uuid.uuid4(),
            organization_id=ids["organization_id"],
            decision_point_id=first_step.decision_point_id,
            sequence=2,
            actor_kind="agent",
            ai_run_id=sid("ai-run:sarah:ambient-note"),
            action_type="complete_encounter_review",
            arguments_json={"requestHash": "f" * 64},
            idempotency_key="learning-console-ai-action",
            status="succeeded",
            attempted_at=first_step.simulator_time_after,
            executed_at=first_step.simulator_time_after,
            human_edit_diff_json={},
        )
        session.add(ai_action)
        await session.flush([ai_action])
        second_step = EnvironmentStep(
            id=uuid.uuid4(),
            organization_id=ids["organization_id"],
            environment_run_id=run.id,
            step_number=2,
            decision_point_id=first_step.decision_point_id,
            observation_manifest_id=first_step.observation_manifest_id,
            action_attempt_id=ai_action.id,
            simulator_time_before=first_step.simulator_time_after,
            simulator_time_after=first_step.simulator_time_after,
            state_before_hash="1" * 64,
            state_after_hash="2" * 64,
            support_kind="simulated",
            terminated=False,
            latency_ms=3,
        )
        session.add(second_step)
        await session.flush([second_step])
        session.add(
            RewardComponent(
                id=uuid.uuid4(),
                organization_id=ids["organization_id"],
                environment_step_id=second_step.id,
                component_name="safety",
                evaluator_key="console-test",
                evaluator_version="1",
                value=Decimal("-1"),
                weight=Decimal("1"),
                hard_violation=True,
                evidence_json={"codes": ["unsafe_test_action"]},
                provenance_kind="simulated",
            )
        )
        await session.commit()
        run_id = run.id

    async with SessionLocal() as session:
        first_page = await learning_console_environment_run_history(
            session,
            organization_id=ids["organization_id"],
            run_id=run_id,
            limit=1,
        )
        metrics, token = begin_request("learning-console-environment-history-test")
        try:
            second_page = await learning_console_environment_run_history(
                session,
                organization_id=ids["organization_id"],
                run_id=run_id,
                after_step=first_page["pagination"]["next_after_step"],
                limit=1,
            )
        finally:
            reset_request(token)
        with pytest.raises(HTTPException) as cross_tenant:
            await learning_console_environment_run_history(
                session,
                organization_id=uuid.uuid4(),
                run_id=run_id,
            )

    assert cross_tenant.value.status_code == 404
    assert metrics.query_count <= 10
    assert first_page["pagination"] == {
        "after_step": 0,
        "limit": 1,
        "next_after_step": 1,
        "has_more": True,
    }
    assert first_page["steps"][0]["decision"]["available_actions"]
    assert first_page["steps"][0]["rewards"]
    assert "synthetic_snapshot" in first_page["steps"][0]["observation"]
    ai_provenance = second_page["steps"][0]["action"]["ai_provenance"]
    assert ai_provenance["model"] == "ambrosia-fixture-2026.1"
    assert ai_provenance["inputs"][0]["content_hash"]
    assert ai_provenance["outputs"][0]["output_hash"]
    assert second_page["steps"][0]["hard_violations"] == ["unsafe_test_action"]
    assert second_page["pagination"]["has_more"] is False
    assert not (_response_keys(second_page) & FORBIDDEN_RESPONSE_KEYS)
