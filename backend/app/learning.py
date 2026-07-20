from __future__ import annotations

import hashlib
import json
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    ActionAttempt,
    DatasetRelease,
    DatasetReleaseItem,
    DecisionPoint,
    DomainEvent,
    EnvironmentRun,
    EnvironmentStep,
    EpisodeDefinition,
    EpisodeEventLink,
    EpisodeInstance,
    ObservationManifest,
    ObservationResource,
    OutcomeObservation,
    RewardComponent,
    SimulationScenario,
    utcnow,
)
from .observability import current_request_id

LEARNING_NAMESPACE = uuid.UUID("8d038ee1-0433-44b0-a512-d4e80a3e0be8")
ENVIRONMENT_CODE_VERSION = "ambrosia-learning-environment-2026.1"
ENVIRONMENT_EVALUATOR = "ambrosia-vector-evaluator"
ENVIRONMENT_EVALUATOR_VERSION = "2026.1"
MAX_EVENT_PAYLOAD_BYTES = 32 * 1024
MAX_OBSERVATION_RESOURCES = 256


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def hash_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def environment_step_idempotency_key(run_id: uuid.UUID, idempotency_key: str) -> str:
    """Return the durable action-attempt key shared by manual and model steps."""

    return f"env-step:{hash_json({'run': str(run_id), 'key': idempotency_key})}"


async def prepare_environment_step(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    expected_sequence: int,
    idempotency_key: str,
) -> ActionAttempt | None:
    """Serialize a run command and reject stale input before any external work."""

    run = await session.scalar(
        select(EnvironmentRun)
        .where(
            EnvironmentRun.organization_id == organization_id,
            EnvironmentRun.id == run_id,
        )
        .with_for_update()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Environment run not found")
    existing_action = await session.scalar(
        select(ActionAttempt).where(
            ActionAttempt.organization_id == organization_id,
            ActionAttempt.idempotency_key
            == environment_step_idempotency_key(run.id, idempotency_key),
        )
    )
    if existing_action is not None:
        return existing_action
    if run.status != "running":
        raise HTTPException(status_code=409, detail="Environment run is terminal")
    if expected_sequence != run.current_step + 1:
        raise HTTPException(
            status_code=409,
            detail=f"Expected environment step {run.current_step + 1}",
        )
    max_steps = int(run.config_json.get("maxSteps", 10_000))
    if expected_sequence > max_steps:
        raise HTTPException(status_code=409, detail="Environment step limit exceeded")
    return None


def _bounded_payload(value: dict[str, Any]) -> dict[str, Any]:
    if len(canonical_json(value).encode()) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError("Learning event metadata exceeds 32 KB")
    return value


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _parsed_time(value: Any, fallback: datetime) -> datetime:
    if not isinstance(value, str):
        return fallback
    try:
        return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return fallback


async def record_domain_event(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    aggregate_sequence: int,
    actor_kind: str,
    occurred_at: datetime,
    payload: dict[str, Any],
    idempotency_key: str,
    patient_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    correlation_id: str | None = None,
    causation_event_id: uuid.UUID | None = None,
    effective_at: datetime | None = None,
    sensitivity: str = "operational",
    purpose_of_use: str = "care_operations",
) -> DomainEvent:
    """Append an idempotent, PHI-minimized event in the caller's transaction."""

    bounded = _bounded_payload(payload)
    payload_hash = hash_json(bounded)
    event_id = uuid.uuid5(
        LEARNING_NAMESPACE,
        f"{organization_id}:domain-event:{idempotency_key}",
    )
    existing = await session.scalar(
        select(DomainEvent).where(
            DomainEvent.organization_id == organization_id,
            DomainEvent.id == event_id,
        )
    )
    if existing is not None:
        identity_matches = (
            existing.event_type == event_type
            and existing.aggregate_type == aggregate_type
            and existing.aggregate_id == aggregate_id
            and existing.aggregate_sequence == aggregate_sequence
            and existing.patient_id == patient_id
        )
        if existing.payload_hash != payload_hash or not identity_matches:
            raise HTTPException(
                status_code=409,
                detail="Learning event idempotency key was reused with different identity or metadata",
            )
        return existing
    event = DomainEvent(
        id=event_id,
        organization_id=organization_id,
        event_type=event_type,
        schema_version=1,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_sequence=aggregate_sequence,
        patient_id=patient_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        request_id=current_request_id(),
        correlation_id=correlation_id[:64] if correlation_id else None,
        causation_event_id=causation_event_id,
        occurred_at=_aware(occurred_at),
        effective_at=_aware(effective_at) if effective_at else None,
        recorded_at=utcnow(),
        payload_json=bounded,
        payload_hash=payload_hash,
        sensitivity=sensitivity,
        purpose_of_use=purpose_of_use,
    )
    session.add(event)
    return event


async def ensure_patient_episode(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    patient_id: uuid.UUID,
    started_at: datetime,
    definition_slug: str = "longitudinal-dermatology-operations",
) -> EpisodeInstance | None:
    """Resolve the released patient-journey definition without creating policy implicitly."""

    definition = await session.scalar(
        select(EpisodeDefinition)
        .where(
            EpisodeDefinition.organization_id == organization_id,
            EpisodeDefinition.slug == definition_slug,
            EpisodeDefinition.status == "released",
        )
        .order_by(EpisodeDefinition.version.desc())
    )
    if definition is None:
        return None
    episode_key = f"patient-journey:{patient_id}"
    existing = await session.scalar(
        select(EpisodeInstance).where(
            EpisodeInstance.organization_id == organization_id,
            EpisodeInstance.episode_key == episode_key,
        )
    )
    if existing is not None:
        return existing
    episode_id = uuid.uuid5(definition.id, episode_key)
    episode = EpisodeInstance(
        id=episode_id,
        organization_id=organization_id,
        episode_definition_id=definition.id,
        episode_key=episode_key,
        source_kind="live",
        patient_id=patient_id,
        status="running",
        started_at=_aware(started_at),
        metadata_json={"rootType": "patient", "rootId": str(patient_id)},
    )
    session.add(episode)
    await session.flush([episode])
    return episode


async def _next_episode_sequence(
    session: AsyncSession,
    model: type[EpisodeEventLink] | type[DecisionPoint] | type[ObservationManifest],
    episode_id: uuid.UUID,
) -> int:
    column = model.sequence
    filter_column = (
        model.episode_instance_id
        if model is not EpisodeEventLink
        else EpisodeEventLink.episode_instance_id
    )
    current = await session.scalar(
        select(func.coalesce(func.max(column), 0)).where(filter_column == episode_id)
    )
    return int(current or 0) + 1


async def create_observation_manifest(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    episode: EpisodeInstance,
    sequence: int,
    as_of_at: datetime,
    resources: list[dict[str, Any]],
    synthetic_snapshot: dict[str, Any] | None = None,
    purpose_of_use: str = "care_operations",
    sensitivity: str = "restricted",
) -> ObservationManifest:
    if len(resources) > MAX_OBSERVATION_RESOURCES:
        raise ValueError("Observation manifest exceeds 256 resources")
    if synthetic_snapshot and sensitivity != "synthetic":
        raise ValueError("Inline observation snapshots are restricted to synthetic evidence")
    snapshot = _bounded_payload(synthetic_snapshot or {})
    recorded_cutoff = utcnow()
    normalized_resources: list[dict[str, Any]] = []
    unique_resources: set[tuple[str, uuid.UUID, int]] = set()
    for item in resources:
        resource_id = uuid.UUID(str(item["resource_id"]))
        resource_version = int(item.get("resource_version", 1))
        if resource_version < 1:
            raise ValueError("Observation resource versions must be positive")
        identity = (str(item["resource_type"]), resource_id, resource_version)
        if not identity[0] or len(identity[0]) > 64:
            raise ValueError("Observation resource type must contain 1 to 64 characters")
        if identity in unique_resources:
            raise ValueError("Observation manifest contains a duplicate resource version")
        unique_resources.add(identity)
        content_hash = str(item["content_hash"]).lower()
        if len(content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in content_hash
        ):
            raise ValueError("Observation resource content hash must be SHA-256")
        snapshot_ref = item.get("snapshot_ref")
        if snapshot_ref is not None and len(str(snapshot_ref)) > 500:
            raise ValueError("Observation resource snapshot reference exceeds 500 characters")
        normalized_resources.append(
            {
                "resource_type": identity[0],
                "resource_id": resource_id,
                "resource_version": resource_version,
                "effective_at": (
                    _parsed_time(item.get("effective_at"), _aware(as_of_at))
                    if item.get("effective_at")
                    else None
                ),
                "recorded_at": _parsed_time(item.get("recorded_at"), recorded_cutoff),
                "content_hash": content_hash,
                "snapshot_ref": str(snapshot_ref) if snapshot_ref is not None else None,
            }
        )
    resource_manifest = [
        {
            "type": item["resource_type"],
            "id": str(item["resource_id"]),
            "version": item["resource_version"],
            "contentHash": item["content_hash"],
            "effectiveAt": item["effective_at"],
            "recordedAt": item["recorded_at"],
            "snapshotRef": item["snapshot_ref"],
        }
        for item in normalized_resources
    ]
    manifest_payload = {
        "episodeId": str(episode.id),
        "sequence": sequence,
        "asOfAt": _aware(as_of_at),
        "resources": resource_manifest,
        "syntheticSnapshot": snapshot,
    }
    manifest_id = uuid.uuid5(episode.id, f"observation:{sequence}:{hash_json(manifest_payload)}")
    manifest = ObservationManifest(
        id=manifest_id,
        organization_id=organization_id,
        episode_instance_id=episode.id,
        sequence=sequence,
        as_of_at=_aware(as_of_at),
        recorded_cutoff_at=recorded_cutoff,
        schema_version=1,
        manifest_hash=hash_json(manifest_payload),
        synthetic_snapshot_json=snapshot,
        sensitivity=sensitivity,
        purpose_of_use=purpose_of_use,
    )
    session.add(manifest)
    # These learning tables deliberately avoid a large ORM object graph. Flush
    # the parent explicitly so composite tenant FKs are valid before resources.
    await session.flush([manifest])
    for index, item in enumerate(normalized_resources, 1):
        session.add(
            ObservationResource(
                id=uuid.uuid5(manifest.id, f"resource:{index}"),
                organization_id=organization_id,
                observation_manifest_id=manifest.id,
                sequence=index,
                resource_type=item["resource_type"],
                resource_id=item["resource_id"],
                resource_version=item["resource_version"],
                effective_at=item["effective_at"],
                recorded_at=item["recorded_at"],
                content_hash=item["content_hash"],
                snapshot_ref=item.get("snapshot_ref"),
            )
        )
    return manifest


async def record_decision_trajectory(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    episode: EpisodeInstance,
    decision_type: str,
    available_actions: list[str],
    selected_action: str,
    observation_resources: list[dict[str, Any]],
    actor_kind: str,
    actor_user_id: uuid.UUID | None,
    actor_role: str | None,
    occurred_at: datetime,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    aggregate_sequence: int,
    event_type: str,
    event_payload: dict[str, Any],
    idempotency_key: str,
    patient_id: uuid.UUID | None = None,
    action_arguments: dict[str, Any] | None = None,
    human_edit_diff: dict[str, Any] | None = None,
    policy_refs: list[dict[str, Any]] | None = None,
    displayed_proposal_id: uuid.UUID | None = None,
    recommendation_rendered_at: datetime | None = None,
    expected_target_type: str | None = None,
    expected_target_id: uuid.UUID | None = None,
    expected_target_version: int | None = None,
    sensitivity: str | None = None,
) -> tuple[DomainEvent, DecisionPoint, ActionAttempt]:
    event = await record_domain_event(
        session,
        organization_id=organization_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_sequence=aggregate_sequence,
        patient_id=patient_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        occurred_at=occurred_at,
        payload=event_payload,
        idempotency_key=idempotency_key,
        correlation_id=str(episode.id),
        sensitivity=sensitivity or ("restricted" if patient_id else "operational"),
    )
    await session.flush([event])
    existing_action = await session.scalar(
        select(ActionAttempt).where(
            ActionAttempt.organization_id == organization_id,
            ActionAttempt.idempotency_key == idempotency_key,
        )
    )
    if existing_action is not None:
        decision = await session.scalar(
            select(DecisionPoint).where(
                DecisionPoint.organization_id == organization_id,
                DecisionPoint.id == existing_action.decision_point_id,
            )
        )
        if decision is None:
            raise RuntimeError("Decision trajectory is incomplete")
        return event, decision, existing_action

    sequence = await _next_episode_sequence(session, DecisionPoint, episode.id)
    manifest = await create_observation_manifest(
        session,
        organization_id=organization_id,
        episode=episode,
        sequence=sequence,
        as_of_at=occurred_at,
        resources=observation_resources,
    )
    decision = DecisionPoint(
        id=uuid.uuid5(episode.id, f"decision:{sequence}:{idempotency_key}"),
        organization_id=organization_id,
        episode_instance_id=episode.id,
        sequence=sequence,
        decision_type=decision_type,
        observation_manifest_id=manifest.id,
        trigger_event_id=event.id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        available_actions_json=available_actions,
        policy_refs_json=policy_refs or [],
        displayed_proposal_id=displayed_proposal_id,
        recommendation_rendered_at=recommendation_rendered_at,
        status="decided",
        opened_at=_aware(occurred_at),
        decided_at=_aware(occurred_at),
    )
    action = ActionAttempt(
        id=uuid.uuid5(decision.id, f"action:1:{idempotency_key}"),
        organization_id=organization_id,
        decision_point_id=decision.id,
        sequence=1,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action_type=selected_action,
        arguments_json=_bounded_payload(action_arguments or {}),
        expected_target_type=expected_target_type,
        expected_target_id=expected_target_id,
        expected_target_version=expected_target_version,
        idempotency_key=idempotency_key,
        status="succeeded",
        attempted_at=_aware(occurred_at),
        executed_at=_aware(occurred_at),
        result_event_id=event.id,
        human_edit_diff_json=_bounded_payload(human_edit_diff or {}),
    )
    link_sequence = await _next_episode_sequence(session, EpisodeEventLink, episode.id)
    session.add(decision)
    await session.flush([decision])
    session.add(action)
    await session.flush([action])
    session.add(
        EpisodeEventLink(
            id=uuid.uuid5(episode.id, f"event-link:{event.id}"),
            organization_id=organization_id,
            episode_instance_id=episode.id,
            domain_event_id=event.id,
            sequence=link_sequence,
            role="decision_result",
        )
    )
    return event, decision, action


async def record_outcome(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    episode: EpisodeInstance,
    outcome_type: str,
    value: dict[str, Any],
    provenance_kind: str,
    observed_at: datetime,
    decision: DecisionPoint | None = None,
    action: ActionAttempt | None = None,
    source_event: DomainEvent | None = None,
    simulator_version: str | None = None,
    confidence: Decimal = Decimal("1.000"),
    check_existing: bool = True,
) -> OutcomeObservation:
    content = _bounded_payload(value)
    outcome_id = uuid.uuid5(
        episode.id,
        f"outcome:{outcome_type}:{source_event.id if source_event else hash_json(content)}",
    )
    if check_existing:
        existing = await session.scalar(
            select(OutcomeObservation).where(
                OutcomeObservation.organization_id == organization_id,
                OutcomeObservation.id == outcome_id,
            )
        )
        if existing is not None:
            if existing.content_hash != hash_json(content):
                raise HTTPException(
                    status_code=409,
                    detail="Outcome idempotency identity was reused with different metadata",
                )
            return existing
    outcome = OutcomeObservation(
        id=outcome_id,
        organization_id=organization_id,
        episode_instance_id=episode.id,
        decision_point_id=decision.id if decision else None,
        action_attempt_id=action.id if action else None,
        outcome_type=outcome_type,
        value_json=content,
        provenance_kind=provenance_kind,
        observed_at=_aware(observed_at),
        source_event_id=source_event.id if source_event else None,
        simulator_version=simulator_version,
        confidence=confidence,
        content_hash=hash_json(content),
    )
    session.add(outcome)
    return outcome


def _scenario_state(scenario: SimulationScenario) -> dict[str, Any]:
    return deepcopy(scenario.initial_state_json)


def _allowed_actions(
    scenario: SimulationScenario,
    state: dict[str, Any],
    actor_role: str,
) -> list[str]:
    stage = state.get("stage")
    transitions = scenario.transition_rules_json.get(str(stage), {})
    allowed = []
    for action_type, rule in transitions.items():
        roles = rule.get("roles", []) if isinstance(rule, dict) else []
        if not roles or actor_role in roles:
            allowed.append(action_type)
    return sorted(allowed)


async def create_environment_run(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    episode_definition_id: uuid.UUID,
    actor_role: str,
    seed: int,
    idempotency_key: str,
) -> EnvironmentRun:
    request_payload = {
        "episodeDefinitionId": str(episode_definition_id),
        "actorRole": actor_role,
        "seed": seed,
    }
    request_hash = hash_json(request_payload)
    run_key = f"demo:{idempotency_key}"
    existing = await session.scalar(
        select(EnvironmentRun).where(
            EnvironmentRun.organization_id == organization_id,
            EnvironmentRun.run_key == run_key,
        )
    )
    if existing is not None:
        if existing.config_json.get("requestHash") != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Environment run idempotency key was reused with different input",
            )
        return existing
    definition = await session.scalar(
        select(EpisodeDefinition).where(
            EpisodeDefinition.organization_id == organization_id,
            EpisodeDefinition.id == episode_definition_id,
            EpisodeDefinition.status == "released",
        )
    )
    if definition is None:
        raise HTTPException(status_code=404, detail="Synthetic episode definition not found")
    scenario = await session.scalar(
        select(SimulationScenario)
        .where(
            SimulationScenario.organization_id == organization_id,
            SimulationScenario.episode_definition_id == definition.id,
            SimulationScenario.synthetic_only.is_(True),
            SimulationScenario.status == "released",
        )
        .order_by(SimulationScenario.version.desc())
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="Released synthetic scenario not found")
    now = utcnow()
    run_id = uuid.uuid5(
        LEARNING_NAMESPACE,
        f"{organization_id}:environment-run:{run_key}",
    )
    episode_id = uuid.uuid5(run_id, "episode")
    episode = EpisodeInstance(
        id=episode_id,
        organization_id=organization_id,
        episode_definition_id=definition.id,
        episode_key=f"environment:{run_id}",
        source_kind="synthetic",
        seed=seed,
        status="running",
        started_at=_aware(scenario.logical_start_at),
        metadata_json={"environmentRunId": str(run_id), "scenarioId": str(scenario.id)},
    )
    state = _scenario_state(scenario)
    if not _allowed_actions(scenario, state, actor_role):
        raise HTTPException(
            status_code=422,
            detail="Actor role has no authorized action in the initial scenario state",
        )
    run = EnvironmentRun(
        id=run_id,
        organization_id=organization_id,
        run_key=run_key,
        mode="simulation",
        simulation_scenario_id=scenario.id,
        episode_definition_id=definition.id,
        episode_instance_id=episode.id,
        agent_kind="interactive_environment_agent",
        code_version=ENVIRONMENT_CODE_VERSION,
        seed=seed,
        config_json={
            "requestHash": request_hash,
            "actorRole": actor_role,
            "requestedByUserId": str(requested_by_user_id),
            "scenarioHash": scenario.content_hash,
            "maxSteps": definition.max_steps,
            "maxDurationSeconds": definition.max_duration_seconds,
        },
        current_step=0,
        state_json=state,
        total_reward_json={},
        hard_violation_count=0,
        status="running",
        started_at=now,
    )
    session.add(episode)
    await session.flush([episode])
    session.add(run)
    await create_observation_manifest(
        session,
        organization_id=organization_id,
        episode=episode,
        sequence=1,
        as_of_at=scenario.logical_start_at,
        resources=scenario.initial_state_refs_json,
        synthetic_snapshot=state.get("observation", {}),
        purpose_of_use="synthetic_evaluation",
        sensitivity="synthetic",
    )
    session.add(
        DomainEvent(
            id=uuid.uuid5(run.id, "created-event"),
            organization_id=organization_id,
            event_type="environment.run.created",
            schema_version=1,
            aggregate_type="environment_run",
            aggregate_id=run.id,
            aggregate_sequence=1,
            actor_kind="human",
            actor_user_id=requested_by_user_id,
            actor_role="presenter",
            request_id=current_request_id(),
            correlation_id=str(run.id),
            occurred_at=_aware(scenario.logical_start_at),
            recorded_at=now,
            payload_json={
                "scenarioId": str(scenario.id),
                "episodeDefinitionId": str(definition.id),
                "actorRole": actor_role,
            },
            payload_hash=hash_json(
                {
                    "scenarioId": str(scenario.id),
                    "episodeDefinitionId": str(definition.id),
                    "actorRole": actor_role,
                }
            ),
            sensitivity="synthetic",
            purpose_of_use="synthetic_evaluation",
        )
    )
    return run


async def _environment_context(
    session: AsyncSession,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[EnvironmentRun, SimulationScenario, EpisodeInstance]:
    query = select(EnvironmentRun).where(
        EnvironmentRun.organization_id == organization_id,
        EnvironmentRun.id == run_id,
    )
    if lock:
        query = query.with_for_update()
    run = await session.scalar(query)
    if run is None:
        raise HTTPException(status_code=404, detail="Environment run not found")
    scenario = await session.scalar(
        select(SimulationScenario).where(
            SimulationScenario.organization_id == organization_id,
            SimulationScenario.id == run.simulation_scenario_id,
            SimulationScenario.synthetic_only.is_(True),
        )
    )
    episode = await session.scalar(
        select(EpisodeInstance).where(
            EpisodeInstance.organization_id == organization_id,
            EpisodeInstance.id == run.episode_instance_id,
        )
    )
    if scenario is None or episode is None:
        raise RuntimeError("Environment run dependencies are incomplete")
    return run, scenario, episode


async def step_environment(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    run_id: uuid.UUID,
    expected_sequence: int,
    idempotency_key: str,
    action_type: str,
    reason_code: str | None,
    ai_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    run, scenario, episode = await _environment_context(
        session, organization_id, run_id, lock=True
    )
    action_key = environment_step_idempotency_key(run.id, idempotency_key)
    request_payload = {
        "expectedSequence": expected_sequence,
        "actionType": action_type,
        "reasonCode": reason_code,
        "aiRunId": str(ai_run_id) if ai_run_id else None,
    }
    request_hash = hash_json(request_payload)
    existing_action = await session.scalar(
        select(ActionAttempt).where(
            ActionAttempt.organization_id == organization_id,
            ActionAttempt.idempotency_key == action_key,
        )
    )
    if existing_action is not None:
        if existing_action.arguments_json.get("requestHash") != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Environment step idempotency key was reused with different input",
            )
        stored_receipt = existing_action.arguments_json.get("resultReceipt")
        if isinstance(stored_receipt, dict):
            return deepcopy(stored_receipt)
        existing_step = await session.scalar(
            select(EnvironmentStep).where(
                EnvironmentStep.organization_id == organization_id,
                EnvironmentStep.environment_run_id == run.id,
                EnvironmentStep.action_attempt_id == existing_action.id,
            )
        )
        if existing_step is None:
            raise RuntimeError("Environment step idempotency record is incomplete")
        return await environment_run_view(
            session,
            organization_id=organization_id,
            run_id=run.id,
            selected_step=existing_step,
        )
    if run.status != "running":
        raise HTTPException(status_code=409, detail="Environment run is terminal")
    if expected_sequence != run.current_step + 1:
        raise HTTPException(
            status_code=409,
            detail=f"Expected environment step {run.current_step + 1}",
        )
    max_steps = int(run.config_json.get("maxSteps", 10_000))
    if expected_sequence > max_steps:
        raise HTTPException(status_code=409, detail="Environment step limit exceeded")

    actor_role = str(run.config_json.get("actorRole", "environment_agent"))
    before_state = deepcopy(run.state_json)
    stage = str(before_state.get("stage", "unknown"))
    stage_rules = scenario.transition_rules_json.get(stage, {})
    rule = stage_rules.get(action_type)
    allowed = _allowed_actions(scenario, before_state, actor_role)
    is_allowed = isinstance(rule, dict) and action_type in allowed
    before_time = _parsed_time(before_state.get("simulatorTime"), scenario.logical_start_at)
    if is_allowed:
        advance_minutes = int(rule.get("advanceMinutes", 0))
        after_time = before_time + timedelta(minutes=max(advance_minutes, 0))
        after_state = {
            "stage": rule.get("nextStage", stage),
            "simulatorTime": after_time.isoformat(),
            "observation": deepcopy(rule.get("observation", {})),
            "supportKind": rule.get("supportKind", "simulated"),
        }
        reward_values = {
            str(key): Decimal(str(value))
            for key, value in dict(rule.get("rewards", {})).items()
        }
        hard_violations = [str(item) for item in rule.get("hardViolations", [])]
        terminated = bool(rule.get("terminated", False))
        termination_reason = rule.get("terminationReason") if terminated else None
        action_status = "succeeded"
        error_code = None
    else:
        after_time = before_time
        after_state = before_state
        default_invalid = scenario.reward_spec_json.get(
            "invalidAction",
            {"policy_compliance": -1, "safety": -1},
        )
        reward_values = {
            str(key): Decimal(str(value)) for key, value in default_invalid.items()
        }
        hard_violations = ["action_not_allowed_in_state"]
        terminated = False
        termination_reason = None
        action_status = "rejected"
        error_code = "action_not_allowed"

    support_kind = str(after_state.get("supportKind", "simulated"))
    if support_kind not in {
        "observed",
        "simulated",
        "expert",
        "unsupported_counterfactual",
    }:
        raise RuntimeError("Scenario emitted an invalid support kind")
    if support_kind == "unsupported_counterfactual":
        terminated = True
        termination_reason = "unsupported_counterfactual"
        episode.counterfactual_boundary_at = before_time
    max_duration_seconds = int(run.config_json.get("maxDurationSeconds", 0))
    if not terminated and expected_sequence >= max_steps:
        terminated = True
        termination_reason = "max_steps_reached"
    if (
        not terminated
        and max_duration_seconds > 0
        and after_time
        >= _aware(scenario.logical_start_at) + timedelta(seconds=max_duration_seconds)
    ):
        terminated = True
        termination_reason = "max_duration_reached"

    current_manifest = await session.scalar(
        select(ObservationManifest).where(
            ObservationManifest.organization_id == organization_id,
            ObservationManifest.episode_instance_id == episode.id,
            ObservationManifest.sequence == expected_sequence,
        )
    )
    if current_manifest is None:
        raise RuntimeError("Environment observation manifest is missing")

    event = await record_domain_event(
        session,
        organization_id=organization_id,
        event_type="environment.action.evaluated",
        aggregate_type="environment_run",
        aggregate_id=run.id,
        aggregate_sequence=expected_sequence + 1,
        actor_kind="agent",
        actor_user_id=requested_by_user_id,
        actor_role=actor_role,
        occurred_at=before_time,
        payload={
            "actionType": action_type,
            "fromStage": stage,
            "toStage": after_state.get("stage"),
            "allowed": is_allowed,
            "supportKind": support_kind,
            "terminated": terminated,
        },
        idempotency_key=action_key,
        correlation_id=str(run.id),
        sensitivity="synthetic",
        purpose_of_use="synthetic_evaluation",
    )
    decision = DecisionPoint(
        id=uuid.uuid5(run.id, f"decision:{expected_sequence}"),
        organization_id=organization_id,
        episode_instance_id=episode.id,
        sequence=expected_sequence,
        decision_type=f"environment.{stage}",
        observation_manifest_id=current_manifest.id,
        trigger_event_id=event.id,
        actor_kind="agent",
        actor_user_id=requested_by_user_id,
        actor_role=actor_role,
        available_actions_json=allowed,
        policy_refs_json=[],
        status="decided",
        opened_at=before_time,
        decided_at=before_time,
    )
    action = ActionAttempt(
        id=uuid.uuid5(run.id, f"action:{expected_sequence}:{action_key}"),
        organization_id=organization_id,
        decision_point_id=decision.id,
        sequence=1,
        actor_kind="agent",
        actor_user_id=requested_by_user_id,
        ai_run_id=ai_run_id,
        action_type=action_type,
        arguments_json={"requestHash": request_hash, "reasonCode": reason_code},
        idempotency_key=action_key,
        status="pending",
        attempted_at=before_time,
        executed_at=None,
        result_event_id=event.id,
        error_code=None,
        human_edit_diff_json={},
    )
    await session.flush([event])
    session.add(decision)
    await session.flush([decision])
    session.add(action)
    await session.flush([action])
    step = EnvironmentStep(
        id=uuid.uuid5(run.id, f"step:{expected_sequence}"),
        organization_id=organization_id,
        environment_run_id=run.id,
        step_number=expected_sequence,
        decision_point_id=decision.id,
        observation_manifest_id=current_manifest.id,
        action_attempt_id=action.id,
        simulator_time_before=before_time,
        simulator_time_after=after_time,
        state_before_hash=hash_json(before_state),
        state_after_hash=hash_json(after_state),
        support_kind=support_kind,
        terminated=terminated,
        termination_reason=termination_reason,
        latency_ms=max(int((time.perf_counter() - started) * 1_000), 0),
    )
    session.add_all(
        [
            step,
            EpisodeEventLink(
                id=uuid.uuid5(episode.id, f"event-link:{event.id}"),
                organization_id=organization_id,
                episode_instance_id=episode.id,
                domain_event_id=event.id,
                sequence=expected_sequence,
                role="environment_transition",
            ),
        ]
    )
    await session.flush([step])
    for component_name, value in reward_values.items():
        session.add(
            RewardComponent(
                id=uuid.uuid5(step.id, f"reward:{component_name}"),
                organization_id=organization_id,
                environment_step_id=step.id,
                component_name=component_name,
                evaluator_key=ENVIRONMENT_EVALUATOR,
                evaluator_version=ENVIRONMENT_EVALUATOR_VERSION,
                value=value,
                weight=Decimal("1"),
                hard_violation=bool(hard_violations),
                evidence_json={"codes": hard_violations},
                provenance_kind=support_kind,
                computed_at=utcnow(),
            )
        )
    await record_outcome(
        session,
        organization_id=organization_id,
        episode=episode,
        outcome_type="workflow_stage_transition",
        value={
            "fromStage": stage,
            "toStage": after_state.get("stage"),
            "actionType": action_type,
            "allowed": is_allowed,
            "terminated": terminated,
        },
        provenance_kind=support_kind,
        observed_at=after_time,
        decision=decision,
        action=action,
        source_event=event,
        simulator_version=scenario.simulator_versions_json.get("environment"),
        check_existing=False,
    )
    totals = {key: Decimal(str(value)) for key, value in run.total_reward_json.items()}
    for component_name, value in reward_values.items():
        totals[component_name] = totals.get(component_name, Decimal("0")) + value
    run.current_step = expected_sequence
    run.state_json = after_state
    run.total_reward_json = {key: float(value) for key, value in totals.items()}
    run.hard_violation_count += len(hard_violations)
    if terminated:
        run.status = "completed" if support_kind != "unsupported_counterfactual" else "terminated"
        run.ended_at = utcnow()
        run.termination_reason = termination_reason or "scenario_complete"
        episode.status = run.status
        episode.ended_at = after_time
        episode.end_event_id = event.id
    await create_observation_manifest(
        session,
        organization_id=organization_id,
        episode=episode,
        sequence=expected_sequence + 1,
        as_of_at=after_time,
        resources=[],
        synthetic_snapshot=after_state.get("observation", {}),
        purpose_of_use="synthetic_evaluation",
        sensitivity="synthetic",
    )
    await session.flush()
    response = await environment_run_view(
        session,
        organization_id=organization_id,
        run_id=run.id,
        selected_step=step,
    )
    if response["latest_step"] is not None:
        response["latest_step"]["action_status"] = action_status
    receipt = json.loads(canonical_json(response))
    action.status = action_status
    action.executed_at = after_time if is_allowed else None
    action.error_code = error_code
    action.arguments_json = {
        **action.arguments_json,
        "resultReceipt": receipt,
    }
    await session.flush([action])
    return deepcopy(receipt)


async def environment_run_view(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    selected_step: EnvironmentStep | None = None,
) -> dict[str, Any]:
    run, scenario, _episode = await _environment_context(session, organization_id, run_id)
    latest_step = selected_step
    if latest_step is None and run.current_step:
        latest_step = await session.scalar(
            select(EnvironmentStep).where(
                EnvironmentStep.organization_id == organization_id,
                EnvironmentStep.environment_run_id == run.id,
                EnvironmentStep.step_number == run.current_step,
            )
        )
    latest_action = None
    rewards: list[RewardComponent] = []
    if latest_step is not None:
        latest_action = await session.scalar(
            select(ActionAttempt).where(
                ActionAttempt.organization_id == organization_id,
                ActionAttempt.id == latest_step.action_attempt_id,
            )
        )
        rewards = list(
            await session.scalars(
                select(RewardComponent).where(
                    RewardComponent.organization_id == organization_id,
                    RewardComponent.environment_step_id == latest_step.id,
                )
            )
        )
    actor_role = str(run.config_json.get("actorRole", "environment_agent"))
    latest_reward = {item.component_name: float(item.value) for item in rewards}
    hard_codes = sorted(
        {
            str(code)
            for item in rewards
            if item.hard_violation
            for code in item.evidence_json.get("codes", [])
        }
    )
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "mode": run.mode,
            "actor_role": actor_role,
            "seed": run.seed,
            "sequence": run.current_step,
            "state_version": run.record_version,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "termination_reason": run.termination_reason,
            "scenario": {
                "slug": scenario.slug,
                "version": scenario.version,
                "simulator_versions": scenario.simulator_versions_json,
            },
        },
        "observation": deepcopy(run.state_json.get("observation", {})),
        "allowed_actions": _allowed_actions(scenario, run.state_json, actor_role)
        if run.status == "running"
        else [],
        "total_reward": run.total_reward_json,
        "hard_violation_count": run.hard_violation_count,
        "latest_step": (
            {
                "sequence": latest_step.step_number,
                "action_type": latest_action.action_type if latest_action else None,
                "action_status": latest_action.status if latest_action else None,
                "support_kind": latest_step.support_kind,
                "terminated": latest_step.terminated,
                "reward": latest_reward,
                "hard_violations": hard_codes,
            }
            if latest_step
            else None
        ),
    }


async def episode_catalog(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    rows = list(
        await session.scalars(
            select(EpisodeDefinition)
            .join(
                SimulationScenario,
                (SimulationScenario.organization_id == EpisodeDefinition.organization_id)
                & (SimulationScenario.episode_definition_id == EpisodeDefinition.id),
            )
            .where(
                EpisodeDefinition.organization_id == organization_id,
                EpisodeDefinition.status == "released",
                SimulationScenario.synthetic_only.is_(True),
                SimulationScenario.status == "released",
            )
            .distinct()
            .order_by(EpisodeDefinition.slug, EpisodeDefinition.version.desc())
            .limit(50)
        )
    )
    return [
        {
            "id": item.id,
            "slug": item.slug,
            "version": item.version,
            "name": item.name,
            "description": item.description,
            "episode_type": item.episode_type,
            "max_steps": item.max_steps,
            "max_duration_seconds": item.max_duration_seconds,
            "action_types": item.action_schema_json.get("actionTypes", []),
            "reward_components": item.reward_schema_json.get("components", []),
            "released_at": item.released_at,
        }
        for item in rows
    ]


async def dataset_manifest_catalog(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(DatasetRelease, func.count(DatasetReleaseItem.id))
            .outerjoin(
                DatasetReleaseItem,
                (DatasetReleaseItem.organization_id == DatasetRelease.organization_id)
                & (DatasetReleaseItem.dataset_release_id == DatasetRelease.id),
            )
            .where(
                DatasetRelease.organization_id == organization_id,
                DatasetRelease.legal_basis == "synthetic_data_only",
            )
            .group_by(DatasetRelease.id)
            .order_by(DatasetRelease.name, DatasetRelease.version.desc())
            .limit(50)
        )
    ).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "version": item.version,
            "status": item.status,
            "classification": "synthetic",
            "contains_phi": False,
            "purpose": item.intended_uses_json,
            "prohibited_uses": item.prohibited_uses_json,
            "schema_version": item.schema_version,
            "row_count": int(row_count),
            "hash": item.content_hash,
            "released_at": item.released_at,
        }
        for item, row_count in rows
    ]
