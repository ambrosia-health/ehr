from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import domain_now
from .config import get_settings
from .models import AIInput, AIOutput, AIRun, DemoScenario, PromptVersion, ProvenanceRecord
from .schemas import AI_OUTPUT_SCHEMAS, APIModel

CAPABILITIES = tuple(AI_OUTPUT_SCHEMAS)
ATTESTED_MODAL_PROVIDER = "modal_open_weights"
ATTESTED_MODAL_MODEL = (
    "Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775"
)


def deterministic_output(capability: str, context: dict[str, Any]) -> dict[str, Any]:
    """Clinically conservative fixtures keep the demo available during model cold starts."""

    patient_name = context.get("patientName", "the patient")
    outputs: dict[str, dict[str, Any]] = {
        "chart_summary": {
            "headline": f"{patient_name} reports an evolving pigmented lesion on the left posterior shoulder.",
            "active_concerns": [
                "Lesion enlarged and darkened over approximately four months",
                "Intermittent mild pruritus without bleeding or ulceration",
            ],
            "relevant_history": [
                "No personal history of skin cancer",
                "Father diagnosed with melanoma at age 61",
                "No anticoagulant use or lidocaine allergy documented",
            ],
            "readiness_flags": [
                "Intake complete",
                "Eligibility active",
                "Clinical images available",
            ],
            "suggested_focus": ["Compare serial images", "Dermoscopy", "Discuss biopsy options"],
        },
        "ambient_note": {
            "subjective": "Changing mole on the left posterior shoulder, larger and darker over four months with occasional itching. No bleeding or pain.",
            "objective": "Left posterior shoulder: 7 x 5 mm asymmetric brown-black papule with irregular border and variegated pigmentation.",
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
                "Provide wound care and warning-sign instructions",
            ],
            "procedure_proposal": {
                "type": "shave_biopsy",
                "cpt": "11102",
                "site": "left posterior shoulder",
            },
        },
        "coding_suggestions": {
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
                    "rationale": "Documentation proposes a shave biopsy of one lesion.",
                    "confidence": 0.96,
                },
            ],
            "documentation_gaps": [],
        },
        "patient_message": {
            "body": "Mild tenderness and a small amount of spotting can occur during the first day. Keep the site clean, apply petrolatum, and cover it as directed. Please contact us for spreading redness, worsening pain, pus, fever, or bleeding that does not stop after firm pressure.",
            "source_instructions": ["Approved shave-biopsy aftercare v2026.1"],
            "route_to_staff": bool(context.get("uncertain", False)),
            "uncertainty_reason": "The question needs clinical review."
            if context.get("uncertain")
            else None,
        },
        "pathology_summary": {
            "clinician_summary": "Compound dysplastic melanocytic nevus with moderate atypia; margins narrowly clear. No melanoma identified.",
            "patient_friendly_summary": "The biopsy showed an atypical but non-cancerous mole. The sampled edges are clear, so we recommend monitoring the area and routine skin checks.",
            "urgency": "routine",
            "follow_up": [
                "Notify patient",
                "Recheck biopsy site in 3 months",
                "Annual full skin exam",
            ],
        },
        "denial_recommendation": {
            "classification": "modifier/documentation",
            "root_cause": "The payer bundled the biopsy with a same-day evaluation because modifier 25 was omitted.",
            "recommended_correction": "Confirm separately identifiable evaluation documentation, append modifier 25 to 99213, and resubmit.",
            "evidence_needed": ["Signed encounter note", "Procedure note", "Original remittance"],
            "appeal_draft": "The separately identifiable evaluation addressed a new changing lesion and resulted in the decision to perform biopsy. The attached signed documentation supports 99213-25 in addition to 11102.",
        },
        "document_extraction": {
            "document_type": context.get("documentType", "insurance_card"),
            "fields": {
                "payerName": "Blue Horizon PPO",
                "memberId": "BHP74209183",
                "groupNumber": "DERM2046",
            },
            "warnings": [],
        },
    }
    if capability not in outputs:
        raise ValueError(f"Unsupported AI capability: {capability}")
    return outputs[capability]


async def _live_inference(
    capability: str,
    context: dict[str, Any],
    *,
    prompt_version: str,
    prompt_template: str,
    prompt_hash: str,
) -> tuple[dict[str, Any], str, str, bool, str | None]:
    settings = get_settings()
    if not settings.modal_ai_url:
        raise RuntimeError("Modal AI URL is not configured")
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            settings.modal_ai_url,
            json={
                "capability": capability,
                "context": context,
                "prompt": {
                    "version": prompt_version,
                    "template": prompt_template,
                    "sha256": prompt_hash,
                },
            },
            headers={"X-Ambrosia-Internal": settings.modal_internal_auth_secret},
        )
        response.raise_for_status()
        provider = response.headers.get("X-Ambrosia-AI-Provider", "modal_unverified_adapter")
        model = response.headers.get("X-Ambrosia-AI-Model", "unreported")
        returned_prompt_version = response.headers.get("X-Ambrosia-AI-Prompt-Version")
        returned_prompt_hash = response.headers.get("X-Ambrosia-AI-Prompt-Hash")
        declared_fallback = response.headers.get("X-Ambrosia-AI-Fallback", "true").lower()
        live_attested = (
            declared_fallback == "false"
            and provider == ATTESTED_MODAL_PROVIDER
            and model == ATTESTED_MODAL_MODEL
            and returned_prompt_version == prompt_version
            and returned_prompt_hash == prompt_hash
        )
        error = response.headers.get("X-Ambrosia-AI-Error-Class")
        if not live_attested and not error:
            error = (
                "remote_inference_reported_fallback"
                if declared_fallback == "true"
                else "remote_model_attestation_missing_or_untrusted"
            )
        return response.json(), provider, model, not live_attested, error


async def run_ai(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    capability: str,
    context: dict[str, Any],
    patient_id: uuid.UUID | None,
    requested_by_user_id: uuid.UUID | None,
    minimum_necessary: bool = True,
) -> tuple[AIRun, APIModel]:
    schema = AI_OUTPUT_SCHEMAS.get(capability)
    if schema is None:
        raise ValueError(f"Unsupported AI capability: {capability}")
    prompt = await session.scalar(
        select(PromptVersion).where(
            PromptVersion.organization_id == organization_id,
            PromptVersion.capability == capability,
            PromptVersion.active.is_(True),
        )
    )
    if prompt is None:
        raise RuntimeError(f"No active prompt version for {capability}")

    started = time.perf_counter()
    fallback_used = False
    error: str | None = None
    prompt_hash = hashlib.sha256(prompt.template.encode()).hexdigest()
    try:
        raw, provider, model, fallback_used, error = await _live_inference(
            capability,
            context,
            prompt_version=prompt.version,
            prompt_template=prompt.template,
            prompt_hash=prompt_hash,
        )
        validated = schema.model_validate(raw)
    except (httpx.HTTPError, RuntimeError, TimeoutError, ValidationError, ValueError) as exc:
        fallback_used = True
        error = str(exc)[:500]
        validated = schema.model_validate(deterministic_output(capability, context))
        provider = "deterministic_fallback"
        model = "ambrosia-fixture-2026.1"

    scenario = await session.scalar(
        select(DemoScenario).where(DemoScenario.organization_id == organization_id)
    )
    if scenario is not None:
        scenario.fallback_indicator = fallback_used

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    recorded_at = await domain_now(session, organization_id)
    run = AIRun(
        organization_id=organization_id,
        capability=capability,
        prompt_version_id=prompt.id,
        patient_id=patient_id,
        requested_by_user_id=requested_by_user_id,
        provider=provider,
        model=model,
        status="completed",
        fallback_used=fallback_used,
        started_at=recorded_at,
        completed_at=recorded_at,
        latency_ms=elapsed_ms,
        error_message=error,
    )
    session.add(run)
    await session.flush()
    canonical_input = json.dumps(context, sort_keys=True, default=str)
    session.add_all(
        [
            AIInput(
                organization_id=organization_id,
                ai_run_id=run.id,
                input_type="minimum_necessary_context",
                content_json=context,
                content_hash=hashlib.sha256(canonical_input.encode()).hexdigest(),
                minimum_necessary=minimum_necessary,
            ),
            AIOutput(
                organization_id=organization_id,
                ai_run_id=run.id,
                output_type=capability,
                content_json=validated.model_dump(mode="json", by_alias=True),
                schema_valid=True,
                confidence=0,
            ),
            ProvenanceRecord(
                organization_id=organization_id,
                entity_type="ai_output",
                entity_id=run.id,
                activity=f"generated_{capability}",
                actor_user_id=requested_by_user_id,
                ai_run_id=run.id,
                source_entity_type="patient" if patient_id else None,
                source_entity_id=patient_id,
                detail_json={
                    "promptVersion": prompt.version,
                    "promptHash": prompt_hash,
                    "fallbackUsed": fallback_used,
                    "schemaValid": True,
                    "confidenceMeaning": "not_calibrated",
                },
            ),
        ]
    )
    await session.flush()
    return run, validated
