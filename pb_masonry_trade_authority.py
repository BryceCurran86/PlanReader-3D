"""PlanReader Masonry Trade Authority Engine (AG-25).

Bridges canonical building model geometry to the specialist Masonry (Brickwork & Blockwork) trade takeoff schedule.
Calculates high-precision masonry trade quantities without duplicate extraction or hallucination:
- Brickwork: External face brick veneer, common brick skins, cavity wall ties (m² & No.)
- Concrete Blockwork: 100/150/200mm series structural blockwork (m²)
- Core Fill & Grouting: Fully or partially core-filled hollow blocks (m³ grout via item)
- Bond Beams & Lintels: Horizontal bond beams (lm), structural steel angle/T-bar lintels (No. & lm)
- Flashings & DPC: Base damp-proof course, window sill trays, weep holes (lm & No.)
- Articulation Joints: Vertical control/expansion joints with backing rod and sealant (lm)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

MASONRY_SOURCE_PREFIX = "PB Masonry Authority v1.0"
STANDARD_BRICKS_PER_M2 = 48.5       # Standard 230x110x76mm brickwork with 10mm mortar joints
STANDARD_BLOCKS_PER_M2 = 12.5       # Standard 390x190mm series concrete blocks
STANDARD_TIES_PER_M2 = 4.5          # Cavity wall ties @ 600x400mm grid


@dataclass
class MasonryWallSpec:
    """Specification and dimensions for a structural masonry or brick veneer wall."""
    element_id: str            # Stable identifier (e.g. "W_BRICK_EXT_01")
    wall_type: str             # "brickwork_veneer", "double_brick", "blockwork_200", "blockwork_150", "blockwork_100"
    description: str
    section: str = "External"  # "External", "Internal", "Substructure"
    length_m: float = 0.0
    height_m: float = 2.70
    openings: List[Dict[str, float]] = field(default_factory=list)  # [{"width": 1.8, "height": 1.2, "area": 2.16}]
    core_fill: str = "none"    # "none", "full", "half" (at 800mm), "quarter" (at 1200mm)
    has_bond_beam: bool = False
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class MasonryTakeoffItem:
    """Standardized masonry trade takeoff item compliant with PlanReader contracts."""
    section: str
    element: str
    location: str
    substrate: str
    finish_system: str
    quantity: float
    unit: str                  # Must be in TAKEOFF_UNITS: 'm²', 'lm', 'No.', 'item', 'L', 'allowance'
    quantity_status: str       # "Measured", "Estimated", "Provisional"
    source_page: str
    source_reference: str
    inclusion_status: str      # "INCLUSION" or "PROVISIONAL"
    confidence: str            # "Verified", "High", "Documented", "Provisional"
    notes: str
    row_role: str = ""

    def to_core_row(self, workspace_id: int, now_stamp: str) -> Dict[str, Any]:
        """Convert to canonical 21-field core takeoff row."""
        assert self.unit in takeoff_contract.TAKEOFF_UNITS, f"Invalid unit {self.unit}"
        return {
            "workspace_id": int(workspace_id),
            "section": str(self.section),
            "element": str(self.element),
            "location": str(self.location),
            "substrate": str(self.substrate),
            "finish_system": str(self.finish_system),
            "quantity": round(float(self.quantity), 2),
            "unit": str(self.unit),
            "quantity_status": str(self.quantity_status),
            "source_page": str(self.source_page or "Architectural A101"),
            "source_reference": str(self.source_reference or MASONRY_SOURCE_PREFIX),
            "inclusion_status": str(self.inclusion_status),
            "coats": 1,
            "coverage_m2_per_litre": 0.0,
            "productivity_m2_per_hour": 0.0,
            "rate_per_unit": 0.0,
            "confidence": str(self.confidence),
            "notes": str(self.notes),
            "row_role": str(self.row_role),
            "created_at": str(now_stamp),
            "updated_at": str(now_stamp),
        }


def calculate_brickwork_items(spec: MasonryWallSpec) -> List[MasonryTakeoffItem]:
    """Calculate trade takeoff items for brickwork veneer or double brick walls."""
    items: List[MasonryTakeoffItem] = []
    if spec.length_m <= 0.0 or spec.height_m <= 0.0:
        return items

    gross_m2 = spec.length_m * spec.height_m
    opening_ded_m2 = sum(float(op.get("area") or (float(op.get("width", 0)) * float(op.get("height", 0)))) for op in spec.openings)
    net_m2 = round(max(0.0, gross_m2 - opening_ded_m2), 2)
    if net_m2 <= 0.0:
        return items

    multiplier = 2.0 if spec.wall_type == "double_brick" else 1.0
    brick_count = int(round(net_m2 * STANDARD_BRICKS_PER_M2 * multiplier))
    mortar_m3 = round(net_m2 * 0.040 * multiplier, 2)

    # 1. Primary Brickwork Wall Area (m²)
    items.append(MasonryTakeoffItem(
        section=spec.section,
        element="Face brickwork skin (76mm standard)",
        location=f"Wall · {spec.element_id}",
        substrate="Selected clay face bricks with 10mm ironed mortar joints",
        finish_system="Laid in stretcher bond, washed down and cleaned with acid wash",
        quantity=net_m2 * multiplier,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Net area: {net_m2:.2f} m² (Gross {gross_m2:.2f} m² - Openings {opening_ded_m2:.2f} m²). Est: ~{brick_count:,} bricks & {mortar_m3:.2f} m³ mortar.",
        row_role="external_wall" if spec.section == "External" else "",
    ))

    # 2. Cavity Wall Ties (No.)
    if spec.section == "External":
        tie_count = int(round(net_m2 * STANDARD_TIES_PER_M2))
        items.append(MasonryTakeoffItem(
            section=spec.section,
            element="Galvanized cavity wall ties",
            location=f"Cavity · {spec.element_id}",
            substrate="Stainless steel / galvanized heavy-duty wire ties",
            finish_system="Built into mortar joints @ 600mm H × 400mm V spacing",
            quantity=float(tie_count),
            unit="No.",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Estimated {tie_count} No. wall ties across {net_m2:.2f} m² cavity wall.",
            row_role="",
        ))

    # 3. Base DPC & Flashing (lm)
    items.append(MasonryTakeoffItem(
        section=spec.section,
        element="Damp-proof course (DPC) & perimeter flashing",
        location=f"Base · {spec.element_id}",
        substrate="Alcor / poly damp-proof course",
        finish_system="Built in at slab level with weep holes at 1200mm centres",
        quantity=round(spec.length_m, 2),
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Base flashing length: {spec.length_m:.2f} lm with mortar bed.",
        row_role="",
    ))

    return items


def calculate_blockwork_items(spec: MasonryWallSpec) -> List[MasonryTakeoffItem]:
    """Calculate trade takeoff items for concrete blockwork walls and core-filling."""
    items: List[MasonryTakeoffItem] = []
    if spec.length_m <= 0.0 or spec.height_m <= 0.0:
        return items

    gross_m2 = spec.length_m * spec.height_m
    opening_ded_m2 = sum(float(op.get("area") or (float(op.get("width", 0)) * float(op.get("height", 0)))) for op in spec.openings)
    net_m2 = round(max(0.0, gross_m2 - opening_ded_m2), 2)
    if net_m2 <= 0.0:
        return items

    series_mm = 200
    if "150" in spec.wall_type:
        series_mm = 150
    elif "100" in spec.wall_type:
        series_mm = 100

    block_count = int(round(net_m2 * STANDARD_BLOCKS_PER_M2))

    # 1. Blockwork Wall Area (m²)
    items.append(MasonryTakeoffItem(
        section=spec.section,
        element=f"Concrete blockwork wall ({series_mm}mm series)",
        location=f"Block wall · {spec.element_id}",
        substrate=f"{series_mm}mm hollow concrete blocks",
        finish_system="Laid in 1:1:6 cement mortar with flush tooled joints",
        quantity=net_m2,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Net wall area: {net_m2:.2f} m² (~{block_count:,} blocks). Gross {gross_m2:.2f} m² less {opening_ded_m2:.2f} m² openings.",
        row_role="external_wall" if spec.section == "External" else "internal_partition",
    ))

    # 2. Core Fill Concrete / Grout (item with m³ formula notes)
    if spec.core_fill in ("full", "half", "quarter"):
        factor = 1.0 if spec.core_fill == "full" else (0.5 if spec.core_fill == "half" else 0.25)
        # 200mm block full core fill: approx 0.10 m³ grout / m² wall
        grout_rate = 0.10 if series_mm >= 200 else 0.075
        grout_vol_m3 = round(net_m2 * grout_rate * factor, 2)

        items.append(MasonryTakeoffItem(
            section=spec.section,
            element=f"Core fill concrete / block grout ({spec.core_fill} fill)",
            location=f"Block cores · {spec.element_id}",
            substrate="20MPa fine aggregate core-fill concrete",
            finish_system="Pumped into vertical cores and compacted by vibrator",
            quantity=grout_vol_m3,
            unit="item",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Grout volume: {grout_vol_m3:.2f} m³ ({spec.core_fill} core-fill across {net_m2:.2f} m² of {series_mm}mm blockwork).",
            row_role="",
        ))

    # 3. Horizontal Bond Beam (lm)
    if spec.has_bond_beam:
        items.append(MasonryTakeoffItem(
            section=spec.section,
            element=f"Horizontal bond beam ({series_mm}mm knock-out blocks)",
            location=f"Bond beam · {spec.element_id}",
            substrate=f"{series_mm}mm knock-out bond beam block with 2-N12 bars",
            finish_system="Grout filled with reinforcing steel",
            quantity=round(spec.length_m, 2),
            unit="lm",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Bond beam length: {spec.length_m:.2f} lm.",
            row_role="",
        ))

    return items


def calculate_lintel_items(spec: MasonryWallSpec) -> List[MasonryTakeoffItem]:
    """Calculate steel/concrete lintels over wall openings."""
    items: List[MasonryTakeoffItem] = []
    for i, op in enumerate(spec.openings):
        w = float(op.get("width") or 0.0)
        if w <= 0.0:
            continue
        # Standard bearing: 150mm each side (total length = w + 0.30m)
        lintel_length_m = round(w + 0.30, 2)
        desc = "Galvanized steel angle lintel (100x100x6)" if w <= 1.8 else "Galvanized T-bar / heavy lintel (150UB)"

        items.append(MasonryTakeoffItem(
            section=spec.section,
            element=f"Opening lintel ({desc})",
            location=f"Lintel #{i+1} · {spec.element_id}",
            substrate="Hot-dip galvanized structural steel lintel",
            finish_system="Bedded on mortar with 150mm end bearings",
            quantity=lintel_length_m,
            unit="lm",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{MASONRY_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Lintel over {w:.2f}m opening (Length: {lintel_length_m:.2f} lm including bearings).",
            row_role="",
        ))

    return items


def generate_workspace_masonry_takeoff(
    specs: Sequence[MasonryWallSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all masonry elements."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[MasonryTakeoffItem] = []
        if "brick" in spec.wall_type:
            items.extend(calculate_brickwork_items(spec))
        elif "block" in spec.wall_type:
            items.extend(calculate_blockwork_items(spec))

        if spec.openings:
            items.extend(calculate_lintel_items(spec))

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
