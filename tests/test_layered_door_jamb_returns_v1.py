"""Source-bound short door-jamb returns in the dark-painted layered ring (default off: ``door_jamb_returns``).

Synthetic only; no private source. The scene copies the drafting convention the rule reads: a segmented swing whose closed chord lies on a
face line of the wall; at each end of the chord a small frame (face strokes starting at the chord end, cross strokes at it); short wall
pieces running from there to walls of the other direction. Neither long-wall collector accepts them: the nib is under 40 pt and extra
lines just outside one face give the stroke-pair collector two partner lines; the stub is a few points long. Nothing here is a wall, an
opening or a quantity.
"""
from __future__ import annotations

import copy
import math
import random

import fitz
import pytest
from shapely.geometry import Point, Polygon, box

import pb_layered_wall_doorway_room_ring_shadow as ring
import pb_source_segmented_door_swing_shadow as seg
from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings

SHA = "cd" * 32
BLACK = (0.0, 0.0, 0.0)
GREY = (0.5, 0.5, 0.5)
LO, HI = 200.0, 252.0            # the doorway along the wall
FAR = 100.0                      # the wall face away from the swing
NIB_END, STUB_END = 165.0, 258.0  # where the short pieces meet the walls of the other direction
ROOM_PROBE = (211.0, 160.0)       # along/across point inside the room behind the door


def _line(a, b):
    return ("l", fitz.Point(*a), fitz.Point(*b))


def _stroke(a, b, width=0.48, color=BLACK, **extra):
    return {"layer": "", "fill": None, "color": color, "width": width, "items": [_line(a, b)], **extra}


class Scene:
    """Rows in order: wall faces and jambs, extra lines, the walls of the other direction, then the swing chain and its leaf.

    ``thickness`` sets the wall; the chord lies on the swing face ``FAR + thickness`` unless ``chord_inset`` moves it into the wall.
    ``map`` turns (along, across) into page points (translation, swap of axes, mirrors)."""

    def __init__(self, *, thickness=6.5, chord_inset=0.0, nib_end=NIB_END, stub_end=STUB_END, vertical=False, mirror_along=False,
                 mirror_across=False, dx=0.0, dy=0.0, drop=(), extra=(), leaf=True, nib_break=False, nib_split=False,
                 perpendicular=True, perp_shift=0.0, jambs_at_lo=True, far_face_at_lo=True, tip_offset=0.0, far_short=0.0):
        self.vertical, self.mirror_along, self.mirror_across, self.dx, self.dy = vertical, mirror_along, mirror_across, dx, dy
        near = FAR + thickness           # the swing face
        self.far, self.near = FAR, near
        chord = near - chord_inset
        rows = []
        named = {}

        def add(name, a, b, **kw):
            named.setdefault(name, []).append(len(rows))
            rows.append(_stroke(self.map(*a), self.map(*b), **kw))

        # the frame at each end of the chord: face strokes starting at the chord end, a cap behind them, cross strokes at the end
        for end, away, tag in ((LO, -2.2, "lo"), (HI, 2.2, "hi")):
            if tag == "hi" or far_face_at_lo:
                add(f"frame_far_{tag}", (end, FAR), (end + away, FAR), width=0.96)
            add(f"frame_near_{tag}", (end, near), (end + away, near), width=0.96)
            add(f"cap_{tag}", (end + away, FAR), (end + away, near), width=0.96)
            if tag == "hi" or jambs_at_lo:
                add(f"jamb_{tag}", (end, FAR), (end, FAR + 2.4), width=0.96)
                add(f"jamb_{tag}", (end, near - 2.4), (end, near), width=0.96)
        # the long nib on the low side: two lines per face, as drawn
        cap_lo = LO - 2.2
        for across, kw in ((FAR, {}), (FAR + 0.7, {}), (near - 0.7, {}), (near, {})):
            if across == FAR and not far_face_at_lo:
                continue
            if nib_break and across == near:
                add("nib", (nib_end, across), (cap_lo - 17.0, across))
                add("nib", (cap_lo - 16.0, across), (cap_lo, across))
            elif nib_split:
                third = (cap_lo - nib_end) / 3.0
                for k in range(3):
                    add("nib", (nib_end + k * third, across), (nib_end + (k + 1) * third, across), **kw)
            else:
                add("nib", (nib_end + (far_short if across == FAR else 0.0), across), (cap_lo, across), **kw)
        # extra lines just outside the swing face give the nib's far face two partner lines
        for across in (near + 0.5, near + 0.98):
            add("outside", (nib_end, across), (cap_lo, across), width=0.24)
        # the stub on the high side
        for across in (FAR, near):
            add("stub", (HI + 2.2, across), (stub_end, across))
        left_face = nib_end - perp_shift
        if perpendicular:
            for along in (left_face - 6.5, left_face):
                add("perp", (along, 20.0), (along, 220.0))
        for along in (stub_end, stub_end + 6.5):
            add("perp", (along, 20.0), (along, 220.0))
        for across in (220.0, 226.5):
            add("back", (left_face - 6.5, across), (stub_end + 6.5, across))
        for a, b, kw in extra:
            add("extra", a, b, **kw)
        # the segmented swing: nine chords from the closed tip (LO) round the hinge (HI), and the radial leaf
        width = HI - LO
        pts = [(HI - width * math.cos(math.radians(10 * k)), chord + width * math.sin(math.radians(10 * k))) for k in range(10)]
        pts[0] = (pts[0][0], pts[0][1] + tip_offset)         # the closed tip, moved off the face by the caller
        for a, b in zip(pts, pts[1:]):
            add("arc", a, b, width=0.48)
        if leaf:
            add("leaf", (HI, chord), (HI, chord + width), width=0.96)
        self.named = named
        self.rows = [r for i, r in enumerate(rows) if i not in {j for n in drop for j in named.get(n, ())}]
        self.chord = chord

    def map(self, along, across):
        if self.mirror_along:
            along = 450.0 - along
        if self.mirror_across:
            across = 330.0 - across
        x, y = (across, along) if self.vertical else (along, across)
        return (x + self.dx, y + self.dy)

    def rect(self, along0, along1, across0, across1):
        (x0, y0), (x1, y1) = self.map(along0, across0), self.map(along1, across1)
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def nib_rect(self):
        return self.rect(NIB_END, LO, self.far, self.near)

    def stub_rect(self):
        return self.rect(HI, STUB_END, self.far, self.near)


def _build(rows, **kw):
    kw.setdefault("door_jamb_returns", True)
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True, **kw)


def _existing_strips(rows, monkeypatch):
    """The strips the builder hands to the helper (everything collected before it), and the witnesses."""
    seen = {}
    real = ring._collect_door_jamb_return_strips

    def spy(drawings, witnesses, strips):
        seen["drawings"], seen["witnesses"], seen["strips"] = drawings, witnesses, list(strips)
        return real(drawings, witnesses, strips)

    monkeypatch.setattr(ring, "_collect_door_jamb_return_strips", spy)
    _build(rows)
    monkeypatch.setattr(ring, "_collect_door_jamb_return_strips", real)
    return seen


def _pieces(rows, monkeypatch):
    seen = _existing_strips(rows, monkeypatch)
    return ring._collect_door_jamb_return_strips(seen["drawings"], seen["witnesses"], seen["strips"])


def _boxes(pieces):
    return sorted(tuple(round(v, 3) for v in (s.x0, s.y0, s.x1, s.y1)) for s in pieces)


def _rounded(*rects):
    return sorted(tuple(round(v, 3) for v in r) for r in rects)


def _door_closed(result, scene):
    """Some closure covers the whole doorway on the wall."""
    want = box(*scene.rect(LO + 0.5, HI - 0.5, scene.chord - 0.1, scene.chord - 0.05))
    for c in result.closures:
        lo, hi = c.gap_interval
        rect = box(lo, c.band[0], hi, c.band[1]) if c.horizontal else box(c.band[0], lo, c.band[1], hi)
        if rect.buffer(0.2).contains(want):
            return True
    return False


def _room(result, scene):
    point = Point(*scene.map(*ROOM_PROBE))
    holding = [r for r in result.rings if Polygon(r.polygon_pdf_pts).contains(point)]
    return min(holding, key=lambda r: r.area_pt2) if holding else None


def _signature(result):
    return (
        result.status, result.reason_codes, result.wall_strip_count, result.wall_gap_count, result.unresolved_gap_count,
        tuple((r.record_id, r.polygon_pdf_pts, r.status) for r in result.rings),
        tuple((c.closure_id, c.kind, c.band, c.gap_interval) for c in result.closures),
    )


# ------------------------------------------------------------------------------------------------ the scene reproduces the failure

def test_the_scene_reproduces_the_failure_without_the_returns():
    scene = Scene()
    (witness,) = seg.collect_source_black_segmented_door_swings(scene.rows)
    assert witness["source_closed_leaf_tip_pdf_pts"] == pytest.approx((LO, scene.near))
    pairs = ring._collect_stroke_pair_strips(scene.rows)
    assert not any(s.x0 < LO - 1.0 and s.horizontal and abs(s.y0 - FAR) < 1.0 for s in pairs)    # the nib gets no pair
    result = _build(scene.rows, door_jamb_returns=False)
    assert not _door_closed(result, scene)
    assert _room(result, scene) is None


# ------------------------------------------------------------------------------------------------ the effect

TRANSFORMS = [
    {}, {"vertical": True}, {"mirror_along": True}, {"mirror_across": True}, {"vertical": True, "mirror_along": True},
    {"vertical": True, "mirror_across": True}, {"dx": 37.5, "dy": -11.25}, {"vertical": True, "dx": -3.0, "dy": 101.0},
]


@pytest.mark.parametrize("transform", TRANSFORMS, ids=lambda t: "+".join(f"{k}" for k in t) or "plain")
def test_both_short_pieces_are_made_from_the_door_s_own_jamb(transform, monkeypatch):
    scene = Scene(**transform)
    pieces = _pieces(scene.rows, monkeypatch)
    assert _boxes(pieces) == _rounded(scene.nib_rect(), scene.stub_rect())
    for piece in pieces:
        assert piece.vertical is bool(transform.get("vertical"))        # oriented along the wall, even where longer across it
        assert piece.path_indices == tuple(sorted(piece.path_indices)) and piece.path_indices


@pytest.mark.parametrize("transform", TRANSFORMS, ids=lambda t: "+".join(f"{k}" for k in t) or "plain")
def test_the_door_closes_and_the_room_behind_it_becomes_a_candidate(transform):
    scene = Scene(**transform)
    result = _build(scene.rows)
    assert _door_closed(result, scene)
    room = _room(result, scene)
    assert room is not None and room.status.value == "candidate"
    assert room.takeoff_eligible is False and room.commercial_projection_allowed is False and room.metric_area_issued is False


def test_the_pieces_keep_the_face_and_jamb_path_ids_and_never_the_door_s_own(monkeypatch):
    scene = Scene()
    pieces = _pieces(scene.rows, monkeypatch)
    owned = set(scene.named["arc"]) | set(scene.named["leaf"])
    nib, stub = sorted(pieces, key=lambda s: s.x0)
    assert owned.isdisjoint(nib.path_indices) and owned.isdisjoint(stub.path_indices)
    assert set(scene.named["frame_far_lo"]) <= set(nib.path_indices) and set(scene.named["jamb_lo"]) & set(nib.path_indices)
    assert set(scene.named["stub"]) <= set(stub.path_indices) and set(scene.named["jamb_hi"]) & set(stub.path_indices)
    assert not set(scene.named["outside"]) & set(nib.path_indices)


def test_split_face_strokes_make_the_same_pieces(monkeypatch):
    whole = Scene()
    split = Scene(nib_split=True)
    assert _boxes(_pieces(split.rows, monkeypatch)) == _boxes(_pieces(whole.rows, monkeypatch))


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_order_of_the_wall_rows_does_not_change_the_pieces(seed, monkeypatch):
    scene = Scene()
    chain = len(scene.named["arc"]) + 1                       # the chain and leaf stay contiguous, as a source swing's strokes are
    head, tail = scene.rows[:-chain], scene.rows[-chain:]
    # the row just before the chain stays put: a stroke ending where the chain starts would be read by the swing detector as part of it
    shuffled = head[:-1]
    random.Random(seed).shuffle(shuffled)
    rows = shuffled + head[-1:] + tail
    assert len(seg.collect_source_black_segmented_door_swings(rows)) == 1
    assert _boxes(_pieces(rows, monkeypatch)) == _boxes(_pieces(scene.rows, monkeypatch))


def test_unrelated_content_elsewhere_changes_nothing(monkeypatch):
    plain = Scene()
    busy = Scene(extra=[((400.0 + 3 * k, 300.0), (400.0 + 3 * k, 380.0), {}) for k in range(12)])
    assert _boxes(_pieces(busy.rows, monkeypatch)) == _boxes(_pieces(plain.rows, monkeypatch))


def test_the_same_witness_twice_makes_each_piece_once(monkeypatch):
    seen = _existing_strips(Scene().rows, monkeypatch)
    once = ring._collect_door_jamb_return_strips(seen["drawings"], seen["witnesses"], seen["strips"])
    twice = ring._collect_door_jamb_return_strips(seen["drawings"], tuple(seen["witnesses"]) * 2, seen["strips"])
    assert _boxes(twice) == _boxes(once) and len(twice) == 2


def test_another_door_s_own_strokes_are_never_read_as_jamb_or_face(monkeypatch):
    scene = Scene()
    seen = _existing_strips(scene.rows, monkeypatch)
    other = {"native_source_path_indices": tuple(scene.named["frame_far_lo"]), "source_hinge_point_pdf_pts": (900.0, 900.0),
             "source_closed_leaf_tip_pdf_pts": (900.0, 952.0)}
    pieces = ring._collect_door_jamb_return_strips(seen["drawings"], (*seen["witnesses"], other), seen["strips"])
    assert _boxes(pieces) == _rounded(scene.stub_rect())                           # without that stroke the low end has no far face


def test_building_never_mutates_the_rows_and_replays_deterministically():
    scene = Scene()
    before = copy.deepcopy(scene.rows)
    first, second = _build(scene.rows), _build(scene.rows)
    assert [(r["color"], r["width"], [tuple((p.x, p.y) for p in i[1:]) for i in r["items"]]) for r in scene.rows] == \
        [(r["color"], r["width"], [tuple((p.x, p.y) for p in i[1:]) for i in r["items"]]) for r in before]
    assert _signature(first) == _signature(second)


# ------------------------------------------------------------------------------------------------ look-alikes mint nothing there

def _only_stub(scene, monkeypatch):
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.stub_rect())


def test_without_a_cross_stroke_at_the_chord_end_that_end_is_left_alone(monkeypatch):
    _only_stub(Scene(jambs_at_lo=False), monkeypatch)


def test_without_a_second_face_that_end_is_left_alone(monkeypatch):
    _only_stub(Scene(far_face_at_lo=False), monkeypatch)


def test_two_possible_second_faces_abstain(monkeypatch):
    third = FAR + 3.0
    scene = Scene(extra=[((LO, third), (NIB_END, third), {})])
    _only_stub(scene, monkeypatch)


def test_faces_that_stop_at_the_frame_abstain(monkeypatch):
    _only_stub(Scene(drop=("nib",)), monkeypatch)


def test_without_a_wall_of_the_other_direction_at_the_far_end_that_end_abstains(monkeypatch):
    _only_stub(Scene(perpendicular=False), monkeypatch)


def test_a_break_in_a_face_stops_the_piece_at_the_break(monkeypatch):
    _only_stub(Scene(nib_break=True), monkeypatch)


@pytest.mark.parametrize("face", ["frame_far_lo", "frame_near_lo"])
def test_a_grey_face_is_not_wall_ink(face, monkeypatch):
    scene = Scene()
    for index in scene.named[face]:
        scene.rows[index] = {**scene.rows[index], "color": GREY}
    _only_stub(scene, monkeypatch)


def test_an_invisible_stroke_is_not_wall_ink(monkeypatch):
    # given straight to the helper: the builder's own ink filter would otherwise have removed it already
    seen = _existing_strips(Scene().rows, monkeypatch)
    rows = list(seen["drawings"])
    scene = Scene()
    for index in scene.named["frame_far_lo"]:
        rows[index] = {**rows[index], "stroke_opacity": 0.0}
    assert _boxes(ring._collect_door_jamb_return_strips(rows, seen["witnesses"], seen["strips"])) == _rounded(scene.stub_rect())


@pytest.mark.parametrize("thickness", [1.0, 12.0])
def test_a_band_outside_the_wall_thickness_window_abstains(thickness, monkeypatch):
    scene = Scene(thickness=thickness)
    for name, end in (("jamb_lo", LO), ("jamb_hi", HI)):             # one cross stroke that fits the band exactly
        first, *rest = scene.named[name]
        scene.rows[first] = _stroke(scene.map(end, FAR + thickness), scene.map(end, FAR), width=0.96)
        for index in rest:
            scene.rows[index] = {"layer": "", "fill": None, "color": None, "items": ()}
    assert _pieces(scene.rows, monkeypatch) == []


@pytest.mark.parametrize("length,made", [(39.5, True), (40.0, False), (55.0, False)])
def test_a_piece_as_long_as_the_long_wall_minimum_is_left_to_those_collectors(length, made, monkeypatch):
    assert ring._MERGED_FACE_MIN_SPAN == 40.0                              # the bound is the merged-face collector's own minimum
    scene = Scene(nib_end=LO - length)
    expected = [scene.rect(LO - length, LO, FAR, scene.near)] if made else []
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.stub_rect(), *expected)


@pytest.mark.parametrize("shift,made", [(0.5, True), (1.5, False)])
def test_the_far_wall_must_touch_within_the_face_cluster_tolerance(shift, made, monkeypatch):
    scene = Scene(perp_shift=shift)                                          # the other wall stops short of the faces' end
    expected = [scene.nib_rect()] if made else []
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.stub_rect(), *expected)


def test_a_wall_of_the_same_direction_at_the_far_end_is_not_a_far_wall(monkeypatch):
    beyond = [((100.0, across), (NIB_END - 0.5, across), {}) for across in (FAR, FAR + 6.5)]
    _only_stub(Scene(perpendicular=False, extra=beyond), monkeypatch)


def test_a_chord_that_is_not_on_a_face_line_abstains(monkeypatch):
    assert _pieces(Scene(chord_inset=3.25).rows, monkeypatch) == []


def test_a_line_running_from_the_jamb_into_the_doorway_is_not_a_face(monkeypatch):
    inward = FAR + 3.0
    scene = Scene(extra=[((LO, inward), (LO + 5.0, inward), {})])
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.nib_rect(), scene.stub_rect())


def test_a_face_a_point_off_the_chord_is_not_the_chord_face(monkeypatch):
    off = FAR + 6.5 - 1.0
    scene = Scene(drop=("frame_near_lo",), extra=[((LO, off), (LO - 2.2, off), {})])
    _only_stub(scene, monkeypatch)


def test_a_diagonal_chord_is_never_processed(monkeypatch):
    scene = Scene(vertical=True)
    seen = _existing_strips(scene.rows, monkeypatch)
    near = FAR + 6.5
    diagonal = {**seen["witnesses"][0], "source_hinge_point_pdf_pts": (near - 3.0, HI), "source_closed_leaf_tip_pdf_pts": (near + 3.0, LO)}
    assert ring._collect_door_jamb_return_strips(seen["drawings"], (diagonal,), seen["strips"]) == []


def test_without_a_swing_there_is_nothing_to_bind_to(monkeypatch):
    scene = Scene(leaf=False)
    assert seg.collect_source_black_segmented_door_swings(scene.rows) == ()
    assert _pieces(scene.rows, monkeypatch) == []
    assert _signature(_build(scene.rows)) == _signature(_build(scene.rows, door_jamb_returns=False))


# ------------------------------------------------------------------------------------------------ the reused tolerances


def _replace(scene, name, strokes):
    """Swap a named group of rows for new (along, across) strokes, in place so every other row keeps its index."""
    indices = scene.named[name]
    assert len(strokes) <= len(indices)
    for index, spec in zip(indices, strokes):
        a, b = spec
        scene.rows[index] = _stroke(scene.map(*a), scene.map(*b), width=0.96)
    for index in indices[len(strokes):]:
        scene.rows[index] = {"layer": "", "fill": None, "color": None, "items": ()}


def test_a_closed_tip_just_off_the_face_keeps_the_band_on_the_drawn_faces(monkeypatch):
    scene = Scene(tip_offset=0.05)
    assert len(seg.collect_source_black_segmented_door_swings(scene.rows)) == 1
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.nib_rect(), scene.stub_rect())


@pytest.mark.parametrize("tilt,made", [(0.05, True), (0.3, False)])
def test_a_face_line_must_run_along_the_wall(tilt, made, monkeypatch):
    scene = Scene()
    _replace(scene, "frame_far_lo", [((LO, FAR), (LO - 2.2, FAR + tilt))])
    expected = [scene.nib_rect()] if made else []
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.stub_rect(), *expected)


@pytest.mark.parametrize("gap,made", [(0.1, True), (0.3, False)])
def test_a_face_must_start_at_the_chord_end(gap, made, monkeypatch):
    scene = Scene()
    _replace(scene, "frame_far_lo", [((LO - gap, FAR), (LO - 2.2, FAR))])
    expected = [scene.nib_rect()] if made else []
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.stub_rect(), *expected)


def test_a_face_that_starts_with_a_tick_is_not_read(monkeypatch):
    scene = Scene()
    scene.rows = scene.rows[:-len(scene.named["arc"]) - 1] + [_stroke(scene.map(LO - 0.5, FAR), scene.map(LO - 2.2, FAR))] +         scene.rows[-len(scene.named["arc"]) - 1:]
    _replace(scene, "frame_far_lo", [((LO, FAR), (LO - 0.5, FAR))])
    _only_stub(scene, monkeypatch)


def test_a_face_drawn_twice_within_the_tolerance_is_one_face(monkeypatch):
    scene = Scene(extra=[((LO, FAR + 0.1), (LO - 2.2, FAR + 0.1), {})])
    assert _boxes(_pieces(scene.rows, monkeypatch)) == _rounded(scene.nib_rect(), scene.stub_rect())


def test_a_line_running_through_the_chord_end_into_the_doorway_is_not_a_jamb_face(monkeypatch):
    scene = Scene(drop=("frame_near_lo",), extra=[((LO + 10.0, FAR + 6.5), (NIB_END, FAR + 6.5), {})])
    _only_stub(scene, monkeypatch)


@pytest.mark.parametrize("cross", [(FAR - 10.0, FAR + 6.5), (FAR, FAR + 20.0), (FAR + 2.0, FAR + 4.0)],
                         ids=["past the far face", "past the chord face", "touching neither face"])
def test_only_a_cross_stroke_within_the_wall_and_on_a_face_is_a_jamb(cross, monkeypatch):
    # drawn from the far end back, so it never ends where the swing chain starts
    scene = Scene(jambs_at_lo=False, extra=[((LO, cross[1]), (LO, cross[0]), {})])
    _only_stub(scene, monkeypatch)


def test_the_piece_ends_where_the_shorter_face_stops(monkeypatch):
    _only_stub(Scene(far_short=3.0), monkeypatch)


def test_a_filled_path_is_not_read_as_a_face(monkeypatch):
    scene = Scene()
    for index in scene.named["frame_far_lo"]:
        scene.rows[index] = {**scene.rows[index], "fill": (0.0, 0.0, 0.0)}
    _only_stub(scene, monkeypatch)


# ------------------------------------------------------------------------------------------------ the switch

def test_off_by_default_and_off_changes_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(ring, "_collect_door_jamb_return_strips", lambda *a: calls.append(a) or [])
    scene = Scene()
    default = build_layered_wall_doorway_room_rings(scene.rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True)
    explicit = _build(scene.rows, door_jamb_returns=False)
    assert not calls and _signature(default) == _signature(explicit)
    _build(scene.rows)
    assert len(calls) == 1


@pytest.mark.parametrize("value", [1, 0, None, "yes"])
def test_the_switch_is_an_explicit_boolean(value):
    with pytest.raises(ValueError, match="door_jamb_returns must be an explicit boolean"):
        _build(Scene().rows, door_jamb_returns=value)


def test_the_switch_requires_the_dark_painted_path():
    with pytest.raises(ValueError, match="door_jamb_returns requires dark_painted_wall_source"):
        build_layered_wall_doorway_room_rings(Scene().rows, source_sha256=SHA, page_index=0, door_jamb_returns=True)


def test_the_byte_entry_point_forwards_the_switch(monkeypatch):
    import hashlib

    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    seen = []
    monkeypatch.setattr(ring, "build_layered_wall_doorway_room_rings", lambda drawings, **kw: seen.append(kw) or "built")
    sha = hashlib.sha256(payload).hexdigest()
    assert ring.build_from_pdf_bytes(payload, source_sha256=sha, page_index=0) == "built"
    assert ring.build_from_pdf_bytes(payload, source_sha256=sha, page_index=0, dark_painted_wall_source=True, door_jamb_returns=True) == "built"
    assert [kw["door_jamb_returns"] for kw in seen] == [False, True]
