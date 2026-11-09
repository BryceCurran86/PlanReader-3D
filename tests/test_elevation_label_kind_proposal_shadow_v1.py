"""Synthetic proof for the shadow-only elevation label -> kind proposal (leader-chain attachment)."""
from __future__ import annotations

import copy
import random

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_elevation_label_kind_proposal_shadow as kp
from pb_elevation_label_kind_proposal_shadow import (
    LabelBlock, OutlineBox, StrokeSegment, label_kind, propose_kind_from_leader,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT


def leaf():
    return OutlineBox("leaf", 200.0, 100.0, 234.0, 300.0, ("rcpt-leaf",))


def frame():
    return OutlineBox("frame", 198.0, 98.0, 236.0, 300.0, ("rcpt-frame",))


def label(text="ALUMINIUM ENTRY DOOR", block_id="L1", trust="corroborated", dx=0.0, dy=0.0):
    return LabelBlock(block_id, text, (300.0 + dx, 310.0 + dy, 380.0 + dx, 320.0 + dy), ("rcpt-label",), trust)


def leader(dx=0.0, dy=0.0, tip_y=260.0):
    # starts 2 pt under the words, runs left along y=308, then up to a tip inside the leaf
    return [StrokeSegment(300.0 + dx, 308.0 + dy, 217.0 + dx, 308.0 + dy, "rcpt-s1"),
            StrokeSegment(217.0 + dx, 308.0 + dy, 217.0 + dx, tip_y + dy, "rcpt-s2")]


def base():
    return [leaf(), frame()], [label()], leader()


def run(outlines=None, blocks=None, strokes=None, witnessed="leaf"):
    o, b, s = base()
    return propose_kind_from_leader("rec", witnessed, o if outlines is None else outlines,
                                    b if blocks is None else blocks, s if strokes is None else strokes)


# ------------------------------------------------------------------------------------------------ positives
def test_label_with_a_leader_ending_inside_the_leaf_proposes_the_door_kind():
    r = run()
    assert r.status is CAND and r.is_candidate and r.kind == "door"
    assert r.reason_codes == (kp.KIND_PROPOSAL,)
    assert r.outline_id == "leaf" and r.nested_outline_ids == ("frame", "leaf")     # the leaf and its frame are one door
    assert r.text_trust == "corroborated" and r.label_block_id == "L1"
    assert set(r.source_observation_ids) == {"rcpt-label", "rcpt-s1", "rcpt-s2", "rcpt-leaf", "rcpt-frame"}
    assert r.status is not EvidenceResolutionStatus.CORROBORATED                      # a proposal, never an authority


def test_a_window_token_proposes_the_window_kind():
    assert run(blocks=[label("ALUMINIUM WINDOW")]).kind == "window"


def test_raw_words_stay_diagnostic_only_and_unknown_trust_is_empty():
    assert run(blocks=[label(trust="raw_unverified")]).text_trust == "raw_unverified_diagnostic_only"
    assert run(blocks=[label(trust="")]).text_trust == ""
    assert run(blocks=[label(trust="corroborated")]).text_trust == "corroborated"


def test_the_frame_can_be_the_witnessed_outline_too():
    r = run(witnessed="frame")
    assert r.status is CAND and r.outline_id == "frame"


# ------------------------------------------------------------------------------------------------ token rules
def test_kind_comes_only_from_an_explicit_token():
    assert label_kind("ALUMINIUM ENTRY DOOR") == ("door", None)
    assert label_kind("sliding doors") == ("door", None)
    assert label_kind("OUTDOOR LIGHT")[0] is None                    # a substring is not a token
    assert label_kind("WINDOWSILL")[0] is None
    assert label_kind("ENTRY") == (None, kp.NO_KIND_TOKEN)
    assert label_kind("DOOR TO MATCH WINDOW") == (None, kp.MIXED_KIND_TOKENS)
    assert label_kind("") == (None, kp.NO_KIND_TOKEN)


def test_a_label_without_a_token_abstains_even_with_a_perfect_leader():
    r = run(blocks=[label("ENTRY 2100")])
    assert r.status is ABST and r.reason_codes == (kp.NO_KIND_TOKEN,) and r.kind is None


def test_mixed_tokens_abstain():
    r = run(blocks=[label("DOOR OR WINDOW")])
    assert r.status is ABST and r.reason_codes == (kp.MIXED_KIND_TOKENS,)


def test_the_kind_never_depends_on_outline_shape_or_size():
    # A tall narrow outline (door-like) and a short wide one (window-like) get exactly the label's kind.
    tall = [OutlineBox("leaf", 200.0, 100.0, 234.0, 300.0), OutlineBox("frame", 198.0, 98.0, 236.0, 300.0)]
    wide = [OutlineBox("leaf", 150.0, 240.0, 290.0, 280.0), OutlineBox("frame", 148.0, 238.0, 292.0, 282.0)]
    for outlines in (tall, wide):
        assert run(outlines=outlines, blocks=[label("WINDOW")]).kind == "window"
        assert run(outlines=outlines, blocks=[label("DOOR")]).kind == "door"


def test_door_like_outline_without_any_label_abstains():
    r = run(blocks=[])
    assert r.status is ABST and r.reason_codes == (kp.NO_LEADER,) and r.kind is None


# ------------------------------------------------------------------------------------------------ leader strictness
def test_a_gap_in_the_leader_chain_ends_the_chain_before_the_outline():
    # A 1 pt gap between the two strokes: the first stroke ends outside every outline, so nothing is attached.
    s = [StrokeSegment(300.0, 308.0, 217.0, 308.0), StrokeSegment(217.0, 307.0, 217.0, 260.0)]
    r = run(strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.NO_LEADER,)


def test_a_leader_that_starts_far_from_the_words_attaches_nothing():
    s = [StrokeSegment(300.0, 340.0, 217.0, 340.0), StrokeSegment(217.0, 340.0, 217.0, 260.0)]
    assert run(strokes=s).status is ABST


def test_a_stroke_near_the_words_that_does_not_lead_away_is_not_a_leader():
    # Underline of the words themselves.
    s = [StrokeSegment(300.0, 321.0, 380.0, 321.0)]
    assert run(strokes=s).status is ABST


def test_a_tip_outside_the_outline_attaches_nothing():
    assert run(strokes=leader(tip_y=305.0)).status is ABST            # stops below the base
    s = [StrokeSegment(300.0, 308.0, 150.0, 308.0), StrokeSegment(150.0, 308.0, 150.0, 260.0)]
    assert run(strokes=s).status is ABST                              # lands left of the frame


def test_a_tip_exactly_on_the_outline_edge_is_not_inside():
    s = [StrokeSegment(300.0, 308.0, 234.0, 308.0), StrokeSegment(234.0, 308.0, 234.0, 260.0)]
    r = run(strokes=s, outlines=[leaf()])
    assert r.status is ABST


def test_a_fork_whose_extra_branch_ends_in_blank_space_does_not_hide_the_route():
    s = leader() + [StrokeSegment(217.0, 308.0, 217.0, 340.0, "rcpt-branch")]          # the corner also continues downward
    r = run(strokes=s)
    assert r.status is CAND and r.kind == "door" and "rcpt-branch" not in r.source_observation_ids


def test_a_fork_into_two_instances_abstains():
    neighbour = OutlineBox("neighbour", 150.0, 100.0, 190.0, 300.0)
    s = leader() + [StrokeSegment(217.0, 308.0, 170.0, 308.0), StrokeSegment(170.0, 308.0, 170.0, 260.0)]
    r = run(outlines=[leaf(), frame(), neighbour], strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.AMBIGUOUS_LEADERS,)


def test_too_many_routes_make_the_label_unusable():
    fan = [StrokeSegment(217.0, 308.0, 217.0 + 3.0 * (i + 1), 308.0) for i in range(kp.MAX_ROUTES + 2)]
    r = run(strokes=[leader()[0]] + fan)
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)


def test_a_diagonal_stroke_is_not_a_leader():
    # hatching and brick courses are diagonal; a diagonal route from the label never attaches it to an outline
    s = [StrokeSegment(300.0, 308.0, 250.0, 258.0), StrokeSegment(250.0, 258.0, 217.0, 258.0)]
    assert run(strokes=s).status is ABST
    diag_only = [StrokeSegment(300.0, 308.0, 217.0, 225.0)]                                # tip (217,225) is inside the leaf
    assert run(strokes=diag_only).status is ABST


def test_a_stroke_beside_the_words_that_does_not_lead_away_is_not_a_leader_even_inside_an_outline():
    # label printed inside the leaf outline, with a line under it whose two ends are equally close to the words
    inside_label = LabelBlock("L1", "DOOR", (205.0, 150.0, 225.0, 160.0), ("rcpt-label",), "corroborated")
    under = [StrokeSegment(205.0, 162.0, 225.0, 162.0)]
    assert run(blocks=[inside_label], strokes=under).status is ABST


def test_a_chain_longer_than_the_limit_abstains_and_exactly_the_limit_is_accepted():
    def chain(n):                               # n segments: n-1 horizontal runs, then one vertical run into the leaf
        xs = [300.0] + [300.0 - (83.0 / (n - 1)) * i for i in range(1, n)]
        segs = [StrokeSegment(xs[i], 308.0, xs[i + 1], 308.0) for i in range(n - 1)]
        return segs + [StrokeSegment(xs[-1], 308.0, xs[-1], 260.0)]

    ok = chain(kp.MAX_CHAIN_SEGMENTS)
    assert len(ok) == kp.MAX_CHAIN_SEGMENTS and run(strokes=ok).status is CAND
    too_long = chain(kp.MAX_CHAIN_SEGMENTS + 1)
    r = run(strokes=too_long)
    assert len(too_long) == kp.MAX_CHAIN_SEGMENTS + 1 and r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)


def test_a_tiny_piece_cannot_bridge_a_gap_in_the_chain():
    # A sub-1pt piece is not a leader segment, so it cannot join the two real pieces on either side of it.
    s = [StrokeSegment(300.0, 308.0, 250.0, 308.0), StrokeSegment(250.0, 308.0, 249.5, 308.0),
         StrokeSegment(249.5, 308.0, 217.0, 308.0), StrokeSegment(217.0, 308.0, 217.0, 260.0)]
    r = run(strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.NO_LEADER,)


def test_a_split_leader_segment_gives_the_same_proposal():
    split = [StrokeSegment(300.0, 308.0, 260.0, 308.0, "a"), StrokeSegment(260.0, 308.0, 217.0, 308.0, "b"),
             StrokeSegment(217.0, 308.0, 217.0, 280.0, "c"), StrokeSegment(217.0, 280.0, 217.0, 260.0, "d")]
    a, b = run(), run(strokes=split)
    assert (b.status, b.kind, b.outline_id, b.nested_outline_ids) == (a.status, a.kind, a.outline_id, a.nested_outline_ids)


def test_segment_direction_does_not_matter():
    rev = [StrokeSegment(s.x1, s.y1, s.x0, s.y0, s.receipt_id) for s in leader()]
    a, b = run(), run(strokes=rev)
    assert a.status is b.status is CAND and a.result_id == b.result_id


# ------------------------------------------------------------------------------------------------ nesting / instances
def test_overlapping_non_nested_outlines_at_the_tip_abstain():
    other = OutlineBox("other", 210.0, 150.0, 260.0, 320.0)           # overlaps the leaf but is not nested with it
    r = run(outlines=[leaf(), frame(), other])
    assert r.status is ABST and r.reason_codes == (kp.NOT_NESTED,)


def test_a_label_pointing_at_another_door_does_not_label_this_one():
    neighbour = OutlineBox("neighbour", 400.0, 100.0, 434.0, 300.0)
    s = [StrokeSegment(300.0, 308.0, 417.0, 308.0), StrokeSegment(417.0, 308.0, 417.0, 260.0)]
    r = run(outlines=[leaf(), frame(), neighbour], strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.NO_LEADER,)
    assert run(outlines=[leaf(), frame(), neighbour], strokes=s, witnessed="neighbour").status is CAND


def test_a_label_with_leaders_to_two_separate_instances_abstains():
    neighbour = OutlineBox("neighbour", 400.0, 100.0, 434.0, 300.0)
    s = leader() + [StrokeSegment(380.0, 315.0, 417.0, 315.0), StrokeSegment(417.0, 315.0, 417.0, 260.0)]
    r = run(outlines=[leaf(), frame(), neighbour], strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.AMBIGUOUS_LEADERS,)
    assert run(outlines=[leaf(), frame(), neighbour], strokes=s, witnessed="neighbour").status is ABST


def test_a_large_surround_containing_both_doors_does_not_hide_the_ambiguity():
    wall = OutlineBox("wall", 0.0, 0.0, 600.0, 400.0)
    neighbour = OutlineBox("neighbour", 400.0, 100.0, 434.0, 300.0)
    s = leader() + [StrokeSegment(380.0, 315.0, 417.0, 315.0), StrokeSegment(417.0, 315.0, 417.0, 260.0)]
    r = run(outlines=[leaf(), frame(), neighbour, wall], strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.AMBIGUOUS_LEADERS,)


def test_the_same_chain_through_a_surround_still_counts_as_one_door():
    wall = OutlineBox("wall", 0.0, 0.0, 600.0, 400.0)
    r = run(outlines=[leaf(), frame(), wall])
    assert r.status is CAND and r.nested_outline_ids == ("frame", "leaf", "wall")


# ------------------------------------------------------------------------------------------------ competing labels
def test_two_labels_with_different_kinds_reaching_one_instance_conflict():
    second = LabelBlock("L2", "WINDOW", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "corroborated")
    s = leader() + [StrokeSegment(200.0, 328.0, 215.0, 328.0), StrokeSegment(215.0, 328.0, 215.0, 250.0)]
    r = run(blocks=[label(), second], strokes=s)
    assert r.status is CONF and r.reason_codes == (kp.COMPETING_LABELS,) and r.kind is None


def test_two_labels_with_the_same_kind_are_one_proposal_with_both_receipts():
    second = LabelBlock("L2", "ENTRY DOOR", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "corroborated")
    s = leader() + [StrokeSegment(200.0, 328.0, 215.0, 328.0), StrokeSegment(215.0, 328.0, 215.0, 250.0)]
    r = run(blocks=[label(), second], strokes=s)
    assert r.status is CAND and r.kind == "door" and r.label_block_id == "L1+L2" and "rcpt-l2" in r.source_observation_ids


def test_a_token_less_label_beside_a_door_label_does_not_conflict():
    second = LabelBlock("L2", "2100", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "corroborated")
    s = leader() + [StrokeSegment(200.0, 328.0, 215.0, 328.0), StrokeSegment(215.0, 328.0, 215.0, 250.0)]
    r = run(blocks=[label(), second], strokes=s)
    assert r.status is CAND and r.kind == "door" and r.label_block_id == "L1"


def test_the_proposal_is_only_as_trusted_as_its_least_trusted_label():
    second = LabelBlock("L2", "ENTRY DOOR", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "raw_unverified")
    s = leader() + [StrokeSegment(200.0, 328.0, 215.0, 328.0), StrokeSegment(215.0, 328.0, 215.0, 250.0)]
    assert run(blocks=[label(), second], strokes=s).text_trust == "raw_unverified_diagnostic_only"
    second_ok = LabelBlock("L2", "ENTRY DOOR", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "corroborated")
    assert run(blocks=[label(), second_ok], strokes=s).text_trust == "corroborated"
    unknown = LabelBlock("L2", "ENTRY DOOR", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "")
    assert run(blocks=[label(), unknown], strokes=s).text_trust == ""


def test_edges_that_coincide_within_the_drawing_tolerance_are_still_nested():
    inner_low = OutlineBox("leaf", 200.0, 100.0, 234.0, 300.03, ("rcpt-leaf",))        # 0.03 pt below the frame base
    assert run(outlines=[inner_low, frame()]).status is CAND
    inner_far = OutlineBox("leaf", 200.0, 100.0, 234.0, 300.2, ("rcpt-leaf",))         # 0.2 pt: a different object
    r = run(outlines=[inner_far, frame()])
    assert r.status is ABST and r.reason_codes == (kp.NOT_NESTED,)


def test_a_second_route_into_a_different_instance_makes_even_a_good_label_ambiguous():
    neighbour = OutlineBox("neighbour", 400.0, 100.0, 434.0, 300.0)
    s = leader() + [StrokeSegment(380.0, 315.0, 417.0, 315.0), StrokeSegment(417.0, 315.0, 417.0, 260.0)]
    other = LabelBlock("L2", "WINDOW", (440.0, 330.0, 470.0, 340.0), ("rcpt-l2",), "corroborated")
    r = run(outlines=[leaf(), frame(), neighbour], blocks=[label(), other], strokes=s)
    assert r.status is ABST and r.reason_codes == (kp.AMBIGUOUS_LEADERS,)


def test_the_order_of_two_same_kind_labels_does_not_change_the_proposal():
    second = LabelBlock("L2", "ENTRY DOOR", (150.0, 330.0, 200.0, 340.0), ("rcpt-l2",), "corroborated")
    s = leader() + [StrokeSegment(200.0, 328.0, 215.0, 328.0), StrokeSegment(215.0, 328.0, 215.0, 250.0)]
    a = run(blocks=[label(), second], strokes=s)
    b = run(blocks=[second, label()], strokes=s)
    assert a == b and a.result_id == b.result_id and a.label_block_id == "L1+L2"


# ------------------------------------------------------------------------------------------------ input safety
def test_non_finite_input_fails_closed():
    nan = float("nan")
    inf = float("inf")
    assert run(strokes=[StrokeSegment(nan, 0.0, 1.0, 1.0)]).reason_codes == (kp.INVALID_INPUT,)
    assert run(blocks=[LabelBlock("L1", "DOOR", (0.0, 0.0, inf, 1.0))]).reason_codes == (kp.INVALID_INPUT,)
    assert run(outlines=[OutlineBox("leaf", 0.0, 0.0, inf, 10.0)]).reason_codes == (kp.INVALID_INPUT,)
    assert run(outlines=[OutlineBox("leaf", 10.0, 0.0, 5.0, 10.0)]).reason_codes == (kp.INVALID_INPUT,)


def test_duplicate_identities_fail_closed():
    assert run(outlines=[leaf(), leaf()]).reason_codes == (kp.INVALID_INPUT,)
    assert run(blocks=[label(), label()]).reason_codes == (kp.INVALID_INPUT,)


def test_a_missing_witnessed_outline_abstains():
    assert run(witnessed="nope").reason_codes == (kp.WITNESSED_MISSING,)
    assert run(witnessed=None).reason_codes == (kp.WITNESSED_MISSING,)


# ------------------------------------------------------------------------------------------------ metamorphic
def shift(dx, dy):
    o = [OutlineBox(x.outline_id, x.x0 + dx, x.y0 + dy, x.x1 + dx, x.y1 + dy, x.receipt_ids) for x in (leaf(), frame())]
    b = [label(dx=dx, dy=dy)]
    return o, b, leader(dx, dy)


@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (1234.5, -987.25), (-5000.0, 4000.0)])
def test_translation_does_not_change_the_proposal(dx, dy):
    o, b, s = shift(dx, dy)
    r = propose_kind_from_leader("rec", "leaf", o, b, s)
    assert r.status is CAND and r.kind == "door" and r.nested_outline_ids == ("frame", "leaf")


def test_input_order_does_not_change_the_result():
    outlines = [leaf(), frame(), OutlineBox("zz", 0.0, 0.0, 10.0, 10.0)]
    blocks = [label(), LabelBlock("L0", "NOTE", (10.0, 10.0, 30.0, 20.0))]
    strokes = leader() + [StrokeSegment(10.0, 30.0, 50.0, 30.0)]
    ref = propose_kind_from_leader("rec", "leaf", outlines, blocks, strokes)
    rng = random.Random(7)
    for _ in range(25):
        o, b, s = outlines[:], blocks[:], strokes[:]
        rng.shuffle(o), rng.shuffle(b), rng.shuffle(s)
        r = propose_kind_from_leader("rec", "leaf", o, b, s)
        assert r == ref and r.result_id == ref.result_id


def test_unrelated_content_does_not_change_the_proposal():
    ref = run()
    far = [OutlineBox("far%d" % i, 1000.0 + 50 * i, 0.0, 1030.0 + 50 * i, 200.0) for i in range(5)]
    extra_blocks = [LabelBlock("N%d" % i, "WINDOW", (2000.0 + 30 * i, 0.0, 2020.0 + 30 * i, 10.0)) for i in range(3)]
    extra_strokes = [StrokeSegment(3000.0, 0.0, 3000.0, 80.0 + i) for i in range(4)]
    o, b, s = base()
    r = propose_kind_from_leader("rec", "leaf", o + far, b + extra_blocks, s + extra_strokes)
    assert (r.status, r.kind, r.nested_outline_ids, r.source_observation_ids) == (ref.status, ref.kind, ref.nested_outline_ids, ref.source_observation_ids)


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    o, b, s = base()
    snap = copy.deepcopy((o, b, s))
    r1 = propose_kind_from_leader("rec", "leaf", o, b, s)
    r2 = propose_kind_from_leader("rec", "leaf", o, b, s)
    assert r1 == r2 and r1.result_id == r2.result_id and (o, b, s) == snap


def test_result_identity_changes_with_the_receipts_and_the_kind():
    a = run()
    b = run(blocks=[LabelBlock("L1", "ALUMINIUM ENTRY DOOR", (300.0, 310.0, 380.0, 320.0), ("rcpt-other",), "corroborated")])
    c = run(blocks=[label("ALUMINIUM WINDOW")])
    assert len({a.result_id, b.result_id, c.result_id}) == 3


# ------------------------------------------------------------------------------------------------ isolation
def test_module_is_isolated_from_authority_modules():
    import ast
    import pathlib
    text = pathlib.Path(kp.__file__).read_text(encoding="utf-8")
    imported = {n.module for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "dataclasses", "math", "re", "typing", "pb_migration_contracts"}
    root = pathlib.Path(kp.__file__).parent
    importers = {p.name for p in root.glob("pb_*.py") if p.name != pathlib.Path(kp.__file__).name
                 and "pb_elevation_label_kind_proposal_shadow" in p.read_text(encoding="utf-8", errors="ignore")}
    assert importers <= {"pb_elevation_source_owned_witness_adapter.py"}, importers      # nothing in production reads it
