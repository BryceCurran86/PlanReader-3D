"""Source Fire Door Electro-Magnetic Hold-Open Release & Door Selector Shadow Authority.

Extracts candidate fire door electro-magnetic hold-open devices, sequential door selectors,
fire resistance ratings, mount styles, and door locations from architectural door schedules and security plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class FireDoorMagHoldCandidate:
    candidate_id: str
    sheet_id: str
    door_leaf_configuration: str
    fire_rating_hours: float
    mount_type: str
    voltage: str
    smoke_release_interface: bool
    sequential_selector_required: bool
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "door_leaf_configuration": self.door_leaf_configuration,
            "fire_rating_hours": self.fire_rating_hours,
            "mount_type": self.mount_type,
            "voltage": self.voltage,
            "smoke_release_interface": self.smoke_release_interface,
            "sequential_selector_required": self.sequential_selector_required,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_fire_door_mag_hold_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "MAG HOLD OPEN",
        "MAGNETIC HOLD OPEN",
        "DOOR SELECTOR",
        "DOOR COORDINATOR",
        "ELECTRO-MAGNETIC HOLDER",
        "MAGNETIC DOOR HOLDER",
        "FIRE DOOR HOLD OPEN",
        "REBATED DOOR SELECTOR",
        "ELECTROMAGNETIC HOLD OPEN",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Leaf configuration
    has_pair = any(k in upper for k in ["PAIR", "DOUBLE", "2 LEAF", "TWO LEAF"])
    has_coord = any(k in upper for k in ["SELECTOR", "COORDINATOR", "REBATED"])
    if "REBATED" in upper or (has_pair and has_coord):
        leaf_config = "DOUBLE_LEAF_REBATED"
    elif has_pair:
        leaf_config = "DOUBLE_LEAF_PLAIN"
    else:
        leaf_config = "SINGLE_LEAF"

    # Fire rating in hours (e.g. "2-HR", "1 HOUR", "-/120/30", "-/60/30", "FRL")
    hr_match = re.search(r"\b(\d{1,2})\s*(?:-|–|\s*)?(?:HR|HOUR)\b", upper)
    frl_match = re.search(r"-/(\d{2,3})/\d{2,3}", upper)
    if hr_match:
        fire_rating = float(hr_match.group(1))
    elif frl_match:
        mins = float(frl_match.group(1))
        fire_rating = round(mins / 60.0, 1)
    else:
        fire_rating = 2.0

    # Mount type (wall mount, floor mount, overhead surface)
    if "FLOOR" in upper:
        mount_type = "FLOOR_MOUNT"
    elif "OVERHEAD" in upper or "TRANSOM" in upper:
        mount_type = "OVERHEAD_SURFACE"
    else:
        mount_type = "WALL_MOUNT"

    # Voltage (24V DC default for life safety / fire alarm loop)
    if "240V" in upper or "240VAC" in upper:
        voltage = "240V_AC"
    else:
        voltage = "24V_DC"

    # Smoke detector / fire alarm trip interface
    smoke_interface = not any(k in upper for k in ["MANUAL ONLY", "NO SMOKE INTERFACE"])

    # Sequential selector required (mandatory for rebated double doors)
    selector_req = (leaf_config == "DOUBLE_LEAF_REBATED") or any(k in upper for k in ["SELECTOR", "COORDINATOR"])

    return {
        "raw_text": clean,
        "door_leaf_configuration": leaf_config,
        "fire_rating_hours": fire_rating,
        "mount_type": mount_type,
        "voltage": voltage,
        "smoke_release_interface": smoke_interface,
        "sequential_selector_required": selector_req,
    }


def evaluate_fire_door_mag_hold_open_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[FireDoorMagHoldCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_fire_door_mag_hold_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_mho_{i+1:03d}"
        cand = FireDoorMagHoldCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            door_leaf_configuration=parsed["door_leaf_configuration"],
            fire_rating_hours=parsed["fire_rating_hours"],
            mount_type=parsed["mount_type"],
            voltage=parsed["voltage"],
            smoke_release_interface=parsed["smoke_release_interface"],
            sequential_selector_required=parsed["sequential_selector_required"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
