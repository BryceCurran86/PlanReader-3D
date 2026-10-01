"""PlanReader Structural Steel Trade Authority Engine (AG-24).

Bridges canonical building model geometry to the specialist Structural Steel trade takeoff schedule.
Calculates high-precision steel trade quantities without duplicate extraction or hallucination:
- Primary Structural Framing: Beams (UB/WB), Columns (UC/SHS), Rafters, Trimmers (lm & tonnes)
- Secondary Steelwork: Purlins (C/Z sections), Girts, Bridging systems (lm & No.)
- Bracing: Roof cross-bracing, wall diagonal bracing, fly braces (lm & No.)
- Connection & Fitting Allowances: Base plates, cleats, bolts, splices (tonnes via standard industry %)
- Surface Protection & Coatings: Shop primer, Hot-Dip Galvanizing (HDG), Intumescent fire coatings (m²)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

STEEL_SOURCE_PREFIX = "PB Structural Steel Authority v1.0"
DEFAULT_CONNECTION_ALLOWANCE_PCT = 10.0  # 10% connection & fittings allowance on primary steel


@dataclass
class SteelMemberSpec:
    """Specification and dimensions for a structural steel member."""
    element_type: str          # "beam", "column", "rafter", "purlin", "girt", "bracing", "lintel"
    element_id: str            # Stable identifier (e.g. "B_310UB40_01", "C_200UC46_01")
    section_mark: str          # e.g. "310UB40.4", "200UC46.2", "100x100x4.0 SHS", "200PFC", "C15015"
    description: str
    section: str = "Structure" # "Structure", "Roof", "Substructure"
    length_m: float = 0.0
    count: int = 1
    mass_kg_per_m: float = 0.0 # kg per linear metre
    surface_area_m2_per_m: float = 0.0  # m² surface area per linear metre for coating
    coating: str = "Shop primed (zinc phosphate)" # "Shop primed", "Hot-dip galvanized (HDG)", "Intumescent 60min"
    grade: str = "Grade 300 / 350 Steel"
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class SteelTakeoffItem:
    """Standardized structural steel trade takeoff item compliant with PlanReader contracts."""
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
            "source_page": str(self.source_page or "Structural S201"),
            "source_reference": str(self.source_reference or STEEL_SOURCE_PREFIX),
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


def calculate_primary_member_items(spec: SteelMemberSpec) -> List[SteelTakeoffItem]:
    """Calculate trade takeoff items for primary structural steel members (beams, columns, rafters)."""
    items: List[SteelTakeoffItem] = []
    count = max(1, spec.count)
    total_length_m = round(count * spec.length_m, 2)
    if total_length_m <= 0.0:
        return items

    total_mass_kg = round(total_length_m * spec.mass_kg_per_m, 2)
    total_mass_tonnes = round(total_mass_kg / 1000.0, 3)

    # 1. Primary Member Run (lm)
    items.append(SteelTakeoffItem(
        section=spec.section,
        element=f"Structural steel {spec.element_type} ({spec.section_mark})",
        location=f"{spec.element_type.title()} · {spec.element_id}",
        substrate=f"{spec.section_mark} ({spec.grade})",
        finish_system="Supply, fabricate and erect",
        quantity=total_length_m,
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{STEEL_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. {spec.section_mark} × {spec.length_m:.2f}m. Total mass: {total_mass_tonnes:.3f} t ({total_mass_kg:.1f} kg @ {spec.mass_kg_per_m:.1f} kg/m).",
        row_role="",
    ))

    # 2. Fabricated Steel Weight (tonnes represented as item)
    items.append(SteelTakeoffItem(
        section=spec.section,
        element=f"Steel fabrication & erection tonnage ({spec.section_mark})",
        location=f"{spec.element_type.title()} tonnage · {spec.element_id}",
        substrate=f"{spec.section_mark} structural steel",
        finish_system="Shop fabrication, delivery to site and crane erection",
        quantity=total_mass_tonnes,
        unit="item",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{STEEL_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Tonnage: {total_mass_tonnes:.3f} tonnes ({total_mass_kg:.1f} kg). Derived as {total_length_m:.2f} lm × {spec.mass_kg_per_m:.2f} kg/m.",
        row_role="",
    ))

    # 3. Surface Protective Treatment / Coating (m²)
    if spec.surface_area_m2_per_m > 0.0:
        total_coating_m2 = round(total_length_m * spec.surface_area_m2_per_m, 2)
        items.append(SteelTakeoffItem(
            section=spec.section,
            element=f"Steel surface coating: {spec.coating}",
            location=f"Coating · {spec.element_id}",
            substrate=f"{spec.section_mark} exposed steel surface",
            finish_system=spec.coating,
            quantity=total_coating_m2,
            unit="m²",
            quantity_status="Measured",
            source_page=spec.source_page,
            source_reference=f"{STEEL_SOURCE_PREFIX} · {spec.element_id}",
            inclusion_status="INCLUSION",
            confidence="Verified",
            notes=f"Coating surface area: {total_coating_m2:.2f} m² ({total_length_m:.2f} lm × {spec.surface_area_m2_per_m:.2f} m²/m).",
            row_role="",
        ))

    return items


def calculate_purlin_and_girt_items(spec: SteelMemberSpec) -> List[SteelTakeoffItem]:
    """Calculate trade takeoff items for secondary cold-formed steel purlins and girts."""
    items: List[SteelTakeoffItem] = []
    count = max(1, spec.count)
    total_length_m = round(count * spec.length_m, 2)
    if total_length_m <= 0.0:
        return items

    total_mass_kg = round(total_length_m * spec.mass_kg_per_m, 2)
    total_tonnes = round(total_mass_kg / 1000.0, 3)

    items.append(SteelTakeoffItem(
        section=spec.section or "Roof",
        element=f"Cold-formed {spec.element_type} ({spec.section_mark})",
        location=f"{spec.element_type.title()} · {spec.element_id}",
        substrate=f"Galvanized high-tensile steel {spec.section_mark}",
        finish_system="Supply and fix to structural rafters with purlin cleats and bolts",
        quantity=total_length_m,
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{STEEL_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} runs of {spec.section_mark} = {total_length_m:.2f} lm. Total mass: {total_tonnes:.3f} t ({total_mass_kg:.1f} kg).",
        row_role="",
    ))

    return items


def calculate_bracing_items(spec: SteelMemberSpec) -> List[SteelTakeoffItem]:
    """Calculate trade takeoff items for structural bracing systems."""
    items: List[SteelTakeoffItem] = []
    count = max(1, spec.count)
    total_length = round(count * spec.length_m, 2)

    items.append(SteelTakeoffItem(
        section=spec.section,
        element=f"Structural cross-bracing ({spec.section_mark})",
        location=f"Bracing · {spec.element_id}",
        substrate=f"{spec.section_mark} with turnbuckles / cleat plates",
        finish_system="Install, tension and lock off",
        quantity=float(count) if spec.length_m <= 0.0 else total_length,
        unit="No." if spec.length_m <= 0.0 else "lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{STEEL_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. bracing bays ({spec.section_mark}).",
        row_role="",
    ))

    return items


def calculate_connection_fittings_allowance(
    primary_specs: Sequence[SteelMemberSpec],
    workspace_id: int,
    now_stamp: str,
    allowance_pct: float = DEFAULT_CONNECTION_ALLOWANCE_PCT,
) -> Optional[Dict[str, Any]]:
    """Calculate standard connection allowance item based on total primary steel tonnage."""
    total_primary_tonnes = 0.0
    for spec in primary_specs:
        if spec.element_type in ("beam", "column", "rafter", "lintel"):
            length = spec.length_m * max(1, spec.count)
            mass_kg = length * spec.mass_kg_per_m
            total_primary_tonnes += mass_kg / 1000.0

    if total_primary_tonnes <= 0.0:
        return None

    conn_tonnes = round(total_primary_tonnes * (allowance_pct / 100.0), 3)
    item = SteelTakeoffItem(
        section="Structure",
        element="Connections, base plates, cleats and fittings allowance",
        location="Structural connections",
        substrate="Grade 250/350 steel plates, stiffeners & grade 8.8 bolts",
        finish_system="Fabricate cleats, base plates and supply high-strength structural bolts",
        quantity=conn_tonnes,
        unit="item",
        quantity_status="Estimated",
        source_page="Structural Details",
        source_reference=STEEL_SOURCE_PREFIX,
        inclusion_status="INCLUSION",
        confidence="High",
        notes=f"{allowance_pct:.1f}% connection allowance on {total_primary_tonnes:.3f} t primary steel = {conn_tonnes:.3f} tonnes.",
        row_role="",
    )
    return item.to_core_row(workspace_id, now_stamp)


def generate_workspace_steel_takeoff(
    specs: Sequence[SteelMemberSpec],
    workspace_id: int,
    now_stamp: str,
    include_connections: bool = True,
    connection_pct: float = DEFAULT_CONNECTION_ALLOWANCE_PCT,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all structural steel elements."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[SteelTakeoffItem] = []
        if spec.element_type in ("beam", "column", "rafter", "lintel"):
            items = calculate_primary_member_items(spec)
        elif spec.element_type in ("purlin", "girt"):
            items = calculate_purlin_and_girt_items(spec)
        elif spec.element_type == "bracing":
            items = calculate_bracing_items(spec)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    if include_connections:
        conn_row = calculate_connection_fittings_allowance(specs, workspace_id, now_stamp, connection_pct)
        if conn_row:
            all_rows.append(conn_row)

    return all_rows
