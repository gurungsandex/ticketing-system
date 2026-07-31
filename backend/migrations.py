"""
Lightweight, idempotent schema migrations for SQLite.

SQLAlchemy's create_all() creates *new* tables but never alters existing ones.
When upgrading an existing deployment, tables like `tickets` and `admin_users`
already exist without the columns added in newer versions. This module adds any
missing columns via `ALTER TABLE ... ADD COLUMN`, which is safe and preserves
all existing rows.

Called once on startup (after create_all). Running it repeatedly is a no-op.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# table -> {column_name: column_definition}
_ADDITIVE_COLUMNS = {
    "tickets": {
        "priority": "TEXT DEFAULT 'normal'",
        "department": "TEXT",
        "location": "TEXT",
        "device": "TEXT",
        "resolution_summary": "TEXT",
        "resolved_at": "DATETIME",
    },
    "admin_users": {
        "chat_status": "TEXT DEFAULT 'offline'",
        "chat_status_updated": "DATETIME",
    },
}


def run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                # Fresh install — create_all already made the full table.
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in present:
                    continue
                try:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
                    logger.info("migration: added %s.%s", table, name)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("migration: could not add %s.%s: %s", table, name, exc)
