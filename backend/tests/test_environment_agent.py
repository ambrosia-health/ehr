from __future__ import annotations

import json
import uuid

from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.environment_agent import choose_environment_action
from app.learning import create_environment_run, environment_run_view, step_environment
from app.models import AIInput, AIOutput, DomainEvent, PromptVersion, ProvenanceRecord
from app.seed import canonical_ids, seed_database, sid


async def _create_run(session, key: str):
    ids = canonical_ids()
    run = await create_environment_run(
        session,
        organization_id=ids["organization_id"],
        requested_by_user_id=sid("user:owner"),
        episode_definition_id=ids["learning_episode_definition_id"],
        actor_role="environment_agent",
        seed=17,
        idempotency_key=key,
    )
    await session.flush()
    return run


async def test_environment_agent_chooses_allowed_action_and_records_hash_only_evidence() -> None:
    ids = canonical_ids()
    async with SessionLocal() as session:
        run = await _create_run(session, "model-policy-fallback")
        initial = await environment_run_view(
            session,
            organization_id=ids["organization_id"],
            run_id=run.id,
        )
        action, ai_run = await choose_environment_action(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            run_id=run.id,
        )
        result = await step_environment(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            run_id=run.id,
            expected_sequence=1,
            idempotency_key=f"agent:{ai_run.id}",
            action_type=action.type,
            reason_code=action.reason_code,
        )
        await session.commit()
        run_id = run.id
        ai_run_id = ai_run.id

    async with SessionLocal() as session:
        ai_input = await session.scalar(select(AIInput).where(AIInput.ai_run_id == ai_run_id))
        ai_output = await session.scalar(select(AIOutput).where(AIOutput.ai_run_id == ai_run_id))
        provenance = await session.scalar(
            select(ProvenanceRecord).where(ProvenanceRecord.ai_run_id == ai_run_id)
        )
        event = await session.scalar(
            select(DomainEvent).where(
                DomainEvent.aggregate_type == "ai_run",
                DomainEvent.aggregate_id == ai_run_id,
            )
        )

    assert action.type == "review_intake"
    assert action.type in initial["allowed_actions"]
    assert action.reason_code == "deterministic_fallback"
    assert ai_run.provider == "deterministic_fallback"
    assert ai_run.model == "ambrosia-fixture-2026.1"
    assert ai_run.fallback_used is True
    assert ai_run.error_message == "OpenAI is not configured"
    assert result["latest_step"]["action_type"] == action.type

    assert ai_input and ai_output and provenance and event
    assert ai_input.content_json == {
        "contextHash": ai_input.content_hash,
        "contextKeys": ["allowedActions", "observation"],
        "resourceRefCount": 0,
        "contentStored": False,
        "purposeOfUse": "synthetic_evaluation",
        "sensitivity": "synthetic",
    }
    assert ai_input.resource_refs_json == []
    persisted_input = json.dumps(ai_input.content_json, sort_keys=True)
    assert "coverageStatus" not in persisted_input
    assert "review_intake" not in persisted_input
    assert ai_output.output_type == "environment_action"
    assert ai_output.content_json == {
        "type": "review_intake",
        "reasonCode": "deterministic_fallback",
    }
    assert provenance.source_entity_type == "environment_run"
    assert provenance.source_entity_id == run_id
    assert provenance.detail_json["purposeOfUse"] == "synthetic_evaluation"
    assert provenance.detail_json["sensitivity"] == "synthetic"
    assert event.patient_id is None
    assert event.purpose_of_use == "synthetic_evaluation"
    assert event.sensitivity == "synthetic"
    assert event.actor_role == "environment_agent"


async def test_existing_demo_seed_adds_environment_prompt_once() -> None:
    ids = canonical_ids()
    prompt_id = sid("prompt:environment_action:2026.1")
    async with SessionLocal() as session:
        await session.execute(delete(PromptVersion).where(PromptVersion.id == prompt_id))
        await session.commit()

        await seed_database(session)
        await seed_database(session)
        count = await session.scalar(
            select(func.count(PromptVersion.id)).where(
                PromptVersion.organization_id == ids["organization_id"],
                PromptVersion.capability == "environment_action",
                PromptVersion.version == "2026.1",
            )
        )
        prompt = await session.get(PromptVersion, prompt_id)

    assert count == 1
    assert prompt is not None
    assert prompt.active is True
    assert prompt.output_schema_json["properties"]["type"]


async def test_environment_agent_records_live_allowed_model_choice(monkeypatch) -> None:
    from app import ai

    async def live_policy(_capability: str, _context: dict, **_prompt):
        return (
            {"type": "request_missing_information", "reasonCode": "needs_more_data"},
            "openai",
            "gpt-5.6-luna",
            False,
            None,
        )

    monkeypatch.setattr(ai, "_live_inference", live_policy)
    ids = canonical_ids()
    async with SessionLocal() as session:
        run = await _create_run(session, "model-policy-live")
        action, ai_run = await choose_environment_action(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            run_id=run.id,
        )
        await session.commit()

    assert action.type == "request_missing_information"
    assert ai_run.provider == "openai"
    assert ai_run.model == "gpt-5.6-luna"
    assert ai_run.fallback_used is False
    assert ai_run.error_message is None


async def test_environment_agent_never_accepts_model_action_outside_allowed_set(
    monkeypatch,
) -> None:
    from app import ai

    async def invalid_policy(_capability: str, _context: dict, **_prompt):
        return (
            {"type": "close_episode", "reasonCode": "skip_ahead"},
            "openai",
            "gpt-5.6-luna",
            False,
            None,
        )

    monkeypatch.setattr(ai, "_live_inference", invalid_policy)
    ids = canonical_ids()
    async with SessionLocal() as session:
        run = await _create_run(session, f"model-policy-invalid-{uuid.uuid4()}")
        action, ai_run = await choose_environment_action(
            session,
            organization_id=ids["organization_id"],
            requested_by_user_id=sid("user:owner"),
            run_id=run.id,
        )
        await session.commit()

    assert action.type == "review_intake"
    assert ai_run.provider == "deterministic_fallback"
    assert ai_run.fallback_used is True
    assert "outside the allowed set" in (ai_run.error_message or "")
