"""Producer-Owned Source Multi-Story Floor-to-Floor Level Datum & Height Extrusion Shadow Authority.

Workstream C Item 25:
Extracts building elevation datums (RL / FFL / SSL), associates plan sheets
with story levels, computes exact floor-to-floor heights (delta RL), and defines
vertical extrusion bounds for 3D walls, columns, stairs, and shafts.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_DATUM_SEAL = object()


@dataclass(frozen=True)
class StoryLevelRecord:
    level_id: str
    level_name: str
    story_index: int
    elevation_reduced_level_m: float
    finished_floor_level_m: float
    structural_slab_level_m: float
    floor_to_floor_height_m: float
    floor_to_ceiling_clear_height_m: float
    associated_sheet_ids: Tuple[str, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "level_id": self.level_id,
            "level_name": self.level_name,
            "story_index": self.story_index,
            "elevation_reduced_level_m": self.elevation_reduced_level_m,
            "finished_floor_level_m": self.finished_floor_level_m,
            "structural_slab_level_m": self.structural_slab_level_m,
            "floor_to_floor_height_m": self.floor_to_floor_height_m,
            "floor_to_ceiling_clear_height_m": self.floor_to_ceiling_clear_height_m,
            "associated_sheet_ids": list(self.associated_sheet_ids),
        }


@dataclass(frozen=True)
class BuildingLevelDatumReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_levels_count: int
    base_level_elevation_m: float
    top_level_elevation_m: float
    total_building_height_m: float
    levels: Tuple[StoryLevelRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _DATUM_SEAL:
            raise TypeError("BuildingLevelDatumReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_levels_count": self.total_levels_count,
            "base_level_elevation_m": self.base_level_elevation_m,
            "top_level_elevation_m": self.top_level_elevation_m,
            "total_building_height_m": self.total_building_height_m,
            "levels": [l.to_dict() for l in self.levels],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceLevelDatumHeightExtrusionShadowAuthority:
    """Computes vertical building level stack, floor-to-floor heights, and story extrusions."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compile_level_stack(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        raw_levels: Sequence[Mapping[str, Any]],
        default_floor_finish_thickness_m: float = 0.05,
        default_ceiling_offset_m: float = 0.60,
    ) -> BuildingLevelDatumReceipt:
        if not raw_levels:
            receipt_id = stable_contract_id(
                "LEVEL_DATUM_RECEIPT",
                (document_id, revision_id, source_sha256, 0),
            )
            return BuildingLevelDatumReceipt(
                receipt_id=receipt_id,
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                total_levels_count=0,
                base_level_elevation_m=0.0,
                top_level_elevation_m=0.0,
                total_building_height_m=0.0,
                levels=(),
                status=EvidenceResolutionStatus.ABSTAINED,
                schema_version=SCHEMA_VERSION,
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                _seal=_DATUM_SEAL,
            )

        # Sort ascending by elevation
        sorted_raw = sorted(
            raw_levels,
            key=lambda l: float(l.get("elevation_reduced_level_m", 0.0)),
        )

        n = len(sorted_raw)
        records: List[StoryLevelRecord] = []

        for i, item in enumerate(sorted_raw):
            rl = float(item["elevation_reduced_level_m"])
            name = str(item.get("level_name", f"Level_{i}"))
            sheets = tuple(item.get("associated_sheet_ids", ()))
            finish_t = float(item.get("floor_finish_thickness_m", default_floor_finish_thickness_m))
            ceil_offset = float(item.get("ceiling_offset_m", default_ceiling_offset_m))

            if i < n - 1:
                next_rl = float(sorted_raw[i + 1]["elevation_reduced_level_m"])
                f2f = round(next_rl - rl, 4)
            else:
                # Top roof/parapet level
                f2f = float(item.get("floor_to_floor_height_m", 3.0))

            clear_h = max(0.0, f2f - ceil_offset)
            ffl = rl
            ssl = round(rl - finish_t, 4)

            level_id = stable_contract_id("LEVEL", (document_id, name, i, rl))

            records.append(
                StoryLevelRecord(
                    level_id=level_id,
                    level_name=name,
                    story_index=i,
                    elevation_reduced_level_m=round(rl, 4),
                    finished_floor_level_m=round(ffl, 4),
                    structural_slab_level_m=ssl,
                    floor_to_floor_height_m=round(f2f, 4),
                    floor_to_ceiling_clear_height_m=round(clear_h, 4),
                    associated_sheet_ids=sheets,
                )
            )

        base_rl = records[0].elevation_reduced_level_m
        top_rl = records[-1].elevation_reduced_level_m
        total_height = round(top_rl - base_rl, 4)

        receipt_id = stable_contract_id(
            "LEVEL_DATUM_RECEIPT",
            (document_id, revision_id, source_sha256, n, base_rl, top_rl),
        )

        return BuildingLevelDatumReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_levels_count=n,
            base_level_elevation_m=base_rl,
            top_level_elevation_m=top_rl,
            total_building_height_m=total_height,
            levels=tuple(records),
            status=EvidenceResolutionStatus.CORROBORATED,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_DATUM_SEAL,
        )
