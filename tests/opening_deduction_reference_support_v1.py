"""Test-only reference semantics for Opening Deduction Authority set behavior.

These helpers do not mint commercial deduction authority. They encode fail-closed
set relationships used by the red-team lane while production Physical Opening Void
and Opening Deduction authorities are still unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence


@dataclass(frozen=True)
class ReferenceDeductionCandidate:
    opening_identity_id: str
    physical_void_record_id: str
    wall_id: str
    face_scope_id: str
    assembly_scope_id: str
    diagnostic_area_m2: float
    resolved: bool = True

    def __post_init__(self) -> None:
        if not self.opening_identity_id:
            raise ValueError("opening_identity_id is required")
        if not self.physical_void_record_id:
            raise ValueError("physical_void_record_id is required")
        if not math.isfinite(self.diagnostic_area_m2) or self.diagnostic_area_m2 < 0.0:
            raise ValueError("diagnostic_area_m2 must be finite and non-negative")


def authorize_reference_deduction_set(
    candidates: Sequence[ReferenceDeductionCandidate],
    *,
    universe_complete: bool,
    wall_id: str,
    face_scope_id: str,
    assembly_scope_id: str,
) -> Optional[tuple[ReferenceDeductionCandidate, ...]]:
    """Return a deduplicated reference set only when every prerequisite is known.

    This is deliberately stricter than provisional arithmetic. Incomplete universes,
    one unresolved relevant opening, scope mismatch, or contradictory duplicate
    physical-opening identities block the entire authoritative set.
    """
    if not universe_complete:
        return None

    by_identity: dict[str, ReferenceDeductionCandidate] = {}
    for candidate in candidates:
        if not candidate.resolved:
            return None
        if candidate.wall_id != wall_id:
            return None
        if candidate.face_scope_id != face_scope_id:
            return None
        if candidate.assembly_scope_id != assembly_scope_id:
            return None

        existing = by_identity.get(candidate.opening_identity_id)
        if existing is None:
            by_identity[candidate.opening_identity_id] = candidate
            continue
        if existing != candidate:
            return None

    return tuple(by_identity[key] for key in sorted(by_identity))


def reference_total_area_or_none(
    authorized: Optional[Sequence[ReferenceDeductionCandidate]],
) -> Optional[float]:
    """Diagnostic scalar after authority readiness; never converts unknown to zero."""
    if authorized is None:
        return None
    return sum(candidate.diagnostic_area_m2 for candidate in authorized)
