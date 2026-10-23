"""Producer-owned source room figured dimension and wall witness shadow authority (Items 18 & 19).

Authenticates figured room dimensions and corresponding internal wall witnesses:
- Associates horizontal and vertical figured dimension pairs with the exact internal
  wall faces of a room polygon.
- Proves witness line alignment against opposing internal wall edges within drawing
  tolerance (<= 2.5 pt).
- Verifies scale consistency: figured aspect ratio (W_mm / L_mm) must match the
  geometric aspect ratio (W_pt / L_pt) within scale consistency tolerance (5%).
- Fails closed on missing dimension orientation, unaligned witness lines, scale
  contradiction, or competing/ambiguous dimension pairs.
- Strictly non-publishing in shadow mode (status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_ROOM_FIGURED_WITNESS_RESOLVED = "source_room_figured_witness_resolved"
SOURCE_ROOM_FIGURED_WITNESS_CANDIDATE = "source_room_figured_witness_candidate"
SOURCE_ROOM_FIGURED_WITNESS_UNAVAILABLE = "source_room_figured_witness_unavailable"
DIMENSION_ORIENTATION_PAIR_UNAVAILABLE = "dimension_orientation_pair_unavailable"
WITNESS_WALL_ALIGNMENT_UNRESOLVED = "witness_wall_alignment_unresolved"
FIGURED_PAIR_SCALE_INCONSISTENT = "figured_pair_scale_inconsistent"
COMPETING_FIGURED_DIMENSION_PAIRS = "competing_figured_dimension_pairs"
INVALID_ROOM_POLYGON = "invalid_room_polygon"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
FIGURED_DIMENSION_VALUE_INVALID = "figured_dimension_value_invalid"

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()

DEFAULT_SNAP_TOLERANCE_PT = 2.5
MAX_SCALE_RATIO_DISCREPANCY = 0.05  # 5% scale consistency tolerance


def _clean(val: Any) -> str:
    return str(val or "").strip()


def _point(val: Any) -> tuple[float, float] | None:
    if type(val) not in (tuple, list) or len(val) != 2:
        return None
    try:
        x, y = float(val[0]), float(val[1])
    except (TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def _validate_polygon_pts(pts: Sequence[Sequence[float]]) -> Polygon | None:
    if type(pts) not in (tuple, list) or len(pts) < 3:
        return None
    coords = []
    for p in pts:
        pt = _point(p)
        if pt is None:
            return None
        coords.append(pt)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords.pop()
    if len(coords) < 3 or len(set(coords)) != len(coords):
        return None
    poly = Polygon(coords)
    return poly if poly.is_valid and poly.area > 0 else None


@dataclass(frozen=True)
class SourceRoomFiguredWitnessSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    physical_room_id: str
    room_label: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_room_id",
            "room_label",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourceBoundDimensionCandidate:
    dimension_id: str
    value_mm: float
    orientation: str  # "horizontal" or "vertical"
    endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    witness_geometries: tuple[tuple[float, float, float, float], ...] = ()
    witness_observation_ids: tuple[str, ...] = ()
    dimension_line_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRoomFaceBoundaryEdge:
    wall_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    stroke_id: str = ""
    role: str = "finished_inner_face"


@dataclass(frozen=True)
class SourceRoomFiguredWitnessRecord:
    record_id: str
    physical_room_id: str
    room_label: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    horizontal_dimension_id: str
    horizontal_value_mm: float
    horizontal_endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    horizontal_witness_ids: tuple[str, ...]
    horizontal_bounding_wall_ids: tuple[str, ...]
    vertical_dimension_id: str
    vertical_value_mm: float
    vertical_endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    vertical_witness_ids: tuple[str, ...]
    vertical_bounding_wall_ids: tuple[str, ...]
    figured_area_m2: float
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    polygon_area_pt2: float
    scale_pt_per_mm: float
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_ROOM_FIGURED_WITNESS_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceRoomFiguredWitnessRecord is producer-owned")


@dataclass(frozen=True)
class SourceRoomFiguredWitnessResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceRoomFiguredWitnessRecord | None = None
    selector: SourceRoomFiguredWitnessSelector | None = None
    schema_version: str = SCHEMA_VERSION


def _line_parts(
    seg: tuple[float, float, float, float],
) -> tuple[str, float, float, float]:
    x0, y0, x1, y1 = seg
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    if dx >= dy:
        return ("horizontal", 0.5 * (y0 + y1), min(x0, x1), max(x0, x1))
    return ("vertical", 0.5 * (x0 + x1), min(y0, y1), max(y0, y1))


def _witness_aligns_with_edge(
    witness_seg: tuple[float, float, float, float],
    edge: SourceRoomFaceBoundaryEdge,
    tolerance_pt: float,
) -> bool:
    w_orient, w_axis, w_lo, w_hi = _line_parts(witness_seg)
    e_seg = (edge.start_pt[0], edge.start_pt[1], edge.end_pt[0], edge.end_pt[1])
    e_orient, e_axis, e_lo, e_hi = _line_parts(e_seg)
    if w_orient != e_orient:
        return False
    if abs(w_axis - e_axis) > tolerance_pt:
        return False
    # Check overlap or touch along the span
    overlap = min(w_hi, e_hi) - max(w_lo, e_lo)
    return overlap >= -tolerance_pt


def evaluate_source_room_figured_witness_shadow(
    selector: SourceRoomFiguredWitnessSelector,
    *,
    room_face_polygon_pdf_pts: Sequence[Sequence[float]],
    bounding_edges: Sequence[SourceRoomFaceBoundaryEdge],
    dimensions: Sequence[SourceBoundDimensionCandidate],
    snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> SourceRoomFiguredWitnessResult:
    """Evaluate whether a room face is authentically measured by figured dimensions.

    Strictly fail-closed: returns CANDIDATE when proven, otherwise ABSTAINED or CONFLICT.
    """
    if not isinstance(selector, SourceRoomFiguredWitnessSelector):
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.ABSTAINED,
            (SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    poly = _validate_polygon_pts(room_face_polygon_pdf_pts)
    if poly is None:
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.ABSTAINED,
            (INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    # Separate horizontal and vertical dimensions
    horizontals = [
        d for d in dimensions if _clean(d.orientation).lower() == "horizontal"
    ]
    verticals = [d for d in dimensions if _clean(d.orientation).lower() == "vertical"]

    if not horizontals or not verticals:
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.ABSTAINED,
            (DIMENSION_ORIENTATION_PAIR_UNAVAILABLE,),
            selector=selector,
        )

    bounds = poly.bounds  # (minx, miny, maxx, maxy)
    poly_w_pt = bounds[2] - bounds[0]
    poly_h_pt = bounds[3] - bounds[1]
    if poly_w_pt <= 0.0 or poly_h_pt <= 0.0:
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.ABSTAINED,
            (INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    # Classify bounding edges into vertical (left/right) and horizontal (top/bottom)
    v_edges = []
    h_edges = []
    for edge in bounding_edges:
        e_seg = (edge.start_pt[0], edge.start_pt[1], edge.end_pt[0], edge.end_pt[1])
        orient, axis, lo, hi = _line_parts(e_seg)
        if orient == "vertical":
            v_edges.append((edge, axis, lo, hi))
        else:
            h_edges.append((edge, axis, lo, hi))

    valid_pairs = []

    for h_dim in horizontals:
        if not math.isfinite(h_dim.value_mm) or h_dim.value_mm <= 0.0:
            continue
        # Horizontal dimension endpoints / witnesses must align with left & right vertical edges
        h_hx = sorted(
            [float(h_dim.endpoints_pt[0][0]), float(h_dim.endpoints_pt[1][0])]
        )
        dim_w_pt = h_hx[1] - h_hx[0]
        if dim_w_pt <= 0.0 or abs(dim_w_pt - poly_w_pt) > snap_tolerance_pt * 2.0:
            continue

        left_matches = []
        right_matches = []
        for edge, axis, lo, hi in v_edges:
            if abs(axis - h_hx[0]) <= snap_tolerance_pt:
                left_matches.append(edge)
            elif abs(axis - h_hx[1]) <= snap_tolerance_pt:
                right_matches.append(edge)

        # Check witness line geometries if provided
        if h_dim.witness_geometries:
            left_w_ok = False
            right_w_ok = False
            for w_seg in h_dim.witness_geometries:
                w_orient, w_axis, _, _ = _line_parts(w_seg)
                if w_orient == "vertical":
                    if abs(w_axis - h_hx[0]) <= snap_tolerance_pt and any(
                        _witness_aligns_with_edge(w_seg, e, snap_tolerance_pt)
                        for e in left_matches
                    ):
                        left_w_ok = True
                    elif abs(w_axis - h_hx[1]) <= snap_tolerance_pt and any(
                        _witness_aligns_with_edge(w_seg, e, snap_tolerance_pt)
                        for e in right_matches
                    ):
                        right_w_ok = True
            if not (left_w_ok and right_w_ok):
                continue
        else:
            if not left_matches or not right_matches:
                continue

        h_bounding_walls = tuple(
            sorted({e.wall_id for e in (left_matches + right_matches) if e.wall_id})
        )

        for v_dim in verticals:
            if not math.isfinite(v_dim.value_mm) or v_dim.value_mm <= 0.0:
                continue
            v_vy = sorted(
                [float(v_dim.endpoints_pt[0][1]), float(v_dim.endpoints_pt[1][1])]
            )
            dim_h_pt = v_vy[1] - v_vy[0]
            if dim_h_pt <= 0.0 or abs(dim_h_pt - poly_h_pt) > snap_tolerance_pt * 2.0:
                continue

            top_matches = []
            bottom_matches = []
            for edge, axis, lo, hi in h_edges:
                if abs(axis - v_vy[0]) <= snap_tolerance_pt:
                    top_matches.append(edge)
                elif abs(axis - v_vy[1]) <= snap_tolerance_pt:
                    bottom_matches.append(edge)

            if v_dim.witness_geometries:
                top_w_ok = False
                bottom_w_ok = False
                for w_seg in v_dim.witness_geometries:
                    w_orient, w_axis, _, _ = _line_parts(w_seg)
                    if w_orient == "horizontal":
                        if abs(w_axis - v_vy[0]) <= snap_tolerance_pt and any(
                            _witness_aligns_with_edge(w_seg, e, snap_tolerance_pt)
                            for e in top_matches
                        ):
                            top_w_ok = True
                        elif abs(w_axis - v_vy[1]) <= snap_tolerance_pt and any(
                            _witness_aligns_with_edge(w_seg, e, snap_tolerance_pt)
                            for e in bottom_matches
                        ):
                            bottom_w_ok = True
                if not (top_w_ok and bottom_w_ok):
                    continue
            else:
                if not top_matches or not bottom_matches:
                    continue

            v_bounding_walls = tuple(
                sorted({e.wall_id for e in (top_matches + bottom_matches) if e.wall_id})
            )

            # Scale consistency gate: ratio (W_mm / L_mm) must match (poly_w_pt / poly_h_pt)
            figured_ratio = float(h_dim.value_mm) / float(v_dim.value_mm)
            geometric_ratio = float(poly_w_pt) / float(poly_h_pt)
            if (
                abs(figured_ratio - geometric_ratio)
                / max(figured_ratio, geometric_ratio)
                > MAX_SCALE_RATIO_DISCREPANCY
            ):
                continue

            valid_pairs.append((h_dim, v_dim, h_bounding_walls, v_bounding_walls))

    if not valid_pairs:
        # Check if there were dimensions that failed scale vs failed alignment
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.ABSTAINED,
            (WITNESS_WALL_ALIGNMENT_UNRESOLVED,),
            selector=selector,
        )

    # Deduplicate matching pairs by dimension IDs
    unique_pairs = {(p[0].dimension_id, p[1].dimension_id): p for p in valid_pairs}

    if len(unique_pairs) > 1:
        return SourceRoomFiguredWitnessResult(
            EvidenceResolutionStatus.CONFLICT,
            (COMPETING_FIGURED_DIMENSION_PAIRS,),
            selector=selector,
        )

    h_dim, v_dim, h_walls, v_walls = next(iter(unique_pairs.values()))
    area_m2 = round((float(h_dim.value_mm) * float(v_dim.value_mm)) / 1_000_000.0, 6)
    scale_pt_per_mm = round(float(poly_w_pt) / float(h_dim.value_mm), 6)

    record_payload = {
        "document_id": selector.document_id,
        "revision_id": selector.revision_id,
        "source_sha256": selector.source_sha256,
        "snapshot_id": selector.snapshot_id,
        "page_id": selector.page_id,
        "physical_room_id": selector.physical_room_id,
        "room_label": selector.room_label,
        "horizontal_dimension_id": h_dim.dimension_id,
        "vertical_dimension_id": v_dim.dimension_id,
        "figured_area_m2": area_m2,
    }
    record_id = stable_contract_id(
        "source_room_figured_witness_record", record_payload, digest_chars=32
    )

    record = SourceRoomFiguredWitnessRecord(
        record_id=record_id,
        physical_room_id=selector.physical_room_id,
        room_label=selector.room_label,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        horizontal_dimension_id=h_dim.dimension_id,
        horizontal_value_mm=float(h_dim.value_mm),
        horizontal_endpoints_pt=h_dim.endpoints_pt,
        horizontal_witness_ids=h_dim.witness_observation_ids,
        horizontal_bounding_wall_ids=h_walls,
        vertical_dimension_id=v_dim.dimension_id,
        vertical_value_mm=float(v_dim.value_mm),
        vertical_endpoints_pt=v_dim.endpoints_pt,
        vertical_witness_ids=v_dim.witness_observation_ids,
        vertical_bounding_wall_ids=v_walls,
        figured_area_m2=area_m2,
        polygon_pdf_pts=tuple(
            tuple(float(c) for c in pt) for pt in poly.exterior.coords[:-1]
        ),
        polygon_area_pt2=float(poly.area),
        scale_pt_per_mm=scale_pt_per_mm,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(SOURCE_ROOM_FIGURED_WITNESS_CANDIDATE,),
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceRoomFiguredWitnessResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(SOURCE_ROOM_FIGURED_WITNESS_RESOLVED,),
        record=record,
        selector=selector,
    )
