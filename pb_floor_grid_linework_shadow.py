"""Floor-grid linework: a typed negative for wall evidence (report only; MAX 7239832358).

See docs/engineering/claude_floor_grid_negative_note_20261128.md. A lattice is, in one light pen and one connected
crossing group: four or more consecutive equally spaced horizontal rules and the same vertically, each rule crossing at
least three rules of the other direction. Pieces of a rule broken at obstacles count as one rule. Nothing is removed,
withheld or published; nothing on a live path imports this.
"""
from __future__ import annotations

import bisect
import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    _visible_source_stroke_paint,
)
from pb_migration_contracts import EvidenceResolutionStatus

FLOOR_GRID_VERSION = "floor-grid-linework-1.0.0"
MIN_RULES = 4
MIN_PITCH_PT = 8.0
MIN_CROSSINGS = 3
MIN_LUMINANCE = 0.25
_RULE_TOL = 0.1  # pieces of one rule share its position
_PITCH_TOL = 0.3
_AXIS_TOL = 1e-3


def _light_pen(row: Mapping[str, Any]) -> tuple | None:
    colour = row.get("color")
    if row.get("fill") is not None or not (isinstance(colour, (tuple, list)) and len(colour) == 3):
        return None
    if not all(type(v) in (int, float) and math.isfinite(v) for v in colour):
        return None
    if sum(colour) / 3.0 < MIN_LUMINANCE or all(v >= 0.995 for v in colour) or not _visible_source_stroke_paint(row):
        return None
    return tuple(round(float(v), 3) for v in colour), round(float(row.get("width") or 0.0), 3)


def _pieces(drawings: Sequence[Any]) -> dict[tuple, list]:
    """{pen: [(horizontal, position, lo, hi, (path, item))]} for axis-aligned light strokes."""
    found: dict[tuple, list] = {}
    for path, row in enumerate(drawings):
        pen = _light_pen(row) if isinstance(row, Mapping) else None
        if pen is None:
            continue
        for item_index, item in enumerate(row.get("items") or ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = tuple(item[1]), tuple(item[2])
            if abs(ay - by) <= _AXIS_TOL and abs(bx - ax) > NOISE_PT:
                found.setdefault(pen, []).append((True, float(ay), min(ax, bx), max(ax, bx), (path, item_index)))
            elif abs(ax - bx) <= _AXIS_TOL and abs(by - ay) > NOISE_PT:
                found.setdefault(pen, []).append((False, float(ax), min(ay, by), max(ay, by), (path, item_index)))
    return found


def _groups(pieces: list) -> list[list]:
    """Pieces joined by crossing, or by lying on one rule and touching."""
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    vertical = sorted((p[1], i) for i, p in enumerate(pieces) if not p[0])
    positions = [x for x, _ in vertical]
    for i, (horizontal, y, x0, x1, _) in enumerate(pieces):
        if not horizontal:
            continue
        for k in range(bisect.bisect_left(positions, x0 - NOISE_PT), bisect.bisect_right(positions, x1 + NOISE_PT)):
            j = vertical[k][1]
            if pieces[j][2] - NOISE_PT <= y <= pieces[j][3] + NOISE_PT:
                union(i, j)
    order = sorted(range(len(pieces)), key=lambda i: (pieces[i][0], round(pieces[i][1] / _RULE_TOL), pieces[i][2]))
    for a, b in pairwise(order):
        p, q = pieces[a], pieces[b]
        if p[0] == q[0] and abs(p[1] - q[1]) <= _RULE_TOL and q[2] <= p[3] + NOISE_PT:
            union(a, b)
    out: dict[int, list] = {}
    for i, piece in enumerate(pieces):
        out.setdefault(find(i), []).append(piece)
    return list(out.values())


def _rules(pieces: list, horizontal: bool) -> list[tuple[float, list]]:
    rows = sorted((p for p in pieces if p[0] == horizontal), key=lambda p: (p[1], p[2], p[4]))
    rules: list[tuple[float, list]] = []
    for piece in rows:
        if rules and piece[1] - rules[-1][1][0][1] <= _RULE_TOL:
            rules[-1][1].append(piece)
        else:
            rules.append((piece[1], [piece]))
    return rules


def _constant_pitch_runs(rules: list) -> list[tuple[float, list]]:
    runs, start = [], 0
    while start + 1 < len(rules):
        pitch = rules[start + 1][0] - rules[start][0]
        end = start + 1
        while end + 1 < len(rules) and abs((rules[end + 1][0] - rules[end][0]) - pitch) <= _PITCH_TOL:
            end += 1
        if pitch >= MIN_PITCH_PT and end - start + 1 >= MIN_RULES:
            runs.append((pitch, rules[start:end + 1]))
            start = end
        else:
            start += 1
    return runs


def _crosses(rule: tuple, others: list) -> int:
    position, pieces = rule
    return sum(1 for other, other_pieces in others
               if any(p[2] - NOISE_PT <= other <= p[3] + NOISE_PT for p in pieces)
               and any(q[2] - NOISE_PT <= position <= q[3] + NOISE_PT for q in other_pieces))


def floor_grid_lattices(drawings: Sequence[Any]) -> list[dict[str, Any]]:
    """Typed lattice records, in a stable order. Report only."""
    records = []
    for pen, pieces in sorted(_pieces(drawings).items()):
        for group in _groups(pieces):
            across = _constant_pitch_runs(_rules(group, True))
            down = _constant_pitch_runs(_rules(group, False))
            for pitch_y, h_rules in across:
                for pitch_x, v_rules in down:
                    h = [r for r in h_rules if _crosses(r, v_rules) >= MIN_CROSSINGS]
                    v = [r for r in v_rules if _crosses(r, h_rules) >= MIN_CROSSINGS]
                    if len(h) < MIN_RULES or len(v) < MIN_RULES:
                        continue
                    members = [p for _pos, rule_pieces in (*h, *v) for p in rule_pieces]
                    xs = [c for p in members for c in ((p[2], p[3]) if p[0] else (p[1],))]
                    ys = [c for p in members for c in ((p[1],) if p[0] else (p[2], p[3]))]
                    records.append({
                        "status": EvidenceResolutionStatus.CANDIDATE,
                        "reason": "regular_light_lattice",
                        "pen": pen, "pitch_x_pt": round(pitch_x, 3), "pitch_y_pt": round(pitch_y, 3),
                        "rules_x": len(v), "rules_y": len(h), "items": tuple(sorted({p[4] for p in members})),
                        "bbox_pdf_pts": (min(xs), min(ys), max(xs), max(ys)),
                        "wall_authority": False, "version": FLOOR_GRID_VERSION,
                    })
    records.sort(key=lambda r: (r["bbox_pdf_pts"], r["pen"], r["items"]))
    return records


def _axis_index(segments) -> dict:
    index: dict[tuple[bool, int], list] = {}
    for (ax, ay), (bx, by) in segments:
        horizontal = abs(ay - by) <= _AXIS_TOL
        if horizontal or abs(ax - bx) <= _AXIS_TOL:
            position = ay if horizontal else ax
            lo, hi = sorted((ax, bx) if horizontal else (ay, by))
            index.setdefault((horizontal, round(position)), []).append((position, lo, hi))
    return index


def _spans(index: dict, horizontal: bool, position: float, lo: float, hi: float) -> list[tuple[float, float]]:
    found = [(max(a, lo), min(b, hi)) for key in (round(position) - 1, round(position), round(position) + 1)
             for line, a, b in index.get((horizontal, key), ())
             if abs(line - position) <= _PITCH_TOL and min(b, hi) > max(a, lo)]
    merged: list[tuple[float, float]] = []
    for a, b in sorted(found):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def _dark_segments(drawings: Sequence[Any]):
    for row in drawings:
        if not isinstance(row, Mapping):
            continue
        stroke, fill = row.get("color"), row.get("fill")
        dark = any(isinstance(c, (tuple, list)) and len(c) == 3 and sum(c) / 3.0 < MIN_LUMINANCE for c in (stroke, fill))
        if not dark:
            continue
        for item in row.get("items") or ():
            if item[0] == "l":
                yield tuple(item[1]), tuple(item[2])
            elif item[0] == "re":
                x0, y0, x1, y1 = (float(v) for v in tuple(item[1]))
                yield from (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)))


def floor_grid_boundary_shares(polygons: Sequence[Sequence[Sequence[float]]], drawings: Sequence[Any],
                               lattices: Sequence[Mapping[str, Any]]) -> list[float]:
    """Per outline, the share of its length drawn by lattice lines alone (dark ink on the same stretch never counts)."""
    grid = _axis_index((tuple(drawings[path]["items"][item][1]), tuple(drawings[path]["items"][item][2]))
                       for record in lattices for path, item in record["items"])
    dark = _axis_index(_dark_segments(drawings))
    shares = []
    for polygon in polygons:
        points = [(float(x), float(y)) for x, y in polygon]
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        total = covered = 0.0
        for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
            total += math.hypot(bx - ax, by - ay)
            horizontal = abs(ay - by) <= _PITCH_TOL
            if not horizontal and abs(ax - bx) > _PITCH_TOL:
                continue
            position = (ay + by) / 2.0 if horizontal else (ax + bx) / 2.0
            lo, hi = sorted((ax, bx) if horizontal else (ay, by))
            for a, b in _spans(grid, horizontal, position, lo, hi):
                hidden = sum(max(0.0, min(b, d1) - max(a, d0)) for d0, d1 in _spans(dark, horizontal, position, lo, hi))
                covered += max(0.0, (b - a) - hidden)
        shares.append(covered / total if total > 0.0 else 0.0)
    return shares


def grid_only_wall_ids(wall_records: Sequence[Any], lattices: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Wall candidates whose every source primitive is a lattice item (``d<path>i<item>`` primitives only)."""
    items = {item for record in lattices for item in record["items"]}
    found = []
    for record in wall_records:
        primitives = tuple(str(p) for p in record.physical_identity.source_primitive_ids)
        parsed = []
        for primitive in primitives:
            path, _, item = primitive[1:].partition("i")
            parsed.append((int(path), int(item)) if primitive.startswith("d") and path.isdigit() and item.isdigit() else None)
        if parsed and all(value in items for value in parsed):
            found.append(record.wall_candidate_id)
    return tuple(sorted(found))
