from __future__ import annotations

from pathlib import Path

import modal

ROOT = Path(__file__).parent

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(str(ROOT), frozen=True, uv_version="0.11.29")
    .add_local_dir(str(ROOT / "app"), remote_path="/root/app", copy=True)
)
app = modal.App("ambrosia-health-domain-api")
runtime_secret = modal.Secret.from_name("ambrosia-runtime")
openai_secret = modal.Secret.from_name("ambrosia-openai")


@app.function(
    image=image,
    secrets=[runtime_secret, openai_secret],
    timeout=300,
    max_containers=4,
)
@modal.asgi_app()
def api():
    from app.main import app as fastapi_app

    return fastapi_app


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
