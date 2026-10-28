"""
pb_source_automatic_transfer_switch_ats_bypass_shadow.py

Shadow candidate authority for electrical emergency power automatic transfer switches (ATS),
drawout bypass isolation units, closed transition synchronizers, and manual transfer switches.

STRICT CONTRACT:
- Candidate authority only: status="CANDIDATE", commercial_projection_allowed=False, takeoff_eligible=False.
- Deterministic 2D grid snapping (SNAP_TOLERANCE_PT = 2.5 pt).
- Primitive safety cap: MAX_SAFETY_CAP_PRIMITIVES = 20_000.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class AutomaticTransferSwitchCandidate:
    candidate_id: str
    element_type: str  # BYPASS_ISOLATION_ATS, STANDARD_AUTOMATIC_TRANSFER_SWITCH, CLOSED_TRANSITION_TRANSFER_SWITCH, MANUAL_TRANSFER_SWITCH, LOAD_SHED_PRIORITY_CONTROLLER
    rated_current_amperes: int
    num_poles: int
    transition_type: str  # OPEN_TRANSITION, CLOSED_TRANSITION, DELAYED_TRANSITION
    enclosure_rating: str  # IP31_INDOOR, IP54_WEATHERPROOF, IP65_HARSH
    short_circuit_withstand_ka: int
    has_bypass_isolation: bool
    has_generator_start_contacts: bool
    tag: Optional[str]
    raw_annotation: str
    snapped_grid_pt: Tuple[float, float]
    source_primitive_id: str
    confidence: float
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False


def snap_point_to_grid(x: float, y: float, tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    snapped_x = round(x / tolerance) * tolerance
    snapped_y = round(y / tolerance) * tolerance
    return (round(snapped_x, 4), round(snapped_y, 4))


def extract_ats_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[AutomaticTransferSwitchCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[AutomaticTransferSwitchCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:AUTOMATIC\s+(?:TRANSFER\s+)?SWITCH|TRANSFER\s+SWITCH|BYPASS\s+ISOLATION(?:\s+ATS)?|MANUAL\s+(?:TRANSFER\s+)?SWITCH|CLOSED\s+TRANSITION(?:\s+ATS)?|CHANGE[- ]?OVER(?:\s+SWITCH)?|ATS|BATS|MTS|CTTS)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (light switch plate, standard circuit breaker without transfer, network Ethernet switch)
    negative_pattern = re.compile(
        r'\b(?:LIGHT\s+SWITCH|ETHERNET\s+SWITCH|NETWORK\s+SWITCH|PUSH\s+BUTTON\s+SWITCH)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:ATS|BATS|MTS|CTTS|COS)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    amp_pattern = re.compile(
        r'\b(?:(\d{2,4})\s*A(?:MPS?|MPERES?)?|RATING\s*[:=]?\s*(\d{2,4})\s*A)\b',
        re.IGNORECASE
    )

    pole_pattern = re.compile(
        r'\b([34])[- ]?P(?:OLES?)?\b',
        re.IGNORECASE
    )

    ka_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*KA)\b',
        re.IGNORECASE
    )

    ip_pattern = re.compile(
        r'\b(IP\s*31|IP\s*54|IP\s*65)\b',
        re.IGNORECASE
    )

    for prim in primitives:
        text = str(prim.get("text", "")).strip()
        if not text:
            continue

        if negative_pattern.search(text):
            continue

        if not keyword_pattern.search(text):
            continue

        upper_text = text.upper()

        # Classify element_type
        if "BYPASS" in upper_text or "BATS" in upper_text:
            element_type = "BYPASS_ISOLATION_ATS"
        elif "CLOSED TRANSITION" in upper_text or "CTTS" in upper_text or "MAKE-BEFORE-BREAK" in upper_text:
            element_type = "CLOSED_TRANSITION_TRANSFER_SWITCH"
        elif "MANUAL" in upper_text or "MTS" in upper_text:
            element_type = "MANUAL_TRANSFER_SWITCH"
        elif "LOAD SHED" in upper_text or "PRIORITY" in upper_text:
            element_type = "LOAD_SHED_PRIORITY_CONTROLLER"
        else:
            element_type = "STANDARD_AUTOMATIC_TRANSFER_SWITCH"

        # Transition type
        if element_type == "CLOSED_TRANSITION_TRANSFER_SWITCH" or "CLOSED" in upper_text:
            transition_type = "CLOSED_TRANSITION"
        elif "DELAYED" in upper_text:
            transition_type = "DELAYED_TRANSITION"
        else:
            transition_type = "OPEN_TRANSITION"

        # Rated current in amperes
        rated_current_amperes = 400
        amp_match = amp_pattern.search(text)
        if amp_match:
            val_a = amp_match.group(1) or amp_match.group(2)
            if val_a:
                a_int = int(val_a)
                if a_int in (63, 100, 125, 160, 200, 250, 400, 630, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000):
                    rated_current_amperes = a_int
                elif 50 <= a_int <= 5000:
                    rated_current_amperes = a_int

        # Number of poles
        num_poles = 4
        pole_match = pole_pattern.search(text)
        if pole_match:
            num_poles = int(pole_match.group(1))

        # Short circuit withstand kA
        short_circuit_withstand_ka = 65
        ka_match = ka_pattern.search(text)
        if ka_match:
            short_circuit_withstand_ka = int(ka_match.group(1))

        # Enclosure rating
        enclosure_rating = "IP31_INDOOR"
        ip_match = ip_pattern.search(text)
        if ip_match:
            ip_str = ip_match.group(1).upper().replace(" ", "")
            if ip_str == "IP54":
                enclosure_rating = "IP54_WEATHERPROOF"
            elif ip_str == "IP65":
                enclosure_rating = "IP65_HARSH"
            else:
                enclosure_rating = "IP31_INDOOR"
        elif "WEATHERPROOF" in upper_text or "OUTDOOR" in upper_text:
            enclosure_rating = "IP54_WEATHERPROOF"

        # Bypass isolation flag
        has_bypass_isolation = bool(
            element_type == "BYPASS_ISOLATION_ATS" or
            "BYPASS" in upper_text or
            "ISOLATION" in upper_text
        )

        # Generator start contacts
        has_generator_start_contacts = bool(
            "GEN" in upper_text or
            "ENGINE" in upper_text or
            "START" in upper_text or
            element_type in ("STANDARD_AUTOMATIC_TRANSFER_SWITCH", "BYPASS_ISOLATION_ATS", "CLOSED_TRANSITION_TRANSFER_SWITCH")
        )

        # Tag
        tag = None
        tag_match = tag_pattern.search(text)
        if tag_match:
            tag = tag_match.group(1).upper()

        x = float(prim.get("x", 0.0))
        y = float(prim.get("y", 0.0))
        snapped_pt = snap_point_to_grid(x, y, tolerance)

        confidence = 0.85
        if tag:
            confidence += 0.05
        if amp_match:
            confidence += 0.05
        if ka_match or pole_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = AutomaticTransferSwitchCandidate(
            candidate_id=f"cand_ats_{uuid4().hex[:8]}",
            element_type=element_type,
            rated_current_amperes=rated_current_amperes,
            num_poles=num_poles,
            transition_type=transition_type,
            enclosure_rating=enclosure_rating,
            short_circuit_withstand_ka=short_circuit_withstand_ka,
            has_bypass_isolation=has_bypass_isolation,
            has_generator_start_contacts=has_generator_start_contacts,
            tag=tag,
            raw_annotation=text,
            snapped_grid_pt=snapped_pt,
            source_primitive_id=str(prim.get("id", f"prim_{uuid4().hex[:6]}")),
            confidence=confidence,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(candidate)

    return candidates
