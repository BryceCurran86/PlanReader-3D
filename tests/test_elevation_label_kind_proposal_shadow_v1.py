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


def test_too_many_routes_that_reach_the_instance_make_it_unresolvable():
    fan = [StrokeSegment(217.0, 308.0, 217.0 + 3.0 * (i + 1), 308.0) for i in range(kp.MAX_ROUTES + 2)]
    r = run(strokes=leader() + fan)                                    # the fan sits at the corner of a leader that enters the leaf
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)


def test_too_many_routes_that_never_reach_the_instance_change_nothing():
    fan = [StrokeSegment(217.0, 308.0, 217.0 + 3.0 * (i + 1), 308.0) for i in range(kp.MAX_ROUTES + 2)]
    r = run(strokes=[leader()[0]] + fan)                               # the same fan, but no stroke ever enters an outline
    assert r.status is ABST and r.reason_codes == (kp.NO_LEADER,)


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


# ------------------------------------------------------------------------------------------------ ambiguity beside a usable label (review 5834419211)
A_BOX = OutlineBox("A", 20.0, 20.0, 40.0, 40.0, ("rcpt-A",))
B_BOX = OutlineBox("B", 30.0, 30.0, 50.0, 50.0, ("rcpt-B",))
DOOR_LABEL = LabelBlock("DOOR", "DOOR", (0.0, 21.0, 5.0, 23.0), ("rcpt-door",), "corroborated")
DOOR_LEADER = StrokeSegment(5.0, 22.0, 25.0, 22.0, "rcpt-door-stroke")
WINDOW_LABEL = LabelBlock("WINDOW", "WINDOW", (0.0, 34.0, 5.0, 36.0), ("rcpt-window",), "corroborated")
WINDOW_LEADER = StrokeSegment(5.0, 35.0, 35.0, 35.0, "rcpt-window-stroke")       # its tip lies inside A and B, which do not nest


def review(blocks, strokes, outlines=(A_BOX, B_BOX), witnessed="A"):
    return propose_kind_from_leader("rec", witnessed, list(outlines), list(blocks), list(strokes))


def test_review_counterexample_each_label_alone():
    assert review([WINDOW_LABEL], [WINDOW_LEADER]).reason_codes == (kp.NOT_NESTED,)
    door = review([DOOR_LABEL], [DOOR_LEADER])
    assert door.status is CAND and door.kind == "door"


def test_review_counterexample_an_ambiguous_window_leader_survives_beside_a_clean_door_label_in_both_orders():
    blocks, strokes = [DOOR_LABEL, WINDOW_LABEL], [DOOR_LEADER, WINDOW_LEADER]
    for bs, ss in ((blocks, strokes), (blocks[::-1], strokes[::-1]), (blocks, strokes[::-1]), (blocks[::-1], strokes)):
        r = review(bs, ss)
        assert r.status is ABST and r.reason_codes == (kp.NOT_NESTED,) and r.kind is None and r.source_observation_ids == ()
    rng = random.Random(3)
    for _ in range(20):
        bs, ss, os_ = blocks[:], strokes[:], [A_BOX, B_BOX]
        rng.shuffle(bs), rng.shuffle(ss), rng.shuffle(os_)
        assert review(bs, ss, os_).reason_codes == (kp.NOT_NESTED,)


def test_an_ambiguous_label_that_does_not_reach_this_instance_is_harmless():
    far = LabelBlock("FAR", "WINDOW", (200.0, 200.0, 205.0, 202.0), ("rcpt-far",), "corroborated")
    far_leader = StrokeSegment(205.0, 201.0, 235.0, 201.0, "rcpt-far-stroke")
    far_a, far_b = OutlineBox("FA", 220.0, 190.0, 240.0, 210.0), OutlineBox("FB", 230.0, 195.0, 250.0, 215.0)       # a non-nested pair elsewhere
    assert review([far], [far_leader], (far_a, far_b), "FA").reason_codes == (kp.NOT_NESTED,)                      # ambiguous for ITS instance
    r = review([DOOR_LABEL, far], [DOOR_LEADER, far_leader], (A_BOX, B_BOX, far_a, far_b))
    assert r.status is CAND and r.kind == "door" and r.source_observation_ids and "rcpt-far" not in r.source_observation_ids


def test_an_overflowing_label_that_reaches_the_instance_survives_beside_a_clean_door_label():
    window = LabelBlock("WINDOW", "WINDOW", (0.0, 34.0, 5.0, 36.0), ("rcpt-window",), "corroborated")
    wleader = StrokeSegment(5.0, 35.0, 25.0, 35.0)                                                     # enters A (not B) and ends in a fan
    fan = [StrokeSegment(25.0, 35.0, 25.0 + 2.0 * (i + 1), 35.0) for i in range(kp.MAX_ROUTES + 2)]
    assert review([DOOR_LABEL], [DOOR_LEADER]).status is CAND
    r = review([DOOR_LABEL, window], [DOOR_LEADER, wleader, *fan])
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,) and r.kind is None
    r2 = review([window, DOOR_LABEL], [*fan, wleader, DOOR_LEADER])
    assert r2.reason_codes == (kp.LEADER_BRANCHES,)
    far_window = LabelBlock("FW", "WINDOW", (300.0, 300.0, 305.0, 302.0))
    far_fan = [StrokeSegment(305.0, 301.0, 305.0 + 2.0 * (i + 1), 301.0) for i in range(kp.MAX_ROUTES + 2)]
    ok = review([DOOR_LABEL, far_window], [DOOR_LEADER, *far_fan])
    assert ok.status is CAND and ok.kind == "door"                                                       # an overflowing label elsewhere is harmless


def test_a_mixed_token_label_reaching_the_instance_vetoes_but_a_token_less_one_does_not():
    mixed = LabelBlock("MIX", "DOOR WINDOW", (0.0, 28.0, 5.0, 30.0), ("rcpt-mix",), "corroborated")
    mixed_leader = StrokeSegment(5.0, 29.0, 25.0, 29.0)
    r = review([DOOR_LABEL, mixed], [DOOR_LEADER, mixed_leader])
    assert r.status is ABST and r.reason_codes == (kp.MIXED_KIND_TOKENS,)
    plain = LabelBlock("TAG", "2100", (0.0, 28.0, 5.0, 30.0), ("rcpt-tag",), "corroborated")
    ok = review([DOOR_LABEL, plain], [DOOR_LEADER, mixed_leader])
    assert ok.status is CAND and ok.kind == "door" and "rcpt-tag" not in ok.source_observation_ids


def test_vetoes_follow_a_fixed_order_whatever_the_input_order():
    # wide outlines so the three labels sit far apart and cannot start each other's leaders
    a = OutlineBox("A", 20.0, 20.0, 200.0, 40.0)
    b = OutlineBox("B", 30.0, 30.0, 210.0, 50.0)
    door = LabelBlock("DOOR", "DOOR", (0.0, 21.0, 5.0, 23.0), ("r-door",), "corroborated")
    door_leader = StrokeSegment(5.0, 22.0, 25.0, 22.0)                                  # clean, inside A only
    window = LabelBlock("WINDOW", "WINDOW", (0.0, 34.0, 5.0, 36.0), ("r-window",), "corroborated")
    window_leader = StrokeSegment(5.0, 35.0, 35.0, 35.0)                                # ends inside A and B (not nested)
    mixed = LabelBlock("MIX", "DOOR WINDOW", (100.0, 5.0, 105.0, 7.0), ("r-mix",), "corroborated")
    mixed_leader = StrokeSegment(102.0, 7.0, 102.0, 25.0)                               # clean, inside A only: mixed kind evidence
    blocks, strokes = [door, window, mixed], [door_leader, window_leader, mixed_leader]
    only_mixed = propose_kind_from_leader("rec", "A", [a, b], [door, mixed], [door_leader, mixed_leader])
    assert only_mixed.status is ABST and only_mixed.reason_codes == (kp.MIXED_KIND_TOKENS,)
    only_window = propose_kind_from_leader("rec", "A", [a, b], [door, window], [door_leader, window_leader])
    assert only_window.reason_codes == (kp.NOT_NESTED,)
    for bs, ss in ((blocks, strokes), (blocks[::-1], strokes[::-1]), (blocks, strokes[::-1])):
        r = propose_kind_from_leader("rec", "A", [a, b], bs, ss)
        assert r.reason_codes == (kp.NOT_NESTED,)                                       # NOT_NESTED outranks MIXED_KIND_TOKENS


def test_a_label_network_too_large_to_follow_is_assumed_to_reach():
    # an overflowing label whose connected stroke network exceeds the cap is a veto even where it visibly reaches nothing
    window = LabelBlock("WINDOW", "WINDOW", (300.0, 300.0, 305.0, 302.0), ("r-window",), "corroborated")
    fan = [StrokeSegment(305.0, 301.0, 305.0 + 2.0 * (i + 1), 301.0) for i in range(kp.MAX_ROUTES + 2)]
    chain = [StrokeSegment(400.0 + 3.0 * i, 500.0, 403.0 + 3.0 * i, 500.0) for i in range(kp.COMPONENT_CAP + 20)]
    joiner = [StrokeSegment(305.0, 301.0, 305.0, 500.0), StrokeSegment(305.0, 500.0, 400.0, 500.0)]
    small = review([DOOR_LABEL, window], [DOOR_LEADER, *fan])
    assert small.status is CAND                                                         # a small overflowing network elsewhere is harmless
    big = review([DOOR_LABEL, window], [DOOR_LEADER, *fan, *joiner, *chain])
    assert big.status is ABST and big.reason_codes == (kp.LEADER_BRANCHES,)


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


# ------------------------------------------------------------------------------------------------ overflowing network: ANY point inside (review of #4264, comment 6760871581)
W_BOX = OutlineBox("W", 10.0, 10.0, 20.0, 20.0, ("rcpt-W",))
CLEAN_DOOR = LabelBlock("DOOR", "DOOR", (11.0, 24.0, 19.0, 26.0), ("rcpt-door",), "corroborated")
CLEAN_DOOR_LEADER = StrokeSegment(15.0, 24.0, 15.0, 18.0, "rcpt-door-stroke")                  # clean: its tip is inside W
CROSSING_LABEL = LabelBlock("WINDOW", "WINDOW", (-12.0, 14.0, -2.0, 16.0), ("rcpt-window",), "corroborated")
CROSSING_STROKE = StrokeSegment(0.0, 15.0, 30.0, 15.0, "rcpt-crossing")                        # crosses W's interior, both ends outside
CROSSING_FAN = [StrokeSegment(30.0, 15.0, 30.0 + 2.0 * (i + 1), 15.0) for i in range(kp.MAX_ROUTES + 2)]       # makes the label overflow


def crossing(blocks, strokes, outlines=(W_BOX,)):
    return propose_kind_from_leader("rec", "W", list(outlines), list(blocks), list(strokes))


def test_the_clean_door_leader_alone_is_a_candidate_and_the_crossing_label_alone_vetoes():
    assert crossing([CLEAN_DOOR], [CLEAN_DOOR_LEADER]).status is CAND
    r = crossing([CROSSING_LABEL], [CROSSING_STROKE, *CROSSING_FAN])
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)                      # its network crosses the witnessed interior


def test_an_overflowing_network_that_crosses_the_interior_with_both_ends_outside_vetoes_in_every_order():
    blocks, strokes = [CLEAN_DOOR, CROSSING_LABEL], [CLEAN_DOOR_LEADER, CROSSING_STROKE, *CROSSING_FAN]
    for bs, ss in ((blocks, strokes), (blocks[::-1], strokes), (blocks, strokes[::-1]), (blocks[::-1], strokes[::-1])):
        r = crossing(bs, ss)
        assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,) and r.kind is None and r.source_observation_ids == ()
    rng = random.Random(11)
    for _ in range(20):
        bs, ss = blocks[:], strokes[:]
        rng.shuffle(bs), rng.shuffle(ss)
        assert crossing(bs, ss).reason_codes == (kp.LEADER_BRANCHES,)


def test_a_vertical_crossing_and_a_crossing_found_through_a_chain_of_contacts_also_veto():
    label = LabelBlock("WINDOW", "WINDOW", (14.0, -12.0, 16.0, -2.0), ("rcpt-window",), "corroborated")
    vertical = StrokeSegment(15.0, 0.0, 15.0, 30.0, "rcpt-v")                                  # top to bottom through W's interior
    fan = [StrokeSegment(15.0, 30.0, 15.0 + 2.0 * (i + 1), 30.0) for i in range(kp.MAX_ROUTES + 2)]
    r = crossing([CLEAN_DOOR, label], [CLEAN_DOOR_LEADER, vertical, *fan])
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)
    # the crossing stroke is reachable ONLY through exact end-to-end contacts: the label is 30 pt away from it
    far_label = LabelBlock("WINDOW", "WINDOW", (-40.0, 14.0, -30.0, 16.0), ("rcpt-window",), "corroborated")
    hops = [StrokeSegment(-30.0, 15.0, -20.0, 15.0, "h1"), StrokeSegment(-20.0, 15.0, -10.0, 15.0, "h2"),
            StrokeSegment(-10.0, 15.0, 0.0, 15.0, "h3")]
    r2 = crossing([CLEAN_DOOR, far_label], [CLEAN_DOOR_LEADER, *hops, CROSSING_STROKE, *CROSSING_FAN])
    assert r2.status is ABST and r2.reason_codes == (kp.LEADER_BRANCHES,)
    broken = [hops[0], hops[1], StrokeSegment(-10.0, 15.0, -0.5, 15.0, "h3-short")]            # a 0.5 pt gap: no contact, no network
    r3 = crossing([CLEAN_DOOR, far_label], [CLEAN_DOOR_LEADER, *broken, CROSSING_STROKE, *CROSSING_FAN])
    assert r3.status is CAND and r3.kind == "door"


def test_a_crossing_stroke_that_is_not_connected_to_the_overflowing_label_is_harmless():
    far_label = LabelBlock("FAR", "WINDOW", (300.0, 300.0, 305.0, 302.0), ("rcpt-far",), "corroborated")
    far_fan = [StrokeSegment(305.0, 301.0, 305.0 + 2.0 * (i + 1), 301.0) for i in range(kp.MAX_ROUTES + 2)]
    r = crossing([CLEAN_DOOR, far_label], [CLEAN_DOOR_LEADER, CROSSING_STROKE, *far_fan])        # the crossing stroke belongs to no label
    assert r.status is CAND and r.kind == "door"


def test_a_network_that_only_grazes_or_misses_the_interior_is_harmless():
    for y in (10.0, 10.1, 20.0, 9.0, 21.0):                      # on the boundary, inside the 0.2 pt margin, or outside
        graze = StrokeSegment(0.0, y, 30.0, y, "rcpt-graze")
        label = LabelBlock("WINDOW", "WINDOW", (-12.0, y - 1.0, -2.0, y + 1.0), ("rcpt-window",), "corroborated")
        fan = [StrokeSegment(30.0, y, 30.0 + 2.0 * (i + 1), y) for i in range(kp.MAX_ROUTES + 2)]
        r = crossing([CLEAN_DOOR, label], [CLEAN_DOOR_LEADER, graze, *fan])
        assert r.status is CAND and r.kind == "door", y
    # touching only at a corner point, then leaving
    corner = StrokeSegment(0.0, 10.0, 10.0, 10.0, "rcpt-corner")
    label = LabelBlock("WINDOW", "WINDOW", (-12.0, 9.0, -2.0, 11.0), ("rcpt-window",), "corroborated")
    fan = [StrokeSegment(10.0, 10.0, 10.0, 10.0 - 2.0 * (i + 1), "rcpt-cfan") for i in range(kp.MAX_ROUTES + 2)]
    assert crossing([CLEAN_DOOR, label], [CLEAN_DOOR_LEADER, corner, *fan]).status is CAND


def test_a_segment_ending_inside_still_vetoes_as_before_and_a_slightly_slanted_crossing_is_not_missed():
    ends_inside = StrokeSegment(0.0, 15.0, 15.0, 15.0, "rcpt-in")
    inner_fan = [StrokeSegment(15.0, 15.0, 15.0, 15.0 + 0.4 * (i + 1)) for i in range(kp.MAX_ROUTES + 2)]
    r = crossing([CLEAN_DOOR, CROSSING_LABEL], [CLEAN_DOOR_LEADER, ends_inside, *inner_fan])
    assert r.status is ABST and r.reason_codes == (kp.LEADER_BRANCHES,)
    slanted = StrokeSegment(0.0, 14.99, 30.0, 15.01, "rcpt-slant")                              # within the axis tolerance, y drifts 0.02 pt
    slanted_fan = [StrokeSegment(30.0, 15.01, 30.0 + 2.0 * (i + 1), 15.01) for i in range(kp.MAX_ROUTES + 2)]
    r2 = crossing([CLEAN_DOOR, CROSSING_LABEL], [CLEAN_DOOR_LEADER, slanted, *slanted_fan])
    assert r2.status is ABST and r2.reason_codes == (kp.LEADER_BRANCHES,)


@pytest.mark.parametrize("seg, expected", [
    ((0.0, 15.0, 30.0, 15.0), True),            # horizontal crossing, both ends outside
    ((15.0, 0.0, 15.0, 30.0), True),            # vertical crossing
    ((0.0, 15.0, 15.0, 15.0), True),            # one end inside
    ((12.0, 12.0, 18.0, 18.0), True),           # wholly inside
    ((0.0, 0.0, 30.0, 30.0), True),             # diagonal through the interior
    ((0.0, 15.0, 9.0, 15.0), False),            # stops short
    ((21.0, 15.0, 30.0, 15.0), False),          # starts beyond
    ((0.0, 9.0, 30.0, 9.0), False),             # passes outside
    ((0.0, 10.2, 30.0, 10.2), False),           # runs exactly along the margin boundary
    ((0.0, 10.3, 30.0, 10.3), True),            # just inside the margin
    ((0.0, 19.8, 30.0, 19.8), False),
    ((0.0, 19.7, 30.0, 19.7), True),
    ((0.0, 15.0, 10.2, 15.0), False),           # ends exactly on the boundary: touches, does not enter
    ((10.2, 15.0, 15.0, 15.0), True),           # starts on the boundary and goes in
    ((0.0, 10.2, 10.2, 10.2), False),
    ((10.2, 0.0, 10.2, 30.0), False),           # along the left margin boundary
    ((0.0, 0.0, 10.2, 10.2), False),            # reaches only the corner point of the interior
    ((0.0, 15.0, 15.0, 30.0), False),           # a diagonal that passes the box by missing its corner
    ((0.0, 5.0, 15.0, 0.0), False),
    ((25.0, 15.0, 10.0, 30.0), False),
    ((15.0, 15.0, 15.0, 15.0), True),           # a point inside
    ((5.0, 5.0, 5.0, 5.0), False),              # a point outside
])
def test_segment_enters_is_strict_about_the_open_interior(seg, expected):
    assert kp._segment_enters(StrokeSegment(*seg), W_BOX) is expected
    assert kp._segment_enters(StrokeSegment(seg[2], seg[3], seg[0], seg[1]), W_BOX) is expected         # direction does not matter


def test_a_box_thinner_than_twice_the_margin_has_no_interior():
    thin = OutlineBox("thin", 10.0, 10.0, 10.3, 20.0)
    assert kp._segment_enters(StrokeSegment(0.0, 15.0, 30.0, 15.0), thin) is False
    flat = OutlineBox("flat", 10.0, 10.0, 20.0, 10.3)
    assert kp._segment_enters(StrokeSegment(15.0, 0.0, 15.0, 30.0), flat) is False


def test_a_diagonal_that_touches_only_a_corner_point_of_the_interior_does_not_enter(monkeypatch):
    monkeypatch.setattr(kp, "INSIDE_MARGIN_PT", 0.25)                       # binary-exact margin so the touching point is exact
    box = OutlineBox("exact", 10.0, 10.0, 20.0, 20.0)
    touching = StrokeSegment(5.25, 14.75, 15.25, 24.75)                      # passes (10.25, 19.75), the interior's corner, then leaves
    assert kp._segment_enters(touching, box) is False
    assert kp._segment_enters(StrokeSegment(5.25, 14.75, 15.25, 24.0), box) is True          # a hair lower it does cut the interior
