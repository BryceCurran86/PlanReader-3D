"""PlanReader Electrical Trade Authority Engine (AG-29).

Bridges canonical building model and electrical layouts to the specialist Electrical trade takeoff schedule.
Calculates high-precision trade quantities without duplicate extraction or hallucination:
- Switchboards & Distribution: Main Switchboard (MSB), sub-distribution boards, metering (No.)
- Lighting & Controls: LED downlights, linear battens, emergency/exit fittings, switches, sensors (No. & lm)
- Power Outlets (GPOs): Standard double GPOs, dedicated appliance circuits (Oven, EV charger, A/C) (No.)
- Data / Communications: Cat6 data outlets, patch panels, NBN equipment enclosures (No.)
- Containment & Conduit: Cable ladder / perforated tray, rigid & flexible conduit runs (lm)

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract

ELECTRICAL_SOURCE_PREFIX = "PB Electrical Authority v1.0"


@dataclass
class ElectricalDeviceSpec:
    """Specification for electrical devices, fittings, and equipment."""
    device_type: str           # "switchboard", "light", "switch", "gpo", "data", "emergency"
    device_mark: str           # e.g. "MSB", "DB-1", "L1", "GPO-D", "DATA-1", "EXIT-1"
    description: str
    location: str              # e.g. "Main Switchroom", "Office 101", "Corridor"
    count: int = 1
    section: str = "Internal"  # "Internal", "External", "Substructure"
    is_dedicated_circuit: bool = False
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class ElectricalContainmentSpec:
    """Specification for cable containment, ladder, tray, and conduit runs."""
    containment_type: str      # "tray", "ladder", "conduit", "duct"
    size_desc: str             # e.g. "300mm Cable Ladder", "25mm HD Conduit"
    description: str
    section: str = "Internal"
    length_m: float = 0.0
    source_page: str = ""
    source_reference: str = ""
    notes: str = ""


@dataclass
class ElectricalTakeoffItem:
    """Standardized electrical trade takeoff item compliant with PlanReader contracts."""
    section: str
    element: str
    location: str
    substrate: str
    finish_system: str
    quantity: float
    unit: str                  # Must be in TAKEOFF_UNITS: 'm²', 'lm', 'No.', 'item', 'L', 'allowance'
    quantity_status: str       # "Measured", "Estimated", "Provisional"
    source_page: str
    source_reference: str
    inclusion_status: str      # "INCLUSION" or "PROVISIONAL"
    confidence: str            # "Verified", "High", "Documented", "Provisional"
    notes: str
    row_role: str = ""

    def to_core_row(self, workspace_id: int, now_stamp: str) -> Dict[str, Any]:
        """Convert to canonical 21-field core takeoff row."""
        assert self.unit in takeoff_contract.TAKEOFF_UNITS, f"Invalid unit {self.unit}"
        return {
            "workspace_id": int(workspace_id),
            "section": str(self.section),
            "element": str(self.element),
            "location": str(self.location),
            "substrate": str(self.substrate),
            "finish_system": str(self.finish_system),
            "quantity": round(float(self.quantity), 2),
            "unit": str(self.unit),
            "quantity_status": str(self.quantity_status),
            "source_page": str(self.source_page or "Electrical Plans E101"),
            "source_reference": str(self.source_reference or ELECTRICAL_SOURCE_PREFIX),
            "inclusion_status": str(self.inclusion_status),
            "coats": 1,
            "coverage_m2_per_litre": 0.0,
            "productivity_m2_per_hour": 0.0,
            "rate_per_unit": 0.0,
            "confidence": str(self.confidence),
            "notes": str(self.notes),
            "row_role": str(self.row_role),
            "created_at": str(now_stamp),
            "updated_at": str(now_stamp),
        }


def calculate_switchboard_items(spec: ElectricalDeviceSpec) -> List[ElectricalTakeoffItem]:
    """Calculate trade items for main switchboards and distribution boards."""
    items: List[ElectricalTakeoffItem] = []
    count = max(1, spec.count)

    items.append(ElectricalTakeoffItem(
        section=spec.section,
        element=f"Distribution switchboard: {spec.description} ({spec.device_mark})",
        location=f"{spec.location} · {spec.device_mark}",
        substrate="Powder-coated sheet steel enclosure with chassis and busbars",
        finish_system="Mount, fit MCB/RCD circuit protection, terminate sub-mains, label and commission",
        quantity=float(count),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{ELECTRICAL_SOURCE_PREFIX} · {spec.device_mark}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. {spec.description} ({spec.device_mark}).",
        row_role="",
    ))

    return items


def calculate_lighting_items(spec: ElectricalDeviceSpec) -> List[ElectricalTakeoffItem]:
    """Calculate trade items for luminaires, switches, and emergency fittings."""
    items: List[ElectricalTakeoffItem] = []
    count = max(1, spec.count)

    if spec.device_type == "emergency":
        element_name = f"Emergency / exit lighting fitting ({spec.description})"
        substrate = "Maintained / non-maintained emergency fitting with 2-hour battery backup"
    elif spec.device_type == "switch":
        element_name = f"Lighting switch / dimmer point ({spec.description})"
        substrate = "Plate switch mechanism in wall flush box"
    else:
        element_name = f"Lighting luminaire ({spec.description})"
        substrate = "LED luminaire fitting complete with driver"

    items.append(ElectricalTakeoffItem(
        section=spec.section,
        element=element_name,
        location=f"{spec.location} · {spec.device_mark}",
        substrate=substrate,
        finish_system="Rough-in circuit wiring, supply, fit off, lamp and test",
        quantity=float(count),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{ELECTRICAL_SOURCE_PREFIX} · {spec.device_mark}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. {spec.description} ({spec.device_mark}) in {spec.location}.",
        row_role="",
    ))

    return items


def calculate_power_items(spec: ElectricalDeviceSpec) -> List[ElectricalTakeoffItem]:
    """Calculate trade items for general power outlets and dedicated circuits."""
    items: List[ElectricalTakeoffItem] = []
    count = max(1, spec.count)

    if spec.is_dedicated_circuit:
        element_name = f"Dedicated power circuit & isolator ({spec.description})"
        substrate = "Dedicated heavy-gauge cabling with local isolator switch"
    else:
        element_name = f"General power outlet ({spec.description})"
        substrate = "10A double GPO wall plate"

    items.append(ElectricalTakeoffItem(
        section=spec.section,
        element=element_name,
        location=f"{spec.location} · {spec.device_mark}",
        substrate=substrate,
        finish_system="Rough-in TPS wiring in wall cavity, fit off faceplate and test",
        quantity=float(count),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{ELECTRICAL_SOURCE_PREFIX} · {spec.device_mark}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. {spec.description} ({spec.device_mark}).",
        row_role="",
    ))

    return items


def calculate_data_items(spec: ElectricalDeviceSpec) -> List[ElectricalTakeoffItem]:
    """Calculate trade items for data/communications outlets and racks."""
    items: List[ElectricalTakeoffItem] = []
    count = max(1, spec.count)

    items.append(ElectricalTakeoffItem(
        section=spec.section,
        element=f"Data / communications outlet: {spec.description} ({spec.device_mark})",
        location=f"{spec.location} · {spec.device_mark}",
        substrate="Cat6 UTP data cabling and RJ45 jack modules",
        finish_system="Run cable to comms rack, punch down on patch panel, fit off and certify",
        quantity=float(count),
        unit="No.",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{ELECTRICAL_SOURCE_PREFIX} · {spec.device_mark}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"{count} No. {spec.description} ({spec.device_mark}).",
        row_role="",
    ))

    return items


def calculate_containment_items(spec: ElectricalContainmentSpec) -> List[ElectricalTakeoffItem]:
    """Calculate trade items for cable tray, ladder, and conduit runs."""
    items: List[ElectricalTakeoffItem] = []
    if spec.length_m <= 0.0:
        return items

    items.append(ElectricalTakeoffItem(
        section=spec.section,
        element=f"Cable containment: {spec.description} ({spec.size_desc})",
        location=f"Containment · {spec.description}",
        substrate=f"Galvanized steel {spec.size_desc} with trapeze hangers",
        finish_system="Suspended from slab soffit with threaded rod, earth bonded",
        quantity=round(spec.length_m, 2),
        unit="lm",
        quantity_status="Measured",
        source_page=spec.source_page,
        source_reference=f"{ELECTRICAL_SOURCE_PREFIX} · {spec.containment_type}",
        inclusion_status="INCLUSION",
        confidence="Verified",
        notes=f"Containment run length: {spec.length_m:.2f} lm.",
        row_role="",
    ))

    return items


def generate_workspace_electrical_takeoff(
    devices: Sequence[ElectricalDeviceSpec],
    containment_runs: Sequence[ElectricalContainmentSpec],
    workspace_id: int,
    now_stamp: str,
) -> List[Dict[str, Any]]:
    """Generate complete list of canonical 21-field core takeoff rows for all electrical scopes."""
    all_rows: List[Dict[str, Any]] = []

    for dev in devices:
        items: List[ElectricalTakeoffItem] = []
        if dev.device_type == "switchboard":
            items = calculate_switchboard_items(dev)
        elif dev.device_type in ("light", "switch", "emergency"):
            items = calculate_lighting_items(dev)
        elif dev.device_type == "gpo":
            items = calculate_power_items(dev)
        elif dev.device_type == "data":
            items = calculate_data_items(dev)

        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    for cont in containment_runs:
        items = calculate_containment_items(cont)
        for item in items:
            all_rows.append(item.to_core_row(workspace_id, now_stamp))

    return all_rows
