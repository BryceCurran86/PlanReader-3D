"""Mitred wall paint closes a corner in topology only: default off, nothing invented.

Synthetic PDF-point geometry. A 100 x 80 ring of 2.5 pt walls whose top-right
corner is painted as a non-rectangular piece, which the strip collectors keep as
a barrier polygon rather than a wall strip.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass

import fitz
import pytest
from shapely.affinity import rotate
from shapely.geometry import Polygon, box

from pb_layered_wall_doorway_room_ring_shadow import _collect_strips
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_source_wall_joint_paint_continuity import detect_source_wall_joint_paint

LAYER = "Enclosure_WallExternal"
BLACK = (0.0, 0.0, 0.0)
OPEN = "source_exterior_perimeter_not_unique_and_closed"

# top (stops short of the corner), right (owns the corner square), bottom, left
WALLS = (
    (0.0, 0.0, 94.0, 2.5),
    (97.5, 0.0, 100.0, 80.0),
    (0.0, 77.5, 97.5, 80.0),
    (0.0, 2.5, 2.5, 77.5),
)
# Flush with the end of the top wall (x=94) and the face of the right wall (x=97.5).
JOINT = ((94.0, 0.0), (97.5, 0.0), (97.5, 1.2), (94.0, 2.5))


def _rect_row(bounds, *, layer=LAYER, fill=BLACK, opacity=1.0):
    rect = fitz.Rect(*bounds)
    return {
        "type": "f", "layer": layer, "fill": fill, "color": None,
        "fill_opacity": opacity, "rect": rect, "items": [("re", rect, 1)],
    }


def _outline_row(points, *, layer=LAYER, fill=BLACK, opacity=1.0):
    corners = [fitz.Point(*point) for point in points]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return {
        "type": "f", "layer": layer, "fill": fill, "color": None, "fill_opacity": opacity,
        "rect": fitz.Rect(min(xs), min(ys), max(xs), max(ys)),
        "items": [("l", a, b) for a, b in zip(corners, corners[1:] + corners[:1])],
    }


def _drawings(*pieces, walls=WALLS):
    return [_rect_row(bounds) for bounds in walls] + list(pieces)


def _attempt(drawings, *, admit=True, **kwargs):
    return attempt_source_native_outer_wall_first(
        drawings, admit_wall_joint_paint=admit, **kwargs
    )


def _same_outline(first, second):
    return Polygon(first).normalize().equals_exact(Polygon(second).normalize(), 1e-6)


def _assert_stays_open(drawings):
    attempt = _attempt(drawings)
    assert attempt.source_wall_joint_paint == ()
    assert (attempt.status, attempt.reason) == ("ABSTAINED", OPEN)


def test_joint_piece_is_a_barrier_polygon_not_a_wall_strip():
    strips, other = _collect_strips(_drawings(_outline_row(JOINT)))
    assert len(strips) == len(WALLS)
    assert [index for index, _polygon in other] == [4]


def test_mitred_corner_closes_only_when_switched_on():
    drawings = _drawings(_outline_row(JOINT))
    off = _attempt(drawings, admit=False)
    assert (off.status, off.reason) == ("ABSTAINED", OPEN)
    assert off.source_wall_joint_paint == ()
    on = _attempt(drawings)
    assert on.status == "CANDIDATE"
    assert len(on.polygon_pdf_pts) >= 4
    assert Polygon(on.polygon_pdf_pts).bounds == pytest.approx((0, 0, 100, 80), abs=0.05)
    (piece,) = on.source_wall_joint_paint
    assert (piece.source_path_id, piece.flush_side_count) == (4, 2)
    assert piece.bounds_pdf_pts == (94.0, 0.0, 97.5, 2.5)
    # Topology only: never a wall band, a path owner or an authority.
    assert on.source_wall_band_count == len(WALLS)
    assert on.source_wall_path_ids == (0, 1, 2, 3)
    assert piece.physical_wall_authenticated is False
    assert piece.measurement_authorized is False
    assert on.measurement_authorized is False
    assert on.physical_wall_authenticated is False
    assert on.internal_wall_filter_authorized is False
    assert piece.to_dict()["kind"] == "source_wall_joint_paint_topology_only"
    assert piece.to_dict()["measurement_authorized"] is False


def test_default_is_off_and_off_ignores_the_piece():
    with_piece = attempt_source_native_outer_wall_first(_drawings(_outline_row(JOINT)))
    without_piece = attempt_source_native_outer_wall_first(_drawings())
    assert with_piece.source_wall_joint_paint == ()
    for name in ("status", "reason", "polygon_pdf_pts", "source_wall_band_count",
                 "source_wall_path_ids", "diagnostic_closed_wall_loop_count"):
        assert getattr(with_piece, name) == getattr(without_piece, name)
    assert with_piece == _attempt(_drawings(_outline_row(JOINT)), admit=False)


@pytest.mark.parametrize("value", [1, 0, "yes", None])
def test_switch_must_be_an_explicit_bool(value):
    with pytest.raises(ValueError, match="admit_wall_joint_paint_must_be_bool"):
        attempt_source_native_outer_wall_first(_drawings(), admit_wall_joint_paint=value)


def test_a_real_unpainted_gap_stays_open():
    _assert_stays_open(_drawings())
    # The piece stops 0.4 pt short of the right wall: paint is not snapped.
    short = ((94.0, 0.0), (97.1, 0.0), (97.1, 1.2), (94.0, 2.5))
    _assert_stays_open(_drawings(_outline_row(short)))


@pytest.mark.parametrize("points", [
    # free piece in the middle of the room
    ((40.0, 40.0), (46.0, 40.0), (46.0, 42.0), (40.0, 45.0)),
    # flush with one wall face only
    ((40.0, 2.5), (46.0, 2.5), (46.0, 4.0), (40.0, 6.0)),
    # comb: two separate prongs on the same wall face are still one line
    ((20.0, 2.5), (22.0, 2.5), (22.0, 6.0), (26.0, 6.0), (26.0, 2.5), (28.0, 2.5),
     (28.0, 8.0), (20.0, 8.0)),
    # arrowhead stabbing into the wall: its sides cross the face, none lies on it
    ((40.0, 1.0), (42.0, 10.0), (38.0, 10.0)),
    # touches both corner walls at single points only
    ((94.0, 1.25), (95.75, 0.0), (97.5, 1.25), (95.75, 2.5)),
], ids=["free", "one_face", "comb", "arrow", "points_only"])
def test_look_alike_pieces_are_not_wall_joints(points):
    _assert_stays_open(_drawings(_outline_row(points)))


@pytest.mark.parametrize("row", [
    _outline_row(JOINT, fill=(1.0, 1.0, 1.0)),
    _outline_row(JOINT, fill=(0.2, 0.2, 0.2)),
    _outline_row(JOINT, opacity=0.5),
    _outline_row(JOINT, layer="Annotation"),
    _outline_row(JOINT, layer="Enclosure_Wall_Finishes"),
    _outline_row(JOINT, layer=""),
], ids=["white", "grey", "translucent", "annotation_layer", "finish_layer", "no_layer"])
def test_only_opaque_black_wall_layer_paint_qualifies(row):
    _assert_stays_open(_drawings(row))


def test_pieces_are_not_chained_through_each_other():
    left = ((94.0, 0.0), (96.0, 0.0), (96.0, 2.5), (95.0, 1.5), (94.0, 2.5))
    right = ((96.0, 0.0), (97.5, 0.0), (97.5, 2.5), (96.75, 1.5), (96.0, 2.5))
    drawings = _drawings(_outline_row(left), _outline_row(right))
    assert len(_collect_strips(drawings)[1]) == 2
    _assert_stays_open(drawings)


def test_pieces_do_not_join_across_declared_viewports():
    drawings = _drawings(_outline_row(JOINT))
    for row in drawings:
        row["viewport_id"] = "floor-plan"
    assert _attempt(drawings).status == "CANDIDATE"
    drawings[4]["viewport_id"] = "elevation"
    _assert_stays_open(drawings)


def test_overlapping_pieces_are_all_admitted_without_choosing():
    other = ((94.0, 0.0), (97.5, 0.0), (97.5, 1.4), (94.0, 2.5))
    assert len(_collect_strips(_drawings(_outline_row(JOINT), _outline_row(other)))[1]) == 2
    attempt = _attempt(_drawings(_outline_row(JOINT), _outline_row(other)))
    assert attempt.status == "CANDIDATE"
    assert [p.source_path_id for p in attempt.source_wall_joint_paint] == [4, 5]


@dataclass(frozen=True)
class _Bar:
    polygon: Polygon
    path_index: int

    def native_path_indices(self):
        return (self.path_index,)


def _bars(angle=0.0):
    return [_Bar(rotate(box(*bounds), angle, origin=(0, 0)), i) for i, bounds in enumerate(WALLS)]


@pytest.mark.filterwarnings("ignore:invalid value encountered")
def test_invalid_or_non_finite_outlines_are_ignored():
    rows = [_rect_row(bounds) for bounds in WALLS] + [_outline_row(JOINT)] * 3
    bowtie = Polygon([(94.0, 0.0), (97.5, 2.5), (97.5, 0.0), (94.0, 2.5)])
    broken = Polygon([(94.0, 0.0), (math.nan, 0.0), (97.5, 1.2), (94.0, 2.5)])
    assert detect_source_wall_joint_paint(
        [(4, bowtie), (5, broken), (6, Polygon()), (99, Polygon(JOINT))],
        source_drawings=rows, wall_bars=_bars(),
    ) == ()
    assert detect_source_wall_joint_paint(
        [(4, Polygon(JOINT))], source_drawings=rows, wall_bars=[],
    ) == ()


@pytest.mark.parametrize("angle", [0.0, 17.0, 33.0, 128.0])
def test_selection_does_not_depend_on_wall_direction(angle):
    rows = [_rect_row(bounds) for bounds in WALLS] + [_outline_row(JOINT)]
    piece = rotate(Polygon(JOINT), angle, origin=(0, 0))
    (selected,) = detect_source_wall_joint_paint(
        [(4, piece)], source_drawings=rows, wall_bars=_bars(angle),
    )
    assert selected.flush_side_count == 2


def _moved(move, *, walls=WALLS, pieces=(JOINT,)):
    drawings = []
    for x0, y0, x1, y1 in walls:
        (ax, ay), (bx, by) = move(x0, y0), move(x1, y1)
        drawings.append(_rect_row((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))))
    drawings += [_outline_row([move(x, y) for x, y in points]) for points in pieces]
    return drawings


@pytest.mark.parametrize("move", [
    lambda x, y: (x - 500.0, y + 300.0),
    lambda x, y: (-y, x),
    lambda x, y: (-x, -y),
    lambda x, y: (y, -x),
    lambda x, y: (-x, y),
    lambda x, y: (0.7 * x, 0.7 * y),
    lambda x, y: (3.0 * x, 3.0 * y),
], ids=["translate", "rot90", "rot180", "rot270", "mirror", "scale_down", "scale_up"])
def test_metamorphic_moves_keep_the_same_answer(move):
    off = _attempt(_moved(move), admit=False)
    on = _attempt(_moved(move))
    assert off.status == "ABSTAINED"
    assert on.status == "CANDIDATE"
    assert [p.flush_side_count for p in on.source_wall_joint_paint] == [2]


@pytest.mark.parametrize("seed", [1, 7, 23])
def test_input_order_does_not_change_the_answer(seed):
    drawings = _drawings(_outline_row(JOINT))
    expected = _attempt(drawings)
    shuffled = list(drawings)
    random.Random(seed).shuffle(shuffled)
    result = _attempt(shuffled)
    assert result.status == expected.status
    assert _same_outline(result.polygon_pdf_pts, expected.polygon_pdf_pts)
    assert [p.outline_pdf_pts for p in result.source_wall_joint_paint] == [
        p.outline_pdf_pts for p in expected.source_wall_joint_paint
    ]


def test_splitting_walls_or_piece_sides_changes_nothing():
    split_walls = (
        (0.0, 0.0, 50.0, 2.5), (50.0, 0.0, 94.0, 2.5),
        (97.5, 0.0, 100.0, 0.6), (97.5, 0.6, 100.0, 40.0), (97.5, 40.0, 100.0, 80.0),
        (0.0, 77.5, 97.5, 80.0), (0.0, 2.5, 2.5, 77.5),
    )
    split_piece = (
        (94.0, 0.0), (97.5, 0.0), (97.5, 0.4), (97.5, 0.8), (97.5, 1.2),
        (94.0, 2.5), (94.0, 1.9), (94.0, 1.5), (94.0, 1.0), (94.0, 0.4),
    )
    whole = _attempt(_drawings(_outline_row(JOINT)))
    split = _attempt(_drawings(_outline_row(split_piece), walls=split_walls))
    assert split.status == whole.status == "CANDIDATE"
    assert [p.flush_side_count for p in split.source_wall_joint_paint] == [2]
    assert Polygon(split.polygon_pdf_pts).symmetric_difference(
        Polygon(whole.polygon_pdf_pts)
    ).area < 0.5


def test_unrelated_ink_and_viewport_growth_change_nothing():
    drawings = _drawings(_outline_row(JOINT))
    expected = _attempt(drawings)
    unrelated = drawings + [
        _outline_row(((400.0, 400.0), (410.0, 400.0), (410.0, 403.0), (400.0, 408.0))),
        _rect_row((300.0, 300.0, 380.0, 302.5), layer="Annotation", fill=(0.6, 0.6, 0.6)),
    ]
    noisy = _attempt(unrelated)
    assert noisy.status == expected.status
    assert _same_outline(noisy.polygon_pdf_pts, expected.polygon_pdf_pts)
    assert noisy.source_wall_joint_paint == expected.source_wall_joint_paint
    for viewport in ((-5.0, -5.0, 105.0, 85.0), (-900.0, -900.0, 900.0, 900.0)):
        scoped = _attempt(drawings, viewport_pdf_pts=viewport)
        assert scoped.status == expected.status
        assert _same_outline(scoped.polygon_pdf_pts, expected.polygon_pdf_pts)
        assert scoped.source_wall_joint_paint == expected.source_wall_joint_paint


def test_a_viewport_that_excludes_the_corner_admits_no_piece():
    drawings = _drawings(_outline_row(JOINT))
    attempt = _attempt(drawings, viewport_pdf_pts=(-5.0, 20.0, 50.0, 85.0))
    assert attempt.source_wall_joint_paint == ()
    assert attempt.status == "ABSTAINED"


def test_replay_is_deterministic_and_inputs_are_not_modified():
    drawings = _drawings(_outline_row(JOINT))
    before = copy.deepcopy(drawings)
    first, second = _attempt(drawings), _attempt(drawings)
    assert first == second
    assert drawings == before


def test_overlapping_declared_viewports_do_not_bridge_or_veto_valid_joints():
    """Viewport-scoped wall union: an overlapping foreign-viewport bar neither lends a flush side nor vetoes a valid joint."""
    # Valid floor-plan ring + joint at index 4, plus an overlapping elevation right wall at index 5
    # (gives only 1 flush side in elevation: x=97.5, while x=94.0 belongs solely to floor-plan).
    drawings = _drawings(_outline_row(JOINT))
    for row in drawings:
        row["viewport_id"] = "floor-plan"
    foreign_bar = _rect_row((97.5, 0.0, 100.0, 80.0))
    foreign_bar["viewport_id"] = "elevation"
    # A joint declared in "elevation" gets only 1 flush side from elevation and 1 from floor-plan -> must NOT pass.
    foreign_joint = _outline_row(JOINT)
    foreign_joint["viewport_id"] = "elevation"
    rows = drawings + [foreign_bar, foreign_joint]
    bars = _bars() + [_Bar(box(97.5, 0.0, 100.0, 80.0), 5)]
    selected = detect_source_wall_joint_paint(
        [(4, Polygon(JOINT)), (6, Polygon(JOINT))],
        source_drawings=rows,
        wall_bars=bars,
    )
    # Index 4 (floor-plan) stays admitted despite overlapping elevation bar; index 6 (elevation, 1 elevation bar only) is rejected.
    assert [p.source_path_id for p in selected] == [4]


def test_unscoped_joint_cannot_bridge_two_different_declared_viewports():
    rows = _drawings(_outline_row(JOINT))
    rows[0]["viewport_id"] = "vp-a"
    rows[1]["viewport_id"] = "vp-b"
    rows[2]["viewport_id"] = "vp-a"
    rows[3]["viewport_id"] = "vp-a"
    # Joint row[4] has no declared viewport_id, touching vp-a (top wall) and vp-b (right wall).
    assert detect_source_wall_joint_paint(
        [(4, Polygon(JOINT))], source_drawings=rows, wall_bars=_bars(),
    ) == ()


def test_overlapping_spatial_viewports_preserve_native_path_indexing_and_deduplicate():
    """Overlapping viewport boxes keep original native path indices and emit each distinct joint once."""
    # Insert 3 leading non-matching rows far outside the viewports so native indices shift (+3).
    prefix = [
        _rect_row((800.0, 800.0, 820.0, 802.5), layer="Annotation"),
        _rect_row((830.0, 800.0, 850.0, 802.5), layer="Annotation"),
        _rect_row((860.0, 800.0, 880.0, 802.5), layer="Annotation"),
    ]
    # Second distinct mitred joint at the bottom-right corner (x=94..97.5, y=77.5..80).
    walls_two_gaps = (
        (0.0, 0.0, 94.0, 2.5),
        (97.5, 0.0, 100.0, 80.0),
        (0.0, 77.5, 94.0, 80.0),
        (0.0, 2.5, 2.5, 77.5),
    )
    joint_bottom = ((94.0, 77.5), (97.5, 78.8), (97.5, 80.0), (94.0, 80.0))
    drawings = prefix + _drawings(_outline_row(JOINT), _outline_row(joint_bottom), walls=walls_two_gaps)
    vp_top = (-5.0, -5.0, 105.0, 50.0)
    vp_bottom = (-5.0, 30.0, 105.0, 85.0)
    vp_overlap_corner = (80.0, -5.0, 105.0, 85.0)

    res_a = _attempt(drawings, viewport_pdf_pts=(vp_top, vp_bottom, vp_overlap_corner))
    res_b = _attempt(drawings, viewport_pdf_pts=(vp_overlap_corner, vp_bottom, vp_top))
    assert res_a.status == res_b.status == "CANDIDATE"
    # Native path indices must remain 7 and 8 (offset by the 3 clipped prefix rows) with no duplicates.
    assert [p.source_path_id for p in res_a.source_wall_joint_paint] == [7, 8]
    assert res_a.source_wall_joint_paint == res_b.source_wall_joint_paint
    assert res_a.source_wall_path_ids == (3, 4, 5, 6)


def test_source_path_indexing_rejects_bool_out_of_range_and_keeps_distinct_joints_per_path():
    rows = _drawings(_outline_row(JOINT))
    # Two distinct non-rectangular joint polygons on the SAME source path index (e.g. compound PDF path),
    # plus a duplicate of the first and malformed path indices (bool, negative, out-of-range).
    walls_two_gaps = (
        (0.0, 0.0, 94.0, 2.5),
        (97.5, 0.0, 100.0, 80.0),
        (0.0, 77.5, 94.0, 80.0),
        (0.0, 2.5, 2.5, 77.5),
    )
    joint_bottom = ((94.0, 77.5), (97.5, 78.8), (97.5, 80.0), (94.0, 80.0))
    bars = [_Bar(box(*b), i) for i, b in enumerate(walls_two_gaps)]
    selected = detect_source_wall_joint_paint(
        [
            (4, Polygon(JOINT)),
            (4, Polygon(JOINT)),  # exact duplicate -> deduplicated
            (4, Polygon(joint_bottom)),  # distinct joint on same path -> kept
            (True, Polygon(JOINT)),  # bool masquerading as int 1 -> rejected
            (-1, Polygon(JOINT)),
            (999, Polygon(JOINT)),
        ],
        source_drawings=rows,
        wall_bars=bars,
    )
    assert len(selected) == 2
    assert all(p.source_path_id == 4 for p in selected)
    assert selected[0].bounds_pdf_pts != selected[1].bounds_pdf_pts


def test_structurally_different_l_shaped_plan_with_internal_reentrant_joint():
    """Second structurally distinct plan topology: concave L-shaped wing with a mitred re-entrant corner."""
    l_walls = (
        (0.0, 0.0, 120.0, 2.5),      # north
        (117.5, 2.5, 120.0, 50.0),   # east upper wing
        (64.0, 47.5, 117.5, 50.0),   # re-entrant horizontal step (stops at x=64, gap to x=60)
        (57.5, 52.5, 60.0, 100.0),   # re-entrant vertical step (starts at y=52.5, gap from y=50)
        (0.0, 97.5, 57.5, 100.0),    # south lower wing
        (0.0, 2.5, 2.5, 97.5),       # west
    )
    # L-shaped mitred wedge bridging x=60..64 and y=47.5..52.5 (flush with step horizontal & step vertical).
    reentrant_joint = ((57.5, 47.5), (64.0, 47.5), (64.0, 50.0), (60.0, 52.5), (57.5, 52.5))
    drawings = _drawings(_outline_row(reentrant_joint), walls=l_walls)
    off = _attempt(drawings, admit=False)
    assert off.status == "ABSTAINED"
    on = _attempt(drawings, admit=True)
    assert on.status == "CANDIDATE"
    assert len(on.source_wall_joint_paint) == 1
    assert on.source_wall_joint_paint[0].source_path_id == len(l_walls)
    assert on.source_wall_joint_paint[0].flush_side_count >= 2
    assert on.source_wall_band_count == len(l_walls)
