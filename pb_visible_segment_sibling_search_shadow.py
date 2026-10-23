"""Search for RASTER_PDF_VISIBLE_SEGMENT siblings near opening segments (no host).

Diagnostic only. Does not grant host, frame, or measurement authority.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityAuthority,
)


def search_visible_segment_siblings_shadow(
    *,
    visibility: SourceVisibilityAuthority,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    opening_support_observation_ids: Sequence[str],
    page_visible_segment_observation_ids: Sequence[str],
) -> dict[str, Any]:
    """Report whether any page-visible segments exist that are not opening supports."""
    support = {str(x).strip() for x in opening_support_observation_ids if str(x).strip()}
    page_ids = [str(x).strip() for x in page_visible_segment_observation_ids if str(x).strip()]
    siblings: list[str] = []
    for oid in page_ids:
        if oid in support:
            continue
        res = visibility.resolve_visible(ObservationSelector(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            observation_id=oid,
        ))
        if res.status is not EvidenceResolutionStatus.CORROBORATED or res.observation is None:
            continue
        kind = str(getattr(res.observation, "observation_kind", "") or "")
        if kind == RASTER_PDF_VISIBLE_SEGMENT or "VISIBLE_SEGMENT" in kind.upper():
            siblings.append(oid)
    return {
        "status": "UNPUBLISHED_VISIBLE_SEGMENT_SIBLING_SEARCH",
        "support_observation_count": len(support),
        "page_visible_candidate_count": len(page_ids),
        "sibling_visible_segment_count": len(siblings),
        "sibling_observation_ids_sample": sorted(siblings)[:12],
        "host_granted": False,
        "first_remaining_gate": (
            "visible_segment_siblings_present_review_only"
            if siblings
            else "visible_segment_siblings_unavailable"
        ),
        "measurement_published": False,
        "shadow_only": True,
    }


def summarize_sibling_search_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gates: dict[str, int] = {}
    total_siblings = 0
    for row in rows:
        gate = str(row.get("first_remaining_gate") or "")
        gates[gate] = gates.get(gate, 0) + 1
        total_siblings += int(row.get("sibling_visible_segment_count") or 0)
    return {
        "status": "UNPUBLISHED_VISIBLE_SEGMENT_SIBLING_SEARCH_SUMMARY",
        "opening_count": len(rows),
        "gate_counts": dict(sorted(gates.items())),
        "total_sibling_hits": total_siblings,
        "host_granted": False,
        "shadow_only": True,
    }
