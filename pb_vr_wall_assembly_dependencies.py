"""Added-wall construction dependency scope for PlanReader's editable 3D program.

This is a *proposed* host object and a *review-only* trade work package.
Use the same canonical element/rate terminology as cross-trade geometry reuse
without minting commercial source evidence for a wall that was DRAWN in VR.
No fabricated wiring, plumbing routes, brace spacing or default board products.

A single wall change regenerates every dependent proposed quantity in one
deterministic function. In production, a separate authenticated wall-create
transaction and trade-specific source approval must precede publishing or
pricing any of these quantities into the customer's canonical takeoff.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Optional, Sequence

_MAX_WALL_M = 200.0
_MAX_HEIGHT_M = 20.0
_MAX_OPENINGS = 100
_MAX_SERVICES = 200
_MAX_BASIS_ITEMS = 1000
_ROUND = 6


def _name(value: object, field: str) -> str:
    if type(value) is not str or not value or not value.strip() or len(value) > 128:
        raise ValueError("new_wall_" + field + "_missing")
    return value


def _num(value: object, field: str, *, zero: bool = False, cap: float = 1e6) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("new_wall_" + field + "_must_be_finite_number")
    if value < 0 or not zero and value <= 0 or value > cap:
        raise ValueError("new_wall_" + field + "_out_of_range")
    return float(value)


def _point(value: object) -> tuple[float, float]:
    if type(value) is not tuple or len(value) != 2:
        raise ValueError("new_wall_position_invalid")
    return tuple(_num(x, "coordinate", zero=True, cap=10000) for x in value)


@dataclass(frozen=True)
class ProposedOpening:
    opening_id: str
    offset_m: float
    width_m: float
    height_m: float
    sill_height_m: float
    opening_kind: str  # door, window, passage
    clearance_verified: bool = False

    def __post_init__(self):
        _name(self.opening_id, "opening_id")
        if self.opening_kind not in ("door", "window", "passage"):
            raise ValueError("new_wall_opening_type_unknown")
        _num(self.offset_m, "opening_offset", zero=True, cap=_MAX_WALL_M)
        _num(self.width_m, "opening_width", cap=_MAX_WALL_M)
        _num(self.height_m, "opening_height", cap=_MAX_HEIGHT_M)
        _num(self.sill_height_m, "opening_sill", zero=True, cap=_MAX_HEIGHT_M)
        if type(self.clearance_verified) is not bool:
            raise ValueError("new_wall_opening_clearance_unverified")


@dataclass(frozen=True)
class WallServiceItem:
    """Explicit fittings or routed services. Quantity is supplied, NOT guessed."""
    service_id: str
    trade: str  # electrical or plumbing
    description: str
    quantity: float
    unit: str  # No. or lm
    specification_id: str
    installed_on_wall: bool

    def __post_init__(self):
        for k in ("service_id", "description", "specification_id"):
            _name(getattr(self, k), k)
        if self.trade not in ("electrical", "plumbing"):
            raise ValueError("new_wall_service_trade_invalid")
        if self.unit not in ("No.", "lm"):
            raise ValueError("new_wall_service_unit_not_supported")
        _num(self.quantity, "service_quantity", cap=1e5)
        if self.unit == "No." and not float(self.quantity).is_integer():
            raise ValueError("new_wall_service_count_not_integer")
        if type(self.installed_on_wall) is not bool:
            raise ValueError("new_wall_service_ownership_unverified")


@dataclass(frozen=True)
class KnownServiceRoute:
    """Same-level service line for intersection flags, not a guessed reroute."""
    route_id: str
    trade: str
    level_id: str
    from_pt: tuple[float, float]
    to_pt: tuple[float, float]
    exact_path_verified: bool

    def __post_init__(self):
        _name(self.route_id, "route_id")
        _name(self.level_id, "route_level")
        if self.trade not in ("electrical", "plumbing"):
            raise ValueError("new_wall_route_trade_invalid")
        a, b = _point(self.from_pt), _point(self.to_pt)
        if math.dist(a, b) <= 1e-8:
            raise ValueError("new_wall_route_degenerate")
        if type(self.exact_path_verified) is not bool:
            raise ValueError("new_wall_route_status_invalid")


@dataclass(frozen=True)
class NewWallDesign:
    workspace_id: str
    source_sha256: str
    snapshot_id: str
    base_model_revision: int
    proposal_id: str
    level_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    height_m: float
    openings: tuple[ProposedOpening, ...] = ()

    def __post_init__(self):
        import re
        for k in ("workspace_id", "snapshot_id", "proposal_id", "level_id"):
            _name(getattr(self, k), k)
        if (type(self.source_sha256) is not str or
            re.fullmatch(r"[a-fA-F0-9]{64}", self.source_sha256) is None):
            raise ValueError("new_wall_original_sha_required")
        if type(self.base_model_revision) is not int or self.base_model_revision < 0:
            raise ValueError("new_wall_model_revision_required")
        length = math.dist(_point(self.start_pt), _point(self.end_pt))
        if not 0.05 <= length <= _MAX_WALL_M:
            raise ValueError("new_wall_length_invalid")
        _num(self.height_m, "height", cap=_MAX_HEIGHT_M)
        if type(self.openings) is not tuple or len(self.openings) > _MAX_OPENINGS:
            raise ValueError("new_wall_opening_cap")
        spans = []
        used = set()
        for entry in self.openings:
            if type(entry) is not ProposedOpening or entry.opening_id in used:
                raise ValueError("new_wall_opening_identity_ambiguous")
            used.add(entry.opening_id)
            if entry.offset_m + entry.width_m > length + 1e-6 or (
                entry.sill_height_m + entry.height_m > self.height_m + 1e-6
            ):
                raise ValueError("new_wall_opening_outside_host")
            spans.append((entry.offset_m, entry.offset_m + entry.width_m,
                          entry.sill_height_m, entry.sill_height_m + entry.height_m))
        for i, a in enumerate(spans):
            for b in spans[i+1:]:
                if (min(a[1],b[1])-max(a[0],b[0]) > 1e-6 and
                    min(a[3],b[3])-max(a[2],b[2]) > 1e-6):
                    raise ValueError("new_wall_opening_overlap")

    @property
    def length_m(self) -> float:
        return math.dist(self.start_pt, self.end_pt)


@dataclass(frozen=True)
class WallAssemblySpecification:
    """Authored project scope, NEVER populated from hidden 'typical' defaults."""
    specification_id: str
    framing_system: Optional[str] = None
    stud_spacing_m: Optional[float] = None
    plate_runs: Optional[int] = None
    noggin_rows: Optional[int] = None
    bracing_system: Optional[str] = None
    bracing_area_m2: Optional[float] = None
    lining_system: Optional[str] = None
    lining_face_ids: tuple[str, ...] = ()
    skirting_system: Optional[str] = None
    skirting_face_ids: tuple[str, ...] = ()
    services: tuple[WallServiceItem, ...] = ()

    def __post_init__(self):
        _name(self.specification_id, "assembly_spec")
        if self.framing_system is not None:
            _name(self.framing_system, "framing_system")
        if self.bracing_system is not None:
            _name(self.bracing_system, "bracing_system")
        if self.lining_system is not None:
            _name(self.lining_system, "lining_system")
        if self.skirting_system is not None:
            _name(self.skirting_system, "skirting_system")
        if self.stud_spacing_m is not None:
            _num(self.stud_spacing_m, "stud_spacing", cap=3)
        for field in ("plate_runs", "noggin_rows"):
            value = getattr(self, field)
            if value is not None and (
                type(value) is not int or value < 0 or value > 20
            ):
                raise ValueError("new_wall_" + field + "_invalid")
        if self.bracing_area_m2 is not None:
            _num(self.bracing_area_m2, "bracing_area", zero=True, cap=1e5)
            if not self.bracing_system:
                raise ValueError("new_wall_bracing_spec_missing")
        for field in ("lining_face_ids", "skirting_face_ids"):
            entries = getattr(self, field)
            if (type(entries) is not tuple or len(entries) > 2 or
                any(x not in ("left", "right") for x in entries) or
                len(set(entries)) != len(entries)):
                raise ValueError("new_wall_" + field + "_invalid")
        if (self.lining_face_ids and not self.lining_system or
            self.skirting_face_ids and not self.skirting_system):
            raise ValueError("new_wall_finish_system_missing")
        if (type(self.services) is not tuple or len(self.services) > _MAX_SERVICES or
            len({s.service_id for s in self.services}) != len(self.services) or
            any(type(s) is not WallServiceItem for s in self.services)):
            raise ValueError("new_wall_services_invalid")


@dataclass(frozen=True)
class ProposedTradeLine:
    line_id: str
    trade: str
    element: str
    description: str
    value: float
    unit: str
    formula: str
    status: str
    host_proposal_id: str
    specification_id: str


@dataclass(frozen=True)
class WallConstructionPackage:
    proposal_id: str
    revision_scope_key: str
    wall_length_m: float
    wall_height_m: float
    quantities: tuple[ProposedTradeLine, ...]
    coordination_required: tuple[str, ...]
    can_publish_commercial: bool = False
    original_source_modified: bool = False

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def _orient(a, b, c) -> float:
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _crosses(a,b,c,d) -> bool:
    return _orient(a,b,c)*_orient(a,b,d) < -1e-8 and (
        _orient(c,d,a)*_orient(c,d,b) < -1e-8
    )


def calculate_new_wall_construction_package(
    wall: NewWallDesign,
    assembly: WallAssemblySpecification,
    *,
    known_service_routes: Sequence[KnownServiceRoute] = (),
) -> WallConstructionPackage:
    """Recompute every dependent trade when this proposed wall changes.

    Nothing here is final design, quantity approval or a wall-create command.
    Missing framing/bracing/MEP documentation means a specific HOLD, not zero.
    """
    if type(wall) is not NewWallDesign or type(assembly) is not WallAssemblySpecification:
        raise TypeError("typed_wall_and_assembly_required")
    if len(known_service_routes) > _MAX_BASIS_ITEMS:
        raise ValueError("service_route_count_exceeded")
    if any(type(route) is not KnownServiceRoute for route in known_service_routes):
        raise TypeError("trusted_service_route_type_required")
    scope = sha256(json.dumps([
        wall.workspace_id,wall.source_sha256.lower(),wall.snapshot_id,
        wall.base_model_revision,wall.proposal_id,
    ], separators=(",",":")).encode()).hexdigest()
    lines = []
    holds = []

    def add(trade: str, element: str, quantity: float, unit: str,
            formula: str, description: str) -> None:
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError("new_wall_derived_quantity_not_finite")
        # Stable IDs allow client to diff/remove the SAME dependent trade line
        # on a wall edit, rather than double-count the original and the update.
        lid=sha256(json.dumps([scope,assembly.specification_id,trade,element,
                               description,unit],separators=(",",":")).encode()).hexdigest()[:32]
        lines.append(ProposedTradeLine(
            line_id=lid,trade=trade,element=element,
            description=description,value=round(quantity,_ROUND),
            unit=unit,formula=formula,status="review_only",
            host_proposal_id=wall.proposal_id,
            specification_id=assembly.specification_id,
        ))

    L = wall.length_m
    H = wall.height_m
    total_open_area = math.fsum(x.width_m*x.height_m for x in wall.openings)
    area = max(0., L*H-total_open_area)
    # A through-wall doorway cuts skirting on the wall faces that actually
    # receive it, not an opening with a window sill above the floor.
    doorway_length = math.fsum(
        x.width_m for x in wall.openings
        if x.opening_kind in ("door","passage") and x.sill_height_m <= 1e-6
    )
    if doorway_length > L+1e-6:
        raise ValueError("door_skirting_deduction_exceeds_wall_length")

    if assembly.framing_system:
        if assembly.plate_runs is not None:
            add("carpentry", "Wall framing plates",
                L * assembly.plate_runs, "lm",
                f"wall length {L:.6f} m × {assembly.plate_runs} explicit plate runs",
                assembly.framing_system)
        else:
            holds.append("framing_plate_runs_not_specified")
        if assembly.stud_spacing_m is not None:
            # A simple upper-bound layout count; structural jamb packs,
            # corner junctions and lintels still require explicit framing.
            stud_count=math.ceil(L/assembly.stud_spacing_m)+1
            add("carpentry","Preliminary wall stud count",
                stud_count,"No.",
                f"ceil({L:.6f} m / {assembly.stud_spacing_m:.6f} m) + 1",
                assembly.framing_system)
            add("carpentry","Preliminary full-height stud stock",
                stud_count*H,"lm",
                f"{stud_count} studs × {H:.6f} m gross wall height",
                assembly.framing_system)
            if wall.openings:
                holds.append("opening_jamb_lintel_and_stud_reinforcement_not_designed")
        else:
            holds.append("framing_stud_spacing_not_specified")
        if assembly.noggin_rows is not None:
            add("carpentry","Noggin stock, preliminary",
                L*assembly.noggin_rows,"lm",
                f"{L:.6f} m × {assembly.noggin_rows} documented noggin rows",
                assembly.framing_system)
        else:
            holds.append("noggin_schedule_not_specified")
    else:
        holds.append("wall_framing_design_required")

    if assembly.bracing_system and assembly.bracing_area_m2 is not None:
        if assembly.bracing_area_m2 > L*H+1e-6:
            raise ValueError("bracing_area_exceeds_host_wall")
        if assembly.bracing_area_m2:
            add("carpentry","Specified wall bracing coverage",
                assembly.bracing_area_m2,"m²",
                f"explicit wall bracing schedule: {assembly.bracing_area_m2:.6f} m²",
                assembly.bracing_system)
    else:
        holds.append("structural_bracing_design_required")

    if assembly.lining_system and assembly.lining_face_ids:
        for face in assembly.lining_face_ids:
            add("plastering","Wall plasterboard lining",
                area,"m²",
                f"{L:.6f} m × {H:.6f} m - {total_open_area:.6f} m² openings; {face} face",
                assembly.lining_system + " · " + face)
    else:
        holds.append("plasterboard_lining_schedule_required")

    if assembly.skirting_system and assembly.skirting_face_ids:
        net=max(0.,L-doorway_length)
        for face in assembly.skirting_face_ids:
            if net > 0:
                add("carpentry","Wall skirting boards",net,"lm",
                    f"{L:.6f} m - {doorway_length:.6f} m floor-level door/passage deductions; {face} face",
                    assembly.skirting_system + " · " + face)
    else:
        holds.append("skirting_face_or_finish_schedule_required")

    trades={"electrical":False, "plumbing":False}
    for service in assembly.services:
        if not service.installed_on_wall:
            raise ValueError("service_item_not_authorized_for_this_wall")
        trades[service.trade]=True
        add(service.trade,
            "Wall electrical item" if service.trade=="electrical" else "Wall plumbing item",
            service.quantity,service.unit,
            f"explicit item {service.service_id}: {service.quantity:.6f} {service.unit}",
            f"{service.description} · {service.specification_id}")
    for route in known_service_routes:
        if route.level_id != wall.level_id:
            continue
        if route.exact_path_verified is not True:
            holds.append(f"{route.trade}_unverified_route_{route.route_id}")
        elif _crosses(wall.start_pt,wall.end_pt,route.from_pt,route.to_pt):
            holds.append(f"{route.trade}_route_conflict_{route.route_id}_requires_redesign")
    for trade in trades:
        if not trades[trade]:
            holds.append(f"{trade}_new_wall_services_to_be_reviewed")
    if wall.openings:
        holds.append("door_window_frame_and_trim_details_require_coordinated_schedule")

    if len({q.line_id for q in lines}) != len(lines):
        raise ValueError("new_wall_duplicate_scope_line_identity")
    return WallConstructionPackage(
        proposal_id=wall.proposal_id, revision_scope_key=scope,
        wall_length_m=round(L,_ROUND),wall_height_m=H,
        quantities=tuple(sorted(lines,key=lambda q:(q.trade,q.element,q.description))),
        coordination_required=tuple(sorted(set(holds))),
    )
