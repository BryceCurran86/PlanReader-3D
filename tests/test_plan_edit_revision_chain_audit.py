"""Pure SQLite test fixtures: no private PDF or production data."""
from hashlib import sha256
import sqlite3

import pytest

from pb_plan_edit_revision_chain_audit import audit_plan_edit_revision_chain

KEY = ("tenant", "workspace", "document", "a" * 64, "snapshot")


def fixture_db():
    db = sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE plan_edit_revisions (
      revision_id TEXT, tenant_id TEXT, workspace_id TEXT, document_id TEXT,
      source_pdf_sha256 TEXT, source_snapshot_id TEXT,
      revision_number INTEGER, parent_revision_id TEXT,
      parent_pdf_sha256 TEXT, updated_pdf_sha256 TEXT, updated_pdf_blob BLOB,
      previous_model_revision INTEGER, updated_model_revision INTEGER
    );
    CREATE TABLE plan_edit_revision_heads (
      tenant_id TEXT, workspace_id TEXT, document_id TEXT,
      source_pdf_sha256 TEXT, source_snapshot_id TEXT,
      revision_id TEXT, revision_number INTEGER, updated_pdf_sha256 TEXT,
      model_revision INTEGER
    );
    """)
    return db


def add_revision(db, n, *, parent_id=None, parent_sha=None, prev_model=None):
    blob = ("test PDF " + str(n)).encode()
    pdf_sha = sha256(blob).hexdigest()
    if parent_sha is None:
        parent_sha = KEY[3] if n == 1 else sha256(("test PDF " + str(n-1)).encode()).hexdigest()
    if parent_id is None:
        parent_id = None if n == 1 else "r" + str(n-1)
    before = n - 1 if prev_model is None else prev_model
    db.execute("INSERT INTO plan_edit_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("r" + str(n), *KEY, n, parent_id, parent_sha,
                pdf_sha, blob, before, before + 1))
    db.execute("DELETE FROM plan_edit_revision_heads")
    db.execute("INSERT INTO plan_edit_revision_heads VALUES (?,?,?,?,?,?,?,?,?)",
               (*KEY, "r" + str(n), n, pdf_sha, before + 1))
    return pdf_sha


def test_empty_scoped_chain_is_valid():
    assert audit_plan_edit_revision_chain(fixture_db(), KEY).intact


def test_valid_two_revision_chain():
    db = fixture_db()
    add_revision(db, 1)
    add_revision(db, 2)
    result = audit_plan_edit_revision_chain(db, KEY)
    assert result.intact and result.revision_count == 2


def test_pdf_tampering_detected():
    db = fixture_db()
    add_revision(db, 1)
    db.execute("UPDATE plan_edit_revisions SET updated_pdf_blob=?", (b"altered",))
    assert "revision_1_pdf_hash_mismatch" in audit_plan_edit_revision_chain(db, KEY).errors


def test_parent_and_model_gaps_detected():
    db = fixture_db()
    add_revision(db, 1)
    add_revision(db, 2, parent_sha="b" * 64, prev_model=9)
    issues = audit_plan_edit_revision_chain(db, KEY).errors
    assert "revision_2_parent_mismatch" in issues
    assert "revision_2_model_revision_gap" in issues


def test_missing_head_and_orphan_head_detected():
    db = fixture_db()
    add_revision(db, 1)
    db.execute("DELETE FROM plan_edit_revision_heads")
    assert "revision_head_missing" in audit_plan_edit_revision_chain(db, KEY).errors
    db.execute("DELETE FROM plan_edit_revisions")
    db.execute("INSERT INTO plan_edit_revision_heads VALUES (?,?,?,?,?,?,?,?,?)",
               (*KEY, "ghost", 1, "b" * 64, 1))
    assert "orphan_revision_head" in audit_plan_edit_revision_chain(db, KEY).errors


def test_cross_tenant_scope_isolated():
    db = fixture_db()
    add_revision(db, 1)
    other = ("different-tenant", *KEY[1:])
    assert audit_plan_edit_revision_chain(db, other).revision_count == 0


def test_malformed_scope_rejected():
    with pytest.raises(ValueError):
        audit_plan_edit_revision_chain(fixture_db(), ("tenant",))


class NoBulkCursor:
    def __init__(self, cursor):
        self.cursor = cursor
    def __iter__(self):
        return iter(self.cursor)
    def fetchall(self):
        raise AssertionError("revision PDFs must be streamed, never fetched in bulk")


class StreamingGuardConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        cursor = super().execute(sql, parameters)
        if "FROM plan_edit_revisions" in sql and "SELECT" in sql:
            return NoBulkCursor(cursor)
        return cursor


def test_long_pdf_chain_uses_streaming_cursor_not_fetchall():
    db = fixture_db()
    for number in range(1, 101):
        add_revision(db, number)
    # The source connection has uncommitted inserts. sqlite3.backup() otherwise
    # blocks waiting for its own write transaction, masking the audit result.
    db.commit()
    gated = sqlite3.connect(":memory:", factory=StreamingGuardConnection)
    db.backup(gated)
    result = audit_plan_edit_revision_chain(gated, KEY)
    assert result.intact
    assert result.revision_count == 100
    other = ("different-tenant", *KEY[1:])
    assert audit_plan_edit_revision_chain(gated, other).revision_count == 0
