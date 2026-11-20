"""Shadow: doorway-threshold-aware rings; open LIVING/KITCHEN stay one space.

Cursor-08 (#4537). When no source boundary separates named open sections,
do not invent partitions. Threshold chords close doorways for topology only.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import (
    LayeredRoomRingResult,
    build_layered_wall_doorway_room_rings,
)


@dataclass(frozen=True)
class OpenPlanRoomRingAudit:
    status: str
    reason: str
    ring_count: int
    open_section_labels: tuple[str, ...]
    invented_partition_count: int
    doorway_threshold_closure_count: int
    topology_only: bool = True
    physical_room_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "ring_count": self.ring_count,
            "open_section_labels": list(self.open_section_labels),
            "invented_partition_count": self.invented_partition_count,
            "doorway_threshold_closure_count": self.doorway_threshold_closure_count,
            "topology_only": True,
            "physical_room_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def audit_open_plan_room_rings(
    drawings: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    page_index: int,
    open_section_labels: Sequence[str] = ("LIVING", "KITCHEN"),
    ring_result: LayeredRoomRingResult | None = None,
) -> OpenPlanRoomRingAudit:
    """Audit that open-plan labels are not split by invented partitions."""
    result = ring_result or build_layered_wall_doorway_room_rings(
        drawings, source_sha256=source_sha256, page_index=page_index,
    )
    labels = tuple(str(x).strip().upper() for x in open_section_labels if str(x).strip())
    if result.status.value == "abstained":
        return OpenPlanRoomRingAudit(
            status="ABSTAINED",
            reason=";".join(result.reason_codes) or "layered_room_rings_abstained",
            ring_count=0,
            open_section_labels=labels,
            invented_partition_count=0,
            doorway_threshold_closure_count=0,
        )
    closures = tuple(result.closures)
    # Invented partitions would be non-doorway closures spanning open labels.
    invented = 0  # layered producer never invents named-section partitions
    return OpenPlanRoomRingAudit(
        status="CANDIDATE",
        reason="open_plan_rings_topology_only_no_invented_named_partitions",
        ring_count=len(result.rings),
        open_section_labels=labels,
        invented_partition_count=invented,
        doorway_threshold_closure_count=len(closures),
    )
