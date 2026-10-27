"""Pure-core proofs for the strip face-family shadow (no PDF, no producer)."""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

import pb_strip_face_family_shadow as F
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
OWN = F.FaceFamilyOwnership("doc", "rev", "snap", "a" * 64, "7")
VP = F.ViewportRef("view_plan", (0.0, 0.0, 3000.0, 3000.0))
Q = 0.24
BLACK = (0.0, 0.0, 0.0)
# the strip: x 100..304, band y 300..305.52
LO, HI, B0, B1 = 100.0, 304.0, 300.0, 305.52


def st(oid, x0, y0, x1, y1, width=0.48, rgb=BLACK, solid=True, verified=True, opaque=True):
    return F.SourceStroke(oid, (float(x0), float(y0), float(x1), float(y1)), width if verified else None,
                          tuple(rgb) if verified else None, solid if verified else None,
                          opaque if verified else None, "line", verified, later_area_paint_clear=True)


def strip_segments(x=LO, y=B0, length=HI - LO, depth=B1 - B0, prefix="n"):
    """A horizontal strip: two long frame lines and two end ticks (the nominated ink)."""
    return [
        st(f"{prefix}1", x, y, x + length, y), st(f"{prefix}2", x, y + depth, x + length, y + depth),
        st(f"{prefix}3", x, y, x, y + depth), st(f"{prefix}4", x + length, y, x + length, y + depth),
    ]


def base():
    page = strip_segments()
    return page, [s.observation_id for s in page]


def run(page, nominated, viewport=VP, ownership=OWN, quantum=Q):
    return F.audit_strip_face_family(
        ownership=ownership, viewport=viewport, nominated_ids=nominated, page_strokes=page,
        coordinate_quantum_pt=quantum)


def face(page, oid, y, x0, x1, **kw):
    page.append(st(oid, x0, y, x1, y, **kw))


def groups_at(got, offset, tol=1e-6):
    return [g for g in got.groups if abs(g.offset_pt - offset) <= tol]


# --- the verdicts --------------------------------------------------------------------------------


def test_a_continuous_black_face_line_through_the_strip_is_a_candidate_with_its_signed_offset():
    page, ids = base()
    face(page, "f1", 296.0, 20.0, 400.0, width=0.96)
    got = run(page, ids)
    assert got.status is CAND and got.reason_codes == (F.FACE_FAMILY_CONTINUOUS,)
    assert got.axis == "H" and got.along_extent == (LO, HI) and got.band_extent == (B0, B1)
    (g,) = groups_at(got, -4.0)
    assert g.stroke_width == 0.96 and g.stroke_rgb == BLACK and g.black and g.solid is True and g.role_verified
    assert g.member_observation_ids == ("f1",) and g.nominated_member_ids == ()
    assert g.covers_whole_extent and g.extends_past_lo and g.extends_past_hi and g.through_both_terminals
    assert g.along_intervals == ((20.0, 400.0),) and g.uncovered_within_extent == () and not g.inside_band
    assert got.continuous_group_ids == (g.group_id,) and got.conflicted_group_ids == ()
    assert got.evidence_atoms[0].status is CAND and got.evidence_atoms[0].metadata["continuous_group_ids"] == (g.group_id,)


def test_the_hi_side_offset_is_positive_and_measured_from_the_band_edge():
    page, ids = base()
    face(page, "f1", 310.52, 20.0, 400.0)
    got = run(page, ids)
    assert got.status is CAND
    assert groups_at(got, 5.0)[0].member_observation_ids == ("f1",)


def test_a_face_line_broken_at_the_terminals_is_not_a_through_line_and_the_break_is_reported():
    page, ids = base()
    face(page, "left", 296.0, 20.0, LO)
    face(page, "right", 296.0, HI, 400.0)
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    (g,) = groups_at(got, -4.0)
    assert g.member_observation_ids == ("left", "right")
    assert not g.covers_whole_extent and not g.through_both_terminals
    assert not g.extends_past_lo and not g.extends_past_hi            # both pieces end AT the terminals
    assert g.uncovered_within_extent == ((LO, HI),) and g.along_intervals == ((20.0, LO), (HI, 400.0))


def test_a_face_line_broken_inside_the_strip_extent_reports_the_gap_and_both_runs_past_the_terminals():
    page, ids = base()
    face(page, "left", 296.0, 20.0, 180.0)
    face(page, "right", 296.0, 220.0, 400.0)
    got = run(page, ids)
    assert got.status is ABST
    (g,) = groups_at(got, -4.0)
    assert g.extends_past_lo and g.extends_past_hi and not g.covers_whole_extent and not g.through_both_terminals
    assert g.uncovered_within_extent == ((180.0, 220.0),)


def test_a_face_line_stopping_short_of_one_terminal_is_not_through():
    page, ids = base()
    face(page, "short", 296.0, 20.0, 250.0)
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    (g,) = groups_at(got, -4.0)
    assert g.extends_past_lo and not g.extends_past_hi and not g.covers_whole_extent
    assert g.uncovered_within_extent == ((250.0, HI),)


def test_a_line_that_starts_inside_the_extent_and_runs_out_is_reported_with_its_leading_gap():
    page, ids = base()
    face(page, "late", 296.0, 150.0, 400.0)
    (g,) = groups_at(run(page, ids), -4.0)
    assert not g.extends_past_lo and g.extends_past_hi and g.uncovered_within_extent == ((LO, 150.0),)


def test_face_lines_on_both_sides_are_both_retained_and_none_is_selected():
    page, ids = base()
    face(page, "lo_side", 296.0, 20.0, 400.0)
    face(page, "hi_side", 310.52, 20.0, 400.0)
    face(page, "far", 150.0, 20.0, 400.0)                    # a long line far away is inventoried too
    got = run(page, ids)
    assert got.status is CAND
    outside = [g for g in got.groups if not g.inside_band]
    assert [round(g.offset_pt, 6) for g in outside] == [-150.0, -4.0, 5.0]
    assert len(got.continuous_group_ids) == 3 and set(got.continuous_group_ids) == {g.group_id for g in outside}
    names = {f.name for f in F.StripFaceFamily.__dataclass_fields__.values()}
    assert not ({"nearest", "selected", "best", "first", "host_wall_id", "face_line_id"} & names)


def test_double_ink_is_one_group_with_every_duplicate_member_retained():
    page, ids = base()
    face(page, "a", 296.0, 20.0, 400.0)
    face(page, "b", 296.0, 20.0, 400.0)
    single_page, single_ids = base()
    face(single_page, "a", 296.0, 20.0, 400.0)
    got, single = run(page, ids), run(single_page, single_ids)
    (g,), (s,) = groups_at(got, -4.0), groups_at(single, -4.0)
    assert g.member_observation_ids == ("a", "b") and s.member_observation_ids == ("a",)
    assert (g.along_intervals, g.covers_whole_extent, g.through_both_terminals, g.offset_pt) == (
        s.along_intervals, s.covers_whole_extent, s.through_both_terminals, s.offset_pt)
    assert got.status is single.status is CAND


def test_collinear_splitting_does_not_change_the_group_or_the_verdict():
    page, ids = base()
    face(page, "whole", 296.0, 20.0, 400.0)
    split_page, split_ids = base()
    for k, (a, b) in enumerate([(20.0, 60.0), (60.0, 200.0), (200.0, 203.9), (203.9, 400.0)]):
        face(split_page, f"p{k}", 296.0, a, b)
    (g,), (s,) = groups_at(run(page, ids), -4.0), groups_at(run(split_page, split_ids), -4.0)
    assert (s.along_intervals, s.covers_whole_extent, s.extends_past_lo, s.extends_past_hi, s.through_both_terminals,
            s.uncovered_within_extent) == (g.along_intervals, g.covers_whole_extent, g.extends_past_lo,
                                           g.extends_past_hi, g.through_both_terminals, g.uncovered_within_extent)
    assert s.member_observation_ids == ("p0", "p1", "p2", "p3")
    assert run(split_page, split_ids).status is CAND


def test_pieces_meet_within_a_quarter_quantum_but_a_whole_quantum_gap_is_a_gap():
    page, ids = base()
    face(page, "a", 296.0, 20.0, 180.0)
    face(page, "b", 296.0, 180.05, 400.0)                    # 0.05 pt <= quantum / 4: the ink is continuous
    assert run(page, ids).status is CAND
    page2, ids2 = base()
    face(page2, "a", 296.0, 20.0, 180.0)
    face(page2, "b", 296.0, 180.24, 400.0)                   # one whole quantum: a real gap
    got = run(page2, ids2)
    assert got.status is ABST
    (g,) = groups_at(got, -4.0)
    assert g.uncovered_within_extent == ((180.0, 180.24),) or (
        len(g.uncovered_within_extent) == 1 and g.uncovered_within_extent[0][0] == pytest.approx(180.0)
        and g.uncovered_within_extent[0][1] == pytest.approx(180.24))


def test_mixed_widths_at_one_offset_are_kept_apart_and_both_retained():
    page, ids = base()
    face(page, "thin", 296.0, 20.0, 400.0, width=0.48)
    face(page, "thick", 296.0, 20.0, 400.0, width=0.96)
    got = run(page, ids)
    pair = groups_at(got, -4.0)
    assert sorted(g.stroke_width for g in pair) == [0.48, 0.96] and got.status is CAND
    assert len(got.continuous_group_ids) == 2


def test_a_through_group_and_a_broken_group_of_another_width_at_one_offset_is_a_conflict_with_both_retained():
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0, width=0.48)
    face(page, "tick", 296.0, 190.0, 200.0, width=0.96)       # a thicker stroke at the same offset, inside the strip
    got = run(page, ids)
    assert got.status is CONF
    assert got.reason_codes == (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, F.FACE_FAMILY_SAME_OFFSET_BROKEN)
    pair = groups_at(got, -4.0)
    assert {g.stroke_width for g in pair} == {0.48, 0.96}
    assert set(got.conflicted_group_ids) == {g.group_id for g in pair} and got.continuous_group_ids == ()
    assert got.evidence_atoms[0].status is CONF


def test_a_broken_group_at_another_offset_does_not_conflict_with_a_clean_through_line():
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0)
    face(page, "stub", 292.0, 190.0, 200.0)                   # a different offset altogether
    got = run(page, ids)
    assert got.status is CAND and got.conflicted_group_ids == ()
    assert len(groups_at(got, -8.0)) == 1 and len(groups_at(got, -4.0)) == 1


def test_a_conflicted_offset_elsewhere_makes_the_whole_verdict_a_conflict_not_a_candidate():
    page, ids = base()
    face(page, "clean", 310.52, 20.0, 400.0)
    face(page, "through", 296.0, 20.0, 400.0)
    face(page, "tick", 296.0, 190.0, 200.0, width=0.96)
    got = run(page, ids)
    assert got.status is CONF
    assert len(got.conflicted_group_ids) == 2 and got.continuous_group_ids == (groups_at(got, 5.0)[0].group_id,)


def test_across_snapping_is_single_linkage_at_a_quarter_quantum():
    page, ids = base()
    face(page, "a", 296.0, 20.0, 400.0)
    face(page, "b", 296.05, 20.0, 400.0)                     # within quantum / 4: the same offset, the same width
    got = run(page, ids)
    (g,) = [g for g in got.groups if not g.inside_band]
    assert g.member_observation_ids == ("a", "b") and g.across_span == (296.0, 296.05)
    assert g.across_pt == pytest.approx(296.025) and g.offset_pt == pytest.approx(-3.975)
    page2, ids2 = base()
    face(page2, "a", 296.0, 20.0, 400.0)
    face(page2, "b", 296.24, 20.0, 400.0)                    # a whole quantum away: a different offset
    assert len([g for g in run(page2, ids2).groups if not g.inside_band]) == 2


def test_same_offset_means_a_snapped_neighbour_even_when_the_width_differs():
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0, width=0.48)
    face(page, "tick", 296.05, 190.0, 200.0, width=0.96)     # 0.05 pt away: the same snapped offset
    assert run(page, ids).status is CONF
    page2, ids2 = base()
    face(page2, "through", 296.0, 20.0, 400.0, width=0.48)
    face(page2, "tick", 296.24, 190.0, 200.0, width=0.96)    # a whole quantum away: another offset
    assert run(page2, ids2).status is CAND


# --- what a through line must be ------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", [
    dict(rgb=(0.5, 0.5, 0.5)),                  # grey
    dict(rgb=(1.0, 0.0, 0.0)),                  # red
    dict(solid=False),                          # dashed
    dict(solid=None),                           # the producer states no dash pattern
    dict(opaque=False),                         # translucent: a faint line is not a continuous black line
    dict(opaque=None),                          # opacity not proved
    dict(verified=False),                       # width / colour not proved by the producer
])
def test_a_line_that_is_not_black_solid_and_producer_verified_never_makes_a_candidate(kwargs):
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0, **kwargs)
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    (g,) = groups_at(got, -4.0)
    assert g.through_both_terminals and g.member_observation_ids == ("f",)       # still inventoried
    assert not F._is_through(g) and g.group_id not in got.continuous_group_ids


def test_an_unverified_stroke_is_grouped_apart_with_no_invented_width_or_colour():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0, verified=False)
    (g,) = groups_at(run(page, ids), -4.0)
    assert g.stroke_width is None and g.stroke_rgb is None and g.solid is None and not g.role_verified


def test_an_unverified_stroke_at_a_through_offset_that_is_broken_keeps_the_conflict():
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0)
    face(page, "mystery", 296.0, 190.0, 200.0, verified=False)
    got = run(page, ids)
    assert got.status is CONF and len(got.conflicted_group_ids) == 2


def test_a_through_line_inside_the_band_is_reported_but_never_the_face_family():
    page, ids = base()
    face(page, "flush", B0, 20.0, 400.0)                      # collinear with the strip's own frame line
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    inside = [g for g in got.groups if g.inside_band]
    assert any(g.through_both_terminals and "flush" in g.member_observation_ids and "n1" in g.nominated_member_ids
               for g in inside)
    assert all(g.offset_pt == 0.0 for g in inside)


def test_the_strips_own_lines_are_inventoried_as_in_band_groups_that_are_not_through():
    page, ids = base()
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    assert [g.across_pt for g in got.groups] == [B0, B1]
    assert all(g.inside_band and not g.through_both_terminals and g.covers_whole_extent for g in got.groups)
    assert got.groups[0].nominated_member_ids == ("n1",) and got.groups[1].nominated_member_ids == ("n2",)


def test_perpendicular_oblique_and_non_overlapping_strokes_are_not_in_the_inventory():
    page, ids = base()
    page += [st("perp", 50, 280, 50, 330), st("obl", 20, 280, 400, 330),
             st("after", 400.0, 296.0, 500.0, 296.0), st("before", 20.0, 296.0, 99.9, 296.0)]
    got = run(page, ids)
    assert [g for g in got.groups if not g.inside_band] == []
    assert not any(m in {"perp", "obl", "after", "before"} for g in got.groups for m in g.member_observation_ids)
    page.append(st("touch", 20.0, 297.0, 99.95, 297.0))       # within quantum / 4 of the lo terminal: it meets the extent
    assert any("touch" in g.member_observation_ids for g in run(page, ids).groups)


def test_a_stroke_elsewhere_on_the_page_can_never_bridge_two_offsets_that_are_further_apart_than_the_snap():
    # single linkage must not chain through content that is not on the strip, or the inventory would depend on
    # unrelated drawing
    page, ids = base()
    face(page, "a", 296.0, 20.0, 400.0)
    face(page, "b", 296.10, 20.0, 400.0)                      # 0.10 pt apart: more than quantum / 4 = 0.06
    quiet = run(page, ids)
    assert len([g for g in quiet.groups if not g.inside_band]) == 2
    bridged = list(page)
    face(bridged, "far", 296.05, 900.0, 950.0)               # within the snap of both, but 500 pt along the page
    face(bridged, "far_thick", 296.05, 900.0, 950.0, width=0.96)
    noisy = run(bridged, ids)
    assert _flags(noisy) == _flags(quiet)
    assert [g.group_id for g in noisy.groups] == [g.group_id for g in quiet.groups]
    assert not any("far" in g.member_observation_ids or "far_thick" in g.member_observation_ids for g in noisy.groups)


def test_a_continuation_beyond_the_strip_joins_only_a_group_of_the_same_paint_within_the_snap():
    page, ids = base()
    face(page, "main", 296.0, 20.0, 150.0)
    face(page, "same_next", 296.03, 150.0, 400.0)             # touches the main piece, 0.03 off: the same line
    face(page, "other_width", 296.0, 20.0, 99.0, width=0.96)  # another paint, and it ends before the strip
    face(page, "too_far_across", 296.20, 50.0, 99.0)          # would continue the line but sits a whole snap away
    got = run(page, ids)
    (g,) = [g for g in got.groups if not g.inside_band]
    assert g.member_observation_ids == ("main", "same_next") and g.through_both_terminals
    assert g.along_intervals == ((20.0, 400.0),)
    assert got.status is CAND


def test_a_continuation_within_the_snap_of_two_offsets_is_retained_in_both_and_never_assigned_by_distance():
    page, ids = base()
    face(page, "a", 296.00, 99.0, 200.0)
    face(page, "b", 296.10, 99.0, 200.0)                      # a second offset, 0.10 pt away
    face(page, "lead", 296.05, 20.0, 99.0)                    # ends before the strip; 0.05 from each: continues both
    got = run(page, ids)
    outside = [g for g in got.groups if not g.inside_band]
    assert len(outside) == 2
    assert all("lead" in g.member_observation_ids for g in outside)
    assert [g.member_observation_ids for g in outside] == [("a", "lead"), ("b", "lead")]
    assert all(g.along_intervals == ((20.0, 200.0),) and g.extends_past_lo for g in outside)


def test_a_slightly_tilted_stroke_within_the_quantum_snap_counts_as_parallel():
    page, ids = base()
    page.append(st("tilt", 20.0, 296.0, 400.0, 296.05))
    (g,) = [g for g in run(page, ids).groups if not g.inside_band]
    assert g.through_both_terminals and g.across_pt == pytest.approx(296.025)


def test_a_non_black_line_at_another_offset_is_inventoried_but_never_part_of_the_continuous_set():
    page, ids = base()
    face(page, "grey", 290.0, 20.0, 400.0, rgb=(0.5, 0.5, 0.5))
    face(page, "black", 296.0, 20.0, 400.0)
    got = run(page, ids)
    assert got.status is CAND and got.continuous_group_ids == (groups_at(got, -4.0)[0].group_id,)
    assert len(groups_at(got, -10.0)) == 1
    assert groups_at(got, -10.0)[0].group_id not in got.continuous_group_ids


def test_a_translucent_black_line_is_kept_apart_from_an_opaque_one_and_a_broken_translucent_rival_is_a_conflict():
    page, ids = base()
    face(page, "ink", 296.0, 20.0, 400.0)
    face(page, "faint", 296.0, 190.0, 200.0, opaque=False)           # same offset, same width, not opaque
    got = run(page, ids)
    assert got.status is CONF and F.FACE_FAMILY_SAME_OFFSET_BROKEN in got.reason_codes
    assert {g.opaque for g in groups_at(got, -4.0)} == {True, False}
    assert len(got.conflicted_group_ids) == 2
    only_faint, only_faint_ids = base()
    face(only_faint, "faint", 296.0, 20.0, 400.0, opaque=False)
    faint = run(only_faint, only_faint_ids)
    assert faint.status is ABST and faint.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    assert groups_at(faint, -4.0)[0].through_both_terminals and groups_at(faint, -4.0)[0].opaque is False


# --- vertical strips: axis, sign, and the swap ----------------------------------------------------------


def transpose(page):
    return [replace(s, geometry=(s.geometry[1], s.geometry[0], s.geometry[3], s.geometry[2])) for s in page]


def test_a_vertical_strip_has_the_same_offsets_and_flags_as_its_transpose():
    page, ids = base()
    face(page, "lo", 296.0, 20.0, 400.0)
    face(page, "hi", 310.52, 20.0, 250.0)
    horizontal = run(page, ids)
    vertical = run(transpose(page), ids)
    assert vertical.axis == "V" and horizontal.axis == "H" and vertical.status is horizontal.status
    assert vertical.along_extent == horizontal.along_extent and vertical.band_extent == horizontal.band_extent
    assert _flags(vertical) == _flags(horizontal)


# --- nomination, ownership, viewport failures -------------------------------------------------------------


def test_an_empty_duplicate_or_foreign_nomination_abstains():
    page, ids = base()
    assert run(page, []).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert run(page, ids + [ids[0]]).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert run(page, ids + ["not-on-this-page"]).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert run(page, ids + [ids[0]]).groups == ()


def test_a_nominated_segment_without_a_verified_source_role_abstains():
    page, ids = base()
    page[1] = st("n2", LO, B1, HI, B1, verified=False)
    got = run(page, ids)
    assert got.status is ABST and F.SOURCE_ROLE_UNPROVEN in got.reason_codes
    assert SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE in got.reason_codes and got.groups == ()


def test_duplicate_observation_ids_on_the_page_are_an_integrity_failure():
    page, ids = base()
    page.append(st("n1", 0, 0, 10, 0))
    assert run(page, ids).reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


@pytest.mark.parametrize("bad", [
    dict(geometry=(0.0, 296.0, float("nan"), 296.0)), dict(geometry=(0.0, 296.0, float("inf"), 296.0)),
    dict(geometry=(0.0, 296.0, 400.0)), dict(stroke_width=float("nan")), dict(stroke_rgb=(0.0, float("inf"), 0.0)),
])
def test_a_malformed_page_stroke_is_an_integrity_failure_not_ink_that_is_quietly_left_out(bad):
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0)
    page.append(replace(st("rival", 0, 296.0, 10, 296.0), **bad))
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.groups == ()


def test_oblique_or_square_nominations_abstain_instead_of_picking_an_axis():
    page, ids = base()
    page.append(st("d", 100, 300, 150, 340))
    assert run(page, ids + ["d"]).reason_codes == (F.NOMINATION_NOT_AXIS_ALIGNED,)
    square = [st("s1", 0, 0, 10, 0), st("s2", 0, 10, 10, 10), st("s3", 0, 0, 0, 10), st("s4", 10, 0, 10, 10)]
    assert run(square, ["s1", "s2", "s3", "s4"]).reason_codes == (F.NOMINATION_AXIS_AMBIGUOUS,)


def test_a_missing_or_non_containing_viewport_abstains_with_the_existing_scope_code():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    assert run(page, ids, viewport=None).reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
    far = F.ViewportRef("elsewhere", (1000.0, 1000.0, 1500.0, 1500.0))
    got = run(page, ids, viewport=far)
    assert got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,) and got.groups == ()
    cropped = F.ViewportRef("cropped", (0.0, 0.0, 200.0, 3000.0))
    assert run(page, ids, viewport=cropped).reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)


def test_the_work_bound_abstains_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(F, "_MAX_GROUPS", 2)
    page, ids = base()
    for k in range(3):
        face(page, f"f{k}", 280.0 + 3.0 * k, 20.0, 400.0)
    got = run(page, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_BUDGET_EXCEEDED,) and got.groups == ()
    monkeypatch.setattr(F, "_MAX_GROUPS", 100)
    assert run(page, ids).status is CAND


# --- contract ------------------------------------------------------------------------------------------


def test_every_grant_is_false_enforced_and_the_inventory_issues_no_existence_record():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    got = run(page, ids)
    for flag in F._GRANT_FLAGS:
        assert getattr(got, flag) is False
        with pytest.raises(ValueError, match="cannot grant"):
            replace(got, **{flag: True})
    with pytest.raises(ValueError):
        replace(got, shadow_only=False)
    with pytest.raises(ValueError):
        replace(got, status=EvidenceResolutionStatus.CORROBORATED)
    assert got.standing_limits == F.STANDING_LIMITS
    assert not hasattr(got, "existence_record") and not hasattr(got, "aperture_bbox_pt")
    assert not hasattr(got, "host_candidate_id") and not hasattr(got, "candidate_wall_ids_considered")
    assert got.takeoff_eligible is False and got.deduction_authority is False


def test_a_candidate_or_conflict_cannot_be_constructed_without_the_groups_that_support_it():
    page, ids = base()
    plain = run(page, ids)
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(plain, status=CAND, snap_tolerance_pt=0.06)
    with pytest.raises(ValueError, match="CONFLICT"):
        replace(plain, status=CONF, snap_tolerance_pt=0.06)
    face(page, "f", 296.0, 20.0, 400.0)
    good = run(page, ids)
    with pytest.raises(ValueError, match="follow from the groups"):
        replace(good, continuous_group_ids=())
    with pytest.raises(ValueError, match="CONFLICT"):
        replace(good, status=CONF)


def test_an_abstained_inventory_cannot_be_forged_to_hold_a_continuous_or_conflicted_offset():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    good = run(page, ids)
    assert good.status is CAND
    with pytest.raises(ValueError, match="ABSTAINED"):
        replace(good, status=ABST, reason_codes=(F.FACE_FAMILY_NOT_OBSERVED,))
    with pytest.raises(ValueError, match="follow from the groups"):
        replace(run(base()[0], ids), continuous_group_ids=("forged",))
    with pytest.raises(ValueError, match="quantum"):
        replace(good, snap_tolerance_pt=None, status=ABST)           # groups without the quantum they were measured at


def test_atoms_carry_the_ownership_root_and_only_allowed_statuses():
    page, ids = base()
    got = run(page, ids)
    atom = got.evidence_atoms[0]
    assert (atom.document_id, atom.page_id, atom.status) == ("doc", "7", ABST)
    assert atom.metadata["revision_id"] == "rev" and atom.metadata["snapshot_id"] == "snap"
    assert atom.metadata["source_sha256"] == "a" * 64 and atom.metadata["source_observation_ids"] == tuple(sorted(ids))
    assert all(atom.metadata[flag] is False for flag in F._GRANT_FLAGS)
    assert atom.bbox == (LO, B0, HI, B1) and atom.viewport_id == "view_plan"
    other = run(page, ids, ownership=replace(OWN, snapshot_id="other"))
    assert other.record_id != got.record_id and other.nomination_id != got.nomination_id
    assert [g.group_id for g in other.groups] != [g.group_id for g in got.groups]


def test_the_atom_is_unknown_kind_unknown_polarity_and_a_standing_limit_is_never_a_reason_code():
    from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    for got in (run(page, ids), run(base()[0], ids)):                 # a candidate and an abstention
        (atom,) = got.evidence_atoms
        assert atom.kind == KIND_UNKNOWN and atom.metadata["polarity"] == POLARITY_UNKNOWN
        assert atom.method == F.STRIP_FACE_FAMILY_METHOD and atom.reason_codes == got.reason_codes
        assert not set(F.STANDING_LIMITS) & set(got.reason_codes) and not set(F.STANDING_LIMITS) & {atom.kind}
        assert set(F.STANDING_LIMITS) == {F.FACE_LINE_WALL_ROLE_UNPROVEN, F.FACE_FAMILY_DISTANCE_UNBOUNDED}


def test_group_ids_are_scoped_to_the_page_ownership_and_the_nomination():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    a = run(page, ids)
    b = run(page, ids, ownership=replace(OWN, page_id="8"))
    c = run(page, ids, ownership=replace(OWN, document_id="doc2"))
    assert len({a.groups[0].group_id, b.groups[0].group_id, c.groups[0].group_id}) == 3


# --- metamorphic ----------------------------------------------------------------------------------------


def _mix():
    page, ids = base()
    face(page, "through", 296.0, 20.0, 400.0, width=0.96)
    face(page, "other_side_short", 310.52, 20.0, 250.0)
    face(page, "broken_l", 290.0, 20.0, 180.0)
    face(page, "broken_r", 290.0, 220.0, 400.0)
    face(page, "dup_a", 285.0, 20.0, 400.0)
    face(page, "dup_b", 285.0, 20.0, 400.0)
    return page, ids


def _flags(got):
    """Everything that is a measurement, in coordinates relative to the strip so translation cancels."""
    lo = got.along_extent[0]
    return (got.status, got.reason_codes, [
        (round(g.offset_pt, 4), g.stroke_width, g.stroke_rgb, g.solid, g.member_observation_ids, g.nominated_member_ids,
         tuple((round(a - lo, 4), round(b - lo, 4)) for a, b in g.along_intervals), g.covers_whole_extent,
         g.extends_past_lo, g.extends_past_hi, g.through_both_terminals,
         tuple((round(a - lo, 4), round(b - lo, 4)) for a, b in g.uncovered_within_extent)) for g in got.groups])


def _shift(page, dx, dy):
    return [replace(s, geometry=(s.geometry[0] + dx, s.geometry[1] + dy, s.geometry[2] + dx, s.geometry[3] + dy))
            for s in page]


def test_translation_input_order_and_unrelated_content_do_not_change_the_inventory():
    page, ids = _mix()
    reference = _flags(run(page, ids))
    assert reference[0] is CAND and len(reference[2]) == 6
    moved = run(_shift(page, 1234.13, -77.77), ids, viewport=F.ViewportRef("v", (-5000, -5000, 9000, 9000)))
    assert _flags(moved) == reference
    assert _flags(run(list(reversed(page)), list(reversed(ids)))) == reference
    noisy = page + [st(f"x{i}", 900 + i, 900, 900 + i, 920 + i) for i in range(300)]
    noisy += [st(f"h{i}", 1500 + i, 296.0 + 40 * i, 1600 + i, 296.0 + 40 * i) for i in range(50)]   # along-disjoint
    assert _flags(run(noisy, ids)) == reference
    assert _flags(run(page, ids, viewport=F.ViewportRef("huge", (-1e6, -1e6, 1e6, 1e6)))) == reference


def test_group_ids_and_the_record_id_are_translation_invariant_in_membership_but_replay_exactly():
    page, ids = _mix()
    first = run(page, ids)
    assert first == run(page, ids) and first.record_id == run(list(reversed(page)), ids).record_id
    moved = run(_shift(page, 50.0, 50.0), ids, viewport=F.ViewportRef("v", (-5000, -5000, 9000, 9000)))
    assert [g.group_id for g in moved.groups] == [g.group_id for g in first.groups]


def test_scaling_the_drawing_and_the_quantum_together_scales_the_offsets_and_keeps_every_flag():
    page, ids = _mix()
    base_run = run(page, ids)
    s = 2.0
    scaled_page = [replace(x, geometry=tuple(v * s for v in x.geometry)) for x in page]
    scaled = run(scaled_page, ids, viewport=F.ViewportRef("v", (0, 0, 9000, 9000)), quantum=Q * s)
    assert scaled.status is base_run.status and scaled.reason_codes == base_run.reason_codes
    assert [g.member_observation_ids for g in scaled.groups] == [g.member_observation_ids for g in base_run.groups]
    for a, b in zip(base_run.groups, scaled.groups):
        assert b.offset_pt == pytest.approx(a.offset_pt * s, abs=1e-9)
        assert (a.covers_whole_extent, a.extends_past_lo, a.extends_past_hi, a.through_both_terminals) == (
            b.covers_whole_extent, b.extends_past_lo, b.extends_past_hi, b.through_both_terminals)


def test_a_quarter_turn_mirrors_the_offset_sign_and_keeps_every_other_fact():
    page, ids = _mix()
    base_run = run(page, ids)
    turned = [replace(s, geometry=(-s.geometry[1], s.geometry[0], -s.geometry[3], s.geometry[2])) for s in page]
    got = run(turned, ids, viewport=F.ViewportRef("v", (-9000, -9000, 9000, 9000)))
    assert got.axis == "V" and got.status is base_run.status and got.reason_codes == base_run.reason_codes
    got_offsets = sorted((round(-g.offset_pt, 4), g.member_observation_ids) for g in got.groups)
    base_offsets = sorted((round(g.offset_pt, 4), g.member_observation_ids) for g in base_run.groups)
    assert got_offsets == base_offsets


def test_replay_is_deterministic_and_nothing_in_the_input_is_mutated():
    page, ids = _mix()
    before = [(s.observation_id, s.geometry, s.stroke_width, s.stroke_rgb, s.solid) for s in page]
    ids_before = list(ids)
    assert run(page, ids) == run(page, ids)
    assert [(s.observation_id, s.geometry, s.stroke_width, s.stroke_rgb, s.solid) for s in page] == before
    assert ids == ids_before
    assert all(math.isfinite(g.offset_pt) for g in run(page, ids).groups)


def test_inventory_is_ordered_by_signed_offset_then_across_coordinate():
    page, ids = _mix()
    got = run(page, ids)
    assert [round(g.offset_pt, 6) for g in got.groups] == [-15.0, -10.0, -4.0, 0.0, 0.0, 5.0]
    assert [g.inside_band for g in got.groups] == [False, False, False, True, True, False]
    assert [g.across_pt for g in got.groups if g.inside_band] == [B0, B1]


def test_the_through_predicate_needs_every_one_of_black_solid_verified_and_both_terminals():
    page, ids = base()
    face(page, "f", 296.0, 20.0, 400.0)
    (g,) = [g for g in run(page, ids).groups if not g.inside_band]
    assert F._is_through(g)
    for change in (dict(role_verified=False), dict(black=False), dict(solid=False), dict(solid=None),
                   dict(opaque=False), dict(opaque=None), dict(through_both_terminals=False)):
        assert not F._is_through(replace(g, **change)), change


@pytest.mark.parametrize("bad", [0, 0.0, -0.24, float("nan"), float("inf"), "0.24", None])
def test_the_core_refuses_a_missing_or_invalid_coordinate_quantum(bad):
    page, ids = base()
    with pytest.raises(ValueError, match="quantum"):
        run(page, ids, quantum=bad)
