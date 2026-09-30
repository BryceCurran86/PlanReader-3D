"""Shadow-only exact fill/stroke text-pair equivalence.

This module proves one narrow source-state proposition:

    two native texttrace spans are the complementary fill and stroke paints
    of the same logical native PDF word.

It does NOT expose trusted text, relax PdfTextIntegrityAuthority, validate
font decoding, resolve clipping, create structural definitions, bind members,
or publish quantities. The live text-integrity authority must remain
TEXT_TRACE_AMBIGUOUS for a selector before this shadow can resolve a pair.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import (
    TEXT_TRACE_AMBIGUOUS,
    _intersection_ratio,
    _texttrace_spans,
    _trace_text,
    _visibility_status,
)
from pb_source_observation_authority import (
    OBSERVATION_UNAVAILABLE,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    ObservationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


PDF_TEXT_FILL_STROKE_EQUIVALENCE_SHADOW_SCHEMA_VERSION = "1.0.0"
PDF_TEXT_FILL_STROKE_EQUIVALENT = "pdf_text_fill_stroke_equivalent"

FILL_STROKE_SHADOW_RESOLVED = "fill_stroke_text_pair_shadow_resolved"
FILL_STROKE_SHADOW_NOT_APPLICABLE = (
    "fill_stroke_text_pair_shadow_not_applicable"
)
FILL_STROKE_SHADOW_PAIR_CONFLICT = "fill_stroke_text_pair_shadow_pair_conflict"
FILL_STROKE_SHADOW_VISIBILITY_BLOCKED = (
    "fill_stroke_text_pair_shadow_visibility_blocked"
)
FILL_STROKE_SHADOW_PAGE_UNAVAILABLE = (
    "fill_stroke_text_pair_shadow_page_unavailable"
)

_BBOX_TOLERANCE_PT = 1e-6
_FLOAT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class FillStrokeTextPairClassification:
    equivalent: bool
    reason_codes: tuple[str, ...]
    raw_text: str
    bbox: tuple[float, float, float, float]
    sequence_numbers: tuple[int, ...] = ()
    render_modes: tuple[int, ...] = ()
    bboxlog_kinds: tuple[str, ...] = ()
    font_name: str = ""
    layer_name: str = ""
    opacity: Optional[float] = None


@dataclass(frozen=True)
class FillStrokeTextPairShadowResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    reason_codes: tuple[str, ...]
    pair_id: Optional[str]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    observation_id: str
    raw_text: str
    bbox: tuple[float, float, float, float]
    sequence_numbers: tuple[int, ...] = ()
    render_modes: tuple[int, ...] = ()
    bboxlog_kinds: tuple[str, ...] = ()
    live_text_reason_codes: tuple[str, ...] = ()
    schema_version: str = PDF_TEXT_FILL_STROKE_EQUIVALENCE_SHADOW_SCHEMA_VERSION


def _bbox_tuple(value: Sequence[object]) -> tuple[float, float, float, float]:
    if len(value) < 4:
        raise ValueError("text bbox requires four coordinates")
    result = tuple(float(value[index]) for index in range(4))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("text bbox must be finite")
    return result  # type: ignore[return-value]


def _bbox_equal(
    left: Sequence[object],
    right: Sequence[object],
) -> bool:
    try:
        a = _bbox_tuple(left)
        b = _bbox_tuple(right)
    except (TypeError, ValueError):
        return False
    return all(
        abs(left_value - right_value) <= _BBOX_TOLERANCE_PT
        for left_value, right_value in zip(a, b)
    )


def _float_equal(left: object, right: object) -> bool:
    try:
        a = float(left)
        b = float(right)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(a)
        and math.isfinite(b)
        and abs(a - b) <= _FLOAT_TOLERANCE
    )


def _point_signature(value: object) -> Optional[tuple[float, float]]:
    try:
        if hasattr(value, "x") and hasattr(value, "y"):
            x = float(value.x)  # type: ignore[attr-defined]
            y = float(value.y)  # type: ignore[attr-defined]
        else:
            x = float(value[0])  # type: ignore[index]
            y = float(value[1])  # type: ignore[index]
    except (IndexError, TypeError, ValueError, AttributeError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


def _char_signature(
    span: Mapping[str, object],
) -> Optional[tuple[tuple[object, ...], ...]]:
    """Return the complete trace character/glyph identity used by this shadow.

    PyMuPDF trace characters are (unicode, glyph_id, origin, bbox). Every
    component is retained. Unknown or malformed character tuples fail closed.
    """

    signatures: list[tuple[object, ...]] = []
    for char in span.get("chars") or ():  # type: ignore[assignment]
        try:
            unicode_codepoint = int(char[0])  # type: ignore[index]
            glyph_id = int(char[1])  # type: ignore[index]
            origin = _point_signature(char[2])  # type: ignore[index]
            bbox = _bbox_tuple(char[3])  # type: ignore[index]
        except (IndexError, TypeError, ValueError):
            return None
        if origin is None:
            return None
        signatures.append(
            (
                unicode_codepoint,
                glyph_id,
                origin,
                bbox,
            )
        )
    return tuple(signatures) if signatures else None


def _span_seqno(span: Mapping[str, object]) -> Optional[int]:
    try:
        return int(span.get("seqno"))
    except (TypeError, ValueError):
        return None


def _span_render_mode(span: Mapping[str, object]) -> Optional[int]:
    try:
        return int(span.get("type"))
    except (TypeError, ValueError):
        return None


def _candidate_spans(
    page: object,
    raw_text: str,
    bbox: Sequence[object],
) -> tuple[Mapping[str, object], ...]:
    spans = _texttrace_spans(page)
    if spans is None:
        return ()
    out: list[Mapping[str, object]] = []
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        if _trace_text(span) != raw_text:
            continue
        if _intersection_ratio(bbox, span.get("bbox") or ()) <= 0.0:
            continue
        out.append(span)
    return tuple(out)


def classify_fill_stroke_text_pair_shadow(
    page: object,
    word: Mapping[str, object],
) -> FillStrokeTextPairClassification:
    """Classify an exact complementary fill/stroke trace pair.

    This is deliberately stricter than ordinary visual similarity. Exactly two
    complete source traces must own the word and every source-owned identity
    component must agree except for the complementary paint operation.
    """

    raw_text = str(word.get("text") or "")
    try:
        bbox = _bbox_tuple(word.get("bbox") or ())
    except (TypeError, ValueError):
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=(0.0, 0.0, 0.0, 0.0),
        )

    candidates = _candidate_spans(page, raw_text, bbox)
    if len(candidates) != 2:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_NOT_APPLICABLE,),
            raw_text=raw_text,
            bbox=bbox,
        )

    first, second = candidates
    seq_first = _span_seqno(first)
    seq_second = _span_seqno(second)
    if seq_first is None or seq_second is None or seq_first == seq_second:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
        )

    ordered = sorted(
        ((seq_first, first), (seq_second, second)),
        key=lambda item: item[0],
    )
    sequence_numbers = (ordered[0][0], ordered[1][0])
    spans = (ordered[0][1], ordered[1][1])
    if sequence_numbers[1] != sequence_numbers[0] + 1:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )

    if not all(_bbox_equal(span.get("bbox") or (), bbox) for span in spans):
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )
    if not _bbox_equal(
        spans[0].get("bbox") or (),
        spans[1].get("bbox") or (),
    ):
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )

    signatures = (_char_signature(spans[0]), _char_signature(spans[1]))
    if signatures[0] is None or signatures[0] != signatures[1]:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )

    font_names = tuple(str(span.get("font") or "") for span in spans)
    if not font_names[0] or font_names[0] != font_names[1]:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )

    layer_names = tuple(str(span.get("layer") or "") for span in spans)
    if layer_names[0] != layer_names[1]:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )

    if not _float_equal(
        spans[0].get("opacity", 1.0),
        spans[1].get("opacity", 1.0),
    ):
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
        )
    opacity = float(spans[0].get("opacity", 1.0))

    render_modes = tuple(_span_render_mode(span) for span in spans)
    if set(render_modes) != {0, 1}:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
            render_modes=tuple(
                value for value in render_modes if value is not None
            ),
        )

    try:
        bboxlog = list(page.get_bboxlog() or ())  # type: ignore[attr-defined]
    except Exception:
        bboxlog = []
    if any(
        seqno < 0 or seqno >= len(bboxlog)
        for seqno in sequence_numbers
    ):
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
            render_modes=(int(render_modes[0]), int(render_modes[1])),
        )

    bboxlog_kinds = tuple(
        str(bboxlog[seqno][0]) for seqno in sequence_numbers
    )
    if set(bboxlog_kinds) != {"fill-text", "stroke-text"}:
        return FillStrokeTextPairClassification(
            equivalent=False,
            reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            raw_text=raw_text,
            bbox=bbox,
            sequence_numbers=sequence_numbers,
            render_modes=(int(render_modes[0]), int(render_modes[1])),
            bboxlog_kinds=bboxlog_kinds,
        )

    for span, kind, render_mode in zip(
        spans,
        bboxlog_kinds,
        render_modes,
    ):
        expected_kind = "fill-text" if render_mode == 0 else "stroke-text"
        if kind != expected_kind:
            return FillStrokeTextPairClassification(
                equivalent=False,
                reason_codes=(FILL_STROKE_SHADOW_PAIR_CONFLICT,),
                raw_text=raw_text,
                bbox=bbox,
                sequence_numbers=sequence_numbers,
                render_modes=(
                    int(render_modes[0]),
                    int(render_modes[1]),
                ),
                bboxlog_kinds=bboxlog_kinds,
            )

        _status, visibility_reasons, resolved_seqno = _visibility_status(
            page,
            bbox,
            span,
        )
        if visibility_reasons or resolved_seqno != _span_seqno(span):
            return FillStrokeTextPairClassification(
                equivalent=False,
                reason_codes=(
                    FILL_STROKE_SHADOW_VISIBILITY_BLOCKED,
                    *tuple(visibility_reasons),
                ),
                raw_text=raw_text,
                bbox=bbox,
                sequence_numbers=sequence_numbers,
                render_modes=(
                    int(render_modes[0]),
                    int(render_modes[1]),
                ),
                bboxlog_kinds=bboxlog_kinds,
                font_name=font_names[0],
                layer_name=layer_names[0],
                opacity=opacity,
            )

    return FillStrokeTextPairClassification(
        equivalent=True,
        reason_codes=(FILL_STROKE_SHADOW_RESOLVED,),
        raw_text=raw_text,
        bbox=bbox,
        sequence_numbers=sequence_numbers,
        render_modes=(int(render_modes[0]), int(render_modes[1])),
        bboxlog_kinds=bboxlog_kinds,
        font_name=font_names[0],
        layer_name=layer_names[0],
        opacity=opacity,
    )


def _blocked(
    *,
    selector: ObservationSelector,
    published,
    status: EvidenceResolutionStatus,
    reason_codes: Sequence[str],
    receipt=None,
) -> FillStrokeTextPairShadowResult:
    revision = getattr(published, "revision", None)
    return FillStrokeTextPairShadowResult(
        status=status,
        proposition=None,
        reason_codes=tuple(dict.fromkeys(str(code) for code in reason_codes)),
        pair_id=None,
        document_id=(
            str(selector.document_id)
            if revision is None
            else str(revision.document_id)
        ),
        revision_id=str(selector.revision_id),
        source_sha256=str(selector.source_sha256),
        snapshot_id=str(selector.snapshot_id),
        page_id=(
            ""
            if receipt is None
            else str(getattr(receipt, "page_id", "") or "")
        ),
        observation_id=str(selector.observation_id),
        raw_text=(
            ""
            if receipt is None
            else str(getattr(receipt, "raw_text", "") or "")
        ),
        bbox=(
            (0.0, 0.0, 0.0, 0.0)
            if receipt is None
            else _bbox_tuple(getattr(receipt, "geometry", ()))
        ),
        live_text_reason_codes=(
            ()
            if receipt is None
            else tuple(getattr(receipt, "reason_codes", ()) or ())
        ),
    )


def resolve_fill_stroke_text_pair_shadow(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    selector: ObservationSelector,
    source_bytes: bytes,
) -> FillStrokeTextPairShadowResult:
    """Resolve a lineage-bound fill/stroke pair shadow for one native word."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned "
            "SourceVisibilityProducer"
        )
    if type(selector) is not ObservationSelector:
        raise TypeError("selector must be ObservationSelector")
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be immutable bytes")

    published = source_visibility_producer.published_snapshot_for_revision(
        selector.revision_id
    )
    if published is None:
        return _blocked(
            selector=selector,
            published=None,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OBSERVATION_UNAVAILABLE,),
        )

    if (
        selector.document_id != published.revision.document_id
        or selector.revision_id != published.revision.revision_id
        or selector.source_sha256 != published.revision.source_sha256
        or selector.snapshot_id != published.snapshot.snapshot_id
    ):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SNAPSHOT_MISMATCH,),
        )

    if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(SOURCE_HASH_MISMATCH,),
        )

    live = source_visibility_producer.text_integrity_authority().resolve_text(
        selector
    )
    receipt = live.receipt
    if receipt is None:
        return _blocked(
            selector=selector,
            published=published,
            status=live.status,
            reason_codes=live.reason_codes or (OBSERVATION_UNAVAILABLE,),
        )

    # This shadow is allowed to explain only the live authority's existing
    # trace-ownership ambiguity. It never supersedes a trusted result or any
    # independent decoding / visibility blocker.
    if (
        live.status is EvidenceResolutionStatus.CORROBORATED
        or TEXT_TRACE_AMBIGUOUS not in tuple(live.reason_codes)
    ):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FILL_STROKE_SHADOW_NOT_APPLICABLE,),
            receipt=receipt,
        )

    try:
        page_index = int(receipt.page_id) - 1
    except (TypeError, ValueError):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FILL_STROKE_SHADOW_PAGE_UNAVAILABLE,),
            receipt=receipt,
        )

    try:
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
    except Exception:
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FILL_STROKE_SHADOW_PAGE_UNAVAILABLE,),
            receipt=receipt,
        )
    try:
        if page_index < 0 or page_index >= int(pdf.page_count):
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(FILL_STROKE_SHADOW_PAGE_UNAVAILABLE,),
                receipt=receipt,
            )
        page = pdf.load_page(page_index)
        classification = classify_fill_stroke_text_pair_shadow(
            page,
            {
                "text": receipt.raw_text,
                "bbox": tuple(receipt.geometry),
            },
        )
    finally:
        pdf.close()

    if not classification.equivalent:
        return FillStrokeTextPairShadowResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            reason_codes=classification.reason_codes,
            pair_id=None,
            document_id=str(published.revision.document_id),
            revision_id=str(published.revision.revision_id),
            source_sha256=str(published.revision.source_sha256),
            snapshot_id=str(published.snapshot.snapshot_id),
            page_id=str(receipt.page_id),
            observation_id=str(selector.observation_id),
            raw_text=str(receipt.raw_text),
            bbox=classification.bbox,
            sequence_numbers=classification.sequence_numbers,
            render_modes=classification.render_modes,
            bboxlog_kinds=classification.bboxlog_kinds,
            live_text_reason_codes=tuple(live.reason_codes),
        )

    pair_id = stable_contract_id(
        "pdf_text_fill_stroke_equivalence_shadow_v1",
        {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_id": receipt.page_id,
            "observation_id": selector.observation_id,
            "raw_text": receipt.raw_text,
            "bbox": classification.bbox,
            "sequence_numbers": classification.sequence_numbers,
            "render_modes": classification.render_modes,
            "bboxlog_kinds": classification.bboxlog_kinds,
        },
        digest_chars=32,
    )
    return FillStrokeTextPairShadowResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PDF_TEXT_FILL_STROKE_EQUIVALENT,
        reason_codes=(FILL_STROKE_SHADOW_RESOLVED,),
        pair_id=pair_id,
        document_id=str(published.revision.document_id),
        revision_id=str(published.revision.revision_id),
        source_sha256=str(published.revision.source_sha256),
        snapshot_id=str(published.snapshot.snapshot_id),
        page_id=str(receipt.page_id),
        observation_id=str(selector.observation_id),
        raw_text=str(receipt.raw_text),
        bbox=classification.bbox,
        sequence_numbers=classification.sequence_numbers,
        render_modes=classification.render_modes,
        bboxlog_kinds=classification.bboxlog_kinds,
        live_text_reason_codes=tuple(live.reason_codes),
    )


__all__ = [
    "PDF_TEXT_FILL_STROKE_EQUIVALENCE_SHADOW_SCHEMA_VERSION",
    "PDF_TEXT_FILL_STROKE_EQUIVALENT",
    "FILL_STROKE_SHADOW_RESOLVED",
    "FILL_STROKE_SHADOW_NOT_APPLICABLE",
    "FILL_STROKE_SHADOW_PAIR_CONFLICT",
    "FILL_STROKE_SHADOW_VISIBILITY_BLOCKED",
    "FILL_STROKE_SHADOW_PAGE_UNAVAILABLE",
    "FillStrokeTextPairClassification",
    "FillStrokeTextPairShadowResult",
    "classify_fill_stroke_text_pair_shadow",
    "resolve_fill_stroke_text_pair_shadow",
]
