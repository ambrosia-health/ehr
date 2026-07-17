from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DemoScenario, utcnow


async def domain_now(session: AsyncSession, organization_id: uuid.UUID) -> datetime:
    """Use the durable scenario clock for synthetic tenants and wall time elsewhere."""

    scenario_time = await session.scalar(
        select(DemoScenario.current_time).where(
            DemoScenario.organization_id == organization_id,
            DemoScenario.active.is_(True),
        )
    )
    value = scenario_time or utcnow()
    return value.replace(tzinfo=value.tzinfo or UTC)
