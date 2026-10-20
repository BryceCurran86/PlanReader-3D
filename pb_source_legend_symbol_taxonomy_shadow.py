"""Producer-Owned Source Plan Legend Symbol Taxonomy & Graphical Key Disambiguation Shadow Authority.

Workstream C Item 26:
Detects drawing legend viewports, builds project symbol taxonomies (electrical,
plumbing, HVAC, fire), and quarantines legend boxes to prevent legend symbols
and swatches from falsely injecting ghost walls and fixtures into plan space.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_LEGEND_SEAL = object()


class LegendCategory(str, Enum):
    WALL_TYPES = "WALL_TYPES"
    ELECTRICAL_SYMBOLS = "ELECTRICAL_SYMBOLS"
    MECHANICAL_HVAC = "MECHANICAL_HVAC"
    PLUMBING_FIXTURES = "PLUMBING_FIXTURES"
    FIRE_SERVICES = "FIRE_SERVICES"


@dataclass(frozen=True)
class SymbolTaxonomyEntry:
    symbol_code: str
    description: str
    category: LegendCategory
    swatch_box: Tuple[float, float, float, float]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "symbol_code": self.symbol_code,
            "description": self.description,
            "category": self.category.value,
            "swatch_box": list(self.swatch_box),
        }


@dataclass(frozen=True)
class LegendViewportRecord:
    viewport_id: str
    sheet_id: str
    bbox: Tuple[float, float, float, float]
    category: LegendCategory
    symbol_count: int
    symbols: Tuple[SymbolTaxonomyEntry, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "viewport_id": self.viewport_id,
            "sheet_id": self.sheet_id,
            "bbox": list(self.bbox),
            "category": self.category.value,
            "symbol_count": self.symbol_count,
            "symbols": [s.to_dict() for s in self.symbols],
        }

    def contains_point(self, pt: Tuple[float, float]) -> bool:
        min_x, min_y, max_x, max_y = self.bbox
        return min_x <= pt[0] <= max_x and min_y <= pt[1] <= max_y


@dataclass(frozen=True)
class PlanLegendSymbolTaxonomyReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_legend_boxes_count: int
    total_registered_symbols: int
    viewports: Tuple[LegendViewportRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _LEGEND_SEAL:
            raise TypeError("PlanLegendSymbolTaxonomyReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_legend_boxes_count": self.total_legend_boxes_count,
            "total_registered_symbols": self.total_registered_symbols,
            "viewports": [v.to_dict() for v in self.viewports],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceLegendSymbolTaxonomyShadowAuthority:
    """Manages legend viewports, quarantining legend regions and cataloging symbol keys."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def register_legend_viewport(
        self,
        *,
        sheet_id: str,
        bbox: Tuple[float, float, float, float],
        category: LegendCategory,
        symbols: Sequence[Tuple[str, str, Tuple[float, float, float, float]]],
    ) -> LegendViewportRecord:
        entries: List[SymbolTaxonomyEntry] = []
        for code, desc, swatch in symbols:
            entries.append(
                SymbolTaxonomyEntry(
                    symbol_code=code,
                    description=desc,
                    category=category,
                    swatch_box=swatch,
                )
            )

        v_id = stable_contract_id(
            "LEGEND_VIEWPORT",
            (sheet_id, bbox, category.value, len(entries)),
        )

        return LegendViewportRecord(
            viewport_id=v_id,
            sheet_id=sheet_id,
            bbox=bbox,
            category=category,
            symbol_count=len(entries),
            symbols=tuple(entries),
        )

    def is_point_quarantined_in_legend(
        self,
        pt: Tuple[float, float],
        viewports: Sequence[LegendViewportRecord],
    ) -> bool:
        return any(v.contains_point(pt) for v in viewports)

    def compile_taxonomy_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        viewports: Sequence[LegendViewportRecord],
    ) -> PlanLegendSymbolTaxonomyReceipt:
        v_tuple = tuple(viewports)
        total_boxes = len(v_tuple)
        total_symbols = sum(v.symbol_count for v in v_tuple)

        receipt_id = stable_contract_id(
            "LEGEND_RECEIPT",
            (document_id, revision_id, source_sha256, total_boxes, total_symbols),
        )

        status = EvidenceResolutionStatus.CORROBORATED if total_boxes > 0 else EvidenceResolutionStatus.ABSTAINED

        return PlanLegendSymbolTaxonomyReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_legend_boxes_count=total_boxes,
            total_registered_symbols=total_symbols,
            viewports=v_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_LEGEND_SEAL,
        )
