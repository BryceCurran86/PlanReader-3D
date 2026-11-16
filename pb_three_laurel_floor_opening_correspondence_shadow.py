"""Read-only room boundary opening witnesses from native PDF source receipts.

A source-owned window restores *topological room enclosure*, not solid wall
material. Swing/slider/garage openings mark thresholds, not floor-through
areas. This module never approves source area, wall paint or customer rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeAlias

from pb_source_internal_swing_room_barrier import SourceInternalSwingRoomBarrier
from pb_source_window_footprint_continuity import WindowFootprintBridge
from pb_source_garage_door_footprint_continuity import GarageDoorFootprintBridge
from pb_source_swing_door_footprint_continuity import ExteriorSwingDoorFootprintBridge
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    FloorWallCandidateReceipt,
)

SourceOpening: TypeAlias = (
    WindowFootprintBridge
    | GarageDoorFootprintBridge
    | ExteriorSwingDoorFootprintBridge
    | ExteriorSlidingDoorFootprintBridge
    | SourceInternalSwingRoomBarrier
)


@dataclass(frozen=True)
class FloorOpeningBoundaryWitness:
    room_label: str
    floor_candidate_path_id: int
    room_side: str
    opening_kind: str
    passage_role: str
    opening_source_path_ids: tuple[int, ...]
    opening_host_path_ids: tuple[int, int]
    opening_bounds_pdf_pts: tuple[float, float, float, float]
    supported_gap_interval_pdf_pts: tuple[float, float]
    supported_gap_length_pdf_pt: float
    source_page_index: int
    boundary_distance_pdf_pt: float
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "room_label": self.room_label,
            "floor_candidate_path_id": self.floor_candidate_path_id,
            "room_side": self.room_side,
            "opening_kind": self.opening_kind,
            "passage_role": self.passage_role,
            "opening_source_path_ids": list(self.opening_source_path_ids),
            "opening_host_path_ids": list(self.opening_host_path_ids),
            "opening_bounds_pdf_pts": list(self.opening_bounds_pdf_pts),
            "supported_gap_interval_pdf_pts": list(self.supported_gap_interval_pdf_pts),
            "supported_gap_length_pdf_pt": round(self.supported_gap_length_pdf_pt, 3),
            "source_page_index": self.source_page_index,
            "boundary_distance_pdf_pt": round(self.boundary_distance_pdf_pt, 3),
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _identity(
    opening: SourceOpening,
) -> tuple[str, str, tuple[int, int], tuple[int, ...]] | None:
    if isinstance(opening, SourceInternalSwingRoomBarrier):
        return (
            "internal_hinged_swing_door",
            "doorway_threshold_not_solid_wall",
            (opening.first_host_path_id, opening.second_host_path_id),
            (opening.swing_arc_path_id, *opening.jamb_cap_path_ids),
        )
    if isinstance(opening, WindowFootprintBridge):
        return (
            "fixed_window",
            "closed_room_edge_not_opaque_wall",
            (opening.left_host_path_id, opening.right_host_path_id),
            tuple(opening.marker_path_ids),
        )
    if isinstance(opening, GarageDoorFootprintBridge):
        return (
            "garage_panel_lift_door",
            "doorway_threshold_not_solid_wall",
            (opening.start_host_path_id, opening.end_host_path_id),
            tuple(opening.jamb_cap_path_ids),
        )
    if isinstance(opening, ExteriorSwingDoorFootprintBridge):
        return (
            "hinged_swing_door",
            "doorway_threshold_not_solid_wall",
            (opening.first_host_path_id, opening.second_host_path_id),
            (opening.swing_arc_path_id, *opening.jamb_cap_path_ids),
        )
    if isinstance(opening, ExteriorSlidingDoorFootprintBridge):
        return (
            "asd_sgd_sliding_door",
            "doorway_threshold_not_solid_wall",
            (opening.first_host_path_id, opening.second_host_path_id),
            (*opening.jamb_cap_path_ids, *opening.sliding_track_path_ids),
        )
    return None


def match_source_exterior_openings_to_floor_wall_gaps(
    receipt: FloorWallCandidateReceipt,
    openings: Sequence[SourceOpening],
    *,
    boundary_tolerance_pdf_pt: float = 0.75,
    min_overlap_pdf_pt: float = 0.5,
) -> tuple[FloorOpeningBoundaryWitness, ...]:
    """Intersect existing native opening receipts with an *uncovered* floor edge.

    Only typed, explicitly page-matched original source-aperture receipts
    produced by the native detectors can match. No guessed opening, snap,
    addition to solid-wall support, physical-face seal or commercial output.
    """
    if receipt.floor_candidate_native_path_id is None or receipt.page_index < 0:
        return ()
    if not receipt.wall_face_candidates:
        return ()
    hits: list[FloorOpeningBoundaryWitness] = []
    for face in receipt.wall_face_candidates:
        if not face.uncovered_intervals_pdf_pt:
            continue
        a, b = face.from_pdf_pt, face.to_pdf_pt
        h = abs(a[1] - b[1]) <= 0.2 and abs(a[0] - b[0]) > 1
        v = abs(a[0] - b[0]) <= 0.2 and abs(a[1] - b[1]) > 1
        if not (h or v):
            continue
        axis = "h" if h else "v"
        position = a[1] if h else a[0]
        for opening in openings:
            identity = _identity(opening)
            if identity is None or opening.page_index != receipt.page_index:
                continue
            if opening.measurement_authorized or opening.physical_wall_authenticated:
                # Receipt types in this lane are strictly non-commercial.
                continue
            if opening.axis != axis:
                continue
            kind, role, hosts, evidence_paths = identity
            if hosts[0] == hosts[1] or min(hosts) < 0 or not evidence_paths:
                continue
            # A coincident graphic on the same sheet is not automatically
            # the room's opening. Require original host paths to be shared
            # with *this exact physical wall-face segment*, not merely
            # with a similarly labelled room or neighbouring viewport.
            # Fixed windows need both side-wall hosts; a threshold may
            # adjoin the room through one host and extend into an
            # independently hosted exterior wall/door frame.
            shared_hosts = set(hosts).intersection(face.supporting_native_wall_paths)
            required_hosts = 2 if kind == "fixed_window" else 1
            if len(shared_hosts) < required_hosts:
                continue
            x0, y0, x1, y1 = opening.bounds_pdf_pts
            if not x0 < x1 or not y0 < y1:
                continue
            if h:
                distance = min(abs(position - y0), abs(position - y1))
                start, end = x0, x1
            else:
                distance = min(abs(position - x0), abs(position - x1))
                start, end = y0, y1
            if distance > boundary_tolerance_pdf_pt:
                continue
            for lower, upper in face.uncovered_intervals_pdf_pt:
                overlap_start = max(lower, start)
                overlap_end = min(upper, end)
                overlap = overlap_end - overlap_start
                if overlap < min_overlap_pdf_pt:
                    continue
                hits.append(
                    FloorOpeningBoundaryWitness(
                        room_label=receipt.label,
                        floor_candidate_path_id=receipt.floor_candidate_native_path_id,
                        room_side=face.side,
                        opening_kind=kind,
                        passage_role=role,
                        opening_source_path_ids=tuple(sorted(set(evidence_paths))),
                        opening_host_path_ids=hosts,
                        opening_bounds_pdf_pts=opening.bounds_pdf_pts,
                        supported_gap_interval_pdf_pts=(overlap_start, overlap_end),
                        supported_gap_length_pdf_pt=overlap,
                        source_page_index=opening.page_index,
                        boundary_distance_pdf_pt=distance,
                    )
                )
    # Never silently choose the first of two source apertures claiming
    # overlapping pieces of the same floor candidate edge. That means
    # their opening identities or host owners are still in competition.
    unique = {
        (
            h.room_side,
            h.opening_kind,
            h.opening_host_path_ids,
            h.supported_gap_interval_pdf_pts,
        ): h
        for h in hits
    }
    candidates = tuple(unique.values())
    accepted = []
    for h in candidates:
        competing = any(
            other is not h
            and other.room_side == h.room_side
            and (other.opening_kind, other.opening_host_path_ids)
            != (h.opening_kind, h.opening_host_path_ids)
            and min(
                other.supported_gap_interval_pdf_pts[1],
                h.supported_gap_interval_pdf_pts[1],
            )
            - max(
                other.supported_gap_interval_pdf_pts[0],
                h.supported_gap_interval_pdf_pts[0],
            )
            > min_overlap_pdf_pt
            for other in candidates
        )
        if not competing:
            accepted.append(h)
    return tuple(
        sorted(
            accepted,
            key=lambda z: (
                z.room_side,
                z.supported_gap_interval_pdf_pts[0],
                z.supported_gap_interval_pdf_pts[1],
                z.opening_kind,
            ),
        )
    )
