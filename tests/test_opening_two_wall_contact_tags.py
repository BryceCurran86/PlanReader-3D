"""Universal after-wall-trace two-sided opening tag regression tests.

No source PDF, benchmark target, room name, drawing name or customer issuer is
used. Angled wall junctions are supported even when both contacts coincide.
"""
from __future__ import annotations

from dataclasses import replace
import math

import fitz
import pytest

from pb_opening_two_wall_contact_tags import (
    DetectedOpeningContacts, OpeningWallContact, TracedWallSection,
    tag_native_segmented_doorway_chords, tag_opening_to_two_wall_sections,
)
from pb_layered_wall_doorway_room_ring_shadow import _Gap
from pb_source_segmented_door_swing_shadow import propose_source_owned_doorway_chords


SCOPE = ("a" * 64, "source-revision-a", "page-2")


def wall(ident, paths, a, b, *, scope=SCOPE):
    return TracedWallSection(ident, scope, paths, a, b)


def opening(a=(10., 0.), b=(12., 0.), *, a_paths=(100,), b_paths=(200,),
            scope=SCOPE):
    return DetectedOpeningContacts(
        "opening-a", scope, (300, 301),
        OpeningWallContact(a, a_paths),
        OpeningWallContact(b, b_paths),
    )


def two_straight():
    return (
        wall("segment-before", (100,), (0., 0.), (10., 0.)),
        wall("segment-after", (200,), (12., 0.), (20., 0.)),
    )


def test_opening_tagged_to_two_distinct_traced_wall_sections():
    tag = tag_opening_to_two_wall_sections(opening(), two_straight())
    assert tag.status == "TWO_WALL_SECTIONS_TAGGED"
    assert tag.wall_section_ids == ("segment-before", "segment-after")
    assert tag.contact_geometry == "STRAIGHT_GAP"
    assert tag.physical_host_authorized is False
    assert tag.measurement_authorized is False


@pytest.mark.parametrize("first_runs_in, second_runs_in", (
    (True, False), (False, True), (True, True),
))
@pytest.mark.parametrize("reverse_contacts", (False, True))
def test_straight_opening_rejects_wall_sections_that_run_into_gap(
    first_runs_in, second_runs_in, reverse_contacts,
):
    door = opening()
    first, second = two_straight()
    if first_runs_in:
        first = replace(first, start_pdf_pts=(18., 0.))
    if second_runs_in:
        second = replace(second, end_pdf_pts=(2., 0.))
    if reverse_contacts:
        door = replace(door, first=door.second, second=door.first)

    tag = tag_opening_to_two_wall_sections(door, (second, first))

    assert tag.status == "UNRESOLVED"
    assert tag.reason == "straight_wall_section_runs_into_opening"
    assert tag.wall_section_ids == ()
    assert tag.candidate_sections_first == (
        second.section_id if reverse_contacts else first.section_id,
    )
    assert tag.candidate_sections_second == (
        first.section_id if reverse_contacts else second.section_id,
    )


def test_one_opening_at_intersection_of_two_perpendicular_traced_walls():
    segments = (
        wall("wall-heading-east", (100,), (-10., 0.), (0., 0.)),
        wall("wall-heading-north", (200,), (0., 0.), (0., 12.)),
    )
    tag = tag_opening_to_two_wall_sections(opening((0., 0.), (0., 0.)), segments)
    assert tag.status == "TWO_WALL_SECTIONS_TAGGED"
    assert tag.wall_section_ids == ("wall-heading-east", "wall-heading-north")
    assert tag.contact_geometry == "WALL_JUNCTION"
    assert tag.measurement_authorized is False


def test_diagonal_wall_corner_and_angled_spanning_opening_are_not_forced_collinear():
    a = wall("diagonal", (100,), (-8., -8.), (0., 0.))
    b = wall("upright", (200,), (0., 0.), (0., 9.))
    junction = tag_opening_to_two_wall_sections(opening((0., 0.), (0., 0.)), (a, b))
    assert junction.contact_geometry == "WALL_JUNCTION"
    b2 = wall("offset", (200,), (2., 1.), (2., 10.))
    span = tag_opening_to_two_wall_sections(opening((0., 0.), (2., 1.)), (a, b2))
    assert span.status == "TWO_WALL_SECTIONS_TAGGED"
    assert span.contact_geometry == "ANGLED_OPENING"


@pytest.mark.parametrize("remove", [0, 1])
def test_opening_with_one_missing_real_wall_stays_unresolved(remove):
    sections = list(two_straight())
    sections.pop(remove)
    tag = tag_opening_to_two_wall_sections(opening(), sections)
    assert tag.status == "UNRESOLVED"
    assert tag.reason == "two_source_wall_end_contacts_required"
    assert tag.wall_section_ids == ()


def test_no_wrong_revision_or_page_wall_tagging():
    source = two_straight()
    swapped = replace(source[1], scope=("a" * 64, "other-revision", "page-2"))
    tag = tag_opening_to_two_wall_sections(opening(), (source[0], swapped))
    assert tag.status == "UNRESOLVED"
    assert tag.candidate_sections_first == ("segment-before",)
    assert not tag.candidate_sections_second


def test_nearby_unrelated_wall_without_native_source_proof_not_selected():
    sections = (*two_straight(), wall("unproven-neighbor", (400,), (12., 0.), (19., 0.)))
    tag = tag_opening_to_two_wall_sections(opening(), sections)
    assert tag.wall_section_ids == ("segment-before", "segment-after")


def test_native_path_id_without_real_wall_endpoint_is_not_a_tag():
    bad = wall("remote-wall", (200,), (13., 0.), (20., 0.))
    tag = tag_opening_to_two_wall_sections(opening(), (two_straight()[0], bad))
    assert tag.status == "UNRESOLVED"
    assert tag.reason == "two_source_wall_end_contacts_required"


def test_competing_sections_with_same_source_wall_path_are_retained_not_chosen():
    first, second = two_straight()
    competitor = replace(first, section_id="alternate-interpretation")
    tag = tag_opening_to_two_wall_sections(opening(), (first, second, competitor))
    assert tag.status == "UNRESOLVED"
    assert tag.reason == "competing_traced_wall_sections"
    assert set(tag.candidate_sections_first) == {"segment-before", "alternate-interpretation"}


def test_same_traced_wall_cannot_be_both_sides_of_opening():
    shared = wall("one-continuous-wall", (100, 200), (10., 0.), (12., 0.))
    tag = tag_opening_to_two_wall_sections(opening(), (shared,))
    assert tag.status == "UNRESOLVED"
    assert tag.reason == "one_wall_section_cannot_supply_two_sides"


def test_zero_span_collinear_mark_does_not_create_phantom_opening():
    a = wall("a", (100,), (-8., 0.), (0., 0.))
    b = wall("b", (200,), (0., 0.), (8., 0.))
    tag = tag_opening_to_two_wall_sections(opening((0., 0.), (0., 0.)), (a, b))
    assert tag.status == "UNRESOLVED"
    assert tag.reason == "coincident_collinear_contact_not_an_opening"


def test_duplicate_traced_section_id_abstains():
    a, b = two_straight()
    assert tag_opening_to_two_wall_sections(opening(), (a, replace(b, section_id=a.section_id))).status == "UNRESOLVED"


@pytest.mark.parametrize("invalid", [
    (True,), (1.0,), (-1,), ("a",), (2, 2), [],
])
def test_malformed_source_path_proofs_never_grant_wall_tags(invalid):
    bad = replace(opening(), first=OpeningWallContact((10., 0.), invalid))
    result = tag_opening_to_two_wall_sections(bad, two_straight())
    assert result.status == "UNRESOLVED"


def test_source_contact_nonfinite_and_boolean_coordinate_rejected():
    for point in ((float("nan"), 0.), (float("inf"), 0.), (True, 0.)):
        bad = replace(opening(), first=OpeningWallContact(point, (100,)))
        assert tag_opening_to_two_wall_sections(bad, two_straight()).status == "UNRESOLVED"


def test_translation_rotation_and_section_order_do_not_change_wall_ids():
    theta = math.pi / 3
    def transform(p):
        x, y = p
        return (round(x * math.cos(theta) - y * math.sin(theta) + 100., 8),
                round(x * math.sin(theta) + y * math.cos(theta) - 30., 8))
    walls = [
        replace(w, start_pdf_pts=transform(w.start_pdf_pts),
                end_pdf_pts=transform(w.end_pdf_pts))
        for w in two_straight()
    ]
    o = opening()
    transformed = replace(
        o, first=replace(o.first, position_pdf_pts=transform(o.first.position_pdf_pts)),
        second=replace(o.second, position_pdf_pts=transform(o.second.position_pdf_pts)),
    )
    result = tag_opening_to_two_wall_sections(transformed, tuple(reversed(walls)))
    assert result.wall_section_ids == ("segment-before", "segment-after")
    assert result.contact_geometry == "STRAIGHT_GAP"


def test_two_distinct_openings_may_share_a_real_wall_section():
    a, b = two_straight()
    c = wall("third-segment", (500,), (21., 0.), (30., 0.))
    second_door = opening((20., 0.), (21., 0.), a_paths=(200,), b_paths=(500,))
    assert tag_opening_to_two_wall_sections(opening(), (a, b, c)).status == "TWO_WALL_SECTIONS_TAGGED"
    assert tag_opening_to_two_wall_sections(second_door, (a, b, c)).status == "TWO_WALL_SECTIONS_TAGGED"


def test_existing_original_segmented_swing_chord_tag_uses_both_native_wall_ends():
    def stroke(p, q):
        return {"fill": None, "color": (0., 0., 0.),
                "items": [("l", fitz.Point(*p), fitz.Point(*q))]}
    # Actual source wall strokes end where the opening is drawn.
    drawings = (
        stroke((0., 10.), (10., 10.)),
        stroke((20., 10.), (30., 10.)),
        stroke((10., 7.), (10., 10.)),
        stroke((20., 7.), (20., 10.)),
    )
    witness = {
        "native_source_path_indices": (80, 81),
        "source_hinge_point_pdf_pts": (20., 10.),
        "source_closed_leaf_tip_pdf_pts": (10., 10.),
    }
    parent = _Gap(True, (7., 12.), 10., 50., (50,), (51,), False)
    chords = propose_source_owned_doorway_chords(drawings, (witness,), (parent,))
    assert len(chords) == 1
    tags = tag_native_segmented_doorway_chords(drawings, chords, scope=SCOPE)
    assert len(tags) == 1
    assert tags[0].status == "TWO_WALL_SECTIONS_TAGGED"
    assert tags[0].wall_section_ids == ("native-wall-end:0", "native-wall-end:1")
    assert tags[0].measurement_authorized is False


@pytest.mark.parametrize("malformed", (
    None, [None], [("l",)], ["l"], [("l", None, None)],
    "not_a_source_segment", [("qu", 12)],
))
def test_malformed_native_segmented_door_wall_end_does_not_crash_or_tag(malformed):
    """The review projection must never bring down original source tracing."""
    def stroke(a, b):
        return {"fill": None, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}
    drawings = (
        {"fill": None, "items": malformed},
        stroke((12., 0.), (20., 0.)),
    )
    chord = {
        "horizontal": True,
        "door_interval_pdf_pts": (10., 12.),
        "wall_band_pdf_pts": (-1., 1.),
        "source_wall_end_left_path_indices": (0,),
        "source_wall_end_right_path_indices": (1,),
        "source_swing_native_path_indices": (3,),
    }
    tags = tag_native_segmented_doorway_chords(drawings, (chord,), scope=SCOPE)
    assert len(tags) == 1
    assert tags[0].status == "UNRESOLVED"
    assert tags[0].measurement_authorized is False


def test_extreme_finite_coordinates_cannot_overflow_into_wall_authentication():
    first = wall("overflow", (100,), (1e308, 0.), (-1e308, 0.))
    second = two_straight()[1]
    observed = opening((1e308, 0.), (12., 0.))
    result = tag_opening_to_two_wall_sections(observed, (first, second))
    assert result.status == "UNRESOLVED"
    assert not result.wall_section_ids
    assert not result.measurement_authorized


def test_extreme_but_finite_perpendicular_wall_vectors_remain_junctions():
    length = 1e200
    source = (
        wall("east", (100,), (0., 0.), (length, 0.)),
        wall("north", (200,), (0., 0.), (0., length)),
    )
    result = tag_opening_to_two_wall_sections(
        opening((0., 0.), (0., 0.)), source,
    )
    assert result.status == "TWO_WALL_SECTIONS_TAGGED"
    assert result.contact_geometry == "WALL_JUNCTION"
    assert result.measurement_authorized is False


def test_original_chord_source_receipts_reject_numeric_coercion():
    """Source-native wall ends can be tagged; forged typed geometry cannot."""
    def stroke(a, b):
        return {"fill": None, "items": [
            ("l", fitz.Point(*a), fitz.Point(*b)),
        ]}

    drawings = (
        stroke((0., 0.), (10., 0.)),
        stroke((12., 0.), (20., 0.)),
        stroke((40., 0.), (50., 0.)),
    )
    good = {
        "horizontal": True,
        "door_interval_pdf_pts": (10., 12.),
        "wall_band_pdf_pts": (-1., 1.),
        "source_wall_end_left_path_indices": (0,),
        "source_wall_end_right_path_indices": (1,),
        "source_swing_native_path_indices": (2,),
    }
    valid = tag_native_segmented_doorway_chords(drawings, (good,), scope=SCOPE)[0]
    assert valid.status == "TWO_WALL_SECTIONS_TAGGED"
    assert valid.wall_section_ids == ("native-wall-end:0", "native-wall-end:1")
    assert valid.physical_host_authorized is False
    assert valid.measurement_authorized is False

    for field, malformed in (
        ("door_interval_pdf_pts", (True, 12.)),
        ("door_interval_pdf_pts", ("10", 12.)),
        ("door_interval_pdf_pts", (12., 10.)),
        ("wall_band_pdf_pts", (False, 1.)),
        ("wall_band_pdf_pts", ("-1", 1.)),
        ("wall_band_pdf_pts", (2., -2.)),
        ("source_wall_end_left_path_indices", (True,)),
        ("source_wall_end_right_path_indices", (1.0,)),
        ("source_swing_native_path_indices", ("2",)),
        ("source_swing_native_path_indices", (2, 2)),
    ):
        candidate = dict(good)
        candidate[field] = malformed
        out = tag_native_segmented_doorway_chords(
            drawings, (candidate,), scope=SCOPE,
        )[0]
        assert out.status == "UNRESOLVED", (field, malformed)
        assert out.reason == "source_chord_receipt_invalid", (field, malformed)
        assert out.wall_section_ids == ()
        assert out.measurement_authorized is False


@pytest.mark.parametrize("bad", (True, "10", None, float("nan"), float("inf")))
def test_native_wall_end_coordinates_reject_invalid_receipts(bad):
    """Malformed native endpoints cannot become two-wall source evidence."""
    class NativePoint:
        def __init__(self, x, y):
            self.x, self.y = x, y

    def stroke(a, b):
        return {"fill": None, "items": [("l", a, b)]}

    chord = {
        "horizontal": True,
        "door_interval_pdf_pts": (10., 12.),
        "wall_band_pdf_pts": (-1., 1.),
        "source_wall_end_left_path_indices": (0,),
        "source_wall_end_right_path_indices": (1,),
        "source_swing_native_path_indices": (2,),
    }
    drawings = (
        stroke(NativePoint(0., 0.), NativePoint(bad, 0.)),
        stroke(NativePoint(12., 0.), NativePoint(20., 0.)),
        stroke(NativePoint(30., 0.), NativePoint(40., 0.)),
    )
    result = tag_native_segmented_doorway_chords(drawings, (chord,), scope=SCOPE)[0]
    assert result.status == "UNRESOLVED"
    assert result.measurement_authorized is False
    assert not result.wall_section_ids


@pytest.mark.parametrize("field", ("door_interval_pdf_pts", "wall_band_pdf_pts"))
def test_oversized_native_chord_integer_fails_closed_without_crashing(field):
    """Huge native integer receipts cannot overflow the source adapter."""
    chord = {
        "horizontal": True,
        "door_interval_pdf_pts": (10., 12.),
        "wall_band_pdf_pts": (-1., 1.),
        "source_wall_end_left_path_indices": (0,),
        "source_wall_end_right_path_indices": (1,),
        "source_swing_native_path_indices": (2,),
    }
    chord[field] = (10 ** 1000, 10 ** 1001)
    result = tag_native_segmented_doorway_chords((), (chord,), scope=SCOPE)
    assert len(result) == 1
    assert result[0].status == "UNRESOLVED"
    assert result[0].reason == "source_chord_receipt_invalid"
    assert result[0].wall_section_ids == ()
    assert result[0].measurement_authorized is False


@pytest.mark.parametrize("contact", ((10 ** 1000, 0.), (0., -(10 ** 1000))))
def test_oversized_native_wall_contact_integer_fails_closed(contact):
    """A valid integer type may still be unrepresentable as PDF float."""
    bad = replace(opening(), first=OpeningWallContact(contact, (100,)))
    result = tag_opening_to_two_wall_sections(bad, two_straight())
    assert result.status == "UNRESOLVED"
    assert result.reason == "opening_contact_geometry_invalid"
    assert result.wall_section_ids == ()
    assert result.measurement_authorized is False


@pytest.mark.parametrize("bad_chord", (None, 4, "not-a-chord", [], True))
def test_malformed_segmented_chord_record_abstains_without_crashing(bad_chord):
    result = tag_native_segmented_doorway_chords((), (bad_chord,), scope=SCOPE)
    assert len(result) == 1
    assert result[0].status == "UNRESOLVED"
    assert result[0].reason == "source_chord_receipt_invalid"
    assert result[0].measurement_authorized is False


@pytest.mark.parametrize("bad_drawings,bad_chords", (
    (None, ()), ((), None), ("not-a-native-drawing-list", ()),
    ((), "not-a-chord-list"),
))
def test_malformed_segmented_source_collections_abstain(bad_drawings, bad_chords):
    result = tag_native_segmented_doorway_chords(bad_drawings, bad_chords, scope=SCOPE)
    assert len(result) == 1
    assert result[0].status == "UNRESOLVED"
    assert result[0].reason == "source_chord_collection_invalid"
    assert result[0].measurement_authorized is False
