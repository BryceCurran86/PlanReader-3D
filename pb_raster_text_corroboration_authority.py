"""Producer-owned raster corroboration of native PDF words (shadow authority).

``PdfTextIntegrityAuthority`` cannot trust a native word whose font program does
not independently confirm the decoded Unicode (for example CID-keyed CFF
subsets: ``text_glyph_mapping_unverified``). This module supplies an
*independent visual* proof for exactly those words, without weakening that
boundary and without touching it.

The native word is a CLAIM, not authority. A word is corroborated only when
the source itself, rendered twice at materially different scales, is read as
that same text:

    producer-owned native word observation
      -> producer-owned PdfTextIntegrity receipt whose blocking reasons are
         exactly ``text_glyph_mapping_unverified``, optionally plus
         ``text_clip_state_unresolved``; the latter can be discharged only
         by the same post-clip rendered-pixel proof below
      -> producer-owned word bbox for ordinary left-to-right text; for a
         non-horizontal source word, only a uniquely bound source texttrace
         character run may replace that bbox as the raster target
      -> the exact region rendered from the immutable stored PDF bytes at
         300 DPI and at 450 DPI (renderer clip; never a page crop)
      -> non-horizontal source text is normalized by one producer-derived,
         lossless quarter-turn before OCR; ordinary text is unchanged
      -> NO padding, NO expansion into neighbouring source pixels and NO
         retry / alternative preprocessing: one deterministic raster pipeline only
         (trying a tight crop, then a padded one, then keeping whichever
         matches the claim would turn preprocessing selection into an
         authority preference)
      -> the production RapidOCR backend run separately on each rasterization
      -> exactly one textual reading per view, identical across both views and
         identical to the native claim (strict equality after NFC + outer
         whitespace only; punctuation and every semantic character preserved).

Anything else abstains: any other text-integrity reason (trace ambiguity,
malformed CMap, explicitly clipped text, hidden/occluded text, decode or glyph
mismatch, ...), zero readings, more than one reading (competing or duplicate detections),
malformed or out-of-bounds OCR geometry, disagreement between the views, or a
reading that differs from the native claim. There is no nearest / first /
highest-confidence / largest-box / edit-distance choice, no confidence
threshold (OCR confidence is retained only as diagnostic provenance), and no
vocabulary correction.

The two views are two independently rendered raster scales read by the SAME OCR
engine. They are not two independent OCR engines and are never described as
such.

The caller supplies only exact immutable lineage and the native observation
address. Word text, bbox, pixels, OCR output, confidence, page parent, source
partition and ToUnicode interpretation are all resolved internally; none can be
passed in. Generic OCR evidence elsewhere stays CANDIDATE-only, and nothing here
alters text-integrity trust, Item 19B, or any commercial quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import math
import unicodedata

import fitz
from types import MappingProxyType
from typing import Mapping, Optional

from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    PdfTextIntegrityAuthority,
)
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    OCRLine,
    RasterOCRBackend,
    select_production_ocr_backend,
)
from pb_source_observation_authority import (
    ObservationSelector,
    ProducerIntegrityError,
    SourceObservationAuthority,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer

RASTER_TEXT_CORROBORATION_SCHEMA_VERSION = "1.0.0"
RASTER_TEXT_CORROBORATION_DPIS: tuple[int, ...] = (300, 450)

RASTER_TEXT_CORROBORATED = "raster_text_corroborated"
RASTER_TEXT_SCOPE_UNAVAILABLE = "raster_text_scope_unavailable"
RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED = "raster_text_source_lineage_unresolved"
RASTER_TEXT_OBSERVATION_NOT_NATIVE_WORD = "raster_text_observation_not_native_word"
RASTER_TEXT_RECEIPT_UNAVAILABLE = "raster_text_integrity_receipt_unavailable"
RASTER_TEXT_INTEGRITY_CONFLICT = "raster_text_integrity_conflict"
RASTER_TEXT_ALREADY_TRUSTED = "raster_text_not_required_already_trusted"
RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY = "raster_text_integrity_not_glyph_only"
RASTER_TEXT_BBOX_INVALID = "raster_text_source_bbox_invalid"
RASTER_TEXT_BACKEND_UNAVAILABLE = "raster_text_backend_unavailable"
RASTER_TEXT_BACKEND_ERROR = "raster_text_backend_error"
RASTER_TEXT_RENDER_FAILED = "raster_text_render_failed"
RASTER_TEXT_PAGE_LINEAGE_MISMATCH = "raster_text_page_lineage_mismatch"
RASTER_TEXT_NO_READING = "raster_text_no_reading"
RASTER_TEXT_COMPETING_READINGS = "raster_text_competing_readings"
RASTER_TEXT_OCR_GEOMETRY_INVALID = "raster_text_ocr_geometry_invalid"
RASTER_TEXT_VIEW_DISAGREEMENT = "raster_text_view_disagreement"
RASTER_TEXT_NATIVE_MISMATCH = "raster_text_native_claim_mismatch"
RASTER_TEXT_RECORD_UNAVAILABLE = "raster_text_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

# OCR geometry must lie inside the OCR image it was read from. A backend may
# report a polygon a hair beyond the pixel grid because of sub-pixel rounding;
# that rounding is the only slack, expressed in pixels, never a fraction of the
# image and never tuned against any result.
_OCR_GEOMETRY_ROUNDING_PX = 2.0


def _rect4(value: object) -> Optional[tuple[float, float, float, float]]:
    try:
        items = tuple(float(v) for v in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if len(items) != 4 or not all(math.isfinite(v) for v in items):
        return None
    x0, y0, x1, y1 = items
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _point2(value: object) -> Optional[tuple[float, float]]:
    try:
        if hasattr(value, "x") and hasattr(value, "y"):
            result = (float(value.x), float(value.y))  # type: ignore[attr-defined]
        else:
            result = (float(value[0]), float(value[1]))  # type: ignore[index]
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    return result if all(math.isfinite(v) for v in result) else None


def _bbox_contains(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-4,
) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def _lossless_rotate(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == -90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if degrees == 90:
        return image.transpose(Image.Transpose.ROTATE_90)
    if degrees == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    return image


def _producer_owned_ocr_target(
    source_producer: SourceObservationProducer,
    *,
    revision_id: str,
    source_sha256: str,
    page_id: str,
    receipt: object,
    word_bbox: tuple[float, float, float, float],
    raw_text: str,
) -> tuple[tuple[float, float, float, float], int]:
    """Resolve one source-owned raster target for non-horizontal native text.

    The historical word bbox remains authoritative for ordinary left-to-right
    text. For text whose authenticated source line direction renders vertical
    or reversed, PyMuPDF's native word bbox can clip glyph ink even though its
    text identity is correct. In that case this helper uses exact source
    character identity (codepoint + origin) to bind the word to one unique
    texttrace character run, takes that run's glyph bboxes as the raster clip,
    and returns one lossless quarter-turn that normalizes its source direction
    to left-to-right before OCR. Any missing or ambiguous source fact falls
    back to the historical word-bbox / zero-rotation path.
    """

    block_no = getattr(receipt, "block_no", None)
    line_no = getattr(receipt, "line_no", None)
    sequence_number = getattr(receipt, "sequence_number", None)
    trace_sequence_numbers = tuple(
        int(value)
        for value in (getattr(receipt, "trace_sequence_numbers", ()) or ())
    )
    if sequence_number is not None:
        sequence_ids = (int(sequence_number),)
    else:
        sequence_ids = trace_sequence_numbers
    if block_no is None or line_no is None or not sequence_ids:
        return word_bbox, 0

    source_bytes = source_producer._store.source_bytes_by_revision.get(str(revision_id))
    if (
        source_bytes is None
        or hashlib.sha256(source_bytes).hexdigest() != str(source_sha256)
    ):
        return word_bbox, 0
    try:
        page_number = int(page_id)
    except (TypeError, ValueError):
        return word_bbox, 0
    if page_number < 1:
        return word_bbox, 0

    try:
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            if page_number > int(pdf.page_count):
                return word_bbox, 0
            page = pdf.load_page(page_number - 1)
            rawdict = page.get_text("rawdict") or {}
            traces = tuple(page.get_texttrace() or ())
            line = rawdict["blocks"][int(block_no)]["lines"][int(line_no)]
            native_direction = _point2(line.get("dir"))
            if native_direction is None:
                return word_bbox, 0

            origin = fitz.Point(0.0, 0.0) * page.rotation_matrix
            endpoint = fitz.Point(*native_direction) * page.rotation_matrix
            display_dx = float(endpoint.x - origin.x)
            display_dy = float(endpoint.y - origin.y)
            magnitude = math.hypot(display_dx, display_dy)
            if magnitude <= 0.0 or not math.isfinite(magnitude):
                return word_bbox, 0
            display_dx /= magnitude
            display_dy /= magnitude
            axis_tol = 1e-6
            if abs(display_dy) <= axis_tol and display_dx > 0.0:
                return word_bbox, 0
            if abs(display_dy) <= axis_tol and display_dx < 0.0:
                rotation_degrees = 180
            elif abs(display_dx) <= axis_tol and display_dy < 0.0:
                rotation_degrees = -90
            elif abs(display_dx) <= axis_tol and display_dy > 0.0:
                rotation_degrees = 90
            else:
                return word_bbox, 0

            native_chars: list[
                tuple[
                    str,
                    tuple[float, float],
                    tuple[float, float, float, float],
                ]
            ] = []
            for span in line.get("spans") or ():
                for char in span.get("chars") or ():
                    char_bbox = _rect4(char.get("bbox"))
                    char_origin = _point2(char.get("origin"))
                    char_text = str(char.get("c") or "")
                    if (
                        char_bbox is not None
                        and char_origin is not None
                        and char_text
                        and _bbox_contains(word_bbox, char_bbox)
                    ):
                        native_chars.append((char_text, char_origin, char_bbox))
            if "".join(item[0] for item in native_chars) != str(raw_text):
                return word_bbox, 0

            trace_chars: list[
                tuple[
                    str,
                    tuple[float, float],
                    tuple[float, float, float, float],
                ]
            ] = []
            sequence_set = set(sequence_ids)
            for span in traces:
                try:
                    seqno = int(span.get("seqno"))
                except (TypeError, ValueError, AttributeError):
                    continue
                if seqno not in sequence_set:
                    continue
                for char in span.get("chars") or ():
                    try:
                        char_text = chr(int(char[0]))
                        char_origin = _point2(char[2])
                        char_bbox = _rect4(char[3])
                    except (IndexError, TypeError, ValueError, OverflowError):
                        continue
                    if char_origin is not None and char_bbox is not None:
                        trace_chars.append((char_text, char_origin, char_bbox))

            run_len = len(native_chars)
            if run_len <= 0 or len(trace_chars) < run_len:
                return word_bbox, 0
            hits: list[
                tuple[
                    tuple[
                        str,
                        tuple[float, float],
                        tuple[float, float, float, float],
                    ],
                    ...,
                ]
            ] = []
            for start in range(0, len(trace_chars) - run_len + 1):
                window = tuple(trace_chars[start : start + run_len])
                matched = True
                for expected, observed in zip(native_chars, window):
                    if expected[0] != observed[0] or any(
                        abs(left - right) > 1e-4
                        for left, right in zip(expected[1], observed[1])
                    ):
                        matched = False
                        break
                if matched:
                    hits.append(window)
            if len(hits) != 1:
                return word_bbox, 0

            boxes = tuple(item[2] for item in hits[0])
            trace_bbox = (
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
                max(box[2] for box in boxes),
                max(box[3] for box in boxes),
            )
            if _rect4(trace_bbox) is None:
                return word_bbox, 0
            return trace_bbox, rotation_degrees
        finally:
            pdf.close()
    except Exception:
        return word_bbox, 0


@dataclass(frozen=True)
class RasterTextCorroborationSelector:
    """Consumer address of one native word. Carries lineage and identity only."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    observation_id: str

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id", "observation_id"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.observation_id,
        )


@dataclass(frozen=True)
class RasterTextView:
    """One independently rendered raster view of the exact word region."""

    dpi: int
    clip_pt: tuple[float, float, float, float]
    image_size_px: tuple[int, int]
    image_png_sha256: str
    line_count: int
    ocr_reading: Optional[str]
    # Diagnostic provenance only. Never compared with a threshold, never used
    # to choose between readings, never part of the record identity.
    ocr_confidence: Optional[float] = None
    # Lossless, source-owned orientation normalization applied exactly once
    # before OCR. Zero preserves the historical exact-render path.
    ocr_rotation_degrees: int = 0


@dataclass(frozen=True)
class RasterTextCorroborationRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    native_observation_id: str
    text_integrity_receipt_id: str
    native_text_integrity_reason_codes: tuple[str, ...]
    source_bbox: tuple[float, float, float, float]
    page_parent_observation_id: str
    source_partition_id: str
    render_dpis: tuple[int, ...]
    backend_name: str
    backend_version: str
    views: tuple[RasterTextView, ...]
    corroborated_text: str
    schema_version: str = RASTER_TEXT_CORROBORATION_SCHEMA_VERSION


@dataclass(frozen=True)
class RasterTextCorroborationResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    corroborated_text: Optional[str] = None
    record: Optional[RasterTextCorroborationRecord] = None
    schema_version: str = RASTER_TEXT_CORROBORATION_SCHEMA_VERSION


def _outcome(
    status: EvidenceResolutionStatus, reason: str, *extra: str
) -> RasterTextCorroborationResult:
    return RasterTextCorroborationResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extra if str(r))])),
    )


def _abstain(reason: str, *extra: str) -> RasterTextCorroborationResult:
    return _outcome(EvidenceResolutionStatus.ABSTAINED, reason, *extra)


def _conflict(reason: str, *extra: str) -> RasterTextCorroborationResult:
    return _outcome(EvidenceResolutionStatus.CONFLICT, reason, *extra)


def normalize_reading(text: Optional[str]) -> str:
    """Deterministic Unicode normalization and outer whitespace only.

    Punctuation, case, digits and internal characters are preserved exactly.
    """

    return unicodedata.normalize("NFC", str(text or "")).strip()


def _geometry_valid(line: OCRLine, size_px: tuple[int, int]) -> bool:
    try:
        x0, y0, x1, y1 = (float(v) for v in line.bbox_px)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return False
    if not (x1 > x0 and y1 > y0):
        return False
    slack = _OCR_GEOMETRY_ROUNDING_PX
    width, height = size_px
    return x0 >= -slack and y0 >= -slack and x1 <= width + slack and y1 <= height + slack


class RasterTextCorroborationAuthority:
    """Read-only lookup of producer-published corroboration outcomes."""

    def __init__(
        self,
        results: Mapping[tuple[str, str, str, str, str], RasterTextCorroborationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "RasterTextCorroborationAuthority must be obtained from "
                "RasterTextCorroborationProducer.authority()"
            )
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: RasterTextCorroborationSelector) -> RasterTextCorroborationResult:
        if type(selector) is not RasterTextCorroborationSelector:
            raise TypeError("selector must be RasterTextCorroborationSelector")
        return self._results.get(selector.key, _abstain(RASTER_TEXT_RECORD_UNAVAILABLE))


class RasterTextCorroborationProducer:
    """Trusted writer of raster-text corroboration records.

    Built only from a producer-owned ``SourceVisibilityProducer``; nothing the
    caller can pass to ``publish`` influences pixels, bbox, claim or reading.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        backend: RasterOCRBackend,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "RasterTextCorroborationProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        self._source: SourceVisibilityProducer = source_visibility_producer
        self._source_producer: SourceObservationProducer = source_visibility_producer._producer
        self._source_authority: SourceObservationAuthority = self._source_producer.authority()
        self._text_authority: PdfTextIntegrityAuthority = source_visibility_producer.text_integrity_authority()
        self._backend = backend
        self._results: dict[tuple[str, str, str, str, str], RasterTextCorroborationResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "RasterTextCorroborationProducer":
        """Production entry with deterministic availability-only OCR selection.

        Backend choice is resolved once before any claim is evaluated using the
        shared production preference order. A failed/no-text result is never
        retried on another engine.
        """

        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        backend, _selection_reason = select_production_ocr_backend()
        return cls(source_visibility_producer, backend, _seal=_PRODUCER_SEAL)

    @classmethod
    def from_source_visibility_producer_for_tests(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        backend: MockOCRBackend,
    ) -> "RasterTextCorroborationProducer":
        """Test-only entry; the exact MockOCRBackend type is the only alternative."""

        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        if type(backend) is not MockOCRBackend:
            raise TypeError("from_source_visibility_producer_for_tests requires exact MockOCRBackend")
        return cls(source_visibility_producer, backend, _seal=_PRODUCER_SEAL)

    def authority(self) -> RasterTextCorroborationAuthority:
        return RasterTextCorroborationAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self, selector: RasterTextCorroborationSelector, result: RasterTextCorroborationResult
    ) -> RasterTextCorroborationResult:
        self._results[selector.key] = result
        return result

    # ------------------------------------------------------------------
    def publish(self, selector: RasterTextCorroborationSelector) -> RasterTextCorroborationResult:
        if type(selector) is not RasterTextCorroborationSelector:
            raise TypeError("selector must be RasterTextCorroborationSelector")
        return self._store(selector, self._evaluate(selector))

    def _evaluate(self, selector: RasterTextCorroborationSelector) -> RasterTextCorroborationResult:
        observation_selector = ObservationSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            observation_id=selector.observation_id,
        )

        # 1. Exact lineage, resolved by the source authority itself.
        source_result = self._source_authority.resolve(observation_selector)
        observation = source_result.observation
        if source_result.status != EvidenceResolutionStatus.CORROBORATED or observation is None:
            return _outcome(
                source_result.status
                if source_result.status != EvidenceResolutionStatus.CORROBORATED
                else EvidenceResolutionStatus.ABSTAINED,
                RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED,
                *source_result.reason_codes,
            )
        if (
            observation.observation_kind != "native_pdf_word"
            or observation.origin_kind != "native"
            or observation.viewport_id is not None
        ):
            return _abstain(RASTER_TEXT_OBSERVATION_NOT_NATIVE_WORD)

        # 2. The word must have cleared every text-integrity condition except
        #    the independent glyph mapping and, optionally, unresolved clip
        #    ownership. The latter is eligible only because the proof below is
        #    performed on the renderer's final post-clip pixels. Explicitly
        #    proven clipping and every other integrity failure remain hard vetoes
        #    before OCR.
        text_result = self._text_authority.resolve_text(observation_selector)
        receipt = text_result.receipt
        if receipt is None:
            return _abstain(RASTER_TEXT_RECEIPT_UNAVAILABLE, *text_result.reason_codes)
        if text_result.status == EvidenceResolutionStatus.CONFLICT:
            return _conflict(RASTER_TEXT_INTEGRITY_CONFLICT, *text_result.reason_codes)
        if text_result.status == EvidenceResolutionStatus.CORROBORATED:
            return _abstain(RASTER_TEXT_ALREADY_TRUSTED)

        receipt_reasons = tuple(receipt.reason_codes)
        receipt_reason_set = set(receipt_reasons)
        raster_admissible_reasons = {
            TEXT_GLYPH_MAPPING_UNVERIFIED,
            TEXT_CLIP_STATE_UNRESOLVED,
        }
        if (
            text_result.status != EvidenceResolutionStatus.ABSTAINED
            or receipt.trusted
            or TEXT_GLYPH_MAPPING_UNVERIFIED not in receipt_reason_set
            or not receipt_reason_set.issubset(raster_admissible_reasons)
            or tuple(text_result.reason_codes) != receipt_reasons
        ):
            return _abstain(RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY, *receipt_reasons)

        # 3. The producer-owned word bbox is the only raster target.
        try:
            bbox = tuple(float(v) for v in observation.geometry[:4])
        except (TypeError, ValueError):
            return _abstain(RASTER_TEXT_BBOX_INVALID)
        if (
            len(bbox) != 4
            or not all(math.isfinite(v) for v in bbox)
            or not (bbox[2] > bbox[0] and bbox[3] > bbox[1])
            or tuple(observation.geometry) != tuple(receipt.geometry)
        ):
            return _abstain(RASTER_TEXT_BBOX_INVALID)

        if not self._backend.is_available():
            return _abstain(RASTER_TEXT_BACKEND_UNAVAILABLE)

        native_claim = normalize_reading(observation.raw_text)
        if not native_claim:
            return _abstain(RASTER_TEXT_NATIVE_MISMATCH, "native_claim_empty")

        # 4. Resolve the single producer-owned raster target once, before OCR.
        # Ordinary left-to-right words preserve the historical exact word bbox.
        # Non-horizontal words may use a uniquely source-bound texttrace glyph
        # run plus one lossless quarter-turn; there is still exactly one raster
        # pipeline per DPI and never a retry/preprocessing preference.
        raster_bbox, ocr_rotation_degrees = _producer_owned_ocr_target(
            self._source_producer,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            page_id=observation.page_id,
            receipt=receipt,
            word_bbox=bbox,
            raw_text=str(observation.raw_text),
        )

        # 5. Two independent renderings of that exact producer-owned region.
        views: list[RasterTextView] = []
        parent_ids: set[tuple[str, str, str]] = set()
        for dpi in RASTER_TEXT_CORROBORATION_DPIS:
            try:
                png_bytes, page_parent = self._source_producer.render_native_page_png(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=observation.page_id,
                    dpi=float(dpi),
                    clip_pt=raster_bbox,
                )
            except (ValueError, ProducerIntegrityError) as exc:
                return _abstain(RASTER_TEXT_RENDER_FAILED, str(exc).split(":")[0].strip())
            if (
                page_parent.page_id != observation.page_id
                or page_parent.source_partition_id != observation.source_partition_id
                or page_parent.document_id != observation.document_id
                or page_parent.revision_id != observation.revision_id
                or page_parent.source_sha256 != observation.source_sha256
            ):
                return _conflict(RASTER_TEXT_PAGE_LINEAGE_MISMATCH)
            parent_ids.add(
                (page_parent.observation_id, page_parent.source_partition_id, page_parent.page_id)
            )
            try:
                rendered = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                cropped = _lossless_rotate(rendered, ocr_rotation_degrees)
            except Exception:
                return _abstain(RASTER_TEXT_RENDER_FAILED, "render_png_undecodable")
            try:
                lines = tuple(self._backend.extract_lines(cropped, dpi=int(dpi)))
            except Exception:
                return _abstain(RASTER_TEXT_BACKEND_ERROR)

            readable = [line for line in lines if normalize_reading(getattr(line, "text", ""))]
            if any(not _geometry_valid(line, (cropped.width, cropped.height)) for line in readable):
                return _abstain(RASTER_TEXT_OCR_GEOMETRY_INVALID)
            reading: Optional[str] = None
            confidence: Optional[float] = None
            if len(readable) == 1:
                reading = normalize_reading(readable[0].text)
                confidence = readable[0].confidence
            if ocr_rotation_degrees == 0:
                ocr_image_png_sha256 = hashlib.sha256(png_bytes).hexdigest()
            else:
                ocr_png = io.BytesIO()
                cropped.save(ocr_png, format="PNG")
                ocr_image_png_sha256 = hashlib.sha256(
                    ocr_png.getvalue()
                ).hexdigest()
            views.append(
                RasterTextView(
                    dpi=int(dpi),
                    clip_pt=raster_bbox,
                    image_size_px=(cropped.width, cropped.height),
                    image_png_sha256=ocr_image_png_sha256,
                    line_count=len(readable),
                    ocr_reading=reading,
                    ocr_confidence=confidence,
                    ocr_rotation_degrees=ocr_rotation_degrees,
                )
            )

        if len(parent_ids) != 1:
            return _conflict(RASTER_TEXT_PAGE_LINEAGE_MISMATCH)
        (parent_observation_id, partition_id, _page) = next(iter(parent_ids))

        # 6. Strict per-view acceptance, then strict agreement.
        if any(view.line_count == 0 for view in views):
            return _abstain(RASTER_TEXT_NO_READING)
        if any(view.line_count > 1 for view in views):
            return _abstain(RASTER_TEXT_COMPETING_READINGS)
        readings = [view.ocr_reading for view in views]
        if len(set(readings)) != 1:
            return _abstain(RASTER_TEXT_VIEW_DISAGREEMENT)
        if readings[0] != native_claim:
            return _abstain(RASTER_TEXT_NATIVE_MISMATCH)

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": observation.page_id,
            "native_observation_id": observation.observation_id,
            "text_integrity_receipt_id": receipt.receipt_id,
            "native_text_integrity_reason_codes": tuple(receipt.reason_codes),
            "source_bbox": bbox,
            "page_parent_observation_id": parent_observation_id,
            "source_partition_id": partition_id,
            "render_dpis": tuple(RASTER_TEXT_CORROBORATION_DPIS),
            "backend_name": self._backend.name,
            "backend_version": self._backend.version,
            "views": tuple(
                (v.dpi, v.image_size_px, v.image_png_sha256, v.ocr_reading)
                for v in views
            ),
            "corroborated_text": native_claim,
        }
        if ocr_rotation_degrees != 0 or raster_bbox != bbox:
            payload["source_owned_ocr_target"] = {
                "clip_pt": raster_bbox,
                "rotation_degrees": ocr_rotation_degrees,
            }

        record = RasterTextCorroborationRecord(
            record_id=stable_contract_id("raster_text_corroboration", payload, digest_chars=32),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=observation.page_id,
            native_observation_id=observation.observation_id,
            text_integrity_receipt_id=receipt.receipt_id,
            native_text_integrity_reason_codes=tuple(receipt.reason_codes),
            source_bbox=bbox,  # type: ignore[arg-type]
            page_parent_observation_id=parent_observation_id,
            source_partition_id=partition_id,
            render_dpis=tuple(RASTER_TEXT_CORROBORATION_DPIS),
            backend_name=self._backend.name,
            backend_version=self._backend.version,
            views=tuple(views),
            corroborated_text=native_claim,
        )
        return RasterTextCorroborationResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(RASTER_TEXT_CORROBORATED,),
            corroborated_text=native_claim,
            record=record,
        )


__all__ = [
    "RASTER_TEXT_ALREADY_TRUSTED",
    "RASTER_TEXT_BACKEND_ERROR",
    "RASTER_TEXT_BACKEND_UNAVAILABLE",
    "RASTER_TEXT_BBOX_INVALID",
    "RASTER_TEXT_COMPETING_READINGS",
    "RASTER_TEXT_CORROBORATED",
    "RASTER_TEXT_CORROBORATION_DPIS",
    "RASTER_TEXT_CORROBORATION_SCHEMA_VERSION",
    "RASTER_TEXT_INTEGRITY_CONFLICT",
    "RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY",
    "RASTER_TEXT_NATIVE_MISMATCH",
    "RASTER_TEXT_NO_READING",
    "RASTER_TEXT_OBSERVATION_NOT_NATIVE_WORD",
    "RASTER_TEXT_OCR_GEOMETRY_INVALID",
    "RASTER_TEXT_PAGE_LINEAGE_MISMATCH",
    "RASTER_TEXT_RECEIPT_UNAVAILABLE",
    "RASTER_TEXT_RECORD_UNAVAILABLE",
    "RASTER_TEXT_RENDER_FAILED",
    "RASTER_TEXT_SCOPE_UNAVAILABLE",
    "RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED",
    "RASTER_TEXT_VIEW_DISAGREEMENT",
    "RasterTextCorroborationAuthority",
    "RasterTextCorroborationProducer",
    "RasterTextCorroborationRecord",
    "RasterTextCorroborationResult",
    "RasterTextCorroborationSelector",
    "RasterTextView",
    "normalize_reading",
]
