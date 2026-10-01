"""PlanReader Formwork Trade Authority Engine (AG-22).

Bridges canonical building model geometry to the specialist Formwork trade takeoff schedule.
Calculates high-precision formwork trade quantities without duplicate extraction or hallucination:
- Soffit Formwork: Flat suspended slabs, drop panels, cantilever balconies (m²)
- Edge Formwork: Slab perimeter edges by depth band, internal slab steps (lm & m²)
- Wall Formwork: Double-faced in-situ RC walls, single-faced rock pours, opening blockouts (m² & lm)
- Column Formwork: Rectangular/square boxes, circular columns, high-propping allowances (m² & No.)
- Beam Formwork: Downstand beams, band beams, edge beams (sides & soffits) (m² & lm)
- Stepdowns & Penetrations: Wet-area/balcony rebates, pipe sleeves, service core blockouts (lm & No.)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

FORMWORK_SOURCE_PREFIX = "PB Formwork Authority v1.0"


@dataclass
class FormworkElementSpec:
    """Specification and dimensions for a structural concrete element requiring formwork."""
    element_type: str          # "soffit", "edge", "wall", "column", "beam", "stepdown", "penetration"
    element_id: str            # Stable identifier
    section: str               # "Substructure", "Structure", "External"
    description: str
    length_m: float = 0.0
    width_m: float = 0.0
    height_m: float = 0.0
    depth_m: float = 0.0
    area_m2: float = 0.0
    perimeter_lm: float = 0.0
    count: int = 1
    is_circular: bool = False
    is_single_faced: bool = False
    is_cantilever: bool = False
    propping_height_m: float = 2.70
    openings: List[Dict[str, float]] = field(default_factory=list)  # [{"width": 1.2, "height": 2.1, "area": 2.52}]
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class FormworkTakeoffItem:
    """Standardized formwork trade takeoff item compliant with PlanReader contracts."""
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
            "source_page": str(self.source_page or "Structural S101"),
            "source_reference": str(self.source_reference or FORMWORK_SOURCE_PREFIX),
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


def calculate_soffit_formwork_items(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork items for suspended slab soffits, drop panels, and cantilevers."""
    items: List[FormworkTakeoffItem] = []
    area = spec.area_m2 if spec.area_m2 > 0.0 else (spec.length_m * spec.width_m)
    if area <= 0.0:
        return items

    # Standard flat soffit formwork
    propping_desc = f"propping up to {spec.propping_height_m:.1f}m"
    if spec.propping_height_m > 3.6:
        propping_desc = f"high propping ({spec.propping_height_m:.1f}m)"

    element_name = "Suspended slab soffit formwork (Class 3)"
    if spec.is_cantilever:
        element_name = "Cantilever balcony soffit formwork (with edge screens)"

    items.append(FormworkTakeoffItem(
        section=spec.section or "Structure",
        element=element_name,
        location=f"Soffit · {spec.element_id}",
        substrate="Plywood / aluminium table form system",
        finish_system=f"Erect, {propping_desc}, strip and de-prop",
        quantity=round(area, 2),
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Soffit contact area {area:.2f} m² with {propping_desc}.",
        row_role="",
    ))

    # Drop panels / column capitals if specified
    if spec.depth_m > 0.0 and spec.count > 0:
        panel_area = spec.count * (spec.length_m * spec.width_m)
        panel_edge = spec.count * 2 * (spec.length_m + spec.width_m)
        items.append(FormworkTakeoffItem(
            section=spec.section or "Structure",
            element=f"Drop panel formwork ({int(spec.depth_m*1000)}mm drop)",
            location=f"Drop panels · {spec.element_id}",
            substrate="Plywood formwork",
            finish_system="Form stepped down drop panel",
            quantity=round(panel_area + (panel_edge * spec.depth_m), 2),
            unit="m²",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"{spec.count} No. drop panels: {panel_area:.2f} m² base + {panel_edge * spec.depth_m:.2f} m² edge drops.",
            row_role="",
        ))

    return items


def calculate_edge_formwork_items(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork items for slab edges and perimeter boards."""
    items: List[FormworkTakeoffItem] = []
    length = spec.perimeter_lm if spec.perimeter_lm > 0.0 else spec.length_m
    depth = spec.depth_m if spec.depth_m > 0.0 else (spec.height_m or 0.150)
    if length <= 0.0:
        return items

    contact_area = round(length * depth, 2)
    depth_band = f"depth <= {int(depth*1000)}mm" if depth <= 0.300 else f"depth {int(depth*1000)}mm"

    # Edge formwork measured in lm (with m² contact area in notes)
    items.append(FormworkTakeoffItem(
        section=spec.section or "Structure",
        element=f"Slab edge formwork ({depth_band})",
        location=f"Slab perimeter · {spec.element_id}",
        substrate="Timber edge boards / steel form liners",
        finish_system="Form, brace, strip and clean",
        quantity=round(length, 2),
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Perimeter length {length:.2f} lm × {int(depth*1000)}mm edge height (Contact area: {contact_area:.2f} m²).",
        row_role="",
    ))

    return items


def calculate_wall_formwork_items(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork items for concrete walls (double or single faced) and opening blockouts."""
    items: List[FormworkTakeoffItem] = []
    length = spec.length_m
    height = spec.height_m if spec.height_m > 0.0 else 2.70
    if length <= 0.0 or height <= 0.0:
        return items

    gross_face = length * height
    # Deduct openings
    total_ded = sum(float(op.get("area") or (float(op.get("width", 0)) * float(op.get("height", 0)))) for op in spec.openings)
    net_face = max(0.0, gross_face - total_ded)

    if spec.is_single_faced:
        total_form_area = round(net_face, 2)
        desc = "Single-faced wall formwork (poured against shoring/earth)"
    else:
        # Double-faced wall formwork (both sides)
        total_form_area = round(net_face * 2.0, 2)
        desc = "Double-faced concrete wall formwork (Class 2)"

    items.append(FormworkTakeoffItem(
        section=spec.section or "Structure",
        element=desc,
        location=f"Wall · {spec.element_id}",
        substrate="Steel frame / plywood wall panels with tie rods",
        finish_system="Erect, tie, align, strip and plug tie holes",
        quantity=total_form_area,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Wall length {length:.2f} lm × {height:.2f}m height. Net face: {net_face:.2f} m² (Deductions: {total_ded:.2f} m²). Total formwork contact: {total_form_area:.2f} m².",
        row_role="",
    ))

    # Opening blockouts (edge forms around windows and doors)
    for i, op in enumerate(spec.openings):
        op_w = float(op.get("width") or 0.0)
        op_h = float(op.get("height") or 0.0)
        thick = spec.depth_m if spec.depth_m > 0.0 else 0.200  # Default 200mm wall
        if op_w > 0.0 and op_h > 0.0:
            blockout_perim = 2 * (op_w + op_h)
            items.append(FormworkTakeoffItem(
                section=spec.section or "Structure",
                element=f"Opening blockout formwork ({int(op_w*1000)}×{int(op_h*1000)}mm)",
                location=f"Wall blockout #{i+1} · {spec.element_id}",
                substrate="Timber boxout frame",
                finish_system="Construct internal boxout, brace and strip",
                quantity=round(blockout_perim, 2),
                unit="lm",
                quantity_status="Measured",
                source_page=spec.source_page,
                source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
                inclusion_status="INCLUSION",
                confidence="Verified",
                notes=f"Boxout perimeter: {blockout_perim:.2f} lm in {int(thick*1000)}mm thick wall.",
                row_role="",
            ))

    return items


def calculate_column_formwork_items(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork items for reinforced concrete columns."""
    items: List[FormworkTakeoffItem] = []
    count = max(1, spec.count)
    height = spec.height_m if spec.height_m > 0.0 else 2.70
    w = spec.width_m if spec.width_m > 0.0 else 0.400
    d = spec.depth_m if spec.depth_m > 0.0 else (spec.length_m or w)

    if spec.is_circular:
        diameter = w
        perim = math.pi * diameter
        total_form_area = round(count * perim * height, 2)
        element_name = f"Circular column formwork ({int(diameter*1000)}mm dia)"
        substrate = "Rigid circular tube forms / split steel shutters"
    else:
        perim = 2 * (w + d)
        total_form_area = round(count * perim * height, 2)
        element_name = f"Rectangular column formwork ({int(w*1000)}×{int(d*1000)}mm)"
        substrate="Plywood column boxes with steel column clamps"

    items.append(FormworkTakeoffItem(
        section=spec.section or "Structure",
        element=element_name,
        location=f"Columns · {spec.element_id}",
        substrate=substrate,
        finish_system="Erect, plumb, clamp, strip and clean",
        quantity=total_form_area,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. columns × {perim:.2f} lm perimeter × {height:.2f}m height = {total_form_area:.2f} m² formwork area.",
        row_role="",
    ))

    # High propping allowance for columns exceeding 3.6m
    if height > 3.6:
        items.append(FormworkTakeoffItem(
            section=spec.section or "Structure",
            element="Extra-over for high column propping (> 3.6m)",
            location=f"Columns · {spec.element_id}",
            substrate="Heavy duty propping & bracing",
            finish_system="Additional bracing and multi-tier access",
            quantity=float(count),
            unit="No.",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Height allowance for {count} No. columns at {height:.2f}m.",
            row_role="",
        ))

    return items


def calculate_beam_formwork_items(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork items for concrete beams (sides and soffit)."""
    items: List[FormworkTakeoffItem] = []
    length = spec.length_m
    w = spec.width_m if spec.width_m > 0.0 else 0.400
    d = spec.depth_m if spec.depth_m > 0.0 else 0.600
    if length <= 0.0:
        return items

    # Formwork contact area: beam soffit + 2 vertical sides
    soffit_area = length * w
    sides_area = length * (2 * d)
    total_form_area = round(soffit_area + sides_area, 2)

    items.append(FormworkTakeoffItem(
        section=spec.section or "Structure",
        element=f"Beam formwork sides & soffit ({int(w*1000)}W × {int(d*1000)}D)",
        location=f"Beams · {spec.element_id}",
        substrate="Timber / plywood beam moulds with bottom falsework",
        finish_system="Erect beam base and side forms, prop, strip",
        quantity=total_form_area,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Beam run {length:.2f} lm: Soffit {soffit_area:.2f} m² + Sides {sides_area:.2f} m² = Total {total_form_area:.2f} m².",
        row_role="",
    ))

    return items


def calculate_stepdowns_and_penetrations(spec: FormworkElementSpec) -> List[FormworkTakeoffItem]:
    """Calculate formwork for slab stepdowns, shower rebates, and service penetrations."""
    items: List[FormworkTakeoffItem] = []
    if spec.element_type == "stepdown":
        length = spec.length_m
        drop = spec.depth_m if spec.depth_m > 0.0 else 0.050  # Default 50mm stepdown
        if length > 0.0:
            items.append(FormworkTakeoffItem(
                section=spec.section or "Structure",
                element=f"Slab stepdown rebate formwork ({int(drop*1000)}mm drop)",
                location=f"Stepdown · {spec.element_id}",
                substrate="Timber rebate former / angle rebate iron",
                finish_system="Fix rebate former to soffit/deck, strip",
                quantity=round(length, 2),
                unit="lm",
                quantity_status="Measured",
                source_page=spec.source_page,
                source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
                inclusion_status="INCLUSION",
                confidence="Verified",
                notes=f"Rebate length: {length:.2f} lm for {int(drop*1000)}mm stepdown (Balcony / wet-area transition).",
                row_role="",
            ))
    elif spec.element_type == "penetration":
        count = max(1, spec.count)
        size_desc = f"{int(spec.width_m*1000)}mm dia" if spec.is_circular else f"{int(spec.width_m*1000)}×{int(spec.depth_m*1000)}mm"
        items.append(FormworkTakeoffItem(
            section=spec.section or "Structure",
            element=f"Slab penetration blockout ({size_desc})",
            location=f"Slab penetrations · {spec.element_id}",
            substrate="PVC pipe sleeve / timber boxout",
            finish_system="Fasten blockout to deck, strip after pour",
            quantity=float(count),
            unit="No.",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{FORMWORK_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"{count} No. service penetrations ({size_desc}).",
            row_role="",
        ))

    return items


def generate_workspace_formwork_takeoff(
    specs: Sequence[FormworkElementSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all formwork elements."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[FormworkTakeoffItem] = []
        if spec.element_type == "soffit":
            items = calculate_soffit_formwork_items(spec)
        elif spec.element_type == "edge":
            items = calculate_edge_formwork_items(spec)
        elif spec.element_type == "wall":
            items = calculate_wall_formwork_items(spec)
        elif spec.element_type == "column":
            items = calculate_column_formwork_items(spec)
        elif spec.element_type == "beam":
            items = calculate_beam_formwork_items(spec)
        elif spec.element_type in ("stepdown", "penetration"):
            items = calculate_stepdowns_and_penetrations(spec)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
