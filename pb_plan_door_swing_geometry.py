"""Count unlabeled floor-plan door swings from native cubic geometry.

Architectural plans often draw a door as a quarter-circle cubic Bézier
(axis-aligned tangents, equal radii). Window-corner fillets use the same
primitive at a smaller, repeated radius.

This module never reads opening tags, callout sizes, or BOQ identities.
It only counts dark quarter-circle cubics and reports how many sit in a
rare larger-radius cluster above the fillet mode.

The caller may emit ``D1`` only when that cluster contains exactly one
swing and no typed door identity already exists. Two or more unlabeled
swings stay silent rather than inventing D1/D2 splits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import fitz

from pb_opening_tag_normalization import normalize_opening_tag

_FLOOR_PLAN_RE = re.compile(
    r"\bfloor\s+plan\b|\bplan\s*:\s*floor\b",
    re.I,
)
_MIN_QUARTER_RADIUS_PT = 12.0
_MAX_QUARTER_RADIUS_PT = 90.0
_MIN_DOOR_RADIUS_PT = 28.0
_MAX_DOOR_RADIUS_PT = 80.0
_EQUAL_RADIUS_RATIO = 0.75
_AXIS_TOL_PT = 1.5
_FILLET_CLUSTER_MIN = 8
_OUTLIER_RATIO = 1.55
_RADIUS_BUCKET_PT = 2.0
_PAIRED_RADIUS_RATIO_MAX = 1.08
_PAIRED_CENTER_DY_PT = 2.5
_PAIRED_SPACING_MIN_RATIO = 0.80
_PAIRED_SPACING_MAX_RATIO = 1.25
_PAIRED_DIMENSION_MIN_MM = 900
_PAIRED_DIMENSION_MAX_MM = 2400
_PAIRED_DIMENSION_MAX_DY_PT = 50.0
_PAIRED_DIMENSION_MAX_DX_PT = 14.0
_PAIRED_REPEAT_MIN = 2
_PAIRED_REPEAT_MAX = 6
_PAIRED_WIDTH_TOL_MM = 50


@dataclass(frozen=True)
class QuarterCircleCubic:
    radius: float
    x: float
    y: float
    page: int


@dataclass(frozen=True)
class PlanDoorSwingCount:
    count: int
    source_page: int
    evidence_text: str


def page_is_floor_plan(text: str) -> bool:
    return bool(_FLOOR_PLAN_RE.search(text or ""))


def _point_xy(point) -> Optional[Tuple[float, float]]:
    try:
        return float(point.x), float(point.y)
    except Exception:
        try:
            return float(point[0]), float(point[1])
        except Exception:
            return None


def _is_dark_stroke(color) -> bool:
    if not color:
        return True
    try:
        return max(float(c) for c in color) <= 0.65
    except TypeError:
        try:
            return float(color) <= 0.65
        except (TypeError, ValueError):
            return True


def iter_quarter_circle_cubics(page: fitz.Page, page_num: int) -> List[QuarterCircleCubic]:
    """Return dark axis-aligned quarter-circle cubics on *page*."""
    hits: List[QuarterCircleCubic] = []
    try:
        drawings = page.get_drawings() or []
    except Exception:
        return hits
    for drawing in drawings:
        if not _is_dark_stroke(drawing.get("color")):
            continue
        for item in drawing.get("items") or []:
            if not item or item[0] != "c" or len(item) < 4:
                continue
            pts = [_point_xy(p) for p in item[1:]]
            if any(p is None for p in pts):
                continue
            start, end = pts[0], pts[-1]
            radius_x = abs(end[0] - start[0])
            radius_y = abs(end[1] - start[1])
            if radius_x < _MIN_QUARTER_RADIUS_PT or radius_y < _MIN_QUARTER_RADIUS_PT:
                continue
            if radius_x > _MAX_QUARTER_RADIUS_PT or radius_y > _MAX_QUARTER_RADIUS_PT:
                continue
            if min(radius_x, radius_y) / max(radius_x, radius_y) < _EQUAL_RADIUS_RATIO:
                continue
            ctrl = pts[1]
            axis_aligned = (
                abs(ctrl[0] - start[0]) < _AXIS_TOL_PT
                or abs(ctrl[1] - start[1]) < _AXIS_TOL_PT
            )
            if not axis_aligned:
                continue
            hits.append(
                QuarterCircleCubic(
                    radius=0.5 * (radius_x + radius_y),
                    x=(start[0] + end[0]) / 2.0,
                    y=(start[1] + end[1]) / 2.0,
                    page=page_num,
                )
            )
    return hits


def _bucket(radius: float) -> int:
    return int(round(radius / _RADIUS_BUCKET_PT) * _RADIUS_BUCKET_PT)


def unlabeled_door_swing_count(hits: Sequence[QuarterCircleCubic]) -> int:
    """How many cubics sit in the rare door-swing radius cluster."""
    if not hits:
        return 0
    buckets: dict[int, int] = {}
    for hit in hits:
        key = _bucket(hit.radius)
        buckets[key] = buckets.get(key, 0) + 1
    modal_r, modal_n = max(buckets.items(), key=lambda item: (item[1], -item[0]))

    if modal_n >= _FILLET_CLUSTER_MIN:
        threshold = max(_MIN_DOOR_RADIUS_PT, _OUTLIER_RATIO * float(modal_r))
        return sum(1 for hit in hits if hit.radius >= threshold)

    doorish = [
        hit
        for hit in hits
        if _MIN_DOOR_RADIUS_PT <= hit.radius <= _MAX_DOOR_RADIUS_PT
    ]
    if not doorish:
        return 0
    radii = [hit.radius for hit in doorish]
    if max(radii) / max(min(radii), 1e-6) > 1.25:
        return 0
    return len(doorish)


def should_emit_sole_unlabeled_door(
    count: int,
    existing_tags: Iterable[str],
) -> bool:
    """True when a single unlabeled plan swing may be emitted as D1."""
    if count != 1:
        return False
    for tag in existing_tags:
        norm = normalize_opening_tag(tag)
        if norm is not None and norm.trade_type == "doors":
            return False
    return True


def _word_dimension_mm(word: Sequence[Any]) -> Optional[int]:
    """Return a plausible figured door width from one native PDF word."""
    if len(word) < 5:
        return None
    raw = str(word[4] or "").strip().replace(",", "")
    if re.fullmatch(r"\d{3,4}", raw) is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if not (_PAIRED_DIMENSION_MIN_MM <= value <= _PAIRED_DIMENSION_MAX_MM):
        return None
    return value


def dimensioned_paired_door_swings(
    hits: Sequence[QuarterCircleCubic],
    words: Sequence[Sequence[Any]],
) -> Tuple[int, Tuple[int, ...], str]:
    """Count repeated double-leaf swing pairs backed by local figured widths.

    Small window fillets can look similar to paired door arcs, so geometry
    alone is not authority here. Every accepted pair must have a native
    900..2400 mm figured width centered directly beside it, and repeated
    instances must agree on that width.
    """
    if len(hits) < 2:
        return 0, (), ""

    candidates = sorted(hits, key=lambda h: (h.page, h.y, h.x))
    native_dims: list[tuple[float, float, int]] = []
    for word in words:
        value = _word_dimension_mm(word)
        if value is None:
            continue
        try:
            x0, y0, x1, y1 = map(float, word[:4])
        except (TypeError, ValueError):
            continue
        native_dims.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0, value))

    used: set[int] = set()
    matched: list[tuple[QuarterCircleCubic, QuarterCircleCubic, int]] = []

    for i, left in enumerate(candidates):
        if i in used:
            continue
        best: Optional[tuple[int, QuarterCircleCubic, int, float]] = None
        for j in range(i + 1, len(candidates)):
            if j in used:
                continue
            right = candidates[j]
            if right.page != left.page:
                continue
            if abs(right.y - left.y) > _PAIRED_CENTER_DY_PT:
                continue
            mean_r = 0.5 * (left.radius + right.radius)
            if mean_r <= 0:
                continue
            radius_ratio = max(left.radius, right.radius) / max(
                min(left.radius, right.radius), 1e-6
            )
            if radius_ratio > _PAIRED_RADIUS_RATIO_MAX:
                continue
            spacing = abs(right.x - left.x)
            spacing_ratio = spacing / mean_r
            if not (
                _PAIRED_SPACING_MIN_RATIO
                <= spacing_ratio
                <= _PAIRED_SPACING_MAX_RATIO
            ):
                continue

            mid_x = 0.5 * (left.x + right.x)
            mid_y = 0.5 * (left.y + right.y)
            dim_matches: list[tuple[float, int]] = []
            for dim_x, dim_y, width_mm in native_dims:
                dx = abs(dim_x - mid_x)
                dy = abs(dim_y - mid_y)
                if dx <= max(_PAIRED_DIMENSION_MAX_DX_PT, 0.9 * mean_r) and (
                    4.0 <= dy <= _PAIRED_DIMENSION_MAX_DY_PT
                ):
                    dim_matches.append((dx + 0.15 * dy, width_mm))
            if not dim_matches:
                continue
            dim_matches.sort(key=lambda item: item[0])
            score, width_mm = dim_matches[0]
            if best is None or score < best[3]:
                best = (j, right, width_mm, score)

        if best is None:
            continue
        j, right, width_mm, _ = best
        used.add(i)
        used.add(j)
        matched.append((left, right, width_mm))

    count = len(matched)
    if count < _PAIRED_REPEAT_MIN or count > _PAIRED_REPEAT_MAX:
        return 0, (), ""

    widths = tuple(item[2] for item in matched)
    if max(widths) - min(widths) > _PAIRED_WIDTH_TOL_MM:
        return 0, (), ""

    evidence = "; ".join(
        (
            f"{width}mm:"
            f"r={left.radius:.2f}@({left.x:.1f},{left.y:.1f})+"
            f"r={right.radius:.2f}@({right.x:.1f},{right.y:.1f})"
        )
        for left, right, width in matched
    )
    return count, widths, evidence


def should_emit_dimensioned_repeated_door_total(
    count: int,
    existing_tags: Iterable[str],
) -> bool:
    """Allow D1 only for repeated, dimension-backed identical door symbols."""
    if count < _PAIRED_REPEAT_MIN or count > _PAIRED_REPEAT_MAX:
        return False
    for tag in existing_tags:
        norm = normalize_opening_tag(tag)
        if norm is not None and norm.trade_type == "doors":
            return False
    return True


def extract_dimensioned_repeated_plan_doors(
    doc: fitz.Document,
    pages: Sequence[int],
) -> Optional[PlanDoorSwingCount]:
    """Resolve repeated paired native door swings from floor-plan pages."""
    found: List[PlanDoorSwingCount] = []
    for pno in pages:
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        text = page.get_text("text") or ""
        if not page_is_floor_plan(text):
            continue
        hits = iter_quarter_circle_cubics(page, pno + 1)
        try:
            words = page.get_text("words") or []
        except Exception:
            words = []
        count, widths, evidence = dimensioned_paired_door_swings(hits, words)
        if count <= 0:
            continue
        found.append(
            PlanDoorSwingCount(
                count=count,
                source_page=pno + 1,
                evidence_text=(
                    f"paired_dimensioned_native_swings widths={list(widths)}; {evidence}"
                ),
            )
        )
    if not found:
        return None
    counts = {item.count for item in found}
    if len(counts) != 1:
        return None
    return found[0]


def extract_sole_plan_door_swing(
    doc: fitz.Document,
    pages: Sequence[int],
) -> Optional[PlanDoorSwingCount]:
    """Return a sole unlabeled door-swing count from floor-plan pages.

    Duplicate floor-plan copies that each show one swing still count as one
    door. Any floor-plan page with two or more unlabeled swings fails closed
    so D1/D2 splits are never invented from geometry alone.
    """
    found: List[PlanDoorSwingCount] = []
    for pno in pages:
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        text = page.get_text("text") or ""
        if not page_is_floor_plan(text):
            continue
        hits = iter_quarter_circle_cubics(page, pno + 1)
        count = unlabeled_door_swing_count(hits)
        if count <= 0:
            continue
        evidence = "; ".join(
            f"r={hit.radius:.1f}@({hit.x:.1f},{hit.y:.1f})" for hit in hits[:12]
        )
        found.append(
            PlanDoorSwingCount(
                count=count,
                source_page=pno + 1,
                evidence_text=evidence,
            )
        )
    if not found:
        return None
    if max(item.count for item in found) != 1:
        return None
    return found[0]
