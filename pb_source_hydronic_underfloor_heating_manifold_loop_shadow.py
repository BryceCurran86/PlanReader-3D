"""Hydronic Underfloor Heating Manifold & Actuated Circuit Loop Shadow Authority.

Deterministic shadow extraction authority for hydronic underfloor radiant heating/cooling
manifolds, circuit loops, flow meters, actuators, and cabinet enclosures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class HydronicManifoldCandidate:
    """Extracted hydronic heating/cooling manifold candidate."""
    item_id: str
    manifold_tag: str
    circuit_count: Optional[int]
    pipe_material: str  # "PEX_A", "PEX_AL_PEX", "PERT", "STANDARD"
    pipe_diameter_mm: Optional[int]
    has_thermal_actuators: bool
    actuator_voltage: Optional[str]  # "24V", "230V", None
    has_flow_meters: bool
    enclosure_type: str  # "RECESSED_CABINET", "SURFACE_MOUNTED", "STANDARD"
    has_mixing_shunt: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "manifold_tag": self.manifold_tag,
            "circuit_count": self.circuit_count,
            "pipe_material": self.pipe_material,
            "pipe_diameter_mm": self.pipe_diameter_mm,
            "has_thermal_actuators": self.has_thermal_actuators,
            "actuator_voltage": self.actuator_voltage,
            "has_flow_meters": self.has_flow_meters,
            "enclosure_type": self.enclosure_type,
            "has_mixing_shunt": self.has_mixing_shunt,
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


def extract_hydronic_manifolds(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[HydronicManifoldCandidate]:
    """Extract hydronic underfloor heating manifolds deterministically."""
    results: List[HydronicManifoldCandidate] = []
    processed_count = 0

    circuit_pattern = re.compile(r"(\d{1,2})\s*(?:PORT|CIRCUIT|LOOP|WAY)S?\b", re.IGNORECASE)
    pipe_size_pattern = re.compile(r"\b(\d{2})\s*MM\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:MAN|UFH|HM|UFM|RAD)[-_]?\d{1,2}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"hm_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GAS MANIFOLD", "COMPRESSED AIR MANIFOLD", "FIRE SPRINKLER MANIFOLD",
            "POTABLE WATER MANIFOLD", "EXPANSION VESSEL ONLY"
        ]):
            continue

        is_hydronic_manifold = any(k in upper_text for k in [
            "UNDERFLOOR HEATING", "UFH MANIFOLD", "HYDRONIC MANIFOLD",
            "RADIANT HEATING MANIFOLD", "IN-SLAB HEATING", "IN-SCREED HEATING",
            "HEATING MANIFOLD", "COOLING MANIFOLD"
        ]) or (tag_pattern.search(text) is not None and ("MANIFOLD" in upper_text or "LOOP" in upper_text or "UFH" in upper_text))

        if not is_hydronic_manifold:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "UFH-MAN"

        # Circuits
        circuit_count: Optional[int] = None
        c_match = circuit_pattern.search(text)
        if c_match:
            circuit_count = int(c_match.group(1))

        # Pipe material
        pipe_material = "STANDARD"
        if "PEX-AL-PEX" in upper_text or "MULTI-LAYER" in upper_text:
            pipe_material = "PEX_AL_PEX"
        elif "PEX-A" in upper_text or "PEXA" in upper_text:
            pipe_material = "PEX_A"
        elif "PERT" in upper_text or "PE-RT" in upper_text:
            pipe_material = "PERT"

        # Pipe diameter
        pipe_diameter_mm: Optional[int] = None
        p_match = pipe_size_pattern.search(text)
        if p_match:
            pipe_diameter_mm = int(p_match.group(1))

        # Actuators
        has_thermal_actuators = any(a in upper_text for a in ["ACTUATOR", "ELECTRO-THERMAL", "THERMO-ELECTRIC", "ZONE VALVE"])
        actuator_voltage: Optional[str] = None
        if "24V" in upper_text:
            actuator_voltage = "24V"
        elif "230V" in upper_text or "240V" in upper_text:
            actuator_voltage = "230V"

        # Flow meters
        has_flow_meters = any(f in upper_text for f in ["FLOW METER", "SIGHT GLASS", "BALANCING INDICATOR", "FLOW INDICATOR"])

        # Enclosure
        enclosure_type = "STANDARD"
        if "RECESSED" in upper_text or "FLUSH CABINET" in upper_text:
            enclosure_type = "RECESSED_CABINET"
        elif "SURFACE" in upper_text:
            enclosure_type = "SURFACE_MOUNTED"

        # Mixing shunt
        has_mixing_shunt = any(m in upper_text for m in ["SHUNT", "MIXING VALVE", "PUMP SET", "INJECTION PUMP", "TEMPERING VALVE"])

        candidate = HydronicManifoldCandidate(
            item_id=item_id,
            manifold_tag=tag,
            circuit_count=circuit_count,
            pipe_material=pipe_material,
            pipe_diameter_mm=pipe_diameter_mm,
            has_thermal_actuators=has_thermal_actuators,
            actuator_voltage=actuator_voltage,
            has_flow_meters=has_flow_meters,
            enclosure_type=enclosure_type,
            has_mixing_shunt=has_mixing_shunt,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
