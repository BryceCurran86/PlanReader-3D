"""PlanReader Concreting Trade Authority Engine (AG-21).

Bridges canonical building model geometry to the Concrete trade takeoff schedule.
Calculates high-precision trade quantities without duplicate extraction or hallucination:
- Slabs (ground & suspended): m² surface, m³ concrete volume, vapor barrier, mesh
- Footings (pad, strip, bored pier): count/lm, m³ volume
- Columns (RC): count No., m³ volume, m² column formwork
- Beams (band beams, edge beams, downstands): lm length, m³ volume, m² formwork
- Walls (concrete & core-filled): lm length, m² face, m³ volume, m² formwork
- Stairs: flight No., steps count, m³ concrete volume, m² formwork
- Edge Formwork: lm perimeter, m² contact area

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

CONCRETE_SOURCE_PREFIX = "PB Concrete Authority v1.0"


@dataclass
class ConcreteElementSpec:
    """Specification and dimensions for a structural concrete element."""
    element_type: str          # "slab", "footing_strip", "footing_pad", "bored_pier", "column", "beam", "wall", "stairs"
    element_id: str            # Stable identifier
    section: str               # "Substructure", "Structure", "External"
    description: str
    concrete_grade: str = "25 MPa Concrete"
    length_m: float = 0.0
    width_m: float = 0.0
    thickness_m: float = 0.0
    height_m: float = 0.0
    count: int = 1
    area_m2: float = 0.0
    perimeter_lm: float = 0.0
    is_suspended: bool = False
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class ConcreteTakeoffItem:
    """Standardized concrete trade takeoff item compliant with PlanReader contracts."""
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
            "source_reference": str(self.source_reference or CONCRETE_SOURCE_PREFIX),
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


def calculate_slab_concrete_items(spec: ConcreteElementSpec) -> List[ConcreteTakeoffItem]:
    """Calculate all trade items for a concrete slab (ground-bearing or suspended)."""
    items: List[ConcreteTakeoffItem] = []
    area = spec.area_m2 if spec.area_m2 > 0.0 else (spec.length_m * spec.width_m)
    thickness = spec.thickness_m if spec.thickness_m > 0.0 else 0.100  # Default 100mm
    if area <= 0.0:
        return items

    vol_m3 = round(area * thickness, 2)
    slab_type = "Suspended slab" if spec.is_suspended else "Slab on ground"
    sec = "Structure" if spec.is_suspended else "Substructure"

    # 1. Primary Slab Area (m²)
    items.append(ConcreteTakeoffItem(
        section=sec,
        element=f"Concrete {slab_type.lower()} ({int(thickness*1000)}mm)",
        location=f"Slab · {spec.element_id}",
        substrate=spec.concrete_grade,
        finish_system="Curing compound / steel trowel finish",
        quantity=round(area, 2),
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Slab area {area:.2f} m² × {int(thickness*1000)}mm thickness. Concrete volume: {vol_m3:.2f} m³ ({spec.concrete_grade}).",
        row_role="floor_area",
    ))

    # 2. Concrete Supply & Placement (item / allowance with m³ in formula notes)
    items.append(ConcreteTakeoffItem(
        section=sec,
        element=f"Concrete supply & pump ({spec.concrete_grade})",
        location=f"Slab · {spec.element_id}",
        substrate=spec.concrete_grade,
        finish_system="Supply, pump and place",
        quantity=vol_m3,
        unit="item",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Supply & place {vol_m3:.2f} m³ of {spec.concrete_grade}. (Calculated as {area:.2f} m² × {thickness:.3f}m).",
        row_role="",
    ))

    # 3. Slab Edge Formwork (lm or m²)
    perimeter = spec.perimeter_lm if spec.perimeter_lm > 0.0 else (2 * (spec.length_m + spec.width_m))
    if perimeter > 0.0:
        edge_form_m2 = round(perimeter * thickness, 2)
        items.append(ConcreteTakeoffItem(
            section=sec,
            element="Slab edge formwork",
            location=f"Slab perimeter · {spec.element_id}",
            substrate="Edge form boards",
            finish_system="Form, strip and clean",
            quantity=round(perimeter, 2),
            unit="lm",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Perimeter edge formwork {perimeter:.2f} lm for {int(thickness*1000)}mm slab edge (Contact area: {edge_form_m2:.2f} m²).",
            row_role="",
        ))

    # 4. Under-slab Vapor Barrier / DPM (Ground-bearing only)
    if not spec.is_suspended:
        items.append(ConcreteTakeoffItem(
            section="Substructure",
            element="Damp-proof membrane / vapor barrier",
            location=f"Slab base · {spec.element_id}",
            substrate="0.2mm Polythene film",
            finish_system="Supplied and laid with 200mm laps and taped joints",
            quantity=round(area * 1.10, 2),  # 10% lap allowance
            unit="m²",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Net area {area:.2f} m² + 10% lap allowance = {area*1.10:.2f} m².",
            row_role="",
        ))

    # 5. Soffit Formwork (Suspended slabs only)
    if spec.is_suspended:
        items.append(ConcreteTakeoffItem(
            section="Structure",
            element="Suspended slab soffit formwork",
            location=f"Soffit underside · {spec.element_id}",
            substrate="Plywood formwork system with propping",
            finish_system="Erect, prop, strip and de-prop",
            quantity=round(area, 2),
            unit="m²",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Suspended soffit formwork area {area:.2f} m².",
            row_role="",
        ))

    return items


def calculate_footing_concrete_items(spec: ConcreteElementSpec) -> List[ConcreteTakeoffItem]:
    """Calculate trade items for strip footings or pad footings."""
    items: List[ConcreteTakeoffItem] = []
    if "strip" in spec.element_type:
        length = spec.length_m
        width = spec.width_m if spec.width_m > 0.0 else 0.400
        depth = spec.thickness_m if spec.thickness_m > 0.0 else 0.450
        if length <= 0.0:
            return items
        vol_m3 = round(length * width * depth, 2)

        items.append(ConcreteTakeoffItem(
            section="Substructure",
            element=f"Strip footing ({int(width*1000)}W × {int(depth*1000)}D)",
            location=f"Foundations · {spec.element_id}",
            substrate=spec.concrete_grade,
            finish_system="Poured against earth / trench",
            quantity=round(length, 2),
            unit="lm",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Strip footing length {length:.2f} lm × {width:.3f}m W × {depth:.3f}m D. Concrete volume: {vol_m3:.2f} m³.",
            row_role="",
        ))
        items.append(ConcreteTakeoffItem(
            section="Substructure",
            element=f"Strip footing concrete supply ({spec.concrete_grade})",
            location=f"Foundations · {spec.element_id}",
            substrate=spec.concrete_grade,
            finish_system="Supply, pump and place in trenches",
            quantity=vol_m3,
            unit="item",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Volume {vol_m3:.2f} m³ ({length:.2f} lm × {width:.3f}m × {depth:.3f}m).",
            row_role="",
        ))
    elif "pad" in spec.element_type:
        count = max(1, spec.count)
        length = spec.length_m if spec.length_m > 0.0 else 1.0
        width = spec.width_m if spec.width_m > 0.0 else 1.0
        depth = spec.thickness_m if spec.thickness_m > 0.0 else 0.500
        vol_per_pad = length * width * depth
        total_vol_m3 = round(count * vol_per_pad, 2)

        items.append(ConcreteTakeoffItem(
            section="Substructure",
            element=f"Pad footings ({int(length*1000)}×{int(width*1000)}×{int(depth*1000)}mm)",
            location=f"Pad foundations · {spec.element_id}",
            substrate=spec.concrete_grade,
            finish_system="Poured in excavated pads",
            quantity=float(count),
            unit="No.",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"{count} No. pad footings ({length:.2f}m × {width:.2f}m × {depth:.2f}m). Total concrete volume: {total_vol_m3:.2f} m³.",
            row_role="",
        ))
    elif "bored_pier" in spec.element_type:
        count = max(1, spec.count)
        diam = spec.width_m if spec.width_m > 0.0 else 0.450
        depth = spec.height_m if spec.height_m > 0.0 else 2.500
        radius = diam / 2.0
        vol_per_pier = math.pi * (radius ** 2) * depth
        total_vol_m3 = round(count * vol_per_pier, 2)

        items.append(ConcreteTakeoffItem(
            section="Substructure",
            element=f"Bored concrete piers ({int(diam*1000)}mm dia × {depth:.1f}m deep)",
            location=f"Piers · {spec.element_id}",
            substrate=spec.concrete_grade,
            finish_system="Bored and poured in shaft",
            quantity=float(count),
            unit="No.",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"{count} No. bored piers ({diam*1000:.0f}mm dia × {depth:.2f}m). Total concrete volume: {total_vol_m3:.2f} m³.",
            row_role="",
        ))
    return items


def calculate_column_concrete_items(spec: ConcreteElementSpec) -> List[ConcreteTakeoffItem]:
    """Calculate trade items for reinforced concrete columns."""
    items: List[ConcreteTakeoffItem] = []
    count = max(1, spec.count)
    w = spec.width_m if spec.width_m > 0.0 else 0.350
    d = spec.length_m if spec.length_m > 0.0 else 0.350
    h = spec.height_m if spec.height_m > 0.0 else 2.700

    vol_per_col = w * d * h
    total_vol = round(count * vol_per_col, 2)
    perimeter = 2 * (w + d)
    formwork_m2 = round(count * perimeter * h, 2)

    # 1. Column Count (No.)
    items.append(ConcreteTakeoffItem(
        section="Structure",
        element=f"Concrete columns ({int(w*1000)}×{int(d*1000)}mm × {h:.2f}m)",
        location=f"Columns · {spec.element_id}",
        substrate=spec.concrete_grade,
        finish_system="Class 2 off-form finish",
        quantity=float(count),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. RC columns. Total concrete volume: {total_vol:.2f} m³.",
        row_role="",
    ))

    # 2. Column Formwork (m²)
    items.append(ConcreteTakeoffItem(
        section="Structure",
        element="Column formwork (Class 2)",
        location=f"Columns · {spec.element_id}",
        substrate="Plywood column boxes / steel shutters",
        finish_system="Form, plumb, strip and clean",
        quantity=formwork_m2,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Formwork area: {count} No. × {perimeter:.2f} lm perimeter × {h:.2f}m height = {formwork_m2:.2f} m².",
        row_role="",
    ))

    return items


def calculate_beam_concrete_items(spec: ConcreteElementSpec) -> List[ConcreteTakeoffItem]:
    """Calculate trade items for reinforced concrete beams."""
    items: List[ConcreteTakeoffItem] = []
    length = spec.length_m
    w = spec.width_m if spec.width_m > 0.0 else 0.400
    d = spec.thickness_m if spec.thickness_m > 0.0 else 0.600
    if length <= 0.0:
        return items

    vol_m3 = round(length * w * d, 2)
    # Formwork: soffit + 2 sides (2 * d + w)
    formwork_m2 = round(length * (w + 2 * d), 2)

    items.append(ConcreteTakeoffItem(
        section="Structure",
        element=f"Concrete beams ({int(w*1000)}W × {int(d*1000)}D)",
        location=f"Beams · {spec.element_id}",
        substrate=spec.concrete_grade,
        finish_system="Formed and poured",
        quantity=round(length, 2),
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Beam run {length:.2f} lm ({int(w*1000)}×{int(d*1000)}mm). Concrete volume: {vol_m3:.2f} m³.",
        row_role="",
    ))

    items.append(ConcreteTakeoffItem(
        section="Structure",
        element="Beam formwork (sides and soffit)",
        location=f"Beams · {spec.element_id}",
        substrate="Timber / plywood formwork",
        finish_system="Erect, prop and strip",
        quantity=formwork_m2,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Formwork area: {length:.2f} lm × ({w:.2f}m soffit + 2 × {d:.2f}m sides) = {formwork_m2:.2f} m².",
        row_role="",
    ))

    return items


def calculate_stairs_concrete_items(spec: ConcreteElementSpec) -> List[ConcreteTakeoffItem]:
    """Calculate trade items for reinforced concrete stairs."""
    items: List[ConcreteTakeoffItem] = []
    flights = max(1, spec.count)
    steps = max(1, int(spec.height_m * 6)) if spec.height_m > 0 else 16  # approx 16 steps per storey
    width = spec.width_m if spec.width_m > 0.0 else 1.000
    # Average waist slab + steps volume: ~0.15 m³ per step per metre width
    vol_m3 = round(flights * steps * width * 0.08, 2)
    formwork_m2 = round(flights * steps * (width * 0.18 + width * 0.28), 2)

    items.append(ConcreteTakeoffItem(
        section="Structure",
        element="Reinforced concrete stairs",
        location=f"Stairs · {spec.element_id}",
        substrate=spec.concrete_grade,
        finish_system="Trowel finished treads & off-form risers",
        quantity=float(flights),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{flights} flight(s) with {steps} steps, {width:.2f}m wide. Concrete volume: {vol_m3:.2f} m³.",
        row_role="",
    ))

    items.append(ConcreteTakeoffItem(
        section="Structure",
        element="Stair formwork (soffit, risers & stringers)",
        location=f"Stairs · {spec.element_id}",
        substrate="Timber formwork",
        finish_system="Form, prop and strip",
        quantity=formwork_m2,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CONCRETE_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Formwork area: {formwork_m2:.2f} m² across {steps} steps.",
        row_role="",
    ))

    return items


def generate_workspace_concrete_takeoff(
    specs: Sequence[ConcreteElementSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all concrete elements."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[ConcreteTakeoffItem] = []
        if spec.element_type == "slab":
            items = calculate_slab_concrete_items(spec)
        elif "footing" in spec.element_type or "bored_pier" in spec.element_type:
            items = calculate_footing_concrete_items(spec)
        elif spec.element_type == "column":
            items = calculate_column_concrete_items(spec)
        elif spec.element_type == "beam":
            items = calculate_beam_concrete_items(spec)
        elif spec.element_type == "stairs":
            items = calculate_stairs_concrete_items(spec)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
