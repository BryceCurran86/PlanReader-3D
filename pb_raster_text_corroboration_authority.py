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
      -> producer-owned PdfTextIntegrity receipt whose ONLY blocking reason is
         ``text_glyph_mapping_unverified``
      -> producer-owned word bbox
      -> the exact region rendered from the immutable stored PDF bytes at
         300 DPI and at 450 DPI (renderer clip; never a page crop)
      -> NO padding, NO expansion into neighbouring source pixels and NO
         alternative preprocessing: one deterministic raster pipeline only
         (trying a tight crop, then a padded one, then keeping whichever
         matches the claim would turn preprocessing selection into an
         authority preference)
      -> the production RapidOCR backend run separately on each rasterization
      -> exactly one textual reading per view, identical across both views and
         identical to the native claim (strict equality after NFC + outer
         whitespace only; punctuation and every semantic character preserved).

Anything else abstains: any other text-integrity reason (trace ambiguity,
malformed CMap, hidden/clipped/occluded text, decode or glyph mismatch, ...),
zero readings, more than one reading (competing or duplicate detections),
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
from types import MappingProxyType
from typing import Mapping, Optional

from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import (
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    PdfTextIntegrityAuthority,
)
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    OCRLine,
    RapidOCRBackend,
    RasterOCRBackend,
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
        """Production entry: always the exact production RapidOCR backend."""

        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, RapidOCRBackend(), _seal=_PRODUCER_SEAL)

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
        #    the independent glyph mapping. Raster OCR never overrides another
        #    failure.
        text_result = self._text_authority.resolve_text(observation_selector)
        receipt = text_result.receipt
        if receipt is None:
            return _abstain(RASTER_TEXT_RECEIPT_UNAVAILABLE, *text_result.reason_codes)
        if text_result.status == EvidenceResolutionStatus.CONFLICT:
            return _conflict(RASTER_TEXT_INTEGRITY_CONFLICT, *text_result.reason_codes)
        if text_result.status == EvidenceResolutionStatus.CORROBORATED:
            return _abstain(RASTER_TEXT_ALREADY_TRUSTED)
        if (
            text_result.status != EvidenceResolutionStatus.ABSTAINED
            or receipt.trusted
            or tuple(receipt.reason_codes) != (TEXT_GLYPH_MAPPING_UNVERIFIED,)
            or tuple(text_result.reason_codes) != tuple(receipt.reason_codes)
        ):
            return _abstain(RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY, *receipt.reason_codes)

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

        # 4. Two independent renderings of the exact word region.
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
                    clip_pt=bbox,
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
                cropped = Image.open(io.BytesIO(png_bytes)).convert("RGB")
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
            views.append(
                RasterTextView(
                    dpi=int(dpi),
                    clip_pt=bbox,  # type: ignore[arg-type]
                    image_size_px=(cropped.width, cropped.height),
                    image_png_sha256=hashlib.sha256(png_bytes).hexdigest(),
                    line_count=len(readable),
                    ocr_reading=reading,
                    ocr_confidence=confidence,
                )
            )

        if len(parent_ids) != 1:
            return _conflict(RASTER_TEXT_PAGE_LINEAGE_MISMATCH)
        (parent_observation_id, partition_id, _page) = next(iter(parent_ids))

        # 5. Strict per-view acceptance, then strict agreement.
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
