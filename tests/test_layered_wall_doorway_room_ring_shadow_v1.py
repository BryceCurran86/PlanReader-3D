"""Synthetic tests for the doorway-closed room ring shadow (no private source needed)."""
from __future__ import annotations

import copy
import hashlib
import math

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_STROKE,
    KIND_SLIDING_LEAF,
    KIND_SWING,
    LayeredRoomRingRecord,
    REASON_OPEN_EXTERIOR,
    REASON_RING_CLOSED,
    build_from_pdf_bytes,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_boundary_doorway_opening_shadow import (
    SourceRoomDoorwayOpeningSelector,
    SourceRoomOpeningCandidate,
    SourceRoomWallEdge,
    evaluate_source_room_boundary_doorway_shadow,
)

SHA = "ab" * 32
WALL = "Enclosure_WallInternal"
K = 0.5522847498


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


def swing(centre, open_tip, closed_tip, tf=identity, layer=WALL, with_leaf=True, circular=True):
    (cx, cy), (ox, oy), (tx, ty) = centre, open_tip, closed_tip
    # controls hug the corner of the bounding square that is opposite the centre
    p2 = (ox + K * (tx - cx), oy + K * (ty - cy))
    p3 = (tx + K * (ox - cx), ty + K * (oy - cy))
    if not circular:
        p2 = (p2[0] + 3.0, p2[1] - 3.0)
        p3 = (p3[0] + 3.0, p3[1] - 3.0)
    arc = {"layer": layer, "fill": None,
           "items": [("c", _pt(tf, ox, oy), _pt(tf, *p2), _pt(tf, *p3), _pt(tf, tx, ty))]}
    rows = [arc]
    if with_leaf:
        rows.append(line(centre, open_tip, tf, layer))
    return rows


def room(tf=identity, *, door=True, window=False, layer=WALL, split_top=None, extra=()):
    """A 100 x 100 room, 2 thick walls. Right wall has a 24 wide swing door; bottom may have a window."""
    rows = []
    rows += strip(0, 0, 100, 2, tf, layer, split_top)
    left = strip(0, 2, 2, 98, tf, layer)
    rows += left
    if window:
        rows += strip(0, 98, 30, 100, tf, layer) + strip(60, 98, 100, 100, tf, layer)
        rows.append(line((30, 98), (60, 98), tf, layer))
    else:
        rows += strip(0, 98, 100, 100, tf, layer)
    if door:
        rows += strip(98, 2, 100, 40, tf, layer) + strip(98, 64, 100, 98, tf, layer)
        rows += swing((98, 40), (74, 40), (98, 64), tf, layer)
    else:
        rows += strip(98, 2, 100, 98, tf, layer)
    rows += list(extra)
    return rows


def candidates(result):
    return [r for r in result.rings if r.status is EvidenceResolutionStatus.CANDIDATE]


def bbox_size(r):
    x0, y0, x1, y1 = r.bbox_pdf_pts
    return round(x1 - x0, 3), round(y1 - y0, 3)


def test_closed_room_with_swing_door_yields_one_candidate_ring_on_the_finished_faces():
    result = build_layered_wall_doorway_room_rings(room(), source_sha256=SHA, page_index=0)
    ring = candidates(result)
    assert len(ring) == 1 and len(result.rings) == 1
    assert ring[0].bbox_pdf_pts == (2.0, 2.0, 98.0, 98.0)
    assert math.isclose(ring[0].area_pt2, 96.0 * 96.0, rel_tol=1e-6)
    assert result.reason_codes == (REASON_RING_CLOSED,)
    assert [c.kind for c in result.closures] == [KIND_SWING]
    assert ring[0].closure_edge_count == 1 and ring[0].bounding_closure_ids == (result.closures[0].closure_id,)
    # the closure is a barrier only: it carries no wall length, host or quantity
    assert ring[0].takeoff_eligible is False and ring[0].commercial_projection_allowed is False
    assert ring[0].physical_room_identity_issued is False and ring[0].metric_area_issued is False


def test_independent_existing_verifier_accepts_every_edge_as_wall_or_doorway_chord():
    result = build_layered_wall_doorway_room_rings(room(), source_sha256=SHA, page_index=0)
    ring = candidates(result)[0]
    walls = []
    for index, (ax, ay, bx, by) in enumerate([(0, 0, 100, 2), (0, 2, 2, 98), (0, 98, 100, 100), (98, 2, 100, 40), (98, 64, 100, 98)]):
        corners = [(ax, ay), (bx, ay), (bx, by), (ax, by)]
        for i in range(4):
            walls.append(SourceRoomWallEdge(f"w{index}", corners[i], corners[(i + 1) % 4]))
    selector = SourceRoomDoorwayOpeningSelector("d", "r", SHA, "s", "1", "room")
    verdict = evaluate_source_room_boundary_doorway_shadow(
        selector, polygon_pdf_pts=ring.polygon_pdf_pts, wall_edges=walls,
        opening_candidates=[SourceRoomOpeningCandidate("door", (98.0, 40.0), (98.0, 64.0))],
    )
    assert verdict.status is EvidenceResolutionStatus.CANDIDATE and verdict.unowned_edge_count == 0
    # and without the doorway chord the same polygon has an unowned edge
    bare = evaluate_source_room_boundary_doorway_shadow(
        selector, polygon_pdf_pts=ring.polygon_pdf_pts, wall_edges=walls, opening_candidates=[])
    assert bare.status is EvidenceResolutionStatus.ABSTAINED


def test_gap_without_any_door_evidence_stays_open():
    result = build_layered_wall_doorway_room_rings(room(door=False)[:0] + _open_gap_room(), source_sha256=SHA, page_index=0)
    assert result.rings == () and result.closures == ()
    assert result.status is EvidenceResolutionStatus.ABSTAINED and result.reason_codes == (REASON_OPEN_EXTERIOR,)


def _open_gap_room(tf=identity):
    rows = strip(0, 0, 100, 2, tf) + strip(0, 2, 2, 98, tf) + strip(0, 98, 100, 100, tf)
    rows += strip(98, 2, 100, 40, tf) + strip(98, 64, 100, 98, tf)  # a gap and no swing, no stroke
    return rows


def test_window_gap_is_closed_only_by_a_source_stroke_that_spans_it_end_to_end():
    closed = build_layered_wall_doorway_room_rings(room(window=True), source_sha256=SHA, page_index=0)
    assert len(candidates(closed)) == 1
    assert sorted(c.kind for c in closed.closures) == sorted([KIND_SWING, KIND_STROKE])
    # a stroke that stops short of one jamb is not a closure
    short = room(window=True)
    short = [r for r in short if r["items"][0][0] != "l" or r["fill"] is not None or r["items"][0][1] != fitz.Point(30, 98)]
    short.append(line((30, 98), (55, 98)))
    open_result = build_layered_wall_doorway_room_rings(short, source_sha256=SHA, page_index=0)
    assert candidates(open_result) == []
    # nor one that starts inside the gap instead of at the other jamb
    other = [r for r in room(window=True) if r["items"][0][0] != "l" or r["fill"] is not None or r["items"][0][1] != fitz.Point(30, 98)]
    other.append(line((35, 98), (60, 98)))
    assert candidates(build_layered_wall_doorway_room_rings(other, source_sha256=SHA, page_index=0)) == []


def test_look_alike_swing_symbols_never_close_a_gap():
    for kwargs in ({"with_leaf": False}, {"circular": False}):
        rows = _open_gap_room() + swing((98, 40), (74, 40), (98, 64), **kwargs)
        result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
        assert candidates(result) == [] and result.closures == ()
    # a complete swing symbol that sits in the middle of the room, away from any wall gap
    floating = room(door=False) + swing((40, 40), (16, 40), (40, 64))
    result = build_layered_wall_doorway_room_rings(floating, source_sha256=SHA, page_index=0)
    assert result.unplaced_swing_count == 1 and result.closures == ()


def test_two_swings_competing_for_one_gap_close_nothing():
    rows = _open_gap_room() + swing((98, 40), (74, 40), (98, 64)) + swing((98, 64), (74, 64), (98, 40))
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert result.ambiguous_swing_count == 2 and result.closures == ()
    assert candidates(result) == []


def test_only_explicit_wall_layers_count():
    result = build_layered_wall_doorway_room_rings(room(layer="Interior_Joinery"), source_sha256=SHA, page_index=0)
    assert result.rings == () and result.wall_strip_count == 0
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    finish = build_layered_wall_doorway_room_rings(room(layer="Finish_WallTiles"), source_sha256=SHA, page_index=0)
    assert finish.wall_strip_count == 0  # a wall FINISH layer is not a wall


def test_hairline_gap_between_wall_pieces_is_a_sliver_not_a_room():
    rows = strip(0, 0, 100, 2) + strip(0, 2.3, 100, 4.3)  # two bands 0.3 apart
    rows += strip(0, 4.3, 2, 98) + strip(98, 4.3, 100, 98) + strip(0, 98, 100, 100)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert result.sliver_region_count >= 1
    assert all(bbox_size(r)[1] > 1.0 for r in result.rings)


def test_jamb_cap_across_a_wall_end_is_part_of_that_wall_not_an_interruption():
    # a 0.28 thick cap drawn across the end of the left wall, as CAD exports do at window jambs
    rows = strip(0, 0, 100, 2) + strip(0, 2, 2, 90) + strip(0, 90, 2, 90.28) + strip(0, 98, 100, 100) + strip(98, 2, 100, 98)
    rows += strip(0, 90.28, 2, 98)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert len(candidates(result)) == 1 and result.unresolved_gap_count == 0


def _signature(result):
    return (
        sorted((tuple(round(v, 2) for v in r.bbox_pdf_pts), r.status.value, len(r.polygon_pdf_pts)) for r in result.rings),
        sorted(c.kind for c in result.closures),
        result.unresolved_gap_count,
    )


def _normalised(result, dx=0.0, dy=0.0, scale=1.0):
    return sorted(round(r.area_pt2 / (scale * scale), 2) for r in result.rings)


@pytest.mark.parametrize("name,tf,scale", [
    ("translation", lambda x, y: (x + 317.25, y - 88.5), 1.0),
    ("rotation90", lambda x, y: (-y + 500.0, x + 40.0), 1.0),
    ("scale2", lambda x, y: (2 * x, 2 * y), 2.0),
])
def test_rigid_and_uniform_scale_transforms_preserve_the_structure(name, tf, scale):
    base = build_layered_wall_doorway_room_rings(room(window=True), source_sha256=SHA, page_index=0)
    moved = build_layered_wall_doorway_room_rings(room(tf, window=True), source_sha256=SHA, page_index=0)
    assert [r.status for r in moved.rings] == [r.status for r in base.rings]
    assert sorted(c.kind for c in moved.closures) == sorted(c.kind for c in base.closures)
    assert _normalised(moved, scale=scale) == _normalised(base)
    assert len(candidates(moved)) == 1


def test_splitting_a_wall_strip_does_not_change_the_ring():
    base = build_layered_wall_doorway_room_rings(room(), source_sha256=SHA, page_index=0)
    split = build_layered_wall_doorway_room_rings(room(split_top=37.0), source_sha256=SHA, page_index=0)
    assert [r.bbox_pdf_pts for r in split.rings] == [r.bbox_pdf_pts for r in base.rings]
    assert _normalised(split) == _normalised(base)


def test_input_order_does_not_change_the_geometry():
    rows = room(window=True)
    forward = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    backward = build_layered_wall_doorway_room_rings(list(reversed(rows)), source_sha256=SHA, page_index=0)
    assert _signature(forward) == _signature(backward)


def test_unrelated_far_content_and_extra_frame_do_not_change_the_room():
    base = build_layered_wall_doorway_room_rings(room(), source_sha256=SHA, page_index=0)
    far = strip(1000, 1000, 1100, 1002) + strip(1000, 1098, 1100, 1100) + strip(1000, 1002, 1002, 1098)
    noisy = build_layered_wall_doorway_room_rings(room(extra=far), source_sha256=SHA, page_index=0)
    assert [r.bbox_pdf_pts for r in noisy.rings if r.status is EvidenceResolutionStatus.CANDIDATE][0] == base.rings[0].bbox_pdf_pts
    assert math.isclose(candidates(noisy)[0].area_pt2, base.rings[0].area_pt2, rel_tol=1e-9)


def test_two_rooms_sharing_a_door_are_two_separate_rings():
    rows = room() + strip(100, 0, 200, 2) + strip(100, 98, 200, 100) + strip(198, 2, 200, 98)
    # the shared wall is the first room's right wall (with its swing door); close the second room's own gaps
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    boxes = sorted(r.bbox_pdf_pts for r in candidates(result))
    assert boxes == [(2.0, 2.0, 98.0, 98.0), (100.0, 2.0, 198.0, 98.0)]


def test_deterministic_replay_and_stable_ids():
    first = build_layered_wall_doorway_room_rings(room(window=True), source_sha256=SHA, page_index=3)
    second = build_layered_wall_doorway_room_rings(room(window=True), source_sha256=SHA, page_index=3)
    assert first == second
    assert [r.record_id for r in first.rings] == [r.record_id for r in second.rings]
    other_page = build_layered_wall_doorway_room_rings(room(window=True), source_sha256=SHA, page_index=4)
    assert other_page.rings[0].record_id != first.rings[0].record_id


def test_inputs_are_not_mutated():
    rows = room(window=True)
    before = copy.deepcopy([(r["layer"], r["fill"], [tuple(map(str, it)) for it in r["items"]]) for r in rows])
    build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    after = [(r["layer"], r["fill"], [tuple(map(str, it)) for it in r["items"]]) for r in rows]
    assert before == after


def test_records_are_producer_owned_and_inputs_are_validated():
    with pytest.raises(TypeError):
        LayeredRoomRingRecord("x", SHA, 0, (), 0, 0.0, (0, 0, 0, 0), 0, 0, (), (), EvidenceResolutionStatus.CANDIDATE, ())
    with pytest.raises(ValueError):
        build_layered_wall_doorway_room_rings(room(), source_sha256="XYZ", page_index=0)
    with pytest.raises(ValueError):
        build_layered_wall_doorway_room_rings(room(), source_sha256=SHA, page_index=-1)


def test_pdf_bytes_entry_point_refuses_a_digest_that_does_not_match_the_bytes():
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(10, 10, 100, 12), color=None, fill=(0, 0, 0))
    data = document.tobytes()
    document.close()
    wrong = build_from_pdf_bytes(data, source_sha256=SHA, page_index=0)
    assert wrong.status is EvidenceResolutionStatus.ABSTAINED and wrong.rings == ()
    right = build_from_pdf_bytes(data, source_sha256=hashlib.sha256(data).hexdigest(), page_index=0)
    assert right.rings == ()  # an unlayered PDF has no explicit wall layer: nothing is claimed


def test_thin_lining_strips_bordering_a_wall_on_one_side_are_not_an_interruption():
    # thin lining pieces at both ends of the bottom face, backed by a continuous wall band below
    rows = strip(0, 0, 100, 2) + strip(0, 2, 2, 98) + strip(98, 2, 100, 98) + strip(0, 98, 100, 100)
    rows += strip(2, 97.72, 30, 98) + strip(70, 97.72, 98, 98)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert len(candidates(result)) == 1 and result.unresolved_gap_count == 0


def test_jamb_caps_at_wall_ends_beside_a_closed_window_do_not_open_the_ring():
    rows = strip(0, 0, 100, 2) + strip(0, 2, 2, 97.72) + strip(0, 97.72, 2, 98)
    rows += strip(98, 2, 100, 40) + strip(98, 64, 100, 97.72) + strip(98, 97.72, 100, 98)
    rows += swing((98, 40), (74, 40), (98, 64))
    rows += strip(0, 98, 30, 100) + strip(60, 98, 100, 100) + [line((30, 98), (60, 98))]
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert len(candidates(result)) == 1 and result.unresolved_gap_count == 0


def test_a_free_standing_return_inside_the_room_does_not_open_it():
    # a short wall return hanging into the room leaves a free band interval beside it; that is
    # not a cut wall, so the ring must stay a candidate and the return is a notch in the polygon
    rows = room() + strip(40, 2, 42, 30)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    ring = candidates(result)
    assert len(ring) == 1 and ring[0].area_pt2 < 96.0 * 96.0
    assert math.isclose(ring[0].area_pt2, 96.0 * 96.0 - 2.0 * 28.0, rel_tol=1e-6)


@pytest.mark.parametrize("tf", [identity, lambda x, y: (-y + 500.0, x + 40.0)], ids=["vertical_gap", "horizontal_gap"])
def test_swing_symbol_wider_than_the_gap_or_off_the_wall_line_closes_nothing(tf):
    too_wide = _open_gap_room(tf) + swing((98, 40), (58, 40), (98, 80), tf)  # closed segment runs past the jamb
    far_from_wall = _open_gap_room(tf) + swing((60, 40), (36, 40), (60, 64), tf)  # same line, 38 away from the wall
    for rows in (too_wide, far_from_wall):
        result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
        assert result.closures == () and result.unplaced_swing_count == 1
        assert candidates(result) == []


def test_a_wall_piece_bridging_part_of_the_band_keeps_the_wall_continuous():
    rows = strip(0, 0, 40, 2) + strip(60, 0, 100, 2) + strip(40, 1, 60, 2)  # a thinner section between two runs
    rows += strip(0, 2, 2, 98) + strip(98, 2, 100, 98) + strip(0, 98, 100, 100)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert len(candidates(result)) == 1 and result.unresolved_gap_count == 0


@pytest.mark.parametrize("seed", [0, 5])
def test_ring_polygons_are_simple_rings_for_downstream_room_area_code(seed):
    # CAD float noise (3e-5 pt) where wall returns and caps meet used to leave repeated vertices
    # (one across the closing edge, one inside the walk), which makes pb_room_area_quantity treat the
    # ring as unusable and every such ring a "duplicate face"
    import random

    from pb_room_area_quantity import _original_pdf_ring

    rnd = random.Random(seed)

    def j():
        return rnd.uniform(-3e-5, 3e-5)

    extra = (strip(40 + j(), 2 + j(), 42 + j(), 30 + j()) + strip(40 + j(), 28 + j(), 44.4 + j(), 30 + j())
             + strip(42 + j(), 10 + j(), 43 + j(), 12 + j()) + strip(41 + j(), 20 + j(), 46 + j(), 22 + j()))
    ring = candidates(build_layered_wall_doorway_room_rings(room() + extra, source_sha256=SHA, page_index=0))[0]
    points = ring.polygon_pdf_pts
    assert all(points[i] != points[(i + 1) % len(points)] for i in range(len(points)))
    assert len(set(points)) == len(points)
    assert _original_pdf_ring(points) is not None


def white_box(x0, y0, x1, y1, tf=identity, layer=WALL, fill=(1.0, 1.0, 1.0)):
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    items = [("l", _pt(tf, *c[i]), _pt(tf, *c[(i + 1) % 4])) for i in range(4)]
    return {"layer": layer, "fill": fill, "items": items}


def robe_room(tf=identity, *, frame_lo=True, frame_hi=True, leaves=2, leaf_layer=WALL, leaf2_start=70.0,
              leaf1_end=71.0, leaf_perp=30.2, extra=(), occlude=False, leaf1_start=45.5, leaf2_end=92.9,
              frame_fill=(1.0, 1.0, 1.0), duplicate_frame=False, second_frame_source=False):
    """The 100 x 100 room plus a wall return (stub) hanging from the top wall and a wardrobe front: two end
    blocks on a band y 28..30 with a 49.6 wide opening (x 44.4..94) holding a frame box at each end and two
    overlapping sliding leaves between them."""
    rows = room(tf) + strip(40, 2, 42, 30, tf) + strip(40, 28, 44.4, 30, tf) + strip(94, 28, 98, 30, tf)
    if frame_lo:
        rows.append(white_box(44.4, 27.72, 45.5, 30.28, tf, fill=frame_fill))
    if frame_hi:
        rows.append(white_box(92.9, 27.72, 94.0, 30.28, tf, fill=frame_fill))
    if duplicate_frame:
        rows.append(white_box(92.9, 27.72, 94.0, 30.28, tf, fill=frame_fill))
    if second_frame_source:
        # a second, narrower frame box ending at the same jamb: two sources for one end, and it hides nothing
        rows.append(white_box(93.8, 27.72, 94.0, 30.28, tf, fill=frame_fill))
    if leaves >= 1:
        rows.append(line((leaf1_start, 28.0), (leaf1_end, 28.0), tf, leaf_layer))
    if leaves >= 2:
        rows.append(line((leaf2_start, leaf_perp), (leaf2_end, leaf_perp), tf, leaf_layer))
    if leaves >= 3:
        rows.append(line((60.0, 28.1), (80.0, 28.1), tf, leaf_layer))  # a third stroke: not the sliding pair
    rows += list(extra)
    if occlude:
        rows.append(white_box(55.0, 27.0, 60.0, 31.0, tf, "Finish_Floor"))  # painted later, hides leaf one
    return rows


def sliding(rows, **kw):
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, sliding_leaf_frame_closure=True, **kw)


def test_two_frames_and_two_overlapping_leaves_close_the_opening_only_under_their_own_control_and_split_the_alcove():
    on = sliding(robe_room())
    assert sorted(c.kind for c in on.closures) == sorted([KIND_SWING, KIND_SLIDING_LEAF])
    assert sorted(r.bbox_pdf_pts for r in candidates(on)) == [(2.0, 2.0, 98.0, 98.0), (42.0, 2.0, 98.0, 28.0)]
    assert on.unresolved_gap_count == 0
    off = build_layered_wall_doorway_room_rings(robe_room(), source_sha256=SHA, page_index=0)
    assert KIND_SLIDING_LEAF not in {c.kind for c in off.closures} and candidates(off) == []
    with pytest.raises(ValueError):
        build_layered_wall_doorway_room_rings(robe_room(), source_sha256=SHA, page_index=0, sliding_leaf_frame_closure=1)


@pytest.mark.parametrize("defect", [
    {"frame_lo": False},               # a frame is missing
    {"frame_hi": False},
    {"leaves": 1},                     # a leaf is missing
    {"leaves": 3},                     # an extra stroke: one-to-many, not the pair
    {"leaf2_start": 71.5},             # a hole between the leaves (shifted leaf)
    {"leaf1_end": 70.0},               # the leaves touch but do not overlap
    {"leaf_layer": "Interior_Joinery"},  # wrong layer
    {"leaf_perp": 33.0},               # farther than one wall thickness from the band
    {"occlude": True},                 # painted over by a later opaque fill
    {"leaf1_start": 47.0},             # the first leaf stops short of its frame
    {"leaf2_end": 90.0},               # the second leaf stops short of its frame
    {"duplicate_frame": True},         # a frame drawn twice: not one frame source
    {"second_frame_source": True},     # two frame sources at one end, neither hiding the other
    {"frame_fill": (0.5, 0.5, 0.5)},   # not a white frame box
])
def test_every_defect_in_the_sliding_leaf_evidence_abstains(defect):
    result = sliding(robe_room(**defect))
    assert KIND_SLIDING_LEAF not in {c.kind for c in result.closures}
    assert candidates(result) == []  # the interruption stays open, so no ring closes


def test_a_duplicated_leaf_or_a_competing_doorway_in_the_same_interruption_abstains():
    duplicate_leaf = robe_room(extra=[line((70.0, 30.2), (92.9, 30.2))])  # the second leaf drawn twice
    assert KIND_SLIDING_LEAF not in {c.kind for c in sliding(duplicate_leaf).closures}
    # a swing doorway whose closed-door segment lies in the same interruption: two doorway claims, none chosen
    competing = robe_room(extra=swing((46.0, 29.0), (46.0, 5.0), (70.0, 29.0)))
    result = sliding(competing)
    assert KIND_SLIDING_LEAF not in {c.kind for c in result.closures}
    assert [c.kind for c in result.closures] == [KIND_SWING]  # only the room's own door stays closed
    assert candidates(result) == []


def test_one_stroke_cannot_evidence_two_openings():
    def wall_and_frames(shared):
        rows = strip(40, 28, 44.4, 30) + strip(74, 28, 78, 30) + strip(108, 28, 112, 30)
        rows += [white_box(44.4, 27.72, 45.5, 30.28), white_box(72.9, 27.72, 74.0, 30.28),
                 white_box(78.0, 27.72, 79.1, 30.28), white_box(106.9, 27.72, 108.0, 30.28)]
        rows += [line((45.5, 28.0), (60.5, 28.0)), line((99.0, 28.0), (106.9, 28.0))]
        if shared:
            rows.append(line((59.5, 30.2), (100.0, 30.2)))  # one long stroke across both openings
        else:
            rows += [line((59.5, 30.2), (72.9, 30.2)), line((79.1, 30.2), (100.0, 30.2))]
        return rows

    separate = sliding(wall_and_frames(False))
    assert [c.kind for c in separate.closures] == [KIND_SLIDING_LEAF, KIND_SLIDING_LEAF]
    assert sliding(wall_and_frames(True)).closures == ()


def test_sliding_closure_is_invariant_to_rigid_motion_and_never_a_wall():
    base = sliding(robe_room())
    rotated = sliding(robe_room(lambda x, y: (-y + 500.0, x + 40.0)))
    moved = sliding(robe_room(lambda x, y: (x + 317.25, y - 88.5)))
    for other in (rotated, moved):
        assert sorted(c.kind for c in other.closures) == sorted(c.kind for c in base.closures)
        assert sorted(round(r.area_pt2, 2) for r in candidates(other)) == sorted(round(r.area_pt2, 2) for r in candidates(base))
    chord_owners = {o for r in candidates(base) for owners in r.edge_owner_ids for o in owners if "closure" in o}
    assert chord_owners  # the chord exists as a typed owner of ring edges, never as a wall strip id
    assert not any(o.startswith("layered_wall_") for o in chord_owners)
