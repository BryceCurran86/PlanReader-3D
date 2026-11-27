"""Reusable generic vector-outlined text extraction shadow (multi-DPI render/OCR).

Shadow-only, default-off source-evidence module for architectural PDFs whose
plan/section/setout/schedule text is stored as vector path outlines rather than
embedded font glyphs. Enforces bounded clip rendering, multi-DPI agreement, and
full spatial/SHA provenance. Never invents finish specifications or commercial
quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Callable, Sequence

SHADOW_SCHEMA_VERSION = "1.0.0"
DEFAULT_RENDER_DPIS: tuple[int, ...] = (216, 288, 360)

_DIMENSION_MM_RE = re.compile(r"^\d{3,5}$")
_OPENING_MARK_RE = re.compile(r"^(?:D|W|GD|SD|SL|FD)\s*-?\s*\d{1,3}[A-Z]?$", re.IGNORECASE)


@dataclass(frozen=True)
class OutlinedTextBodyAssessment:
    page_index: int
    total_native_words: int
    border_native_words: int
    body_native_words: int
    vector_drawing_count: int
    raster_image_count: int
    outlined_text_suspected: bool


@dataclass(frozen=True)
class OcrRawToken:
    text: str
    bbox_px: tuple[float, float, float, float]
    confidence: float = 1.0


@dataclass(frozen=True)
class AgreedOutlinedTextToken:
    normalized_text: str
    raw_texts: tuple[str, ...]
    source_sha256: str
    page_index: int
    bbox_pdf_pts: tuple[float, float, float, float]
    agreement_dpis: tuple[int, ...]
    agreement_ratio: float
    mean_confidence: float


@dataclass(frozen=True)
class VectorOutlinedTextExtractionResult:
    status: str
    source_sha256: str
    page_index: int
    region_bbox_pts: tuple[float, float, float, float]
    render_dpis: tuple[int, ...]
    agreed_tokens: tuple[AgreedOutlinedTextToken, ...]
    rejected_single_dpi_count: int
    rejected_conflicting_count: int
    receipt_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


@dataclass(frozen=True)
class OutlinedCrossSheetWitnessReview:
    status: str
    source_sha256: str
    corroborated_dimension_tokens: tuple[str, ...]
    corroborated_opening_marks: tuple[str, ...]
    finish_authority_status: str
    finish_authority_reason: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


def normalize_outlined_token(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip()).upper()
    return cleaned


def detect_outlined_text_drawing_body(
    page: Any,
    *,
    page_index: int,
    right_border_fraction: float = 0.80,
    bottom_border_fraction: float = 0.85,
    max_body_words_for_outlined: int = 20,
    min_vector_drawings_for_outlined: int = 500,
) -> OutlinedTextBodyAssessment:
    """Classify whether a page's drawing body likely stores text as vector outlines."""
    words = page.get_text("words") or ()
    drawings = page.get_drawings() or ()
    images = page.get_images() or ()
    width = float(page.rect.width)
    height = float(page.rect.height)
    body_words = sum(
        1
        for w in words
        if float(w[2]) < width * right_border_fraction
        and float(w[3]) < height * bottom_border_fraction
    )
    total_words = len(words)
    border_words = total_words - body_words
    suspected = (
        body_words <= max_body_words_for_outlined
        and len(drawings) >= min_vector_drawings_for_outlined
        and len(images) == 0
    )
    return OutlinedTextBodyAssessment(
        page_index=page_index,
        total_native_words=total_words,
        border_native_words=border_words,
        body_native_words=body_words,
        vector_drawing_count=len(drawings),
        raster_image_count=len(images),
        outlined_text_suspected=suspected,
    )


def _default_rapidocr_callable(png_bytes: bytes) -> list[OcrRawToken]:
    from rapidocr import RapidOCR  # type: ignore

    engine = _RAPIDOCR_SINGLETON.get("engine")
    if engine is None:
        engine = RapidOCR()
        _RAPIDOCR_SINGLETON["engine"] = engine
    res = engine(png_bytes)
    tokens: list[OcrRawToken] = []
    boxes = getattr(res, "boxes", None)
    txts = getattr(res, "txts", None)
    scores = getattr(res, "scores", None)
    if boxes is not None and txts is not None:
        score_seq = scores if scores is not None else [1.0] * len(txts)
        for box, txt, sc in zip(boxes, txts, score_seq):
            xs = [float(pt[0]) for pt in box]
            ys = [float(pt[1]) for pt in box]
            tokens.append(
                OcrRawToken(
                    text=str(txt),
                    bbox_px=(min(xs), min(ys), max(xs), max(ys)),
                    confidence=float(sc),
                )
            )
    return tokens


_RAPIDOCR_SINGLETON: dict[str, Any] = {}


def _px_to_pdf_bbox(
    bbox_px: tuple[float, float, float, float],
    clip_pts: tuple[float, float, float, float],
    dpi: int,
) -> tuple[float, float, float, float]:
    scale = 72.0 / float(dpi)
    cx0, cy0, _cx1, _cy1 = clip_pts
    return (
        round(cx0 + float(bbox_px[0]) * scale, 3),
        round(cy0 + float(bbox_px[1]) * scale, 3),
        round(cx0 + float(bbox_px[2]) * scale, 3),
        round(cy0 + float(bbox_px[3]) * scale, 3),
    )


def _center(b: tuple[float, float, float, float]) -> tuple[float, float]:
    return (0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]))


def extract_vector_outlined_text_multi_dpi_shadow(
    *,
    page: Any,
    source_sha256: str,
    page_index: int,
    region_bbox_pts: tuple[float, float, float, float],
    render_dpis: Sequence[int] = DEFAULT_RENDER_DPIS,
    ocr_callable: Callable[[bytes], Sequence[OcrRawToken]] | None = None,
    min_dpi_agreement: int = 2,
    max_center_drift_pts: float = 6.0,
    min_confidence: float = 0.50,
) -> VectorOutlinedTextExtractionResult:
    """Render a bounded PDF clip at multiple DPIs and retain only agreed OCR tokens."""
    clean_sha = str(source_sha256 or "").strip()
    dpis = tuple(sorted({int(d) for d in render_dpis if isinstance(d, int) and d >= 72}))
    rx0, ry0, rx1, ry1 = (float(v) for v in region_bbox_pts)

    if len(clean_sha) < 16 or page_index < 0 or rx1 <= rx0 or ry1 <= ry0:
        return _abstain_extraction(
            source_sha256=clean_sha,
            page_index=page_index,
            region_bbox_pts=(rx0, ry0, rx1, ry1),
            render_dpis=dpis,
            reasons=("invalid_provenance_or_region_clip",),
        )
    if len(dpis) < max(2, min_dpi_agreement):
        return _abstain_extraction(
            source_sha256=clean_sha,
            page_index=page_index,
            region_bbox_pts=(rx0, ry0, rx1, ry1),
            render_dpis=dpis,
            reasons=("insufficient_distinct_render_dpis",),
        )

    import fitz

    backend = ocr_callable or _default_rapidocr_callable
    clip = fitz.Rect(rx0, ry0, rx1, ry1)
    observations: list[tuple[int, str, str, tuple[float, float, float, float], float]] = []
    for dpi in dpis:
        pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        png_bytes = pix.tobytes("png")
        for tok in backend(png_bytes):
            if float(tok.confidence) < min_confidence:
                continue
            norm = normalize_outlined_token(tok.text)
            if not norm:
                continue
            pdf_box = _px_to_pdf_bbox(tok.bbox_px, (rx0, ry0, rx1, ry1), dpi)
            observations.append((dpi, norm, str(tok.text), pdf_box, float(tok.confidence)))

    # Cluster spatial observations across distinct DPIs
    clusters: list[list[tuple[int, str, str, tuple[float, float, float, float], float]]] = []
    for obs in observations:
        oc = _center(obs[3])
        placed = False
        for cl in clusters:
            cc = _center(cl[0][3])
            if math.hypot(oc[0] - cc[0], oc[1] - cc[1]) <= max_center_drift_pts:
                cl.append(obs)
                placed = True
                break
        if not placed:
            clusters.append([obs])

    agreed: list[AgreedOutlinedTextToken] = []
    rejected_single = 0
    rejected_conflict = 0

    for cl in clusters:
        by_dpi: dict[int, list[tuple[int, str, str, tuple[float, float, float, float], float]]] = {}
        for item in cl:
            by_dpi.setdefault(item[0], []).append(item)
        if len(by_dpi) < min_dpi_agreement:
            rejected_single += 1
            continue
        # Pick top-confidence text per DPI and require unanimous normalized text across agreeing DPIs
        per_dpi_best = [max(items, key=lambda x: x[4]) for items in by_dpi.values()]
        distinct_norms = {item[1] for item in per_dpi_best}
        if len(distinct_norms) != 1:
            rejected_conflict += 1
            continue
        norm_txt = next(iter(distinct_norms))
        agreed_dpis = tuple(sorted(item[0] for item in per_dpi_best))
        avg_box = (
            round(sum(item[3][0] for item in per_dpi_best) / len(per_dpi_best), 3),
            round(sum(item[3][1] for item in per_dpi_best) / len(per_dpi_best), 3),
            round(sum(item[3][2] for item in per_dpi_best) / len(per_dpi_best), 3),
            round(sum(item[3][3] for item in per_dpi_best) / len(per_dpi_best), 3),
        )
        mean_conf = round(sum(item[4] for item in per_dpi_best) / len(per_dpi_best), 4)
        agreed.append(
            AgreedOutlinedTextToken(
                normalized_text=norm_txt,
                raw_texts=tuple(item[2] for item in sorted(per_dpi_best, key=lambda x: x[0])),
                source_sha256=clean_sha,
                page_index=page_index,
                bbox_pdf_pts=avg_box,
                agreement_dpis=agreed_dpis,
                agreement_ratio=round(len(agreed_dpis) / len(dpis), 4),
                mean_confidence=mean_conf,
            )
        )

    agreed.sort(key=lambda t: (t.bbox_pdf_pts[1], t.bbox_pdf_pts[0], t.normalized_text))
    receipt_payload = {
        "source_sha256": clean_sha,
        "page_index": page_index,
        "region_bbox_pts": (round(rx0, 3), round(ry0, 3), round(rx1, 3), round(ry1, 3)),
        "render_dpis": dpis,
        "agreed_count": len(agreed),
        "tokens": [(t.normalized_text, t.bbox_pdf_pts, t.agreement_dpis) for t in agreed],
    }
    receipt_sha = hashlib.sha256(json.dumps(receipt_payload, sort_keys=True).encode("utf-8")).hexdigest()

    if not agreed:
        return VectorOutlinedTextExtractionResult(
            status="ABSTAINED",
            source_sha256=clean_sha,
            page_index=page_index,
            region_bbox_pts=(rx0, ry0, rx1, ry1),
            render_dpis=dpis,
            agreed_tokens=(),
            rejected_single_dpi_count=rejected_single,
            rejected_conflicting_count=rejected_conflict,
            receipt_sha256=receipt_sha,
            reason_codes=("no_multi_dpi_agreed_outlined_tokens",),
        )

    return VectorOutlinedTextExtractionResult(
        status="CORROBORATED_MULTI_DPI_OUTLINED_TEXT_SHADOW",
        source_sha256=clean_sha,
        page_index=page_index,
        region_bbox_pts=(rx0, ry0, rx1, ry1),
        render_dpis=dpis,
        agreed_tokens=tuple(agreed),
        rejected_single_dpi_count=rejected_single,
        rejected_conflicting_count=rejected_conflict,
        receipt_sha256=receipt_sha,
        reason_codes=("multi_dpi_outlined_text_corroborated_shadow",),
    )


def reconcile_outlined_cross_sheet_witness_shadow(
    *,
    extractions: Sequence[VectorOutlinedTextExtractionResult],
    expected_source_sha256: str,
    finish_specification_present: bool = False,
) -> OutlinedCrossSheetWitnessReview:
    """Reconcile multi-DPI agreed dimension/opening marks; abstain finishes if spec missing."""
    clean_sha = str(expected_source_sha256 or "").strip()
    if len(clean_sha) < 16 or not extractions:
        return OutlinedCrossSheetWitnessReview(
            status="ABSTAINED",
            source_sha256=clean_sha,
            corroborated_dimension_tokens=(),
            corroborated_opening_marks=(),
            finish_authority_status="ABSTAINED",
            finish_authority_reason="material_specification_missing",
            reason_codes=("source_provenance_or_extractions_missing",),
        )

    for ext in extractions:
        if ext.source_sha256 != clean_sha:
            return OutlinedCrossSheetWitnessReview(
                status="ABSTAINED",
                source_sha256=clean_sha,
                corroborated_dimension_tokens=(),
                corroborated_opening_marks=(),
                finish_authority_status="ABSTAINED",
                finish_authority_reason="cross_revision_or_region_sha_mismatch",
                reason_codes=("cross_revision_or_region_sha_mismatch",),
            )

    dims: set[str] = set()
    marks: set[str] = set()
    for ext in extractions:
        for tok in ext.agreed_tokens:
            val = tok.normalized_text.replace(",", "").strip()
            if _DIMENSION_MM_RE.fullmatch(val):
                mm = int(val)
                if 100 <= mm <= 30000:
                    dims.add(str(mm))
            if _OPENING_MARK_RE.fullmatch(tok.normalized_text):
                marks.add(tok.normalized_text.replace(" ", ""))

    fin_status = "REVIEW_ONLY_SPEC_PRESENT" if finish_specification_present else "ABSTAINED"
    fin_reason = (
        "finish_specification_present_pending_host_binding"
        if finish_specification_present
        else "material_specification_missing"
    )
    if not dims and not marks:
        return OutlinedCrossSheetWitnessReview(
            status="ABSTAINED",
            source_sha256=clean_sha,
            corroborated_dimension_tokens=(),
            corroborated_opening_marks=(),
            finish_authority_status=fin_status,
            finish_authority_reason=fin_reason,
            reason_codes=("no_corroborated_dimension_or_opening_witnesses",),
        )

    return OutlinedCrossSheetWitnessReview(
        status="REVIEW_ONLY_OUTLINED_WITNESSES_RECONCILED",
        source_sha256=clean_sha,
        corroborated_dimension_tokens=tuple(sorted(dims)),
        corroborated_opening_marks=tuple(sorted(marks)),
        finish_authority_status=fin_status,
        finish_authority_reason=fin_reason,
        reason_codes=("outlined_cross_sheet_witnesses_corroborated_review_only",),
    )


def _abstain_extraction(
    *,
    source_sha256: str,
    page_index: int,
    region_bbox_pts: tuple[float, float, float, float],
    render_dpis: tuple[int, ...],
    reasons: tuple[str, ...],
) -> VectorOutlinedTextExtractionResult:
    digest = hashlib.sha256(
        json.dumps({"sha": source_sha256, "page": page_index, "reasons": reasons}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return VectorOutlinedTextExtractionResult(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_index=page_index,
        region_bbox_pts=region_bbox_pts,
        render_dpis=render_dpis,
        agreed_tokens=(),
        rejected_single_dpi_count=0,
        rejected_conflicting_count=0,
        receipt_sha256=digest,
        reason_codes=reasons,
    )


_OUTLINED_CAPTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("roof_plan", re.compile(r"\broof\s+plan\b", re.IGNORECASE)),
    ("site_plan", re.compile(r"\bsite\s+plan\b", re.IGNORECASE)),
    ("reflected_ceiling_plan", re.compile(r"\b(?:reflected\s+)?ceiling\s+plan\b", re.IGNORECASE)),
    ("floor_finish_plan", re.compile(r"\bfloor\s+finish(?:es)?\s+plan\b", re.IGNORECASE)),
    ("floor_plan", re.compile(r"\b(?:ground\s+|first\s+|upper\s+|lower\s+|level\s+\d+\s+)?floor\s+plan\b", re.IGNORECASE)),
    ("elevation", re.compile(r"\b(?:north|south|east|west|front|rear|side|left|right)?\s*elevations?\b", re.IGNORECASE)),
    ("section", re.compile(r"\bsections?\s*(?:[A-Z]\s*[-–—]\s*[A-Z]|\d+)?\b", re.IGNORECASE)),
    ("schedule", re.compile(r"\b(?:door|window|finish(?:es)?|room|hardware)\s+schedule\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class OutlinedCaptionViewClassification:
    """Multi-DPI agreed outlined-vector in-drawing caption classification (A06/Q5446 P0)."""

    status: str  # "CORROBORATED" | "CONFLICT" | "ABSTAINED"
    view_type: str  # "floor_plan" | "roof_plan" | ... | "unproven"
    matched_view_types: tuple[str, ...]
    supporting_texts: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


def classify_outlined_caption_view_type(
    tokens: Sequence[AgreedOutlinedTextToken],
) -> OutlinedCaptionViewClassification:
    """Classify a sheet's view type from multi-DPI agreed outlined-text captions only.

    - Requires ``len(token.agreement_dpis) >= 2`` on every supporting token.
    - Never guesses on conflicting view types (e.g. both ``floor_plan`` and
      ``roof_plan`` on one sheet -> returns ``status="CONFLICT"``).
    - Never grants commercial authority (``shadow_only=True``).
    """
    multi_dpi = [t for t in tokens if len(t.agreement_dpis) >= 2 and t.normalized_text]
    if not multi_dpi:
        return OutlinedCaptionViewClassification(
            status="ABSTAINED",
            view_type="unproven",
            matched_view_types=(),
            supporting_texts=(),
            reason_codes=("no_multi_dpi_agreed_outlined_tokens",),
        )
    # Group tokens on the same visual row (within 10 pt in y) into caption lines
    ordered = sorted(multi_dpi, key=lambda t: (round(t.bbox_pdf_pts[1] / 10.0), t.bbox_pdf_pts[0]))
    lines: list[str] = []
    cur_y: float | None = None
    cur_parts: list[str] = []
    for tok in ordered:
        y = float(tok.bbox_pdf_pts[1])
        if cur_y is None or abs(y - cur_y) <= 10.0:
            cur_parts.append(tok.normalized_text)
            if cur_y is None:
                cur_y = y
        else:
            lines.append(" ".join(cur_parts))
            cur_y = y
            cur_parts = [tok.normalized_text]
    if cur_parts:
        lines.append(" ".join(cur_parts))

    matched_types: set[str] = set()
    supporting: list[str] = []
    for line in lines:
        for view_type, pattern in _OUTLINED_CAPTION_PATTERNS:
            if pattern.search(line):
                matched_types.add(view_type)
                supporting.append(line)
                break  # specific pattern (e.g., roof_plan) takes precedence over generic

    if not matched_types:
        return OutlinedCaptionViewClassification(
            status="ABSTAINED",
            view_type="unproven",
            matched_view_types=(),
            supporting_texts=(),
            reason_codes=("no_outlined_view_caption_matched",),
        )
    sorted_types = tuple(sorted(matched_types))
    if len(sorted_types) > 1:
        return OutlinedCaptionViewClassification(
            status="CONFLICT",
            view_type="unproven",
            matched_view_types=sorted_types,
            supporting_texts=tuple(sorted(set(supporting))),
            reason_codes=("conflicting_outlined_view_captions_on_sheet",),
        )
    return OutlinedCaptionViewClassification(
        status="CORROBORATED",
        view_type=sorted_types[0],
        matched_view_types=sorted_types,
        supporting_texts=tuple(sorted(set(supporting))),
        reason_codes=("outlined_in_drawing_caption_corroborated",),
    )
