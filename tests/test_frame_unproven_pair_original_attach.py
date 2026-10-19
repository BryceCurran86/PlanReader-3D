"""Attach ledger never invents DISTINCT or grants a frame."""
from __future__ import annotations

from pb_frame_unproven_pair_original_attach import attach_frame_unproven_pair_ledgers
from pb_physical_wall_identity import PhysicalEquivalenceClass


def test_aligned_only_opening_attaches_empty_pair_ledger():
    report = attach_frame_unproven_pair_ledgers(
        opening_rows=[{
            "physical_opening_id": "op-1",
            "authenticated_frame_record_id": None,
            "frame_reason_codes": (
                "opening_host_frame_aligned_fragment_distinctness_unproven",
            ),
            "source_host_member_wall_ids": ("host-a", "host-b"),
        }],
        wall_scopes=[{
            "equivalence": {
                "pair_classifications": [
                    ("host-a", "extra", PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
                ],
            },
        }],
    )
    assert report["frame_blocked_openings_with_ledger"] == 1
    assert report["openings"][0]["unproven_pair_ledger"]["unproven_pair_count"] == 0
    assert report["frame_granted"] is False


def test_unproven_pair_reasons_classify_unrecorded_and_ambiguous():
    Class = PhysicalEquivalenceClass
    report = attach_frame_unproven_pair_ledgers(
        opening_rows=[{
            "physical_opening_id": "op-2",
            "frame_reason_codes": (
                "opening_host_frame_unproven_wall_pair:extra:host-a",
                "opening_host_frame_unproven_wall_pair:other:host-b",
            ),
            "source_host_member_wall_ids": ("host-a", "host-b"),
        }],
        wall_scopes=[{
            "equivalence": {
                "pair_classifications": [
                    ("extra", "host-a", Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
                ],
            },
        }],
    )
    pairs = report["openings"][0]["unproven_pair_ledger"]["unproven_pairs"]
    assert len(pairs) == 2
    relations = {p["producer_relation"] for p in pairs}
    assert "AMBIGUOUS_PHYSICAL_EQUIVALENCE" in relations
    assert "UNRECORDED" in relations
    assert all(p["distinctness_proven"] is False for p in pairs)
    assert report["measurement_published"] is False


def test_framed_opening_is_skipped():
    report = attach_frame_unproven_pair_ledgers(
        opening_rows=[{
            "physical_opening_id": "op-signed",
            "authenticated_frame_record_id": "frame-1",
            "frame_reason_codes": (),
            "source_host_member_wall_ids": ("a", "b"),
        }],
        wall_scopes=[],
    )
    assert report["frame_blocked_openings_with_ledger"] == 0
