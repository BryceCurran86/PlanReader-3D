"""Fail-closed semantic kind authority for authenticated physical openings.

This module never creates physical openings and never reads benchmark truth.
It reconciles two already-authenticated semantic evidence sources:

* structural opening pattern from PhysicalOpeningAuthority
* normalized schedule trade type from an explicitly bound schedule instance

A positive door/window structural pattern may classify a physical instance even
when no schedule row is bound.  A schedule may corroborate that class.  If both
sources exist and disagree, the result is CONFLICT and no kind is published.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)


OPENING_KIND_SCHEMA_VERSION = "1.0.0"
OPENING_KIND_STRUCTURAL_DOOR = "opening_kind_structural_door"
OPENING_KIND_STRUCTURAL_WINDOW = "opening_kind_structural_window"
OPENING_KIND_SCHEDULE = "opening_kind_schedule"
OPENING_KIND_LABEL = "opening_kind_label"
OPENING_KIND_CORROBORATED = "opening_kind_corroborated"
OPENING_KIND_CONFLICT = "opening_kind_conflict"
OPENING_KIND_UNAVAILABLE = "opening_kind_unavailable"

_STRUCTURAL_KIND = {
    GAP_CORROBORATED_DOOR_JAMB_LEAF: "door",
    GAP_CORROBORATED_WINDOW_JAMB_PAIR: "window",
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION: "door",
}


@dataclass(frozen=True)
class OpeningKindResolution:
    status: EvidenceResolutionStatus
    opening_kind: Optional[str]
    structural_kind: Optional[str]
    schedule_kind: Optional[str]
    label_kind: Optional[str]
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_KIND_SCHEMA_VERSION


def _normalize_kind(value: object) -> Optional[str]:
    text = str(value or "").strip().lower()
    if text in {"door", "doors"}:
        return "door"
    if text in {"window", "windows"}:
        return "window"
    return None


def resolve_opening_kind(
    *,
    structural_pattern: object,
    schedule_trade_type: object = None,
    label_kind: object = None,
) -> OpeningKindResolution:
    """Resolve a physical opening subtype without guessing from labels.

    Structural pattern is positive source geometry already authenticated by
    PhysicalOpeningAuthority.  schedule_trade_type is accepted only after an
    explicit instance-to-schedule binding has already been proven upstream.
    """

    pattern = str(structural_pattern or "").strip()
    structural_kind = _STRUCTURAL_KIND.get(pattern)
    schedule_kind = _normalize_kind(schedule_trade_type)
    normalized_label_kind = _normalize_kind(label_kind)

    reasons: list[str] = []
    if structural_kind == "door":
        reasons.append(OPENING_KIND_STRUCTURAL_DOOR)
    elif structural_kind == "window":
        reasons.append(OPENING_KIND_STRUCTURAL_WINDOW)
    if schedule_kind is not None:
        reasons.append(OPENING_KIND_SCHEDULE)
    if normalized_label_kind is not None:
        reasons.append(OPENING_KIND_LABEL)

    authenticated_kinds = tuple(
        kind
        for kind in (structural_kind, schedule_kind, normalized_label_kind)
        if kind is not None
    )
    if len(set(authenticated_kinds)) > 1:
        return OpeningKindResolution(
            status=EvidenceResolutionStatus.CONFLICT,
            opening_kind=None,
            structural_kind=structural_kind,
            schedule_kind=schedule_kind,
            label_kind=normalized_label_kind,
            reason_codes=tuple((*reasons, OPENING_KIND_CONFLICT)),
        )

    resolved = authenticated_kinds[0] if authenticated_kinds else None
    if resolved is not None:
        return OpeningKindResolution(
            status=EvidenceResolutionStatus.CORROBORATED,
            opening_kind=resolved,
            structural_kind=structural_kind,
            schedule_kind=schedule_kind,
            label_kind=normalized_label_kind,
            reason_codes=tuple((*reasons, OPENING_KIND_CORROBORATED)),
        )

    return OpeningKindResolution(
        status=EvidenceResolutionStatus.ABSTAINED,
        opening_kind=None,
        structural_kind=None,
        schedule_kind=None,
        label_kind=None,
        reason_codes=(OPENING_KIND_UNAVAILABLE,),
    )


__all__ = [
    "OPENING_KIND_CONFLICT",
    "OPENING_KIND_CORROBORATED",
    "OPENING_KIND_SCHEMA_VERSION",
    "OPENING_KIND_SCHEDULE",
    "OPENING_KIND_LABEL",
    "OPENING_KIND_STRUCTURAL_DOOR",
    "OPENING_KIND_STRUCTURAL_WINDOW",
    "OPENING_KIND_UNAVAILABLE",
    "OpeningKindResolution",
    "resolve_opening_kind",
]
