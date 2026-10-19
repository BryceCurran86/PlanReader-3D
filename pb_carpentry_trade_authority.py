"""PlanReader Carpentry Trade Authority Engine (AG-27).

Bridges canonical building model geometry to the specialist Carpentry & Timber Framing trade takeoff schedule.
Calculates high-precision trade quantities without duplicate extraction or hallucination:
- Wall Framing: Top & bottom plates (lm), studs @ 450/600mm (lm & No.), noggings (lm), frame area (m²)
- Subfloor Framing: Timber bearers & joists (lm), particleboard / plywood structural subfloor (m²)
- Roof Framing: Prefabricated trusses (No.), roof battens (lm), ceiling battens (lm)
- External Cladding & Trims: Lightweight weatherboard/FC cladding (m²), eaves linings (m²), fascia (lm)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

CARPENTRY_SOURCE_PREFIX = "PB Carpentry Authority v1.0"


@dataclass
class CarpentryElementSpec:
    """Specification and dimensions for a structural timber or carpentry element."""
    element_type: str          # "wall_frame", "subfloor", "roof_frame", "cladding", "eaves"
    element_id: str            # Stable identifier (e.g. "FRAME_EXT_01", "ROOF_TRUSS_01")
    description: str
    section: str = "Structure" # "Structure", "External", "Internal", "Roof"
    length_m: float = 0.0
    height_m: float = 0.0
    width_m: float = 0.0
    area_m2: float = 0.0
    perimeter_lm: float = 0.0
    timber_grade: str = "MGP10 Kiln-Dried Pine"
    stud_spacing_mm: int = 450
    overhang_width_m: float = 0.60  # Eave overhang width
    openings: List[Dict[str, float]] = field(default_factory=list)
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class CarpentryTakeoffItem:
    """Standardized carpentry trade takeoff item compliant with PlanReader contracts."""
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
            "source_page": str(self.source_page or "Carpentry Plans"),
            "source_reference": str(self.source_reference or CARPENTRY_SOURCE_PREFIX),
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


def calculate_wall_framing_items(spec: CarpentryElementSpec) -> List[CarpentryTakeoffItem]:
    """Calculate trade items for timber stud wall framing: plates, studs, noggings, and frame area."""
    items: List[CarpentryTakeoffItem] = []
    length = spec.length_m
    height = spec.height_m
    if length <= 0.0 or height <= 0.0:
        return items

    gross_area = round(length * height, 2)
    spacing_m = (spec.stud_spacing_mm or 450) / 1000.0

    # 1. Total Wall Frame Area (m²)
    items.append(CarpentryTakeoffItem(
        section=spec.section,
        element=f"Timber wall framing (90x45 {spec.timber_grade})",
        location=f"Wall frame · {spec.element_id}",
        substrate=f"90x45mm {spec.timber_grade} framing",
        finish_system=f"Prefabricated/stick-built frame with studs @ {spec.stud_spacing_mm}mm centres",
        quantity=gross_area,
        unit="m²",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Gross framing elevation: {length:.2f} lm × {height:.2f}m = {gross_area:.2f} m².",
        row_role="external_wall" if spec.section == "External" else "internal_partition",
    ))

    # 2. Wall Plates: 1 bottom plate + 2 top plates = 3 x length (lm)
    plates_lm = round(length * 3.0, 2)
    items.append(CarpentryTakeoffItem(
        section=spec.section,
        element="Wall plates (bottom plate & double top plate)",
        location=f"Plates · {spec.element_id}",
        substrate=f"90x45mm {spec.timber_grade}",
        finish_system="Anchored to slab/joists and tied at corners",
        quantity=plates_lm,
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Plates run: 3 × {length:.2f} lm = {plates_lm:.2f} lm.",
        row_role="",
    ))

    # 3. Studs: (length / spacing + 1) + 2 extra per opening/corner
    base_studs = int(math.ceil(length / spacing_m)) + 1
    extra_studs = len(spec.openings) * 2 + 2  # jamb studs + corner studs
    total_studs = base_studs + extra_studs
    studs_lm = round(total_studs * (height - 0.135), 2)  # minus 3x 45mm plate thickness

    items.append(CarpentryTakeoffItem(
        section=spec.section,
        element=f"Wall studs ({int(height*1000)}mm cut lengths)",
        location=f"Studs · {spec.element_id}",
        substrate=f"90x45mm {spec.timber_grade}",
        finish_system=f"Spaced @ {spec.stud_spacing_mm}mm crs with double jambs at openings",
        quantity=float(total_studs),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{total_studs} No. studs ({base_studs} common + {extra_studs} jamb/corner). Total length: {studs_lm:.2f} lm.",
        row_role="",
    ))

    # 4. Noggings: 1 row for walls <= 2.7m, 2 rows for > 2.7m
    nogging_rows = 1 if height <= 2.7 else 2
    noggings_lm = round(length * nogging_rows, 2)
    items.append(CarpentryTakeoffItem(
        section=spec.section,
        element="Wall noggings / dwangs",
        location=f"Noggings · {spec.element_id}",
        substrate=f"90x45mm {spec.timber_grade}",
        finish_system=f"Installed horizontally at mid-height between studs ({nogging_rows} row)",
        quantity=noggings_lm,
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Nogging run: {noggings_lm:.2f} lm.",
        row_role="",
    ))

    return items


def calculate_subfloor_framing_items(spec: CarpentryElementSpec) -> List[CarpentryTakeoffItem]:
    """Calculate trade items for timber floor bearers, joists, and structural sheet flooring."""
    items: List[CarpentryTakeoffItem] = []
    # Source area and independently supplied rectangle axes may not
    # contradict one another. Do not coerce text, bool, NaN, infinite or
    # overflowing values into an apparently verified subfloor.
    def _metric_or_none(value: object) -> float | None:
        if type(value) not in (int, float):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) and number >= 0.0 else None

    source_area = _metric_or_none(spec.area_m2)
    source_length = _metric_or_none(spec.length_m)
    source_width = _metric_or_none(spec.width_m)
    if None in (source_area, source_length, source_width):
        return items
    rectangular_area = (
        source_length * source_width
        if source_length > 0.0 and source_width > 0.0 else None
    )
    if (source_area > 0.0 and rectangular_area is not None
            and not math.isclose(source_area, rectangular_area,
                                 rel_tol=0.0, abs_tol=0.011)):
        return items
    area = source_area if source_area > 0.0 else rectangular_area
    if area is None or not math.isfinite(area) or area <= 0.0:
        return items

    # 1. Structural Subfloor Sheets (m²)
    items.append(CarpentryTakeoffItem(
        section=spec.section or "Structure",
        element="Structural particleboard subfloor (19mm tongue & groove)",
        location=f"Subfloor · {spec.element_id}",
        substrate="19mm moisture-resistant structural particleboard",
        finish_system="Glued and screw-fixed to floor joists",
        quantity=round(area, 2),
        unit="m²",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional subfloor area: {area:.2f} m²; 19mm particleboard material not authenticated from original drawing.",
        row_role="floor_area",
    ))

    # 2. Floor Joists: approx 2.5 lm of joist per m² of floor area (@ 450mm crs)
    joists_lm = round(area * 2.4, 2)
    items.append(CarpentryTakeoffItem(
        section=spec.section or "Structure",
        element="Timber floor joists (190x45 / 240x45 MGP10)",
        location=f"Joists · {spec.element_id}",
        substrate="Deep timber joists / I-joists",
        finish_system="Spaced @ 450mm centres, blocked at ends and over bearers",
        quantity=joists_lm,
        unit="lm",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional 2.4 lm/m² joist estimate: {joists_lm:.2f} lm across {area:.2f} m²; structural layout and sizing unverified.",
        row_role="",
    ))

    return items


def calculate_roof_framing_items(spec: CarpentryElementSpec) -> List[CarpentryTakeoffItem]:
    """Calculate trade items for prefabricated timber roof trusses and battens."""
    items: List[CarpentryTakeoffItem] = []
    # A previous 8.0 m fallback labelled roof trusses as Measured even
    # when the source supplied no physical span. Keep numeric candidates
    # only for real dimensions. Standard 900 mm centres are still a design
    # assumption, not a counted original truss layout.
    def _positive_metric(value: object) -> float | None:
        if type(value) not in (int, float):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return numeric if math.isfinite(numeric) and numeric > 0.0 else None

    length = _positive_metric(spec.length_m)
    span = _positive_metric(spec.width_m)
    explicit_area = _positive_metric(spec.area_m2)
    physical_rectangle_area = (
        length * span if length is not None and span is not None else None
    )
    if (
        explicit_area is not None and physical_rectangle_area is not None
        and not math.isclose(explicit_area, physical_rectangle_area,
                             rel_tol=0.0, abs_tol=0.011)
    ):
        return items
    # Missing/zero is the legacy absent-area sentinel. A nonzero, invalid
    # original area claim must not be hidden by substituting an L x W guess.
    if type(spec.area_m2) not in (int, float):
        return items
    try:
        claimed_area = float(spec.area_m2)
    except (TypeError, ValueError, OverflowError):
        return items
    if not math.isfinite(claimed_area) or claimed_area < 0.0:
        return items
    area = explicit_area if explicit_area is not None else physical_rectangle_area
    if area is None or not math.isfinite(area) or area <= 0.0:
        return items

    if length is None or span is None:
        # Without both dimensions the count of complete trusses is not
        # measured, and the roof area alone must not mint a nominal span.
        truss_count = None
    else:
        truss_count = int(math.ceil(length / 0.900)) + 1

    # 1. Prefabricated Trusses (No.)
    if truss_count is not None:
        items.append(CarpentryTakeoffItem(
        section="Roof",
        element=f"Prefabricated timber roof trusses ({span:.1f}m span)",
        location=f"Roof trusses · {spec.element_id}",
        substrate="Engineered gang-nail timber trusses",
        finish_system="Erected, braced with speed-bracing and tied down with triple-grips",
        quantity=float(truss_count),
        unit="No.",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional {truss_count} No. trusses estimated @ 900mm crs over {length:.2f}m source run; original truss setting-out and material unverified.",
        row_role="",
    ))

    # 2. Roof Battens: approx 1.25 lm per m², not actual measured
    # original batten lengths. Preserve it as a provisional design estimate.
    battens_lm = round(area * 1.25, 2)
    items.append(CarpentryTakeoffItem(
        section="Roof",
        element="Timber roof battens (70x35mm MGP10)",
        location=f"Roof battens · {spec.element_id}",
        substrate="70x35mm treated timber battens",
        finish_system="Fixed across truss top chords to receive roof sheeting",
        quantity=battens_lm,
        unit="lm",
        quantity_status="Provisional",
        source_page=spec.source_page,
        source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
        inclusion_status="PROVISIONAL",
        confidence="Provisional",
        notes=f"Provisional batten rate-based estimate: {battens_lm:.2f} lm over {area:.2f} m²; actual battens/spacing/material not source-confirmed.",
        row_role="",
    ))

    return items


def calculate_eaves_and_cladding_items(spec: CarpentryElementSpec) -> List[CarpentryTakeoffItem]:
    """Calculate trade items for external cladding and eave soffits."""
    items: List[CarpentryTakeoffItem] = []
    if spec.element_type == "cladding":
        if spec.area_m2 > 0.0:
            gross_area = spec.area_m2
        elif spec.length_m > 0.0 and spec.height_m > 0.0:
            gross_area = spec.length_m * spec.height_m
        else:
            gross_area = 0.0
        # The cladding gross/net area must remain an actual possible
        # physical surface. A missing original opening area is not a zero-
        # area proof, and deductions larger than their containing elevation
        # cannot be silently clamped into a credible measured takeoff.
        if type(gross_area) not in (int, float):
            return items
        try:
            gross_area = float(gross_area)
        except (TypeError, ValueError, OverflowError):
            return items
        if not math.isfinite(gross_area) or gross_area <= 0.0:
            return items
        deduction_areas = []
        for opening in spec.openings:
            if not isinstance(opening, dict):
                return items
            value = opening.get("area")
            if type(value) not in (int, float):
                return items
            try:
                area = float(value)
            except (TypeError, ValueError, OverflowError):
                return items
            if not math.isfinite(area) or area <= 0.0:
                return items
            deduction_areas.append(area)
        op_ded = math.fsum(deduction_areas)
        if not math.isfinite(op_ded) or op_ded >= gross_area:
            return items
        net_area = round(gross_area - op_ded, 2)
        if net_area > 0.0:
            items.append(CarpentryTakeoffItem(
                section="External",
                element="External weatherboard / FC plank cladding",
                location=f"Cladding · {spec.element_id}",
                substrate="Fibre-cement / timber weatherboards over building wrap and cavity battens",
                finish_system="Lap fixed with concealed stainless steel nails",
                quantity=net_area,
                unit="m²",
                quantity_status="Measured",
                source_page=spec.source_page,
                source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
                inclusion_status="INCLUSION",
                confidence="Verified",
                notes=f"Net cladding area: {net_area:.2f} m² (Gross {gross_area:.2f} m² - Openings {op_ded:.2f} m²).",
                row_role="external_wall",
            ))
    elif spec.element_type == "eaves":
        perimeter = spec.perimeter_lm if spec.perimeter_lm > 0.0 else spec.length_m
        # A zero-width overhang is not an invitation to invent 600 mm.
        # The dataclass's 0.60 default is itself only a provisional estimate.
        overhang = spec.overhang_width_m
        # Eave dimensions/materials are modelling inputs, not issued drawing
        # geometry or a verified material schedule. Never promote this generic
        # fallback to measured customer quantities without a source authority.
        if (perimeter > 0.0 and overhang > 0.0
                and math.isfinite(perimeter) and math.isfinite(overhang)):
            eave_area = round(perimeter * overhang, 2)
            # Eave soffit lining (m²)
            items.append(CarpentryTakeoffItem(
                section="External",
                element=f"Eaves soffit lining ({int(overhang*1000)}mm wide)",
                location=f"Eaves · {spec.element_id}",
                substrate="4.5mm fibre-cement eaves lining sheet with PVC joiners",
                finish_system="Fixed to eave bearer/truss overhang with eave mould trim",
                quantity=eave_area,
                unit="m²",
                quantity_status="Provisional",
                source_page=spec.source_page or "UNVERIFIED - model input only",
                source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
                inclusion_status="PROVISIONAL",
                confidence="Provisional",
                notes=(f"Provisional eaves estimate: {perimeter:.2f} lm × {overhang:.2f}m = {eave_area:.2f} m²; "
                       "perimeter, overhang, 4.5mm FC material and physical soffit face NOT source-authenticated."),
                row_role="",
            ))
            # Timber Fascia (lm)
            items.append(CarpentryTakeoffItem(
                section="External",
                element="Timber fascia board (190x25mm primed LOSP)",
                location=f"Fascia · {spec.element_id}",
                substrate="190x25mm LOSP treated pine fascia",
                finish_system="Fixed to truss tails ready to receive gutter",
                quantity=round(perimeter, 2),
                unit="lm",
                quantity_status="Provisional",
                source_page=spec.source_page or "UNVERIFIED - model input only",
                source_reference=f"{CARPENTRY_SOURCE_PREFIX} · {spec.element_id}",
                inclusion_status="PROVISIONAL",
                confidence="Provisional",
                notes=(f"Provisional fascia estimate: {perimeter:.2f} lm; "
                       "timber fascia material and actual fascia extent NOT source-authenticated."),
                row_role="",
            ))

    return items


def generate_workspace_carpentry_takeoff(
    specs: Sequence[CarpentryElementSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all carpentry elements."""
    all_rows: List[Dict[str, Any]] = []

    for spec in specs:
        items: List[CarpentryTakeoffItem] = []
        if spec.element_type == "wall_frame":
            items = calculate_wall_framing_items(spec)
        elif spec.element_type == "subfloor":
            items = calculate_subfloor_framing_items(spec)
        elif spec.element_type == "roof_frame":
            items = calculate_roof_framing_items(spec)
        elif spec.element_type in ("cladding", "eaves"):
            items = calculate_eaves_and_cladding_items(spec)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
