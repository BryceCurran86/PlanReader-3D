"""Exact native annotation components; candidate opposing evidence only.

Inputs must be authenticated by the source producer before authority consumers
use this shadow geometry result. This does not measure or remove geometry.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence

from pb_figured_dimension_evidence import classify_dimension_token
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_wall_room_topology_typed_negative_evidence import KIND_DIMENSION, POLARITY_OPPOSING


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _unit(a):
    length = math.hypot(*a)
    return None if length <= 1e-9 else (a[0] / length, a[1] / length)


def _opposite_pairs(rows):
    """Retain all source pairs, rather than ranking coincident alternatives."""
    return tuple((a, b) for i, a in enumerate(rows) for b in rows[i + 1:]
        if _dot(a[1], b[1]) < 0 and abs(_cross(a[1], b[1])) <= .08)


def _selected_lines(segments, selected):
    """Rejoin an exact source split; never bridge a gap between primitives."""
    rows = [(frozenset((i,)), tuple(segments[i])) for i in sorted(selected)]
    originals = tuple(rows)
    while True:
        merged = False
        for i, (ids_a, a) in enumerate(rows):
            axis_a = _unit(_sub(a[2:], a[:2]))
            if axis_a is None:
                continue
            for j in range(i + 1, len(rows)):
                ids_b, b = rows[j]
                axis_b = _unit(_sub(b[2:], b[:2]))
                if axis_b is None or abs(_cross(axis_a, axis_b)) > 1e-6:
                    continue
                shared = set((a[:2], a[2:])) & set((b[:2], b[2:]))
                if len(shared) != 1:
                    continue
                endpoint = next(iter(shared))
                outer_a = a[2:] if a[:2] == endpoint else a[:2]
                outer_b = b[2:] if b[:2] == endpoint else b[:2]
                if _dot(_sub(outer_a, endpoint), _sub(outer_b, endpoint)) >= 0:
                    continue
                rows[i] = (ids_a | ids_b, (*outer_a, *outer_b))
                rows.pop(j)
                merged = True
                break
            if merged:
                break
        if not merged:
            return tuple(sorted(set((*originals, *rows)), key=lambda r: tuple(sorted(r[0]))))


def collect_native_dimension_cap_evidence(
    *, segments: Mapping[str, Sequence[float]], words: Sequence[Mapping],
    selected_ids: Sequence[str], document_id: str, page_id: str,
    revision_id: str, source_sha256: str, snapshot_id: str,
) -> tuple[EvidenceAtom, ...]:
    """Nominate covered cap/tick components without a dimension value.

    A selected native line needs same-side perpendicular caps and an
    opposite pair of diagonal tick halves at BOTH endpoints. Trusted numeric
    text must lie along that line and have the matching native text direction.
    Every opening support primitive must belong to the nominated components.
    """
    selected = frozenset(selected_ids)
    if not selected or not selected <= segments.keys():
        return ()
    if any(len(segments[i]) != 4 or not all(math.isfinite(v) for v in segments[i]) for i in selected):
        return ()
    # Exact endpoint addressing avoids rescanning the whole page for each
    # printed word. The same Euclidean equality predicate is applied below.
    endpoints = sorted((x, y, i, ox, oy)
        for i, line in segments.items() if len(line) == 4
        for (x, y), (ox, oy) in ((line[:2], line[2:]), (line[2:], line[:2])))
    components = []
    for line_ids, line in _selected_lines(segments, selected):
        if len(line) != 4 or not all(math.isfinite(v) for v in line):
            continue
        start, end = line[:2], line[2:]
        axis = _unit(_sub(end, start))
        if axis is None:
            continue
        length = math.hypot(*_sub(end, start))
        normal = (-axis[1], axis[0])
        for word in words:
            if not classify_dimension_token(str(word['text'])).is_linear_dimension:
                continue
            text_axis = _unit(tuple(word['axis']))
            if text_axis is None or abs(_cross(axis, text_axis)) > 1e-4:
                continue
            x0, y0, x1, y1 = word['bbox']
            center = ((x0 + x1) / 2, (y0 + y1) / 2)
            height = abs(normal[0]) * (x1 - x0) + abs(normal[1]) * (y1 - y0)
            tolerance = max(1e-6, height * 1e-4)
            along = _dot(_sub(center, start), axis)
            across = abs(_dot(_sub(center, start), normal))
            if height <= 0 or not -tolerance <= along <= length + tolerance:
                continue
            if not tolerance < across <= height * 1.5:
                continue
            covered = set(line_ids)
            valid = True
            endpoint_caps = []
            for endpoint in (start, end):
                caps, ticks = [], []
                lo = bisect_left(endpoints, (endpoint[0] - tolerance,))
                hi = bisect_right(endpoints, (endpoint[0] + tolerance, math.inf))
                for x, y, other_id, ox, oy in endpoints[lo:hi]:
                    if other_id in line_ids:
                        continue
                    if math.hypot(*_sub((x, y), endpoint)) > tolerance:
                        continue
                    away = _sub((ox, oy), endpoint)
                    direction = _unit(away)
                    if direction is None:
                        continue
                    cosine = abs(_dot(axis, direction))
                    if cosine <= 1e-4:
                        caps.append((other_id, direction))
                    elif .4 <= cosine <= .9 and .2 * height <= math.hypot(*away) <= height:
                        ticks.append((other_id, direction))
                tick_pairs = _opposite_pairs(ticks)
                if not caps or not tick_pairs:
                    valid = False
                    break
                endpoint_caps.append(caps)
                covered.update(row[0] for pair in tick_pairs for row in pair)
            cap_pairs = (() if not valid else tuple((a, b)
                for a in endpoint_caps[0] for b in endpoint_caps[1]
                if _dot(a[1], b[1]) > 0 and abs(_cross(a[1], b[1])) <= 1e-4))
            if valid and cap_pairs:
                covered.update(row[0] for pair in cap_pairs for row in pair)
                components.append((tuple(sorted(line_ids)), str(word['id']), frozenset(covered)))
    covered_ids = frozenset(i for _lines, _word, covered in components for i in covered)
    if not selected <= covered_ids:
        return ()
    atoms = []
    for line_ids, word_id, covered in sorted(set(components)):
        metadata = dict(revision_id=revision_id, source_sha256=source_sha256,
            snapshot_id=snapshot_id, polarity=POLARITY_OPPOSING,
            dimension_line_observation_ids=line_ids, text_observation_id=word_id,
            source_observation_ids=tuple(sorted(covered)),
            opening_support_observation_ids=tuple(sorted(selected)),
            all_opening_support_covered=True)
        atoms.append(EvidenceAtom(
            evidence_id=stable_contract_id('native_dimension_cap_evidence', metadata),
            document_id=document_id, page_id=page_id, kind=KIND_DIMENSION,
            method='native_dimension_cap_source_topology',
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=('native_dimension_cap_tick_text_topology',), metadata=metadata))
    return tuple(atoms)
