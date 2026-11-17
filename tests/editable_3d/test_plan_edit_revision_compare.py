"""Synthetic scoped SQLite tests, no private plan PDFs or customer outputs."""
from hashlib import sha256
import json
import sqlite3

import pytest

from pb_plan_edit_revision_compare import (
    PlanRevisionComparisonError, compare_plan_edit_revisions,
)
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import EditorWorkspaceScope

SRC = "a" * 64
RIDS = ("1" * 40, "2" * 40, "3" * 40)


def fixture():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE plan_edit_revisions (
          revision_id TEXT, tenant_id TEXT, workspace_id TEXT,
          document_id TEXT, source_pdf_sha256 TEXT, source_snapshot_id TEXT,
          revision_number INTEGER, revision_label TEXT,
          parent_revision_id TEXT, parent_pdf_sha256 TEXT,
          updated_pdf_sha256 TEXT, updated_pdf_blob BLOB,
          previous_model_revision INTEGER, updated_model_revision INTEGER,
          related_pages_json TEXT, event_json TEXT
        );
    """)
    scope = EditorWorkspaceScope("w", "p", "d", "original1", "snap", SRC, 0)
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant", scope=scope, objects=[],
        canonical_object_ids={}, source_witnesses={})
    principal = EditorPrincipal(
        "estimator", "tenant", frozenset({"w"}),
        frozenset({"w"}), frozenset({"w"}))
    previous_sha = SRC
    for n, rid in enumerate(RIDS, 1):
        blob = ("review revision " + str(n)).encode()
        digest = sha256(blob).hexdigest()
        db.execute("INSERT INTO plan_edit_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (rid, "tenant", "w", "d", SRC, "snap", n,
                    "PR-R000" + str(n), RIDS[n-2] if n > 1 else None,
                    previous_sha, digest, blob, n-1, n,
                    json.dumps([{"pageIndex": n % 2, "requiresDrawingCoordination": True}]),
                    json.dumps({"object_id": "wall-1", "field": "height", "new_value": n})))
        previous_sha = digest
    db.commit()
    return db, principal, workspace


def compare(db, principal, workspace, left=RIDS[0], right=RIDS[2]):
    return compare_plan_edit_revisions(
        db, principal=principal, workspace=workspace,
        older_revision_id=left, newer_revision_id=right)


def test_compare_all_intervening_events_and_affected_pages():
    db, principal, workspace = fixture()
    result = compare(db, principal, workspace)
    assert result["interveningRevisionCount"] == 2
    assert result["affectedPageIndices"] == [0, 1]
    assert [x["revisionNumber"] for x in result["changes"]] == [2, 3]
    assert result["requiresApproval"] and not result["commercialPublicationAllowed"]
    assert not result["geometryRedrawn"]


def test_comparison_may_cover_one_adjacent_revision():
    db, principal, workspace = fixture()
    assert compare(db, principal, workspace, RIDS[0], RIDS[1])["interveningRevisionCount"] == 1


def test_reversed_and_equal_revision_ids_fail_closed():
    db, principal, workspace = fixture()
    with pytest.raises(PlanRevisionComparisonError):
        compare(db, principal, workspace, RIDS[1], RIDS[0])
    with pytest.raises(PlanRevisionComparisonError):
        compare(db, principal, workspace, RIDS[0], RIDS[0])


def test_cross_tenant_actor_denied():
    db, principal, workspace = fixture()
    attacker = EditorPrincipal(
        "attacker", "other-tenant", frozenset({"w"}),
        frozenset({"w"}), frozenset({"w"}))
    with pytest.raises(PermissionError):
        compare(db, attacker, workspace)


def test_tampered_intermediate_pdf_fails_closed():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET updated_pdf_blob=? WHERE revision_id=?",
               (b"tampered", RIDS[1]))
    with pytest.raises(ValueError, match="revision_pdf_integrity_failed"):
        compare(db, principal, workspace)


def test_broken_parent_or_model_chain_fails_closed():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET parent_pdf_sha256=? WHERE revision_id=?",
               ("b" * 64, RIDS[1]))
    with pytest.raises(PlanRevisionComparisonError, match="parent_or_model_gap"):
        compare(db, principal, workspace)


def test_missing_intermediate_revision_fails_closed():
    db, principal, workspace = fixture()
    db.execute("DELETE FROM plan_edit_revisions WHERE revision_id=?", (RIDS[1],))
    with pytest.raises(PlanRevisionComparisonError, match="missing_records"):
        compare(db, principal, workspace)
