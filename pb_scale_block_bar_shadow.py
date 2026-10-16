"""Shadow-only detector for block-style graphic scale bars (alternating blocks with a numeral at every block edge).

Why this exists. ``pb_physical_scale_authority`` accepts one bar model: a baseline with exactly one perpendicular tick
crossing each endpoint, a ``0`` at one end and a physical label (for example ``10 m``) at the other. It deliberately
refuses rectangle corners as ticks. A block bar (a row of filled and empty rectangles, ``0 1 2 ... 10m`` under its block
edges) has no such ticks, so on such a sheet the producer reports ``physical_scale_bar_unavailable`` even though the
sheet states its scale at every metre. This module measures that evidence and nothing else.

Evidence reported. Numerals form an arithmetic progression ``0, s, 2s, ... N s`` on one baseline, equally spaced, with the
physical unit on a label of the run (``10m``); a vertical block edge lies under (or over) at least 70 % of those labels,
within 1 pt of each label centre. The fit gives points per millimetre; the residuals of both the labels and the edges
are reported, together with how that compares to any printed ratio such as ``1:100`` (corroboration only).

Not done. It does not raise any authority, does not replace or call the scale producer, does not accept a ratio as
a scale, and does not choose between several bars: every candidate is returned. A plausible bar is not a
measurement authority until the existing scale producer (or its reviewed successor) accepts it.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, List, Mapping, Optional, Sequence, Tuple

BLOCK_SCALE_BAR_SCHEMA_VERSION = "1.0.0"

MIN_LABELS = 4                      # a bar with fewer labelled edges is not distinguishable from a number row
LABEL_SPACING_TOL_FRACTION = 0.015  # equal-spacing tolerance relative to the step (and at least 0.5 pt)
LABEL_SPACING_TOL_MIN_PT = 0.5
EDGE_MATCH_TOL_PT = 1.0             # a block edge lies within this of its label centre (along the bar)
MIN_EDGE_MATCH_FRACTION = 0.7
ROW_BASELINE_TOL_FRACTION = 0.35    # numerals of one row share a baseline within this fraction of their height
EDGE_SEARCH_HEIGHTS = 6.0           # block edges lie within this many numeral heights of the row
EDGE_MIN_HEIGHTS = 0.4              # a block edge is at least this tall (numeral heights) and at most EDGE_MAX_HEIGHTS
EDGE_MAX_HEIGHTS = 3.5
MM_PER_POINT_AT_1_TO_1 = 25.4 / 72.0

_NUMERAL_RE = re.compile(r"^\s*(\d{1,4})\s*(mm|cm|m)?\s*$", re.IGNORECASE)
_RATIO_RE = re.compile(r"\b(\d{1,3})\s*:\s*(\d{1,5})\b")
_UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}


@dataclass(frozen=True)
class BlockScaleBarCandidate:
    axis: str                              # "x" for a horizontal bar, "y" for a vertical one (native frame)
    label_texts: Tuple[str, ...]
    label_ids: Tuple[str, ...]
    edge_segment_ids: Tuple[str, ...]
    span_pt: float
    physical_span_mm: float
    points_per_mm: float
    label_residual_pt: float               # worst deviation of a label centre from the fitted line
    edge_residual_pt: float                # worst deviation of a matched block edge from the fitted line
    matched_edge_count: int
    printed_ratio_candidates: Tuple[float, ...]
    printed_ratio_relative_difference: Tuple[float, ...]


@dataclass(frozen=True)
class BlockScaleBarReport:
    candidates: Tuple[BlockScaleBarCandidate, ...]
    schema_version: str = BLOCK_SCALE_BAR_SCHEMA_VERSION
    shadow_only: bool = True
    scale_authority_granted: bool = False


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _words(words: Sequence[Mapping[str, Any]]) -> List[Tuple[str, str, Tuple[float, float, float, float]]]:
    out = []
    for position, word in enumerate(words):
        text = str(word.get("text") or "")
        box = word.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        values = tuple(_num(v) for v in box)
        if any(v is None for v in values):
            continue
        x0, y0, x1, y1 = values  # type: ignore[misc]
        if x1 <= x0 or y1 <= y0:
            continue
        ident = str(word.get("id") if word.get("id") not in (None, "") else f"word:{position}")
        out.append((ident, text, (x0, y0, x1, y1)))
    out.sort(key=lambda w: w[0])
    return out


def _vertical_edges(segments: Sequence[Mapping[str, Any]], axis: str):
    """Segments perpendicular to the bar axis (block edges): (id, coordinate along the axis, lo, hi across it)."""
    edges = []
    for position, segment in enumerate(segments):
        vals = tuple(_num(segment.get(k)) for k in ("x1", "y1", "x2", "y2"))
        if any(v is None for v in vals):
            continue
        x1, y1, x2, y2 = vals  # type: ignore[misc]
        ident = str(segment.get("id") if segment.get("id") not in (None, "") else f"anon:{position}")
        if axis == "x" and abs(x1 - x2) < 0.02 and abs(y1 - y2) > 0.0:
            edges.append((ident, (x1 + x2) / 2, min(y1, y2), max(y1, y2)))
        elif axis == "y" and abs(y1 - y2) < 0.02 and abs(x1 - x2) > 0.0:
            edges.append((ident, (y1 + y2) / 2, min(x1, x2), max(x1, x2)))
    edges.sort(key=lambda e: (e[1], e[0]))
    return edges


def detect_block_scale_bars(
    segments: Sequence[Mapping[str, Any]],
    words: Sequence[Mapping[str, Any]],
) -> BlockScaleBarReport:
    """Return every block-style scale bar candidate. Pure, deterministic, input-order invariant."""
    parsed = _words(words)
    ratios: List[float] = []
    for _, text, _ in parsed:
        for match in _RATIO_RE.finditer(text):
            a, b = int(match.group(1)), int(match.group(2))
            if a == 1 and b > 1:
                ratios.append(float(b))
    ratios = sorted(set(ratios))

    numerals = []
    for ident, text, (x0, y0, x1, y1) in parsed:
        match = _NUMERAL_RE.match(text)
        if match is None:
            continue
        numerals.append((ident, int(match.group(1)), (match.group(2) or "").lower(), text, (x0, y0, x1, y1)))

    candidates: List[BlockScaleBarCandidate] = []
    for axis in ("x", "y"):
        edges = _vertical_edges(segments, axis)
        # a "row" is a set of numerals sharing a baseline (axis "x") or a centre line (axis "y")
        rows: List[List[Tuple[Any, ...]]] = []
        def across(n):  # coordinate across the bar
            b = n[4]
            return (b[1] + b[3]) / 2 if axis == "x" else (b[0] + b[2]) / 2

        def along(n):
            b = n[4]
            return (b[0] + b[2]) / 2 if axis == "x" else (b[1] + b[3]) / 2

        def size(n):
            b = n[4]
            return (b[3] - b[1]) if axis == "x" else (b[2] - b[0])

        for n in sorted(numerals, key=lambda n: (across(n), along(n), n[0])):
            placed = False
            for row in rows:
                if abs(across(row[0]) - across(n)) <= ROW_BASELINE_TOL_FRACTION * max(size(row[0]), size(n)):
                    row.append(n)
                    placed = True
                    break
            if not placed:
                rows.append([n])
        for row in rows:
            row.sort(key=lambda n: (along(n), n[0]))
            if len(row) < MIN_LABELS:
                continue
            # every run of consecutive row members that forms 0, s, 2s, ... with equal spacing
            for start in range(len(row)):
                if row[start][1] != 0:
                    continue
                for step_idx in range(start + 1, min(start + 2, len(row))):     # the step is set by the adjacent numeral
                    step = row[step_idx][1] - row[start][1]
                    if step <= 0:
                        continue
                    run = [row[start]]
                    expected = step
                    spacing = along(row[step_idx]) - along(row[start])
                    if spacing <= 0:
                        continue
                    nxt = step_idx
                    run.append(row[nxt])
                    k = 2
                    pos = nxt + 1
                    while pos < len(row):
                        candidate = row[pos]
                        if candidate[1] == k * step and abs(along(candidate) - (along(row[start]) + k * spacing)) <= max(
                                LABEL_SPACING_TOL_MIN_PT, LABEL_SPACING_TOL_FRACTION * spacing):
                            run.append(candidate)
                            k += 1
                        pos += 1
                    if len(run) < MIN_LABELS:
                        continue
                    if any(abs(along(r) - (along(run[0]) + (r[1] // step) * spacing)) > max(
                            LABEL_SPACING_TOL_MIN_PT, LABEL_SPACING_TOL_FRACTION * spacing) for r in run):
                        continue
                    units = {r[2] for r in run if r[2]}
                    if len(units) != 1:
                        continue                                    # no unit, or conflicting units: not a scale bar
                    unit = next(iter(units))
                    # block edges under (or over) the labels
                    height = max(size(r) for r in run)
                    y_row = across(run[0])
                    matched: List[Tuple[str, float, float]] = []
                    for r in run:
                        best = None
                        for ident, coord, lo, hi in edges:
                            if abs(coord - along(r)) > EDGE_MATCH_TOL_PT:
                                continue
                            tall = hi - lo
                            if not (EDGE_MIN_HEIGHTS * height <= tall <= EDGE_MAX_HEIGHTS * height):
                                continue
                            mid = (lo + hi) / 2
                            if abs(mid - y_row) > EDGE_SEARCH_HEIGHTS * height:
                                continue
                            if best is None or abs(coord - along(r)) < abs(best[1] - along(r)):
                                best = (ident, coord, abs(coord - along(r)))
                        if best is not None:
                            matched.append(best)
                    if len(matched) < MIN_EDGE_MATCH_FRACTION * len(run):
                        continue
                    xs = [along(r) for r in run]
                    values = [r[1] for r in run]
                    n = len(run)
                    mean_x, mean_v = sum(xs) / n, sum(values) / n
                    slope = sum((x - mean_x) * (v - mean_v) for x, v in zip(xs, values)) / sum(
                        (v - mean_v) ** 2 for v in values)          # points per unit
                    intercept = mean_x - slope * mean_v
                    label_residual = max(abs(x - (intercept + slope * v)) for x, v in zip(xs, values))
                    edge_residual = 0.0
                    for ident, coord, _ in matched:
                        nearest = min(values, key=lambda v: abs(coord - (intercept + slope * v)))
                        edge_residual = max(edge_residual, abs(coord - (intercept + slope * nearest)))
                    mm_per_unit = _UNIT_MM[unit]
                    points_per_mm = slope / mm_per_unit
                    span_pt = slope * (values[-1] - values[0])
                    diffs = tuple(round(abs(points_per_mm - (1.0 / (MM_PER_POINT_AT_1_TO_1 * ratio))) /
                                        (1.0 / (MM_PER_POINT_AT_1_TO_1 * ratio)), 6) for ratio in ratios)
                    candidates.append(BlockScaleBarCandidate(
                        axis=axis,
                        label_texts=tuple(r[3] for r in run),
                        label_ids=tuple(r[0] for r in run),
                        edge_segment_ids=tuple(sorted({m[0] for m in matched})),
                        span_pt=round(span_pt, 6),
                        physical_span_mm=round((values[-1] - values[0]) * mm_per_unit, 6),
                        points_per_mm=round(points_per_mm, 9),
                        label_residual_pt=round(label_residual, 6),
                        edge_residual_pt=round(edge_residual, 6),
                        matched_edge_count=len(matched),
                        printed_ratio_candidates=tuple(ratios),
                        printed_ratio_relative_difference=diffs,
                    ))
                    break                                           # the first (smallest) step defines this run
    unique = {}
    for c in candidates:
        unique.setdefault((c.axis, c.label_ids), c)
    ordered = tuple(unique[k] for k in sorted(unique))
    return BlockScaleBarReport(ordered)
