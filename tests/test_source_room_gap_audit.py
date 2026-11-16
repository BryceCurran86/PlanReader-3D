"""Host-backed openings remove only their exact original floor-edge intervals."""
from dataclasses import replace

import fitz

from pb_source_room_gap_audit import (
    audit_source_room_outline_remaining_gaps,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    build_floor_to_physical_wall_candidate_receipt,
)
from pb_three_laurel_floor_opening_correspondence_shadow import (
    match_source_exterior_openings_to_floor_wall_gaps,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge


def _fixture():
    points = ((100, 100), (200, 100), (200, 180), (100, 180), (100, 100))
    drawings = [{
        "layer": "Finish_Floor", "type": "f", "fill": (1., 1., 1.),
        "rect": fitz.Rect(100, 100, 200, 180),
        "items": tuple(
            ("l", fitz.Point(*a), fitz.Point(*b))
            for a, b in zip(points, points[1:])
        ),
    }]
    for bounds in (
        (97,100,100,180), (200,100,203,180), (100,180,200,183),
        (100,97,135,100), (165,97,200,100),
    ):
        drawings.append({
            "layer": "Enclosure_WallExternal",
            "type": "f", "fill": (0.,0.,0.),
            "rect": fitz.Rect(*bounds), "items": (),
        })
    words = [(140,130,160,141,"MEDIA",0,0,0)]
    receipt = build_floor_to_physical_wall_candidate_receipt(
        drawings, words, "MEDIA", page_index=2, source_sha256="a"*64,
    )
    window = WindowFootprintBridge(
        left_host_path_id=4, right_host_path_id=5,
        marker_path_ids=(8,9), label_text="ASW",
        bounds_pdf_pts=(135.,97.,165.,100.),
        axis="h",page_index=2,
    )
    witnesses = match_source_exterior_openings_to_floor_wall_gaps(
        receipt,(window,),
    )
    assert len(witnesses) == 1
    return receipt,witnesses


def test_exact_hosted_native_window_explains_only_original_gap():
    receipt,witnesses=_fixture()
    report=audit_source_room_outline_remaining_gaps(receipt,witnesses)
    assert report.original_floor_outline_uncovered_pdf_pt == 30.
    assert report.hosted_opening_coverage_pdf_pt == 30.
    assert report.remaining_unproved_pdf_pt == 0.
    assert report.remaining_sides == ()
    assert report.zero_gap_candidate is True
    assert report.room_enclosure_authenticated is False
    assert report.measurement_authorized is False
    assert report.to_dict()["measurement_authorized"] is False


def test_missing_or_wrong_source_host_leaves_exact_original_gap():
    receipt,witnesses=_fixture()
    for corrupt in (
        (),
        (replace(witnesses[0],source_page_index=3),),
        (replace(witnesses[0],opening_host_path_ids=(99,98)),),
        (replace(witnesses[0],floor_candidate_path_id=999),),
        (replace(witnesses[0],boundary_distance_pdf_pt=6.),),
        (replace(witnesses[0],opening_bounds_pdf_pts=(135.,91.,165.,94.)),),
        (replace(witnesses[0],physical_wall_authenticated=True),),
    ):
        result=audit_source_room_outline_remaining_gaps(receipt,corrupt)
        assert result.hosted_opening_coverage_pdf_pt == 0.
        assert result.remaining_unproved_pdf_pt == 30.
        assert result.zero_gap_candidate is False


def test_repeated_same_opening_never_inflates_supported_source_length():
    receipt,witnesses=_fixture()
    result=audit_source_room_outline_remaining_gaps(
        receipt,(*witnesses,*witnesses),
    )
    assert result.hosted_opening_coverage_pdf_pt == 30.
    assert result.remaining_unproved_pdf_pt == 0.


def test_bad_source_floor_path_or_digest_fails_closed():
    receipt,witnesses=_fixture()
    assert audit_source_room_outline_remaining_gaps(
        replace(receipt,floor_candidate_native_path_id=None),witnesses,
    ) is None
    assert audit_source_room_outline_remaining_gaps(
        replace(receipt,source_sha256="not-verified"),witnesses,
    ) is None
