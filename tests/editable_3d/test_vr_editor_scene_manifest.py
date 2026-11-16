"""Source-owned browser/XR scene: display only, no publication authority."""
from __future__ import annotations

from dataclasses import replace
import math

import pytest

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, compile_editor_scene


def _scope():
    return EditorWorkspaceScope("work-1", "project-1", "doc-1", "rev-1",
                                "snap-1", "a" * 64, 1)


def _wall(**overrides):
    fields = dict(
        object_id="wall-1", object_type="wall", source_file_id="source-1",
        source_sheet="A100", source_page=2, geometry_ref="wall-1",
        original_geometry_ref="source-segment-17", level_id="level-1",
        revision_hash="object-revision-1",
        coordinates_or_measurements={
            "start_pt": [0.0, 0.0], "end_pt": [4.0, 0.0],
            "length": 4.0, "height": 2.7,
            "height_authority": "figured_dimension",
        },
        authority_status="review_required",
        dependent_quantity_ids=["quantity-1"],
    )
    fields.update(overrides)
    return EditableGeometryObject(**fields)


def test_scene_retains_source_and_object_identity_but_blocks_commercial():
    result = compile_editor_scene(_scope(), [_wall()],
                                  canonical_object_ids={"wall-1": "canonical-wall-1"})
    assert result["scope"]["sourceSha256"] == "a" * 64
    assert result["scope"]["revisionId"] == "rev-1"
    assert result["coordinateSystem"]["sourceToModelTransform"] is None
    assert result["readOnly"] is True
    assert result["commercialQuantityPublicationAllowed"] is False
    (obj,) = result["objects"]
    assert obj["canonicalObjectId"] == "canonical-wall-1"
    assert obj["objectRevision"] == "object-revision-1"
    assert obj["source"]["originalGeometryRef"] == "source-segment-17"
    assert obj["quantityLinks"] == ["quantity-1"]
    assert obj["geometry"] == {
        "kind": "wallFace", "start": [0.0, 0.0],
        "end": [4.0, 0.0], "heightM": 2.7,
    }
    assert obj["renderState"] == "review"
    assert obj["canEdit"] is False


def test_unknown_height_renders_only_plan_line_not_fabricated_wall():
    wall = _wall(coordinates_or_measurements={
        "start_pt": [0.0, 0.0], "end_pt": [4.0, 0.0],
        "length": 4.0, "height": 2.7,
        "height_authority": "unknown_height",
    }, authority_status="firm")
    (obj,) = compile_editor_scene(_scope(), [wall],
                                  canonical_object_ids={"wall-1": "canonical-wall-1"})["objects"]
    assert obj["geometry"]["kind"] == "wallLine"
    assert "heightM" not in obj["dimensions"]
    assert "wall_height_unverified" in obj["unresolvedIssues"]
    assert obj["renderState"] == "review"


@pytest.mark.parametrize("measurements", [
    {"start_pt": [0, 0], "end_pt": [4, 0], "length": 3, "height": 2.7,
     "height_authority": "figured_dimension"},
    {"start_pt": [0, 0], "end_pt": [math.nan, 0], "length": 4, "height": 2.7,
     "height_authority": "figured_dimension"},
    {"start_pt": [0, 0], "end_pt": [4, 0], "length": 4, "height": math.inf,
     "height_authority": "figured_dimension"},
])
def test_invalid_geometry_does_not_become_published_mesh(measurements):
    obj = compile_editor_scene(_scope(), [_wall(coordinates_or_measurements=measurements)])["objects"][0]
    assert obj["renderState"] == "review"
    assert obj["canEdit"] is False
    assert obj["geometry"] is None or obj["geometry"]["kind"] == "wallLine"


def test_missing_canonical_identity_cannot_be_assumed_from_geometry():
    obj = compile_editor_scene(_scope(), [_wall(authority_status="firm")])["objects"][0]
    assert obj["canonicalObjectId"] is None
    assert "canonical_identity_unresolved" in obj["unresolvedIssues"]
    assert obj["renderState"] != "verified"


def test_non_wall_objects_remain_inspector_only_without_authenticated_shape():
    room = _wall(object_id="room-1", object_type="room")
    obj = compile_editor_scene(_scope(), [room])["objects"][0]
    assert obj["geometry"] is None
    assert "render_geometry_not_authenticated" in obj["unresolvedIssues"]


def test_duplicate_objects_and_overlarge_scope_fail_closed():
    wall = _wall()
    with pytest.raises(ValueError, match="duplicate_object_id"):
        compile_editor_scene(_scope(), [wall, replace(wall)])
    with pytest.raises(ValueError, match="safety_cap"):
        compile_editor_scene(_scope(), [wall] * 20_001)


@pytest.mark.parametrize("sha,rev", [("", 1), ("bad", 1), ("a" * 64, -1),
                                       ("a" * 64, True)])
def test_unauthenticated_source_or_revision_is_rejected(sha, rev):
    with pytest.raises(ValueError):
        EditorWorkspaceScope("w", "p", "d", "r", "s", sha, rev)


def test_input_objects_not_mutated_and_deterministic_order():
    a, b = _wall(object_id="b"), _wall(object_id="a")
    old = (a.to_dict(), b.to_dict())
    forward = compile_editor_scene(_scope(), [a, b])
    reverse = compile_editor_scene(_scope(), [b, a])
    assert forward == reverse
    assert a.to_dict() == old[0] and b.to_dict() == old[1]
