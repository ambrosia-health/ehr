"""add the governed learning and RL environment substrate

Revision ID: 20260717_0003
Revises: 20260716_0002
Create Date: 2026-07-17 12:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260717_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEARNING_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

APPEND_ONLY_TABLES = (
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

FINALIZED_TABLES = {
    "episode_definitions": "released",
    "episode_instances": "completed,failed,terminated",
    "decision_points": "decided,expired,cancelled",
    "action_attempts": "succeeded,failed,rejected,no_action,cancelled",
    "policy_versions": "released",
    "simulation_scenarios": "released",
    "environment_runs": "completed,failed,terminated",
    "dataset_releases": "released",
}


def _record_columns(*, versioned: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("organization_id", sa.Uuid(), nullable=False),
    ]
    if versioned:
        columns.append(
            sa.Column("record_version", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
    columns.extend(
        [
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]
    )
    return columns


def _record_constraints(table_name: str) -> list[sa.Constraint]:
    return [
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(f"fk_{table_name}_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint("organization_id", "id", name=f"uq_{table_name}_org_id"),
    ]


def _record_indexes(table_name: str) -> None:
    op.create_index(op.f(f"ix_{table_name}_created_at"), table_name, ["created_at"], unique=False)
    op.create_index(
        op.f(f"ix_{table_name}_organization_id"),
        table_name,
        ["organization_id"],
        unique=False,
    )


def upgrade() -> None:
    _expand_existing_tables()
    _create_domain_events()
    _create_episode_definitions()
    _create_policy_versions()
    _create_dataset_releases()
    _backfill_policy_versions()
    _link_current_policy_versions()
    _create_episode_instances()
    _create_event_delivery_checkpoints()
    _create_simulation_scenarios()
    _create_episode_event_links()
    _create_observation_manifests()
    _create_observation_resources()
    _create_decision_points()
    _create_action_attempts()
    _create_environment_runs()
    _create_environment_steps()
    _create_outcome_observations()
    _create_reward_components()
    _create_dataset_release_items()
    _create_postgres_evidence_guards()


def _expand_existing_tables() -> None:
    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "next_event_sequence",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("record_version", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_workflow_runs_positive_next_event_sequence",
            "next_event_sequence > 0",
        )

    bind = op.get_bind()
    workflow_runs = sa.table(
        "workflow_runs",
        sa.column("id", sa.Uuid()),
        sa.column("next_event_sequence", sa.Integer()),
    )
    workflow_events = sa.table(
        "workflow_events",
        sa.column("workflow_run_id", sa.Uuid()),
        sa.column("sequence", sa.Integer()),
    )
    next_sequence = (
        sa.select(sa.func.coalesce(sa.func.max(workflow_events.c.sequence), 0) + 1)
        .where(workflow_events.c.workflow_run_id == workflow_runs.c.id)
        .scalar_subquery()
    )
    bind.execute(workflow_runs.update().values(next_event_sequence=next_sequence))

    with op.batch_alter_table("workflow_events", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_workflow_events_run_sequence", ["workflow_run_id", "sequence"]
        )
        batch_op.create_check_constraint("ck_workflow_events_positive_sequence", "sequence > 0")

    with op.batch_alter_table("automation_policies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_version_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("record_version", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
        batch_op.create_index(
            "ix_automation_policies_current_version_id",
            ["current_version_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_automation_policies_org_id", ["organization_id", "id"]
        )

    with op.batch_alter_table("proposed_actions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "proposal_version",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("expected_target_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payload_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("record_version", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_proposed_actions_positive_proposal_version", "proposal_version > 0"
        )
        batch_op.create_check_constraint(
            "ck_proposed_actions_positive_expected_target_version",
            "expected_target_version IS NULL OR expected_target_version > 0",
        )

    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "proposed_action_version",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("expected_target_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reviewer_role", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "edit_diff_json",
                LEARNING_JSON,
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_approvals_positive_proposed_action_version",
            "proposed_action_version > 0",
        )
        batch_op.create_check_constraint(
            "ck_approvals_positive_expected_target_version",
            "expected_target_version IS NULL OR expected_target_version > 0",
        )

    with op.batch_alter_table("ai_inputs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "resource_refs_json",
                LEARNING_JSON,
                server_default=sa.text("'[]'"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
        batch_op.add_column(sa.Column("snapshot_ref", sa.String(length=500), nullable=True))


def _link_current_policy_versions() -> None:
    with op.batch_alter_table("automation_policies", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_automation_policies_current_version",
            "policy_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        )


def _create_domain_events() -> None:
    op.create_table(
        "domain_events",
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_sequence", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("causation_event_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", LEARNING_JSON, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("sensitivity", sa.String(length=32), nullable=False),
        sa.Column("purpose_of_use", sa.String(length=64), nullable=False),
        *_record_columns(),
        sa.CheckConstraint(
            "aggregate_sequence > 0",
            name=op.f("ck_domain_events_positive_aggregate_sequence"),
        ),
        sa.CheckConstraint(
            "schema_version > 0", name=op.f("ck_domain_events_positive_schema_version")
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_domain_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name=op.f("fk_domain_events_patient_id_patients"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "causation_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_domain_events_causation",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "aggregate_type",
            "aggregate_id",
            "aggregate_sequence",
            name="uq_domain_events_aggregate_sequence",
        ),
        *_record_constraints("domain_events"),
    )
    _record_indexes("domain_events")
    op.create_index(
        "ix_domain_events_org_recorded",
        "domain_events",
        ["organization_id", "recorded_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_domain_events_org_type_occurred",
        "domain_events",
        ["organization_id", "event_type", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_domain_events_org_correlation",
        "domain_events",
        ["organization_id", "correlation_id"],
        unique=False,
    )
    op.create_index(
        "ix_domain_events_org_patient_occurred",
        "domain_events",
        ["organization_id", "patient_id", "occurred_at"],
        unique=False,
    )


def _create_episode_definitions() -> None:
    op.create_table(
        "episode_definitions",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("episode_type", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("start_conditions_json", LEARNING_JSON, nullable=False),
        sa.Column("termination_conditions_json", LEARNING_JSON, nullable=False),
        sa.Column("observation_schema_json", LEARNING_JSON, nullable=False),
        sa.Column("action_schema_json", LEARNING_JSON, nullable=False),
        sa.Column("reward_schema_json", LEARNING_JSON, nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint(
            "status IN ('draft','released')",
            name=op.f("ck_episode_definitions_valid_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_episode_definitions_positive_version")),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_episode_definitions_positive_schema_version"),
        ),
        sa.CheckConstraint("max_steps > 0", name=op.f("ck_episode_definitions_positive_max_steps")),
        sa.CheckConstraint(
            "max_duration_seconds > 0",
            name=op.f("ck_episode_definitions_positive_max_duration_seconds"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_episode_definitions_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            "version",
            name="uq_episode_definitions_slug_version",
        ),
        *_record_constraints("episode_definitions"),
    )
    _record_indexes("episode_definitions")
    op.create_index(
        "ix_episode_definitions_org_status_released",
        "episode_definitions",
        ["organization_id", "status", "released_at"],
        unique=False,
    )
    op.create_index(
        "ix_episode_definitions_org_type",
        "episode_definitions",
        ["organization_id", "episode_type"],
        unique=False,
    )


def _create_policy_versions() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("automation_policy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("conditions_json", LEARNING_JSON, nullable=False),
        sa.Column("actions_json", LEARNING_JSON, nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint(
            "status IN ('draft','released')", name=op.f("ck_policy_versions_valid_status")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_policy_versions_positive_version")),
        sa.CheckConstraint(
            "schema_version > 0", name=op.f("ck_policy_versions_positive_schema_version")
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name=op.f("ck_policy_versions_valid_effective_range"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "automation_policy_id"],
            ["automation_policies.organization_id", "automation_policies.id"],
            name="fk_policy_versions_policy",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_policy_versions_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "automation_policy_id",
            "version",
            name="uq_policy_versions_policy_version",
        ),
        *_record_constraints("policy_versions"),
    )
    _record_indexes("policy_versions")
    op.create_index(
        "ix_policy_versions_org_status_effective",
        "policy_versions",
        ["organization_id", "status", "effective_from"],
        unique=False,
    )


def _create_dataset_releases() -> None:
    op.create_table(
        "dataset_releases",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("intended_uses_json", LEARNING_JSON, nullable=False),
        sa.Column("prohibited_uses_json", LEARNING_JSON, nullable=False),
        sa.Column("legal_basis", sa.String(length=160), nullable=False),
        sa.Column("cohort_definition_json", LEARNING_JSON, nullable=False),
        sa.Column("exclusion_criteria_json", LEARNING_JSON, nullable=False),
        sa.Column("observation_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_window_days", sa.Integer(), nullable=False),
        sa.Column("terminology_versions_json", LEARNING_JSON, nullable=False),
        sa.Column("schema_versions_json", LEARNING_JSON, nullable=False),
        sa.Column("deidentification_method", sa.String(length=120), nullable=False),
        sa.Column("split_strategy_json", LEARNING_JSON, nullable=False),
        sa.Column("lineage_uri", sa.String(length=500), nullable=False),
        sa.Column("lineage_hash", sa.String(length=64), nullable=False),
        sa.Column("retention_policy_json", LEARNING_JSON, nullable=False),
        sa.Column("deletion_policy_json", LEARNING_JSON, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint(
            "status IN ('draft','released')", name=op.f("ck_dataset_releases_valid_status")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_dataset_releases_positive_version")),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_dataset_releases_positive_schema_version"),
        ),
        sa.CheckConstraint(
            "outcome_window_days >= 0",
            name=op.f("ck_dataset_releases_nonnegative_outcome_window"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_dataset_releases_approved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            "version",
            name="uq_dataset_releases_name_version",
        ),
        *_record_constraints("dataset_releases"),
    )
    _record_indexes("dataset_releases")
    op.create_index(
        "ix_dataset_releases_org_status_released",
        "dataset_releases",
        ["organization_id", "status", "released_at"],
        unique=False,
    )


def _backfill_policy_versions() -> None:
    bind = op.get_bind()
    policies = sa.table(
        "automation_policies",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("conditions_json", sa.JSON()),
        sa.column("actions_json", sa.JSON()),
        sa.column("requires_approval", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("current_version_id", sa.Uuid()),
    )
    versions = sa.table(
        "policy_versions",
        sa.column("automation_policy_id", sa.Uuid()),
        sa.column("version", sa.Integer()),
        sa.column("schema_version", sa.Integer()),
        sa.column("conditions_json", LEARNING_JSON),
        sa.column("actions_json", LEARNING_JSON),
        sa.column("requires_approval", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("effective_to", sa.DateTime(timezone=True)),
        sa.column("content_hash", sa.String()),
        sa.column("created_by_user_id", sa.Uuid()),
        sa.column("released_at", sa.DateTime(timezone=True)),
        sa.column("organization_id", sa.Uuid()),
        sa.column("record_version", sa.Integer()),
        sa.column("id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    version_rows: list[dict[str, object]] = []
    policy_links: list[dict[str, object]] = []
    for row in bind.execute(sa.select(policies)).mappings():
        policy_id = row["id"]
        if not isinstance(policy_id, uuid.UUID):
            policy_id = uuid.UUID(str(policy_id))
        version_id = uuid.uuid5(policy_id, "policy-version:1")
        canonical = json.dumps(
            {
                "actions": row["actions_json"],
                "conditions": row["conditions_json"],
                "requiresApproval": row["requires_approval"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        version_rows.append(
            {
                "automation_policy_id": policy_id,
                "version": 1,
                "schema_version": 1,
                "conditions_json": row["conditions_json"],
                "actions_json": row["actions_json"],
                "requires_approval": row["requires_approval"],
                "status": "released",
                "effective_from": row["created_at"],
                "effective_to": None,
                "content_hash": content_hash,
                "created_by_user_id": None,
                "released_at": row["created_at"],
                "organization_id": row["organization_id"],
                "record_version": 1,
                "id": version_id,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        policy_links.append({"policy_pk": policy_id, "version_fk": version_id})
    if version_rows:
        bind.execute(versions.insert(), version_rows)
        bind.execute(
            policies.update()
            .where(policies.c.id == sa.bindparam("policy_pk"))
            .values(current_version_id=sa.bindparam("version_fk")),
            policy_links,
        )


def _create_episode_instances() -> None:
    op.create_table(
        "episode_instances",
        sa.Column("episode_definition_id", sa.Uuid(), nullable=False),
        sa.Column("episode_key", sa.String(length=160), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_event_id", sa.Uuid(), nullable=True),
        sa.Column("end_event_id", sa.Uuid(), nullable=True),
        sa.Column("counterfactual_boundary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", LEARNING_JSON, nullable=False),
        *_record_columns(versioned=True),
        sa.CheckConstraint(
            "source_kind IN ('live','historical','synthetic')",
            name=op.f("ck_episode_instances_valid_source_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','terminated')",
            name=op.f("ck_episode_instances_valid_status"),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name=op.f("ck_episode_instances_valid_time_range"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_episode_instances_definition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "start_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_instances_start_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "end_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_instances_end_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name=op.f("fk_episode_instances_patient_id_patients"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "episode_key",
            name="uq_episode_instances_episode_key",
        ),
        *_record_constraints("episode_instances"),
    )
    _record_indexes("episode_instances")
    op.create_index(
        "ix_episode_instances_org_status_started",
        "episode_instances",
        ["organization_id", "status", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_episode_instances_org_patient_started",
        "episode_instances",
        ["organization_id", "patient_id", "started_at"],
        unique=False,
    )


def _create_event_delivery_checkpoints() -> None:
    op.create_table(
        "event_delivery_checkpoints",
        sa.Column("consumer_name", sa.String(length=120), nullable=False),
        sa.Column("partition_key", sa.String(length=120), nullable=False),
        sa.Column("last_event_id", sa.Uuid(), nullable=True),
        sa.Column("last_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        *_record_columns(versioned=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "last_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_event_delivery_checkpoints_last_event",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "consumer_name",
            "partition_key",
            name="uq_event_delivery_checkpoints_consumer_partition",
        ),
        *_record_constraints("event_delivery_checkpoints"),
    )
    _record_indexes("event_delivery_checkpoints")
    op.create_index(
        "ix_event_delivery_checkpoints_org_lease",
        "event_delivery_checkpoints",
        ["organization_id", "status", "lease_expires_at"],
        unique=False,
    )


def _create_simulation_scenarios() -> None:
    op.create_table(
        "simulation_scenarios",
        sa.Column("episode_definition_id", sa.Uuid(), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("logical_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "initial_state_json",
            LEARNING_JSON,
            nullable=False,
            comment="Server-owned synthetic simulator state; never populated from live PHI",
        ),
        sa.Column("initial_state_refs_json", LEARNING_JSON, nullable=False),
        sa.Column("actor_models_json", LEARNING_JSON, nullable=False),
        sa.Column("transition_rules_json", LEARNING_JSON, nullable=False),
        sa.Column("reward_spec_json", LEARNING_JSON, nullable=False),
        sa.Column("simulator_versions_json", LEARNING_JSON, nullable=False),
        sa.Column("fault_plan_json", LEARNING_JSON, nullable=False),
        sa.Column("synthetic_only", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint("version > 0", name=op.f("ck_simulation_scenarios_positive_version")),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_simulation_scenarios_positive_schema_version"),
        ),
        sa.CheckConstraint(
            "synthetic_only", name=op.f("ck_simulation_scenarios_synthetic_only_required")
        ),
        sa.CheckConstraint(
            "status IN ('draft','released')",
            name=op.f("ck_simulation_scenarios_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_simulation_scenarios_definition",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            "version",
            name="uq_simulation_scenarios_slug_version",
        ),
        *_record_constraints("simulation_scenarios"),
    )
    _record_indexes("simulation_scenarios")
    op.create_index(
        "ix_simulation_scenarios_org_status_released",
        "simulation_scenarios",
        ["organization_id", "status", "released_at"],
        unique=False,
    )


def _create_episode_event_links() -> None:
    op.create_table(
        "episode_event_links",
        sa.Column("episode_instance_id", sa.Uuid(), nullable=False),
        sa.Column("domain_event_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_episode_event_links_positive_sequence")),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_episode_event_links_episode",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "domain_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_episode_event_links_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "episode_instance_id",
            "sequence",
            name="uq_episode_event_links_sequence",
        ),
        sa.UniqueConstraint(
            "episode_instance_id",
            "domain_event_id",
            name="uq_episode_event_links_event",
        ),
        *_record_constraints("episode_event_links"),
    )
    _record_indexes("episode_event_links")
    op.create_index(
        "ix_episode_event_links_org_event",
        "episode_event_links",
        ["organization_id", "domain_event_id"],
        unique=False,
    )


def _create_observation_manifests() -> None:
    op.create_table(
        "observation_manifests",
        sa.Column("episode_instance_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("as_of_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "synthetic_snapshot_json",
            LEARNING_JSON,
            nullable=False,
            comment="Synthetic-only inline observation snapshot; live manifests use snapshot_ref",
        ),
        sa.Column("sensitivity", sa.String(length=32), nullable=False),
        sa.Column("purpose_of_use", sa.String(length=64), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_observation_manifests_positive_sequence")),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_observation_manifests_positive_schema_version"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_observation_manifests_episode",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "episode_instance_id",
            "id",
            name="uq_observation_manifests_episode_id",
        ),
        sa.UniqueConstraint(
            "episode_instance_id",
            "sequence",
            name="uq_observation_manifests_sequence",
        ),
        *_record_constraints("observation_manifests"),
    )
    _record_indexes("observation_manifests")
    op.create_index(
        "ix_observation_manifests_org_as_of",
        "observation_manifests",
        ["organization_id", "as_of_at"],
        unique=False,
    )


def _create_observation_resources() -> None:
    op.create_table(
        "observation_resources",
        sa.Column("observation_manifest_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_ref", sa.String(length=500), nullable=True),
        *_record_columns(),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_observation_resources_positive_sequence")),
        sa.CheckConstraint(
            "resource_version > 0",
            name=op.f("ck_observation_resources_positive_resource_version"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "observation_manifest_id"],
            ["observation_manifests.organization_id", "observation_manifests.id"],
            name="fk_observation_resources_manifest",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "observation_manifest_id",
            "sequence",
            name="uq_observation_resources_sequence",
        ),
        sa.UniqueConstraint(
            "observation_manifest_id",
            "resource_type",
            "resource_id",
            "resource_version",
            name="uq_observation_resources_version",
        ),
        *_record_constraints("observation_resources"),
    )
    _record_indexes("observation_resources")
    op.create_index(
        "ix_observation_resources_org_resource",
        "observation_resources",
        ["organization_id", "resource_type", "resource_id", "resource_version"],
        unique=False,
    )


def _create_decision_points() -> None:
    op.create_table(
        "decision_points",
        sa.Column("episode_instance_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("observation_manifest_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("available_actions_json", LEARNING_JSON, nullable=False),
        sa.Column("policy_refs_json", LEARNING_JSON, nullable=False),
        sa.Column("displayed_proposal_id", sa.Uuid(), nullable=True),
        sa.Column("recommendation_rendered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_decision_points_positive_sequence")),
        sa.CheckConstraint(
            "status IN ('open','decided','expired','cancelled')",
            name=op.f("ck_decision_points_valid_status"),
        ),
        sa.CheckConstraint(
            "decided_at IS NULL OR decided_at >= opened_at",
            name=op.f("ck_decision_points_valid_decision_time"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_decision_points_episode",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id", "observation_manifest_id"],
            [
                "observation_manifests.organization_id",
                "observation_manifests.episode_instance_id",
                "observation_manifests.id",
            ],
            name="fk_decision_points_observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "trigger_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_decision_points_trigger_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_decision_points_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["displayed_proposal_id"],
            ["proposed_actions.id"],
            name=op.f("fk_decision_points_displayed_proposal_id_proposed_actions"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("episode_instance_id", "sequence", name="uq_decision_points_sequence"),
        *_record_constraints("decision_points"),
    )
    _record_indexes("decision_points")
    op.create_index(
        "ix_decision_points_org_type_opened",
        "decision_points",
        ["organization_id", "decision_type", "opened_at"],
        unique=False,
    )
    op.create_index(
        "ix_decision_points_org_status_deadline",
        "decision_points",
        ["organization_id", "status", "deadline_at"],
        unique=False,
    )


def _create_action_attempts() -> None:
    op.create_table(
        "action_attempts",
        sa.Column("decision_point_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_action_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_version", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("arguments_json", LEARNING_JSON, nullable=False),
        sa.Column("expected_target_type", sa.String(length=64), nullable=True),
        sa.Column("expected_target_id", sa.Uuid(), nullable=True),
        sa.Column("expected_target_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_event_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("human_edit_diff_json", LEARNING_JSON, nullable=False),
        *_record_columns(versioned=True),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_action_attempts_positive_sequence")),
        sa.CheckConstraint(
            "proposal_version IS NULL OR proposal_version > 0",
            name=op.f("ck_action_attempts_positive_proposal_version"),
        ),
        sa.CheckConstraint(
            "expected_target_version IS NULL OR expected_target_version > 0",
            name=op.f("ck_action_attempts_positive_expected_target_version"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','succeeded','failed','rejected','no_action','cancelled')",
            name=op.f("ck_action_attempts_valid_status"),
        ),
        sa.CheckConstraint(
            "executed_at IS NULL OR executed_at >= attempted_at",
            name=op.f("ck_action_attempts_valid_execution_time"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_action_attempts_decision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "result_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_action_attempts_result_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_action_attempts_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_action_attempts_ai_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_action_id"],
            ["proposed_actions.id"],
            name=op.f("fk_action_attempts_proposed_action_id_proposed_actions"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("decision_point_id", "sequence", name="uq_action_attempts_sequence"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_action_attempts_idempotency"
        ),
        *_record_constraints("action_attempts"),
    )
    _record_indexes("action_attempts")
    op.create_index(
        "ix_action_attempts_org_status_attempted",
        "action_attempts",
        ["organization_id", "status", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_action_attempts_org_type_attempted",
        "action_attempts",
        ["organization_id", "action_type", "attempted_at"],
        unique=False,
    )


def _create_environment_runs() -> None:
    op.create_table(
        "environment_runs",
        sa.Column("run_key", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("simulation_scenario_id", sa.Uuid(), nullable=True),
        sa.Column("episode_definition_id", sa.Uuid(), nullable=False),
        sa.Column("episode_instance_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_release_id", sa.Uuid(), nullable=True),
        sa.Column("agent_kind", sa.String(length=64), nullable=False),
        sa.Column("agent_model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=True),
        sa.Column("code_version", sa.String(length=120), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("config_json", LEARNING_JSON, nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("state_json", LEARNING_JSON, nullable=False),
        sa.Column("total_reward_json", LEARNING_JSON, nullable=False),
        sa.Column("hard_violation_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_reason", sa.String(length=240), nullable=True),
        *_record_columns(versioned=True),
        sa.CheckConstraint(
            "mode IN ('replay','simulation','shadow')",
            name=op.f("ck_environment_runs_valid_mode"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','terminated')",
            name=op.f("ck_environment_runs_valid_status"),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name=op.f("ck_environment_runs_valid_time_range"),
        ),
        sa.CheckConstraint(
            "current_step >= 0", name=op.f("ck_environment_runs_nonnegative_current_step")
        ),
        sa.CheckConstraint(
            "hard_violation_count >= 0",
            name=op.f("ck_environment_runs_nonnegative_hard_violation_count"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "simulation_scenario_id"],
            ["simulation_scenarios.organization_id", "simulation_scenarios.id"],
            name="fk_environment_runs_scenario",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_definition_id"],
            ["episode_definitions.organization_id", "episode_definitions.id"],
            name="fk_environment_runs_definition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_environment_runs_episode",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "dataset_release_id"],
            ["dataset_releases.organization_id", "dataset_releases.id"],
            name="fk_environment_runs_dataset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
            name=op.f("fk_environment_runs_prompt_version_id_prompt_versions"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id", "run_key", name="uq_environment_runs_run_key"),
        *_record_constraints("environment_runs"),
    )
    _record_indexes("environment_runs")
    op.create_index(
        "ix_environment_runs_org_status_created",
        "environment_runs",
        ["organization_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_environment_runs_org_mode_created",
        "environment_runs",
        ["organization_id", "mode", "created_at"],
        unique=False,
    )


def _create_environment_steps() -> None:
    op.create_table(
        "environment_steps",
        sa.Column("environment_run_id", sa.Uuid(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("decision_point_id", sa.Uuid(), nullable=True),
        sa.Column("observation_manifest_id", sa.Uuid(), nullable=False),
        sa.Column("action_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("simulator_time_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("simulator_time_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_before_hash", sa.String(length=64), nullable=False),
        sa.Column("state_after_hash", sa.String(length=64), nullable=False),
        sa.Column("support_kind", sa.String(length=40), nullable=False),
        sa.Column("terminated", sa.Boolean(), nullable=False),
        sa.Column("termination_reason", sa.String(length=240), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        *_record_columns(),
        sa.CheckConstraint(
            "step_number > 0", name=op.f("ck_environment_steps_positive_step_number")
        ),
        sa.CheckConstraint(
            "latency_ms >= 0", name=op.f("ck_environment_steps_nonnegative_latency")
        ),
        sa.CheckConstraint(
            "support_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name=op.f("ck_environment_steps_valid_support_kind"),
        ),
        sa.CheckConstraint(
            "simulator_time_after IS NULL OR simulator_time_before IS NULL "
            "OR simulator_time_after >= simulator_time_before",
            name=op.f("ck_environment_steps_valid_simulator_time_range"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "environment_run_id"],
            ["environment_runs.organization_id", "environment_runs.id"],
            name="fk_environment_steps_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_environment_steps_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "observation_manifest_id"],
            ["observation_manifests.organization_id", "observation_manifests.id"],
            name="fk_environment_steps_observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_attempt_id"],
            ["action_attempts.organization_id", "action_attempts.id"],
            name="fk_environment_steps_action",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "environment_run_id",
            "step_number",
            name="uq_environment_steps_run_step",
        ),
        *_record_constraints("environment_steps"),
    )
    _record_indexes("environment_steps")
    op.create_index(
        "ix_environment_steps_org_run_step",
        "environment_steps",
        ["organization_id", "environment_run_id", "step_number"],
        unique=False,
    )


def _create_outcome_observations() -> None:
    op.create_table(
        "outcome_observations",
        sa.Column("episode_instance_id", sa.Uuid(), nullable=False),
        sa.Column("decision_point_id", sa.Uuid(), nullable=True),
        sa.Column("action_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_type", sa.String(length=80), nullable=False),
        sa.Column("value_json", LEARNING_JSON, nullable=False),
        sa.Column("provenance_kind", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_resource_type", sa.String(length=64), nullable=True),
        sa.Column("source_resource_id", sa.Uuid(), nullable=True),
        sa.Column("source_resource_version", sa.Integer(), nullable=True),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("simulator_version", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        *_record_columns(),
        sa.CheckConstraint(
            "provenance_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name=op.f("ck_outcome_observations_valid_provenance_kind"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_outcome_observations_valid_confidence"),
        ),
        sa.CheckConstraint(
            "source_resource_version IS NULL OR source_resource_version > 0",
            name=op.f("ck_outcome_observations_positive_source_resource_version"),
        ),
        sa.CheckConstraint(
            "window_end_at IS NULL OR window_start_at IS NULL OR window_end_at >= window_start_at",
            name=op.f("ck_outcome_observations_valid_observation_window"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_outcome_observations_episode",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_point_id"],
            ["decision_points.organization_id", "decision_points.id"],
            name="fk_outcome_observations_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_attempt_id"],
            ["action_attempts.organization_id", "action_attempts.id"],
            name="fk_outcome_observations_action",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_outcome_observations_source_event",
            ondelete="RESTRICT",
        ),
        *_record_constraints("outcome_observations"),
    )
    _record_indexes("outcome_observations")
    op.create_index(
        "ix_outcome_observations_org_type_observed",
        "outcome_observations",
        ["organization_id", "outcome_type", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_outcome_observations_org_episode_observed",
        "outcome_observations",
        ["organization_id", "episode_instance_id", "observed_at"],
        unique=False,
    )


def _create_reward_components() -> None:
    op.create_table(
        "reward_components",
        sa.Column("environment_step_id", sa.Uuid(), nullable=False),
        sa.Column("component_name", sa.String(length=80), nullable=False),
        sa.Column("evaluator_key", sa.String(length=120), nullable=False),
        sa.Column("evaluator_version", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("weight", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("hard_violation", sa.Boolean(), nullable=False),
        sa.Column("evidence_json", LEARNING_JSON, nullable=False),
        sa.Column("provenance_kind", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        *_record_columns(),
        sa.CheckConstraint(
            "provenance_kind IN ('observed','simulated','expert','unsupported_counterfactual')",
            name=op.f("ck_reward_components_valid_provenance_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "environment_step_id"],
            ["environment_steps.organization_id", "environment_steps.id"],
            name="fk_reward_components_step",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "environment_step_id",
            "component_name",
            "evaluator_key",
            "evaluator_version",
            name="uq_reward_components_evaluation",
        ),
        *_record_constraints("reward_components"),
    )
    _record_indexes("reward_components")
    op.create_index(
        "ix_reward_components_org_hard_computed",
        "reward_components",
        ["organization_id", "hard_violation", "computed_at"],
        unique=False,
    )
    op.create_index(
        "ix_reward_components_org_name_computed",
        "reward_components",
        ["organization_id", "component_name", "computed_at"],
        unique=False,
    )


def _create_dataset_release_items() -> None:
    op.create_table(
        "dataset_release_items",
        sa.Column("dataset_release_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("episode_instance_id", sa.Uuid(), nullable=True),
        sa.Column("environment_run_id", sa.Uuid(), nullable=True),
        sa.Column("domain_event_id", sa.Uuid(), nullable=True),
        sa.Column("split", sa.String(length=24), nullable=False),
        sa.Column("inclusion_reason", sa.String(length=500), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_dataset_release_items_positive_sequence")),
        sa.CheckConstraint(
            "split IN ('train','validation','test','holdout')",
            name=op.f("ck_dataset_release_items_valid_split"),
        ),
        sa.CheckConstraint(
            "(CASE WHEN episode_instance_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN environment_run_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN domain_event_id IS NULL THEN 0 ELSE 1 END) = 1",
            name=op.f("ck_dataset_release_items_exactly_one_item"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "dataset_release_id"],
            ["dataset_releases.organization_id", "dataset_releases.id"],
            name="fk_dataset_release_items_release",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "episode_instance_id"],
            ["episode_instances.organization_id", "episode_instances.id"],
            name="fk_dataset_release_items_episode",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "environment_run_id"],
            ["environment_runs.organization_id", "environment_runs.id"],
            name="fk_dataset_release_items_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "domain_event_id"],
            ["domain_events.organization_id", "domain_events.id"],
            name="fk_dataset_release_items_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "dataset_release_id",
            "sequence",
            name="uq_dataset_release_items_sequence",
        ),
        sa.UniqueConstraint(
            "dataset_release_id",
            "episode_instance_id",
            name="uq_dataset_release_items_episode",
        ),
        sa.UniqueConstraint(
            "dataset_release_id",
            "environment_run_id",
            name="uq_dataset_release_items_run",
        ),
        sa.UniqueConstraint(
            "dataset_release_id",
            "domain_event_id",
            name="uq_dataset_release_items_event",
        ),
        *_record_constraints("dataset_release_items"),
    )
    _record_indexes("dataset_release_items")
    op.create_index(
        "ix_dataset_release_items_org_release_split",
        "dataset_release_items",
        ["organization_id", "dataset_release_id", "split"],
        unique=False,
    )


def _create_postgres_evidence_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    # Each call contains one top-level command because asyncpg prepares one command at a time.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ambrosia_guard_learning_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM organizations WHERE id = OLD.organization_id) THEN
              RAISE EXCEPTION 'Learning evidence is append-only';
            END IF;
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'Learning evidence is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ambrosia_guard_finalized_learning_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE finalized_states text[];
        BEGIN
          finalized_states := string_to_array(TG_ARGV[0], ',');
          IF OLD.status = ANY(finalized_states) THEN
            IF TG_OP = 'DELETE'
               AND NOT EXISTS (
                 SELECT 1 FROM organizations WHERE id = OLD.organization_id
               ) THEN
              RETURN OLD;
            END IF;
            RAISE EXCEPTION
              'Finalized learning evidence cannot be changed; create a new version';
          END IF;
          IF TG_OP = 'DELETE' THEN
            RETURN OLD;
          END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    for table_name in APPEND_ONLY_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_guard_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION ambrosia_guard_learning_append_only();
            """
        )
    for table_name, statuses in FINALIZED_TABLES.items():
        op.execute(
            f"""
            CREATE TRIGGER trg_guard_{table_name}_finalized
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION
              ambrosia_guard_finalized_learning_evidence('{statuses}');
            """
        )


def _drop_postgres_evidence_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_guard_{table_name}_append_only ON {table_name}")
    for table_name in FINALIZED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_guard_{table_name}_finalized ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS ambrosia_guard_finalized_learning_evidence()")
    op.execute("DROP FUNCTION IF EXISTS ambrosia_guard_learning_append_only()")


def downgrade() -> None:
    _drop_postgres_evidence_guards()

    with op.batch_alter_table("automation_policies", schema=None) as batch_op:
        batch_op.drop_constraint("fk_automation_policies_current_version", type_="foreignkey")

    for table_name in (
        "dataset_release_items",
        "reward_components",
        "outcome_observations",
        "environment_steps",
        "environment_runs",
        "action_attempts",
        "decision_points",
        "observation_resources",
        "observation_manifests",
        "episode_event_links",
        "simulation_scenarios",
        "event_delivery_checkpoints",
        "episode_instances",
        "dataset_releases",
        "policy_versions",
        "episode_definitions",
        "domain_events",
    ):
        op.drop_table(table_name)

    with op.batch_alter_table("ai_inputs", schema=None) as batch_op:
        batch_op.drop_column("snapshot_ref")
        batch_op.drop_column("schema_version")
        batch_op.drop_column("resource_refs_json")

    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.drop_constraint("ck_approvals_positive_expected_target_version", type_="check")
        batch_op.drop_constraint("ck_approvals_positive_proposed_action_version", type_="check")
        batch_op.drop_column("edit_diff_json")
        batch_op.drop_column("reviewer_role")
        batch_op.drop_column("expected_target_version")
        batch_op.drop_column("proposed_action_version")

    with op.batch_alter_table("automation_policies", schema=None) as batch_op:
        batch_op.drop_constraint("uq_automation_policies_org_id", type_="unique")
        batch_op.drop_index("ix_automation_policies_current_version_id")
        batch_op.drop_column("record_version")
        batch_op.drop_column("current_version_id")

    with op.batch_alter_table("proposed_actions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_proposed_actions_positive_expected_target_version", type_="check"
        )
        batch_op.drop_constraint("ck_proposed_actions_positive_proposal_version", type_="check")
        batch_op.drop_column("record_version")
        batch_op.drop_column("payload_hash")
        batch_op.drop_column("expected_target_version")
        batch_op.drop_column("proposal_version")

    with op.batch_alter_table("workflow_events", schema=None) as batch_op:
        batch_op.drop_constraint("ck_workflow_events_positive_sequence", type_="check")
        batch_op.drop_constraint("uq_workflow_events_run_sequence", type_="unique")

    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_workflow_runs_positive_next_event_sequence", type_="check")
        batch_op.drop_column("record_version")
        batch_op.drop_column("next_event_sequence")
