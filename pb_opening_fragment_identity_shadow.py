"""Mission item 4 — preserve opening identity across fragmented wall geometry.

Multiple host wall fragment IDs may support one physical opening. Distinct
physical openings must not collapse because fragments share a wall ID.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def _clean(value: object) -> str:
    return str(value or "").strip()


def assess_opening_fragment_identity_shadow(
    *,
    openings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Retain every physical opening; report shared fragment membership."""
    by_opening: dict[str, list[str]] = {}
    fragment_owners: dict[str, set[str]] = defaultdict(set)
    for row in openings:
        if not isinstance(row, Mapping):
            raise TypeError("opening row must be a mapping")
        oid = _clean(row.get("physical_opening_id"))
        if not oid:
            raise ValueError("physical opening identity required")
        if oid in by_opening:
            raise ValueError("duplicate physical opening identity")
        fragments = [
            _clean(f) for f in (row.get("host_member_wall_candidate_ids") or ()) if _clean(f)
        ]
        by_opening[oid] = sorted(set(fragments))
        for fid in by_opening[oid]:
            fragment_owners[fid].add(oid)

    shared = {
        fid: sorted(owners)
        for fid, owners in sorted(fragment_owners.items())
        if len(owners) > 1
    }
    collapsed = []
    # A collapse attempt would map multiple openings to one ID — report only.
    for oid, fragments in by_opening.items():
        if not fragments:
            collapsed.append({
                "physical_opening_id": oid,
                "blocker": "opening_host_fragments_unavailable",
            })

    return {
        "status": "UNPUBLISHED_OPENING_FRAGMENT_IDENTITY_SHADOW",
        "openings": [
            {
                "physical_opening_id": oid,
                "host_member_wall_candidate_ids": frags,
                "identity_preserved": True,
            }
            for oid, frags in sorted(by_opening.items())
        ],
        "shared_fragment_owners": shared,
        "incomplete_openings": collapsed,
        "merged_physical_opening_ids": [],
        "first_remaining_gate": (
            "shared_host_fragment_across_openings_review"
            if shared
            else (
                "opening_host_fragments_unavailable"
                if collapsed
                else "opening_fragment_identity_review_only"
            )
        ),
        "measurement_published": False,
        "shadow_only": True,
        "limitation": (
            "Shared fragment membership is retained for review; it does not merge "
            "distinct physical openings or grant host authority."
        ),
    }
