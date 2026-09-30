"""Neutral exact geometry helpers for rectangle-only PDF fill paths.

This module owns no text-trust or structural semantics. It answers only whether
one producer-owned drawing is a provably exact union of disjoint filled
rectangles and, when so, how much of a subject rectangle that fill covers.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Sequence


EXACT_FILL_GEOMETRY_RESOLVED = "resolved"
EXACT_FILL_GEOMETRY_UNSUPPORTED = "unsupported_geometry"
EXACT_FILL_GEOMETRY_OVERLAPPING = "overlapping_rectangles"


@dataclass(frozen=True)
class ExactFillCoverageResult:
    status: str
    coverage_ratio: Optional[float]
    rectangles: tuple[tuple[float, float, float, float], ...] = ()


def _rect_tuple(
    value: Sequence[object],
) -> tuple[float, float, float, float]:
    if len(value) < 4:
        raise ValueError("rectangle requires four coordinates")
    result = tuple(float(value[index]) for index in range(4))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("rectangle coordinates must be finite")
    x0, y0, x1, y1 = result
    if x1 <= x0 or y1 <= y0:
        raise ValueError("rectangle must have positive area")
    return x0, y0, x1, y1


def _intersection_area(
    first: Sequence[object],
    second: Sequence[object],
) -> float:
    try:
        ax0, ay0, ax1, ay1 = _rect_tuple(first)
        bx0, by0, bx1, by1 = _rect_tuple(second)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(
        0.0,
        min(ay1, by1) - max(ay0, by0),
    )


def index_drawings_by_seqno(
    drawings: Sequence[object],
) -> dict[int, tuple[Mapping[str, object], ...]]:
    grouped: dict[int, list[Mapping[str, object]]] = {}
    for drawing in drawings:
        if not isinstance(drawing, Mapping):
            continue
        try:
            seqno = int(drawing.get("seqno"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        grouped.setdefault(seqno, []).append(drawing)
    return {
        seqno: tuple(rows)
        for seqno, rows in grouped.items()
    }


def exact_disjoint_rectangle_fill_coverage(
    drawing: Mapping[str, object],
    subject_bbox: Sequence[object],
) -> ExactFillCoverageResult:
    """Return exact subject coverage for one proven rectangle-only fill.

    Positive resolution requires a fill/fill-stroke drawing containing only
    positive-area rectangle items whose interiors do not overlap. Disjoint
    rectangles are exact under either non-zero or even-odd fill rules.
    """
    if str(drawing.get("type") or "") not in {"f", "fs"}:
        return ExactFillCoverageResult(
            status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
            coverage_ratio=None,
        )
    if drawing.get("fill") is None:
        return ExactFillCoverageResult(
            status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
            coverage_ratio=None,
        )

    items = tuple(drawing.get("items") or ())
    if not items:
        return ExactFillCoverageResult(
            status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
            coverage_ratio=None,
        )

    try:
        subject = _rect_tuple(subject_bbox)
    except (TypeError, ValueError):
        return ExactFillCoverageResult(
            status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
            coverage_ratio=None,
        )

    rectangles: list[tuple[float, float, float, float]] = []
    for item in items:
        if (
            not isinstance(item, (tuple, list))
            or len(item) < 2
            or item[0] != "re"
        ):
            return ExactFillCoverageResult(
                status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
                coverage_ratio=None,
            )
        try:
            rectangles.append(_rect_tuple(item[1]))
        except (TypeError, ValueError):
            return ExactFillCoverageResult(
                status=EXACT_FILL_GEOMETRY_UNSUPPORTED,
                coverage_ratio=None,
            )

    for index, first in enumerate(rectangles):
        for second in rectangles[index + 1 :]:
            if _intersection_area(first, second) > 1e-9:
                return ExactFillCoverageResult(
                    status=EXACT_FILL_GEOMETRY_OVERLAPPING,
                    coverage_ratio=None,
                    rectangles=tuple(rectangles),
                )

    x0, y0, x1, y1 = subject
    subject_area = (x1 - x0) * (y1 - y0)
    covered = sum(
        _intersection_area(subject, rectangle)
        for rectangle in rectangles
    )
    coverage = min(1.0, max(0.0, covered / subject_area))
    return ExactFillCoverageResult(
        status=EXACT_FILL_GEOMETRY_RESOLVED,
        coverage_ratio=coverage,
        rectangles=tuple(rectangles),
    )


__all__ = [
    "EXACT_FILL_GEOMETRY_RESOLVED",
    "EXACT_FILL_GEOMETRY_UNSUPPORTED",
    "EXACT_FILL_GEOMETRY_OVERLAPPING",
    "ExactFillCoverageResult",
    "index_drawings_by_seqno",
    "exact_disjoint_rectangle_fill_coverage",
]
