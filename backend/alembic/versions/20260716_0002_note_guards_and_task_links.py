"""add signed-note guards and denial task links

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("claim_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("denial_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_claim_id_claims",
            "claims",
            ["claim_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_tasks_denial_id_denials",
            "denials",
            ["denial_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_tasks_claim_id", ["claim_id"], unique=False)
        batch_op.create_index("ix_tasks_denial_id", ["denial_id"], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        # asyncpg accepts exactly one top-level command in each prepared statement.
        op.execute(
            """
            CREATE OR REPLACE FUNCTION ambrosia_guard_signed_note()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('signed', 'amended')
                   AND EXISTS (SELECT 1 FROM organizations WHERE id = OLD.organization_id) THEN
                  RAISE EXCEPTION
                    'Signed clinical notes are immutable; create an amendment instead';
                END IF;
                RETURN OLD;
              END IF;
              IF OLD.status IN ('signed', 'amended') THEN
                IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id
                   OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
                   OR NEW.author_user_id IS DISTINCT FROM OLD.author_user_id
                   OR NEW.content IS DISTINCT FROM OLD.content
                   OR NEW.structured_content::jsonb IS DISTINCT FROM OLD.structured_content::jsonb
                   OR NEW.current_version IS DISTINCT FROM OLD.current_version
                   OR NEW.ai_run_id IS DISTINCT FROM OLD.ai_run_id
                   OR NEW.signed_at IS DISTINCT FROM OLD.signed_at
                   OR NEW.signed_by_user_id IS DISTINCT FROM OLD.signed_by_user_id
                   OR NEW.signature_hash IS DISTINCT FROM OLD.signature_hash
                   OR NOT (
                        NEW.status = OLD.status
                        OR (OLD.status = 'signed' AND NEW.status = 'amended')
                   ) THEN
                  RAISE EXCEPTION
                    'Signed clinical notes are immutable; create an amendment instead';
                END IF;
              END IF;
              RETURN NEW;
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_guard_signed_note
            BEFORE UPDATE OR DELETE ON encounter_notes
            FOR EACH ROW EXECUTE FUNCTION ambrosia_guard_signed_note();
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION ambrosia_guard_append_only_note_child()
            RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE note_org uuid;
            BEGIN
              IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Signed note history is append-only';
              END IF;
              SELECT organization_id INTO note_org FROM encounter_notes WHERE id = OLD.note_id;
              IF note_org IS NOT NULL
                 AND EXISTS (SELECT 1 FROM organizations WHERE id = note_org) THEN
                RAISE EXCEPTION 'Signed note history is append-only';
              END IF;
              RETURN OLD;
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_guard_note_versions_append_only
            BEFORE UPDATE OR DELETE ON note_versions
            FOR EACH ROW EXECUTE FUNCTION ambrosia_guard_append_only_note_child();
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_guard_note_amendments_append_only
            BEFORE UPDATE OR DELETE ON note_amendments
            FOR EACH ROW EXECUTE FUNCTION ambrosia_guard_append_only_note_child();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_guard_note_amendments_append_only ON note_amendments"
        )
        op.execute("DROP TRIGGER IF EXISTS trg_guard_note_versions_append_only ON note_versions")
        op.execute("DROP TRIGGER IF EXISTS trg_guard_signed_note ON encounter_notes")
        op.execute("DROP FUNCTION IF EXISTS ambrosia_guard_append_only_note_child()")
        op.execute("DROP FUNCTION IF EXISTS ambrosia_guard_signed_note()")

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_tasks_denial_id")
        batch_op.drop_index("ix_tasks_claim_id")
        batch_op.drop_constraint("fk_tasks_denial_id_denials", type_="foreignkey")
        batch_op.drop_constraint("fk_tasks_claim_id_claims", type_="foreignkey")
        batch_op.drop_column("denial_id")
        batch_op.drop_column("claim_id")
