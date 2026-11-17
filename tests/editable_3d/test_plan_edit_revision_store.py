"""Immutable related-page PlanReader revisions using actual SQLite + PDF."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import sqlite3

import fitz
import pytest

from pb_editable_3d_correction_model import (
    CorrectionSource, Editable3DCorrectionLedger, EditableGeometryObject,
)
from pb_plan_edit_revision_bundle import (
    RelatedPageCoverage, SourcePageLink, render_related_page_revision,
)
from pb_plan_edit_revision_store import (
    PlanRevisionConflict, install_plan_edit_revision_schema,
    save_plan_edit_revision, get_plan_edit_pdf, list_plan_edit_revisions,
)
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness


def _pdf():
    doc = fitz.open()
    for i in range(3):
        p = doc.new_page(width=540, height=600)
        p.insert_text((30, 120), f"ORIGINAL SHEET {i+1}: unchanged vector PDF")
    data = doc.tobytes()
    doc.close()
    return data


def _fixture():
    original = _pdf()
    digest = sha256(original).hexdigest()
    scope = EditorWorkspaceScope("w1", "p1", "d1", "rev1", "snapshot1", digest, 0)
    obj = EditableGeometryObject(
        object_id="wall-1", object_type="wall", source_file_id="pdf-1",
        source_page=1, source_sheet="A101",
        original_geometry_ref="path-18", geometry_ref="wall-1",
        revision_hash="source-revision",
        coordinates_or_measurements={
            "start_pt":[0.0,0.0], "end_pt":[4.0,0.0],
            "length":4.0, "height":2.4,
            "height_authority":"figured_dimension", "openings":[],
        },
    )
    witness = VerifiedSourceWitness(
        document_id="d1", revision_id="rev1", source_sha256=digest,
        source_file_id="pdf-1", source_page=1, source_sheet="A101",
        original_geometry_ref="path-18",
    )
    ws = AuthorizedSceneWorkspace(
        tenant_id="tenant1", scope=scope, objects=[obj],
        canonical_object_ids={"wall-1":"canonical-wall-1"},
        source_witnesses={"wall-1":witness},
    )
    user = EditorPrincipal(
        "estimator-1","tenant1", frozenset({"w1"}),
        frozenset({"w1"}), frozenset({"w1"}),
    )
    ledger = Editable3DCorrectionLedger()
    ledger.register_object(obj)
    links = (
        SourcePageLink(
            page_index=0, page_label="1", sheet="A101",
            document_id="d1", revision_id="rev1", source_sha256=digest,
            snapshot_id="snapshot1", canonical_object_id="canonical-wall-1",
            native_geometry_ref="path-18", relationship="origin",
            producer_status="original_source", evidence_ids=("native-path-18",),
            pdf_region=(20., 150., 220., 190.),
        ),
        SourcePageLink(
            page_index=1, page_label="2", sheet="A201",
            document_id="d1", revision_id="rev1", source_sha256=digest,
            snapshot_id="snapshot1", canonical_object_id="canonical-wall-1",
            native_geometry_ref="elevation-wall-18",
            relationship="cross_sheet", producer_status="corroborated",
            evidence_ids=("producer-registration-1", "callout-W01", "target-native-18"),
        ),
    )
    coverage = RelatedPageCoverage(
        document_id="d1", revision_id="rev1", source_sha256=digest,
        snapshot_id="snapshot1", canonical_object_id="canonical-wall-1",
        links=links, known_related_page_indices=(0,1), complete=True,
    )
    command = dict(
        commandId="command-1", idempotencyKey="key-1",
        workspaceId="w1", projectId="p1", documentId="d1",
        revisionId="rev1", snapshotId="snapshot1", sourceSha256=digest,
        baseModelRevision=0, targetObjectId="wall-1",
        targetRevisionHash="source-revision",
        targetCanonicalId="canonical-wall-1",
        commandType="SET_WALL_HEIGHT", payload={"newValue":3.0},
        reason="Verified documented elevation change",
    )
    return original, user, ws, ledger, coverage, command


def _conn():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE workspaces(id INTEGER PRIMARY KEY);
    INSERT INTO workspaces(id) VALUES (1);
    CREATE TABLE editable_3d_correction_events (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       workspace_id INTEGER NOT NULL, correction_id TEXT NOT NULL,
       object_id TEXT NOT NULL, object_type TEXT NOT NULL, field TEXT NOT NULL,
       old_value_json TEXT, new_value_json TEXT NOT NULL,
       reason TEXT NOT NULL, actor TEXT NOT NULL, source TEXT NOT NULL,
       previous_revision_hash TEXT, new_revision_hash TEXT NOT NULL,
       created_at TEXT NOT NULL,
       FOREIGN KEY(workspace_id) REFERENCES workspaces(id));
    CREATE TABLE editable_3d_object_state (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       workspace_id INTEGER NOT NULL, object_id TEXT NOT NULL,
       authority_status TEXT NOT NULL, approved_by TEXT, approved_at TEXT,
       revision_hash TEXT NOT NULL, correction_ids_json TEXT NOT NULL,
       updated_at TEXT NOT NULL,
       UNIQUE(workspace_id,object_id),
       FOREIGN KEY(workspace_id) REFERENCES workspaces(id));
    """)
    install_plan_edit_revision_schema(db)
    return db


def _save(db, fixture):
    original, user, ws, ledger, coverage, command = fixture
    return save_plan_edit_revision(
        db, principal=user, workspace=ws, workspace_db_id=1,
        ledger=ledger, command=command, original_pdf_bytes=original,
        page_coverage=coverage,
    )


def _annotation_count(page):
    return len(tuple(page.annots() or ()))


def test_save_one_version_annotates_every_verified_related_page_and_keeps_original():
    fixture = _fixture()
    original, user, ws, ledger, coverage, command = fixture
    db = _conn()
    before_hash = sha256(original).hexdigest()
    saved = _save(db, fixture)
    assert saved["saved"] is True
    assert saved["revisionLabel"] == "PR-R0001"
    assert saved["revisionNumber"] == 1
    assert saved["updatedModelRevision"] == 1
    assert saved["requiresApproval"] is True
    assert saved["commercialPublicationAllowed"] is False
    assert saved["geometryRedrawn"] is False
    assert [p["pageIndex"] for p in saved["pagesRevised"]] == [0,1]
    assert all(p["requiresDrawingCoordination"] for p in saved["pagesRevised"])
    assert sha256(original).hexdigest() == before_hash
    blob, digest = get_plan_edit_pdf(db, user, ws, saved["revisionId"])
    assert sha256(blob).hexdigest() == digest
    pdf = fitz.open(stream=blob, filetype="pdf")
    assert pdf.page_count == 3
    assert [_annotation_count(pdf[i]) for i in range(3)] == [2,1,0]
    for i in range(3):
        assert f"ORIGINAL SHEET {i+1}" in pdf[i].get_text()
    annotated = [a.info.get("content", "") for a in pdf[1].annots()]
    assert "PR-R0001" in annotated[0]
    pdf.close()
    assert len(list_plan_edit_revisions(db, user, ws)) == 1
    assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0] == 1
    state = db.execute(
        "SELECT authority_status, approved_by FROM editable_3d_object_state"
    ).fetchone()
    assert state[1] is None
    assert "review" in state[0].lower()
    assert ledger.events == ()  # no browser-side mutation


def test_idempotent_replay_does_not_insert_duplicate_event_or_pdf():
    fixture = _fixture()
    db = _conn()
    a = _save(db, fixture)
    b = _save(db, fixture)
    assert a == b
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0] == 1
    original, user, ws, ledger, coverage, command = fixture
    bad = dict(command, reason="Changed another reason")
    with pytest.raises(PlanRevisionConflict, match="idempotency_key_reused"):
        save_plan_edit_revision(
            db, principal=user, workspace=ws, workspace_db_id=1,
            ledger=ledger, command=bad, original_pdf_bytes=original,
            page_coverage=coverage,
        )


def test_second_saved_version_inherits_prior_page_marks_and_stale_edits_fail():
    original, user, ws, ledger, coverage, cmd = _fixture()
    db = _conn()
    first = _save(db, (original,user,ws,ledger,coverage,cmd))
    first_pdf, first_sha = get_plan_edit_pdf(db, user, ws, first["revisionId"])

    # Production loader would replay the saved event and update model revision.
    outcome = ledger.apply_correction(
        correction_id=cmd["commandId"], object_id="wall-1", field="height",
        new_value=3.0, reason=cmd["reason"], actor=user.subject_id,
        source=CorrectionSource.EDITOR_3D.value,
        expected_revision_hash=cmd["targetRevisionHash"],
    )
    assert outcome.ok
    obj = ledger.get_object("wall-1")
    ws2 = replace(ws, scope=replace(ws.scope, model_revision=1), objects=[obj])
    cmd2 = dict(cmd, commandId="command-2", idempotencyKey="key-2",
                targetRevisionHash=obj.revision_hash, baseModelRevision=1,
                payload={"newValue":3.2}, reason="Confirm latest roof section height")
    second = _save(db, (original,user,ws2,ledger,coverage,cmd2))
    assert second["revisionNumber"] == 2
    assert second["revisionLabel"] == "PR-R0002"
    assert second["parentRevisionId"] == first["revisionId"]
    assert second["updatedModelRevision"] == 2
    last_pdf, _ = get_plan_edit_pdf(db, user,ws2,second["revisionId"])
    assert last_pdf != first_pdf
    with fitz.open(stream=last_pdf,filetype="pdf") as pdf:
        assert [_annotation_count(pdf[i]) for i in range(3)] == [4,2,0]
    assert get_plan_edit_pdf(db, user, ws, first["revisionId"])[1] == first_sha
    with pytest.raises(PlanRevisionConflict, match="stale_document_model_revision"):
        save_plan_edit_revision(
            db, principal=user, workspace=ws, workspace_db_id=1,
            ledger=Editable3DCorrectionLedger(), command=dict(cmd,
                commandId="command-3", idempotencyKey="key-3"),
            original_pdf_bytes=original, page_coverage=coverage,
        )
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == 2


def test_any_unresolved_or_missing_related_page_abstains_without_partial_save():
    original,user,ws,ledger,coverage,cmd=_fixture()
    db=_conn()
    cases = [
        replace(coverage, complete=False),
        replace(coverage, unresolved_page_indices=(2,)),
        replace(coverage, known_related_page_indices=(0,1,2)),
        replace(coverage, links=coverage.links[:1]),
        replace(coverage, known_related_page_indices=(0,0)),
    ]
    for candidate in cases:
        with pytest.raises((ValueError, PlanRevisionConflict)):
            save_plan_edit_revision(
                db, principal=user, workspace=ws, workspace_db_id=1,
                ledger=ledger, command=cmd, original_pdf_bytes=original,
                page_coverage=candidate,
            )
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0] == 0


def test_wrong_source_pdf_and_missing_write_grant_block_before_writes():
    original,user,ws,ledger,coverage,cmd=_fixture()
    db=_conn()
    with pytest.raises(PlanRevisionConflict, match="original_source_pdf_identity"):
        save_plan_edit_revision(
            db, principal=user, workspace=ws, workspace_db_id=1,
            ledger=ledger, command=cmd, original_pdf_bytes=original + b"F",
            page_coverage=coverage,
        )
    viewer = replace(user, allowed_revision_workspace_ids=frozenset())
    with pytest.raises(PermissionError, match="revision_save_permission"):
        save_plan_edit_revision(
            db, principal=viewer, workspace=ws, workspace_db_id=1,
            ledger=ledger, command=cmd, original_pdf_bytes=original,
            page_coverage=coverage,
        )
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == 0


def test_transaction_rollback_if_legacy_correction_state_write_fails():
    fixture=_fixture()
    db=_conn()
    db.execute("DROP TABLE editable_3d_object_state")
    with pytest.raises(sqlite3.OperationalError):
        _save(db,fixture)
    assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM plan_edit_revision_heads").fetchone()[0] == 0


def test_wrong_tenant_cannot_fetch_revision_or_history():
    fixture=_fixture()
    original,user,ws,ledger,coverage,cmd=fixture
    db=_conn()
    saved=_save(db,fixture)
    attacker=EditorPrincipal(
        "other","other-tenant", frozenset({"w1"}),
        frozenset({"w1"}), frozenset({"w1"}),
    )
    with pytest.raises(PermissionError):
        get_plan_edit_pdf(db, attacker, ws, saved["revisionId"])
    with pytest.raises(PermissionError):
        list_plan_edit_revisions(db, attacker, ws)
