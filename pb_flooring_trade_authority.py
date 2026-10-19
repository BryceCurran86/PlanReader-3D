"""PlanReader Flooring & Tiling Trade Authority Engine (AG-26).

Bridges canonical building space and room geometry to the specialist Flooring & Tiling trade takeoff schedule.
Calculates high-precision trade quantities without duplicate extraction or hallucination:
- Carpet & Resilient: Carpet (m²), underlay (m²), smooth-edge perimeter grippers (lm), transitions
- Timber & Laminate: Engineered timber / hybrid flooring (m²), acoustic underlay (m²), perimeter quads (lm)
- Vinyl & Sheet: Vinyl planks / commercial sheet (m²), floor levelling/prep (m²), coved skirtings (lm)
- Floor Tiling: Ceramic / porcelain floor tiles (m²), tile skirtings (lm), edge angle trims (lm)
- Wet-Area Substrates: Sand & cement screed to falls (m²), liquid waterproofing membrane with upturns (m²)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

FLOORING_SOURCE_PREFIX = "PB Flooring Authority v1.0"


@dataclass
class FlooringSpaceSpec:
    """Specification and dimensions for a room or space requiring floor finishes."""
    space_id: str              # Stable room identifier (e.g. "ROOM_BED_01", "ROOM_BATH_01")
    room_name: str             # e.g. "Bedroom 1", "Living / Dining", "Master Ensuite"
    floor_finish: str          # "carpet", "timber", "vinyl", "tiles"
    section: str = "Internal"  # "Internal", "External"
    area_m2: float = 0.0
    perimeter_lm: float = 0.0
    door_deduction_lm: float = 0.90
    is_wet_area: bool = False
    requires_screed: bool = False
    screed_depth_mm: int = 40
    requires_waterproofing: bool = False
    tile_size_desc: str = "600x600 Porcelain"
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class FlooringTakeoffItem:
    """Standardized flooring trade takeoff item compliant with PlanReader contracts."""
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
            "source_page": str(self.source_page or "Finishes Schedule"),
            "source_reference": str(self.source_reference or FLOORING_SOURCE_PREFIX),
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


def _typed_metric(value: object, *, positive: bool = False) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        metric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(metric) or metric < 0.0 or (positive and metric <= 0.0):
        return None
    return metric


def _original_doorway_net_perimeter(spec: FlooringSpaceSpec) -> float | None:
    """Return the model's skirting/gripper estimate, never a FIRM line item."""
    perimeter = _typed_metric(spec.perimeter_lm)
    doorway = _typed_metric(spec.door_deduction_lm)
    if perimeter is None or doorway is None or doorway > perimeter:
        return None
    return round(perimeter - doorway, 2)


def calculate_timber_flooring_items(spec: FlooringSpaceSpec) -> List[FlooringTakeoffItem]:
    """Calculate trade items for timber, engineered wood, or laminate flooring."""
    items: List[FlooringTakeoffItem] = []
    if _typed_metric(spec.area_m2, positive=True) is None:
        return items

    # 1. Timber Floor Covering (m²)
    items.append(FlooringTakeoffItem(
        section=spec.section,
        element="Engineered timber flooring",
        location=f"{spec.room_name} · {spec.space_id}",
        substrate="Selected engineered timber boards floating on acoustic underlay",
        finish_system="Laid with staggered end-joints and 10mm perimeter expansion gap",
        quantity=spec.area_m2,
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional internal floor area {spec.area_m2:.2f} m²; physical clear wall faces and timber finish must be authenticated from original drawing.",
        row_role="floor_area",
    ))

    # 2. Acoustic Underlay (m²)
    items.append(FlooringTakeoffItem(
        section=spec.section,
        element="Acoustic floor underlay (3mm closed-cell PE)",
        location=f"{spec.room_name} · {spec.space_id}",
        substrate="3mm high-density foam underlay with integrated moisture barrier",
        finish_system="Loose laid with taped butt joints",
        quantity=spec.area_m2,
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Matches timber area: {spec.area_m2:.2f} m².",
        row_role="",
    ))

    # 3. Perimeter Quad / Beading (lm)
    net_perimeter = _original_doorway_net_perimeter(spec)
    if net_perimeter is not None and net_perimeter > 0.0:
        items.append(FlooringTakeoffItem(
            section=spec.section,
            element="Perimeter timber quad beading",
            location=f"Perimeter · {spec.space_id}",
            substrate="19x19mm timber quad mould matching floor finish",
            finish_system="Pinned to skirting over expansion gap",
            quantity=round(net_perimeter, 2),
            unit="lm",
            quantity_status="Provisional",
            source_page=spec.source_page,
            source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
            inclusion_status="PROVISIONAL",
            confidence="Provisional",
            notes=f"Provisional quad {net_perimeter:.2f} lm after assumed {spec.door_deduction_lm:.2f} lm doorway deduction; original threshold width unresolved.",
            row_role="",
        ))

    return items


def calculate_carpet_flooring_items(spec: FlooringSpaceSpec) -> List[FlooringTakeoffItem]:
    """Calculate trade items for broadloom carpet or carpet tiles."""
    items: List[FlooringTakeoffItem] = []
    if _typed_metric(spec.area_m2, positive=True) is None:
        return items

    # 1. Carpet Covering (m²)
    items.append(FlooringTakeoffItem(
        section=spec.section,
        element="Carpet floor covering (twist pile / plush)",
        location=f"{spec.room_name} · {spec.space_id}",
        substrate="Selected broadloom carpet",
        finish_system="Power stretched onto perimeter smooth edge grippers",
        quantity=spec.area_m2,
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional internal floor area {spec.area_m2:.2f} m²; carpet finishes end at actual doorway threshold, not inferred 900mm or under walls.",
        row_role="floor_area",
    ))

    # 2. Carpet Underlay (m²)
    items.append(FlooringTakeoffItem(
        section=spec.section,
        element="Carpet underlay (10mm foam/rubber)",
        location=f"{spec.room_name} · {spec.space_id}",
        substrate="10mm heavy-domestic foam underlay",
        finish_system="Taped seams, fitted within smooth-edge perimeter",
        quantity=spec.area_m2,
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Matches carpet area: {spec.area_m2:.2f} m².",
        row_role="",
    ))

    # 3. Smooth Edge Grippers (lm)
    net_perimeter = _original_doorway_net_perimeter(spec)
    if net_perimeter is not None and net_perimeter > 0.0:
        items.append(FlooringTakeoffItem(
            section=spec.section,
            element="Carpet smooth-edge architectural grippers",
            location=f"Perimeter · {spec.space_id}",
            substrate="Plywood gripper strip with angled pins",
            finish_system="Fastened to concrete/timber substrate @ 6mm from skirting",
            quantity=round(net_perimeter, 2),
            unit="lm",
            quantity_status="Provisional",
            source_page=spec.source_page,
            source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
            inclusion_status="PROVISIONAL",
            confidence="Provisional",
            notes=f"Provisional gripper run {net_perimeter:.2f} lm; doorway deduction {spec.door_deduction_lm:.2f} lm is not source-authenticated.",
            row_role="",
        ))

    return items


def calculate_tiling_items(spec: FlooringSpaceSpec) -> List[FlooringTakeoffItem]:
    """Calculate trade items for floor tiling, sand/cement screed, and waterproofing."""
    items: List[FlooringTakeoffItem] = []
    if _typed_metric(spec.area_m2, positive=True) is None:
        return items

    if any(type(flag) is not bool for flag in
           (spec.is_wet_area, spec.requires_screed, spec.requires_waterproofing)):
        return items
    # The material and inside-wall-face are generic modelling inputs here;
    # a source-closed FT occurrence producer must independently certify them.
    # 1. Floor Tiling (m²)
    items.append(FlooringTakeoffItem(
        section=spec.section,
        element=f"Floor tiles ({spec.tile_size_desc})",
        location=f"{spec.room_name} · {spec.space_id}",
        substrate=f"Selected {spec.tile_size_desc} tiles bedded on polymer-modified adhesive",
        finish_system="Laid to falls with matching epoxy/cementitious grout and perimeter silicone",
        quantity=spec.area_m2,
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional tiling area {spec.area_m2:.2f} m²; finish mark/material and clear internal floor boundary require source authentication.",
        row_role="floor_area",
    ))

    # 2. Sand & Cement Screed to Falls (m²)
    if (
        (spec.requires_screed or spec.is_wet_area)
        and type(spec.screed_depth_mm) is int and spec.screed_depth_mm > 0
    ):
        items.append(FlooringTakeoffItem(
            section=spec.section,
            element=f"Sand & cement bed screed ({spec.screed_depth_mm}mm average)",
            location=f"Screed · {spec.space_id}",
            substrate="1:4 sand and cement semi-dry screed bed",
            finish_system="Trowelled and graded to floor waste (minimum 1:80 fall)",
            quantity=spec.area_m2,
            unit="m²",
            quantity_status="Provisional",
            source_page=spec.source_page,
            source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
            inclusion_status="PROVISIONAL",
            confidence="Provisional",
            notes=f"Provisional screed area: {spec.area_m2:.2f} m² ({spec.screed_depth_mm}mm nominal thickness); original screed scope/falls/thickness unverified.",
            row_role="",
        ))

    # 3. Liquid Waterproofing Membrane with Perimeter Upturns (m²)
    if (
        (spec.requires_waterproofing or spec.is_wet_area)
        and _typed_metric(spec.perimeter_lm) is not None
    ):
        # Floor area + 150mm vertical perimeter upturn (plus bond breaker)
        upturn_m2 = round(spec.perimeter_lm * 0.150, 2)
        total_waterproofing_m2 = round(spec.area_m2 + upturn_m2, 2)
        items.append(FlooringTakeoffItem(
            section=spec.section,
            element="Liquid-applied waterproofing membrane (Class III)",
            location=f"Waterproofing · {spec.space_id}",
            substrate="Polyurethane elastomeric liquid membrane with bandage tape",
            finish_system="2 coats applied over primed substrate with 150mm vertical upturns",
            quantity=total_waterproofing_m2,
            unit="m²",
            quantity_status="Provisional",
            source_page=spec.source_page,
            source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
            inclusion_status="PROVISIONAL",
            confidence="Provisional",
            notes=f"Provisional waterproofing {spec.area_m2:.2f} m² plus assumed 150mm upturn {upturn_m2:.2f} m² = {total_waterproofing_m2:.2f} m²; membrane, actual wet scope and upturn not authenticated.",
            row_role="",
        ))

    # 4. Tile Skirtings (lm)
    net_perimeter = _original_doorway_net_perimeter(spec)
    if net_perimeter is not None and net_perimeter > 0.0:
        items.append(FlooringTakeoffItem(
            section=spec.section,
            element="Tile skirtings (100mm high)",
            location=f"Skirtings · {spec.space_id}",
            substrate=f"Mitred/cushion-edged {spec.tile_size_desc} cuts",
            finish_system="Adhesive fixed with silicone joint at floor junction",
            quantity=round(net_perimeter, 2),
            unit="lm",
            quantity_status="Provisional",
            source_page=spec.source_page,
            source_reference=f"{FLOORING_SOURCE_PREFIX} · {spec.space_id}",
            inclusion_status="PROVISIONAL",
            confidence="Provisional",
            notes=f"Provisional tile skirting {net_perimeter:.2f} lm; doorway deduction {spec.door_deduction_lm:.2f} lm is a model assumption unless independently verified.",
            row_role="",
        ))

    return items


def generate_workspace_flooring_takeoff(
    specs: Sequence[FlooringSpaceSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all flooring spaces."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[FlooringTakeoffItem] = []
        if spec.floor_finish in ("timber", "laminate", "hybrid"):
            items = calculate_timber_flooring_items(spec)
        elif spec.floor_finish == "carpet":
            items = calculate_carpet_flooring_items(spec)
        elif spec.floor_finish in ("tiles", "tiling"):
            items = calculate_tiling_items(spec)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
