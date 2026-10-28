"""Pure-core proofs for the sub-floor ink census shadow (no PDF, no producer)."""
from __future__ import annotations

import random
import re
from dataclasses import replace

import pytest

import pb_subfloor_ink_census_shadow as C
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
OWN = C.CensusOwnership("doc", "rev", "snap", "a" * 64, "7")
VP = C.ViewportRef("view_plan", (0.0, 0.0, 2000.0, 2000.0))
Q = 0.24
EQ = Q * 0.25
BLACK = (0.0, 0.0, 0.0)
CLEAR_LOG = C.PaintLog((), True)


def raw(drawing, x0, y0, x1, y1, *, kind="line", edge=None, item=0, width=0.48, rgb=BLACK, stroked=True, seq=None,
        opacity=1.0, solid=True, seq_end="same", clip="none"):
    """One raw item. `clip` is "none" (the producer proves no clip), "unknown", "present" (a clip of unproven shape)
    or a rectangle (the producer proves the clip is exactly this rectangle)."""
    ident = f"d{drawing}i{item}" + (f"e{edge}" if edge is not None else "")
    seq = drawing if seq is None else seq
    return C.RawItem(
        item_id=ident, drawing_index=drawing, item_index=item, edge_index=edge, kind=kind,
        geometry=(float(x0), float(y0), float(x1), float(y1)), stroked=stroked,
        stroke_width=width if stroked else None, stroke_rgb=rgb if stroked else None,
        stroke_opacity=opacity if stroked else None, solid=solid, sequence_number=seq,
        sequence_end=seq if seq_end == "same" else seq_end, clip_known=clip != "unknown",
        clip_present=clip not in ("none", "unknown"), clip_exact_rect=tuple(clip) if isinstance(clip, tuple) else None)


def vis(oid, x0, y0, x1, y1, width=0.48, rgb=BLACK, verified=True, solid_opaque=True):
    return C.VisibleInk(oid, (float(x0), float(y0), float(x1), float(y1)), width if verified else None,
                        rgb if verified else None, solid_opaque, verified)


def run(items=(), visible=(), *, region=None, nominated=None, viewports=(VP,), paint=CLEAR_LOG, ownership=OWN,
        complete=True, quantum=Q):
    return C.census_sub_floor_ink(
        ownership=ownership, floor_plan_viewports=tuple(viewports), region_bbox=region, nominated_ids=nominated,
        visible=list(visible), items=list(items), paint=paint, coordinate_quantum_pt=quantum,
        visible_inventory_complete=complete)


def window(x=100.0, y=300.0, *, length=60.0, depth=5.52, post=2.64, glass=0.48, hidden="both", first_drawing=0,
           prefix="w", width=0.48, tick_width=None, hidden_geometry=None, panels=1, rebate_shift=0.0):
    """A glazing strip the way the strip finder reads it: frame lines along the strip, a full-depth frame tick at both
    ends of every cell, a glass-pair of two lines inside every cell, and two pane end ticks per cell that span the
    pair. A pane end tick is a visible item (glass >= the floor), a hidden item (hidden='both' | 'lo' | 'hi' for a
    one-panel strip, 'all' for every cell), or absent (hidden='none').

    `rebate_shift` moves the glass pair off centre; the cell edges are listed in `cells`."""
    panel_len = (length - (panels + 1) * post) / panels
    cells = [(x + post + k * (panel_len + post), x + post + k * (panel_len + post) + panel_len) for k in range(panels)]
    p0 = y + (depth - glass) / 2.0 + rebate_shift
    p1 = p0 + glass
    visible = [vis(f"{prefix}top", x, y, x + length, y, width), vis(f"{prefix}bot", x, y + depth, x + length, y + depth, width)]
    items = []
    drawing = first_drawing
    for k, (a, b) in enumerate(cells):
        tag = "" if panels == 1 else str(k)
        visible += [vis(f"{prefix}fa{tag}", a, y, a, y + depth, width), vis(f"{prefix}fb{tag}", b, y, b, y + depth, width),
                    vis(f"{prefix}pl{tag}", a, p0, b, p0, width), vis(f"{prefix}pu{tag}", a, p1, b, p1, width)]
        for end, pos in (("lo", a), ("hi", b)):
            if glass >= C.PRODUCER_LINE_ITEM_FLOOR_PT:
                visible.append(vis(f"{prefix}tick{tag}_{end}", pos, p0, pos, p1, width))
            elif hidden == "all" or (panels == 1 and hidden in ("both", end)):
                geometry = hidden_geometry(pos, p0, p1) if hidden_geometry else (pos, p0, pos, p1)
                items.append(raw(drawing, *geometry, width=tick_width or width))
                drawing += 1
    return visible, items, tuple(v.observation_id for v in visible)


def nominate(visible):
    """The strip's frame and glass-pair lines and its full-depth cell-edge ticks (never a pane end tick)."""
    return tuple(v.observation_id for v in visible if re.search(r"(top|bot|fa\d?|fb\d?|pl\d?|pu\d?)$", v.observation_id))


# --- the floor ---------------------------------------------------------------------------------------------


def test_the_floor_is_exact_at_half_a_point_and_is_the_producers_absolute_value():
    items = [raw(i, 64.0, 100.0 + 10 * i, 64.0 + length, 100.0 + 10 * i)
             for i, length in enumerate((0.48, 0.4999, 0.5, 0.5001, 0.52))]
    got = run(items, region=(60.0, 90.0, 70.0, 160.0))
    assert [i.item_id for i in got.sub_floor_items] == ["d0i0", "d1i0"]
    assert got.extractor_line_floor_pt == 0.5 and got.visibility_segment_floor_pt == 0.5
    assert all(i.length < 0.5 for i in got.sub_floor_items)


def test_the_floor_does_not_scale_with_the_drawing():
    """The floor is the producer's absolute constant: doubling a drawing turns hidden ticks into visible ones."""
    small = [raw(0, 10.0, 10.0, 10.0, 10.48)]
    big = [raw(0, 20.0, 20.0, 20.0, 20.96)]
    assert len(run(small, region=(0.0, 0.0, 50.0, 50.0)).sub_floor_items) == 1
    assert run(big, region=(0.0, 0.0, 50.0, 50.0)).sub_floor_items == ()


def test_visible_length_items_and_visible_ink_are_never_reported_so_nothing_is_double_counted():
    visible, items, _ = window(glass=0.72)
    every_stroke = [raw(k, *v.geometry) for k, v in enumerate(visible)]
    got = run(every_stroke, visible, region=(90.0, 290.0, 170.0, 315.0))
    assert got.sub_floor_items == () and got.unstroked_sub_floor_count == 0 and items == []
    assert got.visible_in_region_count == len(visible)
    hidden_visible, hidden_items, _ = window(glass=0.48)
    got = run(hidden_items, hidden_visible, region=(90.0, 290.0, 170.0, 315.0))
    assert [i.item_id for i in got.sub_floor_items] == ["d0i0", "d1i0"]
    assert {i.item_id for i in got.sub_floor_items}.isdisjoint({v.observation_id for v in hidden_visible})


def test_rectangle_edges_are_hidden_by_the_visibility_floor_and_lines_by_the_extractor_floor():
    items = [
        raw(0, 10.0, 10.0, 10.4, 10.0, kind="rect_edge", edge=0), raw(0, 10.4, 10.0, 10.4, 20.0, kind="rect_edge", edge=1),
        raw(0, 10.4, 20.0, 10.0, 20.0, kind="rect_edge", edge=2), raw(0, 10.0, 20.0, 10.0, 10.0, kind="rect_edge", edge=3),
        raw(1, 30.0, 30.0, 30.4, 30.0),
    ]
    got = run(items, region=(0.0, 0.0, 50.0, 50.0))
    by = {i.item_id: i for i in got.sub_floor_items}
    assert sorted(by) == ["d0i0e0", "d0i0e2", "d1i0"]
    assert by["d0i0e0"].hidden_by == C.HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR and by["d1i0"].hidden_by == C.HIDDEN_BY_EXTRACTOR_LINE_FLOOR
    assert by["d0i0e2"].edge_index == 2 and by["d1i0"].edge_index is None
    group = next(g for g in got.groups if g.orientation == "H")
    assert (group.count, group.line_items, group.rect_edges) == (3, 1, 2)


def test_an_unknown_item_kind_or_nonfinite_geometry_is_refused_not_guessed():
    bad_kind = replace(raw(0, 1.0, 1.0, 1.2, 1.0), kind="curve")
    with pytest.raises(ValueError, match="unknown raw item kind"):
        run([bad_kind], region=(0.0, 0.0, 5.0, 5.0))
    with pytest.raises(ValueError, match="finite"):
        run([replace(raw(0, 1.0, 1.0, 1.2, 1.0), geometry=(1.0, 1.0, float("nan"), 1.0))], region=(0.0, 0.0, 5.0, 5.0))


def test_unstroked_short_items_are_counted_but_never_itemised_or_grouped():
    items = [raw(0, 10.0, 10.0, 10.3, 10.0, stroked=False), raw(1, 10.0, 12.0, 10.3, 12.0)]
    got = run(items, region=(0.0, 0.0, 50.0, 50.0))
    assert got.unstroked_sub_floor_count == 1 and [i.item_id for i in got.sub_floor_items] == ["d1i0"]
    assert sum(g.count for g in got.groups) == 1


def test_orientation_is_axis_aligned_within_the_lattice_equality_oblique_or_a_point():
    items = [
        raw(0, 0.0, 0.0, 0.4, 0.0), raw(1, 0.0, 1.0, 0.0, 1.4), raw(2, 0.0, 2.0, 0.4, 2.0 + EQ * 0.99),
        raw(3, 0.0, 3.0, 0.4, 3.0 + EQ * 1.2), raw(4, 0.0, 4.0, 0.03, 4.03),
    ]
    got = run(items, region=(0.0, 0.0, 10.0, 10.0))
    assert {i.item_id: i.orientation for i in got.sub_floor_items} == {
        "d0i0": "H", "d1i0": "V", "d2i0": "H", "d3i0": "oblique", "d4i0": "point"}
    assert all(i.strip_relation is None and i.touches_band_edge is None for i in got.sub_floor_items)


def test_groups_count_by_width_colour_orientation_and_the_length_rounded_to_a_hundredth():
    items = [
        raw(0, 5.0, 5.0, 5.0, 5.48), raw(1, 6.0, 5.0, 6.0, 5.4800001), raw(2, 7.0, 5.0, 7.0, 5.4849),
        raw(3, 8.0, 5.0, 8.0, 5.4851), raw(4, 9.0, 5.0, 9.0, 5.48, width=0.24), raw(5, 10.0, 5.0, 10.0, 5.48, rgb=(1.0, 0.0, 0.0)),
        raw(6, 11.0, 5.0, 11.48, 5.0),
    ]
    got = run(items, region=(0.0, 0.0, 50.0, 50.0))
    table = {(g.stroke_width, g.stroke_rgb, g.orientation, g.length_bucket): g.count for g in got.groups}
    assert table == {
        (0.48, BLACK, "V", 0.48): 3,          # 0.48, 0.4800001 and 0.4849 all round to the 0.48 bucket
        (0.48, BLACK, "V", 0.49): 1,          # 0.4851 rounds up
        (0.24, BLACK, "V", 0.48): 1, (0.48, (1.0, 0.0, 0.0), "V", 0.48): 1, (0.48, BLACK, "H", 0.48): 1,
    }
    assert sum(g.count for g in got.groups) == len(got.sub_floor_items) == 7
    assert got.groups == tuple(sorted(got.groups, key=lambda g: (g.stroke_width, g.stroke_rgb, g.orientation, g.length_bucket)))


# --- relation to producer-visible ink -----------------------------------------------------------------------


def test_endpoint_coincidence_is_per_endpoint_within_the_lattice_equality_and_never_an_interior_touch():
    hidden = raw(0, 100.0, 300.0, 100.0, 300.48)
    visible = [
        vis("near", 100.05, 290.0, 100.05, 300.0),        # shares the a endpoint within the lattice equality
        vis("far", 100.07, 300.48, 100.07, 310.0),         # 0.07 away from the b endpoint: not the same coordinate
        vis("through", 90.0, 300.2, 110.0, 300.2),         # crosses the item's interior: no endpoint there
    ]
    got = run([hidden], visible, region=(90.0, 290.0, 110.0, 310.0))
    item = got.sub_floor_items[0]
    assert item.endpoint_a_visible_ids == ("near",) and item.endpoint_b_visible_ids == ()
    assert item.endpoints_coincide_visible is True
    lone = run([hidden], [visible[1], visible[2]], region=(90.0, 290.0, 110.0, 310.0)).sub_floor_items[0]
    assert lone.endpoints_coincide_visible is False and lone.endpoint_a_visible_ids == lone.endpoint_b_visible_ids == ()
    both = run([hidden], [vis("z", 100.0, 300.0, 120.0, 300.0), vis("y", 100.0, 300.0, 100.0, 280.0)],
               region=(90.0, 270.0, 130.0, 310.0)).sub_floor_items[0]
    assert both.endpoint_a_visible_ids == ("y", "z")      # every visible segment is retained, sorted


def test_region_membership_keeps_an_item_within_the_lattice_equality_of_the_edge_and_drops_the_rest():
    items = [raw(0, 110.05, 305.0, 110.05, 305.3), raw(1, 110.1, 305.0, 110.1, 305.3), raw(2, 105.0, 305.0, 105.0, 305.3)]
    got = run(items, region=(100.0, 300.0, 110.0, 310.0))
    assert [i.item_id for i in got.sub_floor_items] == ["d0i0", "d2i0"]


def test_region_mode_never_evaluates_closure_and_never_claims_a_cell():
    visible, items, _ = window()
    got = run(items, visible, region=(90.0, 290.0, 170.0, 315.0))
    assert got.status is ABST and got.reason_codes == (C.CLOSURE_NOT_EVALUATED_REGION_MODE,)
    assert got.mode == "region" and got.would_close_cell is None and got.cells == () and got.displaced_visible_cells == ()
    assert got.nomination_id is None and got.axis is None and got.region == (90.0, 290.0, 170.0, 315.0)
    assert len(got.sub_floor_items) == 2 and got.viewport_id == "view_plan"


# --- viewport scope ---------------------------------------------------------------------------------------------


def test_a_missing_or_non_containing_or_ambiguous_viewport_gives_no_census():
    visible, items, _ = window()
    for viewports in ((), (C.ViewportRef("elsewhere", (1000.0, 1000.0, 1500.0, 1500.0)),),
                      (C.ViewportRef("crop", (0.0, 0.0, 120.0, 2000.0)),),
                      (VP, C.ViewportRef("second", (50.0, 50.0, 900.0, 900.0)))):
        got = run(items, visible, region=(90.0, 290.0, 170.0, 315.0), viewports=viewports)
        assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
        assert got.sub_floor_items == () and got.groups == () and got.viewport_id is None and got.cells == ()


def test_growing_the_viewport_or_adding_a_far_one_changes_nothing_in_the_census():
    visible, items, _ = window()
    base = run(items, visible, region=(90.0, 290.0, 170.0, 315.0))
    bigger = run(items, visible, region=(90.0, 290.0, 170.0, 315.0), viewports=(C.ViewportRef("view_plan", (-9e3, -9e3, 9e3, 9e3)),))
    far = run(items, visible, region=(90.0, 290.0, 170.0, 315.0),
              viewports=(VP, C.ViewportRef("far", (5000.0, 5000.0, 6000.0, 6000.0))))
    for other in (bigger, far):
        assert (other.sub_floor_items, other.groups, other.reason_codes, other.region) == (
            base.sub_floor_items, base.groups, base.reason_codes, base.region)


# --- paint order ---------------------------------------------------------------------------------------------------


ITEM = raw(0, 100.0, 300.0, 100.0, 300.48, seq=5)
FOOT = C._expand(C._bbox(ITEM.geometry), 0.48 / 2.0)
REGION = (90.0, 290.0, 110.0, 310.0)


def paint_of(*ops, item=ITEM, aligned=True, reason=""):
    got = run([item], region=REGION, paint=C.PaintLog(tuple(ops), aligned, reason))
    return got.sub_floor_items[0]


def op(seq, bbox=(90.0, 290.0, 110.0, 310.0), *, kind="fill-path", drawing=None, cover=None, segments=None):
    return C.PaintOp(seq, kind, bbox, drawing, cover, segments)


def test_a_later_proven_opaque_rectangle_that_contains_the_stroke_footprint_covers_the_item():
    got = paint_of(op(7, drawing=3, cover=(90.0, 290.0, 110.0, 310.0)))
    assert got.paint_order == C.PAINT_COVERED and got.paint_basis == C.PAINT_BASIS_COVER
    assert got.covering_drawing_indices == (3,)


def test_a_cover_exactly_equal_to_the_footprint_covers_and_one_a_hair_short_does_not():
    assert paint_of(op(7, FOOT, drawing=3, cover=FOOT)).paint_order == C.PAINT_COVERED
    short = (FOOT[0], FOOT[1], FOOT[2] - 0.001, FOOT[3])
    assert paint_of(op(7, FOOT, drawing=3, cover=short)).paint_order == C.PAINT_UNPROVEN


def test_an_earlier_or_simultaneous_fill_does_not_cover_and_nothing_painted_later_is_reported_clear():
    assert paint_of(op(4, drawing=3, cover=(90.0, 290.0, 110.0, 310.0))).paint_order == C.PAINT_CLEAR
    assert paint_of(op(5, drawing=3, cover=(90.0, 290.0, 110.0, 310.0))).paint_order == C.PAINT_CLEAR
    assert paint_of().paint_order == C.PAINT_CLEAR
    assert paint_of().paint_basis == C.PAINT_BASIS_CLEAR and paint_of().covering_drawing_indices == ()


def test_a_later_fill_that_only_partly_covers_or_proves_nothing_leaves_the_order_unproven():
    partial = paint_of(op(7, drawing=3, cover=(90.0, 290.0, 100.1, 310.0)))
    assert partial.paint_order == C.PAINT_UNPROVEN and partial.paint_basis == C.PAINT_BASIS_OVERLAP
    unproved = paint_of(op(7, drawing=3, cover=None))           # translucent, clipped, blended or not a rectangle
    assert unproved.paint_order == C.PAINT_UNPROVEN and unproved.covering_drawing_indices == ()


def test_a_later_fill_elsewhere_does_not_disturb_a_clear_item():
    assert paint_of(op(7, (500.0, 500.0, 600.0, 600.0), drawing=3, cover=(500.0, 500.0, 600.0, 600.0))
                    ).paint_order == C.PAINT_CLEAR


def test_text_images_and_shadings_painted_later_over_the_item_are_unproven_not_ignored():
    for kind in ("fill-image", "fill-text", "fill-shade", "fill-image-mask", "some-future-kind"):
        assert paint_of(op(9, kind=kind)).paint_order == C.PAINT_UNPROVEN, kind


def test_a_later_stroke_is_judged_by_its_own_reach_not_its_bounding_box():
    miss = op(8, (95.0, 290.0, 110.0, 305.0), kind="stroke-path", drawing=3, segments=((95.0, 290.0, 110.0, 305.0, 0.12),))
    hit = op(8, (95.0, 290.0, 110.0, 310.0), kind="stroke-path", drawing=3, segments=((100.0, 290.0, 100.0, 310.0, 0.12),))
    bbox_only = op(8, (95.0, 290.0, 110.0, 305.0), kind="stroke-path", drawing=3, segments=None)
    assert paint_of(miss).paint_order == C.PAINT_CLEAR
    assert paint_of(hit).paint_order == C.PAINT_UNPROVEN
    assert paint_of(bbox_only).paint_order == C.PAINT_UNPROVEN


def test_a_later_opaque_black_stroke_cannot_hide_a_black_item_and_can_hide_anything_else():
    black_over = op(8, (95.0, 290.0, 110.0, 310.0), kind="stroke-path", drawing=3,
                    segments=((100.0, 290.0, 100.0, 310.0, 0.12),))
    flagged = replace(black_over, black_opaque_stroke=True)
    assert paint_of(black_over).paint_order == C.PAINT_UNPROVEN                  # a stroke of unknown colour may hide it
    assert paint_of(flagged).paint_order == C.PAINT_CLEAR and paint_of(flagged).paint_basis == C.PAINT_BASIS_CLEAR
    for changed in (dict(rgb=(1.0, 0.0, 0.0)), dict(rgb=(0.0, 0.0, 0.0, 1.0)), dict(solid=False), dict(opacity=0.5)):
        other = raw(0, 100.0, 300.0, 100.0, 300.48, seq=5, **changed)
        assert paint_of(flagged, item=other).paint_order == C.PAINT_UNPROVEN, changed
    # the flag never turns a fill, an image or any other later paint into something harmless
    for kind in ("fill-image", "fill-path", "fill-text", "clip-path"):
        with pytest.raises(ValueError, match="only a stroke"):
            replace(op(9, kind=kind), black_opaque_stroke=True)
    with pytest.raises(ValueError, match="only a stroke"):
        C.PaintOp(9, "stroke-path", (0.0, 0.0, 1.0, 1.0), black_opaque_stroke=1)
    # ... and it does not stop a proven cover from covering
    cover = op(7, drawing=9, cover=(90.0, 290.0, 110.0, 310.0))
    assert paint_of(flagged, cover).paint_order == C.PAINT_COVERED


def test_a_cover_wins_over_other_later_paint_and_every_covering_drawing_is_retained():
    got = paint_of(op(7, drawing=9, cover=(90.0, 290.0, 110.0, 310.0)), op(8, drawing=4, cover=(80.0, 280.0, 120.0, 320.0)),
                   op(9, kind="fill-image"))
    assert got.paint_order == C.PAINT_COVERED and got.covering_drawing_indices == (4, 9)


def test_an_unaligned_paint_log_or_a_missing_sequence_decides_nothing():
    cover = op(7, drawing=3, cover=(90.0, 290.0, 110.0, 310.0))
    got = paint_of(cover, aligned=False, reason="paint_log_not_aligned_with_drawing_sequence")
    assert got.paint_order == C.PAINT_UNPROVEN and got.paint_basis == "paint_log_not_aligned_with_drawing_sequence"
    assert paint_of(cover, aligned=False).paint_basis == "paint_log_not_aligned_with_drawing_sequence"
    unsequenced = paint_of(cover, item=raw(0, 100.0, 300.0, 100.0, 300.48, seq=None, seq_end=None))
    assert unsequenced.paint_order == C.PAINT_UNPROVEN and unsequenced.paint_basis == C.PAINT_BASIS_SEQUENCE_MISSING


def test_a_drawing_that_is_stroked_then_filled_occupies_two_sequence_numbers_and_its_own_fill_never_covers_it():
    item = raw(0, 100.0, 300.0, 100.0, 300.48, seq=5, seq_end=6)
    own_stroke = op(6, kind="stroke-path", drawing=0, segments=((100.0, 300.0, 100.0, 300.48, 0.24),))
    assert paint_of(own_stroke, item=item).paint_order == C.PAINT_CLEAR
    assert paint_of(op(7, drawing=3, cover=(90.0, 290.0, 110.0, 310.0)), item=item).paint_order == C.PAINT_COVERED


def test_the_paint_check_budget_leaves_unproven_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(C, "_MAX_PAINT_PAIR_CHECKS", 0)
    got = paint_of(op(7, drawing=3, cover=(90.0, 290.0, 110.0, 310.0)))
    assert got.paint_order == C.PAINT_UNPROVEN and got.paint_basis == C.PAINT_BASIS_BUDGET


# --- nomination and the strip's region -------------------------------------------------------------------------------


def test_nominated_region_is_the_strips_box_grown_by_its_own_depth_on_every_side():
    visible, items, _ = window(x=100.0, y=300.0, length=60.0, depth=5.52)
    got = run(items, visible, nominated=nominate(visible))
    depth = got.band_extent[1] - got.band_extent[0]
    assert got.axis == "H" and got.along_extent == pytest.approx((100.0, 160.0)) and got.band_extent == pytest.approx((300.0, 305.52))
    assert depth == pytest.approx(5.52)
    assert got.region == pytest.approx((100.0 - depth, 300.0 - depth, 160.0 + depth, 305.52 + depth))
    deep, items2, _ = window(x=100.0, y=300.0, length=60.0, depth=8.0)
    other = run(items2, deep, nominated=nominate(deep))
    assert other.region == pytest.approx((92.0, 292.0, 168.0, 316.0))       # no fixed margin: the depth is the margin


def test_a_vertical_strip_is_read_with_the_axes_swapped():
    visible, items, _ = window()
    swapped_visible = [vis(v.observation_id, v.geometry[1], v.geometry[0], v.geometry[3], v.geometry[2]) for v in visible]
    swapped_items = [raw(k, i.geometry[1], i.geometry[0], i.geometry[3], i.geometry[2]) for k, i in enumerate(items)]
    got = run(swapped_items, swapped_visible, nominated=nominate(swapped_visible))
    assert got.axis == "V" and got.status is CAND and got.along_extent == pytest.approx((100.0, 160.0))


def test_nomination_failures_abstain_before_any_census():
    visible, items, ids = window()
    for bad in ((), ids + (ids[0],), ids + ("not-on-this-page",)):
        got = run(items, visible, nominated=bad)
        assert got.status is ABST and got.reason_codes == (C.NOMINATION_NOT_VISIBLE_ON_PAGE,) and got.sub_floor_items == ()
    unverified = [replace(v, role_verified=False, stroke_width=None, stroke_rgb=None) if v.observation_id == "wtop" else v
                  for v in visible]
    got = run(items, unverified, nominated=nominate(visible))
    assert got.reason_codes == (C.SOURCE_ROLE_UNPROVEN, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
    diagonal = visible + [vis("diag", 100.0, 300.0, 150.0, 340.0)]
    assert run(items, diagonal, nominated=nominate(visible) + ("diag",)).reason_codes == (C.NOMINATION_NOT_AXIS_ALIGNED,)
    square = [vis("s1", 0, 0, 10, 0), vis("s2", 0, 10, 10, 10), vis("s3", 0, 0, 0, 10), vis("s4", 10, 0, 10, 10)]
    assert run([], square, nominated=("s1", "s2", "s3", "s4")).reason_codes == (C.NOMINATION_AXIS_AMBIGUOUS,)


def test_a_nomination_without_any_depth_names_no_region():
    """Ink along one line has no depth of its own, so the region (the box grown by the strip's depth) is undefined."""
    line = [vis("l1", 100.0, 300.0, 130.0, 300.0), vis("l2", 130.0, 300.0, 160.0, 300.0 + EQ * 0.5)]
    got = run([], line, nominated=("l1", "l2"))
    assert got.status is ABST and got.reason_codes == (C.NOMINATION_HAS_NO_DEPTH,)
    assert got.sub_floor_items == () and got.region is None and got.axis == "H"


def test_items_touching_the_strips_band_edges_are_reported_with_their_relation_to_the_strip():
    visible, items, _ = window()
    extra = [
        raw(10, 120.0, 300.0, 120.3, 300.0), raw(11, 130.0, 305.52, 130.0, 305.9), raw(12, 140.0, 302.0, 140.0, 302.3),
        raw(13, 162.0, 300.0, 162.3, 300.0), raw(14, 150.0, 300.0, 150.0, 305.52 + 0.0, width=0.48),
    ]
    got = run(items + extra[:4], visible, nominated=nominate(visible))
    touch = {i.item_id: i.touches_band_edge for i in got.sub_floor_items}
    assert touch["d10i0"] == "lo" and touch["d11i0"] == "hi" and touch["d12i0"] is None and touch["d13i0"] is None
    assert got.band_edge_item_ids == ("d10i0", "d11i0")
    rel = {i.item_id: i.strip_relation for i in got.sub_floor_items}
    assert rel["d10i0"] == "parallel" and rel["d11i0"] == "perpendicular" and rel["d0i0"] == "perpendicular"
    # the pane end ticks sit between the glass lines, not on the band edges
    assert touch["d0i0"] is None and touch["d1i0"] is None
    assert extra[4].geometry[3] == 305.52           # (a full-depth tick is visible-length and never a candidate)


def test_an_opaque_cover_is_proven_only_for_a_plain_unlayered_opaque_unclipped_rectangle_fill():
    fill = {"type": "f", "fill": (1.0, 1.0, 1.0), "fill_opacity": 1.0, "items": [("re", _Rect(10.0, 20.0, 30.0, 40.0))]}
    known_clear = (True, False, True, None)
    assert C._opaque_cover(fill, known_clear, False) == (10.0, 20.0, 30.0, 40.0)
    assert C._opaque_cover(fill, known_clear, True) is None                       # a blend mode / soft mask exists
    assert C._opaque_cover({**fill, "fill_opacity": 0.5}, known_clear, False) is None
    assert C._opaque_cover({**fill, "fill": None}, known_clear, False) is None
    assert C._opaque_cover({**fill, "type": "s"}, known_clear, False) is None
    assert C._opaque_cover({**fill, "layer": "Hidden"}, known_clear, False) is None
    assert C._opaque_cover({**fill, "oc": 17}, known_clear, False) is None
    assert C._opaque_cover(fill, None, False) is None and C._opaque_cover(fill, (False, False, False, None), False) is None
    assert C._opaque_cover(fill, (True, True, False, None), False) is None       # a clip of unproven shape
    assert C._opaque_cover(fill, (True, True, True, (0.0, 0.0, 25.0, 100.0)), False) == (10.0, 20.0, 25.0, 40.0)
    assert C._opaque_cover(fill, (True, True, True, (50.0, 50.0, 60.0, 60.0)), False) is None      # clipped away
    curve = {**fill, "items": [("c", None, None, None, None)]}
    assert C._opaque_cover(curve, known_clear, False) is None


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


# --- the cell-closure diagnostic ------------------------------------------------------------------------------------------


def census_of(visible, items, **kw):
    return run(items, visible, nominated=nominate(visible), **kw)


def test_hidden_end_ticks_that_exactly_complete_a_missing_pair_make_a_candidate_never_a_window():
    visible, items, _ = window(glass=0.48)
    got = census_of(visible, items)
    assert got.status is CAND and got.reason_codes == (C.SUB_FLOOR_TICKS_WOULD_CLOSE_CELL,)
    assert got.would_close_cell is True and len(got.cells) == 1
    cell = got.cells[0]
    assert cell.would_close_cell and not cell.visible_closed and not cell.inside_visible_cell and cell.completion_paint == "clear"
    assert (cell.lo_tick.support, cell.hi_tick.support) == (C.TICK_SUB_FLOOR, C.TICK_SUB_FLOOR)
    assert cell.lo_tick.sub_floor_item_ids == ("d0i0",) and cell.hi_tick.sub_floor_item_ids == ("d1i0",)
    assert cell.pane_lines == pytest.approx((302.52, 303.0)) and cell.along == pytest.approx((102.64, 157.36))
    assert cell.frame_lines == pytest.approx((300.0, 305.52)) and cell.stroke_rgbs == (BLACK,)
    assert got.standing_limits == C.STANDING_LIMITS and got.evidence_atoms[0].status is CAND
    assert got.evidence_atoms[0].metadata["physical_opening_granted"] is False
    assert not hasattr(got, "existence_record") and not hasattr(got, "host_candidate_id")


def test_a_cell_the_visible_ink_already_closes_is_reported_as_closed_and_stays_abstained():
    visible, items, _ = window(glass=0.72)
    got = census_of(visible, items)
    assert items == [] and got.sub_floor_items == ()
    assert got.status is ABST and got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION,) and got.would_close_cell is False
    assert len(got.cells) == 1 and got.cells[0].visible_closed and not got.cells[0].would_close_cell
    assert got.cells[0].completion_paint == C.PAINT_NOT_APPLICABLE
    assert (got.cells[0].lo_tick.support, got.cells[0].hi_tick.support) == (C.TICK_VISIBLE, C.TICK_VISIBLE)


def test_one_hidden_tick_cannot_complete_a_pair_when_the_other_end_has_no_tick_at_all():
    for which in ("lo", "hi", "none"):
        visible, items, _ = window(glass=0.48, hidden=which)
        got = census_of(visible, items)
        assert got.status is ABST and got.would_close_cell is False and got.cells == (), which
        assert got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION,)


def test_a_frame_outline_closed_by_full_depth_ticks_is_not_mistaken_for_a_glazing_cell():
    """Without a glass pair there is no cell: the outline's own lines have no frame around them."""
    visible, items, _ = window(glass=0.48, hidden="none")
    got = census_of(visible, items)
    assert got.cells == () and got.would_close_cell is False


def _strokes(*specs):
    return [C._Stroke(*s) for s in specs]        # (offset, lo, hi, ident, hidden)


def test_an_end_tick_exported_in_collinear_pieces_is_one_tick_when_nothing_longer_stands_at_its_station():
    par = _strokes((0.0, 0.0, 10.0, "l1", False), (1.0, 0.0, 10.0, "l2", False))
    perp = _strokes((0.0, 0.0, 0.5, "a1", True), (0.0, 0.5, 1.0, "a2", True), (10.0, 0.0, 1.0, "b", False))
    assert C._pane_boxes(par, perp, EQ) == [(0.0, 10.0, 0.0, 1.0)]
    # a longer stroke at the same station absorbs the pieces into one collinear span: no tick of that range remains
    assert C._pane_boxes(par, perp + _strokes((0.0, -2.0, 3.0, "frame", False)), EQ) == []


def test_tick_support_is_visible_mixed_or_sub_floor_and_a_longer_frame_tick_is_not_a_piece():
    vis_piece = _strokes((5.0, 0.0, 0.6, "v", False))
    sub_piece = _strokes((5.0, 0.6, 1.0, "h", True))
    mixed = C._tick_support(5.0, 0.0, 1.0, vis_piece, sub_piece, C._covers_by_offset(vis_piece, EQ), EQ)
    assert (mixed.support, mixed.visible_ids, mixed.sub_floor_item_ids) == (C.TICK_MIXED, ("v",), ("h",))
    full = _strokes((5.0, 0.0, 1.0, "v", False))
    assert C._tick_support(5.0, 0.0, 1.0, full, [], C._covers_by_offset(full, EQ), EQ).support == C.TICK_VISIBLE
    assert C._tick_support(5.0, 0.0, 1.0, [], sub_piece, {}, EQ).support == C.TICK_SUB_FLOOR
    longer = _strokes((5.0, -2.0, 3.0, "frame", False))
    got = C._tick_support(5.0, 0.0, 1.0, longer, sub_piece, C._covers_by_offset(longer, EQ), EQ)
    assert got.support == C.TICK_SUB_FLOOR and got.visible_ids == ()


def test_collinear_hidden_pieces_next_to_a_full_depth_frame_tick_are_absorbed_exactly_as_the_finder_absorbs_them():
    visible, _, _ = window(glass=0.72)
    p0 = 300.0 + (5.52 - 0.72) / 2.0
    visible = [v for v in visible if v.observation_id != "wtick_hi"]
    pieces = [raw(0, 157.36, p0, 157.36, p0 + 0.36), raw(1, 157.36, p0 + 0.36, 157.36, p0 + 0.72)]
    got = census_of(visible, pieces)
    assert got.status is ABST and got.would_close_cell is False and got.cells == ()
    assert len(_sibling_strips(_ink(visible, pieces))) == 0         # the finder reads nothing here either


@pytest.mark.parametrize("name, kwargs", [
    ("too_short", dict(hidden_geometry=lambda pos, p0, p1: (pos, p0, pos, p0 + 0.4))),
    ("overshooting", dict(hidden_geometry=lambda pos, p0, p1: (pos, p0 - 0.1, pos, p1))),
    ("wrong_width", dict(tick_width=0.24)),
    ("oblique", dict(hidden_geometry=lambda pos, p0, p1: (pos - 0.2, p0, pos + 0.2, p1))),
    ("beyond_the_glass_lines", dict(hidden_geometry=lambda pos, p0, p1: (pos - 4.0 if pos < 130 else pos + 4.0, p0,
                                                                        pos - 4.0 if pos < 130 else pos + 4.0, p1))),
])
def test_look_alike_hidden_marks_do_not_complete_a_pair(name, kwargs):
    visible, items, _ = window(glass=0.48, **kwargs)
    got = census_of(visible, items)
    assert got.status is ABST and got.would_close_cell is False, name
    assert all(not c.would_close_cell for c in got.cells)


@pytest.mark.parametrize("name, build", [
    ("off_centre_glass_pair", lambda: window(glass=0.48, rebate_shift=0.6)),
    ("no_frame_lines", lambda: _without(window(glass=0.48), ("wtop", "wbot"))),
    ("cell_edges_not_crossed_over_the_full_depth", lambda: _without(window(glass=0.48), ("wfa", "wfb"))),
    ("glass_pair_not_narrower_than_the_rebates", lambda: window(glass=0.48, depth=1.2)),
    ("only_one_frame_line", lambda: _without(window(glass=0.48), ("wbot",))),
])
def test_a_glass_pair_without_the_finders_glazing_anatomy_around_it_is_not_a_cell(name, build):
    visible, items, _ = build()
    got = census_of(visible, items)
    assert got.would_close_cell is False and got.status is ABST and len(items) == 2, name
    assert all(not c.would_close_cell for c in got.cells)
    assert len(_sibling_strips(_ink(visible, items))) == 0, name


def _without(built, ids):
    visible, items, _ = built
    kept = [v for v in visible if v.observation_id not in ids]
    return kept, items, tuple(v.observation_id for v in kept)


def test_hidden_marks_that_are_dashed_translucent_or_not_black_never_close_a_cell():
    visible, items, _ = window(glass=0.48)
    for change in (dict(solid=False), dict(opacity=0.5), dict(rgb=(1.0, 0.0, 0.0)), dict(rgb=(0.0, 0.0, 0.0, 1.0))):
        altered = [replace(i, **{"solid": change.get("solid", i.solid), "stroke_opacity": change.get("opacity", i.stroke_opacity),
                                 "stroke_rgb": change.get("rgb", i.stroke_rgb)}) for i in items]
        got = census_of(visible, altered)
        assert got.status is ABST and got.would_close_cell is False, change
        assert len(got.sub_floor_items) == 2              # still census, only not closure evidence


def test_the_pane_lines_must_be_verified_solid_black_producer_ink():
    visible, items, _ = window(glass=0.48)
    for victim in ("wpl", "wpu"):
        for change in (dict(role_verified=False, stroke_width=None, stroke_rgb=None), dict(solid_opaque=False),
                       dict(stroke_rgb=(0.5, 0.5, 0.5))):
            altered = [replace(v, **change) if v.observation_id == victim else v for v in visible]
            ids = tuple(v.observation_id for v in visible if v.observation_id.endswith(("top", "bot", "fa", "fb")))
            got = run(items, altered, nominated=ids)
            assert got.would_close_cell is False and got.status is ABST, (victim, change)


def test_the_finder_groups_blacks_by_width_so_two_blacks_of_one_width_are_one_class():
    visible, items, _ = window(glass=0.48)
    shaded = [replace(v, stroke_rgb=(0.05, 0.05, 0.05)) if v.observation_id in ("wpl", "wtop") else v for v in visible]
    got = census_of(shaded, items)
    assert got.status is CAND and len(got.cells) == 1
    assert got.cells[0].stroke_rgbs == ((0.0, 0.0, 0.0), (0.05, 0.05, 0.05))
    assert len(_sibling_strips(_ink(shaded, items))) == 1


def test_completions_painted_over_or_unprovable_stay_geometric_but_abstain():
    visible, items, _ = window(glass=0.48)
    cover = C.PaintOp(50, "fill-path", (90.0, 290.0, 170.0, 315.0), 9, (90.0, 290.0, 170.0, 315.0))
    covered = census_of(visible, items, paint=C.PaintLog((cover,), True))
    assert covered.status is ABST and covered.would_close_cell is True
    assert covered.reason_codes == (C.COMPLETION_COVERED_BY_LATER_FILL,) and covered.cells[0].completion_paint == "covered"
    image = census_of(visible, items, paint=C.PaintLog((C.PaintOp(50, "fill-image", (90.0, 290.0, 170.0, 315.0)),), True))
    assert image.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,) and image.cells[0].completion_paint == "unproven"
    unaligned = census_of(visible, items, paint=C.PaintLog((), False, "paint_log_unavailable"))
    assert unaligned.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,) and unaligned.would_close_cell is True
    both = census_of(visible, items, paint=C.PaintLog((cover, C.PaintOp(51, "fill-image", (90.0, 290.0, 110.0, 315.0))), True))
    assert both.reason_codes == (C.COMPLETION_COVERED_BY_LATER_FILL,) and both.cells[0].completion_paint == "covered"


def test_a_completion_whose_hidden_ticks_may_be_clipped_away_is_unproven():
    visible, items, _ = window(glass=0.48)
    for clip in ("unknown", "present", (0.0, 0.0, 120.0, 400.0)):          # unknown, unproven shape, cuts the far tick
        clipped = [replace(i, clip_known=clip != "unknown", clip_present=clip != "unknown",
                           clip_exact_rect=clip if isinstance(clip, tuple) else None) for i in items]
        got = census_of(visible, clipped)
        assert got.status is ABST and got.would_close_cell is True and got.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,), clip
        assert {i.paint_basis for i in got.sub_floor_items} >= {C.PAINT_BASIS_CLIP_UNPROVEN}
    roomy = [replace(i, clip_known=True, clip_present=True, clip_exact_rect=(0.0, 0.0, 500.0, 500.0)) for i in items]
    assert census_of(visible, roomy).status is CAND                          # a clip proven to contain the stroke


def test_an_incomplete_visible_inventory_forbids_a_candidate_but_keeps_the_geometry():
    visible, items, _ = window(glass=0.48)
    got = census_of(visible, items, complete=False)
    assert got.status is ABST and got.would_close_cell is True and got.visible_inventory_complete is False
    assert got.reason_codes == (C.VISIBLE_INVENTORY_INCOMPLETE,)
    assert run(items, visible, region=(90.0, 290.0, 170.0, 315.0), complete=False).reason_codes == (
        C.CLOSURE_NOT_EVALUATED_REGION_MODE, C.VISIBLE_INVENTORY_INCOMPLETE)


def test_a_visible_segment_of_the_region_whose_primitive_join_is_unproven_is_a_rival_the_closure_cannot_see():
    visible, items, _ = window(glass=0.48)
    rival = C.VisibleInk("rival", (120.0, 301.0, 120.0, 304.0), None, None, False, False)
    got = census_of(visible + [rival], items)
    assert got.status is ABST and got.visible_inventory_complete is False and got.would_close_cell is True
    assert got.reason_codes == (C.VISIBLE_INVENTORY_INCOMPLETE,)
    far = C.VisibleInk("far", (1500.0, 1500.0, 1500.0, 1510.0), None, None, False, False)
    assert census_of(visible + [far], items).status is CAND                  # outside the region it is irrelevant
    # a stroke-less segment (a fill edge) whose join IS proven is not ink and is not a rival
    unstroked = C.VisibleInk("fill_edge", (120.0, 301.0, 120.0, 304.0), None, None, False, True)
    assert census_of(visible + [unstroked], items).status is CAND


def test_a_hidden_tick_shorter_than_the_pane_pair_inside_a_visible_cell_changes_nothing():
    visible, _, _ = window(glass=0.72)
    p0 = 300.0 + (5.52 - 0.72) / 2.0
    got = census_of(visible, [raw(0, 130.0, p0, 130.0, p0 + 0.36)])
    assert got.status is ABST and got.would_close_cell is False and got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION,)
    assert got.displaced_visible_cells == () and len(got.cells) == 1 and got.cells[0].visible_closed
    assert len(_sibling_strips(_ink(visible, []))) == len(_sibling_strips(_ink(visible, [raw(0, 130.0, p0, 130.0, p0 + 0.36)]))) == 1


def test_hidden_ticks_that_nest_inside_a_visible_cell_displace_it_and_the_finder_would_lose_the_strip():
    """A thinner glass pair with hidden end ticks drawn inside a visible cell makes the finder's innermost box the
    inner one, whose nearest enclosing lines are the outer glass lines: no cell remains. Reported, never resolved."""
    visible, _, _ = window(glass=0.72)
    a, b, inner0 = 102.64, 157.36, 300.0 + (5.52 - 0.48) / 2.0
    visible = visible + [vis("wil", a, inner0, b, inner0), vis("wiu", a, inner0 + 0.48, b, inner0 + 0.48)]
    ticks = [raw(0, a, inner0, a, inner0 + 0.48), raw(1, b, inner0, b, inner0 + 0.48)]
    got = census_of(visible, ticks)
    assert got.status is ABST and got.would_close_cell is False
    assert got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION, C.HIDDEN_TICKS_DISPLACE_VISIBLE_CELL)
    assert len(got.displaced_visible_cells) == 1 and got.cells == ()
    displaced = got.displaced_visible_cells[0]
    assert displaced.pane_lines == pytest.approx((302.4, 303.12)) and displaced.hidden_item_ids_in_cell == ("d0i0", "d1i0")
    assert len(_sibling_strips(_ink(visible, []))) == 1 and len(_sibling_strips(_ink(visible, ticks))) == 0


def test_a_completed_cell_and_a_displaced_one_together_are_not_an_exact_completion():
    """One width class completes a cell while hidden ink of another displaces a visible cell: the completion is not exact."""
    visible, items, _ = window(glass=0.48)
    other, _, _ = window(glass=0.72, prefix="x", width=0.24)
    a, b, inner0 = 102.64, 157.36, 300.0 + (5.52 - 0.48) / 2.0
    other = other + [vis("xil", a, inner0, b, inner0, 0.24), vis("xiu", a, inner0 + 0.48, b, inner0 + 0.48, 0.24)]
    nested = [raw(10, a, inner0, a, inner0 + 0.48, width=0.24), raw(11, b, inner0, b, inner0 + 0.48, width=0.24)]
    got = census_of(visible + other, items + nested)
    assert got.would_close_cell is True and got.status is ABST
    assert got.reason_codes == (C.HIDDEN_TICKS_DISPLACE_VISIBLE_CELL,)
    assert [d.stroke_width for d in got.displaced_visible_cells] == [0.24]


def test_the_visible_reading_is_snapped_without_the_hidden_ink_so_a_hidden_coordinate_cannot_alter_it():
    """Visible ink alone closes a cell whose glass lines start 0.05 inside the tick station (one coordinate). A hidden
    stray tick 0.04 on the other side of that station re-clusters the station away from the line ends once it is
    snapped together with them: the finder then loses the cell. The census reports that as a displacement of the
    cell the visible ink alone closes, which it can only do if it reads the visible ink on its own."""
    visible, _, _ = window(glass=0.72)
    nudged = [replace(v, geometry=(v.geometry[0] + 0.05, *v.geometry[1:])) if v.observation_id in ("wpl", "wpu") else v
              for v in visible]
    stray = raw(0, 102.64 - 0.04, 300.2, 102.64 - 0.04, 300.6)
    assert len(_sibling_strips(_ink(nudged, []))) == 1 and len(_sibling_strips(_ink(nudged, [stray]))) == 0
    got = census_of(nudged, [stray])
    assert got.status is ABST and got.would_close_cell is False
    assert len(got.displaced_visible_cells) == 1 and got.displaced_visible_cells[0].hidden_item_ids_in_cell == ()
    assert got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION, C.HIDDEN_TICKS_DISPLACE_VISIBLE_CELL)
    alone = census_of(nudged, [])
    assert len(alone.cells) == 1 and alone.cells[0].visible_closed and alone.displaced_visible_cells == ()


def test_two_readings_of_one_stretch_are_an_ambiguity_not_a_choice():
    """A second width class carries its own glass pair over the same stretch: both are kept, the verdict abstains."""
    visible, items, _ = window(glass=0.48)
    other, _, _ = window(glass=0.72, prefix="x", width=0.24)
    got = census_of(visible + other, items)
    assert got.status is ABST and got.would_close_cell is True and got.reason_codes == (C.CLOSURE_AMBIGUOUS,)
    assert {c.stroke_width for c in got.cells} == {0.24, 0.48} and len({c.pane_lines for c in got.cells}) == 2
    assert [c.would_close_cell for c in sorted(got.cells, key=lambda c: c.stroke_width)] == [False, True]


def test_a_two_panel_strip_with_every_pane_tick_hidden_completes_both_cells():
    visible, items, _ = window(glass=0.48, length=110.0, panels=2, hidden="all")
    got = census_of(visible, items)
    assert len(items) == 4 and got.status is CAND and len(got.cells) == 2 and all(c.would_close_cell for c in got.cells)
    assert [v for c in sorted(got.cells, key=lambda c: c.along) for v in c.along] == pytest.approx(
        [102.64, 153.68, 156.32, 207.36])
    assert {c.cell_id for c in got.cells} == {c.cell_id for c in census_of(visible, items).cells}
    assert len({c.cell_id for c in got.cells}) == 2


# --- the diagnostic against the strip finder it claims to mirror ------------------------------------------------------------


def _sibling_strips(ink):
    import pb_source_plan_glazing_strip_callout_shadow as S

    scope = S.PlanCalloutStripScope(
        ownership=S.SourceOwnership("d", "r", "s", "a" * 64, S.PRODUCER_INPUT_PROVENANCE), plan_page_id="1",
        elevation_page_id="2", callout_mark_pattern=r"[WD]\d+", coordinate_quantum_pt=Q, dimension_quantum_mm=5.0,
        plan_viewports=(S.PlanViewportRef("v", (0.0, 0.0, 2000.0, 2000.0)),))
    return S.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=[], elevation_types=[]).strips


def _ink(visible, items):
    import pb_source_plan_glazing_strip_callout_shadow as S

    out = [S.PlanInkSegment(v.observation_id, *v.geometry, v.stroke_width, True) for v in visible]
    out += [S.PlanInkSegment(i.item_id, *i.geometry, i.stroke_width, max(i.stroke_rgb) <= 0.1,
                             continuous_opaque=i.solid and i.stroke_opacity == 1.0) for i in items]
    return out


VARIANTS = [
    ("hidden_ticks", dict(glass=0.48), 1),
    ("visible_ticks", dict(glass=0.72), 1),
    ("two_panels_hidden", dict(glass=0.48, length=110.0, panels=2, hidden="all"), 2),
    ("lo_only", dict(glass=0.48, hidden="lo"), 1),
    ("no_ticks", dict(glass=0.48, hidden="none"), 1),
    ("too_short", dict(glass=0.48, hidden_geometry=lambda pos, p0, p1: (pos, p0, pos, p0 + 0.4)), 1),
    ("overshooting", dict(glass=0.48, hidden_geometry=lambda pos, p0, p1: (pos, p0 - 0.1, pos, p1)), 1),
    ("wrong_width", dict(glass=0.48, tick_width=0.24), 1),
    ("oblique", dict(glass=0.48, hidden_geometry=lambda pos, p0, p1: (pos - 0.2, p0, pos + 0.2, p1)), 1),
    ("beyond_lines", dict(glass=0.48, hidden_geometry=lambda pos, p0, p1: (pos - 4.0 if pos < 130 else pos + 4.0, p0,
                                                                          pos - 4.0 if pos < 130 else pos + 4.0, p1)), 1),
    ("off_centre", dict(glass=0.48, rebate_shift=0.6), 1),
    ("shallow_frame", dict(glass=0.48, depth=1.2), 1),
]


@pytest.mark.parametrize("name, kwargs, panels", VARIANTS, ids=[v[0] for v in VARIANTS])
def test_the_diagnostic_agrees_with_the_strip_finder_on_ink_with_and_without_the_hidden_ticks(name, kwargs, panels):
    visible, items, _ = window(**kwargs)
    before = _sibling_strips(_ink(visible, []))
    after = _sibling_strips(_ink(visible, items))
    diagnostic = census_of(visible, items).would_close_cell
    assert diagnostic is (len(after) > len(before)), (name, len(before), len(after))
    if diagnostic:
        assert len(after) == 1 and after[0].panel_count == panels and after[0].band == pytest.approx((300.0, 305.52))
        assert len(before) == 0


# --- contract ---------------------------------------------------------------------------------------------------------------


def test_every_grant_is_false_enforced_and_the_census_issues_no_existence_record():
    visible, items, _ = window()
    got = census_of(visible, items)
    for flag in C._GRANT_FLAGS:
        assert getattr(got, flag) is False
        with pytest.raises(ValueError, match="cannot grant"):
            replace(got, **{flag: True})
    with pytest.raises(ValueError):
        replace(got, shadow_only=False)
    with pytest.raises(ValueError):
        replace(got, status=EvidenceResolutionStatus.CORROBORATED)
    assert got.takeoff_eligible is False and got.deduction_authority is False and got.existence_record_issued is False
    assert all(got.evidence_atoms[0].metadata[flag] is False for flag in C._GRANT_FLAGS)


def test_a_candidate_cannot_be_constructed_without_a_completed_clear_cell_and_the_single_reason():
    visible, items, _ = window(glass=0.72)
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(census_of(visible, items), status=CAND)
    visible, items, _ = window(glass=0.48)
    good = census_of(visible, items)
    assert good.status is CAND
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(good, reason_codes=(C.SUB_FLOOR_TICKS_WOULD_CLOSE_CELL, C.CLOSURE_AMBIGUOUS))
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(good, visible_inventory_complete=False)
    blocked = replace(good.cells[0], completion_paint="unproven")
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(good, cells=(blocked,))
    displaced = C.DisplacedVisibleCell(0.48, (BLACK,), (302.4, 303.12), (102.64, 157.36), ("d0i0",))
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(good, displaced_visible_cells=(displaced,))


def test_atoms_carry_the_ownership_root_and_only_allowed_statuses():
    visible, items, _ = window()
    got = census_of(visible, items)
    atom = got.evidence_atoms[0]
    assert (atom.document_id, atom.page_id, atom.status) == ("doc", "7", CAND)
    assert atom.metadata["revision_id"] == "rev" and atom.metadata["snapshot_id"] == "snap"
    assert atom.metadata["source_sha256"] == "a" * 64 and atom.metadata["source_observation_ids"] == got.nominated_observation_ids
    assert atom.bbox == pytest.approx(got.region)
    other = census_of(visible, items, ownership=replace(OWN, snapshot_id="other"))
    assert other.record_id != got.record_id and other.nomination_id != got.nomination_id
    assert got.ownership == OWN and got.viewport_id == "view_plan"


def test_invalid_requests_are_refused_not_guessed():
    visible, items, _ = window()
    with pytest.raises(ValueError, match="exactly one"):
        run(items, visible)
    with pytest.raises(ValueError, match="exactly one"):
        run(items, visible, region=(0.0, 0.0, 1.0, 1.0), nominated=("wtop",))
    for quantum in (0.0, -1.0, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="quantum"):
            run(items, visible, region=(0.0, 0.0, 1.0, 1.0), quantum=quantum)
    for region in ((5.0, 0.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, float("nan"), 1.0), (0.0, 0.0, 1.0)):
        with pytest.raises(ValueError):
            run(items, visible, region=region)
    with pytest.raises(ValueError, match="boolean"):
        run(items, visible, region=(0.0, 0.0, 1.0, 1.0), complete=1)


def test_work_bounds_abstain_instead_of_truncating(monkeypatch):
    visible, items, _ = window()
    monkeypatch.setattr(C, "_MAX_SUB_FLOOR_ITEMS", 1)
    got = census_of(visible, items)
    assert got.status is ABST and got.reason_codes == (C.ITEM_BUDGET_EXCEEDED,) and got.sub_floor_items == ()
    monkeypatch.setattr(C, "_MAX_SUB_FLOOR_ITEMS", 100)
    monkeypatch.setattr(C, "_MAX_CLOSURE_STROKES", 3)
    assert census_of(visible, items).reason_codes == (C.ITEM_BUDGET_EXCEEDED,)


# --- metamorphic -------------------------------------------------------------------------------------------------------------


def _shift_paint(log, dx, dy):
    def box(b):
        return (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)

    return C.PaintLog(tuple(replace(
        o, bbox=box(o.bbox), opaque_cover=box(o.opaque_cover) if o.opaque_cover else None,
        stroke_segments=tuple((s[0] + dx, s[1] + dy, s[2] + dx, s[3] + dy, s[4]) for s in o.stroke_segments)
        if o.stroke_segments else None) for o in log.ops), log.aligned, log.unproven_reason)


def _shift(visible, items, dx, dy):
    return ([replace(v, geometry=(v.geometry[0] + dx, v.geometry[1] + dy, v.geometry[2] + dx, v.geometry[3] + dy)) for v in visible],
            [replace(i, geometry=(i.geometry[0] + dx, i.geometry[1] + dy, i.geometry[2] + dx, i.geometry[3] + dy)) for i in items])


def _summary(got, origin=(0.0, 0.0)):
    ox, oy = origin
    rel = lambda g: tuple(round(v - (ox if k % 2 == 0 else oy), 3) for k, v in enumerate(g))   # noqa: E731
    return (got.status, got.reason_codes, got.would_close_cell,
            [(i.item_id, i.kind, round(i.length, 2), i.orientation, rel(i.geometry), i.paint_order, i.endpoints_coincide_visible,
              i.endpoint_a_visible_ids, i.endpoint_b_visible_ids, i.touches_band_edge) for i in got.sub_floor_items],
            [(g.stroke_width, g.stroke_rgb, g.orientation, g.length_bucket, g.count) for g in got.groups],
            [(round(c.pane_lines[0] - oy, 3), round(c.pane_lines[1] - oy, 3), round(c.along[0] - ox, 3), round(c.along[1] - ox, 3),
              c.lo_tick.support, c.hi_tick.support, c.would_close_cell, c.completion_paint) for c in got.cells])


def _scene():
    visible, items, _ = window(glass=0.48)
    more = [raw(10, 120.0, 300.0, 120.3, 300.0), raw(11, 130.0, 305.52, 130.0, 305.9)]
    cover = C.PaintOp(50, "fill-path", (500.0, 500.0, 600.0, 600.0), 9, (500.0, 500.0, 600.0, 600.0))
    return visible, items + more, C.PaintLog((cover,), True)


def test_translation_does_not_change_the_census():
    visible, items, log = _scene()
    base = census_of(visible, items, paint=log)
    for dx, dy in ((1234.13, -77.77), (-250.5, 810.25)):
        v2, i2 = _shift(visible, items, dx, dy)
        moved = run(i2, v2, nominated=nominate(v2), paint=_shift_paint(log, dx, dy),
                    viewports=(C.ViewportRef("v", (-9e3, -9e3, 9e3, 9e3)),))
        assert _summary(moved, (dx, dy)) == _summary(base)


def test_input_order_and_splitting_the_visible_ink_do_not_change_the_census():
    visible, items, log = _scene()
    base = _summary(census_of(visible, items, paint=log))
    rng = random.Random(7)
    for _ in range(5):
        v, i = list(visible), list(items)
        rng.shuffle(v)
        rng.shuffle(i)
        ids = nominate(visible)
        rng.shuffle(list_ids := list(ids))
        assert _summary(run(i, v, nominated=tuple(list_ids), paint=log)) == base
    # a visible frame line exported in two collinear pieces is the same line
    split = [vis("wtop_a", 100.0, 300.0, 130.0, 300.0), vis("wtop_b", 130.0, 300.0, 160.0, 300.0)] + [
        v for v in visible if v.observation_id != "wtop"]
    got = run(items, split, nominated=("wtop_a", "wtop_b") + tuple(i for i in nominate(visible) if i != "wtop"), paint=log)
    assert got.status is CAND and [c.pane_lines for c in got.cells] == [c.pane_lines for c in census_of(visible, items).cells]


def test_a_quarter_turn_swaps_the_axes_and_keeps_the_verdict():
    visible, items, log = _scene()
    base = census_of(visible, items, paint=log)
    swap = lambda g: (g[1], g[0], g[3], g[2])   # noqa: E731
    v2 = [replace(v, geometry=swap(v.geometry)) for v in visible]
    i2 = [replace(i, geometry=swap(i.geometry)) for i in items]
    log2 = C.PaintLog(tuple(replace(o, bbox=swap(o.bbox), opaque_cover=swap(o.opaque_cover) if o.opaque_cover else None)
                            for o in log.ops), True)
    turned = run(i2, v2, nominated=nominate(v2), paint=log2)
    assert (turned.axis, base.axis) == ("V", "H")
    assert turned.status is base.status and turned.reason_codes == base.reason_codes
    assert [(c.pane_lines, c.along, c.would_close_cell) for c in turned.cells] == [(c.pane_lines, c.along, c.would_close_cell) for c in base.cells] \
        or [(round(c.pane_lines[0] - 300.0, 3), round(c.along[0], 3)) for c in turned.cells] == \
        [(round(c.pane_lines[0] - 300.0, 3), round(c.along[0], 3)) for c in base.cells]
    assert sorted(i.orientation for i in turned.sub_floor_items) == sorted({"H": "V", "V": "H"}[i.orientation]
                                                                          for i in base.sub_floor_items)


def test_unrelated_content_far_from_the_strip_and_viewport_expansion_change_nothing():
    visible, items, log = _scene()
    quiet = _summary(census_of(visible, items, paint=log))
    noisy_items = items + [raw(100 + k, 1500.0 + k, 1500.0, 1500.0 + k, 1500.3) for k in range(300)]
    noisy_visible = visible + [vis(f"x{k}", 1500.0 + k, 1500.0, 1500.0 + k, 1520.0) for k in range(300)]
    noisy_log = C.PaintLog(log.ops + tuple(C.PaintOp(60 + k, "fill-path", (1500.0, 1500.0, 1600.0, 1600.0), 200 + k,
                                                     (1500.0, 1500.0, 1600.0, 1600.0)) for k in range(50)), True)
    assert _summary(run(noisy_items, noisy_visible, nominated=nominate(visible), paint=noisy_log)) == quiet


def test_replay_is_deterministic_and_ids_are_stable():
    visible, items, log = _scene()
    first, again = census_of(visible, items, paint=log), census_of(visible, items, paint=log)
    assert first == again and first.record_id == again.record_id and first.cells[0].cell_id == again.cells[0].cell_id
    assert first.evidence_atoms[0].evidence_id == again.evidence_atoms[0].evidence_id


def test_the_core_mutates_none_of_its_inputs():
    visible, items, log = _scene()
    v_before, i_before, l_before = list(visible), list(items), log
    census_of(visible, items, paint=log)
    assert visible == v_before and items == i_before and log is l_before
    assert [id(x) for x in visible] == [id(x) for x in v_before] and [id(x) for x in items] == [id(x) for x in i_before]
    with pytest.raises(Exception):
        items[0].geometry = (0.0, 0.0, 0.0, 0.0)          # records are frozen
