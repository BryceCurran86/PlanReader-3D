"""Test-only authority-selection reference for Net-wall Boolean Union."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from tests.net_wall_boolean_reference_v1 import Rect


@dataclass(frozen=True)
class ReferenceApplicableVoid:
    opening_identity_id: str
    host_wall_id: str
    geometry: Rect
    resolved: bool = True
    applicable: bool = True
    physical_equivalence_unambiguous: bool = True


def select_target_wall_voids_or_none(
    candidates: Sequence[ReferenceApplicableVoid],
    *,
    target_wall_id: str,
    opening_universe_complete: bool,
) -> Optional[tuple[Rect, ...]]:
    if not opening_universe_complete:
        return None

    selected: list[Rect] = []
    seen: dict[str, ReferenceApplicableVoid] = {}
    for candidate in candidates:
        if candidate.host_wall_id != target_wall_id:
            continue
        if not candidate.resolved:
            return None
        if not candidate.physical_equivalence_unambiguous:
            return None
        if not candidate.applicable:
            continue

        existing = seen.get(candidate.opening_identity_id)
        if existing is not None:
            if existing.geometry != candidate.geometry:
                return None
            continue
        seen[candidate.opening_identity_id] = candidate
        selected.append(candidate.geometry)

    return tuple(selected)
