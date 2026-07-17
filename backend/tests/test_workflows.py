from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal, engine
from app.main import app
from app.models import (
    Appeal,
    Approval,
    Claim,
    ClaimEvent,
    Denial,
    DiagnosticResult,
    EncounterNote,
    Message,
    MessageDraft,
    NoteVersion,
    Order,
    PatientBalance,
    Payment,
    Procedure,
    ProposedAction,
    ProvenanceRecord,
    Specimen,
    Task,
    User,
)
from app.security import DemoIdentityProvider
from app.seed import canonical_ids, sid


def _patient_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "patient"}


def _provider_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "provider"}


def _biller_headers() -> dict[str, str]:
    return {"X-Demo-Persona": "biller"}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def _bootstrap(client, persona: str) -> dict:
    response = await client.get("/api/demo/bootstrap", headers={"X-Demo-Persona": persona})
    assert response.status_code == 200, response.text
    return response.json()


def _intake_body(slot_id: str, *, urgent_signs: list[str] | None = None) -> dict:
    return {
        "reason": "Changing mole on my left posterior shoulder",
        "firstNoticed": "3–6 months ago",
        "change": ["Wider or larger", "Darker color"],
        "symptoms": ["Itching"],
        "urgentSigns": urgent_signs or [],
        "appointmentSlot": slot_id,
        "insurancePayer": "Blue Horizon PPO",
        "insuranceMemberId": "BHP74209183",
        "medications": ["Sertraline 50 mg daily"],
        "allergies": ["Adhesive tape — rash"],
        "personalSkinCancerHistory": "None",
        "familySkinCancerHistory": "Father had melanoma at 61",
        "pharmacy": "Hudson Community Pharmacy, New York",
        "consents": {"treatment": True, "privacy": True, "photography": True},
    }


async def test_intake_validates_consents_slots_triage_and_retry(client) -> None:
    bootstrap = await _bootstrap(client, "patient")
    slots = bootstrap["intake"]["availableSlots"]
    assert len({slot["id"] for slot in slots}) == len(slots)
    assert len({slot["providerId"] for slot in slots}) == 1

    missing_consent = _intake_body(slots[0]["id"])
    missing_consent["consents"]["photography"] = False
    assert (
        await client.post(
            "/api/intake/submissions",
            headers=_patient_headers(),
            json=missing_consent,
        )
    ).status_code == 422

    contradictory = _intake_body(slots[0]["id"])
    contradictory["symptoms"] = ["No symptoms", "Itching"]
    assert (
        await client.post("/api/intake/submissions", headers=_patient_headers(), json=contradictory)
    ).status_code == 422
    contradictory = _intake_body(slots[0]["id"])
    contradictory["urgentSigns"] = ["None of these", "Bleeding that will not stop"]
    assert (
        await client.post("/api/intake/submissions", headers=_patient_headers(), json=contradictory)
    ).status_code == 422

    stale = _intake_body(str(uuid.uuid4()))
    assert (
        await client.post("/api/intake/submissions", headers=_patient_headers(), json=stale)
    ).status_code == 409

    urgent = _intake_body(slots[0]["id"], urgent_signs=["Bleeding that will not stop"])
    first = await client.post("/api/intake/submissions", headers=_patient_headers(), json=urgent)
    assert first.status_code == 200, first.text
    first_receipt = first.json()
    assert first_receipt["triage"]["status"] == "staff_review"
    assert first_receipt["triage"]["readinessStatus"] == "needs_review"
    assert first_receipt["triage"]["taskId"]
    assert first_receipt["triage"]["notificationId"]
    second = await client.post("/api/intake/submissions", headers=_patient_headers(), json=urgent)
    assert second.status_code == 200, second.text
    assert second.json()["triage"] == first_receipt["triage"]
    assert second.json()["eligibilityCheckId"] == first_receipt["eligibilityCheckId"]
    assert second.json()["estimateId"] == first_receipt["estimateId"]

    changed_coverage = _intake_body(slots[0]["id"], urgent_signs=["Bleeding that will not stop"])
    changed_coverage["insurancePayer"] = "Northstar Health Plan"
    changed_coverage["insuranceMemberId"] = "NSH-NEW-7781"
    changed = await client.post(
        "/api/intake/submissions",
        headers=_patient_headers(),
        json=changed_coverage,
    )
    assert changed.status_code == 200, changed.text
    changed_receipt = changed.json()
    assert changed_receipt["eligibilityCheckId"] != first_receipt["eligibilityCheckId"]
    assert changed_receipt["estimateId"] != first_receipt["estimateId"]
    changed_retry = await client.post(
        "/api/intake/submissions",
        headers=_patient_headers(),
        json=changed_coverage,
    )
    assert changed_retry.status_code == 200, changed_retry.text
    assert changed_retry.json()["eligibilityCheckId"] == changed_receipt["eligibilityCheckId"]
    assert changed_retry.json()["estimateId"] == changed_receipt["estimateId"]

    reloaded = await _bootstrap(client, "patient")
    assert reloaded["intake"]["triage"] == first_receipt["triage"]
    assert reloaded["patient"]["readiness"] == 0
    assert reloaded["intake"]["eligibility"]["payer"] == "Northstar Health Plan"
    assert reloaded["intake"]["eligibility"]["memberId"] == "NSH-NEW-7781"
    assert (
        reloaded["financialContext"]["eligibility"]["id"] == changed_receipt["eligibilityCheckId"]
    )
    assert reloaded["financialContext"]["estimate"]["id"] == changed_receipt["estimateId"]
    assert reloaded["scenario"]["chapter"] == 2


async def test_completion_pathology_claims_integrity_and_domain_clock(
    presenter_client,
) -> None:
    ids = canonical_ids()
    premature = await presenter_client.post("/api/demo/triggers/pathology", json={})
    assert premature.status_code == 409
    bootstrap = await _bootstrap(presenter_client, "provider")
    action_ids = [item["id"] for item in bootstrap["encounter"]["proposals"]]
    expected_note_version = bootstrap["encounter"]["note"]["currentVersion"]["number"]
    expected_note_hash = bootstrap["encounter"]["note"]["currentVersion"]["contentHash"]

    invalid = await presenter_client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json={
            "proposedActionIds": action_ids[:-1],
            "attest": True,
            "signNote": True,
            "attestation": "Reviewed source records",
            "expectedNoteVersion": expected_note_version,
            "expectedNoteHash": expected_note_hash,
        },
    )
    assert invalid.status_code == 409
    async with SessionLocal() as session:
        note = await session.get(EncounterNote, ids["sarah_note_id"])
        procedure_count = int(
            await session.scalar(
                select(func.count(Procedure.id)).where(
                    Procedure.encounter_id == ids["sarah_encounter_id"]
                )
            )
            or 0
        )
    assert note and note.status == "proposed"
    assert procedure_count == 0

    edited_content = (
        "Subjective: Changing shoulder lesion.\n\n"
        "Assessment and plan: Shave biopsy after signed consent; send surgical pathology."
    )
    edited = await presenter_client.patch(
        f"/api/notes/{ids['sarah_note_id']}",
        headers=_provider_headers(),
        json={
            "content": edited_content,
            "structuredContent": {
                "subjective": "Changing shoulder lesion",
                "assessmentPlan": "Shave biopsy and surgical pathology",
            },
            "reason": "Clinician review",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["note"]["currentVersion"] == expected_note_version + 1
    stale = await presenter_client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json={
            "proposedActionIds": action_ids,
            "attest": True,
            "signNote": True,
            "attestation": "Reviewed source records and approved all actions",
            "expectedNoteVersion": expected_note_version,
            "expectedNoteHash": expected_note_hash,
        },
    )
    assert stale.status_code == 409
    refreshed = await _bootstrap(presenter_client, "provider")
    expected_note_version = refreshed["encounter"]["note"]["currentVersion"]["number"]
    expected_note_hash = refreshed["encounter"]["note"]["currentVersion"]["contentHash"]

    advanced = await presenter_client.post("/api/demo/advance-time", json={"hours": 48})
    assert advanced.status_code == 200
    domain_time = datetime.fromisoformat(advanced.json()["scenario"]["currentTime"])
    assert domain_time.tzinfo is not None

    async with SessionLocal() as session:
        second_provider = await session.get(User, sid("user:dr-elias-brooks"))
    assert second_provider
    runtime = get_settings()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=True),
        base_url="http://testserver",
    ) as wrong_provider_client:
        wrong_provider_client.cookies.set(
            runtime.session_cookie_name,
            DemoIdentityProvider(runtime).issue(second_provider),
        )
        wrong_provider = await wrong_provider_client.post(
            f"/api/encounters/{ids['sarah_encounter_id']}/complete",
            json={
                "proposedActionIds": action_ids,
                "attest": True,
                "signNote": True,
                "attestation": "Reviewed source records and approved all actions",
                "expectedNoteVersion": expected_note_version,
                "expectedNoteHash": expected_note_hash,
            },
        )
    assert wrong_provider.status_code == 403
    async with SessionLocal() as session:
        note = await session.get(EncounterNote, ids["sarah_note_id"])
        # The authorized edit above legitimately promoted the AI proposal into a
        # clinician-owned draft; the rejected completion must leave that state intact.
        assert note and note.status == "draft"
    completed = await presenter_client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json={
            "proposedActionIds": action_ids,
            "attest": True,
            "signNote": True,
            "attestation": "Reviewed source records and approved all actions",
            "expectedNoteVersion": expected_note_version,
            "expectedNoteHash": expected_note_hash,
        },
    )
    assert completed.status_code == 200, completed.text
    receipt = completed.json()
    signed_at = datetime.fromisoformat(receipt["signedAt"])
    assert signed_at.tzinfo is not None
    assert signed_at >= domain_time
    async with SessionLocal() as session:
        procedure = await session.get(Procedure, uuid.UUID(receipt["procedureId"]))
        order = await session.get(Order, uuid.UUID(receipt["orderId"]))
        specimen = await session.get(Specimen, uuid.UUID(receipt["specimenId"]))
    assert procedure and order and specimen
    assert procedure.provider_id == order.ordering_provider_id
    assert procedure.lesion_id == ids["sarah_lesion_id"]
    assert order.lesion_id == procedure.lesion_id
    assert specimen.lesion_id == procedure.lesion_id
    assert specimen.procedure_id == procedure.id
    assert specimen.order_id == order.id
    async with SessionLocal() as session:
        signed_note = await session.get(EncounterNote, ids["sarah_note_id"])
        signed_version = await session.scalar(
            select(NoteVersion).where(
                NoteVersion.note_id == ids["sarah_note_id"],
                NoteVersion.version_number == signed_note.current_version,
            )
        )
        aftercare_draft = await session.get(MessageDraft, sid("message-draft:sarah:aftercare"))
        shower_reply_draft = await session.get(
            MessageDraft, sid("message-draft:sarah:shower-reply")
        )
        aftercare_message = await session.get(Message, uuid.UUID(receipt["messageId"]))
        aftercare_provenance = await session.scalar(
            select(ProvenanceRecord).where(
                ProvenanceRecord.entity_type == "message",
                ProvenanceRecord.entity_id == aftercare_message.id,
                ProvenanceRecord.activity == "human_approved_ai_draft",
            )
        )
    assert signed_note.content == edited_content
    assert signed_note.current_version == expected_note_version
    assert signed_version and signed_version.content_hash == expected_note_hash
    assert aftercare_draft.status == "approved"
    assert shower_reply_draft.status == "proposed"
    assert aftercare_message.body == aftercare_draft.body
    assert aftercare_message.ai_run_id == aftercare_draft.ai_run_id
    assert aftercare_provenance.source_entity_id == aftercare_draft.id
    repeat = await presenter_client.post(
        f"/api/encounters/{ids['sarah_encounter_id']}/complete",
        headers=_provider_headers(),
        json={
            "proposedActionIds": action_ids,
            "attest": True,
            "signNote": True,
            "attestation": "Reviewed source records and approved all actions",
            "expectedNoteVersion": expected_note_version,
            "expectedNoteHash": expected_note_hash,
        },
    )
    assert repeat.status_code == 200
    assert repeat.json()["procedureId"] == receipt["procedureId"]
    assert repeat.json()["claimId"] == receipt["claimId"]

    immutable = await presenter_client.patch(
        f"/api/notes/{ids['sarah_note_id']}",
        headers=_provider_headers(),
        json={"content": "replace", "structuredContent": {}, "reason": "not allowed"},
    )
    assert immutable.status_code == 409
    amended = await presenter_client.post(
        f"/api/notes/{ids['sarah_note_id']}/amendments",
        headers=_provider_headers(),
        json={"reason": "Clarify follow-up", "amendmentText": "Follow up in six months."},
    )
    assert amended.status_code == 200
    amended_retry = await presenter_client.post(
        f"/api/notes/{ids['sarah_note_id']}/amendments",
        headers=_provider_headers(),
        json={"reason": "Clarify follow-up", "amendmentText": "Follow up in six months."},
    )
    assert amended_retry.status_code == 200
    assert amended_retry.json()["amendment"]["id"] == amended.json()["amendment"]["id"]
    amended_at = datetime.fromisoformat(amended.json()["amendment"]["signedAt"])
    assert amended_at.tzinfo is not None
    assert amended_at >= signed_at

    pathology = await presenter_client.post("/api/demo/triggers/pathology", json={})
    assert pathology.status_code == 200, pathology.text
    assert pathology.json()["created"] is True
    result_id = pathology.json()["resultId"]
    pathology_repeat = await presenter_client.post("/api/demo/triggers/pathology", json={})
    assert pathology_repeat.status_code == 200
    assert pathology_repeat.json()["created"] is False
    assert pathology_repeat.json()["resultId"] == result_id

    async with SessionLocal() as session:
        result = await session.get(DiagnosticResult, uuid.UUID(result_id))
        current_closure = await session.get(Task, uuid.UUID(receipt["closureTaskId"]))
        prior_result = await session.get(
            DiagnosticResult, sid("diagnostic-result:sarah:2022-nevus")
        )
        prior_order = await session.get(Order, prior_result.order_id)
        prior_review = Task(
            id=uuid.uuid5(prior_result.id, "review-task"),
            organization_id=ids["organization_id"],
            patient_id=ids["sarah_patient_id"],
            encounter_id=prior_order.encounter_id,
            assigned_user_id=sid("user:provider"),
            task_type="pathology_review",
            title="Review separate historical result",
            description="Regression fixture for result-scoped task handling.",
            priority="routine",
            status="open",
            due_at=_aware(domain_time),
        )
        prior_closure = Task(
            id=uuid.uuid5(prior_order.encounter_id, "pathology-tracking-task"),
            organization_id=ids["organization_id"],
            patient_id=ids["sarah_patient_id"],
            encounter_id=prior_order.encounter_id,
            assigned_user_id=sid("user:provider"),
            task_type="pathology_tracking",
            title="Close separate historical result",
            description="Regression fixture for encounter-scoped closure handling.",
            priority="routine",
            status="open",
            due_at=_aware(domain_time),
        )
        session.add_all([prior_review, prior_closure])
        await session.commit()
    assert result and current_closure
    assert result.order_id == order.id
    assert result.specimen_id == specimen.id
    assert result.procedure_id == procedure.id
    assert result.lesion_id == procedure.lesion_id

    reviewed = await presenter_client.post(
        f"/api/pathology/results/{result_id}/review",
        headers=_provider_headers(),
        json={"notifyPatient": False, "createFollowup": False},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["notificationId"] is None
    first_reviewed_at = datetime.fromisoformat(reviewed.json()["reviewedAt"])
    assert first_reviewed_at.tzinfo is not None
    async with SessionLocal() as session:
        result_after_review = await session.get(DiagnosticResult, uuid.UUID(result_id))
        closure_after_review = await session.get(Task, uuid.UUID(receipt["closureTaskId"]))
        prior_review_after = await session.get(Task, prior_review.id)
        prior_closure_after = await session.get(Task, prior_closure.id)
        first_reviewer_id = result_after_review.reviewed_by_user_id
    assert closure_after_review and closure_after_review.status == "open"
    assert prior_review_after and prior_review_after.status == "open"
    assert prior_closure_after and prior_closure_after.status == "open"

    notified = await presenter_client.post(
        f"/api/pathology/results/{result_id}/review",
        headers=_provider_headers(),
        json={"notifyPatient": True, "createFollowup": True},
    )
    assert notified.status_code == 200, notified.text
    assert notified.json()["status"] == "notified"
    async with SessionLocal() as session:
        result_after_notify = await session.get(DiagnosticResult, uuid.UUID(result_id))
        closure_after_notify = await session.get(Task, uuid.UUID(receipt["closureTaskId"]))
        prior_review_after = await session.get(Task, prior_review.id)
        prior_closure_after = await session.get(Task, prior_closure.id)
    assert result_after_notify.reviewed_by_user_id == first_reviewer_id
    assert _aware(result_after_notify.reviewed_at) == _aware(first_reviewed_at)
    assert result_after_notify.patient_notified_at is not None
    assert closure_after_notify and closure_after_notify.status == "completed"
    assert prior_review_after and prior_review_after.status == "open"
    assert prior_closure_after and prior_closure_after.status == "open"

    notified_repeat = await presenter_client.post(
        f"/api/pathology/results/{result_id}/review",
        headers=_provider_headers(),
        json={"notifyPatient": True, "createFollowup": True},
    )
    assert notified_repeat.status_code == 200
    assert notified_repeat.json()["reviewId"] == notified.json()["reviewId"]
    assert notified_repeat.json()["notificationId"] == notified.json()["notificationId"]

    presenter_bootstrap = (await presenter_client.get("/api/demo/bootstrap")).json()
    assert presenter_bootstrap["encounter"]["completionReceipt"]["claimId"] == receipt["claimId"]
    assert presenter_bootstrap["patient"]["lesion"]["status"] == "biopsied"
    assert presenter_bootstrap["pathology"]["aiProvenance"]["capability"] == "pathology_summary"
    assert (
        datetime.fromisoformat(presenter_bootstrap["pathology"]["reviewedAt"]) == first_reviewed_at
    )
    assert presenter_bootstrap["pathology"]["notifiedAt"] is not None
    assert presenter_bootstrap["scenario"]["chapter"] == 5

    transitions = []
    for _ in range(6):
        response = await presenter_client.post("/api/demo/triggers/claim-response", json={})
        assert response.status_code == 200, response.text
        transitions.append(response.json())
    assert transitions[-2]["status"] == "paid"
    assert transitions[-1]["status"] == "paid"
    assert transitions[-1]["changed"] is False
    paid_at = datetime.fromisoformat(transitions[-2]["claim"]["paidAt"])
    assert paid_at.tzinfo is not None
    assert paid_at >= signed_at


async def test_message_routing_and_human_approval_provenance(client) -> None:
    ids = canonical_ids()
    routine = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_patient_headers(),
        json={"body": "Thank you."},
    )
    assert routine.status_code == 200
    assert routine.json()["triage"] == "routine"
    warning = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_patient_headers(),
        json={
            "body": "It is warmer and redder and I am not sure whether it is infected.",
        },
    )
    assert warning.status_code == 200, warning.text
    assert warning.json()["triage"] == "staff_review"
    assert warning.json()["triageTaskId"]
    async with SessionLocal() as session:
        draft = await session.scalar(
            select(MessageDraft)
            .where(
                MessageDraft.conversation_id == ids["sarah_conversation_id"],
                MessageDraft.status == "proposed",
            )
            .order_by(MessageDraft.created_at.desc())
        )
    assert draft
    sent = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_provider_headers(),
        json={"body": draft.body, "approveAiDraftId": str(draft.id)},
    )
    assert sent.status_code == 200, sent.text
    sent_retry = await client.post(
        f"/api/conversations/{ids['sarah_conversation_id']}/messages",
        headers=_provider_headers(),
        json={"body": draft.body, "approveAiDraftId": str(draft.id)},
    )
    assert sent_retry.status_code == 200, sent_retry.text
    assert sent_retry.json()["messageId"] == sent.json()["messageId"]
    async with SessionLocal() as session:
        provenance = await session.scalar(
            select(ProvenanceRecord).where(
                ProvenanceRecord.entity_type == "message",
                ProvenanceRecord.entity_id == uuid.UUID(sent.json()["messageId"]),
                ProvenanceRecord.activity == "human_approved_ai_draft",
            )
        )
    assert provenance and provenance.ai_run_id == draft.ai_run_id


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Postgres row-lock contract")
async def test_concurrent_draft_approval_is_exactly_once(client) -> None:
    ids = canonical_ids()
    drafted = await client.post(
        "/api/messages/draft",
        headers=_provider_headers(),
        json={
            "conversationId": str(ids["sarah_conversation_id"]),
            "question": "Can I replace the bandage tomorrow?",
        },
    )
    assert drafted.status_code == 200, drafted.text
    draft = drafted.json()["draft"]
    responses = await asyncio.gather(
        *(
            client.post(
                f"/api/conversations/{ids['sarah_conversation_id']}/messages",
                headers=_provider_headers(),
                json={"body": draft["body"], "approveAiDraftId": draft["id"]},
            )
            for _ in range(2)
        )
    )
    assert [response.status_code for response in responses] == [200, 200]
    message_ids = {response.json()["messageId"] for response in responses}
    assert len(message_ids) == 1
    message_id = uuid.UUID(message_ids.pop())
    async with SessionLocal() as session:
        message_count = await session.scalar(
            select(func.count(Message.id)).where(Message.id == message_id)
        )
        provenance_count = await session.scalar(
            select(func.count(ProvenanceRecord.id)).where(
                ProvenanceRecord.entity_type == "message",
                ProvenanceRecord.entity_id == message_id,
                ProvenanceRecord.activity == "human_approved_ai_draft",
            )
        )
    assert message_count == 1
    assert provenance_count == 1


async def test_conversation_read_receipt_is_directional_tenant_wide_and_idempotent(client) -> None:
    before = await _bootstrap(client, "provider")
    non_sarah = next(
        item
        for item in before["conversations"]
        if item["patient"] != "Sarah Mitchell" and item["unread"] > 0
    )
    queue_before = next(item for item in before["queues"] if item["id"] == "messages")["count"]
    metrics_before = (
        await client.get("/api/mso/metrics", headers={"X-Demo-Persona": "owner"})
    ).json()["patientSatisfactionIndicators"]["messageReadRatePercent"]

    read = await client.post(
        f"/api/conversations/{non_sarah['id']}/read",
        headers=_provider_headers(),
        json={},
    )
    assert read.status_code == 200, read.text
    receipt = read.json()
    assert receipt["changedCount"] == non_sarah["unread"]
    assert datetime.fromisoformat(receipt["readAt"]).tzinfo is not None
    repeat = await client.post(
        f"/api/conversations/{non_sarah['id']}/read",
        headers=_provider_headers(),
        json={},
    )
    assert repeat.status_code == 200
    assert repeat.json()["changedCount"] == 0
    assert repeat.json()["readAt"] == receipt["readAt"]

    after = await _bootstrap(client, "provider")
    reloaded = next(item for item in after["conversations"] if item["id"] == non_sarah["id"])
    assert reloaded["unread"] == 0
    queue_after = next(item for item in after["queues"] if item["id"] == "messages")["count"]
    assert queue_after == queue_before - receipt["changedCount"]
    metrics_after = (
        await client.get("/api/mso/metrics", headers={"X-Demo-Persona": "owner"})
    ).json()["patientSatisfactionIndicators"]["messageReadRatePercent"]
    # Staff reading an inbound patient message must not inflate the separate
    # patient-read rate for outbound staff/provider messages.
    assert metrics_after == metrics_before


async def test_conversation_read_normalizes_prior_sqlite_receipt_offsets(client) -> None:
    patient_workspace = await _bootstrap(client, "patient")
    conversation_id = patient_workspace["conversations"][0]["id"]
    first_read = await client.post(
        f"/api/conversations/{conversation_id}/read",
        headers=_provider_headers(),
        json={},
    )
    assert first_read.status_code == 200, first_read.text
    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        headers=_patient_headers(),
        json={"body": "One more routine question about tomorrow morning."},
    )
    assert sent.status_code == 200, sent.text
    second_read = await client.post(
        f"/api/conversations/{conversation_id}/read",
        headers=_provider_headers(),
        json={},
    )
    assert second_read.status_code == 200, second_read.text
    assert second_read.json()["changedCount"] == 1
    assert datetime.fromisoformat(second_read.json()["readAt"]).tzinfo is not None


async def test_denial_recovery_stays_visible_and_records_biller_approval(client) -> None:
    biller_before = await _bootstrap(client, "biller")
    visible_open_denials = [
        item
        for item in biller_before["claims"]
        if (item.get("denial") or {}).get("status") == "open"
    ]
    assert len(visible_open_denials) == 1
    visible_claim = visible_open_denials[0]
    claim_id = uuid.UUID(visible_claim["id"])
    denial_id = uuid.UUID(visible_claim["denial"]["id"])
    source_task_id = visible_claim["denial"]["assignedTaskId"]
    assert source_task_id

    async with SessionLocal() as session:
        denial = await session.get(Denial, denial_id)
        task = await session.get(Task, uuid.UUID(source_task_id))
        assert denial and denial.status == "open" and denial.claim_id == claim_id
        assert task and task.claim_id == claim_id and task.denial_id == denial_id
        proposed_action = await session.scalar(
            select(ProposedAction).where(
                ProposedAction.entity_type == "denial",
                ProposedAction.entity_id == denial.id,
                ProposedAction.action_type == "resubmit_with_modifier_25",
            )
        )
        assert proposed_action and proposed_action.status == "proposed"
        proposed_action_id = proposed_action.id
    response = await client.post(
        f"/api/claims/{claim_id}/correct-and-resubmit",
        headers=_biller_headers(),
        json={
            "appealBody": "Signed documentation supports the separately identifiable service.",
            "correction": "Append modifier 25 and attach signed documentation.",
            "sourceTaskId": source_task_id,
        },
    )
    assert response.status_code == 200, response.text
    async with SessionLocal() as session:
        claim = await session.get(Claim, claim_id)
        denial = await session.scalar(select(Denial).where(Denial.claim_id == claim_id))
        appeal = await session.scalar(select(Appeal).where(Appeal.denial_id == denial.id))
        proposed_action = await session.get(ProposedAction, proposed_action_id)
        approval = await session.scalar(
            select(Approval).where(Approval.proposed_action_id == proposed_action_id)
        )
    assert claim and claim.status == "submitted"
    assert denial and denial.status == "resolved"
    assert appeal and appeal.status == "submitted"
    assert proposed_action and proposed_action.status == "approved"
    assert approval and approval.decision == "approved"
    assert approval.reviewer_user_id == sid("user:biller")
    assert approval.decided_at is not None

    async with SessionLocal() as session:
        source_claim = await session.get(Claim, claim_id)
        second_claim = Claim(
            id=uuid.uuid5(claim_id, "second-patient-balance-claim"),
            organization_id=source_claim.organization_id,
            claim_number=f"{source_claim.claim_number}-SECOND",
            patient_id=source_claim.patient_id,
            encounter_id=source_claim.encounter_id,
            coverage_id=source_claim.coverage_id,
            billing_provider_id=source_claim.billing_provider_id,
            status="adjudicated",
            total_charge=30,
            allowed_amount=30,
            paid_amount=0,
            patient_responsibility=30,
            submitted_at=source_claim.submitted_at,
            adjudicated_at=source_claim.submitted_at,
        )
        session.add(second_claim)
        await session.commit()

    lifecycle = []
    for expected_status in ["accepted", "adjudicated", "paid"]:
        advanced = await client.post(
            f"/api/rcm/claims/{claim_id}/advance",
            headers=_biller_headers(),
            json={},
        )
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["claim"]["status"] == expected_status
        lifecycle.append(advanced.json()["claim"])
    assert lifecycle[0]["submittedAt"] is not None
    assert lifecycle[1]["adjudicatedAt"] is not None
    assert lifecycle[2]["paidAt"] is not None

    async with SessionLocal() as session:
        appeal = await session.scalar(select(Appeal).where(Appeal.denial_id == denial_id))
        claim = await session.get(Claim, claim_id)
        payer_payments = (
            await session.scalars(
                select(Payment).where(Payment.claim_id == claim_id, Payment.source == "payer")
            )
        ).all()
        balance = await session.scalar(
            select(PatientBalance).where(PatientBalance.patient_id == claim.patient_id)
        )
        aggregate_responsibility = await session.scalar(
            select(func.sum(Claim.patient_responsibility)).where(
                Claim.patient_id == claim.patient_id,
                Claim.status.in_(["adjudicated", "paid"]),
            )
        )
        event_count = int(
            await session.scalar(
                select(func.count(ClaimEvent.id)).where(ClaimEvent.claim_id == claim_id)
            )
            or 0
        )
    assert appeal and appeal.status == "won" and appeal.outcome == "paid"
    assert appeal.recovered_amount == claim.paid_amount
    assert len(payer_payments) == 1
    assert payer_payments[0].amount == claim.paid_amount
    assert balance and balance.current_balance == aggregate_responsibility

    terminal = await client.post(
        f"/api/rcm/claims/{claim_id}/advance",
        headers=_biller_headers(),
        json={},
    )
    assert terminal.status_code == 200
    assert terminal.json()["claim"]["status"] == "paid"
    async with SessionLocal() as session:
        terminal_event_count = int(
            await session.scalar(
                select(func.count(ClaimEvent.id)).where(ClaimEvent.claim_id == claim_id)
            )
            or 0
        )
        terminal_payment_count = int(
            await session.scalar(
                select(func.count(Payment.id)).where(
                    Payment.claim_id == claim_id, Payment.source == "payer"
                )
            )
            or 0
        )
    assert terminal_event_count == event_count
    assert terminal_payment_count == 1

    biller = await _bootstrap(client, "biller")
    recovered = next(item for item in biller["claims"] if item["id"] == str(claim_id))
    assert recovered["denial"]["status"] == "resolved"
    assert recovered["denial"]["recovery"]["status"] == "won"
    assert recovered["denial"]["recovery"]["outcome"] == "paid"
    assert recovered["denial"]["recovery"]["recoveredAmount"] == float(claim.paid_amount)
    assert recovered["lines"]
    assert len(recovered["payments"]) == 1
    assert recovered["balance"]["scope"] == "patient_aggregate"
    assert recovered["balance"]["currentBalance"] == float(aggregate_responsibility)
    assert recovered["claimBalance"]["currentBalance"] == float(claim.patient_responsibility)
    assert recovered["provenance"]["source"] == "durable_claim_lines_and_clearinghouse_events"


async def test_lesion_observation_round_trips_site_view_and_comparison(client) -> None:
    ids = canonical_ids()
    response = await client.post(
        "/api/lesions/observations",
        headers=_provider_headers(),
        json={
            "lesionId": str(ids["sarah_lesion_id"]),
            "encounterId": str(ids["sarah_encounter_id"]),
            "site": "left posterior shoulder",
            "view": "posterior",
            "lengthMm": 7.2,
            "widthMm": 5.1,
            "morphology": "asymmetric pigmented papule",
            "border": "irregular",
            "pigmentation": "variegated brown-black",
            "changeOverTime": "slightly wider",
            "symptoms": ["itching", "tenderness"],
            "comparison": "Compared with the prior overview image",
            "assessment": "Biopsy remains indicated",
        },
    )
    assert response.status_code == 200, response.text
    reloaded = await _bootstrap(client, "provider")
    observation = reloaded["patient"]["lesion"]["latestObservation"]
    assert observation["site"] == "left posterior shoulder"
    assert observation["view"] == "posterior"
    assert observation["comparison"] == "Compared with the prior overview image"
    assert observation["symptoms"] == ["itching", "tenderness"]
