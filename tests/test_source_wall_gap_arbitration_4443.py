"""Regression: source-painted continuous wall outranks inferred opening-gap chords.

These are noncommercial room-preview tests: no measured floors or wall takeoff.
"""
from dataclasses import replace

from pb_structural_room_region_shadow import (
    _gap_covered_by_physical_wall,
    chord_id,
    derive_structural_room_regions,
)
from pb_structural_wall_ink_shadow import (
    OpeningGapCandidate,
    StructuralInkDecision,
    StructuralWallInkReport,
    WALL_NETWORK_INK_CANDIDATE,
)


def line(ident, x1, y1, x2, y2):
    return {"id": ident, "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def ink_for(scene, gaps):
    return StructuralWallInkReport(
        decisions=tuple(StructuralInkDecision(s["id"], WALL_NETWORK_INK_CANDIDATE,
                                               ("source_positive_test_wall",), None, 1)
                        for s in scene),
        class_table=(), network_count=1, darkest_ink_color=(0., 0., 0.),
        reason_codes=(), opening_gaps=tuple(gaps),
    )


def test_continuous_source_wall_rejects_false_opening_but_not_wall():
    # A false opening is asserted on the middle of the unbroken top wall.
    scene = [
        line("top", 100, 100, 400, 100),
        line("right", 400, 100, 400, 300),
        line("bottom", 400, 300, 100, 300),
        line("left", 100, 300, 100, 100),
    ]
    false_gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "ghost.a", "ghost.b")
    report = derive_structural_room_regions(scene, ink_for(scene, [false_gap]))
    assert len(report.regions) == 1
    assert report.chord_ids == ()
    assert report.suppressed_wall_covered_chord_ids == (chord_id(false_gap),)
    assert report.regions[0].closure_chord_ids == ()
    assert "top" in report.regions[0].boundary_primitive_ids


def test_genuine_door_gap_is_closed_by_typed_chord_and_keeps_ancestry():
    scene = [
        line("top.a", 100, 100, 170, 100),
        line("top.b", 220, 100, 400, 100),
        line("right", 400, 100, 400, 300),
        line("bottom", 400, 300, 100, 300),
        line("left", 100, 300, 100, 100),
    ]
    true_gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "top.a", "top.b")
    ink = ink_for(scene, [true_gap])
    closed = derive_structural_room_regions(scene, ink)
    open_ = derive_structural_room_regions(scene, replace(ink, opening_gaps=()))
    assert closed.chord_ids == (chord_id(true_gap),)
    assert closed.suppressed_wall_covered_chord_ids == ()
    assert len(closed.regions) == 1
    assert closed.regions[0].closure_chord_ids == (chord_id(true_gap),)
    assert open_.regions == ()


def test_crossing_or_parallel_nearby_wall_is_not_coverage_of_door_gap():
    gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "top.a", "top.b")
    assert not _gap_covered_by_physical_wall(gap, {
        "crossing_partition": (195, 70, 195, 130),
        "other_wall_face": (160, 102.6, 230, 102.6),
    })
    assert _gap_covered_by_physical_wall(gap, {
        "crossing_partition": (195, 70, 195, 130),
        "original_wall": (160, 100, 230, 100),
    })


def test_short_fragment_does_not_fabricate_continuity():
    gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "a", "b")
    assert not _gap_covered_by_physical_wall(gap, {"short": (180, 100, 195, 100)})


def test_fragmented_but_contiguous_source_wall_suppresses_false_gap():
    gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "a", "b")
    assert _gap_covered_by_physical_wall(gap, {
        "stroke1": (165, 100, 194, 100),
        "stroke2": (194, 100, 226, 100),
    })


def test_two_end_stubs_with_genuine_gap_do_not_count_as_continuous_wall():
    gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "a", "b")
    assert not _gap_covered_by_physical_wall(gap, {
        "stub1": (165, 100, 190, 100),
        "stub2": (200, 100, 225, 100),
    })


def test_ninety_five_percent_wall_coverage_is_not_permission_to_erase_a_gap():
    gap = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "a", "b")
    # A former 90% overlap rule wrongly suppressed this genuine 2.5 pt break.
    assert not _gap_covered_by_physical_wall(gap, {
        "almost_continuous": (170, 100, 217.5, 100),
    })


def test_reverse_direction_fragmented_wall_is_still_continuous():
    gap = OpeningGapCandidate((220, 100), (170, 100), 50, 2.6, "a", "b")
    assert _gap_covered_by_physical_wall(gap, {
        "first": (195, 100, 170, 100),
        "second": (220, 100, 195, 100),
    })
