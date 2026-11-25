"""P3b: a segmented swing's OWN strokes are door symbol ink and never mint wall strips in the dark-painted layered ring.

Synthetic only; no private source. A source door swing (a quarter-turn chain of black single-line strokes with its one radial
leaf) is detected by ``collect_source_black_segmented_door_swings``. The leaf is collinear with the hinge-side jamb line, so the
line-based wall-strip collectors (merged collinear dark face, stroke pair, wall-end closure, heavy stroke) read it as a thin wall
face. That strip reaches into the doorway, the raw wall gap stops short of the door's far end, and the chord proposer's 0.18 pt
containment test finds no parent gap. With ``door_jamb_returns`` on (default off; the exclusion ships only paired with the jamb
returns), the builder gives those collectors a view of the rows in which the witness-owned native paths are inert (same indices, same
length); the door detection, the proposer and every other consumer keep reading the full rows. A page without a witness is
untouched. Nothing here is a wall, an opening or a quantity.
"""
from __future__ import annotations

import copy
import math
import random

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as ring
import pb_source_segmented_door_swing_shadow as seg
from pb_layered_wall_doorway_room_ring_shadow import (
    _without_door_owned_paths,
    build_layered_wall_doorway_room_rings,
)

SHA = "ab" * 32
BLACK = (0.0, 0.0, 0.0)
GREEN = (0.0, 0.5, 0.0)
INERT = {"layer": "", "fill": None, "color": None, "items": ()}


def _line(a, b):
    return ("l", fitz.Point(*a), fitz.Point(*b))


def _stroke(a, b, width=0.5, color=BLACK):
    return {"layer": "", "fill": None, "color": color, "width": width, "items": [_line(a, b)]}


class Scene:
    """A wall with one doorway, its jambs and a segmented source swing whose radial leaf is collinear with the hinge-side jamb.

    ``rows`` keeps the order: wall faces, jambs, nine consecutive chord strokes, the radial leaf. The wall runs along x (or along y when
    ``vertical``); the doorway interval is [100, 100 + width] on the wall line y = 43 before translation."""

    def __init__(self, *, width=52.0, vertical=False, dx=0.0, dy=0.0, leaf=True, lead=0):
        self.width, self.vertical = width, vertical
        lo, hi, y0 = 100.0, 100.0 + width, 43.0
        self.lo, self.hi, self.y0 = lo, hi, y0

        def point(along, across):
            x, y = (across, along) if vertical else (along, across)
            return (x + dx, y + dy)

        rows = [INERT] * lead                                              # unrelated leading rows: shifts every native index
        for across in (y0 - 3.0, y0 + 3.0):
            rows.append(_stroke(point(lo - 100.0, across), point(lo, across)))
            rows.append(_stroke(point(hi, across), point(hi + 148.0, across)))
        self.jamb_lo = len(rows)
        rows.append(_stroke(point(lo, y0 - 3.0), point(lo, y0 + 3.0)))
        self.jamb_hi = len(rows)
        rows.append(_stroke(point(hi, y0 - 3.0), point(hi, y0 + 3.0)))
        pts = [point(hi - width * math.cos(math.radians(10 * k)), y0 + width * math.sin(math.radians(10 * k))) for k in range(10)]
        self.arc = tuple(range(len(rows), len(rows) + 9))
        for a, b in zip(pts, pts[1:]):
            rows.append(_stroke(a, b))
        self.leaf = None
        if leaf:
            self.leaf = len(rows)
            rows.append(_stroke(point(hi, y0), point(hi, y0 + width)))
        self.rows = rows
        self.owned = set(self.arc) | ({self.leaf} if leaf else set())


def _build(rows, **kw):
    kw.setdefault("door_jamb_returns", True)   # the exclusion ships only paired with the jamb returns
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True, **kw)


def _signature(result):
    return (
        result.status, result.reason_codes, result.wall_strip_count, result.wall_gap_count, result.unresolved_gap_count,
        result.merged_collinear_dark_face_strip_count,
        tuple((r.record_id, r.polygon_pdf_pts) for r in result.rings),
        tuple(c.closure_id for c in result.closures),
        tuple(c["door_interval_pdf_pts"] for c in result.source_owned_doorway_chords),
        tuple(w["native_source_path_indices"] for w in result.source_segmented_swing_witnesses),
    )


def _proposal_gaps(monkeypatch):
    seen = []
    real = seg.propose_source_owned_doorway_chords

    def spy(drawings, witnesses, gaps):
        seen.append([(g.horizontal, tuple(g.band), g.lo, g.hi) for g in gaps])
        return real(drawings, witnesses, gaps)

    monkeypatch.setattr(seg, "propose_source_owned_doorway_chords", spy)
    return seen


# ------------------------------------------------------------------------------------------------ the scene

def test_the_scene_reproduces_the_failure_condition():
    scene = Scene()
    (witness,) = seg.collect_source_black_segmented_door_swings(scene.rows)
    assert witness["leaf_native_path_index"] == scene.leaf
    assert set(witness["native_source_path_indices"]) == scene.owned
    # read as plain wall ink, the leaf and the hinge-side jamb merge into one thin strip longer than 40 pt
    strips = ring._collect_merged_collinear_dark_face_strips(scene.rows)
    owning = [s for s in strips if scene.leaf in s.native_path_indices()]
    assert len(owning) == 1 and scene.jamb_hi in owning[0].native_path_indices()


# ------------------------------------------------------------------------------------------------ paired and off by default

def test_without_the_paired_switch_the_door_s_strokes_are_read_exactly_as_before(monkeypatch):
    scene = Scene()
    calls = []
    real = ring._without_door_owned_paths
    monkeypatch.setattr(ring, "_without_door_owned_paths", lambda *a: calls.append(1) or real(*a))
    off = _build(scene.rows, door_jamb_returns=False)
    assert calls == [] and off.source_owned_doorway_chords == ()   # the failure the exclusion repairs is still there
    on = _build(scene.rows)
    assert calls == [1] and len(on.source_owned_doorway_chords) == 1


# ------------------------------------------------------------------------------------------------ the effect

@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("width", [23.0, 52.08, 138.0])
@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (37.5, -21.25)])
def test_a_door_whose_own_leaf_and_jamb_are_collinear_still_gets_its_chord(vertical, width, dx, dy):
    scene = Scene(width=width, vertical=vertical, dx=dx, dy=dy)
    result = _build(scene.rows)
    (witness,) = result.source_segmented_swing_witnesses
    (chord,) = result.source_owned_doorway_chords
    along = dy if vertical else dx                                           # the shift along the wall line
    assert chord["horizontal"] is (not vertical)
    assert chord["door_interval_pdf_pts"] == pytest.approx((scene.lo + along, scene.hi + along), abs=0.02)
    # original native indices, never renumbered: the chord was proposed from the FULL rows
    assert set(chord["source_swing_native_path_indices"]) == scene.owned == set(witness["native_source_path_indices"])
    assert chord["commercial_publishable"] is False and chord["metric_area_issued"] is False
    assert chord["candidate_topology_doorway_closure"] is True and chord["source_physical_door_host_authenticated"] is False


def test_the_raw_gap_the_proposer_sees_is_the_whole_doorway(monkeypatch):
    seen = _proposal_gaps(monkeypatch)
    scene = Scene()
    _build(scene.rows)
    (gaps,) = seen
    assert len(gaps) == 1
    horizontal, band, lo, hi = gaps[0]
    assert horizontal and (lo, hi) == pytest.approx((scene.lo, scene.hi), abs=1e-6)   # not 0.6 pt short of the far end


def test_unrelated_rows_before_the_door_shift_its_indices_but_not_its_chord():
    plain = Scene()
    shifted = Scene(lead=40)
    a, b = _build(plain.rows), _build(shifted.rows)
    (ca,), (cb,) = a.source_owned_doorway_chords, b.source_owned_doorway_chords
    assert ca["door_interval_pdf_pts"] == cb["door_interval_pdf_pts"]
    assert set(cb["source_swing_native_path_indices"]) == shifted.owned and shifted.owned != plain.owned


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_order_of_the_wall_faces_and_jambs_does_not_change_the_chord(seed):
    # the four wall faces and the two jambs come before the door's own chain and leaf; permute that block only (the chain stays contiguous,
    # as a source swing's strokes are), so every native index of the wall rows moves while the door does not
    scene = Scene()
    head, tail = scene.rows[:6], scene.rows[6:]
    shuffled = list(head)
    random.Random(seed).shuffle(shuffled)
    got = _build(shuffled + tail)
    base = _build(scene.rows)
    (chord,), (expected,) = got.source_owned_doorway_chords, base.source_owned_doorway_chords
    assert chord["door_interval_pdf_pts"] == pytest.approx(expected["door_interval_pdf_pts"], abs=1e-6)
    assert got.wall_gap_count == base.wall_gap_count


def test_building_never_mutates_the_rows_and_replays_deterministically():
    scene = Scene()
    before = copy.deepcopy(scene.rows)
    first, second = _build(scene.rows), _build(scene.rows)
    assert scene.rows == before
    assert _signature(first) == _signature(second)


# ------------------------------------------------------------------------------------------------ the view

def test_the_helper_makes_only_the_owned_rows_inert_and_never_mutates():
    scene = Scene()
    witnesses = seg.collect_source_black_segmented_door_swings(scene.rows)
    before = copy.deepcopy(scene.rows)
    view = _without_door_owned_paths(scene.rows, witnesses)
    assert scene.rows == before
    assert len(view) == len(scene.rows)
    assert {i for i, row in enumerate(view) if row is not scene.rows[i]} == scene.owned
    assert all(view[i]["items"] == () and view[i]["fill"] is None and view[i]["color"] is None for i in scene.owned)
    assert all(view[i] is scene.rows[i] for i in range(len(view)) if i not in scene.owned)


def test_the_helper_returns_the_input_itself_without_a_witness():
    rows = tuple(Scene(leaf=False).rows)
    assert _without_door_owned_paths(rows, ()) is rows
    assert seg.collect_source_black_segmented_door_swings(rows) == ()
    assert _without_door_owned_paths(rows, seg.collect_source_black_segmented_door_swings(rows)) is rows


def test_every_line_based_collector_reads_the_view_and_the_filled_ones_read_the_full_rows(monkeypatch):
    scene = Scene()
    got = {}

    def spy(name, real):
        def wrapper(rows, *args, **kwargs):
            got.setdefault(name, rows)                                           # the strip assembly's own call is the first
            return real(rows, *args, **kwargs)
        monkeypatch.setattr(ring, name, wrapper)

    for name in ("_collect_merged_collinear_dark_face_strips", "_collect_stroke_pair_strips", "_collect_wall_end_closing_strips",
                 "_collect_source_heavy_stroke_strips", "_collect_strips", "_collect_dark_painted_source_wall_strips"):
        spy(name, getattr(ring, name))
    _build(scene.rows, wall_end_stroke_closures=True, source_heavy_stroke_wall_bands=True)
    for name in ("_collect_merged_collinear_dark_face_strips", "_collect_stroke_pair_strips", "_collect_wall_end_closing_strips",
                 "_collect_source_heavy_stroke_strips"):
        rows = got[name]
        assert len(rows) == len(scene.rows), name
        assert {i for i, row in enumerate(rows) if row is not scene.rows[i]} == scene.owned, name
        assert all(rows[i]["items"] == () for i in scene.owned), name
    for name in ("_collect_strips", "_collect_dark_painted_source_wall_strips"):
        assert all(a is b for a, b in zip(got[name], scene.rows)) and len(got[name]) == len(scene.rows), name


def test_the_door_detection_the_arc_finder_and_the_proposer_keep_reading_the_full_rows(monkeypatch):
    # The exclusion changes what the wall-strip collectors read and nothing else: a door is still detected, found as an arc and proposed
    # from the real ink, with every original native index in place.
    scene = Scene()
    got = {}

    def spy(owner, name):
        real = getattr(owner, name)

        def wrapper(rows, *args, **kwargs):
            got.setdefault(name, rows)
            return real(rows, *args, **kwargs)
        monkeypatch.setattr(owner, name, wrapper)

    spy(seg, "collect_source_black_segmented_door_swings")
    spy(seg, "propose_source_owned_doorway_chords")
    spy(ring, "_swing_arcs")
    _build(scene.rows)
    assert set(got) == {"collect_source_black_segmented_door_swings", "propose_source_owned_doorway_chords", "_swing_arcs"}
    for name, rows in got.items():
        assert len(rows) == len(scene.rows) and all(a is b for a, b in zip(rows, scene.rows)), name


def test_the_witnesses_are_found_once_per_build_and_only_on_the_dark_painted_path(monkeypatch):
    calls = []
    real = seg.collect_source_black_segmented_door_swings
    monkeypatch.setattr(seg, "collect_source_black_segmented_door_swings", lambda rows: calls.append(1) or real(rows))
    scene = Scene()
    _build(scene.rows)
    assert len(calls) == 1
    calls.clear()
    build_layered_wall_doorway_room_rings(scene.rows, source_sha256=SHA, page_index=0)
    assert calls == []


# ------------------------------------------------------------------------------------------------ look-alike negatives and invariance

def test_a_chain_without_a_unique_leaf_is_not_a_witness_and_hides_nothing(monkeypatch):
    scene = Scene(leaf=False)
    got = {}

    def spy(name, real):
        def wrapper(rows, *args, **kwargs):
            got.setdefault(name, rows)
            return real(rows, *args, **kwargs)
        monkeypatch.setattr(ring, name, wrapper)

    spy("_collect_strips", ring._collect_strips)
    spy("_collect_merged_collinear_dark_face_strips", ring._collect_merged_collinear_dark_face_strips)
    result = _build(scene.rows)
    assert result.source_segmented_swing_witnesses == () and result.source_owned_doorway_chords == ()
    # no witness: the line-based collector reads the very rows the filled collector reads, not a copy with holes
    assert got["_collect_merged_collinear_dark_face_strips"] is got["_collect_strips"]


def test_a_wall_stroke_that_is_not_witness_owned_still_mints_its_strip():
    # the same long wall face, drawn beside a witness, is still a merged-face strip: only witness-owned paths are hidden
    scene = Scene()
    far = [_stroke((1000.0 + 6.0 * k, 500.0), (1000.0 + 6.0 * k + 5.0, 500.0)) for k in range(40)]   # a dashed face of 40 dashes
    rows = scene.rows + far
    result_with = _build(rows)
    result_without = _build(scene.rows)
    assert result_with.merged_collinear_dark_face_strip_count == result_without.merged_collinear_dark_face_strip_count + 1
    assert len(result_with.source_owned_doorway_chords) == len(result_without.source_owned_doorway_chords) == 1


def test_a_witness_free_page_is_identical_with_the_exclusion_switched_off(monkeypatch):
    rng = random.Random(7)
    rows = []
    for k in range(60):                                                         # random black strokes and dashed faces, no swing
        x, y = rng.uniform(0, 400), rng.uniform(0, 400)
        horizontal = rng.random() < 0.5
        length = rng.uniform(3, 90)
        a = (x, y)
        b = (x + length, y) if horizontal else (x, y + length)
        rows.append(_stroke(a, b, width=rng.choice([0.5, 1.2, 2.0])))
    assert seg.collect_source_black_segmented_door_swings(rows) == ()
    on = _build(rows)
    monkeypatch.setattr(ring, "_without_door_owned_paths", lambda drawings, witnesses: drawings)
    off = _build(rows)
    assert _signature(on) == _signature(off)


def test_green_ink_and_the_default_path_are_untouched(monkeypatch):
    scene = Scene()
    with_green = scene.rows + [_stroke((10.0, 10.0), (200.0, 10.0), color=GREEN)]
    assert _signature(_build(with_green)) == _signature(_build(scene.rows))
    monkeypatch.setattr(ring, "_without_door_owned_paths", lambda drawings, witnesses: drawings)
    off = _build(scene.rows)
    assert off.source_owned_doorway_chords == ()                                 # disabled: the failure comes back (the effect is real)
