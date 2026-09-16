"""Conservative native-PDF text render evidence.

This module reports only page-appearance facts for native text traces. It does
not prove Unicode decoding, bind text to semantic entities, or authorize any
quantity. Positive render eligibility therefore remains a prerequisite rather
than a dimension authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


PROVEN_RENDERED = "PROVEN_RENDERED"
PROVEN_NON_RENDERING = "PROVEN_NON_RENDERING"
PROVEN_OCCLUDED = "PROVEN_OCCLUDED"
UNRESOLVED_PARTIAL_OCCLUSION = "UNRESOLVED_PARTIAL_OCCLUSION"
UNRESOLVED_CONTRAST = "UNRESOLVED_CONTRAST"
UNRESOLVED_RENDER_STATE = "UNRESOLVED_RENDER_STATE"


@dataclass(frozen=True)
class NativeTextRenderEvidence:
    raw_text: str
    bbox: tuple[float, float, float, float]
    render_state: str
    render_eligible: bool
    sequence_number: int | None
    reason_codes: tuple[str, ...]


def _rect(value: Sequence[object]) -> tuple[float, float, float, float] | None:
    if len(value) < 4:
        return None
    try:
        result = tuple(float(value[index]) for index in range(4))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in result):
        return None
    x0, y0, x1, y1 = result
    if x1 < x0 or y1 < y0:
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
    return (x0, y0, x1, y1)


def _contains(outer: Sequence[object], inner: Sequence[object]) -> bool:
    a = _rect(outer)
    b = _rect(inner)
    if a is None or b is None:
        return False
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


def _intersects(left: Sequence[object], right: Sequence[object]) -> bool:
    a = _rect(left)
    b = _rect(right)
    if a is None or b is None:
        return False
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _trace_text(trace: object) -> str:
    if not isinstance(trace, dict):
        return ""
    result: list[str] = []
    for char in trace.get("chars") or ():
        try:
            result.append(chr(int(char[0])))
        except (IndexError, TypeError, ValueError, OverflowError):
            return ""
    return "".join(result)


def _trace_bbox(trace: object) -> tuple[float, float, float, float] | None:
    if not isinstance(trace, dict):
        return None
    value = trace.get("bbox")
    if value is None:
        chars = trace.get("chars") or ()
        boxes = []
        for char in chars:
            try:
                box = _rect(char[3])
            except (IndexError, TypeError):
                box = None
            if box is not None:
                boxes.append(box)
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    return _rect(value)


def _colour_is_default_page_white(trace: dict) -> bool:
    colour = trace.get("color")
    try:
        values = tuple(float(item) for item in colour)
    except (TypeError, ValueError):
        return False
    if len(values) < 3:
        return False
    return all(value >= 0.99 for value in values[:3])


def _classify_trace(trace: dict, bboxlog: Sequence[object]) -> NativeTextRenderEvidence:
    raw_text = _trace_text(trace)
    bbox = _trace_bbox(trace)
    if bbox is None:
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=(0.0, 0.0, 0.0, 0.0),
            render_state=UNRESOLVED_RENDER_STATE,
            render_eligible=False,
            sequence_number=None,
            reason_codes=("native_text_render_bbox_unresolved",),
        )

    try:
        seqno = int(trace.get("seqno"))
    except (TypeError, ValueError):
        seqno = -1
    try:
        opacity = float(trace.get("opacity", 0.0))
    except (TypeError, ValueError):
        opacity = 0.0
    try:
        render_type = int(trace.get("type", 99))
    except (TypeError, ValueError):
        render_type = 99

    logged_kind = ""
    if 0 <= seqno < len(bboxlog):
        entry = bboxlog[seqno]
        try:
            logged_kind = str(entry[0])
        except (IndexError, TypeError):
            logged_kind = ""

    if opacity <= 0.0 or render_type > 1 or logged_kind == "ignore-text":
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=bbox,
            render_state=PROVEN_NON_RENDERING,
            render_eligible=False,
            sequence_number=seqno if seqno >= 0 else None,
            reason_codes=("native_text_proven_non_rendering",),
        )

    later_full_cover = False
    later_partial_cover = False
    if seqno >= 0:
        for index, entry in enumerate(bboxlog):
            if index <= seqno:
                continue
            try:
                kind = str(entry[0])
                other_bbox = entry[1]
            except (IndexError, TypeError):
                continue
            if kind not in {"fill-path", "fill-image", "fill-shade"}:
                continue
            if _contains(other_bbox, bbox):
                later_full_cover = True
                break
            if _intersects(other_bbox, bbox):
                later_partial_cover = True

    if later_full_cover:
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=bbox,
            render_state=PROVEN_OCCLUDED,
            render_eligible=False,
            sequence_number=seqno if seqno >= 0 else None,
            reason_codes=("native_text_proven_later_full_occlusion",),
        )
    if later_partial_cover:
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=bbox,
            render_state=UNRESOLVED_PARTIAL_OCCLUSION,
            render_eligible=False,
            sequence_number=seqno if seqno >= 0 else None,
            reason_codes=("native_text_partial_occlusion_unresolved",),
        )
    if _colour_is_default_page_white(trace):
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=bbox,
            render_state=UNRESOLVED_CONTRAST,
            render_eligible=False,
            sequence_number=seqno if seqno >= 0 else None,
            reason_codes=("native_text_default_page_contrast_unresolved",),
        )
    if logged_kind not in {"fill-text", "stroke-text", ""}:
        return NativeTextRenderEvidence(
            raw_text=raw_text,
            bbox=bbox,
            render_state=UNRESOLVED_RENDER_STATE,
            render_eligible=False,
            sequence_number=seqno if seqno >= 0 else None,
            reason_codes=("native_text_render_operation_unresolved",),
        )

    return NativeTextRenderEvidence(
        raw_text=raw_text,
        bbox=bbox,
        render_state=PROVEN_RENDERED,
        render_eligible=True,
        sequence_number=seqno if seqno >= 0 else None,
        reason_codes=("native_text_proven_rendered",),
    )


def extract_native_text_render_evidence(page: object) -> tuple[NativeTextRenderEvidence, ...]:
    """Return conservative render-only evidence for native text traces."""
    try:
        traces = tuple(page.get_texttrace() or ())  # type: ignore[attr-defined]
        bboxlog = tuple(page.get_bboxlog() or ())  # type: ignore[attr-defined]
    except Exception:
        return ()
    records = [
        _classify_trace(trace, bboxlog)
        for trace in traces
        if isinstance(trace, dict) and _trace_text(trace)
    ]
    return tuple(records)


__all__ = [
    "NativeTextRenderEvidence",
    "PROVEN_NON_RENDERING",
    "PROVEN_OCCLUDED",
    "PROVEN_RENDERED",
    "UNRESOLVED_CONTRAST",
    "UNRESOLVED_PARTIAL_OCCLUSION",
    "UNRESOLVED_RENDER_STATE",
    "extract_native_text_render_evidence",
]
