from __future__ import annotations

from pathlib import Path

import modal

ROOT = Path(__file__).parent
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
MODEL_DIR = "/models/qwen2.5-0.5b-instruct"


def _download_model() -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
    )


image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(str(ROOT), frozen=True, uv_version="0.11.29")
    .add_local_dir(str(ROOT / "app"), remote_path="/root/app", copy=True)
)
model_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "accelerate==1.14.0",
        "safetensors==0.6.2",
        "torch==2.9.1",
        "transformers==4.57.6",
    )
    .run_function(_download_model, timeout=1200)
)
app = modal.App("ambrosia-health-domain-api")
runtime_secret = modal.Secret.from_name("ambrosia-runtime")
ai_internal_secret = modal.Secret.from_name("ambrosia-ai-internal")


@app.function(
    image=image,
    secrets=[runtime_secret],
    timeout=300,
    min_containers=1,
    max_containers=4,
    scaledown_window=1200,
)
@modal.asgi_app()
def api():
    from app.main import app as fastapi_app

    return fastapi_app


@app.cls(
    image=model_image,
    gpu="T4",
    timeout=120,
    startup_timeout=300,
    scaledown_window=900,
    max_containers=2,
)
class StructuredClinicalModel:
    """Small open-weights model; every output is revalidated by the domain boundary."""

    @modal.enter()
    def load(self) -> None:
        import torch
        from transformers import pipeline

        self.generator = pipeline(
            "text-generation",
            model=MODEL_DIR,
            tokenizer=MODEL_DIR,
            device=0,
            dtype=torch.float16,
        )

    @modal.method()
    def generate(
        self,
        capability: str,
        context: dict,
        schema: dict,
        conservative_reference: dict,
        prompt: dict,
    ) -> dict:
        import json

        system = (
            "You are a clinical documentation assistant operating only on synthetic demo data. "
            "Return one JSON object and no prose. Follow the supplied JSON Schema exactly. "
            "Do not invent diagnoses, medications, codes, or facts beyond the context and "
            "conservative reference. Start from conservativeReference and preserve every "
            "required key; change a value only when context explicitly supports a safer value. "
            "Preserve uncertainty and route unsafe ambiguity to staff. "
            f"Execute this versioned instruction: {prompt['template']}"
        )
        payload = {
            "capability": capability,
            "context": context,
            "jsonSchema": schema,
            "conservativeReference": conservative_reference,
            "promptVersion": prompt["version"],
            "promptSha256": prompt["sha256"],
        }
        result = self.generator(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(payload, sort_keys=True, default=str),
                },
            ],
            max_new_tokens=512,
            do_sample=False,
        )
        generated = result[0]["generated_text"]
        if isinstance(generated, list):
            text = generated[-1]["content"]
        else:
            text = generated
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model did not return a JSON object")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Model output must be a JSON object")
        return parsed


def _validated_model_output(
    capability: str,
    context: dict,
    raw: dict,
    conservative_reference: dict,
):
    from app.schemas import AI_OUTPUT_SCHEMAS

    schema = AI_OUTPUT_SCHEMAS[capability]
    output = schema.model_validate(raw)
    serialized = output.model_dump(mode="json", by_alias=True)
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


@app.function(image=image, timeout=180)
def structured_inference(
    capability: str, context: dict, prompt: dict
) -> dict:
    """Internal callable with the same schema, semantic, and fallback boundary as HTTP."""

    from app.ai import deterministic_output
    from app.schemas import AI_OUTPUT_SCHEMAS

    schema = AI_OUTPUT_SCHEMAS.get(capability)
    if schema is None or not isinstance(context, dict) or not isinstance(prompt, dict):
        raise ValueError("Invalid inference request")
    reference = deterministic_output(capability, context)
    try:
        raw = StructuredClinicalModel().generate.remote(
            capability,
            context,
            schema.model_json_schema(by_alias=True),
            reference,
            prompt,
        )
        output = _validated_model_output(capability, context, raw, reference)
    except Exception:
        output = schema.model_validate(reference)
    return output.model_dump(mode="json", by_alias=True)


async def _inference_http(request, response) -> dict:
    import hashlib
    import hmac
    import json
    import os

    from fastapi import HTTPException

    from app.ai import deterministic_output
    from app.schemas import AI_OUTPUT_SCHEMAS

    supplied_secret = request.headers.get("X-Ambrosia-Internal", "")
    expected_secret = os.environ.get("MODAL_INTERNAL_AUTH_SECRET", "")
    if not expected_secret or not hmac.compare_digest(supplied_secret, expected_secret):
        raise HTTPException(status_code=404, detail="Not found")
    raw_body = await request.body()
    if len(raw_body) > 64_000:
        raise HTTPException(status_code=413, detail="Inference request exceeds 64 KB")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid inference request") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid inference request")
    capability = payload.get("capability")
    context = payload.get("context", {})
    prompt = payload.get("prompt", {})
    schema = AI_OUTPUT_SCHEMAS.get(capability)
    if (
        schema is None
        or not isinstance(context, dict)
        or not isinstance(prompt, dict)
        or not isinstance(prompt.get("version"), str)
        or not isinstance(prompt.get("template"), str)
        or not isinstance(prompt.get("sha256"), str)
        or len(prompt["template"]) > 4_000
        or len(prompt["version"]) > 64
        or len(prompt["sha256"]) != 64
    ):
        raise HTTPException(status_code=422, detail="Invalid inference request")
    actual_prompt_hash = hashlib.sha256(prompt["template"].encode()).hexdigest()
    if not hmac.compare_digest(actual_prompt_hash, prompt["sha256"]):
        raise HTTPException(status_code=422, detail="Prompt hash does not match its template")
    reference = deterministic_output(capability, context)
    try:
        raw = await StructuredClinicalModel().generate.remote.aio(
            capability,
            context,
            schema.model_json_schema(by_alias=True),
            reference,
            prompt,
        )
        output = _validated_model_output(capability, context, raw, reference)
        response.headers["X-Ambrosia-AI-Provider"] = "modal_open_weights"
        response.headers["X-Ambrosia-AI-Model"] = f"{MODEL_ID}@{MODEL_REVISION}"
        response.headers["X-Ambrosia-AI-Fallback"] = "false"
    except Exception as exc:
        # Never let model cold starts, resource pressure, or malformed JSON block care work.
        print(f"structured inference fallback: {capability} ({type(exc).__name__})")
        output = schema.model_validate(deterministic_output(capability, context))
        response.headers["X-Ambrosia-AI-Provider"] = "modal_deterministic_fallback"
        response.headers["X-Ambrosia-AI-Model"] = "ambrosia-fixture-2026.1"
        response.headers["X-Ambrosia-AI-Fallback"] = "true"
        response.headers["X-Ambrosia-AI-Error-Class"] = type(exc).__name__
    response.headers["X-Ambrosia-AI-Prompt-Version"] = prompt["version"]
    response.headers["X-Ambrosia-AI-Prompt-Hash"] = prompt["sha256"]
    return output.model_dump(mode="json", by_alias=True)


def _build_inference_app():
    """Build the HTTP boundary without importing FastAPI in the GPU model image."""

    from fastapi import FastAPI, Request, Response

    async def inference_route(request, response):
        return await _inference_http(request, response)

    # FastAPI discovers its special Request/Response injections from concrete
    # annotations. Assign them here because postponed local annotations would be
    # unresolved strings and become required query parameters instead.
    inference_route.__annotations__ = {
        "request": Request,
        "response": Response,
        "return": dict,
    }
    inference_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    inference_app.add_api_route("/", inference_route, methods=["POST"])
    return inference_app


@app.function(image=image, secrets=[ai_internal_secret], timeout=180)
@modal.asgi_app(label="structured-inference")
def structured_inference_webhook():
    """Authenticated, size-bounded HTTP adapter consumed by `MODAL_AI_URL`."""

    return _build_inference_app()


@app.function(
    image=image,
    secrets=[runtime_secret],
    schedule=modal.Cron("*/5 * * * *"),
    timeout=120,
)
def durable_workflow_poller() -> dict[str, str]:
    """Scheduled wake-up boundary; durable workflow state remains in Neon, never Modal Queue."""

    import asyncio

    async def poll() -> dict[str, str]:
        from sqlalchemy import select

        from app.database import SessionLocal
        from app.models import AppointmentReminder, Task, utcnow
        from app.providers import messaging_provider

        delivered = 0
        escalated = 0
        async with SessionLocal() as session:
            reminders = (
                await session.scalars(
                    select(AppointmentReminder).where(
                        AppointmentReminder.delivery_status == "scheduled",
                        AppointmentReminder.scheduled_for <= utcnow(),
                    )
                )
            ).all()
            for reminder in reminders:
                await messaging_provider.deliver_reminder(session, reminder)
                delivered += 1
            tasks = (
                await session.scalars(
                    select(Task).where(
                        Task.status.in_(["open", "in_progress"]),
                        Task.due_at.is_not(None),
                        Task.due_at <= utcnow(),
                        Task.priority != "urgent",
                    )
                )
            ).all()
            for task in tasks:
                task.priority = "urgent"
                escalated += 1
            await session.commit()
        return {
            "status": "processed",
            "store": "neon",
            "remindersDelivered": str(delivered),
            "tasksEscalated": str(escalated),
        }

    return asyncio.run(poll())
