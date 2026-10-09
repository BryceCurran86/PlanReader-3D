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
    return None if not math.isfinite(length) or length <= 1e-9 else (a[0] / length, a[1] / length)


def _opposite_pairs(rows):
    """Retain all source pairs, rather than ranking coincident alternatives."""
    return tuple((a, b) for i, a in enumerate(rows) for b in rows[i + 1:]
        if _dot(a[1], b[1]) < 0 and abs(_cross(a[1], b[1])) <= .08)


def _source_lines(segments):
    """Retain all axes and exact connected splits, without bridging gaps.

    A queried witness need not itself be the dimension axis. Compile the page's
    source components first, then require complete coverage of the query.
    """
    lines = {i: tuple(line) for i, line in segments.items()
        if len(line) == 4 and all(math.isfinite(v) for v in line)
        and _unit(_sub(line[2:], line[:2])) is not None}
    at_endpoint = {}
    for i, line in lines.items():
        for point in (line[:2], line[2:]):
            at_endpoint.setdefault(point, set()).add(i)
    originals = tuple((frozenset((i,)), line) for i, line in lines.items())
    components = set()
    visited = set()
    for i in sorted(lines):
        if i in visited:
            continue
        line = lines[i]
        axis = _unit(_sub(line[2:], line[:2]))
        members, pending = set(), [i]
        while pending:
            member = pending.pop()
            if member in members:
                continue
            other = lines[member]
            other_axis = _unit(_sub(other[2:], other[:2]))
            # Exact collinearity avoids cumulative drift through a chain.
            if (abs(_cross(axis, other_axis)) > 1e-6
                    or any(abs(_cross(axis, _sub(p, line[:2]))) > 1e-6
                        for p in (other[:2], other[2:]))):
                continue
            members.add(member)
            for point in (other[:2], other[2:]):
                pending.extend(sorted(at_endpoint[point] - members))
        visited.update(members)
        points = {p for member in members
            for p in (lines[member][:2], lines[member][2:])}
        ordered = sorted(points, key=lambda p: (_dot(_sub(p, line[:2]), axis), p))
        components.add((frozenset(members), (*ordered[0], *ordered[-1])))
    return tuple(sorted(set((*originals, *components)),
        key=lambda r: (tuple(sorted(r[0])), r[1])))


def compile_native_dimension_cap_components(
    *, segments: Mapping[str, Sequence[float]], words: Sequence[Mapping],
):
    """Compile immutable source geometry facts; no authority or dimension value.

    A native axis needs same-side perpendicular witnesses and an opposite pair
    of diagonal tick halves at BOTH terminators. Each axis endpoint must lie
    within the terminator tick's radius. Trusted numeric text must
    lie between those terminators and have matching native text direction.
    """
    # Exact endpoint addressing avoids rescanning the whole page for each
    # printed word. The same Euclidean equality predicate is applied below.
    endpoints = sorted((x, y, i, ox, oy)
        for i, line in segments.items() if len(line) == 4 and all(math.isfinite(v) for v in line)
        for (x, y), (ox, oy) in ((line[:2], line[2:]), (line[2:], line[:2])))
    components = []
    for line_ids, line in _source_lines(segments):
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
            terminators = []
            # A tick junction may be inside an overhanging native axis. Find
            # all perpendicular source witnesses crossing that axis; never
            # choose a nearest or first junction.
            lo = bisect_left(endpoints, (min(start[0], end[0]) - tolerance,))
            hi = bisect_right(endpoints, (max(start[0], end[0]) + tolerance, math.inf))
            junctions = set()
            for x, y, other_id, ox, oy in endpoints[lo:hi]:
                if other_id in line_ids:
                    continue
                point = (x, y)
                away = _unit(_sub((ox, oy), point))
                u = _dot(_sub(point, start), axis)
                if (away is not None and abs(_dot(axis, away)) <= 1e-4
                        and abs(_dot(_sub(point, start), normal)) <= tolerance
                        and -tolerance <= u <= length + tolerance):
                    junctions.add(point)
            for endpoint in sorted(junctions):
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
                        ticks.append((other_id, direction, math.hypot(*away)))
                tick_pairs = _opposite_pairs(ticks)
                if not caps or not tick_pairs:
                    continue
                u = _dot(_sub(endpoint, start), axis)
                terminators.append((u, caps, tick_pairs))
            for first in terminators:
                for last in terminators:
                    u0, caps0, ticks0 = first
                    u1, caps1, ticks1 = last
                    if u1 - u0 <= tolerance or not u0 - tolerance <= along <= u1 + tolerance:
                        continue
                    # Entire native axis coverage requires both terminal
                    # overhangs to be bounded by their own diagonal ticks.
                    valid0 = tuple(pair for pair in ticks0
                        if -tolerance <= u0 <= max(t[2] for t in pair) + tolerance)
                    valid1 = tuple(pair for pair in ticks1
                        if -tolerance <= length - u1 <= max(t[2] for t in pair) + tolerance)
                    cap_pairs = tuple((a, b) for a in caps0 for b in caps1
                        if _dot(a[1], b[1]) > 0 and abs(_cross(a[1], b[1])) <= 1e-4)
                    if not valid0 or not valid1 or not cap_pairs:
                        continue
                    covered = set(line_ids)
                    covered.update(t[0] for pair in (*valid0, *valid1) for t in pair)
                    covered.update(t[0] for pair in cap_pairs for t in pair)
                    components.append((tuple(sorted(line_ids)), str(word['id']), frozenset(covered)))
    return tuple(sorted(set(components),
        key=lambda row: (row[0], row[1], tuple(sorted(row[2])))))


def native_dimension_cap_evidence_from_components(
    *, components, selected_ids: Sequence[str], document_id: str, page_id: str,
    revision_id: str, source_sha256: str, snapshot_id: str,
) -> tuple[EvidenceAtom, ...]:
    """Nominate fully covered supports from previously compiled source facts.

    This geometry helper is not an authority. Producer callers must reprove all
    current source receipts before supplying immutable compiled facts.
    """
    selected = frozenset(selected_ids)
    if not selected:
        return ()
    covered_ids = frozenset(i for _lines, _word, covered in components for i in covered)
    if not selected <= covered_ids:
        return ()
    atoms = []
    for line_ids, word_id, covered in sorted(set(components),
            key=lambda row: (row[0], row[1], tuple(sorted(row[2])))):
        if not selected & covered:
            continue
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


def collect_native_dimension_cap_evidence(
    *, segments: Mapping[str, Sequence[float]], words: Sequence[Mapping],
    selected_ids: Sequence[str], document_id: str, page_id: str,
    revision_id: str, source_sha256: str, snapshot_id: str,
) -> tuple[EvidenceAtom, ...]:
    """Compile and nominate complete components without measuring text."""
    selected = frozenset(selected_ids)
    if not selected or not selected <= segments.keys():
        return ()
    if any(len(segments[i]) != 4 or not all(math.isfinite(v) for v in segments[i]) for i in selected):
        return ()
    components = compile_native_dimension_cap_components(segments=segments, words=words)
    return native_dimension_cap_evidence_from_components(components=components,
        selected_ids=tuple(selected), document_id=document_id, page_id=page_id,
        revision_id=revision_id, source_sha256=source_sha256, snapshot_id=snapshot_id)
