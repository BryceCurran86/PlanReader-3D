"""Unproven frame-pair ledger never invents DISTINCT or grants a frame."""
from __future__ import annotations

from pb_frame_unproven_pair_shadow import (
    build_frame_unproven_pair_ledger,
    parse_unproven_wall_pair_reason,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class


def test_parse_pair_reason():
    assert parse_unproven_wall_pair_reason(
        "opening_host_frame_unproven_wall_pair:wall-b:wall-a"
    ) == ("wall-b", "wall-a")
    assert parse_unproven_wall_pair_reason("other") is None


def test_unrecorded_and_ambiguous_pairs_are_retained_sorted_without_frame_grant():
    report = build_frame_unproven_pair_ledger(
        [
            "opening_host_frame_aligned_fragment_distinctness_unproven",
            "opening_host_frame_unproven_wall_pair:other:left",
            "opening_host_frame_unproven_wall_pair:other:right",
            "opening_host_frame_unproven_wall_pair:other:left",  # duplicate ignored
        ],
        [
            ("other", "right", Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
        ],
        component_member_ids=("left", "right"),
    )
    assert report["frame_granted"] is False
    assert report["unproven_pair_count"] == 2
    assert [p["sorted_pair"] for p in report["unproven_pairs"]] == [
        ["left", "other"],
        ["other", "right"],
    ]
    assert report["unproven_pairs"][0]["producer_relation"] == "UNRECORDED"
    assert report["unproven_pairs"][1]["producer_relation"] == "AMBIGUOUS_PHYSICAL_EQUIVALENCE"
    assert report["benchmark_score_granted"] is False


def test_same_physical_wall_relation_blocks_extent_without_nearest_election():
    report = build_frame_unproven_pair_ledger(
        ["opening_host_frame_unproven_wall_pair:extra:left"],
        [("extra", "left", Class.SAME_PHYSICAL_WALL.value)],
        component_member_ids=("left", "right"),
    )
    row = report["unproven_pairs"][0]
    assert row["producer_relation"] == "SAME_PHYSICAL_WALL"
    assert row["blocker"] == "same_physical_wall_blocks_whole_wall_extent"
    assert row["frame_granted"] is False


def test_input_order_invariance():
    reasons = [
        "opening_host_frame_unproven_wall_pair:b:a",
        "opening_host_frame_unproven_wall_pair:c:a",
    ]
    pairs = [("c", "a", Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value)]
    first = build_frame_unproven_pair_ledger(reasons, pairs, component_member_ids=("a",))
    second = build_frame_unproven_pair_ledger(
        list(reversed(reasons)), list(reversed(pairs)), component_member_ids=("a",)
    )
    assert first == second
