"""Fixtures for the post-completeness opening -> host-wall validator.

This module is test support only.  It deliberately distinguishes caller probes
from the future producer-owned host-binding writer/query boundary and reuses the
existing #323 wall-path fingerprint implementation rather than forking it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_hosted_opening_geometry import HostedOpeningSpan
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_wall_identity_v2 import canonical_path_fingerprint


BASE_SHA = "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"
HISTORICAL_334_HEAD = "c1c1ad1a64e7c5c26ee85dc9455c31e4c0c8c0fc"
SHA_A = "a" * 64
SHA_B = "b" * 64
Point = Tuple[float, float]


@dataclass(frozen=True)
class CallerHostBindingProbe:
    """Caller-authored lookalike data; never host-binding authority."""

    opening_record_id: str
    wall_candidate_id: str
    path_fingerprint: tuple[Point, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    claimed_complete: bool


@dataclass(frozen=True)
class HostUniverseSlice:
    """A caller-local list.  Its completeness flag is only a claim."""

    walls: tuple[WallCandidate, ...]
    document_id: str = "doc-host"
    revision_id: str = "R1"
    source_sha256: str = SHA_A
    snapshot_id: str = "snap-host"
    page_id: str = "1"
    viewport_id: str | None = None
    decision_scope_id: str = "host-scope:page-1"
    claimed_complete: bool = True
    source_complete: bool = True
    traversal_truncated: bool = False


def transform_point(
    point: Point,
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: Point = (0.0, 0.0),
) -> Point:
    angle = math.radians(angle_deg)
    x, y = point
    return (
        scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0],
        scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1],
    )


def transform_polyline(
    pts: Sequence[Point],
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: Point = (0.0, 0.0),
) -> tuple[Point, ...]:
    return tuple(
        transform_point(point, angle_deg=angle_deg, scale=scale, offset=offset)
        for point in pts
    )


def make_wall(
    candidate_id: str,
    pts: Sequence[Point],
    *,
    junction_types: tuple[JunctionType, JunctionType] = (
        JunctionType.ENDPOINT,
        JunctionType.ENDPOINT,
    ),
    viewport_id: str = "vp_1",
    length_m: float | None = None,
    face_a_segment_ids: tuple[str, ...] | None = None,
    is_curved: bool = False,
) -> WallCandidate:
    segment_ids = face_a_segment_ids or (f"seg:{candidate_id}",)
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="single_line",
        centerline_pts=tuple(pts),
        face_a_segment_ids=segment_ids,
        face_b_segment_ids=None,
        is_curved=is_curved,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=length_m,
        end_node_ids=(f"{candidate_id}:n0", f"{candidate_id}:n1"),
        junction_types=junction_types,
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.8,
    )


def make_span(
    *,
    jamb_start: Point,
    jamb_end: Point,
    host_orientation_deg: float = 0.0,
    page: int = 1,
    wall_thickness_pt: float = 10.0,
) -> HostedOpeningSpan:
    return HostedOpeningSpan(
        page=page,
        host_orientation_deg=host_orientation_deg,
        jamb_start=jamb_start,
        jamb_end=jamb_end,
        span_pt=math.hypot(jamb_end[0] - jamb_start[0], jamb_end[1] - jamb_start[1]),
        width_m=None,
        wall_thickness_pt=wall_thickness_pt,
        subtype="door_like",
        evidence_flags=(
            "host_wall_band",
            "aligned_two_face_gap",
            "jamb_boundaries_confirmed",
        ),
        reason="synthetic_fixture",
    )


def continuous_host_wall(
    *,
    wall_id: str = "wall_through",
    y: float = 100.0,
    x0: float = 20.0,
    x1: float = 220.0,
    viewport_id: str = "vp_1",
) -> WallCandidate:
    return make_wall(
        wall_id,
        ((x0, y), (x1, y)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        viewport_id=viewport_id,
    )


def flanking_host_walls(
    *,
    gap_lo: float = 100.0,
    gap_hi: float = 140.0,
    y: float = 100.0,
    left_id: str = "wall_left",
    right_id: str = "wall_right",
    viewport_id: str = "vp_1",
) -> tuple[WallCandidate, WallCandidate]:
    return (
        make_wall(left_id, ((20.0, y), (gap_lo, y)), viewport_id=viewport_id),
        make_wall(right_id, ((gap_hi, y), (220.0, y)), viewport_id=viewport_id),
    )


def parallel_competitor(
    *,
    wall_id: str = "wall_parallel",
    y: float = 130.0,
    viewport_id: str = "vp_1",
) -> WallCandidate:
    return continuous_host_wall(wall_id=wall_id, y=y, viewport_id=viewport_id)


def producer_path_fingerprint(pts: Sequence[Point]) -> tuple[Point, ...]:
    return canonical_path_fingerprint(pts)


def edge_records_for(
    walls: Sequence[WallCandidate],
    *,
    shared_source_by_wall: Mapping[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Build producer-side edge records for physical-wall identity recomputation."""

    source_map = dict(shared_source_by_wall or {})
    records: dict[str, dict[str, object]] = {}
    for wall in walls:
        if len(wall.centerline_pts) < 2:
            continue
        start = wall.centerline_pts[0]
        end = wall.centerline_pts[-1]
        source_id = source_map.get(wall.candidate_id, f"src:{wall.candidate_id}")
        for edge_id in wall.face_a_segment_ids:
            records[str(edge_id)] = {
                "id": str(edge_id),
                "x1": float(start[0]),
                "y1": float(start[1]),
                "x2": float(end[0]),
                "y2": float(end[1]),
                "source_primitive_ids": (source_id,),
            }
    return records


def assert_host_capability_locked() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def shuffle_walls(walls: Sequence[WallCandidate], seed: int) -> tuple[WallCandidate, ...]:
    import random

    items = list(walls)
    random.Random(seed).shuffle(items)
    return tuple(items)


def reverse_wall_direction(wall: WallCandidate) -> WallCandidate:
    return make_wall(
        wall.candidate_id,
        tuple(reversed(wall.centerline_pts)),
        junction_types=(wall.junction_types[1], wall.junction_types[0]),
        viewport_id=wall.viewport_id,
        length_m=wall.length_m,
        face_a_segment_ids=wall.face_a_segment_ids,
        is_curved=wall.is_curved,
    )


def collinear_split_points(
    pts: Sequence[Point],
    splits: Iterable[float],
) -> tuple[Point, ...]:
    if len(pts) != 2:
        return tuple(pts)
    (x0, y0), (x1, y1) = pts
    out: list[Point] = [(x0, y0)]
    for fraction in splits:
        out.append((x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction))
    out.append((x1, y1))
    return tuple(out)
