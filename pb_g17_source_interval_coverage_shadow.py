"""Read-only original-span coverage audit for G17 versus W4 candidates.

Every candidate wall is considered independently. Shared source-primitive
ancestry and original interval coverage are NECESSARY diagnostics, never
sufficient to grant physical equivalence, structural wall role or a host.
The caller must authenticate all producer records; this module cannot.
"""
from __future__ import annotations

from collections import Counter
from math import hypot, isfinite
from typing import Any, Sequence

_COORD_TOL = 1e-6


def _line(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    try:
        points = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(isfinite(v) for v in points):
        return None
    return points if hypot(points[2]-points[0], points[3]-points[1]) > _COORD_TOL else None


def _source_interval(source: tuple[float, ...], candidate: object) -> tuple[float, float] | None:
    """Exact original-line overlap, not a tolerance-based wall join.

    The tolerance is for round-trip floating point only. It cannot bridge
    finite drafting gaps or infer parentage from proximity.
    """
    other = _line(candidate)
    if other is None:
        return None
    x, y, u, v = source
    dx, dy = u-x, v-y
    length = hypot(dx, dy)
    unit_x, unit_y = dx/length, dy/length
    projections = []
    for px, py in ((other[0], other[1]), (other[2], other[3])):
        rx, ry = px-x, py-y
        perpendicular = abs(unit_x*ry-unit_y*rx)
        if perpendicular > _COORD_TOL:
            return None
        projections.append(unit_x*rx+unit_y*ry)
    low = max(0., min(projections))
    high = min(length, max(projections))
    return (low, high) if high-low > _COORD_TOL else None


def _gaps(length: float, intervals: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    if not intervals:
        return ((0., length),)
    current = 0.
    gaps = []
    for low, high in sorted(intervals):
        if low > current + _COORD_TOL:
            gaps.append((current, low))
        current = max(current, high)
    if length > current + _COORD_TOL:
        gaps.append((current, length))
    return tuple(gaps)


def audit_g17_original_source_interval_coverage(
    source_fragments: Sequence[Any], candidate_wall_records: Sequence[Any],
) -> dict[str, Any]:
    """Keep every source edge and candidate; all positive checks remain shadow.

    Each W4 record is evaluated independently: two different wall candidates
    cannot jointly cover one original source interval or confer ancestry.
    Original source equivalence and source authenticity are NOT re-proved here.
    """
    walls = tuple(candidate_wall_records)
    collisions = tuple(sorted(
        key for key, count in Counter(str(w.wall_candidate_id) for w in walls).items()
        if count > 1
    ))
    originals = tuple(sorted(tuple(source_fragments), key=lambda item: (
        str(item.edge_id), repr(tuple(item.geometry)),
        tuple(sorted(str(s) for s in item.source_primitive_ids)),
    )))
    rows = []
    for index, original in enumerate(originals):
        line = _line(original.geometry)
        source_ids = frozenset(str(s) for s in original.source_primitive_ids)
        evidence = []
        if line is not None and source_ids:
            length = hypot(line[2]-line[0], line[3]-line[1])
            for wall in walls:
                supported = []
                geometric_foreign = []
                for fragment in tuple(getattr(wall, 'source_edge_fragments', ()) or ()):
                    interval = _source_interval(line, fragment.geometry)
                    if interval is None:
                        continue
                    shared = source_ids.intersection(str(s) for s in fragment.source_primitive_ids)
                    item = dict(edge_id=str(fragment.edge_id), original_span_pt=interval)
                    if shared:
                        supported.append(dict(item, shared_source_primitive_ids=tuple(sorted(shared))))
                    else:
                        geometric_foreign.append(item)
                if not supported and not geometric_foreign:
                    continue
                gaps = _gaps(length, tuple(r['original_span_pt'] for r in supported))
                evidence.append(dict(
                    candidate_wall_id=str(wall.wall_candidate_id),
                    source_owned_interval_witnesses=tuple(sorted(
                        supported, key=lambda x:(x['original_span_pt'],x['edge_id']))),
                    geometric_only_foreign_source_overlaps=tuple(sorted(
                        geometric_foreign,key=lambda x:(x['original_span_pt'],x['edge_id']))),
                    uncovered_original_intervals_pt=gaps,
                    complete_original_interval_candidate=bool(supported) and not gaps,
                    physical_equivalence_granted=False,
                ))
            evidence.sort(key=lambda x:(x['candidate_wall_id'],
                repr(x['source_owned_interval_witnesses']),
                repr(x['geometric_only_foreign_source_overlaps'])))
        rows.append(dict(
            original_edge_index=index, original_edge_id=str(original.edge_id),
            original_source_primitive_ids=tuple(sorted(source_ids)),
            original_geometry=line,
            source_geometry_valid=line is not None and bool(source_ids),
            competing_wall_candidates=tuple(evidence),
            first_blocker=(
                'original_source_interval_invalid_or_lineage_missing'
                if line is None or not source_ids else
                'source_owned_w4_interval_missing' if not any(
                    e['source_owned_interval_witnesses'] for e in evidence) else
                'source_owned_w4_interval_incomplete' if not any(
                    e['complete_original_interval_candidate'] for e in evidence) else
                'structural_role_and_physical_equivalence_unproven'
            ),
            physical_equivalence_granted=False,
        ))
    return dict(
        original_source_edges=tuple(rows),
        competing_wall_candidate_address_collisions=collisions,
        structural_wall_role_granted=False,
        physical_wall_equivalence_granted=False,
        opening_host_granted=False,
        metric_quantity_granted=False,
        original_source_authentication_performed=False,
        original_candidate_universe_complete_proven=False,
    )
