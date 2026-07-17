from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_session
from .models import Membership, Organization, PatientAccount, Role, User


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    display_name: str
    persona_key: str
    roles: frozenset[str]
    is_presenter: bool
    patient_id: uuid.UUID | None = None
    presenter_actor_id: uuid.UUID | None = None

    def has_any_role(self, allowed: set[str]) -> bool:
        return bool(self.roles & allowed)


class DemoIdentityProvider:
    """Replaceable demo identity boundary; production OIDC can implement the same lookups."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(
            settings.session_secret, salt="ambrosia-session-v1"
        )

    def issue(self, user: User, *, presenter_actor_id: uuid.UUID | None = None) -> str:
        payload = {"sub": str(user.id), "org": str(user.organization_id)}
        if presenter_actor_id is not None:
            payload["presenter_actor"] = str(presenter_actor_id)
        return self.serializer.dumps(payload)

    def verify(self, token: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
        try:
            data = self.serializer.loads(token, max_age=self.settings.session_ttl_seconds)
            presenter_actor = data.get("presenter_actor")
            return (
                uuid.UUID(data["sub"]),
                uuid.UUID(data["org"]),
                uuid.UUID(presenter_actor) if presenter_actor else None,
            )
        except (BadSignature, SignatureExpired, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
            ) from exc


async def _principal_for_user(
    session: AsyncSession,
    user: User,
    *,
    presenter_actor_id: uuid.UUID | None = None,
) -> Principal:
    role_names = (
        await session.scalars(
            select(Role.name)
            .join(Membership, Membership.role_id == Role.id)
            .where(
                Membership.user_id == user.id,
                Membership.organization_id == user.organization_id,
            )
        )
    ).all()
    patient_id = await session.scalar(
        select(PatientAccount.patient_id).where(
            PatientAccount.user_id == user.id,
            PatientAccount.organization_id == user.organization_id,
        )
    )
    return Principal(
        user_id=user.id,
        organization_id=user.organization_id,
        display_name=user.display_name,
        persona_key=user.persona_key or str(user.id),
        roles=frozenset(role_names),
        is_presenter=presenter_actor_id is not None,
        patient_id=patient_id,
        presenter_actor_id=presenter_actor_id,
    )


async def principal_from_persona(
    persona_key: str, session: AsyncSession, *, require_active: bool = True
) -> Principal:
    user = await session.scalar(
        select(User)
        .join(
            Organization,
            (Organization.id == User.organization_id)
            & (Organization.slug == "ambrosia-dermatology")
            & (Organization.demo_mode.is_(True)),
        )
        .where(User.persona_key == persona_key)
    )
    if user is None or (require_active and not user.is_active):
        raise HTTPException(status_code=401, detail="Unknown demo persona")
    return await _principal_for_user(session, user)


async def get_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    # Explicit test/demo header is intentionally unavailable outside demo mode.
    persona_key = request.headers.get("X-Demo-Persona")
    if persona_key and settings.demo_mode and settings.environment.lower() == "test":
        return await principal_from_persona(persona_key, session)

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    user_id, organization_id, presenter_actor_id = DemoIdentityProvider(settings).verify(token)
    user = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    if presenter_actor_id is not None:
        presenter_actor = await session.scalar(
            select(User).where(
                User.id == presenter_actor_id,
                User.organization_id == organization_id,
                User.is_active.is_(True),
                User.is_presenter.is_(True),
            )
        )
        if presenter_actor is None:
            raise HTTPException(status_code=401, detail="Presenter delegation is no longer valid")
    return await _principal_for_user(session, user, presenter_actor_id=presenter_actor_id)


def require_roles(*roles: str):
    allowed = set(roles)

    async def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.has_any_role(allowed):
            raise HTTPException(
                status_code=403, detail=f"Requires one of: {', '.join(sorted(allowed))}"
            )
        return principal

    return dependency


def enforce_patient_scope(principal: Principal, patient_id: uuid.UUID) -> None:
    if "patient" in principal.roles and principal.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Patients may only access their own record")


SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
