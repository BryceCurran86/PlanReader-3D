"""Read-only mission ledger for Cursor quantity-recovery PRs (not a score)."""
from __future__ import annotations

from typing import Any


# Static ledger of Cursor deliverables in this autonomous session. Update when
# new PRs land; never encode expected BOQ or match counts as targets.
MISSION_LEDGER: dict[str, Any] = {
    "status": "UNPUBLISHED_CURSOR_QUANTITY_RECOVERY_LEDGER",
    "shadow_only": True,
    "benchmark_score_granted": False,
    "prs": [
        {"number": 3348, "items": ["8-precursor"], "note": "G17 flank W4 end-reach ledger"},
        {"number": 3351, "items": ["2", "8"], "note": "end-reach attach to unhosted census"},
        {"number": 3350, "items": ["1", "3-4", "9-12", "14-18", "23-24", "26", "28"], "note": "arch + first shadow batch"},
        {"number": 3354, "items": ["1", "2-shadow", "4-collision"], "note": "receipt refresh, host identity, W4 collision"},
        {
            "number": 3356,
            "items": [
                "3",
                "4",
                "5-shadow",
                "6",
                "7-shadow",
                "10",
                "12-shadow",
                "13",
                "19-22",
                "25",
                "27",
                "29-30-refuse",
            ],
            "note": "batch2 + stacker/bifold/door-height fail-closed shadows + compose diag",
        },
        {
            "number": 3391,
            "items": [
                "host-lineage",
                "segment-parent-end-reach",
                "w4-id-disjoint",
                "multi-gate-original",
                "face-end-census",
                "remaining-gates-original",
                "maryborough-finish-pitch",
                "batch40b-deep-census",
                "batch40b-receipt-consistency",
                "host-architecture-note",
                "batch41-span-namespace",
                "digit-tail-ambiguous-abstain",
                "axis-pair-helper-restore",
                "batch42-raster-segment-split",
                "digit-tail-vs-raster_segment-not-dNi0",
            ],
            "note": (
                "batch40–42 host lineage; digit-tail hits are almost all "
                "raster_segment not dNi0; abstain; no FIRM/host/score"
            ),
        },
    ],
    "blocked_without_other_lanes_or_owner": [
        {"item": 5, "blocker": "STACKER host/frame FIRM — GPT MAX + owner PDF"},
        {"item": 7, "blocker": "BIFOLD kind FIRM promotion — needs source-closed MAX/GPT1"},
        {"item": 12, "blocker": "door height FIRM — owner USER_APPROVED or owned figured height"},
        {"item": 16, "blocker": "wall length/height FIRM — GPT1 seams with owned evidence"},
        {"item": 19, "blocker": "room/finish producers — GPT2"},
        {"item": 25, "blocker": "seal activation — GPT3 + owner promotion"},
        {"item": 29, "blocker": "frozen V2 eval after sealed appends — GPT3"},
        {"item": 30, "blocker": "verified score — post-eval only"},
    ],
}


def mission_ledger() -> dict[str, Any]:
    return dict(MISSION_LEDGER)


def main() -> None:
    import json
    print(json.dumps(mission_ledger(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
