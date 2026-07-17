from __future__ import annotations

import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import domain_now
from .models import (
    Appeal,
    AppointmentReminder,
    Claim,
    ClaimEvent,
    ClaimLine,
    ClaimResponse,
    Coverage,
    Denial,
    EligibilityCheck,
    IntegrationEvent,
    Message,
    PatientBalance,
    Payment,
)


class EligibilityProvider(ABC):
    @abstractmethod
    async def check(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        patient_id: uuid.UUID,
        coverage: Coverage,
        appointment_id: uuid.UUID | None,
    ) -> EligibilityCheck: ...


class ClearinghouseProvider(ABC):
    @abstractmethod
    async def advance(self, session: AsyncSession, claim: Claim) -> Claim: ...


def eligibility_input_fingerprint(
    coverage: Coverage,
    appointment_id: uuid.UUID | None,
) -> str:
    """Identify the exact coverage inputs used for an eligibility response."""

    payload = {
        "appointmentId": str(appointment_id) if appointment_id else None,
        "groupNumber": coverage.group_number or None,
        "memberId": coverage.member_id,
        "payerName": coverage.payer_name,
        "planName": coverage.plan_name,
        "subscriberName": coverage.subscriber_name,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class MessagingProvider(ABC):
    @abstractmethod
    async def deliver_message(self, session: AsyncSession, message: Message) -> str: ...

    @abstractmethod
    async def deliver_reminder(
        self, session: AsyncSession, reminder: AppointmentReminder
    ) -> str: ...


class PaymentProvider(ABC):
    @abstractmethod
    async def settle(self, session: AsyncSession, payment: Payment) -> str: ...


class PathologyNetworkProvider(ABC):
    @abstractmethod
    async def acknowledge_order(
        self, session: AsyncSession, *, organization_id: uuid.UUID, order_id: uuid.UUID
    ) -> str: ...


class EPrescribingProvider(ABC):
    @abstractmethod
    async def transmit(
        self, session: AsyncSession, *, organization_id: uuid.UUID, order_id: uuid.UUID
    ) -> str: ...


class SimulatedEligibilityProvider(EligibilityProvider):
    async def check(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        patient_id: uuid.UUID,
        coverage: Coverage,
        appointment_id: uuid.UUID | None,
    ) -> EligibilityCheck:
        now = await domain_now(session, organization_id)
        input_fingerprint = eligibility_input_fingerprint(coverage, appointment_id)
        check = EligibilityCheck(
            organization_id=organization_id,
            patient_id=patient_id,
            coverage_id=coverage.id,
            appointment_id=appointment_id,
            status="active",
            requested_at=now,
            responded_at=now,
            deductible_remaining=Decimal("420.00"),
            copay=Decimal("45.00"),
            coinsurance_percent=Decimal("20.00"),
            response_json={
                "inputFingerprint": input_fingerprint,
                "networkStatus": "in_network",
                "specialistVisit": "covered",
                "priorAuthorizationRequired": False,
                "coverageSnapshot": {
                    "payerName": coverage.payer_name,
                    "planName": coverage.plan_name,
                    "memberId": coverage.member_id,
                    "groupNumber": coverage.group_number,
                    "subscriberName": coverage.subscriber_name,
                    "appointmentId": str(appointment_id) if appointment_id else None,
                },
            },
            provider="simulated_payer",
        )
        session.add(check)
        await session.flush()
        session.add(
            IntegrationEvent(
                organization_id=organization_id,
                provider="simulated_payer",
                direction="inbound",
                event_type="eligibility_response",
                entity_type="eligibility_check",
                entity_id=check.id,
                idempotency_key=f"eligibility:{check.id}",
                payload_json=check.response_json,
                status="processed",
            )
        )
        return check


class SimulatedClearinghouseProvider(ClearinghouseProvider):
    transitions = {
        "draft": "validated",
        "validated": "submitted",
        "submitted": "accepted",
        "accepted": "adjudicated",
        "adjudicated": "paid",
    }

    async def advance(self, session: AsyncSession, claim: Claim) -> Claim:
        old = claim.status
        new = self.transitions.get(old, old)
        if new == old:
            return claim
        now = await domain_now(session, claim.organization_id)
        claim.status = new
        if new == "submitted":
            claim.submitted_at = now
        elif new == "adjudicated":
            claim.adjudicated_at = now
            claim.allowed_amount = (claim.total_charge * Decimal("0.72")).quantize(Decimal("0.01"))
            claim.patient_responsibility = min(Decimal("85.00"), claim.allowed_amount)
            lines = (
                await session.scalars(
                    select(ClaimLine)
                    .where(
                        ClaimLine.claim_id == claim.id,
                        ClaimLine.organization_id == claim.organization_id,
                    )
                    .order_by(ClaimLine.line_number)
                )
            ).all()
            allocated = Decimal("0.00")
            for index, line in enumerate(lines):
                line.allowed_amount = (
                    claim.allowed_amount - allocated
                    if index == len(lines) - 1
                    else (claim.allowed_amount * line.charge_amount / claim.total_charge).quantize(
                        Decimal("0.01")
                    )
                )
                allocated += line.allowed_amount
        elif new == "paid":
            claim.paid_at = now
            claim.paid_amount = max(
                Decimal("0.00"), claim.allowed_amount - claim.patient_responsibility
            )
            lines = (
                await session.scalars(
                    select(ClaimLine)
                    .where(
                        ClaimLine.claim_id == claim.id,
                        ClaimLine.organization_id == claim.organization_id,
                    )
                    .order_by(ClaimLine.line_number)
                )
            ).all()
            allocated = Decimal("0.00")
            for index, line in enumerate(lines):
                line.paid_amount = (
                    claim.paid_amount - allocated
                    if index == len(lines) - 1
                    else (claim.paid_amount * line.allowed_amount / claim.allowed_amount).quantize(
                        Decimal("0.01")
                    )
                )
                allocated += line.paid_amount
            payment = await session.scalar(
                select(Payment).where(
                    Payment.claim_id == claim.id,
                    Payment.organization_id == claim.organization_id,
                    Payment.source == "payer",
                )
            )
            if payment is None:
                payment = Payment(
                    organization_id=claim.organization_id,
                    claim_id=claim.id,
                    patient_id=claim.patient_id,
                    source="payer",
                    amount=claim.paid_amount,
                    payment_method="835 electronic remittance",
                    reference=f"SIM-ERA-{claim.claim_number}",
                    status="settled",
                    received_at=now,
                )
                session.add(payment)
            else:
                payment.amount = claim.paid_amount
                payment.status = "settled"
                payment.received_at = now
            await self._recompute_patient_balance(session, claim, now)
            denial = await session.scalar(
                select(Denial).where(
                    Denial.claim_id == claim.id,
                    Denial.organization_id == claim.organization_id,
                )
            )
            if denial:
                appeal = await session.scalar(
                    select(Appeal).where(
                        Appeal.denial_id == denial.id,
                        Appeal.organization_id == claim.organization_id,
                    )
                )
                if appeal:
                    appeal.status = "won"
                    appeal.outcome = "paid"
                    appeal.recovered_amount = claim.paid_amount
            session.add(
                IntegrationEvent(
                    organization_id=claim.organization_id,
                    provider="simulated_remittance",
                    direction="inbound",
                    event_type="payment_settled",
                    entity_type="claim",
                    entity_id=claim.id,
                    idempotency_key=f"payment-settled:{claim.id}",
                    payload_json={
                        "allowedAmount": str(claim.allowed_amount),
                        "payerPaid": str(claim.paid_amount),
                        "patientResponsibility": str(claim.patient_responsibility),
                    },
                    status="processed",
                    occurred_at=now,
                )
            )
        session.add(
            ClaimEvent(
                organization_id=claim.organization_id,
                claim_id=claim.id,
                event_type=f"claim_{new}",
                from_status=old,
                to_status=new,
                occurred_at=now,
                actor_kind="simulated_clearinghouse",
                detail_json={"deterministic": True},
            )
        )
        session.add(
            ClaimResponse(
                organization_id=claim.organization_id,
                claim_id=claim.id,
                response_type="status",
                status_code=new.upper(),
                received_at=now,
                payload_json={"claimNumber": claim.claim_number, "status": new},
                provider="simulated_clearinghouse",
            )
        )
        await session.flush()
        return claim

    async def _recompute_patient_balance(
        self,
        session: AsyncSession,
        claim: Claim,
        now,
    ) -> PatientBalance:
        claims = (
            await session.scalars(
                select(Claim).where(
                    Claim.organization_id == claim.organization_id,
                    Claim.patient_id == claim.patient_id,
                    Claim.status.in_(["adjudicated", "paid"]),
                )
            )
        ).all()
        settled_patient_payments = (
            await session.scalars(
                select(Payment).where(
                    Payment.organization_id == claim.organization_id,
                    Payment.patient_id == claim.patient_id,
                    Payment.source == "patient",
                    Payment.status == "settled",
                )
            )
        ).all()
        responsibility = sum(
            (item.patient_responsibility for item in claims), start=Decimal("0.00")
        )
        patient_paid = sum(
            (item.amount for item in settled_patient_payments), start=Decimal("0.00")
        )
        outstanding = max(Decimal("0.00"), responsibility - patient_paid)
        balance = await session.scalar(
            select(PatientBalance).where(
                PatientBalance.patient_id == claim.patient_id,
                PatientBalance.organization_id == claim.organization_id,
            )
        )
        last_payment_at = max(
            (item.received_at for item in settled_patient_payments), default=None
        )
        if balance is None:
            balance = PatientBalance(
                organization_id=claim.organization_id,
                patient_id=claim.patient_id,
                current_balance=outstanding,
                last_statement_at=now,
                last_payment_at=last_payment_at,
                status="due" if outstanding else "current",
            )
            session.add(balance)
        else:
            balance.current_balance = outstanding
            balance.last_statement_at = now
            balance.last_payment_at = last_payment_at
            balance.status = "due" if outstanding else "current"
        return balance


class SimulatedMessagingProvider(MessagingProvider):
    async def deliver_message(self, session: AsyncSession, message: Message) -> str:
        reference = f"sim-msg-{str(message.id)[:12]}"
        session.add(
            IntegrationEvent(
                organization_id=message.organization_id,
                provider="simulated_messaging",
                direction="outbound",
                event_type="secure_message_delivered",
                entity_type="message",
                entity_id=message.id,
                idempotency_key=reference,
                payload_json={"status": "delivered"},
                status="processed",
            )
        )
        return reference

    async def deliver_reminder(self, session: AsyncSession, reminder: AppointmentReminder) -> str:
        reference = f"sim-reminder-{str(reminder.id)[:12]}"
        reminder.sent_at = await domain_now(session, reminder.organization_id)
        reminder.delivery_status = "delivered"
        reminder.provider_message_id = reference
        return reference


class SimulatedPaymentProvider(PaymentProvider):
    async def settle(self, session: AsyncSession, payment: Payment) -> str:
        payment.status = "settled"
        return f"sim-payment-{str(payment.id)[:12]}"


class _OrderAcknowledgementMixin:
    provider_name = "simulated_network"
    event_type = "order_acknowledged"

    async def _ack(
        self, session: AsyncSession, *, organization_id: uuid.UUID, order_id: uuid.UUID
    ) -> str:
        reference = f"{self.provider_name}-{str(order_id)[:12]}"
        acknowledged_at = await domain_now(session, organization_id)
        session.add(
            IntegrationEvent(
                organization_id=organization_id,
                provider=self.provider_name,
                direction="outbound",
                event_type=self.event_type,
                entity_type="order",
                entity_id=order_id,
                idempotency_key=reference,
                payload_json={"acknowledgedAt": acknowledged_at.isoformat()},
                status="processed",
            )
        )
        return reference


class SimulatedPathologyNetwork(_OrderAcknowledgementMixin, PathologyNetworkProvider):
    provider_name = "simulated_pathology"
    event_type = "pathology_order_acknowledged"

    async def acknowledge_order(
        self, session: AsyncSession, *, organization_id: uuid.UUID, order_id: uuid.UUID
    ) -> str:
        return await self._ack(session, organization_id=organization_id, order_id=order_id)


class SimulatedEPrescribingProvider(_OrderAcknowledgementMixin, EPrescribingProvider):
    provider_name = "simulated_eprescribing"
    event_type = "prescription_transmitted"

    async def transmit(
        self, session: AsyncSession, *, organization_id: uuid.UUID, order_id: uuid.UUID
    ) -> str:
        return await self._ack(session, organization_id=organization_id, order_id=order_id)


eligibility_provider: EligibilityProvider = SimulatedEligibilityProvider()
clearinghouse_provider: ClearinghouseProvider = SimulatedClearinghouseProvider()
messaging_provider: MessagingProvider = SimulatedMessagingProvider()
payment_provider: PaymentProvider = SimulatedPaymentProvider()
pathology_provider: PathologyNetworkProvider = SimulatedPathologyNetwork()
eprescribing_provider: EPrescribingProvider = SimulatedEPrescribingProvider()
