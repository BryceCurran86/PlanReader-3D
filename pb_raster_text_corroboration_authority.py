"""Immutable-source raster corroboration for native PDF text.

This authority is deliberately narrower than PdfTextIntegrityAuthority. It never
relaxes native PDF decoding checks. A native word can be corroborated only when
its producer-owned receipt is otherwise clean and is blocked solely because the
embedded font program cannot independently verify the ToUnicode glyph mapping.

Positive path:
native word -> exact producer-owned bbox -> immutable source-page render ->
exact crop -> one OCR result -> normalized text agreement.

No caller pixels, caller bbox, proximity matching, confidence threshold,
semantic interpretation, or quantity publication participate here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import math
from types import MappingProxyType
from typing import Mapping, Optional
import unicodedata

from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import TEXT_GLYPH_MAPPING_UNVERIFIED
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    NullOCRBackend,
    OCRLine,
    RapidOCRBackend,
    RasterOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

RASTER_TEXT_CORROBORATION_SCHEMA_VERSION = "1.0.0"

RASTER_TEXT_CORROBORATED = "raster_text_corroborated"
RASTER_TEXT_UNAVAILABLE = "raster_text_corroboration_unavailable"
RASTER_TEXT_NATIVE_ALREADY_TRUSTED = "raster_text_native_already_trusted"
RASTER_TEXT_NATIVE_PREREQUISITE_UNRESOLVED = "raster_text_native_prerequisite_unresolved"
RASTER_TEXT_NATIVE_BLOCKER_NOT_GLYPH_ONLY = "raster_text_native_blocker_not_glyph_only"
RASTER_TEXT_BACKEND_UNAVAILABLE = "raster_text_ocr_backend_unavailable"
RASTER_TEXT_SOURCE_RENDER_UNAVAILABLE = "raster_text_source_render_unavailable"
RASTER_TEXT_SOURCE_GEOMETRY_INVALID = "raster_text_source_geometry_invalid"
RASTER_TEXT_OCR_EMPTY = "raster_text_ocr_empty"
RASTER_TEXT_OCR_AMBIGUOUS = "raster_text_ocr_ambiguous"
RASTER_TEXT_OCR_MISMATCH = "raster_text_ocr_mismatch"
RASTER_TEXT_OCR_OUTPUT_INVALID = "raster_text_ocr_output_invalid"
RASTER_TEXT_OCR_EXTRACTION_FAILED = "raster_text_ocr_extraction_failed"
RASTER_TEXT_LINEAGE_MISMATCH = "raster_text_lineage_mismatch"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_PRODUCTION_BACKEND_TYPES = (
    NullOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
    RapidOCRBackend,
)
_Key = tuple[str, str, str, str, str]


def _selector_key(selector: ObservationSelector) -> _Key:
    return (
        selector.document_id,
        selector.revision_id,
        selector.source_sha256,
        selector.snapshot_id,
        selector.observation_id,
    )


def _normalise_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split()).casefold()


def _box_within(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> bool:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    return (
        all(math.isfinite(value) for value in inner)
        and ix1 > ix0
        and iy1 > iy0
        and ix0 >= ox0
        and iy0 >= oy0
        and ix1 <= ox1
        and iy1 <= oy1
    )


def _choose_environment_backend() -> RasterOCRBackend:
    rapid = RapidOCRBackend()
    if rapid.is_available():
        return rapid
    tesseract = TesseractOCRBackend()
    if tesseract.is_available():
        return tesseract
    winocr = WinOCRBackend()
    if winocr.is_available():
        return winocr
    return NullOCRBackend()


@dataclass(frozen=True)
class RasterTextCorroborationReceipt:
    receipt_id: str
    parent_observation_id: str
    native_text_integrity_receipt_id: str
    page_parent_observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    source_partition_id: str
    raw_text: str
    geometry: tuple[float, float, float, float]
    rendered_page_sha256: str
    crop_bbox_pt: tuple[float, float, float, float]
    crop_pixel_size: tuple[int, int]
    backend_name: str
    backend_version: str
    dpi: int
    ocr_text: str
    ocr_bbox_px: tuple[float, float, float, float]
    schema_version: str = RASTER_TEXT_CORROBORATION_SCHEMA_VERSION


@dataclass(frozen=True)
class RasterTextCorroborationResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    trusted_text: Optional[str]
    reason_codes: tuple[str, ...]
    receipt: Optional[RasterTextCorroborationReceipt] = None


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
) -> RasterTextCorroborationResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return RasterTextCorroborationResult(
        status=status,
        proposition=None,
        trusted_text=None,
        reason_codes=(reason,),
        receipt=None,
    )


class RasterTextCorroborationAuthority:
    """Read-only lookup over producer-published raster corroboration results."""

    def __init__(
        self,
        results: Mapping[_Key, RasterTextCorroborationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("RasterTextCorroborationAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_text(
        self,
        selector: ObservationSelector,
    ) -> RasterTextCorroborationResult:
        if type(selector) is not ObservationSelector:
            raise TypeError("selector must be ObservationSelector")
        return self._results.get(
            _selector_key(selector),
            _blocked(EvidenceResolutionStatus.ABSTAINED, RASTER_TEXT_UNAVAILABLE),
        )


class RasterTextCorroborationProducer:
    """Producer-owned immutable-source OCR corroboration for one native word."""

    def __init__(
        self,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        backend: RasterOCRBackend,
        dpi: int,
        allow_test_backend: bool,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "RasterTextCorroborationProducer must be obtained from create() "
                "or create_for_tests()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )
        if allow_test_backend:
            if type(backend) is not MockOCRBackend:
                raise TypeError("create_for_tests requires exact MockOCRBackend")
        elif type(backend) not in _PRODUCTION_BACKEND_TYPES:
            raise TypeError(
                "production backend must be exact RapidOCRBackend, "
                "TesseractOCRBackend, WinOCRBackend, or NullOCRBackend"
            )
        dpi_value = int(dpi)
        if dpi_value <= 0:
            raise ValueError("dpi must be a positive integer")

        self._source_visibility_producer = source_visibility_producer
        self._source_producer = source_visibility_producer._producer
        self._native_text_authority = (
            source_visibility_producer.text_integrity_authority()
        )
        self._backend = backend
        self._dpi = dpi_value
        self._results: dict[_Key, RasterTextCorroborationResult] = {}
        self._page_render_cache: dict[
            tuple[str, str, str, str, int],
            tuple[bytes, object, Image.Image],
        ] = {}

    @classmethod
    def create(
        cls,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        backend: Optional[RasterOCRBackend] = None,
        dpi: int = 300,
    ) -> "RasterTextCorroborationProducer":
        active = backend if backend is not None else _choose_environment_backend()
        return cls(
            source_visibility_producer=source_visibility_producer,
            backend=active,
            dpi=dpi,
            allow_test_backend=False,
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def create_for_tests(
        cls,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        backend: MockOCRBackend,
        dpi: int = 300,
    ) -> "RasterTextCorroborationProducer":
        return cls(
            source_visibility_producer=source_visibility_producer,
            backend=backend,
            dpi=dpi,
            allow_test_backend=True,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> RasterTextCorroborationAuthority:
        return RasterTextCorroborationAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: ObservationSelector,
        result: RasterTextCorroborationResult,
    ) -> RasterTextCorroborationResult:
        self._results[_selector_key(selector)] = result
        return result

    def _render_page(
        self,
        selector: ObservationSelector,
        page_id: str,
    ) -> tuple[bytes, object, Image.Image]:
        key = (
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            str(page_id),
            self._dpi,
        )
        cached = self._page_render_cache.get(key)
        if cached is not None:
            return cached
        png_bytes, page_parent = self._source_producer.render_native_page_png(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=key[3],
            dpi=float(self._dpi),
        )
        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        value = (png_bytes, page_parent, image)
        self._page_render_cache[key] = value
        return value

    def publish(
        self,
        selector: ObservationSelector,
    ) -> RasterTextCorroborationResult:
        if type(selector) is not ObservationSelector:
            raise TypeError("selector must be ObservationSelector")

        cached = self._results.get(_selector_key(selector))
        if cached is not None:
            return cached

        published = self._source_visibility_producer.published_snapshot_for_revision(
            selector.revision_id
        )
        if (
            published is None
            or published.revision.document_id != selector.document_id
            or published.revision.revision_id != selector.revision_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or self._source_producer.current_revision_id(selector.document_id)
            != selector.revision_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_LINEAGE_MISMATCH,
                ),
            )

        native = self._native_text_authority.resolve_text(selector)
        receipt = native.receipt
        if native.status is EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_NATIVE_ALREADY_TRUSTED,
                ),
            )
        if native.status is not EvidenceResolutionStatus.ABSTAINED or receipt is None:
            return self._store(
                selector,
                _blocked(
                    native.status,
                    RASTER_TEXT_NATIVE_PREREQUISITE_UNRESOLVED,
                ),
            )
        if (
            tuple(receipt.reason_codes) != (TEXT_GLYPH_MAPPING_UNVERIFIED,)
            or receipt.decode_status != "tounicode_glyph_unverified"
            or receipt.visibility_status != "proven_visible"
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_NATIVE_BLOCKER_NOT_GLYPH_ONLY,
                ),
            )

        if not self._backend.is_available():
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_BACKEND_UNAVAILABLE,
                ),
            )

        try:
            geometry = tuple(float(value) for value in receipt.geometry)
        except (TypeError, ValueError):
            geometry = ()
        if len(geometry) != 4:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_SOURCE_GEOMETRY_INVALID,
                ),
            )
        bbox = geometry  # type: ignore[assignment]

        try:
            png_bytes, page_parent, page_image = self._render_page(
                selector,
                receipt.page_id,
            )
        except (ValueError, RuntimeError, OSError):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_TEXT_SOURCE_RENDER_UNAVAILABLE,
                ),
            )

        if (
            getattr(page_parent, "document_id", None) != receipt.document_id
            or getattr(page_parent, "revision_id", None) != receipt.revision_id
            or getattr(page_parent, "source_sha256", None) != receipt.source_sha256
            or getattr(page_parent, "page_id", None) != receipt.page_id
            or getattr(page_parent, "source_partition_id", None)
            != receipt.source_partition_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_TEXT_LINEAGE_MISMATCH,
                ),
            )

        page_geometry = tuple(
            float(value) for value in getattr(page_parent, "geometry", ())[:2]
        )
        if len(page_geometry) != 2:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_TEXT_SOURCE_GEOMETRY_INVALID,
                ),
            )
        page_bbox = (0.0, 0.0, page_geometry[0], page_geometry[1])
        if not _box_within(bbox, page_bbox):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_SOURCE_GEOMETRY_INVALID,
                ),
            )

        pt_to_px = float(self._dpi) / 72.0
        x0, y0, x1, y1 = bbox
        crop_px = (
            max(0, int(math.floor(x0 * pt_to_px))),
            max(0, int(math.floor(y0 * pt_to_px))),
            min(page_image.width, int(math.ceil(x1 * pt_to_px))),
            min(page_image.height, int(math.ceil(y1 * pt_to_px))),
        )
        if crop_px[2] <= crop_px[0] or crop_px[3] <= crop_px[1]:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_SOURCE_GEOMETRY_INVALID,
                ),
            )
        crop = page_image.crop(crop_px)

        try:
            raw_lines = tuple(self._backend.extract_lines(crop, dpi=self._dpi))
        except Exception:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_TEXT_OCR_EXTRACTION_FAILED,
                ),
            )

        valid_lines: list[OCRLine] = []
        for line in raw_lines:
            text = str(getattr(line, "text", "") or "").strip()
            if not text:
                continue
            try:
                lx0, ly0, lx1, ly1 = tuple(
                    float(value) for value in getattr(line, "bbox_px", ())
                )
            except (TypeError, ValueError):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        RASTER_TEXT_OCR_OUTPUT_INVALID,
                    ),
                )
            line_bbox = (lx0, ly0, lx1, ly1)
            if not _box_within(
                line_bbox,
                (0.0, 0.0, float(crop.width), float(crop.height)),
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        RASTER_TEXT_OCR_OUTPUT_INVALID,
                    ),
                )
            valid_lines.append(line)

        if not valid_lines:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_OCR_EMPTY,
                ),
            )
        if len(valid_lines) != 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_OCR_AMBIGUOUS,
                ),
            )

        line = valid_lines[0]
        ocr_text = str(line.text or "").strip()
        if _normalise_text(ocr_text) != _normalise_text(receipt.raw_text):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_TEXT_OCR_MISMATCH,
                ),
            )

        ocr_bbox = tuple(float(value) for value in line.bbox_px)
        payload = {
            "parent_observation_id": receipt.parent_observation_id,
            "native_text_integrity_receipt_id": receipt.receipt_id,
            "page_parent_observation_id": page_parent.observation_id,
            "document_id": receipt.document_id,
            "revision_id": receipt.revision_id,
            "source_sha256": receipt.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": receipt.page_id,
            "source_partition_id": receipt.source_partition_id,
            "raw_text": receipt.raw_text,
            "geometry": bbox,
            "rendered_page_sha256": hashlib.sha256(png_bytes).hexdigest(),
            "crop_bbox_pt": bbox,
            "crop_pixel_size": (int(crop.width), int(crop.height)),
            "backend_name": self._backend.name,
            "backend_version": self._backend.version,
            "dpi": self._dpi,
            "ocr_text": ocr_text,
            "ocr_bbox_px": ocr_bbox,
        }
        corroboration = RasterTextCorroborationReceipt(
            receipt_id=stable_contract_id(
                "raster_text_corroboration",
                payload,
                digest_chars=32,
            ),
            **payload,
        )
        return self._store(
            selector,
            RasterTextCorroborationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                proposition=RASTER_TEXT_CORROBORATED,
                trusted_text=receipt.raw_text,
                reason_codes=(RASTER_TEXT_CORROBORATED,),
                receipt=corroboration,
            ),
        )


__all__ = [
    "RASTER_TEXT_BACKEND_UNAVAILABLE",
    "RASTER_TEXT_CORROBORATED",
    "RASTER_TEXT_CORROBORATION_SCHEMA_VERSION",
    "RASTER_TEXT_LINEAGE_MISMATCH",
    "RASTER_TEXT_NATIVE_ALREADY_TRUSTED",
    "RASTER_TEXT_NATIVE_BLOCKER_NOT_GLYPH_ONLY",
    "RASTER_TEXT_NATIVE_PREREQUISITE_UNRESOLVED",
    "RASTER_TEXT_OCR_AMBIGUOUS",
    "RASTER_TEXT_OCR_EMPTY",
    "RASTER_TEXT_OCR_EXTRACTION_FAILED",
    "RASTER_TEXT_OCR_MISMATCH",
    "RASTER_TEXT_OCR_OUTPUT_INVALID",
    "RASTER_TEXT_SOURCE_GEOMETRY_INVALID",
    "RASTER_TEXT_SOURCE_RENDER_UNAVAILABLE",
    "RASTER_TEXT_UNAVAILABLE",
    "RasterTextCorroborationAuthority",
    "RasterTextCorroborationProducer",
    "RasterTextCorroborationReceipt",
    "RasterTextCorroborationResult",
]
