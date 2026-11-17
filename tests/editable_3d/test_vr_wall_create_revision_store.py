"""Atomic original-source-safe creation and cross-sheet PDF regression tests."""
from dataclasses import replace
from hashlib import sha256
import io
import sqlite3

import fitz
import pytest

from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_scene_manifest import EditorWorkspaceScope
from pb_vr_wall_assembly_dependencies import NewWallDesign, WallAssemblySpecification
from pb_vr_wall_create_revision_store import (
    VerifiedNewWallPageProjection, VerifiedWallDrawingCoverage,
    WallCreateConflict, create_wall_and_related_page_revision,
    get_created_wall_pdf, install_wall_creation_schema, list_created_walls,
)


def fixture():
    pdf = fitz.open()
    for _ in range(3):
        pdf.new_page(width=500, height=450)
    original = pdf.tobytes()
    pdf.close()
    digest = sha256(original).hexdigest()
    scope = EditorWorkspaceScope(
        workspace_id="ws1", project_id="project1", document_id="doc1",
        revision_id="rev1", snapshot_id="snap1", source_sha256=digest,
        model_revision=0,
    )
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant1", scope=scope, objects=[],
        canonical_object_ids={},
    )
    principal = EditorPrincipal(
        "editor1", "tenant1", frozenset({"ws1"}),
        frozenset({"ws1"}), frozenset({"ws1"}),
    )
    wall = NewWallDesign(
        workspace_id="ws1", source_sha256=digest, snapshot_id="snap1",
        base_model_revision=0, proposal_id="wall1", level_id="ground",
        start_pt=(0., 0.), end_pt=(3., 0.), height_m=2.4,
    )
    spec = WallAssemblySpecification(
        specification_id="W01", framing_system="timber",
        plate_runs=2, stud_spacing_m=0.6, noggin_rows=1,
    )
    pages = (
        VerifiedNewWallPageProjection(0, "A101", "floor", "registered_floor",
                                      (55., 55.), (255., 55.)),
        VerifiedNewWallPageProjection(2, "A301", "section", "registered_section",
                                      (40., 90.), (140., 90.)),
    )
    coverage = VerifiedWallDrawingCoverage(
        "doc1", digest, "snap1", "wall1", True, (0, 2), pages,
    )
    db = sqlite3.connect(":memory:")
    install_wall_creation_schema(db)
    return db, principal, workspace, wall, spec, coverage, original


def save(fx, **overrides):
    db, principal, workspace, wall, spec, coverage, original = fx
    kwargs = dict(
        principal=principal, workspace=workspace, wall=wall,
        assembly=spec, routes=(), coverage=coverage,
        original_pdf=original, idempotency_key="request1",
        command_identity={"proposalId": "wall1", "newWall": True},
    )
    kwargs.update(overrides)
    return create_wall_and_related_page_revision(db, **kwargs)


def test_atomic_model_wall_and_two_pdf_vectors_with_original_untouched():
    fx = fixture()
    db, principal, ws, wall, spec, coverage, original = fx
    result = save(fx)
    assert result["persisted"] is True
    assert result["modelRevision"] == 1
    assert result["commercialPublicationAllowed"] is False
    assert len(result["pagesRevised"]) == 2
    assert {p["sheetId"] for p in result["pagesRevised"]} == {"A101", "A301"}
    assert result["canonicalWallId"].startswith("vr-wall:")
    saved = get_created_wall_pdf(db, principal, ws, result["revisionId"])
    assert saved != original
    assert sha256(original).hexdigest() == ws.scope.source_sha256
    pdf = fitz.open(stream=saved, filetype="pdf")
    try:
        assert len(pdf) == 3
        assert len(list(pdf[0].annots())) == 1
        assert len(list(pdf[2].annots())) == 1
        assert pdf[1].get_contents() is None or not pdf[1].get_text()
    finally:
        pdf.close()
    created = list_created_walls(db, principal, ws)
    assert len(created) == 1
    assert created[0]["canonicalWallId"] == result["canonicalWallId"]
    assert created[0]["workingDesignOnly"]


def test_idempotent_exact_replay_but_reused_token_or_proposal_rejected():
    fx = fixture()
    first = save(fx)
    second = save(fx)
    assert second["idempotentReplay"] is True
    assert second["revisionId"] == first["revisionId"]
    with pytest.raises(WallCreateConflict, match="idempotency"):
        save(fx, command_identity={"different": True})
    with pytest.raises(WallCreateConflict, match="proposal_already_exists"):
        save(fx, idempotency_key="request2")


def test_stale_source_model_or_incomplete_related_pages_rejected_without_write():
    fx = fixture()
    db, principal, workspace, wall, spec, coverage, original = fx
    with pytest.raises(WallCreateConflict, match="universe"):
        save(fx, coverage=replace(coverage, complete=False))
    with pytest.raises(WallCreateConflict, match="projection"):
        save(fx, coverage=replace(coverage, known_affected_page_indices=(0, 1, 2)))
    with pytest.raises(PermissionError):
        save(fx, wall=replace(wall, base_model_revision=1))
    with pytest.raises(WallCreateConflict, match="original_source"):
        save(fx, original_pdf=b"not the original")
    assert db.execute("SELECT COUNT(*) FROM vr_created_wall_revisions").fetchone()[0] == 0


def test_pdf_out_of_page_geometry_rolls_back_wall_and_head():
    fx = fixture()
    db, principal, ws, wall, spec, coverage, original = fx
    bad = VerifiedNewWallPageProjection(
        0, "A101", "floor", "registered_floor", (900., 30.), (990., 30.))
    with pytest.raises(WallCreateConflict, match="outside_page"):
        save(fx, coverage=replace(coverage, projections=(bad, coverage.projections[1])))
    assert db.execute("SELECT COUNT(*) FROM vr_created_wall_revisions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM vr_created_wall_heads").fetchone()[0] == 0


def test_tenant_and_read_grant_isolation():
    fx = fixture()
    db, principal, ws, wall, spec, coverage, original = fx
    save(fx)
    other = replace(principal, tenant_id="another")
    with pytest.raises(PermissionError):
        list_created_walls(db, other, ws)
    with pytest.raises(PermissionError):
        get_created_wall_pdf(db, other, ws, "a" * 40)


def test_successive_wall_revision_reuses_previous_pdf_and_increments_model():
    fx = fixture()
    db, principal, ws, wall, spec, coverage, original = fx
    one = save(fx)
    updated_ws = replace(ws, scope=replace(ws.scope, model_revision=1))
    wall2 = replace(wall, proposal_id="wall2", base_model_revision=1,
                    start_pt=(0., 1.), end_pt=(3., 1.))
    coverage2 = replace(coverage, proposal_id="wall2")
    two = save(fx, workspace=updated_ws, wall=wall2, coverage=coverage2,
               idempotency_key="request2",
               command_identity={"proposalId": "wall2"})
    assert two["revisionNumber"] == 2
    assert two["modelRevision"] == 2
    pdf = fitz.open(stream=get_created_wall_pdf(db, principal, updated_ws, two["revisionId"]),
                    filetype="pdf")
    try:
        assert len(list(pdf[0].annots())) == 2
        assert len(list(pdf[2].annots())) == 2
    finally:
        pdf.close()
    assert len(list_created_walls(db, principal, updated_ws)) == 2
