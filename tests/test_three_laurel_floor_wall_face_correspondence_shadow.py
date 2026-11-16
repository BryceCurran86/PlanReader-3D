"""The floor candidate is NOT physical wall/door/customer authority.

Exercises typed native wall ownership and the path-level diagnostic output.
The original 3Laurel SHA-pinned page is replayed separately on Bryce's PC;
public CI does not require private originals.
"""

import fitz

from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    build_floor_to_physical_wall_candidate_receipt,
)


def _floor_rect(*, layer="Finish_Floor", viewport=None):
    coords = [(100, 100), (200, 100), (200, 180), (100, 180), (100, 100)]
    items = [("l", fitz.Point(*a), fitz.Point(*b)) for a, b in zip(coords, coords[1:])]
    row = {
        "layer": layer,
        "type": "f",
        "fill": (1.0, 1.0, 1.0),
        "rect": fitz.Rect(100, 100, 200, 180),
        "items": items,
    }
    if viewport:
        row["source_viewport_id"] = viewport
    return row


def _wall(bounds, *, layer="Enclosure_WallInternal", viewport=None):
    r = {
        "layer": layer,
        "type": "f",
        "fill": (0.0, 0.0, 0.0),
        "rect": fitz.Rect(*bounds),
        "items": [],
    }
    if viewport:
        r["source_viewport_id"] = viewport
    return r


def _words(label="MEDIA"):
    return [(140.0, 130.0, 160.0, 141.0, label, 0, 0, 0)]


def _four_walls():
    return [
        _wall((97, 100, 100, 180)),
        _wall((200, 100, 203, 180)),
        _wall((100, 97, 200, 100)),
        _wall((100, 180, 200, 183)),
    ]


def test_original_source_wall_layer_receipt_has_four_real_owned_sides():
    d = [_floor_rect(), *_four_walls()]
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.floor_candidate_native_path_id == 0
    assert r.supporting_native_wall_paths == (1, 2, 3, 4)
    assert len(r.wall_face_candidates) == 4
    assert r.supported_boundary_pdf_pt == r.total_boundary_pdf_pt == 360.0
    assert all(
        s.supported_length_pdf_pt == s.length_pdf_pt for s in r.wall_face_candidates
    )
    assert r.status == "ABSTAINED"
    assert r.physical_wall_authenticated is False
    assert r.measurement_authorized is False
    emitted = r.to_dict()
    assert emitted["measurement_authorized"] is False
    assert emitted["supporting_native_wall_paths"] == [1, 2, 3, 4]


def test_floor_finish_outline_and_annotations_cannot_be_wall_proof():
    d = [_floor_rect(), *_four_walls()]
    for source in d[1:]:
        source["layer"] = "Annotation_Dimensions"
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.floor_candidate_native_path_id == 0
    assert r.supported_boundary_pdf_pt == 0.0
    assert r.supporting_native_wall_paths == ()
    assert all(s.uncovered_intervals_pdf_pt for s in r.wall_face_candidates)
    assert r.measurement_authorized is False


def test_unowned_other_floor_paint_cannot_satisfy_missing_physical_walls():
    d = [_floor_rect(), _floor_rect(), *_four_walls()[1:]]
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.floor_candidate_native_path_id == 0
    assert 1 not in r.supporting_native_wall_paths  # floor never a wall
    assert r.supported_boundary_pdf_pt < r.total_boundary_pdf_pt
    assert r.physical_wall_authenticated is False


def test_wrong_viewport_wall_owner_does_not_cover_missing_side():
    d = [_floor_rect(viewport="FLOOR_PLAN"), *_four_walls()]
    d[1]["source_viewport_id"] = "ELEVATION"
    d[2]["source_viewport_id"] = "FLOOR_PLAN"
    d[3]["source_viewport_id"] = "FLOOR_PLAN"
    d[4]["source_viewport_id"] = "FLOOR_PLAN"
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert 1 not in r.supporting_native_wall_paths
    assert r.supported_boundary_pdf_pt == 280.0
    assert r.measurement_authorized is False


def test_genuine_doors_leave_an_uncovered_threshold_not_guessed_solid_wall():
    d = [_floor_rect(), *_four_walls()]
    d[4]["rect"] = fitz.Rect(100, 180, 150, 183)
    d.append(_wall((170, 180, 200, 183)))
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.total_boundary_pdf_pt == 360.0
    assert r.supported_boundary_pdf_pt == 340.0
    bottom = [s for s in r.wall_face_candidates if s.side == "south"]
    assert len(bottom) == 1
    assert bottom[0].uncovered_intervals_pdf_pt == ((150.0, 170.0),)
    assert r.measurement_authorized is False


def test_missing_label_or_unclosed_floor_candidate_abstains():
    d = [_floor_rect(), *_four_walls()]
    assert (
        build_floor_to_physical_wall_candidate_receipt(d, (), "MEDIA").status
        == "ABSTAINED"
    )
    assert (
        build_floor_to_physical_wall_candidate_receipt(d, (), "MEDIA").reason
        == "source_label_missing"
    )
    d[0]["items"] = d[0]["items"][:-1]
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.floor_candidate_native_path_id is None
    assert r.reason == "no_source_floor_candidate_containing_label"
    assert r.measurement_authorized is False


def test_any_false_rectangle_or_arbitrary_mismatch_is_diagnostic_not_issuer():
    d = [_floor_rect(), *_four_walls()]
    d[1]["layer"] = ""
    d[2]["fill"] = (1.0, 1.0, 1.0)
    d[3]["layer"] = "Interior_Joinery"
    d[4]["layer"] = "Finish_Floor"
    r = build_floor_to_physical_wall_candidate_receipt(d, _words(), "MEDIA")
    assert r.floor_candidate_native_path_id == 0
    assert r.supporting_native_wall_paths == ()
    assert r.supported_boundary_pdf_pt == 0.0
    assert not r.physical_wall_authenticated
