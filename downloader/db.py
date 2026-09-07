"""Postgres connection and schema migrations."""

import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor, Json

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"
MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def get_connection():
    db_url = os.getenv("POSTGRES_URL", "postgresql://postgres:password@localhost:5432/statutes")
    return psycopg2.connect(db_url, cursor_factory=DictCursor)


@contextmanager
def connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def list_migrations(directory: Path | str = MIGRATIONS_DIR) -> list[Path]:
    """Return migration files sorted by version. Names must match NNN_name.sql with no gaps."""
    directory = Path(directory)
    files = sorted(p for p in directory.iterdir() if p.suffix == ".sql")
    versions = []
    for path in files:
        match = MIGRATION_NAME.match(path.name)
        if not match:
            raise ValueError(f"migration name {path.name!r} does not match NNN_name.sql")
        versions.append(int(match.group(1)))
    expected = list(range(1, len(versions) + 1))
    if versions != expected:
        raise ValueError(f"migration versions {versions} are not sequential from 001")
    return files


def apply_migrations(conn, directory: Path | str = MIGRATIONS_DIR) -> list[str]:
    """Apply unapplied migrations in order inside one transaction each. Returns the names applied."""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

    newly_applied = []
    for path in list_migrations(directory):
        version = path.name
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()
        except Exception:
            conn.rollback()
            logger.error("migration %s failed", version)
            raise
        logger.info("applied migration %s", version)
        newly_applied.append(version)
    return newly_applied


def init_db(directory: Path | str = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Safe to call at every process start."""
    with connection() as conn:
        return apply_migrations(conn, directory)


def insert_statute(pl_number, congress, law_number, title, date_enacted, volume, start_page, end_page, pdf_path,
                   conn=None):
    """Insert a statutes row. Returns the id, or None when pl_number already exists."""
    own = conn is None
    if own:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO statutes (pl_number, congress, law_number, title, date_enacted, volume, start_page,
                                      end_page, pdf_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pl_number) DO UPDATE SET
                    title = EXCLUDED.title,
                    date_enacted = EXCLUDED.date_enacted,
                    volume = COALESCE(EXCLUDED.volume, statutes.volume),
                    start_page = COALESCE(EXCLUDED.start_page, statutes.start_page),
                    end_page = COALESCE(EXCLUDED.end_page, statutes.end_page),
                    pdf_path = COALESCE(EXCLUDED.pdf_path, statutes.pdf_path)
                RETURNING id;
                """,
                (pl_number, congress, law_number, title, date_enacted, volume, start_page, end_page, pdf_path),
            )
            result = cur.fetchone()
            conn.commit()
            return result["id"] if result else None
    finally:
        if own:
            conn.close()


def jsonb(value):
    """Wrap a dict for a JSONB column."""
    return Json(value) if value is not None else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    applied = init_db()
    print(f"applied {len(applied)} migration(s): {applied}")
