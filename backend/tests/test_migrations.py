from __future__ import annotations

import ast
from pathlib import Path

VERSIONS = Path(__file__).parents[1] / "alembic" / "versions"
INITIAL_MIGRATION = VERSIONS / "20260716_0001_create_domain_schema.py"
GUARD_MIGRATION = VERSIONS / "20260716_0002_note_guards_and_task_links.py"


def test_postgres_note_guard_ddl_uses_one_statement_per_execute() -> None:
    """asyncpg prepared statements reject multiple top-level SQL commands."""

    assert "ambrosia_guard_" not in INITIAL_MIGRATION.read_text()
    migration_source = GUARD_MIGRATION.read_text()
    assert (
        "NEW.structured_content::jsonb IS DISTINCT FROM OLD.structured_content::jsonb"
        in migration_source
    )
    assert '"fk_tasks_denial_id_denials"' in migration_source
    tree = ast.parse(migration_source)
    statements: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if (
            node.func.attr != "execute"
            or not isinstance(node.func.value, ast.Name)
            or node.func.value.id != "op"
            or len(node.args) != 1
        ):
            continue
        statement = ast.literal_eval(node.args[0])
        if "ambrosia_guard_" in statement or "trg_guard_" in statement:
            statements.append(statement.upper())

    assert len(statements) == 10
    assert sum("CREATE OR REPLACE FUNCTION" in item for item in statements) == 2
    assert sum("CREATE TRIGGER" in item for item in statements) == 3
    assert sum(item.lstrip().startswith("DROP ") for item in statements) == 5
    for statement in statements:
        top_level_commands = sum(
            marker in statement
            for marker in ("CREATE OR REPLACE FUNCTION", "CREATE TRIGGER", "DROP ")
        )
        assert top_level_commands == 1
