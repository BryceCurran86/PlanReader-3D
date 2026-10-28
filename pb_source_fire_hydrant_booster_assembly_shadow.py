"""Underground Water Main Fire Hydrant Booster Assembly & Storz Connections Shadow Authority.

Deterministic shadow extraction authority for external fire hydrant booster
assemblies, Storz inlet connections, cabinets/enclosures, and backflow preventers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FireHydrantBoosterCandidate:
    """Extracted fire hydrant booster assembly candidate."""
    item_id: str
    assembly_type: str  # "CABINET_ENCLOSURE", "WALL_MOUNTED", "PILLAR_HYDRANT", "TANK_INLET", "STANDARD"
    tag: str
    inlet_outlets_count: Optional[int]
    coupling_type: str  # "STORZ", "BIC", "NST", "THREADED", "STANDARD"
    main_pipe_size_mm: Optional[int]
    has_cabinet_enclosure: bool
    backflow_device_type: Optional[str]  # "RPZD", "DCV", "NONE"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "assembly_type": self.assembly_type,
            "tag": self.tag,
            "inlet_outlets_count": self.inlet_outlets_count,
            "coupling_type": self.coupling_type,
            "main_pipe_size_mm": self.main_pipe_size_mm,
            "has_cabinet_enclosure": self.has_cabinet_enclosure,
            "backflow_device_type": self.backflow_device_type,
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


def extract_fire_hydrant_booster_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[FireHydrantBoosterCandidate]:
    """Extract fire hydrant booster candidates deterministically."""
    results: List[FireHydrantBoosterCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:FHB|HBA|FBA|HB|FH|FDC)(?:[-_]?[A-Z0-9]{1,4})?)\b", re.IGNORECASE)
    inlets_pattern = re.compile(r"\b([2-8])[-\s]*(?:WAY|PORT|STORZ|INLET|OUTLET)S?\b", re.IGNORECASE)
    pipe_size_pattern = re.compile(r"\b(?:DN|DIA|O)?\s*(250|200|150|100|80|65)\s*(?:MM|DIA|DN)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"fhb_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE HOSE REEL", "FHR-", "INTERNAL HOSE REEL",
            "DOMESTIC WATER METER", "POTABLE WATER METER",
            "GAS REGULATOR", "GAS METER BOX", "IRRIGATION BACKFLOW"
        ]):
            continue

        is_booster = any(k in upper_text for k in [
            "HYDRANT BOOSTER", "FIRE BOOSTER", "STORZ", "FIRE BRIGADE BOOSTER",
            "PILLAR HYDRANT", "FIRE DEPARTMENT CONNECTION", "FDC", "FIRE HYDRANT MANIFOLD"
        ]) or (tag_pattern.search(text) is not None and ("BOOSTER" in upper_text or "HYDRANT" in upper_text or "STORZ" in upper_text))

        if not is_booster:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "FHB-ITEM"

        # Cabinet enclosure
        has_cabinet_enclosure = any(c in upper_text for c in [
            "CABINET", "KIOSK", "ENCLOSURE", "VIEWING PANEL", "FREESTANDING CABINET"
        ])

        # Assembly type
        assembly_type = "CABINET_ENCLOSURE" if has_cabinet_enclosure else "STANDARD"
        if "PILLAR" in upper_text or "STANDPIPE" in upper_text:
            assembly_type = "PILLAR_HYDRANT"
        elif "WALL MOUNT" in upper_text or "RECESSED" in upper_text or "FACADE" in upper_text:
            assembly_type = "WALL_MOUNTED"
        elif "TANK INLET" in upper_text or "SUCTION BOOSTER" in upper_text:
            assembly_type = "TANK_INLET"
        elif has_cabinet_enclosure:
            assembly_type = "CABINET_ENCLOSURE"

        # Inlets / Outlets count
        inlet_outlets_count: Optional[int] = None
        inlets_match = inlets_pattern.search(text)
        if inlets_match:
            inlet_outlets_count = int(inlets_match.group(1))

        # Coupling Type
        coupling_type = "STORZ"
        if "BIC" in upper_text or "BRITISH INSTANTANEOUS" in upper_text:
            coupling_type = "BIC"
        elif "NST" in upper_text or "NATIONAL STANDARD" in upper_text:
            coupling_type = "NST"
        elif "THREADED" in upper_text or "BSP" in upper_text:
            coupling_type = "THREADED"
        elif "STORZ" in upper_text:
            coupling_type = "STORZ"

        # Main Pipe Size
        main_pipe_size_mm: Optional[int] = None
        pipe_matches = list(pipe_size_pattern.finditer(text))
        for match in pipe_matches:
            val = int(match.group(1))
            if val in [65, 80, 100, 150, 200, 250]:
                if main_pipe_size_mm is None or val > main_pipe_size_mm:
                    main_pipe_size_mm = val

        # Backflow device
        backflow_device_type: Optional[str] = None
        if "RPZD" in upper_text or "REDUCED PRESSURE" in upper_text:
            backflow_device_type = "RPZD"
        elif "DCV" in upper_text or "DOUBLE CHECK" in upper_text:
            backflow_device_type = "DCV"
        elif "BACKFLOW" in upper_text:
            backflow_device_type = "RPZD"

        candidate = FireHydrantBoosterCandidate(
            item_id=item_id,
            assembly_type=assembly_type,
            tag=tag,
            inlet_outlets_count=inlet_outlets_count,
            coupling_type=coupling_type,
            main_pipe_size_mm=main_pipe_size_mm,
            has_cabinet_enclosure=has_cabinet_enclosure,
            backflow_device_type=backflow_device_type,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results