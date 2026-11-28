"""Default-off generic room finish, wet-area tile-height, and setback witness shadow (AG-R10/R11).

Captures generic room-level finish/material evidence, wet-area waterproofing /
wall-tile height / boundary setback witnesses, and cross-sheet plan-to-schedule
/ elevation room correspondence for handoff to Claude's physical face lane and
MAX's issuer integration:

- Zero job-specific or room-name hardcoding (all rooms handled uniformly by
  normalized room key and explicit source witness type).
- Distinguishes explicit full-height tiling (``full_height``) vs explicit
  figured wall-tile height in mm (e.g., ``1800 mm`` / ``2.1 m``) vs explicit
  wet-area setback/hob witness (mm).
- Rejects cross-revision / cross-SHA witnesses, out-of-range heights/setbacks,
  and conflicting specs on the same room/surface.

Shadow-only (``shadow_only=True``, ``commercial_authority_granted=False``).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus


SCHEMA_VERSION = "1.0.0"

VALID_SURFACE_ROLES = frozenset({"floor", "wall", "wet_area_wall", "ceiling"})


@dataclass(frozen=True)
class RoomFinishSetbackWitness:
    """One producer-owned room finish, wall-tile height, or setback witness."""

    witness_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    room_key: str
    surface_role: str  # "floor" | "wall" | "wet_area_wall" | "ceiling"
    material_label: str
    tile_height_mm: Optional[float] = None
    full_height_lining: bool = False
    setback_mm: Optional[float] = None


@dataclass(frozen=True)
class RoomFinishSetbackSummary:
    """Aggregated shadow-only finish & setback handoff packet for one room/surface."""

    room_key: str
    surface_role: str
    material_label: Optional[str]
    tile_height_mm: Optional[float]
    full_height_lining: bool
    setback_mm: Optional[float]
    witness_ids: tuple[str, ...]
    source_page_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _valid_mm(value: Optional[float], *, low: float, high: float) -> bool:
    if value is None:
        return True
    return not isinstance(value, bool) and math.isfinite(value) and low <= float(value) <= high


def compile_room_finish_setback_witnesses_shadow(
    *,
    witnesses: Sequence[RoomFinishSetbackWitness],
    expected_document_id: str,
    expected_revision_id: str,
    expected_source_sha256: str,
) -> tuple[RoomFinishSetbackSummary, ...]:
    """Compile and conflict-check room finish/tile-height/setback witnesses."""
    grouped: dict[tuple[str, str], list[RoomFinishSetbackWitness]] = {}
    for w in witnesses:
        if (
            w.document_id != expected_document_id
            or w.revision_id != expected_revision_id
            or w.source_sha256 != expected_source_sha256
        ):
            continue
        rkey = str(w.room_key or "").strip()
        role = str(w.surface_role or "").strip().lower()
        if not rkey or role not in VALID_SURFACE_ROLES:
            continue
        grouped.setdefault((rkey, role), []).append(w)

    results: list[RoomFinishSetbackSummary] = []
    for (rkey, role), group in sorted(grouped.items()):
        wids = tuple(sorted(w.witness_id for w in group))
        pages = tuple(sorted({str(w.page_id) for w in group}))

        if any(
            not str(w.material_label or "").strip()
            or not _valid_mm(w.tile_height_mm, low=100.0, high=6000.0)
            or not _valid_mm(w.setback_mm, low=0.0, high=5000.0)
            or (w.full_height_lining and w.tile_height_mm is not None)
            for w in group
        ):
            results.append(
                RoomFinishSetbackSummary(
                    room_key=rkey,
                    surface_role=role,
                    material_label=None,
                    tile_height_mm=None,
                    full_height_lining=False,
                    setback_mm=None,
                    witness_ids=wids,
                    source_page_ids=pages,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=("room_finish_witness_invalid_or_out_of_range",),
                )
            )
            continue

        mats = {" ".join(w.material_label.strip().upper().split()) for w in group}
        heights = {w.tile_height_mm for w in group if w.tile_height_mm is not None}
        full_flags = {bool(w.full_height_lining) for w in group}
        setbacks = {w.setback_mm for w in group if w.setback_mm is not None}

        if len(mats) > 1 or len(heights) > 1 or len(full_flags) > 1 or len(setbacks) > 1:
            results.append(
                RoomFinishSetbackSummary(
                    room_key=rkey,
                    surface_role=role,
                    material_label=None,
                    tile_height_mm=None,
                    full_height_lining=False,
                    setback_mm=None,
                    witness_ids=wids,
                    source_page_ids=pages,
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=("room_finish_or_setback_witness_conflict",),
                )
            )
            continue

        results.append(
            RoomFinishSetbackSummary(
                room_key=rkey,
                surface_role=role,
                material_label=" ".join(group[0].material_label.strip().split()),
                tile_height_mm=next(iter(heights), None),
                full_height_lining=next(iter(full_flags)),
                setback_mm=next(iter(setbacks), None),
                witness_ids=wids,
                source_page_ids=pages,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(
                    "room_finish_cross_sheet_corroborated"
                    if len(pages) > 1
                    else "room_finish_single_sheet_corroborated",
                ),
            )
        )

    return tuple(results)


__all__ = [
    "RoomFinishSetbackSummary",
    "RoomFinishSetbackWitness",
    "SCHEMA_VERSION",
    "VALID_SURFACE_ROLES",
    "compile_room_finish_setback_witnesses_shadow",
]
