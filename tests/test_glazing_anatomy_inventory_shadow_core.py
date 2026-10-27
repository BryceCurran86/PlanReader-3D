"""Pure-core proofs for the glazing anatomy inventory shadow (no PDF, no producer unless stated)."""
from __future__ import annotations

import random
from dataclasses import replace

import pytest

import pb_glazing_anatomy_inventory_shadow as A
from pb_migration_contracts import EvidenceResolutionStatus

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
OWN = A.AnatomyOwnership("doc", "rev", "snap", "a" * 64, "7")
Q = 0.24
W = 0.48
G1, G2, G3, G4, G5, G6, G7, G8 = A.GATE_NAMES
BIG = A.ViewportRef("view_plan", (-5000.0, -5000.0, 9000.0, 9000.0))


class Page:
    """A page of thin black strokes, drawn the way a CAD export draws a glazing strip."""

    def __init__(self):
        self.ink: list = []
        self._n = 0

    def line(self, a, b, width=W, double=False, black=True, opaque=True):
        for _ in range(2 if double else 1):
            self._n += 1
            self.ink.append(A.InkSegment(f"i{self._n}", float(a[0]), float(a[1]), float(b[0]), float(b[1]),
                                         width, black, opaque))

    def along(self, axis, a, b, off, width=W, double=False, split=False, **kw):
        pt = (lambda t: (t, off)) if axis == "H" else (lambda t: (off, t))
        if split:
            mid = (a + b) / 2.0
            self.line(pt(a), pt(mid), width, double, **kw)
            self.line(pt(mid), pt(b), width, double, **kw)
        else:
            self.line(pt(a), pt(b), width, double, **kw)

    def across(self, axis, t, o_a, o_b, width=W, **kw):
        pt = (lambda t_, o: (t_, o)) if axis == "H" else (lambda t_, o: (o, t_))
        self.line(pt(t, o_a), pt(t, o_b), width, **kw)

    def strip(self, axis, lo, n0, *, panels=3, frame_len=204.0, post=2.64, depth=5.52, pane=(2.4, 3.12), width=W,
              end_posts=True, drop_pane_ticks=(), drop_cell_edges=(), split=False, double=True, pane_width=None,
              drop_end_posts=()):
        pane_width = width if pane_width is None else pane_width
        panel_len = (frame_len - (panels + 1) * post) / panels
        pos = lo
        for k in range(panels + 1):
            skip = ((not end_posts and k in (0, panels)) or (k == 0 and "lo" in drop_end_posts)
                    or (k == panels and "hi" in drop_end_posts))
            if not skip:
                for off in (n0, n0 + depth):
                    self.along(axis, pos, pos + post, off, width)
            pos += post
            if k == panels:
                break
            a, b = pos, pos + panel_len
            for off in (n0, n0 + depth):
                self.along(axis, a, b, off, width, double=double, split=split)
            for side, edge in (("lo", a), ("hi", b)):
                if (k, side) not in drop_cell_edges:
                    self.across(axis, edge, n0, n0 + depth, width)
            for off in (n0 + pane[0], n0 + pane[1]):
                self.along(axis, a, b, off, pane_width, split=split)
            for side, edge in (("lo", a), ("hi", b)):
                if (k, side) not in drop_pane_ticks:
                    self.across(axis, edge, n0 + pane[0], n0 + pane[1], pane_width)
            pos += panel_len
        return {"axis": axis, "frame": (lo, lo + frame_len), "band": (n0, n0 + depth)}


def run(page, viewports=(BIG,), ownership=OWN, ink=None, quantum=Q, **kw):
    return A.inventory_glazing_anatomy(ownership=ownership, ink=page.ink if ink is None else ink,
                                       viewports=viewports, coordinate_quantum_pt=quantum, **kw)


def by_pair(inv, p, q, tol=1e-6):
    return [c for c in inv.candidates if abs(c.pair[0] - p) < tol and abs(c.pair[1] - q) < tol]


def valid(**kw):
    page = Page()
    page.strip("H", 100.0, 300.0, **kw)
    return page


# --- (a) a fully valid strip ------------------------------------------------------------------------


def test_a_fully_valid_three_panel_strip_passes_every_gate_and_chains_into_one_strip():
    inv = run(valid(panels=3))
    assert inv.status is CAND and inv.reason_codes == (A.ACCEPTED_CELLS_PRESENT,)
    (strip,) = inv.strips
    assert strip.axis == "H" and strip.panel_count == 3 and strip.extent_complete and strip.full_anatomy
    assert strip.band == (300.0, 305.52) and strip.along[0] == pytest.approx(102.64)
    assert strip.merged_rule_copy_agrees is True and strip.viewport_id == "view_plan"
    assert strip.end_post_widths == pytest.approx((2.64, 2.64)) and len(strip.inner_post_widths) == 2
    pane = [c for c in inv.candidates if c.in_merged_inventory]
    assert len(pane) == 3 and all(c.first_failed_gate is None for c in pane)
    assert all(state == A.PASSED for c in pane for _, state in c.gates)
    assert all(c.pair == pytest.approx((302.4, 303.12)) and c.frame_offsets == (300.0, 305.52) for c in pane)
    assert all(c.rebates == pytest.approx((2.4, 2.4)) and c.cross_closed == (True, True) for c in pane)
    assert all(c.strip_id == strip.strip_id and c.chain_panel_count == 3 for c in pane)
    assert not inv.near_misses
    hist = dict(inv.first_failed_gate_histogram)
    # the two inner posts are closed boxes in the TRANSPOSED axis (the cell-end strokes are the pair, the frame
    # lines are the ticks); the frame is far deeper there than the post is long, which is exactly what g3 rejects
    posts = [c for c in inv.candidates if c.first_failed_gate == G3]
    assert len(posts) == 2 and all(c.axis == "V" and c.along == (300.0, 305.52) for c in posts)
    assert hist[A.ALL_GATES_PASSED] == 3 and hist[G3] == 2 and sum(hist.values()) == 5
    # the frame outline around each pane is a container, not a candidate
    assert inv.container_box_count == 3 and len(inv.candidates) == 5


def test_the_gate_set_is_fixed_ordered_and_documented():
    assert A.GATE_NAMES == (
        "g1_pair_closed_by_end_ticks", "g2_enclosing_frame_lines_exist", "g3_frame_deeper_than_cell_is_long",
        "g4_pair_narrower_than_each_rebate", "g5_pair_centred", "g6_cell_closed_across_full_depth",
        "g7_chains_with_neighbour", "g8_end_posts_both_present")
    assert set(A.GATE_DESCRIPTIONS) == set(A.GATE_NAMES)
    assert "PASSES" in A.GATE_DESCRIPTIONS[G3]


def test_a_vertical_strip_is_found_with_the_same_gates():
    page = Page()
    page.strip("V", 50.0, 400.0, panels=3)
    inv = run(page)
    assert [(s.axis, s.panel_count) for s in inv.strips] == [("V", 3)]


# --- (b) a cell missing one end tick -----------------------------------------------------------------


def test_a_cell_missing_one_pane_end_tick_fails_g1_and_is_retained_with_its_geometry():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=3, drop_pane_ticks={(1, "hi")})
    inv = run(page)
    half = [c for c in by_pair(inv, 302.4, 303.12) if c.closure == A.CLOSURE_HI_MISSING]
    assert len(half) == 1
    c = half[0]
    assert c.first_failed_gate == G1 and not c.in_merged_inventory and not c.near_miss
    assert [s for _, s in c.gates] == [A.FAILED] + [A.NOT_EVALUATED] * 7
    assert c.along == pytest.approx((169.76, 234.24)) and c.detail == (A.CLOSURE_HI_MISSING,)
    assert c.frame_offsets is None
    # its frame outline is now the innermost closed box there and fails g2 (nothing encloses it)
    frame = [c for c in by_pair(inv, 300.0, 305.52) if c.along[0] == pytest.approx(169.76)]
    assert len(frame) == 1 and frame[0].first_failed_gate == G2
    # the other two panels are still accepted, as two separate one-panel strips
    assert sorted(s.panel_count for s in inv.strips) == [1, 1]


def test_a_cell_missing_the_lo_tick_is_the_mirror_case():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=1, frame_len=70.0, drop_pane_ticks={(0, "lo")})
    inv = run(page)
    (half,) = [c for c in by_pair(inv, 302.4, 303.12)]
    assert half.closure == A.CLOSURE_LO_MISSING and half.first_failed_gate == G1
    assert inv.status is ABST and inv.reason_codes == (A.NO_ACCEPTED_CELL,) and inv.strips == ()


# --- (c) unequal rebates and a wide pair ---------------------------------------------------------------


def test_an_off_centre_pair_passes_g4_and_fails_g5():
    inv = run(valid(panels=1, frame_len=70.0, pane=(1.5, 2.22)))
    (c,) = by_pair(inv, 301.5, 302.22)
    assert c.first_failed_gate == G5 and c.detail == ("pair_not_centred",)
    assert [s for _, s in c.gates] == [A.PASSED] * 4 + [A.FAILED] + [A.NOT_EVALUATED] * 3
    assert c.rebates == pytest.approx((1.5, 3.3)) and not c.in_merged_inventory and inv.strips == ()


def test_a_pair_wider_than_a_rebate_fails_g4():
    inv = run(valid(panels=1, frame_len=70.0, pane=(1.0, 4.52)))
    (c,) = by_pair(inv, 301.0, 304.52)
    assert c.first_failed_gate == G4 and c.rebates == pytest.approx((1.0, 1.0))


# --- (d) frame lines that do not cover the cell --------------------------------------------------------


def test_frame_lines_that_do_not_cover_the_cell_fail_g2():
    page = Page()
    a, b = 100.0, 160.0
    for off in (302.4, 303.12):
        page.along("H", a, b, off)
    page.across("H", a, 302.4, 303.12)
    page.across("H", b, 302.4, 303.12)
    for off in (300.0, 305.52):
        page.along("H", a, a + 20.0, off)          # the frame stops short of the cell
    inv = run(page)
    (c,) = inv.candidates
    assert c.first_failed_gate == G2 and set(c.detail) == {"no_enclosing_line_below", "no_enclosing_line_above"}
    assert inv.status is ABST


def test_only_one_side_missing_names_that_side():
    page = Page()
    for off in (302.4, 303.12):
        page.along("H", 100.0, 160.0, off)
    page.across("H", 100.0, 302.4, 303.12)
    page.across("H", 160.0, 302.4, 303.12)
    page.along("H", 90.0, 170.0, 300.0)             # only the lower enclosing line exists
    (c,) = run(page).candidates
    assert c.first_failed_gate == G2 and c.detail == ("no_enclosing_line_above",)


# --- (e) a doubled-ink wall ribbon look-alike and a shallow-cell look-alike --------------------------------


def test_a_doubled_ink_wall_ribbon_is_one_candidate_that_fails_g2():
    page = Page()
    for off in (500.0, 505.52):
        page.along("H", 100.0, 304.0, off, double=True)
    for x in (100.0, 304.0):
        page.across("H", x, 500.0, 505.52)
        page.across("H", x, 500.0, 505.52)          # doubled end strokes too
    inv = run(page)
    (c,) = inv.candidates
    assert c.first_failed_gate == G2 and c.closure == A.CLOSURE_BOTH and not c.in_merged_inventory
    assert inv.strips == () and inv.status is ABST and not inv.near_misses
    assert dict(inv.first_failed_gate_histogram)[G2] == 1


def test_a_cell_shorter_than_the_frame_is_deep_fails_g3():
    page = Page()
    for off in (300.0, 305.52):
        page.along("H", 100.0, 110.0, off)
    for off in (302.4, 303.12):
        page.along("H", 103.0, 106.0, off)
    page.across("H", 103.0, 302.4, 303.12)
    page.across("H", 106.0, 302.4, 303.12)
    (c,) = run(page).candidates
    assert c.first_failed_gate == G3 and c.detail == ("frame_not_shallower_than_cell_is_long",)


def test_a_closed_pair_not_longer_than_it_is_thick_is_counted_not_enumerated():
    page = Page()
    for off in (300.0, 305.5):
        page.along("H", 101.0, 106.5, off)
    page.across("H", 101.0, 300.0, 305.5)
    page.across("H", 106.5, 300.0, 305.5)             # a 5.5 pt square: not longer than it is thick either way
    inv = run(page)
    assert inv.candidates == () and inv.short_pair_count == 2 and inv.strips == ()


# --- (f) / (g) single-panel cells with and without end posts -------------------------------------------------


def test_a_single_panel_cell_with_end_posts_passes_every_gate():
    inv = run(valid(panels=1, frame_len=70.0))
    (strip,) = inv.strips
    assert strip.panel_count == 1 and strip.extent_complete and strip.full_anatomy
    (c,) = [c for c in inv.candidates if c.in_merged_inventory]
    assert c.first_failed_gate is None and c.chain_panel_count == 1 and c.end_post_widths == pytest.approx((2.64, 2.64))


def test_a_single_panel_cell_without_end_posts_fails_only_g8_and_is_a_near_miss_the_merged_rule_accepts():
    inv = run(valid(panels=1, frame_len=70.0, end_posts=False))
    (strip,) = inv.strips
    assert strip.panel_count == 1 and not strip.extent_complete and not strip.full_anatomy
    assert strip.end_post_widths == (None, None)
    (c,) = [c for c in inv.candidates if c.in_merged_inventory]
    assert c.first_failed_gate == G8 and c.in_merged_inventory and c.near_miss
    assert [s for _, s in c.gates] == [A.PASSED] * 7 + [A.FAILED]
    assert c.detail == ("lo_end_post_missing", "hi_end_post_missing")
    assert inv.near_misses == (c,) and inv.status is CAND


def test_one_missing_end_post_names_that_end_for_every_cell_of_the_strip():
    inv = run(valid(panels=3, drop_end_posts={"hi"}))
    (strip,) = inv.strips
    assert strip.end_post_widths == (pytest.approx(2.64), None) and not strip.extent_complete
    cells = [c for c in inv.candidates if c.in_merged_inventory]
    assert len(cells) == 3 and all(c.first_failed_gate == G8 and c.near_miss for c in cells)
    assert all(c.detail == ("hi_end_post_missing",) for c in cells)
    assert len(inv.near_misses) == 3 and strip.merged_rule_copy_agrees is True


def test_a_cell_missing_a_cell_end_cross_stroke_fails_only_g6_and_is_a_near_miss_the_merged_rule_misses():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=3, drop_cell_edges={(1, "hi")})
    inv = run(page)
    miss = [c for c in inv.candidates if c.first_failed_gate == G6]
    assert len(miss) == 1
    c = miss[0]
    assert c.cross_closed == (True, False) and c.detail == ("hi_cell_end_not_closed_across_depth",)
    assert c.near_miss and not c.in_merged_inventory
    assert [s for _, s in c.gates] == [A.PASSED] * 5 + [A.FAILED] + [A.NOT_EVALUATED] * 2
    assert c in inv.near_misses
    assert sorted(s.panel_count for s in inv.strips) == [1, 1]          # the merged rule would also split here


# --- g7: overlapping cells cannot chain -----------------------------------------------------------------------


def test_two_overlapping_accepted_cells_with_the_same_frame_offsets_fail_g7_and_both_are_kept():
    page = Page()
    for off in (300.0, 311.04):
        page.along("H", 100.0, 230.0, off)
    for lo, hi, p, q in ((110.0, 180.0, 304.8, 306.24), (150.0, 220.0, 304.44, 306.6)):
        for off in (p, q):
            page.along("H", lo, hi, off)
        page.across("H", lo, p, q)
        page.across("H", hi, p, q)
        page.across("H", lo, 300.0, 311.04)
        page.across("H", hi, 300.0, 311.04)
    inv = run(page)
    accepted = [c for c in inv.candidates if c.in_merged_inventory]
    assert len(accepted) == 2 and all(c.first_failed_gate == G7 for c in accepted)
    assert all(c.detail == ("overlaps_accepted_cell_with_the_same_frame_offsets",) for c in accepted)
    assert [s for _, s in accepted[0].gates] == [A.PASSED] * 6 + [A.FAILED, A.NOT_EVALUATED]
    assert sorted(s.panel_count for s in inv.strips) == [1, 1] and not any(s.full_anatomy for s in inv.strips)


# --- stroke widths ----------------------------------------------------------------------------------------------


def test_mixed_stroke_widths_are_kept_apart_and_never_combined_into_a_cell():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=1, frame_len=70.0, width=0.48)
    page.strip("H", 100.0, 500.0, panels=1, frame_len=70.0, width=0.72)
    inv = run(page)
    assert sorted((s.stroke_width, s.panel_count) for s in inv.strips) == [(0.48, 1), (0.72, 1)]
    assert [w.stroke_width for w in inv.width_classes] == [0.48, 0.72]
    assert all(w.strip_count == 1 and w.accepted_cell_count == 1 for w in inv.width_classes)
    for strip in inv.strips:
        assert set(strip.ink_ids) <= {s.ink_id for s in page.ink if s.width == strip.stroke_width}


def test_a_pane_pair_in_another_width_than_its_frame_is_not_combined_with_it():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=1, frame_len=70.0, width=0.48, pane_width=0.96)
    inv = run(page)
    assert inv.strips == () and inv.status is ABST
    wide = [c for c in inv.candidates if c.stroke_width == 0.96]
    assert len(wide) == 1 and wide[0].first_failed_gate == G2
    thin = [c for c in inv.candidates if c.stroke_width == 0.48]
    assert thin and all(c.first_failed_gate == G2 for c in thin)


def test_ink_that_is_not_black_continuous_and_axis_aligned_forms_no_cell():
    base = valid(panels=1, frame_len=70.0)
    assert run(base).strips
    light = Page()
    for s in base.ink:
        light.ink.append(A.InkSegment(s.ink_id, s.x0, s.y0, s.x1, s.y1, s.width, False, s.continuous_opaque))
    assert run(light).candidates == ()
    dashed = [A.InkSegment(s.ink_id, s.x0, s.y0, s.x1, s.y1, s.width, True, False) for s in base.ink]
    assert run(base, ink=dashed).candidates == ()
    tilted = [A.InkSegment(s.ink_id, s.x0, s.y0, s.x1 + 1.0, s.y1 + 1.0, s.width, True, True) for s in base.ink]
    assert run(base, ink=tilted).candidates == ()
    with pytest.raises(ValueError):
        A.InkSegment("x", 0, 0, 1, 1, W, 1, True)


# --- invariance -----------------------------------------------------------------------------------------------------


def _mixed_page():
    page = Page()
    page.strip("H", 100.0, 300.0, panels=3, drop_pane_ticks={(1, "hi")})
    page.strip("H", 100.0, 420.0, panels=1, frame_len=70.0, end_posts=False)
    page.strip("V", 600.0, 200.0, panels=2, frame_len=140.0, drop_cell_edges={(0, "lo")})
    page.strip("H", 100.0, 520.0, panels=1, frame_len=70.0, pane=(1.5, 2.22))
    for off in (700.0, 705.52):
        page.along("H", 100.0, 304.0, off, double=True)
    for x in (100.0, 304.0):
        page.across("H", x, 700.0, 705.52)
    return page


def _summary(inv, dx=0.0, dy=0.0):
    def rel(axis, pair, along):
        a_off, p_off = (dx, dy) if axis == "H" else (dy, dx)
        return (tuple(round(v - p_off, 4) for v in pair), tuple(round(v - a_off, 4) for v in along))

    cands = [(c.axis, c.stroke_width, *rel(c.axis, c.pair, c.along), c.closure, c.first_failed_gate, c.detail,
              c.in_merged_inventory, c.near_miss, c.chain_panel_count) for c in inv.candidates]
    strips = [(s.axis, s.stroke_width, *rel(s.axis, s.band, s.along), s.panel_count, s.extent_complete,
               s.full_anatomy, tuple(round(v, 4) for v in s.panel_lengths)) for s in inv.strips]
    # short_pair_count is an export-dependent diagnostic (it counts tick pairs a stroke export happens to create),
    # not a gate input, so it is deliberately not part of the invariance summary
    return (inv.status, inv.reason_codes, cands, strips, inv.first_failed_gate_histogram, inv.container_box_count,
            [(w.stroke_width, w.candidate_count, w.accepted_cell_count) for w in inv.width_classes])


def test_the_mixed_page_has_every_variant_in_its_histogram():
    inv = run(_mixed_page())
    hist = dict(inv.first_failed_gate_histogram)
    assert hist[G1] >= 1 and hist[G2] >= 1 and hist[G5] == 1 and hist[G6] == 1 and hist[G8] >= 1
    assert sum(hist.values()) == len(inv.candidates)
    assert {c.first_failed_gate for c in inv.near_misses} == {G6, G8}


def test_input_order_and_shuffles_change_nothing_at_all():
    page = _mixed_page()
    base = run(page)
    assert run(page, ink=list(reversed(page.ink))) == base
    for seed in (1, 2, 3):
        shuffled = list(page.ink)
        random.Random(seed).shuffle(shuffled)
        assert run(page, ink=shuffled) == base


def test_replay_is_deterministic_and_stable_ids_carry_the_ownership_root():
    page = _mixed_page()
    first, again = run(page), run(page)
    assert first == again and first.record_id == again.record_id
    other = run(page, ownership=replace(OWN, snapshot_id="other"))
    assert other.record_id != first.record_id
    assert {c.candidate_id for c in other.candidates}.isdisjoint({c.candidate_id for c in first.candidates})
    assert {s.strip_id for s in other.strips}.isdisjoint({s.strip_id for s in first.strips})
    for flag_ownership in (replace(OWN, document_id="d2"), replace(OWN, revision_id="r2"),
                           replace(OWN, source_sha256="b" * 64), replace(OWN, page_id="8")):
        assert run(page, ownership=flag_ownership).record_id != first.record_id


def test_translation_does_not_change_any_gate_result():
    page = _mixed_page()
    dx, dy = 1234.13, -77.77
    moved = [A.InkSegment(s.ink_id, s.x0 + dx, s.y0 + dy, s.x1 + dx, s.y1 + dy, s.width, True, True) for s in page.ink]
    assert _summary(run(page, ink=moved), dx, dy) == _summary(run(page))


def test_collinear_splitting_and_duplicate_ink_change_no_gate_result():
    plain = Page()
    plain.strip("H", 100.0, 300.0, panels=3, double=False)
    split = Page()
    split.strip("H", 100.0, 300.0, panels=3, double=True, split=True)
    twice = Page()
    twice.strip("H", 100.0, 300.0, panels=3, double=False)
    twice.strip("H", 100.0, 300.0, panels=3, double=False)
    ref = _summary(run(plain))
    assert _summary(run(split)) == ref
    assert _summary(run(twice)) == ref
    broken = Page()
    broken.strip("H", 100.0, 300.0, panels=3, double=True, split=True, drop_pane_ticks={(1, "hi")})
    plain_broken = Page()
    plain_broken.strip("H", 100.0, 300.0, panels=3, double=False, drop_pane_ticks={(1, "hi")})
    assert _summary(run(broken)) == _summary(run(plain_broken))


def test_unrelated_content_and_a_larger_viewport_change_nothing():
    page = _mixed_page()
    quiet = run(page)
    noisy = Page()
    noisy.ink = list(page.ink)
    for i in range(300):
        noisy.line((2000.0 + 7.0 * i, 900.0), (2000.0 + 7.0 * i, 920.0 + i % 17))
    loud = run(noisy)
    assert loud.candidates == quiet.candidates and loud.strips == quiet.strips
    wide = run(page, viewports=(A.ViewportRef("big", (-1e6, -1e6, 1e6, 1e6)),))
    assert wide.candidates == quiet.candidates
    assert [s.viewport_id for s in wide.strips] == ["big"] * len(wide.strips)


# --- viewport: reported, never gating ----------------------------------------------------------------------------------


def test_the_viewport_is_reported_per_strip_and_never_gates_the_inventory():
    page = valid(panels=3)
    inside = run(page, viewports=(A.ViewportRef("vp", (0.0, 0.0, 400.0, 400.0)),))
    assert inside.strips[0].viewport_id == "vp" and inside.status is CAND
    for viewports in ((), (A.ViewportRef("far", (1000.0, 1000.0, 2000.0, 2000.0)),),
                      (A.ViewportRef("crop", (0.0, 0.0, 150.0, 400.0)),),
                      (A.ViewportRef("v1", (0.0, 0.0, 400.0, 400.0)), A.ViewportRef("v2", (50.0, 50.0, 390.0, 390.0)))):
        got = run(page, viewports=viewports)
        assert got.status is CAND and got.strips[0].viewport_id is None
        assert got.candidates == inside.candidates


# --- work bounds -----------------------------------------------------------------------------------------------------------


def test_the_ink_budget_abstains_with_a_typed_reason_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(A, "_MAX_INK", 5)
    inv = run(valid(panels=3))
    assert inv.status is ABST and inv.reason_codes == (A.INK_BUDGET_EXCEEDED,)
    assert inv.candidates == () and inv.strips == () and inv.ink_count > 5 and inv.ownership == OWN


def test_the_candidate_budget_abstains_with_a_typed_reason_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(A, "_MAX_CANDIDATES", 2)
    inv = run(valid(panels=3))
    assert inv.status is ABST and inv.reason_codes == (A.CANDIDATE_BUDGET_EXCEEDED,)
    assert inv.candidates == () and inv.strips == ()


# --- self check against the in-module copy of the merged rule ----------------------------------------------------------------


def test_the_in_module_copy_of_the_merged_rule_agrees_on_every_variant():
    inv = run(_mixed_page())
    assert inv.strips and all(s.merged_rule_copy_agrees is True for s in inv.strips)


def test_a_disagreeing_copy_abstains_instead_of_publishing(monkeypatch):
    real = A._reference_panels

    def short(strokes, axis, eq, lines):
        got = real(strokes, axis, eq, lines)
        return set() if got else got

    monkeypatch.setattr(A, "_reference_panels", short)
    inv = run(valid(panels=3))
    assert inv.status is ABST and inv.reason_codes == (A.SELF_CHECK_DISAGREES,)
    assert inv.strips and all(s.merged_rule_copy_agrees is False for s in inv.strips)
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(inv, status=CAND)


def test_a_page_too_large_for_the_quadratic_copy_reports_the_check_as_not_run(monkeypatch):
    monkeypatch.setattr(A, "_SELF_CHECK_MAX_BOXES", 0)
    inv = run(valid(panels=3))
    assert inv.status is CAND and all(s.merged_rule_copy_agrees is None for s in inv.strips)


# --- contract ------------------------------------------------------------------------------------------------------------------


def test_every_grant_is_false_enforced_and_the_inventory_issues_no_existence_record():
    inv = run(valid(panels=3))
    for flag in A._GRANT_FLAGS:
        assert getattr(inv, flag) is False
        with pytest.raises(ValueError, match="cannot grant"):
            replace(inv, **{flag: True})
    with pytest.raises(ValueError):
        replace(inv, shadow_only=False)
    with pytest.raises(ValueError):
        replace(inv, status=EvidenceResolutionStatus.CORROBORATED)
    with pytest.raises(ValueError):
        replace(inv, status=EvidenceResolutionStatus.CONFLICT)
    assert inv.takeoff_eligible is False and inv.deduction_authority is False
    names = set(type(inv).__dataclass_fields__)
    assert not ({"existence_record", "aperture_bbox_pt", "host_candidate_id", "host_wall_id", "area_m2",
                 "window_type", "tag", "count"} & names)
    assert set(A.STANDING_LIMITS) == set(inv.standing_limits)


def test_a_candidate_inventory_cannot_be_built_without_a_strip_and_a_cell_cannot_lie_about_its_gates():
    inv = run(valid(panels=3))
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(inv, strips=())
    abstained = run(valid(panels=1, frame_len=70.0, pane=(1.5, 2.22)))
    assert abstained.status is ABST
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(abstained, status=CAND)
    cell = inv.candidates[0]
    with pytest.raises(ValueError):
        replace(cell, first_failed_gate=G2)
    with pytest.raises(ValueError):
        replace(cell, gates=tuple((n, A.PASSED if i != 3 else A.FAILED) for i, (n, _) in enumerate(cell.gates)))
    with pytest.raises(ValueError):
        replace(cell, in_merged_inventory=False)
    with pytest.raises(ValueError):
        replace(cell, near_miss=True)


def test_atoms_carry_the_ownership_root_and_only_allowed_statuses():
    inv = run(valid(panels=3))
    (atom,) = inv.evidence_atoms
    assert (atom.document_id, atom.page_id, atom.status) == ("doc", "7", CAND)
    assert atom.metadata["revision_id"] == "rev" and atom.metadata["snapshot_id"] == "snap"
    assert atom.metadata["source_sha256"] == "a" * 64
    assert all(atom.metadata[flag] is False for flag in A._GRANT_FLAGS)
    assert atom.bbox is not None and atom.bbox[1] == 300.0 and atom.bbox[3] == 305.52
    empty = run(Page())
    assert empty.status is ABST and empty.reason_codes == (A.NO_ACCEPTED_CELL,)
    assert empty.evidence_atoms[0].status is ABST and empty.evidence_atoms[0].bbox is None


def test_unverified_ink_abstains_but_the_lists_stay_attached_as_data_and_do_not_change_the_gate_results():
    page = valid(panels=3)
    got = run(page, unverified_ink_count=4)
    assert got.status is ABST and got.reason_codes == (A.INK_UNVERIFIED,) and got.unverified_ink_count == 4
    assert got.candidates == run(page).candidates and got.strips == run(page).strips and len(got.strips) == 1
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(got, status=CAND)
    both = run(page, unverified_ink_count=1)
    assert both.status is ABST and run(page).status is CAND


def test_a_non_positive_quantum_is_rejected():
    for bad in (0, -1.0, float("nan"), float("inf"), "0.24", None):
        with pytest.raises(ValueError):
            A.inventory_glazing_anatomy(ownership=OWN, ink=[], viewports=(), coordinate_quantum_pt=bad)


def test_the_empty_page_is_a_typed_abstention():
    inv = run(Page())
    assert inv.status is ABST and inv.reason_codes == (A.NO_ACCEPTED_CELL,)
    assert inv.candidates == () and inv.strips == () and dict(inv.first_failed_gate_histogram)[G1] == 0


# --- equality with the merged module's own strip inventory ------------------------------------------------------------------------


def _merged_strips(page):
    import pb_source_plan_glazing_strip_callout_shadow as merged

    ink = [merged.PlanInkSegment(s.ink_id, s.x0, s.y0, s.x1, s.y1, s.width, s.black, s.continuous_opaque)
           for s in page.ink]
    scope = merged.PlanCalloutStripScope(
        ownership=merged.SourceOwnership("doc", "rev", "snap", "a" * 64, merged.PRODUCER_INPUT_PROVENANCE),
        plan_page_id="7", elevation_page_id="8", callout_mark_pattern=r"[A-Z]\d+", coordinate_quantum_pt=Q,
        dimension_quantum_mm=5.0, plan_viewports=())
    result = merged.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=[], elevation_types=[])
    return sorted((s.axis, s.band, s.along, s.frame_along, s.panel_count, s.panel_lengths, s.inner_post_widths,
                   s.end_post_widths, s.extent_complete, s.stroke_width, s.ink_ids) for s in result.strips)


def _mine(inv):
    return sorted((s.axis, s.band, s.along, s.frame_along, s.panel_count, s.panel_lengths, s.inner_post_widths,
                   s.end_post_widths, s.extent_complete, s.stroke_width, s.ink_ids) for s in inv.strips)


def _equality_pages():
    pages = {}
    pages["valid3"] = valid(panels=3)
    pages["single_with_posts"] = valid(panels=1, frame_len=70.0)
    pages["single_no_posts"] = valid(panels=1, frame_len=70.0, end_posts=False)
    pages["seven"] = valid(panels=7, frame_len=430.0)
    pages["mixed"] = _mixed_page()
    page = Page()
    page.strip("H", 100.0, 300.0, panels=3, width=0.48)
    page.strip("V", 700.0, 200.0, panels=5, frame_len=260.0, width=0.72)
    page.strip("H", 100.0, 500.0, panels=2, frame_len=140.0, drop_cell_edges={(1, "hi")})
    pages["widths_and_axes"] = page
    return pages


@pytest.mark.parametrize("name", sorted(_equality_pages()))
def test_the_accepted_strips_equal_the_merged_modules_strip_inventory_exactly(name):
    page = _equality_pages()[name]
    assert _mine(run(page)) == _merged_strips(page)
    assert all(s.merged_rule_copy_agrees is True for s in run(page).strips)


# --- retained rivals: nothing is resolved silently by nearest / last / later ------------------------------------------------------


def _frame_cells(page, cells, frame=(300.0, 311.04)):
    """Accepted-shape cells drawn line by line inside ONE shared frame; each cell is (lo, hi, p, q)."""
    o0, o1 = frame
    for off in frame:
        page.along("H", min(c[0] for c in cells) - 3.0, max(c[1] for c in cells) + 3.0, off)
    for lo, hi, p, q in cells:
        for off in (p, q):
            page.along("H", lo, hi, off)
        for edge in (lo, hi):
            page.across("H", edge, p, q)
            page.across("H", edge, o0, o1)


def test_a_cell_with_two_possible_predecessors_fails_g7_instead_of_silently_taking_the_later_one():
    page = Page()
    _frame_cells(page, [(110.0, 220.0, 304.8, 306.24), (150.0, 222.0, 304.44, 306.6), (224.0, 290.0, 304.8, 306.24)])
    inv = run(page)
    accepted = sorted((c for c in inv.candidates if c.in_merged_inventory), key=lambda c: c.along)
    assert [c.along[0] for c in accepted] == [110.0, 150.0, 224.0]
    assert all(c.first_failed_gate == G7 for c in accepted)
    assert accepted[0].detail == (A.OVERLAP_DETAIL,) and accepted[1].detail == (A.OVERLAP_DETAIL,)
    assert accepted[2].detail == (A.AMBIGUOUS_NEIGHBOUR_DETAIL,)           # the follower is flagged too
    assert _mine(inv) == _merged_strips(page)                               # acceptance (the merged chain) is unchanged
    assert not any(s.full_anatomy for s in inv.strips)


def test_a_clean_chain_is_never_flagged_as_ambiguous():
    page = Page()
    _frame_cells(page, [(110.0, 180.0, 304.8, 306.24), (183.0, 250.0, 304.8, 306.24), (253.0, 330.0, 304.8, 306.24)])
    inv = run(page)
    accepted = [c for c in inv.candidates if c.in_merged_inventory]
    assert len(accepted) == 3 and all(c.first_failed_gate != G7 for c in accepted)
    assert sorted(s.panel_count for s in inv.strips) == [3]


def test_the_nearest_covering_frame_line_is_the_merged_definition_and_the_farther_rival_is_kept_as_data():
    base = valid(panels=1, frame_len=70.0)
    plain = run(base)
    assert [c.frame_rivals for c in plain.candidates if c.in_merged_inventory] == [(None, None)]
    outer = valid(panels=1, frame_len=70.0)
    outer._n = 10_000
    outer.along("H", 95.0, 180.0, 296.0)
    outer.along("H", 95.0, 180.0, 310.0)
    got = run(outer)
    (cell,) = [c for c in got.candidates if c.in_merged_inventory]
    assert cell.frame_offsets == (300.0, 305.52) and cell.frame_rivals == (296.0, 310.0)
    assert _mine(got) == _merged_strips(outer) and len(got.strips) == 1        # the rivals decided nothing
    assert got.candidates != plain.candidates and got.record_id != plain.record_id   # but the record states them


def test_a_decoy_line_nearer_than_the_true_frame_changes_the_verdict_exactly_as_the_merged_rule_and_names_the_true_frame():
    page = valid(panels=1, frame_len=70.0)
    page._n = 10_000
    page.along("H", 99.0, 175.0, 301.2)           # a covering line between the true lower frame line and the pair
    inv = run(page)
    (c,) = [c for c in by_pair(inv, 302.4, 303.12) if c.closure == A.CLOSURE_BOTH]
    assert c.first_failed_gate == G5 and c.frame_offsets == (301.2, 305.52)
    assert c.frame_rivals == (300.0, None) and not c.in_merged_inventory
    assert inv.strips == () and _merged_strips(page) == []


def test_an_end_post_width_is_the_merged_rules_last_matching_piece_and_every_distinct_width_is_kept():
    page = valid(panels=1, frame_len=70.0)
    page._n = 10_000
    page.along("H", 101.14, 102.64, 305.52)       # a second, narrower stroke piece ending at the same cell end
    inv = run(page)
    (strip,) = inv.strips
    assert strip.end_post_widths[0] == pytest.approx(1.5)
    assert strip.end_post_alternatives[0] == pytest.approx((1.5, 2.64))
    assert strip.end_post_alternatives[1] == pytest.approx((2.64,))
    assert _mine(inv) == _merged_strips(page)
    plain = run(valid(panels=1, frame_len=70.0))
    assert plain.strips[0].end_post_alternatives[0] == pytest.approx((2.64,))
    assert plain.strips[0].end_post_alternatives[1] == pytest.approx((2.64,))
    missing = run(valid(panels=1, frame_len=70.0, end_posts=False))
    assert missing.strips[0].end_post_alternatives == ((), ())
    with pytest.raises(ValueError, match="end post"):
        replace(plain.strips[0], end_post_alternatives=((), ()))


# --- metamorphic: transposition, half-turn, scale ------------------------------------------------------------------------------------


def _moved(page, fn):
    out = []
    for s in page.ink:
        x0, y0 = fn(s.x0, s.y0)
        x1, y1 = fn(s.x1, s.y1)
        out.append(A.InkSegment(s.ink_id, x0, y0, x1, y1, s.width, True, True))
    return out


def _facts(inv, scale=1.0):
    return (inv.status, inv.reason_codes, inv.first_failed_gate_histogram, inv.container_box_count,
            sorted(((c.first_failed_gate, c.in_merged_inventory, c.near_miss, c.chain_panel_count, c.stroke_width)
                    for c in inv.candidates), key=repr),
            sorted(((s.panel_count, s.extent_complete, s.full_anatomy, s.stroke_width, round(s.frame_depth / scale, 4),
                     tuple(round(v / scale, 4) for v in s.panel_lengths)) for s in inv.strips), key=repr))


def test_transposing_the_page_swaps_the_axes_and_changes_no_gate_result():
    page = _mixed_page()
    base = run(page)
    swapped = run(page, ink=_moved(page, lambda x, y: (y, x)))
    assert _facts(swapped) == _facts(base)
    assert sorted(s.axis for s in swapped.strips) == sorted({"H": "V", "V": "H"}[s.axis] for s in base.strips)


def test_a_half_turn_swaps_lo_and_hi_and_changes_no_gate_result():
    page = _mixed_page()
    base = run(page)
    turned = run(page, ink=_moved(page, lambda x, y: (-x, -y)))
    assert _facts(turned) == _facts(base)
    flip = {A.CLOSURE_LO_MISSING: A.CLOSURE_HI_MISSING, A.CLOSURE_HI_MISSING: A.CLOSURE_LO_MISSING,
            A.CLOSURE_BOTH: A.CLOSURE_BOTH}
    assert sorted(c.closure for c in turned.candidates) == sorted(flip[c.closure] for c in base.candidates)


def test_scaling_the_page_and_its_quantum_together_changes_no_gate_result():
    page = _mixed_page()
    base = run(page)
    for factor in (2.0, 0.5):
        scaled = run(page, ink=_moved(page, lambda x, y, f=factor: (f * x, f * y)), quantum=Q * factor)
        assert _facts(scaled, factor) == _facts(base)


def test_adding_a_disjoint_strip_elsewhere_leaves_every_existing_record_and_id_unchanged():
    base = _mixed_page()
    bigger = Page()
    bigger.ink = list(base.ink)
    bigger._n = 50_000
    bigger.strip("H", 2000.0, 3000.0, panels=2, frame_len=150.0)
    a, b = run(base), run(bigger)
    assert set(a.candidates) <= set(b.candidates) and set(a.strips) <= set(b.strips)
    assert len(b.strips) == len(a.strips) + 1 and len(b.candidates) > len(a.candidates)


def test_candidate_and_strip_ids_are_unique_on_every_variant_page():
    for name, page in _equality_pages().items():
        inv = run(page)
        assert len({c.candidate_id for c in inv.candidates}) == len(inv.candidates), name
        assert len({s.strip_id for s in inv.strips}) == len(inv.strips), name
        assert all(c.strip_id in {s.strip_id for s in inv.strips} for c in inv.candidates if c.strip_id), name


def test_the_inputs_are_not_mutated_and_every_record_is_frozen():
    import dataclasses

    page = _mixed_page()
    before = [(s.ink_id, s.x0, s.y0, s.x1, s.y1, s.width, s.black, s.continuous_opaque) for s in page.ink]
    objects = list(page.ink)
    viewports = (BIG,)
    inv = run(page, viewports=viewports)
    assert [(s.ink_id, s.x0, s.y0, s.x1, s.y1, s.width, s.black, s.continuous_opaque) for s in page.ink] == before
    assert all(a is b for a, b in zip(page.ink, objects)) and len(page.ink) == len(objects) and viewports == (BIG,)
    for record in (page.ink[0], BIG, inv, inv.candidates[0], inv.strips[0], inv.width_classes[0], OWN):
        field = dataclasses.fields(record)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, field, None)


def test_the_result_does_not_depend_on_the_hash_seed():
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo, tests = Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent
    code = ("import sys; sys.path[:0] = [%r, %r]; import test_glazing_anatomy_inventory_shadow_core as T; "
            "inv = T.run(T._mixed_page()); print(inv.record_id, len(inv.candidates), len(inv.strips))"
            ) % (str(repo), str(tests))
    seen = set()
    for seed in ("1", "2", "3"):
        completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                                   env={**os.environ, "PYTHONHASHSEED": seed})
        assert completed.returncode == 0, completed.stderr
        seen.add(completed.stdout.strip().splitlines()[-1])
    assert len(seen) == 1 and next(iter(seen)).split()[1:] != ["0", "0"]


# --- work bounds and standing limits -----------------------------------------------------------------------------------------------------


def test_the_candidate_budget_is_enforced_before_the_quadratic_innermost_test(monkeypatch):
    monkeypatch.setattr(A, "_MAX_CANDIDATES", 2)

    def boom(*args, **kwargs):
        raise AssertionError("the innermost test ran past the work bound")

    monkeypatch.setattr(A, "_split_innermost", boom)
    inv = run(valid(panels=3))
    assert inv.status is ABST and inv.reason_codes == (A.CANDIDATE_BUDGET_EXCEEDED,) and inv.candidates == ()


def test_parallel_lines_with_no_end_tick_at_all_are_not_candidates_and_the_limit_is_stated():
    page = Page()
    for off in (302.4, 303.12):
        page.along("H", 100.0, 160.0, off)
    inv = run(page)
    assert inv.candidates == () and A.PAIRS_WITHOUT_ANY_END_TICK_NOT_ENUMERATED in inv.standing_limits
    assert {A.FRAME_IS_NEAREST_COVERING_LINE_RIVALS_REPORTED, A.NEAR_MISS_KNOWS_ONLY_THE_FIRST_FAILED_GATE,
            A.VIEWPORT_REPORTED_NOT_GATING, A.INVENTORY_NOT_WINDOW_EXISTENCE} <= set(inv.standing_limits)


def test_every_record_carries_the_ownership_and_a_foreign_record_cannot_be_attached():
    inv = run(valid(panels=3))
    assert inv.candidates and inv.strips
    assert all(c.ownership == OWN for c in inv.candidates) and all(s.ownership == OWN for s in inv.strips)
    foreign = replace(inv.strips[0], ownership=replace(OWN, snapshot_id="elsewhere"))
    with pytest.raises(ValueError, match="ownership"):
        replace(inv, strips=(foreign,))
    foreign_cell = replace(inv.candidates[0], ownership=replace(OWN, page_id="8"))
    with pytest.raises(ValueError, match="ownership"):
        replace(inv, candidates=(foreign_cell, *inv.candidates[1:]))
    for bad in (dict(document_id=""), dict(page_id=7), dict(source_sha256="abc"), dict(revision_id=None),
                dict(source_sha256="A" * 64), dict(snapshot_id=b"s")):
        with pytest.raises(ValueError):
            replace(OWN, **bad)
