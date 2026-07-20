from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


LEARNING_JSON = JSON().with_variant(JSONB(), "postgresql")


class RecordMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OptimisticVersionMixin:
    """Opt-in SQLAlchemy optimistic concurrency for mutable records."""

    record_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.record_version}


class TenantMixin:
    @declared_attr
    def organization_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
        )


# Identity and organizations


class Organization(RecordMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)


class Location(TenantMixin, RecordMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    name: Mapped[str] = mapped_column(String(160))
    address_line1: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    postal_code: Mapped[str] = mapped_column(String(12))
    phone: Mapped[str] = mapped_column(String(32))


class Role(RecordMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(240))


class User(TenantMixin, RecordMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email"),)

    email: Mapped[str] = mapped_column(String(254), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    persona_key: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_presenter: Mapped[bool] = mapped_column(Boolean, default=False)


class Membership(TenantMixin, RecordMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )


class Provider(TenantMixin, RecordMixin, Base):
    __tablename__ = "providers"
    __table_args__ = (UniqueConstraint("organization_id", "npi"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    npi: Mapped[str] = mapped_column(String(10), index=True)
    credentials: Mapped[str] = mapped_column(String(64))
    specialty: Mapped[str] = mapped_column(String(120), default="Dermatology")
    accepting_new_patients: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffProfile(TenantMixin, RecordMixin, Base):
    __tablename__ = "staff_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    title: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120))


class PatientAccount(TenantMixin, RecordMixin, Base):
    __tablename__ = "patient_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_patient_accounts_org_user"),
        UniqueConstraint("organization_id", "patient_id", name="uq_patient_accounts_org_patient"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    portal_status: Mapped[str] = mapped_column(String(32), default="active")


# Clinical


class Patient(TenantMixin, RecordMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("organization_id", "medical_record_number"),
        Index("ix_patients_org_name", "organization_id", "last_name", "first_name"),
    )

    medical_record_number: Mapped[str] = mapped_column(String(32), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    date_of_birth: Mapped[date] = mapped_column(Date)
    sex_at_birth: Mapped[str] = mapped_column(String(32))
    gender_identity: Mapped[str | None] = mapped_column(String(64))
    pronouns: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(32))
    preferred_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)


class PatientContact(TenantMixin, RecordMixin, Base):
    __tablename__ = "patient_contacts"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    relationship: Mapped[str | None] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(String(254))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class Coverage(TenantMixin, RecordMixin, Base):
    __tablename__ = "coverages"
    __table_args__ = (UniqueConstraint("organization_id", "member_id", "payer_name"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    payer_name: Mapped[str] = mapped_column(String(160), index=True)
    plan_name: Mapped[str] = mapped_column(String(160))
    member_id: Mapped[str] = mapped_column(String(80))
    group_number: Mapped[str | None] = mapped_column(String(80))
    subscriber_name: Mapped[str] = mapped_column(String(160))
    relationship: Mapped[str] = mapped_column(String(40), default="self")
    effective_date: Mapped[date] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)


class Allergy(TenantMixin, RecordMixin, Base):
    __tablename__ = "allergies"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    substance: Mapped[str] = mapped_column(String(160))
    reaction: Mapped[str] = mapped_column(String(240))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="active")


class Medication(TenantMixin, RecordMixin, Base):
    __tablename__ = "medications"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    dose: Mapped[str | None] = mapped_column(String(80))
    frequency: Mapped[str | None] = mapped_column(String(80))
    prescriber: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="active")


class Problem(TenantMixin, RecordMixin, Base):
    __tablename__ = "problems"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(24), index=True)
    code_system: Mapped[str] = mapped_column(String(32), default="ICD-10-CM")
    display: Mapped[str] = mapped_column(String(240))
    onset_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active")


class Appointment(TenantMixin, RecordMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="positive_duration"),
        UniqueConstraint("organization_id", "provider_id", "starts_at"),
        Index("ix_appointments_org_start", "organization_id", "starts_at"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    visit_type: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="booked", index=True)
    readiness_status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Encounter(TenantMixin, RecordMixin, Base):
    __tablename__ = "encounters"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="RESTRICT"), unique=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chief_complaint: Mapped[str] = mapped_column(String(500))
    ambient_transcript: Mapped[str | None] = mapped_column(Text)


class EncounterNote(TenantMixin, RecordMixin, Base):
    __tablename__ = "encounter_notes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','proposed','signed','amended')", name="valid_note_status"
        ),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    note_type: Mapped[str] = mapped_column(String(40), default="progress_note")
    content: Mapped[str] = mapped_column(Text, default="")
    structured_content: Mapped[dict] = mapped_column(JSON, default=dict)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    signature_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL")
    )


class NoteVersion(TenantMixin, RecordMixin, Base):
    __tablename__ = "note_versions"
    __table_args__ = (UniqueConstraint("note_id", "version_number"),)

    note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounter_notes.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    content: Mapped[str] = mapped_column(Text)
    structured_content: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(240), default="Initial version")


class NoteAmendment(TenantMixin, RecordMixin, Base):
    __tablename__ = "note_amendments"

    note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounter_notes.id", ondelete="RESTRICT"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(String(500))
    amendment_text: Mapped[str] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    signature_hash: Mapped[str] = mapped_column(String(64), unique=True)


class Lesion(TenantMixin, RecordMixin, Base):
    __tablename__ = "lesions"
    __table_args__ = (UniqueConstraint("organization_id", "patient_id", "label"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    anatomical_location: Mapped[str] = mapped_column(String(160), index=True)
    body_map_x: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    body_map_y: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    body_map_view: Mapped[str] = mapped_column(String(16), default="posterior")
    first_noted_at: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="monitoring", index=True)


class LesionObservation(TenantMixin, RecordMixin, Base):
    __tablename__ = "lesion_observations"

    lesion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="CASCADE"), index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="SET NULL"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    anatomical_site: Mapped[str | None] = mapped_column(String(160))
    body_map_view: Mapped[str | None] = mapped_column(String(16))
    length_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    width_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    morphology: Mapped[str] = mapped_column(String(160))
    border: Mapped[str] = mapped_column(String(120))
    pigmentation: Mapped[str] = mapped_column(String(120))
    change_over_time: Mapped[str] = mapped_column(String(240))
    symptoms: Mapped[str] = mapped_column(String(240))
    comparison: Mapped[str | None] = mapped_column(String(500))
    assessment: Mapped[str | None] = mapped_column(String(240))
    source: Mapped[str] = mapped_column(String(32), default="clinician")


class ClinicalImage(TenantMixin, RecordMixin, Base):
    __tablename__ = "clinical_images"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    lesion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="SET NULL"), index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="SET NULL")
    )
    file_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_records.id", ondelete="RESTRICT"), unique=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    anatomical_location: Mapped[str] = mapped_column(String(160))
    view: Mapped[str] = mapped_column(String(80), default="clinical")
    is_patient_submitted: Mapped[bool] = mapped_column(Boolean, default=False)


class Procedure(TenantMixin, RecordMixin, Base):
    __tablename__ = "procedures"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    lesion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="SET NULL"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT")
    )
    code: Mapped[str] = mapped_column(String(24), index=True)
    code_system: Mapped[str] = mapped_column(String(32), default="CPT")
    display: Mapped[str] = mapped_column(String(240))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    documentation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="completed")


class Consent(TenantMixin, RecordMixin, Base):
    __tablename__ = "consents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="SET NULL")
    )
    consent_type: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_by_name: Mapped[str] = mapped_column(String(160))
    signature_text: Mapped[str] = mapped_column(String(200))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Order(TenantMixin, RecordMixin, Base):
    __tablename__ = "orders"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    lesion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="SET NULL")
    )
    ordering_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT")
    )
    order_type: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(40))
    display: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="ordered", index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Specimen(TenantMixin, RecordMixin, Base):
    __tablename__ = "specimens"
    __table_args__ = (UniqueConstraint("organization_id", "accession_number"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("procedures.id", ondelete="RESTRICT")
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    lesion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="RESTRICT")
    )
    accession_number: Mapped[str] = mapped_column(String(80), index=True)
    specimen_type: Mapped[str] = mapped_column(String(120))
    body_site: Mapped[str] = mapped_column(String(160))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(32), default="collected", index=True)


class DiagnosticResult(TenantMixin, RecordMixin, Base):
    __tablename__ = "diagnostic_results"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    specimen_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("specimens.id", ondelete="RESTRICT"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    lesion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesions.id", ondelete="RESTRICT")
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("procedures.id", ondelete="RESTRICT")
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT")
    )
    result_type: Mapped[str] = mapped_column(String(64), default="surgical_pathology")
    status: Mapped[str] = mapped_column(String(32), default="preliminary", index=True)
    diagnosis: Mapped[str] = mapped_column(String(500))
    narrative: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    resulted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    patient_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Patient engagement


class Conversation(TenantMixin, RecordMixin, Base):
    __tablename__ = "conversations"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(240))
    channel: Mapped[str] = mapped_column(String(32), default="secure_message")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(TenantMixin, RecordMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    sender_kind: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="sent", index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL")
    )


class MessageDraft(TenantMixin, RecordMixin, Base):
    __tablename__ = "message_drafts"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.900"))
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL")
    )


class Questionnaire(TenantMixin, RecordMixin, Base):
    __tablename__ = "questionnaires"
    __table_args__ = (UniqueConstraint("organization_id", "slug", "version"),)

    slug: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(20))
    schema_json: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QuestionnaireResponse(TenantMixin, RecordMixin, Base):
    __tablename__ = "questionnaire_responses"

    questionnaire_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questionnaires.id", ondelete="RESTRICT"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="in_progress", index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommunicationPreference(TenantMixin, RecordMixin, Base):
    __tablename__ = "communication_preferences"
    __table_args__ = (UniqueConstraint("organization_id", "patient_id", "channel"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    destination: Mapped[str] = mapped_column(String(254))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppointmentReminder(TenantMixin, RecordMixin, Base):
    __tablename__ = "appointment_reminders"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(160))


# Operations


class Task(TenantMixin, RecordMixin, Base):
    __tablename__ = "tasks"

    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="SET NULL")
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), index=True
    )
    denial_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("denials.id", ondelete="SET NULL"), index=True
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(24), default="routine", index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskComment(TenantMixin, RecordMixin, Base):
    __tablename__ = "task_comments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    body: Mapped[str] = mapped_column(Text)


class WorkflowRun(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("next_event_sequence > 0", name="positive_next_event_sequence"),
    )

    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    next_event_sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "sequence", name="uq_workflow_events_run_sequence"),
        CheckConstraint("sequence > 0", name="positive_sequence"),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AutomationPolicy(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "automation_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        UniqueConstraint("organization_id", "id", name="uq_automation_policies_org_id"),
    )

    name: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    conditions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "policy_versions.id",
            name="fk_automation_policies_current_version",
            ondelete="SET NULL",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
    )


class Notification(TenantMixin, RecordMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Revenue cycle management


class EligibilityCheck(TenantMixin, RecordMixin, Base):
    __tablename__ = "eligibility_checks"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    coverage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("coverages.id", ondelete="RESTRICT"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deductible_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    copay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    coinsurance_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="simulated_payer")


class Estimate(TenantMixin, RecordMixin, Base):
    __tablename__ = "estimates"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="RESTRICT"), index=True
    )
    eligibility_check_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("eligibility_checks.id", ondelete="RESTRICT")
    )
    total_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expected_plan_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    patient_responsibility: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(24), default="presented")
    disclaimer: Mapped[str] = mapped_column(String(500))


class Claim(TenantMixin, RecordMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("organization_id", "claim_number"),)

    claim_number: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"), index=True
    )
    coverage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("coverages.id", ondelete="RESTRICT")
    )
    billing_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("providers.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    total_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    allowed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    patient_responsibility: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClaimLine(TenantMixin, RecordMixin, Base):
    __tablename__ = "claim_lines"
    __table_args__ = (UniqueConstraint("claim_id", "line_number"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    procedure_code: Mapped[str] = mapped_column(String(24), index=True)
    diagnosis_codes: Mapped[list] = mapped_column(JSON, default=list)
    units: Mapped[int] = mapped_column(Integer, default=1)
    charge_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    allowed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class ClaimEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "claim_events"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    actor_kind: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClaimResponse(TenantMixin, RecordMixin, Base):
    __tablename__ = "claim_responses"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    response_type: Mapped[str] = mapped_column(String(64), index=True)
    status_code: Mapped[str] = mapped_column(String(32))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="simulated_clearinghouse")


class Denial(TenantMixin, RecordMixin, Base):
    __tablename__ = "denials"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    reason_code: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    denied_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    denied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Appeal(TenantMixin, RecordMixin, Base):
    __tablename__ = "appeals"

    denial_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("denials.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    appeal_text: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(64))
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class Payment(TenantMixin, RecordMixin, Base):
    __tablename__ = "payments"

    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_method: Mapped[str] = mapped_column(String(64))
    reference: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="settled")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatientBalance(TenantMixin, RecordMixin, Base):
    __tablename__ = "patient_balances"
    __table_args__ = (UniqueConstraint("organization_id", "patient_id"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    last_statement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="current")


# AI and safety


class PromptVersion(TenantMixin, RecordMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("organization_id", "capability", "version"),)

    capability: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(32))
    template: Mapped[str] = mapped_column(Text)
    output_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AIRun(TenantMixin, RecordMixin, Base):
    __tablename__ = "ai_runs"

    capability: Mapped[str] = mapped_column(String(80), index=True)
    prompt_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prompt_versions.id", ondelete="RESTRICT")
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500))


class AIInput(TenantMixin, RecordMixin, Base):
    __tablename__ = "ai_inputs"

    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True
    )
    input_type: Mapped[str] = mapped_column(String(64))
    content_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    minimum_necessary: Mapped[bool] = mapped_column(Boolean, default=True)
    resource_refs_json: Mapped[list] = mapped_column(
        LEARNING_JSON, default=list, server_default="[]"
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    snapshot_ref: Mapped[str | None] = mapped_column(String(500))


class AIOutput(TenantMixin, RecordMixin, Base):
    __tablename__ = "ai_outputs"

    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True
    )
    output_type: Mapped[str] = mapped_column(String(64))
    content_json: Mapped[dict] = mapped_column(JSON)
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.900"))


class ProposedAction(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "proposed_actions"
    __table_args__ = (
        CheckConstraint("proposal_version > 0", name="positive_proposal_version"),
        CheckConstraint(
            "expected_target_version IS NULL OR expected_target_version > 0",
            name="positive_expected_target_version",
        ),
    )

    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL"), index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    action_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    proposal_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    expected_target_version: Mapped[int | None] = mapped_column(Integer)
    payload_hash: Mapped[str | None] = mapped_column(String(64))


class Approval(TenantMixin, RecordMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("proposed_action_version > 0", name="positive_proposed_action_version"),
        CheckConstraint(
            "expected_target_version IS NULL OR expected_target_version > 0",
            name="positive_expected_target_version",
        ),
    )

    proposed_action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposed_actions.id", ondelete="RESTRICT"), index=True
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(24), index=True)
    comment: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    proposed_action_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    expected_target_version: Mapped[int | None] = mapped_column(Integer)
    reviewer_role: Mapped[str | None] = mapped_column(String(64))
    edit_diff_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict, server_default="{}")


class ProvenanceRecord(TenantMixin, RecordMixin, Base):
    __tablename__ = "provenance_records"

    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    activity: Mapped[str] = mapped_column(String(80))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL")
    )
    source_entity_type: Mapped[str | None] = mapped_column(String(64))
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Governance


class AuditEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


class FileRecord(TenantMixin, RecordMixin, Base):
    __tablename__ = "file_records"
    __table_args__ = (UniqueConstraint("organization_id", "storage_key"),)

    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    storage_provider: Mapped[str] = mapped_column(String(32), default="vercel")
    storage_key: Mapped[str] = mapped_column(String(500))
    public_demo_url: Mapped[str | None] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str] = mapped_column(String(64), default="clinical_image")


class IntegrationEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "integration_events"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)

    provider: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(16))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="processed", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Learning substrate


class DomainEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_domain_events_org_id"),
        UniqueConstraint(
            "organization_id",
            "aggregate_type",
            "aggregate_id",
            "aggregate_sequence",
            name="uq_domain_events_aggregate_sequence",
        ),
        ForeignKeyConstraint(
            ["organization_id", "causation_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_domain_events_causation",
            ondelete="CASCADE",
        ),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        CheckConstraint("aggregate_sequence > 0", name="positive_aggregate_sequence"),
        Index(
            "ix_domain_events_org_recorded",
            "organization_id",
            "recorded_at",
            "id",
        ),
        Index(
            "ix_domain_events_org_type_occurred",
            "organization_id",
            "event_type",
            "occurred_at",
        ),
        Index(
            "ix_domain_events_org_correlation",
            "organization_id",
            "correlation_id",
        ),
        Index(
            "ix_domain_events_org_patient_occurred",
            "organization_id",
            "patient_id",
            "occurred_at",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    aggregate_sequence: Mapped[int] = mapped_column(Integer)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL")
    )
    actor_kind: Mapped[str] = mapped_column(String(32))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_role: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    causation_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    sensitivity: Mapped[str] = mapped_column(String(32), default="operational")
    purpose_of_use: Mapped[str] = mapped_column(String(64), default="care_operations")


class EventDeliveryCheckpoint(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "event_delivery_checkpoints"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_event_delivery_checkpoints_org_id"),
        UniqueConstraint(
            "organization_id",
            "consumer_name",
            "partition_key",
            name="uq_event_delivery_checkpoints_consumer_partition",
        ),
        ForeignKeyConstraint(
            ["organization_id", "last_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_event_delivery_checkpoints_last_event",
            ondelete="CASCADE",
        ),
        Index(
            "ix_event_delivery_checkpoints_org_lease",
            "organization_id",
            "status",
            "lease_expires_at",
        ),
    )

    consumer_name: Mapped[str] = mapped_column(String(120))
    partition_key: Mapped[str] = mapped_column(String(120), default="default")
    last_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    last_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="idle")
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class EpisodeDefinition(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "episode_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_episode_definitions_org_id"),
        UniqueConstraint(
            "organization_id", "slug", "version", name="uq_episode_definitions_slug_version"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        CheckConstraint("max_steps > 0", name="positive_max_steps"),
        CheckConstraint("max_duration_seconds > 0", name="positive_max_duration_seconds"),
        CheckConstraint("status IN ('draft','released')", name="valid_status"),
        Index(
            "ix_episode_definitions_org_status_released",
            "organization_id",
            "status",
            "released_at",
        ),
        Index(
            "ix_episode_definitions_org_type",
            "organization_id",
            "episode_type",
        ),
    )

    slug: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    episode_type: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    start_conditions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    termination_conditions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    observation_schema_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    action_schema_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    reward_schema_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    max_steps: Mapped[int] = mapped_column(Integer, default=100)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, default=2_592_000)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EpisodeInstance(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "episode_instances"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_episode_instances_org_id"),
        UniqueConstraint("organization_id", "episode_key", name="uq_episode_instances_episode_key"),
        ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_episode_instances_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "start_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_instances_start_event",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "end_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_instances_end_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_kind IN ('live','historical','synthetic')", name="valid_source_kind"
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','terminated')",
            name="valid_status",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="valid_time_range",
        ),
        Index(
            "ix_episode_instances_org_status_started",
            "organization_id",
            "status",
            "started_at",
        ),
        Index(
            "ix_episode_instances_org_patient_started",
            "organization_id",
            "patient_id",
            "started_at",
        ),
    )

    episode_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    episode_key: Mapped[str] = mapped_column(String(160))
    source_kind: Mapped[str] = mapped_column(String(24))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL")
    )
    seed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    end_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    counterfactual_boundary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)


class EpisodeEventLink(TenantMixin, RecordMixin, Base):
    __tablename__ = "episode_event_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_episode_event_links_org_id"),
        UniqueConstraint("episode_instance_id", "sequence", name="uq_episode_event_links_sequence"),
        UniqueConstraint(
            "episode_instance_id",
            "domain_event_id",
            name="uq_episode_event_links_event",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_episode_event_links_episode",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "domain_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_event_links_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        Index(
            "ix_episode_event_links_org_event",
            "organization_id",
            "domain_event_id",
        ),
    )

    episode_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    domain_event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(32), default="trajectory")


class ObservationManifest(TenantMixin, RecordMixin, Base):
    __tablename__ = "observation_manifests"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_observation_manifests_org_id"),
        UniqueConstraint(
            "organization_id",
            "episode_instance_id",
            "id",
            name="uq_observation_manifests_episode_id",
        ),
        UniqueConstraint(
            "episode_instance_id", "sequence", name="uq_observation_manifests_sequence"
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_observation_manifests_episode",
            ondelete="CASCADE",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        Index(
            "ix_observation_manifests_org_as_of",
            "organization_id",
            "as_of_at",
        ),
    )

    episode_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    as_of_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    snapshot_ref: Mapped[str | None] = mapped_column(String(500))
    synthetic_snapshot_json: Mapped[dict] = mapped_column(
        LEARNING_JSON,
        default=dict,
        comment=("Synthetic-only inline observation snapshot; live manifests use snapshot_ref"),
    )
    sensitivity: Mapped[str] = mapped_column(String(32), default="restricted")
    purpose_of_use: Mapped[str] = mapped_column(String(64), default="care_operations")


class ObservationResource(TenantMixin, RecordMixin, Base):
    __tablename__ = "observation_resources"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_observation_resources_org_id"),
        UniqueConstraint(
            "observation_manifest_id",
            "sequence",
            name="uq_observation_resources_sequence",
        ),
        UniqueConstraint(
            "observation_manifest_id",
            "resource_type",
            "resource_id",
            "resource_version",
            name="uq_observation_resources_version",
        ),
        ForeignKeyConstraint(
            ["organization_id", "observation_manifest_id"],
            ["observation_manifests.organization_id", "observation_manifests.id"],
            name="fk_observation_resources_manifest",
            ondelete="CASCADE",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("resource_version > 0", name="positive_resource_version"),
        Index(
            "ix_observation_resources_org_resource",
            "organization_id",
            "resource_type",
            "resource_id",
            "resource_version",
        ),
    )

    observation_manifest_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    resource_version: Mapped[int] = mapped_column(Integer)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64))
    snapshot_ref: Mapped[str | None] = mapped_column(String(500))


class DecisionPoint(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "decision_points"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_decision_points_org_id"),
        UniqueConstraint("episode_instance_id", "sequence", name="uq_decision_points_sequence"),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_decision_points_episode",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id", "observation_manifest_id"],
            [
                "observation_manifests.organization_id",
                "observation_manifests.episode_instance_id",
                "observation_manifests.id",
            ],
            name="fk_decision_points_observation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "trigger_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_decision_points_trigger_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("status IN ('open','decided','expired','cancelled')", name="valid_status"),
        CheckConstraint(
            "decided_at IS NULL OR decided_at >= opened_at", name="valid_decision_time"
        ),
        Index(
            "ix_decision_points_org_type_opened",
            "organization_id",
            "decision_type",
            "opened_at",
        ),
        Index(
            "ix_decision_points_org_status_deadline",
            "organization_id",
            "status",
            "deadline_at",
        ),
    )

    episode_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    decision_type: Mapped[str] = mapped_column(String(80))
    observation_manifest_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    actor_kind: Mapped[str] = mapped_column(String(32))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_role: Mapped[str | None] = mapped_column(String(64))
    available_actions_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    policy_refs_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    displayed_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposed_actions.id", ondelete="SET NULL")
    )
    recommendation_rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionAttempt(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "action_attempts"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_action_attempts_org_id"),
        UniqueConstraint("decision_point_id", "sequence", name="uq_action_attempts_sequence"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_action_attempts_idempotency"
        ),
        ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_action_attempts_decision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "result_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_action_attempts_result_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint(
            "proposal_version IS NULL OR proposal_version > 0",
            name="positive_proposal_version",
        ),
        CheckConstraint(
            "expected_target_version IS NULL OR expected_target_version > 0",
            name="positive_expected_target_version",
        ),
        CheckConstraint(
            "status IN ('pending','succeeded','failed','rejected','no_action','cancelled')",
            name="valid_status",
        ),
        CheckConstraint(
            "executed_at IS NULL OR executed_at >= attempted_at", name="valid_execution_time"
        ),
        Index(
            "ix_action_attempts_org_status_attempted",
            "organization_id",
            "status",
            "attempted_at",
        ),
        Index(
            "ix_action_attempts_org_type_attempted",
            "organization_id",
            "action_type",
            "attempted_at",
        ),
    )

    decision_point_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    actor_kind: Mapped[str] = mapped_column(String(32))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_runs.id", ondelete="SET NULL")
    )
    proposed_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposed_actions.id", ondelete="SET NULL")
    )
    proposal_version: Mapped[int | None] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(80))
    arguments_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    expected_target_type: Mapped[str | None] = mapped_column(String(64))
    expected_target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    expected_target_version: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    human_edit_diff_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)


class OutcomeObservation(TenantMixin, RecordMixin, Base):
    __tablename__ = "outcome_observations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_outcome_observations_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_outcome_observations_episode",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_outcome_observations_decision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "action_attempt_id"],
            ["action_attempts.organization_id", "action_attempts.id"],
            name="fk_outcome_observations_action",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_outcome_observations_source_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "provenance_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name="valid_provenance_kind",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="valid_confidence"),
        CheckConstraint(
            "source_resource_version IS NULL OR source_resource_version > 0",
            name="positive_source_resource_version",
        ),
        CheckConstraint(
            "window_end_at IS NULL OR window_start_at IS NULL OR window_end_at >= window_start_at",
            name="valid_observation_window",
        ),
        Index(
            "ix_outcome_observations_org_type_observed",
            "organization_id",
            "outcome_type",
            "observed_at",
        ),
        Index(
            "ix_outcome_observations_org_episode_observed",
            "organization_id",
            "episode_instance_id",
            "observed_at",
        ),
    )

    episode_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    decision_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    action_attempt_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    outcome_type: Mapped[str] = mapped_column(String(80))
    value_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    provenance_kind: Mapped[str] = mapped_column(String(40))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_resource_type: Mapped[str | None] = mapped_column(String(64))
    source_resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_resource_version: Mapped[int | None] = mapped_column(Integer)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    simulator_version: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("1.000"))
    content_hash: Mapped[str] = mapped_column(String(64))


class PolicyVersion(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_policy_versions_org_id"),
        UniqueConstraint(
            "automation_policy_id", "version", name="uq_policy_versions_policy_version"
        ),
        ForeignKeyConstraint(
            ["organization_id", "automation_policy_id"],
            ["automation_policies.organization_id", "automation_policies.id"],
            name="fk_policy_versions_policy",
            ondelete="CASCADE",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        CheckConstraint("status IN ('draft','released')", name="valid_status"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="valid_effective_range",
        ),
        Index(
            "ix_policy_versions_org_status_effective",
            "organization_id",
            "status",
            "effective_from",
        ),
    )

    automation_policy_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    conditions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    actions_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SimulationScenario(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "simulation_scenarios"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_simulation_scenarios_org_id"),
        UniqueConstraint(
            "organization_id",
            "slug",
            "version",
            name="uq_simulation_scenarios_slug_version",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_simulation_scenarios_definition",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        CheckConstraint("synthetic_only", name="synthetic_only_required"),
        CheckConstraint("status IN ('draft','released')", name="valid_status"),
        Index(
            "ix_simulation_scenarios_org_status_released",
            "organization_id",
            "status",
            "released_at",
        ),
    )

    episode_definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    slug: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(Integer)
    logical_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    initial_state_json: Mapped[dict] = mapped_column(
        LEARNING_JSON,
        default=dict,
        comment="Server-owned synthetic simulator state; never populated from live PHI",
    )
    initial_state_refs_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    actor_models_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    transition_rules_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    reward_spec_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    simulator_versions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    fault_plan_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    synthetic_only: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    content_hash: Mapped[str] = mapped_column(String(64))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetRelease(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "dataset_releases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_dataset_releases_org_id"),
        UniqueConstraint(
            "organization_id", "name", "version", name="uq_dataset_releases_name_version"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
        CheckConstraint("outcome_window_days >= 0", name="nonnegative_outcome_window"),
        CheckConstraint("status IN ('draft','released')", name="valid_status"),
        Index(
            "ix_dataset_releases_org_status_released",
            "organization_id",
            "status",
            "released_at",
        ),
    )

    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    intended_uses_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    prohibited_uses_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    legal_basis: Mapped[str] = mapped_column(String(160))
    cohort_definition_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    exclusion_criteria_json: Mapped[list] = mapped_column(LEARNING_JSON, default=list)
    observation_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome_window_days: Mapped[int] = mapped_column(Integer, default=0)
    terminology_versions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    schema_versions_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    deidentification_method: Mapped[str] = mapped_column(String(120))
    split_strategy_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    lineage_uri: Mapped[str] = mapped_column(String(500))
    lineage_hash: Mapped[str] = mapped_column(String(64))
    retention_policy_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    deletion_policy_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnvironmentRun(TenantMixin, OptimisticVersionMixin, RecordMixin, Base):
    __tablename__ = "environment_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_environment_runs_org_id"),
        UniqueConstraint("organization_id", "run_key", name="uq_environment_runs_run_key"),
        ForeignKeyConstraint(
            ["organization_id", "simulation_scenario_id"],
            ["simulation_scenarios.organization_id", "simulation_scenarios.id"],
            name="fk_environment_runs_scenario",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_environment_runs_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_environment_runs_episode",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "dataset_release_id"],
            ["dataset_releases.organization_id", "dataset_releases.id"],
            name="fk_environment_runs_dataset",
            ondelete="RESTRICT",
        ),
        CheckConstraint("mode IN ('replay','simulation','shadow')", name="valid_mode"),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','terminated')",
            name="valid_status",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="valid_time_range",
        ),
        CheckConstraint("current_step >= 0", name="nonnegative_current_step"),
        CheckConstraint("hard_violation_count >= 0", name="nonnegative_hard_violation_count"),
        Index(
            "ix_environment_runs_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_environment_runs_org_mode_created",
            "organization_id",
            "mode",
            "created_at",
        ),
    )

    run_key: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(String(24))
    simulation_scenario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    episode_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    episode_instance_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    dataset_release_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    agent_kind: Mapped[str] = mapped_column(String(64))
    agent_model: Mapped[str | None] = mapped_column(String(120))
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prompt_versions.id", ondelete="SET NULL")
    )
    code_version: Mapped[str] = mapped_column(String(120))
    seed: Mapped[int | None] = mapped_column(Integer)
    config_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    state_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    total_reward_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    hard_violation_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    termination_reason: Mapped[str | None] = mapped_column(String(240))


class EnvironmentStep(TenantMixin, RecordMixin, Base):
    __tablename__ = "environment_steps"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_environment_steps_org_id"),
        UniqueConstraint("environment_run_id", "step_number", name="uq_environment_steps_run_step"),
        ForeignKeyConstraint(
            ["organization_id", "environment_run_id"],
            ["environment_runs.organization_id", "environment_runs.id"],
            name="fk_environment_steps_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_environment_steps_decision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "observation_manifest_id"],
            ["observation_manifests.organization_id", "observation_manifests.id"],
            name="fk_environment_steps_observation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "action_attempt_id"],
            ["action_attempts.organization_id", "action_attempts.id"],
            name="fk_environment_steps_action",
            ondelete="RESTRICT",
        ),
        CheckConstraint("step_number > 0", name="positive_step_number"),
        CheckConstraint("latency_ms >= 0", name="nonnegative_latency"),
        CheckConstraint(
            "support_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name="valid_support_kind",
        ),
        CheckConstraint(
            "simulator_time_after IS NULL OR simulator_time_before IS NULL "
            "OR simulator_time_after >= simulator_time_before",
            name="valid_simulator_time_range",
        ),
        Index(
            "ix_environment_steps_org_run_step",
            "organization_id",
            "environment_run_id",
            "step_number",
        ),
    )

    environment_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    step_number: Mapped[int] = mapped_column(Integer)
    decision_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    observation_manifest_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    action_attempt_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    simulator_time_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    simulator_time_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state_before_hash: Mapped[str] = mapped_column(String(64))
    state_after_hash: Mapped[str] = mapped_column(String(64))
    support_kind: Mapped[str] = mapped_column(String(40))
    terminated: Mapped[bool] = mapped_column(Boolean, default=False)
    termination_reason: Mapped[str | None] = mapped_column(String(240))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class RewardComponent(TenantMixin, RecordMixin, Base):
    __tablename__ = "reward_components"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_reward_components_org_id"),
        UniqueConstraint(
            "environment_step_id",
            "component_name",
            "evaluator_key",
            "evaluator_version",
            name="uq_reward_components_evaluation",
        ),
        ForeignKeyConstraint(
            ["organization_id", "environment_step_id"],
            ["environment_steps.organization_id", "environment_steps.id"],
            name="fk_reward_components_step",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "provenance_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name="valid_provenance_kind",
        ),
        Index(
            "ix_reward_components_org_hard_computed",
            "organization_id",
            "hard_violation",
            "computed_at",
        ),
        Index(
            "ix_reward_components_org_name_computed",
            "organization_id",
            "component_name",
            "computed_at",
        ),
    )

    environment_step_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    component_name: Mapped[str] = mapped_column(String(80))
    evaluator_key: Mapped[str] = mapped_column(String(120))
    evaluator_version: Mapped[str] = mapped_column(String(64))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("1"))
    hard_violation: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_json: Mapped[dict] = mapped_column(LEARNING_JSON, default=dict)
    provenance_kind: Mapped[str] = mapped_column(String(40))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DatasetReleaseItem(TenantMixin, RecordMixin, Base):
    __tablename__ = "dataset_release_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_dataset_release_items_org_id"),
        UniqueConstraint(
            "dataset_release_id", "sequence", name="uq_dataset_release_items_sequence"
        ),
        UniqueConstraint(
            "dataset_release_id",
            "episode_instance_id",
            name="uq_dataset_release_items_episode",
        ),
        UniqueConstraint(
            "dataset_release_id",
            "environment_run_id",
            name="uq_dataset_release_items_run",
        ),
        UniqueConstraint(
            "dataset_release_id", "domain_event_id", name="uq_dataset_release_items_event"
        ),
        ForeignKeyConstraint(
            ["organization_id", "dataset_release_id"],
            ["dataset_releases.organization_id", "dataset_releases.id"],
            name="fk_dataset_release_items_release",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_dataset_release_items_episode",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "environment_run_id"],
            ["environment_runs.organization_id", "environment_runs.id"],
            name="fk_dataset_release_items_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "domain_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_dataset_release_items_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("split IN ('train','validation','test','holdout')", name="valid_split"),
        CheckConstraint(
            "(CASE WHEN episode_instance_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN environment_run_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN domain_event_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="exactly_one_item",
        ),
        Index(
            "ix_dataset_release_items_org_release_split",
            "organization_id",
            "dataset_release_id",
            "split",
        ),
    )

    dataset_release_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    episode_instance_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    environment_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    domain_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    split: Mapped[str] = mapped_column(String(24))
    inclusion_reason: Mapped[str] = mapped_column(String(500))


class DemoScenario(TenantMixin, RecordMixin, Base):
    __tablename__ = "demo_scenarios"
    __table_args__ = (UniqueConstraint("organization_id", "slug"),)

    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    current_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_chapter: Mapped[str] = mapped_column(String(64), default="patient_initiation")
    fallback_indicator: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DemoTimelineEvent(TenantMixin, RecordMixin, Base):
    __tablename__ = "demo_timeline_events"
    __table_args__ = (UniqueConstraint("demo_scenario_id", "sequence"),)

    demo_scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("demo_scenarios.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    chapter: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


@event.listens_for(EncounterNote, "before_update", propagate=True)
def prevent_signed_note_mutation(
    _mapper: object, _connection: object, target: EncounterNote
) -> None:
    """Signed content is append-only; later clinical context must be an amendment."""

    state = inspect(target)
    previous_status = state.attrs.status.history.deleted
    was_signed = bool(
        (previous_status and previous_status[0] in {"signed", "amended"})
        or (not previous_status and target.status in {"signed", "amended"})
    )
    if not was_signed:
        return
    status_history = state.attrs.status.history
    if status_history.has_changes():
        old_status = status_history.deleted[0] if status_history.deleted else target.status
        new_status = status_history.added[0] if status_history.added else target.status
        if not (old_status == "signed" and new_status == "amended"):
            raise ValueError(
                "A signed note cannot be reopened or have its lifecycle status rolled back."
            )
    allowed = {"status", "updated_at"}
    changed = {
        attribute.key
        for attribute in state.attrs
        if attribute.history.has_changes() and attribute.key not in allowed
    }
    if changed:
        raise ValueError(
            "Signed clinical notes are immutable; create a note amendment instead "
            f"(attempted: {', '.join(sorted(changed))})."
        )


@event.listens_for(EncounterNote, "before_delete", propagate=True)
def prevent_signed_note_delete(_mapper: object, _connection: object, target: EncounterNote) -> None:
    if target.status in {"signed", "amended"}:
        raise ValueError("Signed clinical notes cannot be deleted.")


@event.listens_for(NoteVersion, "before_update", propagate=True)
@event.listens_for(NoteVersion, "before_delete", propagate=True)
def prevent_note_version_mutation(
    _mapper: object, _connection: object, _target: NoteVersion
) -> None:
    raise ValueError("Note versions are append-only and cannot be changed or deleted.")


@event.listens_for(NoteAmendment, "before_update", propagate=True)
@event.listens_for(NoteAmendment, "before_delete", propagate=True)
def prevent_note_amendment_mutation(
    _mapper: object, _connection: object, _target: NoteAmendment
) -> None:
    raise ValueError("Signed note amendments are append-only and cannot be changed or deleted.")


def prevent_append_only_evidence_mutation(
    _mapper: object, _connection: object, target: object
) -> None:
    raise ValueError(f"{type(target).__name__} is append-only evidence and cannot be changed.")


def prevent_finalized_evidence_update(_mapper: object, _connection: object, target: object) -> None:
    finalized_statuses = _FINALIZED_EVIDENCE_STATUSES[type(target)]
    state = inspect(target)
    status_history = state.attrs.status.history
    previous_status = (
        status_history.deleted[0] if status_history.deleted else state.attrs.status.value
    )
    if previous_status in finalized_statuses:
        raise ValueError(
            f"Finalized {type(target).__name__} evidence cannot be changed; create a new version."
        )


def prevent_finalized_evidence_delete(_mapper: object, _connection: object, target: object) -> None:
    finalized_statuses = _FINALIZED_EVIDENCE_STATUSES[type(target)]
    if inspect(target).attrs.status.value in finalized_statuses:
        raise ValueError(f"Finalized {type(target).__name__} evidence cannot be deleted.")


_APPEND_ONLY_EVIDENCE_MODELS = (
    WorkflowEvent,
    DomainEvent,
    EpisodeEventLink,
    ObservationManifest,
    ObservationResource,
    OutcomeObservation,
    EnvironmentStep,
    RewardComponent,
    DatasetReleaseItem,
)

_FINALIZED_EVIDENCE_STATUSES = {
    EpisodeDefinition: frozenset({"released"}),
    EpisodeInstance: frozenset({"completed", "failed", "terminated"}),
    DecisionPoint: frozenset({"decided", "expired", "cancelled"}),
    ActionAttempt: frozenset({"succeeded", "failed", "rejected", "no_action", "cancelled"}),
    PolicyVersion: frozenset({"released"}),
    SimulationScenario: frozenset({"released"}),
    EnvironmentRun: frozenset({"completed", "failed", "terminated"}),
    DatasetRelease: frozenset({"released"}),
}

for _evidence_model in _APPEND_ONLY_EVIDENCE_MODELS:
    event.listen(
        _evidence_model,
        "before_update",
        prevent_append_only_evidence_mutation,
        propagate=True,
    )
    event.listen(
        _evidence_model,
        "before_delete",
        prevent_append_only_evidence_mutation,
        propagate=True,
    )

for _evidence_model in _FINALIZED_EVIDENCE_STATUSES:
    event.listen(
        _evidence_model,
        "before_update",
        prevent_finalized_evidence_update,
        propagate=True,
    )
    event.listen(
        _evidence_model,
        "before_delete",
        prevent_finalized_evidence_delete,
        propagate=True,
    )
