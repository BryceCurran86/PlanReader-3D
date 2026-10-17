"""Shadow metric polygons from independently figured, source-witnessed room sides.

This module is a geometry calculation, not a new measurement-authority issuer.
Callers must bind every original side and figured value through the existing
source visibility / figured-dimension authority before passing any record here.
Its CANDIDATE result must never be interpreted as FIRM QuantityEvidence.
Neither title-block scale nor native PDF-point length is used as a conversion.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class FiguredPhysicalSide:
    source_side_id: str
    start_pdf_pt: tuple[float, float]
    end_pdf_pt: tuple[float, float]
    source_segment_ids: tuple[str, ...]
    length_mm: float | None = None
    figured_dimension_id: str | None = None
    witness_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FiguredPolygonMetricShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_area_m2: float | None
    metric_vertices_mm: tuple[tuple[float, float], ...]
    source_figure_ids: tuple[str, ...]
    closure_inferred_side_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str
    physical_room_id: str
    diagnostic_only: bool = True
    source_side_ids: tuple[str, ...] = ()
    source_segment_ids: tuple[str, ...] = ()


def _finite_positive(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if math.isfinite(numeric) and numeric > 0 else None


def _point(value: object) -> tuple[float, float] | None:
    if type(value) not in (tuple, list) or len(value) != 2:
        return None
    if any(type(item) not in (float, int) for item in value):
        return None
    try:
        xy = (float(value[0]), float(value[1]))
    except (TypeError, ValueError, OverflowError):
        return None
    return xy if all(math.isfinite(v) for v in xy) else None


def _ids(value: object, *, minimum: int = 1) -> bool:
    return (
        type(value) in (tuple, list)
        and len(value) >= minimum
        and all(type(item) is str and item and item == item.strip() for item in value)
        and len(set(value)) == len(value)
    )


def measure_figured_room_edge_chain_shadow(
    sides: Sequence[FiguredPhysicalSide],
    *,
    source_sha256: str,
    revision_id: str,
    page_id: str,
    physical_room_id: str,
) -> FiguredPolygonMetricShadow:
    """Reconstruct a complete orthogonal metric ring without a guessed scale.

    At most one unfigured length per independent orthogonal direction can be
    derived from *exact source-ring closure*. Underconstrained chains abstain.
    A candidate number does not authenticate wall roles, metric source units,
    original figured text, material/finish, or commercial authority.
    """
    def block(reason: str) -> FiguredPolygonMetricShadow:
        return FiguredPolygonMetricShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,), None, (), (), (),
            str(source_sha256), str(revision_id), str(page_id),
            str(physical_room_id),
        )

    if (
        type(source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
        or any(type(v) is not str or not v or v != v.strip()
               for v in (revision_id, page_id, physical_room_id))
    ):
        return block("figured_source_lineage_invalid")
    if type(sides) not in (tuple, list) or len(sides) < 4:
        return block("physical_room_source_edge_chain_unavailable")

    starts: list[tuple[float, float]] = []
    ends: list[tuple[float, float]] = []
    known: list[float | None] = []
    dimension_ids: set[str] = set()
    side_ids: set[str] = set()
    source_segment_ids: set[str] = set()
    for side in sides:
        if type(side) is not FiguredPhysicalSide:
            return block("figured_source_side_record_untrusted")
        if (
            type(side.source_side_id) is not str or not side.source_side_id
            or side.source_side_id != side.source_side_id.strip()
            or side.source_side_id in side_ids
            or not _ids(side.source_segment_ids)
            or any(name in source_segment_ids for name in side.source_segment_ids)
        ):
            return block("figured_source_side_identity_conflict")
        side_ids.add(side.source_side_id)
        source_segment_ids.update(side.source_segment_ids)
        start = _point(side.start_pdf_pt)
        end = _point(side.end_pdf_pt)
        if start is None or end is None or start == end:
            return block("figured_source_side_geometry_invalid")
        starts.append(start)
        ends.append(end)
        if side.length_mm is None:
            if side.figured_dimension_id is not None or side.witness_observation_ids:
                return block("figured_source_dimension_receipt_incomplete")
            known.append(None)
        else:
            measured = _finite_positive(side.length_mm)
            dim = side.figured_dimension_id
            if (
                measured is None or type(dim) is not str or not dim
                or dim != dim.strip() or dim in dimension_ids
                or not _ids(side.witness_observation_ids, minimum=2)
            ):
                return block("figured_source_dimension_receipt_incomplete")
            known.append(measured)
            dimension_ids.add(dim)

    if any(ends[i] != starts[(i + 1) % len(starts)]
           for i in range(len(starts))):
        return block("physical_room_source_edge_chain_unclosed")
    if len(set(starts)) != len(starts):
        return block("physical_room_source_ring_self_touching")
    try:
        from shapely.geometry import Polygon
        pdf_ring = Polygon(starts)
        if not pdf_ring.is_valid or pdf_ring.area <= 0.0:
            return block("physical_room_source_ring_not_simple")
    except (ValueError, OverflowError):
        return block("physical_room_source_ring_not_simple")

    initial = (ends[0][0] - starts[0][0], ends[0][1] - starts[0][1])
    norm = math.hypot(*initial)
    if not math.isfinite(norm) or norm == 0:
        return block("figured_source_side_geometry_invalid")
    ux, uy = initial[0] / norm, initial[1] / norm
    axes: list[int] = []
    signs: list[int] = []
    for start, end in zip(starts, ends):
        dx, dy = end[0] - start[0], end[1] - start[1]
        magnitude = math.hypot(dx, dy)
        if not math.isfinite(magnitude) or magnitude <= 0:
            return block("figured_source_side_geometry_invalid")
        parallel = (dx * ux + dy * uy) / magnitude
        normal = (-dx * uy + dy * ux) / magnitude
        if abs(abs(parallel) - 1) <= 1e-9 and abs(normal) <= 1e-9:
            axes.append(0)
            signs.append(1 if parallel > 0 else -1)
        elif abs(abs(normal) - 1) <= 1e-9 and abs(parallel) <= 1e-9:
            axes.append(1)
            signs.append(1 if normal > 0 else -1)
        else:
            return block("figured_source_room_not_orthogonal")

    metric_lengths = list(known)
    inferred: list[str] = []
    for axis in (0, 1):
        positions = [i for i, value in enumerate(axes) if value == axis]
        missing = [i for i in positions if metric_lengths[i] is None]
        known_signed = math.fsum(
            signs[i] * metric_lengths[i]
            for i in positions if metric_lengths[i] is not None
        )
        if len(missing) > 1:
            return block("figured_room_edge_chain_underconstrained")
        if len(missing) == 1:
            ix = missing[0]
            solved = -known_signed / signs[ix]
            if not math.isfinite(solved) or solved <= 0:
                return block("figured_room_edge_chain_closure_conflict")
            metric_lengths[ix] = solved
            inferred.append(sides[ix].source_side_id)
        elif abs(known_signed) > 1e-9 * max(
            1.0, math.fsum(metric_lengths[i] for i in positions)
        ):
            return block("figured_room_edge_chain_closure_conflict")

    vertices: list[tuple[float, float]] = [(0.0, 0.0)]
    for axis, sign, length in zip(axes, signs, metric_lengths):
        x, y = vertices[-1]
        vertices.append((
            x + sign * length if axis == 0 else x,
            y + sign * length if axis == 1 else y,
        ))
    scale = max(1.0, *(abs(k) for p in vertices for k in p))
    if math.hypot(*vertices[-1]) > scale * 1e-9:
        return block("figured_room_edge_chain_closure_conflict")
    ring = tuple(vertices[:-1])
    try:
        metric_polygon = Polygon(ring)
        if not metric_polygon.is_valid or metric_polygon.area <= 0.0:
            return block("figured_room_metric_polygon_not_simple")
        area_m2 = metric_polygon.area / 1_000_000.0
    except (ValueError, OverflowError):
        return block("figured_room_metric_polygon_not_simple")
    if not math.isfinite(area_m2) or area_m2 <= 0:
        return block("figured_room_metric_polygon_not_simple")
    return FiguredPolygonMetricShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("figured_edge_chain_shadow_only",),
        area_m2, ring, tuple(sorted(dimension_ids)), tuple(sorted(inferred)),
        source_sha256, revision_id, page_id, physical_room_id,
        source_side_ids=tuple(side.source_side_id for side in sides),
        source_segment_ids=tuple(sorted(source_segment_ids)),
    )
