"""Pure-core proofs for the strip structural assessment shadow (no PDF, no producer)."""
from __future__ import annotations

from dataclasses import replace

import pytest

import pb_strip_structural_assessment_shadow as A
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, GAP_CORROBORATED_WINDOW_JAMB_PAIR, JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED, VISIBLE_WALL_CONTINUATION_REQUIRED,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
OWN = A.AssessmentOwnership("doc", "rev", "snap", "a" * 64, "7")
VP = A.ViewportRef("view_plan", (0.0, 0.0, 2000.0, 2000.0))
Q = 0.24
STRONG = JAMB_BOUNDED_TWO_FACE_INTERRUPTION


def role(oid, x0, y0, x1, y1, width=0.48, verified=True):
    return A.SourceRole(oid, (float(x0), float(y0), float(x1), float(y1)), width if verified else None,
                        (0.0, 0.0, 0.0) if verified else None, "line", verified)


def strip_segments(x=100.0, y=300.0, length=204.0, depth=5.52, prefix="n"):
    """A horizontal strip: two long frame lines and two end ticks (the nominated ink)."""
    return [
        role(f"{prefix}1", x, y, x + length, y), role(f"{prefix}2", x, y + depth, x + length, y + depth),
        role(f"{prefix}3", x, y, x, y + depth), role(f"{prefix}4", x + length, y, x + length, y + depth),
    ]


def run(page, nominated, candidates=(), corroborated=(), status=None, viewport=VP, ownership=OWN):
    return A.assess_strip_hypothesis(
        ownership=ownership, viewport=viewport, nominated_ids=nominated, page_segments=page, candidates=list(candidates),
        corroborated_member_sets=frozenset(frozenset(c) for c in corroborated), member_status=status or {},
        coordinate_quantum_pt=Q)


def fragment(page, name, g0, g1, reach=60.0, y=302.4, gap=0.72):
    """A strong candidate the way the authority forms it: face pieces OUTSIDE the gap [g0, g1] on both sides,
    and two jambs that join the face-break endpoints at g0 and g1."""
    page += [role(f"{name}_fa", g0 - reach, y, g0, y), role(f"{name}_fb", g0 - reach, y + gap, g0, y + gap),
             role(f"{name}_ra", g1, y, g1 + reach, y), role(f"{name}_rb", g1, y + gap, g1 + reach, y + gap),
             role(f"{name}_ja", g0, y, g0, y + gap), role(f"{name}_jb", g1, y, g1, y + gap)]
    return tuple(sorted(f"{name}_{k}" for k in ("fa", "fb", "ra", "rb", "ja", "jb")))


def base():
    page = strip_segments()
    ids = [r.observation_id for r in page]
    return page, ids


# --- the verdicts --------------------------------------------------------------------------------


def test_no_overlapping_fragment_abstains_with_the_existing_wall_continuation_code():
    page, ids = base()
    got = run(page, ids)
    assert got.status is ABST and VISIBLE_WALL_CONTINUATION_REQUIRED in got.reason_codes
    assert A.TERMINAL_ROLE_UNPROVEN in got.reason_codes and got.fragments == ()
    assert got.axis == "H" and got.along_extent == (100.0, 304.0) and got.band_extent == (300.0, 305.52)


def test_a_corroborated_strong_candidate_spanning_the_whole_extent_is_the_only_way_to_a_candidate():
    page, ids = base()
    members = fragment(page, "w", 100, 304)
    got = run(page, ids, [("w", STRONG, members)], corroborated=[members], status={m: "corroborated" for m in members})
    assert got.status is CAND and A.WHOLE_EXTENT_CANDIDATE_PRESENT in got.reason_codes
    assert got.fragments[0].spans_whole_extent and got.fragments[0].existence == "corroborated"
    assert A.TERMINAL_ROLE_UNPROVEN in got.reason_codes          # a candidate never says the terminals are proven
    assert got.evidence_atoms[0].status is CAND


def test_overlapping_post_gap_fragments_without_a_whole_extent_candidate_keep_the_conflict():
    page, ids = base()
    left = ("left", STRONG, fragment(page, "left", 164.0, 166.88, reach=64.0))      # an interior post gap
    right = ("right", STRONG, fragment(page, "right", 232.0, 234.64, reach=64.0))   # the next post gap
    corro = [left[2], right[2]]
    got = run(page, ids, [left, right], corroborated=corro, status={m: "corroborated" for c in corro for m in c})
    assert got.status is CONF
    assert AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in got.reason_codes and A.FRAGMENTS_ONLY in got.reason_codes
    assert [f.existence for f in got.fragments] == ["corroborated", "corroborated"]
    assert all(not f.spans_whole_extent for f in got.fragments)
    assert [f.gap_span for f in got.fragments] == [(164.0, 166.88), (232.0, 234.64)]
    assert not any(f.gap_crosses_lo_terminal or f.gap_crosses_hi_terminal for f in got.fragments)
    assert {f.candidate_id for f in got.fragments} == {"left", "right"}


def test_a_whole_extent_candidate_with_any_other_overlapping_fragment_is_a_conflict_not_a_choice():
    page, ids = base()
    whole = ("whole", STRONG, fragment(page, "whole", 100, 304))
    part = ("part", STRONG, fragment(page, "part", 164.0, 166.88))
    got = run(page, ids, [whole, part], corroborated=[whole[2]], status={m: "corroborated" for m in whole[2]})
    assert got.status is CONF and AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in got.reason_codes
    assert {f.candidate_id for f in got.fragments} == {"whole", "part"}


def test_fragments_that_are_unresolved_and_not_whole_abstain_with_the_fragment_code():
    page, ids = base()
    got = run(page, ids, [("c", STRONG, fragment(page, "c", 164.0, 166.88))], status={})
    assert got.status is ABST and A.FRAGMENTS_ONLY in got.reason_codes
    assert got.fragments[0].existence == "unresolved"


def test_a_contested_whole_extent_candidate_abstains_and_keeps_the_ambiguity_code():
    page, ids = base()
    members = fragment(page, "w", 100, 304)
    got = run(page, ids, [("w", STRONG, members)], status={m: "conflict" for m in members})
    assert got.status is ABST and AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in got.reason_codes
    assert got.fragments[0].existence == "contested"


def test_generic_patterns_are_rival_evidence_only_and_never_count_as_the_whole_extent():
    page, ids = base()
    members = fragment(page, "g", 100, 304)
    got = run(page, ids, [("g", GAP_CORROBORATED_WINDOW_JAMB_PAIR, members)], corroborated=[members],
              status={m: "corroborated" for m in members})
    assert got.status is not CAND
    assert got.fragments[0].rival_evidence_only and not got.fragments[0].strong_pattern


def test_every_duplicate_geometry_class_member_and_crossing_rival_is_retained():
    page, ids = base()
    members = fragment(page, "d", 164.0, 166.88)
    dup_a = ("dup_a", STRONG, members)
    dup_b = ("dup_b", STRONG, members)                                 # same members, different candidate id
    wide = ("wide", STRONG, fragment(page, "wide", 40, 340, reach=10.0))   # an opening that starts and ends outside the strip
    got = run(page, ids, [dup_a, dup_b, wide])
    assert [f.candidate_id for f in got.fragments] == ["dup_a", "dup_b", "wide"]
    wide_f = got.fragments[2]
    assert wide_f.gap_crosses_lo_terminal and wide_f.gap_crosses_hi_terminal and wide_f.gap_span == (40.0, 340.0)
    assert wide_f.members_cross_lo_terminal and wide_f.members_cross_hi_terminal and wide_f.member_span == (30.0, 350.0)


def test_member_lines_running_past_a_terminal_are_not_the_opening_crossing_it():
    page, ids = base()
    members = fragment(page, "end", 100, 102.64, reach=75.0)    # a post gap at the strip's own lo end, faces reaching 75 pt out
    got = run(page, ids, [("end", STRONG, members)])
    f = got.fragments[0]
    assert f.members_cross_lo_terminal and not f.gap_crosses_lo_terminal and not f.spans_whole_extent
    assert f.gap_span == (100.0, 102.64) and f.member_span == (25.0, 177.64)


# --- nomination and ownership failures -----------------------------------------------------------


def test_an_empty_duplicate_or_foreign_nomination_abstains():
    page, ids = base()
    assert run(page, []).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert run(page, ids + [ids[0]]).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert run(page, ids + ["not-on-this-page"]).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)


def test_a_nominated_segment_without_a_verified_source_role_abstains():
    page, ids = base()
    page[1] = role("n2", 100, 305.52, 304, 305.52, verified=False)
    got = run(page, ids)
    assert got.status is ABST and A.SOURCE_ROLE_UNPROVEN in got.reason_codes


def test_oblique_or_square_nominations_abstain_instead_of_picking_an_axis():
    page, ids = base()
    page.append(role("d", 100, 300, 150, 340))
    assert run(page, ids + ["d"]).reason_codes == (A.NOMINATION_NOT_AXIS_ALIGNED,)
    square = [role("s1", 0, 0, 10, 0), role("s2", 0, 10, 10, 10), role("s3", 0, 0, 0, 10), role("s4", 10, 0, 10, 10)]
    assert run(square, ["s1", "s2", "s3", "s4"]).reason_codes == (A.NOMINATION_AXIS_AMBIGUOUS,)


def test_a_missing_or_non_containing_viewport_abstains_with_the_existing_scope_code():
    page, ids = base()
    assert run(page, ids, viewport=None).reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
    far = A.ViewportRef("elsewhere", (1000.0, 1000.0, 1500.0, 1500.0))
    assert run(page, ids, viewport=far).reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)


# --- terminals: what is drawn, with the producer's own widths --------------------------------------


def test_terminal_inventory_reports_every_stroke_at_each_end_with_its_own_width_and_no_threshold():
    page, ids = base()
    page += [role("pier_lo", 100, 296, 100, 310, width=0.96), role("pier_hi", 304, 300, 304, 305.52, width=0.96),
             role("wall_face", 20, 296, 400, 296, width=0.24), role("far", 600, 300, 600, 305.52)]
    got = run(page, ids)
    by = {(t.end, t.observation_id): t for t in got.terminals}
    assert ("lo", "pier_lo") in by and by[("lo", "pier_lo")].stroke_width == 0.96
    assert by[("lo", "pier_lo")].extends_beyond_band and by[("lo", "pier_lo")].spans_band
    assert by[("hi", "pier_hi")].spans_band and not by[("hi", "pier_hi")].extends_beyond_band
    assert not by[("lo", "pier_lo")].nominated and by[("lo", "n3")].nominated
    assert ("lo", "wall_face") in by and by[("lo", "wall_face")].orientation == "parallel"   # a through-line is reported too
    assert all(t.observation_id != "far" for t in got.terminals)
    assert [t.end for t in got.terminals] == sorted(t.end for t in got.terminals)


def test_the_terminal_inventory_budget_abstains_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(A, "_MAX_TERMINAL_ITEMS", 2)
    page, ids = base()
    assert run(page, ids).reason_codes == (A.TERMINAL_BUDGET_EXCEEDED,)


# --- contract ------------------------------------------------------------------------------------


def test_every_grant_is_false_enforced_and_the_assessment_issues_no_existence_record():
    page, ids = base()
    got = run(page, ids)
    for flag in A._GRANT_FLAGS:
        assert getattr(got, flag) is False
        with pytest.raises(ValueError, match="cannot grant"):
            replace(got, **{flag: True})
    with pytest.raises(ValueError):
        replace(got, shadow_only=False)
    with pytest.raises(ValueError):
        replace(got, status=EvidenceResolutionStatus.CORROBORATED)
    assert got.standing_limits == A.STANDING_LIMITS
    assert not hasattr(got, "existence_record") and not hasattr(got, "aperture_bbox_pt")
    assert not hasattr(got, "host_candidate_id") and not hasattr(got, "candidate_wall_ids_considered")


def test_a_candidate_cannot_be_constructed_without_the_one_corroborated_whole_extent_fragment():
    page, ids = base()
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(run(page, ids), status=CAND)


def test_atoms_carry_the_ownership_root_and_only_allowed_statuses():
    page, ids = base()
    got = run(page, ids)
    atom = got.evidence_atoms[0]
    assert (atom.document_id, atom.page_id, atom.status) == ("doc", "7", ABST)
    assert atom.metadata["revision_id"] == "rev" and atom.metadata["snapshot_id"] == "snap"
    assert atom.metadata["source_sha256"] == "a" * 64 and atom.metadata["source_observation_ids"] == tuple(sorted(ids))
    assert all(atom.metadata[flag] is False for flag in A._GRANT_FLAGS)
    other = run(page, ids, ownership=replace(OWN, snapshot_id="other"))
    assert other.record_id != got.record_id and other.nomination_id != got.nomination_id


# --- metamorphic ---------------------------------------------------------------------------------


def _shift(page, dx, dy):
    return [A.SourceRole(r.observation_id, (r.geometry[0] + dx, r.geometry[1] + dy, r.geometry[2] + dx, r.geometry[3] + dy),
                         r.stroke_width, r.stroke_rgb, r.kind, r.role_verified) for r in page]


def _summary(got):
    return (got.status, got.reason_codes, got.axis, tuple(round(v - got.along_extent[0], 2) for v in got.along_extent),
            [(f.candidate_id, f.existence, f.gap_crosses_lo_terminal, f.gap_crosses_hi_terminal, f.spans_whole_extent, f.gap_span and tuple(round(v - got.along_extent[0], 2) for v in f.gap_span)) for f in got.fragments],
            [(t.end, t.observation_id, t.stroke_width, t.nominated) for t in got.terminals])


def test_translation_input_order_and_axis_swap_do_not_change_the_verdict():
    page, ids = base()
    cands = [("left", STRONG, fragment(page, "left", 164.0, 166.88)), ("right", STRONG, fragment(page, "right", 232.0, 234.64))]
    page.append(role("pier", 100, 296, 100, 310, width=0.96))
    corro = [c[2] for c in cands]
    status = {m: "corroborated" for c in corro for m in c}
    base_summary = _summary(run(page, ids, cands, corro, status))
    moved = run(_shift(page, 1234.13, -77.77), ids, cands, corro, status, viewport=A.ViewportRef("v", (-5000, -5000, 9000, 9000)))
    assert _summary(moved) == base_summary
    assert _summary(run(list(reversed(page)), list(reversed(ids)), list(reversed(cands)), corro, status)) == base_summary
    swapped = [A.SourceRole(r.observation_id, (r.geometry[1], r.geometry[0], r.geometry[3], r.geometry[2]), r.stroke_width,
                            r.stroke_rgb, r.kind, r.role_verified) for r in page]
    sw = run(swapped, ids, cands, corro, status)
    assert sw.axis == "V"
    assert (sw.status, [(f.candidate_id, f.existence) for f in sw.fragments]) == (
        base_summary[0], [(f[0], f[1]) for f in base_summary[4]])


def test_unrelated_content_far_from_the_strip_changes_nothing():
    page, ids = base()
    quiet = _summary(run(page, ids))
    noisy = page + [role(f"x{i}", 900 + i, 900, 900 + i, 920 + i) for i in range(300)]
    assert _summary(run(noisy, ids)) == quiet


def test_replay_is_deterministic():
    page, ids = base()
    assert run(page, ids) == run(page, ids)
