"""Synthetic proof for the shadow-only door-swing figure binding (owner rule: a figure inside the swing drawing belongs to the door)."""
from __future__ import annotations

import copy
import math
import random

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_door_swing_figure_binding_shadow as sw
from pb_door_swing_figure_binding_shadow import FigureWord, OpeningEnds, SwingArc, bind_figures_to_swings, hinge_corners

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED


def quarter(hx, hy, sx, sy, r, arc_id="a1"):
    """Quarter arc hinged at (hx, hy): the closed leaf runs along x towards sx, the open leaf along y towards sy."""
    k = r / math.sqrt(2.0)
    return SwingArc(arc_id, hx + sx * r, hy, hx, hy + sy * r, hx + sx * k, hy + sy * k, ("rcpt-" + arc_id,))


def opening(oid, hx, hy, sx, length, thickness=2.5, off=1.0):
    return OpeningEnds(oid, hx, hy + off, hx + sx * length, hy + off, thickness, ("rcpt-" + oid,))


def fig(wid, text, cx, cy, w=14.0, h=8.0, trust="corroborated"):
    return FigureWord(wid, text, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, trust, ("rcpt-" + wid,))


def base():
    return ([opening("o1", 100.0, 100.0, 1, 30.0)], [quarter(100.0, 100.0, 1, 1, 30.0)], [fig("w1", "870", 110.0, 112.0)])


def run(openings=None, arcs=None, figures=None, enabled=True):
    o, a, f = base()
    return bind_figures_to_swings(o if openings is None else openings, a if arcs is None else arcs,
                                  f if figures is None else figures, enabled=enabled)


# ------------------------------------------------------------------------------------------------ positives
def test_a_figure_inside_the_swing_binds_to_the_door():
    (r,) = run()
    assert r.status is CAND and r.is_candidate and r.reason_codes == (sw.SWING_BINDING_CANDIDATE,)
    assert r.figure_word_id == "w1" and r.figure_text == "870" and r.printed_figure_value == 870.0
    assert r.swing_arc_id == "a1" and r.hinge == (100.0, 100.0) and r.text_trust == "corroborated"
    assert set(r.source_observation_ids) == {"rcpt-w1", "rcpt-a1", "rcpt-o1"}
    assert r.status is not EvidenceResolutionStatus.CORROBORATED                  # a check, never an authority


def test_thousands_separator_figures_parse_and_non_figure_words_are_ignored():
    o, a, _ = base()
    f = [fig("w1", "1,200", 110.0, 112.0), fig("tag", "D1", 120.0, 108.0, w=8.0), fig("note", "ENTRY", 112.0, 120.0)]
    (r,) = bind_figures_to_swings(o, a, f, enabled=True)
    assert r.status is CAND and r.printed_figure_value == 1200.0 and r.figure_word_id == "w1"


def test_the_hinge_can_be_at_either_end_of_the_opening():
    # hinge at the far end: the closed leaf runs back along x
    o = [opening("o1", 130.0, 100.0, -1, 30.0)]
    a = [quarter(130.0, 100.0, -1, 1, 30.0)]
    f = [fig("w1", "870", 120.0, 112.0)]
    (r,) = bind_figures_to_swings(o, a, f, enabled=True)
    assert r.status is CAND and r.hinge == (130.0, 100.0)


def test_the_swing_may_open_to_either_side_of_the_wall():
    o = [opening("o1", 100.0, 100.0, 1, 30.0)]
    a = [quarter(100.0, 100.0, 1, -1, 30.0)]
    f = [fig("w1", "870", 110.0, 88.0)]
    assert bind_figures_to_swings(o, a, f, enabled=True)[0].status is CAND


def test_the_leaf_may_be_shorter_than_the_opening_by_up_to_the_wall_thickness():
    o = [opening("o1", 100.0, 100.0, 1, 32.0)]                       # clear opening 32, leaf 30, thickness 2.5
    assert bind_figures_to_swings(o, base()[1], base()[2], enabled=True)[0].status is CAND
    o = [opening("o1", 100.0, 100.0, 1, 33.0)]                       # 3.0 > 2.5: not this door's leaf
    r = bind_figures_to_swings(o, base()[1], base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.NO_HINGED_SWING,)


def test_two_records_of_one_physical_door_share_its_figure():
    o = [opening("o1", 100.0, 100.0, 1, 30.0), opening("o2", 100.0, 100.0, 1, 29.0, off=1.6)]
    out = bind_figures_to_swings(o, base()[1], base()[2], enabled=True)
    assert [r.status for r in out] == [CAND, CAND] and {r.figure_word_id for r in out} == {"w1"}


# ------------------------------------------------------------------------------------------------ the hinge and the leaf
def test_the_hinge_is_the_arc_centre_not_the_opposite_corner():
    arc = quarter(100.0, 100.0, 1, 1, 30.0)
    assert hinge_corners(arc) == ((100.0, 100.0),)                         # the opposite corner is not one radius from the midpoint
    flipped = SwingArc("flip", arc.sx, arc.sy, arc.ex, arc.ey, 130.0 - 30.0 / math.sqrt(2.0), 130.0 - 30.0 / math.sqrt(2.0))
    assert hinge_corners(flipped) == ((130.0, 130.0),)                      # an arc bulging the other way is centred on the other corner
    assert hinge_corners(SwingArc("e", 0.0, 0.0, 30.0, 20.0, 20.0, 5.0)) == ()   # not square: an ellipse, not a quarter circle


def test_the_opposite_corner_is_not_a_hinge():
    # an opening of the same length lying at the opposite corner of the arc's square does not own the swing
    o = [opening("far", 130.0, 130.0, -1, 30.0)]
    assert bind_figures_to_swings(o, base()[1], base()[2], enabled=True)[0].reason_codes == (sw.NO_HINGED_SWING,)


def test_a_swing_not_hinged_at_the_opening_abstains():
    o = [opening("o1", 100.0, 100.0 + 5.0, 1, 30.0, off=0.0)]        # hinge 5 pt off the wall line: beyond the thickness
    r = bind_figures_to_swings(o, base()[1], base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.NO_HINGED_SWING,)


def test_a_window_corner_fillet_is_not_a_door_swing():
    o = [opening("win", 100.0, 100.0, 1, 30.0)]
    a = [quarter(100.0, 100.0, 1, 1, 5.0)]                           # a small repeated radius at the window corner
    f = [fig("w1", "870", 102.0, 103.0, w=3.0, h=2.0)]
    assert bind_figures_to_swings(o, a, f, enabled=True)[0].reason_codes == (sw.NO_HINGED_SWING,)


def test_a_double_leaf_door_with_two_half_radius_arcs_abstains():
    o = [opening("dbl", 100.0, 100.0, 1, 30.0)]
    a = [quarter(100.0, 100.0, 1, 1, 15.0, "a1"), quarter(130.0, 100.0, -1, 1, 15.0, "a2")]
    assert bind_figures_to_swings(o, a, base()[2], enabled=True)[0].reason_codes == (sw.NO_HINGED_SWING,)


def test_two_full_length_swings_hinged_at_both_ends_abstain():
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a1"), quarter(130.0, 100.0, -1, 1, 30.0, "a2")]
    r = bind_figures_to_swings(base()[0], a, base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.MULTIPLE_HINGED_SWINGS,)


def test_no_swing_at_all_abstains_even_with_a_figure_beside_the_door():
    r = bind_figures_to_swings(base()[0], [], base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.NO_HINGED_SWING,)


def test_one_swing_painted_twice_is_one_swing_with_both_receipts():
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a2"), quarter(100.0, 100.0, 1, 1, 30.0, "a1")]
    (r,) = bind_figures_to_swings(base()[0], a, base()[2], enabled=True)
    assert r.status is CAND and r.swing_arc_id == "a1" and {"rcpt-a1", "rcpt-a2"} <= set(r.source_observation_ids)


def test_a_repainted_swing_does_not_make_the_figure_sit_in_two_swings():
    o = [opening("o1", 100.0, 100.0, 1, 30.0), opening("o2", 100.0, 100.0, 1, 29.0, off=1.6)]
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a1"), quarter(100.0, 100.0, 1, 1, 30.0, "a2")]
    out = bind_figures_to_swings(o, a, base()[2], enabled=True)
    assert [r.status for r in out] == [CAND, CAND]


def test_swings_that_differ_beyond_the_signature_tolerance_stay_distinct():
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a1"), quarter(100.0, 100.0, 1, 1, 30.4, "a2")]       # 0.4 pt larger radius
    r = bind_figures_to_swings(base()[0], a, base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.MULTIPLE_HINGED_SWINGS,)


def test_an_opening_thicker_than_it_is_long_accepts_no_arc():
    # the wall thickness is the tolerance; a thickness as large as the length would accept any arc, so it abstains
    o = [OpeningEnds("o1", 100.0, 101.0, 130.0, 101.0, 30.0)]
    r = bind_figures_to_swings(o, base()[1], base()[2], enabled=True)[0]
    assert r.status is ABST and r.reason_codes == (sw.IMPLAUSIBLE_OPENING,)
    r = bind_figures_to_swings([OpeningEnds("o1", 100.0, 101.0, 130.0, 101.0, 29.9)], base()[1], base()[2], enabled=True)[0]
    assert r.reason_codes != (sw.IMPLAUSIBLE_OPENING,)


# ------------------------------------------------------------------------------------------------ the figure
def test_a_figure_outside_the_swing_does_not_bind():
    r = run(figures=[fig("w1", "870", 110.0, 150.0)])[0]
    assert r.status is ABST and r.reason_codes == (sw.NO_FIGURE_IN_SWING,)


def test_the_square_corner_beyond_the_arc_is_not_inside_the_swing():
    # inside the arc's bounding square but farther than one radius from the hinge: outside the quarter disc
    r = run(figures=[fig("w1", "870", 127.0, 127.0, w=2.0, h=2.0)])[0]
    assert r.status is ABST and r.reason_codes == (sw.NO_FIGURE_IN_SWING,)


def test_the_mirror_quadrant_is_not_inside_the_swing():
    r = run(figures=[fig("w1", "870", 110.0, 88.0)])[0]                # the other side of the wall: the leaf never sweeps it
    assert r.status is ABST and r.reason_codes == (sw.NO_FIGURE_IN_SWING,)


def test_a_figure_straddling_the_arc_abstains():
    r = run(figures=[fig("w1", "870", 125.0, 118.0, w=14.0, h=8.0)])[0]  # far corner is beyond one radius
    assert r.status is ABST and r.reason_codes == (sw.FIGURE_STRADDLES_SWING,)


def test_a_figure_with_exactly_one_corner_outside_the_disc_is_a_straddler():
    r = run(figures=[FigureWord("w1", "870", 112.0, 114.0, 123.0, 124.5, "corroborated", ("rcpt-w1",))])[0]   # 3 of 4 corners inside
    assert r.status is ABST and r.reason_codes == (sw.FIGURE_STRADDLES_SWING,)


def test_an_inside_figure_with_a_straddler_is_ambiguous():
    f = [fig("w1", "870", 110.0, 112.0), fig("w2", "900", 125.0, 118.0)]
    r = run(figures=f)[0]
    assert r.status is ABST and r.reason_codes == (sw.FIGURE_STRADDLES_SWING,)


def test_two_figures_inside_the_swing_abstain_even_when_equal():
    f = [fig("w1", "870", 108.0, 108.0, w=8.0), fig("w2", "870", 114.0, 118.0, w=8.0)]
    r = run(figures=f)[0]
    assert r.status is ABST and r.reason_codes == (sw.MULTIPLE_FIGURES_IN_SWING,)


def test_a_figure_inside_two_hinged_swings_abstains_for_both_doors():
    # two doors whose swings overlap, with one figure in the overlap
    o = [opening("o1", 100.0, 100.0, 1, 30.0), opening("o2", 112.0, 100.0, 1, 30.0)]
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a1"), quarter(112.0, 100.0, 1, 1, 30.0, "a2")]
    f = [fig("w1", "870", 118.0, 108.0, w=6.0, h=4.0)]
    out = bind_figures_to_swings(o, a, f, enabled=True)
    assert [r.reason_codes for r in out] == [(sw.FIGURE_IN_MULTIPLE_SWINGS,)] * 2


def test_the_binding_never_depends_on_the_figure_value():
    for text in ("870", "1,200", "600", "999"):
        r = run(figures=[fig("w1", text, 110.0, 112.0)])[0]
        assert r.status is CAND and r.figure_word_id == "w1"
    # a word that is not figure-like is not a width at all
    assert run(figures=[fig("w1", "D1", 110.0, 112.0)])[0].reason_codes == (sw.NO_FIGURE_IN_SWING,)


def test_text_trust_is_carried_and_never_changes_the_binding():
    assert run(figures=[fig("w1", "870", 110.0, 112.0, trust="raw_unverified")])[0].text_trust == "raw_unverified"
    assert run(figures=[fig("w1", "870", 110.0, 112.0, trust="")])[0].text_trust == ""
    assert run(figures=[fig("w1", "870", 110.0, 112.0, trust="whatever")])[0].text_trust == ""


def test_a_rotated_figure_box_is_handled_by_its_own_extent():
    r = run(figures=[fig("w1", "1,200", 110.0, 112.0, w=8.0, h=18.0)])[0]    # printed vertically: tall narrow box
    assert r.status is CAND


# ------------------------------------------------------------------------------------------------ metamorphic
def _xform(o, a, f, point, scale=1.0):
    def p(x, y):
        return point(x, y)

    oo = [OpeningEnds(x.opening_id, *p(x.ax, x.ay), *p(x.bx, x.by), x.thickness * scale, x.receipt_ids) for x in o]
    aa = [SwingArc(x.arc_id, *p(x.sx, x.sy), *p(x.ex, x.ey), *p(x.mx, x.my), x.receipt_ids) for x in a]
    ff = []
    for x in f:
        (ax, ay), (bx, by) = p(x.x0, x.y0), p(x.x1, x.y1)
        ff.append(FigureWord(x.word_id, x.text, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), x.text_trust, x.receipt_ids))
    return oo, aa, ff


@pytest.mark.parametrize("name,point,scale", [
    ("translate", lambda x, y: (x + 1234.5, y - 987.25), 1.0),
    ("rotate90", lambda x, y: (-y, x), 1.0),
    ("rotate180", lambda x, y: (-x, -y), 1.0),
    ("mirror", lambda x, y: (-x, y), 1.0),
    ("scale", lambda x, y: (3.0 * x, 3.0 * y), 3.0),
    ("rotate_scale_translate", lambda x, y: (-2.0 * y + 50.0, 2.0 * x - 7.0), 2.0),
])
def test_rigid_and_similarity_transforms_do_not_change_the_binding(name, point, scale):
    o, a, f = _xform(*base(), point, scale)
    (r,) = bind_figures_to_swings(o, a, f, enabled=True)
    assert r.status is CAND and r.figure_word_id == "w1" and r.swing_arc_id == "a1", name


def test_input_order_does_not_change_the_result():
    o = [opening("o1", 100.0, 100.0, 1, 30.0), opening("o2", 300.0, 100.0, 1, 24.0)]
    a = [quarter(100.0, 100.0, 1, 1, 30.0, "a1"), quarter(300.0, 100.0, 1, 1, 24.0, "a2")]
    f = [fig("w1", "870", 110.0, 112.0), fig("w2", "720", 308.0, 110.0), fig("w3", "450", 600.0, 600.0)]
    ref = bind_figures_to_swings(o, a, f, enabled=True)
    rng = random.Random(11)
    for _ in range(25):
        oo, aa, ff = o[:], a[:], f[:]
        rng.shuffle(oo), rng.shuffle(aa), rng.shuffle(ff)
        out = bind_figures_to_swings(oo, aa, ff, enabled=True)
        assert out == ref and [r.result_id for r in out] == [r.result_id for r in ref]


def test_unrelated_content_does_not_change_the_binding():
    ref = run()[0]
    o, a, f = base()
    far_arcs = [quarter(1000.0 + 90 * i, 1000.0, 1, 1, 30.0, "far%d" % i) for i in range(5)]
    far_figs = [fig("far%d" % i, "870", 5000.0 + 20 * i, 5000.0) for i in range(5)]
    far_open = [opening("fo%d" % i, 2000.0 + 90 * i, 2000.0, 1, 24.0) for i in range(3)]
    out = bind_figures_to_swings(o + far_open, a + far_arcs, f + far_figs, enabled=True)
    mine = next(r for r in out if r.opening_id == "o1")
    assert (mine.status, mine.figure_word_id, mine.swing_arc_id) == (ref.status, ref.figure_word_id, ref.swing_arc_id)


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    o, a, f = base()
    snap = copy.deepcopy((o, a, f))
    r1 = bind_figures_to_swings(o, a, f, enabled=True)
    r2 = bind_figures_to_swings(o, a, f, enabled=True)
    assert r1 == r2 and [r.result_id for r in r1] == [r.result_id for r in r2] and (o, a, f) == snap


def test_result_identity_changes_with_the_figure_the_swing_and_the_receipts():
    a = run()[0]
    b = run(figures=[fig("w9", "870", 110.0, 112.0)])[0]
    c = run(arcs=[quarter(100.0, 100.0, 1, 1, 30.0, "a9")])[0]
    d = run(figures=[FigureWord("w1", "870", 103.0, 108.0, 117.0, 116.0, "corroborated", ("other",))])[0]
    assert len({a.result_id, b.result_id, c.result_id, d.result_id}) == 4


# ------------------------------------------------------------------------------------------------ switches and input safety
def test_default_off_and_strict_enabled_flag():
    o, a, f = base()
    assert bind_figures_to_swings(o, a, f) == ()
    assert bind_figures_to_swings(o, a, f, enabled=False) == ()
    for bad in (1, "yes", None):
        with pytest.raises(ValueError):
            bind_figures_to_swings(o, a, f, enabled=bad)


def test_non_finite_and_degenerate_input_fails_closed():
    nan, inf = float("nan"), float("inf")
    assert run(figures=[FigureWord("w1", "870", nan, 0.0, 1.0, 1.0)])[0].reason_codes == (sw.INVALID_INPUT,)
    assert run(arcs=[SwingArc("a1", 0.0, 0.0, inf, 1.0, 0.5, 0.5)])[0].reason_codes == (sw.INVALID_INPUT,)
    assert run(arcs=[SwingArc("a1", 0.0, 0.0, 1.0, 1.0, nan, 0.5)])[0].reason_codes == (sw.INVALID_INPUT,)
    assert run(openings=[OpeningEnds("o1", 0.0, 0.0, 0.0, 0.0, 2.5)])[0].reason_codes == (sw.INVALID_INPUT,)      # zero length
    assert run(openings=[OpeningEnds("o1", 0.0, 0.0, 10.0, 0.0, 0.0)])[0].reason_codes == (sw.INVALID_INPUT,)     # no thickness
    assert run(figures=[FigureWord("w1", "870", 5.0, 0.0, 1.0, 1.0)])[0].reason_codes == (sw.INVALID_INPUT,)       # inverted box


def test_duplicate_identities_fail_closed():
    o, a, f = base()
    assert bind_figures_to_swings(o + o, a, f, enabled=True)[0].reason_codes == (sw.INVALID_INPUT,)
    assert bind_figures_to_swings(o, a + a, f, enabled=True)[0].reason_codes == (sw.INVALID_INPUT,)
    assert bind_figures_to_swings(o, a, f + f, enabled=True)[0].reason_codes == (sw.INVALID_INPUT,)


def test_a_non_square_arc_is_never_a_swing():
    o, f = base()[0], base()[2]
    a = [SwingArc("a1", 130.0, 100.0, 100.0, 120.0, 122.0, 112.0)]     # 30 x 20: an elliptical arc
    assert bind_figures_to_swings(o, a, f, enabled=True)[0].reason_codes == (sw.NO_HINGED_SWING,)


# ------------------------------------------------------------------------------------------------ isolation
def test_module_is_isolated_from_authority_modules():
    import ast
    import pathlib
    text = pathlib.Path(sw.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "dataclasses", "math", "re", "typing", "pb_migration_contracts"}
    root = pathlib.Path(sw.__file__).parent
    importers = sorted(p.name for p in root.glob("pb_*.py") if p.name != pathlib.Path(sw.__file__).name
                       and "pb_door_swing_figure_binding_shadow" in p.read_text(encoding="utf-8", errors="ignore"))
    assert importers == ["pb_door_swing_figure_binding_adapter.py"], importers          # nothing in production reads it
