"""Applies numbered .sql files from migrations/ exactly once, in filename order."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def apply_migrations(conn, migrations_dir="migrations"):
    """Run every migration not yet recorded in ops.schema_migrations. Returns names applied now."""
    # The tracking table must exist before we can ask which migrations are done
    with conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS ops")
            cur.execute(
                """CREATE TABLE IF NOT EXISTS ops.schema_migrations (
                       filename   TEXT PRIMARY KEY,
                       applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"""
            )

    applied_now = []
    with conn:  # one transaction: all new migrations apply together or not at all
        with conn.cursor() as cur:
            # Advisory lock: if two containers start at once, the second waits here
            cur.execute("SELECT pg_advisory_xact_lock(727311)")
            cur.execute("SELECT filename FROM ops.schema_migrations")
            done = {row[0] for row in cur.fetchall()}
            for path in sorted(Path(migrations_dir).glob("*.sql")):
                if path.name in done:
                    continue
                log.info("applying migration %s", path.name)
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO ops.schema_migrations (filename) VALUES (%s)", (path.name,)
                )
                applied_now.append(path.name)
    return applied_now
