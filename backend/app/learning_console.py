from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    ActionAttempt,
    AIInput,
    AIOutput,
    AIRun,
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
    PromptVersion,
    RewardComponent,
    SimulationScenario,
)

MAX_CONSOLE_PAGE_SIZE = 50
DEFAULT_CONSOLE_PAGE_SIZE = 20
_UUID_IN_ACTION = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_ACTION_CATEGORY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}")


def _bounded_limit(limit: int) -> int:
    if limit < 1:
        raise HTTPException(status_code=422, detail="Limit must be positive")
    return min(limit, MAX_CONSOLE_PAGE_SIZE)


def _bounded_offset(offset: int) -> int:
    if offset < 0:
        raise HTTPException(status_code=422, detail="Offset must not be negative")
    return offset


def _json_hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _tenant_json_hash(organization_id: uuid.UUID, value: Any) -> str:
    return _json_hash({"organization_id": str(organization_id), "value": value})


def _action_category(value: Any) -> str:
    """Reduce a potentially identifier-bearing action label to a safe category."""

    if not isinstance(value, str):
        return "action"
    uuid_match = _UUID_IN_ACTION.search(value)
    candidate = value[: uuid_match.start()] if uuid_match else value
    candidate = re.split(r"[:/?#=\s]", candidate, maxsplit=1)[0].rstrip("._-")
    match = _ACTION_CATEGORY.match(candidate)
    return match.group(0) if match else "action"


def _safe_available_actions(
    actions: list[Any],
    *,
    organization_id: uuid.UUID,
    synthetic: bool,
) -> list[Any]:
    if synthetic:
        return deepcopy(actions)
    return [
        {
            "type": _action_category(
                action.get("type", action.get("actionType", action.get("action_type")))
                if isinstance(action, dict)
                else action
            ),
            "action_hash": _tenant_json_hash(organization_id, action),
        }
        for action in actions
    ]


def _resource_identity_hash(
    organization_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
) -> str:
    return hashlib.sha256(f"{organization_id}:{resource_type}:{resource_id}".encode()).hexdigest()


def _episode_summary(
    episode: EpisodeInstance,
    definition: EpisodeDefinition,
) -> dict[str, Any]:
    # episode_key, patient_id, and metadata_json can contain live record identifiers.
    return {
        "id": episode.id,
        "source_kind": episode.source_kind,
        "status": episode.status,
        "seed": episode.seed,
        "started_at": episode.started_at,
        "ended_at": episode.ended_at,
        "counterfactual_boundary_at": episode.counterfactual_boundary_at,
        "record_version": episode.record_version,
        "definition": {
            "id": definition.id,
            "slug": definition.slug,
            "version": definition.version,
            "name": definition.name,
            "episode_type": definition.episode_type,
            "content_hash": definition.content_hash,
        },
    }


def _environment_run_summary(
    run: EnvironmentRun,
    scenario: SimulationScenario | None,
) -> dict[str, Any]:
    # run_key and arbitrary config/state are intentionally excluded from list views.
    return {
        "id": run.id,
        "status": run.status,
        "mode": run.mode,
        "agent_kind": run.agent_kind,
        "agent_model": run.agent_model,
        "code_version": run.code_version,
        "seed": run.seed,
        "current_step": run.current_step,
        "total_reward": deepcopy(run.total_reward_json),
        "hard_violation_count": run.hard_violation_count,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "termination_reason": run.termination_reason,
        "created_at": run.created_at,
        "scenario": (
            {
                "id": scenario.id,
                "slug": scenario.slug,
                "version": scenario.version,
                "content_hash": scenario.content_hash,
            }
            if scenario is not None
            else None
        ),
    }


def _dataset_summary(release: DatasetRelease, item_count: int) -> dict[str, Any]:
    # lineage_uri and item membership are deliberately absent. The console exposes
    # release governance, not a route to storage or to a patient-level cohort.
    classification = "synthetic" if release.legal_basis == "synthetic_data_only" else "governed"
    return {
        "id": release.id,
        "name": release.name,
        "version": release.version,
        "schema_version": release.schema_version,
        "status": release.status,
        "classification": classification,
        "intended_uses": deepcopy(release.intended_uses_json),
        "prohibited_uses": deepcopy(release.prohibited_uses_json),
        "legal_basis": release.legal_basis,
        "observation_cutoff_at": release.observation_cutoff_at,
        "outcome_window_days": release.outcome_window_days,
        "deidentification_method": release.deidentification_method,
        "schema_versions": deepcopy(release.schema_versions_json),
        "content_hash": release.content_hash,
        "lineage_hash": release.lineage_hash,
        "item_count": item_count,
        "released_at": release.released_at,
    }


async def _load_ai_provenance(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    ai_run_ids: set[uuid.UUID],
) -> dict[uuid.UUID, dict[str, Any]]:
    if not ai_run_ids:
        return {}

    run_rows = (
        await session.execute(
            select(AIRun, PromptVersion.version)
            .outerjoin(
                PromptVersion,
                (PromptVersion.organization_id == AIRun.organization_id)
                & (PromptVersion.id == AIRun.prompt_version_id),
            )
            .where(
                AIRun.organization_id == organization_id,
                AIRun.id.in_(ai_run_ids),
            )
            .order_by(AIRun.started_at.desc(), AIRun.id.desc())
            .limit(MAX_CONSOLE_PAGE_SIZE)
        )
    ).all()
    visible_ids = {run.id for run, _prompt_version in run_rows}
    if not visible_ids:
        return {}

    input_rows = list(
        await session.scalars(
            select(AIInput)
            .where(
                AIInput.organization_id == organization_id,
                AIInput.ai_run_id.in_(visible_ids),
            )
            .order_by(AIInput.created_at, AIInput.id)
            .limit(MAX_CONSOLE_PAGE_SIZE + 1)
        )
    )
    output_rows = list(
        await session.scalars(
            select(AIOutput)
            .where(
                AIOutput.organization_id == organization_id,
                AIOutput.ai_run_id.in_(visible_ids),
            )
            .order_by(AIOutput.created_at, AIOutput.id)
            .limit(MAX_CONSOLE_PAGE_SIZE + 1)
        )
    )
    inputs_truncated = len(input_rows) > MAX_CONSOLE_PAGE_SIZE
    outputs_truncated = len(output_rows) > MAX_CONSOLE_PAGE_SIZE
    input_rows = input_rows[:MAX_CONSOLE_PAGE_SIZE]
    output_rows = output_rows[:MAX_CONSOLE_PAGE_SIZE]
    inputs_by_run: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for item in input_rows:
        # content_json, resource_refs_json, and snapshot_ref may resolve live context.
        inputs_by_run[item.ai_run_id].append(
            {
                "input_type": item.input_type,
                "content_hash": item.content_hash,
                "minimum_necessary": item.minimum_necessary,
                "schema_version": item.schema_version,
            }
        )
    outputs_by_run: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for item in output_rows:
        # Hashing retains reproducibility without returning generated clinical content.
        outputs_by_run[item.ai_run_id].append(
            {
                "output_type": item.output_type,
                "output_hash": _json_hash(item.content_json),
                "schema_valid": item.schema_valid,
                "confidence": float(item.confidence),
            }
        )

    return {
        run.id: {
            "id": run.id,
            "capability": run.capability,
            "provider": run.provider,
            "model": run.model,
            "status": run.status,
            "fallback_used": run.fallback_used,
            "prompt_version_id": run.prompt_version_id,
            "prompt_version": prompt_version,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "latency_ms": run.latency_ms,
            "inputs": inputs_by_run.get(run.id, []),
            "outputs": outputs_by_run.get(run.id, []),
            "inputs_truncated": inputs_truncated,
            "outputs_truncated": outputs_truncated,
        }
        for run, prompt_version in run_rows
    }


async def learning_console_bootstrap(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 10,
) -> dict[str, Any]:
    """Return a bounded, tenant-scoped console overview without live content."""

    page_size = _bounded_limit(limit)
    metric_row = (
        await session.execute(
            select(
                select(func.count(EpisodeInstance.id))
                .where(EpisodeInstance.organization_id == organization_id)
                .scalar_subquery()
                .label("episodes"),
                select(func.count(EpisodeInstance.id))
                .where(
                    EpisodeInstance.organization_id == organization_id,
                    EpisodeInstance.status.in_(("pending", "running")),
                )
                .scalar_subquery()
                .label("active_episodes"),
                select(func.count(EnvironmentRun.id))
                .where(EnvironmentRun.organization_id == organization_id)
                .scalar_subquery()
                .label("environment_runs"),
                select(func.count(EnvironmentRun.id))
                .where(
                    EnvironmentRun.organization_id == organization_id,
                    EnvironmentRun.status.in_(("pending", "running")),
                )
                .scalar_subquery()
                .label("active_environment_runs"),
                select(func.count(AIRun.id))
                .where(AIRun.organization_id == organization_id)
                .scalar_subquery()
                .label("ai_runs"),
                select(func.count(AIRun.id))
                .where(
                    AIRun.organization_id == organization_id,
                    AIRun.status == "failed",
                )
                .scalar_subquery()
                .label("failed_ai_runs"),
                select(func.count(DatasetRelease.id))
                .where(DatasetRelease.organization_id == organization_id)
                .scalar_subquery()
                .label("dataset_releases"),
                select(func.count(func.distinct(RewardComponent.environment_step_id)))
                .where(
                    RewardComponent.organization_id == organization_id,
                    RewardComponent.hard_violation.is_(True),
                )
                .scalar_subquery()
                .label("hard_violations"),
            )
        )
    ).one()

    episode_rows = (
        await session.execute(
            select(EpisodeInstance, EpisodeDefinition)
            .join(
                EpisodeDefinition,
                (EpisodeDefinition.organization_id == EpisodeInstance.organization_id)
                & (EpisodeDefinition.id == EpisodeInstance.episode_definition_id),
            )
            .where(EpisodeInstance.organization_id == organization_id)
            .order_by(EpisodeInstance.created_at.desc(), EpisodeInstance.id.desc())
            .limit(page_size)
        )
    ).all()
    environment_rows = (
        await session.execute(
            select(EnvironmentRun, SimulationScenario)
            .outerjoin(
                SimulationScenario,
                (SimulationScenario.organization_id == EnvironmentRun.organization_id)
                & (SimulationScenario.id == EnvironmentRun.simulation_scenario_id),
            )
            .where(EnvironmentRun.organization_id == organization_id)
            .order_by(EnvironmentRun.created_at.desc(), EnvironmentRun.id.desc())
            .limit(page_size)
        )
    ).all()
    recent_ai_ids = list(
        await session.scalars(
            select(AIRun.id)
            .where(AIRun.organization_id == organization_id)
            .order_by(AIRun.started_at.desc(), AIRun.id.desc())
            .limit(page_size)
        )
    )
    ai_provenance = await _load_ai_provenance(
        session,
        organization_id=organization_id,
        ai_run_ids=set(recent_ai_ids),
    )
    datasets = (
        await session.execute(
            select(DatasetRelease, func.count(DatasetReleaseItem.id))
            .outerjoin(
                DatasetReleaseItem,
                (DatasetReleaseItem.organization_id == DatasetRelease.organization_id)
                & (DatasetReleaseItem.dataset_release_id == DatasetRelease.id),
            )
            .where(DatasetRelease.organization_id == organization_id)
            .group_by(DatasetRelease.id)
            .order_by(DatasetRelease.created_at.desc(), DatasetRelease.id.desc())
            .limit(page_size)
        )
    ).all()

    return {
        "overview": {
            "episode_count": int(metric_row.episodes or 0),
            "active_episode_count": int(metric_row.active_episodes or 0),
            "environment_run_count": int(metric_row.environment_runs or 0),
            "active_environment_run_count": int(metric_row.active_environment_runs or 0),
            "ai_run_count": int(metric_row.ai_runs or 0),
            "failed_ai_run_count": int(metric_row.failed_ai_runs or 0),
            "dataset_release_count": int(metric_row.dataset_releases or 0),
            "hard_violation_count": int(metric_row.hard_violations or 0),
        },
        "recent_episodes": [
            _episode_summary(episode, definition) for episode, definition in episode_rows
        ],
        "recent_environment_runs": [
            _environment_run_summary(run, scenario) for run, scenario in environment_rows
        ],
        "recent_ai_runs": [
            ai_provenance[run_id] for run_id in recent_ai_ids if run_id in ai_provenance
        ],
        "datasets": [
            _dataset_summary(release, int(item_count)) for release, item_count in datasets
        ],
        "limit": page_size,
    }


def _safe_observation(
    manifest: ObservationManifest,
    resources: list[ObservationResource],
    *,
    organization_id: uuid.UUID,
    synthetic: bool,
    collection_truncated: bool = False,
) -> dict[str, Any]:
    visible_resources = resources[:MAX_CONSOLE_PAGE_SIZE]
    result = {
        "id": manifest.id,
        "sequence": manifest.sequence,
        "as_of_at": manifest.as_of_at,
        "recorded_cutoff_at": manifest.recorded_cutoff_at,
        "schema_version": manifest.schema_version,
        "manifest_hash": manifest.manifest_hash,
        "sensitivity": manifest.sensitivity,
        "purpose_of_use": manifest.purpose_of_use,
        "resources": [
            {
                "sequence": item.sequence,
                "resource_type": item.resource_type,
                "resource_identity_hash": _resource_identity_hash(
                    organization_id,
                    item.resource_type,
                    item.resource_id,
                ),
                "resource_version": item.resource_version,
                "effective_at": item.effective_at,
                "recorded_at": item.recorded_at,
                "content_hash": item.content_hash,
            }
            for item in visible_resources
        ],
        "resource_count": None if collection_truncated else len(resources),
        "resource_count_returned": len(visible_resources),
        "resources_truncated": collection_truncated or len(resources) > MAX_CONSOLE_PAGE_SIZE,
    }
    if synthetic and manifest.sensitivity == "synthetic":
        result["synthetic_snapshot"] = deepcopy(manifest.synthetic_snapshot_json)
    return result


def _safe_action(
    action: ActionAttempt,
    ai_provenance: dict[uuid.UUID, dict[str, Any]],
    *,
    organization_id: uuid.UUID,
    synthetic: bool,
) -> dict[str, Any]:
    result = {
        "id": action.id,
        "sequence": action.sequence,
        "action_type": (
            action.action_type if synthetic else _action_category(action.action_type)
        ),
        "actor_kind": action.actor_kind,
        "status": action.status,
        "attempted_at": action.attempted_at,
        "executed_at": action.executed_at,
        "error_code": action.error_code,
        "proposal_version": action.proposal_version,
        "expected_target_type": (
            action.expected_target_type
            if synthetic or action.expected_target_type is None
            else _action_category(action.expected_target_type)
        ),
        "expected_target_version": action.expected_target_version,
        "arguments_hash": _json_hash(action.arguments_json),
        "human_edit_hash": (
            _json_hash(action.human_edit_diff_json) if action.human_edit_diff_json else None
        ),
        "result_event_id": action.result_event_id,
        "ai_provenance": (
            ai_provenance.get(action.ai_run_id) if action.ai_run_id is not None else None
        ),
    }
    if not synthetic:
        result["action_type_hash"] = _tenant_json_hash(organization_id, action.action_type)
        result["expected_target_type_hash"] = (
            _tenant_json_hash(organization_id, action.expected_target_type)
            if action.expected_target_type is not None
            else None
        )
    return result


def _safe_policy_refs(policy_refs: list[Any]) -> list[dict[str, Any]]:
    safe_keys = {
        "automationPolicyId",
        "contentHash",
        "key",
        "policyId",
        "policyVersionId",
        "slug",
        "version",
        "automation_policy_id",
        "content_hash",
        "policy_id",
        "policy_version_id",
    }
    return [
        {key: deepcopy(value) for key, value in item.items() if key in safe_keys}
        for item in policy_refs
        if isinstance(item, dict)
    ]


async def learning_console_episode_trajectory(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    episode_id: uuid.UUID,
    offset: int = 0,
    limit: int = DEFAULT_CONSOLE_PAGE_SIZE,
) -> dict[str, Any]:
    """Reconstruct a bounded trajectory page without resolving live resources."""

    page_offset = _bounded_offset(offset)
    page_size = _bounded_limit(limit)
    episode_row = (
        await session.execute(
            select(EpisodeInstance, EpisodeDefinition)
            .join(
                EpisodeDefinition,
                (EpisodeDefinition.organization_id == EpisodeInstance.organization_id)
                & (EpisodeDefinition.id == EpisodeInstance.episode_definition_id),
            )
            .where(
                EpisodeInstance.organization_id == organization_id,
                EpisodeInstance.id == episode_id,
            )
        )
    ).one_or_none()
    if episode_row is None:
        raise HTTPException(status_code=404, detail="Learning episode not found")
    episode, definition = episode_row
    synthetic = episode.source_kind == "synthetic"

    decision_rows = list(
        await session.scalars(
            select(DecisionPoint)
            .where(
                DecisionPoint.organization_id == organization_id,
                DecisionPoint.episode_instance_id == episode.id,
            )
            .order_by(DecisionPoint.sequence, DecisionPoint.id)
            .offset(page_offset)
            .limit(page_size + 1)
        )
    )
    decisions_have_more = len(decision_rows) > page_size
    decisions = decision_rows[:page_size]
    decision_ids = {item.id for item in decisions}
    manifest_ids = {item.observation_manifest_id for item in decisions}

    manifests = (
        list(
            await session.scalars(
                select(ObservationManifest)
                .where(
                    ObservationManifest.organization_id == organization_id,
                    ObservationManifest.episode_instance_id == episode.id,
                    ObservationManifest.id.in_(manifest_ids),
                )
                .order_by(ObservationManifest.sequence, ObservationManifest.id)
            )
        )
        if manifest_ids
        else []
    )
    resources = (
        list(
            await session.scalars(
                select(ObservationResource)
                .where(
                    ObservationResource.organization_id == organization_id,
                    ObservationResource.observation_manifest_id.in_(manifest_ids),
                )
                .order_by(
                    ObservationResource.observation_manifest_id,
                    ObservationResource.sequence,
                )
                .limit(len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE + 1)
            )
        )
        if manifest_ids
        else []
    )
    resources_globally_truncated = len(resources) > len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE
    resources = resources[: len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE]
    actions = (
        list(
            await session.scalars(
                select(ActionAttempt)
                .where(
                    ActionAttempt.organization_id == organization_id,
                    ActionAttempt.decision_point_id.in_(decision_ids),
                )
                .order_by(ActionAttempt.decision_point_id, ActionAttempt.sequence)
                .limit(len(decision_ids) * MAX_CONSOLE_PAGE_SIZE + 1)
            )
        )
        if decision_ids
        else []
    )
    actions_globally_truncated = len(actions) > len(decision_ids) * MAX_CONSOLE_PAGE_SIZE
    actions = actions[: len(decision_ids) * MAX_CONSOLE_PAGE_SIZE]
    ai_provenance = await _load_ai_provenance(
        session,
        organization_id=organization_id,
        ai_run_ids={item.ai_run_id for item in actions if item.ai_run_id is not None},
    )

    resources_by_manifest: dict[uuid.UUID, list[ObservationResource]] = defaultdict(list)
    for item in resources:
        resources_by_manifest[item.observation_manifest_id].append(item)
    manifest_by_id = {item.id: item for item in manifests}
    actions_by_decision: dict[uuid.UUID, list[ActionAttempt]] = defaultdict(list)
    for item in actions:
        actions_by_decision[item.decision_point_id].append(item)

    action_ids = {item.id for item in actions}
    event_ids = {
        event_id
        for event_id in (
            *(item.trigger_event_id for item in decisions),
            *(item.result_event_id for item in actions),
        )
        if event_id is not None
    }
    event_rows = (
        (
            await session.execute(
                select(EpisodeEventLink, DomainEvent)
                .join(
                    DomainEvent,
                    (DomainEvent.organization_id == EpisodeEventLink.organization_id)
                    & (DomainEvent.id == EpisodeEventLink.domain_event_id),
                )
                .where(
                    EpisodeEventLink.organization_id == organization_id,
                    EpisodeEventLink.episode_instance_id == episode.id,
                    EpisodeEventLink.domain_event_id.in_(event_ids),
                )
                .order_by(EpisodeEventLink.sequence, EpisodeEventLink.id)
                .limit(len(event_ids))
            )
        ).all()
        if event_ids
        else []
    )
    event_by_id = {event.id: (link, event) for link, event in event_rows}

    outcome_associations = [OutcomeObservation.decision_point_id.in_(decision_ids)]
    if action_ids:
        outcome_associations.append(OutcomeObservation.action_attempt_id.in_(action_ids))
    outcome_page_cap = len(decision_ids) * MAX_CONSOLE_PAGE_SIZE
    outcome_rows = (
        list(
            await session.scalars(
                select(OutcomeObservation)
                .where(
                    OutcomeObservation.organization_id == organization_id,
                    OutcomeObservation.episode_instance_id == episode.id,
                    or_(*outcome_associations),
                )
                .order_by(
                    OutcomeObservation.decision_point_id,
                    OutcomeObservation.observed_at,
                    OutcomeObservation.id,
                )
                .limit(outcome_page_cap + 1)
            )
        )
        if decision_ids
        else []
    )
    outcomes_truncated = (
        len(outcome_rows) > outcome_page_cap or actions_globally_truncated
    )
    outcomes = outcome_rows[:outcome_page_cap]
    action_to_decision = {item.id: item.decision_point_id for item in actions}
    outcomes_by_decision: dict[uuid.UUID, list[OutcomeObservation]] = defaultdict(list)
    for outcome in outcomes:
        owner_id = (
            outcome.decision_point_id
            if outcome.decision_point_id in decision_ids
            else None
        ) or (
            action_to_decision.get(outcome.action_attempt_id)
            if outcome.action_attempt_id is not None
            else None
        )
        if owner_id in decision_ids:
            outcomes_by_decision[owner_id].append(outcome)

    def present_outcome(outcome: OutcomeObservation) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": outcome.id,
            "decision_point_id": outcome.decision_point_id,
            "action_attempt_id": outcome.action_attempt_id,
            "outcome_type": outcome.outcome_type,
            "provenance_kind": outcome.provenance_kind,
            "observed_at": outcome.observed_at,
            "window_start_at": outcome.window_start_at,
            "window_end_at": outcome.window_end_at,
            "source_resource_type": outcome.source_resource_type,
            "source_resource_version": outcome.source_resource_version,
            "source_event_id": outcome.source_event_id,
            "simulator_version": outcome.simulator_version,
            "confidence": float(outcome.confidence),
            "content_hash": outcome.content_hash,
        }
        if synthetic:
            payload["value"] = deepcopy(outcome.value_json)
        return payload

    decision_payloads: list[dict[str, Any]] = []
    event_payloads: list[dict[str, Any]] = []
    outcome_payloads: list[dict[str, Any]] = []
    for decision in decisions:
        manifest = manifest_by_id.get(decision.observation_manifest_id)
        if manifest is None:
            raise RuntimeError("Decision observation manifest is incomplete")
        attempts = actions_by_decision.get(decision.id, [])
        selected = next(
            (
                item
                for item in reversed(attempts)
                if item.status in {"succeeded", "rejected", "no_action"}
            ),
            attempts[-1] if attempts else None,
        )
        associated_events: list[dict[str, Any]] = []
        seen_event_ids: set[uuid.UUID] = set()
        event_candidates = [
            *(
                [(selected.result_event_id, "result", selected.id)]
                if selected is not None and selected.result_event_id is not None
                else []
            ),
            *[
                (attempt.result_event_id, "result", attempt.id)
                for attempt in attempts
                if attempt.result_event_id is not None and attempt is not selected
            ],
            *(
                [(decision.trigger_event_id, "trigger", None)]
                if decision.trigger_event_id is not None
                else []
            ),
        ]
        for event_id, association, action_attempt_id in event_candidates:
            if event_id in seen_event_ids or event_id not in event_by_id:
                continue
            seen_event_ids.add(event_id)
            link, event = event_by_id[event_id]
            associated_events.append(
                {
                    "id": event.id,
                    # The console joins events to the owning decision, so the frontend
                    # can concatenate decision pages without a second event cursor.
                    "sequence": decision.sequence,
                    "episode_sequence": link.sequence,
                    "decision_point_id": decision.id,
                    "action_attempt_id": action_attempt_id,
                    "association": association,
                    "role": link.role,
                    "event_type": event.event_type,
                    "schema_version": event.schema_version,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_identity_hash": _resource_identity_hash(
                        organization_id,
                        event.aggregate_type,
                        event.aggregate_id,
                    ),
                    "aggregate_sequence": event.aggregate_sequence,
                    "actor_kind": event.actor_kind,
                    "actor_role": event.actor_role,
                    "occurred_at": event.occurred_at,
                    "effective_at": event.effective_at,
                    "recorded_at": event.recorded_at,
                    "payload_hash": event.payload_hash,
                    "sensitivity": event.sensitivity,
                    "purpose_of_use": event.purpose_of_use,
                }
            )
        decision_outcomes = [
            present_outcome(outcome) for outcome in outcomes_by_decision.get(decision.id, [])
        ]
        event_payloads.extend(associated_events)
        outcome_payloads.extend(decision_outcomes)
        decision_payloads.append(
            {
                "id": decision.id,
                "sequence": decision.sequence,
                "decision_type": decision.decision_type,
                "status": decision.status,
                "actor_kind": decision.actor_kind,
                "actor_role": decision.actor_role,
                "opened_at": decision.opened_at,
                "decided_at": decision.decided_at,
                "recommendation_rendered_at": decision.recommendation_rendered_at,
                "available_actions": _safe_available_actions(
                    decision.available_actions_json,
                    organization_id=organization_id,
                    synthetic=synthetic,
                ),
                "policy_refs": _safe_policy_refs(decision.policy_refs_json),
                "policy_refs_hash": _json_hash(decision.policy_refs_json),
                "observation": _safe_observation(
                    manifest,
                    resources_by_manifest.get(manifest.id, []),
                    organization_id=organization_id,
                    synthetic=synthetic,
                    collection_truncated=resources_globally_truncated,
                ),
                "selected_action": (
                    _safe_action(
                        selected,
                        ai_provenance,
                        organization_id=organization_id,
                        synthetic=synthetic,
                    )
                    if selected is not None
                    else None
                ),
                "action_attempts": [
                    _safe_action(
                        item,
                        ai_provenance,
                        organization_id=organization_id,
                        synthetic=synthetic,
                    )
                    for item in attempts[:MAX_CONSOLE_PAGE_SIZE]
                ],
                "action_attempts_truncated": actions_globally_truncated
                or len(attempts) > MAX_CONSOLE_PAGE_SIZE,
                "events": associated_events,
                "outcomes": decision_outcomes,
                "outcomes_truncated": outcomes_truncated,
            }
        )
    return {
        "episode": _episode_summary(episode, definition),
        "decisions": decision_payloads,
        "events": event_payloads,
        "outcomes": outcome_payloads,
        "pagination": {
            "offset": page_offset,
            "limit": page_size,
            "next_offset": page_offset + len(decisions) if decisions_have_more else None,
            "has_more": {
                "decisions": decisions_have_more,
                "events": False,
                "outcomes": False,
            },
            "scope": "decision_page",
            "events_truncated": actions_globally_truncated,
            "outcomes_truncated": outcomes_truncated,
        },
    }


async def learning_console_environment_run_history(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    after_step: int = 0,
    limit: int = DEFAULT_CONSOLE_PAGE_SIZE,
) -> dict[str, Any]:
    """Return a bounded environment run page with reward and AI provenance."""

    if after_step < 0:
        raise HTTPException(status_code=422, detail="Step cursor must not be negative")
    page_size = _bounded_limit(limit)
    run_row = (
        await session.execute(
            select(EnvironmentRun, SimulationScenario, EpisodeInstance)
            .outerjoin(
                SimulationScenario,
                (SimulationScenario.organization_id == EnvironmentRun.organization_id)
                & (SimulationScenario.id == EnvironmentRun.simulation_scenario_id),
            )
            .outerjoin(
                EpisodeInstance,
                (EpisodeInstance.organization_id == EnvironmentRun.organization_id)
                & (EpisodeInstance.id == EnvironmentRun.episode_instance_id),
            )
            .where(
                EnvironmentRun.organization_id == organization_id,
                EnvironmentRun.id == run_id,
            )
        )
    ).one_or_none()
    if run_row is None:
        raise HTTPException(status_code=404, detail="Environment run not found")
    run, scenario, episode = run_row
    synthetic = episode is not None and episode.source_kind == "synthetic"

    step_rows = list(
        await session.scalars(
            select(EnvironmentStep)
            .where(
                EnvironmentStep.organization_id == organization_id,
                EnvironmentStep.environment_run_id == run.id,
                EnvironmentStep.step_number > after_step,
            )
            .order_by(EnvironmentStep.step_number, EnvironmentStep.id)
            .limit(page_size + 1)
        )
    )
    has_more = len(step_rows) > page_size
    steps = step_rows[:page_size]
    action_ids = {item.action_attempt_id for item in steps if item.action_attempt_id is not None}
    decision_ids = {item.decision_point_id for item in steps if item.decision_point_id is not None}
    manifest_ids = {item.observation_manifest_id for item in steps}
    step_ids = {item.id for item in steps}

    actions = (
        list(
            await session.scalars(
                select(ActionAttempt).where(
                    ActionAttempt.organization_id == organization_id,
                    ActionAttempt.id.in_(action_ids),
                )
            )
        )
        if action_ids
        else []
    )
    decisions = (
        list(
            await session.scalars(
                select(DecisionPoint).where(
                    DecisionPoint.organization_id == organization_id,
                    DecisionPoint.id.in_(decision_ids),
                )
            )
        )
        if decision_ids
        else []
    )
    manifests = (
        list(
            await session.scalars(
                select(ObservationManifest).where(
                    ObservationManifest.organization_id == organization_id,
                    ObservationManifest.id.in_(manifest_ids),
                )
            )
        )
        if manifest_ids
        else []
    )
    resources = (
        list(
            await session.scalars(
                select(ObservationResource)
                .where(
                    ObservationResource.organization_id == organization_id,
                    ObservationResource.observation_manifest_id.in_(manifest_ids),
                )
                .order_by(
                    ObservationResource.observation_manifest_id,
                    ObservationResource.sequence,
                )
                .limit(len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE + 1)
            )
        )
        if manifest_ids
        else []
    )
    resources_globally_truncated = len(resources) > len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE
    resources = resources[: len(manifest_ids) * MAX_CONSOLE_PAGE_SIZE]
    rewards = (
        list(
            await session.scalars(
                select(RewardComponent)
                .where(
                    RewardComponent.organization_id == organization_id,
                    RewardComponent.environment_step_id.in_(step_ids),
                )
                .order_by(RewardComponent.environment_step_id, RewardComponent.component_name)
                .limit(len(step_ids) * MAX_CONSOLE_PAGE_SIZE + 1)
            )
        )
        if step_ids
        else []
    )
    rewards_globally_truncated = len(rewards) > len(step_ids) * MAX_CONSOLE_PAGE_SIZE
    rewards = rewards[: len(step_ids) * MAX_CONSOLE_PAGE_SIZE]
    ai_provenance = await _load_ai_provenance(
        session,
        organization_id=organization_id,
        ai_run_ids={item.ai_run_id for item in actions if item.ai_run_id is not None},
    )

    action_by_id = {item.id: item for item in actions}
    decision_by_id = {item.id: item for item in decisions}
    manifest_by_id = {item.id: item for item in manifests}
    resources_by_manifest: dict[uuid.UUID, list[ObservationResource]] = defaultdict(list)
    for item in resources:
        resources_by_manifest[item.observation_manifest_id].append(item)
    rewards_by_step: dict[uuid.UUID, list[RewardComponent]] = defaultdict(list)
    for item in rewards:
        rewards_by_step[item.environment_step_id].append(item)

    step_payloads: list[dict[str, Any]] = []
    for step in steps:
        manifest = manifest_by_id.get(step.observation_manifest_id)
        if manifest is None:
            raise RuntimeError("Environment step observation manifest is incomplete")
        action = action_by_id.get(step.action_attempt_id)
        decision = decision_by_id.get(step.decision_point_id)
        step_rewards = rewards_by_step.get(step.id, [])
        hard_codes = sorted(
            {
                str(code)
                for reward in step_rewards
                if reward.hard_violation
                for code in reward.evidence_json.get("codes", [])
            }
        )
        step_payloads.append(
            {
                "id": step.id,
                "step_number": step.step_number,
                "simulator_time_before": step.simulator_time_before,
                "simulator_time_after": step.simulator_time_after,
                "state_before_hash": step.state_before_hash,
                "state_after_hash": step.state_after_hash,
                "support_kind": step.support_kind,
                "terminated": step.terminated,
                "termination_reason": step.termination_reason,
                "latency_ms": step.latency_ms,
                "observation": _safe_observation(
                    manifest,
                    resources_by_manifest.get(manifest.id, []),
                    organization_id=organization_id,
                    synthetic=synthetic,
                    collection_truncated=resources_globally_truncated,
                ),
                "decision": (
                    {
                        "id": decision.id,
                        "decision_type": decision.decision_type,
                        "status": decision.status,
                        "actor_kind": decision.actor_kind,
                        "actor_role": decision.actor_role,
                        "available_actions": _safe_available_actions(
                            decision.available_actions_json,
                            organization_id=organization_id,
                            synthetic=synthetic,
                        ),
                        "policy_refs": _safe_policy_refs(decision.policy_refs_json),
                        "policy_refs_hash": _json_hash(decision.policy_refs_json),
                    }
                    if decision is not None
                    else None
                ),
                "action": (
                    _safe_action(
                        action,
                        ai_provenance,
                        organization_id=organization_id,
                        synthetic=synthetic,
                    )
                    if action is not None
                    else None
                ),
                "rewards": [
                    {
                        "component_name": reward.component_name,
                        "value": float(reward.value),
                        "weight": float(reward.weight),
                        "hard_violation": reward.hard_violation,
                        "evaluator_key": reward.evaluator_key,
                        "evaluator_version": reward.evaluator_version,
                        "provenance_kind": reward.provenance_kind,
                        "computed_at": reward.computed_at,
                        "evidence_codes": [
                            str(code) for code in reward.evidence_json.get("codes", [])
                        ],
                    }
                    for reward in step_rewards[:MAX_CONSOLE_PAGE_SIZE]
                ],
                "rewards_truncated": rewards_globally_truncated
                or len(step_rewards) > MAX_CONSOLE_PAGE_SIZE,
                "hard_violations": hard_codes,
            }
        )

    config = run.config_json if isinstance(run.config_json, dict) else {}
    run_payload = _environment_run_summary(run, scenario)
    run_payload["episode_instance_id"] = run.episode_instance_id
    run_payload["episode_definition_id"] = run.episode_definition_id
    run_payload["dataset_release_id"] = run.dataset_release_id
    run_payload["prompt_version_id"] = run.prompt_version_id
    run_payload["configuration"] = {
        "actor_role": config.get("actorRole"),
        "scenario_hash": config.get("scenarioHash"),
        "max_steps": config.get("maxSteps"),
        "max_duration_seconds": config.get("maxDurationSeconds"),
    }
    if synthetic:
        run_payload["current_state"] = deepcopy(run.state_json)

    return {
        "run": run_payload,
        "steps": step_payloads,
        "pagination": {
            "after_step": after_step,
            "limit": page_size,
            "next_after_step": steps[-1].step_number if has_more and steps else None,
            "has_more": has_more,
        },
    }
