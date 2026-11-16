"""Original painted orthogonal wall corners cannot be inferred from floor art."""
from __future__ import annotations

from dataclasses import replace
import fitz

from pb_source_painted_wall_corner_witness import (
    review_source_painted_wall_corners,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    build_floor_to_physical_wall_candidate_receipt,
)

SHA = "b" * 64


def _wall(bounds, *, layer="Enclosure_WallInternal", fill=(0, 0, 0),
          viewport_id="v1", type_="f"):
    return {
        "layer": layer, "type": type_, "fill": fill,
        "rect": fitz.Rect(*bounds), "items": (),
        "viewport_id": viewport_id,
    }


def _source():
    vertices = (
        (100, 100), (200, 100), (200, 180), (100, 180), (100, 100),
    )
    floor = {
        "layer": "Finish_Floor", "type": "f", "fill": (1, 1, 1),
        "rect": fitz.Rect(100, 100, 200, 180),
        "viewport_id": "v1",
        "items": tuple(
            ("l", fitz.Point(*a), fitz.Point(*b))
            for a, b in zip(vertices, vertices[1:])
        ),
    }
    return [
        floor,
        _wall((97, 100, 100, 180)),       # west
        _wall((100, 97, 200, 100)),       # north
        _wall((200, 100, 203, 180)),      # east
        _wall((100, 180, 200, 183)),      # south
    ]


def _receipt(drawings):
    return build_floor_to_physical_wall_candidate_receipt(
        drawings, [(135, 140, 160, 151, "BATH", 1, 0, 0)],
        "BATH", source_sha256=SHA, page_index=2,
    )


def test_four_real_perpendicular_painted_wall_corners_are_candidate_only():
    drawings = _source()
    review = review_source_painted_wall_corners(
        drawings, _receipt(drawings),
    )
    assert review.expected_corner_count == 4
    assert len(review.observed_corners) == 4
    assert review.missing_corner_indices == ()
    assert len({
        tuple(sorted(c.source_wall_path_ids))
        for c in review.observed_corners
    }) == 4
    assert all(c.native_wall_fill_gap_pdf_pt == 0 for c in review.observed_corners)
    assert not review.physical_room_authenticated
    assert not review.measurement_authorized
    assert not review.to_dict()["measurement_authorized"]


def test_corner_succeeds_with_real_small_native_fill_gap_but_no_approval():
    drawings = _source()
    drawings[2] = _wall((100, 97, 200, 99.72))
    review = review_source_painted_wall_corners(drawings, _receipt(drawings))
    assert len(review.observed_corners) == 4
    assert sum(c.native_wall_fill_gap_pdf_pt > 0 for c in review.observed_corners) >= 1
    assert not review.physical_room_authenticated


def test_missing_wall_end_cannot_be_closed_by_nearby_floor_outline():
    drawings = _source()
    drawings[2] = _wall((100, 97, 198, 100))
    review = review_source_painted_wall_corners(drawings, _receipt(drawings))
    assert len(review.observed_corners) < 4
    assert review.missing_corner_indices
    assert not review.measurement_authorized


def test_duplicate_competing_wall_owner_refuses_ambiguous_corner():
    drawings = _source()
    drawings.append(dict(drawings[2]))
    review = review_source_painted_wall_corners(drawings, _receipt(drawings))
    assert len(review.observed_corners) == 2
    assert len(review.missing_corner_indices) == 2


def test_floor_and_annotation_ink_never_substitute_painted_wall_owner():
    for layer, fill, type_ in (
        ("Finish_Floor", (0, 0, 0), "f"),
        ("Annotation_General", (0, 0, 0), "f"),
        ("Enclosure_WallInternal", (1, 1, 1), "f"),
        ("Enclosure_WallInternal", (0, 0, 0), "s"),
    ):
        drawings = _source()
        drawings[2] = _wall(
            (100, 97, 200, 100), layer=layer, fill=fill, type_=type_,
        )
        review = review_source_painted_wall_corners(
            drawings, _receipt(drawings),
        )
        assert len(review.observed_corners) < 4
        assert not review.measurement_authorized


def test_conflicting_source_viewport_and_invalid_source_identity_fail_closed():
    drawings = _source()
    drawings[2] = _wall((100, 97, 200, 100), viewport_id="foreign")
    review = review_source_painted_wall_corners(drawings, _receipt(drawings))
    assert len(review.observed_corners) < 4
    assert review.missing_corner_indices

    source = _source()
    receipt = _receipt(source)
    for forged in (
        replace(receipt, source_sha256="fake"),
        replace(receipt, page_index=-1),
        replace(receipt, floor_candidate_native_path_id=900),
        replace(receipt, floor_candidate_native_path_id=1),
    ):
        assert review_source_painted_wall_corners(source, forged) is None


def test_no_authorization_even_when_all_candidates_have_observed_corners():
    drawings = _source()
    receipt = _receipt(drawings)
    accepted = review_source_painted_wall_corners(drawings, receipt)
    assert len(accepted.observed_corners) == 4
    assert accepted.physical_room_authenticated is False
    assert accepted.measurement_authorized is False
    assert not any(c.physical_wall_authenticated for c in accepted.observed_corners)
    assert not any(c.measurement_authorized for c in accepted.observed_corners)


def test_no_large_hairline_snap_tolerance_that_changes_customer_geometry():
    drawings = _source()
    receipt = _receipt(drawings)
    assert review_source_painted_wall_corners(
        drawings, receipt, max_native_gap_pdf_pt=2.5,
    ) is None
