from __future__ import annotations

import asyncio
import hashlib

from .ai import (
    ATTESTED_AI_MODEL,
    ATTESTED_AI_PROVIDER,
    ATTESTED_AI_REASONING_EFFORT,
    _live_inference,
)


async def attest() -> None:
    prompt = "Ambrosia chart_summary prompt. Use minimum necessary context and return schema-valid JSON."
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    output, provider, model, fallback_used, error = await _live_inference(
        "chart_summary",
        {"patientName": "Synthetic readiness patient"},
        prompt_version="2026.1",
        prompt_template=prompt,
        prompt_hash=prompt_hash,
    )
    if (
        provider != ATTESTED_AI_PROVIDER
        or model != ATTESTED_AI_MODEL
        or fallback_used
        or error
        or not output.get("headline")
        or not output.get("activeConcerns")
    ):
        raise RuntimeError("OpenAI attestation returned an unexpected result")
    print(
        f"OpenAI {model} with {ATTESTED_AI_REASONING_EFFORT} reasoning "
        "returned schema- and semantic-valid output."
    )


def main() -> None:
    asyncio.run(attest())


if __name__ == "__main__":
    main()
