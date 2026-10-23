"""
Source Electrical Substation Transformer Bund Oil Containment Sump Shadow Authority.

Extracts and validates electrical transformer oil containment bunds, oil/water separator sumps,
flame trap gravel beds, optical oil sensors, and fail-safe pneumatic shutoff valves strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class TransformerOilBundSumpCallout:
    raw_text: str
    containment_type: str
    bund_capacity_litres: Optional[float]
    flame_trap_medium: str
    oil_sensor_shutoff: str
    bund_wall_height_mm: Optional[float]
    transformer_kva_rating: Optional[str]
    dielectric_fluid_type: str
    position: Tuple[float, float] = (0.0, 0.0)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def snap_point(x: float, y: float, snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap coordinates to discrete precision grid."""
    if snap_tol <= 0.0:
        return (x, y)
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_transformer_oil_bund_sump_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "TRANSFORMER BUND",
        "OIL BUND",
        "OIL CONTAINMENT",
        "TRANSFORMER SUMP",
        "OIL SPILL BUND",
        "FLAME TRAP",
        "OIL/WATER SEPARATOR SUMP",
        "OIL-WATER SEPARATOR SUMP",
        "TRANSFORMER COMPOUND BUND",
        "DIELECTRIC OIL CONTAINMENT",
        "TRANSFORMER SPILL BASIN",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("TRANSFORMER" in upper or "SUBSTATION" in upper)
        and ("BUND" in upper or "OIL CONTAINMENT" in upper or "OIL SUMP" in upper or "SPILL BASIN" in upper or "FLAME TRAP" in upper)
    )
    if not has_trigger:
        return None

    # Containment Type
    if any(k in upper for k in ["SEPARATOR SUMP", "OIL/WATER", "OIL-WATER", "DRAINAGE SUMP"]):
        containment_type = "OIL_WATER_SEPARATOR_SUMP"
    elif any(k in upper for k in ["FLAME TRAP", "FIRE QUENCHING", "QUENCHING BAFFLE"]):
        containment_type = "FIRE_QUENCHING_FLAME_TRAP"
    elif any(k in upper for k in ["POLY BUND", "PREFABRICATED BUND", "POLYETHYLENE CONTAINMENT"]):
        containment_type = "INTEGRAL_POLY_CONTAINMENT_BASIN"
    elif any(k in upper for k in ["BUND WALL", "PERIMETER BUND", "CONCRETE BUND"]):
        containment_type = "TRANSFORMER_OIL_BUND_WALL"
    else:
        containment_type = "GENERIC_OIL_SPILL_BUND"

    # Bund Capacity (Litres or converted Gallons)
    bund_capacity_l: Optional[float] = None
    litres_m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{3,6})\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    if litres_m:
        bund_capacity_l = float(litres_m.group(1).replace(",", ""))
    else:
        gal_m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{3,5})\s*(?:GAL|GALLONS?)\b", upper)
        if gal_m:
            bund_capacity_l = round(float(gal_m.group(1).replace(",", "")) * 3.78541, 1)

    # Flame Trap Medium
    if any(k in upper for k in ["GRAVEL", "CRUSHED ROCK", "AGGREGATE BED", "STONE BED"]):
        flame_trap = "WASHED_CRUSHED_GRAVEL_BED"
    elif any(k in upper for k in ["ALUMINUM BAFFLE", "ALUMINIUM BAFFLE", "QUENCHING BAFFLE"]):
        flame_trap = "ALUMINUM_FLAME_QUENCHING_BAFFLES"
    elif any(k in upper for k in ["FIRE RETARDANT GRATE", "FIRE RETARDANT GRATING", "FIRE RETARDANT", "FIBERGLASS GRATING", "STEEL GRATING"]):
        flame_trap = "FIRE_RETARDANT_GRATING"
    else:
        flame_trap = "UNSPECIFIED"

    # Oil Sensor / Fail-Safe Shutoff
    if any(k in upper for k in ["OIL SENSOR", "OPTICAL SENSOR", "OPTICAL PROBE", "OIL DETECTOR", "OIL DETECTION"]):
        sensor_shutoff = "OIL_DETECTION_OPTICAL_SENSOR"
    elif any(k in upper for k in ["FAIL-SAFE VALVE", "PNEUMATIC SHUTOFF", "FAIL SAFE VALVE", "SHUTOFF VALVE"]):
        sensor_shutoff = "PNEUMATIC_FAIL_SAFE_SHUTOFF_VALVE"
    elif any(k in upper for k in ["FLOAT SWITCH", "LEVEL SWITCH", "ALARM SWITCH"]):
        sensor_shutoff = "OIL_SPILL_FLOAT_SWITCH"
    else:
        sensor_shutoff = "UNSPECIFIED"

    # Bund Wall Height (mm)
    wall_height_mm: Optional[float] = None
    wh_m = re.search(r"(\d{3,4})\s*MM\s*(?:HIGH|HEIGHT|DEEP|BUND\s*WALL)", upper)
    if wh_m:
        wall_height_mm = float(wh_m.group(1))

    # Transformer kVA / MVA Rating
    kva_m = re.search(r"\b(\d+(?:\.\d+)?\s*(?:KVA|MVA))\b", upper)
    transformer_rating = kva_m.group(1).replace(" ", "") if kva_m else None

    # Dielectric Fluid Type
    if any(k in upper for k in ["FR3", "NATURAL ESTER", "VEGETABLE OIL"]):
        fluid_type = "NATURAL_ESTER_FR3"
    elif any(k in upper for k in ["SYNTHETIC ESTER", "MIDEL"]):
        fluid_type = "SYNTHETIC_ESTER_FLUID"
    elif any(k in upper for k in ["SILICONE OIL", "SILICONE FLUID"]):
        fluid_type = "SILICONE_OIL"
    elif any(k in upper for k in ["MINERAL OIL", "INSULATING OIL", "TRANSFORMER OIL"]):
        fluid_type = "MINERAL_INSULATING_OIL"
    else:
        fluid_type = "UNSPECIFIED"

    return {
        "raw_text": clean,
        "containment_type": containment_type,
        "bund_capacity_litres": bund_capacity_l,
        "flame_trap_medium": flame_trap,
        "oil_sensor_shutoff": sensor_shutoff,
        "bund_wall_height_mm": wall_height_mm,
        "transformer_kva_rating": transformer_rating,
        "dielectric_fluid_type": fluid_type,
    }


def extract_transformer_oil_bund_sump_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[TransformerOilBundSumpCallout]:
    results: List[TransformerOilBundSumpCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_transformer_oil_bund_sump_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = TransformerOilBundSumpCallout(
            raw_text=parsed["raw_text"],
            containment_type=parsed["containment_type"],
            bund_capacity_litres=parsed["bund_capacity_litres"],
            flame_trap_medium=parsed["flame_trap_medium"],
            oil_sensor_shutoff=parsed["oil_sensor_shutoff"],
            bund_wall_height_mm=parsed["bund_wall_height_mm"],
            transformer_kva_rating=parsed["transformer_kva_rating"],
            dielectric_fluid_type=parsed["dielectric_fluid_type"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_flame_trap": parsed["flame_trap_medium"] != "UNSPECIFIED",
                "has_capacity": parsed["bund_capacity_litres"] is not None,
                "has_sensor": parsed["oil_sensor_shutoff"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_transformer_oil_bund_sump_system(
    candidates: List[TransformerOilBundSumpCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    flame_trap_counts: Dict[str, int] = {}
    instrumented_count = 0
    sized_bund_count = 0

    for c in candidates:
        type_counts[c.containment_type] = type_counts.get(c.containment_type, 0) + 1
        flame_trap_counts[c.flame_trap_medium] = flame_trap_counts.get(c.flame_trap_medium, 0) + 1
        if c.oil_sensor_shutoff != "UNSPECIFIED":
            instrumented_count += 1
        if c.bund_capacity_litres is not None:
            sized_bund_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "flame_trap_counts": flame_trap_counts,
        "instrumented_count": instrumented_count,
        "sized_bund_count": sized_bund_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
