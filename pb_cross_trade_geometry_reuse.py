"""Fail-closed cross-trade geometry reuse from canonical building objects.

This module proves one thing only:

    ONE AUTHENTICATED CANONICAL OBJECT -> MULTIPLE EXPLICIT TRADE QUANTITIES

It does not extract geometry and it does not manufacture trade scope. A trade
quantity publishes only when:
- the host object has a stable canonical identity;
- the geometric quantity needed by the formula is already resolved; and
- the caller supplies an explicit source/spec-backed trade description.

There are deliberately no defaults for brickwork, plasterboard, paint,
insulation, slab thickness, roof pitch, reinforcement laps, door widths, or
finish-face ownership.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from pb_auto_geometry_v1219 import SOURCE_PREFIX
import pb_takeoff_row_contract as takeoff_contract
from pb_hardened_authority_contract import authenticated_tile_surface_rows


_ALLOWED_HOST_TYPES = {"WALL", "SLAB", "ROOF", "SPACE", "FLOOR", "CEILING"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _positive(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


def _nonnegative(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0.0 else None


def _evidence_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(dict.fromkeys(_clean(item) for item in value if _clean(item)))


def _trade_spec(
    specs: Optional[Mapping[str, Any]],
    trade_name: str,
) -> Optional[Mapping[str, Any]]:
    if not isinstance(specs, Mapping):
        return None
    candidate = specs.get(trade_name)
    return candidate if isinstance(candidate, Mapping) else None


def _material(spec: Mapping[str, Any]) -> Optional[str]:
    value = _clean(
        spec.get("material")
        or spec.get("system")
        or spec.get("profile")
        or spec.get("substrate")
    )
    return value or None


def _spec_evidence(spec: Mapping[str, Any]) -> tuple[str, ...]:
    return _evidence_ids(spec.get("evidence_ids"))


def _face_ids(spec: Mapping[str, Any]) -> tuple[str, ...]:
    return _evidence_ids(spec.get("physical_face_ids"))


def _spec_section(spec: Mapping[str, Any]) -> Optional[str]:
    section = _clean(spec.get("section")).lower()
    if section == "internal":
        return "Internal"
    if section == "external":
        return "External"
    if section == "roof":
        return "Roof"
    if section == "structure":
        return "Structure"
    if section == "substructure":
        return "Substructure"
    return None


def _wall_section(wall: Mapping[str, Any]) -> Optional[str]:
    role = _clean(wall.get("role")).lower()
    if role == "external":
        return "External"
    if role == "internal":
        return "Internal"
    return None


def _polygon_perimeter_m(value: object) -> Optional[float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    points: list[tuple[float, float]] = []
    try:
        for point in value:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                return None
            x, y = float(point[0]), float(point[1])
            if not math.isfinite(x) or not math.isfinite(y):
                return None
            points.append((x, y))
    except (TypeError, ValueError, OverflowError):
        return None
    perimeter = 0.0
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        perimeter += math.hypot(second[0] - first[0], second[1] - first[1])
    return perimeter if math.isfinite(perimeter) and perimeter > 0.0 else None


@dataclass
class DerivedTradeQuantity:
    """One explicit trade quantity derived from one canonical host object."""

    trade_scope: str
    section: str
    element: str
    location: str
    substrate: str
    quantity: float
    unit: str
    host_object_id: str
    host_object_type: str
    derivation_formula: str
    host_evidence_ids: tuple[str, ...] = ()
    spec_evidence_ids: tuple[str, ...] = ()
    confidence: str = "Source-derived"
    notes: str = ""
    status: str = "Measured"

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.quantity)) or float(self.quantity) < 0.0:
            raise ValueError(
                "Derived trade quantity must be a non-negative finite number"
            )
        self.quantity = round(float(self.quantity), 6)
        if not _clean(self.host_object_id):
            raise ValueError("host_object_id must be a canonical object id")
        if self.host_object_type not in _ALLOWED_HOST_TYPES:
            raise ValueError(
                f"unsupported host_object_type {self.host_object_type!r}"
            )
        if not _clean(self.derivation_formula):
            raise ValueError("derivation_formula must be explicit")
        unit = _clean(self.unit)
        if unit in {"m2", "sqm", "m^2"}:
            self.unit = "m²"
        elif unit in {"m3", "cum", "m^3"}:
            self.unit = "m³"
        elif unit.lower() in {"ea", "count", "nr", "no"}:
            self.unit = "No."
        elif unit in {"m", "lin.m", "linear_m"}:
            self.unit = "lm"
        else:
            self.unit = unit
        self.host_evidence_ids = tuple(dict.fromkeys(self.host_evidence_ids))
        self.spec_evidence_ids = tuple(dict.fromkeys(self.spec_evidence_ids))


def _quantity(
    *,
    trade_scope: str,
    section: str,
    element: str,
    location: str,
    material: str,
    quantity: float,
    unit: str,
    host_id: str,
    host_type: str,
    formula: str,
    host_evidence_ids: tuple[str, ...],
    spec_evidence_ids: tuple[str, ...],
    notes: str,
) -> DerivedTradeQuantity:
    return DerivedTradeQuantity(
        trade_scope=trade_scope,
        section=section,
        element=element,
        location=location,
        substrate=material,
        quantity=quantity,
        unit=unit,
        host_object_id=host_id,
        host_object_type=host_type,
        derivation_formula=formula,
        host_evidence_ids=host_evidence_ids,
        spec_evidence_ids=spec_evidence_ids,
        notes=notes,
    )


def derive_wall_trade_quantities(
    wall: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse one resolved canonical wall across explicitly bound trade scopes."""

    wall_id = _clean(wall.get("canonical_wall_id"))
    net_area_m2 = _positive(wall.get("net_area_m2"))
    section = _wall_section(wall)
    host_evidence = _evidence_ids(wall.get("evidence_ids"))
    if (
        not wall_id
        or net_area_m2 is None
        or section is None
        or wall.get("physical_identity_resolved") is not True
        or wall.get("quantity_complete") is not True
        or not host_evidence
    ):
        return []

    results: List[DerivedTradeQuantity] = []

    for spec_name, trade_scope, element in (
        ("masonry", "masonry", f"{section} walling / masonry"),
        ("insulation", "insulation", "Wall insulation"),
    ):
        spec = _trade_spec(specs, spec_name)
        if spec is None:
            continue
        material = _material(spec)
        spec_evidence = _spec_evidence(spec)
        if not material or not spec_evidence:
            continue
        results.append(
            _quantity(
                trade_scope=trade_scope,
                section=section,
                element=element,
                location=wall_id,
                material=material,
                quantity=net_area_m2,
                unit="m²",
                host_id=wall_id,
                host_type="WALL",
                formula=f"Canonical net wall area {net_area_m2:.6f} m²",
                host_evidence_ids=host_evidence,
                spec_evidence_ids=spec_evidence,
                notes=f"Derived once from canonical wall {wall_id}.",
            )
        )

    for spec_name, trade_scope, element in (
        ("linings", "linings", "Wall lining"),
        ("painting", "painting", "Wall painting"),
    ):
        spec = _trade_spec(specs, spec_name)
        if spec is None:
            continue
        material = _material(spec)
        spec_evidence = _spec_evidence(spec)
        face_ids = _face_ids(spec)
        face_section = _spec_section(spec)
        if not material or not spec_evidence or not face_ids or face_section is None:
            continue
        quantity_m2 = net_area_m2 * len(face_ids)
        results.append(
            _quantity(
                trade_scope=trade_scope,
                section=face_section,
                element=element,
                location=f"{wall_id} · {';'.join(face_ids)}",
                material=material,
                quantity=quantity_m2,
                unit="m²",
                host_id=wall_id,
                host_type="WALL",
                formula=(
                    f"Canonical net wall area {net_area_m2:.6f} m² × "
                    f"{len(face_ids)} source-bound face(s)"
                ),
                host_evidence_ids=host_evidence,
                spec_evidence_ids=spec_evidence,
                notes=(
                    f"Face-scoped finish derived from canonical wall {wall_id}; "
                    "physical face ownership supplied by source-bound finish evidence."
                ),
            )
        )

    # Wall tiling is not allowed to reuse the whole canonical net-wall area
    # merely because a finish spec names one or more face IDs.  It must arrive
    # through the hardened internal-elevation authority chain and carry an
    # authenticated per-face tile extent.
    tiling = _trade_spec(specs, "tiling")
    if tiling is not None:
        material = _material(tiling)
        spec_evidence = _spec_evidence(tiling)
        face_section = _spec_section(tiling)
        authenticated_surfaces = authenticated_tile_surface_rows(
            tiling, canonical_wall_id=wall_id
        )
        if material and spec_evidence and face_section is not None and authenticated_surfaces:
            quantity_m2 = sum(
                float(row["tile_extent_m2"]) for row in authenticated_surfaces
            )
            face_ids = tuple(
                str(row["physical_wall_face_id"]) for row in authenticated_surfaces
            )
            surface_evidence = tuple(
                dict.fromkeys(
                    evidence_id
                    for row in authenticated_surfaces
                    for evidence_id in (row.get("evidence_ids") or ())
                    if str(evidence_id)
                )
            )
            results.append(
                _quantity(
                    trade_scope="tiling",
                    section=face_section,
                    element="Wall tiling",
                    location=f"{wall_id} · {';'.join(face_ids)}",
                    material=material,
                    quantity=quantity_m2,
                    unit="m²",
                    host_id=wall_id,
                    host_type="WALL",
                    formula=(
                        "Authenticated internal-elevation wall-face tile extents: "
                        + " + ".join(
                            f"{float(row['tile_extent_m2']):.6f} m²"
                            for row in authenticated_surfaces
                        )
                    ),
                    host_evidence_ids=tuple(dict.fromkeys(host_evidence + surface_evidence)),
                    spec_evidence_ids=spec_evidence,
                    notes=(
                        f"Tile quantity derived only from authenticated physical wall-face "
                        f"extent(s) on canonical wall {wall_id}; canonical net wall area "
                        "is not used as a tile proxy."
                    ),
                )
            )

    skirting = _trade_spec(specs, "skirting")
    if skirting is not None:
        length_m = _positive(wall.get("length_m"))
        material = _material(skirting)
        spec_evidence = _spec_evidence(skirting)
        face_ids = _face_ids(skirting)
        face_section = _spec_section(skirting)
        door_deduction_m = _nonnegative(
            skirting.get("door_width_deduction_m")
        )
        if (
            length_m is not None
            and material
            and spec_evidence
            and face_ids
            and face_section is not None
            and door_deduction_m is not None
            and door_deduction_m <= length_m
        ):
            net_length_m = length_m - door_deduction_m
            if net_length_m > 0.0:
                results.append(
                    _quantity(
                        trade_scope="carpentry",
                        section=face_section,
                        element="Skirting boards",
                        location=f"{wall_id} · {';'.join(face_ids)}",
                        material=material,
                        quantity=net_length_m,
                        unit="lm",
                        host_id=wall_id,
                        host_type="WALL",
                        formula=(
                            f"Canonical wall length {length_m:.6f} m - "
                            f"source-bound door widths {door_deduction_m:.6f} m"
                        ),
                        host_evidence_ids=host_evidence,
                        spec_evidence_ids=spec_evidence,
                        notes=f"Skirting derived from canonical wall {wall_id}.",
                    )
                )

    return results


def derive_slab_trade_quantities(
    slab: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse one resolved canonical slab without inventing material scope."""

    slab_id = _clean(slab.get("canonical_slab_id"))
    area_m2 = _positive(slab.get("area_m2"))
    thickness_m = _positive(slab.get("thickness_m"))
    if (
        not slab_id
        or area_m2 is None
        or thickness_m is None
        or slab.get("geometry_complete") is not True
        or slab.get("thickness_complete") is not True
    ):
        return []

    provenance = slab.get("provenance")
    host_evidence = ()
    if isinstance(provenance, Mapping):
        host_evidence = _evidence_ids(provenance.get("evidence_ids"))
        if not host_evidence:
            annotation = _clean(provenance.get("annotation_raw_text"))
            boundary_id = _clean(provenance.get("boundary_id"))
            host_evidence = tuple(
                value
                for value in (
                    f"annotation:{annotation}" if annotation else "",
                    f"boundary:{boundary_id}" if boundary_id else "",
                )
                if value
            )

    results: List[DerivedTradeQuantity] = []
    context = _clean(
        specs.get("context") if isinstance(specs, Mapping) else ""
    ).lower()
    context_evidence = _evidence_ids(
        specs.get("context_evidence_ids")
        if isinstance(specs, Mapping)
        else ()
    )
    section = (
        "Substructure"
        if context == "ground"
        else "Structure"
    )

    concrete = _trade_spec(specs, "concrete")
    if concrete is not None:
        material = _material(concrete)
        spec_evidence = _spec_evidence(concrete)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="concrete",
                    section=section,
                    element="Slab concrete",
                    location=slab_id,
                    material=material,
                    quantity=area_m2 * thickness_m,
                    unit="m³",
                    host_id=slab_id,
                    host_type="SLAB",
                    formula=(
                        f"Canonical slab area {area_m2:.6f} m² × "
                        f"thickness {thickness_m:.6f} m"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Concrete volume derived from canonical slab {slab_id}.",
                )
            )

    perimeter_m = _polygon_perimeter_m(slab.get("polygon_m"))
    edge_formwork = _trade_spec(specs, "edge_formwork")
    if edge_formwork is not None and perimeter_m is not None:
        material = _material(edge_formwork)
        spec_evidence = _spec_evidence(edge_formwork)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="formwork",
                    section=section,
                    element="Slab edge formwork",
                    location=f"{slab_id} · edge",
                    material=material,
                    quantity=perimeter_m * thickness_m,
                    unit="m²",
                    host_id=slab_id,
                    host_type="SLAB",
                    formula=(
                        f"Canonical slab polygon perimeter {perimeter_m:.6f} m × "
                        f"thickness {thickness_m:.6f} m"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Edge formwork derived from canonical slab {slab_id}.",
                )
            )

    soffit = _trade_spec(specs, "soffit_formwork")
    if soffit is not None and context == "suspended" and context_evidence:
        material = _material(soffit)
        spec_evidence = _spec_evidence(soffit)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="formwork",
                    section="Structure",
                    element="Slab soffit formwork",
                    location=f"{slab_id} · soffit",
                    material=material,
                    quantity=area_m2,
                    unit="m²",
                    host_id=slab_id,
                    host_type="SLAB",
                    formula=f"Canonical slab soffit area {area_m2:.6f} m²",
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=(*context_evidence, *spec_evidence),
                    notes=f"Soffit formwork derived from canonical slab {slab_id}.",
                )
            )

    waterproofing = _trade_spec(specs, "waterproofing")
    if (
        waterproofing is not None
        and context == "ground"
        and context_evidence
    ):
        material = _material(waterproofing)
        spec_evidence = _spec_evidence(waterproofing)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="waterproofing",
                    section="Substructure",
                    element="Under-slab membrane",
                    location=f"{slab_id} · underside",
                    material=material,
                    quantity=area_m2,
                    unit="m²",
                    host_id=slab_id,
                    host_type="SLAB",
                    formula=f"Canonical slab footprint area {area_m2:.6f} m²",
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=(*context_evidence, *spec_evidence),
                    notes=f"Membrane quantity derived from canonical slab {slab_id}.",
                )
            )

    reinforcement = _trade_spec(specs, "reinforcement")
    source_reinforcement = slab.get("reinforcement")
    if (
        reinforcement is not None
        and isinstance(source_reinforcement, (list, tuple))
        and source_reinforcement
    ):
        material = _material(reinforcement)
        if not material:
            descriptions = []
            for item in source_reinforcement:
                if isinstance(item, Mapping):
                    text = _clean(
                        item.get("specification")
                        or item.get("reinforcement_type")
                    )
                    if text:
                        descriptions.append(text)
            material = "; ".join(dict.fromkeys(descriptions)) or None
        spec_evidence = _spec_evidence(reinforcement)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="reinforcement",
                    section=section,
                    element="Slab reinforcement coverage",
                    location=f"{slab_id} · reinforcement",
                    material=material,
                    quantity=area_m2,
                    unit="m²",
                    host_id=slab_id,
                    host_type="SLAB",
                    formula=(
                        f"Canonical slab area {area_m2:.6f} m²; "
                        "no unproven lap or waste factor applied"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=(
                        f"Reinforcement coverage derived from canonical slab {slab_id}; "
                        "procurement laps remain a separate costing/spec assumption."
                    ),
                )
            )

    return results


def derive_roof_trade_quantities(
    roof: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse a canonical roof's already-proven metric parameters."""

    roof_id = _clean(roof.get("canonical_roof_id"))
    covering_area_m2 = _positive(roof.get("covering_area_m2"))
    host_evidence = _evidence_ids(roof.get("evidence_ids"))
    if (
        not roof_id
        or covering_area_m2 is None
        or roof.get("metric_parameter_geometry_complete") is not True
        or not host_evidence
    ):
        return []

    results: List[DerivedTradeQuantity] = []

    for spec_name, trade_scope, element in (
        ("cladding", "roofing", "Roof cladding / coverings"),
        ("insulation", "insulation", "Roof insulation / sarking"),
    ):
        spec = _trade_spec(specs, spec_name)
        if spec is None:
            continue
        material = _material(spec)
        spec_evidence = _spec_evidence(spec)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope=trade_scope,
                    section="Roof",
                    element=element,
                    location=roof_id,
                    material=material,
                    quantity=covering_area_m2,
                    unit="m²",
                    host_id=roof_id,
                    host_type="ROOF",
                    formula=(
                        f"Source-owned canonical roof covering area "
                        f"{covering_area_m2:.6f} m²"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Derived from canonical roof {roof_id}.",
                )
            )

    capping = _trade_spec(specs, "capping")
    ridge_length_m = _positive(roof.get("ridge_length_m"))
    if capping is not None and ridge_length_m is not None:
        material = _material(capping)
        spec_evidence = _spec_evidence(capping)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="roofing",
                    section="Roof",
                    element="Ridge / hip capping",
                    location=f"{roof_id} · ridge",
                    material=material,
                    quantity=ridge_length_m,
                    unit="lm",
                    host_id=roof_id,
                    host_type="ROOF",
                    formula=(
                        f"Canonical source-owned ridge length "
                        f"{ridge_length_m:.6f} m"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Capping derived from canonical roof {roof_id}.",
                )
            )

    gutters = _trade_spec(specs, "gutters")
    eave_length_lm = _positive(roof.get("eave_length_lm"))
    if gutters is not None and eave_length_lm is not None:
        material = _material(gutters)
        spec_evidence = _spec_evidence(gutters)
        if material and spec_evidence:
            results.append(
                _quantity(
                    trade_scope="plumbing",
                    section="Roof",
                    element="Eaves gutters",
                    location=f"{roof_id} · eaves",
                    material=material,
                    quantity=eave_length_lm,
                    unit="lm",
                    host_id=roof_id,
                    host_type="ROOF",
                    formula=(
                        f"Canonical source-owned eave length "
                        f"{eave_length_lm:.6f} m"
                    ),
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Gutters derived from canonical roof {roof_id}.",
                )
            )

    return results


def _derive_area_surface_trade_quantities(
    *,
    surface: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]],
    host_id_field: str,
    host_type: str,
    area_field: str,
    quantity_id_field: str,
    authority_field: str,
    trade_definitions: Sequence[tuple[str, str, str]],
) -> List[DerivedTradeQuantity]:
    host_id = _clean(surface.get(host_id_field))
    area_m2 = _positive(surface.get(area_field))
    quantity_id = _clean(surface.get(quantity_id_field))
    authority = _clean(surface.get(authority_field))
    host_evidence = _evidence_ids(surface.get("evidence_ids"))
    if (
        not host_id
        or area_m2 is None
        or not quantity_id
        or not authority
        or not host_evidence
    ):
        return []

    host_evidence = tuple(
        dict.fromkeys((*host_evidence, quantity_id))
    )
    results: List[DerivedTradeQuantity] = []
    for spec_name, trade_scope, element in trade_definitions:
        spec = _trade_spec(specs, spec_name)
        if spec is None:
            continue
        material = _material(spec)
        spec_evidence = _spec_evidence(spec)
        section = _spec_section(spec)
        if not material or not spec_evidence or section is None:
            continue
        results.append(
            _quantity(
                trade_scope=trade_scope,
                section=section,
                element=element,
                location=host_id,
                material=material,
                quantity=area_m2,
                unit="m²",
                host_id=host_id,
                host_type=host_type,
                formula=(
                    f"Canonical {host_type.lower()} metric area "
                    f"{area_m2:.6f} m²"
                ),
                host_evidence_ids=host_evidence,
                spec_evidence_ids=spec_evidence,
                notes=(
                    f"Trade quantity reuses canonical {host_type.lower()} "
                    f"surface {host_id}; no waste factor applied."
                ),
            )
        )
    return results


def derive_floor_surface_trade_quantities(
    floor: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse one canonical floor surface across explicitly scoped floor trades."""

    if floor.get("geometry_complete") is not True:
        return []
    return _derive_area_surface_trade_quantities(
        surface=floor,
        specs=specs,
        host_id_field="canonical_floor_id",
        host_type="FLOOR",
        area_field="metric_area_m2",
        quantity_id_field="metric_area_quantity_id",
        authority_field="metric_area_authority",
        trade_definitions=(
            ("flooring", "flooring", "Floor finish / covering"),
            ("tiling", "tiling", "Floor tiling"),
            ("coating", "painting", "Floor coating"),
            ("waterproofing", "waterproofing", "Floor waterproofing"),
        ),
    )


_PANEL_FINISH_SEMANTICS = frozenset({"insulated_panel", "sandwich_panel"})


def _ceiling_insulation_spec_allowed(spec: Optional[Mapping[str, Any]]) -> bool:
    if spec is None:
        return True
    material = _clean(
        spec.get("material")
        or spec.get("system")
        or spec.get("profile")
        or spec.get("substrate")
    )
    normalized_material = material.lower().replace("-", "_").replace(" ", "_")
    semantic_finish = _clean(spec.get("semantic_finish")).lower()

    # Panel-like ceiling insulation requires an upstream normalized semantic.
    # Raw project abbreviations (notably IP) and unnormalized panel wording are
    # never interpreted in the canonical quantity layer.
    panel_like = (
        material.upper() == "IP"
        or normalized_material in {
            "insulated_panel",
            "insulation_panel",
            "sandwich_panel",
        }
    )
    if panel_like:
        return semantic_finish in _PANEL_FINISH_SEMANTICS
    return True

def derive_ceiling_trade_quantities(
    ceiling: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse one canonical ceiling surface across explicitly scoped trades."""

    if (
        ceiling.get("geometry_complete") is not True
        or ceiling.get("metric_area_complete") is not True
    ):
        return []
    effective_specs = specs
    insulation_spec = _trade_spec(specs, "insulation")
    if insulation_spec is not None and not _ceiling_insulation_spec_allowed(
        insulation_spec
    ):
        effective_specs = dict(specs or {})
        effective_specs.pop("insulation", None)

    return _derive_area_surface_trade_quantities(
        surface=ceiling,
        specs=effective_specs,
        host_id_field="canonical_ceiling_id",
        host_type="CEILING",
        area_field="area_m2",
        quantity_id_field="ceiling_quantity_id",
        authority_field="physical_scale_record_id",
        trade_definitions=(
            ("lining", "linings", "Ceiling lining"),
            ("painting", "painting", "Ceiling painting"),
            ("insulation", "insulation", "Ceiling insulation"),
        ),
    )


def derive_space_trade_quantities(
    space: Mapping[str, Any],
    specs: Optional[Mapping[str, Any]] = None,
    doors: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[DerivedTradeQuantity]:
    """Reuse metric room perimeter for trims only.

    Floor finishes and ceiling linings are intentionally not derived from a
    room-area proxy here. Those trades must consume the canonical FLOOR and
    CEILING surface objects instead.
    """

    space_id = _clean(space.get("canonical_room_id"))
    perimeter_m = _positive(space.get("perimeter_m"))
    host_evidence = _evidence_ids(space.get("evidence_ids"))
    if not space_id or perimeter_m is None or not host_evidence:
        return []

    results: List[DerivedTradeQuantity] = []

    skirting = _trade_spec(specs, "skirting")
    if skirting is not None and doors is not None:
        material = _material(skirting)
        spec_evidence = _spec_evidence(skirting)
        section = _spec_section(skirting)
        widths: list[float] = []
        valid_widths = True
        for door in doors:
            width = _positive(
                door.get("width_m") if isinstance(door, Mapping) else None
            )
            if width is None:
                valid_widths = False
                break
            widths.append(width)
        if material and spec_evidence and section and valid_widths:
            door_deduction_m = sum(widths)
            if door_deduction_m <= perimeter_m:
                quantity_m = perimeter_m - door_deduction_m
                if quantity_m > 0.0:
                    results.append(
                        _quantity(
                            trade_scope="carpentry",
                            section=section,
                            element="Skirting boards",
                            location=f"{space_id} · perimeter",
                            material=material,
                            quantity=quantity_m,
                            unit="lm",
                            host_id=space_id,
                            host_type="SPACE",
                            formula=(
                                f"Canonical room perimeter {perimeter_m:.6f} m - "
                                f"explicit door widths {door_deduction_m:.6f} m"
                            ),
                            host_evidence_ids=host_evidence,
                            spec_evidence_ids=spec_evidence,
                            notes=f"Skirting derived from canonical room {space_id}.",
                        )
                    )

    cornice = _trade_spec(specs, "cornice")
    if cornice is not None:
        material = _material(cornice)
        spec_evidence = _spec_evidence(cornice)
        section = _spec_section(cornice)
        if material and spec_evidence and section:
            results.append(
                _quantity(
                    trade_scope="plastering",
                    section=section,
                    element="Ceiling cornice trim",
                    location=f"{space_id} · perimeter head",
                    material=material,
                    quantity=perimeter_m,
                    unit="lm",
                    host_id=space_id,
                    host_type="SPACE",
                    formula=f"Canonical room perimeter {perimeter_m:.6f} m",
                    host_evidence_ids=host_evidence,
                    spec_evidence_ids=spec_evidence,
                    notes=f"Cornice derived from canonical room {space_id}.",
                )
            )

    return results


def to_takeoff_rows(
    workspace_id: int,
    quantities: Sequence[DerivedTradeQuantity],
    source_page: str = "1",
    source_prefix: str = SOURCE_PREFIX,
) -> List[Tuple[Any, ...]]:
    """Convert supported quantities into the legacy 21-field row.

    This adapter is intentionally fail-closed. If a correct canonical quantity
    uses a unit the current takeoff schema cannot represent, especially m³, the
    function raises instead of corrupting the unit.
    """

    rows: List[Tuple[Any, ...]] = []
    stamp = ""

    for q in quantities:
        if q.unit not in takeoff_contract.TAKEOFF_UNITS:
            raise takeoff_contract.TakeoffRowContractError(
                f"canonical cross-trade quantity unit {q.unit!r} is not "
                f"representable by takeoff_rows units "
                f"{takeoff_contract.TAKEOFF_UNITS!r}; widen the runtime "
                "contract before publication"
            )

        if q.host_object_type == "WALL":
            if q.trade_scope == "masonry":
                role = (
                    "external_wall"
                    if q.section == "External"
                    else "internal_partition"
                    if q.section == "Internal"
                    else ""
                )
            else:
                role = "wall_finish"
        else:
            role = ""

        source_ref = (
            f"{source_prefix} · canonical_cross_trade:"
            f"{q.trade_scope}:{q.host_object_id}"
        )
        evidence_note = (
            f" Host evidence: {', '.join(q.host_evidence_ids)}."
            if q.host_evidence_ids
            else ""
        )
        spec_note = (
            f" Spec evidence: {', '.join(q.spec_evidence_ids)}."
            if q.spec_evidence_ids
            else ""
        )
        notes = (
            f"{q.notes} Derivation: {q.derivation_formula}."
            f"{evidence_note}{spec_note}"
        ).strip()
        inclusion = "INCLUSION" if role == "floor_area" else "PROVISIONAL"

        row = (
            int(workspace_id),
            q.section,
            q.element,
            q.location,
            q.substrate,
            q.substrate,
            q.quantity,
            q.unit,
            q.status,
            str(source_page),
            source_ref,
            inclusion,
            0,
            0.0,
            0.0,
            0.0,
            q.confidence,
            notes,
            role,
            stamp,
            stamp,
        )
        rows.append(
            takeoff_contract.validate_values(
                row,
                takeoff_contract.CORE_FIELDS,
                source=source_ref,
            )
        )

    return rows


__all__ = [
    "DerivedTradeQuantity",
    "derive_ceiling_trade_quantities",
    "derive_floor_surface_trade_quantities",
    "derive_roof_trade_quantities",
    "derive_slab_trade_quantities",
    "derive_space_trade_quantities",
    "derive_wall_trade_quantities",
    "to_takeoff_rows",
]
