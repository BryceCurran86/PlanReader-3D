"""Strict jamb caps in the dark-painted layered ring (default off: ``jamb_caps_must_be_wall_ends``).

Synthetic only; no private source. A wall drawn as dark filled bars has one 60 pt interruption with a stroke across each end. Today any
visible stroke up to 80 pt long, of any colour, may cap that interruption. With the switch on a cap stroke must be wall ink and END at
the wall faces; it may reach a far face line only where a door swing is already placed there. Topology only: nothing here is a wall,
an opening or a quantity.
"""
from __future__ import annotations

import copy
import hashlib
import random

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as ring
from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_STROKE,
    KIND_SWING,
    build_layered_wall_doorway_room_rings,
)

SHA = "ef" * 32
BLACK = (0.0, 0.0, 0.0)
DARK_GREY = (0.2, 0.2, 0.2)
GREY = (0.5, 0.5, 0.5)
PINK = (1.0, 0.5, 0.5)
BLUE = (0.0, 0.0, 1.0)
KAPPA = 0.5522847498
LO, HI = 30.0, 90.0                    # the interruption along the wall
NEAR = (98.0, 99.5)                    # the near face bar across the wall
FAR_BAR = (110.0, 111.5)               # a second face line of a thick wall


def identity(x, y):
    return x, y


def _bar(x0, y0, x1, y1, tf):
    ax, ay = tf(x0, y0)
    bx, by = tf(x1, y1)
    rect = fitz.Rect(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
    return {"layer": "", "fill": BLACK, "color": None, "items": [("re", rect, 1)]}


def _stroke(a, b, tf, color=BLACK, width=0.48):
    return {"layer": "", "fill": None, "color": color, "width": width,
            "items": [("l", fitz.Point(*tf(*a)), fitz.Point(*tf(*b)))]}


def _cap(along, across, tf, color=BLACK):
    """A stroke across the wall at ``along``, spanning ``across`` = (from, to)."""
    return _stroke((across[0], along), (across[1], along), tf, color=color)


def _swing(centre, open_tip, closed_tip, tf):
    (cx, cy), (ox, oy), (tx, ty) = centre, open_tip, closed_tip
    p2 = (ox + KAPPA * (tx - cx), oy + KAPPA * (ty - cy))
    p3 = (tx + KAPPA * (ox - cx), ty + KAPPA * (oy - cy))
    arc = {"layer": "", "fill": None, "color": BLACK, "width": 0.48,
           "items": [("c", fitz.Point(*tf(ox, oy)), fitz.Point(*tf(*p2)), fitz.Point(*tf(*p3)), fitz.Point(*tf(tx, ty)))]}
    return [arc, _stroke(centre, open_tip, tf)]


def _wall(band, tf, lo=LO, hi=HI):
    return [_bar(band[0], 2.0, band[1], lo, tf), _bar(band[0], hi, band[1], 118.0, tf)]


def _door_on(face, tf, lo=LO, hi=HI, outward=1.0):
    """A swing hinged at ``hi`` whose closed leaf lies on the face line ``face``."""
    return _swing((face, hi), (face + outward * (hi - lo), hi), (face, lo), tf)


def thin(tf=identity, *, low=NEAR, high=NEAR, low_color=BLACK, high_color=BLACK, extra=()):
    rows = _wall(NEAR, tf)
    rows.append(_cap(LO, low, tf, color=low_color))
    rows.append(_cap(HI, high, tf, color=high_color))
    return rows + list(extra)


def thick(tf=identity, *, low=(98.0, 110.7), high=(98.0, 102.6), far=((FAR_BAR, LO, HI),), doors=((111.5, LO, HI, 1.0),)):
    """The near face with long jamb strokes reaching a far face line; ``far`` bars and ``doors`` are placed separately."""
    rows = _wall(NEAR, tf)
    for band, lo, hi in far:
        rows += _wall(band, tf, lo, hi)
    rows.append(_cap(LO, low, tf))
    rows.append(_cap(HI, high, tf))
    for face, lo, hi, outward in doors:
        rows += _door_on(face, tf, lo, hi, outward)
    return rows


def _build(rows, **kw):
    kw.setdefault("dark_painted_wall_source", True)
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, **kw)


def _strict(rows):
    return _build(rows, jamb_caps_must_be_wall_ends=True)


def _box(closure):
    lo, hi = closure.gap_interval
    return (closure.kind, closure.horizontal, tuple(round(v, 3) for v in closure.band), round(lo, 3), round(hi, 3))


def _boxes(result):
    return sorted(_box(c) for c in result.closures)


def _cap_closures(result):
    return [c for c in result.closures if c.kind == KIND_STROKE]


def _near_closed(result, tf=identity):
    """True when the near face interruption holds a stroke closure."""
    ax, ay = tf(NEAR[0], LO)
    bx, by = tf(NEAR[1], HI)
    want = (sorted((ax, bx)), sorted((ay, by)))
    for c in _cap_closures(result):
        lo, hi = c.gap_interval
        xs = (lo, hi) if c.horizontal else c.band
        ys = c.band if c.horizontal else (lo, hi)
        if all(abs(a - b) < 0.01 for a, b in zip(sorted(xs), want[0])) and all(abs(a - b) < 0.01 for a, b in zip(sorted(ys), want[1])):
            return True
    return False


# ------------------------------------------------------------------------------------------------ a real wall end still closes

@pytest.mark.parametrize("tf", [identity, lambda x, y: (x + 37.25, y + 11.5), lambda x, y: (y, x),
                                lambda x, y: (240.0 - x, y), lambda x, y: (x, 130.0 - y)],
                         ids=["plain", "translated", "axes_swapped", "mirrored_across", "mirrored_along"])
def test_short_jamb_strokes_close_the_interruption_exactly_as_before(tf):
    off, on = _build(thin(tf)), _strict(thin(tf))
    assert _near_closed(off, tf) and _near_closed(on, tf)
    assert _boxes(on) == _boxes(off)
    assert [c.native_path_indices for c in on.closures] == [c.native_path_indices for c in off.closures]


@pytest.mark.parametrize("low", [(97.21, 99.5), (98.0, 100.29), (97.21, 100.29)])
def test_a_jamb_stroke_a_little_past_a_face_still_counts(low):
    assert _near_closed(_strict(thin(low=low)))


@pytest.mark.parametrize("low", [(97.19, 99.5), (98.0, 100.31)])
def test_a_jamb_stroke_further_past_a_face_does_not_count(low):
    assert _near_closed(_build(thin(low=low)))
    assert not _near_closed(_strict(thin(low=low)))


def test_a_jamb_split_by_a_small_notch_still_counts():
    rows = _wall(NEAR, identity) + [_cap(LO, (98.0, 98.6), identity), _cap(LO, (98.9, 99.5), identity), _cap(HI, NEAR, identity)]
    assert _near_closed(_strict(rows))


def test_wall_ink_is_the_module_s_own_wall_support_role():
    on_wall_layer = thin(low_color=DARK_GREY, high_color=DARK_GREY)
    for row in on_wall_layer[-2:]:
        row["layer"] = "Enclosure_WallInternal"
    assert _near_closed(_strict(on_wall_layer))
    # the same dark grey on an unnamed layer is not wall support (the module's existing role), so it no longer caps
    unnamed = thin(low_color=DARK_GREY, high_color=DARK_GREY)
    assert _near_closed(_build(unnamed)) and not _near_closed(_strict(unnamed))


# ------------------------------------------------------------------------------------------------ look-alikes that close today only

LOOKALIKES = {
    "one_long_line": dict(low=(98.0, 130.0)),
    "alcove_mouth_between_two_returns": dict(low=(98.0, 114.0), high=(98.0, 114.0)),
    "fixture_edges_on_the_other_side": dict(low=(86.0, 99.5), high=(86.0, 99.5)),
    "line_crossing_the_wall": dict(low=(90.0, 108.0)),
}


@pytest.mark.parametrize("name", sorted(LOOKALIKES))
@pytest.mark.parametrize("tf", [identity, lambda x, y: (y, x), lambda x, y: (240.0 - x, y)], ids=["plain", "swapped", "mirrored"])
def test_a_stroke_running_past_the_wall_no_longer_ends_it(name, tf):
    rows = thin(tf, **LOOKALIKES[name])
    assert _near_closed(_build(rows), tf)                      # the behaviour the switch removes
    assert not _near_closed(_strict(rows), tf)


@pytest.mark.parametrize("color", [GREY, PINK, BLUE], ids=["grey", "pink", "blue"])
@pytest.mark.parametrize("end", ["low", "high"])
def test_a_short_stroke_that_is_not_wall_ink_no_longer_ends_a_wall(color, end):
    rows = thin(**{f"{end}_color": color})
    assert _near_closed(_build(rows))
    assert not _near_closed(_strict(rows))


# ------------------------------------------------------------------------------------------------ the far face line of one doorway

@pytest.mark.parametrize("tf", [identity, lambda x, y: (x - 12.5, y + 40.0), lambda x, y: (y, x), lambda x, y: (240.0 - x, y),
                                lambda x, y: (x, 130.0 - y)],
                         ids=["plain", "translated", "axes_swapped", "mirrored_across", "mirrored_along"])
def test_jamb_strokes_reach_a_far_face_line_where_the_door_swing_is(tf):
    result = _strict(thick(tf))
    assert _near_closed(result, tf)
    assert any(c.kind == KIND_SWING for c in result.closures)
    assert _boxes(result) == _boxes(_build(thick(tf)))


def test_without_a_swing_on_the_far_face_the_strokes_are_too_long():
    rows = thick(doors=())
    assert _near_closed(_build(rows))
    assert not _near_closed(_strict(rows))


def test_a_far_swing_wider_than_this_interruption_is_another_opening():
    rows = thick(far=((FAR_BAR, 26.0, 94.0),), doors=((111.5, 26.0, 94.0, 1.0),))
    result = _strict(rows)
    assert any(c.kind == KIND_SWING for c in result.closures)   # that door is still its own closure
    assert _near_closed(_build(rows)) and not _near_closed(result)


@pytest.mark.parametrize("lo,hi", [(30.2, 90.0), (30.0, 89.8), (34.0, 90.0), (29.7, 90.3)])
def test_a_far_swing_inside_this_interruption_is_the_same_doorway(lo, hi):
    rows = thick(far=((FAR_BAR, lo, hi),), doors=((111.5, lo, hi, 1.0),))
    assert _near_closed(_strict(rows))


@pytest.mark.parametrize("lo,hi", [(29.6, 90.0), (30.0, 90.4), (26.0, 86.0)])
def test_a_far_swing_reaching_past_either_end_is_not_this_doorway(lo, hi):
    rows = thick(far=((FAR_BAR, lo, hi),), doors=((111.5, lo, hi, 1.0),))
    assert _near_closed(_build(rows)) and not _near_closed(_strict(rows))


def test_a_swing_in_a_wall_of_the_other_direction_is_not_a_far_face():
    rows = thick(far=(), doors=(), low=(98.0, 105.0))
    rows += [_bar(2.0, 104.0, 40.0, 105.5, identity), _bar(80.0, 104.0, 96.0, 105.5, identity)]
    rows += _swing((80.0, 105.5), (80.0, 145.5), (40.0, 105.5), identity)
    result = _strict(rows)
    assert any(c.kind == KIND_SWING and c.horizontal for c in result.closures)
    assert _near_closed(_build(rows)) and not _near_closed(result)


def test_a_far_face_too_deep_on_its_own_does_not_cancel_a_near_enough_one():
    rows = thick(far=((FAR_BAR, LO, HI), ((125.0, 126.5), LO, HI)), doors=((111.5, LO, HI, 1.0), (126.5, LO, HI, 1.0)))
    assert _near_closed(_strict(rows))


def test_a_far_face_just_within_a_third_of_the_width_is_this_wall():
    # 18.5 pt deep for a 60 pt opening: inside one third (20 pt)
    rows = thick(low=(98.0, 115.7), far=(((115.0, 116.5), LO, HI),), doors=((116.5, LO, HI, 1.0),))
    assert _near_closed(_strict(rows))


def test_a_far_face_more_than_a_third_of_the_width_away_is_not_this_wall():
    rows = thick(low=(98.0, 125.7), far=(((125.0, 126.5), LO, HI),), doors=((126.5, LO, HI, 1.0),))
    assert _near_closed(_build(rows))
    assert not _near_closed(_strict(rows))


def test_two_far_faces_that_together_are_too_deep_leave_only_the_wall_band():
    rows = thick(far=((FAR_BAR, LO, HI), ((85.0, 86.5), LO, HI)), doors=((111.5, LO, HI, 1.0), (85.0, LO, HI, -1.0)))
    result = _strict(rows)
    assert sum(c.kind == KIND_SWING for c in result.closures) == 2
    assert _near_closed(_build(rows)) and not _near_closed(result)


def test_a_stroke_past_the_far_face_line_does_not_count():
    rows = thick(low=(98.0, 112.4))
    assert _near_closed(_build(rows))
    assert not _near_closed(_strict(rows))


def test_the_far_face_does_not_let_a_grey_stroke_in():
    rows = thick()
    rows[4] = _cap(LO, (98.0, 110.7), identity, color=GREY)     # the near low cap
    assert not _near_closed(_strict(rows))


# ------------------------------------------------------------------------------------------------ invariance, replay and the switch

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_input_order_does_not_change_the_closures(seed):
    for rows in (thin(), thick(), thin(low=(98.0, 130.0))):
        shuffled = list(rows)
        random.Random(seed).shuffle(shuffled)
        assert _boxes(_strict(shuffled)) == _boxes(_strict(rows))


def test_unrelated_content_elsewhere_changes_nothing_near_the_wall():
    extra = [_bar(300.0, 10.0 + 12.0 * k, 301.5, 18.0 + 12.0 * k, identity) for k in range(6)]
    for rows in (thin(), thick(), thin(low=(98.0, 130.0))):
        before = [b for b in _boxes(_strict(rows)) if b[2][0] < 200.0]
        after = [b for b in _boxes(_strict(rows + extra)) if b[2][0] < 200.0]
        assert after == before


def test_building_never_mutates_the_rows_and_replays_deterministically():
    rows = thick()
    before = copy.deepcopy(rows)
    first, second = _strict(rows), _strict(rows)
    assert [(r["color"], r["fill"], [tuple(i[1:]) for i in r["items"]]) for r in rows] == \
        [(r["color"], r["fill"], [tuple(i[1:]) for i in r["items"]]) for r in before]
    assert first == second


def test_switched_off_is_the_same_as_not_passing_it():
    for rows in (thin(), thick(), thin(**LOOKALIKES["alcove_mouth_between_two_returns"])):
        assert _build(rows, jamb_caps_must_be_wall_ends=False) == _build(rows)


@pytest.mark.parametrize("value", [1, 0, None, "yes"])
def test_the_switch_is_an_explicit_boolean(value):
    with pytest.raises(ValueError, match="jamb_caps_must_be_wall_ends must be an explicit boolean"):
        _build(thin(), jamb_caps_must_be_wall_ends=value)


def test_the_switch_requires_the_dark_painted_path():
    with pytest.raises(ValueError, match="jamb_caps_must_be_wall_ends requires dark_painted_wall_source"):
        build_layered_wall_doorway_room_rings(thin(), source_sha256=SHA, page_index=0, jamb_caps_must_be_wall_ends=True)


def test_the_byte_entry_point_forwards_the_switch(monkeypatch):
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    seen = []
    monkeypatch.setattr(ring, "build_layered_wall_doorway_room_rings", lambda drawings, **kw: seen.append(kw) or "built")
    sha = hashlib.sha256(payload).hexdigest()
    assert ring.build_from_pdf_bytes(payload, source_sha256=sha, page_index=0) == "built"
    assert ring.build_from_pdf_bytes(payload, source_sha256=sha, page_index=0, dark_painted_wall_source=True,
                                     jamb_caps_must_be_wall_ends=True) == "built"
    assert [kw["jamb_caps_must_be_wall_ends"] for kw in seen] == [False, True]
