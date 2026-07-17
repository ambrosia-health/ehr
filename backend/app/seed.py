from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AIInput,
    AIOutput,
    AIRun,
    Allergy,
    Appeal,
    Appointment,
    AppointmentReminder,
    AuditEvent,
    AutomationPolicy,
    Claim,
    ClaimEvent,
    ClaimLine,
    ClaimResponse,
    ClinicalImage,
    CommunicationPreference,
    Consent,
    Conversation,
    Coverage,
    DemoScenario,
    DemoTimelineEvent,
    Denial,
    DiagnosticResult,
    EligibilityCheck,
    Encounter,
    EncounterNote,
    Estimate,
    FileRecord,
    IntegrationEvent,
    Lesion,
    LesionObservation,
    Location,
    Medication,
    Membership,
    Message,
    MessageDraft,
    NoteVersion,
    Notification,
    Order,
    Organization,
    Patient,
    PatientAccount,
    PatientBalance,
    PatientContact,
    Payment,
    Problem,
    Procedure,
    PromptVersion,
    ProposedAction,
    ProvenanceRecord,
    Provider,
    Questionnaire,
    QuestionnaireResponse,
    Role,
    Specimen,
    StaffProfile,
    Task,
    TaskComment,
    User,
    WorkflowEvent,
    WorkflowRun,
)
from .schemas import AI_OUTPUT_SCHEMAS

SEED_NAMESPACE = uuid.UUID("b9a2e333-797c-4581-8964-1d91e49e9e60")
DEMO_NOW = datetime(2026, 7, 16, 13, 0, tzinfo=UTC)
DEMO_ORG_SLUG = "ambrosia-dermatology"
_RESET_LOCK = asyncio.Lock()


def sid(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


COHORT_NAMES = [
    ("Noah", "Williams"),
    ("Olivia", "Bennett"),
    ("Ethan", "Kim"),
    ("Ava", "Thompson"),
    ("Mateo", "Rivera"),
    ("Sophia", "Nguyen"),
    ("Liam", "Foster"),
    ("Isabella", "Martinez"),
    ("James", "Walker"),
    ("Mia", "Anderson"),
    ("Benjamin", "Carter"),
    ("Amelia", "Brooks"),
    ("Lucas", "Reed"),
    ("Harper", "Morgan"),
    ("Henry", "Sullivan"),
    ("Evelyn", "Price"),
    ("Alexander", "Cooper"),
    ("Camila", "Flores"),
    ("Daniel", "Park"),
    ("Luna", "Richardson"),
    ("Michael", "Turner"),
    ("Sofia", "Ramirez"),
    ("Sebastian", "Wood"),
    ("Chloe", "Patel"),
    ("Jack", "Murphy"),
    ("Layla", "Evans"),
    ("Owen", "Bailey"),
    ("Nora", "Hughes"),
    ("Samuel", "Diaz"),
    ("Grace", "Chen"),
    ("Leo", "Washington"),
    ("Zoe", "Russell"),
    ("Julian", "Bell"),
    ("Lily", "Ortiz"),
    ("David", "Peterson"),
    ("Aria", "Gray"),
    ("Joseph", "James"),
    ("Hazel", "Watson"),
    ("Gabriel", "Sanders"),
    ("Violet", "Bryant"),
]


async def seed_database(session: AsyncSession, *, commit: bool = True) -> dict[str, uuid.UUID]:
    existing = await session.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    if existing is not None:
        if not existing.demo_mode:
            raise RuntimeError("Refusing to seed over a non-demo organization")
        return canonical_ids()

    role_descriptions = {
        "patient": "Patient portal access to the member's own chart and messages",
        "provider": "Clinical care, documentation, orders, and result review",
        "clinical_staff": "Intake, scheduling, tasks, and delegated clinical operations",
        "biller": "Claims, denials, appeals, payments, and balances",
        "mso_owner": "Organization-wide operational and financial oversight",
    }
    roles = {role.name: role for role in (await session.scalars(select(Role))).all()}
    for name, description in role_descriptions.items():
        if name not in roles:
            role = Role(id=sid(f"role:{name}"), name=name, description=description)
            roles[name] = role
            session.add(role)
    await session.flush()

    org = Organization(
        id=sid("org"),
        name="Ambrosia Dermatology Partners",
        slug=DEMO_ORG_SLUG,
        timezone="America/New_York",
        demo_mode=True,
    )
    locations = [
        Location(
            id=sid("location:midtown"),
            organization_id=org.id,
            name="Midtown Dermatology",
            address_line1="145 East 42nd Street, Suite 1200",
            city="New York",
            state="NY",
            postal_code="10017",
            phone="(212) 555-0148",
        ),
        Location(
            id=sid("location:brooklyn"),
            organization_id=org.id,
            name="Brooklyn Heights Dermatology",
            address_line1="88 Montague Street, Floor 4",
            city="Brooklyn",
            state="NY",
            postal_code="11201",
            phone="(718) 555-0182",
        ),
    ]
    session.add(org)
    await session.flush()
    session.add_all(locations)
    await session.flush()

    user_specs = [
        ("patient", "sarah.mitchell@example.test", "Sarah Mitchell", "patient", False),
        ("provider", "maya.chen@example.test", "Dr. Maya Chen", "provider", False),
        ("dr-elias-brooks", "elias.brooks@example.test", "Dr. Elias Brooks", "provider", False),
        ("dr-amara-okafor", "amara.okafor@example.test", "Dr. Amara Okafor", "provider", False),
        ("clinical", "jordan.lee@example.test", "Jordan Lee", "clinical_staff", False),
        ("alex-johnson", "alex.johnson@example.test", "Alex Johnson", "clinical_staff", False),
        ("biller", "priya.shah@example.test", "Priya Shah", "biller", False),
        ("owner", "alex.morgan@example.test", "Alex Morgan", "mso_owner", True),
    ]
    users: dict[str, User] = {}
    memberships: list[Membership] = []
    for key, email, display_name, role_name, presenter in user_specs:
        user = User(
            id=sid(f"user:{key}"),
            organization_id=org.id,
            email=email,
            display_name=display_name,
            persona_key=key
            if key in {"patient", "provider", "clinical", "biller", "owner"}
            else None,
            is_active=True,
            is_presenter=presenter,
        )
        users[key] = user
        session.add(user)
        memberships.append(
            Membership(
                id=sid(f"membership:{key}:{role_name}"),
                organization_id=org.id,
                user_id=user.id,
                role_id=roles[role_name].id,
                location_id=locations[0].id,
            )
        )
    await session.flush()
    session.add_all(memberships)
    await session.flush()

    providers = [
        Provider(
            id=sid("provider:maya"),
            organization_id=org.id,
            user_id=users["provider"].id,
            npi="0000000001",
            credentials="MD, FAAD",
            specialty="Medical and Surgical Dermatology",
        ),
        Provider(
            id=sid("provider:elias"),
            organization_id=org.id,
            user_id=users["dr-elias-brooks"].id,
            npi="0000000002",
            credentials="MD",
            specialty="Dermatologic Surgery",
        ),
        Provider(
            id=sid("provider:amara"),
            organization_id=org.id,
            user_id=users["dr-amara-okafor"].id,
            npi="0000000003",
            credentials="MD, FAAD",
            specialty="General Dermatology",
        ),
    ]
    session.add_all(providers)
    await session.flush()
    session.add_all(
        [
            StaffProfile(
                id=sid("staff:nina"),
                organization_id=org.id,
                user_id=users["clinical"].id,
                title="Clinical Coordinator",
                department="Clinical Operations",
            ),
            StaffProfile(
                id=sid("staff:alex"),
                organization_id=org.id,
                user_id=users["alex-johnson"].id,
                title="Patient Access Coordinator",
                department="Patient Access",
            ),
            StaffProfile(
                id=sid("staff:marcus"),
                organization_id=org.id,
                user_id=users["biller"].id,
                title="Revenue Cycle Specialist",
                department="Revenue Cycle",
            ),
            StaffProfile(
                id=sid("staff:elena"),
                organization_id=org.id,
                user_id=users["owner"].id,
                title="MSO Owner",
                department="Operations",
            ),
        ]
    )
    await session.flush()

    sarah = Patient(
        id=sid("patient:sarah"),
        organization_id=org.id,
        medical_record_number="AM-10482",
        first_name="Sarah",
        last_name="Mitchell",
        date_of_birth=date(1988, 4, 12),
        sex_at_birth="female",
        gender_identity="woman",
        pronouns="she/her",
        email="sarah.mitchell@example.test",
        phone="(917) 555-0146",
        status="active",
    )
    session.add(sarah)
    await session.flush()
    session.add(
        PatientAccount(
            id=sid("patient-account:sarah"),
            organization_id=org.id,
            user_id=users["patient"].id,
            patient_id=sarah.id,
            portal_status="active",
        )
    )
    session.add_all(
        [
            PatientContact(
                id=sid("contact:sarah:mobile"),
                organization_id=org.id,
                patient_id=sarah.id,
                kind="mobile",
                name="Sarah Mitchell",
                value=sarah.phone,
                is_primary=True,
            ),
            PatientContact(
                id=sid("contact:sarah:emergency"),
                organization_id=org.id,
                patient_id=sarah.id,
                kind="emergency",
                name="Daniel Mitchell",
                relationship="spouse",
                value="(917) 555-0191",
            ),
            PatientContact(
                id=sid("contact:sarah:pharmacy"),
                organization_id=org.id,
                patient_id=sarah.id,
                kind="pharmacy",
                name="Hudson Community Pharmacy",
                relationship=None,
                value="475 6th Avenue, New York, NY",
                is_primary=True,
            ),
        ]
    )
    sarah_coverage = Coverage(
        id=sid("coverage:sarah"),
        organization_id=org.id,
        patient_id=sarah.id,
        payer_name="Blue Horizon PPO",
        plan_name="Preferred PPO",
        member_id="BHP74209183",
        group_number="DERM2046",
        subscriber_name="Sarah Mitchell",
        relationship="self",
        effective_date=date(2026, 1, 1),
        status="active",
    )
    session.add(sarah_coverage)
    session.add_all(
        [
            Allergy(
                id=sid("allergy:sarah:adhesive"),
                organization_id=org.id,
                patient_id=sarah.id,
                substance="Adhesive tape",
                reaction="Localized contact dermatitis",
                severity="mild",
                status="active",
            ),
            Medication(
                id=sid("medication:sarah:sertraline"),
                organization_id=org.id,
                patient_id=sarah.id,
                name="Sertraline",
                dose="50 mg",
                frequency="once daily",
                prescriber="Dr. Helena Ortiz",
                status="active",
            ),
            Medication(
                id=sid("medication:sarah:levonorgestrel"),
                organization_id=org.id,
                patient_id=sarah.id,
                name="Levonorgestrel intrauterine device",
                dose="52 mg",
                frequency="in situ",
                prescriber="Dr. Helena Ortiz",
                status="active",
            ),
            Problem(
                id=sid("problem:sarah:family-history"),
                organization_id=org.id,
                patient_id=sarah.id,
                code="Z80.8",
                display="Family history of malignant neoplasm of other organs or systems",
                onset_date=date(2019, 6, 1),
                status="active",
            ),
            Problem(
                id=sid("problem:sarah:atypical-nevus"),
                organization_id=org.id,
                patient_id=sarah.id,
                code="Z86.018",
                display="History of mildly atypical nevus, right anterior thigh, excised 2022",
                onset_date=date(2022, 5, 12),
                status="active",
            ),
        ]
    )
    await session.flush()

    questionnaire = Questionnaire(
        id=sid("questionnaire:derm-intake"),
        organization_id=org.id,
        slug="new-lesion-intake",
        title="New or changing lesion intake",
        version="2026.1",
        schema_json={
            "sections": [
                "reasonForVisit",
                "lesionHistory",
                "symptoms",
                "medications",
                "allergies",
                "skinCancerHistory",
                "pharmacy",
                "insurance",
                "consents",
                "images",
            ]
        },
        is_active=True,
    )
    session.add(questionnaire)
    await session.flush()

    sarah_appt = Appointment(
        id=sid("appointment:sarah:hero"),
        organization_id=org.id,
        patient_id=sarah.id,
        provider_id=providers[0].id,
        location_id=locations[0].id,
        starts_at=DEMO_NOW + timedelta(hours=1, minutes=30),
        duration_minutes=30,
        visit_type="New lesion evaluation",
        reason="Changing mole on left posterior shoulder",
        status="checked_in",
        readiness_status="ready",
        booked_at=DEMO_NOW - timedelta(days=3),
        checked_in_at=DEMO_NOW + timedelta(hours=1, minutes=15),
    )
    sarah_encounter = Encounter(
        id=sid("encounter:sarah:hero"),
        organization_id=org.id,
        appointment_id=sarah_appt.id,
        patient_id=sarah.id,
        provider_id=providers[0].id,
        status="in_progress",
        started_at=DEMO_NOW + timedelta(hours=1, minutes=32),
        chief_complaint="Changing mole on left posterior shoulder",
        ambient_transcript="The mole has slowly enlarged and become darker over four months. It occasionally itches but has not bled. Exam shows a seven by five millimeter asymmetric pigmented papule with an irregular border.",
    )
    session.add(sarah_appt)
    await session.flush()
    session.add(sarah_encounter)
    await session.flush()
    session.add(
        QuestionnaireResponse(
            id=sid("questionnaire-response:sarah"),
            organization_id=org.id,
            questionnaire_id=questionnaire.id,
            patient_id=sarah.id,
            appointment_id=sarah_appt.id,
            status="completed",
            response_json={
                "reasonForVisit": "Changing mole on left posterior shoulder",
                "firstNoticed": "3–6 months ago",
                "lesionHistory": "Changing during the last 3–6 months",
                "symptoms": ["Itching"],
                "changes": ["Wider or larger", "Darker color"],
                "urgentSigns": [],
                "medications": [
                    "Sertraline 50 mg once daily",
                    "Levonorgestrel intrauterine device 52 mg in situ",
                ],
                "allergies": ["Adhesive tape — Localized contact dermatitis"],
                "personalSkinCancerHistory": "None",
                "familySkinCancerHistory": "Father treated for melanoma at age 61",
                "pharmacy": "Hudson Community Pharmacy, 475 6th Avenue",
            },
            completed_at=DEMO_NOW - timedelta(days=2),
        )
    )
    session.add_all(
        [
            Consent(
                id=sid("consent:sarah:privacy"),
                organization_id=org.id,
                patient_id=sarah.id,
                encounter_id=sarah_encounter.id,
                consent_type="privacy_and_treatment",
                version="2026.1",
                accepted_at=DEMO_NOW - timedelta(days=2),
                accepted_by_name="Sarah Mitchell",
                signature_text="Sarah Mitchell",
            ),
            Consent(
                id=sid("consent:sarah:biopsy"),
                organization_id=org.id,
                patient_id=sarah.id,
                encounter_id=sarah_encounter.id,
                consent_type="shave_biopsy",
                version="2026.1",
                accepted_at=DEMO_NOW + timedelta(hours=1, minutes=42),
                accepted_by_name="Sarah Mitchell",
                signature_text="Sarah Mitchell",
            ),
        ]
    )

    eligibility = EligibilityCheck(
        id=sid("eligibility:sarah"),
        organization_id=org.id,
        patient_id=sarah.id,
        coverage_id=sarah_coverage.id,
        appointment_id=sarah_appt.id,
        status="active",
        requested_at=DEMO_NOW - timedelta(days=3),
        responded_at=DEMO_NOW - timedelta(days=3),
        deductible_remaining=Decimal("420.00"),
        copay=Decimal("45.00"),
        coinsurance_percent=Decimal("20.00"),
        response_json={"networkStatus": "in_network", "priorAuthorizationRequired": False},
    )
    estimate = Estimate(
        id=sid("estimate:sarah"),
        organization_id=org.id,
        patient_id=sarah.id,
        appointment_id=sarah_appt.id,
        eligibility_check_id=eligibility.id,
        total_charge=Decimal("395.00"),
        expected_plan_payment=Decimal("310.00"),
        patient_responsibility=Decimal("85.00"),
        status="accepted",
        disclaimer="This good-faith estimate may change based on services performed and payer adjudication.",
    )
    session.add(eligibility)
    await session.flush()
    session.add(estimate)
    await session.flush()

    lesion = Lesion(
        id=sid("lesion:sarah:left-shoulder"),
        organization_id=org.id,
        patient_id=sarah.id,
        label="Left posterior shoulder lesion",
        anatomical_location="left posterior shoulder",
        body_map_x=Decimal("29.00"),
        body_map_y=Decimal("26.00"),
        body_map_view="posterior",
        first_noted_at=date(2025, 1, 10),
        status="biopsy_recommended",
    )
    observations = [
        LesionObservation(
            id=sid("lesion-observation:sarah:prior"),
            organization_id=org.id,
            lesion_id=lesion.id,
            observed_at=DEMO_NOW - timedelta(days=120),
            length_mm=Decimal("5.0"),
            width_mm=Decimal("4.5"),
            morphology="flat pigmented macule",
            border="mostly regular",
            pigmentation="medium brown",
            change_over_time="baseline patient photograph",
            symptoms="none",
            source="patient",
        ),
        LesionObservation(
            id=sid("lesion-observation:sarah:current"),
            organization_id=org.id,
            lesion_id=lesion.id,
            encounter_id=sarah_encounter.id,
            observed_at=DEMO_NOW + timedelta(hours=1, minutes=38),
            length_mm=Decimal("7.0"),
            width_mm=Decimal("5.0"),
            morphology="asymmetric pigmented papule",
            border="irregular and focally notched",
            pigmentation="variegated brown to black",
            change_over_time="increased by approximately 2 mm and darkened over four months",
            symptoms="intermittent mild pruritus; no bleeding or pain",
            assessment="Neoplasm of uncertain behavior; rule out dysplastic nevus versus melanoma",
            source="clinician",
        ),
    ]
    session.add(lesion)
    await session.flush()
    session.add_all(observations)
    await session.flush()
    stable_calf_lesion = Lesion(
        id=sid("lesion:sarah:left-calf"),
        organization_id=org.id,
        patient_id=sarah.id,
        label="Stable left lateral calf nevus",
        anatomical_location="left lateral calf",
        body_map_x=Decimal("38.00"),
        body_map_y=Decimal("77.00"),
        body_map_view="posterior",
        first_noted_at=date(2024, 6, 10),
        status="monitoring",
    )
    excised_thigh_lesion = Lesion(
        id=sid("lesion:sarah:right-thigh"),
        organization_id=org.id,
        patient_id=sarah.id,
        label="Excised right anterior thigh nevus",
        anatomical_location="right anterior thigh",
        body_map_x=Decimal("61.00"),
        body_map_y=Decimal("63.00"),
        body_map_view="anterior",
        first_noted_at=date(2022, 4, 20),
        status="excised",
    )
    session.add_all([stable_calf_lesion, excised_thigh_lesion])
    await session.flush()
    session.add_all(
        [
            LesionObservation(
                id=sid("lesion-observation:sarah:left-calf"),
                organization_id=org.id,
                lesion_id=stable_calf_lesion.id,
                observed_at=DEMO_NOW - timedelta(days=30),
                length_mm=Decimal("4.0"),
                width_mm=Decimal("3.0"),
                morphology="symmetric brown macule",
                border="smooth and regular",
                pigmentation="uniform medium brown",
                change_over_time="unchanged for two years",
                symptoms="none",
                assessment="Benign-appearing melanocytic nevus; continue monitoring",
                source="clinician",
            ),
            LesionObservation(
                id=sid("lesion-observation:sarah:right-thigh:2022"),
                organization_id=org.id,
                lesion_id=excised_thigh_lesion.id,
                observed_at=datetime(2022, 5, 12, 14, 20, tzinfo=UTC),
                length_mm=Decimal("6.0"),
                width_mm=Decimal("4.0"),
                morphology="asymmetric brown macule",
                border="mildly irregular",
                pigmentation="two-tone brown",
                change_over_time="removed in 2022; no pigment recurrence",
                symptoms="none",
                assessment="Mildly atypical compound nevus, completely excised",
                source="clinician",
            ),
        ]
    )
    await session.flush()

    prior_time = datetime(2022, 5, 12, 14, 0, tzinfo=UTC)
    prior_appointment = Appointment(
        id=sid("appointment:sarah:2022-nevus"),
        organization_id=org.id,
        patient_id=sarah.id,
        provider_id=providers[0].id,
        location_id=locations[0].id,
        starts_at=prior_time,
        duration_minutes=30,
        visit_type="Excision",
        reason="Atypical nevus, right anterior thigh",
        status="completed",
        readiness_status="ready",
        booked_at=prior_time - timedelta(days=14),
        checked_in_at=prior_time - timedelta(minutes=9),
    )
    session.add(prior_appointment)
    await session.flush()
    prior_encounter = Encounter(
        id=sid("encounter:sarah:2022-nevus"),
        organization_id=org.id,
        appointment_id=prior_appointment.id,
        patient_id=sarah.id,
        provider_id=providers[0].id,
        status="completed",
        started_at=prior_time,
        completed_at=prior_time + timedelta(minutes=28),
        chief_complaint="Excision of atypical nevus, right anterior thigh",
    )
    session.add(prior_encounter)
    await session.flush()
    prior_note_text = "Excision of the right anterior thigh atypical nevus was completed with layered closure. Final pathology showed mild atypia with clear margins."
    prior_note = EncounterNote(
        id=sid("note:sarah:2022-nevus"),
        organization_id=org.id,
        encounter_id=prior_encounter.id,
        author_user_id=users["provider"].id,
        status="signed",
        content=prior_note_text,
        structured_content={
            "assessment": "Mildly atypical nevus",
            "plan": "Completely excised; routine surveillance",
        },
        current_version=1,
        signed_at=prior_encounter.completed_at + timedelta(minutes=16),
        signed_by_user_id=users["provider"].id,
        signature_hash=content_hash(f"signed:{prior_note_text}:2022-05-12"),
    )
    session.add(prior_note)
    await session.flush()
    session.add(
        NoteVersion(
            id=sid("note-version:sarah:2022-nevus:1"),
            organization_id=org.id,
            note_id=prior_note.id,
            version_number=1,
            author_user_id=users["provider"].id,
            content=prior_note_text,
            structured_content=prior_note.structured_content,
            content_hash=content_hash(prior_note_text),
            reason="Signed operative note",
        )
    )
    prior_procedure = Procedure(
        id=sid("procedure:sarah:2022-nevus"),
        organization_id=org.id,
        encounter_id=prior_encounter.id,
        patient_id=sarah.id,
        lesion_id=excised_thigh_lesion.id,
        provider_id=providers[0].id,
        code="11402",
        display="Excision, benign lesion, trunk/arms/legs, 1.1 to 2.0 cm",
        performed_at=prior_time + timedelta(minutes=8),
        documentation="Elliptical excision with layered closure after informed consent.",
        status="completed",
    )
    prior_order = Order(
        id=sid("order:sarah:2022-nevus"),
        organization_id=org.id,
        encounter_id=prior_encounter.id,
        patient_id=sarah.id,
        lesion_id=excised_thigh_lesion.id,
        ordering_provider_id=providers[0].id,
        order_type="surgical_pathology",
        code="DERMPATH",
        display="Dermatopathology examination",
        status="resulted",
        ordered_at=prior_time + timedelta(minutes=10),
    )
    session.add_all([prior_procedure, prior_order])
    await session.flush()
    prior_specimen = Specimen(
        id=sid("specimen:sarah:2022-nevus"),
        organization_id=org.id,
        order_id=prior_order.id,
        procedure_id=prior_procedure.id,
        patient_id=sarah.id,
        lesion_id=excised_thigh_lesion.id,
        accession_number="SYN-DP-220512-019",
        specimen_type="excision",
        body_site="right anterior thigh",
        collected_at=prior_time + timedelta(minutes=10),
        status="resulted",
    )
    session.add(prior_specimen)
    await session.flush()
    session.add(
        DiagnosticResult(
            id=sid("diagnostic-result:sarah:2022-nevus"),
            organization_id=org.id,
            order_id=prior_order.id,
            specimen_id=prior_specimen.id,
            patient_id=sarah.id,
            lesion_id=excised_thigh_lesion.id,
            procedure_id=prior_procedure.id,
            clinician_id=providers[0].id,
            result_type="surgical_pathology",
            status="final",
            diagnosis="Compound melanocytic nevus with mild atypia; margins clear",
            narrative="Mild architectural disorder and cytologic atypia. No melanoma. Examined margins are free.",
            summary="Mildly atypical compound nevus, completely excised.",
            resulted_at=prior_time + timedelta(days=4),
            reviewed_at=prior_time + timedelta(days=4, hours=2),
            reviewed_by_user_id=users["provider"].id,
            patient_notified_at=prior_time + timedelta(days=4, hours=3),
        )
    )
    await session.flush()
    files = [
        FileRecord(
            id=sid("file:sarah:overview"),
            organization_id=org.id,
            patient_id=sarah.id,
            storage_provider="vercel",
            storage_key="synthetic/sarah-left-posterior-shoulder.png",
            public_demo_url="/images/clinical/sarah-left-posterior-shoulder.png",
            filename="sarah-left-posterior-shoulder.png",
            content_type="image/png",
            byte_size=2_838_119,
            sha256="69c0f5c4ad9a7d5db96fda92ae463c006c276c618db77e7e2776f3cf152c7900",
            classification="synthetic_clinical_image",
        ),
        FileRecord(
            id=sid("file:sarah:dermoscopy"),
            organization_id=org.id,
            patient_id=sarah.id,
            storage_provider="vercel",
            storage_key="synthetic/sarah-left-posterior-shoulder-dermoscopy.png",
            public_demo_url="/images/clinical/sarah-left-posterior-shoulder-dermoscopy.png",
            filename="sarah-left-posterior-shoulder-dermoscopy.png",
            content_type="image/png",
            byte_size=2_074_246,
            sha256="065a4a12e675fd4a1fddd6896f6f8068d19f3fc50d45bc784834f30a76e6b04a",
            classification="synthetic_clinical_image",
        ),
    ]
    session.add_all(files)
    await session.flush()
    session.add_all(
        [
            ClinicalImage(
                id=sid("clinical-image:sarah:overview"),
                organization_id=org.id,
                patient_id=sarah.id,
                lesion_id=lesion.id,
                encounter_id=sarah_encounter.id,
                file_record_id=files[0].id,
                captured_at=DEMO_NOW - timedelta(days=2),
                anatomical_location="left posterior shoulder",
                view="overview",
                is_patient_submitted=True,
            ),
            ClinicalImage(
                id=sid("clinical-image:sarah:dermoscopy"),
                organization_id=org.id,
                patient_id=sarah.id,
                lesion_id=lesion.id,
                encounter_id=sarah_encounter.id,
                file_record_id=files[1].id,
                captured_at=DEMO_NOW + timedelta(hours=1, minutes=39),
                anatomical_location="left posterior shoulder",
                view="dermoscopy",
                is_patient_submitted=False,
            ),
        ]
    )
    await session.flush()

    for capability, schema in AI_OUTPUT_SCHEMAS.items():
        session.add(
            PromptVersion(
                id=sid(f"prompt:{capability}:2026.1"),
                organization_id=org.id,
                capability=capability,
                version="2026.1",
                template=f"Ambrosia {capability} prompt. Use minimum necessary context and return schema-valid JSON.",
                output_schema_json=schema.model_json_schema(),
                active=True,
            )
        )

    # Predetermined foreign keys intentionally avoid ORM relationships; stage parents explicitly.
    await session.flush()

    previsit_run = AIRun(
        id=sid("ai-run:sarah:previsit"),
        organization_id=org.id,
        capability="chart_summary",
        prompt_version_id=sid("prompt:chart_summary:2026.1"),
        patient_id=sarah.id,
        requested_by_user_id=users["provider"].id,
        provider="deterministic_fallback",
        model="ambrosia-fixture-2026.1",
        status="completed",
        fallback_used=True,
        started_at=DEMO_NOW - timedelta(hours=2),
        completed_at=DEMO_NOW - timedelta(hours=2),
        latency_ms=2,
        error_message="Modal inference unavailable during canonical seed",
    )
    summary_json = {
        "headline": "Changing pigmented lesion on the left posterior shoulder",
        "activeConcerns": ["Enlarging", "Darker pigmentation", "Intermittent itching"],
        "relevantHistory": ["Father diagnosed with melanoma at 61", "No personal skin cancer"],
        "readinessFlags": ["Intake complete", "Eligibility active", "Images available"],
        "suggestedFocus": ["Dermoscopy", "Compare image history", "Discuss biopsy"],
    }
    session.add(previsit_run)
    await session.flush()
    session.add_all(
        [
            AIInput(
                id=sid("ai-input:sarah:previsit"),
                organization_id=org.id,
                ai_run_id=previsit_run.id,
                input_type="minimum_necessary_context",
                content_json={"patientId": str(sarah.id), "appointmentId": str(sarah_appt.id)},
                content_hash=content_hash(f"{sarah.id}:{sarah_appt.id}"),
                minimum_necessary=True,
            ),
            AIOutput(
                id=sid("ai-output:sarah:previsit"),
                organization_id=org.id,
                ai_run_id=previsit_run.id,
                output_type="chart_summary",
                content_json=summary_json,
                schema_valid=True,
                confidence=Decimal("0.990"),
            ),
        ]
    )
    await session.flush()

    async def add_seeded_ai_run(
        *,
        key: str,
        capability: str,
        context: dict,
        output: dict,
        started_at: datetime,
    ) -> AIRun:
        validated = AI_OUTPUT_SCHEMAS[capability].model_validate(output)
        run = AIRun(
            id=sid(f"ai-run:sarah:{key}"),
            organization_id=org.id,
            capability=capability,
            prompt_version_id=sid(f"prompt:{capability}:2026.1"),
            patient_id=sarah.id,
            requested_by_user_id=users["provider"].id,
            provider="deterministic_fallback",
            model="ambrosia-fixture-2026.1",
            status="completed",
            fallback_used=True,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=2,
            error_message="Modal inference unavailable during canonical seed",
        )
        session.add(run)
        session.add_all(
            [
                AIInput(
                    id=sid(f"ai-input:sarah:{key}"),
                    organization_id=org.id,
                    ai_run_id=run.id,
                    input_type="minimum_necessary_context",
                    content_json=context,
                    content_hash=content_hash(repr(sorted(context.items()))),
                    minimum_necessary=True,
                ),
                AIOutput(
                    id=sid(f"ai-output:sarah:{key}"),
                    organization_id=org.id,
                    ai_run_id=run.id,
                    output_type=capability,
                    content_json=validated.model_dump(mode="json", by_alias=True),
                    schema_valid=True,
                    confidence=Decimal("0.990"),
                ),
            ]
        )
        return run

    ambient_run = await add_seeded_ai_run(
        key="ambient-note",
        capability="ambient_note",
        context={
            "encounterId": str(sarah_encounter.id),
            "transcript": sarah_encounter.ambient_transcript,
        },
        output={
            "subjective": "Changing lesion for four months with enlargement, darkening, and intermittent itching; no bleeding or pain.",
            "objective": "Left posterior shoulder: 7 x 5 mm asymmetric pigmented papule with an irregular border and variegated pigmentation.",
            "assessment": [
                {
                    "code": "D48.5",
                    "display": "Neoplasm of uncertain behavior of skin",
                    "detail": "Rule out dysplastic nevus versus melanoma",
                }
            ],
            "plan": [
                "Recommend shave biopsy after informed consent",
                "Send specimen for surgical pathology",
                "Provide approved wound care instructions",
            ],
            "procedureProposal": {
                "type": "shave_biopsy",
                "cpt": "11102",
                "site": "left posterior shoulder",
            },
        },
        started_at=DEMO_NOW - timedelta(minutes=10),
    )
    coding_run = await add_seeded_ai_run(
        key="coding",
        capability="coding_suggestions",
        context={"encounterId": str(sarah_encounter.id), "noteId": str(sid("note:sarah:hero"))},
        output={
            "suggestions": [
                {
                    "code": "D48.5",
                    "system": "ICD-10-CM",
                    "display": "Neoplasm of uncertain behavior of skin",
                    "rationale": "Diagnosis remains uncertain pending pathology.",
                    "confidence": 0.97,
                },
                {
                    "code": "11102",
                    "system": "CPT",
                    "display": "Tangential biopsy of skin, single lesion",
                    "rationale": "The proposed procedure is a shave biopsy of one lesion.",
                    "confidence": 0.96,
                },
            ],
            "documentationGaps": [],
        },
        started_at=DEMO_NOW - timedelta(minutes=9),
    )
    aftercare_body = (
        "Your visit summary and shave-biopsy aftercare are ready. Keep the site covered with "
        "petrolatum and a clean bandage, and contact us for spreading redness, worsening pain, "
        "fever, pus, or bleeding that does not stop with firm pressure. Pathology usually returns "
        "within 3–5 business days."
    )
    aftercare_run = await add_seeded_ai_run(
        key="aftercare-message",
        capability="patient_message",
        context={
            "encounterId": str(sarah_encounter.id),
            "instructionVersion": "shave-biopsy-aftercare-2026.1",
        },
        output={
            "body": aftercare_body,
            "sourceInstructions": ["Approved shave-biopsy aftercare v2026.1"],
            "routeToStaff": False,
            "uncertaintyReason": None,
        },
        started_at=DEMO_NOW - timedelta(minutes=8),
    )
    shower_reply_body = (
        "Yes. You may shower tomorrow. Let clean water run over the site, pat it dry, then "
        "apply a thin layer of petrolatum and a fresh bandage. Avoid soaking or swimming "
        "until the skin has closed."
    )
    shower_reply_run = await add_seeded_ai_run(
        key="shower-reply",
        capability="patient_message",
        context={
            "conversationId": str(sid("conversation:sarah:biopsy")),
            "question": "If you biopsy it today, can I shower tomorrow morning?",
        },
        output={
            "body": shower_reply_body,
            "sourceInstructions": ["Approved shave-biopsy aftercare v2026.1"],
            "routeToStaff": False,
            "uncertaintyReason": None,
        },
        started_at=DEMO_NOW - timedelta(minutes=7),
    )
    seeded_ai_runs = [row for row in session.new if isinstance(row, AIRun)]
    await session.flush(seeded_ai_runs)
    seeded_ai_context = [row for row in session.new if isinstance(row, (AIInput, AIOutput))]
    await session.flush(seeded_ai_context)
    note_content = (
        "Subjective: Changing lesion on the left posterior shoulder, larger and darker over four months "
        "with occasional itching; no pain or bleeding.\n\nObjective: 7 x 5 mm asymmetric brown-black "
        "papule with irregular border and variegated pigmentation.\n\nAssessment: Neoplasm of uncertain "
        "behavior of skin (D48.5).\n\nPlan: Recommend shave biopsy, surgical pathology, wound care, "
        "and result notification."
    )
    note = EncounterNote(
        id=sid("note:sarah:hero"),
        organization_id=org.id,
        encounter_id=sarah_encounter.id,
        author_user_id=users["provider"].id,
        status="proposed",
        content=note_content,
        structured_content={
            "subjective": "Changing lesion for four months",
            "objective": "7 x 5 mm asymmetric pigmented papule",
            "assessment": [{"code": "D48.5", "display": "Neoplasm of uncertain behavior of skin"}],
            "plan": ["Shave biopsy", "Surgical pathology", "Aftercare"],
        },
        current_version=1,
        ai_run_id=ambient_run.id,
    )
    session.add(note)
    await session.flush()
    session.add(
        NoteVersion(
            id=sid("note-version:sarah:1"),
            organization_id=org.id,
            note_id=note.id,
            version_number=1,
            author_user_id=users["provider"].id,
            content=note_content,
            structured_content=note.structured_content,
            content_hash=content_hash(note_content),
            reason="AI-assisted draft reviewed in encounter workspace",
        )
    )
    action_specs = [
        ("sign_note", "encounter_note", note.id, {"noteId": str(note.id)}),
        (
            "confirm_biopsy_consent",
            "encounter",
            sarah_encounter.id,
            {"consentType": "shave_biopsy", "consentId": str(sid("consent:sarah:biopsy"))},
        ),
        (
            "create_shave_biopsy",
            "encounter",
            sarah_encounter.id,
            {"cpt": "11102", "site": "left posterior shoulder", "lesionId": str(lesion.id)},
        ),
        (
            "create_pathology_order",
            "encounter",
            sarah_encounter.id,
            {"testCode": "DERMPATH", "lesionId": str(lesion.id)},
        ),
        (
            "create_specimen",
            "encounter",
            sarah_encounter.id,
            {"type": "shave biopsy", "site": "left posterior shoulder"},
        ),
        (
            "apply_coding",
            "encounter",
            sarah_encounter.id,
            {"diagnosis": "D48.5", "procedure": "11102"},
        ),
        (
            "send_aftercare",
            "encounter",
            sarah_encounter.id,
            {
                "template": "shave-biopsy-aftercare-2026.1",
                "draftId": str(sid("message-draft:sarah:aftercare")),
            },
        ),
        (
            "create_pathology_task",
            "encounter",
            sarah_encounter.id,
            {"dueDays": 5, "escalation": "unreviewed_or_unnotified"},
        ),
    ]
    action_run = {
        "apply_coding": coding_run.id,
        "send_aftercare": aftercare_run.id,
    }
    for kind, entity_type, entity_id, payload in action_specs:
        session.add(
            ProposedAction(
                id=sid(f"proposed-action:sarah:{kind}"),
                organization_id=org.id,
                ai_run_id=action_run.get(kind, ambient_run.id),
                patient_id=sarah.id,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=kind,
                payload_json=payload,
                rationale="Generated from approved encounter context; clinician review required.",
                status="proposed",
                requires_approval=True,
            )
        )
    await session.flush()

    sarah_conversation = Conversation(
        id=sid("conversation:sarah:biopsy"),
        organization_id=org.id,
        patient_id=sarah.id,
        subject="Shoulder biopsy and aftercare",
        channel="secure_message",
        status="open",
        assigned_user_id=users["clinical"].id,
        last_message_at=DEMO_NOW - timedelta(minutes=35),
    )
    session.add(sarah_conversation)
    await session.flush()
    session.add_all(
        [
            Message(
                id=sid("message:sarah:confirmation"),
                organization_id=org.id,
                conversation_id=sarah_conversation.id,
                sender_user_id=users["clinical"].id,
                sender_kind="staff",
                body="You are confirmed with Dr. Chen today at 10:30 AM. Please arrive 15 minutes early. We received your intake and shoulder photos.",
                status="read",
                sent_at=DEMO_NOW - timedelta(days=1),
                read_at=DEMO_NOW - timedelta(days=1, minutes=-8),
            ),
            Message(
                id=sid("message:sarah:question"),
                organization_id=org.id,
                conversation_id=sarah_conversation.id,
                sender_user_id=users["patient"].id,
                sender_kind="patient",
                body="If you biopsy it today, can I shower tomorrow morning?",
                status="sent",
                sent_at=DEMO_NOW - timedelta(minutes=35),
            ),
            MessageDraft(
                id=sid("message-draft:sarah:aftercare"),
                organization_id=org.id,
                conversation_id=sarah_conversation.id,
                author_user_id=users["clinical"].id,
                body=aftercare_body,
                status="proposed",
                confidence=Decimal("0.970"),
                ai_run_id=aftercare_run.id,
            ),
            MessageDraft(
                id=sid("message-draft:sarah:shower-reply"),
                organization_id=org.id,
                conversation_id=sarah_conversation.id,
                author_user_id=users["clinical"].id,
                body=shower_reply_body,
                status="proposed",
                confidence=Decimal("0.980"),
                ai_run_id=shower_reply_run.id,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            CommunicationPreference(
                id=sid("communication-preference:sarah:sms"),
                organization_id=org.id,
                patient_id=sarah.id,
                channel="sms",
                enabled=True,
                destination=sarah.phone,
                consented_at=DEMO_NOW - timedelta(days=3),
            ),
            CommunicationPreference(
                id=sid("communication-preference:sarah:portal"),
                organization_id=org.id,
                patient_id=sarah.id,
                channel="secure_message",
                enabled=True,
                destination=sarah.email,
                consented_at=DEMO_NOW - timedelta(days=3),
            ),
            AppointmentReminder(
                id=sid("reminder:sarah"),
                organization_id=org.id,
                appointment_id=sarah_appt.id,
                channel="sms",
                scheduled_for=DEMO_NOW - timedelta(days=1),
                sent_at=DEMO_NOW - timedelta(days=1),
                delivery_status="delivered",
                provider_message_id="sim-reminder-sarah-hero",
            ),
        ]
    )

    workflow = WorkflowRun(
        id=sid("workflow:sarah:biopsy"),
        organization_id=org.id,
        workflow_type="biopsy_completion",
        entity_type="encounter",
        entity_id=sarah_encounter.id,
        status="awaiting_approval",
        idempotency_key=f"biopsy-completion:{sarah_encounter.id}",
        input_json={
            "proposedActionIds": [
                str(sid(f"proposed-action:sarah:{item[0]}")) for item in action_specs
            ]
        },
        output_json={},
        started_at=DEMO_NOW + timedelta(hours=1, minutes=45),
    )
    session.add(workflow)
    await session.flush()
    session.add(
        WorkflowEvent(
            id=sid("workflow-event:sarah:proposals-ready"),
            organization_id=org.id,
            workflow_run_id=workflow.id,
            event_type="proposals_ready",
            sequence=1,
            payload_json={"count": len(action_specs), "requiresApproval": True},
        )
    )
    session.add(
        AutomationPolicy(
            id=sid("automation-policy:pathology-followup"),
            organization_id=org.id,
            name="Pathology result safety net",
            event_type="pathology_result_received",
            conditions_json={"resultStatus": "final"},
            actions_json=[
                {"action": "create_clinician_task", "dueHours": 24},
                {"action": "draft_patient_message"},
                {"action": "escalate_if_unreviewed", "afterHours": 48},
            ],
            enabled=True,
            requires_approval=True,
        )
    )
    session.add(
        AutomationPolicy(
            id=sid("automation-policy:metric-assumptions"),
            organization_id=org.id,
            name="MSO metric time assumptions 2026.1",
            event_type="metric_assumptions",
            conditions_json={
                "version": "2026.1",
                "aiRunMinutesAvoided": 8,
                "deliveredReminderMinutesAvoided": 3,
                "metricTargets": {
                    "conversion": 75,
                    "noshow": 8,
                    "response": 4,
                    "sign": 30,
                    "path_open": 0,
                    "path_closure": 24,
                    "accept": 95,
                    "denial": 5,
                    "ar": 30,
                    "revenue": 250,
                    "doc": 30,
                    "avoided": 300,
                    "satisfaction": 90,
                },
            },
            actions_json=[],
            enabled=True,
            requires_approval=False,
        )
    )
    session.add(
        AutomationPolicy(
            id=sid("automation-policy:scheduling-template"),
            organization_id=org.id,
            name="Standard provider availability",
            event_type="schedule_availability",
            conditions_json={"timezone": "America/New_York", "minimumLeadMinutes": 30},
            actions_json=[
                {
                    "weekdays": [0, 1, 2, 3, 4],
                    "start": "09:00",
                    "end": "17:00",
                    "slotMinutes": 30,
                }
            ],
            enabled=True,
            requires_approval=False,
        )
    )
    session.add_all(
        [
            Task(
                id=sid("task:sarah:review-complete"),
                organization_id=org.id,
                patient_id=sarah.id,
                encounter_id=sarah_encounter.id,
                assigned_user_id=users["provider"].id,
                task_type="unsigned_note",
                title="Review and complete Sarah Mitchell's encounter",
                description="Review the AI-proposed note, shave biopsy, pathology order, coding, and aftercare actions.",
                priority="high",
                status="open",
                due_at=DEMO_NOW + timedelta(hours=3),
            ),
            Notification(
                id=sid("notification:maya:sarah-ready"),
                organization_id=org.id,
                user_id=users["provider"].id,
                title="Sarah Mitchell is ready",
                body="Intake, eligibility, and two lesion images are available.",
                kind="patient_ready",
                entity_type="appointment",
                entity_id=sarah_appt.id,
            ),
        ]
    )

    session.add(
        PatientBalance(
            id=sid("patient-balance:sarah"),
            organization_id=org.id,
            patient_id=sarah.id,
            current_balance=Decimal("0.00"),
            status="current",
        )
    )
    await session.flush()

    scenario = DemoScenario(
        id=sid("demo-scenario:sarah"),
        organization_id=org.id,
        slug="sarah-mitchell-journey",
        name="Sarah Mitchell: changing lesion to revenue recovery",
        description="A deterministic, fully synthetic dermatology journey spanning patient access, clinical care, pathology, RCM, and MSO analytics.",
        current_time=DEMO_NOW,
        current_chapter="patient_initiation",
        fallback_indicator=True,
        active=True,
    )
    session.add(scenario)
    await session.flush()
    timeline_specs = [
        (1, "patient_initiation", "appointment_booked", DEMO_NOW - timedelta(days=3)),
        (2, "command_center", "intake_completed", DEMO_NOW - timedelta(days=2)),
        (3, "encounter", "encounter_started", DEMO_NOW + timedelta(hours=1, minutes=32)),
        (4, "pathology", "pathology_result_arrives", DEMO_NOW + timedelta(days=3)),
        (5, "rcm", "claim_accepted", DEMO_NOW + timedelta(days=5)),
        (6, "rcm", "claim_adjudicated", DEMO_NOW + timedelta(days=12)),
        (7, "rcm", "claim_paid", DEMO_NOW + timedelta(days=18)),
    ]
    for sequence, chapter, event_type, scheduled_for in timeline_specs:
        session.add(
            DemoTimelineEvent(
                id=sid(f"demo-timeline:{sequence}"),
                organization_id=org.id,
                demo_scenario_id=scenario.id,
                sequence=sequence,
                chapter=chapter,
                event_type=event_type,
                scheduled_for=scheduled_for,
                status="completed" if scheduled_for <= DEMO_NOW else "pending",
                executed_at=scheduled_for if scheduled_for <= DEMO_NOW else None,
                payload_json={"patientId": str(sarah.id)},
            )
        )
    session.add_all(
        [
            ProvenanceRecord(
                id=sid("provenance:sarah:ambient-note"),
                organization_id=org.id,
                entity_type="encounter_note",
                entity_id=note.id,
                activity="ai_draft_created",
                actor_user_id=users["provider"].id,
                ai_run_id=ambient_run.id,
                source_entity_type="encounter",
                source_entity_id=sarah_encounter.id,
                recorded_at=DEMO_NOW - timedelta(hours=2),
                detail_json={"humanApprovalRequired": True, "fallbackUsed": True},
            ),
            AuditEvent(
                id=sid("audit:sarah:chart-opened"),
                organization_id=org.id,
                actor_user_id=users["provider"].id,
                action="chart_opened",
                entity_type="patient",
                entity_id=sarah.id,
                patient_id=sarah.id,
                occurred_at=DEMO_NOW - timedelta(minutes=12),
                request_id="seed-sarah-chart-opened",
                detail_json={"purpose": "treatment"},
            ),
            AuditEvent(
                id=sid("audit:sarah:qualified-initiation"),
                organization_id=org.id,
                actor_user_id=users["patient"].id,
                action="patient_concern_qualified",
                entity_type="patient_initiation",
                entity_id=sid("initiation:sarah"),
                patient_id=sarah.id,
                occurred_at=DEMO_NOW - timedelta(days=3, minutes=20),
                request_id="seed-sarah-qualified-initiation",
                detail_json={"appointmentId": str(sarah_appt.id), "source": "digital_intake"},
            ),
            IntegrationEvent(
                id=sid("integration:sarah:eligibility"),
                organization_id=org.id,
                provider="simulated_payer",
                direction="inbound",
                event_type="eligibility_response",
                entity_type="eligibility_check",
                entity_id=eligibility.id,
                idempotency_key="seed:eligibility:sarah",
                payload_json=eligibility.response_json,
                status="processed",
                occurred_at=DEMO_NOW - timedelta(days=3),
            ),
        ]
    )
    # Clear the hero graph before cohort batching so every pending object below
    # belongs to one of the explicit dependency stages.
    await session.flush()

    # A coherent longitudinal cohort drives every dashboard metric; no metric constants are seeded.
    first_denial: Denial | None = None
    first_denied_claim: Claim | None = None
    first_pathology: DiagnosticResult | None = None
    for index, (first_name, last_name) in enumerate(COHORT_NAMES, start=1):
        patient = Patient(
            id=sid(f"patient:cohort:{index}"),
            organization_id=org.id,
            medical_record_number=f"ADP-{2200 + index:07d}",
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date(1950 + (index * 7) % 51, 1 + index % 12, 1 + (index * 3) % 27),
            sex_at_birth="female" if index % 2 == 0 else "male",
            gender_identity="woman" if index % 2 == 0 else "man",
            pronouns="she/her" if index % 2 == 0 else "he/him",
            email=f"{first_name.lower()}.{last_name.lower()}@example.test",
            phone=f"(646) 555-{1000 + index:04d}",
            status="active",
        )
        coverage = Coverage(
            id=sid(f"coverage:cohort:{index}"),
            organization_id=org.id,
            patient_id=patient.id,
            payer_name=["Blue Horizon PPO", "MetroCare Health", "Empire Community Plan"][index % 3],
            plan_name=["Choice Plus", "Gold EPO", "Community PPO"][index % 3],
            member_id=f"SYN{index:08d}",
            group_number=f"GRP{100 + index % 7}",
            subscriber_name=f"{first_name} {last_name}",
            relationship="self",
            effective_date=date(2026, 1, 1),
            status="active",
        )
        provider = providers[index % len(providers)]
        starts_at = DEMO_NOW - timedelta(days=index * 2, hours=index % 5)
        status = "no_show" if index % 13 == 0 else "cancelled" if index % 17 == 0 else "completed"
        appointment = Appointment(
            id=sid(f"appointment:cohort:{index}"),
            organization_id=org.id,
            patient_id=patient.id,
            provider_id=provider.id,
            location_id=locations[index % 2].id,
            starts_at=starts_at,
            duration_minutes=30,
            visit_type=["Full skin examination", "Acne follow-up", "Lesion evaluation"][index % 3],
            reason=["Annual skin cancer screening", "Acne treatment follow-up", "Spot of concern"][
                index % 3
            ],
            status=status,
            readiness_status="ready" if status == "completed" else "not_started",
            booked_at=starts_at - timedelta(days=8 + index % 6),
            checked_in_at=starts_at - timedelta(minutes=8) if status == "completed" else None,
        )
        session.add(patient)
        session.add_all([coverage, appointment])
        session.add(
            AuditEvent(
                id=sid(f"audit:cohort:{index}:qualified-initiation"),
                organization_id=org.id,
                actor_user_id=None,
                action="patient_concern_qualified",
                entity_type="patient_initiation",
                entity_id=sid(f"initiation:cohort:{index}"),
                patient_id=patient.id,
                occurred_at=appointment.booked_at - timedelta(minutes=15),
                request_id=f"seed-qualified-{index}",
                detail_json={"appointmentId": str(appointment.id), "source": "phone_or_web"},
            )
        )
        session.add(
            PatientContact(
                id=sid(f"contact:cohort:{index}"),
                organization_id=org.id,
                patient_id=patient.id,
                kind="mobile",
                name=f"{first_name} {last_name}",
                value=patient.phone,
                is_primary=True,
            )
        )
        if index % 2 == 0:
            cohort_lesion = Lesion(
                id=sid(f"lesion:cohort:{index}"),
                organization_id=org.id,
                patient_id=patient.id,
                label=f"{['Right forearm', 'Upper back', 'Left cheek'][index % 3]} lesion",
                anatomical_location=["right dorsal forearm", "upper back", "left cheek"][index % 3],
                body_map_x=Decimal(str(20 + index % 60)),
                body_map_y=Decimal(str(20 + index % 55)),
                body_map_view="anterior" if index % 3 != 1 else "posterior",
                first_noted_at=(starts_at - timedelta(days=240)).date(),
                status="monitoring",
            )
            session.add(cohort_lesion)
            session.add(
                LesionObservation(
                    id=sid(f"lesion-observation:cohort:{index}"),
                    organization_id=org.id,
                    lesion_id=cohort_lesion.id,
                    observed_at=starts_at,
                    length_mm=Decimal(str(3 + index % 6)),
                    width_mm=Decimal(str(2 + index % 5)),
                    morphology=["tan macule", "stuck-on papule", "pink scaly plaque"][index % 3],
                    border="regular",
                    pigmentation="uniform",
                    change_over_time="stable by patient report",
                    symptoms="none",
                    assessment=["benign nevus", "seborrheic keratosis", "actinic keratosis"][
                        index % 3
                    ],
                    source="clinician",
                )
            )
        if status != "completed":
            session.add(
                PatientBalance(
                    id=sid(f"patient-balance:cohort:{index}"),
                    organization_id=org.id,
                    patient_id=patient.id,
                    current_balance=Decimal("0.00"),
                    status="current",
                )
            )
            continue

        completed_at = starts_at + timedelta(minutes=24 + index % 17)
        encounter = Encounter(
            id=sid(f"encounter:cohort:{index}"),
            organization_id=org.id,
            appointment_id=appointment.id,
            patient_id=patient.id,
            provider_id=provider.id,
            status="completed",
            started_at=starts_at,
            completed_at=completed_at,
            chief_complaint=appointment.reason,
        )
        signed_at = completed_at + timedelta(minutes=18 + (index % 6) * 11)
        cohort_note_content = f"Completed dermatology visit for {appointment.reason.lower()}. Findings and plan reviewed with the patient."
        cohort_note = EncounterNote(
            id=sid(f"note:cohort:{index}"),
            organization_id=org.id,
            encounter_id=encounter.id,
            author_user_id=[users["provider"], users["dr-elias-brooks"], users["dr-amara-okafor"]][
                index % 3
            ].id,
            status="signed",
            content=cohort_note_content,
            structured_content={"assessment": appointment.reason, "plan": "Follow up as directed"},
            current_version=1,
            signed_at=signed_at,
            signed_by_user_id=provider.user_id,
            signature_hash=content_hash(
                f"{sid(f'note:cohort:{index}')}:{cohort_note_content}:{signed_at.isoformat()}"
            ),
        )
        session.add(encounter)
        session.add(cohort_note)
        session.add(
            NoteVersion(
                id=sid(f"note-version:cohort:{index}:1"),
                organization_id=org.id,
                note_id=cohort_note.id,
                version_number=1,
                author_user_id=provider.user_id,
                content=cohort_note_content,
                structured_content=cohort_note.structured_content,
                content_hash=content_hash(cohort_note_content),
                reason="Signed encounter documentation",
            )
        )
        claim_status = (
            "denied"
            if index % 9 == 0
            else "submitted"
            if index % 5 == 0
            else "accepted"
            if index % 4 == 0
            else "adjudicated"
            if index % 3 == 0
            else "paid"
        )
        charge = Decimal(210 + (index % 5) * 35)
        allowed = (
            (charge * Decimal("0.72")).quantize(Decimal("0.01"))
            if claim_status in {"adjudicated", "paid", "denied"}
            else Decimal("0.00")
        )
        patient_resp = (
            Decimal("45.00") if claim_status in {"adjudicated", "paid"} else Decimal("0.00")
        )
        paid = allowed - patient_resp if claim_status == "paid" else Decimal("0.00")
        claim = Claim(
            id=sid(f"claim:cohort:{index}"),
            organization_id=org.id,
            claim_number=f"ADP-26-{50000 + index}",
            patient_id=patient.id,
            encounter_id=encounter.id,
            coverage_id=coverage.id,
            billing_provider_id=provider.id,
            status=claim_status,
            total_charge=charge,
            allowed_amount=allowed,
            paid_amount=paid,
            patient_responsibility=patient_resp,
            submitted_at=completed_at + timedelta(days=1),
            adjudicated_at=completed_at + timedelta(days=12)
            if claim_status in {"adjudicated", "paid", "denied"}
            else None,
            paid_at=completed_at + timedelta(days=18) if claim_status == "paid" else None,
        )
        session.add(claim)
        session.add_all(
            [
                ClaimLine(
                    id=sid(f"claim-line:cohort:{index}:1"),
                    organization_id=org.id,
                    claim_id=claim.id,
                    line_number=1,
                    procedure_code=["99213", "99214", "17000"][index % 3],
                    diagnosis_codes=[["Z12.83"], ["L70.0"], ["L57.0"]][index % 3],
                    units=1,
                    charge_amount=charge,
                    allowed_amount=allowed,
                    paid_amount=paid,
                ),
                ClaimEvent(
                    id=sid(f"claim-event:cohort:{index}:created"),
                    organization_id=org.id,
                    claim_id=claim.id,
                    event_type="claim_created",
                    from_status=None,
                    to_status="draft",
                    occurred_at=completed_at,
                    actor_kind="workflow",
                    detail_json={},
                ),
                ClaimEvent(
                    id=sid(f"claim-event:cohort:{index}:current"),
                    organization_id=org.id,
                    claim_id=claim.id,
                    event_type=f"claim_{claim_status}",
                    from_status="submitted" if claim_status != "submitted" else "validated",
                    to_status=claim_status,
                    occurred_at=completed_at
                    + timedelta(
                        days=12 if claim_status in {"adjudicated", "paid", "denied"} else 2
                    ),
                    actor_kind="simulated_clearinghouse",
                    detail_json={"deterministic": True},
                ),
                ClaimResponse(
                    id=sid(f"claim-response:cohort:{index}"),
                    organization_id=org.id,
                    claim_id=claim.id,
                    response_type="remittance"
                    if claim_status in {"paid", "denied"}
                    else "acknowledgement",
                    status_code=claim_status.upper(),
                    received_at=completed_at + timedelta(days=12),
                    payload_json={"claimNumber": claim.claim_number, "status": claim_status},
                    provider="simulated_clearinghouse",
                ),
            ]
        )
        balance_value = patient_resp if claim_status in {"adjudicated", "paid"} else Decimal("0.00")
        session.add(
            PatientBalance(
                id=sid(f"patient-balance:cohort:{index}"),
                organization_id=org.id,
                patient_id=patient.id,
                current_balance=balance_value,
                last_statement_at=DEMO_NOW - timedelta(days=3) if balance_value else None,
                last_payment_at=claim.paid_at,
                status="due" if balance_value else "current",
            )
        )
        if claim_status == "paid":
            session.add(
                Payment(
                    id=sid(f"payment:cohort:{index}:payer"),
                    organization_id=org.id,
                    claim_id=claim.id,
                    patient_id=patient.id,
                    source="payer",
                    amount=paid,
                    payment_method="835 electronic remittance",
                    reference=f"SIM-ERA-{50000 + index}",
                    status="settled",
                    received_at=claim.paid_at,
                )
            )
        if claim_status == "denied":
            denial = Denial(
                id=sid(f"denial:cohort:{index}"),
                organization_id=org.id,
                claim_id=claim.id,
                category="modifier/documentation",
                reason_code="CO-97",
                reason="Payment included in another service; separately identifiable E/M modifier missing.",
                denied_amount=charge,
                status="open" if first_denial is None else "resolved",
                denied_at=claim.adjudicated_at,
                resolved_at=None
                if first_denial is None
                else claim.adjudicated_at + timedelta(days=8),
            )
            session.add(denial)
            if first_denial is None:
                first_denial = denial
                first_denied_claim = claim

        if index <= 8:
            conversation = Conversation(
                id=sid(f"conversation:cohort:{index}"),
                organization_id=org.id,
                patient_id=patient.id,
                subject=["Prescription refill", "Rash follow-up", "Appointment question"][
                    index % 3
                ],
                channel="secure_message",
                status="open" if index % 3 == 0 else "closed",
                assigned_user_id=users["clinical"].id,
                last_message_at=starts_at + timedelta(days=2),
            )
            session.add(conversation)
            session.add(
                Message(
                    id=sid(f"message:cohort:{index}"),
                    organization_id=org.id,
                    conversation_id=conversation.id,
                    sender_user_id=None,
                    sender_kind="patient",
                    body=[
                        "Could you send the refill to the pharmacy already listed in my chart?",
                        "The redness is improving, but should I continue the cream for another week?",
                        "May I move my follow-up to a Friday afternoon?",
                    ][index % 3],
                    status="read" if index % 3 else "sent",
                    sent_at=starts_at + timedelta(days=2),
                    read_at=starts_at + timedelta(days=2, minutes=24) if index % 3 else None,
                )
            )

        # A prior pathology chain supplies a real unreviewed safety-queue item.
        if index == 2:
            pathology_lesion = sid(f"lesion:cohort:{index}")
            procedure = Procedure(
                id=sid("procedure:cohort:pathology"),
                organization_id=org.id,
                encounter_id=encounter.id,
                patient_id=patient.id,
                lesion_id=pathology_lesion,
                provider_id=provider.id,
                code="11102",
                display="Tangential biopsy of skin, single lesion",
                performed_at=completed_at - timedelta(minutes=8),
                documentation="Shave biopsy performed after informed consent; hemostasis achieved.",
                status="completed",
            )
            order = Order(
                id=sid("order:cohort:pathology"),
                organization_id=org.id,
                encounter_id=encounter.id,
                patient_id=patient.id,
                lesion_id=pathology_lesion,
                ordering_provider_id=provider.id,
                order_type="surgical_pathology",
                code="DERMPATH",
                display="Dermatopathology examination",
                status="resulted",
                ordered_at=completed_at,
            )
            specimen = Specimen(
                id=sid("specimen:cohort:pathology"),
                organization_id=org.id,
                order_id=order.id,
                procedure_id=procedure.id,
                patient_id=patient.id,
                lesion_id=pathology_lesion,
                accession_number="SYN-DP-260702-014",
                specimen_type="shave biopsy",
                body_site="left cheek",
                collected_at=completed_at,
                status="resulted",
            )
            first_pathology = DiagnosticResult(
                id=sid("diagnostic-result:cohort:pathology"),
                organization_id=org.id,
                order_id=order.id,
                specimen_id=specimen.id,
                patient_id=patient.id,
                lesion_id=pathology_lesion,
                procedure_id=procedure.id,
                clinician_id=provider.id,
                result_type="surgical_pathology",
                status="final",
                diagnosis="Basal cell carcinoma, nodular type, involving the deep margin",
                narrative="Sections show a nodular proliferation of atypical basaloid cells with peripheral palisading. Tumor extends to the deep tissue edge.",
                summary="Nodular basal cell carcinoma; treatment planning required.",
                resulted_at=DEMO_NOW - timedelta(hours=9),
            )
            session.add_all([procedure, order])
            session.add(specimen)
            session.add(first_pathology)
            session.add(
                Task(
                    id=uuid.uuid5(first_pathology.id, "review-task"),
                    organization_id=org.id,
                    patient_id=patient.id,
                    encounter_id=encounter.id,
                    assigned_user_id=provider.user_id,
                    task_type="pathology_review",
                    title=f"Review pathology for {first_name} {last_name}",
                    description="Final pathology indicates basal cell carcinoma and requires treatment planning.",
                    priority="high",
                    status="open",
                    due_at=DEMO_NOW + timedelta(hours=15),
                )
            )

    # IDs are deterministic UUIDs, so cohort rows can be flushed once per FK
    # layer instead of once per patient. This keeps remote Postgres seeding to
    # a fixed number of round trips as the cohort grows.
    cohort_flush_stages = (
        (Patient,),
        (Coverage, Appointment, AuditEvent, PatientContact, Lesion),
        (LesionObservation, PatientBalance, Encounter, Conversation),
        (EncounterNote, Claim, Message, Procedure, Order),
        (NoteVersion, ClaimLine, ClaimEvent, ClaimResponse, Payment, Denial, Specimen),
        (DiagnosticResult, Task),
    )
    for stage_types in cohort_flush_stages:
        stage_rows = [row for row in session.new if isinstance(row, stage_types)]
        if stage_rows:
            await session.flush(stage_rows)
    if session.new:
        unhandled = ", ".join(sorted({type(row).__name__ for row in session.new}))
        raise RuntimeError(f"Unbatched cohort seed models: {unhandled}")

    if first_denial is not None and first_denied_claim is not None:
        appeal_text = (
            "The separately identifiable evaluation addressed a new changing lesion and resulted in the "
            "decision to perform biopsy. The attached signed evaluation and procedure documentation support "
            "payment of the E/M service with modifier 25."
        )
        appeal = Appeal(
            id=sid("appeal:canonical-denial"),
            organization_id=org.id,
            denial_id=first_denial.id,
            author_user_id=users["biller"].id,
            status="draft",
            appeal_text=appeal_text,
            evidence_json=["signed_encounter_note", "procedure_note", "remittance_advice"],
            recovered_amount=Decimal("0.00"),
        )
        denial_action = ProposedAction(
            id=sid("proposed-action:canonical-denial"),
            organization_id=org.id,
            patient_id=first_denied_claim.patient_id,
            entity_type="denial",
            entity_id=first_denial.id,
            action_type="resubmit_with_modifier_25",
            payload_json={"appealId": str(appeal.id), "modifier": "25"},
            rationale="Signed documentation supports a separately identifiable evaluation.",
            status="proposed",
            requires_approval=True,
        )
        session.add_all([appeal, denial_action])
        denial_task = Task(
            id=sid("task:canonical-denial"),
            organization_id=org.id,
            patient_id=first_denied_claim.patient_id,
            encounter_id=first_denied_claim.encounter_id,
            claim_id=first_denied_claim.id,
            denial_id=first_denial.id,
            assigned_user_id=users["biller"].id,
            task_type="denial_followup",
            title=f"Correct and resubmit {first_denied_claim.claim_number}",
            description="Append modifier 25, attach the signed note, and submit the drafted appeal.",
            priority="high",
            status="in_progress",
            due_at=DEMO_NOW + timedelta(days=1),
        )
        session.add(denial_task)
        await session.flush()
        session.add(
            TaskComment(
                id=sid("task-comment:canonical-denial"),
                organization_id=org.id,
                task_id=denial_task.id,
                author_user_id=users["biller"].id,
                body="The signed encounter and procedure notes are attached to the appeal packet.",
            )
        )

    for index in range(1, 11):
        session.add(
            AuditEvent(
                id=sid(f"audit:unconverted-initiation:{index}"),
                organization_id=org.id,
                actor_user_id=None,
                action="patient_concern_qualified",
                entity_type="patient_initiation",
                entity_id=sid(f"initiation:unconverted:{index}"),
                patient_id=None,
                occurred_at=DEMO_NOW - timedelta(days=index),
                request_id=f"seed-unconverted-{index}",
                detail_json={"appointmentId": None, "source": "digital_intake"},
            )
        )

    if first_pathology is None:
        raise RuntimeError("Canonical pathology record was not created")
    await session.flush()
    if commit:
        await session.commit()
    return canonical_ids()


def canonical_ids() -> dict[str, uuid.UUID]:
    return {
        "organization_id": sid("org"),
        "sarah_patient_id": sid("patient:sarah"),
        "sarah_appointment_id": sid("appointment:sarah:hero"),
        "sarah_encounter_id": sid("encounter:sarah:hero"),
        "sarah_note_id": sid("note:sarah:hero"),
        "sarah_lesion_id": sid("lesion:sarah:left-shoulder"),
        "sarah_claim_id": sid("claim:sarah"),
        "sarah_conversation_id": sid("conversation:sarah:biopsy"),
        "scenario_id": sid("demo-scenario:sarah"),
    }


async def reset_demo_database(session: AsyncSession) -> dict[str, uuid.UUID]:
    async with _RESET_LOCK:
        try:
            bind = session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_key)"),
                    {"lock_key": 6_366_812_619_011_845_174},
                )
            organization = await session.scalar(
                select(Organization)
                .where(Organization.slug == DEMO_ORG_SLUG)
                .with_for_update()
            )
            if organization is not None and not organization.demo_mode:
                raise RuntimeError("Refusing to reset a non-demo organization")
            if organization is not None:
                await session.execute(delete(Organization).where(Organization.id == organization.id))
                await session.flush()
                session.expunge_all()
            ids = await seed_database(session, commit=False)
            await session.commit()
            return ids
        except Exception:
            await session.rollback()
            raise
