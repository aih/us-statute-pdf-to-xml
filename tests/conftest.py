import os

import pytest


@pytest.fixture
def pg_conn():
    """A live Postgres connection, or skip. Set POSTGRES_URL (docker compose sets it in the app container)."""
    url = os.getenv("POSTGRES_URL")
    if not url:
        pytest.skip("POSTGRES_URL not set")
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"Postgres not reachable: {exc}")
    yield conn
    conn.close()
