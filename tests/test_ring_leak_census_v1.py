"""P4a: the read-only ring-leak census (pure module).

Synthetic only; no private source. ``pb_ring_leak_census`` reads what a ring builder produced and answers, from source ink geometry
only: what is inside every unclosed raw wall gap, how many rings closing a chosen set of gaps would add, and which raw gaps are one
aperture seen more than once. Nothing here is a wall, an opening, a closure, a room, a quantity or a score, and the census changes no
ring, closure, gate or builder. The ink classes and the aperture overlap rule are descriptive; the 10 and 140 pt buckets are the
builders' own face-identity band (pinned against ``_stroke_closed`` in the tool tests).
"""
from __future__ import annotations

import copy
import json
import math
import random
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

import pb_ring_leak_census as census
from pb_ring_leak_census import (
    BuilderCapture, BuilderRing, CensusInputError, InkIndex, PlainGap, aperture_groups, arc_in_gap, census_report,
    classify_unclosed_gap_ink, count_rings, gaps_overlap, item_bbox, length_bucket, ring_parts, witness_in_gap,
)

OPEN_GAP = census.REASON_OPEN_GAP


# ------------------------------------------------------------------------------------------------ helpers

def _line(a, b, *, fill=None):
    return {"layer": "", "fill": fill, "color": (0.0, 0.0, 0.0), "items": [("l", a, b)]}


def _gap(lo=150.0, hi=180.0, band=(294.0, 300.0), *, horizontal=False, collinear=True, left=(), right=()):
    return PlainGap(horizontal=horizontal, band=band, lo=lo, hi=hi, collinear=collinear, left_path_indices=tuple(left), right_path_indices=tuple(right))


def _classify(rows, gap=None, **kw):
    return classify_unclosed_gap_ink(rows, gap or _gap(), **kw)


def _klass(rows, gap=None, **kw):
    return _classify(rows, gap, **kw)["class"]


def _parts(geometry):
    if geometry.is_empty:
        return []
    return [geometry] if geometry.geom_type == "Polygon" else [g for g in geometry.geoms if g.geom_type == "Polygon"]


def _room_barrier(*, closure=None, extra_walls=()):
    """A 200 x 140 room of 6 pt walls whose right wall is cut by a doorway (y 150..180), plus an optional closing rectangle."""
    walls = [box(100, 100, 300, 106), box(100, 234, 300, 240), box(100, 100, 106, 240), box(294, 100, 300, 150), box(294, 180, 300, 240), *extra_walls]
    if closure is not None:
        walls.append(closure)
    return unary_union(walls)


def _toy_capture(*, closed=False, rule=census.PREVIEW_RING_RULE, rows=(), owner_evidence=None, ring_count_override=None, door_witnesses=(), native_arcs=(),
                 arc_info=None, builder_unresolved=None, extra_gaps=(), extra_closed=(), extra_walls=()):
    gap = _gap()
    closure = box(294, 150, 300, 180) if closed else None
    barrier = _room_barrier(closure=closure, extra_walls=extra_walls)
    domain = barrier.envelope.buffer(1.0, join_style=2)
    interior = box(106, 106, 294, 234)
    rings = [BuilderRing("candidate", ("layered_wall_ring_closed_by_source_ink",), interior)] if closed else []
    if ring_count_override is not None:
        rings = rings[:ring_count_override] if ring_count_override <= len(rings) else rings + [rings[0]] * (ring_count_override - len(rings))
    gaps = (gap, *extra_gaps)
    flags = (closed, *extra_closed)
    unresolved = sum(1 for g, c in zip(gaps, flags) if g.collinear and not c)
    return BuilderCapture(
        builder=census.BUILDER_PREVIEW_FORK, status="candidate" if closed else "abstained", reason_codes=("toy",), rows=list(rows), gaps=gaps, closed=flags,
        barrier=barrier, domain=domain, median_thickness=6.0, ring_rule=rule, noise_pt=0.05, closure_rect=lambda g: g.rect(),
        closed_union=lambda polys: unary_union(list(polys)), polygon_parts=_parts, ring_touch=lambda polygon, i: False,
        builder_strip_count=5, builder_gap_count=len(gaps), builder_closure_count=sum(flags),
        builder_unresolved_collinear=unresolved if builder_unresolved is None else builder_unresolved, builder_rings=tuple(rings),
        owner_evidence=owner_evidence, native_arcs=tuple(native_arcs), door_witnesses=tuple(door_witnesses), arc_info=arc_info,
    )


# ------------------------------------------------------------------------------------------------ buckets, gaps and items

@pytest.mark.parametrize("length,bucket", [
    (0.001, "lt10"), (9.999, "lt10"), (10.0, "10to140"), (75.0, "10to140"), (140.0, "10to140"), (140.001, "gt140"), (900.0, "gt140"),
])
def test_length_buckets_are_the_builders_opening_band(length, bucket):
    assert length_bucket(length) == bucket


@pytest.mark.parametrize("kwargs", [
    {"lo": 5.0, "hi": 5.0}, {"lo": 6.0, "hi": 5.0}, {"band": (300.0, 294.0)}, {"band": (294.0, 294.0)}, {"lo": math.nan}, {"hi": math.inf},
    {"band": (math.nan, 300.0)}, {"collinear": 1}, {"horizontal": None},
])
def test_a_malformed_gap_is_refused(kwargs):
    with pytest.raises(CensusInputError):
        _gap(**kwargs)


def test_a_gap_knows_its_length_thickness_and_rectangle():
    vertical, horizontal = _gap(), _gap(100.0, 130.0, (40.0, 46.0), horizontal=True)
    assert vertical.length == pytest.approx(30.0) and vertical.thickness == pytest.approx(6.0)
    assert vertical.rect().bounds == pytest.approx((294.0, 150.0, 300.0, 180.0))
    assert horizontal.rect().bounds == pytest.approx((100.0, 40.0, 130.0, 46.0))


def test_plain_gap_copies_a_builder_gap_look_alike():
    original = SimpleNamespace(horizontal=True, band=(1, 7), lo=2, hi=40, collinear=False, left_path_indices=[3], right_path_indices=[4, 5])
    copied = census.plain_gap(original)
    assert copied == PlainGap(True, (1.0, 7.0), 2.0, 40.0, False, (3,), (4, 5))


def test_item_bbox_mirrors_the_builders():
    point = lambda x, y: SimpleNamespace(x=x, y=y)  # noqa: E731
    assert item_bbox(("l", point(5, 9), point(2, 3))) == (2.0, 3.0, 5.0, 9.0)
    assert item_bbox(("l", (5, 9), (2, 3))) == (2.0, 3.0, 5.0, 9.0)
    assert item_bbox(("re", SimpleNamespace(x0=1, y0=2, x1=3, y1=4))) == (1.0, 2.0, 3.0, 4.0)
    assert item_bbox(("re", (1, 2, 3, 4))) == (1.0, 2.0, 3.0, 4.0)
    assert item_bbox(("c", (0, 0), (1, 5), (4, 5), (5, 0))) == (0.0, 0.0, 5.0, 5.0)
    axis_aligned = SimpleNamespace(ul=point(0, 0), ur=point(4, 0), lr=point(4, 2), ll=point(0, 2))
    rotated = SimpleNamespace(ul=point(0, 1), ur=point(2, 0), lr=point(3, 2), ll=point(1, 3))
    assert item_bbox(("qu", axis_aligned)) == (0.0, 0.0, 4.0, 2.0)
    assert item_bbox(("qu", rotated)) is None                  # the builders ignore a rotated quad
    assert item_bbox(("zz", (0, 0))) is None and item_bbox(()) is None


# ------------------------------------------------------------------------------------------------ ink classes

def test_an_empty_gap_is_empty():
    result = _classify([])
    assert result["class"] == "empty" and result["bucket"] == "10to140" and result["length_pt"] == pytest.approx(30.0)
    assert result["ink_rows"] == {"curve": 0, "parallel": 0, "perpendicular": 0, "fill": 0, "other": 0}
    assert result["best_parallel_end_miss_pt"] is None and result["owners"] == []


def test_strokes_across_the_band_are_perpendicular_strokes():
    rows = [_line((294.0, 160.0), (300.0, 160.0)), _line((294.0, 170.0), (300.0, 170.0))]
    result = _classify(rows)
    assert result["class"] == "perpendicular_strokes" and result["ink_rows"]["perpendicular"] == 2


def test_one_stroke_spanning_at_least_sixty_percent_is_one_partial_spanning_stroke():
    assert _klass([_line((294.0, 152.0), (294.0, 172.0))]) == "one_partial_spanning_stroke"        # 20 of 30 pt
    assert _klass([_line((294.0, 150.0), (294.0, 168.0))]) == "one_partial_spanning_stroke"        # exactly 60 percent
    assert _klass([_line((294.0, 150.0), (294.0, 167.9))]) == "other_ink_only"                     # just under 60 percent is not a spanning stroke


def test_two_spanning_strokes_in_two_rows_are_parallel_strokes_2plus_but_one_row_counts_once():
    a, b = _line((294.0, 151.0), (294.0, 171.0)), _line((294.0, 159.0), (294.0, 179.0))
    assert _klass([a, b]) == "parallel_strokes_2plus"
    both_in_one_row = {"layer": "", "fill": None, "color": None, "items": [a["items"][0], b["items"][0]]}
    assert _klass([both_in_one_row]) == "one_partial_spanning_stroke"                              # ink is counted per drawing row


def test_a_stroke_parallel_to_the_gap_counts_inside_the_inflated_rectangle_and_an_oblique_one_is_other_ink():
    assert _klass([_line((296.5, 152.0), (296.5, 175.0))]) == "one_partial_spanning_stroke"          # inside the wall band
    assert _klass([_line((288.5, 152.0), (288.5, 175.0))]) == "one_partial_spanning_stroke"          # within one wall thickness outside it
    assert _klass([_line((280.0, 152.0), (280.0, 175.0))]) == "empty"                                # beyond one thickness
    assert _klass([_line((294.0, 152.0), (300.0, 175.0))]) == "other_ink_only"                       # oblique across the band


def test_a_stroke_slightly_off_axis_beyond_the_tolerance_is_oblique():
    assert _klass([_line((294.0, 152.0), (294.05, 175.0))]) == "one_partial_spanning_stroke"       # within 0.12 pt of parallel
    assert _klass([_line((294.0, 152.0), (294.13, 175.0))]) == "other_ink_only"                    # beyond it


def test_curves_and_fills_are_other_ink():
    assert _klass([{"items": [("c", (296.0, 152.0), (296.0, 160.0), (298.0, 168.0), (299.0, 175.0))], "fill": None}]) == "other_ink_only"
    assert _klass([{"items": [("re", (294.0, 155.0, 300.0, 175.0))], "fill": (0.5, 0.5, 0.5)}]) == "other_ink_only"
    assert _classify([{"items": [("re", (294.0, 155.0, 300.0, 175.0))], "fill": (0.5, 0.5, 0.5)}])["ink_rows"]["fill"] == 1


def test_a_filled_row_counts_as_a_fill_even_if_it_carries_a_spanning_line():
    row = {"layer": "", "fill": (0.2, 0.2, 0.2), "color": None, "items": [("l", (294.0, 152.0), (294.0, 175.0))]}
    result = _classify([row])
    assert result["ink_rows"]["fill"] == 1 and result["ink_rows"]["parallel"] == 0 and result["class"] == "other_ink_only"


def test_rows_that_own_the_bounding_strips_are_not_ink_in_the_gap():
    rows = [_line((294.0, 152.0), (294.0, 175.0))]
    assert _klass(rows, _gap(left=(0,))) == "empty"
    assert _klass(rows, _gap(right=(0,))) == "empty"
    assert _klass(rows, _gap(left=(1,), right=(2,))) == "one_partial_spanning_stroke"           # other row indices do not hide it


def test_ink_outside_the_inflated_rectangle_or_inside_the_end_inset_is_ignored():
    assert _klass([_line((294.0, 160.0), (300.0, 160.0))]) == "perpendicular_strokes"
    assert _klass([_line((294.0, 150.2), (300.0, 150.2))]) == "empty"                              # inside the 0.5 pt end inset
    assert _klass([_line((294.0, 150.6), (300.0, 150.6))]) == "perpendicular_strokes"
    assert _klass([_line((250.0, 160.0), (256.0, 160.0))]) == "empty"                              # more than one wall thickness off the band
    assert _klass([_line((289.0, 160.0), (295.0, 160.0))]) == "perpendicular_strokes"             # within one wall thickness of the band


def test_class_order_is_owners_then_door_witness_then_native_arc_then_strokes():
    rows = [_line((294.0, 152.0), (294.0, 175.0))]
    assert _klass(rows, owners=("stroke_or_jamb", "swing"), door_witnesses=1, native_arcs=1) == "competing_owners"
    assert _klass(rows, owners=("swing",), door_witnesses=1, native_arcs=1) == "source_door_witness_in_gap"
    assert _klass(rows, door_witnesses=1, native_arcs=1) == "source_door_witness_in_gap"
    assert _klass(rows, native_arcs=1) == "native_arc_swing_not_placed"
    assert _klass(rows) == "one_partial_spanning_stroke"
    assert _classify(rows, owners=("swing",))["owners"] == ["swing"]


def test_the_best_parallel_stroke_end_miss_is_signed_positive_when_it_stops_short():
    result = _classify([_line((294.0, 152.0), (294.0, 172.0)), _line((294.0, 151.0), (294.0, 160.0))], _gap())
    assert result["best_parallel_end_miss_pt"] == [2.0, 8.0]
    beyond = _classify([_line((294.0, 148.0), (294.0, 182.0))])                                   # extends past both ends: negative misses
    assert beyond["class"] == "one_partial_spanning_stroke" and beyond["best_parallel_end_miss_pt"] == [-2.0, -2.0]


def test_a_horizontal_gap_classifies_like_the_vertical_one_after_swapping_axes():
    horizontal = _gap(150.0, 180.0, (294.0, 300.0), horizontal=True)
    swapped = {
        "partial": [_line((152.0, 294.0), (172.0, 294.0))], "perp": [_line((160.0, 294.0), (160.0, 300.0))],
        "two": [_line((151.0, 294.0), (171.0, 294.0)), _line((159.0, 294.0), (179.0, 294.0))],
    }
    assert _klass(swapped["partial"], horizontal) == "one_partial_spanning_stroke"
    assert _klass(swapped["perp"], horizontal) == "perpendicular_strokes"
    assert _klass(swapped["two"], horizontal) == "parallel_strokes_2plus"


@pytest.mark.parametrize("dx,dy,scale", [(0.0, 0.0, 1.0), (37.5, -21.25, 1.0), (-300.0, 410.0, 1.0), (0.0, 0.0, 2.0), (11.0, 5.0, 3.0)])
def test_classes_survive_translation_and_uniform_scale(dx, dy, scale):
    def moved(p):
        return (p[0] * scale + dx, p[1] * scale + dy)
    scenes = {
        "partial": [((294.0, 152.0), (294.0, 172.0))], "perp": [((294.0, 160.0), (300.0, 160.0))], "empty": [],
        "two": [((294.0, 151.0), (294.0, 171.0)), ((294.0, 159.0), (294.0, 179.0))],
    }
    expected = {"partial": "one_partial_spanning_stroke", "perp": "perpendicular_strokes", "empty": "empty", "two": "parallel_strokes_2plus"}
    gap = _gap(150.0 * scale + dy, 180.0 * scale + dy, (294.0 * scale + dx, 300.0 * scale + dx))
    for name, segments in scenes.items():
        rows = [_line(moved(a), moved(b)) for a, b in segments]
        assert _klass(rows, gap) == expected[name], name


def test_row_order_and_unrelated_leading_rows_do_not_change_the_class():
    ink = [_line((294.0, 151.0), (294.0, 171.0)), _line((294.0, 159.0), (294.0, 179.0)), _line((294.0, 160.0), (300.0, 160.0))]
    base = _classify(ink)
    random.Random(3).shuffle(ink)
    assert _classify(ink) == base
    far_away = [_line((900.0, 900.0), (900.0, 950.0)), _line((10.0, 10.0), (60.0, 10.0))]
    assert _classify(far_away + ink)["class"] == base["class"] and _classify(far_away + ink)["ink_rows"] == base["ink_rows"]


def test_classification_never_mutates_the_rows_and_replays_exactly():
    rows = [_line((294.0, 151.0), (294.0, 171.0)), {"items": [("c", (296, 152), (296, 160), (298, 168), (299, 175))], "fill": None}, None, {"items": ()}]
    before = copy.deepcopy(rows)
    first, second = _classify(rows), _classify(rows)
    assert rows == before and first == second and json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_an_index_built_once_gives_the_same_answer_as_raw_rows():
    rows = [_line((294.0, 151.0), (294.0, 171.0)), _line((294.0, 160.0), (300.0, 160.0))]
    assert classify_unclosed_gap_ink(InkIndex(rows), _gap()) == classify_unclosed_gap_ink(rows, _gap())


def test_the_classifier_takes_plain_gaps_only():
    with pytest.raises(CensusInputError):
        classify_unclosed_gap_ink([], SimpleNamespace(horizontal=False, band=(0, 1), lo=0, hi=20, collinear=True))


# ------------------------------------------------------------------------------------------------ door evidence in a gap

def test_a_native_arc_in_a_gap_is_one_whose_centre_and_tip_lie_on_the_gap_line_inside_its_interval():
    arc = {"centre": (297.0, 152.0), "closed_tip": (297.0, 178.0)}
    assert arc_in_gap(arc, _gap())
    assert not arc_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.2, 178.0)}, _gap())          # not on one line (0.05 pt)
    assert not arc_in_gap({"centre": (297.0, 140.0), "closed_tip": (297.0, 178.0)}, _gap())          # starts before the gap
    assert not arc_in_gap({"centre": (250.0, 152.0), "closed_tip": (250.0, 178.0)}, _gap())          # beside the wall, off its band
    assert arc_in_gap({"centre": (297.0, 150.0), "closed_tip": (297.0, 180.04)}, _gap())             # 0.05 pt of slack at the ends


def test_a_segmented_witness_needs_a_real_along_extent_and_the_wider_axis_tolerance():
    ok = {"centre": (297.0, 152.0), "closed_tip": (297.1, 178.0)}
    assert witness_in_gap(ok, _gap())
    assert not witness_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.3, 178.0)}, _gap())        # beyond 0.12 pt
    assert not witness_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.0, 152.8)}, _gap())        # under 1 pt along
    assert not witness_in_gap({"centre": (297.0, 140.0), "closed_tip": (297.0, 170.0)}, _gap())


# ------------------------------------------------------------------------------------------------ apertures

def test_overlapping_gaps_on_one_line_are_one_aperture_and_touching_or_disjoint_ones_are_not():
    a = _gap(150.0, 180.0, (294.0, 300.0))
    twin = _gap(152.0, 178.0, (296.0, 299.0))                               # a thinner band over the same interval
    touching_interval = _gap(180.0, 210.0, (294.0, 300.0))                  # shares only an end point
    touching_band = _gap(150.0, 180.0, (300.0, 306.0))                      # adjacent band, no overlap
    other_axis = _gap(150.0, 180.0, (294.0, 300.0), horizontal=True)
    assert gaps_overlap(a, twin) and gaps_overlap(twin, a)
    assert not gaps_overlap(a, touching_interval) and not gaps_overlap(a, touching_band) and not gaps_overlap(a, other_axis)
    assert aperture_groups([a, twin, touching_interval, touching_band, other_axis]) == ((0, 1), (2,), (3,), (4,))


def test_aperture_groups_are_transitive_ordered_and_independent_of_the_input_order():
    a, b, c = _gap(0.0, 40.0), _gap(30.0, 80.0), _gap(70.0, 120.0)         # a-b and b-c overlap, a-c do not
    assert aperture_groups([a, b, c]) == ((0, 1, 2),)
    gaps = [a, b, c, _gap(300.0, 340.0), _gap(500.0, 540.0, (10.0, 16.0))]
    expected = {frozenset({(g.lo, g.hi, g.band) for g in group}) for group in ([a, b, c], [gaps[3]], [gaps[4]])}
    for seed in range(6):
        shuffled = gaps[:]
        random.Random(seed).shuffle(shuffled)
        groups = aperture_groups(shuffled)
        assert {frozenset({(shuffled[i].lo, shuffled[i].hi, shuffled[i].band) for i in group}) for group in groups} == expected
        assert all(list(g) == sorted(g) for g in groups) and [g[0] for g in groups] == sorted(g[0] for g in groups)


def test_no_gaps_give_no_groups_and_one_gap_one_group():
    assert aperture_groups([]) == () and aperture_groups([_gap()]) == ((0,),)


# ------------------------------------------------------------------------------------------------ ring recomputation

def test_rings_are_recomputed_from_the_barrier_and_a_closing_rectangle_encloses_the_room():
    open_room, closed_room = _toy_capture(), _toy_capture(closed=True)
    assert count_rings(open_room) == 0 and count_rings(closed_room) == 1
    assert count_rings(open_room, [box(294, 150, 300, 180)]) == 1


def test_a_closing_rectangle_that_covers_a_small_ring_removes_it():
    pocket_wall = [box(150, 150, 170, 154), box(150, 166, 170, 170), box(150, 150, 154, 170), box(166, 150, 170, 170)]      # a 12 x 12 cell
    capture = _toy_capture(closed=True)
    capture = BuilderCapture(**{**capture.__dict__, "barrier": unary_union([capture.barrier, *pocket_wall])})
    assert count_rings(capture) == 2
    assert count_rings(capture, [box(150, 150, 170, 170)]) == 1


def test_the_two_ring_rules_differ_on_a_medium_pocket_exactly_as_the_builders_do():
    cell = [box(150, 150, 150 + 9 + 12, 156), box(150, 150 + 9 + 6, 150 + 9 + 12, 150 + 9 + 12), box(150, 150, 156, 150 + 9 + 12), box(150 + 9 + 6, 150, 150 + 9 + 12, 150 + 9 + 12)]
    base = _toy_capture(closed=True)
    barrier = unary_union([base.barrier, *cell])                                   # a 9 x 9 enclosed cell inside the room
    preview = BuilderCapture(**{**base.__dict__, "barrier": barrier, "ring_rule": census.PREVIEW_RING_RULE})
    layered = BuilderCapture(**{**base.__dict__, "barrier": barrier, "ring_rule": census.LAYERED_RING_RULE})
    assert count_rings(preview) == 2 and count_rings(layered) == 1                 # half a thickness inset keeps it, a full one does not
    extent_only = census.RingRule(sliver_inset_factor=0.4, min_extent_factor=6.0)  # a cavity test on its own drops it too
    assert count_rings(BuilderCapture(**{**base.__dict__, "barrier": barrier, "ring_rule": extent_only})) == 1


def test_a_free_part_touching_the_domain_boundary_is_the_exterior_not_a_ring():
    base = _toy_capture()
    assert count_rings(base) == 0
    wide_domain = BuilderCapture(**{**base.__dict__, "domain": base.domain.buffer(40.0)})
    assert count_rings(wide_domain) == 0                                            # the exterior still reaches the edge through the doorway
    sealed = _toy_capture(closed=True)
    assert count_rings(BuilderCapture(**{**sealed.__dict__, "domain": sealed.domain.buffer(40.0)})) == 1


# ------------------------------------------------------------------------------------------------ the report

def test_the_report_of_a_leaking_room_counts_the_gap_the_class_and_the_ring_it_would_add():
    report = census_report(_toy_capture())
    assert report["schema_version"] == census.SCHEMA_VERSION and report["builder"] == "preview_fork"
    assert report["counts"]["raw_gaps"] == 1 and report["counts"]["raw_gaps_collinear"] == 1 and report["counts"]["closed"] == 0 and report["counts"]["rings"] == 0
    assert report["replication"]["exact"] is True
    assert report["unclosed_gaps"]["count"] == 1 and report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|empty": 1}
    assert report["unclosed_gaps"]["unresolved_collinear_by_bucket"] == {"10to140": 1}
    unblock = report["unblocking_power"]
    assert unblock["rings_now"] == 0 and unblock["rings_recomputed"] == 0
    assert unblock["if_all_unresolved_collinear_closed"] == 1 and unblock["if_all_opening_sized_unresolved_closed"] == 1
    assert unblock["if_every_unclosed_raw_gap_closed_UPPER_BOUND_NOT_A_RULE"] == 1 and unblock["if_all_unclosed_of_one_class_closed"] == {"empty": 1}
    assert unblock["single_closure"] == {"gaps_adding_a_ring": 1, "adding_by_orientation_and_class": {"collinear|empty": 1}, "adding_by_bucket": {"10to140": 1},
                                         "adding_with_door_evidence": 0, "gaps_removing_a_ring": 0,
                                         "adding_by_effect": {"encloses_new_space": 1}, "adding_by_orientation_and_effect": {"collinear|encloses_new_space": 1}}
    assert report["apertures"]["raw_gaps"] == 1 and report["apertures"]["ring_adding_gaps"] == 1 and report["apertures"]["ring_adding_distinct_groups"] == 1
    assert report["unblocking_power_withheld"] is None


def test_the_report_of_a_closed_room_has_no_unclosed_gap_and_one_ring():
    report = census_report(_toy_capture(closed=True))
    assert report["counts"]["closed"] == 1 and report["counts"]["rings"] == 1 and report["counts"]["rings_by_status_and_reason"] == {
        "candidate|layered_wall_ring_closed_by_source_ink": 1}
    assert report["unclosed_gaps"]["count"] == 0 and report["unclosed_gaps"]["held_open_rings"] == []
    assert report["unblocking_power"]["single_closure"]["gaps_adding_a_ring"] == 0 and report["replication"]["exact"] is True
    assert report["apertures"]["groups_with_a_closed_gap"] == 1 and report["apertures"]["unclosed_gaps_sharing_a_group_with_a_closed_gap"] == 0


def test_each_replication_check_fails_on_its_own_and_withholds_the_ring_figures():
    wrong_unresolved = census_report(_toy_capture(builder_unresolved=3))
    assert wrong_unresolved["replication"]["unresolved_collinear"] == {"census": 1, "builder": 3, "match": False} and wrong_unresolved["replication"]["exact"] is False
    assert wrong_unresolved["replication"]["closed"]["match"] is True and wrong_unresolved["replication"]["rings"]["match"] is True
    assert wrong_unresolved["unblocking_power"] is not None                       # the ring model still holds, so its figures stand
    wrong_rings = census_report(_toy_capture(closed=True, ring_count_override=2))
    assert wrong_rings["replication"]["rings"] == {"recomputed": 1, "builder": 2, "match": False} and wrong_rings["replication"]["exact"] is False
    assert wrong_rings["unblocking_power"] is None and wrong_rings["unblocking_power_withheld"] == "ring_count_replication_not_exact"
    assert wrong_rings["apertures"]["ring_adding_gaps"] is None and wrong_rings["apertures"]["ring_adding_distinct_groups"] is None
    wrong_closed = census_report(BuilderCapture(**{**_toy_capture(closed=True).__dict__, "builder_closure_count": 4}))
    assert wrong_closed["replication"]["closed"] == {"census": 1, "builder": 4, "match": False} and wrong_closed["replication"]["exact"] is False


def test_unblocking_can_be_switched_off_and_then_is_not_called_withheld():
    report = census_report(_toy_capture(), unblocking=False)
    assert report["unblocking_power"] is None and report["unblocking_power_withheld"] is None
    assert report["unclosed_gaps"]["count"] == 1 and report["replication"]["exact"] is True


def test_native_arc_and_door_witness_evidence_in_a_gap_sets_the_class_and_the_door_evidence_count():
    arc = {"centre": (297.0, 152.0), "closed_tip": (297.0, 178.0)}
    witness = {"centre": (297.0, 152.0), "closed_tip": (297.0, 178.0)}
    with_arc = census_report(_toy_capture(native_arcs=[arc]))
    assert with_arc["unclosed_gaps"]["by_class"] == {"native_arc_swing_not_placed": 1}
    assert with_arc["unblocking_power"]["single_closure"]["adding_with_door_evidence"] == 1
    with_witness = census_report(_toy_capture(door_witnesses=[witness]))
    assert with_witness["unclosed_gaps"]["by_class"] == {"source_door_witness_in_gap": 1}
    competing = census_report(_toy_capture(native_arcs=[arc], owner_evidence=lambda i: ("swing", "stroke_or_jamb")))
    assert competing["unclosed_gaps"]["by_class"] == {"competing_owners": 1} and competing["unclosed_gaps"]["owner_sets"] == {"swing+stroke_or_jamb": 1}


def test_a_ring_held_open_by_one_gap_is_reported_with_the_class_of_the_gap():
    base = _toy_capture(closed=True)
    interior = base.builder_rings[0].polygon
    held = BuilderRing("abstained", (OPEN_GAP,), interior)
    capture = BuilderCapture(**{**base.__dict__, "closed": (False,), "builder_closure_count": 0, "builder_unresolved_collinear": 1,
                               "builder_rings": (held,), "ring_touch": lambda polygon, i: True, "rows": [_line((294.0, 152.0), (294.0, 172.0))]})
    report = census_report(capture)
    assert report["counts"]["rings_by_status_and_reason"] == {f"abstained|{OPEN_GAP}": 1}
    assert report["unclosed_gaps"]["held_open_rings"] == [{"leaking_gaps": 1, "classes": ["one_partial_spanning_stroke"]}]
    assert report["unclosed_gaps"]["touching_no_ring"] == 0 and report["unclosed_gaps"]["touching_an_abstained_ring"] == 1


def test_gaps_that_close_nothing_new_are_counted_as_touching_no_ring():
    report = census_report(_toy_capture())
    assert report["unclosed_gaps"]["touching_no_ring"] == 1 and report["unclosed_gaps"]["touching_an_abstained_ring"] == 0


def test_a_second_gap_in_the_same_aperture_groups_with_the_first_and_counts_as_a_twin_of_a_closed_gap():
    twin = _gap(152.0, 178.0, (296.0, 299.0))
    report = census_report(_toy_capture(closed=True, extra_gaps=(twin,), extra_closed=(False,)))
    apertures = report["apertures"]
    assert apertures["raw_gaps"] == 2 and apertures["groups"] == 1 and apertures["groups_with_two_or_more_gaps"] == 1 and apertures["gaps_in_such_groups"] == 2
    assert apertures["largest_group"] == 2 and apertures["groups_with_a_closed_gap"] == 1
    assert apertures["unclosed_gaps_sharing_a_group_with_a_closed_gap"] == 1 and apertures["unresolved_collinear_sharing_a_group_with_a_closed_gap"] == 1


def test_a_non_collinear_gap_is_counted_apart_and_never_in_the_unresolved_collinear_figures():
    stub = _gap(120.0, 150.0, (200.0, 206.0), horizontal=False, collinear=False)
    report = census_report(_toy_capture(closed=True, extra_gaps=(stub,), extra_closed=(False,)))
    assert report["counts"]["raw_gaps_non_collinear"] == 1 and report["unclosed_gaps"]["non_collinear"] == 1 and report["unclosed_gaps"]["collinear"] == 0
    assert report["unclosed_gaps"]["unresolved_collinear_by_class"] == {} and report["replication"]["unresolved_collinear"]["census"] == 0
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"non_collinear|empty": 1}


def test_the_partial_stroke_end_misses_are_listed_without_coordinates():
    rows = [_line((294.0, 152.0), (294.0, 172.0))]
    report = census_report(_toy_capture(rows=rows))
    assert report["unclosed_gaps"]["by_class"] == {"one_partial_spanning_stroke": 1}
    assert report["partial_stroke_end_misses_pt"] == [{"miss_lo": 2.0, "miss_hi": 8.0, "gap_length": 30.0}]


def test_per_gap_records_carry_indices_lengths_and_counts_only():
    report = census_report(_toy_capture(rows=[_line((294.0, 160.0), (300.0, 160.0))]), per_gap=True)
    (record,) = report["gap_records"]
    assert set(record) == {"index", "orientation", "collinear", "class", "bucket", "length_pt", "thickness_pt", "owners", "door_witnesses", "native_arcs",
                           "ink_rows", "rings_touched", "single_closure_ring_gain", "single_closure_effect", "aperture_group_size"}
    assert record["index"] == 0 and record["orientation"] == "vertical" and record["class"] == "perpendicular_strokes" and record["single_closure_ring_gain"] == 1 and record["single_closure_effect"] == "encloses_new_space"
    assert "gap_records" not in census_report(_toy_capture())


def test_the_report_is_plain_json_deterministic_and_carries_no_coordinates():
    capture = _toy_capture(rows=[_line((294.0, 152.0), (294.0, 172.0)), _line((294.0, 160.0), (300.0, 160.0))])
    first, second = census_report(capture, per_gap=True), census_report(capture, per_gap=True)
    assert first == second
    text = json.dumps(first, sort_keys=True)
    assert text == json.dumps(json.loads(text), sort_keys=True)
    for key_part in ("bbox", "polygon", "coord", "pdf_pts", "words", "name"):
        assert key_part not in text.lower(), key_part
    for coordinate in ("294.0", "300.0", "150.0", "180.0", "106.0", "240.0"):         # the scene's own coordinates never appear
        assert f": {coordinate}" not in text and f"[{coordinate}" not in text and f", {coordinate}" not in text, coordinate


def test_the_census_never_mutates_the_capture_inputs():
    rows = [_line((294.0, 152.0), (294.0, 172.0))]
    capture = _toy_capture(rows=rows)
    before_rows, before_wkt = copy.deepcopy(rows), (capture.barrier.wkt, capture.domain.wkt)
    census_report(capture, per_gap=True)
    assert rows == before_rows and (capture.barrier.wkt, capture.domain.wkt) == before_wkt


def test_a_capture_must_have_one_closed_flag_per_gap_and_plain_gaps():
    base = _toy_capture()
    with pytest.raises(CensusInputError):
        BuilderCapture(**{**base.__dict__, "closed": (True, False)})
    with pytest.raises(CensusInputError):
        BuilderCapture(**{**base.__dict__, "gaps": (SimpleNamespace(),)})


def test_the_arc_section_reports_candidates_and_whether_competing_gaps_are_one_aperture():
    twin_a, twin_b = _gap(150.0, 180.0, (294.0, 300.0)), _gap(152.0, 178.0, (296.0, 299.0))
    different = _gap(300.0, 330.0, (294.0, 300.0))
    info = census.ArcInfo(found=4, rejected_by_finder=7, builder_unplaced=1, builder_ambiguous=2, candidate_gap_indices=((), (0,), (0, 1), (0, 2)))
    capture = _toy_capture(extra_gaps=(twin_b, different), extra_closed=(False, False), arc_info=info)
    arcs = census_report(capture)["native_arcs"]
    assert arcs["found"] == 4 and arcs["rejected_by_finder"] == 7 and arcs["builder_unplaced"] == 1 and arcs["builder_ambiguous"] == 2
    assert arcs["per_arc_candidate_gaps"] == {"no_candidate_gap": 1, "one_candidate_gap": 1, "several_candidate_gaps": 2}
    assert arcs["several_candidate_shape"] == {"all_pairs_overlap_one_aperture": 1, "different_apertures": 1}
    assert arcs["several_candidate_kinds"] == {"collinear+collinear": 2}
    assert census_report(_toy_capture())["native_arcs"] is None


# ------------------------------------------------------------------------------------------------ boundaries and pins

def test_the_schema_version_is_pinned():
    assert census.SCHEMA_VERSION == "1.0.0"


def test_a_quad_with_float_noise_is_still_an_axis_aligned_rectangle():
    point = lambda x, y: SimpleNamespace(x=x, y=y)  # noqa: E731
    noisy = SimpleNamespace(ul=point(0.0, 0.0), ur=point(4.0000000001, 0.0000000001), lr=point(4.0, 2.0), ll=point(0.0000000001, 2.0000000001))
    assert item_bbox(("qu", noisy)) == (0.0, 0.0, 4.0, 2.0)


def test_items_without_a_bounding_box_are_ignored_not_fatal():
    point = lambda x, y: SimpleNamespace(x=x, y=y)  # noqa: E731
    rotated = SimpleNamespace(ul=point(0, 1), ur=point(2, 0), lr=point(3, 2), ll=point(1, 3))
    rows = [{"items": [("qu", rotated)], "fill": None}, {"items": [("zz", (0, 0))], "fill": None}, {"items": None, "fill": None}, None]
    assert _klass(rows) == "empty"


@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("offset,inside", [(-5.5, True), (-6.5, False), (11.5, True), (12.5, False)])
def test_ink_within_one_wall_thickness_beyond_either_side_of_the_band_counts_in_both_orientations(horizontal, offset, inside):
    gap = _gap(150.0, 180.0, (294.0, 300.0), horizontal=horizontal)          # band 294..300: ink counts from 288 to 306
    across = 294.0 + offset
    stroke = _line((152.0, across), (175.0, across)) if horizontal else _line((across, 152.0), (across, 175.0))
    assert _klass([stroke], gap) == ("one_partial_spanning_stroke" if inside else "empty")


def test_the_axis_tolerance_boundaries_are_inclusive(monkeypatch):
    monkeypatch.setattr(census, "AXIS_TOLERANCE_PT", 0.125)                  # exactly representable, so the boundary is exact
    assert _klass([_line((294.0, 152.0), (294.125, 175.0))]) == "one_partial_spanning_stroke"
    assert _klass([_line((294.0, 152.0), (294.126, 175.0))]) == "other_ink_only"
    assert _klass([_line((294.0, 160.0), (300.0, 160.125))]) == "perpendicular_strokes"
    assert _klass([_line((294.0, 160.0), (300.0, 160.126))]) == "other_ink_only"


def test_a_perpendicular_stroke_must_span_half_the_wall_thickness():
    assert _klass([_line((294.0, 160.0), (297.0, 160.0))]) == "perpendicular_strokes"       # exactly half of 6 pt
    assert _klass([_line((294.0, 160.0), (296.9, 160.0))]) == "other_ink_only"


def test_unfilled_rectangles_are_other_ink_and_filled_ones_are_fills():
    outline = {"items": [("re", (294.0, 155.0, 300.0, 175.0))], "fill": None}
    solid = {"items": [("re", (294.0, 155.0, 300.0, 175.0))], "fill": (0.5, 0.5, 0.5)}
    assert _classify([outline])["ink_rows"] == {"curve": 0, "parallel": 0, "perpendicular": 0, "fill": 0, "other": 1}
    assert _classify([solid])["ink_rows"] == {"curve": 0, "parallel": 0, "perpendicular": 0, "fill": 1, "other": 0}


def test_a_curve_is_counted_as_a_curve_row():
    curve = {"items": [("c", (296.0, 152.0), (296.0, 160.0), (298.0, 168.0), (299.0, 175.0))], "fill": None}
    assert _classify([curve])["ink_rows"] == {"curve": 1, "parallel": 0, "perpendicular": 0, "fill": 0, "other": 0}


def test_spans_of_rows_that_do_not_count_as_parallel_never_set_the_best_end_miss():
    solid_with_a_long_line = {"layer": "", "fill": (0.2, 0.2, 0.2), "color": None, "items": [("l", (294.0, 150.0), (294.0, 180.0))]}
    result = _classify([solid_with_a_long_line, _line((294.0, 152.0), (294.0, 172.0))])
    assert result["ink_rows"]["fill"] == 1 and result["ink_rows"]["parallel"] == 1 and result["best_parallel_end_miss_pt"] == [2.0, 8.0]


def test_the_best_parallel_stroke_is_the_longest_and_ties_go_to_the_lower_start():
    longer, shorter = _line((294.0, 151.0), (294.0, 171.0)), _line((294.0, 150.0), (294.0, 169.0))
    assert _classify([longer, shorter])["best_parallel_end_miss_pt"] == [1.0, 9.0]
    assert _classify([shorter, longer])["best_parallel_end_miss_pt"] == [1.0, 9.0]
    low, high = _line((294.0, 150.0), (294.0, 170.0)), _line((294.0, 152.0), (294.0, 172.0))
    assert _classify([high, low])["best_parallel_end_miss_pt"] == [0.0, 10.0]


def test_the_classification_reports_the_door_evidence_counts_it_was_given():
    result = _classify([], door_witnesses=2, native_arcs=3)
    assert result["door_witnesses"] == 2 and result["native_arcs"] == 3
    assert _classify([])["door_witnesses"] == 0 and _classify([])["native_arcs"] == 0


def test_door_evidence_takes_the_line_from_the_centre_for_arcs_and_from_the_mean_for_witnesses():
    gap = _gap()                                                             # band 294..300, so the allowed line is 288..306
    assert not arc_in_gap({"centre": (306.015625, 152.0), "closed_tip": (305.984375, 178.0)}, gap)     # centre beyond; the mean is exactly 306
    assert arc_in_gap({"centre": (305.984375, 152.0), "closed_tip": (306.015625, 178.0)}, gap)
    assert witness_in_gap({"centre": (306.0546875, 152.0), "closed_tip": (305.9453125, 178.0)}, gap)   # the mean is exactly 306
    assert not witness_in_gap({"centre": (306.0546875, 152.0), "closed_tip": (306.0, 178.0)}, gap)      # the mean is beyond


def test_door_evidence_segments_are_ordered_before_the_interval_test():
    gap = _gap()
    assert arc_in_gap({"centre": (297.0, 178.0), "closed_tip": (297.0, 152.0)}, gap)
    assert not arc_in_gap({"centre": (297.0, 178.0), "closed_tip": (297.0, 140.0)}, gap)
    assert not arc_in_gap({"centre": (297.0, 140.0), "closed_tip": (297.0, 178.0)}, gap)
    assert not arc_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.0, 195.0)}, gap)
    assert not arc_in_gap({"centre": (297.0, 195.0), "closed_tip": (297.0, 152.0)}, gap)


@pytest.mark.parametrize("line,inside", [(288.0, True), (289.0, True), (305.0, True), (306.0, True), (287.9, False), (306.1, False)])
def test_door_evidence_may_lie_within_one_wall_thickness_of_the_band(line, inside):
    segment = {"centre": (line, 152.0), "closed_tip": (line, 178.0)}
    assert arc_in_gap(segment, _gap()) is inside and witness_in_gap(segment, _gap()) is inside


def test_a_what_if_unions_the_builders_own_polygons_with_the_extra_rectangles():
    seen = []

    def recording_union(polygons):
        polygons = list(polygons)
        seen.append(polygons)
        return unary_union(polygons)

    base = _toy_capture()
    pieces = [box(100, 100, 300, 106), box(100, 234, 300, 240), box(100, 100, 106, 240), box(294, 100, 300, 150), box(294, 180, 300, 240)]
    extra = box(294, 150, 300, 180)
    with_inputs = BuilderCapture(**{**base.__dict__, "closed_union": recording_union, "barrier_inputs": tuple(pieces)})
    assert count_rings(with_inputs, [extra]) == 1 and seen == [[*pieces, extra]]
    seen.clear()
    without_inputs = BuilderCapture(**{**base.__dict__, "closed_union": recording_union})
    assert count_rings(without_inputs, [extra]) == 1 and seen == [[without_inputs.barrier, extra]]
    seen.clear()
    count_rings(with_inputs)
    assert seen == []                                                        # no extra rectangles: the builder's own barrier, no union


# ------------------------------------------------------------------------------------------------ slivers and the witness boundary

def _enclosed_pocket(barrier, x0, y0, x1, y1, wall=2.0):
    """A closed pocket whose free interior is exactly (x0, y0)-(x1, y1), inside the toy room."""
    frame = [box(x0 - wall, y0 - wall, x1 + wall, y0), box(x0 - wall, y1, x1 + wall, y1 + wall), box(x0 - wall, y0, x0, y1), box(x1, y0, x1 + wall, y1)]
    return unary_union([barrier, *frame])


@pytest.mark.parametrize("rule,width,kept", [
    (census.PREVIEW_RING_RULE, 5.0, False),      # a 5 pt corridor is narrower than the median 6 pt strip: half of it is inset to nothing
    (census.PREVIEW_RING_RULE, 7.0, True),
    (census.LAYERED_RING_RULE, 11.0, False),     # a full thickness inset on each side removes anything under 12 pt wide
    (census.LAYERED_RING_RULE, 13.0, True),
])
def test_a_free_part_narrower_than_the_rules_inset_is_a_sliver_and_not_a_ring(rule, width, kept):
    base = _toy_capture(closed=True, rule=rule)
    barrier = _enclosed_pocket(base.barrier, 150.0, 150.0, 150.0 + width, 210.0)          # a long thin pocket 60 pt tall
    capture = BuilderCapture(**{**base.__dict__, "barrier": barrier})
    assert count_rings(capture) == (2 if kept else 1)


def test_a_segmented_witness_needs_more_than_one_point_along_the_door_line():
    assert not witness_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.0, 153.0)}, _gap())           # exactly 1 pt
    assert witness_in_gap({"centre": (297.0, 152.0), "closed_tip": (297.0, 153.001)}, _gap())


def test_a_pocket_narrow_on_one_axis_only_is_not_a_cavity():
    base = _toy_capture(closed=True, rule=census.LAYERED_RING_RULE)
    barrier = _enclosed_pocket(base.barrier, 150.0, 150.0, 170.0, 210.0)                   # 20 x 60: one extent under 36, the other over
    capture = BuilderCapture(**{**base.__dict__, "barrier": barrier})
    assert count_rings(capture) == 2


def test_a_ring_is_held_open_only_when_it_is_abstained_for_the_open_gap_reason():
    base = _toy_capture(closed=True)
    interior = base.builder_rings[0].polygon

    def held(status, reasons):
        ring = BuilderRing(status, reasons, interior)
        capture = BuilderCapture(**{**base.__dict__, "closed": (False,), "builder_closure_count": 0, "builder_unresolved_collinear": 1,
                                   "builder_rings": (ring,), "ring_touch": lambda polygon, i: True})
        return census_report(capture)["unclosed_gaps"]["held_open_rings"]

    assert held("abstained", (OPEN_GAP,)) == [{"leaking_gaps": 1, "classes": ["empty"]}]
    assert held("abstained", ("unowned_ring_edge",)) == []                                 # abstained for another reason: not held open by a gap
    assert held("candidate", (OPEN_GAP,)) == []                                            # a candidate ring never is


def test_collinear_and_non_collinear_unclosed_gaps_are_counted_and_bucketed_apart():
    stub = _gap(120.0, 124.0, (200.0, 206.0), collinear=False)                             # 4 pt, an open end meeting a wall
    report = census_report(_toy_capture(extra_gaps=(stub,), extra_closed=(False,)))
    unclosed = report["unclosed_gaps"]
    assert unclosed["count"] == 2 and unclosed["collinear"] == 1 and unclosed["non_collinear"] == 1
    assert unclosed["unresolved_collinear_by_bucket"] == {"10to140": 1} and unclosed["unresolved_collinear_by_class"] == {"empty": 1}
    assert unclosed["by_class_and_bucket"] == {"empty|10to140": 1, "empty|lt10": 1}


def test_aperture_figures_separate_singletons_from_multi_gap_groups_and_ring_adding_gaps_from_both():
    twin_a, twin_b = _gap(300.0, 330.0, (294.0, 300.0)), _gap(305.0, 325.0, (295.0, 299.0))     # one aperture seen twice, outside the room
    report = census_report(_toy_capture(extra_gaps=(twin_a, twin_b), extra_closed=(False, False)))
    apertures = report["apertures"]
    assert apertures["raw_gaps"] == 3 and apertures["groups"] == 2 and apertures["groups_with_two_or_more_gaps"] == 1 and apertures["gaps_in_such_groups"] == 2
    assert apertures["ring_adding_gaps"] == 1 and apertures["ring_adding_distinct_groups"] == 1 and apertures["ring_adding_gaps_in_multi_gap_groups"] == 0


def test_a_gap_whose_closure_adds_no_ring_is_not_ring_adding_even_when_rings_exist():
    far_gap = _gap(300.0, 330.0, (394.0, 400.0))                                           # outside the room: closing it changes nothing
    report = census_report(_toy_capture(closed=True, extra_gaps=(far_gap,), extra_closed=(False,)))
    assert report["counts"]["rings"] == 1 and report["unclosed_gaps"]["count"] == 1
    assert report["unblocking_power"]["single_closure"]["gaps_adding_a_ring"] == 0
    assert report["unblocking_power"]["single_closure"]["gaps_removing_a_ring"] == 0
    assert report["unblocking_power"]["single_closure"]["adding_by_effect"] == {} and report["unblocking_power"]["single_closure"]["adding_by_orientation_and_effect"] == {}
    assert report["unblocking_power"]["if_all_unresolved_collinear_closed"] == 1 and report["apertures"]["ring_adding_gaps"] == 0


def test_the_per_class_closing_sets_close_only_the_gaps_of_that_class():
    stub = _gap(120.0, 150.0, (200.0, 206.0), collinear=False)                             # closing it changes nothing here
    rows = [_line((200.0, 130.0), (206.0, 130.0))]                                         # a stroke across the stub's band: perpendicular
    report = census_report(_toy_capture(rows=rows, extra_gaps=(stub,), extra_closed=(False,)))
    by_class = report["unblocking_power"]["if_all_unclosed_of_one_class_closed"]
    assert by_class == {"empty": 1, "perpendicular_strokes": 0}
    assert report["unblocking_power"]["if_every_unclosed_raw_gap_closed_UPPER_BOUND_NOT_A_RULE"] == 1


def test_per_gap_records_say_how_many_rings_a_gap_touches_and_how_big_its_aperture_group_is():
    twin = _gap(152.0, 178.0, (296.0, 299.0))
    capture = _toy_capture(extra_gaps=(twin,), extra_closed=(False,))
    capture = BuilderCapture(**{**capture.__dict__, "ring_touch": lambda polygon, i: i == 0, "builder_rings": (BuilderRing("candidate", ("x",), box(106, 106, 294, 234)),),
                               "builder_unresolved_collinear": 2})
    first, second = census_report(capture, per_gap=True)["gap_records"]
    assert (first["rings_touched"], first["aperture_group_size"]) == (1, 2) and (second["rings_touched"], second["aperture_group_size"]) == (0, 2)


def test_several_candidate_gaps_are_one_aperture_only_when_every_pair_overlaps():
    twin_a, twin_b, far = _gap(150.0, 180.0, (294.0, 300.0)), _gap(152.0, 178.0, (296.0, 299.0)), _gap(300.0, 330.0, (294.0, 300.0))
    info = census.ArcInfo(found=1, rejected_by_finder=0, builder_unplaced=0, builder_ambiguous=1, candidate_gap_indices=((0, 1, 2),))
    capture = _toy_capture(extra_gaps=(twin_b, far), extra_closed=(False, False), arc_info=info)
    arcs = census_report(capture)["native_arcs"]
    assert arcs["several_candidate_shape"] == {"different_apertures": 1}                   # gaps 0 and 1 overlap, gap 2 overlaps neither
    assert twin_a.horizontal == capture.gaps[0].horizontal


# ------------------------------------------------------------------------------------------------ what one closure does

@pytest.mark.parametrize("gain,area,effect", [
    (1, 5.0, "encloses_new_space"), (1, 1.1e-6, "encloses_new_space"), (1, 1e-6, "splits_an_enclosed_ring"), (1, 0.0, "splits_an_enclosed_ring"),
    (1, -30.0, "splits_an_enclosed_ring"), (3, 400.0, "encloses_new_space"), (0, 100.0, "adds_no_ring"), (0, -4.0, "adds_no_ring"),
    (-1, 100.0, "removes_a_ring"), (-2, 0.0, "removes_a_ring"),
])
def test_a_single_closure_that_adds_a_ring_either_encloses_new_space_or_splits_an_enclosed_ring(gain, area, effect):
    assert census.single_closure_effect(gain, area) == effect


def test_ring_parts_are_the_rings_and_their_count_is_the_ring_count():
    open_room, closed_room = _toy_capture(), _toy_capture(closed=True)
    assert ring_parts(open_room) == [] and len(ring_parts(closed_room)) == count_rings(closed_room) == 1
    (part,) = ring_parts(closed_room)
    assert part.area == pytest.approx(188.0 * 128.0)
    (after,) = ring_parts(open_room, [box(294, 150, 300, 180)])
    assert after.area == pytest.approx(188.0 * 128.0)


def test_closing_the_doorway_of_a_leaking_room_encloses_new_space_and_closing_a_partition_end_only_splits_a_ring():
    leaking = census_report(_toy_capture())
    assert leaking["unblocking_power"]["single_closure"]["adding_by_effect"] == {"encloses_new_space": 1}
    assert leaking["apertures"]["ring_adding_gaps"] == 1 and leaking["apertures"]["new_space_gaps"] == 1 and leaking["apertures"]["new_space_distinct_groups"] == 1
    partition = box(200, 106, 206, 200)                                                    # hangs from the top wall and stops 34 pt short of the bottom wall
    end_gap = _gap(200.0, 234.0, (200.0, 206.0), collinear=False)
    split = census_report(_toy_capture(closed=True, extra_walls=(partition,), extra_gaps=(end_gap,), extra_closed=(False,)), per_gap=True)
    assert split["counts"]["rings"] == 1 and split["replication"]["exact"] is True
    single = split["unblocking_power"]["single_closure"]
    assert single["gaps_adding_a_ring"] == 1 and single["adding_by_effect"] == {"splits_an_enclosed_ring": 1}
    assert single["adding_by_orientation_and_effect"] == {"non_collinear|splits_an_enclosed_ring": 1}
    assert split["apertures"]["ring_adding_gaps"] == 1 and split["apertures"]["new_space_gaps"] == 0 and split["apertures"]["new_space_distinct_groups"] == 0
    (record,) = split["gap_records"]
    assert record["single_closure_ring_gain"] == 1 and record["single_closure_effect"] == "splits_an_enclosed_ring"


def test_the_effect_figures_are_withheld_together_with_the_other_ring_figures():
    withheld = census_report(_toy_capture(closed=True, ring_count_override=2))
    assert withheld["unblocking_power"] is None
    assert withheld["apertures"]["new_space_gaps"] is None and withheld["apertures"]["new_space_distinct_groups"] is None
    quiet = census_report(_toy_capture(), per_gap=True, unblocking=False)
    assert quiet["gap_records"][0]["single_closure_effect"] is None
