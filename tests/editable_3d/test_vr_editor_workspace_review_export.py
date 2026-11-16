"""Real workspace masses may be previewed, never silently given PDF ownership."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_workspace_review_export import export_workspace_review_scene


def _wall(object_id="wall-1", **overrides):
    fields = dict(
        object_id=object_id, object_type="wall",
        source_page=2, source_sheet="A101",
        geometry_ref=object_id, original_geometry_ref="opaque-mass-1",
        revision_hash="r1", authority_status="firm",
        coordinates_or_measurements={
            "start_pt": [0.0, 0.0], "end_pt": [4.0, 0.0],
            "length": 4.0, "height": 2.4,
            "height_authority": "figured_dimension",
        },
    )
    fields.update(overrides)
    return EditableGeometryObject(**fields)


def _export(*, workspace=None, document=None, objects=None, correction_count=1):
    return export_workspace_review_scene(
        workspace=workspace or {"id": 7, "job_no": "JOB-7"},
        document=document or {
            "id": 14, "workspace_id": 7, "sha256": "a" * 64,
            "mime_type": "application/pdf", "file_name": "Original.pdf",
        },
        objects=[_wall()] if objects is None else objects,
        correction_count=correction_count,
    )


def test_firm_wall_from_opaque_mass_remains_unverified_in_real_workspace_export():
    scene = _export()
    assert scene["readOnly"] is True
    assert scene["commercialQuantityPublicationAllowed"] is False
    assert scene["scope"]["documentId"] == "14"
    assert scene["scope"]["workspaceId"] == "7"
    assert scene["scope"]["sourceSha256"] == "a" * 64
    (wall,) = scene["objects"]
    assert wall["renderState"] == "review"
    assert wall["canEdit"] is False
    assert wall["canonicalObjectId"] is None
    assert "canonical_identity_unresolved" in wall["unresolvedIssues"]
    assert wall["geometry"]["kind"] == "wallFace"  # display only, not quantity


def test_foreign_workspace_document_cannot_be_exported():
    with pytest.raises(ValueError, match="outside_workspace"):
        _export(document={
            "id": 14, "workspace_id": 8,
            "sha256": "a" * 64, "file_name": "foreign.pdf",
        })


@pytest.mark.parametrize("bad_hash", ["", "not-a-sha", "a" * 63, None])
def test_missing_original_document_sha_fail_closed(bad_hash):
    with pytest.raises(ValueError, match="sha256_missing"):
        _export(document={
            "id": 14, "workspace_id": 7,
            "sha256": bad_hash, "file_name": "Original.pdf",
        })


def test_cannot_use_unrelated_non_pdf_attachment_as_drawing():
    with pytest.raises(ValueError, match="requires_pdf"):
        _export(document={
            "id": 14, "workspace_id": 7, "sha256": "a" * 64,
            "mime_type": "text/plain", "file_name": "notes.txt",
        })


def test_deterministic_reversed_input_and_live_object_not_modified():
    a, b = _wall("a"), _wall("b")
    snapshot = [a.to_dict(), b.to_dict()]
    first = _export(objects=[b, a])
    second = _export(objects=[a, b])
    assert first == second
    assert [o["objectId"] for o in first["objects"]] == ["a", "b"]
    assert [a.to_dict(), b.to_dict()] == snapshot


def test_snapshot_changes_with_actual_geometry_or_correction_count():
    original = _wall()
    first = _export(objects=[original])
    measurements = dict(original.coordinates_or_measurements)
    measurements["height"] = 2.7
    changed = _export(objects=[replace(original, coordinates_or_measurements=measurements)])
    assert first["scope"]["snapshotId"] != changed["scope"]["snapshotId"]
    later = _export(objects=[original], correction_count=2)
    assert first["scope"]["snapshotId"] != later["scope"]["snapshotId"]
    assert later["scope"]["modelRevision"] == 2


@pytest.mark.parametrize("count", [-1, 1.3, True])
def test_bad_revision_event_count_not_accepted(count):
    with pytest.raises(ValueError, match="invalid_correction_count"):
        _export(correction_count=count)


def test_unverified_source_does_not_invent_a_height_or_source_path():
    obj = _wall(
        source_page=None, source_sheet=None, original_geometry_ref=None,
        coordinates_or_measurements={
            "start_pt": [0, 0], "end_pt": [4, 0],
            "length": 4, "height": 2.7,
            "height_authority": "unknown_height",
        },
    )
    wall = _export(objects=[obj])["objects"][0]
    assert wall["geometry"]["kind"] == "wallLine"
    assert wall["renderState"] == "review"
    assert "heightM" not in wall["dimensions"]
    assert wall["source"]["originalGeometryRef"] is None
