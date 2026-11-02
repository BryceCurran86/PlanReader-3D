"""GPT3: JobHub destination identity must be checked inside the publish transaction.

These source-neutral tests exercise the real SQLite JobHub write consumer. They
do not authenticate an original drawing, quantity, signed seal or frozen score.
"""
from __future__ import annotations

import sqlite3

import pytest

from pb_jobhub_publishing_contract import (
    PublishingMode,
    validate_publishing_gate,
)
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_commercial_identity_default_safety import _minimal_commercial_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _approved_package():
    package = _minimal_commercial_package(
        estimator="Source Estimator",
        created_by="Source Estimator",
        approved_by="Source Estimator",
    )
    package.project_identity.job_no = "26-017"
    package.project_identity.target_jobhub_job_id = 501
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    return package


class _DestinationChangedAtConnect:
    """Reproduce the gap between a separate bridge.query and bridge.connect."""

    def __init__(self, conn, *, remove=False):
        self.conn = conn
        self.remove = remove
        self.query_calls = 0

    def query(self, sql, params=()):
        # The old implementation read the ORIGINAL identity here, before the
        # connect() hook changed it. This intentionally preserves that exploit.
        self.query_calls += 1
        cur = self.conn.execute(sql, params)
        cols = [column[0] for column in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def connect(self):
        if self.remove:
            self.conn.execute("DELETE FROM jobs WHERE id=501")
        else:
            self.conn.execute(
                "UPDATE jobs SET job_no='OTHER-PROJECT' WHERE id=501"
            )
        self.conn.commit()
        return self.conn


@pytest.mark.parametrize(("remove", "expected"), [
    (False, "target job number conflicts"),
    (True, "does not exist"),
])
def test_destination_changed_after_preflight_before_connect_cannot_publish(
    test_dbs, remove, expected,
):
    _, hub, _ = test_dbs
    bridge = _DestinationChangedAtConnect(hub, remove=remove)
    with pytest.raises(RuntimeError, match=expected):
        execute_jobhub_publishing(
            _approved_package(), bridge, user_name="Source Estimator"
        )
    # A separate read would have been stale; the only accepted identity
    # observation is made on the connection that actually writes.
    assert bridge.query_calls == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


def test_commercial_publish_reserves_writer_before_destination_identity_read(
    test_dbs,
):
    _, hub, bridge = test_dbs
    statements = []
    hub.set_trace_callback(statements.append)
    receipt = execute_jobhub_publishing(
        _approved_package(), bridge, user_name="Source Estimator"
    )
    hub.set_trace_callback(None)
    normalized = [statement.strip().upper() for statement in statements]
    begin_index = next(
        i for i, statement in enumerate(normalized)
        if statement.startswith("BEGIN IMMEDIATE")
    )
    identity_index = next(
        i for i, statement in enumerate(normalized)
        if statement.startswith("SELECT JOB_NO FROM JOBS WHERE ID=")
    )
    insert_index = next(
        i for i, statement in enumerate(normalized)
        if statement.startswith("INSERT INTO PAINTING_TAKEOFF_PACKAGES")
    )
    assert begin_index < identity_index < insert_index
    assert receipt["status"] == "Published"
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


def test_draft_publish_uses_same_atomic_destination_identity_check(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = PublishingMode.DRAFT.value
    package.payload_hash = package.compute_payload_hash()
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["status"] == "Draft"
    assert hub.execute(
        "SELECT status FROM painting_takeoff_packages"
    ).fetchone()[0] == "Draft"


def test_duplicate_publish_rejected_within_reserved_transaction(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    execute_jobhub_publishing(package, bridge, user_name="Source Estimator")
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, user_name="Source Estimator")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


def test_line_write_failure_rolls_back_header_and_lines(test_dbs):
    _, hub, bridge = test_dbs
    hub.execute("""
        CREATE TRIGGER reject_line_insert BEFORE INSERT
        ON painting_takeoff_package_lines
        BEGIN SELECT RAISE(ABORT, 'line write rejected'); END;
    """)
    hub.commit()
    with pytest.raises(sqlite3.IntegrityError, match="line write rejected"):
        execute_jobhub_publishing(
            _approved_package(), bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


def test_existing_caller_transaction_still_checks_current_identity(test_dbs):
    _, hub, bridge = test_dbs
    hub.execute("UPDATE jobs SET job_no='UNRELATED' WHERE id=501")
    assert hub.in_transaction
    with pytest.raises(RuntimeError, match="target job number conflicts"):
        execute_jobhub_publishing(
            _approved_package(), bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


class _PostgresDialectCursor:
    """Translate only parameter syntax for an offline PostgreSQL-path smoke."""

    def __init__(self, conn, statements):
        self.cursor = conn.cursor()
        self.statements = statements

    def execute(self, sql, params=()):
        self.statements.append(sql.strip())
        # This adapter does NOT prove a live PostgreSQL server or row locking.
        # It verifies the actual downstream SQL uses PostgreSQL placeholders,
        # SELECT FOR UPDATE and INSERT RETURNING rather than SQLite lastrowid.
        assert "?" not in sql
        translated = sql.replace("%s", "?").replace(" FOR UPDATE", "")
        self.cursor.execute(translated, params)

    def fetchone(self):
        return self.cursor.fetchone()


class _PostgresDialectConnection:
    def __init__(self, sqlite_conn, statements):
        self.sqlite_conn = sqlite_conn
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.sqlite_conn.rollback()
        return False

    def cursor(self):
        return _PostgresDialectCursor(self.sqlite_conn, self.statements)

    def commit(self):
        self.sqlite_conn.commit()


class _PostgresDialectBridge:
    kind = "postgres"

    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn
        self.statements = []

    def connect(self):
        return _PostgresDialectConnection(
            self.sqlite_conn, self.statements
        )


def test_postgres_dialect_uses_locked_identity_and_returning_id(test_dbs):
    _, hub, _ = test_dbs
    bridge = _PostgresDialectBridge(hub)
    receipt = execute_jobhub_publishing(
        _approved_package(), bridge, user_name="Source Estimator"
    )
    assert receipt["status"] == "Published"
    assert bridge.statements[0] == (
        "SELECT job_no FROM jobs WHERE id=%s FOR UPDATE"
    )
    assert any(
        "RETURNING id" in sql and "INSERT INTO painting_takeoff_packages" in sql
        for sql in bridge.statements
    )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


def test_postgres_dialect_rejects_changed_target_before_insert(test_dbs):
    _, hub, _ = test_dbs
    hub.execute("UPDATE jobs SET job_no='WRONG' WHERE id=501")
    hub.commit()
    bridge = _PostgresDialectBridge(hub)
    with pytest.raises(RuntimeError, match="target job number conflicts"):
        execute_jobhub_publishing(
            _approved_package(), bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
