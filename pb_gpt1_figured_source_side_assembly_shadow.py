"""Reassemble original split structural ink into dimension-bound shadow room sides.

The input membership is exact source-observation IDs from a *separate*
source owner. This module cannot decide whether any PDF stroke is a wall,
reconcile ambiguous candidates, or promote a measured metric to FIRM.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceWallFragment:
    source_segment_id: str
    start_pdf_pt: tuple[float, float]
    end_pdf_pt: tuple[float, float]


@dataclass(frozen=True)
class FiguredSideSourceMembership:
    source_side_id: str
    segment_observation_ids: tuple[str, ...]
    measured_length_mm: float | None = None
    figured_dimension_id: str | None = None
    figured_witness_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceFiguredSideAssembly:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_side: FiguredPhysicalSide | None
    diagnostic_only: bool = True


@dataclass(frozen=True)
class SourceFiguredRingAssembly:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    ordered_sides: tuple[FiguredPhysicalSide, ...]
    diagnostic_only: bool = True


def _point(point: object) -> tuple[float, float] | None:
    if type(point) not in (tuple, list) or len(point) != 2:
        return None
    if any(type(n) not in (int, float) for n in point):
        return None
    try:
        result = (float(point[0]), float(point[1]))
    except (TypeError, ValueError, OverflowError):
        return None
    return result if all(math.isfinite(v) for v in result) else None


def assemble_original_figured_side_fragments(
    membership: FiguredSideSourceMembership,
    fragments: Sequence[SourceWallFragment],
) -> SourceFiguredSideAssembly:
    """Merge exact collinear, touching source fragments with no gap imputation."""
    def block(reason: str) -> SourceFiguredSideAssembly:
        return SourceFiguredSideAssembly(
            EvidenceResolutionStatus.ABSTAINED, (reason,), None
        )

    if type(membership) is not FiguredSideSourceMembership or type(fragments) not in (tuple, list):
        return block("source_side_membership_untrusted")
    names = membership.segment_observation_ids
    if (
        type(membership.source_side_id) is not str
        or not membership.source_side_id
        or type(names) not in (tuple, list)
        or len(names) == 0
        or any(type(n) is not str or not n or n != n.strip() for n in names)
        or len(set(names)) != len(names)
    ):
        return block("source_side_membership_invalid")
    if len(fragments) != len(names):
        return block("source_side_original_fragment_unavailable")
    mapped = {}
    for part in fragments:
        if type(part) is not SourceWallFragment:
            return block("source_side_fragment_untrusted")
        if type(part.source_segment_id) is not str or part.source_segment_id in mapped:
            return block("source_side_fragment_identity_conflict")
        first = _point(part.start_pdf_pt)
        second = _point(part.end_pdf_pt)
        if first is None or second is None or first == second:
            return block("source_side_fragment_geometry_invalid")
        mapped[part.source_segment_id] = (first, second)
    if set(mapped) != set(names):
        return block("source_side_original_fragment_unavailable")

    # A metric cannot be inferred by relative source fragment length.
    # Its only possible input is the independently printed figured dimension.
    if membership.measured_length_mm is None:
        if membership.figured_dimension_id is not None or membership.figured_witness_ids:
            return block("source_side_figured_receipt_incomplete")
    elif (
        type(membership.measured_length_mm) not in (int, float)
        or not math.isfinite(float(membership.measured_length_mm))
        or membership.measured_length_mm <= 0
        or type(membership.figured_dimension_id) is not str
        or not membership.figured_dimension_id
        or type(membership.figured_witness_ids) not in (tuple, list)
        or len(membership.figured_witness_ids) < 2
        or any(type(s) is not str or not s for s in membership.figured_witness_ids)
        or len(set(membership.figured_witness_ids)) != len(membership.figured_witness_ids)
    ):
        return block("source_side_figured_receipt_incomplete")

    first = mapped[sorted(mapped)[0]]
    vx, vy = first[1][0] - first[0][0], first[1][1] - first[0][1]
    size = math.hypot(vx, vy)
    if not math.isfinite(size) or size <= 0:
        return block("source_side_fragment_geometry_invalid")
    ux, uy = vx / size, vy / size
    ranges: list[tuple[float, float, tuple[float, float], tuple[float, float]]] = []
    for start, end in mapped.values():
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 0 or not math.isfinite(length):
            return block("source_side_fragment_geometry_invalid")
        cross = dx * uy - dy * ux
        offset = ((start[0] - first[0][0]) * uy
                  - (start[1] - first[0][1]) * ux)
        if abs(cross) > 1e-8 * length or abs(offset) > 1e-8 * max(1., length):
            return block("source_side_source_fragments_not_collinear")
        lo, hi = sorted((
            (start[0] - first[0][0]) * ux + (start[1] - first[0][1]) * uy,
            (end[0] - first[0][0]) * ux + (end[1] - first[0][1]) * uy,
        ))
        endpoints = sorted((start, end), key=lambda v: (
            (v[0] - first[0][0]) * ux + (v[1] - first[0][1]) * uy
        ))
        ranges.append((lo, hi, endpoints[0], endpoints[1]))
    ranges.sort(key=lambda t: t[:2])
    for a, b in zip(ranges, ranges[1:]):
        if abs(a[1] - b[0]) > 1e-8 * max(1., abs(a[1]), abs(b[0])):
            return block("source_side_fragments_overlap_or_gap")
        if math.dist(a[3], b[2]) > 1e-8:
            return block("source_side_fragments_not_exactly_joined")

    side = FiguredPhysicalSide(
        source_side_id=membership.source_side_id,
        start_pdf_pt=ranges[0][2],
        end_pdf_pt=ranges[-1][3],
        source_segment_ids=tuple(sorted(mapped)),
        length_mm=membership.measured_length_mm,
        figured_dimension_id=membership.figured_dimension_id,
        witness_observation_ids=membership.figured_witness_ids,
    )
    return SourceFiguredSideAssembly(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_split_strokes_reassembled_shadow_only",),
        side,
    )


def assemble_original_figured_room_ring(
    sides: Sequence[FiguredPhysicalSide],
) -> SourceFiguredRingAssembly:
    """Order one source-owned physical room cycle; reject all rival topologies."""
    def block(reason: str) -> SourceFiguredRingAssembly:
        return SourceFiguredRingAssembly(
            EvidenceResolutionStatus.ABSTAINED, (reason,), ()
        )
    if type(sides) not in (tuple, list) or len(sides) < 4:
        return block("source_room_original_sides_unavailable")
    if any(type(side) is not FiguredPhysicalSide for side in sides):
        return block("source_room_original_side_type_invalid")

    vertices: dict[tuple[float, float], list[int]] = {}
    for i, side in enumerate(sides):
        start, end = _point(side.start_pdf_pt), _point(side.end_pdf_pt)
        if start is None or end is None or start == end:
            return block("source_room_original_side_geometry_invalid")
        vertices.setdefault(start, []).append(i)
        vertices.setdefault(end, []).append(i)
    if any(len(indices) != 2 for indices in vertices.values()):
        return block("source_room_original_ring_branch_or_gap")
    if len(vertices) != len(sides):
        return block("source_room_original_ring_nonunique_vertices")

    # Lexicographic traversal chooses serialization order only, NOT a room,
    # dimension or finish candidate. The two equivalent windings are physical
    # reversal of the same proven degree-two polygon, not rival room choices.
    current = min(vertices)
    ordered: list[FiguredPhysicalSide] = []
    visited: set[int] = set()
    while len(visited) < len(sides):
        available = [index for index in vertices[current] if index not in visited]
        if not available:
            return block("source_room_original_ring_disconnected")
        if len(available) > 1:
            available.sort(key=lambda index: (
                sides[index].end_pdf_pt
                if sides[index].start_pdf_pt == current else sides[index].start_pdf_pt
            ))
        ix = available[0]
        side = sides[ix]
        if tuple(side.start_pdf_pt) == current:
            next_side = side
        elif tuple(side.end_pdf_pt) == current:
            next_side = replace(
                side, start_pdf_pt=side.end_pdf_pt, end_pdf_pt=side.start_pdf_pt
            )
        else:
            return block("source_room_original_ring_disconnected")
        ordered.append(next_side)
        visited.add(ix)
        current = tuple(next_side.end_pdf_pt)
    if current != tuple(ordered[0].start_pdf_pt):
        return block("source_room_original_ring_unclosed")

    return SourceFiguredRingAssembly(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_figured_ring_assembled_shadow_only",),
        tuple(ordered),
    )
