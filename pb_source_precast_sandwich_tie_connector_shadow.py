"""Source Precast Concrete Insulated Sandwich Panel Tie Connector Shadow Authority.

Extracts candidate composite wythe tie connectors, insulation layer specifications,
wythe thicknesses, and connector layout grids from structural/precast panel drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SandwichTieConnectorCandidate:
    candidate_id: str
    sheet_id: str
    connector_type: str
    insulation_type: str
    insulation_thickness_mm: Optional[float]
    outer_wythe_thickness_mm: Optional[float]
    inner_wythe_thickness_mm: Optional[float]
    spacing_mm: Optional[float]
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "connector_type": self.connector_type,
            "insulation_type": self.insulation_type,
            "insulation_thickness_mm": self.insulation_thickness_mm,
            "outer_wythe_thickness_mm": self.outer_wythe_thickness_mm,
            "inner_wythe_thickness_mm": self.inner_wythe_thickness_mm,
            "spacing_mm": self.spacing_mm,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_sandwich_tie_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SANDWICH PANEL TIE",
        "INSULATED PANEL TIE",
        "GFRP CONNECTOR",
        "FIBERGLASS PIN",
        "THERMOMASS",
        "COMPOSITE TIE",
        "TRUSS TIE",
        "WYTHE CONNECTOR",
        "SANDWICH WALL TIE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Connector type
    if "TRUSS" in upper or "STAINLESS" in upper:
        connector_type = "STAINLESS_TRUSS_TIE"
    elif "CARBON" in upper or "C-GRID" in upper:
        connector_type = "CARBON_FIBER_GRID"
    elif "SLEEVE" in upper or "CYLINDER" in upper:
        connector_type = "CYLINDER_SLEEVE_PIN"
    else:
        connector_type = "GFRP_PIN_CONNECTOR"

    # Insulation type
    if "XPS" in upper or "EXTRUDED" in upper:
        insulation_type = "XPS"
    elif "EPS" in upper or "EXPANDED" in upper:
        insulation_type = "EPS"
    elif "MINERAL" in upper or "ROCKWOOL" in upper:
        insulation_type = "MINERAL_WOOL"
    else:
        insulation_type = "PIR"

    # Multi-wythe format e.g. "75/50/150" or "80-75-175" (outer / insulation / inner)
    tri_match = re.search(r"\b(\d{2,3})[\/\-](\d{2,3})[\/\-](\d{2,3})\b", upper)
    outer_wythe = None
    insul_thick = None
    inner_wythe = None
    if tri_match:
        outer_wythe = float(tri_match.group(1))
        insul_thick = float(tri_match.group(2))
        inner_wythe = float(tri_match.group(3))
    else:
        # Check individual callouts
        out_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:OUTER|FACING|EXTERIOR|FASCIA)\s*(?:WYTHE|PANEL)?", upper)
        if out_match:
            outer_wythe = float(out_match.group(1))

        ins_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:INSULATION|PIR|XPS|EPS|CORE)", upper)
        if ins_match:
            insul_thick = float(ins_match.group(1))

        in_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:INNER|STRUCTURAL|BACKUP|INTERIOR)\s*(?:WYTHE|PANEL)?", upper)
        if in_match:
            inner_wythe = float(in_match.group(1))

    # Spacing (e.g. "@ 400 CTS", "400MM SPACING", "@ 600MM C/C")
    space_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3,4})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS|SPACING)", upper)
    spacing_mm = float(space_match.group(1)) if space_match else 400.0

    return {
        "raw_text": clean,
        "connector_type": connector_type,
        "insulation_type": insulation_type,
        "insulation_thickness_mm": insul_thick or 50.0,
        "outer_wythe_thickness_mm": outer_wythe or 75.0,
        "inner_wythe_thickness_mm": inner_wythe or 150.0,
        "spacing_mm": spacing_mm,
    }


def evaluate_precast_sandwich_tie_connector_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SandwichTieConnectorCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_sandwich_tie_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_spt_{i+1:03d}"
        cand = SandwichTieConnectorCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            connector_type=parsed["connector_type"],
            insulation_type=parsed["insulation_type"],
            insulation_thickness_mm=parsed["insulation_thickness_mm"],
            outer_wythe_thickness_mm=parsed["outer_wythe_thickness_mm"],
            inner_wythe_thickness_mm=parsed["inner_wythe_thickness_mm"],
            spacing_mm=parsed["spacing_mm"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
