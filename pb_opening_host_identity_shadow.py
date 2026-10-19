"""D3 — Structural-host identity shadow: retain all candidates, never nearest.

Consumes producer-owned wall candidate IDs and optional equivalence pair classes.
Does not publish ``OpeningHostBinding`` or invent hosts from proximity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_physical_wall_identity import PhysicalEquivalenceClass


_DISTINCT = PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value
_SAME = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value
_AMBIGUOUS = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value


def _clean(value: object) -> str:
    return str(value or "").strip()


def build_opening_host_identity_shadow(
    *,
    physical_opening_id: str,
    candidate_wall_ids: Sequence[str],
    pair_classifications: Sequence[Sequence[str]] | Sequence[tuple[str, str, str]] = (),
) -> dict[str, Any]:
    """Classify host identity readiness while retaining every candidate."""
    oid = _clean(physical_opening_id)
    if not oid:
        raise ValueError("physical opening identity required")
    candidates = [_clean(wid) for wid in candidate_wall_ids if _clean(wid)]
    if len(candidates) != len(set(candidates)):
        raise ValueError("duplicate host candidate wall ids")

    relations: dict[tuple[str, str], str] = {}
    for row in pair_classifications:
        if len(row) != 3:
            raise ValueError("pair classification must be (left, right, class)")
        left, right, classification = (_clean(row[0]), _clean(row[1]), _clean(row[2]))
        if not left or not right or not classification:
            raise ValueError("incomplete pair classification")
        key = tuple(sorted((left, right)))
        if key in relations and relations[key] != classification:
            raise ValueError("conflicting pair classification")
        relations[key] = classification

    retained = sorted(candidates)
    if not retained:
        disposition = "structural_host_unavailable"
    elif len(retained) == 1:
        disposition = "unique_structural_host_candidate_observed"
    else:
        # Multi-candidate: require complete pairwise DISTINCT or SAME grouping
        # proof. Missing/AMBIGUOUS → fail closed. Never elect nearest/first.
        incomplete = False
        ambiguous = False
        for i, left in enumerate(retained):
            for right in retained[i + 1 :]:
                classification = relations.get(tuple(sorted((left, right))))
                if classification is None:
                    incomplete = True
                elif classification == _AMBIGUOUS:
                    ambiguous = True
        if ambiguous:
            disposition = "ambiguous_physical_wall_equivalence_for_host"
        elif incomplete:
            disposition = "physical_wall_equivalence_required_for_host"
        else:
            # All pairs classified SAME or DISTINCT — still review-only; unique
            # host band selection remains the producer authority's job.
            disposition = "multiple_structural_host_candidates_retained"

    return {
        "physical_opening_id": oid,
        "disposition": disposition,
        "retained_candidate_wall_ids": retained,
        "retained_candidate_count": len(retained),
        "elected_host_wall_id": None,
        "nearest_or_first_used": False,
        "host_granted": False,
        "frame_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }
