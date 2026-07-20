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
from .learning import hash_json, record_domain_event
from .models import AIInput, AIOutput, AIRun, DemoScenario, PromptVersion, ProvenanceRecord
from .schemas import AI_OUTPUT_SCHEMAS, APIModel, EnvironmentActionContext

CAPABILITIES = tuple(AI_OUTPUT_SCHEMAS)
ATTESTED_AI_PROVIDER = "openai"
ATTESTED_AI_MODEL = "gpt-5.6-luna"
ATTESTED_AI_REASONING_EFFORT = "low"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _context_resource_refs(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract bounded logical references without pretending they are snapshots."""

    references: list[dict[str, Any]] = []
    for key, value in sorted(context.items()):
        if not key.endswith("Id") or not isinstance(value, (str, uuid.UUID)):
            continue
        try:
            resource_id = uuid.UUID(str(value))
        except ValueError:
            continue
        resource_type = key[:-2] or "resource"
        references.append(
            {
                "resourceType": resource_type,
                "resourceId": str(resource_id),
                "referenceHash": hash_json(
                    {"resourceType": resource_type, "resourceId": str(resource_id)}
                ),
            }
        )
    return references[:64]


def deterministic_output(capability: str, context: dict[str, Any]) -> dict[str, Any]:
    """Conservative fixtures keep synthetic workflows available during provider outages."""

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
    if capability == "environment_action":
        # Keep the capability-wide schema fixture executable for generic health checks.
        # The environment service validates and always supplies the real bounded context.
        policy_context = (
            context
            if "observation" in context and "allowedActions" in context
            else {"observation": {}, "allowedActions": ["escalate"]}
        )
        policy_input = EnvironmentActionContext.model_validate(policy_context)
        outstanding_work = policy_input.observation.get("outstandingWork", [])
        if not isinstance(outstanding_work, list):
            outstanding_work = []
        selected = next(
            (
                action
                for action in outstanding_work
                if isinstance(action, str) and action in policy_input.allowed_actions
            ),
            None,
        )
        if selected is None:
            selected = next(
                (
                    action
                    for action in policy_input.allowed_actions
                    if action != "escalate"
                ),
                policy_input.allowed_actions[0],
            )
        return {"type": selected, "reasonCode": "deterministic_fallback"}
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
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI is not configured")
    schema = AI_OUTPUT_SCHEMAS[capability]
    conservative_reference = deterministic_output(capability, context)
    if capability == "environment_action":
        developer_instruction = (
            "You are an evaluation policy acting only in an isolated synthetic environment. "
            "Return one JSON object and no prose. Select exactly one type listed in "
            "allowedActions. Use only the supplied observation and allowedActions; do not "
            "infer hidden patient facts, future state, rewards, or transition rules. Escalate "
            "when the observation does not safely support another allowed action. "
            f"Execute this versioned instruction: {prompt_template}"
        )
    else:
        developer_instruction = (
            "You are a clinical documentation assistant operating only on synthetic demo data. "
            "Return one JSON object and no prose. Follow the supplied output schema. "
            "Do not invent diagnoses, medications, codes, or facts beyond the context and "
            "conservative reference. Start from conservativeReference and preserve every "
            "required key; change a value only when context explicitly supports a safer value. "
            "Preserve uncertainty and route unsafe ambiguity to staff. "
            f"Execute this versioned instruction: {prompt_template}"
        )
    model_input = {
        "capability": capability,
        "context": context,
        "conservativeReference": conservative_reference,
        "promptVersion": prompt_version,
        "promptSha256": prompt_hash,
    }
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": ATTESTED_AI_MODEL,
                "reasoning": {"effort": ATTESTED_AI_REASONING_EFFORT},
                "store": False,
                "safety_identifier": "ambrosia-synthetic-demo",
                "max_output_tokens": 2_500,
                "input": [
                    {"role": "developer", "content": developer_instruction},
                    {
                        "role": "user",
                        "content": json.dumps(model_input, sort_keys=True, default=str),
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": f"ambrosia_{capability}",
                        "schema": schema.model_json_schema(by_alias=True),
                        # Dynamic-map capabilities require non-strict generation. The
                        # Pydantic and semantic validators below remain authoritative.
                        "strict": False,
                    }
                },
            },
        )
        response.raise_for_status()
    response_body = response.json()
    if not isinstance(response_body, dict):
        raise ValueError("OpenAI response must be a JSON object")
    if response_body.get("status") != "completed":
        raise RuntimeError("openai_response_incomplete")
    model = response_body.get("model", "unreported")
    if model != ATTESTED_AI_MODEL:
        raise RuntimeError("openai_model_attestation_mismatch")
    output_items = response_body.get("output")
    if not isinstance(output_items, list):
        raise ValueError("OpenAI output must be a list")
    text_parts: list[str] = []
    for item in output_items:
        if not isinstance(item, dict):
            raise ValueError("OpenAI output items must be objects")
        if item.get("type") != "message":
            continue
        content_items = item.get("content")
        if not isinstance(content_items, list):
            raise ValueError("OpenAI message content must be a list")
        for content in content_items:
            if not isinstance(content, dict):
                raise ValueError("OpenAI message content items must be objects")
            if content.get("type") != "output_text":
                continue
            text = content.get("text")
            if not isinstance(text, str):
                raise ValueError("OpenAI output text must be a string")
            text_parts.append(text)
    output_text = "".join(text_parts)
    if not output_text:
        raise RuntimeError("openai_output_text_missing")
    raw = json.loads(output_text)
    if not isinstance(raw, dict):
        raise ValueError("OpenAI output must be a JSON object")
    validated = _validated_model_output(
        capability,
        context,
        raw,
        conservative_reference,
    )
    return (
        validated.model_dump(mode="json", by_alias=True),
        ATTESTED_AI_PROVIDER,
        model,
        False,
        None,
    )


def _validated_model_output(
    capability: str,
    context: dict[str, Any],
    raw: dict[str, Any],
    conservative_reference: dict[str, Any],
) -> APIModel:
    schema = AI_OUTPUT_SCHEMAS[capability]
    output = schema.model_validate(raw)
    serialized = output.model_dump(mode="json", by_alias=True)
    if capability == "environment_action":
        policy_input = EnvironmentActionContext.model_validate(context)
        if serialized["type"] not in policy_input.allowed_actions:
            raise ValueError("Environment policy selected an action outside the allowed set")
    if (
        capability == "patient_message"
        and context.get("uncertain")
        and not serialized["routeToStaff"]
    ):
        raise ValueError("Uncertain patient messages must route to staff")
    if capability == "coding_suggestions":
        allowed_codes = {
            (item["system"], item["code"])
            for item in conservative_reference["suggestions"]
        }
        proposed_codes = {
            (item["system"], item["code"]) for item in serialized["suggestions"]
        }
        if not proposed_codes <= allowed_codes:
            raise ValueError("Model proposed an unsupported billing code")
    if (
        capability == "pathology_summary"
        and serialized["urgency"] != conservative_reference["urgency"]
    ):
        raise ValueError("Model urgency conflicts with the source result")
    if capability == "patient_message":
        approved_sources = set(conservative_reference["source_instructions"])
        if not set(serialized["sourceInstructions"]) <= approved_sources:
            raise ValueError("Patient message cites an unapproved instruction")
    return output


async def run_ai(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    capability: str,
    context: dict[str, Any],
    patient_id: uuid.UUID | None,
    requested_by_user_id: uuid.UUID | None,
    minimum_necessary: bool = True,
    purpose_of_use: str = "care_operations",
    sensitivity: str | None = None,
    source_entity_type: str | None = None,
    source_entity_id: uuid.UUID | None = None,
    actor_role: str = "clinical_assistant",
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
        conservative_reference = deterministic_output(capability, context)
        validated = _validated_model_output(
            capability,
            context,
            raw,
            conservative_reference,
        )
    except (httpx.HTTPError, RuntimeError, TimeoutError, ValidationError, ValueError) as exc:
        fallback_used = True
        error = str(exc)[:500]
        conservative_reference = deterministic_output(capability, context)
        validated = _validated_model_output(
            capability,
            context,
            conservative_reference,
            conservative_reference,
        )
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
    output_content = validated.model_dump(mode="json", by_alias=True)
    input_hash = hashlib.sha256(canonical_input.encode()).hexdigest()
    output_hash = hash_json(output_content)
    resource_refs = _context_resource_refs(context)
    effective_sensitivity = sensitivity or ("restricted" if patient_id else "operational")
    input_metadata: dict[str, Any] = {
        "contextHash": input_hash,
        "contextKeys": sorted(str(key) for key in context),
        "resourceRefCount": len(resource_refs),
        "contentStored": False,
    }
    if purpose_of_use != "care_operations":
        input_metadata.update(
            {
                "purposeOfUse": purpose_of_use,
                "sensitivity": effective_sensitivity,
            }
        )
    session.add_all(
        [
            AIInput(
                organization_id=organization_id,
                ai_run_id=run.id,
                input_type="minimum_necessary_context",
                content_json=input_metadata,
                content_hash=input_hash,
                minimum_necessary=minimum_necessary,
                resource_refs_json=resource_refs,
                schema_version=1,
            ),
            AIOutput(
                organization_id=organization_id,
                ai_run_id=run.id,
                output_type=capability,
                content_json=output_content,
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
                source_entity_type=source_entity_type
                or ("patient" if patient_id else None),
                source_entity_id=source_entity_id or patient_id,
                detail_json={
                    "promptVersion": prompt.version,
                    "promptHash": prompt_hash,
                    "fallbackUsed": fallback_used,
                    "schemaValid": True,
                    "confidenceMeaning": "not_calibrated",
                    "purposeOfUse": purpose_of_use,
                    "sensitivity": effective_sensitivity,
                },
            ),
        ]
    )
    await record_domain_event(
        session,
        organization_id=organization_id,
        event_type="ai.run.completed",
        aggregate_type="ai_run",
        aggregate_id=run.id,
        aggregate_sequence=1,
        patient_id=patient_id,
        actor_kind="ai",
        actor_user_id=requested_by_user_id,
        actor_role=actor_role,
        occurred_at=recorded_at,
        payload={
            "capability": capability,
            "promptVersion": prompt.version,
            "promptHash": prompt_hash,
            "inputHash": input_hash,
            "outputHash": output_hash,
            "provider": provider,
            "model": model,
            "fallbackUsed": fallback_used,
            "schemaValid": True,
            "minimumNecessary": minimum_necessary,
            "latencyMs": elapsed_ms,
        },
        idempotency_key=f"ai-run:{run.id}:completed",
        sensitivity=effective_sensitivity,
        purpose_of_use=purpose_of_use,
    )
    await session.flush()
    return run, validated
