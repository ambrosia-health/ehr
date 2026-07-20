from __future__ import annotations

import hashlib
import json
import re
import uuid

import pytest
from sqlalchemy import func, select

from app.ai import run_ai
from app.database import SessionLocal
from app.learning import hash_json
from app.models import (
    ActionAttempt,
    AIInput,
    AIOutput,
    DecisionPoint,
    DomainEvent,
    EpisodeDefinition,
    EpisodeEventLink,
    ObservationManifest,
    ObservationResource,
    OutcomeObservation,
    ProposedAction,
)
from app.seed import canonical_ids, sid
from tests.test_workflows import _intake_body


def _provider_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "provider"}


def _biller_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "biller"}


def _patient_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "patient"}


def _query_count(response) -> int:
    match = re.search(r'desc="(\d+) queries"', response.headers.get("server-timing", ""))
    assert match, response.headers.get("server-timing")
    return int(match.group(1))


async def _complete_canonical_encounter(presenter_client):
    workspace_response = await presenter_client.get(
        "/api/demo/bootstrap",
        headers=_provider_headers(),
    )
    assert workspace_response.status_code == 200, workspace_response.text
    workspace = workspace_response.json()
    note_version = workspace["encounter"]["note"]["currentVersion"]
    body = {
        "proposedActionIds": [item["id"] for item in workspace["encounter"]["proposals"]],
        "attest": True,
        "signNote": True,
        "attestation": "Reviewed source records and approved all actions",
        "expectedNoteVersion": note_version["number"],
        "expectedNoteHash": note_version["contentHash"],
    }
    completed = await presenter_client.post(
        f"/api/encounters/{canonical_ids()['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json=body,
    )
    assert completed.status_code == 200, completed.text
    return workspace, body, completed


async def _decision_graph(
    session,
    *,
    event_type: str,
    decision_type: str,
    outcome_type: str,
) -> tuple[DomainEvent, DecisionPoint, ActionAttempt, OutcomeObservation]:
    event = await session.scalar(
        select(DomainEvent).where(
            DomainEvent.organization_id == canonical_ids()["organization_id"],
            DomainEvent.event_type == event_type,
        )
    )
    assert event is not None
    decision = await session.scalar(
        select(DecisionPoint).where(
            DecisionPoint.organization_id == canonical_ids()["organization_id"],
            DecisionPoint.trigger_event_id == event.id,
            DecisionPoint.decision_type == decision_type,
        )
    )
    assert decision is not None
    action = await session.scalar(
        select(ActionAttempt).where(
            ActionAttempt.organization_id == canonical_ids()["organization_id"],
            ActionAttempt.decision_point_id == decision.id,
        )
    )
    assert action is not None
    outcome = await session.scalar(
        select(OutcomeObservation).where(
            OutcomeObservation.organization_id == canonical_ids()["organization_id"],
            OutcomeObservation.source_event_id == event.id,
            OutcomeObservation.decision_point_id == decision.id,
            OutcomeObservation.action_attempt_id == action.id,
            OutcomeObservation.outcome_type == outcome_type,
        )
    )
    assert outcome is not None
    return event, decision, action, outcome


async def _logical_trajectory_counts(
    session,
    *,
    event: DomainEvent,
    decision: DecisionPoint,
    outcome: OutcomeObservation,
) -> tuple[int, int, int, int]:
    event_count = await session.scalar(
        select(func.count(DomainEvent.id)).where(
            DomainEvent.organization_id == event.organization_id,
            DomainEvent.event_type == event.event_type,
            DomainEvent.aggregate_type == event.aggregate_type,
            DomainEvent.aggregate_id == event.aggregate_id,
        )
    )
    decision_count = await session.scalar(
        select(func.count(DecisionPoint.id)).where(
            DecisionPoint.organization_id == decision.organization_id,
            DecisionPoint.episode_instance_id == decision.episode_instance_id,
            DecisionPoint.decision_type == decision.decision_type,
        )
    )
    action_count = await session.scalar(
        select(func.count(ActionAttempt.id))
        .join(DecisionPoint, DecisionPoint.id == ActionAttempt.decision_point_id)
        .where(
            DecisionPoint.organization_id == decision.organization_id,
            DecisionPoint.episode_instance_id == decision.episode_instance_id,
            DecisionPoint.decision_type == decision.decision_type,
        )
    )
    outcome_count = await session.scalar(
        select(func.count(OutcomeObservation.id)).where(
            OutcomeObservation.organization_id == outcome.organization_id,
            OutcomeObservation.episode_instance_id == outcome.episode_instance_id,
            OutcomeObservation.outcome_type == outcome.outcome_type,
        )
    )
    assert None not in (event_count, decision_count, action_count, outcome_count)
    return event_count, decision_count, action_count, outcome_count


async def test_ai_run_appends_hash_only_event_and_bounded_resource_refs() -> None:
    ids = canonical_ids()
    raw_marker = "Synthetic raw clinical marker that must not enter the event"
    context = {
        "patientId": str(ids["sarah_patient_id"]),
        "encounterId": str(ids["sarah_encounter_id"]),
        "patientName": "Sarah Mitchell",
        "clinicalText": raw_marker,
    }
    async with SessionLocal() as session:
        run, _output = await run_ai(
            session,
            organization_id=ids["organization_id"],
            capability="chart_summary",
            context=context,
            patient_id=ids["sarah_patient_id"],
            requested_by_user_id=sid("user:provider"),
        )
        await session.commit()
        run_id = run.id

    async with SessionLocal() as session:
        ai_input = await session.scalar(select(AIInput).where(AIInput.ai_run_id == run_id))
        ai_output = await session.scalar(select(AIOutput).where(AIOutput.ai_run_id == run_id))
        event = await session.scalar(
            select(DomainEvent).where(
                DomainEvent.aggregate_type == "ai_run",
                DomainEvent.aggregate_id == run_id,
                DomainEvent.event_type == "ai.run.completed",
            )
        )
        event_count = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.aggregate_type == "ai_run",
                DomainEvent.aggregate_id == run_id,
                DomainEvent.event_type == "ai.run.completed",
            )
        )
    assert ai_input and ai_output and event
    assert event_count == 1
    assert event.patient_id == ids["sarah_patient_id"]
    assert event.sensitivity == "restricted"
    assert event.purpose_of_use == "care_operations"
    assert set(event.payload_json) == {
        "capability",
        "promptVersion",
        "promptHash",
        "inputHash",
        "outputHash",
        "provider",
        "model",
        "fallbackUsed",
        "schemaValid",
        "minimumNecessary",
        "latencyMs",
    }
    canonical_input = json.dumps(context, sort_keys=True, default=str)
    assert event.payload_json["inputHash"] == hashlib.sha256(canonical_input.encode()).hexdigest()
    assert event.payload_json["outputHash"] == hash_json(ai_output.content_json)
    assert event.payload_hash == hash_json(event.payload_json)
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", event.payload_json[key])
        for key in ("promptHash", "inputHash", "outputHash")
    )
    refs = {item["resourceType"]: item for item in ai_input.resource_refs_json}
    assert ai_input.content_json == {
        "contextHash": event.payload_json["inputHash"],
        "contextKeys": sorted(context),
        "resourceRefCount": 2,
        "contentStored": False,
    }
    assert ai_input.content_hash == event.payload_json["inputHash"]
    assert set(refs) == {"encounter", "patient"}
    assert refs["encounter"]["resourceId"] == str(ids["sarah_encounter_id"])
    assert refs["patient"]["resourceId"] == str(ids["sarah_patient_id"])
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["referenceHash"]) for item in refs.values())
    persisted_input_text = json.dumps(
        {
            "content": ai_input.content_json,
            "resourceRefs": ai_input.resource_refs_json,
            "event": event.payload_json,
        },
        sort_keys=True,
    )
    assert raw_marker not in persisted_input_text
    assert "Sarah Mitchell" not in persisted_input_text


async def test_intake_capture_records_choice_set_hashes_outcome_and_retry(client) -> None:
    workspace = (await client.get("/api/demo/bootstrap", headers=_patient_headers())).json()
    slots = workspace["intake"]["availableSlots"]
    selected_slot_id = slots[0]["id"]
    body = _intake_body(selected_slot_id)
    first = await client.post(
        "/api/intake/submissions",
        headers=_patient_headers(),
        json=body,
    )
    assert first.status_code == 200, first.text
    assert _query_count(first) <= 65

    async with SessionLocal() as session:
        event, decision, action, outcome = await _decision_graph(
            session,
            event_type="intake.submission_completed",
            decision_type="patient_intake_submission",
            outcome_type="intake_submission_accepted",
        )
        resources = list(
            await session.scalars(
                select(ObservationResource).where(
                    ObservationResource.observation_manifest_id == decision.observation_manifest_id
                )
            )
        )
    assert event.actor_kind == "patient"
    assert event.actor_role == "patient"
    assert event.payload_hash == hash_json(event.payload_json)
    assert event.payload_json["selectedSlotId"] == selected_slot_id
    assert re.fullmatch(r"[0-9a-f]{64}", event.payload_json["submissionHash"])
    assert set(decision.available_actions_json) == {
        f"book_appointment_slot:{slot['id']}" for slot in slots
    }
    assert action.action_type == f"book_appointment_slot:{selected_slot_id}"
    assert action.arguments_json["selectedSlotId"] == selected_slot_id
    assert action.status == "succeeded"
    assert outcome.provenance_kind == "observed"
    assert outcome.value_json["accepted"] is True
    assert outcome.source_event_id == event.id
    assert {item.resource_type for item in resources} >= {"questionnaire", "appointment"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", item.content_hash) for item in resources)
    capture_text = json.dumps(
        {
            "event": event.payload_json,
            "action": action.arguments_json,
        },
        sort_keys=True,
    )
    for raw_value in (
        body["reason"],
        body["insuranceMemberId"],
        body["medications"][0],
    ):
        assert raw_value not in capture_text

    retry = await client.post(
        "/api/intake/submissions",
        headers=_patient_headers(),
        json=body,
    )
    assert retry.status_code == 200, retry.text
    async with SessionLocal() as session:
        counts = await _logical_trajectory_counts(
            session,
            event=event,
            decision=decision,
            outcome=outcome,
        )
    assert counts == (1, 1, 1, 1)


async def test_encounter_completion_captures_exact_proposals_note_version_and_retry(
    presenter_client,
) -> None:
    ids = canonical_ids()
    workspace, body, completed = await _complete_canonical_encounter(presenter_client)
    assert _query_count(completed) <= 90
    offered_ids = {uuid.UUID(item["id"]) for item in workspace["encounter"]["proposals"]}
    expected_note = workspace["encounter"]["note"]["currentVersion"]

    async with SessionLocal() as session:
        event, decision, action, outcome = await _decision_graph(
            session,
            event_type="encounter.review_completed",
            decision_type="encounter_review",
            outcome_type="encounter.review_execution",
        )
        proposals = list(
            await session.scalars(select(ProposedAction).where(ProposedAction.id.in_(offered_ids)))
        )
        resources = list(
            await session.scalars(
                select(ObservationResource).where(
                    ObservationResource.observation_manifest_id == decision.observation_manifest_id
                )
            )
        )
        manifest = await session.get(ObservationManifest, decision.observation_manifest_id)

    expected_selected = {
        str(item.id): {
            "id": str(item.id),
            "type": item.action_type,
            "version": item.proposal_version,
            "payloadHash": item.payload_hash,
        }
        for item in proposals
    }
    event_selected = {item["id"]: item for item in event.payload_json["selectedActions"]}
    action_selected = {item["id"]: item for item in action.arguments_json["selectedActions"]}
    assert set(expected_selected) == {str(item) for item in offered_ids}
    assert event.aggregate_id == ids["sarah_encounter_id"]
    assert event.payload_hash == hash_json(event.payload_json)
    assert event_selected == action_selected == expected_selected
    assert event.payload_json["rejectedActionIds"] == []
    assert action.arguments_json["rejectedActionIds"] == []
    assert set(decision.available_actions_json) == {item.action_type for item in proposals}
    assert action.action_type == "complete_encounter_review"
    assert action.expected_target_type == "encounter_note"
    assert action.expected_target_id == ids["sarah_note_id"]
    assert action.expected_target_version == expected_note["number"]
    assert event.payload_json["noteRef"] == {
        "id": str(ids["sarah_note_id"]),
        "version": expected_note["number"],
        "contentHash": expected_note["contentHash"],
        "signatureHash": event.payload_json["noteRef"]["signatureHash"],
    }
    assert re.fullmatch(r"[0-9a-f]{64}", event.payload_json["noteRef"]["signatureHash"])
    assert outcome.provenance_kind == "observed"
    assert outcome.value_json == {
        "status": "completed",
        "noteSigned": True,
        "consentVerified": True,
        "procedureRecorded": True,
        "pathologyOrderCreated": True,
        "specimenTracked": True,
        "aftercareSent": True,
        "pathologyTrackingTaskOpen": True,
        "claimStatus": "draft",
    }
    assert manifest and manifest.synthetic_snapshot_json == {}
    proposal_resources = {
        item.resource_id: item for item in resources if item.resource_type == "proposed_action"
    }
    assert set(proposal_resources) == offered_ids
    assert all(
        proposal_resources[item.id].resource_version == item.proposal_version
        and re.fullmatch(r"[0-9a-f]{64}", proposal_resources[item.id].content_hash)
        for item in proposals
    )
    note_resource = next(item for item in resources if item.resource_type == "note_version")
    assert note_resource.resource_version == expected_note["number"]
    assert note_resource.content_hash == expected_note["contentHash"]

    retry = await presenter_client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json=body,
    )
    assert retry.status_code == 200, retry.text
    async with SessionLocal() as session:
        counts = await _logical_trajectory_counts(
            session,
            event=event,
            decision=decision,
            outcome=outcome,
        )
    assert counts == (1, 1, 1, 1)


async def test_pathology_arrival_and_review_capture_linked_provenance_and_retries(
    presenter_client,
) -> None:
    await _complete_canonical_encounter(presenter_client)
    arrival = await presenter_client.post("/api/demo/triggers/pathology", json={})
    assert arrival.status_code == 200, arrival.text
    assert arrival.json()["created"] is True
    assert _query_count(arrival) <= 48
    result_id = uuid.UUID(arrival.json()["resultId"])

    async with SessionLocal() as session:
        event = await session.scalar(
            select(DomainEvent).where(
                DomainEvent.event_type == "pathology.result_received",
                DomainEvent.aggregate_id == result_id,
            )
        )
        assert event is not None
        link = await session.scalar(
            select(EpisodeEventLink).where(
                EpisodeEventLink.domain_event_id == event.id,
                EpisodeEventLink.role == "outcome",
            )
        )
        outcome = await session.scalar(
            select(OutcomeObservation).where(
                OutcomeObservation.source_event_id == event.id,
                OutcomeObservation.outcome_type == "pathology.result_available",
            )
        )
    assert link and outcome
    assert link.episode_instance_id == outcome.episode_instance_id
    assert event.actor_kind == "external_system"
    assert event.payload_hash == hash_json(event.payload_json)
    assert set(event.payload_json["sourceRefs"]) == {"procedure", "order", "specimen"}
    assert all(
        ref["version"] == 1 and re.fullmatch(r"[0-9a-f]{64}", ref["contentHash"])
        for ref in event.payload_json["sourceRefs"].values()
    )
    assert outcome.provenance_kind == "simulated"
    assert outcome.simulator_version == "simulated-pathology-2026.1"
    assert outcome.decision_point_id is None and outcome.action_attempt_id is None
    assert outcome.value_json == {
        "resultStatus": "final",
        "orderStatus": "resulted",
        "specimenStatus": "resulted",
        "reviewTaskStatus": "open",
        "messageDraftStatus": "proposed",
        "humanReviewRequired": True,
    }
    arrival_capture = json.dumps(event.payload_json, sort_keys=True)
    for forbidden in ("Sarah Mitchell", "No melanoma", "SYN-DP-"):
        assert forbidden not in arrival_capture

    repeated_arrival = await presenter_client.post("/api/demo/triggers/pathology", json={})
    assert repeated_arrival.status_code == 200
    assert repeated_arrival.json()["created"] is False
    assert repeated_arrival.json()["resultId"] == str(result_id)

    reviewed = await presenter_client.post(
        f"/api/pathology/results/{result_id}/review",
        headers=_provider_headers(),
        json={"notifyPatient": True, "createFollowup": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert _query_count(reviewed) <= 42
    async with SessionLocal() as session:
        review_event, decision, action, review_outcome = await _decision_graph(
            session,
            event_type="pathology.review_completed",
            decision_type="pathology_result_review",
            outcome_type="pathology_review_recorded",
        )
    assert review_event.aggregate_type == "pathology_review"
    assert review_event.payload_json["resultId"] == str(result_id)
    assert review_event.payload_json["selectedAction"] == (
        "review_pathology_and_notify_patient_and_create_followup"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", review_event.payload_json["executedMessageHash"])
    assert set(decision.available_actions_json) == {
        "review_pathology",
        "review_pathology_and_create_followup",
        "review_pathology_and_notify_patient",
        "review_pathology_and_notify_patient_and_create_followup",
    }
    assert action.expected_target_type == "diagnostic_result"
    assert action.expected_target_id == result_id
    assert action.human_edit_diff_json["edited"] is False
    assert review_outcome.provenance_kind == "observed"
    assert review_outcome.value_json["reviewRecorded"] is True
    assert review_outcome.value_json["patientNotificationRequested"] is True
    assert review_outcome.value_json["followupRequested"] is True

    repeated_review = await presenter_client.post(
        f"/api/pathology/results/{result_id}/review",
        headers=_provider_headers(),
        json={"notifyPatient": True, "createFollowup": True},
    )
    assert repeated_review.status_code == 200, repeated_review.text
    assert repeated_review.json()["reviewId"] == reviewed.json()["reviewId"]
    async with SessionLocal() as session:
        arrival_event_count = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.event_type == event.event_type,
                DomainEvent.aggregate_type == event.aggregate_type,
                DomainEvent.aggregate_id == event.aggregate_id,
            )
        )
        arrival_link_count = await session.scalar(
            select(func.count(EpisodeEventLink.id)).where(
                EpisodeEventLink.episode_instance_id == link.episode_instance_id,
                EpisodeEventLink.domain_event_id == event.id,
                EpisodeEventLink.role == "outcome",
            )
        )
        arrival_outcome_count = await session.scalar(
            select(func.count(OutcomeObservation.id)).where(
                OutcomeObservation.episode_instance_id == outcome.episode_instance_id,
                OutcomeObservation.outcome_type == outcome.outcome_type,
            )
        )
        review_counts = await _logical_trajectory_counts(
            session,
            event=review_event,
            decision=decision,
            outcome=review_outcome,
        )
    assert (arrival_event_count, arrival_link_count, arrival_outcome_count) == (1, 1, 1)
    assert review_counts == (1, 1, 1, 1)


async def test_denial_resubmission_capture_hashes_evidence_and_does_not_duplicate(client) -> None:
    workspace = (await client.get("/api/demo/bootstrap", headers=_biller_headers())).json()
    claim = next(
        item for item in workspace["claims"] if (item.get("denial") or {}).get("status") == "open"
    )
    claim_id = uuid.UUID(claim["id"])
    denial = claim["denial"]
    appeal_body = "Signed documentation supports the separately identifiable service."
    correction = "Append modifier 25 and attach signed documentation."
    body = {
        "appealBody": appeal_body,
        "correction": correction,
        "sourceTaskId": denial["assignedTaskId"],
    }
    first = await client.post(
        f"/api/claims/{claim_id}/correct-and-resubmit",
        headers=_biller_headers(),
        json=body,
    )
    assert first.status_code == 200, first.text
    assert _query_count(first) <= 46

    async with SessionLocal() as session:
        event, decision, action, outcome = await _decision_graph(
            session,
            event_type="claim.corrected_and_resubmitted",
            decision_type="denial_correction_and_resubmission",
            outcome_type="claim_resubmission_recorded",
        )
        resources = list(
            await session.scalars(
                select(ObservationResource).where(
                    ObservationResource.observation_manifest_id == decision.observation_manifest_id
                )
            )
        )
    assert event.patient_id is not None
    assert event.actor_kind == "human"
    assert event.actor_role == "biller"
    assert event.payload_json["claimId"] == str(claim_id)
    assert event.payload_json["denialId"] == denial["id"]
    assert event.payload_json["modifier"] == "25"
    assert re.fullmatch(r"[0-9a-f]{64}", event.payload_json["executedAppealHash"])
    assert re.fullmatch(r"[0-9a-f]{64}", event.payload_json["correctionHash"])
    assert decision.available_actions_json == ["correct_and_resubmit_claim"]
    assert action.action_type == "correct_and_resubmit_claim"
    assert action.proposed_action_id is None
    assert decision.displayed_proposal_id == uuid.UUID(event.payload_json["proposedActionId"])
    assert action.expected_target_type == "proposed_action"
    assert action.expected_target_id == decision.displayed_proposal_id
    assert action.expected_target_version == event.payload_json["proposalVersion"]
    assert (
        action.human_edit_diff_json["executedAppealHash"]
        == event.payload_json["executedAppealHash"]
    )
    assert outcome.provenance_kind == "observed"
    assert outcome.value_json["denialStatus"] == "resolved"
    assert outcome.value_json["appealStatus"] == "submitted"
    assert {item.resource_type for item in resources} >= {
        "claim",
        "denial",
        "proposed_action",
        "task",
        "claim_line",
    }
    capture_text = json.dumps(
        {
            "event": event.payload_json,
            "action": action.arguments_json,
            "edit": action.human_edit_diff_json,
        },
        sort_keys=True,
    )
    assert appeal_body not in capture_text
    assert correction not in capture_text

    retry = await client.post(
        f"/api/claims/{claim_id}/correct-and-resubmit",
        headers=_biller_headers(),
        json=body,
    )
    assert retry.status_code == 409
    async with SessionLocal() as session:
        counts = await _logical_trajectory_counts(
            session,
            event=event,
            decision=decision,
            outcome=outcome,
        )
    assert counts == (1, 1, 1, 1)


async def test_append_only_and_finalized_learning_evidence_guards() -> None:
    async with SessionLocal() as session:
        event = await session.scalar(
            select(DomainEvent).where(DomainEvent.event_type == "appointment.booked")
        )
        assert event is not None
        event.payload_json = {"tampered": True}
        with pytest.raises(ValueError, match="append-only evidence"):
            await session.flush()
        await session.rollback()

    async with SessionLocal() as session:
        definition = await session.get(
            EpisodeDefinition,
            canonical_ids()["learning_episode_definition_id"],
        )
        assert definition and definition.status == "released"
        definition.description = "Mutated finalized definition"
        with pytest.raises(ValueError, match="Finalized EpisodeDefinition evidence"):
            await session.flush()
        await session.rollback()
