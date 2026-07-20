from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import run_ai
from .clock import domain_now
from .config import get_settings
from .learning import (
    ensure_patient_episode,
    hash_json,
    record_decision_trajectory,
    record_domain_event,
    record_outcome,
)
from .models import (
    AIOutput,
    AIRun,
    Allergy,
    Appeal,
    Appointment,
    AppointmentReminder,
    Approval,
    AuditEvent,
    AutomationPolicy,
    Claim,
    ClaimEvent,
    ClaimLine,
    ClinicalImage,
    Consent,
    Conversation,
    Coverage,
    DemoScenario,
    DemoTimelineEvent,
    Denial,
    DiagnosticResult,
    DomainEvent,
    EligibilityCheck,
    Encounter,
    EncounterNote,
    EpisodeEventLink,
    EpisodeInstance,
    Estimate,
    FileRecord,
    Lesion,
    LesionObservation,
    Location,
    Medication,
    Membership,
    Message,
    MessageDraft,
    NoteAmendment,
    NoteVersion,
    Notification,
    Order,
    Organization,
    Patient,
    PatientBalance,
    PatientContact,
    Payment,
    Problem,
    Procedure,
    PromptVersion,
    ProposedAction,
    ProvenanceRecord,
    Provider,
    QuestionnaireResponse,
    Role,
    Specimen,
    Task,
    User,
    WorkflowEvent,
    WorkflowRun,
)
from .providers import clearinghouse_provider, messaging_provider, pathology_provider
from .seed import DEMO_NOW, canonical_ids

DEMO_CHAPTERS: tuple[tuple[str, str], ...] = (
    ("patient_initiation", "Patient initiation"),
    ("command_center", "Command center"),
    ("encounter", "AI-native encounter"),
    ("review_complete", "Review and complete"),
    ("pathology", "Pathology closure"),
    ("rcm", "Revenue cycle"),
    ("mso", "MSO intelligence"),
)


def row_dict(model: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = exclude or set()
    return {
        column.name: getattr(model, column.key)
        for column in model.__table__.columns
        if column.name not in excluded
    }


def _percent(numerator: int | float | Decimal, denominator: int | float | Decimal) -> float:
    return round(float(numerator) / float(denominator) * 100, 1) if denominator else 0.0


def _resource_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat()


def _observation_resource(
    *,
    resource_type: str,
    resource_id: uuid.UUID,
    content_hash: str,
    resource_version: int = 1,
    effective_at: datetime | None = None,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_version": resource_version,
        "content_hash": content_hash,
        "effective_at": _resource_time(effective_at),
        "recorded_at": _resource_time(recorded_at),
    }


async def _patient_learning_episode(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    patient_id: uuid.UUID,
    started_at: datetime,
) -> EpisodeInstance | None:
    episode_key = f"patient-journey:{patient_id}"
    episode = await session.scalar(
        select(EpisodeInstance).where(
            EpisodeInstance.organization_id == organization_id,
            EpisodeInstance.episode_key == episode_key,
        )
    )
    if episode is not None:
        return episode
    return await ensure_patient_episode(
        session,
        organization_id=organization_id,
        patient_id=patient_id,
        started_at=started_at,
    )


async def _link_episode_event(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    episode: EpisodeInstance,
    event: DomainEvent,
    role: str,
) -> EpisodeEventLink:
    link_id = uuid.uuid5(episode.id, f"event-link:{event.id}")
    existing = await session.scalar(
        select(EpisodeEventLink).where(
            EpisodeEventLink.organization_id == organization_id,
            EpisodeEventLink.id == link_id,
            EpisodeEventLink.episode_instance_id == episode.id,
        )
    )
    if existing is not None:
        return existing
    current_sequence = await session.scalar(
        select(func.coalesce(func.max(EpisodeEventLink.sequence), 0)).where(
            EpisodeEventLink.organization_id == organization_id,
            EpisodeEventLink.episode_instance_id == episode.id,
        )
    )
    link = EpisodeEventLink(
        id=link_id,
        organization_id=organization_id,
        episode_instance_id=episode.id,
        domain_event_id=event.id,
        sequence=int(current_sequence or 0) + 1,
        role=role,
    )
    session.add(link)
    return link


async def ai_provenance(
    session: AsyncSession,
    organization_id: uuid.UUID,
    ai_run_id: uuid.UUID | None,
) -> dict[str, Any] | None:
    if ai_run_id is None:
        return None
    row = (
        await session.execute(
            select(AIRun, PromptVersion, AIOutput)
            .join(
                PromptVersion,
                (PromptVersion.id == AIRun.prompt_version_id)
                & (PromptVersion.organization_id == organization_id),
            )
            .outerjoin(
                AIOutput,
                (AIOutput.ai_run_id == AIRun.id) & (AIOutput.organization_id == organization_id),
            )
            .where(AIRun.id == ai_run_id, AIRun.organization_id == organization_id)
        )
    ).first()
    if row is None:
        return None
    run, prompt, output = row
    return {
        "ai_run_id": run.id,
        "capability": run.capability,
        "prompt_version": prompt.version,
        "provider": run.provider,
        "model": run.model,
        "fallback_used": run.fallback_used,
        "schema_valid": bool(output and output.schema_valid),
    }


async def get_demo_scenario(session: AsyncSession, organization_id: uuid.UUID) -> DemoScenario:
    scenario = await session.scalar(
        select(DemoScenario).where(
            DemoScenario.organization_id == organization_id,
            DemoScenario.active.is_(True),
        )
    )
    if scenario is None:
        raise HTTPException(status_code=503, detail="Demo scenario is not initialized")
    return scenario


async def set_demo_chapter(
    session: AsyncSession,
    organization_id: uuid.UUID,
    chapter: str,
    *,
    allow_regression: bool = False,
) -> DemoScenario:
    chapter_numbers = {key: index for index, (key, _label) in enumerate(DEMO_CHAPTERS, 1)}
    if chapter not in chapter_numbers:
        raise HTTPException(status_code=422, detail=f"Unknown demo chapter: {chapter}")
    scenario = await get_demo_scenario(session, organization_id)
    current_number = chapter_numbers.get(scenario.current_chapter, 1)
    if allow_regression or chapter_numbers[chapter] >= current_number:
        scenario.current_chapter = chapter
    return scenario


async def get_patient_bundle(
    session: AsyncSession, organization_id: uuid.UUID, patient_id: uuid.UUID
) -> dict[str, Any]:
    patient = await session.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.organization_id == organization_id)
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    coverages = (
        await session.scalars(
            select(Coverage).where(
                Coverage.patient_id == patient_id,
                Coverage.organization_id == organization_id,
            )
        )
    ).all()
    medications = (
        await session.scalars(
            select(Medication).where(
                Medication.patient_id == patient_id,
                Medication.organization_id == organization_id,
                Medication.status == "active",
            )
        )
    ).all()
    allergies = (
        await session.scalars(
            select(Allergy).where(
                Allergy.patient_id == patient_id,
                Allergy.organization_id == organization_id,
                Allergy.status == "active",
            )
        )
    ).all()
    appointments = (
        await session.scalars(
            select(Appointment)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.organization_id == organization_id,
            )
            .order_by(Appointment.starts_at.desc())
        )
    ).all()
    lesions = (
        await session.scalars(
            select(Lesion).where(
                Lesion.patient_id == patient_id,
                Lesion.organization_id == organization_id,
            )
        )
    ).all()
    observations = (
        await session.scalars(
            select(LesionObservation)
            .where(
                LesionObservation.organization_id == organization_id,
                LesionObservation.lesion_id.in_([lesion.id for lesion in lesions]),
            )
            .order_by(LesionObservation.observed_at)
        )
    ).all()
    observations_by_lesion: dict[uuid.UUID, list[LesionObservation]] = defaultdict(list)
    for observation in observations:
        observations_by_lesion[observation.lesion_id].append(observation)
    images = (
        await session.execute(
            select(ClinicalImage, FileRecord)
            .join(FileRecord, FileRecord.id == ClinicalImage.file_record_id)
            .where(
                ClinicalImage.patient_id == patient_id,
                ClinicalImage.organization_id == organization_id,
            )
            .order_by(ClinicalImage.captured_at)
        )
    ).all()
    contacts = (
        await session.scalars(
            select(PatientContact).where(
                PatientContact.patient_id == patient_id,
                PatientContact.organization_id == organization_id,
            )
        )
    ).all()
    problems = (
        await session.scalars(
            select(Problem).where(
                Problem.patient_id == patient_id,
                Problem.organization_id == organization_id,
                Problem.status == "active",
            )
        )
    ).all()
    eligibility_checks = (
        await session.scalars(
            select(EligibilityCheck)
            .where(
                EligibilityCheck.patient_id == patient_id,
                EligibilityCheck.organization_id == organization_id,
            )
            .order_by(
                EligibilityCheck.responded_at.desc(),
                EligibilityCheck.created_at.desc(),
                EligibilityCheck.id.desc(),
            )
        )
    ).all()
    note_rows = (
        await session.execute(
            select(EncounterNote, Encounter, User)
            .join(
                Encounter,
                (Encounter.id == EncounterNote.encounter_id)
                & (Encounter.organization_id == organization_id),
            )
            .join(
                User,
                (User.id == EncounterNote.author_user_id)
                & (User.organization_id == organization_id),
            )
            .where(
                EncounterNote.organization_id == organization_id,
                Encounter.patient_id == patient_id,
            )
            .order_by(EncounterNote.signed_at.desc(), EncounterNote.created_at.desc())
        )
    ).all()
    pathology_results = (
        await session.scalars(
            select(DiagnosticResult)
            .where(
                DiagnosticResult.organization_id == organization_id,
                DiagnosticResult.patient_id == patient_id,
            )
            .order_by(DiagnosticResult.resulted_at.desc())
        )
    ).all()
    lesion_items = []
    for lesion in lesions:
        lesion_observations = observations_by_lesion[lesion.id]
        latest = lesion_observations[-1] if lesion_observations else None
        lesion_items.append(
            {
                **row_dict(lesion),
                "latest_observation": (
                    {
                        **row_dict(latest),
                        "site": latest.anatomical_site or lesion.anatomical_location,
                        "view": latest.body_map_view or lesion.body_map_view,
                        "symptoms": [
                            part.strip() for part in latest.symptoms.split(";") if part.strip()
                        ],
                    }
                    if latest
                    else None
                ),
                "observations": [row_dict(item) for item in lesion_observations],
            }
        )
    pharmacy = next(
        (contact for contact in contacts if contact.kind == "pharmacy" and contact.is_primary),
        next((contact for contact in contacts if contact.kind == "pharmacy"), None),
    )
    latest_eligibility = eligibility_checks[0] if eligibility_checks else None
    latest_appointment = appointments[0] if appointments else None
    signed_notes = [
        {
            "id": note.id,
            "encounter_id": encounter.id,
            "status": note.status,
            "current_version": note.current_version,
            "signed_at": note.signed_at,
            "author": {"id": author.id, "name": author.display_name},
        }
        for note, encounter, author in note_rows
        if note.status in {"signed", "amended"}
    ]
    recent_events = [
        {
            "id": appointment.id,
            "kind": "appointment",
            "occurred_at": appointment.starts_at,
            "title": appointment.visit_type,
            "detail": appointment.status.replace("_", " ").title(),
        }
        for appointment in appointments
    ]
    recent_events.extend(
        {
            "id": result.id,
            "kind": "pathology",
            "occurred_at": result.resulted_at,
            "title": "Pathology result",
            "detail": result.summary,
        }
        for result in pathology_results
    )
    recent_events.extend(
        {
            "id": note.id,
            "kind": "signed_note",
            "occurred_at": note.signed_at,
            "title": "Signed encounter note",
            "detail": f"Version {note.current_version} · {author.display_name}",
        }
        for note, _encounter, author in note_rows
        if note.signed_at is not None
    )
    recent_events.sort(
        key=lambda item: item["occurred_at"].replace(tzinfo=item["occurred_at"].tzinfo or UTC),
        reverse=True,
    )
    chart_time = await domain_now(session, organization_id)
    return {
        **row_dict(patient),
        "full_name": f"{patient.first_name} {patient.last_name}",
        "age": int((chart_time.date() - patient.date_of_birth).days / 365.2425),
        "coverages": [row_dict(item) for item in coverages],
        "medications": [row_dict(item) for item in medications],
        "allergies": [row_dict(item) for item in allergies],
        "appointments": [row_dict(item) for item in appointments],
        "problems": [row_dict(item) for item in problems],
        "contacts": [row_dict(item) for item in contacts],
        "pharmacy": row_dict(pharmacy) if pharmacy else None,
        "readiness": {
            "status": latest_appointment.readiness_status if latest_appointment else "unknown",
            "appointment_id": latest_appointment.id if latest_appointment else None,
            "appointment_starts_at": latest_appointment.starts_at if latest_appointment else None,
            "eligibility_status": latest_eligibility.status if latest_eligibility else "unknown",
            "eligibility_checked_at": (
                latest_eligibility.responded_at if latest_eligibility else None
            ),
        },
        "eligibility": row_dict(latest_eligibility) if latest_eligibility else None,
        "lesions": lesion_items,
        "recent_events": recent_events[:10],
        "prior_signed_notes": signed_notes,
        "pathology_history": [row_dict(item) for item in pathology_results],
        "images": [
            {**row_dict(image), "url": file.public_demo_url, "file": row_dict(file)}
            for image, file in images
        ],
    }


def availability_slot_id(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    location_id: uuid.UUID,
    starts_at: datetime,
) -> uuid.UUID:
    canonical_start = starts_at.replace(tzinfo=starts_at.tzinfo or UTC).astimezone(UTC).isoformat()
    return uuid.uuid5(
        organization_id,
        f"availability:{provider_id}:{location_id}:{canonical_start}",
    )


async def get_availability(
    session: AsyncSession, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    scenario = await get_demo_scenario(session, organization_id)
    provider_rows = (
        await session.execute(
            select(Provider, User)
            .join(User, User.id == Provider.user_id)
            .where(
                Provider.organization_id == organization_id,
                User.organization_id == organization_id,
                Provider.accepting_new_patients.is_(True),
            )
            .order_by(User.display_name)
        )
    ).all()
    canonical_provider_rows = [row for row in provider_rows if row[1].persona_key == "provider"]
    if canonical_provider_rows:
        provider_rows = canonical_provider_rows
    locations = (
        await session.scalars(
            select(Location)
            .where(Location.organization_id == organization_id)
            .order_by(Location.name)
        )
    ).all()
    policy = await session.scalar(
        select(AutomationPolicy).where(
            AutomationPolicy.organization_id == organization_id,
            AutomationPolicy.event_type == "schedule_availability",
            AutomationPolicy.enabled.is_(True),
        )
    )
    if not policy or not policy.actions_json or not provider_rows or not locations:
        return []
    template = policy.actions_json[0]
    timezone_name = policy.conditions_json.get("timezone", "America/New_York")
    local_zone = ZoneInfo(timezone_name)
    local_now = scenario.current_time.astimezone(local_zone)
    lead = int(policy.conditions_json.get("minimumLeadMinutes", 30))
    eligible_after = local_now + timedelta(minutes=lead)
    existing = (
        await session.scalars(
            select(Appointment).where(
                Appointment.organization_id == organization_id,
                Appointment.status.not_in(["cancelled", "no_show"]),
                Appointment.starts_at >= scenario.current_time,
            )
        )
    ).all()
    slots: list[dict[str, Any]] = []
    weekdays = set(template.get("weekdays", [0, 1, 2, 3, 4]))
    hour, minute = (int(part) for part in template.get("start", "09:00").split(":"))
    end_hour, end_minute = (int(part) for part in template.get("end", "17:00").split(":"))
    slot_minutes = int(template.get("slotMinutes", 30))
    for day_offset in range(8):
        day = (local_now + timedelta(days=day_offset)).date()
        if day.weekday() not in weekdays:
            continue
        cursor = local_now.replace(
            year=day.year,
            month=day.month,
            day=day.day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        day_end = cursor.replace(hour=end_hour, minute=end_minute)
        while cursor + timedelta(minutes=slot_minutes) <= day_end:
            if cursor >= eligible_after:
                for provider_index, (provider, user) in enumerate(provider_rows):
                    start_utc = cursor.astimezone(UTC)
                    end_utc = start_utc + timedelta(minutes=slot_minutes)
                    conflict = any(
                        appointment.provider_id == provider.id
                        and appointment.starts_at.replace(
                            tzinfo=appointment.starts_at.tzinfo or UTC
                        )
                        < end_utc
                        and appointment.starts_at.replace(
                            tzinfo=appointment.starts_at.tzinfo or UTC
                        )
                        + timedelta(minutes=appointment.duration_minutes)
                        > start_utc
                        for appointment in existing
                    )
                    if conflict:
                        continue
                    location = locations[provider_index % len(locations)]
                    slots.append(
                        {
                            "id": availability_slot_id(
                                organization_id, provider.id, location.id, start_utc
                            ),
                            "provider_id": provider.id,
                            "provider_name": user.display_name,
                            "credentials": provider.credentials,
                            "location_id": location.id,
                            "location_name": location.name,
                            "starts_at": start_utc,
                            "duration_minutes": slot_minutes,
                            "source_policy_id": policy.id,
                        }
                    )
                    if len(slots) == 6:
                        return slots
            cursor += timedelta(minutes=slot_minutes)
    return slots


async def get_encounter_bundle(
    session: AsyncSession, organization_id: uuid.UUID, encounter_id: uuid.UUID
) -> dict[str, Any]:
    encounter = await session.scalar(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.organization_id == organization_id,
        )
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    patient = await session.scalar(
        select(Patient).where(
            Patient.id == encounter.patient_id,
            Patient.organization_id == organization_id,
        )
    )
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.encounter_id == encounter.id,
            EncounterNote.organization_id == organization_id,
        )
    )
    note_versions = []
    amendments = []
    if note:
        note_versions = (
            await session.scalars(
                select(NoteVersion)
                .where(
                    NoteVersion.note_id == note.id,
                    NoteVersion.organization_id == organization_id,
                )
                .order_by(NoteVersion.version_number)
            )
        ).all()
        amendments = (
            await session.scalars(
                select(NoteAmendment)
                .where(
                    NoteAmendment.note_id == note.id,
                    NoteAmendment.organization_id == organization_id,
                )
                .order_by(NoteAmendment.signed_at)
            )
        ).all()
    lesions = (
        await session.scalars(
            select(Lesion).where(
                Lesion.patient_id == encounter.patient_id,
                Lesion.organization_id == organization_id,
            )
        )
    ).all()
    lesion_data: list[dict[str, Any]] = []
    for lesion in lesions:
        observations = (
            await session.scalars(
                select(LesionObservation)
                .where(
                    LesionObservation.lesion_id == lesion.id,
                    LesionObservation.organization_id == organization_id,
                )
                .order_by(LesionObservation.observed_at)
            )
        ).all()
        images = (
            await session.execute(
                select(ClinicalImage, FileRecord)
                .join(FileRecord, FileRecord.id == ClinicalImage.file_record_id)
                .where(
                    ClinicalImage.lesion_id == lesion.id,
                    ClinicalImage.organization_id == organization_id,
                )
                .order_by(ClinicalImage.captured_at)
            )
        ).all()
        lesion_data.append(
            {
                **row_dict(lesion),
                "observations": [row_dict(item) for item in observations],
                "images": [
                    {**row_dict(image), "url": file.public_demo_url} for image, file in images
                ],
            }
        )
    actions = (
        await session.scalars(
            select(ProposedAction)
            .where(
                ProposedAction.organization_id == organization_id,
                ProposedAction.patient_id == encounter.patient_id,
                or_(
                    ProposedAction.entity_id == encounter.id,
                    ProposedAction.entity_id == (note.id if note else uuid.uuid4()),
                ),
            )
            .order_by(ProposedAction.created_at)
        )
    ).all()
    orders = (
        await session.scalars(
            select(Order).where(
                Order.encounter_id == encounter.id,
                Order.organization_id == organization_id,
            )
        )
    ).all()
    procedures = (
        await session.scalars(
            select(Procedure).where(
                Procedure.encounter_id == encounter.id,
                Procedure.organization_id == organization_id,
            )
        )
    ).all()
    return {
        **row_dict(encounter),
        "patient": row_dict(patient) if patient else None,
        "note": (
            {
                **row_dict(note),
                "versions": [row_dict(item) for item in note_versions],
                "amendments": [row_dict(item) for item in amendments],
            }
            if note
            else None
        ),
        "lesions": lesion_data,
        "proposed_actions": [row_dict(item) for item in actions],
        "orders": [row_dict(item) for item in orders],
        "procedures": [row_dict(item) for item in procedures],
    }


async def command_center(session: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    scenario = await get_demo_scenario(session, organization_id)
    timezone_name = await session.scalar(
        select(Organization.timezone).where(Organization.id == organization_id)
    )
    local_zone = ZoneInfo(timezone_name or "UTC")
    scenario_time = scenario.current_time.replace(tzinfo=scenario.current_time.tzinfo or UTC)
    local_start = scenario_time.astimezone(local_zone).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = local_start.astimezone(UTC)
    end = (local_start + timedelta(days=1)).astimezone(UTC)
    schedule_rows = (
        await session.execute(
            select(Appointment, Patient, Provider, User)
            .join(
                Patient,
                (Patient.id == Appointment.patient_id)
                & (Patient.organization_id == organization_id),
            )
            .join(
                Provider,
                (Provider.id == Appointment.provider_id)
                & (Provider.organization_id == organization_id),
            )
            .join(
                User,
                (User.id == Provider.user_id) & (User.organization_id == organization_id),
            )
            .where(
                Appointment.organization_id == organization_id,
                Appointment.starts_at >= start,
                Appointment.starts_at < end,
            )
            .order_by(Appointment.starts_at)
        )
    ).all()
    tasks = (
        await session.scalars(
            select(Task)
            .where(Task.organization_id == organization_id, Task.status != "completed")
            .order_by(Task.priority.desc(), Task.due_at)
        )
    ).all()
    unsigned_notes = int(
        await session.scalar(
            select(func.count(EncounterNote.id)).where(
                EncounterNote.organization_id == organization_id,
                EncounterNote.status.in_(["draft", "proposed"]),
            )
        )
        or 0
    )
    open_pathology = int(
        await session.scalar(
            select(func.count(DiagnosticResult.id)).where(
                DiagnosticResult.organization_id == organization_id,
                DiagnosticResult.status == "final",
                DiagnosticResult.reviewed_at.is_(None),
            )
        )
        or 0
    )
    pathology_results = (
        await session.scalars(
            select(DiagnosticResult).where(
                DiagnosticResult.organization_id == organization_id,
                DiagnosticResult.status == "final",
            )
        )
    ).all()
    scenario_utc = scenario_time.astimezone(UTC)
    pathology_due_today = 0
    closure_sla_eligible = 0
    closure_sla_met = 0
    for result in pathology_results:
        resulted_at = result.resulted_at.replace(tzinfo=result.resulted_at.tzinfo or UTC)
        closure_due_at = resulted_at + timedelta(hours=24)
        notified_at = (
            result.patient_notified_at.replace(tzinfo=result.patient_notified_at.tzinfo or UTC)
            if result.patient_notified_at
            else None
        )
        if notified_at is None and start <= closure_due_at < end:
            pathology_due_today += 1
        if closure_due_at <= scenario_utc or notified_at is not None:
            closure_sla_eligible += 1
            if notified_at is not None and notified_at <= closure_due_at:
                closure_sla_met += 1
    pathology_closure_on_time_percent = (
        round(100 * closure_sla_met / closure_sla_eligible) if closure_sla_eligible else 100
    )
    claims_work = int(
        await session.scalar(
            select(func.count(Claim.id)).where(
                Claim.organization_id == organization_id,
                Claim.status.in_(["draft", "denied"]),
            )
        )
        or 0
    )
    appointment_ids = [appointment.id for appointment, *_ in schedule_rows]
    patient_ids = [appointment.patient_id for appointment, *_ in schedule_rows]
    eligibility_verified = int(
        await session.scalar(
            select(func.count(func.distinct(EligibilityCheck.appointment_id))).where(
                EligibilityCheck.organization_id == organization_id,
                EligibilityCheck.appointment_id.in_(appointment_ids),
                EligibilityCheck.status == "active",
                EligibilityCheck.responded_at.is_not(None),
            )
        )
        or 0
    )
    summaries_prepared = int(
        await session.scalar(
            select(func.count(func.distinct(AIRun.patient_id))).where(
                AIRun.organization_id == organization_id,
                AIRun.patient_id.in_(patient_ids),
                AIRun.capability == "chart_summary",
                AIRun.status == "completed",
            )
        )
        or 0
    )
    encounter_note_rows = (
        await session.execute(
            select(Encounter, EncounterNote)
            .outerjoin(
                EncounterNote,
                (EncounterNote.encounter_id == Encounter.id)
                & (EncounterNote.organization_id == organization_id),
            )
            .where(
                Encounter.organization_id == organization_id,
                Encounter.appointment_id.in_(appointment_ids),
            )
        )
    ).all()
    documentation_support_percent = (
        round(
            100
            * sum(
                note is not None and note.ai_run_id is not None
                for _encounter, note in encounter_note_rows
            )
            / len(encounter_note_rows)
        )
        if encounter_note_rows
        else 0
    )
    metric_policy = await session.scalar(
        select(AutomationPolicy).where(
            AutomationPolicy.organization_id == organization_id,
            AutomationPolicy.event_type == "metric_assumptions",
            AutomationPolicy.enabled.is_(True),
        )
    )
    summary_minutes_saved = summaries_prepared * int(
        (metric_policy.conditions_json if metric_policy else {}).get("aiRunMinutesAvoided", 0)
    )
    return {
        "current_time": scenario.current_time,
        "schedule": [
            {
                **row_dict(appointment),
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "medical_record_number": patient.medical_record_number,
                "provider_name": user.display_name,
                "high_priority": "changing" in appointment.reason.lower(),
            }
            for appointment, patient, _provider, user in schedule_rows
        ],
        "work_queue": [row_dict(task) for task in tasks[:20]],
        "counts": {
            "today_appointments": len(schedule_rows),
            "ready_patients": sum(a.readiness_status == "ready" for a, *_ in schedule_rows),
            "missing_intake": sum(a.readiness_status != "ready" for a, *_ in schedule_rows),
            "insurance_issues": sum(
                a.readiness_status == "insurance_issue" for a, *_ in schedule_rows
            ),
            "high_priority_concerns": sum(
                "changing" in a.reason.lower() for a, *_ in schedule_rows
            ),
            "unreviewed_pathology": open_pathology,
            "pathology_due_today": pathology_due_today,
            "pathology_closure_on_time_percent": pathology_closure_on_time_percent,
            "unsigned_notes": unsigned_notes,
            "refill_requests": sum(t.task_type == "refill" for t in tasks),
            "claims_requiring_work": claims_work,
            "eligibility_verified": eligibility_verified,
            "summaries_prepared": summaries_prepared,
            "summary_minutes_saved": summary_minutes_saved,
            "documentation_support_percent": documentation_support_percent,
        },
    }


async def calculate_mso_metrics(
    session: AsyncSession, organization_id: uuid.UUID
) -> dict[str, Any]:
    scenario = await get_demo_scenario(session, organization_id)
    appointments = (
        await session.scalars(
            select(Appointment).where(Appointment.organization_id == organization_id)
        )
    ).all()
    encounters = (
        await session.scalars(select(Encounter).where(Encounter.organization_id == organization_id))
    ).all()
    notes = (
        await session.scalars(
            select(EncounterNote).where(EncounterNote.organization_id == organization_id)
        )
    ).all()
    results = (
        await session.scalars(
            select(DiagnosticResult).where(DiagnosticResult.organization_id == organization_id)
        )
    ).all()
    claims = (
        await session.scalars(select(Claim).where(Claim.organization_id == organization_id))
    ).all()
    claim_events = (
        await session.scalars(
            select(ClaimEvent)
            .where(ClaimEvent.organization_id == organization_id)
            .order_by(ClaimEvent.occurred_at, ClaimEvent.created_at, ClaimEvent.id)
        )
    ).all()
    denials = (
        await session.scalars(select(Denial).where(Denial.organization_id == organization_id))
    ).all()
    payments = (
        await session.scalars(select(Payment).where(Payment.organization_id == organization_id))
    ).all()
    messages = (
        await session.scalars(
            select(Message)
            .where(Message.organization_id == organization_id)
            .order_by(Message.conversation_id, Message.sent_at)
        )
    ).all()
    ai_runs = int(
        await session.scalar(
            select(func.count(AIRun.id)).where(
                AIRun.organization_id == organization_id, AIRun.status == "completed"
            )
        )
        or 0
    )
    reminders = int(
        await session.scalar(
            select(func.count(AppointmentReminder.id)).where(
                AppointmentReminder.organization_id == organization_id,
                AppointmentReminder.delivery_status == "delivered",
            )
        )
        or 0
    )
    qualified_initiations = (
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "patient_concern_qualified",
            )
        )
    ).all()
    booked_initiations = [
        event for event in qualified_initiations if event.detail_json.get("appointmentId")
    ]
    metric_policy = await session.scalar(
        select(AutomationPolicy).where(
            AutomationPolicy.organization_id == organization_id,
            AutomationPolicy.event_type == "metric_assumptions",
            AutomationPolicy.enabled.is_(True),
        )
    )
    assumptions = metric_policy.conditions_json if metric_policy else {}
    ai_minutes_avoided = int(assumptions.get("aiRunMinutesAvoided", 0))
    reminder_minutes_avoided = int(assumptions.get("deliveredReminderMinutesAvoided", 0))

    completed = [item for item in appointments if item.status == "completed"]
    no_shows = [item for item in appointments if item.status == "no_show"]
    no_show_eligible = [*completed, *no_shows]
    signed_notes = [item for item in notes if item.signed_at is not None]
    encounter_by_id = {item.id: item for item in encounters}
    sign_minutes = [
        (note.signed_at - encounter_by_id[note.encounter_id].completed_at).total_seconds() / 60
        for note in signed_notes
        if note.encounter_id in encounter_by_id
        and encounter_by_id[note.encounter_id].completed_at is not None
    ]
    closed_pathology = [item for item in results if item.patient_notified_at is not None]
    pathology_hours = [
        (item.patient_notified_at - item.resulted_at).total_seconds() / 3600
        for item in closed_pathology
    ]
    first_outcome_by_claim: dict[uuid.UUID, str] = {}
    payer_outcomes = {"accepted", "adjudicated", "paid", "denied"}
    for event in claim_events:
        if event.to_status in payer_outcomes and event.claim_id not in first_outcome_by_claim:
            first_outcome_by_claim[event.claim_id] = event.to_status
    outcome_claim_ids = set(first_outcome_by_claim)
    first_pass_denied_claim_ids = {
        claim_id for claim_id, outcome in first_outcome_by_claim.items() if outcome == "denied"
    }
    accepted_claim_ids = outcome_claim_ids - first_pass_denied_claim_ids
    open_claims = [
        item for item in claims if item.status not in {"paid"} and item.submitted_at is not None
    ]
    weighted_ar: list[tuple[float, Decimal]] = []
    for item in open_claims:
        days_open = max(0.0, (scenario.current_time - item.submitted_at).total_seconds() / 86400)
        collectible = (
            item.allowed_amount
            if item.adjudicated_at is not None or item.allowed_amount > 0
            else item.total_charge
        )
        outstanding = max(Decimal("0"), collectible - item.paid_amount)
        if outstanding:
            weighted_ar.append((days_open, outstanding))
    patient_messages = [item for item in messages if item.sender_kind == "patient"]
    response_hours: list[float] = []
    by_conversation: dict[uuid.UUID, list[Message]] = defaultdict(list)
    for message in messages:
        by_conversation[message.conversation_id].append(message)
    for patient_message in patient_messages:
        next_response = next(
            (
                item
                for item in by_conversation[patient_message.conversation_id]
                if item.sent_at > patient_message.sent_at
                and item.sender_kind in {"staff", "provider"}
            ),
            None,
        )
        if next_response:
            response_hours.append(
                (next_response.sent_at - patient_message.sent_at).total_seconds() / 3600
            )
    claim_by_id = {claim.id: claim for claim in claims}
    completed_encounter_ids = {
        encounter.id for encounter in encounters if encounter.status == "completed"
    }
    allocated_payments = [
        payment
        for payment in payments
        if payment.status == "settled"
        and payment.claim_id in claim_by_id
        and claim_by_id[payment.claim_id].encounter_id in completed_encounter_ids
    ]
    collected = sum((payment.amount for payment in allocated_payments), Decimal("0"))
    total_ar_balance = sum((weight for _days, weight in weighted_ar), Decimal("0"))
    weighted_days_in_ar = (
        sum(days * float(weight) for days, weight in weighted_ar) / float(total_ar_balance)
        if total_ar_balance
        else 0.0
    )
    read_outbound = [
        item
        for item in messages
        if item.sender_kind in {"staff", "provider"} and item.read_at is not None
    ]
    outbound = [item for item in messages if item.sender_kind in {"staff", "provider"}]
    return {
        "calculated_at": scenario.current_time,
        "source": "tenant-scoped durable records",
        "appointment_conversion_percent": _percent(
            len(booked_initiations), len(qualified_initiations)
        ),
        "no_show_rate_percent": _percent(len(no_shows), len(no_show_eligible)),
        "median_patient_response_hours": round(median(response_hours), 1)
        if response_hours
        else None,
        "median_time_to_signed_note_minutes": round(median(sign_minutes), 1)
        if sign_minutes
        else None,
        "open_pathology": sum(
            item.status == "final" and item.patient_notified_at is None for item in results
        ),
        "median_pathology_closure_hours": round(median(pathology_hours), 1)
        if pathology_hours
        else None,
        "claim_acceptance_percent": _percent(len(accepted_claim_ids), len(outcome_claim_ids)),
        "denial_rate_percent": _percent(len(first_pass_denied_claim_ids), len(outcome_claim_ids)),
        "average_days_in_ar": round(weighted_days_in_ar, 1),
        "revenue_per_completed_visit": round(float(collected) / len(completed), 2)
        if completed
        else 0.0,
        "median_documentation_minutes": round(median(sign_minutes), 1) if sign_minutes else None,
        "estimated_staff_minutes_avoided": (
            ai_runs * ai_minutes_avoided + reminders * reminder_minutes_avoided
        ),
        "patient_satisfaction_indicators": {
            "message_read_rate_percent": _percent(len(read_outbound), len(outbound)),
            "portal_engagement_count": len(patient_messages),
        },
        "supporting_counts": {
            "appointments": len(appointments),
            "no_show_eligible_visits": len(no_show_eligible),
            "completed_visits": len(completed),
            "claims": len(claims),
            "denials": len(denials),
            "first_pass_denied_claims": len(first_pass_denied_claim_ids),
            "payer_outcome_claims": len(outcome_claim_ids),
            "pending_submitted_claims": sum(item.status == "submitted" for item in claims),
            "patient_messages_eligible_for_response": len(patient_messages),
            "patient_messages_with_response": len(response_hours),
            "completed_encounters_eligible_for_signing": len(completed_encounter_ids),
            "signed_encounters": len(sign_minutes),
            "final_pathology_results": sum(item.status == "final" for item in results),
            "notified_pathology_results": len(pathology_hours),
            "payments": len(payments),
            "ai_runs": ai_runs,
            "pathology": len(results),
            "qualified_initiations": len(qualified_initiations),
            "booked_initiations": len(booked_initiations),
            "open_ar_balance": total_ar_balance,
            "allocated_payments": len(allocated_payments),
        },
        "definitions": {
            "appointment_conversion": "Qualified patient-concern audit events with a durable appointment ID divided by all qualified concern events.",
            "no_show_rate": "No-show visits divided by completed plus no-show visits; future, booked, cancelled, and in-progress appointments are excluded.",
            "first_pass_claim_acceptance": "Claims whose first durable payer outcome was accepted, adjudicated, or paid divided by claims with a first payer outcome; pending submissions are excluded.",
            "denial_rate": "Claims whose first durable payer outcome was denied divided by claims with a first payer outcome; pending submissions are excluded.",
            "days_in_ar": "Net collectible-weighted days since submission for unpaid claims: charge before adjudication, then allowed minus paid.",
            "revenue_per_visit": "Settled payments allocated through claims to completed encounters divided by completed encounters.",
            "staff_work_avoided": "Completed AI runs and delivered reminders multiplied by the active versioned metric-assumptions automation policy.",
        },
        "assumptions": {
            "policy_id": metric_policy.id if metric_policy else None,
            "policy_version": assumptions.get("version"),
            "ai_run_minutes_avoided": ai_minutes_avoided,
            "delivered_reminder_minutes_avoided": reminder_minutes_avoided,
            "metric_targets": assumptions.get("metricTargets", {}),
        },
    }


async def rcm_workspace(session: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(Claim, Patient)
            .join(
                Patient,
                (Patient.id == Claim.patient_id) & (Patient.organization_id == organization_id),
            )
            .where(Claim.organization_id == organization_id)
            .order_by(Claim.created_at.desc())
        )
    ).all()
    denials = (
        await session.scalars(select(Denial).where(Denial.organization_id == organization_id))
    ).all()
    denial_by_claim = {item.claim_id: item for item in denials}
    total_charges = sum((claim.total_charge for claim, _ in rows), Decimal("0"))
    total_paid = sum((claim.paid_amount for claim, _ in rows), Decimal("0"))
    return {
        "summary": {
            "total_claims": len(rows),
            "charges": total_charges,
            "paid": total_paid,
            "open_denials": sum(item.status == "open" for item in denials),
            "remaining": total_charges - total_paid,
        },
        "claims": [
            {
                **row_dict(claim),
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "denial": row_dict(denial_by_claim[claim.id])
                if claim.id in denial_by_claim
                else None,
            }
            for claim, patient in rows
        ],
    }


async def complete_encounter_review(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    encounter_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    signature_secret: str,
    selected_action_ids: list[uuid.UUID] | None = None,
    expected_note_version: int,
    expected_note_hash: str,
    attestation: str = "Clinician reviewed and approved all selected actions.",
) -> dict[str, Any]:
    encounter = await session.scalar(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.organization_id == organization_id,
        )
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    assigned_provider = await session.scalar(
        select(Provider).where(
            Provider.id == encounter.provider_id,
            Provider.organization_id == organization_id,
        )
    )
    if assigned_provider is None:
        raise HTTPException(status_code=409, detail="Encounter has no assigned provider")
    if assigned_provider.user_id != reviewer_user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned encounter provider may sign without a durable delegation",
        )
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.encounter_id == encounter.id,
            EncounterNote.organization_id == organization_id,
        )
    )
    if note is None:
        raise HTTPException(status_code=409, detail="Encounter has no note to sign")
    if note.status in {"signed", "amended"}:
        return await get_encounter_bundle(session, organization_id, encounter.id)
    current_note_version = await session.scalar(
        select(NoteVersion).where(
            NoteVersion.note_id == note.id,
            NoteVersion.organization_id == organization_id,
            NoteVersion.version_number == note.current_version,
        )
    )
    if current_note_version is None:
        raise HTTPException(status_code=409, detail="Current note version is unavailable")
    if (
        note.current_version != expected_note_version
        or current_note_version.content_hash != expected_note_hash
    ):
        raise HTTPException(
            status_code=409,
            detail="The note changed in another tab; reload before signing",
        )
    signed_at = await domain_now(session, organization_id)
    offered_actions = (
        await session.scalars(
            select(ProposedAction)
            .where(
                ProposedAction.organization_id == organization_id,
                ProposedAction.patient_id == encounter.patient_id,
                ProposedAction.status == "proposed",
                or_(ProposedAction.entity_id == encounter.id, ProposedAction.entity_id == note.id),
            )
            .order_by(ProposedAction.created_at, ProposedAction.id)
        )
    ).all()
    offered_by_id = {action.id: action for action in offered_actions}
    selected_ids = set(selected_action_ids or offered_by_id)
    if selected_action_ids and selected_ids != selected_ids.intersection(offered_by_id):
        raise HTTPException(
            status_code=422,
            detail="Every selected action must belong to this encounter and await approval",
        )
    actions = [action for action in offered_actions if action.id in selected_ids]
    required = {
        "sign_note",
        "confirm_biopsy_consent",
        "create_shave_biopsy",
        "create_pathology_order",
        "create_specimen",
        "apply_coding",
        "send_aftercare",
        "create_pathology_task",
    }
    if not required.issubset({action.action_type for action in actions}):
        raise HTTPException(
            status_code=409,
            detail="Review must approve the note, biopsy, pathology order, coding, and aftercare actions",
        )
    lesion_values = {
        action.payload_json.get("lesionId")
        for action in actions
        if action.action_type in {"create_shave_biopsy", "create_pathology_order"}
    }
    if None in lesion_values or len(lesion_values) != 1:
        raise HTTPException(
            status_code=409,
            detail="Biopsy and pathology actions must identify the same lesion",
        )
    try:
        lesion_id = uuid.UUID(str(next(iter(lesion_values))))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Approved lesion ID is invalid") from exc
    lesion = await session.scalar(
        select(Lesion).where(
            Lesion.id == lesion_id,
            Lesion.patient_id == encounter.patient_id,
            Lesion.organization_id == organization_id,
        )
    )
    if lesion is None:
        raise HTTPException(status_code=409, detail="Approved lesion is not part of this encounter")
    aftercare_action = next(
        (action for action in actions if action.action_type == "send_aftercare"), None
    )
    try:
        aftercare_draft_id = uuid.UUID(str(aftercare_action.payload_json.get("draftId")))
    except (AttributeError, ValueError) as exc:
        raise HTTPException(
            status_code=409, detail="Approved aftercare action has no durable draft"
        ) from exc
    aftercare_draft = await session.scalar(
        select(MessageDraft).where(
            MessageDraft.id == aftercare_draft_id,
            MessageDraft.organization_id == organization_id,
            MessageDraft.status == "proposed",
            MessageDraft.ai_run_id == aftercare_action.ai_run_id,
        )
    )
    if aftercare_draft is None:
        raise HTTPException(
            status_code=409,
            detail="Approved aftercare action is not linked to an approvable AI draft",
        )
    consent = await session.scalar(
        select(Consent).where(
            Consent.organization_id == organization_id,
            Consent.patient_id == encounter.patient_id,
            Consent.encounter_id == encounter.id,
            Consent.consent_type == "shave_biopsy",
            Consent.revoked_at.is_(None),
        )
    )
    if (
        consent is None
        or not consent.accepted_by_name.strip()
        or not consent.signature_text.strip()
        or not consent.version.strip()
        or consent.accepted_at is None
    ):
        raise HTTPException(
            status_code=409,
            detail="A signed, active, versioned shave-biopsy consent linked to this encounter is required",
        )
    proposal_payload_hashes: dict[uuid.UUID, str] = {}
    observation_resources = [
        _observation_resource(
            resource_type="encounter",
            resource_id=encounter.id,
            content_hash=hash_json(
                {
                    "appointmentId": str(encounter.appointment_id),
                    "patientId": str(encounter.patient_id),
                    "providerId": str(encounter.provider_id),
                    "status": encounter.status,
                    "startedAt": encounter.started_at,
                    "chiefComplaintHash": hashlib.sha256(
                        encounter.chief_complaint.encode()
                    ).hexdigest(),
                    "ambientTranscriptHash": (
                        hashlib.sha256(encounter.ambient_transcript.encode()).hexdigest()
                        if encounter.ambient_transcript
                        else None
                    ),
                }
            ),
            effective_at=encounter.started_at,
            recorded_at=encounter.updated_at,
        ),
        _observation_resource(
            resource_type="note_version",
            resource_id=current_note_version.id,
            resource_version=current_note_version.version_number,
            content_hash=current_note_version.content_hash,
            effective_at=current_note_version.created_at,
            recorded_at=current_note_version.created_at,
        ),
        _observation_resource(
            resource_type="consent",
            resource_id=consent.id,
            content_hash=hash_json(
                {
                    "encounterId": str(consent.encounter_id),
                    "consentType": consent.consent_type,
                    "documentVersion": consent.version,
                    "acceptedAt": consent.accepted_at,
                    "revokedAt": consent.revoked_at,
                    "signatureHash": hashlib.sha256(consent.signature_text.encode()).hexdigest(),
                }
            ),
            effective_at=consent.accepted_at,
            recorded_at=consent.updated_at,
        ),
        _observation_resource(
            resource_type="lesion",
            resource_id=lesion.id,
            content_hash=hash_json(
                {
                    "patientId": str(lesion.patient_id),
                    "status": lesion.status,
                    "anatomicalLocationHash": hashlib.sha256(
                        lesion.anatomical_location.encode()
                    ).hexdigest(),
                }
            ),
            recorded_at=lesion.updated_at,
        ),
        _observation_resource(
            resource_type="message_draft",
            resource_id=aftercare_draft.id,
            content_hash=hash_json(
                {
                    "conversationId": str(aftercare_draft.conversation_id),
                    "status": aftercare_draft.status,
                    "bodyHash": hashlib.sha256(aftercare_draft.body.encode()).hexdigest(),
                    "aiRunId": str(aftercare_draft.ai_run_id)
                    if aftercare_draft.ai_run_id
                    else None,
                }
            ),
            recorded_at=aftercare_draft.updated_at,
        ),
    ]
    for action in offered_actions:
        payload_hash = action.payload_hash or hash_json(action.payload_json)
        proposal_payload_hashes[action.id] = payload_hash
        action.payload_hash = payload_hash
        observation_resources.append(
            _observation_resource(
                resource_type="proposed_action",
                resource_id=action.id,
                resource_version=action.proposal_version,
                content_hash=hash_json(
                    {
                        "actionType": action.action_type,
                        "entityType": action.entity_type,
                        "entityId": str(action.entity_id) if action.entity_id else None,
                        "payloadHash": payload_hash,
                        "rationaleHash": hashlib.sha256(action.rationale.encode()).hexdigest(),
                        "status": action.status,
                        "requiresApproval": action.requires_approval,
                        "aiRunId": str(action.ai_run_id) if action.ai_run_id else None,
                        "expectedTargetVersion": action.expected_target_version,
                    }
                ),
                recorded_at=action.updated_at,
            )
        )
    selected_action_refs = [
        {
            "id": str(action.id),
            "type": action.action_type,
            "version": action.proposal_version,
            "payloadHash": proposal_payload_hashes[action.id],
        }
        for action in actions
    ]
    rejected_action_ids = sorted(
        str(action.id) for action in offered_actions if action.id not in selected_ids
    )
    selection_hash = hash_json(
        {
            "noteHash": expected_note_hash,
            "selectedActionIds": sorted(str(action.id) for action in actions),
        }
    )
    trajectory_idempotency_key = (
        f"encounter-review:{encounter.id}:{expected_note_version}:{selection_hash[:32]}"
    )
    signature_payload = "|".join(
        [
            str(note.id),
            note.content,
            json.dumps(note.structured_content, sort_keys=True),
            str(reviewer_user_id),
            signed_at.isoformat(),
            signature_secret,
        ]
    )
    note.status = "signed"
    note.signed_at = signed_at
    note.signed_by_user_id = reviewer_user_id
    note.signature_hash = hashlib.sha256(signature_payload.encode()).hexdigest()
    for action in actions:
        action.status = "approved"
        session.add(
            Approval(
                organization_id=organization_id,
                proposed_action_id=action.id,
                reviewer_user_id=reviewer_user_id,
                decision="approved",
                comment=attestation,
                decided_at=signed_at,
                proposed_action_version=action.proposal_version,
                expected_target_version=(
                    action.expected_target_version
                    or (expected_note_version if action.action_type == "sign_note" else None)
                ),
                reviewer_role="provider",
                edit_diff_json={},
            )
        )

    procedure = await session.scalar(
        select(Procedure).where(
            Procedure.encounter_id == encounter.id,
            Procedure.organization_id == organization_id,
            Procedure.code == "11102",
        )
    )
    if procedure is None:
        procedure = Procedure(
            id=uuid.uuid5(encounter.id, "shave-biopsy"),
            organization_id=organization_id,
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            lesion_id=lesion.id,
            provider_id=encounter.provider_id,
            code="11102",
            code_system="CPT",
            display="Tangential biopsy of skin, single lesion",
            performed_at=signed_at,
            documentation=(
                "After informed consent, the left posterior shoulder was cleansed and anesthetized. "
                "A shave biopsy was performed to the dermis. Hemostasis was achieved with aluminum "
                "chloride, petrolatum and a pressure dressing were applied, and wound care was reviewed."
            ),
            status="completed",
        )
        session.add(procedure)
    lesion.status = "biopsied"
    order = await session.scalar(
        select(Order).where(
            Order.encounter_id == encounter.id,
            Order.organization_id == organization_id,
            Order.order_type == "surgical_pathology",
        )
    )
    if order is None:
        order = Order(
            id=uuid.uuid5(encounter.id, "pathology-order"),
            organization_id=organization_id,
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            lesion_id=lesion.id,
            ordering_provider_id=encounter.provider_id,
            order_type="surgical_pathology",
            code="DERMPATH",
            display="Dermatopathology examination",
            status="ordered",
            ordered_at=signed_at,
        )
        session.add(order)
    await session.flush()
    specimen = await session.scalar(
        select(Specimen).where(
            Specimen.order_id == order.id,
            Specimen.organization_id == organization_id,
        )
    )
    if specimen is None:
        specimen = Specimen(
            id=uuid.uuid5(order.id, "specimen"),
            organization_id=organization_id,
            order_id=order.id,
            procedure_id=procedure.id,
            patient_id=encounter.patient_id,
            lesion_id=lesion.id,
            accession_number=f"SYN-DP-{signed_at:%y%m%d}-{str(encounter.id)[:6].upper()}",
            specimen_type="shave biopsy",
            body_site="left posterior shoulder",
            collected_at=signed_at,
            status="in_transit",
        )
        session.add(specimen)
    lesion.status = "biopsied"
    encounter.status = "completed"
    encounter.completed_at = signed_at
    await pathology_provider.acknowledge_order(
        session, organization_id=organization_id, order_id=order.id
    )

    claim = await session.scalar(
        select(Claim).where(
            Claim.encounter_id == encounter.id,
            Claim.organization_id == organization_id,
        )
    )
    if claim is None:
        coverage = await session.scalar(
            select(Coverage).where(
                Coverage.patient_id == encounter.patient_id,
                Coverage.organization_id == organization_id,
                Coverage.status == "active",
            )
        )
        if coverage is None:
            raise HTTPException(
                status_code=409, detail="Active coverage is required to create claim"
            )
        claim = Claim(
            id=(
                canonical_ids()["sarah_claim_id"]
                if encounter.id == canonical_ids()["sarah_encounter_id"]
                else uuid.uuid5(encounter.id, "claim")
            ),
            organization_id=organization_id,
            claim_number=f"ADP-{signed_at:%y%m%d}-{str(encounter.patient_id)[:4].upper()}",
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            coverage_id=coverage.id,
            billing_provider_id=encounter.provider_id,
            status="draft",
            total_charge=Decimal("395.00"),
            patient_responsibility=Decimal("85.00"),
        )
        session.add(claim)
        await session.flush()
        session.add_all(
            [
                ClaimLine(
                    organization_id=organization_id,
                    claim_id=claim.id,
                    line_number=1,
                    procedure_code="99203",
                    diagnosis_codes=["D48.5"],
                    units=1,
                    charge_amount=Decimal("230.00"),
                ),
                ClaimLine(
                    organization_id=organization_id,
                    claim_id=claim.id,
                    line_number=2,
                    procedure_code="11102",
                    diagnosis_codes=["D48.5"],
                    units=1,
                    charge_amount=Decimal("165.00"),
                ),
            ]
        )
    claim.status = "draft"
    existing_claim_event = await session.scalar(
        select(ClaimEvent).where(
            ClaimEvent.claim_id == claim.id,
            ClaimEvent.event_type == "clinical_review_complete",
        )
    )
    if existing_claim_event is None:
        session.add(
            ClaimEvent(
                organization_id=organization_id,
                claim_id=claim.id,
                event_type="clinical_review_complete",
                from_status="draft",
                to_status="draft",
                occurred_at=signed_at,
                actor_kind="provider",
                detail_json={"codingApproved": True, "noteSignature": note.signature_hash},
            )
        )

    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == aftercare_draft.conversation_id,
            Conversation.patient_id == encounter.patient_id,
            Conversation.organization_id == organization_id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            organization_id=organization_id,
            patient_id=encounter.patient_id,
            subject="Biopsy aftercare",
            status="open",
            last_message_at=signed_at,
        )
        session.add(conversation)
        await session.flush()
    aftercare = Message(
        id=uuid.uuid5(encounter.id, "aftercare-message"),
        organization_id=organization_id,
        conversation_id=conversation.id,
        sender_user_id=reviewer_user_id,
        sender_kind="provider",
        body=aftercare_draft.body,
        status="sent",
        sent_at=signed_at,
        ai_run_id=aftercare_draft.ai_run_id,
    )
    session.add(aftercare)
    aftercare_draft.status = "approved"
    await session.flush()
    await messaging_provider.deliver_message(session, aftercare)
    pathology_task = await session.scalar(
        select(Task).where(
            Task.id == uuid.uuid5(encounter.id, "pathology-tracking-task"),
            Task.patient_id == encounter.patient_id,
            Task.encounter_id == encounter.id,
            Task.organization_id == organization_id,
            Task.task_type == "pathology_tracking",
        )
    )
    if pathology_task is None:
        pathology_task = Task(
            id=uuid.uuid5(encounter.id, "pathology-tracking-task"),
            organization_id=organization_id,
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            assigned_user_id=reviewer_user_id,
            task_type="pathology_tracking",
            title="Track pathology result and patient notification",
            description="Ensure the specimen results, clinician review occurs, and the patient is notified.",
            priority="high",
            status="open",
            due_at=signed_at + timedelta(days=5),
        )
        session.add(pathology_task)
    for task in (
        await session.scalars(
            select(Task).where(
                Task.encounter_id == encounter.id,
                Task.organization_id == organization_id,
                Task.task_type == "unsigned_note",
                Task.status != "completed",
            )
        )
    ).all():
        task.status = "completed"
        task.completed_at = signed_at
    workflow = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.entity_id == encounter.id,
            WorkflowRun.workflow_type == "biopsy_completion",
            WorkflowRun.organization_id == organization_id,
        )
    )
    if workflow:
        workflow.status = "completed"
        workflow.finished_at = signed_at
        workflow.output_json = {
            "noteId": str(note.id),
            "consentId": str(consent.id),
            "procedureId": str(procedure.id),
            "orderId": str(order.id),
            "specimenId": str(specimen.id),
            "claimId": str(claim.id),
            "messageId": str(aftercare.id),
            "taskId": str(pathology_task.id),
        }
        # Canonical runs already contain the proposals-ready event at sequence 1.
        # The max keeps pre-counter seeded runs safe while normal writes consume
        # the optimistic counter without a sequence scan.
        next_sequence = max(int(workflow.next_event_sequence), 2)
        workflow.next_event_sequence = next_sequence + 1
        session.add(
            WorkflowEvent(
                organization_id=organization_id,
                workflow_run_id=workflow.id,
                event_type="clinician_approved_and_executed",
                sequence=next_sequence,
                payload_json=workflow.output_json,
            )
        )
    session.add_all(
        [
            ProvenanceRecord(
                organization_id=organization_id,
                entity_type="encounter_note",
                entity_id=note.id,
                activity="clinician_approved_and_signed",
                actor_user_id=reviewer_user_id,
                ai_run_id=note.ai_run_id,
                source_entity_type="encounter",
                source_entity_id=encounter.id,
                detail_json={"signatureHash": note.signature_hash},
            ),
            ProvenanceRecord(
                organization_id=organization_id,
                entity_type="message",
                entity_id=aftercare.id,
                activity="human_approved_ai_draft",
                actor_user_id=reviewer_user_id,
                ai_run_id=aftercare_draft.ai_run_id,
                source_entity_type="message_draft",
                source_entity_id=aftercare_draft.id,
                detail_json={
                    "proposedActionId": str(aftercare_action.id),
                    "template": aftercare_action.payload_json.get("template"),
                    "editedBeforeSend": False,
                },
            ),
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=reviewer_user_id,
                action="encounter_review_completed",
                entity_type="encounter",
                entity_id=encounter.id,
                patient_id=encounter.patient_id,
                occurred_at=signed_at,
                detail_json={
                    "noteId": str(note.id),
                    "consentId": str(consent.id),
                    "attestation": attestation,
                    "procedureId": str(procedure.id),
                    "orderId": str(order.id),
                    "claimId": str(claim.id),
                },
            ),
        ]
    )
    episode = await _patient_learning_episode(
        session,
        organization_id=organization_id,
        patient_id=encounter.patient_id,
        started_at=encounter.started_at or signed_at,
    )
    review_event_payload = {
        "status": encounter.status,
        "noteRef": {
            "id": str(note.id),
            "version": expected_note_version,
            "contentHash": expected_note_hash,
            "signatureHash": note.signature_hash,
        },
        "selectedActions": selected_action_refs,
        "rejectedActionIds": rejected_action_ids,
        "resultRefs": {
            "consentId": str(consent.id),
            "procedureId": str(procedure.id),
            "orderId": str(order.id),
            "specimenId": str(specimen.id),
            "claimId": str(claim.id),
            "messageId": str(aftercare.id),
            "pathologyTaskId": str(pathology_task.id),
            "workflowId": str(workflow.id) if workflow else None,
        },
    }
    if episode is not None:
        event, decision, action_attempt = await record_decision_trajectory(
            session,
            organization_id=organization_id,
            episode=episode,
            decision_type="encounter_review",
            available_actions=sorted({action.action_type for action in offered_actions}),
            selected_action="complete_encounter_review",
            observation_resources=observation_resources,
            actor_kind="human",
            actor_user_id=reviewer_user_id,
            actor_role="provider",
            occurred_at=signed_at,
            aggregate_type="encounter",
            aggregate_id=encounter.id,
            aggregate_sequence=2,
            event_type="encounter.review_completed",
            event_payload=review_event_payload,
            idempotency_key=trajectory_idempotency_key,
            patient_id=encounter.patient_id,
            action_arguments={
                "selectedActions": selected_action_refs,
                "rejectedActionIds": rejected_action_ids,
                "attestationHash": hashlib.sha256(attestation.encode()).hexdigest(),
            },
            expected_target_type="encounter_note",
            expected_target_id=note.id,
            expected_target_version=expected_note_version,
        )
        # Persist the manifest and decision before the action. The learning
        # tables use composite tenant foreign keys without ORM relationships,
        # so an explicit dependency flush keeps SQLite and Postgres ordering
        # identical while retaining one transaction.
        session.expunge(action_attempt)
        await session.flush()
        session.add(action_attempt)
        await session.flush()
        await record_outcome(
            session,
            organization_id=organization_id,
            episode=episode,
            outcome_type="encounter.review_execution",
            value={
                "status": encounter.status,
                "noteSigned": note.status == "signed",
                "consentVerified": True,
                "procedureRecorded": procedure.status == "completed",
                "pathologyOrderCreated": order.status == "ordered",
                "specimenTracked": specimen.status == "in_transit",
                "aftercareSent": aftercare.status == "sent",
                "pathologyTrackingTaskOpen": pathology_task.status == "open",
                "claimStatus": claim.status,
            },
            provenance_kind="observed",
            observed_at=signed_at,
            decision=decision,
            action=action_attempt,
            source_event=event,
        )
    else:
        await record_domain_event(
            session,
            organization_id=organization_id,
            event_type="encounter.review_completed",
            aggregate_type="encounter",
            aggregate_id=encounter.id,
            aggregate_sequence=2,
            patient_id=encounter.patient_id,
            actor_kind="human",
            actor_user_id=reviewer_user_id,
            actor_role="provider",
            occurred_at=signed_at,
            effective_at=signed_at,
            payload=review_event_payload,
            idempotency_key=trajectory_idempotency_key,
            sensitivity="restricted",
        )
    await set_demo_chapter(session, organization_id, "review_complete")
    await session.flush()
    return await get_encounter_bundle(session, organization_id, encounter.id)


async def trigger_sarah_pathology(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    signature_secret: str,
) -> DiagnosticResult:
    ids = canonical_ids()
    encounter = await session.scalar(
        select(Encounter).where(
            Encounter.id == ids["sarah_encounter_id"],
            Encounter.organization_id == organization_id,
        )
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Sarah's encounter is unavailable")
    procedure = await session.scalar(
        select(Procedure).where(
            Procedure.encounter_id == encounter.id,
            Procedure.organization_id == organization_id,
        )
    )
    if procedure is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Pathology cannot arrive before clinician review creates the signed note, "
                "procedure, order, and specimen"
            ),
        )
    order = await session.scalar(
        select(Order).where(
            Order.encounter_id == encounter.id,
            Order.organization_id == organization_id,
            Order.order_type == "surgical_pathology",
        )
    )
    if procedure is None or order is None:
        raise HTTPException(status_code=409, detail="Biopsy workflow is incomplete")
    specimen = await session.scalar(
        select(Specimen).where(
            Specimen.order_id == order.id,
            Specimen.organization_id == organization_id,
        )
    )
    if specimen is None:
        raise HTTPException(status_code=409, detail="Pathology specimen is unavailable")
    if not (
        procedure.lesion_id == order.lesion_id == specimen.lesion_id
        and specimen.procedure_id == procedure.id
        and specimen.order_id == order.id
    ):
        raise HTTPException(status_code=409, detail="Pathology chain references are inconsistent")
    existing = await session.scalar(
        select(DiagnosticResult).where(
            DiagnosticResult.order_id == order.id,
            DiagnosticResult.organization_id == organization_id,
        )
    )
    if existing:
        return existing
    source_refs = {
        "procedure": {
            "id": str(procedure.id),
            "version": 1,
            "contentHash": hash_json(
                {
                    "encounterId": str(procedure.encounter_id),
                    "patientId": str(procedure.patient_id),
                    "lesionId": str(procedure.lesion_id) if procedure.lesion_id else None,
                    "code": procedure.code,
                    "performedAt": procedure.performed_at,
                    "status": procedure.status,
                    "documentationHash": hashlib.sha256(
                        procedure.documentation.encode()
                    ).hexdigest(),
                }
            ),
        },
        "order": {
            "id": str(order.id),
            "version": 1,
            "contentHash": hash_json(
                {
                    "encounterId": str(order.encounter_id),
                    "patientId": str(order.patient_id),
                    "lesionId": str(order.lesion_id) if order.lesion_id else None,
                    "orderType": order.order_type,
                    "code": order.code,
                    "status": order.status,
                    "orderedAt": order.ordered_at,
                }
            ),
        },
        "specimen": {
            "id": str(specimen.id),
            "version": 1,
            "contentHash": hash_json(
                {
                    "orderId": str(specimen.order_id),
                    "procedureId": str(specimen.procedure_id),
                    "patientId": str(specimen.patient_id),
                    "lesionId": str(specimen.lesion_id),
                    "accessionNumberHash": hashlib.sha256(
                        specimen.accession_number.encode()
                    ).hexdigest(),
                    "collectedAt": specimen.collected_at,
                    "status": specimen.status,
                }
            ),
        },
    }
    scenario = await get_demo_scenario(session, organization_id)
    scenario_time = scenario.current_time.replace(tzinfo=scenario.current_time.tzinfo or UTC)
    result_time = max(scenario_time, DEMO_NOW + timedelta(days=3))
    result = DiagnosticResult(
        id=uuid.uuid5(order.id, "result"),
        organization_id=organization_id,
        order_id=order.id,
        specimen_id=specimen.id,
        patient_id=encounter.patient_id,
        lesion_id=procedure.lesion_id,
        procedure_id=procedure.id,
        clinician_id=encounter.provider_id,
        result_type="surgical_pathology",
        status="final",
        diagnosis="Compound dysplastic melanocytic nevus with moderate atypia; examined margins are clear",
        narrative=(
            "Sections show a compound melanocytic proliferation with architectural disorder and "
            "moderate cytologic atypia. No melanoma is identified. The examined tissue margins are free."
        ),
        summary=(
            "Moderately atypical compound dysplastic nevus. No melanoma. Examined margins are clear; "
            "clinical monitoring is appropriate."
        ),
        resulted_at=result_time,
    )
    session.add(result)
    order.status = "resulted"
    specimen.status = "resulted"
    await session.flush()
    run, summary = await run_ai(
        session,
        organization_id=organization_id,
        capability="pathology_summary",
        context={
            "patientName": "Sarah Mitchell",
            "diagnosis": result.diagnosis,
            "narrative": result.narrative,
        },
        patient_id=encounter.patient_id,
        requested_by_user_id=actor_user_id,
    )
    task = Task(
        id=uuid.uuid5(result.id, "review-task"),
        organization_id=organization_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        assigned_user_id=(await session.get(Provider, encounter.provider_id)).user_id,
        task_type="pathology_review",
        title="Review Sarah Mitchell's final pathology",
        description=summary.clinician_summary,
        priority="high",
        status="open",
        due_at=result_time + timedelta(hours=24),
    )
    conversation_id = uuid.uuid5(encounter.id, "pathology-conversation")
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.patient_id == encounter.patient_id,
            Conversation.organization_id == organization_id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            id=conversation_id,
            organization_id=organization_id,
            patient_id=encounter.patient_id,
            subject="Pathology result and follow-up",
            status="open",
            assigned_user_id=task.assigned_user_id,
            last_message_at=result_time,
        )
        session.add(conversation)
        await session.flush()
    draft = MessageDraft(
        id=uuid.uuid5(result.id, "patient-draft"),
        organization_id=organization_id,
        conversation_id=conversation.id,
        author_user_id=None,
        body=summary.patient_friendly_summary,
        status="proposed",
        confidence=Decimal("0.990"),
        ai_run_id=run.id,
    )
    session.add_all([task, draft])
    scenario.current_time = result_time
    await set_demo_chapter(session, organization_id, "pathology")
    for event in (
        await session.scalars(
            select(DemoTimelineEvent).where(
                DemoTimelineEvent.demo_scenario_id == scenario.id,
                DemoTimelineEvent.event_type == "pathology_result_arrives",
            )
        )
    ).all():
        event.status = "completed"
        event.executed_at = result_time
    session.add_all(
        [
            ProvenanceRecord(
                organization_id=organization_id,
                entity_type="diagnostic_result",
                entity_id=result.id,
                activity="received_and_summarized",
                actor_user_id=actor_user_id,
                ai_run_id=run.id,
                source_entity_type="specimen",
                source_entity_id=specimen.id,
                detail_json={"network": "simulated_pathology", "humanReviewRequired": True},
            ),
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="pathology_result_received",
                entity_type="diagnostic_result",
                entity_id=result.id,
                patient_id=encounter.patient_id,
                occurred_at=result_time,
                detail_json={"taskId": str(task.id), "messageDraftId": str(draft.id)},
            ),
        ]
    )
    episode = await _patient_learning_episode(
        session,
        organization_id=organization_id,
        patient_id=encounter.patient_id,
        started_at=encounter.started_at or result_time,
    )
    result_content_hash = hash_json(
        {
            "orderId": str(result.order_id),
            "specimenId": str(result.specimen_id),
            "patientId": str(result.patient_id),
            "lesionId": str(result.lesion_id),
            "procedureId": str(result.procedure_id),
            "resultType": result.result_type,
            "status": result.status,
            "diagnosisHash": hashlib.sha256(result.diagnosis.encode()).hexdigest(),
            "narrativeHash": hashlib.sha256(result.narrative.encode()).hexdigest(),
            "summaryHash": hashlib.sha256(result.summary.encode()).hexdigest(),
            "resultedAt": result.resulted_at,
        }
    )
    event = await record_domain_event(
        session,
        organization_id=organization_id,
        event_type="pathology.result_received",
        aggregate_type="diagnostic_result",
        aggregate_id=result.id,
        aggregate_sequence=1,
        patient_id=encounter.patient_id,
        actor_kind="external_system",
        actor_user_id=actor_user_id,
        actor_role="presenter",
        occurred_at=result_time,
        effective_at=result_time,
        correlation_id=str(episode.id) if episode else None,
        payload={
            "status": result.status,
            "resultContentHash": result_content_hash,
            "sourceRefs": source_refs,
            "resultRefs": {
                "aiRunId": str(run.id),
                "aiSummaryHash": hash_json(summary.model_dump(mode="json", by_alias=True)),
                "reviewTaskId": str(task.id),
                "messageDraftId": str(draft.id),
                "messageDraftBodyHash": hashlib.sha256(draft.body.encode()).hexdigest(),
            },
            "humanReviewRequired": True,
            "provider": "simulated_pathology",
        },
        idempotency_key=f"pathology-result:{result.id}:received:v1",
        sensitivity="restricted",
    )
    if episode is not None:
        await _link_episode_event(
            session,
            organization_id=organization_id,
            episode=episode,
            event=event,
            role="outcome",
        )
        await record_outcome(
            session,
            organization_id=organization_id,
            episode=episode,
            outcome_type="pathology.result_available",
            value={
                "resultStatus": result.status,
                "orderStatus": order.status,
                "specimenStatus": specimen.status,
                "reviewTaskStatus": task.status,
                "messageDraftStatus": draft.status,
                "humanReviewRequired": True,
            },
            provenance_kind="simulated",
            observed_at=result_time,
            source_event=event,
            simulator_version="simulated-pathology-2026.1",
        )
    await session.flush()
    return result


async def advance_demo_time(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    days: int,
    hours: int,
    chapter: str | None,
    signature_secret: str,
) -> dict[str, Any]:
    scenario = await get_demo_scenario(session, organization_id)
    scenario.current_time += timedelta(days=days, hours=hours)
    if chapter:
        await set_demo_chapter(session, organization_id, chapter)
    events = (
        await session.scalars(
            select(DemoTimelineEvent)
            .where(
                DemoTimelineEvent.demo_scenario_id == scenario.id,
                DemoTimelineEvent.status == "pending",
                DemoTimelineEvent.scheduled_for <= scenario.current_time,
            )
            .order_by(DemoTimelineEvent.sequence)
        )
    ).all()
    executed: list[str] = []
    for event in events:
        if event.event_type == "pathology_result_arrives":
            await trigger_sarah_pathology(
                session,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                signature_secret=signature_secret,
            )
        elif event.event_type.startswith("claim_"):
            target = event.event_type.removeprefix("claim_")
            claim = await session.scalar(
                select(Claim).where(
                    Claim.id == canonical_ids()["sarah_claim_id"],
                    Claim.organization_id == organization_id,
                )
            )
            if claim is None:
                raise HTTPException(
                    status_code=409,
                    detail="Claim timeline cannot advance before clinician review creates the claim",
                )
            for _ in range(5):
                if claim.status == target:
                    break
                before = claim.status
                await clearinghouse_provider.advance(session, claim)
                if claim.status == before:
                    break
        event.status = "completed"
        event.executed_at = scenario.current_time
        executed.append(event.event_type)
    session.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="demo_time_advanced",
            entity_type="demo_scenario",
            entity_id=scenario.id,
            occurred_at=scenario.current_time,
            detail_json={
                "days": days,
                "hours": hours,
                "currentTime": scenario.current_time.isoformat(),
                "executed": executed,
            },
        )
    )
    await session.flush()
    return {**row_dict(scenario), "executed_events": executed}


async def demo_bootstrap(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    session_payload: dict[str, Any],
) -> dict[str, Any]:
    runtime = get_settings()
    ids = canonical_ids()
    roles = set(session_payload.get("roles") or [])
    scenario = await get_demo_scenario(session, organization_id)
    organization = await session.scalar(
        select(Organization).where(Organization.id == organization_id)
    )
    location = await session.scalar(
        select(Location)
        .where(Location.organization_id == organization_id)
        .order_by(Location.created_at)
    )
    booked_row = (
        await session.execute(
            select(Appointment, Provider, User, Location)
            .join(
                Provider,
                (Provider.id == Appointment.provider_id)
                & (Provider.organization_id == organization_id),
            )
            .join(
                User,
                (User.id == Provider.user_id) & (User.organization_id == organization_id),
            )
            .join(
                Location,
                (Location.id == Appointment.location_id)
                & (Location.organization_id == organization_id),
            )
            .where(
                Appointment.id == ids["sarah_appointment_id"],
                Appointment.patient_id == ids["sarah_patient_id"],
                Appointment.organization_id == organization_id,
            )
        )
    ).first()
    sarah = await get_patient_bundle(session, organization_id, ids["sarah_patient_id"])
    encounter_bundle = await get_encounter_bundle(
        session, organization_id, ids["sarah_encounter_id"]
    )
    dashboard = await command_center(session, organization_id)
    metric_values = await calculate_mso_metrics(session, organization_id)
    availability = await get_availability(session, organization_id)
    local_zone = ZoneInfo(organization.timezone)

    persona_rows = (
        await session.execute(
            select(User, Role)
            .join(
                Membership,
                (Membership.user_id == User.id) & (Membership.organization_id == organization_id),
            )
            .join(Role, Role.id == Membership.role_id)
            .where(
                User.organization_id == organization_id,
                User.persona_key.is_not(None),
                User.is_active.is_(True),
            )
        )
    ).all()
    persona_titles = {
        "patient": "Patient",
        "provider": "Dermatologist",
        "clinical": "Clinical coordinator",
        "biller": "RCM specialist",
        "owner": "MSO owner",
    }
    personas = sorted(
        [
            {
                "id": user.persona_key,
                "name": user.display_name,
                "title": persona_titles[user.persona_key],
                "initials": "".join(
                    part[0] for part in user.display_name.replace("Dr. ", "").split()[:2]
                ),
            }
            for user, _role in persona_rows
        ],
        key=lambda item: ["patient", "provider", "clinical", "biller", "owner"].index(item["id"]),
    )

    contacts = (
        await session.scalars(
            select(PatientContact).where(
                PatientContact.organization_id == organization_id,
                PatientContact.patient_id == ids["sarah_patient_id"],
            )
        )
    ).all()
    pharmacy = next((item for item in contacts if item.kind == "pharmacy"), None)
    problems = (
        await session.scalars(
            select(Problem).where(
                Problem.organization_id == organization_id,
                Problem.patient_id == ids["sarah_patient_id"],
                Problem.status == "active",
            )
        )
    ).all()
    active_lesion = next(item for item in sarah["lesions"] if item["id"] == ids["sarah_lesion_id"])
    active_lesion_bundle = next(
        item for item in encounter_bundle["lesions"] if item["id"] == ids["sarah_lesion_id"]
    )
    latest_observation = active_lesion_bundle["observations"][-1]
    overview = next(
        (item for item in active_lesion_bundle["images"] if item["view"] == "overview"), None
    )
    dermoscopy = next(
        (item for item in active_lesion_bundle["images"] if item["view"] == "dermoscopy"), None
    )
    overview_file = (
        await session.scalar(
            select(FileRecord).where(
                FileRecord.id == overview["file_record_id"],
                FileRecord.organization_id == organization_id,
                FileRecord.patient_id == ids["sarah_patient_id"],
            )
        )
        if overview
        else None
    )
    dermoscopy_file = (
        await session.scalar(
            select(FileRecord).where(
                FileRecord.id == dermoscopy["file_record_id"],
                FileRecord.organization_id == organization_id,
                FileRecord.patient_id == ids["sarah_patient_id"],
            )
        )
        if dermoscopy
        else None
    )
    if not all([overview, overview_file, dermoscopy, dermoscopy_file]):
        raise HTTPException(
            status_code=503,
            detail="Canonical lesion image metadata is incomplete",
        )
    coverage = await session.scalar(
        select(Coverage)
        .where(
            Coverage.organization_id == organization_id,
            Coverage.patient_id == ids["sarah_patient_id"],
            Coverage.status == "active",
        )
        .order_by(Coverage.updated_at.desc(), Coverage.id.desc())
    )
    eligibility = await session.scalar(
        select(EligibilityCheck)
        .where(
            EligibilityCheck.organization_id == organization_id,
            EligibilityCheck.patient_id == ids["sarah_patient_id"],
            EligibilityCheck.coverage_id == coverage.id,
        )
        .order_by(
            EligibilityCheck.responded_at.desc(),
            EligibilityCheck.created_at.desc(),
            EligibilityCheck.id.desc(),
        )
    )
    estimate = await session.scalar(
        select(Estimate)
        .where(
            Estimate.organization_id == organization_id,
            Estimate.patient_id == ids["sarah_patient_id"],
            Estimate.eligibility_check_id == eligibility.id,
        )
        .order_by(Estimate.created_at.desc(), Estimate.id.desc())
    )
    intake_response = await session.scalar(
        select(QuestionnaireResponse)
        .where(
            QuestionnaireResponse.organization_id == organization_id,
            QuestionnaireResponse.patient_id == ids["sarah_patient_id"],
            QuestionnaireResponse.status == "completed",
        )
        .order_by(QuestionnaireResponse.completed_at.desc())
    )
    if intake_response is None:
        raise HTTPException(status_code=503, detail="Canonical intake response is unavailable")
    durable_intake = intake_response.response_json
    intake_triage_task = await session.scalar(
        select(Task)
        .where(
            Task.organization_id == organization_id,
            Task.patient_id == ids["sarah_patient_id"],
            Task.task_type == "urgent_intake_triage",
        )
        .order_by(Task.created_at.desc())
    )
    intake_triage_notification = await session.scalar(
        select(Notification)
        .where(
            Notification.organization_id == organization_id,
            Notification.entity_type == "questionnaire_response",
            Notification.entity_id == intake_response.id,
            Notification.kind == "urgent_intake_triage",
        )
        .order_by(Notification.created_at.desc())
    )
    intake_draft = {
        "reason": durable_intake.get("reasonForVisit", ""),
        "firstNoticed": durable_intake.get("firstNoticed", ""),
        "change": durable_intake.get("changes", []),
        "symptoms": durable_intake.get("symptoms", []),
        "medications": durable_intake.get("medications")
        or [
            " ".join(filter(None, [item["name"], item["dose"], item["frequency"]]))
            for item in sarah["medications"]
        ],
        "allergies": durable_intake.get("allergies")
        or [f"{item['substance']} — {item['reaction']}" for item in sarah["allergies"]],
        "personalSkinCancerHistory": durable_intake.get("personalSkinCancerHistory", ""),
        "familySkinCancerHistory": durable_intake.get("familySkinCancerHistory", ""),
        "pharmacy": durable_intake.get("pharmacy") or (pharmacy.value if pharmacy else ""),
        "urgentSigns": durable_intake.get("urgentSigns", []),
    }

    note = encounter_bundle["note"]
    current_note_version = note["versions"][-1]
    note_author = await session.scalar(
        select(User).where(
            User.id == note["author_user_id"],
            User.organization_id == organization_id,
        )
    )
    biopsy_consent = await session.scalar(
        select(Consent)
        .where(
            Consent.organization_id == organization_id,
            Consent.patient_id == ids["sarah_patient_id"],
            Consent.encounter_id == ids["sarah_encounter_id"],
            Consent.consent_type == "shave_biopsy",
        )
        .order_by(Consent.accepted_at.desc())
    )
    note_ai_provenance = await ai_provenance(session, organization_id, note["ai_run_id"])
    completion_workflow = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.organization_id == organization_id,
            WorkflowRun.workflow_type == "biopsy_completion",
            WorkflowRun.entity_id == ids["sarah_encounter_id"],
            WorkflowRun.status == "completed",
        )
    )
    completion_artifacts = completion_workflow.output_json if completion_workflow else {}
    completion_receipt = (
        {
            "status": "completed",
            "signedAt": note["signed_at"],
            "noteId": completion_artifacts.get("noteId"),
            "consentId": completion_artifacts.get("consentId"),
            "procedureId": completion_artifacts.get("procedureId"),
            "specimenId": completion_artifacts.get("specimenId"),
            "orderId": completion_artifacts.get("orderId"),
            "claimId": completion_artifacts.get("claimId"),
            "messageId": completion_artifacts.get("messageId"),
            "closureTaskId": completion_artifacts.get("taskId"),
        }
        if completion_workflow
        else None
    )
    previsit_output = await session.scalar(
        select(AIOutput)
        .join(
            AIRun,
            (AIRun.id == AIOutput.ai_run_id) & (AIRun.organization_id == organization_id),
        )
        .where(
            AIOutput.organization_id == organization_id,
            AIRun.patient_id == ids["sarah_patient_id"],
            AIRun.capability == "chart_summary",
        )
        .order_by(AIOutput.created_at.desc())
    )
    previsit_content = previsit_output.content_json if previsit_output else {}
    proposal_map = {
        "sign_note": (
            "proposal_note",
            "Documentation",
            "Sign structured encounter note",
            "History, exam, assessment, and plan with AI provenance attached.",
            True,
        ),
        "confirm_biopsy_consent": (
            "proposal_consent",
            "Consent",
            "Confirm biopsy consent",
            "Signed shave-biopsy consent is linked to this encounter.",
            True,
        ),
        "create_shave_biopsy": (
            "proposal_biopsy",
            "Procedure",
            "Create shave biopsy",
            "Left posterior shoulder; anesthetic, technique, and hemostasis documented.",
            True,
        ),
        "create_pathology_order": (
            "proposal_path",
            "Pathology",
            "Create specimen and pathology order",
            "Rule out dysplastic nevus versus melanoma; routine priority.",
            True,
        ),
        "create_specimen": (
            "proposal_specimen",
            "Pathology",
            "Create linked specimen",
            "Shave specimen inherits patient, lesion, procedure, order, and body-site links.",
            True,
        ),
        "apply_coding": (
            "proposal_codes",
            "Coding",
            "Add CPT 11102 + ICD-10 D48.5",
            "Coding support remains a clinician-approved proposal.",
            True,
        ),
        "send_aftercare": (
            "proposal_aftercare",
            "Communication",
            "Send approved aftercare",
            "Wound care, warning signs, and expected pathology timing.",
            True,
        ),
        "create_pathology_task": (
            "proposal_task",
            "Safety",
            "Create pathology closure task",
            "Escalates if result review or patient notification is missing.",
            True,
        ),
    }
    proposals = []
    for action in encounter_bundle["proposed_actions"]:
        alias, category, title, detail, required = proposal_map[action["action_type"]]
        proposals.append(
            {
                "id": action["id"],
                "uiAlias": alias,
                "category": category,
                "title": title,
                "detail": detail,
                "required": required,
                "status": action["status"],
            }
        )
    missing_actions = set(proposal_map).difference(
        action["action_type"] for action in encounter_bundle["proposed_actions"]
    )
    if missing_actions:
        raise HTTPException(
            status_code=503,
            detail=f"Canonical workflow is missing durable actions: {', '.join(sorted(missing_actions))}",
        )
    transcript = []
    for line in encounter_bundle["ambient_transcript"].splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            transcript.append({"time": parts[0], "speaker": parts[1], "text": parts[2]})
    if not transcript:
        transcript = [
            {
                "time": scenario.current_time.astimezone(local_zone).strftime("%H:%M"),
                "speaker": "Ambient transcript",
                "text": encounter_bundle["ambient_transcript"],
            }
        ]

    hero_result = await session.scalar(
        select(DiagnosticResult)
        .join(
            Procedure,
            (Procedure.id == DiagnosticResult.procedure_id)
            & (Procedure.organization_id == organization_id),
        )
        .where(
            DiagnosticResult.organization_id == organization_id,
            Procedure.encounter_id == ids["sarah_encounter_id"],
        )
    )
    procedure = await session.scalar(
        select(Procedure).where(
            Procedure.organization_id == organization_id,
            Procedure.encounter_id == ids["sarah_encounter_id"],
        )
    )
    order = await session.scalar(
        select(Order).where(
            Order.organization_id == organization_id,
            Order.encounter_id == ids["sarah_encounter_id"],
        )
    )
    specimen = (
        await session.scalar(
            select(Specimen).where(
                Specimen.organization_id == organization_id,
                Specimen.order_id == order.id,
            )
        )
        if order
        else None
    )
    pathology_status = (
        "notified"
        if hero_result and hero_result.patient_notified_at
        else "reviewed"
        if hero_result and hero_result.reviewed_at
        else "received"
        if hero_result
        else "pending"
    )
    pathology_provenance_record = (
        await session.scalar(
            select(ProvenanceRecord)
            .where(
                ProvenanceRecord.organization_id == organization_id,
                ProvenanceRecord.entity_type == "diagnostic_result",
                ProvenanceRecord.entity_id == hero_result.id,
                ProvenanceRecord.ai_run_id.is_not(None),
            )
            .order_by(ProvenanceRecord.recorded_at.desc())
        )
        if hero_result
        else None
    )
    pathology_ai_provenance = await ai_provenance(
        session,
        organization_id,
        pathology_provenance_record.ai_run_id if pathology_provenance_record else None,
    )
    pathology_message_draft = (
        await session.scalar(
            select(MessageDraft).where(
                MessageDraft.organization_id == organization_id,
                MessageDraft.ai_run_id == pathology_provenance_record.ai_run_id,
            )
        )
        if pathology_provenance_record
        else None
    )
    pathology_followup = (
        await session.scalar(
            select(Task).where(
                Task.id == uuid.uuid5(hero_result.id, "six-month-lesion-followup"),
                Task.organization_id == organization_id,
                Task.patient_id == hero_result.patient_id,
            )
        )
        if hero_result
        else None
    )
    hero_clinician = (
        (
            await session.execute(
                select(Provider, User)
                .join(
                    User,
                    (User.id == Provider.user_id) & (User.organization_id == organization_id),
                )
                .where(
                    Provider.id == hero_result.clinician_id,
                    Provider.organization_id == organization_id,
                )
            )
        ).first()
        if hero_result
        else None
    )
    pathology_links = [
        {"kind": "patient", "id": ids["sarah_patient_id"], "label": "Sarah Mitchell"},
        {"kind": "lesion", "id": ids["sarah_lesion_id"], "label": "Left posterior shoulder"},
        {
            "kind": "image",
            "id": overview["id"] if overview else ids["sarah_lesion_id"],
            "label": "Clinical overview",
        },
    ]
    for kind, entity, label in [
        ("procedure", procedure, "Shave biopsy"),
        ("specimen", specimen, "Shave specimen"),
        ("order", order, "Surgical pathology order"),
        ("result", hero_result, "Final pathology"),
    ]:
        if entity:
            pathology_links.append({"kind": kind, "id": entity.id, "label": label})
    if hero_clinician:
        pathology_links.append(
            {
                "kind": "clinician",
                "id": hero_clinician[0].id,
                "label": hero_clinician[1].display_name,
            }
        )

    conversation_rows = (
        await session.execute(
            select(Conversation, Patient)
            .join(
                Patient,
                (Patient.id == Conversation.patient_id)
                & (Patient.organization_id == organization_id),
            )
            .where(Conversation.organization_id == organization_id)
            .order_by(Conversation.last_message_at.desc())
        )
    ).all()
    conversations = []
    for conversation, conversation_patient in conversation_rows:
        messages = (
            await session.scalars(
                select(Message)
                .where(
                    Message.organization_id == organization_id,
                    Message.conversation_id == conversation.id,
                )
                .order_by(Message.sent_at)
            )
        ).all()
        drafts = []
        if "patient" not in roles:
            drafts = (
                await session.scalars(
                    select(MessageDraft).where(
                        MessageDraft.organization_id == organization_id,
                        MessageDraft.conversation_id == conversation.id,
                        MessageDraft.status == "proposed",
                    )
                )
            ).all()
        message_items = []
        for message in messages:
            sender = await session.scalar(
                select(User.display_name).where(
                    User.id == message.sender_user_id,
                    User.organization_id == organization_id,
                )
            )
            message_items.append(
                {
                    "id": message.id,
                    "sender": sender or message.sender_kind.title(),
                    "sentAt": message.sent_at,
                    "body": message.body,
                }
            )
        message_items.extend(
            {
                "id": draft.id,
                "sender": "AI draft · requires staff approval",
                "sentAt": draft.created_at,
                "body": draft.body,
                "aiDraft": True,
                "status": draft.status,
            }
            for draft in drafts
        )
        needs_staff_review = bool(
            await session.scalar(
                select(Task.id).where(
                    Task.organization_id == organization_id,
                    Task.patient_id == conversation.patient_id,
                    Task.task_type == "message_review",
                    Task.status.in_(["open", "in_progress"]),
                )
            )
        )
        conversations.append(
            {
                "id": conversation.id,
                "subject": conversation.subject,
                "patientId": conversation_patient.id,
                "patient": f"{conversation_patient.first_name} {conversation_patient.last_name}",
                "unread": sum(
                    message.read_at is None
                    and (
                        message.sender_kind != "patient"
                        if "patient" in roles
                        else message.sender_kind == "patient"
                    )
                    for message in messages
                ),
                "risk": "staff_review" if needs_staff_review else "routine",
                "messages": message_items,
            }
        )

    include_claims = bool(session_payload.get("presenter") or "biller" in roles)
    hero_claim = (
        await session.scalar(
            select(Claim).where(
                Claim.organization_id == organization_id,
                Claim.encounter_id == ids["sarah_encounter_id"],
            )
        )
        if include_claims
        else None
    )
    denied_claim_ids = (
        list(
            await session.scalars(
                select(Denial.claim_id).where(Denial.organization_id == organization_id)
            )
        )
        if include_claims
        else []
    )
    claim_scope = or_(Claim.id == ids["sarah_claim_id"], Claim.id.in_(denied_claim_ids))
    if "patient" in roles:
        claim_scope = Claim.patient_id == ids["sarah_patient_id"]
    actionable_open_denial = (
        select(Denial.id)
        .where(
            Denial.organization_id == organization_id,
            Denial.claim_id == Claim.id,
            Denial.status == "open",
        )
        .exists()
    )
    claim_rows = (
        (
            await session.execute(
                select(Claim, Patient, Coverage)
                .join(
                    Patient,
                    (Patient.id == Claim.patient_id) & (Patient.organization_id == organization_id),
                )
                .join(
                    Coverage,
                    (Coverage.id == Claim.coverage_id)
                    & (Coverage.organization_id == organization_id),
                )
                .where(
                    Claim.organization_id == organization_id,
                    claim_scope,
                )
                .order_by(
                    actionable_open_denial.desc(),
                    (Claim.id == ids["sarah_claim_id"]).desc(),
                    (Claim.status != "denied").desc(),
                    Claim.claim_number.desc(),
                    Claim.id,
                )
                .limit(2)
            )
        ).all()
        if include_claims
        else []
    )
    claims = []
    for claim, patient, claim_coverage in claim_rows:
        lines = (
            await session.scalars(
                select(ClaimLine)
                .where(
                    ClaimLine.organization_id == organization_id,
                    ClaimLine.claim_id == claim.id,
                )
                .order_by(ClaimLine.line_number)
            )
        ).all()
        events = (
            await session.scalars(
                select(ClaimEvent)
                .where(
                    ClaimEvent.organization_id == organization_id,
                    ClaimEvent.claim_id == claim.id,
                )
                .order_by(ClaimEvent.occurred_at)
            )
        ).all()
        denial = await session.scalar(
            select(Denial)
            .where(
                Denial.organization_id == organization_id,
                Denial.claim_id == claim.id,
            )
            .order_by(
                (Denial.status == "open").desc(),
                Denial.denied_at.desc(),
                Denial.id,
            )
        )
        claim_payments = (
            await session.scalars(
                select(Payment)
                .where(
                    Payment.organization_id == organization_id,
                    Payment.claim_id == claim.id,
                )
                .order_by(Payment.received_at)
            )
        ).all()
        patient_balance = await session.scalar(
            select(PatientBalance).where(
                PatientBalance.organization_id == organization_id,
                PatientBalance.patient_id == claim.patient_id,
            )
        )
        claim_eligibility = await session.scalar(
            select(EligibilityCheck)
            .where(
                EligibilityCheck.organization_id == organization_id,
                EligibilityCheck.patient_id == claim.patient_id,
                EligibilityCheck.coverage_id == claim.coverage_id,
            )
            .order_by(
                EligibilityCheck.responded_at.desc(),
                EligibilityCheck.created_at.desc(),
                EligibilityCheck.id.desc(),
            )
        )
        claim_estimate = (
            await session.scalar(
                select(Estimate)
                .where(
                    Estimate.organization_id == organization_id,
                    Estimate.patient_id == claim.patient_id,
                    Estimate.eligibility_check_id == claim_eligibility.id,
                )
                .order_by(Estimate.created_at.desc())
            )
            if claim_eligibility
            else None
        )
        claim_item = {
            "id": claim.id,
            "claimNumber": claim.claim_number,
            "patient": f"{patient.first_name} {patient.last_name}",
            "payer": claim_coverage.payer_name,
            "amount": float(claim.total_charge),
            "allowed": float(claim.allowed_amount),
            "paid": float(claim.paid_amount),
            "remainingBalance": float(max(Decimal("0"), claim.allowed_amount - claim.paid_amount)),
            "patientResponsibility": float(claim.patient_responsibility),
            "status": claim.status,
            "codes": [line.procedure_code for line in lines]
            + sorted({code for line in lines for code in line.diagnosis_codes}),
            "lines": [
                {
                    "id": line.id,
                    "lineNumber": line.line_number,
                    "procedureCode": line.procedure_code,
                    "diagnosisCodes": line.diagnosis_codes,
                    "units": line.units,
                    "charge": float(line.charge_amount),
                    "allowed": float(line.allowed_amount),
                    "paid": float(line.paid_amount),
                }
                for line in lines
            ],
            "payments": [
                {
                    "id": payment.id,
                    "source": payment.source,
                    "amount": float(payment.amount),
                    "method": payment.payment_method,
                    "reference": payment.reference,
                    "status": payment.status,
                    "receivedAt": payment.received_at,
                }
                for payment in claim_payments
            ],
            "balance": (
                {
                    "scope": "patient_aggregate",
                    "currentBalance": float(patient_balance.current_balance),
                    "status": patient_balance.status,
                    "lastStatementAt": patient_balance.last_statement_at,
                    "lastPaymentAt": patient_balance.last_payment_at,
                }
                if patient_balance
                else None
            ),
            "claimBalance": {
                "scope": "claim",
                "currentBalance": float(
                    max(
                        Decimal("0.00"),
                        claim.patient_responsibility
                        - sum(
                            (
                                payment.amount
                                for payment in claim_payments
                                if payment.source == "patient" and payment.status == "settled"
                            ),
                            start=Decimal("0.00"),
                        ),
                    )
                ),
                "status": (
                    "due"
                    if claim.patient_responsibility
                    > sum(
                        (
                            payment.amount
                            for payment in claim_payments
                            if payment.source == "patient" and payment.status == "settled"
                        ),
                        start=Decimal("0.00"),
                    )
                    else "current"
                ),
            },
            "financialContext": {
                "eligibility": (
                    {
                        "id": claim_eligibility.id,
                        "status": claim_eligibility.status,
                        "checkedAt": claim_eligibility.responded_at,
                        "network": claim_eligibility.response_json.get("networkStatus"),
                        "copay": float(claim_eligibility.copay),
                        "deductibleRemaining": float(claim_eligibility.deductible_remaining),
                    }
                    if claim_eligibility
                    else None
                ),
                "estimate": (
                    {
                        "id": claim_estimate.id,
                        "status": claim_estimate.status,
                        "totalCharge": float(claim_estimate.total_charge),
                        "expectedPlanPayment": float(claim_estimate.expected_plan_payment),
                        "patientResponsibility": float(claim_estimate.patient_responsibility),
                    }
                    if claim_estimate
                    else None
                ),
            },
            "provenance": {
                "source": "durable_claim_lines_and_clearinghouse_events",
                "latestEventId": events[-1].id if events else None,
                "aiProvenance": None,
            },
            "events": [
                {"label": event.to_status.title(), "at": event.occurred_at, "complete": True}
                for event in events
            ],
        }
        if denial:
            appeal = await session.scalar(
                select(Appeal).where(
                    Appeal.organization_id == organization_id,
                    Appeal.denial_id == denial.id,
                )
            )
            task = await session.scalar(
                select(Task).where(
                    Task.organization_id == organization_id,
                    Task.patient_id == patient.id,
                    Task.claim_id == claim.id,
                    Task.denial_id == denial.id,
                    Task.task_type == "denial_followup",
                )
            )
            claim_item["denial"] = {
                "id": denial.id,
                "status": denial.status,
                "code": denial.reason_code,
                "reason": denial.reason,
                "recommendation": "Verify the signed documentation, correct the claim, and resubmit through the clearinghouse.",
                "recommendationSource": "rules_based",
                "aiProvenance": None,
                "recoverable": float(denial.denied_amount),
                "appealDraft": appeal.appeal_text if appeal else "",
                "assignedTaskId": task.id if task else "",
                "recovery": (
                    {
                        "appealId": appeal.id,
                        "status": appeal.status,
                        "outcome": appeal.outcome,
                        "recoveredAmount": float(appeal.recovered_amount),
                        "submittedAt": appeal.submitted_at,
                    }
                    if appeal
                    else None
                ),
            }
        claims.append(claim_item)

    local_schedule = []
    for appointment in dashboard["schedule"]:
        if (
            session_payload.get("persona") == "patient"
            and appointment["patient_id"] != ids["sarah_patient_id"]
        ):
            continue
        local_time = appointment["starts_at"].astimezone(local_zone)
        local_schedule.append(
            {
                "id": appointment["id"],
                "startsAt": appointment["starts_at"],
                "time": local_time.strftime("%-I:%M %p"),
                "patient": appointment["patient_name"],
                "visit": appointment["visit_type"],
                "provider": appointment["provider_name"],
                "readiness": 100 if appointment["readiness_status"] == "ready" else 0,
                "readinessStatus": appointment["readiness_status"],
                "flags": ["AI summary", "Family history"]
                if appointment["patient_id"] == ids["sarah_patient_id"]
                else [],
                "status": appointment["status"].replace("_", " ").title(),
            }
        )
    counts = dashboard["counts"]
    queues = [
        {
            "id": "path",
            "label": "Pathology to review",
            "count": counts["unreviewed_pathology"],
            "detail": "Final results awaiting clinician action",
            "tone": "warning",
            "href": "/pathology",
        },
        {
            "id": "notes",
            "label": "Unsigned notes",
            "count": counts["unsigned_notes"],
            "detail": "Drafts requiring provider signature",
            "tone": "info",
            "href": f"/encounters/{ids['sarah_encounter_id']}",
        },
        {
            "id": "intake",
            "label": "Missing intake",
            "count": counts["missing_intake"],
            "detail": "Across today's scheduled visits",
            "tone": "neutral",
            "href": "/command-center",
        },
        {
            "id": "claims",
            "label": "Claims needing work",
            "count": counts["claims_requiring_work"],
            "detail": "Draft or denied claims",
            "tone": "danger",
            "href": "/rcm",
        },
        {
            "id": "messages",
            "label": "Patient messages",
            "count": sum(item["unread"] for item in conversations),
            "detail": "Secure threads awaiting response",
            "tone": "ai",
            "href": "/messages",
        },
        {
            "id": "refills",
            "label": "Refill requests",
            "count": counts["refill_requests"],
            "detail": "Protocol-routed requests",
            "tone": "success",
            "href": "/messages",
        },
    ]

    metric_specs = [
        (
            "conversion",
            "Appointment conversion",
            "appointment_conversion_percent",
            "%",
            "higher",
            "appointments + audit_events",
        ),
        ("noshow", "No-show rate", "no_show_rate_percent", "%", "lower", "appointments"),
        (
            "response",
            "Patient response time",
            "median_patient_response_hours",
            "h",
            "lower",
            "messages + conversations",
        ),
        (
            "sign",
            "Time to signed note",
            "median_time_to_signed_note_minutes",
            "m",
            "lower",
            "encounters + encounter_notes",
        ),
        ("path_open", "Open pathology", "open_pathology", "", "lower", "diagnostic_results"),
        (
            "path_closure",
            "Pathology closure time",
            "median_pathology_closure_hours",
            "h",
            "lower",
            "diagnostic_results + messages",
        ),
        (
            "accept",
            "First-pass claim acceptance",
            "claim_acceptance_percent",
            "%",
            "higher",
            "claims + claim_events",
        ),
        ("denial", "Denial rate", "denial_rate_percent", "%", "lower", "claims + denials"),
        ("ar", "Days in A/R", "average_days_in_ar", "", "lower", "claims + payments"),
        (
            "revenue",
            "Revenue per visit",
            "revenue_per_completed_visit",
            "$",
            "higher",
            "payments + claims + encounters",
        ),
        (
            "doc",
            "Documentation time",
            "median_documentation_minutes",
            "m",
            "lower",
            "encounters + encounter_notes",
        ),
        (
            "avoided",
            "Staff work avoided",
            "estimated_staff_minutes_avoided",
            "m",
            "higher",
            "ai_runs + appointment_reminders + automation_policies",
        ),
        ("satisfaction", "Patient message read rate", None, "%", "higher", "messages"),
    ]
    metrics = []
    supporting_counts = metric_values["supporting_counts"]
    metric_support = {
        "conversion": f"{supporting_counts['booked_initiations']} booked / {supporting_counts['qualified_initiations']} qualified",
        "noshow": f"{supporting_counts['no_show_eligible_visits']} completed or no-show visits",
        "response": (
            f"{supporting_counts['patient_messages_with_response']} responded / "
            f"{supporting_counts['patient_messages_eligible_for_response']} eligible patient messages"
        ),
        "sign": (
            f"{supporting_counts['signed_encounters']} signed / "
            f"{supporting_counts['completed_encounters_eligible_for_signing']} eligible encounters"
        ),
        "path_open": f"{supporting_counts['pathology']} pathology results",
        "path_closure": (
            f"{supporting_counts['notified_pathology_results']} notified / "
            f"{supporting_counts['final_pathology_results']} final results"
        ),
        "accept": (
            f"{supporting_counts['payer_outcome_claims']} claims with a first payer outcome; "
            f"{supporting_counts['pending_submitted_claims']} pending excluded"
        ),
        "denial": (
            f"{supporting_counts['first_pass_denied_claims']} denied / "
            f"{supporting_counts['payer_outcome_claims']} first payer outcomes"
        ),
        "ar": f"${float(supporting_counts['open_ar_balance']):,.2f} open balance",
        "revenue": f"{supporting_counts['allocated_payments']} allocated payments / {supporting_counts['completed_visits']} visits",
        "doc": f"{supporting_counts['completed_visits']} completed visits",
        "avoided": f"{supporting_counts['ai_runs']} AI runs under policy {metric_values['assumptions']['policy_version']}",
        "satisfaction": f"{metric_values['patient_satisfaction_indicators']['portal_engagement_count']} portal messages",
    }
    metric_assumptions = {
        "conversion": metric_values["definitions"]["appointment_conversion"],
        "noshow": metric_values["definitions"]["no_show_rate"],
        "accept": metric_values["definitions"]["first_pass_claim_acceptance"],
        "denial": metric_values["definitions"]["denial_rate"],
        "ar": metric_values["definitions"]["days_in_ar"],
        "revenue": metric_values["definitions"]["revenue_per_visit"],
        "avoided": metric_values["definitions"]["staff_work_avoided"],
    }
    targets = metric_values["assumptions"]["metric_targets"]
    for metric_id, label, key, suffix, direction, source in metric_specs:
        value = (
            metric_values["patient_satisfaction_indicators"]["message_read_rate_percent"]
            if key is None
            else metric_values[key]
        )
        display = (
            None
            if value is None
            else f"${value:,.0f}"
            if suffix == "$"
            else f"{value:g}{suffix}"
        )
        target_value = float(targets[metric_id])
        numeric_value = float(value) if value is not None else None
        if numeric_value is None:
            score = None
        elif direction == "higher":
            score = round(min(100, 100 * numeric_value / target_value)) if target_value else 100
        elif target_value == 0:
            score = 100 if numeric_value == 0 else max(0, round(100 - numeric_value * 20))
        else:
            score = (
                100 if numeric_value == 0 else round(min(100, 100 * target_value / numeric_value))
            )
        target_display = f"${target_value:,.0f}" if suffix == "$" else f"{target_value:g}{suffix}"
        direction_label = "at least" if direction == "higher" else "at most"
        metrics.append(
            {
                "id": metric_id,
                "label": label,
                "value": display,
                "change": (
                    "Insufficient matched records"
                    if value is None
                    else "Calculated from current records"
                ),
                "target": f"{direction_label} {target_display}",
                "score": score,
                "tone": (
                    "neutral"
                    if score is None
                    else "success"
                    if score >= 100
                    else "info"
                    if score >= 70
                    else "warning"
                    if score >= 50
                    else "danger"
                ),
                "supportingCount": metric_support[metric_id],
                "assumption": (
                    metric_assumptions.get(
                        metric_id,
                        "Direct calculation from the current tenant-scoped durable record set.",
                    )
                    + f" Target is {direction_label} {target_display} under policy "
                    f"{metric_values['assumptions']['policy_version']}."
                ),
                "source": source,
            }
        )

    chapter_map = {key: (index, label) for index, (key, label) in enumerate(DEMO_CHAPTERS, 1)}
    chapter, chapter_label = chapter_map.get(scenario.current_chapter, (1, DEMO_CHAPTERS[0][1]))
    note_status = "draft" if note["status"] in {"draft", "proposed"} else note["status"]
    appointment_address = (
        f"{location.address_line1}, {location.city}, {location.state} {location.postal_code}"
    )
    eligible_slots = []
    for slot in availability:
        local_start = slot["starts_at"].astimezone(local_zone)
        eligible_slots.append(
            {
                "id": slot["id"],
                "startsAt": slot["starts_at"],
                "dayLabel": local_start.strftime("%A"),
                "dateLabel": local_start.strftime("%B %-d"),
                "timeLabel": local_start.strftime("%-I:%M %p"),
                "provider": slot["provider_name"],
                "location": slot["location_name"],
                "providerId": slot["provider_id"],
                "locationId": slot["location_id"],
            }
        )
    payload = {
        "session": session_payload,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "location": f"{location.name} · {location.city}",
            "timezone": organization.timezone,
        },
        "scenario": {
            "id": scenario.id,
            "chapter": chapter,
            "chapterLabel": chapter_label,
            "currentTime": scenario.current_time,
            "modelMode": "deterministic_fallback" if scenario.fallback_indicator else "live",
        },
        "personas": personas,
        "intake": {
            "draft": intake_draft,
            "availableSlots": eligible_slots,
            "bookedAppointment": (
                {
                    "id": booked_row[0].id,
                    "slotId": availability_slot_id(
                        organization_id,
                        booked_row[1].id,
                        booked_row[3].id,
                        booked_row[0].starts_at,
                    ),
                    "providerId": booked_row[1].id,
                    "provider": booked_row[2].display_name,
                    "locationId": booked_row[3].id,
                    "location": booked_row[3].name,
                    "startsAt": booked_row[0].starts_at,
                    "status": booked_row[0].status,
                }
                if booked_row
                else None
            ),
            "eligibility": {
                "payer": coverage.payer_name,
                "plan": coverage.plan_name,
                "status": eligibility.status,
                "network": eligibility.response_json.get("networkStatus", "in_network"),
                "specialistCopay": float(eligibility.copay),
                "deductibleRemaining": float(eligibility.deductible_remaining),
                "estimatedResponsibility": float(estimate.patient_responsibility),
                "checkedAt": eligibility.responded_at,
                "memberId": coverage.member_id,
            },
            "triage": {
                "status": "staff_review" if intake_triage_task else "routine",
                "taskId": intake_triage_task.id if intake_triage_task else None,
                "notificationId": (
                    intake_triage_notification.id if intake_triage_notification else None
                ),
                "readinessStatus": (booked_row[0].readiness_status if booked_row else "unknown"),
            },
            "appointmentAddress": appointment_address,
            "preparation": [
                "Bring a photo ID and insurance card",
                "Wear clothing that makes the shoulder easy to examine",
                "Continue prescribed medication unless directed otherwise",
            ],
        },
        "commandCenter": {
            "scheduledVisits": counts["today_appointments"],
            "completedVisits": sum(item["status"] == "completed" for item in dashboard["schedule"]),
            "inProgressVisits": sum(
                item["status"] in {"checked_in", "in_progress"} for item in dashboard["schedule"]
            ),
            "readinessPercent": round(100 * counts["ready_patients"] / counts["today_appointments"])
            if counts["today_appointments"]
            else 0,
            "medianSignMinutes": metric_values["median_time_to_signed_note_minutes"],
            "signMinutesImprovement": 0,
            "pathologyClosurePercent": counts["pathology_closure_on_time_percent"],
            "pathologyDueToday": counts["pathology_due_today"],
            "eligibilityVerified": counts["eligibility_verified"],
            "summariesPrepared": counts["summaries_prepared"],
            "summaryMinutesSaved": counts["summary_minutes_saved"],
            "documentationSupportPercent": counts["documentation_support_percent"],
        },
        "patient": {
            "id": sarah["id"],
            "name": sarah["full_name"],
            "initials": "SM",
            "dob": sarah["date_of_birth"],
            "age": sarah["age"],
            "pronouns": sarah["pronouns"],
            "phone": sarah["phone"],
            "email": sarah["email"],
            "mrn": sarah["medical_record_number"],
            "pharmacy": f"{pharmacy.name} · {pharmacy.value}" if pharmacy else "Not recorded",
            "insurance": f"{coverage.payer_name} {coverage.plan_name} · {coverage.status.title()}",
            "allergies": [
                f"{item['substance']} — {item['reaction']}" for item in sarah["allergies"]
            ],
            "medications": [
                " ".join(filter(None, [item["name"], item["dose"], item["frequency"]]))
                for item in sarah["medications"]
            ],
            "problems": [item.display for item in problems],
            "readiness": (100 if booked_row and booked_row[0].readiness_status == "ready" else 0),
            "readinessStatus": booked_row[0].readiness_status if booked_row else "unknown",
            "lesions": sarah["lesions"],
            "recentEvents": sarah["recent_events"],
            "priorSignedNotes": sarah["prior_signed_notes"],
            "pathologyHistory": sarah["pathology_history"],
            "readinessDetail": sarah["readiness"],
            "contacts": sarah["contacts"],
            "lesion": {
                "id": active_lesion["id"],
                "status": active_lesion["status"],
                "label": "Changing pigmented lesion",
                "location": active_lesion["anatomical_location"].title(),
                "dimensions": f"{latest_observation['length_mm']:g} × {latest_observation['width_mm']:g} mm",
                "morphology": latest_observation["morphology"],
                "border": latest_observation["border"],
                "pigmentation": latest_observation["pigmentation"],
                "symptoms": [part.strip() for part in latest_observation["symptoms"].split(";")],
                "change": latest_observation["change_over_time"],
                "overviewImage": {
                    "id": overview_file.id,
                    "url": overview_file.public_demo_url,
                    "name": overview_file.filename,
                    "size": overview_file.byte_size,
                    "type": overview_file.content_type,
                    "sha256": overview_file.sha256,
                    "capturedAt": overview["captured_at"],
                },
                "dermoscopyImage": {
                    "id": dermoscopy_file.id,
                    "url": dermoscopy_file.public_demo_url,
                    "name": dermoscopy_file.filename,
                    "size": dermoscopy_file.byte_size,
                    "type": dermoscopy_file.content_type,
                    "sha256": dermoscopy_file.sha256,
                    "capturedAt": dermoscopy["captured_at"],
                },
                "firstObserved": active_lesion["first_noted_at"],
                "observations": [
                    {
                        "id": observation["id"],
                        "observedAt": observation["observed_at"],
                        "lengthMm": float(observation["length_mm"]),
                        "widthMm": float(observation["width_mm"]),
                        "morphology": observation["morphology"],
                        "border": observation["border"],
                        "pigmentation": observation["pigmentation"],
                        "changeOverTime": observation["change_over_time"],
                        "symptoms": [
                            part.strip()
                            for part in observation["symptoms"].split(";")
                            if part.strip()
                        ],
                        "assessment": observation["assessment"],
                        "comparison": observation.get("comparison"),
                        "source": observation["source"],
                    }
                    for observation in active_lesion_bundle["observations"]
                ],
                "latestObservation": {
                    "id": latest_observation["id"],
                    "site": latest_observation.get("anatomical_site")
                    or active_lesion["anatomical_location"],
                    "view": latest_observation.get("body_map_view")
                    or active_lesion["body_map_view"],
                    "lengthMm": float(latest_observation["length_mm"]),
                    "widthMm": float(latest_observation["width_mm"]),
                    "morphology": latest_observation["morphology"],
                    "border": latest_observation["border"],
                    "pigmentation": latest_observation["pigmentation"],
                    "changeOverTime": latest_observation["change_over_time"],
                    "symptoms": [
                        part.strip()
                        for part in latest_observation["symptoms"].split(";")
                        if part.strip()
                    ],
                    "assessment": latest_observation["assessment"],
                    "comparison": latest_observation.get("comparison"),
                    "source": latest_observation["source"],
                    "observedAt": latest_observation["observed_at"],
                },
            },
        },
        "schedule": local_schedule,
        "queues": queues,
        "encounter": {
            "id": encounter_bundle["id"],
            "noteId": note["id"],
            "status": note_status,
            "aiProvenance": note_ai_provenance,
            "completionReceipt": completion_receipt,
            "note": {
                "id": note["id"],
                "status": note_status,
                "currentVersion": {
                    "id": current_note_version["id"],
                    "number": current_note_version["version_number"],
                    "createdAt": current_note_version["created_at"],
                    "reason": current_note_version["reason"],
                    "contentHash": current_note_version["content_hash"],
                },
                "author": {
                    "id": note_author.id,
                    "name": note_author.display_name,
                },
                "signedAt": note["signed_at"],
                "consent": {
                    "id": biopsy_consent.id,
                    "status": "revoked" if biopsy_consent.revoked_at else "active",
                    "version": biopsy_consent.version,
                    "acceptedAt": biopsy_consent.accepted_at,
                },
            },
            "previsitSummary": previsit_content.get(
                "headline", "Changing lesion visit ready for review."
            ),
            "draftNote": {
                "chiefConcern": encounter_bundle["chief_complaint"],
                "historyOfPresentIllness": note["structured_content"].get(
                    "subjective", "Changing lesion for four months"
                ),
                "focusedExam": note["structured_content"].get(
                    "objective", "7 × 5 mm asymmetric pigmented papule"
                ),
                "assessmentPlan": note["structured_content"].get(
                    "assessmentPlan",
                    "Favor dysplastic nevus; rule out melanoma. Recommend shave biopsy today after informed consent.",
                ),
            },
            "transcript": transcript,
            "timeline": [
                {
                    "date": observation["observed_at"],
                    "title": (
                        "Patient baseline photograph"
                        if observation["source"] == "patient"
                        else "Clinician lesion examination"
                        if observation["source"] == "clinician"
                        else "Structured lesion observation"
                    ),
                    "detail": observation["change_over_time"],
                    "tone": "info" if observation["source"] == "patient" else "ai",
                }
                for observation in active_lesion_bundle["observations"]
            ],
            "proposals": proposals,
        },
        "pathology": {
            "id": hero_result.id if hero_result else None,
            "accession": specimen.accession_number if specimen else "Pending review completion",
            "status": pathology_status,
            "diagnosis": hero_result.diagnosis
            if hero_result
            else "Pending specimen collection and pathology",
            "summary": hero_result.summary
            if hero_result
            else "Review and complete the encounter to create the specimen and order.",
            "receivedAt": hero_result.resulted_at
            if hero_result
            else scenario.current_time + timedelta(days=3),
            "reviewedAt": hero_result.reviewed_at if hero_result else None,
            "notifiedAt": hero_result.patient_notified_at if hero_result else None,
            "closureDueAt": (
                hero_result.resulted_at
                if hero_result
                else scenario.current_time + timedelta(days=3)
            )
            + timedelta(hours=24),
            "priority": "routine",
            "aiProvenance": pathology_ai_provenance,
            "patientMessageDraft": (
                {
                    "id": pathology_message_draft.id,
                    "body": pathology_message_draft.body,
                    "status": pathology_message_draft.status,
                    "createdAt": pathology_message_draft.created_at,
                    "aiProvenance": pathology_ai_provenance,
                }
                if pathology_message_draft
                else None
            ),
            "followup": (
                {
                    "id": pathology_followup.id,
                    "status": pathology_followup.status,
                    "title": pathology_followup.title,
                    "dueAt": pathology_followup.due_at,
                    "completedAt": pathology_followup.completed_at,
                }
                if pathology_followup
                else None
            ),
            "links": pathology_links,
        },
        "conversations": conversations,
        "claims": claims,
        "financialContext": {
            "source": "durable_coverage_eligibility_and_estimate_records",
            "coverage": {
                "id": coverage.id,
                "payer": coverage.payer_name,
                "plan": coverage.plan_name,
                "memberId": coverage.member_id,
                "status": coverage.status,
            },
            "eligibility": {
                "id": eligibility.id,
                "status": eligibility.status,
                "network": eligibility.response_json.get("networkStatus"),
                "checkedAt": eligibility.responded_at,
                "copay": float(eligibility.copay),
                "deductibleRemaining": float(eligibility.deductible_remaining),
            },
            "estimate": {
                "id": estimate.id,
                "status": estimate.status,
                "totalCharge": float(estimate.total_charge),
                "expectedPlanPayment": float(estimate.expected_plan_payment),
                "patientResponsibility": float(estimate.patient_responsibility),
            },
        },
        "metrics": metrics,
        "health": [
            {
                "id": "api",
                "service": (
                    "Modal domain API"
                    if runtime.execution_platform == "modal"
                    else "FastAPI domain API · local runtime"
                ),
                "status": "healthy",
                "latency": "Request served",
            },
            {
                "id": "db",
                "service": (
                    "SQLite local source of truth"
                    if runtime.is_sqlite
                    else "Neon Postgres source of truth"
                ),
                "status": "healthy",
                "latency": "Connected",
            },
            {
                "id": "ai",
                "service": (
                    "OpenAI GPT-5.6 Luna"
                    if runtime.openai_api_key
                    else "Local deterministic inference fixtures"
                ),
                "status": "degraded" if scenario.fallback_indicator else "healthy",
                "latency": (
                    "Low reasoning configured"
                    if runtime.openai_api_key
                    else "Local fallback active"
                ),
            },
            {
                "id": "jobs",
                "service": "Durable workflow store",
                "status": "healthy",
                "latency": "Database-backed",
            },
        ],
        "triggerIds": {
            "patientId": ids["sarah_patient_id"],
            "encounterId": ids["sarah_encounter_id"],
            "lesionId": ids["sarah_lesion_id"],
            "claimId": hero_claim.id if hero_claim else None,
            "pathologyResultId": hero_result.id if hero_result else None,
        },
    }
    if session_payload.get("presenter"):
        return payload

    persona = session_payload.get("persona")
    payload["personas"] = [item for item in personas if item["id"] == persona]
    payload["health"] = []
    payload["triggerIds"] = None
    if roles & {"provider", "clinical_staff"}:
        payload["queues"] = [
            item
            for item in queues
            if item["id"] in {"path", "notes", "intake", "messages", "refills"}
        ]
        payload["claims"] = []
        payload["metrics"] = [
            item
            for item in metrics
            if item["id"] in {"response", "sign", "path_open", "path_closure", "doc"}
        ]
    elif "biller" in roles:
        payload["intake"] = None
        payload["commandCenter"] = None
        payload["patient"] = None
        payload["schedule"] = []
        payload["queues"] = [item for item in queues if item["id"] == "claims"]
        payload["encounter"] = None
        payload["pathology"] = None
        payload["conversations"] = []
        payload["metrics"] = [
            item for item in metrics if item["id"] in {"accept", "denial", "ar", "revenue"}
        ]
    elif "mso_owner" in roles:
        payload["intake"] = None
        payload["patient"] = None
        payload["schedule"] = []
        payload["encounter"] = None
        payload["pathology"] = None
        payload["conversations"] = []
        payload["claims"] = []
        payload["financialContext"] = None
    elif "patient" in roles:
        if session_payload.get("patient_id") != ids["sarah_patient_id"]:
            raise HTTPException(status_code=403, detail="Patient demo scope is unavailable")
        payload["commandCenter"] = None
        payload["queues"] = []
        payload["encounter"] = None
        payload["pathology"] = None
        payload["claims"] = []
        payload["metrics"] = []
        payload["conversations"] = [
            item
            for item in conversations
            if str(item["patientId"]) == str(session_payload.get("patient_id"))
        ]
    else:
        raise HTTPException(status_code=403, detail="No authorized demo workspace role")
    return payload
