"""W4 mark-local boundary audit only; never promote source or finish rights."""
from types import SimpleNamespace
from copy import deepcopy

import pytest

from tools.diag_gpt2_p11_ft3_mark_local_face_gates import audit_mark_local_faces


def _sources(*, tainted=(), excluded=(), degenerate=(), polygons=None):
    default = (
        ("room-a", ((0, 0), (20, 0), (20, 20), (0, 20)), ("wall-a",)),
        ("room-b", ((30, 0), (50, 0), (50, 20), (30, 20)), ("wall-b",)),
    )
    witnesses = [{
        "face_id": fid, "polygon_pdf_pts": poly,
        "bounding_wall_ids": walls, "area_page_pts2": 400.0,
    } for fid, poly, walls in (polygons if polygons is not None else default)]
    wall = SimpleNamespace(
        records=tuple(range(8)), viewport_bbox=(0, 0, 100, 100),
        boundary_evaluation=SimpleNamespace(
            status="evaluated", boundary_tainted_wall_candidate_ids=tainted,
            excluded_boundary_primitives=excluded,
        )
    )
    face = SimpleNamespace(
        records=(), ownership_evaluation=SimpleNamespace(
            status="evaluated",
            owned_face_ids=tuple(x["face_id"] for x in witnesses),
            degenerate_owned_face_ids=degenerate,
        )
    )
    return wall, face, witnesses


def _mark(obs="native-a", xy=(10, 10), verified=True):
    x, y = xy
    return {
        "source_word_observation_id": obs,
        "native_bbox_pdf_pts": (x - 1, y - 1, x + 1, y + 1),
        "source_text_verified": verified,
        "text": "FT3",
    }


def _run(marks, **kw):
    wall, face, witnesses = _sources(**kw)
    return audit_mark_local_faces(
        wall=wall, face=face, witnesses=witnesses, marks=marks
    )


def _one(out):
    return out["mark_local_boundary_first_gates"][0]


def test_single_containing_w4_face_is_not_a_room_or_material_owner():
    a = _run([_mark()])
    row = _one(a)
    assert row["first_unclosed_gate"] == "one_shadow_face_not_authentic_physical_room"
    assert [c["shadow_face_id"] for c in row["all_containing_shadow_faces"]] == ["room-a"]
    assert row["all_containing_shadow_faces"][0]["first_boundary_gates"] == [
        "shadow_edge_ownership_only_not_physical_room"
    ]
    assert not row["physical_room_identity_published"]
    assert not row["ft3_occurrence_published"]
    assert not row["finish_area_published"]
    assert not a["new_material_occurrence_or_metric_quantity_published"]


def test_native_text_untrusted_abstains_even_with_containing_face():
    a = _run([_mark(verified=False)])
    assert _one(a)["first_unclosed_gate"] == "source_word_integrity_unresolved"
    assert len(_one(a)["all_containing_shadow_faces"]) == 1


def test_first_source_boundary_taint_is_preserved_without_electing_owner():
    a = _run([_mark()], tainted=("wall-a",))
    owner, = _one(a)["all_containing_shadow_faces"]
    assert owner["original_boundary_tainted_w4_ids"] == ["wall-a"]
    assert owner["first_boundary_gates"] == ["producer_w4_boundary_tainted"]


def test_excluded_native_primitive_touch_and_degenerate_abstain():
    excluded = (SimpleNamespace(
        source_observation_id="excluded-original-grid",
        x1=5., y1=5., x2=15., y2=5.,
    ),)
    a = _run([_mark()], excluded=excluded, degenerate=("room-a",))
    row, = _one(a)["all_containing_shadow_faces"]
    assert row["excluded_original_source_observation_ids"] == ["excluded-original-grid"]
    assert "original_excluded_structural_primitive_touches_face" in row["first_boundary_gates"]
    assert "producer_shadow_degenerate_or_tiny" in row["first_boundary_gates"]


def test_multiple_shadow_containing_faces_no_nearest_or_first_election():
    overlap = (
        ("face-left", ((0, 0), (20, 0), (20, 20), (0, 20)), ("w1",)),
        ("face-right", ((5, 0), (25, 0), (25, 20), (5, 20)), ("w2",)),
    )
    out = _run([_mark()], polygons=overlap)
    assert _one(out)["first_unclosed_gate"] == "multiple_shadow_faces_at_original_mark"
    assert {x["shadow_face_id"] for x in _one(out)["all_containing_shadow_faces"]} == {
        "face-left", "face-right",
    }


def test_mark_on_boundary_keeps_boundary_ambiguity():
    out = _run([_mark(xy=(20, 10))])
    a, = _one(out)["all_containing_shadow_faces"]
    assert "mark_centre_on_face_boundary" in a["first_boundary_gates"]
    assert not a["source_verified_room_face"]


def test_mark_outside_authenticated_viewport_or_faces_stays_blocked():
    out = _run([_mark(xy=(90, 90))])
    assert _one(out)["first_unclosed_gate"] == "original_source_mark_not_inside_edge_owned_face"
    out = _run([_mark(xy=(110, 110))])
    assert _one(out)["first_unclosed_gate"] == "source_mark_outside_authenticated_viewport"


def test_witness_inventory_or_source_observation_collision_cannot_disappear():
    wall, face, witnesses = _sources()
    with pytest.raises(ValueError, match="repeated_original_native_word_receipt"):
        audit_mark_local_faces(
            wall=wall, face=face, witnesses=witnesses,
            marks=[_mark(), _mark()],
        )
    with pytest.raises(ValueError, match="source_shadow_witness_universe_incomplete"):
        audit_mark_local_faces(
            wall=wall, face=face, witnesses=witnesses[:1],
            marks=[_mark()],
        )


@pytest.mark.parametrize("transform", [
    lambda x, y: (x + 140, y + 90),
    lambda x, y: (-y + 190, x + 130),
    lambda x, y: (x * 2, y * 2),
])
def test_translation_rotation_scale_and_mark_order_do_not_select_a_room(transform):
    def rect(vertices):
        return tuple(transform(*v) for v in vertices)
    mark_a = _mark(xy=(10, 10))
    mark_b = _mark(obs="native-b", xy=(40, 10))
    original = _run([mark_b, mark_a])
    wall, face, witnesses = _sources()
    moved = [
        dict(w, polygon_pdf_pts=rect(w["polygon_pdf_pts"]))
        for w in deepcopy(witnesses)
    ]
    allpts = [p for w in moved for p in w["polygon_pdf_pts"]]
    wall.viewport_bbox = (
        min(p[0] for p in allpts) - 20,
        min(p[1] for p in allpts) - 20,
        max(p[0] for p in allpts) + 20,
        max(p[1] for p in allpts) + 20,
    )
    transformed = []
    for m in [mark_a, mark_b]:
        cx = (m["native_bbox_pdf_pts"][0] + m["native_bbox_pdf_pts"][2]) / 2
        cy = (m["native_bbox_pdf_pts"][1] + m["native_bbox_pdf_pts"][3]) / 2
        px, py = transform(cx, cy)
        transformed.append(_mark(obs=m["source_word_observation_id"], xy=(px, py)))
    out = audit_mark_local_faces(
        wall=wall, face=face, witnesses=tuple(reversed(moved)),
        marks=transformed,
    )
    assert [
        r["first_unclosed_gate"] for r in original["mark_local_boundary_first_gates"]
    ] == [
        r["first_unclosed_gate"] for r in out["mark_local_boundary_first_gates"]
    ]
