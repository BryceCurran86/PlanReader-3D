"""Synthetic tests for aperture-complete closures in the layered doorway ring builder (no private source needed).

One physical opening is often described by several raw wall gaps at once (a wall's body band and its face lines). The builder closes the clear
opening where door evidence exists, but a wall stub between the opening and the wall it meets carries no strip, so the face-line gap that spans the
stub stays unresolved and the room leaks through a slit narrower than the wall is thick. ``aperture_complete_closures`` (default off) closes such
a gap as a ``KIND_APERTURE_MEMBER`` barrier that carries the native paths of the evidence-closed gaps of its own aperture, never anything else.
"""
from __future__ import annotations

import copy
import hashlib
import math
import random

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as module
from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_APERTURE_MEMBER,
    KIND_SLIDING_LEAF,
    KIND_STROKE,
    KIND_SWING,
    LayeredDoorwayClosure,
    _Gap,
    _aperture_complete_evidence,
    build_from_pdf_bytes,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32
WALL = "Enclosure_WallInternal"
K = 0.5522847498
NOISE = 0.05  # the builder's representation-noise constant

BODY = (40.0, 46.0)  # the wall's body band, 6 thick
FACE = (45.0, 46.4)  # a face band 1.4 thick, sticking 0.4 above the body band (a host-wall-thick band)
THIN_FACE = (45.4, 46.4)  # 1.0 thick: lining-thin, so no swing is ever placed on it
SECOND = (44.0, 45.4)  # a second 1.4-thick band of the same wall (the second seed of the two-seed scene)
REACH = 2.0 * (BODY[1] - BODY[0])  # one wall stub (shorter than the wall is thick) plus the thickness of the wall it meets
OPENING = (10.6, 58.0)  # the clear opening of the doorway on the body band


def identity(x: float, y: float) -> tuple[float, float]:
    return x, y


def _pt(tf, x, y):
    return fitz.Point(*tf(x, y))


def strip(x0, y0, x1, y1, tf=identity, layer=WALL, split=None):
    """A filled black strip as a closed four-line path (so any rigid transform stays valid)."""
    rows = []
    pieces = [(x0, y0, x1, y1)]
    if split is not None:
        if x1 - x0 >= y1 - y0:
            pieces = [(x0, y0, split, y1), (split, y0, x1, y1)]
        else:
            pieces = [(x0, y0, x1, split), (x0, split, x1, y1)]
    for ax, ay, bx, by in pieces:
        c = [(ax, ay), (bx, ay), (bx, by), (ax, by)]
        items = [("l", _pt(tf, *c[i]), _pt(tf, *c[(i + 1) % 4])) for i in range(4)]
        rows.append({"layer": layer, "fill": (0.0, 0.0, 0.0), "items": items})
    return rows


def line(a, b, tf=identity, layer=WALL):
    return {"layer": layer, "fill": None, "items": [("l", _pt(tf, *a), _pt(tf, *b))]}


def swing(centre, open_tip, closed_tip, tf=identity, layer=WALL):
    (cx, cy), (ox, oy), (tx, ty) = centre, open_tip, closed_tip
    p2 = (ox + K * (tx - cx), oy + K * (ty - cy))
    p3 = (tx + K * (ox - cx), ty + K * (oy - cy))
    arc = {"layer": layer, "fill": None, "items": [("c", _pt(tf, ox, oy), _pt(tf, *p2), _pt(tf, *p3), _pt(tf, tx, ty))]}
    return [arc, line(centre, open_tip, tf, layer)]


def office_analog(
    tf=identity, *, seed="stroke", face=FACE, p_east=4.0, second_opening=False, second_band=False, partition=False, lining=False,
    twin_stroke=False, extra=(),
):
    """A room (x p_east..118, y face top..138) whose south wall W (body band y 40..46) has a doorway on its west part.

    A perpendicular wall P ends at x = ``p_east`` and a jamb line J (x 9.4..10.6) cuts the body band, so the clear opening is x 10.6..58 and the
    wall stub between P and J (x p_east..9.4) carries no strip. A face strip on the east part of W leaves the face-line gap free to span the stub
    as well: that gap is the doorway's twin, wider than the closed opening. ``seed`` is the door evidence on the opening: a stroke spanning it end
    to end, a swing, or None.
    """
    rows = []
    rows += strip(p_east - 4.0, -60, p_east, 140, tf)  # P
    pieces = [(58, 122)] if not second_opening else [(58, 68), (90, 122)]  # a second opening x 68..90, 10 pt past the doorway
    for a, b in pieces:
        rows += strip(a, BODY[0], b, BODY[1], tf)
        rows += strip(a, face[0], b, face[1], tf)
        if second_band:
            rows += strip(a, SECOND[0], b, SECOND[1], tf)
        if lining:
            rows += strip(a, 46.0, b, 47.2, tf)  # a second face line overlapping only the twin's band
    rows += strip(9.4, -10, 10.6, 46.2, tf)  # J: fully cuts the body band, not the face band
    rows += strip(118, 46, 122, 140, tf)
    rows += strip(p_east - 4.0, 138, 122, 142, tf)
    if seed == "stroke":
        rows.append(line((OPENING[0], 43.0), (OPENING[1], 43.0), tf))
    elif seed == "swing":
        rows += swing((OPENING[0], 46), (OPENING[0], 46 + 47.4), (OPENING[1], 46), tf)
    if partition:
        rows += strip(p_east, 90, 20, 94, tf) + strip(50, 90, 118, 94, tf)  # an open interior partition on another band
    if twin_stroke:
        rows.append(line((p_east, 45.8), (58, 45.8), tf))  # one stroke spanning the twin end to end
    rows += list(extra)
    return rows


def closed_room(tf=identity, *, window=False):
    """A 100 x 100 room with a swing door in its right wall (and optionally a window with a spanning stroke in its bottom wall)."""
    rows = strip(0, 0, 100, 2, tf) + strip(0, 2, 2, 98, tf)
    if window:
        rows += strip(0, 98, 30, 100, tf) + strip(60, 98, 100, 100, tf)
        rows.append(line((30, 98), (60, 98), tf))
    else:
        rows += strip(0, 98, 100, 100, tf)
    rows += strip(98, 2, 100, 40, tf) + strip(98, 64, 100, 98, tf)
    rows += swing((98, 40), (74, 40), (98, 64), tf)
    return rows


def build(rows, *, on, **flags):
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, aperture_complete_closures=on, **flags)


def candidates(result):
    return [r for r in result.rings if r.status is EvidenceResolutionStatus.CANDIDATE]


def _r(values):
    return tuple(round(v, 4) for v in values)


def _closure_view(result):
    return sorted((c.kind, _r(c.band), _r(c.gap_interval)) for c in result.closures)


def _signature(result):
    return (
        sorted((_r(r.bbox_pdf_pts), r.status.value, round(r.area_pt2, 2)) for r in result.rings),
        _closure_view(result),
        result.unresolved_gap_count,
    )


def _closure(kind=KIND_SWING, band=BODY, interval=OPENING, native=(1, 2), horizontal=True):
    return LayeredDoorwayClosure(
        closure_id="c", kind=kind, horizontal=horizontal, band=band, gap_interval=interval, native_path_indices=native, wall_path_indices=(),
    )


def _seed(kind=KIND_SWING, band=BODY, interval=OPENING, native=(1, 2), horizontal=True):
    gap = _Gap(horizontal, band, interval[0], interval[1], (), ())
    return gap, _closure(kind, band, interval, native, horizontal)


def _twin(lo=4.0, hi=58.0, band=FACE, horizontal=True, collinear=False):
    return _Gap(horizontal, band, lo, hi, (), (), collinear)


# ------------------------------------------------------------------------------------------------ the scene as the builder sees it

def test_without_the_keyword_the_doorway_stays_closed_but_the_room_leaks_through_the_wall_stub():
    off = build(office_analog(), on=False)
    assert _closure_view(off) == [(KIND_STROKE, _r(BODY), _r(OPENING))]
    assert off.rings == () and off.status is EvidenceResolutionStatus.ABSTAINED
    # the default is the keyword off
    assert build_layered_wall_doorway_room_rings(office_analog(), source_sha256=SHA, page_index=0) == off


def test_with_the_keyword_the_twin_gap_is_closed_as_an_aperture_member_and_the_room_gets_its_ring():
    on = build(office_analog(), on=True)
    assert on.status is EvidenceResolutionStatus.CANDIDATE
    ring = candidates(on)
    assert len(on.rings) == 1 and len(ring) == 1
    assert ring[0].bbox_pdf_pts == (4.0, 46.4, 118.0, 138.0)
    assert math.isclose(ring[0].area_pt2, 114.0 * 91.6, rel_tol=1e-9)
    assert _closure_view(on) == sorted([(KIND_STROKE, _r(BODY), _r(OPENING)), (KIND_APERTURE_MEMBER, _r(FACE), (4.0, 58.0))])
    seed, member = sorted(on.closures, key=lambda c: c.band)
    # the member is a barrier of its own kind (never a doorway chord) that carries the seed's native paths
    assert member.kind == KIND_APERTURE_MEMBER and seed.kind == KIND_STROKE
    assert member.native_path_indices == seed.native_path_indices and member.closure_id != seed.closure_id
    # the ring can say which closure it relied on: its south edge is the member, not the seed (which the face line covers)
    assert ring[0].bounding_closure_ids == (member.closure_id,)
    assert ring[0].takeoff_eligible is False and ring[0].commercial_projection_allowed is False
    assert ring[0].physical_room_identity_issued is False and ring[0].metric_area_issued is False


def test_the_seed_evidence_may_also_be_a_swing_and_the_twin_may_be_lining_thin():
    rows = office_analog(seed="swing", face=THIN_FACE)
    off, on = build(rows, on=False), build(rows, on=True)
    assert [c.kind for c in off.closures] == [KIND_SWING] and off.rings == ()
    assert sorted(c.kind for c in on.closures) == sorted([KIND_SWING, KIND_APERTURE_MEMBER]) and len(candidates(on)) == 1
    assert len({c.native_path_indices for c in on.closures}) == 1


def test_a_twin_inherits_the_paths_of_every_seed_of_its_aperture_and_chooses_none(monkeypatch):
    # two closed gaps of one aperture with different evidence (as a swing and a jamb stroke can be): both qualify, so both are carried
    def two_strokes(drawings, gap, *, all_ink=False):
        if gap.band == BODY:
            return (9001,)
        if gap.band == SECOND:
            return (9002,)
        return None

    monkeypatch.setattr(module, "_stroke_closed", two_strokes)
    rows = office_analog(seed=None, p_east=8.0, second_band=True)
    off, on = build(rows, on=False), build(rows, on=True)
    assert sorted(c.native_path_indices for c in off.closures) == [(9001,), (9002,)] and off.rings == ()
    member = [c for c in on.closures if c.kind == KIND_APERTURE_MEMBER]
    assert len(on.closures) == 3 and len(member) == 1 and member[0].native_path_indices == (9001, 9002)
    assert len(candidates(on)) == 1


def test_a_twin_the_builder_already_closes_by_its_own_stroke_needs_nothing_from_the_keyword():
    rows = office_analog(twin_stroke=True)
    off, on = build(rows, on=False), build(rows, on=True)
    assert len(candidates(off)) == 1 and [c.kind for c in off.closures] == [KIND_STROKE, KIND_STROKE]
    assert on == off


def test_closures_are_stable_across_replays_and_inputs_are_not_mutated():
    rows = office_analog()
    frozen = copy.deepcopy(rows)
    first, second = build(rows, on=True), build(rows, on=True)
    assert first == second and [r.record_id for r in first.rings] == [r.record_id for r in second.rings]
    assert [c.closure_id for c in first.closures] == [c.closure_id for c in second.closures]
    assert rows == frozen


# ------------------------------------------------------------------------------------------------ look-alikes that must not be completed

def test_without_door_evidence_nothing_is_inherited():
    rows = office_analog(seed=None)
    on = build(rows, on=True)
    assert on.closures == () and on.rings == () and on == build(rows, on=False)


def test_a_twin_beyond_the_widened_interval_stays_open_and_the_room_still_leaks():
    # P ends 12.4 pt west of the opening's start: more than one stub plus the wall it meets (two band thicknesses)
    rows = office_analog(p_east=OPENING[0] - REACH - 0.4)
    on = build(rows, on=True)
    assert len(on.closures) == 1 and on.rings == ()
    assert on == build(rows, on=False)


@pytest.mark.parametrize("excess,completes", [(-0.6, True), (0.0, True), (0.04, True), (0.07, False), (0.6, False)])
def test_the_widening_is_two_band_thicknesses_within_representation_noise(excess, completes):
    rows = office_analog(p_east=OPENING[0] - REACH - excess)
    on = build(rows, on=True)
    assert (len(candidates(on)) == 1) is completes
    assert len(on.closures) == (2 if completes else 1)


@pytest.mark.parametrize("top,completes", [(51.0, True), (51.04, True), (51.07, False), (52.0, False)])
def test_a_gap_thicker_than_the_closed_band_is_a_different_structure_and_stays_open(top, completes):
    # the body band is 6 thick: a twin band of up to 6 (plus noise) is a line of the same wall, a thicker one is not
    rows = office_analog(face=(45.0, top))
    on = build(rows, on=True)
    assert (len(candidates(on)) == 1) is completes
    assert len(on.closures) == (2 if completes else 1)


def test_a_second_opening_beside_the_doorway_is_a_second_aperture_not_the_same_one():
    # an opening with no evidence starts 10 pt past the doorway (inside the widened reach) but shares no interval with it
    rows = office_analog(second_opening=True)
    on, off = build(rows, on=True), build(rows, on=False)
    assert len(on.closures) == 2 and len(off.closures) == 1
    assert on.unresolved_gap_count == off.unresolved_gap_count == 2  # the second opening's body and face gaps stay open
    assert candidates(on) == []  # the room still leaks through the second opening


def test_a_gap_on_another_band_that_only_shares_an_interval_is_not_the_same_aperture():
    rows = office_analog(partition=True)  # an open partition gap, x 20..50, on band y 90..94: inside the doorway's interval, far from its band
    on, off = build(rows, on=True), build(rows, on=False)
    assert on.unresolved_gap_count == off.unresolved_gap_count == 1
    assert len(on.closures) == 2 and len(off.closures) == 1


def test_a_member_is_not_itself_a_seed_for_a_further_gap():
    # a lining band overlaps the twin's band only: it must not be completed through the twin
    rows = office_analog(lining=True)
    on = build(rows, on=True)
    assert len(on.closures) == 2
    ring = candidates(on)
    assert len(ring) == 1 and ring[0].bbox_pdf_pts[1] == 46.4


def test_a_gap_that_already_carries_competing_evidence_is_left_unresolved(monkeypatch):
    # the twin is spanned end to end by a stroke AND claims a sliding closure: two doorway claims, none chosen, even with a seed beside it
    def sliding_for_the_twin(drawings, gap):
        return (9999,) if gap.band == FACE else None

    monkeypatch.setattr(module, "_sliding_leaf_evidence", sliding_for_the_twin)
    rows = office_analog(twin_stroke=True)
    off = build(rows, on=False, sliding_leaf_frame_closure=True)
    on = build(rows, on=True, sliding_leaf_frame_closure=True)
    assert [c.kind for c in off.closures] == [KIND_STROKE] and off.rings == ()
    assert on == off and KIND_SLIDING_LEAF not in {c.kind for c in on.closures}


def test_nothing_changes_where_there_is_nothing_to_complete():
    for rows in (closed_room(), closed_room(window=True), office_analog(twin_stroke=True), office_analog(seed=None)):
        assert build(rows, on=True) == build(rows, on=False)
    result = build(closed_room(window=True), on=True)
    assert len(candidates(result)) == 1 and sorted(c.kind for c in result.closures) == sorted([KIND_SWING, KIND_STROKE])


# ------------------------------------------------------------------------------------------------ the rule itself

def test_helper_returns_the_sorted_native_paths_of_the_qualifying_seed():
    assert _aperture_complete_evidence(_twin(), [_seed(native=(9, 3, 5))]) == (3, 5, 9)
    assert _aperture_complete_evidence(_twin(), []) is None
    assert _aperture_complete_evidence(_twin(), [_seed(native=())]) is None  # a seed without a native path gives nothing to carry


def test_helper_keeps_every_qualifying_seed_whatever_its_kind_and_chooses_none():
    a = _seed(native=(2, 1))
    b = _seed(native=(4,), kind=KIND_STROKE, band=(40.5, 45.5))
    assert _aperture_complete_evidence(_twin(), [a, b]) == (1, 2, 4)
    assert _aperture_complete_evidence(_twin(), [b, a]) == (1, 2, 4)
    # the same native paths twice are one set; a sliding-leaf seed is a seed like any other
    assert _aperture_complete_evidence(_twin(), [a, _seed(kind=KIND_STROKE, native=(1, 2))]) == (1, 2)
    assert _aperture_complete_evidence(_twin(), [_seed(kind=KIND_SLIDING_LEAF, native=(6, 7))]) == (6, 7)


def test_helper_ignores_a_seed_that_does_not_qualify():
    near = _seed(native=(1, 2))
    far = _seed(kind=KIND_STROKE, native=(7,), interval=(300.0, 340.0))  # another doorway: not this aperture
    assert _aperture_complete_evidence(_twin(), [far, near]) == (1, 2)
    assert _aperture_complete_evidence(_twin(), [near, far]) == (1, 2)
    assert _aperture_complete_evidence(_twin(), [far]) is None


def test_helper_needs_the_same_orientation():
    assert _aperture_complete_evidence(_twin(horizontal=False), [_seed()]) is None
    assert _aperture_complete_evidence(_twin(horizontal=False), [_seed(horizontal=False)]) is not None


@pytest.mark.parametrize("band,found", [
    ((46.0, 47.2), False),            # touching only: no overlap
    ((46.0 - 0.03, 47.2), False),     # an overlap under the representation noise is none
    ((46.0 - 0.07, 47.2), True),      # more than the noise
    ((20.0, 30.0), False),            # a different wall line
    ((41.0, 45.0), True),             # inside the body band
])
def test_helper_needs_the_bands_to_overlap_by_more_than_the_noise(band, found):
    assert (_aperture_complete_evidence(_twin(band=band), [_seed()]) is not None) is found


@pytest.mark.parametrize("lo,hi,found", [
    (58.0, 65.0, False),              # touching only (and inside the reach, so only the overlap rule can refuse it)
    (58.0 - 0.03, 65.0, False),       # under the noise
    (58.0 - 0.07, 65.0, True),        # more than the noise
    (58.5, 66.0, False),              # disjoint
    (20.0, 30.0, True),               # inside the opening
])
def test_helper_needs_the_intervals_to_overlap_by_more_than_the_noise(lo, hi, found):
    assert (_aperture_complete_evidence(_twin(lo=lo, hi=hi), [_seed()]) is not None) is found


def test_helper_overlaps_of_exactly_the_noise_are_no_overlap():
    seed = _seed(band=(-6.0, 0.0), interval=(-48.0, 0.0))  # exact binary-friendly numbers: the overlaps below are exactly 0.05
    assert _aperture_complete_evidence(_twin(lo=-5.0, hi=5.0, band=(-NOISE, 1.2)), [seed]) is None
    assert _aperture_complete_evidence(_twin(lo=-5.0, hi=5.0, band=(-NOISE - 0.01, 1.2)), [seed]) is not None
    assert _aperture_complete_evidence(_twin(lo=-NOISE, hi=5.0, band=(-1.0, 1.2)), [seed]) is None
    assert _aperture_complete_evidence(_twin(lo=-NOISE - 0.01, hi=5.0, band=(-1.0, 1.2)), [seed]) is not None


@pytest.mark.parametrize("lo,hi,found", [
    (OPENING[0] - REACH, OPENING[1] + REACH, True),
    (OPENING[0] - REACH - 0.04, OPENING[1] + REACH + 0.04, True),
    (OPENING[0] - REACH - 0.07, OPENING[1], False),
    (OPENING[0], OPENING[1] + REACH + 0.07, False),
    (OPENING[0] - 3 * REACH, OPENING[1], False),
])
def test_helper_widens_each_end_by_two_of_the_seed_band_thicknesses(lo, hi, found):
    assert (_aperture_complete_evidence(_twin(lo=lo, hi=hi), [_seed()]) is not None) is found


def test_helper_widening_is_inclusive_at_exactly_the_reach_plus_the_noise():
    assert _aperture_complete_evidence(_twin(lo=OPENING[0] - REACH - NOISE, hi=OPENING[1]), [_seed()]) is not None
    assert _aperture_complete_evidence(_twin(lo=OPENING[0], hi=OPENING[1] + REACH + NOISE), [_seed()]) is not None


def test_helper_widens_by_the_seeds_own_thickness_not_the_twins():
    thin = _seed(band=(40.0, 43.0), interval=(10.0, 50.0))  # 3 thick: reach 6
    assert _aperture_complete_evidence(_twin(lo=4.1, hi=50.0, band=(41.0, 44.0)), [thin]) is not None
    assert _aperture_complete_evidence(_twin(lo=3.9, hi=50.0, band=(41.0, 44.0)), [thin]) is None
    thick = _seed(band=(40.0, 52.0), interval=(10.0, 50.0))  # 12 thick: reach 24
    assert _aperture_complete_evidence(_twin(lo=-13.9, hi=50.0, band=(41.0, 44.0)), [thick]) is not None
    assert _aperture_complete_evidence(_twin(lo=-14.1, hi=50.0, band=(41.0, 44.0)), [thick]) is None


@pytest.mark.parametrize("top,found", [(51.0, True), (51.04, True), (51.07, False), (60.0, False), (46.4, True)])
def test_helper_refuses_a_gap_thicker_than_the_seed_band(top, found):
    assert (_aperture_complete_evidence(_twin(band=(45.0, top)), [_seed()]) is not None) is found


def test_helper_thickness_limit_is_inclusive_at_exactly_the_seed_band_plus_the_noise():
    seed = _seed(band=(0.0, 6.0), interval=(10.0, 50.0))
    assert _aperture_complete_evidence(_twin(lo=10.0, hi=50.0, band=(1.0, 1.0 + 6.0 + NOISE)), [seed]) is not None
    assert _aperture_complete_evidence(_twin(lo=10.0, hi=50.0, band=(1.0, 1.0 + 6.0 + NOISE + 0.02)), [seed]) is None


def test_helper_judges_the_thickness_against_each_seed_separately():
    thin = _seed(native=(8,), band=(44.0, 45.4))  # a twin as thick as 1.4 qualifies against a 1.4 seed ...
    wide = _seed(native=(1, 2))  # ... and against the 6 thick body band
    narrow = _seed(native=(3,), band=(44.5, 45.5))  # ... but not against a 1.0 thick one
    assert _aperture_complete_evidence(_twin(lo=9.0), [thin, wide, narrow]) == (1, 2, 8)


# ------------------------------------------------------------------------------------------------ geometry-preserving invariances

TRANSFORMS = [
    ("translation", lambda x, y: (x + 317.25, y - 88.5), 1.0),
    ("rotation90", lambda x, y: (-y + 500.0, x + 40.0), 1.0),
    ("rotation270", lambda x, y: (y + 10.0, -x + 300.0), 1.0),
    ("reflection", lambda x, y: (-x + 400.0, y), 1.0),
    ("scale2", lambda x, y: (2 * x, 2 * y), 2.0),
]


@pytest.mark.parametrize("name,tf,scale", TRANSFORMS)
def test_rigid_and_uniform_scale_transforms_preserve_the_completion(name, tf, scale):
    base = build(office_analog(), on=True)
    moved = build(office_analog(tf), on=True)
    assert [r.status for r in moved.rings] == [r.status for r in base.rings] == [EvidenceResolutionStatus.CANDIDATE]
    assert sorted(c.kind for c in moved.closures) == sorted(c.kind for c in base.closures)
    assert math.isclose(moved.rings[0].area_pt2 / (scale * scale), base.rings[0].area_pt2, rel_tol=1e-9)
    assert build(office_analog(tf), on=False).rings == ()


def test_input_order_does_not_change_the_result():
    rows = office_analog()
    reference = _signature(build(rows, on=True))
    assert _signature(build(list(reversed(rows)), on=True)) == reference
    rng = random.Random(20261125)
    for _ in range(6):
        shuffled = list(rows)
        rng.shuffle(shuffled)
        assert _signature(build(shuffled, on=True)) == reference


def test_splitting_wall_strips_does_not_change_the_result():
    base = build(office_analog(), on=True)
    split = (
        strip(0, -60, 4, 140, split=30.0) + strip(58, 40, 122, 46, split=90.0) + strip(58, 45.0, 122, 46.4, split=75.0)
        + strip(9.4, -10, 10.6, 46.2, split=20.0) + strip(118, 46, 122, 140, split=100.0) + strip(0, 138, 122, 142, split=60.0)
        + [line((OPENING[0], 43.0), (OPENING[1], 43.0))]
    )
    assert len(split) == len(office_analog()) + 6
    assert _signature(build(split, on=True)) == _signature(base)


def test_unrelated_far_content_and_a_larger_frame_do_not_change_the_room():
    base = build(office_analog(), on=True)
    far = strip(1000, 1000, 1100, 1002) + strip(1000, 1098, 1100, 1100) + strip(1000, 1002, 1002, 1098)
    frame = strip(-500, -500, 1500, -496) + strip(-500, 1496, 1500, 1500) + strip(-500, -496, -496, 1496) + strip(1496, -496, 1500, 1496)
    noisy = build(office_analog(extra=far + frame), on=True)
    assert [r.bbox_pdf_pts for r in candidates(noisy) if r.bbox_pdf_pts == base.rings[0].bbox_pdf_pts] == [base.rings[0].bbox_pdf_pts]
    assert [c.kind for c in noisy.closures] == [c.kind for c in base.closures]


def test_the_completion_also_works_on_the_dark_painted_source_path():
    rows = office_analog()
    off = build(rows, on=False, dark_painted_wall_source=True)
    on = build(rows, on=True, dark_painted_wall_source=True)
    assert candidates(off) == [] and len(candidates(on)) == 1
    assert len(on.closures) == len(off.closures) + 1


# ------------------------------------------------------------------------------------------------ the keyword itself

@pytest.mark.parametrize("value", [1, 0, "yes", None, 1.0, [True]])
def test_the_keyword_must_be_an_explicit_boolean(value):
    with pytest.raises(ValueError, match="aperture_complete_closures"):
        build_layered_wall_doorway_room_rings(office_analog(), source_sha256=SHA, page_index=0, aperture_complete_closures=value)


def test_the_new_kind_is_exported_and_distinct():
    assert KIND_APERTURE_MEMBER == "aperture_member_closure"
    assert "KIND_APERTURE_MEMBER" in module.__all__
    assert len({KIND_APERTURE_MEMBER, KIND_STROKE, KIND_SWING, KIND_SLIDING_LEAF}) == 4


@pytest.mark.parametrize("flag", [True, False])
def test_the_pdf_bytes_entry_point_forwards_the_keyword_and_defaults_it_off(monkeypatch, flag):
    document = fitz.open()
    document.new_page(width=300, height=300)
    data = document.tobytes()
    document.close()
    sha = hashlib.sha256(data).hexdigest()
    seen = []

    def recorder(drawings, **kwargs):
        seen.append(kwargs)
        return "sentinel"

    monkeypatch.setattr(module, "build_layered_wall_doorway_room_rings", recorder)
    assert build_from_pdf_bytes(data, source_sha256=sha, page_index=0, aperture_complete_closures=flag) == "sentinel"
    assert seen[-1]["aperture_complete_closures"] is flag
    assert build_from_pdf_bytes(data, source_sha256=sha, page_index=0) == "sentinel"
    assert seen[-1]["aperture_complete_closures"] is False
