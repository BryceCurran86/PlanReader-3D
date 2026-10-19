"""Attach frame unproven-pair ledgers to original opening frame receipts.

Pure diagnostic enrichment. Never grants frame, metric, quantity, or count.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_frame_unproven_pair_shadow import build_frame_unproven_pair_ledger

_TARGET_ALIGNED = "opening_host_frame_aligned_fragment_distinctness_unproven"
_PAIR_PREFIX = "opening_host_frame_unproven_wall_pair:"


def _pair_classifications_from_wall_scopes(
    wall_scopes: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for scope in wall_scopes:
        equivalence = scope.get("equivalence") or {}
        for row in equivalence.get("pair_classifications") or ():
            if len(row) != 3:
                raise ValueError("wall equivalence pair must be (left, right, class)")
            left, right, classification = (str(row[0]), str(row[1]), str(row[2]))
            key = tuple(sorted((left, right)))
            if key in seen:
                continue
            seen.add(key)
            rows.append((left, right, classification))
    return rows


def attach_frame_unproven_pair_ledgers(
    *,
    opening_rows: Sequence[Mapping[str, Any]],
    wall_scopes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build per-opening ledgers for frame-blocked originals only."""
    classifications = _pair_classifications_from_wall_scopes(wall_scopes)
    attached: list[dict[str, Any]] = []
    for row in opening_rows:
        identity = str(row.get("physical_opening_id") or "").strip()
        if not identity:
            raise ValueError("physical opening identity required")
        reasons = tuple(str(r) for r in (row.get("frame_reason_codes") or ()))
        host_members = tuple(
            str(m) for m in (row.get("source_host_member_wall_ids")
                             or row.get("host_member_wall_candidate_ids")
                             or ())
            if str(m).strip()
        )
        frame_id = row.get("authenticated_frame_record_id") or row.get("frame_record_id")
        has_pair_reason = any(r.startswith(_PAIR_PREFIX) for r in reasons)
        has_aligned = any(_TARGET_ALIGNED in r for r in reasons)
        if frame_id or not (has_pair_reason or has_aligned):
            continue
        ledger = build_frame_unproven_pair_ledger(
            reasons,
            classifications,
            component_member_ids=host_members,
        )
        attached.append({
            "physical_opening_id": identity,
            "frame_reason_codes": list(reasons),
            "source_host_member_wall_ids": list(host_members),
            "unproven_pair_ledger": ledger,
            "frame_granted": False,
            "measurement_published": False,
        })
    relation_counts: dict[str, int] = {}
    for item in attached:
        for pair in item["unproven_pair_ledger"]["unproven_pairs"]:
            key = pair["producer_relation"]
            relation_counts[key] = relation_counts.get(key, 0) + 1
    return {
        "status": "UNPUBLISHED_FRAME_UNPROVEN_PAIR_ORIGINAL_ATTACH",
        "frame_blocked_openings_with_ledger": len(attached),
        "producer_equivalence_pair_count": len(classifications),
        "relation_counts": dict(sorted(relation_counts.items())),
        "openings": attached,
        "frame_granted": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
