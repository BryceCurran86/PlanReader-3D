"""Shadow: page-by-page source-native live trace diagnostics (non-commercial).

Cursor-10 (#4537). Outside vs inside walls, room candidates, temporary doorway
closures, source-path/ABSTAIN receipts and progress. Visual output stays
non-commercial until original issuers verify.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_source_inside_face_thermal_envelope_shadow import (
    InsideFaceThermalEnvelopeShadow,
)
from pb_source_native_exterior_perimeter_graph_shadow import (
    ExteriorPerimeterGraphShadow,
)
from pb_source_native_door_topology_closure_shadow import (
    SourceNativeDoorTopologyClosureCensus,
)


@dataclass(frozen=True)
class SourceNativeLiveTraceDiagnostics:
    page_index: int
    source_sha256: str
    outside_wall_path_ids: tuple[int, ...]
    inside_face_point_count: int
    room_candidate_count: int
    topology_closure_count: int
    abstain_receipts: tuple[str, ...]
    progress: Mapping[str, Any]
    status: str
    reason: str
    commercial_publishable: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "source_sha256": self.source_sha256,
            "outside_wall_path_ids": list(self.outside_wall_path_ids),
            "inside_face_point_count": self.inside_face_point_count,
            "room_candidate_count": self.room_candidate_count,
            "topology_closure_count": self.topology_closure_count,
            "abstain_receipts": list(self.abstain_receipts),
            "progress": dict(self.progress),
            "status": self.status,
            "reason": self.reason,
            "visual_output_non_commercial": True,
            "commercial_publishable": False,
            "measurement_authorized": False,
            "official_frozen120_score_change": 0,
            "color_legend": {
                "outside_walls": "red",
                "inside_walls": "blue",
                "room_candidates": "green",
                "temporary_doorway_closures": "orange",
                "abstain": "magenta",
            },
        }


def build_source_native_live_trace_diagnostics(
    *,
    page_index: int,
    source_sha256: str,
    footprint: ExternalFootprintTrace | None = None,
    perimeter: ExteriorPerimeterGraphShadow | None = None,
    inside_face: InsideFaceThermalEnvelopeShadow | None = None,
    door_closures: SourceNativeDoorTopologyClosureCensus | None = None,
    room_candidate_count: int = 0,
) -> SourceNativeLiveTraceDiagnostics:
    abstains: list[str] = []
    outside_ids: list[int] = []
    if perimeter is not None:
        for edge in perimeter.edges:
            if edge.status.value == "abstained":
                abstains.append(f"edge:{edge.edge_index}:{edge.reason}")
            outside_ids.extend(int(i) for i in edge.native_path_indices)
        for corner in perimeter.corners:
            if corner.status.value == "abstained":
                abstains.append(f"corner:{corner.corner_index}:{corner.joint_kind}")
    if inside_face is not None and inside_face.status == "ABSTAINED":
        abstains.append(f"inside_face:{inside_face.reason}")
    if door_closures is not None and door_closures.status == "ABSTAINED":
        abstains.append(f"door_closures:{door_closures.reason}")
    if footprint is not None and footprint.status != "CANDIDATE":
        abstains.append(f"footprint:{footprint.reason}")

    closure_count = 0
    if door_closures is not None:
        closure_count = (
            len(door_closures.cavity_slider_closures)
            + len(door_closures.sliding_joinery_closures)
        )
    inside_pts = (
        0
        if inside_face is None
        else len(inside_face.inside_face_clockwise_pdf_pts)
    )
    progress = {
        "footprint_candidate": bool(
            footprint is not None and footprint.status == "CANDIDATE"
        ),
        "perimeter_owned_edges": 0 if perimeter is None else perimeter.owned_edge_count,
        "inside_face_candidate": bool(
            inside_face is not None and inside_face.status == "CANDIDATE"
        ),
        "topology_closures": closure_count,
        "room_candidates": int(room_candidate_count),
        "abstain_count": len(abstains),
    }
    return SourceNativeLiveTraceDiagnostics(
        page_index=int(page_index),
        source_sha256=str(source_sha256 or ""),
        outside_wall_path_ids=tuple(sorted(set(outside_ids))),
        inside_face_point_count=inside_pts,
        room_candidate_count=int(room_candidate_count),
        topology_closure_count=closure_count,
        abstain_receipts=tuple(abstains),
        progress=progress,
        status="CANDIDATE",
        reason="source_native_live_trace_diagnostics_non_commercial",
    )
