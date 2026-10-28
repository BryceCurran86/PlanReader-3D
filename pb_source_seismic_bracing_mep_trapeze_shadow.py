"""Seismic Bracing for Suspended MEP Services & Trapeze Shadow Authority.

Deterministic shadow extraction authority for seismic sway braces, rigid strut restraints,
cable sway braces, and trapeze hanger assemblies for suspended building services.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SeismicBraceCandidate:
    """Extracted seismic brace or trapeze candidate."""
    item_id: str
    brace_orientation: str  # "TRANSVERSE", "LONGITUDINAL", "FOUR_WAY", "STANDARD"
    brace_mechanism: str  # "RIGID_STRUT", "CABLE_SWAY", "ROD_STIFFENER", "STANDARD"
    mep_service: str  # "CABLE_TRAY", "DUCTWORK", "PIPE_RACK", "BUSDUCT", "GENERAL_MEP"
    tag: str
    drop_rod_mm: Optional[int]
    channel_size_mm: Optional[str]  # e.g. "41x41", "41x21", "41x82"
    design_standard: str  # "AS1170_4", "NZS4219", "SMACNA", "ASCE7", "STANDARD"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "brace_orientation": self.brace_orientation,
            "brace_mechanism": self.brace_mechanism,
            "mep_service": self.mep_service,
            "tag": self.tag,
            "drop_rod_mm": self.drop_rod_mm,
            "channel_size_mm": self.channel_size_mm,
            "design_standard": self.design_standard,
            "coordinates": self.coordinates,
            "raw_text": self.raw_text,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap point coordinates to the nearest grid step."""
    return (
        round(round(pt[0] / tolerance) * tolerance, 3),
        round(round(pt[1] / tolerance) * tolerance, 3),
    )


def extract_seismic_braces(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SeismicBraceCandidate]:
    """Extract seismic sway braces and MEP trapeze items deterministically."""
    results: List[SeismicBraceCandidate] = []
    processed_count = 0

    rod_pattern = re.compile(r"\b(?:M(\d{2})|(\d{1,2})\s*MM)\s*(?:THREADED\s*)?(?:DROP\s*)?ROD\b", re.IGNORECASE)
    channel_pattern = re.compile(r"\b(41\s*[xX]\s*(?:41|21|82))\b")
    tag_pattern = re.compile(r"\b((?:SB|SEIS|TR|SWAY|SR)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"seis_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "ROOF TRUSS TIE DOWN ONLY", "WALL TIE", "SEISMIC EXPANSION JOINT ONLY",
            "STRUCTURAL CROSS BRACING ONLY"
        ]):
            continue

        is_seismic_mep = any(k in upper_text for k in [
            "SEISMIC BRACE", "SEISMIC RESTRAINT", "SWAY BRACE", "SEISMIC TRAPEZE",
            "CABLE SWAY BRACE", "TRANSVERSE BRACE", "LONGITUDINAL BRACE",
            "4-WAY SEISMIC", "FOUR-WAY SEISMIC", "MEP SEISMIC"
        ]) or (tag_pattern.search(text) is not None and ("SEISMIC" in upper_text or "SWAY" in upper_text or "TRAPEZE" in upper_text))

        if not is_seismic_mep:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "SEIS-BRACE"

        # Brace orientation
        brace_orientation = "STANDARD"
        if "4-WAY" in upper_text or "4 WAY" in upper_text or "FOUR-WAY" in upper_text:
            brace_orientation = "FOUR_WAY"
        elif "TRANSVERSE" in upper_text:
            brace_orientation = "TRANSVERSE"
        elif "LONGITUDINAL" in upper_text:
            brace_orientation = "LONGITUDINAL"

        # Brace mechanism
        brace_mechanism = "RIGID_STRUT"
        if "CABLE" in upper_text or "AIRCRAFT CABLE" in upper_text:
            brace_mechanism = "CABLE_SWAY"
        elif "ROD STIFFENER" in upper_text:
            brace_mechanism = "ROD_STIFFENER"
        elif "STRUT" in upper_text or "UNISTRUT" in upper_text or "RIGID" in upper_text:
            brace_mechanism = "RIGID_STRUT"

        # MEP Service
        mep_service = "GENERAL_MEP"
        if "BUSDUCT" in upper_text or "BUSWAY" in upper_text:
            mep_service = "BUSDUCT"
        elif "CABLE TRAY" in upper_text or "LADDER TRAY" in upper_text:
            mep_service = "CABLE_TRAY"
        elif "DUCT" in upper_text or "DUCTWORK" in upper_text or "HVAC" in upper_text:
            mep_service = "DUCTWORK"
        elif "PIPE" in upper_text or "PIPING" in upper_text or "CHW" in upper_text:
            mep_service = "PIPE_RACK"

        # Drop rod
        drop_rod_mm: Optional[int] = None
        rod_match = rod_pattern.search(text)
        if rod_match:
            drop_rod_mm = int(rod_match.group(1) or rod_match.group(2))

        # Channel size
        channel_size_mm: Optional[str] = None
        ch_match = channel_pattern.search(text)
        if ch_match:
            channel_size_mm = ch_match.group(1).replace(" ", "").lower()

        # Design standard
        design_standard = "STANDARD"
        if "1170.4" in text or "AS 1170" in upper_text:
            design_standard = "AS1170_4"
        elif "4219" in text or "NZS" in upper_text:
            design_standard = "NZS4219"
        elif "SMACNA" in upper_text:
            design_standard = "SMACNA"
        elif "ASCE" in upper_text or "IBC" in upper_text:
            design_standard = "ASCE7"

        candidate = SeismicBraceCandidate(
            item_id=item_id,
            brace_orientation=brace_orientation,
            brace_mechanism=brace_mechanism,
            mep_service=mep_service,
            tag=tag,
            drop_rod_mm=drop_rod_mm,
            channel_size_mm=channel_size_mm,
            design_standard=design_standard,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
