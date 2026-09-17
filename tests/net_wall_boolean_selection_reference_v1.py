"""Test-only authority-selection reference for Net-wall Boolean Union.

This module never authorizes geometry. It models fail-closed selection behavior after
upstream physical-void/applicability propositions have been independently resolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class ReferenceApplicableVoid:
    opening_identity_id: str
    host_wall_id: str
    geometry: BaseGeometry
    resolved: bool = True
    applicable: bool = True
    physical_equivalence_unambiguous: bool = True


def select_target_wall_voids_or_none(
    candidates: Sequence[ReferenceApplicableVoid],
    *,
    target_wall_id: str,
    opening_universe_complete: bool,
) -> Optional[tuple[BaseGeometry, ...]]:
    """Return target-wall applicable voids only when every relevant fact is known."""
    if not opening_universe_complete:
        return None

    selected: list[BaseGeometry] = []
    seen: dict[str, ReferenceApplicableVoid] = {}
    for candidate in candidates:
        # A positively different host is irrelevant to this wall and must never be
        # subtracted from it.
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
            # Exact duplicate observation is harmless; contradictory geometry for
            # one physical opening blocks instead of first/nearest wins.
            if not existing.geometry.equals(candidate.geometry):
                return None
            continue
        seen[candidate.opening_identity_id] = candidate
        selected.append(candidate.geometry)

    return tuple(selected)
