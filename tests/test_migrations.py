from pathlib import Path

import pytest

from downloader import db


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        if sql.startswith("INSERT INTO schema_migrations"):
            self.conn.applied.add(params[0])

    def fetchall(self):
        return [(v,) for v in sorted(self.conn.applied)]


class FakeConn:
    def __init__(self, applied=()):
        self.applied = set(applied)
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def write_migrations(tmp_path: Path, names):
    for name in names:
        (tmp_path / name).write_text(f"-- {name}\nSELECT 1;\n")
    return tmp_path


def test_repo_migrations_are_sequential():
    files = db.list_migrations()
    assert [p.name for p in files][:3] == [
        "001_initial.sql",
        "002_packages_granules.sql",
        "003_title_text.sql",
    ]


def test_list_migrations_rejects_gap(tmp_path):
    write_migrations(tmp_path, ["001_a.sql", "003_c.sql"])
    with pytest.raises(ValueError, match="sequential"):
        db.list_migrations(tmp_path)


def test_list_migrations_rejects_bad_name(tmp_path):
    write_migrations(tmp_path, ["001_a.sql", "second.sql"])
    with pytest.raises(ValueError, match="does not match"):
        db.list_migrations(tmp_path)


def test_apply_migrations_runs_in_order_and_records(tmp_path):
    write_migrations(tmp_path, ["002_b.sql", "001_a.sql", "003_c.sql"])
    conn = FakeConn()
    applied = db.apply_migrations(conn, tmp_path)
    assert applied == ["001_a.sql", "002_b.sql", "003_c.sql"]
    sql_run = [sql for sql, _ in conn.executed if sql.startswith("-- ")]
    assert sql_run == ["-- 001_a.sql\nSELECT 1;\n", "-- 002_b.sql\nSELECT 1;\n", "-- 003_c.sql\nSELECT 1;\n"]
    assert conn.applied == {"001_a.sql", "002_b.sql", "003_c.sql"}
    # one commit for the schema_migrations table plus one per migration
    assert conn.commits == 4


def test_apply_migrations_skips_already_applied(tmp_path):
    write_migrations(tmp_path, ["001_a.sql", "002_b.sql"])
    conn = FakeConn(applied={"001_a.sql"})
    applied = db.apply_migrations(conn, tmp_path)
    assert applied == ["002_b.sql"]
    assert all("001_a.sql" not in sql for sql, _ in conn.executed if sql.startswith("-- "))


def test_apply_migrations_second_run_is_noop(tmp_path):
    write_migrations(tmp_path, ["001_a.sql"])
    conn = FakeConn()
    assert db.apply_migrations(conn, tmp_path) == ["001_a.sql"]
    assert db.apply_migrations(conn, tmp_path) == []


@pytest.mark.integration
def test_init_db_against_postgres_is_idempotent(pg_conn):
    db.apply_migrations(pg_conn)
    assert db.apply_migrations(pg_conn) == []
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'statutes' AND column_name = 'title'"
        )
        assert cur.fetchone()[0] == "text"
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert {"statutes", "conversions", "benchmarks", "packages", "granules", "schema_migrations"} <= tables
