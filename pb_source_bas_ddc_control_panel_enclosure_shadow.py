"""Building Automation System (BAS/BMS) Direct Digital Controller (DDC) Panel Shadow Authority.

Deterministic shadow extraction authority for building automation DDC panels,
field controller enclosures, BACnet/Modbus modules, remote I/O, and UPS backups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class BASDDCPanelCandidate:
    """Extracted BAS/BMS DDC panel candidate."""
    item_id: str
    panel_type: str  # "MAIN_PLANT_DDC", "FLOOR_DDC", "ROOFTOP_DDC", "REMOTE_IO_PANEL", "STANDARD"
    tag: str
    io_point_capacity: Optional[int]
    ip_rating: str  # "IP54", "IP55", "IP56", "IP65", "IP66", "STANDARD"
    comm_protocol: str  # "BACNET_IP", "BACNET_MSTP", "MODBUS_RTU", "LONWORKS", "STANDARD"
    has_ups_backup: bool
    enclosure_size_desc: Optional[str]  # e.g. "1000x800x300mm"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "panel_type": self.panel_type,
            "tag": self.tag,
            "io_point_capacity": self.io_point_capacity,
            "ip_rating": self.ip_rating,
            "comm_protocol": self.comm_protocol,
            "has_ups_backup": self.has_ups_backup,
            "enclosure_size_desc": self.enclosure_size_desc,
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


def extract_bas_ddc_panel_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[BASDDCPanelCandidate]:
    """Extract BAS/BMS DDC panel candidates deterministically."""
    results: List[BASDDCPanelCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:DDC|BMS[-_]?CP|BMS|BCP|RIO)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    io_pattern = re.compile(r"\b(\d{1,3})\s*(?:I/O|IO|POINT|PTS)\b", re.IGNORECASE)
    size_pattern = re.compile(r"\b(\d{3,4}\s*[xX]\s*\d{3,4}(?:\s*[xX]\s*\d{2,4})?(?:\s*MM)?)\b", re.IGNORECASE)
    ip_pattern = re.compile(r"\b(IP54|IP55|IP56|IP65|IP66)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"ddc_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "MAIN SWITCHBOARD", "MSB-", "DISTRIBUTION BOARD", "DB-",
            "FIRE ALARM", "FACP-", "EWIS", "ACCESS CONTROL PANEL",
            "SECURITY PANEL", "CCTV RACK", "MOTOR CONTROL CENTRE", "MCC-"
        ]):
            continue

        is_ddc = any(k in upper_text for k in [
            "DDC PANEL", "BMS PANEL", "DIRECT DIGITAL CONTROL", "BMS CONTROLLER",
            "DDC CONTROLLER", "BUILDING AUTOMATION", "BMS CONTROL PANEL", "REMOTE I/O"
        ]) or (tag_pattern.search(text) is not None and ("DDC" in upper_text or "BMS" in upper_text or "CONTROLLER" in upper_text or "AUTOMATION" in upper_text or "RIO" in upper_text or "I/O" in upper_text))

        if not is_ddc:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "DDC-PANEL"

        # UPS Backup
        has_ups_backup = any(u in upper_text for u in [
            "UPS", "UNINTERRUPTIBLE POWER", "BATTERY BACKUP"
        ])

        # Communication Protocol
        comm_protocol = "BACNET_IP"
        if "MODBUS" in upper_text:
            comm_protocol = "MODBUS_RTU"
        elif "MS/TP" in upper_text or "MSTP" in upper_text:
            comm_protocol = "BACNET_MSTP"
        elif "LONWORKS" in upper_text or "LON" in upper_text:
            comm_protocol = "LONWORKS"
        elif "BACNET/IP" in upper_text or "BACNET" in upper_text or "IP" in upper_text:
            comm_protocol = "BACNET_IP"

        # Panel Type
        panel_type = "FLOOR_DDC"
        if "MAIN PLANT" in upper_text or "CENTRAL PLANT" in upper_text or "CHILLER" in upper_text or "BOILER" in upper_text:
            panel_type = "MAIN_PLANT_DDC"
        elif "ROOF" in upper_text or "ROOFTOP" in upper_text or "WEATHERPROOF" in upper_text:
            panel_type = "ROOFTOP_DDC"
        elif "REMOTE I/O" in upper_text or "RIO" in upper_text or "EXPANSION" in upper_text or "RIO-" in tag:
            panel_type = "REMOTE_IO_PANEL"
        elif "FLOOR" in upper_text or "LEVEL" in upper_text or "AHU" in upper_text:
            panel_type = "FLOOR_DDC"

        # IP Rating
        ip_rating = "IP54"
        ip_match = ip_pattern.search(text)
        if ip_match:
            ip_rating = ip_match.group(1).upper()
        elif panel_type == "ROOFTOP_DDC" or "OUTDOOR" in upper_text or "WEATHERPROOF" in upper_text:
            ip_rating = "IP65"

        # I/O Capacity
        io_point_capacity: Optional[int] = None
        io_match = io_pattern.search(text)
        if io_match:
            val = int(io_match.group(1))
            if 8 <= val <= 512:
                io_point_capacity = val

        # Enclosure size
        enclosure_size_desc: Optional[str] = None
        sz_match = size_pattern.search(text)
        if sz_match:
            enclosure_size_desc = sz_match.group(1).replace(" ", "")

        candidate = BASDDCPanelCandidate(
            item_id=item_id,
            panel_type=panel_type,
            tag=tag,
            io_point_capacity=io_point_capacity,
            ip_rating=ip_rating,
            comm_protocol=comm_protocol,
            has_ups_backup=has_ups_backup,
            enclosure_size_desc=enclosure_size_desc,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results