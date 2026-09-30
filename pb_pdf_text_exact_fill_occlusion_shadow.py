"""Shadow-only exact geometry check for later filled-path text occlusion.

The live PDF text-integrity authority intentionally remains unchanged. This
module evaluates one narrow false-negative mechanism: a later fill-path whose
aggregate bounding box overlaps text even though the actual source-owned
filled geometry does not.

Positive refinement is deliberately restricted to a path that:
* is uniquely owned by the bboxlog sequence number;
* is a fill / fill-stroke drawing with source-owned rectangle items only;
* contains finite, positive-area axis-aligned rectangles; and
* has no positive-area overlap between rectangle items.

For such a path the painted area is exactly the union of the rectangles
regardless of PDF winding / even-odd fill rules. Any mixed geometry,
overlapping rectangle set, ownership ambiguity, non-fill occluder, or missing
producer state abstains. No live or commercial authority consumes this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_exact_fill_geometry import (
    EXACT_FILL_GEOMETRY_OVERLAPPING,
    EXACT_FILL_GEOMETRY_RESOLVED,
    exact_disjoint_rectangle_fill_coverage,
    index_drawings_by_seqno,
)
from pb_pdf_text_integrity_authority import TEXT_OCCLUDED_BY_LATER_PAINT


PDF_TEXT_EXACT_FILL_OCCLUSION_SHADOW_SCHEMA_VERSION = "1.0.0"
TEXT_NOT_OCCLUDED_BY_LATER_PAINT = "text_not_occluded_by_later_paint"

SHADOW_EXACT_FILL_OCCLUSION = (
    "pdf_text_exact_fill_occlusion_shadow_exact_occlusion"
)
SHADOW_EXACT_FILL_CLEAR = "pdf_text_exact_fill_occlusion_shadow_clear"
SHADOW_NO_LATER_OCCLUSION_CANDIDATE = (
    "pdf_text_exact_fill_occlusion_shadow_no_candidate"
)
SHADOW_BBOXLOG_UNAVAILABLE = (
    "pdf_text_exact_fill_occlusion_shadow_bboxlog_unavailable"
)
SHADOW_DRAWINGS_UNAVAILABLE = (
    "pdf_text_exact_fill_occlusion_shadow_drawings_unavailable"
)
SHADOW_TEXT_SEQNO_INVALID = (
    "pdf_text_exact_fill_occlusion_shadow_text_seqno_invalid"
)
SHADOW_NON_FILL_OCCLUDER = (
    "pdf_text_exact_fill_occlusion_shadow_non_fill_occluder"
)
SHADOW_DRAWING_OWNERSHIP_UNRESOLVED = (
    "pdf_text_exact_fill_occlusion_shadow_drawing_ownership_unresolved"
)
SHADOW_UNSUPPORTED_FILL_GEOMETRY = (
    "pdf_text_exact_fill_occlusion_shadow_unsupported_fill_geometry"
)
SHADOW_OVERLAPPING_RECTANGLES = (
    "pdf_text_exact_fill_occlusion_shadow_overlapping_rectangles"
)


@dataclass(frozen=True)
class PdfTextExactFillOcclusionShadow:
    shadow_id: str
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    reason_codes: tuple[str, ...]
    subject_bbox: tuple[float, float, float, float]
    text_sequence_number: int
    bbox_overlap_threshold: float
    current_bbox_candidate_count: int
    exact_fill_path_count: int
    max_exact_coverage_ratio: Optional[float]
    evaluated_fill_sequence_numbers: tuple[int, ...]
    schema_version: str = PDF_TEXT_EXACT_FILL_OCCLUSION_SHADOW_SCHEMA_VERSION


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


def _intersection_ratio(
    subject: Sequence[object],
    other: Sequence[object],
) -> float:
    try:
        x0, y0, x1, y1 = _rect_tuple(subject)
    except (TypeError, ValueError):
        return 0.0
    area = (x1 - x0) * (y1 - y0)
    return _intersection_area(subject, other) / area


def _result(
    *,
    status: EvidenceResolutionStatus,
    proposition: Optional[str],
    reason_codes: Sequence[str],
    subject_bbox: tuple[float, float, float, float],
    text_sequence_number: int,
    bbox_overlap_threshold: float,
    current_bbox_candidate_count: int,
    exact_fill_path_count: int,
    max_exact_coverage_ratio: Optional[float],
    evaluated_fill_sequence_numbers: Sequence[int],
) -> PdfTextExactFillOcclusionShadow:
    unique_reasons = tuple(
        dict.fromkeys(str(code) for code in reason_codes if str(code))
    )
    rounded_coverage = (
        None
        if max_exact_coverage_ratio is None
        else round(float(max_exact_coverage_ratio), 12)
    )
    evaluated = tuple(
        int(value) for value in evaluated_fill_sequence_numbers
    )
    payload = {
        "schema_version": PDF_TEXT_EXACT_FILL_OCCLUSION_SHADOW_SCHEMA_VERSION,
        "status": status.value,
        "proposition": proposition,
        "reason_codes": unique_reasons,
        "subject_bbox": subject_bbox,
        "text_sequence_number": int(text_sequence_number),
        "bbox_overlap_threshold": float(bbox_overlap_threshold),
        "current_bbox_candidate_count": int(current_bbox_candidate_count),
        "exact_fill_path_count": int(exact_fill_path_count),
        "max_exact_coverage_ratio": rounded_coverage,
        "evaluated_fill_sequence_numbers": evaluated,
    }
    return PdfTextExactFillOcclusionShadow(
        shadow_id=stable_contract_id(
            "pdf_text_exact_fill_occlusion_shadow",
            payload,
            digest_chars=32,
        ),
        status=status,
        proposition=proposition,
        reason_codes=unique_reasons,
        subject_bbox=subject_bbox,
        text_sequence_number=int(text_sequence_number),
        bbox_overlap_threshold=float(bbox_overlap_threshold),
        current_bbox_candidate_count=int(current_bbox_candidate_count),
        exact_fill_path_count=int(exact_fill_path_count),
        max_exact_coverage_ratio=rounded_coverage,
        evaluated_fill_sequence_numbers=evaluated,
    )


def resolve_later_paint_occlusion_shadow(
    page: object,
    subject_bbox: Sequence[object],
    text_sequence_number: int,
    *,
    bbox_overlap_threshold: float = 0.65,
) -> PdfTextExactFillOcclusionShadow:
    """Refine only exact disjoint-rectangle fill-path occlusion in shadow."""

    bbox = _rect_tuple(subject_bbox)
    seqno = int(text_sequence_number)
    threshold = float(bbox_overlap_threshold)
    if not math.isfinite(threshold) or not (0.0 < threshold <= 1.0):
        raise ValueError(
            "bbox_overlap_threshold must be finite and in (0, 1]"
        )

    try:
        bboxlog = list(page.get_bboxlog() or ())  # type: ignore[attr-defined]
    except Exception:
        return _result(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=(SHADOW_BBOXLOG_UNAVAILABLE,),
            subject_bbox=bbox,
            text_sequence_number=seqno,
            bbox_overlap_threshold=threshold,
            current_bbox_candidate_count=0,
            exact_fill_path_count=0,
            max_exact_coverage_ratio=None,
            evaluated_fill_sequence_numbers=(),
        )

    if not (0 <= seqno < len(bboxlog)):
        return _result(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=(SHADOW_TEXT_SEQNO_INVALID,),
            subject_bbox=bbox,
            text_sequence_number=seqno,
            bbox_overlap_threshold=threshold,
            current_bbox_candidate_count=0,
            exact_fill_path_count=0,
            max_exact_coverage_ratio=None,
            evaluated_fill_sequence_numbers=(),
        )

    try:
        drawings = list(  # type: ignore[attr-defined]
            page.get_drawings(extended=True) or ()
        )
    except Exception:
        return _result(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=(SHADOW_DRAWINGS_UNAVAILABLE,),
            subject_bbox=bbox,
            text_sequence_number=seqno,
            bbox_overlap_threshold=threshold,
            current_bbox_candidate_count=0,
            exact_fill_path_count=0,
            max_exact_coverage_ratio=None,
            evaluated_fill_sequence_numbers=(),
        )

    by_seqno = index_drawings_by_seqno(drawings)

    current_candidates = 0
    exact_paths = 0
    max_coverage: Optional[float] = None
    evaluated_seqnos: list[int] = []
    unresolved_reasons: list[str] = []

    for paint_seqno, item in enumerate(
        bboxlog[seqno + 1 :],
        start=seqno + 1,
    ):
        try:
            paint_kind, paint_bbox = str(item[0]), item[1]
        except (IndexError, TypeError):
            continue
        if paint_kind not in {
            "fill-path",
            "fill-image",
            "fill-shade",
            "fill-text",
        }:
            continue
        if _intersection_ratio(bbox, paint_bbox) < threshold:
            continue

        current_candidates += 1

        if paint_kind != "fill-path":
            unresolved_reasons.append(SHADOW_NON_FILL_OCCLUDER)
            continue

        owned = by_seqno.get(paint_seqno, ())
        if len(owned) != 1:
            unresolved_reasons.append(
                SHADOW_DRAWING_OWNERSHIP_UNRESOLVED
            )
            continue

        geometry = exact_disjoint_rectangle_fill_coverage(
            owned[0],
            bbox,
        )
        if geometry.status == EXACT_FILL_GEOMETRY_OVERLAPPING:
            unresolved_reasons.append(SHADOW_OVERLAPPING_RECTANGLES)
            continue
        if (
            geometry.status != EXACT_FILL_GEOMETRY_RESOLVED
            or geometry.coverage_ratio is None
        ):
            unresolved_reasons.append(SHADOW_UNSUPPORTED_FILL_GEOMETRY)
            continue

        exact_paths += 1
        evaluated_seqnos.append(paint_seqno)
        coverage = geometry.coverage_ratio
        max_coverage = (
            coverage
            if max_coverage is None
            else max(max_coverage, coverage)
        )
        if coverage >= threshold:
            return _result(
                status=EvidenceResolutionStatus.CORROBORATED,
                proposition=TEXT_OCCLUDED_BY_LATER_PAINT,
                reason_codes=(SHADOW_EXACT_FILL_OCCLUSION,),
                subject_bbox=bbox,
                text_sequence_number=seqno,
                bbox_overlap_threshold=threshold,
                current_bbox_candidate_count=current_candidates,
                exact_fill_path_count=exact_paths,
                max_exact_coverage_ratio=max_coverage,
                evaluated_fill_sequence_numbers=evaluated_seqnos,
            )

    if current_candidates == 0:
        return _result(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=(SHADOW_NO_LATER_OCCLUSION_CANDIDATE,),
            subject_bbox=bbox,
            text_sequence_number=seqno,
            bbox_overlap_threshold=threshold,
            current_bbox_candidate_count=0,
            exact_fill_path_count=0,
            max_exact_coverage_ratio=None,
            evaluated_fill_sequence_numbers=(),
        )

    if unresolved_reasons:
        return _result(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=unresolved_reasons,
            subject_bbox=bbox,
            text_sequence_number=seqno,
            bbox_overlap_threshold=threshold,
            current_bbox_candidate_count=current_candidates,
            exact_fill_path_count=exact_paths,
            max_exact_coverage_ratio=max_coverage,
            evaluated_fill_sequence_numbers=evaluated_seqnos,
        )

    return _result(
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=TEXT_NOT_OCCLUDED_BY_LATER_PAINT,
        reason_codes=(SHADOW_EXACT_FILL_CLEAR,),
        subject_bbox=bbox,
        text_sequence_number=seqno,
        bbox_overlap_threshold=threshold,
        current_bbox_candidate_count=current_candidates,
        exact_fill_path_count=exact_paths,
        max_exact_coverage_ratio=max_coverage,
        evaluated_fill_sequence_numbers=evaluated_seqnos,
    )


__all__ = [
    "PDF_TEXT_EXACT_FILL_OCCLUSION_SHADOW_SCHEMA_VERSION",
    "TEXT_NOT_OCCLUDED_BY_LATER_PAINT",
    "SHADOW_EXACT_FILL_OCCLUSION",
    "SHADOW_EXACT_FILL_CLEAR",
    "SHADOW_NO_LATER_OCCLUSION_CANDIDATE",
    "SHADOW_BBOXLOG_UNAVAILABLE",
    "SHADOW_DRAWINGS_UNAVAILABLE",
    "SHADOW_TEXT_SEQNO_INVALID",
    "SHADOW_NON_FILL_OCCLUDER",
    "SHADOW_DRAWING_OWNERSHIP_UNRESOLVED",
    "SHADOW_UNSUPPORTED_FILL_GEOMETRY",
    "SHADOW_OVERLAPPING_RECTANGLES",
    "PdfTextExactFillOcclusionShadow",
    "resolve_later_paint_occlusion_shadow",
]
