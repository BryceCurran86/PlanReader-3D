"""Source Commercial Laundry Lint Trap & Hydrodynamic Interceptor Shadow Authority.

Extracts candidate laundry lint traps, dual filter baskets, holding capacities,
pipe diameters, and gastight access covers from hydraulic trade waste plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class LaundryLintTrapCandidate:
    candidate_id: str
    sheet_id: str
    trap_material: str
    capacity_litres: float
    dual_filter_baskets: bool
    inlet_outlet_dia_mm: float
    cover_class: str
    sampling_point_present: bool
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "trap_material": self.trap_material,
            "capacity_litres": self.capacity_litres,
            "dual_filter_baskets": self.dual_filter_baskets,
            "inlet_outlet_dia_mm": self.inlet_outlet_dia_mm,
            "cover_class": self.cover_class,
            "sampling_point_present": self.sampling_point_present,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_laundry_lint_trap_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "LINT TRAP",
        "LAUNDRY INTERCEPTOR",
        "LINT PIT",
        "LINT SCREEN",
        "TRADE WASTE LINT",
        "COMMERCIAL LAUNDRY TRAP",
        "HYDRODYNAMIC LINT",
        "LAUNDRY TRAP",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Trap construction material
    if "POLY" in upper or "POLYETHYLENE" in upper:
        trap_mat = "ROTOMOULDED_POLYETHYLENE"
    elif "CONCRETE" in upper or "PRECAST" in upper:
        trap_mat = "PRECAST_CONCRETE"
    elif "STAINLESS" in upper or "316" in upper or "SS" in upper:
        trap_mat = "STAINLESS_STEEL_316"
    else:
        trap_mat = "ROTOMOULDED_POLYETHYLENE"

    # Holding capacity (e.g. "500L", "1000 LITRES", "1500 LTR", "250L")
    cap_match = re.search(r"\b(\d{3,4})\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    capacity = float(cap_match.group(1)) if cap_match else 500.0

    # Dual filter baskets
    dual_baskets = any(k in upper for k in ["DUAL", "2 BASKET", "TWO BASKET", "DOUBLE BASKET", "SECONDARY SCREEN"]) or ("BASKET" in upper and "FILTER" in upper)

    # Inlet / Outlet pipe diameter (e.g. "DN100", "150MM PIPE", "DN150", "100MM INLET")
    pipe_match = re.search(r"\b(?:DN\s*|Ø\s*)(\d{2,3})\b", upper)
    if not pipe_match:
        pipe_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:INLET|OUTLET|PIPE|DRAIN)", upper)
    pipe_dia = float(pipe_match.group(1)) if pipe_match else 100.0

    # Cover class (Class B vs Class D gastight)
    if "CLASS D" in upper or "TRAFFICABLE" in upper:
        cover_class = "CLASS_D_GASTIGHT"
    elif "CLASS B" in upper:
        cover_class = "CLASS_B_GASTIGHT"
    else:
        cover_class = "BOLTED_AIRTIGHT"

    # Sampling point
    sampling = any(k in upper for k in ["SAMPLING", "TEST POINT", "INSPECTION POINT"])

    return {
        "raw_text": clean,
        "trap_material": trap_mat,
        "capacity_litres": capacity,
        "dual_filter_baskets": dual_baskets,
        "inlet_outlet_dia_mm": pipe_dia,
        "cover_class": cover_class,
        "sampling_point_present": sampling,
    }


def evaluate_laundry_lint_trap_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[LaundryLintTrapCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_laundry_lint_trap_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_llt_{i+1:03d}"
        cand = LaundryLintTrapCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            trap_material=parsed["trap_material"],
            capacity_litres=parsed["capacity_litres"],
            dual_filter_baskets=parsed["dual_filter_baskets"],
            inlet_outlet_dia_mm=parsed["inlet_outlet_dia_mm"],
            cover_class=parsed["cover_class"],
            sampling_point_present=parsed["sampling_point_present"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
