from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import run_ai
from .learning import environment_run_view
from .models import AIRun
from .schemas import EnvironmentAction, EnvironmentActionContext


async def choose_environment_action(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> tuple[EnvironmentAction, AIRun]:
    """Choose one typed action from the current synthetic run observation."""

    view = await environment_run_view(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    if view["run"]["status"] != "running":
        raise HTTPException(status_code=409, detail="Environment run is terminal")

    policy_input = EnvironmentActionContext.model_validate(
        {
            "observation": view["observation"],
            "allowedActions": view["allowed_actions"],
        }
    )
    ai_run, output = await run_ai(
        session,
        organization_id=organization_id,
        capability="environment_action",
        context=policy_input.model_dump(mode="json", by_alias=True),
        patient_id=None,
        requested_by_user_id=requested_by_user_id,
        purpose_of_use="synthetic_evaluation",
        sensitivity="synthetic",
        source_entity_type="environment_run",
        source_entity_id=run_id,
        actor_role="environment_agent",
    )
    if not isinstance(output, EnvironmentAction):
        raise RuntimeError("Environment policy returned an unexpected output type")
    return output, ai_run
