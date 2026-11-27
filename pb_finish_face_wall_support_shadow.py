"""Report only (#4764 7225222738, C06/C08): is every edge of a finish-bearing room face on wall evidence?

See docs/engineering/claude_finish_face_wall_support_note_20261128.md. Wall evidence along an edge stretch is either a
second face of the SAME ink running 1.2 to 8 pt behind the face on that edge, with exactly one such face (three faces are
hatch, not a wall), or one of the layered builder's filled wall bars behind the edge. Lines closer together than the
builder's 1.2 pt thinnest wall are one face drawn more than once; lines on the room side are ignored. A remaining
stretch counts as a wall END only when a line is drawn along all of it, it touches a supported wall or closure, and it is
no longer than that wall is thick there -- never on length alone.

``wide_candidate`` is separate and never counts as support: an unsupported stretch whose only same-ink partner is 8 to
14 pt behind (the builder's filled-wall limit), running along at least 70% of the edge, with no further face one thickness
beyond (hatch), and with a drawn same-ink line across the whole band near an end of the pair (a wall return). Ink that is paper white or the
owner's excluded green never counts; no other colour is excluded. A doorway closure given by the caller also covers its
stretch. Thicknesses, minimum length and tolerances are the layered builder's own. Nothing is promoted, closed, removed or
published, and no live path imports this.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from shapely.geometry import Point, Polygon

from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT, _DARK_FILL_THICK_MAX, _STROKE_PAIR_CLUSTER_PT, _STROKE_PAIR_MIN_SPAN, _STROKE_PAIR_THICK_MAX,
    _STROKE_PAIR_THICK_MIN,
    _collect_dark_painted_source_wall_strips, _opaque, _owner_excluded_green_ink, _visible_source_stroke_paint,
)
from pb_migration_contracts import EvidenceResolutionStatus

PAIRED, FILLED, CLOSURE, WALL_END, WIDE = "paired", "filled", "closure", "wall_end", "wide_candidate"
_AROUND_PT = 2.0 * _DARK_FILL_THICK_MAX + _STROKE_PAIR_CLUSTER_PT  # search radius: a wide pair plus its hatch check
_BLACK = (0.0, 0.0, 0.0)


def _paper_white(color: Any) -> bool:
    return isinstance(color, (tuple, list)) and len(color) == 3 and all(
        type(v) in (int, float) and v >= 0.995 for v in color)


def _near(row: Mapping[str, Any], region: tuple[float, float, float, float]) -> bool:
    rect = row.get("rect")
    if rect is None:
        return True
    x0, y0, x1, y1 = (float(v) for v in tuple(rect))  # a flat line has an empty rect: compare the numbers
    return not (x1 < region[0] or x0 > region[2] or y1 < region[1] or y0 > region[3])


def _ink_near(drawings: Sequence[Any], region: tuple[float, float, float, float]):
    """Visible wall-eligible paint near the face: horizontal and vertical lines per ink colour, and the fills.

    Fills are recoloured black only so the builder's bar collector accepts them; list positions are kept."""
    inks: dict[tuple[float, ...], list[tuple[bool, float, float, float]]] = {}
    fills: list[dict | None] = [None] * len(drawings)
    for index, row in enumerate(drawings):
        if not (isinstance(row, Mapping) and row.get("items") and _near(row, region)):
            continue
        stroke, fill = row.get("color"), row.get("fill")
        if fill is not None and not _paper_white(fill):
            if not _owner_excluded_green_ink(fill) and _opaque(row):
                fills[index] = {**row, "color": None, "fill": _BLACK, "layer": ""}
        elif (stroke is not None and not _paper_white(stroke) and not _owner_excluded_green_ink(stroke)
              and _visible_source_stroke_paint(row)):
            lines = inks.setdefault(tuple(round(float(v), 3) for v in stroke), [])
            for item in row["items"]:
                if item[0] != "l":
                    continue
                (ax, ay), (bx, by) = tuple(item[1]), tuple(item[2])
                if abs(ay - by) <= 1e-3 and abs(bx - ax) > NOISE_PT:
                    lines.append((True, (ay + by) / 2.0, min(ax, bx), max(ax, bx)))
                elif abs(ax - bx) <= 1e-3 and abs(by - ay) > NOISE_PT:
                    lines.append((False, (ax + bx) / 2.0, min(ay, by), max(ay, by)))
    return dict(sorted(inks.items())), fills


def _faces(lines, horizontal: bool, line: float, outward: float, start: float, end: float,
           behind_limit: float = _STROKE_PAIR_THICK_MAX):
    """Faces on or behind an edge: (offset of the room-side line, its runs).

    Only lines running beside the edge say which faces there are (lines closer than the thinnest wall are one face);
    other pieces at a face's offsets only extend its runs. So drawing elsewhere on the page changes nothing. Runs shorter
    than the builder's minimum are dropped."""
    band = [((perp - line) * outward, lo, hi) for is_horizontal, perp, lo, hi in lines if is_horizontal == horizontal
            and -NOISE_PT * 2 <= (perp - line) * outward <= _STROKE_PAIR_CLUSTER_PT + behind_limit]
    groups: list[list[float]] = []
    for offset in sorted(offset for offset, lo, hi in band if min(hi, end) > max(lo, start)):
        if groups and offset - groups[-1][-1] < _STROKE_PAIR_THICK_MIN:
            groups[-1].append(offset)
        else:
            groups.append([offset])
    faces = []
    for group in groups:
        runs: list[list[float]] = []
        for lo, hi in sorted((lo, hi) for offset, lo, hi in band if group[0] <= offset <= group[-1]):
            if runs and lo <= runs[-1][1] + _STROKE_PAIR_CLUSTER_PT:
                runs[-1][1] = max(runs[-1][1], hi)
            else:
                runs.append([lo, hi])
        runs = [(lo, hi) for lo, hi in runs if hi - lo >= _STROKE_PAIR_MIN_SPAN]
        if runs:
            faces.append((group[0], runs))
    return faces


def _paired_stretches(lines, horizontal: bool, line: float, outward: float, start: float, end: float):
    """Stretches of an edge with a face of one ink on it and exactly one same-ink face a wall's thickness behind it."""
    faces = _faces(lines, horizontal, line, outward, start, end)
    near = next(((offset, runs) for offset, runs in faces if offset <= _STROKE_PAIR_CLUSTER_PT), None)
    if near is None:
        return []
    behind = [(offset - near[0], runs) for offset, runs in faces
              if _STROKE_PAIR_THICK_MIN <= offset - near[0] <= _STROKE_PAIR_THICK_MAX]
    every = [near[1], *(runs for _thickness, runs in behind)]
    cuts = sorted({start, end, *(v for runs in every for run in runs for v in run if start < v < end)})
    found = []
    for lo, hi in zip(cuts, cuts[1:]):
        middle = (lo + hi) / 2.0
        covers = lambda runs: any(a <= middle <= b for a, b in runs)
        partners = [thickness for thickness, runs in behind if covers(runs)]
        if covers(near[1]) and len(partners) == 1:
            found.append((lo - start, hi - start, partners[0]))
    return found


def _wide_stretches(lines, horizontal: bool, line: float, outward: float, start: float, end: float):
    """Stretches paired only 8 to 14 pt apart, long enough, not hatch, and with a drawn wall return near an end."""
    faces = _faces(lines, horizontal, line, outward, start, end, behind_limit=3.0 * _DARK_FILL_THICK_MAX)
    near = next(((offset, runs) for offset, runs in faces if offset <= _STROKE_PAIR_CLUSTER_PT), None)
    if near is None or any(_STROKE_PAIR_THICK_MIN <= offset - near[0] <= _STROKE_PAIR_THICK_MAX for offset, _ in faces):
        return []
    wide = [(offset - near[0], runs) for offset, runs in faces
            if _STROKE_PAIR_THICK_MAX < offset - near[0] <= _DARK_FILL_THICK_MAX]
    if not wide:
        return []
    thickness, far = wide[0]  # any second face within reach is caught by the next check
    if any(thickness < offset - near[0] <= 2.0 * thickness + _STROKE_PAIR_CLUSTER_PT for offset, _ in faces):
        return []  # a further face one thickness on: hatch or steps, not a wall
    together = [(max(a, c, start), min(b, d, end)) for a, b in near[1] for c, d in far if min(b, d, end) > max(a, c, start)]
    if sum(hi - lo for lo, hi in together) < 0.7 * (end - start):
        return []
    band = sorted((line + outward * near[0], line + outward * (near[0] + thickness)))
    returns = [position for is_horizontal, position, lo, hi in lines if is_horizontal != horizontal
               and lo <= band[0] + _STROKE_PAIR_CLUSTER_PT and hi >= band[1] - _STROKE_PAIR_CLUSTER_PT]
    return [(lo - start, hi - start) for lo, hi in together
            if any(min(abs(position - lo), abs(position - hi)) <= thickness + _STROKE_PAIR_CLUSTER_PT
                   for position in returns)]


def _drawn_on(lines, horizontal: bool, line: float, outward: float, lo: float, hi: float) -> bool:
    """Is a line (any length) drawn along all of [lo, hi] on this edge?"""
    spans = sorted((max(a, lo), min(b, hi)) for is_horizontal, perp, a, b in lines
                   if is_horizontal == horizontal and -NOISE_PT * 2 <= (perp - line) * outward <= _STROKE_PAIR_CLUSTER_PT
                   and min(b, hi) > max(a, lo))
    reach = lo
    for a, b in spans:
        if a > reach + NOISE_PT * 2:
            return False
        reach = max(reach, b)
    return reach >= hi - NOISE_PT * 2


def _uncovered(spans: list[tuple[float, float]], length: float) -> list[tuple[float, float]]:
    gaps, reach = [], 0.0
    for lo, hi in sorted(spans):
        if lo > reach:
            gaps.append((reach, lo))
        reach = max(reach, hi)
    if length > reach:
        gaps.append((reach, length))
    return gaps


def _wall_ends(found: list[dict], inks) -> None:
    """Add each uncovered stretch that is a drawn wall end of a touching supported wall or closure at least as thick."""
    tol = _STROKE_PAIR_CLUSTER_PT
    for index, edge in enumerate(found):
        if edge["axis"] is None:
            continue
        length = edge["length"]
        for lo, hi in _uncovered([s[:2] for s in edge["support"]], length):
            if lo > tol and hi < length - tol:
                continue  # a break in the middle of an edge is not a wall end
            touching = [s for s in edge["support"] if abs(s[1] - lo) <= tol or abs(s[0] - hi) <= tol]
            for corner, other, other_corner in (("a", found[index - 1], "b"),
                                               ("b", found[(index + 1) % len(found)], "a")):
                if min(abs(lo - edge[corner]), abs(hi - edge[corner])) <= tol:
                    touching += [s for s in other["support"]
                                 if min(abs(s[0] - other[other_corner]), abs(s[1] - other[other_corner])) <= tol]
            if any(hi - lo <= thickness + tol and any(
                    _drawn_on(lines, edge["axis"], edge["line"], edge["outward"], edge["start"] + lo, edge["start"] + hi)
                    for key, lines in inks.items() if ink is None or key == ink)
                   for _lo, _hi, thickness, ink in touching):
                edge["ends"].append((lo, hi))


def _union_length(spans: list[tuple[float, float]], length: float) -> tuple[float, float]:
    """(covered length, longest uncovered stretch) of spans already clipped to [0, length]."""
    covered, longest_gap, reach = 0.0, 0.0, 0.0
    for lo, hi in sorted(spans):
        if lo > reach:
            longest_gap = max(longest_gap, lo - reach)
        covered += max(0.0, hi - max(lo, reach))
        reach = max(reach, hi)
    return covered, max(longest_gap, length - reach)


def face_wall_support(polygon: Sequence[tuple[float, float]], drawings: Sequence[Any], closures: Sequence[Any] = ()) -> dict:
    """Per edge of ``polygon``: the stretch on paired or filled wall evidence, on a given doorway closure, or neither."""
    points = [(float(x), float(y)) for x, y in polygon]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    room = Polygon(points)
    if len(points) < 3 or not room.is_valid or room.area <= 0.0:
        return {"status": EvidenceResolutionStatus.ABSTAINED, "reason": "face_polygon_invalid", "edges": []}
    x0, y0, x1, y1 = room.bounds
    inks, fills = _ink_near(drawings, (x0 - _AROUND_PT, y0 - _AROUND_PT, x1 + _AROUND_PT, y1 + _AROUND_PT))
    bars = _collect_dark_painted_source_wall_strips(fills)
    found = []
    for a, b in zip(points, points[1:] + points[:1]):
        length = math.dist(a, b)
        horizontal = abs(a[1] - b[1]) <= NOISE_PT * 2 < abs(a[0] - b[0])
        vertical = abs(a[0] - b[0]) <= NOISE_PT * 2 < abs(a[1] - b[1])
        stretches: dict[str, list[tuple[float, float]]] = {PAIRED: [], FILLED: [], CLOSURE: []}
        support: list[tuple[float, float, float, tuple | None]] = []  # (from, to, wall thickness there, ink)
        edge = {"length": length, "axis": None, "support": support, "stretches": stretches, "ends": [], "wide": []}
        if horizontal or vertical:
            along, across = (0, 1) if horizontal else (1, 0)
            line = (a[across] + b[across]) / 2.0
            start, end = sorted((a[along], b[along]))
            probe = [0.0, 0.0]
            probe[along], probe[across] = (start + end) / 2.0, line + NOISE_PT
            room_above = room.covers(Point(*probe))  # the room lies towards larger ``across``

            edge.update(axis=horizontal, line=line, start=start, a=a[along] - start, b=b[along] - start,
                        outward=-1.0 if room_above else 1.0)

            def clip(lo: float, hi: float) -> tuple[float, float] | None:
                lo, hi = max(lo, start) - start, min(hi, end) - start
                return (lo, hi) if hi > lo else None

            for ink, runs in inks.items():
                for lo, hi, thickness in _paired_stretches(runs, horizontal, line, edge["outward"], start, end):
                    stretches[PAIRED].append((lo, hi))
                    support.append((lo, hi, thickness, ink))
                edge["wide"] += _wide_stretches(runs, horizontal, line, edge["outward"], start, end)
            for strip in bars:
                if not (strip.horizontal if horizontal else strip.vertical):
                    continue
                low, high = strip.band()
                near_face = high if room_above else low  # the bar must lie on the other side of the line
                if abs(near_face - line) <= _STROKE_PAIR_CLUSTER_PT and (span := clip(*strip.span())) is not None:
                    stretches[FILLED].append(span)
                    support.append((*span, high - low, None))
            for closure in closures:
                if closure.horizontal == horizontal and (closure.band[0] - _STROKE_PAIR_CLUSTER_PT <= line
                                                         <= closure.band[1] + _STROKE_PAIR_CLUSTER_PT):
                    if (span := clip(*closure.gap_interval)) is not None:
                        stretches[CLOSURE].append(span)
                        support.append((*span, closure.band[1] - closure.band[0], None))
        found.append(edge)
    _wall_ends(found, inks)
    edges = []
    for edge in found:
        length, stretches = edge["length"], edge["stretches"]
        every = [span for spans in stretches.values() for span in spans] + edge["ends"]
        covered, longest_gap = _union_length(every, length)
        wide = _union_length(every + edge["wide"], length)[0] - covered  # only what the rules above leave bare
        edges.append({
            "length": length,
            **{kind: _union_length(spans, length)[0] for kind, spans in stretches.items()},
            WALL_END: _union_length(edge["ends"], length)[0],
            WIDE: max(0.0, wide),
            "unsupported": max(0.0, length - covered),
            "longest_gap": longest_gap,
        })
    total = sum(edge["length"] for edge in edges)
    supported = all(edge["longest_gap"] <= _STROKE_PAIR_CLUSTER_PT for edge in edges)
    return {
        "status": EvidenceResolutionStatus.CANDIDATE if supported else EvidenceResolutionStatus.ABSTAINED,
        "reason": "every_edge_on_wall_evidence" if supported else "face_edge_without_wall_evidence",
        "edges": edges,
        "unsupported_share": sum(edge["unsupported"] for edge in edges) / total if total else 1.0,
        "wide_candidate_share": sum(edge[WIDE] for edge in edges) / total if total else 0.0,
    }
