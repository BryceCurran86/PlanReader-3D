"""Review-only restoration preflight on synthetic immutable SQLite history."""
from dataclasses import replace
from hashlib import sha256
import json
import sqlite3

import pytest

from pb_plan_edit_revision_restore_preflight import (
    PlanRevisionRestoreBlocked, preview_plan_edit_restore,
)
from pb_plan_edit_revision_store import install_plan_edit_revision_schema
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import EditorWorkspaceScope

SOURCE = "a" * 64
RIDS = ("1" * 40, "2" * 40, "3" * 40)


def fixture():
    db = sqlite3.connect(":memory:")
    install_plan_edit_revision_schema(db)
    current_sha = SOURCE
    for number, rid in enumerate(RIDS, 1):
        blob = ("immutable review PDF " + str(number)).encode()
        digest = sha256(blob).hexdigest()
        command = json.dumps({"commandId": "c" + str(number)})
        db.execute(
            """INSERT INTO plan_edit_revisions (
                revision_id,tenant_id,workspace_id,workspace_db_id,document_id,
                source_revision_id,source_pdf_sha256,source_snapshot_id,
                revision_number,revision_label,parent_revision_id,
                parent_pdf_sha256,updated_pdf_sha256,updated_pdf_blob,
                previous_model_revision,updated_model_revision,command_sha256,
                idempotency_key,command_json,corrected_object_json,event_json,
                related_pages_json,actor_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, "tenant", "w", 1, "d", "source-rev", SOURCE, "snapshot",
             number, "PR-R000" + str(number),
             RIDS[number-2] if number > 1 else None,
             current_sha, digest, blob, number-1, number,
             sha256(command.encode()).hexdigest(), "k" + str(number),
             command, "{}", "{}",
             json.dumps([{"pageIndex": number % 2}]), "owner"),
        )
        current_sha = digest
    db.execute(
        """INSERT INTO plan_edit_revision_heads
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("tenant", "w", "d", SOURCE, "snapshot", RIDS[2], 3, 3, current_sha),
    )
    db.commit()
    scope = EditorWorkspaceScope(
        "w", "project", "d", "source-rev", "snapshot", SOURCE, 3)
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant", scope=scope, objects=[],
        canonical_object_ids={}, source_witnesses={})
    principal = EditorPrincipal(
        "reviewer", "tenant", frozenset({"w"}),
        frozenset({"w"}), frozenset({"w"}))
    return db, principal, workspace


def preview(db, principal, workspace, target=RIDS[0]):
    return preview_plan_edit_restore(
        db, principal=principal, workspace=workspace,
        target_revision_id=target)


def test_positive_preview_never_modifies_original_or_history():
    db, principal, workspace = fixture()
    before = db.total_changes
    result = preview(db, principal, workspace)
    assert result["interveningRevisionCount"] == 2
    assert result["potentiallyAffectedPageIndices"] == [0, 1]
    assert result["restoreWriteAuthorized"] is False
    assert result["restorePerformed"] is False
    assert result["newAtomicRevisionRequired"]
    assert not result["commercialPublicationAllowed"]
    assert db.total_changes == before


def test_latest_revision_cannot_be_restored_as_new_work():
    db, principal, workspace = fixture()
    with pytest.raises(PlanRevisionRestoreBlocked, match="target_must_be_older"):
        preview(db, principal, workspace, RIDS[2])


def test_cross_tenant_actor_denied():
    db, principal, workspace = fixture()
    outsider = EditorPrincipal(
        "other", "different", frozenset({"w"}),
        frozenset({"w"}), frozenset({"w"}))
    with pytest.raises(PermissionError):
        preview(db, outsider, workspace)


def test_stale_authenticated_workspace_head_denied():
    db, principal, workspace = fixture()
    stale = replace(workspace, scope=replace(workspace.scope, model_revision=1))
    with pytest.raises(PlanRevisionRestoreBlocked, match="current_head_not_loaded"):
        preview(db, principal, stale)


def test_tampered_middle_pdf_blocks_rollback_preflight():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET updated_pdf_blob=? WHERE revision_id=?",
               (b"altered", RIDS[1]))
    with pytest.raises(PlanRevisionRestoreBlocked, match="corrupt_revision_chain"):
        preview(db, principal, workspace)


def test_parent_chain_gap_blocks_rollback_preflight():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET parent_pdf_sha256=? WHERE revision_id=?",
               ("b" * 64, RIDS[1]))
    with pytest.raises(PlanRevisionRestoreBlocked, match="corrupt_revision_chain"):
        preview(db, principal, workspace)


def test_missing_head_blocks_rollback_preflight():
    db, principal, workspace = fixture()
    db.execute("DELETE FROM plan_edit_revision_heads")
    with pytest.raises(PlanRevisionRestoreBlocked, match="corrupt_revision_chain"):
        preview(db, principal, workspace)


def test_malformed_intervening_page_manifest_blocks_preview():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET related_pages_json=? WHERE revision_id=?",
               (json.dumps([{"pageIndex": -1}]), RIDS[1]))
    with pytest.raises(PlanRevisionRestoreBlocked, match="invalid_page_evidence"):
        preview(db, principal, workspace)
