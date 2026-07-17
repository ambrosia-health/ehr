from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class APIModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class LoginRequest(APIModel):
    persona_key: str
    presenter_key: str | None = None


class DemoSessionRequest(APIModel):
    persona: str
    presenter_code: str | None = None


class SwitchPersonaRequest(APIModel):
    persona_key: str = Field(validation_alias=AliasChoices("personaKey", "persona"))


class CompositeImage(APIModel):
    """Reference to a server-owned synthetic file; clients never supply file metadata."""

    file_id: uuid.UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    synthetic: Literal[True]


class CompositeIntakeRequest(APIModel):
    patient_id: uuid.UUID | None = None
    reason: str
    first_noticed: str
    change: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    urgent_signs: list[str] = Field(default_factory=list)
    image: CompositeImage | None = None
    appointment_slot: uuid.UUID
    insurance_payer: str = "Blue Horizon PPO"
    insurance_member_id: str
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    personal_skin_cancer_history: str = "None"
    family_skin_cancer_history: str = "None"
    pharmacy: str = "Not provided"
    consents: CompositeConsents = Field(default_factory=lambda: CompositeConsents())

    @model_validator(mode="after")
    def validate_exclusive_none_options(self) -> CompositeIntakeRequest:
        normalized_symptoms = {item.strip().lower() for item in self.symptoms}
        if "no symptoms" in normalized_symptoms and len(normalized_symptoms) > 1:
            raise ValueError("No symptoms cannot be combined with a reported symptom")
        normalized_urgent_signs = {item.strip().lower() for item in self.urgent_signs}
        if "none of these" in normalized_urgent_signs and len(normalized_urgent_signs) > 1:
            raise ValueError("None of these cannot be combined with an urgent warning sign")
        return self


class CompositeConsents(APIModel):
    treatment: bool = False
    privacy: bool = False
    photography: bool = False


CompositeIntakeRequest.model_rebuild()


class PatientInitiationRequest(APIModel):
    patient_id: uuid.UUID | None = None
    concern: str = "Changing mole on my left posterior shoulder"
    symptoms: list[str] = Field(default_factory=lambda: ["mild itching"])
    changes: list[str] = Field(default_factory=lambda: ["larger", "darker"])
    urgent_warning_signs: list[str] = Field(default_factory=list)
    image_url: str | None = "/images/clinical/sarah-left-posterior-shoulder.png"


class AppointmentBookingRequest(APIModel):
    patient_id: uuid.UUID | None = None
    provider_id: uuid.UUID
    location_id: uuid.UUID
    starts_at: datetime
    reason: str
    visit_type: str = "New lesion evaluation"


class IntakeMedication(APIModel):
    name: str
    dose: str | None = None
    frequency: str | None = None


class IntakeAllergy(APIModel):
    substance: str
    reaction: str
    severity: str = "mild"


class IntakeInsurance(APIModel):
    payer_name: str
    plan_name: str
    member_id: str
    group_number: str | None = None
    subscriber_name: str
    relationship: str = "self"


class IntakeConsent(APIModel):
    consent_type: str
    version: str = "2026.1"
    accepted: bool
    signature_text: str


class IntakeRequest(APIModel):
    patient_id: uuid.UUID | None = None
    appointment_id: uuid.UUID
    reason_for_visit: str
    lesion_history: str
    symptoms: list[str]
    changes: list[str]
    medications: list[IntakeMedication] = Field(default_factory=list)
    allergies: list[IntakeAllergy] = Field(default_factory=list)
    personal_skin_cancer_history: str = "None"
    family_skin_cancer_history: str = "None"
    pharmacy: str
    insurance: IntakeInsurance
    consents: list[IntakeConsent]
    image_urls: list[str] = Field(default_factory=list)


class AmbientRequest(APIModel):
    transcript: str


class NoteUpdateRequest(APIModel):
    content: str
    structured_content: dict[str, Any]
    reason: str = "Clinician edit"


class AmendmentRequest(APIModel):
    reason: str
    amendment_text: str


class LesionObservationRequest(APIModel):
    lesion_id: uuid.UUID | None = None
    encounter_id: uuid.UUID | None = None
    site: str | None = None
    view: str | None = None
    length_mm: Decimal = Field(gt=0, le=100)
    width_mm: Decimal = Field(gt=0, le=100)
    morphology: str
    border: str
    pigmentation: str
    change_over_time: str
    symptoms: str | list[str]
    comparison: str | None = None
    assessment: str | None = None


class ReviewCompleteRequest(APIModel):
    proposed_action_ids: list[uuid.UUID] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "proposedActionIds", "approvedProposalIds", "approved_proposal_ids"
        ),
    )
    attest: Literal[True]
    sign_note: Literal[True]
    attestation: str = Field(min_length=8, max_length=500)
    expected_note_version: int = Field(ge=1)
    expected_note_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MessageRequest(APIModel):
    conversation_id: uuid.UUID
    body: str = Field(min_length=1, max_length=5000)


class DraftMessageRequest(APIModel):
    conversation_id: uuid.UUID
    question: str = Field(min_length=1, max_length=3000)


class ApproveDraftRequest(APIModel):
    body: str | None = None


class PathologyReviewRequest(APIModel):
    patient_message: str | None = None
    notify_patient: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "notifyPatient", "approvePatientMessage", "approve_patient_message"
        ),
    )
    create_followup: bool = False
    disposition: str = "clinical_monitoring"


class AdvanceTimeRequest(APIModel):
    days: int = Field(default=0, ge=0, le=30)
    hours: int = Field(default=0, ge=0, le=720)
    chapter: str | None = None


class TriggerRequest(APIModel):
    entity_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("entityId", "resultId", "result_id", "claimId", "claim_id"),
    )


class AppealRequest(APIModel):
    denial_id: uuid.UUID
    appeal_text: str | None = None


class ClaimResubmitRequest(APIModel):
    appeal_body: str = Field(min_length=1, max_length=20_000)
    correction: str = Field(min_length=1, max_length=4_000)
    source_task_id: uuid.UUID | None = None


class AIRequest(APIModel):
    patient_id: uuid.UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class EncounterNoteDraftRequest(APIModel):
    assessment_plan: str = Field(min_length=1, max_length=20_000)


class DocumentExtractionOutput(APIModel):
    document_type: str
    fields: dict[str, str]
    warnings: list[str]


class ChartSummaryOutput(APIModel):
    headline: str
    active_concerns: list[str]
    relevant_history: list[str]
    readiness_flags: list[str]
    suggested_focus: list[str]


class AmbientNoteOutput(APIModel):
    subjective: str
    objective: str
    assessment: list[dict[str, str]]
    plan: list[str]
    procedure_proposal: dict[str, Any]


class CodingSuggestion(APIModel):
    code: str
    system: Literal["ICD-10-CM", "CPT"]
    display: str
    rationale: str
    confidence: float = Field(ge=0, le=1)


class CodingSuggestionsOutput(APIModel):
    suggestions: list[CodingSuggestion]
    documentation_gaps: list[str]


class PatientMessageOutput(APIModel):
    body: str
    source_instructions: list[str]
    route_to_staff: bool
    uncertainty_reason: str | None = None


class PathologySummaryOutput(APIModel):
    clinician_summary: str
    patient_friendly_summary: str
    urgency: Literal["routine", "soon", "urgent"]
    follow_up: list[str]


class DenialRecommendationOutput(APIModel):
    classification: str
    root_cause: str
    recommended_correction: str
    evidence_needed: list[str]
    appeal_draft: str


AI_OUTPUT_SCHEMAS: dict[str, type[APIModel]] = {
    "chart_summary": ChartSummaryOutput,
    "ambient_note": AmbientNoteOutput,
    "coding_suggestions": CodingSuggestionsOutput,
    "patient_message": PatientMessageOutput,
    "pathology_summary": PathologySummaryOutput,
    "denial_recommendation": DenialRecommendationOutput,
    "document_extraction": DocumentExtractionOutput,
}
