"""Test support for opening→host-wall binding red-team (fixtures only).

No production host-binding authority is defined here. Fixtures build synthetic
WallCandidates, HostedOpeningSpans, and ownership probes for fail-closed /
expected-RED tests. Reuses #323 canonical_path_fingerprint — does not fork it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_hosted_opening_geometry import HostedOpeningSpan
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_wall_identity_v2 import canonical_path_fingerprint


BASE_SHA = "62a161519e617cdf9ce23069820dbf7c68aaf521"

Point = Tuple[float, float]


@dataclass(frozen=True)
class CallerHostBindingProbe:
    """Caller-facing probe — must never self-certify host binding authority."""

    opening_id: str
    wall_candidate_id: str
    path_fingerprint: tuple[Point, ...]
    page_id: str
    viewport_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    universe_complete_claim: bool


@dataclass(frozen=True)
class HostUniverseSlice:
    """A local wall list. Completeness is a claim, never a proof."""

    walls: tuple[WallCandidate, ...]
    claimed_complete: bool
    viewport_id: str
    page_id: str
    document_id: str
    revision_id: str
    source_sha256: str


def transform_point(
    point: Point,
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: Point = (0.0, 0.0),
) -> Point:
    angle = math.radians(angle_deg)
    x, y = point
    xr = scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0]
    yr = scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1]
    return (xr, yr)


def transform_polyline(
    pts: Sequence[Point],
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: Point = (0.0, 0.0),
) -> tuple[Point, ...]:
    return tuple(
        transform_point(p, angle_deg=angle_deg, scale=scale, offset=offset) for p in pts
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
    face_a_segment_ids: tuple[str, ...] = ("seg_a",),
    is_curved: bool = False,
) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="single_line",
        centerline_pts=tuple(pts),
        face_a_segment_ids=face_a_segment_ids,
        face_b_segment_ids=None,
        is_curved=is_curved,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=length_m,
        end_node_ids=("n0", "n1"),
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
    subtype: str = "door_like",
) -> HostedOpeningSpan:
    span_pt = math.hypot(jamb_end[0] - jamb_start[0], jamb_end[1] - jamb_start[1])
    return HostedOpeningSpan(
        page=page,
        host_orientation_deg=host_orientation_deg,
        jamb_start=jamb_start,
        jamb_end=jamb_end,
        span_pt=span_pt,
        width_m=None,
        wall_thickness_pt=wall_thickness_pt,
        subtype=subtype,  # type: ignore[arg-type]
        evidence_flags=("host_wall_band", "aligned_two_face_gap", "jamb_boundaries_confirmed"),
        reason="synthetic_fixture",
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
    """Classic interrupted run: two collinear dangling chains flanking a gap."""

    left = make_wall(
        left_id,
        ((20.0, y), (gap_lo, y)),
        viewport_id=viewport_id,
        face_a_segment_ids=("left_seg",),
    )
    right = make_wall(
        right_id,
        ((gap_hi, y), (220.0, y)),
        viewport_id=viewport_id,
        face_a_segment_ids=("right_seg",),
    )
    return left, right


def continuous_host_wall(
    *,
    wall_id: str = "wall_through",
    y: float = 100.0,
    x0: float = 20.0,
    x1: float = 220.0,
    viewport_id: str = "vp_1",
) -> WallCandidate:
    """Unbroken centerline that geometrically contains an opening span."""

    return make_wall(
        wall_id,
        ((x0, y), (x1, y)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        viewport_id=viewport_id,
        face_a_segment_ids=("through_seg",),
    )


def parallel_competitor(
    *,
    wall_id: str = "wall_parallel",
    y: float = 130.0,
    viewport_id: str = "vp_1",
) -> WallCandidate:
    return make_wall(
        wall_id,
        ((20.0, y), (220.0, y)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        viewport_id=viewport_id,
        face_a_segment_ids=("parallel_seg",),
    )


def producer_path_fingerprint(pts: Sequence[Point]) -> tuple[Point, ...]:
    """Reuse #323 algorithm only — never invent a second fingerprint."""

    return canonical_path_fingerprint(pts)


def assert_host_capability_locked(physical: PhysicalOpeningAuthority | None = None) -> None:
    caps = (
        physical.capabilities()
        if physical is not None
        else PhysicalOpeningAuthority.capabilities()
    )
    assert caps["host_binding"] is False
    assert caps["host_identity"] is False
    assert caps["opening_dimensions"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def shuffle_walls(walls: Sequence[WallCandidate], seed: int = 17) -> list[WallCandidate]:
    import random

    items = list(walls)
    rng = random.Random(seed)
    rng.shuffle(items)
    return items


def reverse_wall_direction(wall: WallCandidate, new_id: str | None = None) -> WallCandidate:
    pts = tuple(reversed(wall.centerline_pts))
    jtypes = (wall.junction_types[1], wall.junction_types[0])
    return make_wall(
        new_id or wall.candidate_id,
        pts,
        junction_types=jtypes,
        viewport_id=wall.viewport_id,
        length_m=wall.length_m,
        face_a_segment_ids=wall.face_a_segment_ids,
        is_curved=wall.is_curved,
    )


def collinear_split_points(pts: Sequence[Point], splits: Iterable[float]) -> tuple[Point, ...]:
    """Insert collinear interior vertices along a straight two-point run."""

    if len(pts) != 2:
        return tuple(pts)
    (x0, y0), (x1, y1) = pts
    out: list[Point] = [(x0, y0)]
    for t in splits:
        out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append((x1, y1))
    return tuple(out)
