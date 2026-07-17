from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import CAPABILITIES, run_ai
from .clock import domain_now
from .config import Settings, get_settings
from .database import SessionLocal, create_schema, get_session
from .models import (
    Allergy,
    Appeal,
    Appointment,
    AppointmentReminder,
    Approval,
    AuditEvent,
    Claim,
    ClaimEvent,
    ClaimLine,
    ClinicalImage,
    Consent,
    Conversation,
    Coverage,
    Denial,
    DiagnosticResult,
    EligibilityCheck,
    Encounter,
    EncounterNote,
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
    PatientContact,
    Problem,
    Procedure,
    ProposedAction,
    ProvenanceRecord,
    Provider,
    Questionnaire,
    QuestionnaireResponse,
    Role,
    Specimen,
    Task,
    User,
    WorkflowRun,
    utcnow,
)
from .providers import (
    clearinghouse_provider,
    eligibility_input_fingerprint,
    eligibility_provider,
    messaging_provider,
)
from .schemas import (
    AdvanceTimeRequest,
    AIRequest,
    AmbientRequest,
    AmendmentRequest,
    AppealRequest,
    AppointmentBookingRequest,
    ApproveDraftRequest,
    ClaimResubmitRequest,
    CompositeIntakeRequest,
    DemoSessionRequest,
    DraftMessageRequest,
    EncounterNoteDraftRequest,
    IntakeRequest,
    LesionObservationRequest,
    LoginRequest,
    MessageRequest,
    NoteUpdateRequest,
    PathologyReviewRequest,
    PatientInitiationRequest,
    ReviewCompleteRequest,
    SwitchPersonaRequest,
    TriggerRequest,
    to_camel,
)
from .security import (
    DemoIdentityProvider,
    Principal,
    enforce_patient_scope,
    get_principal,
    principal_from_persona,
    require_roles,
)
from .seed import DEMO_ORG_SLUG, canonical_ids, reset_demo_database, seed_database
from .services import (
    advance_demo_time,
    availability_slot_id,
    calculate_mso_metrics,
    command_center,
    complete_encounter_review,
    demo_bootstrap,
    get_availability,
    get_demo_scenario,
    get_encounter_bundle,
    get_patient_bundle,
    rcm_workspace,
    row_dict,
    set_demo_chapter,
    trigger_sarah_pathology,
)

_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$"
)


def _rfc3339(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.isoformat().replace("+00:00", "Z")


def _camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            to_camel(str(key)) if isinstance(key, str) else key: _camelize(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_camelize(item) for item in value]
    if isinstance(value, datetime):
        return _rfc3339(value)
    if isinstance(value, str) and _RFC3339_DATETIME.fullmatch(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _rfc3339(parsed)
    return value


class CamelJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(_camelize(content))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.auto_create_schema:
        await create_schema()
    if settings.auto_seed:
        async with SessionLocal() as session:
            await seed_database(session)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    default_response_class=CamelJSONResponse,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID", "X-Demo-Persona"],
)


@app.middleware("http")
async def prevent_sensitive_response_caching(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Cookie, Authorization"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-ID"] = request_id
    return response


Session = Annotated[AsyncSession, Depends(get_session)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
ProviderPrincipal = Annotated[Principal, Depends(require_roles("provider"))]
ClinicalPrincipal = Annotated[Principal, Depends(require_roles("provider", "clinical_staff"))]
PatientCarePrincipal = Annotated[
    Principal, Depends(require_roles("patient", "provider", "clinical_staff"))
]
BillerPrincipal = Annotated[Principal, Depends(require_roles("biller"))]
StaffPrincipal = Annotated[
    Principal,
    Depends(require_roles("provider", "clinical_staff", "biller", "mso_owner")),
]
OperationsPrincipal = Annotated[
    Principal, Depends(require_roles("provider", "clinical_staff", "mso_owner"))
]


def principal_payload(principal: Principal) -> dict[str, Any]:
    persona = principal.persona_key
    return {
        "authenticated": True,
        "user_id": principal.user_id,
        "organization_id": principal.organization_id,
        "display_name": principal.display_name,
        "persona": persona,
        "roles": sorted(principal.roles),
        "presenter": principal.is_presenter,
        "is_presenter": principal.is_presenter,
        "presenter_actor_id": principal.presenter_actor_id,
        "patient_id": principal.patient_id,
    }


async def presenter_principal(
    principal: CurrentPrincipal,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    if not runtime.demo_mode or not principal.is_presenter:
        raise HTTPException(status_code=403, detail="Protected presenter session required")
    return principal


PresenterPrincipal = Annotated[Principal, Depends(presenter_principal)]


def set_session_cookie(
    response: Response,
    token: str,
    runtime: Settings,
) -> None:
    response.set_cookie(
        runtime.session_cookie_name,
        token,
        max_age=runtime.session_ttl_seconds,
        httponly=True,
        secure=runtime.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, runtime: Settings) -> None:
    """Expire the session with the same attributes used when it was issued.

    `__Host-` cookies are ignored by browsers unless every Set-Cookie operation,
    including deletion, carries Secure and Path=/ with no Domain attribute.
    """

    response.delete_cookie(
        runtime.session_cookie_name,
        httponly=True,
        secure=runtime.secure_cookies,
        samesite="lax",
        path="/",
    )


@app.get("/healthz")
@app.get("/api/health")
async def health(session: Session) -> dict[str, Any]:
    try:
        await session.execute(text("SELECT 1"))
        database = "healthy"
    except Exception:
        database = "unavailable"
    return {
        "status": "healthy" if database == "healthy" else "degraded",
        "service": "ambrosia-domain-api",
        "database": database,
        "ai": "openai_configured" if get_settings().openai_api_key else "fallback_only",
        "environment": get_settings().environment,
        "demo_mode": get_settings().demo_mode,
        "time": utcnow(),
    }


@app.get("/api/auth/personas")
@app.get("/api/personas")
async def personas(session: Session) -> dict[str, Any]:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="Not found")
    demo_organization = await session.scalar(
        select(Organization).where(
            Organization.slug == DEMO_ORG_SLUG,
            Organization.demo_mode.is_(True),
        )
    )
    if demo_organization is None:
        raise HTTPException(status_code=503, detail="Demo organization is unavailable")
    rows = (
        await session.execute(
            select(User, Role)
            .join(
                Membership,
                (Membership.user_id == User.id)
                & (Membership.organization_id == demo_organization.id),
            )
            .join(Role, Role.id == Membership.role_id)
            .where(
                User.organization_id == demo_organization.id,
                User.persona_key.is_not(None),
                User.is_active.is_(True),
            )
            .order_by(User.display_name)
        )
    ).all()
    titles = {
        "patient": "Patient",
        "provider": "Dermatologist",
        "clinical": "Clinical coordinator",
        "biller": "RCM specialist",
        "owner": "MSO owner",
    }
    persona_rows: dict[str, dict[str, Any]] = {}
    for user, role in rows:
        if user.persona_key is None or user.persona_key in persona_rows:
            continue
        persona_rows[user.persona_key] = {
            "id": user.persona_key,
            "persona_key": user.persona_key,
            "name": user.display_name,
            "title": titles.get(user.persona_key or "", role.description),
            "initials": "".join(
                part[0] for part in user.display_name.replace("Dr. ", "").split()[:2]
            ),
            "role": role.name,
            "presenter_capable": user.is_presenter,
        }
    return {"personas": list(persona_rows.values())}


async def _login_persona(
    session: AsyncSession,
    response: Response,
    runtime: Settings,
    persona_key: str,
    presenter_key: str | None,
) -> dict[str, Any]:
    if not runtime.demo_mode:
        raise HTTPException(status_code=404, detail="Demo authentication is disabled")
    user = await session.scalar(
        select(User)
        .join(
            Organization,
            (Organization.id == User.organization_id)
            & (Organization.slug == DEMO_ORG_SLUG)
            & (Organization.demo_mode.is_(True)),
        )
        .where(User.persona_key == persona_key, User.is_active.is_(True))
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo persona")
    presenter_actor_id: uuid.UUID | None = None
    if presenter_key is not None:
        if not hmac.compare_digest(presenter_key, runtime.presenter_key):
            raise HTTPException(status_code=403, detail="Invalid presenter code")
        presenter_actor = (
            user
            if user.is_presenter
            else await session.scalar(
                select(User).where(
                    User.organization_id == user.organization_id,
                    User.is_presenter.is_(True),
                    User.is_active.is_(True),
                )
            )
        )
        if presenter_actor is None:
            raise HTTPException(status_code=503, detail="Presenter identity is unavailable")
        presenter_actor_id = presenter_actor.id
    identity = DemoIdentityProvider(runtime)
    set_session_cookie(
        response,
        identity.issue(user, presenter_actor_id=presenter_actor_id),
        runtime,
    )
    principal = await principal_from_persona(persona_key, session)
    session_data = principal_payload(principal)
    session_data["presenter"] = presenter_actor_id is not None
    session_data["is_presenter"] = presenter_actor_id is not None
    session_data["presenter_actor_id"] = presenter_actor_id
    return {"session": session_data}


@app.post("/api/auth/login")
async def login(
    payload: LoginRequest,
    response: Response,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _login_persona(
        session, response, runtime, payload.persona_key, payload.presenter_key
    )


@app.post("/api/auth/demo/session")
async def demo_session(
    payload: DemoSessionRequest,
    response: Response,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _login_persona(session, response, runtime, payload.persona, payload.presenter_code)


@app.get("/api/auth/me")
async def me(principal: CurrentPrincipal) -> dict[str, Any]:
    return {"session": principal_payload(principal)}


@app.post("/api/auth/logout")
async def logout(
    response: Response, runtime: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    clear_session_cookie(response, runtime)
    return {"authenticated": False}


@app.post("/api/auth/switch")
async def switch_persona(
    payload: SwitchPersonaRequest,
    response: Response,
    presenter: PresenterPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    target = await session.scalar(
        select(User).where(
            User.persona_key == payload.persona_key,
            User.organization_id == presenter.organization_id,
            User.is_active.is_(True),
        )
    )
    if target is None or target.organization_id != presenter.organization_id:
        raise HTTPException(status_code=404, detail="Persona not found")
    actor_id = presenter.presenter_actor_id or presenter.user_id
    set_session_cookie(
        response,
        DemoIdentityProvider(runtime).issue(target, presenter_actor_id=actor_id),
        runtime,
    )
    target_principal = await principal_from_persona(payload.persona_key, session)
    switched = principal_payload(target_principal)
    switched["presenter"] = True
    switched["is_presenter"] = True
    switched["presenter_actor_id"] = actor_id
    return {"session": switched}


async def _resolve_patient(
    session: AsyncSession,
    principal: Principal,
    requested: uuid.UUID | None,
) -> Patient:
    patient_id = requested or principal.patient_id or canonical_ids()["sarah_patient_id"]
    enforce_patient_scope(principal, patient_id)
    patient = await session.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == principal.organization_id,
        )
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.get("/api/patients/{patient_id}")
async def patient_chart(
    patient_id: uuid.UUID,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    enforce_patient_scope(principal, patient_id)
    return await get_patient_bundle(session, principal.organization_id, patient_id)


async def _initiate_patient_journey_legacy(
    payload: PatientInitiationRequest,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    patient = await _resolve_patient(session, principal, payload.patient_id)
    now = await domain_now(session, principal.organization_id)
    conversation = Conversation(
        organization_id=principal.organization_id,
        patient_id=patient.id,
        subject="New changing lesion concern",
        status="open",
        last_message_at=now,
    )
    session.add(conversation)
    await session.flush()
    message = Message(
        organization_id=principal.organization_id,
        conversation_id=conversation.id,
        sender_user_id=principal.user_id,
        sender_kind="patient" if "patient" in principal.roles else "staff",
        body=(
            f"{payload.concern}. Changes: {', '.join(payload.changes)}. "
            f"Symptoms: {', '.join(payload.symptoms) or 'none'}."
        ),
        status="sent",
        sent_at=now,
    )
    session.add(message)
    session.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="patient_concern_initiated",
            entity_type="conversation",
            entity_id=conversation.id,
            patient_id=patient.id,
            occurred_at=now,
            detail_json={
                "urgentWarningSigns": payload.urgent_warning_signs,
                "imageProvided": bool(payload.image_url),
            },
        )
    )
    await session.commit()
    return {
        "conversation_id": conversation.id,
        "patient_id": patient.id,
        "triage": "staff_review" if payload.urgent_warning_signs else "routine",
        "urgent_warning_signs": payload.urgent_warning_signs,
        "availability": await get_availability(session, principal.organization_id),
    }


async def _assert_slot_available(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    starts_at: Any,
    duration_minutes: int = 30,
    exclude_id: uuid.UUID | None = None,
) -> None:
    existing = (
        await session.scalars(
            select(Appointment).where(
                Appointment.organization_id == organization_id,
                Appointment.provider_id == provider_id,
                Appointment.status.not_in(["cancelled", "no_show"]),
            )
        )
    ).all()
    target_end = starts_at + timedelta(minutes=duration_minutes)
    for appointment in existing:
        if exclude_id and appointment.id == exclude_id:
            continue
        existing_start = appointment.starts_at
        if existing_start.tzinfo is None and starts_at.tzinfo is not None:
            existing_start = existing_start.replace(tzinfo=starts_at.tzinfo)
        existing_end = existing_start + timedelta(minutes=appointment.duration_minutes)
        if existing_start < target_end and existing_end > starts_at:
            raise HTTPException(
                status_code=409, detail="This appointment slot is no longer available"
            )
    query = select(Appointment.id).where(
        Appointment.organization_id == organization_id,
        Appointment.provider_id == provider_id,
        Appointment.starts_at == starts_at,
        Appointment.status.not_in(["cancelled", "no_show"]),
    )
    if exclude_id:
        query = query.where(Appointment.id != exclude_id)
    if await session.scalar(query):
        raise HTTPException(status_code=409, detail="This appointment slot is no longer available")


async def _eligibility_and_estimate(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    patient: Patient,
    coverage: Coverage,
    appointment: Appointment,
) -> tuple[EligibilityCheck, Estimate]:
    """Reuse only payer results produced from the current coverage input set."""

    await session.flush()
    input_fingerprint = eligibility_input_fingerprint(coverage, appointment.id)
    eligibility = await session.scalar(
        select(EligibilityCheck)
        .where(
            EligibilityCheck.organization_id == organization_id,
            EligibilityCheck.patient_id == patient.id,
            EligibilityCheck.coverage_id == coverage.id,
            EligibilityCheck.appointment_id == appointment.id,
        )
        .order_by(
            EligibilityCheck.responded_at.desc(),
            EligibilityCheck.created_at.desc(),
            EligibilityCheck.id.desc(),
        )
    )
    if (
        eligibility is None
        or eligibility.response_json.get("inputFingerprint") != input_fingerprint
    ):
        eligibility = await eligibility_provider.check(
            session,
            organization_id=organization_id,
            patient_id=patient.id,
            coverage=coverage,
            appointment_id=appointment.id,
        )
    estimate = await session.scalar(
        select(Estimate)
        .where(
            Estimate.organization_id == organization_id,
            Estimate.patient_id == patient.id,
            Estimate.appointment_id == appointment.id,
            Estimate.eligibility_check_id == eligibility.id,
        )
        .order_by(Estimate.created_at.desc(), Estimate.id.desc())
    )
    if estimate is None:
        estimate = Estimate(
            organization_id=organization_id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            eligibility_check_id=eligibility.id,
            total_charge=Decimal("395.00"),
            expected_plan_payment=Decimal("310.00"),
            patient_responsibility=Decimal("85.00"),
            status="presented",
            disclaimer="Good-faith estimate; final responsibility follows payer adjudication.",
        )
        session.add(estimate)
        await session.flush()
    return eligibility, estimate


async def _require_assigned_encounter_provider(
    session: AsyncSession,
    *,
    principal: Principal,
    encounter_id: uuid.UUID,
) -> Encounter:
    encounter = await session.scalar(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.organization_id == principal.organization_id,
        )
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    assigned_provider = await session.scalar(
        select(Provider).where(
            Provider.id == encounter.provider_id,
            Provider.organization_id == principal.organization_id,
        )
    )
    if assigned_provider is None:
        raise HTTPException(status_code=409, detail="Encounter has no assigned provider")
    if assigned_provider.user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned encounter provider may mutate it without a durable delegation",
        )
    return encounter


@app.get("/api/appointments/availability")
async def availability(principal: PatientCarePrincipal, session: Session) -> dict[str, Any]:
    return {"slots": await get_availability(session, principal.organization_id)}


async def _book_appointment_legacy(
    payload: AppointmentBookingRequest,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    patient = await _resolve_patient(session, principal, payload.patient_id)
    now = await domain_now(session, principal.organization_id)
    provider = await session.scalar(
        select(Provider).where(
            Provider.id == payload.provider_id,
            Provider.organization_id == principal.organization_id,
        )
    )
    location = await session.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.organization_id == principal.organization_id,
        )
    )
    if provider is None or location is None:
        raise HTTPException(status_code=404, detail="Provider or location not found")
    await _assert_slot_available(
        session,
        organization_id=principal.organization_id,
        provider_id=provider.id,
        starts_at=payload.starts_at,
    )
    appointment = Appointment(
        organization_id=principal.organization_id,
        patient_id=patient.id,
        provider_id=provider.id,
        location_id=location.id,
        starts_at=payload.starts_at,
        duration_minutes=30,
        visit_type=payload.visit_type,
        reason=payload.reason,
        status="booked",
        readiness_status="not_started",
        booked_at=now,
    )
    session.add(appointment)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="This appointment slot is no longer available"
        ) from exc
    await session.refresh(appointment)
    return {"appointment": row_dict(appointment)}


@app.post("/api/intake/submissions")
async def composite_intake_submission(
    payload: CompositeIntakeRequest,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    consent_ok = all(
        [
            payload.consents.treatment,
            payload.consents.privacy,
            payload.consents.photography,
        ]
    )
    if not consent_ok:
        raise HTTPException(
            status_code=422,
            detail="Treatment, privacy, and clinical-photography consent are required",
        )
    patient = await _resolve_patient(session, principal, payload.patient_id)
    now = await domain_now(session, principal.organization_id)
    appointment = await session.scalar(
        select(Appointment).where(
            Appointment.id == canonical_ids()["sarah_appointment_id"],
            Appointment.patient_id == patient.id,
            Appointment.organization_id == principal.organization_id,
        )
    )
    selected_slot = None
    if appointment is not None:
        existing_slot_id = availability_slot_id(
            principal.organization_id,
            appointment.provider_id,
            appointment.location_id,
            appointment.starts_at,
        )
        if existing_slot_id == payload.appointment_slot:
            selected_slot = {
                "id": existing_slot_id,
                "provider_id": appointment.provider_id,
                "location_id": appointment.location_id,
                "starts_at": appointment.starts_at,
                "duration_minutes": appointment.duration_minutes,
            }
    if selected_slot is None:
        selected_slot = next(
            (
                slot
                for slot in await get_availability(session, principal.organization_id)
                if slot["id"] == payload.appointment_slot
            ),
            None,
        )
    if selected_slot is None:
        raise HTTPException(
            status_code=409,
            detail="The selected appointment slot is invalid, stale, or no longer available",
        )
    provider = await session.scalar(
        select(Provider).where(
            Provider.id == selected_slot["provider_id"],
            Provider.organization_id == principal.organization_id,
        )
    )
    location = await session.scalar(
        select(Location).where(
            Location.id == selected_slot["location_id"],
            Location.organization_id == principal.organization_id,
        )
    )
    if provider is None or location is None:
        raise HTTPException(
            status_code=409, detail="The selected scheduling resources are unavailable"
        )
    provider_user = await session.scalar(
        select(User).where(
            User.id == provider.user_id,
            User.organization_id == principal.organization_id,
        )
    )
    if provider_user is None:
        raise HTTPException(status_code=409, detail="The selected provider identity is unavailable")
    await _assert_slot_available(
        session,
        organization_id=principal.organization_id,
        provider_id=provider.id,
        starts_at=selected_slot["starts_at"],
        duration_minutes=selected_slot["duration_minutes"],
        exclude_id=appointment.id if appointment else None,
    )
    if appointment is None:
        appointment = Appointment(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            provider_id=provider.id,
            location_id=location.id,
            starts_at=selected_slot["starts_at"],
            duration_minutes=selected_slot["duration_minutes"],
            visit_type="New lesion evaluation",
            reason=payload.reason,
            status="booked",
            readiness_status="in_progress",
            booked_at=now,
        )
        session.add(appointment)
    else:
        appointment.provider_id = provider.id
        appointment.location_id = location.id
        appointment.starts_at = selected_slot["starts_at"]
        appointment.duration_minutes = selected_slot["duration_minutes"]
        appointment.reason = payload.reason
        appointment.status = "booked"
        appointment.readiness_status = "in_progress"
    questionnaire = await session.scalar(
        select(Questionnaire).where(
            Questionnaire.organization_id == principal.organization_id,
            Questionnaire.slug == "new-lesion-intake",
            Questionnaire.is_active.is_(True),
        )
    )
    if questionnaire is None:
        raise HTTPException(status_code=503, detail="Intake questionnaire is unavailable")
    response_record = await session.scalar(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.organization_id == principal.organization_id,
            QuestionnaireResponse.patient_id == patient.id,
            QuestionnaireResponse.questionnaire_id == questionnaire.id,
        )
    )
    normalized_response = {
        "reasonForVisit": payload.reason,
        "firstNoticed": payload.first_noticed,
        "lesionHistory": f"First noticed {payload.first_noticed}",
        "changes": payload.change,
        "symptoms": payload.symptoms,
        "urgentSigns": payload.urgent_signs,
        "personalSkinCancerHistory": payload.personal_skin_cancer_history,
        "familySkinCancerHistory": payload.family_skin_cancer_history,
        "pharmacy": payload.pharmacy,
        "medications": payload.medications,
        "allergies": payload.allergies,
    }
    if response_record is None:
        response_record = QuestionnaireResponse(
            organization_id=principal.organization_id,
            questionnaire_id=questionnaire.id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            status="completed",
            response_json=normalized_response,
            completed_at=now,
        )
        session.add(response_record)
    else:
        response_record.appointment_id = appointment.id
        response_record.response_json = normalized_response
        response_record.status = "completed"
        response_record.completed_at = now
    coverage = await session.scalar(
        select(Coverage).where(
            Coverage.organization_id == principal.organization_id,
            Coverage.patient_id == patient.id,
            Coverage.status == "active",
        )
    )
    if coverage is None:
        coverage = Coverage(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            payer_name=payload.insurance_payer,
            plan_name="Choice Plus",
            member_id=payload.insurance_member_id,
            subscriber_name=f"{patient.first_name} {patient.last_name}",
            relationship="self",
            effective_date=now.date().replace(month=1, day=1),
            status="active",
        )
        session.add(coverage)
    else:
        coverage.payer_name = payload.insurance_payer
        coverage.member_id = payload.insurance_member_id
    for medication_text in payload.medications:
        name = medication_text.split()[0]
        existing_medication = await session.scalar(
            select(Medication).where(
                Medication.organization_id == principal.organization_id,
                Medication.patient_id == patient.id,
                func.lower(Medication.name).like(f"{name.lower()}%"),
                Medication.status == "active",
            )
        )
        if existing_medication is None:
            session.add(
                Medication(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    name=medication_text,
                    dose=medication_text.removeprefix(name).strip() or None,
                    prescriber=f"Patient-reported verbatim: {medication_text}",
                    status="active",
                )
            )
        else:
            existing_medication.prescriber = f"Patient-reported verbatim: {medication_text}"
    for allergy_text in payload.allergies:
        parts = allergy_text.replace("—", "-").split("-", 1)
        substance = parts[0].strip()
        reaction = parts[1].strip() if len(parts) > 1 else "Patient-reported reaction"
        existing_allergy = await session.scalar(
            select(Allergy).where(
                Allergy.organization_id == principal.organization_id,
                Allergy.patient_id == patient.id,
                func.lower(Allergy.substance) == substance.lower(),
                Allergy.status == "active",
            )
        )
        if existing_allergy is None:
            session.add(
                Allergy(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    substance=substance,
                    reaction=reaction,
                    severity="mild",
                    status="active",
                )
            )
    problem_specs = [
        ("Z86.018", payload.personal_skin_cancer_history),
        ("Z80.8", payload.family_skin_cancer_history),
    ]
    for code, display in problem_specs:
        if display.strip().lower() in {"none", "no", "n/a"}:
            continue
        existing_problem = await session.scalar(
            select(Problem).where(
                Problem.organization_id == principal.organization_id,
                Problem.patient_id == patient.id,
                Problem.code == code,
                Problem.status == "active",
            )
        )
        if existing_problem:
            existing_problem.display = display
        else:
            session.add(
                Problem(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    code=code,
                    display=display,
                    onset_date=now.date(),
                    status="active",
                )
            )
    pharmacy_contact = await session.scalar(
        select(PatientContact).where(
            PatientContact.organization_id == principal.organization_id,
            PatientContact.patient_id == patient.id,
            PatientContact.kind == "pharmacy",
            PatientContact.is_primary.is_(True),
        )
    )
    if pharmacy_contact is None:
        session.add(
            PatientContact(
                organization_id=principal.organization_id,
                patient_id=patient.id,
                kind="pharmacy",
                name=payload.pharmacy.split(",", 1)[0],
                value=payload.pharmacy,
                is_primary=True,
            )
        )
    else:
        pharmacy_contact.name = payload.pharmacy.split(",", 1)[0]
        pharmacy_contact.value = payload.pharmacy
    eligibility, estimate = await _eligibility_and_estimate(
        session,
        organization_id=principal.organization_id,
        patient=patient,
        coverage=coverage,
        appointment=appointment,
    )
    consent_types = ["treatment", "privacy", "clinical_photography"]
    for consent_type in consent_types:
        existing_consent = await session.scalar(
            select(Consent).where(
                Consent.organization_id == principal.organization_id,
                Consent.patient_id == patient.id,
                Consent.consent_type == consent_type,
                Consent.revoked_at.is_(None),
            )
        )
        if existing_consent is None:
            session.add(
                Consent(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    consent_type=consent_type,
                    version="2026.1",
                    accepted_at=now,
                    accepted_by_name=f"{patient.first_name} {patient.last_name}",
                    signature_text=f"{patient.first_name} {patient.last_name}",
                )
            )
    lesion = await session.scalar(
        select(Lesion).where(
            Lesion.organization_id == principal.organization_id,
            Lesion.patient_id == patient.id,
            Lesion.anatomical_location == "left posterior shoulder",
        )
    )
    file_record = None
    if payload.image:
        if lesion is None:
            raise HTTPException(
                status_code=409,
                detail="The referenced image cannot be linked until the lesion exists",
            )
        file_record = await session.scalar(
            select(FileRecord).where(
                FileRecord.id == payload.image.file_id,
                FileRecord.organization_id == principal.organization_id,
                FileRecord.patient_id == patient.id,
                FileRecord.classification == "synthetic_clinical_image",
            )
        )
        if file_record is None:
            raise HTTPException(status_code=404, detail="Synthetic image reference not found")
        if not hmac.compare_digest(file_record.sha256.lower(), payload.image.sha256.lower()):
            raise HTTPException(
                status_code=422,
                detail="Synthetic image hash does not match the server-owned file record",
            )
        linked_image = await session.scalar(
            select(ClinicalImage).where(
                ClinicalImage.organization_id == principal.organization_id,
                ClinicalImage.file_record_id == file_record.id,
            )
        )
        if linked_image is None:
            session.add(
                ClinicalImage(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    lesion_id=lesion.id,
                    file_record_id=file_record.id,
                    captured_at=now,
                    anatomical_location=lesion.anatomical_location,
                    view="patient_overview",
                    is_patient_submitted=True,
                )
            )
        elif linked_image.patient_id != patient.id or linked_image.lesion_id != lesion.id:
            raise HTTPException(
                status_code=409,
                detail="Synthetic image is already linked to a different clinical record",
            )
    actionable_urgent_signs = [
        item
        for item in payload.urgent_signs
        if item.strip().lower() not in {"none", "none of these", "no", "n/a"}
    ]
    triage_task_id = uuid.uuid5(response_record.id, "urgent-intake-triage")
    triage_task = await session.scalar(
        select(Task).where(
            Task.id == triage_task_id,
            Task.organization_id == principal.organization_id,
            Task.patient_id == patient.id,
        )
    )
    triage_notification = None
    if actionable_urgent_signs:
        clinical_user = await session.scalar(
            select(User).where(
                User.organization_id == principal.organization_id,
                User.persona_key == "clinical",
                User.is_active.is_(True),
            )
        )
        if triage_task is None:
            triage_task = Task(
                id=triage_task_id,
                organization_id=principal.organization_id,
                patient_id=patient.id,
                assigned_user_id=clinical_user.id if clinical_user else None,
                task_type="urgent_intake_triage",
                title="Review urgent lesion-intake warning signs",
                description="; ".join(actionable_urgent_signs),
                priority="high",
                status="open",
                due_at=now + timedelta(minutes=15),
            )
            session.add(triage_task)
        if clinical_user:
            notification_id = uuid.uuid5(response_record.id, "urgent-intake-notification")
            triage_notification = await session.scalar(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.organization_id == principal.organization_id,
                )
            )
            if triage_notification is None:
                triage_notification = Notification(
                    id=notification_id,
                    organization_id=principal.organization_id,
                    user_id=clinical_user.id,
                    title="Urgent intake needs clinical review",
                    body=f"{patient.first_name} {patient.last_name}: "
                    + "; ".join(actionable_urgent_signs),
                    kind="urgent_intake_triage",
                    entity_type="questionnaire_response",
                    entity_id=response_record.id,
                )
                session.add(triage_notification)
        appointment.readiness_status = "needs_review"
    elif triage_task and triage_task.status != "completed":
        appointment.readiness_status = "needs_review"
    else:
        appointment.readiness_status = "ready"
    reminder = await session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.organization_id == principal.organization_id,
            AppointmentReminder.appointment_id == appointment.id,
            AppointmentReminder.channel == "sms",
        )
    )
    if reminder is None:
        reminder = AppointmentReminder(
            organization_id=principal.organization_id,
            appointment_id=appointment.id,
            channel="sms",
            scheduled_for=appointment.starts_at - timedelta(days=1),
            delivery_status="scheduled",
        )
        session.add(reminder)
    else:
        reminder.scheduled_for = appointment.starts_at - timedelta(days=1)
    existing_audit = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == principal.organization_id,
            AuditEvent.actor_user_id == principal.user_id,
            AuditEvent.action == "intake_submitted",
            AuditEvent.entity_id == response_record.id,
        )
    )
    if existing_audit is None:
        session.add(
            AuditEvent(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                action="intake_submitted",
                entity_type="questionnaire_response",
                entity_id=response_record.id,
                patient_id=patient.id,
                occurred_at=now,
                detail_json={"normalized": True, "urgentSigns": payload.urgent_signs},
            )
        )
    await set_demo_chapter(session, principal.organization_id, "command_center")
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="The intake or appointment was already recorded"
        ) from exc
    return {
        "message": "Intake complete and appointment confirmed",
        "patient_id": patient.id,
        "appointment_id": appointment.id,
        "appointment": {
            "id": appointment.id,
            "slot_id": selected_slot["id"],
            "provider_id": provider.id,
            "provider": provider_user.display_name,
            "location_id": location.id,
            "location": location.name,
            "starts_at": appointment.starts_at,
            "status": appointment.status,
        },
        "questionnaire_response_id": response_record.id,
        "eligibility_check_id": eligibility.id,
        "estimate_id": estimate.id,
        "image_file_id": file_record.id if file_record else None,
        "eligibility_status": eligibility.status,
        "patient_responsibility": estimate.patient_responsibility,
        "triage": {
            "status": (
                "staff_review" if appointment.readiness_status == "needs_review" else "routine"
            ),
            "task_id": triage_task.id if triage_task else None,
            "notification_id": triage_notification.id if triage_notification else None,
            "readiness_status": appointment.readiness_status,
        },
        "preparation_instructions": [
            "Bring a photo ID and insurance card",
            "Wear clothing that makes the shoulder easy to examine",
            "Continue prescribed medications unless your clinician directs otherwise",
        ],
    }


async def _submit_structured_intake_legacy(
    payload: IntakeRequest,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    patient = await _resolve_patient(session, principal, payload.patient_id)
    now = await domain_now(session, principal.organization_id)
    appointment = await session.scalar(
        select(Appointment).where(
            Appointment.id == payload.appointment_id,
            Appointment.patient_id == patient.id,
            Appointment.organization_id == principal.organization_id,
        )
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    consent_aliases = {"photography": "clinical_photography"}
    accepted_consents = {
        consent_aliases.get(item.consent_type, item.consent_type)
        for item in payload.consents
        if item.accepted and item.signature_text.strip()
    }
    required_consents = {"treatment", "privacy", "clinical_photography"}
    if missing_consents := required_consents - accepted_consents:
        raise HTTPException(
            status_code=422,
            detail=f"Missing explicit consent: {', '.join(sorted(missing_consents))}",
        )
    questionnaire = await session.scalar(
        select(Questionnaire).where(
            Questionnaire.organization_id == principal.organization_id,
            Questionnaire.slug == "new-lesion-intake",
            Questionnaire.is_active.is_(True),
        )
    )
    if questionnaire is None:
        raise HTTPException(status_code=503, detail="Intake questionnaire is unavailable")
    for item in payload.medications:
        existing = await session.scalar(
            select(Medication).where(
                Medication.organization_id == principal.organization_id,
                Medication.patient_id == patient.id,
                func.lower(Medication.name) == item.name.lower(),
                Medication.status == "active",
            )
        )
        if existing:
            existing.dose = item.dose
            existing.frequency = item.frequency
        else:
            session.add(
                Medication(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    name=item.name,
                    dose=item.dose,
                    frequency=item.frequency,
                    status="active",
                )
            )
    for item in payload.allergies:
        existing = await session.scalar(
            select(Allergy).where(
                Allergy.organization_id == principal.organization_id,
                Allergy.patient_id == patient.id,
                func.lower(Allergy.substance) == item.substance.lower(),
                Allergy.status == "active",
            )
        )
        if existing:
            existing.reaction = item.reaction
            existing.severity = item.severity
        else:
            session.add(
                Allergy(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    substance=item.substance,
                    reaction=item.reaction,
                    severity=item.severity,
                    status="active",
                )
            )
    coverage = await session.scalar(
        select(Coverage).where(
            Coverage.organization_id == principal.organization_id,
            Coverage.patient_id == patient.id,
            Coverage.status == "active",
        )
    )
    insurance = payload.insurance
    if coverage is None:
        coverage = Coverage(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            payer_name=insurance.payer_name,
            plan_name=insurance.plan_name,
            member_id=insurance.member_id,
            group_number=insurance.group_number,
            subscriber_name=insurance.subscriber_name,
            relationship=insurance.relationship,
            effective_date=now.date().replace(month=1, day=1),
            status="active",
        )
        session.add(coverage)
    else:
        coverage.payer_name = insurance.payer_name
        coverage.plan_name = insurance.plan_name
        coverage.member_id = insurance.member_id
        coverage.group_number = insurance.group_number
        coverage.subscriber_name = insurance.subscriber_name
        coverage.relationship = insurance.relationship
    for consent in payload.consents:
        if not consent.accepted:
            continue
        consent_type = consent_aliases.get(consent.consent_type, consent.consent_type)
        existing = await session.scalar(
            select(Consent).where(
                Consent.organization_id == principal.organization_id,
                Consent.patient_id == patient.id,
                Consent.consent_type == consent_type,
                Consent.version == consent.version,
                Consent.revoked_at.is_(None),
            )
        )
        if existing is None:
            session.add(
                Consent(
                    organization_id=principal.organization_id,
                    patient_id=patient.id,
                    encounter_id=None,
                    consent_type=consent_type,
                    version=consent.version,
                    accepted_at=now,
                    accepted_by_name=f"{patient.first_name} {patient.last_name}",
                    signature_text=consent.signature_text,
                )
            )
    response_record = await session.scalar(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.organization_id == principal.organization_id,
            QuestionnaireResponse.patient_id == patient.id,
            QuestionnaireResponse.appointment_id == appointment.id,
        )
    )
    answers = {
        "reasonForVisit": payload.reason_for_visit,
        "lesionHistory": payload.lesion_history,
        "symptoms": payload.symptoms,
        "changes": payload.changes,
        "personalSkinCancerHistory": payload.personal_skin_cancer_history,
        "familySkinCancerHistory": payload.family_skin_cancer_history,
        "pharmacy": payload.pharmacy,
        "imageUrls": payload.image_urls,
    }
    if response_record is None:
        response_record = QuestionnaireResponse(
            organization_id=principal.organization_id,
            questionnaire_id=questionnaire.id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            status="completed",
            response_json=answers,
            completed_at=now,
        )
        session.add(response_record)
    else:
        response_record.response_json = answers
        response_record.status = "completed"
        response_record.completed_at = now
    appointment.readiness_status = "ready"
    await set_demo_chapter(session, principal.organization_id, "command_center")
    eligibility, estimate = await _eligibility_and_estimate(
        session,
        organization_id=principal.organization_id,
        patient=patient,
        coverage=coverage,
        appointment=appointment,
    )
    await session.commit()
    return {
        "patient_id": patient.id,
        "appointment_id": appointment.id,
        "response_id": response_record.id,
        "eligibility": row_dict(eligibility),
        "estimate": row_dict(estimate),
        "normalized_records": {
            "medications": len(payload.medications),
            "allergies": len(payload.allergies),
            "consents": sum(item.accepted for item in payload.consents),
            "coverage": 1,
        },
    }


@app.get("/api/dashboard/command-center")
@app.get("/api/dashboard")
async def dashboard(principal: OperationsPrincipal, session: Session) -> dict[str, Any]:
    data = await command_center(session, principal.organization_id)
    if "mso_owner" in principal.roles and not principal.is_presenter:
        return {**data, "schedule": [], "work_queue": []}
    return data


@app.get("/api/encounters/{encounter_id}")
async def encounter_detail(
    encounter_id: uuid.UUID,
    principal: ClinicalPrincipal,
    session: Session,
) -> dict[str, Any]:
    bundle = await get_encounter_bundle(session, principal.organization_id, encounter_id)
    enforce_patient_scope(principal, bundle["patient_id"])
    return bundle


@app.post("/api/encounters/{encounter_id}/ambient")
async def ambient_note(
    encounter_id: uuid.UUID,
    payload: AmbientRequest,
    principal: ProviderPrincipal,
    session: Session,
) -> dict[str, Any]:
    encounter = await _require_assigned_encounter_provider(
        session,
        principal=principal,
        encounter_id=encounter_id,
    )
    await set_demo_chapter(session, principal.organization_id, "encounter")
    patient = await session.scalar(
        select(Patient).where(
            Patient.id == encounter.patient_id,
            Patient.organization_id == principal.organization_id,
        )
    )
    encounter.ambient_transcript = payload.transcript
    run, output = await run_ai(
        session,
        organization_id=principal.organization_id,
        capability="ambient_note",
        context={
            "patientName": f"{patient.first_name} {patient.last_name}",
            "transcript": payload.transcript,
            "encounterId": str(encounter.id),
        },
        patient_id=patient.id,
        requested_by_user_id=principal.user_id,
    )
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.encounter_id == encounter.id,
            EncounterNote.organization_id == principal.organization_id,
        )
    )
    if note is None:
        note = EncounterNote(
            organization_id=principal.organization_id,
            encounter_id=encounter.id,
            author_user_id=principal.user_id,
            status="proposed",
            content="",
            structured_content={},
            current_version=0,
        )
        session.add(note)
        await session.flush()
    if note.status in {"signed", "amended"}:
        raise HTTPException(status_code=409, detail="AI cannot replace a signed note")
    structured = output.model_dump(mode="json", by_alias=True)
    note.structured_content = structured
    note.content = (
        f"Subjective: {output.subjective}\n\nObjective: {output.objective}\n\n"
        f"Assessment: {output.assessment}\n\nPlan: {'; '.join(output.plan)}"
    )
    note.status = "proposed"
    note.ai_run_id = run.id
    note.current_version += 1
    session.add(
        NoteVersion(
            organization_id=principal.organization_id,
            note_id=note.id,
            version_number=note.current_version,
            author_user_id=principal.user_id,
            content=note.content,
            structured_content=structured,
            content_hash=hashlib.sha256(note.content.encode()).hexdigest(),
            reason="Ambient transcript draft",
            created_at=run.completed_at,
            updated_at=run.completed_at,
        )
    )
    await session.commit()
    return {
        "ai_run": row_dict(run),
        "note": row_dict(note),
        "output": structured,
        "requires_approval": True,
    }


@app.patch("/api/notes/{note_id}")
async def update_draft_note(
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
    principal: ProviderPrincipal,
    session: Session,
) -> dict[str, Any]:
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.id == note_id,
            EncounterNote.organization_id == principal.organization_id,
        )
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await _require_assigned_encounter_provider(
        session,
        principal=principal,
        encounter_id=note.encounter_id,
    )
    if note.status in {"signed", "amended"}:
        raise HTTPException(status_code=409, detail="Signed notes are immutable; add an amendment")
    now = await domain_now(session, principal.organization_id)
    note.content = payload.content
    note.structured_content = payload.structured_content
    note.status = "draft"
    note.current_version += 1
    version = NoteVersion(
        organization_id=principal.organization_id,
        note_id=note.id,
        version_number=note.current_version,
        author_user_id=principal.user_id,
        content=payload.content,
        structured_content=payload.structured_content,
        content_hash=hashlib.sha256(payload.content.encode()).hexdigest(),
        reason=payload.reason,
        created_at=now,
        updated_at=now,
    )
    session.add(version)
    await session.commit()
    return {"note": row_dict(note), "version": row_dict(version)}


@app.post("/api/notes/{note_id}/amendments")
async def amend_note(
    note_id: uuid.UUID,
    payload: AmendmentRequest,
    principal: ProviderPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.id == note_id,
            EncounterNote.organization_id == principal.organization_id,
        )
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await _require_assigned_encounter_provider(
        session,
        principal=principal,
        encounter_id=note.encounter_id,
    )
    if note.status not in {"signed", "amended"}:
        raise HTTPException(status_code=409, detail="Only signed notes may be amended")
    signed_at = await domain_now(session, principal.organization_id)
    signature = hashlib.sha256(
        f"{note.id}|{payload.reason}|{payload.amendment_text}|{principal.user_id}|{signed_at.isoformat()}|{runtime.session_secret}".encode()
    ).hexdigest()
    amendment = NoteAmendment(
        organization_id=principal.organization_id,
        note_id=note.id,
        author_user_id=principal.user_id,
        reason=payload.reason,
        amendment_text=payload.amendment_text,
        signed_at=signed_at,
        signature_hash=signature,
    )
    session.add(amendment)
    note.status = "amended"
    session.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="signed_note_amended",
            entity_type="note_amendment",
            entity_id=amendment.id,
            occurred_at=signed_at,
            detail_json={"noteId": str(note.id), "reason": payload.reason},
        )
    )
    await session.commit()
    return {"note": row_dict(note), "amendment": row_dict(amendment)}


@app.get("/api/lesions/{lesion_id}")
async def lesion_timeline(
    lesion_id: uuid.UUID,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    lesion = await session.scalar(
        select(Lesion).where(
            Lesion.id == lesion_id,
            Lesion.organization_id == principal.organization_id,
        )
    )
    if lesion is None:
        raise HTTPException(status_code=404, detail="Lesion not found")
    enforce_patient_scope(principal, lesion.patient_id)
    observations = (
        await session.scalars(
            select(LesionObservation)
            .where(
                LesionObservation.lesion_id == lesion.id,
                LesionObservation.organization_id == principal.organization_id,
            )
            .order_by(LesionObservation.observed_at)
        )
    ).all()
    images = (
        await session.execute(
            select(ClinicalImage, FileRecord)
            .join(
                FileRecord,
                (FileRecord.id == ClinicalImage.file_record_id)
                & (FileRecord.organization_id == principal.organization_id),
            )
            .where(
                ClinicalImage.lesion_id == lesion.id,
                ClinicalImage.organization_id == principal.organization_id,
            )
        )
    ).all()
    return {
        "lesion": row_dict(lesion),
        "observations": [row_dict(item) for item in observations],
        "images": [{**row_dict(image), "url": file.public_demo_url} for image, file in images],
    }


@app.post("/api/lesions/observations")
async def add_lesion_observation(
    payload: LesionObservationRequest,
    principal: ClinicalPrincipal,
    session: Session,
) -> dict[str, Any]:
    if payload.lesion_id is None:
        raise HTTPException(status_code=422, detail="Lesion ID is required")
    lesion = await session.scalar(
        select(Lesion).where(
            Lesion.id == payload.lesion_id,
            Lesion.organization_id == principal.organization_id,
        )
    )
    if lesion is None:
        raise HTTPException(status_code=404, detail="Lesion not found")
    if payload.encounter_id:
        encounter = await _require_assigned_encounter_provider(
            session,
            principal=principal,
            encounter_id=payload.encounter_id,
        )
        if encounter.patient_id != lesion.patient_id:
            raise HTTPException(status_code=404, detail="Encounter not found for this patient")
    observed_at = await domain_now(session, principal.organization_id)
    previous_observed_at = await session.scalar(
        select(LesionObservation.observed_at)
        .where(
            LesionObservation.lesion_id == lesion.id,
            LesionObservation.organization_id == principal.organization_id,
        )
        .order_by(LesionObservation.observed_at.desc())
    )
    if previous_observed_at:
        previous_observed_at = previous_observed_at.replace(
            tzinfo=previous_observed_at.tzinfo or UTC
        )
        if previous_observed_at >= observed_at:
            observed_at = previous_observed_at + timedelta(microseconds=1)
    observation = LesionObservation(
        organization_id=principal.organization_id,
        lesion_id=lesion.id,
        encounter_id=payload.encounter_id,
        observed_at=observed_at,
        anatomical_site=payload.site or lesion.anatomical_location,
        body_map_view=payload.view or lesion.body_map_view,
        length_mm=payload.length_mm,
        width_mm=payload.width_mm,
        morphology=payload.morphology,
        border=payload.border,
        pigmentation=payload.pigmentation,
        change_over_time=payload.change_over_time,
        symptoms="; ".join(payload.symptoms)
        if isinstance(payload.symptoms, list)
        else payload.symptoms,
        comparison=payload.comparison,
        assessment=payload.assessment,
        source="clinician",
    )
    session.add(observation)
    await session.commit()
    return {
        "observation": row_dict(observation),
        "observation_id": observation.id,
        "recorded_at": observation.observed_at,
    }


@app.post("/api/lesions/{lesion_id}/observations")
async def add_scoped_lesion_observation(
    lesion_id: uuid.UUID,
    payload: LesionObservationRequest,
    principal: ClinicalPrincipal,
    session: Session,
) -> dict[str, Any]:
    if payload.lesion_id is not None and payload.lesion_id != lesion_id:
        raise HTTPException(status_code=422, detail="Path and body lesion IDs do not match")
    result = await add_lesion_observation(
        payload.model_copy(update={"lesion_id": lesion_id}), principal, session
    )
    observation = result["observation"]
    return {
        **result,
        "observation_id": observation["id"],
        "recorded_at": observation["observed_at"],
    }


@app.post("/api/encounters/{encounter_id}/note-draft")
async def save_encounter_note_draft(
    encounter_id: uuid.UUID,
    payload: EncounterNoteDraftRequest,
    principal: ProviderPrincipal,
    session: Session,
) -> dict[str, Any]:
    encounter = await _require_assigned_encounter_provider(
        session,
        principal=principal,
        encounter_id=encounter_id,
    )
    note = await session.scalar(
        select(EncounterNote).where(
            EncounterNote.encounter_id == encounter.id,
            EncounterNote.organization_id == principal.organization_id,
        )
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Encounter note not found")
    if note.status in {"signed", "amended"}:
        raise HTTPException(status_code=409, detail="Signed notes are immutable; add an amendment")
    now = await domain_now(session, principal.organization_id)
    structured = dict(note.structured_content)
    structured["assessmentPlan"] = payload.assessment_plan
    note.structured_content = structured
    note.content = f"{note.content.rstrip()}\n\nAssessment and plan: {payload.assessment_plan}"
    note.status = "draft"
    note.current_version += 1
    version = NoteVersion(
        organization_id=principal.organization_id,
        note_id=note.id,
        version_number=note.current_version,
        author_user_id=principal.user_id,
        content=note.content,
        structured_content=structured,
        content_hash=hashlib.sha256(note.content.encode()).hexdigest(),
        reason="Clinician saved assessment and plan draft",
        created_at=now,
        updated_at=now,
    )
    session.add(version)
    await session.commit()
    return {
        "note_id": note.id,
        "version": note.current_version,
        "saved_at": now,
    }


@app.post("/api/encounters/{encounter_id}/review-complete")
@app.post("/api/encounters/{encounter_id}/complete")
async def review_and_complete(
    encounter_id: uuid.UUID,
    payload: ReviewCompleteRequest,
    principal: ProviderPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not payload.attest or not payload.sign_note:
        raise HTTPException(status_code=422, detail="Clinician attestation is required")
    if not payload.proposed_action_ids:
        raise HTTPException(status_code=422, detail="Select the proposed actions to approve")
    bundle = await complete_encounter_review(
        session,
        organization_id=principal.organization_id,
        encounter_id=encounter_id,
        reviewer_user_id=principal.user_id,
        signature_secret=runtime.session_secret,
        selected_action_ids=payload.proposed_action_ids,
        expected_note_version=payload.expected_note_version,
        expected_note_hash=payload.expected_note_hash,
        attestation=payload.attestation,
    )
    workflow = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.organization_id == principal.organization_id,
            WorkflowRun.workflow_type == "biopsy_completion",
            WorkflowRun.entity_id == encounter_id,
        )
    )
    artifacts = workflow.output_json if workflow else {}
    note = bundle["note"]
    procedure = await session.scalar(
        select(Procedure).where(
            Procedure.organization_id == principal.organization_id,
            Procedure.encounter_id == encounter_id,
            Procedure.code == "11102",
        )
    )
    order = await session.scalar(
        select(Order).where(
            Order.organization_id == principal.organization_id,
            Order.encounter_id == encounter_id,
            Order.order_type == "surgical_pathology",
        )
    )
    specimen = (
        await session.scalar(
            select(Specimen).where(
                Specimen.organization_id == principal.organization_id,
                Specimen.order_id == order.id,
            )
        )
        if order
        else None
    )
    claim = await session.scalar(
        select(Claim).where(
            Claim.organization_id == principal.organization_id,
            Claim.encounter_id == encounter_id,
        )
    )
    closure_task = await session.scalar(
        select(Task).where(
            Task.organization_id == principal.organization_id,
            Task.encounter_id == encounter_id,
            Task.task_type == "pathology_tracking",
        )
    )
    await session.commit()
    return {
        "encounter_id": bundle["id"],
        "status": bundle["status"],
        "signed_at": note["signed_at"],
        "note_id": note["id"],
        "note_version": note["current_version"],
        "consent_id": artifacts.get("consentId"),
        "procedure_id": artifacts.get("procedureId") or (procedure.id if procedure else None),
        "specimen_id": artifacts.get("specimenId") or (specimen.id if specimen else None),
        "order_id": artifacts.get("orderId") or (order.id if order else None),
        "claim_id": artifacts.get("claimId") or (claim.id if claim else None),
        "message_id": artifacts.get("messageId"),
        "closure_task_id": artifacts.get("taskId") or (closure_task.id if closure_task else None),
    }


@app.get("/api/pathology")
@app.get("/api/pathology/results")
async def pathology_queue(principal: ClinicalPrincipal, session: Session) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(DiagnosticResult, Patient, Specimen)
            .join(
                Patient,
                (Patient.id == DiagnosticResult.patient_id)
                & (Patient.organization_id == principal.organization_id),
            )
            .join(
                Specimen,
                (Specimen.id == DiagnosticResult.specimen_id)
                & (Specimen.organization_id == principal.organization_id),
            )
            .where(DiagnosticResult.organization_id == principal.organization_id)
            .order_by(DiagnosticResult.resulted_at.desc())
        )
    ).all()
    return {
        "results": [
            {
                **row_dict(result),
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "accession_number": specimen.accession_number,
            }
            for result, patient, specimen in rows
        ]
    }


@app.post("/api/pathology/{result_id}/review")
@app.post("/api/pathology/results/{result_id}/review")
async def review_pathology_result(
    result_id: uuid.UUID,
    payload: PathologyReviewRequest,
    principal: ProviderPrincipal,
    session: Session,
) -> dict[str, Any]:
    result = await session.scalar(
        select(DiagnosticResult).where(
            DiagnosticResult.id == result_id,
            DiagnosticResult.organization_id == principal.organization_id,
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pathology result not found")
    assigned_provider = await session.scalar(
        select(Provider).where(
            Provider.id == result.clinician_id,
            Provider.organization_id == principal.organization_id,
        )
    )
    if assigned_provider is None or assigned_provider.user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the result's assigned clinician may review without a durable delegation",
        )
    order = await session.scalar(
        select(Order).where(
            Order.id == result.order_id,
            Order.organization_id == principal.organization_id,
            Order.patient_id == result.patient_id,
        )
    )
    if order is None:
        raise HTTPException(status_code=409, detail="Pathology result has no valid source order")
    now = await domain_now(session, principal.organization_id)
    if result.reviewed_at is None:
        result.reviewed_at = now
        result.reviewed_by_user_id = principal.user_id
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == uuid.uuid5(order.encounter_id, "pathology-conversation"),
            Conversation.patient_id == result.patient_id,
            Conversation.organization_id == principal.organization_id,
        )
    )
    sent_message = None
    if payload.notify_patient:
        if conversation is None:
            raise HTTPException(
                status_code=409,
                detail="Pathology result has no encounter-linked patient conversation",
            )
        draft = await session.scalar(
            select(MessageDraft).where(
                MessageDraft.id == uuid.uuid5(result.id, "patient-draft"),
                MessageDraft.conversation_id == conversation.id,
                MessageDraft.organization_id == principal.organization_id,
                MessageDraft.status.in_(["proposed", "approved"]),
            )
        )
        if draft is None and not payload.patient_message:
            raise HTTPException(
                status_code=409,
                detail="Patient notification requires the visible AI draft or an explicit reviewed body",
            )
        body = payload.patient_message or draft.body
        notification_id = uuid.uuid5(result.id, "patient-pathology-notification")
        sent_message = await session.scalar(
            select(Message).where(
                Message.id == notification_id,
                Message.organization_id == principal.organization_id,
                Message.conversation_id == conversation.id,
            )
        )
        if sent_message is None:
            sent_message = Message(
                id=notification_id,
                organization_id=principal.organization_id,
                conversation_id=conversation.id,
                sender_user_id=principal.user_id,
                sender_kind="provider",
                body=body,
                status="sent",
                sent_at=now,
                ai_run_id=draft.ai_run_id if draft else None,
            )
            session.add(sent_message)
            conversation.last_message_at = now
            await session.flush()
            await messaging_provider.deliver_message(session, sent_message)
            if draft:
                session.add(
                    ProvenanceRecord(
                        organization_id=principal.organization_id,
                        entity_type="message",
                        entity_id=sent_message.id,
                        activity="human_approved_ai_draft",
                        actor_user_id=principal.user_id,
                        ai_run_id=draft.ai_run_id,
                        source_entity_type="message_draft",
                        source_entity_id=draft.id,
                        detail_json={"editedBeforeSend": body.strip() != draft.body.strip()},
                    )
                )
            await session.flush()
        if draft:
            draft.status = "approved"
        result.patient_notified_at = result.patient_notified_at or now
    review_task = await session.scalar(
        select(Task).where(
            Task.id == uuid.uuid5(result.id, "review-task"),
            Task.organization_id == principal.organization_id,
            Task.patient_id == result.patient_id,
            Task.encounter_id == order.encounter_id,
            Task.task_type == "pathology_review",
            Task.status != "completed",
        )
    )
    closure_task = await session.scalar(
        select(Task).where(
            Task.id == uuid.uuid5(order.encounter_id, "pathology-tracking-task"),
            Task.organization_id == principal.organization_id,
            Task.patient_id == result.patient_id,
            Task.encounter_id == order.encounter_id,
            Task.task_type == "pathology_tracking",
            Task.status != "completed",
        )
    )
    if review_task:
        review_task.status = "completed"
        review_task.completed_at = now
    if closure_task and result.patient_notified_at:
        closure_task.status = "completed"
        closure_task.completed_at = now
    followup = None
    if payload.create_followup:
        followup_id = uuid.uuid5(result.id, "six-month-lesion-followup")
        followup = await session.scalar(
            select(Task).where(
                Task.id == followup_id,
                Task.organization_id == principal.organization_id,
            )
        )
        if followup is None:
            followup = Task(
                id=followup_id,
                organization_id=principal.organization_id,
                patient_id=result.patient_id,
                assigned_user_id=principal.user_id,
                task_type="followup_scheduling",
                title="Offer six-month lesion follow-up",
                description=(
                    "Offer a six-month lesion and biopsy-site check; record appointment acceptance "
                    "or documented deferral."
                ),
                priority="routine",
                status="open",
                due_at=now + timedelta(days=14),
            )
            session.add(followup)
    audit_action = (
        "pathology_reviewed_and_notified" if payload.notify_patient else "pathology_reviewed"
    )
    audit_id = uuid.uuid5(
        result.id,
        f"{audit_action}:{payload.create_followup}:{payload.disposition}",
    )
    audit = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.id == audit_id,
            AuditEvent.organization_id == principal.organization_id,
        )
    )
    if audit is None:
        audit = AuditEvent(
            id=audit_id,
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action=audit_action,
            entity_type="diagnostic_result",
            entity_id=result.id,
            patient_id=result.patient_id,
            occurred_at=now,
            detail_json={
                "messageId": str(sent_message.id) if sent_message else None,
                "followupId": str(followup.id) if followup else None,
                "disposition": payload.disposition,
            },
        )
        session.add(audit)
    await session.flush()
    await session.commit()
    return {
        "result_id": result.id,
        "review_id": audit.id,
        "status": "notified" if result.patient_notified_at else "reviewed",
        "reviewed_at": result.reviewed_at,
        "notification_id": sent_message.id if sent_message else None,
        "closure_task_id": closure_task.id if closure_task else None,
        "followup_id": followup.id if followup else None,
    }


@app.get("/api/messages")
async def conversations(principal: PatientCarePrincipal, session: Session) -> dict[str, Any]:
    query = select(Conversation).where(Conversation.organization_id == principal.organization_id)
    if "patient" in principal.roles:
        query = query.where(Conversation.patient_id == principal.patient_id)
    conversation_rows = (
        await session.scalars(query.order_by(Conversation.last_message_at.desc()))
    ).all()
    output = []
    for conversation in conversation_rows:
        message_rows = (
            await session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.organization_id == principal.organization_id,
                )
                .order_by(Message.sent_at)
            )
        ).all()
        drafts = []
        if "patient" not in principal.roles:
            drafts = (
                await session.scalars(
                    select(MessageDraft).where(
                        MessageDraft.conversation_id == conversation.id,
                        MessageDraft.organization_id == principal.organization_id,
                        MessageDraft.status == "proposed",
                    )
                )
            ).all()
        output.append(
            {
                **row_dict(conversation),
                "messages": [row_dict(message) for message in message_rows],
                "drafts": [row_dict(draft) for draft in drafts],
            }
        )
    return {"conversations": output}


@app.post("/api/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == principal.organization_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    enforce_patient_scope(principal, conversation.patient_id)
    recipient_is_patient = "patient" in principal.roles
    rows = (
        await session.scalars(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.organization_id == principal.organization_id,
                (
                    Message.sender_kind != "patient"
                    if recipient_is_patient
                    else Message.sender_kind == "patient"
                ),
            )
        )
    ).all()
    now = await domain_now(session, principal.organization_id)
    unread = [message for message in rows if message.read_at is None]
    for message in unread:
        message.read_at = now
    existing_receipts = [message.read_at for message in rows if message.read_at is not None]

    def as_utc(value: datetime) -> datetime:
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    # SQLite drops offsets on round-trip while the domain clock is offset-aware;
    # normalize before comparing so local and Neon execute the same contract.
    read_at = max((as_utc(value) for value in existing_receipts), default=as_utc(now))
    await session.commit()
    return {
        "conversation_id": conversation.id,
        "changed_count": len(unread),
        "read_at": read_at,
    }


async def _triage_patient_message(
    session: AsyncSession,
    *,
    principal: Principal,
    conversation: Conversation,
    message: Message,
) -> tuple[str, uuid.UUID | None]:
    if message.sender_kind != "patient":
        return "routine", None
    normalized = " ".join(message.body.lower().replace("’", "'").split())
    warning_terms = (
        "fever",
        "pus",
        "infected",
        "infection",
        "warmer",
        "increasing redness",
        "redder",
        "spreading redness",
        "worsening pain",
        "severe pain",
        "bleeding won't stop",
        "bleeding that won't stop",
        "bleeding does not stop",
        "cannot stop bleeding",
        "shortness of breath",
        "facial swelling",
        "hives",
        "allergic reaction",
    )
    if not any(term in normalized for term in warning_terms):
        return "routine", None
    task_id = uuid.uuid5(message.id, "staff-message-triage")
    task = await session.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.organization_id == principal.organization_id,
        )
    )
    if task is None:
        task = Task(
            id=task_id,
            organization_id=principal.organization_id,
            patient_id=conversation.patient_id,
            assigned_user_id=conversation.assigned_user_id,
            task_type="message_review",
            title="Review patient warning-sign message",
            description=message.body,
            priority="high",
            status="open",
            due_at=message.sent_at + timedelta(minutes=15),
        )
        session.add(task)
    draft_id = uuid.uuid5(message.id, "ai-staff-response-draft")
    existing_draft = await session.scalar(
        select(MessageDraft).where(
            MessageDraft.id == draft_id,
            MessageDraft.organization_id == principal.organization_id,
        )
    )
    if existing_draft is None:
        run, output = await run_ai(
            session,
            organization_id=principal.organization_id,
            capability="patient_message",
            context={"question": message.body, "uncertain": True},
            patient_id=conversation.patient_id,
            requested_by_user_id=principal.user_id,
        )
        session.add(
            MessageDraft(
                id=draft_id,
                organization_id=principal.organization_id,
                conversation_id=conversation.id,
                author_user_id=None,
                body=output.body,
                status="proposed",
                confidence=Decimal("0.700"),
                ai_run_id=run.id,
            )
        )
    return "staff_review", task.id


@app.post("/api/messages")
async def send_message(
    payload: MessageRequest,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.organization_id == principal.organization_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    enforce_patient_scope(principal, conversation.patient_id)
    sender_kind = (
        "patient"
        if "patient" in principal.roles
        else "provider"
        if "provider" in principal.roles
        else "staff"
    )
    message = Message(
        organization_id=principal.organization_id,
        conversation_id=conversation.id,
        sender_user_id=principal.user_id,
        sender_kind=sender_kind,
        body=payload.body,
        status="sent",
        sent_at=await domain_now(session, principal.organization_id),
    )
    session.add(message)
    conversation.last_message_at = message.sent_at
    await session.flush()
    await messaging_provider.deliver_message(session, message)
    triage, triage_task_id = await _triage_patient_message(
        session,
        principal=principal,
        conversation=conversation,
        message=message,
    )
    await session.commit()
    return {
        "message": row_dict(message),
        "triage": triage,
        "triage_task_id": triage_task_id,
    }


@app.post("/api/conversations/{conversation_id}/messages")
async def send_conversation_message(
    conversation_id: uuid.UUID,
    request: Request,
    principal: PatientCarePrincipal,
    session: Session,
) -> dict[str, Any]:
    data = await request.json()
    body = data.get("body") or data.get("message")
    if not isinstance(body, str) or not body.strip():
        raise HTTPException(status_code=422, detail="Message body is required")
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == principal.organization_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    enforce_patient_scope(principal, conversation.patient_id)
    draft_id = data.get("approve_ai_draft_id") or data.get("approveAiDraftId")
    draft = None
    if draft_id:
        if "patient" in principal.roles:
            raise HTTPException(status_code=403, detail="Patients cannot approve AI message drafts")
        try:
            parsed_draft_id = uuid.UUID(str(draft_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid AI draft ID") from exc
        draft = await session.scalar(
            select(MessageDraft).where(
                MessageDraft.id == parsed_draft_id,
                MessageDraft.conversation_id == conversation.id,
                MessageDraft.organization_id == principal.organization_id,
                MessageDraft.status == "proposed",
            )
        )
        if draft is None:
            raise HTTPException(status_code=409, detail="AI draft is not available for approval")
    sender_kind = (
        "patient"
        if "patient" in principal.roles
        else "provider"
        if "provider" in principal.roles
        else "staff"
    )
    message = Message(
        organization_id=principal.organization_id,
        conversation_id=conversation.id,
        sender_user_id=principal.user_id,
        sender_kind=sender_kind,
        body=body.strip(),
        status="sent",
        sent_at=await domain_now(session, principal.organization_id),
        ai_run_id=draft.ai_run_id if draft else None,
    )
    session.add(message)
    conversation.last_message_at = message.sent_at
    if draft:
        draft.status = "approved"
    await session.flush()
    await messaging_provider.deliver_message(session, message)
    if draft:
        session.add(
            ProvenanceRecord(
                organization_id=principal.organization_id,
                entity_type="message",
                entity_id=message.id,
                activity="human_approved_ai_draft",
                actor_user_id=principal.user_id,
                ai_run_id=draft.ai_run_id,
                source_entity_type="message_draft",
                source_entity_id=draft.id,
                detail_json={"editedBeforeSend": body.strip() != draft.body.strip()},
            )
        )
    triage, triage_task_id = await _triage_patient_message(
        session,
        principal=principal,
        conversation=conversation,
        message=message,
    )
    await session.commit()
    return {
        "message_id": message.id,
        "sent_at": message.sent_at,
        "status": message.status,
        "triage": triage,
        "triage_task_id": triage_task_id,
    }


@app.post("/api/messages/draft")
async def draft_message(
    payload: DraftMessageRequest,
    principal: ClinicalPrincipal,
    session: Session,
) -> dict[str, Any]:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.organization_id == principal.organization_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    now = await domain_now(session, principal.organization_id)
    uncertain = any(
        term in payload.question.lower()
        for term in ["fever", "pus", "severe", "won't stop", "cannot stop", "allergic"]
    )
    run, output = await run_ai(
        session,
        organization_id=principal.organization_id,
        capability="patient_message",
        context={"question": payload.question, "uncertain": uncertain},
        patient_id=conversation.patient_id,
        requested_by_user_id=principal.user_id,
    )
    draft = MessageDraft(
        organization_id=principal.organization_id,
        conversation_id=conversation.id,
        author_user_id=principal.user_id,
        body=output.body,
        status="proposed",
        confidence=Decimal("0.990") if not output.route_to_staff else Decimal("0.700"),
        ai_run_id=run.id,
    )
    session.add(draft)
    if output.route_to_staff:
        session.add(
            Task(
                organization_id=principal.organization_id,
                patient_id=conversation.patient_id,
                assigned_user_id=principal.user_id,
                task_type="message_review",
                title="Review uncertain patient question",
                description=payload.question,
                priority="high",
                status="open",
                due_at=now + timedelta(hours=2),
            )
        )
    await session.commit()
    return {
        "draft": row_dict(draft),
        "route_to_staff": output.route_to_staff,
        "source_instructions": output.source_instructions,
    }


@app.post("/api/message-drafts/{draft_id}/approve")
async def approve_message_draft(
    draft_id: uuid.UUID,
    payload: ApproveDraftRequest,
    principal: ClinicalPrincipal,
    session: Session,
) -> dict[str, Any]:
    draft = await session.scalar(
        select(MessageDraft).where(
            MessageDraft.id == draft_id,
            MessageDraft.organization_id == principal.organization_id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "proposed":
        raise HTTPException(status_code=409, detail="Draft is no longer awaiting approval")
    now = await domain_now(session, principal.organization_id)
    message = Message(
        organization_id=principal.organization_id,
        conversation_id=draft.conversation_id,
        sender_user_id=principal.user_id,
        sender_kind="provider" if "provider" in principal.roles else "staff",
        body=payload.body or draft.body,
        status="sent",
        sent_at=now,
        ai_run_id=draft.ai_run_id,
    )
    session.add(message)
    draft.status = "approved"
    await session.flush()
    await messaging_provider.deliver_message(session, message)
    session.add(
        ProvenanceRecord(
            organization_id=principal.organization_id,
            entity_type="message",
            entity_id=message.id,
            activity="human_approved_ai_draft",
            actor_user_id=principal.user_id,
            ai_run_id=draft.ai_run_id,
            source_entity_type="message_draft",
            source_entity_id=draft.id,
            detail_json={"editedBeforeSend": message.body.strip() != draft.body.strip()},
        )
    )
    await session.commit()
    return {"message": row_dict(message), "draft": row_dict(draft)}


@app.get("/api/rcm")
@app.get("/api/rcm/claims")
async def revenue_cycle(principal: BillerPrincipal, session: Session) -> dict[str, Any]:
    return await rcm_workspace(session, principal.organization_id)


@app.post("/api/rcm/claims/{claim_id}/advance")
async def advance_claim(
    claim_id: uuid.UUID,
    principal: BillerPrincipal,
    session: Session,
) -> dict[str, Any]:
    claim = await session.scalar(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.organization_id == principal.organization_id,
        )
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status == "denied":
        raise HTTPException(
            status_code=409, detail="Denied claim requires correction and resubmission"
        )
    await clearinghouse_provider.advance(session, claim)
    await set_demo_chapter(session, principal.organization_id, "rcm")
    await session.commit()
    return {"claim": row_dict(claim), "at": await domain_now(session, principal.organization_id)}


@app.post("/api/rcm/appeals")
async def create_appeal(
    payload: AppealRequest,
    principal: BillerPrincipal,
    session: Session,
) -> dict[str, Any]:
    denial = await session.scalar(
        select(Denial).where(
            Denial.id == payload.denial_id,
            Denial.organization_id == principal.organization_id,
        )
    )
    if denial is None:
        raise HTTPException(status_code=404, detail="Denial not found")
    existing = await session.scalar(
        select(Appeal).where(
            Appeal.denial_id == denial.id,
            Appeal.organization_id == principal.organization_id,
        )
    )
    if existing:
        return {"appeal": row_dict(existing)}
    _, recommendation = await run_ai(
        session,
        organization_id=principal.organization_id,
        capability="denial_recommendation",
        context={"reasonCode": denial.reason_code, "reason": denial.reason},
        patient_id=None,
        requested_by_user_id=principal.user_id,
    )
    appeal = Appeal(
        organization_id=principal.organization_id,
        denial_id=denial.id,
        author_user_id=principal.user_id,
        status="draft",
        appeal_text=payload.appeal_text or recommendation.appeal_draft,
        evidence_json=recommendation.evidence_needed,
        recovered_amount=Decimal("0.00"),
    )
    session.add(appeal)
    await session.commit()
    return {"appeal": row_dict(appeal), "recommendation": recommendation}


@app.post("/api/claims/{claim_id}/correct-and-resubmit")
async def correct_and_resubmit(
    claim_id: uuid.UUID,
    payload: ClaimResubmitRequest,
    principal: BillerPrincipal,
    session: Session,
) -> dict[str, Any]:
    claim = await session.scalar(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.organization_id == principal.organization_id,
        )
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    denial = await session.scalar(
        select(Denial).where(
            Denial.claim_id == claim.id,
            Denial.organization_id == principal.organization_id,
            Denial.status == "open",
        )
    )
    if denial is None:
        raise HTTPException(status_code=409, detail="Claim has no open denial")
    task_query = select(Task).where(
        Task.organization_id == principal.organization_id,
        Task.patient_id == claim.patient_id,
        Task.claim_id == claim.id,
        Task.denial_id == denial.id,
        Task.task_type == "denial_followup",
        Task.status != "completed",
    )
    if payload.source_task_id:
        task_query = task_query.where(Task.id == payload.source_task_id)
    task = await session.scalar(task_query)
    if payload.source_task_id and task is None:
        raise HTTPException(
            status_code=422, detail="Source denial task is not valid for this claim"
        )
    appeal = await session.scalar(
        select(Appeal).where(
            Appeal.denial_id == denial.id,
            Appeal.organization_id == principal.organization_id,
        )
    )
    now = await domain_now(session, principal.organization_id)
    denial_action = await session.scalar(
        select(ProposedAction).where(
            ProposedAction.organization_id == principal.organization_id,
            ProposedAction.entity_type == "denial",
            ProposedAction.entity_id == denial.id,
            ProposedAction.action_type == "resubmit_with_modifier_25",
        )
    )
    if denial_action is None or denial_action.status not in {"proposed", "approved"}:
        raise HTTPException(status_code=409, detail="Denial correction lacks an approvable action")
    existing_approval = await session.scalar(
        select(Approval).where(
            Approval.organization_id == principal.organization_id,
            Approval.proposed_action_id == denial_action.id,
            Approval.decision == "approved",
        )
    )
    if existing_approval is None:
        session.add(
            Approval(
                id=uuid.uuid5(denial_action.id, "biller-approved-resubmission"),
                organization_id=principal.organization_id,
                proposed_action_id=denial_action.id,
                reviewer_user_id=principal.user_id,
                decision="approved",
                comment=payload.correction,
                decided_at=now,
            )
        )
    denial_action.status = "approved"
    if appeal is None:
        appeal = Appeal(
            organization_id=principal.organization_id,
            denial_id=denial.id,
            author_user_id=principal.user_id,
            status="submitted",
            appeal_text=payload.appeal_body,
            evidence_json=["signed_encounter_note", "procedure_note", "remittance_advice"],
            submitted_at=now,
            recovered_amount=Decimal("0.00"),
        )
        session.add(appeal)
    else:
        appeal.author_user_id = principal.user_id
        appeal.appeal_text = payload.appeal_body
        appeal.status = "submitted"
        appeal.submitted_at = now
    lines = (
        await session.scalars(
            select(ClaimLine)
            .where(
                ClaimLine.claim_id == claim.id,
                ClaimLine.organization_id == principal.organization_id,
            )
            .order_by(ClaimLine.line_number)
        )
    ).all()
    evaluation_line = next((line for line in lines if line.procedure_code.startswith("99")), None)
    if evaluation_line and not evaluation_line.procedure_code.endswith("-25"):
        evaluation_line.procedure_code = f"{evaluation_line.procedure_code}-25"
    denial.status = "resolved"
    denial.resolved_at = now
    claim.status = "validated"
    await clearinghouse_provider.advance(session, claim)
    correction_event = ClaimEvent(
        organization_id=principal.organization_id,
        claim_id=claim.id,
        event_type="claim_corrected_and_resubmitted",
        from_status="denied",
        to_status=claim.status,
        occurred_at=claim.submitted_at or now,
        actor_kind="biller",
        detail_json={
            "denialId": str(denial.id),
            "appealId": str(appeal.id),
            "correction": payload.correction,
            "modifier": "25",
            "sourceTaskId": str(task.id) if task else None,
        },
    )
    session.add(correction_event)
    await session.flush()
    if task:
        task.status = "completed"
        task.completed_at = now
    session.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="claim_corrected_for_resubmission",
            entity_type="claim",
            entity_id=claim.id,
            patient_id=claim.patient_id,
            occurred_at=now,
            detail_json={
                "denialId": str(denial.id),
                "appealId": str(appeal.id),
                "claimEventId": str(correction_event.id),
                "modifier": "25",
            },
        )
    )
    await set_demo_chapter(session, principal.organization_id, "rcm")
    await session.flush()
    await session.commit()
    return {
        "claim_id": claim.id,
        "claim_event_id": correction_event.id,
        "status": claim.status,
        "submitted_at": claim.submitted_at,
        "assigned_task_id": task.id if task else None,
    }


@app.get("/api/mso/metrics")
async def mso_metrics(
    principal: Annotated[Principal, Depends(require_roles("mso_owner"))],
    session: Session,
) -> dict[str, Any]:
    return await calculate_mso_metrics(session, principal.organization_id)


@app.post("/api/ai/{capability}")
async def invoke_ai(
    capability: str,
    payload: AIRequest,
    principal: StaffPrincipal,
    session: Session,
) -> dict[str, Any]:
    if capability not in CAPABILITIES:
        raise HTTPException(status_code=404, detail="Unknown AI capability")
    clinical_capabilities = {
        "chart_summary",
        "ambient_note",
        "coding_suggestions",
        "patient_message",
        "pathology_summary",
        "document_extraction",
    }
    billing_capabilities = {"denial_recommendation", "document_extraction"}
    allowed = (
        clinical_capabilities
        if principal.roles & {"provider", "clinical_staff"}
        else billing_capabilities
        if "biller" in principal.roles
        else set()
    )
    if capability not in allowed:
        raise HTTPException(status_code=403, detail="AI capability is outside this role's scope")
    if len(json.dumps(payload.context, sort_keys=True, default=str).encode()) > 64_000:
        raise HTTPException(status_code=413, detail="AI context exceeds the 64 KB demo limit")
    patient_bound_capabilities = clinical_capabilities - {"document_extraction"}
    if capability in patient_bound_capabilities and payload.patient_id is None:
        raise HTTPException(status_code=422, detail="This AI capability requires a patient ID")
    if payload.patient_id:
        patient_exists = await session.scalar(
            select(Patient.id).where(
                Patient.id == payload.patient_id,
                Patient.organization_id == principal.organization_id,
            )
        )
        if not patient_exists:
            raise HTTPException(status_code=404, detail="Patient not found")
        if payload.patient_id != canonical_ids()["sarah_patient_id"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    "The generic demo AI harness is grounded only for canonical Sarah data; "
                    "use a resource-specific workflow endpoint for other patients"
                ),
            )
    run, output = await run_ai(
        session,
        organization_id=principal.organization_id,
        capability=capability,
        context=payload.context,
        patient_id=payload.patient_id,
        requested_by_user_id=principal.user_id,
        minimum_necessary=False,
    )
    await session.commit()
    return {
        "run": row_dict(run),
        "output": output.model_dump(mode="json", by_alias=True),
        "requires_approval": True,
    }


@app.get("/api/demo/bootstrap")
async def bootstrap(principal: CurrentPrincipal, session: Session) -> dict[str, Any]:
    return await demo_bootstrap(
        session,
        organization_id=principal.organization_id,
        session_payload=principal_payload(principal),
    )


@app.get("/api/presenter/health")
@app.get("/api/demo/health")
async def presenter_health(
    principal: PresenterPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    scenario = await get_demo_scenario(session, principal.organization_id)
    counts = {
        "patients": int(
            await session.scalar(
                select(func.count(Patient.id)).where(
                    Patient.organization_id == principal.organization_id
                )
            )
            or 0
        ),
        "appointments": int(
            await session.scalar(
                select(func.count(Appointment.id)).where(
                    Appointment.organization_id == principal.organization_id
                )
            )
            or 0
        ),
        "claims": int(
            await session.scalar(
                select(func.count(Claim.id)).where(
                    Claim.organization_id == principal.organization_id
                )
            )
            or 0
        ),
    }
    return {
        "status": "degraded" if scenario.fallback_indicator else "healthy",
        "scenario": row_dict(scenario),
        "counts": counts,
        "model_fallback": scenario.fallback_indicator,
        "runtime": runtime.execution_platform,
        "database": "sqlite_local" if runtime.is_sqlite else "neon_postgres",
        "ai_provider": (
            "openai"
            if runtime.openai_api_key
            else "local_deterministic_fallback"
        ),
    }


@app.post("/api/presenter/reset")
@app.post("/api/demo/reset")
async def reset_demo(
    presenter: PresenterPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if runtime.environment.lower() in {"production", "prod"} and not runtime.allow_demo_reset:
        raise HTTPException(
            status_code=403,
            detail="Production reset requires ALLOW_SYNTHETIC_DEMO_RESET=true",
        )
    ids = await reset_demo_database(session)
    return {"message": "Canonical synthetic scenario restored", "ids": ids, "at": utcnow()}


@app.post("/api/presenter/advance")
@app.post("/api/demo/advance-time")
async def advance_time(
    payload: AdvanceTimeRequest,
    presenter: PresenterPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    scenario = await advance_demo_time(
        session,
        organization_id=presenter.organization_id,
        actor_user_id=presenter.presenter_actor_id or presenter.user_id,
        days=payload.days,
        hours=payload.hours,
        chapter=payload.chapter,
        signature_secret=runtime.session_secret,
    )
    await session.commit()
    return {"message": "Demo time advanced", "scenario": scenario, "at": utcnow()}


@app.post("/api/presenter/triggers/pathology")
@app.post("/api/demo/triggers/pathology")
async def trigger_pathology(
    _payload: TriggerRequest,
    presenter: PresenterPrincipal,
    session: Session,
    runtime: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    existing = await session.scalar(
        select(DiagnosticResult.id)
        .join(
            Procedure,
            (Procedure.id == DiagnosticResult.procedure_id)
            & (Procedure.organization_id == presenter.organization_id),
        )
        .where(
            DiagnosticResult.organization_id == presenter.organization_id,
            Procedure.encounter_id == canonical_ids()["sarah_encounter_id"],
        )
    )
    result = await trigger_sarah_pathology(
        session,
        organization_id=presenter.organization_id,
        actor_user_id=presenter.presenter_actor_id or presenter.user_id,
        signature_secret=runtime.session_secret,
    )
    await session.commit()
    return {
        "message": (
            "Synthetic pathology result received"
            if existing is None
            else "Synthetic pathology result already existed"
        ),
        "created": existing is None,
        "result_id": result.id,
        "status": result.status,
        "result": row_dict(result),
        "at": await domain_now(session, presenter.organization_id),
    }


@app.post("/api/presenter/triggers/claim")
@app.post("/api/demo/triggers/claim-response")
async def trigger_claim_response(
    payload: TriggerRequest,
    presenter: PresenterPrincipal,
    session: Session,
) -> dict[str, Any]:
    try:
        claim_id = (
            uuid.UUID(payload.entity_id) if payload.entity_id else canonical_ids()["sarah_claim_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid claim ID") from exc
    claim = await session.scalar(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.organization_id == presenter.organization_id,
        )
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status == "denied":
        raise HTTPException(status_code=409, detail="Denied claim requires correction")
    from_status = claim.status
    await clearinghouse_provider.advance(session, claim)
    await set_demo_chapter(session, presenter.organization_id, "rcm")
    await session.commit()
    return {
        "message": f"Claim advanced to {claim.status}",
        "changed": claim.status != from_status,
        "claim_id": claim.id,
        "status": claim.status,
        "from_status": from_status,
        "to_status": claim.status,
        "claim": row_dict(claim),
        "at": await domain_now(session, presenter.organization_id),
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Ambrosia Health Domain API", "docs": "/api/docs", "health": "/api/health"}
