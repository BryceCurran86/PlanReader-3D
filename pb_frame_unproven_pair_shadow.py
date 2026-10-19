"""Shadow ledger for aligned-frame unproven wall/member pairs (mission 3–4).

Post-#3338, ``OpeningHostFrameProducer._shared_host_frame`` may emit
``opening_host_frame_unproven_wall_pair:{wall}:{member}`` reason codes under
``source_fragment_roles_shadow``. This module turns those codes plus producer
equivalence classifications into a stable sorted SAME/DISTINCT/AMBIGUOUS/
UNRECORDED ledger without granting frame, metric, or quantity authority.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_physical_wall_identity import PhysicalEquivalenceClass


_PAIR_PREFIX = "opening_host_frame_unproven_wall_pair:"
_DISTINCT = PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value
_SAME = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value
_AMBIGUOUS = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value


def _clean(value: object) -> str:
    return str(value or "").strip()


def parse_unproven_wall_pair_reason(reason: str) -> tuple[str, str] | None:
    text = _clean(reason)
    if not text.startswith(_PAIR_PREFIX):
        return None
    rest = text[len(_PAIR_PREFIX) :]
    wall_id, sep, member_id = rest.partition(":")
    if not sep or not _clean(wall_id) or not _clean(member_id):
        return None
    return _clean(wall_id), _clean(member_id)


def build_frame_unproven_pair_ledger(
    reason_codes: Sequence[str],
    pair_classifications: Sequence[Sequence[str]] | Sequence[tuple[str, str, str]],
    *,
    component_member_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Classify every unproven aligned pair; never invent DISTINCT or a frame."""
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

    members = {_clean(mid) for mid in component_member_ids if _clean(mid)}
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for reason in reason_codes:
        parsed = parse_unproven_wall_pair_reason(reason)
        if parsed is None:
            continue
        wall_id, member_id = parsed
        key = tuple(sorted((wall_id, member_id)))
        if key in seen:
            continue
        seen.add(key)
        classification = relations.get(key)
        if classification == _DISTINCT:
            relation = "DISTINCT_PHYSICAL_WALLS"
            # A DISTINCT receipt would not normally appear as an unproven pair;
            # retain it explicitly and still refuse frame grant.
            blocker = "distinct_recorded_but_still_listed_unproven"
        elif classification == _SAME:
            relation = "SAME_PHYSICAL_WALL"
            blocker = "same_physical_wall_blocks_whole_wall_extent"
        elif classification == _AMBIGUOUS:
            relation = "AMBIGUOUS_PHYSICAL_EQUIVALENCE"
            blocker = "ambiguous_physical_equivalence"
        elif classification is None:
            relation = "UNRECORDED"
            blocker = "unrecorded_equivalence_relation"
        else:
            relation = classification
            blocker = "non_distinct_equivalence_relation"
        pairs.append({
            "aligned_wall_candidate_id": wall_id,
            "component_member_id": member_id,
            "sorted_pair": list(key),
            "producer_relation": relation,
            "distinctness_proven": classification == _DISTINCT,
            "member_is_component": member_id in members,
            "blocker": blocker,
            "frame_granted": False,
        })

    pairs_sorted = sorted(
        pairs,
        key=lambda row: (row["sorted_pair"][0], row["sorted_pair"][1]),
    )
    return {
        "status": "UNPUBLISHED_FRAME_UNPROVEN_PAIR_SHADOW",
        "unproven_pair_count": len(pairs_sorted),
        "unproven_pairs": pairs_sorted,
        "frame_granted": False,
        "metric_quantity_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
        "limitation": (
            "Diagnostic addressing of aligned competitors only. UNRECORDED and "
            "AMBIGUOUS are never positive DISTINCT. No frame publish."
        ),
    }
