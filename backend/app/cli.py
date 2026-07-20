from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy import func, select, text

from alembic import command

from .config import get_settings
from .database import Base, SessionLocal
from .models import (
    AIOutput,
    AIRun,
    AutomationPolicy,
    Claim,
    ClaimLine,
    Consent,
    DiagnosticResult,
    DomainEvent,
    EncounterNote,
    EpisodeDefinition,
    EpisodeEventLink,
    EpisodeInstance,
    IntegrationEvent,
    Lesion,
    MessageDraft,
    NoteVersion,
    Order,
    Organization,
    Patient,
    PatientBalance,
    Payment,
    PolicyVersion,
    Procedure,
    ProposedAction,
    ProvenanceRecord,
    SimulationScenario,
    Specimen,
    WorkflowRun,
)
from .seed import (
    DEMO_ORG_SLUG,
    canonical_ids,
    reset_demo_database,
    seed_database,
)


def alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


async def seed() -> None:
    async with SessionLocal() as session:
        ids = await seed_database(session)
    print(f"Seeded canonical synthetic organization {ids['organization_id']}")


async def reset() -> None:
    settings = get_settings()
    if settings.environment.lower() in {"production", "prod"} and not settings.allow_demo_reset:
        raise RuntimeError(
            "Production reset refused; set ALLOW_SYNTHETIC_DEMO_RESET=true only for a synthetic deployment"
        )
    async with SessionLocal() as session:
        ids = await reset_demo_database(session)
    print(f"Reset only {DEMO_ORG_SLUG}; restored organization {ids['organization_id']}")


async def verify() -> None:
    async with SessionLocal() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
        )
        if organization is None:
            raise RuntimeError("Canonical synthetic organization is not seeded")
        patient_count = int(
            await session.scalar(
                select(func.count(Patient.id)).where(Patient.organization_id == organization.id)
            )
            or 0
        )
        if not 31 <= patient_count <= 51:
            raise RuntimeError(f"Expected 31–51 synthetic patients, found {patient_count}")
        missing = sorted(
            table
            for table in {
                "organizations",
                "patients",
                "encounters",
                "encounter_notes",
                "lesions",
                "diagnostic_results",
                "claims",
                "claim_events",
                "ai_runs",
                "proposed_actions",
                "approvals",
                "audit_events",
                "domain_events",
                "event_delivery_checkpoints",
                "episode_definitions",
                "episode_instances",
                "episode_event_links",
                "observation_manifests",
                "observation_resources",
                "decision_points",
                "action_attempts",
                "outcome_observations",
                "policy_versions",
                "simulation_scenarios",
                "dataset_releases",
                "environment_runs",
                "environment_steps",
                "reward_components",
                "dataset_release_items",
            }
            if table not in Base.metadata.tables
        )
        if missing:
            raise RuntimeError(f"Metadata is missing required tables: {', '.join(missing)}")
        ids = canonical_ids()
        sarah = await session.scalar(
            select(Patient).where(
                Patient.id == ids["sarah_patient_id"],
                Patient.organization_id == organization.id,
            )
        )
        lesion = await session.scalar(
            select(Lesion).where(
                Lesion.id == ids["sarah_lesion_id"],
                Lesion.patient_id == ids["sarah_patient_id"],
                Lesion.organization_id == organization.id,
            )
        )
        note = await session.scalar(
            select(EncounterNote).where(
                EncounterNote.id == ids["sarah_note_id"],
                EncounterNote.encounter_id == ids["sarah_encounter_id"],
                EncounterNote.organization_id == organization.id,
            )
        )
        if not sarah or not lesion or not note:
            raise RuntimeError(
                "Sarah's canonical patient, lesion, encounter, and note chain is incomplete"
            )
        learning_definition = await session.scalar(
            select(EpisodeDefinition).where(
                EpisodeDefinition.id == ids["learning_episode_definition_id"],
                EpisodeDefinition.organization_id == organization.id,
                EpisodeDefinition.status == "released",
            )
        )
        learning_episode = await session.scalar(
            select(EpisodeInstance).where(
                EpisodeInstance.id == ids["learning_episode_id"],
                EpisodeInstance.organization_id == organization.id,
                EpisodeInstance.patient_id == sarah.id,
                EpisodeInstance.source_kind == "synthetic",
            )
        )
        learning_scenario = await session.scalar(
            select(SimulationScenario).where(
                SimulationScenario.id == ids["learning_scenario_id"],
                SimulationScenario.organization_id == organization.id,
                SimulationScenario.episode_definition_id
                == ids["learning_episode_definition_id"],
                SimulationScenario.synthetic_only.is_(True),
                SimulationScenario.status == "released",
            )
        )
        if not learning_definition or not learning_episode or not learning_scenario:
            raise RuntimeError(
                "Canonical learning definition, episode, or synthetic scenario is incomplete"
            )
        linked_event_count = int(
            await session.scalar(
                select(func.count(EpisodeEventLink.id)).where(
                    EpisodeEventLink.organization_id == organization.id,
                    EpisodeEventLink.episode_instance_id == learning_episode.id,
                )
            )
            or 0
        )
        learning_event_count = int(
            await session.scalar(
                select(func.count(DomainEvent.id)).where(
                    DomainEvent.organization_id == organization.id,
                    DomainEvent.patient_id == sarah.id,
                    DomainEvent.correlation_id == str(learning_episode.id),
                )
            )
            or 0
        )
        if linked_event_count != 3 or learning_event_count != 3:
            raise RuntimeError(
                "Canonical learning episode must start with three ordered source events"
            )
        policies = list(
            await session.scalars(
                select(AutomationPolicy).where(
                    AutomationPolicy.organization_id == organization.id
                )
            )
        )
        versioned_policy_ids = dict(
            (
                await session.execute(
                    select(PolicyVersion.automation_policy_id, PolicyVersion.id).where(
                        PolicyVersion.organization_id == organization.id,
                        PolicyVersion.status == "released",
                        PolicyVersion.version == 1,
                    )
                )
            ).all()
        )
        if any(
            policy.current_version_id != versioned_policy_ids.get(policy.id)
            for policy in policies
        ):
            raise RuntimeError("Every canonical automation policy must point to released version 1")
        version_count = int(
            await session.scalar(
                select(func.count(NoteVersion.id)).where(
                    NoteVersion.note_id == note.id,
                    NoteVersion.organization_id == organization.id,
                )
            )
            or 0
        )
        if version_count != note.current_version or version_count < 1:
            raise RuntimeError(
                f"Sarah note version invariant failed: header={note.current_version}, rows={version_count}"
            )
        actions = (
            await session.scalars(
                select(ProposedAction).where(
                    ProposedAction.organization_id == organization.id,
                    ProposedAction.patient_id == sarah.id,
                    ProposedAction.entity_id.in_([note.id, ids["sarah_encounter_id"]]),
                )
            )
        ).all()
        action_types = {action.action_type for action in actions}
        expected_actions = {
            "sign_note",
            "confirm_biopsy_consent",
            "create_shave_biopsy",
            "create_pathology_order",
            "create_specimen",
            "apply_coding",
            "send_aftercare",
            "create_pathology_task",
        }
        if action_types != expected_actions:
            raise RuntimeError(
                "Sarah proposed-action invariant failed: "
                f"missing={sorted(expected_actions - action_types)}, "
                f"unexpected={sorted(action_types - expected_actions)}"
            )
        note_run = await session.scalar(
            select(AIRun).where(
                AIRun.id == note.ai_run_id,
                AIRun.organization_id == organization.id,
            )
        )
        note_output = await session.scalar(
            select(AIOutput).where(
                AIOutput.ai_run_id == note.ai_run_id,
                AIOutput.organization_id == organization.id,
                AIOutput.schema_valid.is_(True),
            )
        )
        if note_run is None or note_run.capability != "ambient_note" or note_output is None:
            raise RuntimeError(
                "Sarah note provenance is not aligned to a schema-valid ambient-note run"
            )
        expected_action_capabilities = {
            "apply_coding": "coding_suggestions",
            "send_aftercare": "patient_message",
        }
        for action in actions:
            action_run = await session.scalar(
                select(AIRun).where(
                    AIRun.id == action.ai_run_id,
                    AIRun.organization_id == organization.id,
                )
            )
            expected_capability = expected_action_capabilities.get(
                action.action_type, "ambient_note"
            )
            if action_run is None or action_run.capability != expected_capability:
                raise RuntimeError(
                    f"Sarah {action.action_type} provenance expected {expected_capability}"
                )
        aftercare_draft = await session.scalar(
            select(MessageDraft)
            .join(
                AIRun,
                (AIRun.id == MessageDraft.ai_run_id) & (AIRun.organization_id == organization.id),
            )
            .where(
                MessageDraft.organization_id == organization.id,
                MessageDraft.conversation_id == ids["sarah_conversation_id"],
                AIRun.capability == "patient_message",
            )
        )
        if aftercare_draft is None:
            raise RuntimeError("Sarah's aftercare AI draft is missing")
        draft_run = await session.scalar(
            select(AIRun).where(
                AIRun.id == aftercare_draft.ai_run_id,
                AIRun.organization_id == organization.id,
            )
        )
        if draft_run is None or draft_run.capability != "patient_message":
            raise RuntimeError("Sarah's aftercare draft is not linked to a patient-message run")
        if aftercare_draft.status == "approved":
            approval_provenance = await session.scalar(
                select(ProvenanceRecord).where(
                    ProvenanceRecord.organization_id == organization.id,
                    ProvenanceRecord.source_entity_type == "message_draft",
                    ProvenanceRecord.source_entity_id == aftercare_draft.id,
                    ProvenanceRecord.activity == "human_approved_ai_draft",
                )
            )
            if approval_provenance is None:
                raise RuntimeError("Approved AI aftercare is missing human-approval provenance")
        consent = await session.scalar(
            select(Consent).where(
                Consent.organization_id == organization.id,
                Consent.patient_id == sarah.id,
                Consent.encounter_id == ids["sarah_encounter_id"],
                Consent.consent_type == "shave_biopsy",
                Consent.revoked_at.is_(None),
            )
        )
        if (
            not consent
            or not consent.accepted_by_name
            or not consent.signature_text
            or not consent.version
        ):
            raise RuntimeError("Sarah's active, signed, versioned biopsy consent is incomplete")

        result = await session.scalar(
            select(DiagnosticResult)
            .where(
                DiagnosticResult.organization_id == organization.id,
                DiagnosticResult.patient_id == sarah.id,
                DiagnosticResult.lesion_id != ids["sarah_lesion_id"],
            )
            .order_by(DiagnosticResult.resulted_at)
        )
        if result is None:
            raise RuntimeError("Sarah has no durable historical pathology result chain")
        procedure = await session.scalar(
            select(Procedure).where(
                Procedure.id == result.procedure_id,
                Procedure.organization_id == organization.id,
                Procedure.patient_id == sarah.id,
                Procedure.lesion_id == result.lesion_id,
            )
        )
        order = await session.scalar(
            select(Order).where(
                Order.id == result.order_id,
                Order.organization_id == organization.id,
                Order.patient_id == sarah.id,
                Order.lesion_id == result.lesion_id,
            )
        )
        specimen = await session.scalar(
            select(Specimen).where(
                Specimen.id == result.specimen_id,
                Specimen.organization_id == organization.id,
                Specimen.patient_id == sarah.id,
                Specimen.lesion_id == result.lesion_id,
                Specimen.procedure_id == result.procedure_id,
                Specimen.order_id == result.order_id,
            )
        )
        result_lesion = await session.scalar(
            select(Lesion).where(
                Lesion.id == result.lesion_id,
                Lesion.patient_id == sarah.id,
                Lesion.organization_id == organization.id,
            )
        )
        if not all([procedure, order, specimen, result_lesion]):
            raise RuntimeError(
                "Sarah pathology linkage invariant failed across lesion/procedure/order/specimen/result"
            )
        if (
            result_lesion.anatomical_location != "right anterior thigh"
            or specimen.body_site != "right anterior thigh"
        ):
            raise RuntimeError(
                "Sarah's historical pathology chain is not the intended 2022 thigh lesion"
            )
        current_result = await session.scalar(
            select(DiagnosticResult).where(
                DiagnosticResult.organization_id == organization.id,
                DiagnosticResult.patient_id == sarah.id,
                DiagnosticResult.lesion_id == ids["sarah_lesion_id"],
            )
        )
        if current_result is not None:
            current_chain_count = int(
                await session.scalar(
                    select(func.count(Specimen.id)).where(
                        Specimen.organization_id == organization.id,
                        Specimen.id == current_result.specimen_id,
                        Specimen.order_id == current_result.order_id,
                        Specimen.procedure_id == current_result.procedure_id,
                        Specimen.lesion_id == ids["sarah_lesion_id"],
                    )
                )
                or 0
            )
            if current_chain_count != 1:
                raise RuntimeError("Sarah's current shoulder pathology linkage is incomplete")
        cohort_pathology = await session.scalar(
            select(DiagnosticResult.id).where(
                DiagnosticResult.organization_id == organization.id,
                DiagnosticResult.patient_id != sarah.id,
                DiagnosticResult.status == "final",
            )
        )
        if cohort_pathology is None:
            raise RuntimeError("Seeded cohort pathology safety queue is missing")

        claims = (
            await session.scalars(select(Claim).where(Claim.organization_id == organization.id))
        ).all()
        for claim in claims:
            lines = (
                await session.scalars(
                    select(ClaimLine).where(
                        ClaimLine.organization_id == organization.id,
                        ClaimLine.claim_id == claim.id,
                    )
                )
            ).all()
            line_charge = sum((line.charge_amount for line in lines), start=0)
            line_allowed = sum((line.allowed_amount for line in lines), start=0)
            line_paid = sum((line.paid_amount for line in lines), start=0)
            if line_charge != claim.total_charge:
                raise RuntimeError(
                    f"Claim {claim.claim_number} line charges {line_charge} != header {claim.total_charge}"
                )
            if not 0 <= claim.paid_amount <= claim.allowed_amount <= claim.total_charge:
                raise RuntimeError(f"Claim {claim.claim_number} violates paid <= allowed <= charge")
            if line_allowed != claim.allowed_amount or line_paid != claim.paid_amount:
                raise RuntimeError(
                    f"Claim {claim.claim_number} line allowed/paid amounts do not reconcile"
                )
            if claim.status == "paid":
                payer_payments = list(
                    await session.scalars(
                        select(Payment).where(
                            Payment.organization_id == organization.id,
                            Payment.claim_id == claim.id,
                            Payment.source == "payer",
                            Payment.status == "settled",
                        )
                    )
                )
                payment_total = sum((payment.amount for payment in payer_payments), start=0)
                if payment_total != claim.paid_amount:
                    raise RuntimeError(
                        f"Claim {claim.claim_number} payer payments do not match paid amount"
                    )
        balances = (
            await session.scalars(
                select(PatientBalance).where(PatientBalance.organization_id == organization.id)
            )
        ).all()
        for balance in balances:
            responsibility = sum(
                (
                    claim.patient_responsibility
                    for claim in claims
                    if claim.patient_id == balance.patient_id
                    and claim.status in {"adjudicated", "paid"}
                ),
                start=0,
            )
            patient_paid = sum(
                (
                    payment.amount
                    for payment in await session.scalars(
                        select(Payment).where(
                            Payment.organization_id == organization.id,
                            Payment.patient_id == balance.patient_id,
                            Payment.source == "patient",
                            Payment.status == "settled",
                        )
                    )
                ),
                start=0,
            )
            if balance.current_balance != max(0, responsibility - patient_paid):
                raise RuntimeError("Patient aggregate balance does not reconcile")

        tenant_edges = [
            ("appointments", "patients", "patient_id"),
            ("appointments", "providers", "provider_id"),
            ("appointments", "locations", "location_id"),
            ("encounters", "appointments", "appointment_id"),
            ("encounters", "patients", "patient_id"),
            ("encounter_notes", "encounters", "encounter_id"),
            ("clinical_images", "file_records", "file_record_id"),
            ("procedures", "encounters", "encounter_id"),
            ("orders", "encounters", "encounter_id"),
            ("specimens", "orders", "order_id"),
            ("diagnostic_results", "specimens", "specimen_id"),
            ("claims", "encounters", "encounter_id"),
            ("claim_lines", "claims", "claim_id"),
            ("messages", "conversations", "conversation_id"),
        ]
        for child, parent, foreign_key in tenant_edges:
            mismatch_count = int(
                await session.scalar(
                    text(
                        f"SELECT COUNT(*) FROM {child} child "
                        f"JOIN {parent} parent ON parent.id = child.{foreign_key} "
                        "WHERE child.organization_id <> parent.organization_id"
                    )
                )
                or 0
            )
            if mismatch_count:
                raise RuntimeError(f"Tenant mismatch across {child}.{foreign_key} -> {parent}.id")
        duplicate_workflow_key = await session.scalar(
            select(WorkflowRun.idempotency_key)
            .group_by(WorkflowRun.organization_id, WorkflowRun.idempotency_key)
            .having(func.count(WorkflowRun.id) > 1)
        )
        duplicate_integration_key = await session.scalar(
            select(IntegrationEvent.idempotency_key)
            .group_by(IntegrationEvent.organization_id, IntegrationEvent.idempotency_key)
            .having(func.count(IntegrationEvent.id) > 1)
        )
        if duplicate_workflow_key or duplicate_integration_key:
            raise RuntimeError("Duplicate tenant-scoped idempotency keys found")
        if session.get_bind().dialect.name == "postgresql":
            trigger_names = set(
                await session.scalars(
                    text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
                )
            )
            required_triggers = {
                "trg_guard_signed_note",
                "trg_guard_note_versions_append_only",
                "trg_guard_note_amendments_append_only",
            }
            required_triggers.update(
                f"trg_guard_{table_name}_append_only"
                for table_name in (
                    "workflow_events",
                    "domain_events",
                    "episode_event_links",
                    "observation_manifests",
                    "observation_resources",
                    "outcome_observations",
                    "environment_steps",
                    "reward_components",
                    "dataset_release_items",
                )
            )
            required_triggers.update(
                f"trg_guard_{table_name}_finalized"
                for table_name in (
                    "episode_definitions",
                    "episode_instances",
                    "decision_points",
                    "action_attempts",
                    "policy_versions",
                    "simulation_scenarios",
                    "environment_runs",
                    "dataset_releases",
                )
            )
            missing_triggers = required_triggers - trigger_names
            if missing_triggers:
                raise RuntimeError(
                    "Postgres evidence guards are missing: "
                    + ", ".join(sorted(missing_triggers))
                )
    print(
        f"Verified {patient_count} synthetic patients, {len(Base.metadata.tables)} tables, "
        "Sarah's clinical/learning graphs, policy versions, financial reconciliation, "
        "tenant edges, and idempotency keys"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="ambrosia-db", description="Ambrosia database operations")
    parser.add_argument("command", choices=["migrate", "seed", "reset", "verify"])
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            command.upgrade(alembic_config(), "head")
        elif args.command == "seed":
            command.upgrade(alembic_config(), "head")
            asyncio.run(seed())
        elif args.command == "reset":
            asyncio.run(reset())
        elif args.command == "verify":
            asyncio.run(verify())
    except Exception as exc:
        print(f"ambrosia-db {args.command} failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
