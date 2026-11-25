"""P3a: measurement-only receipts for the source-owned doorway chord gates.

Synthetic only; no private source. ``propose_source_owned_doorway_chords`` either proposes a bounded doorway chord for a segmented
swing witness or silently skips it. ``diagnose_source_owned_doorway_chord_gates`` says WHY, one receipt per witness, in witness order:
the first failing gate (axis, four supports, parent raw gap, competing parents, duplicate interval), the support counts and native path
ids, and for every same-axis raw gap on the door's wall line the signed miss at each end of the door interval. It never changes the
proposer: each receipt's ``chord_proposed`` comes from a real proposer call, and ``agrees_with_proposer`` says whether the re-derived
gate agrees. Nothing here is a wall, an opening, a closure, a quantity or a score.
"""
from __future__ import annotations

import copy
import json
import math
import random
from types import SimpleNamespace

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_source_segmented_door_swing_shadow as seg
from pb_layered_wall_doorway_room_ring_shadow import _Gap
from pb_source_segmented_door_swing_shadow import (
    collect_source_black_segmented_door_swings,
    diagnose_source_owned_doorway_chord_gates as diagnose,
    propose_source_owned_doorway_chords,
)
from tools import diag_source_door_chord_gates as tool

BLACK = (0.0, 0.0, 0.0)
G0 = "G0_axis_not_horizontal_or_vertical"
G1 = "G1_wall_end_or_jamb_support_missing"
G2 = "G2_no_parent_raw_wall_gap"
G3 = "G3_competing_parent_raw_wall_gaps"
G4 = "G4_duplicate_door_interval"
REQUIRED = ("left", "right", "jamb_left", "jamb_right")


def _stroke(a, b, width=0.5):
    return {"layer": "", "fill": None, "color": BLACK, "width": width, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def door(width=52.0, *, lo=100.0, y0=43.0, vertical=False, dx=0.0, dy=0.0, drop=(), shift=None, perp=None, jamb_half=3.0,
         extend=100.0, extend_right=None, slant=0.0, tilt=0.0, threshold=False, threshold_shift=(0.0, 0.0), flip=False):
    """Rows of one door on a wall line: ONE stroke per support, then nine chord strokes of a quarter circle about the hinge at ``hi`` and
    the radial leaf. The wall runs along x (along y when ``vertical``); the door interval is [lo, lo + width] on the line ``y0``.

    ``drop`` removes support kinds; ``shift`` moves a support end along the wall by a signed amount; ``perp`` is the wall-end strokes'
    distance from the wall line; ``jamb_half`` is how far the jambs reach each side of the line; ``extend`` is how far the left wall-end
    stroke runs away from the door (``extend_right`` the right one, default the same); ``slant`` tilts the left wall-end stroke off the
    axis and ``tilt`` the left jamb; ``flip`` swings the door to the other side of the wall line (the same interval, different swing
    geometry)."""
    shift = shift or {}
    hi = lo + width
    perp = 3.0 if perp is None else perp
    sign = -1.0 if flip else 1.0
    extend_right = extend if extend_right is None else extend_right

    def point(along, across):
        x, y = (across, along) if vertical else (along, across)
        return (x + dx, y + dy)

    rows = []
    if "left" not in drop:
        rows.append(_stroke(point(lo - extend, y0 + perp), point(lo + shift.get("left", 0.0), y0 + perp + slant)))
    if "right" not in drop:
        rows.append(_stroke(point(hi + shift.get("right", 0.0), y0 + perp), point(hi + extend_right, y0 + perp)))
    if "jamb_left" not in drop:
        at = lo + shift.get("jamb_left", 0.0)
        rows.append(_stroke(point(at, y0 - jamb_half), point(at + tilt, y0 + jamb_half)))
    if "jamb_right" not in drop:
        at = hi + shift.get("jamb_right", 0.0)
        rows.append(_stroke(point(at, y0 - jamb_half), point(at, y0 + jamb_half)))
    if threshold:
        rows.append(_stroke(point(lo + threshold_shift[0], y0 + 1.0), point(hi + threshold_shift[1], y0 + 1.0)))
    pts = [point(hi - width * math.cos(math.radians(10 * k)), y0 + sign * width * math.sin(math.radians(10 * k))) for k in range(10)]
    for a, b in zip(pts, pts[1:]):
        rows.append(_stroke(a, b))
    rows.append(_stroke(point(hi, y0), point(hi, y0 + sign * width)))
    return rows


def parent(*, lo=100.0, hi=152.0, y0=43.0, horizontal=True, half=3.0, lo_miss=0.0, hi_miss=0.0):
    """A raw gap whose ends are ``lo_miss`` / ``hi_miss`` SHORT of the door interval (negative = beyond it)."""
    return _Gap(horizontal, (y0 - half, y0 + half), lo + lo_miss, hi - hi_miss, (), ())


def run(rows, gaps):
    witnesses = collect_source_black_segmented_door_swings(rows)
    return witnesses, diagnose(rows, witnesses, tuple(gaps))


def one(rows, gaps):
    witnesses, receipts = run(rows, gaps)
    assert len(witnesses) == 1 and len(receipts) == 1
    return receipts[0]


# ------------------------------------------------------------------------------------------------ the chord and the flags

def test_a_supported_door_with_one_whole_parent_gap_is_a_chord_and_the_receipt_says_so():
    rows = door()
    r = one(rows, [parent()])
    assert r["first_failing_gate"] is None
    assert r["chord_proposed"] is True and r["agrees_with_proposer"] is True
    assert r["axis"] == "horizontal" and r["witness_index"] == 0
    assert r["door_interval_pdf_pts"] == (100.0, 152.0) and r["wall_line_perp_pdf_pts"] == 43.0
    assert r["parent_gap_count"] == 1 and r["parent_gap_indices"] == (0,) and r["duplicate_of_witness_index"] is None
    assert all(r["support_counts"][k] == 1 for k in REQUIRED) and r["support_counts"]["threshold"] == 0
    assert r["missing_required_supports"] == ()
    (chord,) = propose_source_owned_doorway_chords(rows, collect_source_black_segmented_door_swings(rows), (parent(),))
    assert chord["door_interval_pdf_pts"] == r["door_interval_pdf_pts"]


def test_every_receipt_is_diagnostic_only_and_authorises_nothing():
    receipts = run(door(), [parent()])[1] + run(door(drop=("left",)), [parent()])[1]
    assert len(receipts) == 2
    for r in receipts:
        assert r["diagnostic_only"] is True
        for flag in ("candidate_topology_doorway_closure", "source_physical_door_host_authenticated", "metric_area_issued",
                     "commercial_publishable"):
            assert r[flag] is False, flag
        json.dumps(r)                                                            # plain data, serialisable


def test_no_witness_gives_no_receipts():
    assert diagnose([], (), ()) == ()
    assert diagnose([_stroke((0.0, 0.0), (50.0, 0.0))], (), (parent(),)) == ()


# ------------------------------------------------------------------------------------------------ G1: supports

@pytest.mark.parametrize("kind", REQUIRED)
def test_each_missing_required_support_is_the_first_failing_gate(kind):
    r = one(door(drop=(kind,)), [parent()])
    assert r["first_failing_gate"] == G1 and r["chord_proposed"] is False and r["agrees_with_proposer"] is True
    assert r["missing_required_supports"] == (kind,)
    assert r["support_counts"][kind] == 0 and r["support_path_indices"][kind] == ()
    assert all(r["support_counts"][k] == 1 for k in REQUIRED if k != kind)


def test_several_missing_supports_are_listed_in_the_fixed_order():
    r = one(door(drop=("jamb_right", "left")), [parent()])
    assert r["first_failing_gate"] == G1 and r["missing_required_supports"] == ("left", "jamb_right")


def test_a_door_that_fails_its_supports_still_reports_its_parent_gaps():
    r = one(door(drop=("left",)), [parent(), parent(hi_miss=2.4)])
    assert r["first_failing_gate"] == G1 and r["parent_gap_count"] == 1 and len(r["gap_candidates"]) == 2


def test_the_threshold_stroke_is_optional_and_counted():
    with_threshold = one(door(threshold=True), [parent()])
    without = one(door(), [parent()])
    assert with_threshold["support_counts"]["threshold"] == 1 and without["support_counts"]["threshold"] == 0
    assert with_threshold["chord_proposed"] is True and without["chord_proposed"] is True


def test_support_path_indices_are_the_original_native_indices():
    rows = [_stroke((0.0, 0.0), (1.0, 0.0))] * 3 + door()                         # three unrelated leading rows shift every index
    r = one(rows, [parent()])
    assert r["support_path_indices"]["left"] == (3,) and r["support_path_indices"]["right"] == (4,)
    assert r["support_path_indices"]["jamb_left"] == (5,) and r["support_path_indices"]["jamb_right"] == (6,)
    assert set(r["witness_native_path_indices"]) == set(range(7, 17))


@pytest.mark.parametrize("what,kind,kwargs,passes", [
    ("wall-end ends 0.17 pt inside the tolerance", "left", {"shift": {"left": 0.17}}, True),
    ("wall-end ends 0.19 pt outside it", "left", {"shift": {"left": 0.19}}, False),
    ("right wall-end starts 0.17 pt off", "right", {"shift": {"right": -0.17}}, True),
    ("right wall-end starts 0.19 pt off", "right", {"shift": {"right": -0.19}}, False),
    ("left jamb 0.17 pt off", "jamb_left", {"shift": {"jamb_left": 0.17}}, True),
    ("left jamb 0.19 pt off", "jamb_left", {"shift": {"jamb_left": 0.19}}, False),
    ("right jamb 0.17 pt off", "jamb_right", {"shift": {"jamb_right": -0.17}}, True),
    ("right jamb 0.19 pt off", "jamb_right", {"shift": {"jamb_right": -0.19}}, False),
    ("wall-end 2.9 pt from the wall line", "left", {"perp": 2.9}, True),
    ("wall-end 3.1 pt from the wall line", "left", {"perp": 3.1}, False),
    ("jamb reaches 13.9 pt each side", "jamb_left", {"jamb_half": 13.9}, True),
    ("jamb reaches 14.1 pt each side", "jamb_left", {"jamb_half": 14.1}, False),
    ("wall-end 1.25 pt long", "left", {"extend": 1.25}, True),
    ("wall-end 1.1 pt long", "left", {"extend": 1.1}, False),
    ("wall-end 1.25 pt long, its end 0.17 pt past the door end", "left", {"extend": 1.08, "extend_right": 100.0, "shift": {"left": 0.17}}, True),
    ("wall-end slanted 0.1 pt off the axis", "left", {"slant": 0.1}, True),
    ("wall-end slanted 0.14 pt off the axis", "left", {"slant": 0.14}, False),
    ("jamb leaning 0.1 pt", "jamb_left", {"tilt": 0.1}, True),
    ("jamb leaning 0.14 pt", "jamb_left", {"tilt": 0.14}, False),
    ("jamb 1.4 pt long", "jamb_left", {"jamb_half": 0.7}, True),
    ("jamb 1.1 pt long", "jamb_left", {"jamb_half": 0.55}, False),
    ("wall-end 0.179 pt inside the tolerance", "left", {"shift": {"left": 0.179}}, True),
    ("wall-end 0.181 pt outside it", "left", {"shift": {"left": 0.181}}, False),
    ("right wall-end 0.179 pt off", "right", {"shift": {"right": -0.179}}, True),
    ("right wall-end 0.181 pt off", "right", {"shift": {"right": -0.181}}, False),
    ("left jamb 0.179 pt off", "jamb_left", {"shift": {"jamb_left": 0.179}}, True),
    ("left jamb 0.181 pt off", "jamb_left", {"shift": {"jamb_left": 0.181}}, False),
    ("right jamb 0.179 pt off", "jamb_right", {"shift": {"jamb_right": -0.179}}, True),
    ("right jamb 0.181 pt off", "jamb_right", {"shift": {"jamb_right": -0.181}}, False),
    ("wall-end 2.99 pt from the wall line", "left", {"perp": 2.99}, True),
    ("wall-end 3.01 pt from the wall line", "left", {"perp": 3.01}, False),
    ("jamb reaches 13.99 pt each side", "jamb_left", {"jamb_half": 13.99}, True),
    ("jamb reaches 14.01 pt each side", "jamb_left", {"jamb_half": 14.01}, False),
    ("wall-end 1.21 pt long", "left", {"extend": 1.21}, True),
    ("wall-end 1.19 pt long", "left", {"extend": 1.19}, False),
    ("wall-end 1.209 pt long, its end 0.179 pt past the door end", "left",
     {"extend": 1.03, "extend_right": 100.0, "shift": {"left": 0.179}}, True),
    ("wall-end slanted 0.115 pt", "left", {"slant": 0.115}, True),
    ("wall-end slanted 0.125 pt", "left", {"slant": 0.125}, False),
    ("jamb leaning 0.115 pt", "jamb_left", {"tilt": 0.115}, True),
    ("jamb leaning 0.125 pt", "jamb_left", {"tilt": 0.125}, False),
    ("jamb 1.21 pt long", "jamb_left", {"jamb_half": 0.605}, True),
    ("jamb 1.19 pt long", "jamb_left", {"jamb_half": 0.595}, False),
])

def test_support_tolerance_boundaries(what, kind, kwargs, passes):
    r = one(door(**kwargs), [parent()])
    assert (r["support_counts"][kind] >= 1) is passes, what
    assert (r["first_failing_gate"] is None) is passes and r["agrees_with_proposer"] is True, what

@pytest.mark.parametrize("shift,count", [
    ((0.0, 0.0), 1), ((0.179, 0.0), 1), ((0.181, 0.0), 0), ((0.0, 0.179), 1), ((0.0, 0.181), 0), ((0.5, 0.0), 0), ((0.0, 0.5), 0),
    ((-0.179, -0.179), 1), ((-0.181, 0.0), 0),
])
def test_the_optional_threshold_stroke_needs_both_ends_within_0_18_pt(shift, count):
    r = one(door(threshold=True, threshold_shift=shift), [parent()])
    assert r["support_counts"]["threshold"] == count and r["first_failing_gate"] is None and r["agrees_with_proposer"] is True


def test_the_wall_end_distance_uses_the_mean_of_hinge_and_closed_tip():
    # the hinge sits on the wall line, the closed tip 0.12 pt off it: the wall line the proposer uses is their mean (0.06 pt off), so a
    # wall-end 3.05 pt from the hinge is still within 3.0 pt of it
    rows = door(perp=3.05)
    (real,) = collect_source_black_segmented_door_swings(rows)
    w = _manual_witness(real, (152.0, 43.0), (100.0, 43.12))
    (r,) = diagnose(rows, (w,), (parent(),))
    assert r["wall_line_perp_pdf_pts"] == pytest.approx(43.06) and r["support_counts"]["left"] == 1
    assert r["first_failing_gate"] is None and r["agrees_with_proposer"] is True


def test_a_witness_that_owns_a_support_stroke_does_not_count_it_and_does_not_claim_the_chord_of_another():
    rows = door()
    (real,) = collect_source_black_segmented_door_swings(rows)
    own_left = dict(real)
    own_left["native_source_path_indices"] = tuple(sorted(set(real["native_source_path_indices"]) | {0}))   # stroke 0 is the left wall-end
    receipts = diagnose(rows, (own_left, real), (parent(),))
    assert receipts[0]["first_failing_gate"] == G1 and receipts[0]["missing_required_supports"] == ("left",)
    assert receipts[1]["first_failing_gate"] is None
    assert [r["chord_proposed"] for r in receipts] == [False, True] and all(r["agrees_with_proposer"] for r in receipts)


def test_support_path_indices_are_ascending():
    rows = [_stroke((0.0, 40.0), (100.0, 40.0))] + door()                        # a second left wall-end, 3 pt the other side
    r = one(rows, [parent()])
    assert r["support_counts"]["left"] == 2 and r["support_path_indices"]["left"] == (0, 1)


# ------------------------------------------------------------------------------------------------ G0: axis

def _manual_witness(real, hinge, tip):
    w = dict(real)
    w["source_hinge_point_pdf_pts"] = hinge
    w["source_closed_leaf_tip_pdf_pts"] = tip
    return w


@pytest.mark.parametrize("what,hinge,tip,axis,gate0", [
    ("exactly horizontal", (152.0, 0.0), (100.0, 0.0), "horizontal", False),
    ("0.12 pt off the axis is still horizontal", (152.0, 0.0), (100.0, 0.12), "horizontal", False),
    ("0.2 pt off the axis is ambiguous", (152.0, 0.0), (100.0, 0.2), "ambiguous", True),
    ("exactly vertical", (0.0, 152.0), (0.0, 100.0), "vertical", False),
    ("a diagonal is ambiguous", (152.0, 0.0), (100.0, 52.0), "ambiguous", True),
    ("a door narrower than 1 pt is ambiguous", (100.5, 0.0), (100.0, 0.0), "ambiguous", True),
    ("0.125 pt off the axis is ambiguous", (152.0, 0.0), (100.0, 0.125), "ambiguous", True),
    ("a 1.5 pt door is horizontal", (101.5, 0.0), (100.0, 0.0), "horizontal", False),
    ("vertical, 0.12 pt off the axis", (0.0, 152.0), (0.12, 100.0), "vertical", False),
    ("vertical, 0.125 pt off the axis is ambiguous", (0.0, 152.0), (0.125, 100.0), "ambiguous", True),
    ("vertical, 0.2 pt off the axis is ambiguous", (0.0, 152.0), (0.2, 100.0), "ambiguous", True),
    ("a vertical door narrower than 1 pt is ambiguous", (0.0, 100.5), (0.0, 100.0), "ambiguous", True),
    ("a 1.5 pt vertical door is vertical", (0.0, 101.5), (0.0, 100.0), "vertical", False),
])
def test_the_axis_gate(what, hinge, tip, axis, gate0):
    (real,) = collect_source_black_segmented_door_swings(door())
    w = _manual_witness(real, hinge, tip)
    (r,) = diagnose(door(), (w,), (parent(),))
    assert r["axis"] == axis, what
    assert (r["first_failing_gate"] == G0) is gate0, what
    assert r["agrees_with_proposer"] is True, what
    if gate0:
        assert r["door_interval_pdf_pts"] is None and r["wall_line_perp_pdf_pts"] is None
        assert r["gap_candidates"] is None and r["support_counts"] is None and r["parent_gap_count"] is None
    else:
        assert r["door_interval_pdf_pts"] is not None and r["gap_candidates"] is not None


# ------------------------------------------------------------------------------------------------ G2 / G3: parent raw gaps

def test_no_gap_at_all_is_no_parent():
    r = one(door(), [])
    assert r["first_failing_gate"] == G2 and r["parent_gap_count"] == 0 and r["gap_candidates"] == ()
    assert r["agrees_with_proposer"] is True


def test_a_gap_of_the_other_orientation_is_not_a_candidate():
    r = one(door(), [parent(horizontal=False)])
    assert r["first_failing_gate"] == G2 and r["gap_candidates"] == ()


def test_a_gap_on_another_wall_line_is_not_a_candidate():
    assert one(door(), [parent(y0=43.0 + 30.0)])["gap_candidates"] == ()
    near = parent(y0=43.0 + 5.0, half=3.0)                                        # band 45..51 holds 43 within max(.18, 6)
    assert len(one(door(), [near])["gap_candidates"]) == 1


@pytest.mark.parametrize("hi_miss,is_parent", [(0.17, True), (0.19, False), (-1200.0, True), (2.4, False), (0.6, False)])
def test_a_gap_must_reach_the_far_end_within_0_18_pt(hi_miss, is_parent):
    r = one(door(), [parent(hi_miss=hi_miss)])
    (c,) = r["gap_candidates"]
    assert c["is_parent"] is is_parent and (r["parent_gap_count"] == 1) is is_parent
    assert c["hi_end_miss_pdf_pts"] == pytest.approx(hi_miss, abs=1e-9)
    assert (r["first_failing_gate"] is None) is is_parent and r["agrees_with_proposer"] is True


@pytest.mark.parametrize("lo_miss,is_parent", [(0.17, True), (0.19, False), (-1286.0, True), (1.0, False)])
def test_a_gap_must_reach_the_near_end_within_0_18_pt(lo_miss, is_parent):
    r = one(door(), [parent(lo_miss=lo_miss)])
    (c,) = r["gap_candidates"]
    assert c["is_parent"] is is_parent and c["lo_end_miss_pdf_pts"] == pytest.approx(lo_miss, abs=1e-9)
    assert r["agrees_with_proposer"] is True


def test_a_gap_that_contains_the_door_with_neither_end_coincident_is_not_a_parent():
    r = one(door(), [parent(lo_miss=-5.0, hi_miss=-5.0)])
    (c,) = r["gap_candidates"]
    assert c["contains_interval"] is True and c["an_end_coincides"] is False and c["is_parent"] is False
    assert r["first_failing_gate"] == G2 and r["agrees_with_proposer"] is True


def test_a_gap_that_coincides_at_one_end_but_stops_inside_the_other_is_not_a_parent():
    r = one(door(), [parent(hi_miss=1.0)])
    (c,) = r["gap_candidates"]
    assert c["an_end_coincides"] is True and c["contains_interval"] is False and c["is_parent"] is False


def test_the_receipt_reports_the_signed_miss_of_every_candidate_gap_in_order():
    gaps = [parent(hi_miss=2.4), parent(hi_miss=-300.0, half=2.0), parent(lo_miss=1.0)]
    r = one(door(), gaps)
    assert [c["gap_index"] for c in r["gap_candidates"]] == [0, 1, 2]
    assert [c["hi_end_miss_pdf_pts"] for c in r["gap_candidates"]] == pytest.approx([2.4, -300.0, 0.0])
    assert [c["lo_end_miss_pdf_pts"] for c in r["gap_candidates"]] == pytest.approx([0.0, 0.0, 1.0])
    assert r["parent_gap_indices"] == (1,) and r["first_failing_gate"] is None
    assert r["same_axis_gap_count"] == 3 and r["gap_count"] == 3


def test_two_different_parents_compete():
    r = one(door(), [parent(half=3.0), parent(half=2.0, hi_miss=-40.0)])
    assert r["first_failing_gate"] == G3 and r["parent_gap_count"] == 2 and r["parent_gap_indices"] == (0, 1)
    assert r["parents_share_one_geometry"] is False and r["chord_proposed"] is False and r["agrees_with_proposer"] is True


def test_two_identical_parents_are_still_two_parents_but_one_geometry():
    r = one(door(), [parent(), parent()])
    assert r["first_failing_gate"] == G3 and r["parent_gap_count"] == 2 and r["parents_share_one_geometry"] is True
    assert r["agrees_with_proposer"] is True


def test_a_parent_beside_non_parents_is_the_only_parent():
    r = one(door(), [parent(hi_miss=2.4), parent(), parent(horizontal=False), parent(y0=500.0)])
    assert r["parent_gap_indices"] == (1,) and r["first_failing_gate"] is None and len(r["gap_candidates"]) == 2
    assert r["same_axis_gap_count"] == 3 and r["gap_count"] == 4


@pytest.mark.parametrize("what,band,candidate", [
    ("a thin band 0.19 pt above the wall line is just outside", (43.19, 43.29), False),
    ("a thin band 0.17 pt above the wall line is just inside", (43.17, 43.27), True),
    ("a thin band 0.19 pt below the wall line is just outside", (42.71, 42.81), False),
    ("a thin band 0.17 pt below the wall line is just inside", (42.73, 42.83), True),
    ("a thick band is judged by its own thickness above", (31.0, 38.0), True),
    ("a thick band is judged by its own thickness below", (48.0, 55.0), True),
    ("a thick band further than its thickness is outside", (30.0, 35.0), False),
])
def test_the_wall_line_band_tolerance_is_the_larger_of_0_18_pt_and_the_band_thickness(what, band, candidate):
    r = one(door(), [_Gap(True, band, 100.0, 152.0, (), ())])
    assert (len(r["gap_candidates"]) == 1) is candidate, what
    assert r["agrees_with_proposer"] is True, what


@pytest.mark.parametrize("lo_miss,hi_miss,is_parent", [
    (0.179, 0.0, True), (0.181, 0.0, False), (0.0, 0.179, True), (0.0, 0.181, False),
    (-0.179, -0.179, True), (-0.181, -0.181, False), (-0.179, -0.181, True), (-0.181, -0.179, True),
])
def test_a_gap_must_contain_the_door_and_share_an_end_within_0_18_pt(lo_miss, hi_miss, is_parent):
    r = one(door(), [parent(lo_miss=lo_miss, hi_miss=hi_miss)])
    (c,) = r["gap_candidates"]
    assert c["is_parent"] is is_parent and r["agrees_with_proposer"] is True


def test_two_parents_that_differ_only_in_their_far_end_or_band_width_are_not_one_geometry():
    far = one(door(), [_Gap(True, (40.0, 46.0), 100.0, 152.0, (), ()), _Gap(True, (40.0, 46.0), 100.0, 300.0, (), ())])
    wide = one(door(), [_Gap(True, (40.0, 46.0), 100.0, 152.0, (), ()), _Gap(True, (40.0, 50.0), 100.0, 152.0, (), ())])
    for r in (far, wide):
        assert r["first_failing_gate"] == G3 and r["parent_gap_count"] == 2 and r["parents_share_one_geometry"] is False


# ------------------------------------------------------------------------------------------------ G4: duplicate interval

def test_a_second_witness_on_the_same_interval_is_a_duplicate():
    rows = door() + door(flip=True, drop=REQUIRED)                                # the same doorway swung to the other side
    witnesses, receipts = run(rows, [parent()])
    assert len(witnesses) == 2 and len(receipts) == 2
    assert [r["first_failing_gate"] for r in receipts] == [None, G4]
    assert [r["chord_proposed"] for r in receipts] == [True, False]
    assert [r["duplicate_of_witness_index"] for r in receipts] == [None, 0]
    assert all(r["agrees_with_proposer"] for r in receipts)
    assert [r["witness_index"] for r in receipts] == [0, 1]
    assert receipts[0]["witness_native_path_indices"] != receipts[1]["witness_native_path_indices"]


def test_doors_with_the_same_far_end_or_the_same_numbers_on_the_other_axis_are_not_duplicates():
    rows = door() + door(40.0, lo=112.0, flip=True)                               # same wall line and far end, another near end
    receipts = run(rows, [parent()])[1]
    assert [r["door_interval_pdf_pts"] for r in receipts] == [(100.0, 152.0), (112.0, 152.0)]
    assert [r["first_failing_gate"] for r in receipts] == [None, None] and all(r["agrees_with_proposer"] for r in receipts)
    rows = door() + door(vertical=True)                                           # the same numbers on the other axis
    receipts = run(rows, [parent(), parent(horizontal=False)])[1]
    assert [r["axis"] for r in receipts] == ["horizontal", "vertical"]
    assert [r["first_failing_gate"] for r in receipts] == [None, None] and all(r["agrees_with_proposer"] for r in receipts)


def test_doors_that_share_one_end_or_one_interval_on_another_wall_line_are_not_duplicates():
    # same wall line and near end, different width: two intervals, both inside the one raw gap
    receipts = run(door() + door(40.0, flip=True), [parent()])[1]
    assert [r["door_interval_pdf_pts"] for r in receipts] == [(100.0, 152.0), (100.0, 140.0)]
    assert [r["first_failing_gate"] for r in receipts] == [None, None] and all(r["agrees_with_proposer"] for r in receipts)
    # the same interval on a parallel wall line one hundred points away
    receipts = run(door() + door(y0=143.0, flip=True), [parent(), parent(y0=143.0)])[1]
    assert [r["wall_line_perp_pdf_pts"] for r in receipts] == [43.0, 143.0]
    assert [r["first_failing_gate"] for r in receipts] == [None, None] and all(r["agrees_with_proposer"] for r in receipts)


def test_a_witness_with_the_same_paths_but_another_interval_or_axis_does_not_claim_the_chord():
    rows = door()
    (real,) = collect_source_black_segmented_door_swings(rows)
    shifted = _manual_witness(real, (153.0, 43.0), (101.0, 43.0))                 # same paths, interval moved by one point
    turned = _manual_witness(real, (43.0, 152.0), (43.0, 100.0))                  # same paths, the other axis, the same numbers
    receipts = diagnose(rows, (shifted, turned, real), (parent(),))
    assert [r["chord_proposed"] for r in receipts] == [False, False, True]
    assert [r["first_failing_gate"] is None for r in receipts] == [False, False, True]
    assert all(r["agrees_with_proposer"] for r in receipts)


def test_the_axis_extent_is_the_hinge_to_closed_tip_distance_along_each_axis():
    assert one(door(), [parent()])["axis_extent_pdf_pts"] == (52.0, 0.0)
    assert one(door(vertical=True), [parent(horizontal=False)])["axis_extent_pdf_pts"] == (0.0, 52.0)


def test_a_single_parent_is_not_a_shared_geometry():
    assert one(door(), [parent()])["parents_share_one_geometry"] is False
    assert one(door(), [])["parents_share_one_geometry"] is False


def test_a_witness_that_fails_an_earlier_gate_does_not_make_the_next_one_a_duplicate():
    rows = door()
    (real,) = collect_source_black_segmented_door_swings(rows)
    ambiguous = _manual_witness(real, (152.0, 43.0), (100.0, 43.2))               # same indices, fails G0
    receipts = diagnose(rows, (ambiguous, real), (parent(),))
    assert [r["first_failing_gate"] for r in receipts] == [G0, None]
    assert [r["chord_proposed"] for r in receipts] == [False, True] and all(r["agrees_with_proposer"] for r in receipts)


# ------------------------------------------------------------------------------------------------ seeded fuzz, invariance

def _random_case(seed):
    rng = random.Random(seed)
    vertical = rng.random() < 0.5
    rows, gaps, first_width = [], [], None
    for k in range(rng.choice([1, 1, 2, 3])):
        width = rng.choice([23.0, 38.5, 52.0, 70.25, 138.0])
        first_width = first_width or width
        lo = 100.0 + 600.0 * k
        drop = tuple(kind for kind in REQUIRED if rng.random() < 0.06)
        shift = {kind: rng.choice([0.17, -0.17, 0.19, -0.19, 0.5]) for kind in REQUIRED if rng.random() < 0.2}
        rows += door(width, lo=lo, vertical=vertical, drop=drop, shift=shift, perp=rng.choice([3.0, 3.0, 3.0, 2.9, 3.1]),
                     jamb_half=rng.choice([3.0, 3.0, 3.0, 13.9, 14.1]), threshold=rng.random() < 0.3)
        if rng.random() < 0.6:                                                    # most doorways have a whole raw gap on their line
            gaps.append(parent(lo=lo, hi=lo + width, horizontal=not vertical))
        for _ in range(rng.choice([0, 0, 1, 1, 2])):
            gaps.append(parent(lo=lo, hi=lo + width, horizontal=not vertical, half=rng.choice([3.0, 2.0, 4.0]),
                               lo_miss=rng.choice([0.0, 0.0, 0.17, 0.19, -1000.0, 1.0, -5.0]),
                               hi_miss=rng.choice([0.0, 0.0, 0.17, 0.19, -1000.0, 2.4, -5.0]),
                               y0=rng.choice([43.0, 43.0, 43.0, 49.5, 90.0])))
        if rng.random() < 0.1:
            gaps.append(gaps[-1] if gaps else parent())
    if rng.random() < 0.15:                                                       # the first doorway swung to the other side as well
        rows += door(first_width, lo=100.0, vertical=vertical, flip=True, drop=REQUIRED)
    return rows, gaps


SEEDS = range(300)


def test_the_re_derived_gate_agrees_with_the_real_proposer_on_seeded_fuzz():
    witness_total = chords = 0
    for seed in SEEDS:
        rows, gaps = _random_case(seed)
        witnesses, receipts = run(rows, gaps)
        proposed = propose_source_owned_doorway_chords(rows, witnesses, tuple(gaps))
        assert len(receipts) == len(witnesses), seed
        assert [r["witness_index"] for r in receipts] == list(range(len(witnesses))), seed
        assert all(r["agrees_with_proposer"] for r in receipts), seed
        assert sum(r["chord_proposed"] for r in receipts) == len(proposed), seed
        assert [tuple(w["native_source_path_indices"]) for w, r in zip(witnesses, receipts) if r["chord_proposed"]] == \
               [tuple(c["source_swing_native_path_indices"]) for c in proposed], seed
        witness_total += len(witnesses)
        chords += len(proposed)
    assert witness_total > 300 and 30 < chords < witness_total                    # the fuzz really exercises both outcomes


def _gap_case(seed):
    """One fully supported door and 1 to 4 random raw gaps (orientation, band, thickness and end misses all vary)."""
    rng = random.Random(10_000 + seed)
    vertical = rng.random() < 0.5
    gaps = [parent(horizontal=(not vertical) if rng.random() < 0.85 else vertical, half=rng.choice([0.05, 1.0, 3.0, 5.0]),
                   y0=rng.choice([43.0, 43.0, 43.2, 44.0, 49.0, 60.0]),
                   lo_miss=rng.choice([0.0, 0.1, 0.17, 0.19, 0.5, -0.1, -300.0]),
                   hi_miss=rng.choice([0.0, 0.1, 0.17, 0.19, 0.5, -0.1, -300.0])) for _ in range(rng.choice([1, 2, 3, 4]))]
    return door(52.0, vertical=vertical), gaps


def test_the_parent_gap_gates_agree_with_the_real_proposer_on_random_gap_sets():
    seen = {}
    for seed in range(400):
        rows, gaps = _gap_case(seed)
        witnesses, receipts = run(rows, gaps)
        assert len(receipts) == 1 and receipts[0]["agrees_with_proposer"], seed
        r = receipts[0]
        assert r["parent_gap_count"] == sum(c["is_parent"] for c in r["gap_candidates"]), seed
        assert r["same_axis_gap_count"] == sum(1 for g in gaps if g.horizontal == (r["axis"] == "horizontal")), seed
        seen[r["first_failing_gate"]] = seen.get(r["first_failing_gate"], 0) + 1
    assert set(seen) == {None, G2, G3} and min(seen.values()) >= 15, seen


def test_every_reachable_gate_is_reached_by_the_fuzz():
    seen = set()
    for seed in SEEDS:
        rows, gaps = _random_case(seed)
        seen |= {r["first_failing_gate"] for r in run(rows, gaps)[1]}
    assert seen == {None, G1, G2, G3, G4}                                         # G0 needs a hand-made witness (see the axis test)


def _translate(rows, gaps, dx, dy):
    out = copy.deepcopy(rows)
    for row in out:
        a, b = row["items"][0][1], row["items"][0][2]
        row["items"] = [("l", fitz.Point(a.x + dx, a.y + dy), fitz.Point(b.x + dx, b.y + dy))]
    moved = []
    for g in gaps:
        across, along = (dy, dx) if g.horizontal else (dx, dy)
        moved.append(_Gap(g.horizontal, (g.band[0] + across, g.band[1] + across), g.lo + along, g.hi + along, (), ()))
    return out, moved


def _swap_axes(rows, gaps):
    out = copy.deepcopy(rows)
    for row in out:
        a, b = row["items"][0][1], row["items"][0][2]
        row["items"] = [("l", fitz.Point(a.y, a.x), fitz.Point(b.y, b.x))]
    return out, [_Gap(not g.horizontal, g.band, g.lo, g.hi, (), ()) for g in gaps]


def _essence(receipts):
    return [(r["first_failing_gate"], r["chord_proposed"], tuple(sorted(r["support_counts"].items())), r["parent_gap_count"],
             r["missing_required_supports"], r["parents_share_one_geometry"], r["duplicate_of_witness_index"],
             tuple((c["gap_index"], round(c["lo_end_miss_pdf_pts"], 6), round(c["hi_end_miss_pdf_pts"], 6), c["is_parent"])
                   for c in r["gap_candidates"])) for r in receipts]


@pytest.mark.parametrize("seed", list(range(0, 300, 7)))
def test_translation_and_axis_swap_do_not_change_the_receipts(seed):
    rows, gaps = _random_case(seed)
    base_receipts = run(rows, gaps)[1]
    base = _essence(base_receipts)
    moved_rows, moved_gaps = _translate(rows, gaps, 37.5, -21.25)
    assert _essence(run(moved_rows, moved_gaps)[1]) == base
    swapped_rows, swapped_gaps = _swap_axes(rows, gaps)
    swapped = run(swapped_rows, swapped_gaps)[1]
    assert _essence(swapped) == base
    flip = {"horizontal": "vertical", "vertical": "horizontal", "ambiguous": "ambiguous"}
    assert [r["axis"] for r in swapped] == [flip[r["axis"]] for r in base_receipts]


def test_unrelated_leading_rows_shift_the_indices_and_nothing_else():
    rows, gaps = _random_case(3)
    lead = [_stroke((5000.0, 5000.0), (5000.0, 5000.5))] * 25
    a, b = run(rows, gaps)[1], run(lead + rows, gaps)[1]
    assert _essence(a) == _essence(b)
    assert [r["witness_native_path_indices"] for r in b] == [tuple(i + 25 for i in r["witness_native_path_indices"]) for r in a]


def test_diagnosing_never_mutates_and_replays_deterministically():
    rows, gaps = _random_case(11)
    witnesses = collect_source_black_segmented_door_swings(rows)
    before = copy.deepcopy((rows, witnesses, gaps))
    first, second = diagnose(rows, witnesses, tuple(gaps)), diagnose(rows, witnesses, tuple(gaps))
    assert (rows, witnesses, gaps) == before
    assert first == second and json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_proposer_is_unchanged_by_diagnosing():
    rows, gaps = _random_case(21)
    witnesses = collect_source_black_segmented_door_swings(rows)
    before = propose_source_owned_doorway_chords(rows, witnesses, tuple(gaps))
    diagnose(rows, witnesses, tuple(gaps))
    assert propose_source_owned_doorway_chords(rows, witnesses, tuple(gaps)) == before


def test_the_receipt_calls_the_real_proposer_and_does_not_trust_its_own_gates(monkeypatch):
    rows = door()
    witnesses = collect_source_black_segmented_door_swings(rows)
    monkeypatch.setattr(seg, "propose_source_owned_doorway_chords", lambda *a, **k: ())    # a proposer that proposes nothing
    (r,) = diagnose(rows, witnesses, (parent(),))
    assert r["chord_proposed"] is False and r["first_failing_gate"] is None
    assert r["agrees_with_proposer"] is False                                     # drift is flagged, never hidden


# ------------------------------------------------------------------------------------------------ the read-only tool

def _ring_scene(width=52.0, lo=1234.5, y0=43.0):
    """A wall with one doorway drawn the way the ring builder reads it: two faces each side, two jambs, the swing chain and its leaf."""
    hi = lo + width
    rows = []
    for y in (y0 - 3.0, y0 + 3.0):
        rows.append(_stroke((lo - 100.0, y), (lo, y)))
        rows.append(_stroke((hi, y), (hi + 148.0, y)))
    rows.append(_stroke((lo, y0 - 3.0), (lo, y0 + 3.0)))
    rows.append(_stroke((hi, y0 - 3.0), (hi, y0 + 3.0)))
    pts = [(hi - width * math.cos(math.radians(10 * k)), y0 + width * math.sin(math.radians(10 * k))) for k in range(10)]
    for a, b in zip(pts, pts[1:]):
        rows.append(_stroke(a, b))
    rows.append(_stroke((hi, y0), (hi, y0 + width)))
    return rows


@pytest.mark.parametrize("door_jamb_returns", [False, True])
def test_the_tool_names_the_gate_and_the_strip_that_owns_the_door_ink(door_jamb_returns):
    report = tool.page_report(_ring_scene(), page_index=0, door_jamb_returns=door_jamb_returns)
    assert report["builder_keeps_door_owned_strokes_out_of_the_strips"] is door_jamb_returns
    assert report["proposal_called"] is True and report["witness_count"] == 1 and report["raw_gap_count"] >= 1
    assert report["all_receipts_agree_with_the_proposer"] is True
    (w,) = report["witnesses"]
    assert w["agrees_with_proposer"] is True and w["axis"] == "horizontal"
    merged = [s for s in w["strips_owning_witness_paths"] if s["collector"] == "merged_collinear_face"]
    assert merged and merged[0]["owned_paths_in_strip"] >= 1 and merged[0]["covers_the_wall_line"] is True
    assert merged[0]["strip_runs_along_the_door_axis"] is False                   # a thin strip standing across the doorway
    assert 0.3 < merged[0]["reach_into_door_interval_pdf_pts"] < 1.0              # at its hinge end (the finding of the P3a note)
    assert report["witnesses_with_strips_from_their_own_paths"] == 1
    if report["builder_keeps_door_owned_strokes_out_of_the_strips"]:              # the builder run with the door-ink exclusion
        assert w["first_failing_gate"] == "chord_proposed" and report["chord_count"] == 1
    else:
        assert w["first_failing_gate"] == G2 and report["chord_count"] == 0
        (candidate,) = w["gap_candidates"]
        assert 0.3 < candidate["hi_end_miss_pdf_pts"] < 1.0 and candidate["contains_interval"] is False
        assert report["gate_histogram"] == {G2: 1}


def test_the_tool_prints_no_coordinates():
    report = tool.page_report(_ring_scene(lo=1234.5), page_index=0)
    text = json.dumps(report, sort_keys=True)
    assert "1234" not in text and "1286" not in text                              # neither end of the doorway
    assert "pdf_pts" in text and report["rows"] == len(_ring_scene())


def test_a_page_without_a_proposal_says_why_and_the_proposer_is_restored():
    real = seg.propose_source_owned_doorway_chords
    report = tool.page_report([], page_index=0)
    assert report["proposal_called"] is False and report["witness_count"] == 0 and report["witnesses"] == []
    assert report["builder_status"] == "abstained" and report["builder_reason_codes"]
    assert seg.propose_source_owned_doorway_chords is real
    with pytest.raises(ValueError):
        tool.page_report(_ring_scene(), page_index=-1)                            # the builder refuses; the spy must not leak
    assert seg.propose_source_owned_doorway_chords is real


def test_summary_only_drops_the_witness_records_but_keeps_the_counts():
    detailed = tool.page_report(_ring_scene(), page_index=0)
    summary = tool.page_report(_ring_scene(), page_index=0, detail=False)
    assert summary["witnesses"] == [] and summary["witness_count"] == detailed["witness_count"]
    assert summary["gate_histogram"] == detailed["gate_histogram"]


def _write_pdf(path, rows):
    document = fitz.open()
    page = document.new_page(width=2000, height=600)
    for row in rows:
        a, b = row["items"][0][1], row["items"][0][2]
        shape = page.new_shape()
        shape.draw_line(a, b)
        shape.finish(color=BLACK, width=0.5, closePath=False)                # one open line per path, as a CAD export writes it
        shape.commit()
    document.save(str(path))
    document.close()


def test_the_command_line_reads_a_pdf_and_writes_a_counts_only_report(tmp_path):
    pdf, out = tmp_path / "scene.pdf", tmp_path / "report.json"
    _write_pdf(pdf, _ring_scene())
    assert tool.main(["--pdf", str(pdf), "--page-index", "0", "--json-out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["totals"]["pages"] == 1 and report["totals"]["witnesses"] == 1 and report["totals"]["pages_with_a_proposal"] == 1
    assert len(report["source_sha256_prefix"]) == 16 and report["pages"][0]["page_index"] == 0
    assert sum(report["totals"]["gate_histogram"].values()) == 1
    assert "1234" not in out.read_text(encoding="utf-8") and "1286" not in out.read_text(encoding="utf-8")
    assert tool.main(["--pdf", str(pdf), "--all-pages", "--summary-only", "--json-out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pages"][0]["witnesses"] == []


def test_the_command_line_needs_exactly_one_way_to_name_pages(tmp_path):
    pdf = tmp_path / "scene.pdf"
    _write_pdf(pdf, _ring_scene())
    with pytest.raises(SystemExit):
        tool.main(["--pdf", str(pdf)])
    with pytest.raises(SystemExit):
        tool.main(["--pdf", str(pdf), "--page-index", "0", "--all-pages"])
    with pytest.raises(ValueError):
        tool.main(["--pdf", str(pdf), "--page-index", "5"])


def _strip(x0, y0, x1, y1, ids):
    return layered._Strip(path_index=ids[0], x0=x0, y0=y0, x1=x1, y1=y1, path_indices=tuple(ids))


def test_strip_attribution_reports_reach_thickness_and_wall_line_cover():
    receipt = {"axis": "horizontal", "door_interval_pdf_pts": (100.0, 152.0), "wall_line_perp_pdf_pts": 43.0}
    witness = {"native_source_path_indices": (7, 8, 9)}
    strips = {
        "merged_collinear_face": [
            _strip(151.4, 40.0, 152.6, 95.0, (9, 12)),     # a thin strip standing across the doorway at its hinge end
            _strip(160.0, 40.0, 161.2, 95.0, (8,)),        # wholly beyond the far end
            _strip(100.0, 43.17, 130.0, 44.37, (7,)),      # along the axis, its lower edge 0.17 pt above the wall line: still covers it
            _strip(100.0, 43.2, 130.0, 44.4, (7,)),        # 0.2 pt above: does not
            _strip(100.0, 10.0, 130.0, 11.2, (99,)),       # owns none of the witness's paths
        ],
        "stroke_pair": [_strip(100.0, 42.0, 152.0, 44.0, (9,))],
    }
    got = tool.strip_attribution(strips, witness, receipt)
    assert [(g["collector"], g["owned_paths_in_strip"], g["strip_path_count"], g["thickness_pdf_pts"], g["strip_runs_along_the_door_axis"],
             g["reach_into_door_interval_pdf_pts"], g["covers_the_wall_line"]) for g in got] == [
        ("merged_collinear_face", 1, 2, 1.2, False, 0.6, True),
        ("merged_collinear_face", 1, 1, 1.2, False, 0.0, True),
        ("merged_collinear_face", 1, 1, 1.2, True, 30.0, True),
        ("merged_collinear_face", 1, 1, 1.2, True, 30.0, False),
        ("stroke_pair", 1, 1, 2.0, True, 52.0, True),
    ]
    vertical = {"axis": "vertical", "door_interval_pdf_pts": (100.0, 152.0), "wall_line_perp_pdf_pts": 43.0}
    (v,) = tool.strip_attribution({"stroke_pair": [_strip(40.0, 90.0, 46.0, 170.0, (9,))]}, witness, vertical)
    assert v["reach_into_door_interval_pdf_pts"] == 52.0 and v["covers_the_wall_line"] is True       # extents are read on the door's axis
    unmeasured = {"axis": "ambiguous", "door_interval_pdf_pts": None, "wall_line_perp_pdf_pts": None}
    (u,) = tool.strip_attribution({"stroke_pair": [_strip(0.0, 0.0, 9.0, 1.0, (9,))]}, witness, unmeasured)
    assert u["reach_into_door_interval_pdf_pts"] is None and u["covers_the_wall_line"] is None


def _fake_capture(rows, witnesses, gaps):
    fake = SimpleNamespace(status=SimpleNamespace(value="candidate"), reason_codes=())
    return lambda _rows, **_kw: (fake, (rows, witnesses, gaps))


def test_page_report_labels_a_chord_and_counts_strips_and_agreement(monkeypatch):
    rows = door() + door(lo=700.0, drop=("jamb_right",))                          # the second door has no jamb to merge its leaf with
    witnesses = collect_source_black_segmented_door_swings(rows)
    gaps = (parent(), parent(lo=700.0, hi=752.0))
    monkeypatch.setattr(tool, "capture_proposer_call", _fake_capture(rows, witnesses, gaps))
    report = tool.page_report(rows, page_index=3)
    assert report["page_index"] == 3 and report["proposal_called"] is True and report["raw_gap_count"] == 2
    assert report["witness_count"] == 2 and report["chord_count"] == 1
    assert report["gate_histogram"] == {"chord_proposed": 1, G1: 1}
    assert [w["first_failing_gate"] for w in report["witnesses"]] == ["chord_proposed", G1]
    assert report["witnesses_with_strips_from_their_own_paths"] == 1             # the first leaf merges with its jamb, the second cannot
    assert report["all_receipts_agree_with_the_proposer"] is True
    real = seg.diagnose_source_owned_doorway_chord_gates

    def tampered(*args, **kwargs):
        receipts = [dict(r) for r in real(*args, **kwargs)]
        receipts[1]["agrees_with_proposer"] = False
        return tuple(receipts)

    monkeypatch.setattr(seg, "diagnose_source_owned_doorway_chord_gates", tampered)
    assert tool.page_report(rows, page_index=3)["all_receipts_agree_with_the_proposer"] is False


def _write_two_page_pdf(path, rows):
    document = fitz.open()
    for page_rows in (rows, []):
        page = document.new_page(width=2000, height=600)
        for row in page_rows:
            a, b = row["items"][0][1], row["items"][0][2]
            shape = page.new_shape()
            shape.draw_line(a, b)
            shape.finish(color=BLACK, width=0.5, closePath=False)
            shape.commit()
    document.save(str(path))
    document.close()


def test_the_command_line_counts_pages_with_a_proposal_and_checks_the_page_range(tmp_path):
    pdf, out = tmp_path / "two.pdf", tmp_path / "report.json"
    _write_two_page_pdf(pdf, _ring_scene())
    assert tool.main(["--pdf", str(pdf), "--all-pages", "--json-out", str(out)]) == 0
    totals = json.loads(out.read_text(encoding="utf-8"))["totals"]
    assert totals["pages"] == 2 and totals["pages_with_a_proposal"] == 1 and totals["witnesses"] == 1
    with pytest.raises(ValueError, match="outside the 2 page"):
        tool.main(["--pdf", str(pdf), "--page-index", "2", "--json-out", str(out)])
    assert tool.main(["--pdf", str(pdf), "--page-index", "1", "--json-out", str(out)]) == 0
