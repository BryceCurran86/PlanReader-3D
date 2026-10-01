"""Cross-Trade Geometry Reuse Engine (AG-13).

Proves that PlanReader's canonical building model supports multiple trade quantities
from a single authenticated physical object without duplicate geometric extraction
or hallucinated trade quantities.

Core Principle:
ONE PHYSICAL BUILDING OBJECT = MULTIPLE TRADE QUANTITIES
- Physical Wall -> Masonry, Plaster, Paint, Tile, Insulation, Skirting
- Physical Slab -> Concrete, Formwork, Reinforcement, Vapor Barrier, Finishes
- Physical Roof -> Roofing Cladding, Framing, Insulation, Gutters, Capping
- Physical Space -> Floor Finish, Ceiling Lining, Skirting, Wall Finishes, Fixtures
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus
import pb_takeoff_row_contract as takeoff_contract

SOURCE_PREFIX = "PB Auto Geometry v1.2.19"


@dataclass
class DerivedTradeQuantity:
    """A trade quantity mathematically derived from an authenticated physical building object."""
    trade_scope: str           # e.g. "masonry", "linings", "painting", "tiling", "concrete"
    section: str               # "Internal", "External", "Substructure", "Roof"
    element: str               # e.g. "External brickwork", "Internal plasterboard"
    location: str              # e.g. "North wall (N01)", "Ground Floor Slab"
    substrate: str             # e.g. "Clay brickwork", "Plasterboard 10mm"
    quantity: float            # Measured quantity value
    unit: str                  # "m²", "lm", "No.", "item", "L", "allowance"
    host_object_id: str        # Stable identity of the physical building object
    host_object_type: str      # "WALL", "SLAB", "ROOF", "SPACE"
    derivation_formula: str    # Provenance mathematical formula
    confidence: str = "Documented"
    notes: str = ""
    status: str = "Measured"

    def __post_init__(self) -> None:
        if not math.isfinite(self.quantity) or self.quantity < 0.0:
            raise ValueError(f"Derived trade quantity must be non-negative finite number, got {self.quantity}")
        self.quantity = round(self.quantity, 2)
        if self.unit in ("m2", "sqm", "m^2"):
            self.unit = "m²"
        elif self.unit in ("m3", "cum", "m^3"):
            self.unit = "item"
        elif self.unit in ("ea", "count", "nr", "no"):
            self.unit = "No."


def derive_wall_trade_quantities(
    wall: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Derive multiple trade quantities from a single physical wall object.

    Trades supported:
    - Masonry (brickwork/blockwork core)
    - Linings (plasterboard lining)
    - Painting (internal/external paint coats)
    - Tiling (wet-area tile lining if specified)
    - Insulation (cavity/stud insulation batts)
    - Carpentry (base skirting)
    """
    wall_id = str(wall.get("wall_ref") or wall.get("wall_id") or wall.get("id") or "wall")
    length_m = float(wall.get("length_m") or 0.0)
    height_m = float(wall.get("height_m") or 0.0)
    gross_m2 = float(wall.get("gross_m2") or (length_m * height_m))
    ded_m2 = float(wall.get("opening_deduction_m2") or 0.0)
    net_m2 = float(wall.get("net_m2") or max(0.0, gross_m2 - ded_m2))

    if net_m2 <= 0.0 or length_m <= 0.0:
        return []

    is_ext = bool(wall.get("is_external", True))
    side = str(wall.get("side") or ("External" if is_ext else "Internal"))
    section = "External" if is_ext else "Internal"
    substrate = str(wall.get("substrate") or ("Brick veneer" if is_ext else "Plasterboard stud wall"))

    specs_map = dict(specs or {})
    results: List[DerivedTradeQuantity] = []

    # 1. Structural / Masonry core
    if specs_map.get("include_masonry", is_ext):
        core_sub = specs_map.get("masonry_substrate", substrate)
        results.append(DerivedTradeQuantity(
            trade_scope="masonry",
            section=section,
            element=f"{section} walling / masonry",
            location=f"{side} · {wall_id}",
            substrate=core_sub,
            quantity=net_m2,
            unit="m2",
            host_object_id=wall_id,
            host_object_type="WALL",
            derivation_formula=f"Gross {gross_m2:.2f} m² - Deductions {ded_m2:.2f} m²",
            notes=f"Structural wall core derived from physical wall {wall_id}.",
        ))

    # 2. Linings (Plasterboard)
    if specs_map.get("include_linings", True):
        lining_sub = specs_map.get("lining_substrate", "Plasterboard 10mm")
        results.append(DerivedTradeQuantity(
            trade_scope="linings",
            section="Internal",
            element="Wall lining / plasterboard",
            location=f"{side} (internal face) · {wall_id}",
            substrate=lining_sub,
            quantity=net_m2,
            unit="m2",
            host_object_id=wall_id,
            host_object_type="WALL",
            derivation_formula=f"Net wall area {net_m2:.2f} m²",
            notes=f"Wall lining derived from physical wall {wall_id}.",
        ))

    # 3. Painting
    if specs_map.get("include_painting", True):
        paint_sub = specs_map.get("paint_system", "Acrylic 2-coat")
        results.append(DerivedTradeQuantity(
            trade_scope="painting",
            section=section,
            element=f"{section} wall painting",
            location=f"{side} · {wall_id}",
            substrate=paint_sub,
            quantity=net_m2,
            unit="m2",
            host_object_id=wall_id,
            host_object_type="WALL",
            derivation_formula=f"Net wall face area {net_m2:.2f} m²",
            notes=f"Wall paint finish derived from physical wall {wall_id}.",
        ))

    # 4. Insulation
    if specs_map.get("include_insulation", is_ext):
        insul_sub = specs_map.get("insulation_system", "R2.5 Thermal Batts")
        results.append(DerivedTradeQuantity(
            trade_scope="insulation",
            section=section,
            element="Wall thermal insulation",
            location=f"{side} cavity · {wall_id}",
            substrate=insul_sub,
            quantity=net_m2,
            unit="m2",
            host_object_id=wall_id,
            host_object_type="WALL",
            derivation_formula=f"Net cavity area {net_m2:.2f} m²",
            notes=f"Wall insulation derived from physical wall {wall_id}.",
        ))

    # 5. Carpentry Skirting (Base run)
    if specs_map.get("include_skirting", not is_ext):
        # Base length minus door deductions if present
        door_width = float(specs_map.get("door_width_deduction_m", 0.0))
        net_base_lm = max(0.0, length_m - door_width)
        if net_base_lm > 0.0:
            results.append(DerivedTradeQuantity(
                trade_scope="carpentry",
                section="Internal",
                element="Skirting boards",
                location=f"{side} base · {wall_id}",
                substrate=specs_map.get("skirting_profile", "MDF 67x18mm"),
                quantity=net_base_lm,
                unit="lm",
                host_object_id=wall_id,
                host_object_type="WALL",
                derivation_formula=f"Wall length {length_m:.2f} lm - Door deductions {door_width:.2f} lm",
                notes=f"Skirting run derived from physical wall {wall_id}.",
            ))

    return results


def derive_slab_trade_quantities(
    slab: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Derive multiple trade quantities from a single physical slab object.

    Trades supported:
    - Concrete (slab volume m3)
    - Formwork (edge formwork m2, soffit formwork m2 if suspended)
    - Waterproofing (vapor barrier membrane m2)
    - Reinforcement (reinforcing mesh m2 with lap factor)
    - Finishes (concrete sealer / topping m2)
    """
    slab_id = str(slab.get("floor_id") or slab.get("id") or "slab")
    area_m2 = float(slab.get("area_m2") or slab.get("specified_floor_area_m2") or 0.0)
    thickness_m = float(slab.get("thickness_m") or 0.1)
    perimeter_m = float(slab.get("perimeter_m") or 0.0)
    is_suspended = bool(slab.get("is_suspended", False))

    if area_m2 <= 0.0:
        return []

    results: List[DerivedTradeQuantity] = []
    specs_map = dict(specs or {})

    # 1. Concrete Volume (m3)
    volume_m3 = round(area_m2 * thickness_m, 2)
    results.append(DerivedTradeQuantity(
        trade_scope="concrete",
        section="Substructure" if not is_suspended else "Structure",
        element="Slab concrete",
        location=f"Slab · {slab_id}",
        substrate=specs_map.get("concrete_grade", "25 MPa Concrete"),
        quantity=volume_m3,
        unit="m3",
        host_object_id=slab_id,
        host_object_type="SLAB",
        derivation_formula=f"Area {area_m2:.2f} m² × Thickness {thickness_m:.3f} m",
        notes=f"Concrete volume derived from physical slab {slab_id}.",
    ))

    # 2. Edge Formwork (m2)
    if perimeter_m > 0.0 and specs_map.get("include_formwork", True):
        edge_form_m2 = round(perimeter_m * thickness_m, 2)
        results.append(DerivedTradeQuantity(
            trade_scope="formwork",
            section="Substructure" if not is_suspended else "Structure",
            element="Slab edge formwork",
            location=f"Slab edge · {slab_id}",
            substrate=specs_map.get("edge_formwork_system", "Timber edge boards"),
            quantity=edge_form_m2,
            unit="m2",
            host_object_id=slab_id,
            host_object_type="SLAB",
            derivation_formula=f"Perimeter {perimeter_m:.2f} lm × Thickness {thickness_m:.3f} m",
            notes=f"Edge formwork derived from physical slab {slab_id}.",
        ))

    # 3. Soffit Formwork (m2) - for suspended slabs
    if is_suspended and specs_map.get("include_formwork", True):
        results.append(DerivedTradeQuantity(
            trade_scope="formwork",
            section="Structure",
            element="Slab soffit formwork",
            location=f"Slab underside · {slab_id}",
            substrate=specs_map.get("soffit_formwork_system", "Plywood formwork system"),
            quantity=area_m2,
            unit="m2",
            host_object_id=slab_id,
            host_object_type="SLAB",
            derivation_formula=f"Suspended soffit area {area_m2:.2f} m²",
            notes=f"Soffit formwork derived from physical slab {slab_id}.",
        ))

    # 4. Vapor Barrier (m2) - for ground-bearing slabs
    if not is_suspended and specs_map.get("include_vapor_barrier", True):
        results.append(DerivedTradeQuantity(
            trade_scope="waterproofing",
            section="Substructure",
            element="Vapor barrier membrane",
            location=f"Slab underlay · {slab_id}",
            substrate=specs_map.get("membrane_type", "0.2mm Polythene Damp-Proof Membrane"),
            quantity=area_m2,
            unit="m2",
            host_object_id=slab_id,
            host_object_type="SLAB",
            derivation_formula=f"Ground slab footprint area {area_m2:.2f} m²",
            notes=f"Vapor barrier derived from physical slab {slab_id}.",
        ))

    # 5. Reinforcement Mesh (m2)
    if specs_map.get("include_reinforcement", True):
        lap_factor = float(specs_map.get("mesh_lap_factor", 1.10))
        mesh_area_m2 = round(area_m2 * lap_factor, 2)
        results.append(DerivedTradeQuantity(
            trade_scope="reinforcement",
            section="Substructure" if not is_suspended else "Structure",
            element="Slab reinforcing mesh",
            location=f"Slab bed · {slab_id}",
            substrate=specs_map.get("mesh_grade", "SL72 Steel Mesh"),
            quantity=mesh_area_m2,
            unit="m2",
            host_object_id=slab_id,
            host_object_type="SLAB",
            derivation_formula=f"Plan area {area_m2:.2f} m² × Lap Factor {lap_factor:.2f}",
            notes=f"Reinforcing mesh derived from physical slab {slab_id}.",
        ))

    return results


def derive_roof_trade_quantities(
    roof: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Derive multiple trade quantities from a single physical roof object.

    Trades supported:
    - Roofing Cladding (raked pitch area m2)
    - Roof Framing / Battens (raked roof area m2)
    - Roof Insulation / Sarking (raked area m2)
    - Plumbing Gutters (eave perimeter lm)
    - Roofing Capping / Valleys (ridge/valley lm)
    """
    roof_id = str(roof.get("roof_id") or roof.get("id") or "roof")
    plan_area_m2 = float(roof.get("plan_area_m2") or roof.get("specified_floor_area_m2") or 0.0)
    pitch_deg = float(roof.get("pitch_deg") or 22.5)
    eave_length_lm = float(roof.get("eave_length_lm") or 0.0)
    ridge_length_lm = float(roof.get("ridge_length_lm") or 0.0)

    if plan_area_m2 <= 0.0:
        return []

    # True raked surface area = plan area / cos(pitch) = plan area * sec(pitch)
    pitch_rad = math.radians(pitch_deg)
    sec_pitch = 1.0 / math.cos(pitch_rad) if math.cos(pitch_rad) > 0.0 else 1.0
    raked_area_m2 = round(plan_area_m2 * sec_pitch, 2)

    results: List[DerivedTradeQuantity] = []
    specs_map = dict(specs or {})

    # 1. Roofing Cladding (m2)
    cladding_sub = specs_map.get("roof_cladding", "Colorbond Corrugated Sheet")
    results.append(DerivedTradeQuantity(
        trade_scope="roofing",
        section="Roof",
        element="Roof cladding / coverings",
        location=f"Roof · {roof_id}",
        substrate=cladding_sub,
        quantity=raked_area_m2,
        unit="m2",
        host_object_id=roof_id,
        host_object_type="ROOF",
        derivation_formula=f"Plan {plan_area_m2:.2f} m² × sec({pitch_deg:.1f}°) [{sec_pitch:.3f}]",
        notes=f"Roof cladding derived from physical roof {roof_id}.",
    ))

    # 2. Roof Insulation / Sarking (m2)
    if specs_map.get("include_insulation", True):
        insul_sub = specs_map.get("roof_insulation", "Anticon 60mm Blanket & Foil")
        results.append(DerivedTradeQuantity(
            trade_scope="insulation",
            section="Roof",
            element="Roof thermal sarking / blanket",
            location=f"Roof underlay · {roof_id}",
            substrate=insul_sub,
            quantity=raked_area_m2,
            unit="m2",
            host_object_id=roof_id,
            host_object_type="ROOF",
            derivation_formula=f"Raked roof area {raked_area_m2:.2f} m²",
            notes=f"Roof insulation derived from physical roof {roof_id}.",
        ))

    # 3. Eaves Gutters (lm)
    if eave_length_lm > 0.0 and specs_map.get("include_gutters", True):
        gutter_sub = specs_map.get("gutter_profile", "Quad 115mm Colorbond Gutter")
        results.append(DerivedTradeQuantity(
            trade_scope="plumbing",
            section="Roof",
            element="Eaves gutters",
            location=f"Eaves · {roof_id}",
            substrate=gutter_sub,
            quantity=round(eave_length_lm, 2),
            unit="lm",
            host_object_id=roof_id,
            host_object_type="ROOF",
            derivation_formula=f"Eaves perimeter {eave_length_lm:.2f} lm",
            notes=f"Gutters derived from physical roof {roof_id}.",
        ))

    # 4. Ridge Capping (lm)
    if ridge_length_lm > 0.0 and specs_map.get("include_capping", True):
        capping_sub = specs_map.get("capping_profile", "Roll-top Ridge Capping")
        results.append(DerivedTradeQuantity(
            trade_scope="roofing",
            section="Roof",
            element="Ridge and hip capping",
            location=f"Ridge / Hip · {roof_id}",
            substrate=capping_sub,
            quantity=round(ridge_length_lm, 2),
            unit="lm",
            host_object_id=roof_id,
            host_object_type="ROOF",
            derivation_formula=f"Ridge seam length {ridge_length_lm:.2f} lm",
            notes=f"Capping derived from physical roof {roof_id}.",
        ))

    return results


def derive_space_trade_quantities(
    space: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
    doors: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[DerivedTradeQuantity]:
    """Derive multiple trade quantities from a single physical room/space object.

    Trades supported:
    - Floor Finishes (carpet, tile, timber m2)
    - Ceiling Linings (plasterboard m2)
    - Skirting (perimeter minus door widths lm)
    - Ceiling Cornice (perimeter lm)
    """
    space_id = str(space.get("room_number") or space.get("name") or space.get("id") or "space")
    floor_area_m2 = float(space.get("specified_floor_area_m2") or space.get("area_m2") or 0.0)
    perimeter_m = float(space.get("perimeter_m") or 0.0)

    if floor_area_m2 <= 0.0:
        return []

    results: List[DerivedTradeQuantity] = []
    specs_map = dict(specs or {})

    # 1. Floor Finish (m2)
    floor_finish_sub = specs_map.get("floor_finish", "Direct stick carpet")
    results.append(DerivedTradeQuantity(
        trade_scope="finishes",
        section="Internal",
        element="Floor finishes / covering",
        location=f"Room {space_id} · floor",
        substrate=floor_finish_sub,
        quantity=floor_area_m2,
        unit="m2",
        host_object_id=space_id,
        host_object_type="SPACE",
        derivation_formula=f"Room net floor area {floor_area_m2:.2f} m²",
        notes=f"Floor covering derived from physical room {space_id}.",
    ))

    # 2. Ceiling Lining (m2)
    ceiling_sub = specs_map.get("ceiling_substrate", "10mm Plasterboard Ceiling")
    results.append(DerivedTradeQuantity(
        trade_scope="linings",
        section="Internal",
        element="Ceiling lining / plasterboard",
        location=f"Room {space_id} · ceiling",
        substrate=ceiling_sub,
        quantity=floor_area_m2,
        unit="m2",
        host_object_id=space_id,
        host_object_type="SPACE",
        derivation_formula=f"Room ceiling area {floor_area_m2:.2f} m²",
        notes=f"Ceiling lining derived from physical room {space_id}.",
    ))

    # 3. Skirting (lm) = perimeter minus door openings
    if perimeter_m > 0.0 and specs_map.get("include_skirting", True):
        door_deduction_m = sum(float(d.get("width_m") or 0.9) for d in (doors or []))
        skirting_lm = round(max(0.0, perimeter_m - door_deduction_m), 2)
        skirting_sub = specs_map.get("skirting_profile", "Timber 67mm Skirting")
        results.append(DerivedTradeQuantity(
            trade_scope="carpentry",
            section="Internal",
            element="Internal skirting boards",
            location=f"Room {space_id} · perimeter",
            substrate=skirting_sub,
            quantity=skirting_lm,
            unit="lm",
            host_object_id=space_id,
            host_object_type="SPACE",
            derivation_formula=f"Perimeter {perimeter_m:.2f} lm - Door deductions {door_deduction_m:.2f} lm",
            notes=f"Skirting run derived from physical room {space_id}.",
        ))

    # 4. Cornice (lm)
    if perimeter_m > 0.0 and specs_map.get("include_cornice", True):
        cornice_sub = specs_map.get("cornice_profile", "Cove 90mm Cornice")
        results.append(DerivedTradeQuantity(
            trade_scope="plastering",
            section="Internal",
            element="Ceiling cornice trim",
            location=f"Room {space_id} · perimeter head",
            substrate=cornice_sub,
            quantity=round(perimeter_m, 2),
            unit="lm",
            host_object_id=space_id,
            host_object_type="SPACE",
            derivation_formula=f"Room perimeter {perimeter_m:.2f} lm",
            notes=f"Cornice run derived from physical room {space_id}.",
        ))

    return results


def to_takeoff_rows(
    workspace_id: int,
    quantities: Sequence[DerivedTradeQuantity],
    source_page: str = "1",
    source_prefix: str = SOURCE_PREFIX,
) -> List[Tuple[Any, ...]]:
    """Convert a sequence of DerivedTradeQuantity objects into canonical 21-field takeoff rows."""
    rows: List[Tuple[Any, ...]] = []
    stamp = ""

    for q in quantities:
        # Map to canonical AUTO_ROW_ROLES ("external_wall", "internal_partition", "wall_finish", "floor_area", "")
        if q.host_object_type == "WALL":
            if q.trade_scope == "masonry":
                role = "external_wall" if q.section == "External" else "internal_partition"
            else:
                role = "wall_finish"
        elif q.host_object_type in ("SLAB", "SPACE") and q.trade_scope in ("concrete", "finishes"):
            role = "floor_area"
        else:
            role = ""

        source_ref = f"{source_prefix} · {q.trade_scope}:{q.host_object_id}"
        notes = f"{q.notes} Derivation: {q.derivation_formula}."
        inclusion = "INCLUSION" if role == "floor_area" else "PROVISIONAL"

        row = (
            int(workspace_id),
            q.section,
            q.element,
            q.location,
            q.substrate,
            q.substrate,             # finish_system
            q.quantity,
            q.unit,
            q.status,                # quantity_status
            source_page,
            source_ref,
            inclusion,               # inclusion_status
            2 if "paint" in q.trade_scope else 1,  # coats
            0.0,                     # coverage_m2_per_litre
            0.0,                     # productivity_m2_per_hour
            0.0,                     # rate_per_unit
            q.confidence,
            notes,
            role,                    # row_role
            stamp,
            stamp,
        )
        rows.append(row)

    return rows
