from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


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

    @model_validator(mode="before")
    @classmethod
    def reject_nul_characters(cls, value: Any) -> Any:
        def inspect(item: Any) -> None:
            if isinstance(item, str) and "\x00" in item:
                raise ValueError("Text fields cannot contain NUL characters")
            if isinstance(item, dict):
                for key, nested in item.items():
                    inspect(key)
                    inspect(nested)
            elif isinstance(item, list | tuple):
                for nested in item:
                    inspect(nested)

        inspect(value)
        return value


class DemoSessionRequest(APIModel):
    persona: str = Field(min_length=1, max_length=64)
    presenter_code: str | None = Field(default=None, max_length=512)


class SwitchPersonaRequest(APIModel):
    persona: str = Field(min_length=1, max_length=64)


class CompositeImage(APIModel):
    """Reference to a server-owned synthetic file; clients never supply file metadata."""

    file_id: uuid.UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    synthetic: Literal[True]


class CompositeIntakeRequest(APIModel):
    patient_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=500)
    first_noticed: str = Field(min_length=1, max_length=200)
    change: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        default_factory=list, max_length=20
    )
    symptoms: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        default_factory=list, max_length=20
    )
    urgent_signs: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        default_factory=list, max_length=20
    )
    image: CompositeImage | None = None
    appointment_slot: uuid.UUID
    insurance_payer: str = Field(default="Blue Horizon PPO", min_length=1, max_length=160)
    insurance_member_id: str = Field(min_length=1, max_length=80)
    medications: list[Annotated[str, StringConstraints(min_length=1, max_length=120)]] = Field(
        default_factory=list, max_length=100
    )
    allergies: list[Annotated[str, StringConstraints(min_length=1, max_length=160)]] = Field(
        default_factory=list, max_length=100
    )
    personal_skin_cancer_history: str = Field(default="None", max_length=240)
    family_skin_cancer_history: str = Field(default="None", max_length=240)
    pharmacy: str = Field(default="Not provided", max_length=160)
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


class AmbientRequest(APIModel):
    transcript: str = Field(min_length=1, max_length=100_000)


class NoteUpdateRequest(APIModel):
    content: str = Field(min_length=1, max_length=100_000)
    structured_content: dict[str, Any] = Field(max_length=200)
    reason: str = Field(default="Clinician edit", min_length=1, max_length=240)


class AmendmentRequest(APIModel):
    reason: str = Field(min_length=1, max_length=500)
    amendment_text: str = Field(min_length=1, max_length=20_000)


class LesionObservationRequest(APIModel):
    lesion_id: uuid.UUID | None = None
    encounter_id: uuid.UUID | None = None
    site: str | None = Field(default=None, max_length=160)
    view: str | None = Field(default=None, max_length=16)
    length_mm: Decimal = Field(gt=0, le=100)
    width_mm: Decimal = Field(gt=0, le=100)
    morphology: str = Field(min_length=1, max_length=160)
    border: str = Field(min_length=1, max_length=120)
    pigmentation: str = Field(min_length=1, max_length=120)
    change_over_time: str = Field(min_length=1, max_length=240)
    symptoms: (
        Annotated[str, StringConstraints(min_length=1, max_length=240)]
        | list[Annotated[str, StringConstraints(min_length=1, max_length=120)]]
    )
    comparison: str | None = Field(default=None, max_length=500)
    assessment: str | None = Field(default=None, max_length=240)


class ReviewCompleteRequest(APIModel):
    proposed_action_ids: list[uuid.UUID] = Field(default_factory=list)
    attest: Literal[True]
    sign_note: Literal[True]
    attestation: str = Field(min_length=8, max_length=500)
    expected_note_version: int = Field(ge=1)
    expected_note_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DraftMessageRequest(APIModel):
    conversation_id: uuid.UUID
    question: str = Field(min_length=1, max_length=3000)


class ConversationMessageRequest(APIModel):
    body: str = Field(min_length=1, max_length=5_000)
    approve_ai_draft_id: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def reject_blank_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message body is required")
        return value


class PathologyReviewRequest(APIModel):
    patient_message: str | None = Field(default=None, min_length=1, max_length=5_000)
    notify_patient: bool = False
    create_followup: bool = False
    disposition: str = Field(default="clinical_monitoring", min_length=1, max_length=100)


class AdvanceTimeRequest(APIModel):
    days: int = Field(default=0, ge=0, le=30)
    hours: int = Field(default=0, ge=0, le=720)
    chapter: str | None = Field(default=None, max_length=64)


class TriggerRequest(APIModel):
    entity_id: str | None = Field(default=None, max_length=64)


EnvironmentActionType = Literal[
    "review_intake",
    "complete_encounter_review",
    "review_pathology",
    "notify_patient",
    "submit_claim",
    "correct_and_resubmit_claim",
    "close_episode",
    "request_missing_information",
    "escalate",
]


class EnvironmentAction(APIModel):
    """A bounded command selected from the server-owned synthetic action space."""

    type: EnvironmentActionType
    reason_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )


class EnvironmentActionContext(APIModel):
    """The complete, intentionally narrow input visible to an environment policy."""

    observation: dict[str, Any]
    allowed_actions: list[EnvironmentActionType] = Field(min_length=1, max_length=32)

    @field_validator("allowed_actions")
    @classmethod
    def require_unique_actions(
        cls, value: list[EnvironmentActionType]
    ) -> list[EnvironmentActionType]:
        if len(value) != len(set(value)):
            raise ValueError("Allowed environment actions must be unique")
        return value


class EnvironmentRunRequest(APIModel):
    episode_definition_id: uuid.UUID
    actor_role: Literal[
        "environment_agent",
        "patient",
        "clinical_staff",
        "provider",
        "biller",
        "mso_owner",
    ]
    seed: int = Field(default=0, ge=0, le=2_147_483_647)
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )


class EnvironmentStepRequest(APIModel):
    expected_sequence: int = Field(ge=1)
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    action: EnvironmentAction


class EnvironmentModelStepRequest(APIModel):
    """Advance one synthetic step using the configured model policy."""

    expected_sequence: int = Field(ge=1)
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )


class AppealRequest(APIModel):
    denial_id: uuid.UUID
    appeal_text: str | None = Field(default=None, min_length=1, max_length=20_000)


class ClaimResubmitRequest(APIModel):
    appeal_body: str = Field(min_length=1, max_length=20_000)
    correction: str = Field(min_length=1, max_length=4_000)
    source_task_id: uuid.UUID | None = None


class AIRequest(APIModel):
    patient_id: uuid.UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)


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
    "environment_action": EnvironmentAction,
}
