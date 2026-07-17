from __future__ import annotations

from types import SimpleNamespace

import httpx
from sqlalchemy import select

from app import ai
from app.ai import deterministic_output, run_ai
from app.database import SessionLocal
from app.models import AIInput, AIOutput, AIRun, DemoScenario, PromptVersion, ProvenanceRecord
from app.schemas import AI_OUTPUT_SCHEMAS
from app.seed import canonical_ids


async def test_all_deterministic_capabilities_validate_and_persist_provenance(
    monkeypatch,
) -> None:
    for capability, schema in AI_OUTPUT_SCHEMAS.items():
        schema.model_validate(
            deterministic_output(capability, {"patientName": "Synthetic Patient"})
        )

    async def timeout(_capability: str, _context: dict, **_prompt) -> dict:
        raise httpx.TimeoutException("forced evaluation timeout")

    monkeypatch.setattr(ai, "_live_inference", timeout)
    ids = canonical_ids()
    async with SessionLocal() as session:
        run, output = await run_ai(
            session,
            organization_id=ids["organization_id"],
            capability="ambient_note",
            context={"patientName": "Sarah Mitchell", "transcript": "Synthetic transcript"},
            patient_id=ids["sarah_patient_id"],
            requested_by_user_id=None,
        )
        await session.commit()
        prompt = await session.scalar(
            select(PromptVersion).where(PromptVersion.id == run.prompt_version_id)
        )
        stored_input = await session.scalar(select(AIInput).where(AIInput.ai_run_id == run.id))
        stored_output = await session.scalar(select(AIOutput).where(AIOutput.ai_run_id == run.id))
        provenance = await session.scalar(
            select(ProvenanceRecord).where(ProvenanceRecord.ai_run_id == run.id)
        )
    assert output.subjective
    assert run.provider == "deterministic_fallback"
    assert run.fallback_used is True
    assert "forced evaluation timeout" in (run.error_message or "")
    assert prompt and prompt.version == "2026.1"
    assert stored_input and len(stored_input.content_hash) == 64
    assert stored_output and stored_output.schema_valid is True
    assert provenance and provenance.detail_json["schemaValid"] is True


async def test_invalid_live_schema_falls_back_without_breaking_workflow(monkeypatch) -> None:
    async def invalid_schema(_capability: str, _context: dict, **_prompt) -> dict:
        return {"not": "the required schema"}

    monkeypatch.setattr(ai, "_live_inference", invalid_schema)
    ids = canonical_ids()
    async with SessionLocal() as session:
        run, output = await run_ai(
            session,
            organization_id=ids["organization_id"],
            capability="pathology_summary",
            context={"patientName": "Sarah Mitchell"},
            patient_id=ids["sarah_patient_id"],
            requested_by_user_id=None,
        )
        await session.commit()
        persisted = await session.scalar(select(AIRun).where(AIRun.id == run.id))
    assert output.urgency == "routine"
    assert persisted and persisted.status == "completed"
    assert persisted.fallback_used is True
    assert persisted.error_message


async def test_attested_modal_model_output_is_recorded_as_live(monkeypatch) -> None:
    async def live_model(capability: str, context: dict, **_prompt):
        return (
            deterministic_output(capability, context),
            "modal_open_weights",
            "Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775",
            False,
            None,
        )

    monkeypatch.setattr(ai, "_live_inference", live_model)
    ids = canonical_ids()
    async with SessionLocal() as session:
        run, output = await run_ai(
            session,
            organization_id=ids["organization_id"],
            capability="chart_summary",
            context={"patientName": "Sarah Mitchell"},
            patient_id=ids["sarah_patient_id"],
            requested_by_user_id=None,
        )
        await session.commit()
        scenario = await session.scalar(
            select(DemoScenario).where(
                DemoScenario.organization_id == ids["organization_id"]
            )
        )
    assert output.headline.startswith("Sarah Mitchell")
    assert run.provider == "modal_open_weights"
    assert run.model.endswith("@7ae557604adf67be50417f59c2c2f167def9a775")
    assert run.fallback_used is False
    assert run.error_message is None
    assert scenario and scenario.fallback_indicator is False


async def test_missing_remote_attestation_is_never_recorded_as_live(monkeypatch) -> None:
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                headers={"X-Ambrosia-AI-Fallback": "false"},
                json=deterministic_output("chart_summary", {"patientName": "Sarah Mitchell"}),
            )

    monkeypatch.setattr(
        ai,
        "get_settings",
        lambda: SimpleNamespace(
            modal_ai_url="https://modal.invalid/inference",
            modal_internal_auth_secret="test-secret",
            ai_timeout_seconds=1,
        ),
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    _output, provider, model, fallback_used, error = await ai._live_inference(
        "chart_summary",
        {"patientName": "Sarah Mitchell"},
        prompt_version="2026.1",
        prompt_template="Return schema-valid JSON.",
        prompt_hash="0" * 64,
    )
    assert provider == "modal_unverified_adapter"
    assert model == "unreported"
    assert fallback_used is True
    assert error == "remote_model_attestation_missing_or_untrusted"
