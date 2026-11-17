"""Source-neutral SQLite fixtures for working-plan provenance packets."""
from hashlib import sha256
import json
import sqlite3

import pytest

from pb_plan_edit_revision_provenance import (
    PlanRevisionProvenanceError, export_plan_edit_revision_provenance,
)
from pb_plan_edit_revision_store import install_plan_edit_revision_schema
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import EditorWorkspaceScope

RID = "f" * 40
SOURCE = "a" * 64


def fixture():
    db = sqlite3.connect(":memory:")
    install_plan_edit_revision_schema(db)
    scope = EditorWorkspaceScope("w", "p", "d", "source-rev", "snap", SOURCE, 0)
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant", scope=scope, objects=[],
        canonical_object_ids={}, source_witnesses={})
    principal = EditorPrincipal(
        "reviewer", "tenant", frozenset({"w"}),
        frozenset({"w"}), frozenset({"w"}))
    command = {"commandId": "edit-1", "targetObjectId": "wall-1"}
    serialized = json.dumps(command, sort_keys=True, separators=(",", ":"))
    blob = b"synthetic protected review pdf"
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
        (RID, "tenant", "w", 1, "d", "source-rev", SOURCE, "snap",
         1, "PR-R0001", None, SOURCE, sha256(blob).hexdigest(), blob,
         0, 1, sha256(serialized.encode()).hexdigest(),
         "idempotency-1", serialized, "{}",
         json.dumps({"correction_id": "edit-1", "object_id": "wall-1",
                     "actor": "reviewer"}),
         json.dumps([{"pageIndex": 0}, {"pageIndex": 2}]), "reviewer"),
    )
    db.commit()
    return db, principal, workspace


def export(db, principal, workspace):
    return export_plan_edit_revision_provenance(
        db, principal=principal, workspace=workspace, revision_id=RID)


def test_packet_is_deterministic_and_contains_no_private_pdf_or_raw_event():
    db, principal, workspace = fixture()
    first = export(db, principal, workspace)
    assert first == export(db, principal, workspace)
    assert first["originalSourcePdfSha256"] == SOURCE
    assert first["reviewPageIndices"] == [0, 2]
    assert first["cryptographicallySigned"] is False
    assert not first["commercialPublicationAllowed"]
    assert "actor" not in first and "event" not in first
    assert b"synthetic protected review pdf" not in str(first).encode()
    digest = first.pop("packetSha256")
    canonical = json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
    assert sha256(canonical).hexdigest() == digest


def test_cross_tenant_read_rejected():
    db, _, workspace = fixture()
    attacker = EditorPrincipal(
        "outsider", "other", frozenset({"w"}), frozenset({"w"}), frozenset({"w"}))
    with pytest.raises(PermissionError):
        export(db, attacker, workspace)


def test_pdf_tamper_detected_before_export():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET updated_pdf_blob=?", (b"altered",))
    with pytest.raises(ValueError, match="revision_pdf_integrity_failed"):
        export(db, principal, workspace)


def test_command_digest_forgery_rejected():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET command_json=?",
               (json.dumps({"commandId": "forged", "targetObjectId": "wall-1"}),))
    with pytest.raises(PlanRevisionProvenanceError, match="provenance_mismatch"):
        export(db, principal, workspace)


def test_actor_and_source_revision_mismatch_rejected():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET actor_id=?", ("not-author",))
    with pytest.raises(PlanRevisionProvenanceError, match="provenance_mismatch"):
        export(db, principal, workspace)
    db.execute("UPDATE plan_edit_revisions SET actor_id=?,source_revision_id=?",
               ("reviewer", "wrong-source"))
    with pytest.raises(PlanRevisionProvenanceError, match="provenance_mismatch"):
        export(db, principal, workspace)


def test_duplicate_and_invalid_page_evidence_rejected():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET related_pages_json=?",
               (json.dumps([{"pageIndex": 0}, {"pageIndex": 0}]),))
    with pytest.raises(PlanRevisionProvenanceError, match="duplicated"):
        export(db, principal, workspace)
    db.execute("UPDATE plan_edit_revisions SET related_pages_json=?",
               (json.dumps([{"pageIndex": -1}]),))
    with pytest.raises(PlanRevisionProvenanceError, match="invalid"):
        export(db, principal, workspace)


def test_missing_page_coverage_rejected():
    db, principal, workspace = fixture()
    db.execute("UPDATE plan_edit_revisions SET related_pages_json='[]'")
    with pytest.raises(PlanRevisionProvenanceError, match="coverage_missing"):
        export(db, principal, workspace)
