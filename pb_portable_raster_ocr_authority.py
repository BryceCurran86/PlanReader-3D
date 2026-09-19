"""Portable raster OCR and native-text reconciliation authority (Item 24 / F25).

Provides consistent, leak-free visual and OCR drawing text extraction across
canonical CI and runtime environments without depending on local machine state
or undeclared binary installations.

Key rules:
- Clean provider/backend interface (Tesseract, WinOCR, Null production; Mock tests-only).
- Deterministic capability detection without crashing or hardcoded paths.
- Explicit provenance on every record: backend name/version, DPI, page, viewport.
- Page & viewport spatial binding.
- Output clearly identified as OCR-derived (is_ocr_derived=True, extraction_method="raster_ocr").
- OCR publish status is CANDIDATE only — never silent CORROBORATED/FIRM authority.
- Native-text and OCR reconciliation labels are diagnostic; they do not raise firm authority.
- Fail closed when OCR backend is unavailable (never fakes text).
- Caller page_images / native_texts maps are tagged non-authority.
- 100% portable on Python 3.13 and 3.14: zero local absolute paths or machine-specific configs.
- Generic only: ZERO benchmark IDs, ground truth BOQs, or project-name heuristics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import math
import os
import shutil
from types import MappingProxyType
from typing import Any, Optional

from PIL import Image

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_source_observation_authority import PublishedSourceSnapshot

PORTABLE_RASTER_OCR_SCHEMA_VERSION = "1.0.0"

OCR_EXTRACTION_RESOLVED = "ocr_extraction_resolved"
OCR_BACKEND_UNAVAILABLE = "ocr_backend_unavailable"
OCR_LINEAGE_MISMATCH = "ocr_lineage_mismatch"
OCR_NATIVE_CONFLICT = "ocr_native_conflict"
OCR_NO_TEXT_DETECTED = "ocr_no_text_detected"
OCR_SCOPE_UNAVAILABLE = "ocr_scope_unavailable"
OCR_SOURCE_IMAGE_MISSING = "ocr_source_image_missing"
OCR_CALLER_PAGE_IMAGES_NOT_AUTHORITY = "ocr_caller_page_images_not_authority"
OCR_CALLER_NATIVE_TEXT_NOT_AUTHORITY = "ocr_caller_native_text_not_authority"
OCR_PROVISIONAL_CANDIDATE_ONLY = "ocr_provisional_candidate_only"
OCR_CONFIDENCE_UNAVAILABLE_FROM_BACKEND = "ocr_confidence_unavailable_from_backend"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
# Populated after Null/Tesseract/WinOCR class definitions below.
_PRODUCTION_BACKEND_TYPES: tuple[type, ...] = ()

_Key = tuple[str, str, str, str, str, Optional[str], Optional[tuple[float, float, float, float]]]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


# ---------------------------------------------------------------------------
# Backend Models and Protocols
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OCRLine:
    """One recognized line of text with bounding box and confidence.

    ``confidence`` is ``None`` when the backend engine does not expose a
    numerical confidence score at all (e.g. Windows.Media.Ocr, whose
    ``OcrWord``/``OcrLine`` types carry only ``text`` and
    ``bounding_rect`` -- no score). ``None`` must never be silently
    coerced to an invented value such as 0.5; callers that need a number
    must treat ``None`` as "not measured", not "average confidence".
    """

    text: str
    confidence: Optional[float]
    bbox_px: tuple[float, float, float, float]  # (x0, y0, x1, y1) in image pixels
    bbox_pt: Optional[tuple[float, float, float, float]] = None  # in PDF points

    def __post_init__(self) -> None:
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


class RasterOCRBackend(ABC):
    """Abstract interface for portable raster OCR providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the OCR backend engine."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string of the OCR backend."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend is installed and executable in this environment."""
        ...

    @abstractmethod
    def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
        """Perform text recognition on the given image."""
        ...


class NullOCRBackend(RasterOCRBackend):
    """Null object backend for environments without an installed OCR engine."""

    @property
    def name(self) -> str:
        return "null_backend"

    @property
    def version(self) -> str:
        return "0.0.0"

    def is_available(self) -> bool:
        return False

    def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
        return ()


class WinOCRBackend(RasterOCRBackend):
    """Windows.Media.Ocr backend (optional native Windows runtime).

    Bridges a PIL image to a WinRT ``SoftwareBitmap`` via an in-memory PNG
    round-trip (``BitmapDecoder`` decodes real image bytes -- no bounding
    box or pixel data is invented), runs ``OcrEngine.recognize_async``, and
    converts each recognized line's own word bounding rectangles into an
    ``OCRLine``. ``Windows.Media.Ocr``'s ``OcrWord``/``OcrLine`` types
    expose only ``text`` and ``bounding_rect`` -- no confidence score of
    any kind -- so every line from this backend carries
    ``confidence=None``, never a fabricated number.
    """

    @property
    def name(self) -> str:
        return "win_ocr"

    @property
    def version(self) -> str:
        return "windows_media_ocr_1.0"

    def is_available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            import winrt.windows.media.ocr  # type: ignore
            return True
        except Exception:
            return False

    def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
        if not self.is_available():
            raise RuntimeError("WinOCR backend is not available")
        import asyncio

        return asyncio.run(self._extract_lines_async(image, dpi))

    async def _extract_lines_async(self, image: Image.Image, dpi: int) -> tuple[OCRLine, ...]:
        import io

        from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        try:
            writer.write_bytes(png_bytes)
            await writer.store_async()
            await writer.flush_async()
        finally:
            writer.detach_stream()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        bitmap = SoftwareBitmap.convert(bitmap, BitmapPixelFormat.GRAY8)

        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError(
                "no Windows OCR language is installed for the current user profile"
            )

        result = await engine.recognize_async(bitmap)

        scale_to_pt = 72.0 / float(dpi) if dpi > 0 else 1.0
        lines: list[OCRLine] = []
        for line in result.lines:
            words = list(line.words)
            if not words:
                continue
            x0 = min(w.bounding_rect.x for w in words)
            y0 = min(w.bounding_rect.y for w in words)
            x1 = max(w.bounding_rect.x + w.bounding_rect.width for w in words)
            y1 = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
            bbox_px = (float(x0), float(y0), float(x1), float(y1))
            bbox_pt = (
                round(x0 * scale_to_pt, 4),
                round(y0 * scale_to_pt, 4),
                round(x1 * scale_to_pt, 4),
                round(y1 * scale_to_pt, 4),
            )
            lines.append(
                OCRLine(
                    text=str(line.text),
                    confidence=None,
                    bbox_px=bbox_px,
                    bbox_pt=bbox_pt,
                )
            )
        return tuple(lines)


OCRBackend = RasterOCRBackend


class MockOCRBackend(RasterOCRBackend):
    """Deterministic in-memory backend for unit tests only.

    Not a production authority input. ``PortableRasterOCRProducer.from_backend``
    rejects this type; tests must use ``from_backend_for_tests``.
    """

    def __init__(
        self,
        canned_lines: Sequence[OCRLine] = (),
        *,
        is_ready: bool = True,
        version: str = "mock-1.0.0",
        fail_with: Optional[BaseException] = None,
    ) -> None:
        self._lines = tuple(canned_lines)
        self._is_ready = is_ready
        self._version = version
        self._fail_with = fail_with

    @property
    def name(self) -> str:
        return "mock_ocr"

    @property
    def version(self) -> str:
        return self._version

    def is_available(self) -> bool:
        return self._is_ready

    def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
        if not self._is_ready:
            raise RuntimeError("Mock OCR backend unavailable")
        if self._fail_with is not None:
            raise self._fail_with
        return self._lines


class TesseractOCRBackend(RasterOCRBackend):
    """Portable Tesseract backend using standard PATH resolution or TESSERACT_CMD."""

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        self._custom_cmd = tesseract_cmd or os.environ.get("TESSERACT_CMD")

    @property
    def name(self) -> str:
        return "tesseract"

    @property
    def version(self) -> str:
        try:
            import pytesseract
            return str(getattr(pytesseract, "__version__", "unknown"))
        except Exception:
            return "unknown"

    def _resolved_cmd(self) -> Optional[str]:
        if self._custom_cmd:
            return self._custom_cmd if os.path.exists(self._custom_cmd) else None
        return shutil.which("tesseract")

    def is_available(self) -> bool:
        try:
            import pytesseract
        except ImportError:
            return False
        cmd = self._resolved_cmd()
        if not cmd:
            return False
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
            test_img = Image.new("RGB", (10, 10), "white")
            pytesseract.image_to_data(test_img, output_type=pytesseract.Output.DICT)
            return True
        except Exception:
            return False

    def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
        if not self.is_available():
            raise RuntimeError("Tesseract backend is not available")
        import pytesseract

        cmd = self._resolved_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        n_boxes = len(data.get("text", []))
        lines: list[OCRLine] = []

        scale_to_pt = 72.0 / float(dpi) if dpi > 0 else 1.0

        for i in range(n_boxes):
            text = str(data["text"][i] or "").strip()
            if not text:
                continue
            conf_raw = float(data.get("conf", [0])[i])
            conf = max(0.0, min(1.0, conf_raw / 100.0)) if conf_raw >= 0 else 0.5
            x = float(data.get("left", [0])[i])
            y = float(data.get("top", [0])[i])
            w = float(data.get("width", [0])[i])
            h = float(data.get("height", [0])[i])
            bbox_px = (x, y, x + w, y + h)
            bbox_pt = (
                round(x * scale_to_pt, 4),
                round(y * scale_to_pt, 4),
                round((x + w) * scale_to_pt, 4),
                round((y + h) * scale_to_pt, 4),
            )
            lines.append(
                OCRLine(
                    text=text,
                    confidence=conf,
                    bbox_px=bbox_px,
                    bbox_pt=bbox_pt,
                )
            )
        return tuple(lines)


# Exact production backends only — Mock and arbitrary subclasses are not authority.
_PRODUCTION_BACKEND_TYPES = (NullOCRBackend, TesseractOCRBackend, WinOCRBackend)


@dataclass(frozen=True)
class OCRCapabilityReport:
    """Environment capability probe report."""

    available_backends: tuple[str, ...]
    default_backend: Optional[str]
    tesseract_available: bool
    pillow_available: bool

    @property
    def has_active_ocr(self) -> bool:
        return bool(self.available_backends)


def detect_ocr_capabilities() -> OCRCapabilityReport:
    """Probe runtime environment for OCR engines without raising exceptions."""
    pillow_ok = True
    try:
        from PIL import Image
    except ImportError:
        pillow_ok = False

    tess = TesseractOCRBackend()
    tess_ok = tess.is_available()

    backends: list[str] = []
    if tess_ok:
        backends.append("tesseract")

    default = backends[0] if backends else None
    return OCRCapabilityReport(
        available_backends=tuple(backends),
        default_backend=default,
        tesseract_available=tess_ok,
        pillow_available=pillow_ok,
    )


# ---------------------------------------------------------------------------
# Selectors & Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentSnapshotLineage:
    """Document snapshot lineage reference for producer binding."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")


@dataclass(frozen=True)
class PortableRasterOCRSelector:
    """Consumer addressing selector for raster OCR extraction."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str] = None
    target_region_pt: Optional[tuple[float, float, float, float]] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.page_id, "page_id")
        if self.target_region_pt is not None:
            if len(self.target_region_pt) != 4:
                raise ValueError("target_region_pt must be a 4-tuple (x0, y0, x1, y1)")
            x0, y0, x1, y1 = (float(v) for v in self.target_region_pt)
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                raise ValueError("target_region_pt coordinates must be finite")
            if x1 <= x0 or y1 <= y0:
                raise ValueError("target_region_pt must have positive span")
            object.__setattr__(self, "target_region_pt", (x0, y0, x1, y1))

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.target_region_pt,
        )


@dataclass(frozen=True)
class RasterOCREvidenceRecord:
    """Immutable, provenance-tracked OCR evidence publication record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    target_region_pt: Optional[tuple[float, float, float, float]]
    lines: tuple[OCRLine, ...]
    full_text: str
    backend_name: str
    backend_version: str
    dpi: int
    is_ocr_derived: bool = True
    extraction_method: str = "raster_ocr"
    # None when the backend supplied no numerical confidence for ANY line
    # (e.g. WinOCR) -- never fabricated as an invented average.
    confidence: Optional[float] = None
    reconciliation_status: str = "provisional"
    schema_version: str = PORTABLE_RASTER_OCR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.page_id, "page_id")
        _require_nonempty(self.backend_name, "backend_name")


@dataclass(frozen=True)
class PortableRasterOCRResult:
    """Result envelope for portable raster OCR resolution."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[RasterOCREvidenceRecord] = None
    schema_version: str = PORTABLE_RASTER_OCR_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra_reasons: str,
) -> PortableRasterOCRResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return PortableRasterOCRResult(
        status=status,
        reason_codes=reasons,
        record=None,
    )


# ---------------------------------------------------------------------------
# Native / OCR Reconciliation
# ---------------------------------------------------------------------------

def normalize_text_for_reconciliation(text: Optional[str]) -> str:
    """Normalize text by stripping whitespace and non-alphanumeric punctuation."""
    if not text:
        return ""
    import re
    return re.sub(r"[\s\-_]+", "", text.strip()).upper()


def reconcile_native_and_ocr_text(
    native_text: Optional[str],
    ocr_text: Optional[str],
) -> tuple[Optional[str], str, tuple[str, ...]]:
    """Reconcile native PDF text against OCR text.

    Returns:
        (resolved_text, reconciliation_status, reason_codes)
        where reconciliation_status in {"confirmed", "provisional", "conflict_manual_review"}
    """
    clean_native = (native_text or "").strip()
    clean_ocr = (ocr_text or "").strip()

    if clean_native and clean_ocr:
        norm_native = normalize_text_for_reconciliation(clean_native)
        norm_ocr = normalize_text_for_reconciliation(clean_ocr)
        if norm_native == norm_ocr:
            return clean_native, "confirmed", ("native_ocr_reconciled_match",)
        else:
            # Native text and OCR contradict: flag for manual review, fail closed
            return None, "conflict_manual_review", (OCR_NATIVE_CONFLICT,)

    if clean_native and not clean_ocr:
        return clean_native, "confirmed", ("native_text_authoritative",)

    if clean_ocr and not clean_native:
        # OCR only: strictly provisional, never silent FIRM authority
        return clean_ocr, "provisional", ("provisional_ocr_only",)

    return None, "unresolved", (OCR_NO_TEXT_DETECTED,)


# ---------------------------------------------------------------------------
# Producer & Authority
# ---------------------------------------------------------------------------

class PortableRasterOCRAuthority:
    """Read-only exact-scope selector lookup for raster OCR evidence."""

    def __init__(
        self,
        results: Mapping[_Key, PortableRasterOCRResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("PortableRasterOCRAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: PortableRasterOCRSelector) -> PortableRasterOCRResult:
        if type(selector) is not PortableRasterOCRSelector:
            raise TypeError("selector must be PortableRasterOCRSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OCR_SCOPE_UNAVAILABLE,
            ),
        )


class PortableRasterOCRProducer:
    """Trusted boundary extracting and publishing portable raster OCR evidence.

    OCR records are shadow/diagnostic evidence only. Successful publish uses
    ``EvidenceResolutionStatus.CANDIDATE`` — never CORROBORATED/FIRM. Caller
    ``page_images`` / ``native_texts`` maps are not measurement authority.
    """

    def __init__(
        self,
        backend: RasterOCRBackend,
        page_images: Mapping[str, Image.Image],
        native_texts: Optional[Mapping[tuple[str, Optional[str]], str]] = None,
        default_dpi: int = 150,
        snapshot: Optional[PublishedSourceSnapshot] = None,
        *,
        _allow_test_backend: bool = False,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "PortableRasterOCRProducer must be obtained from from_backend()"
            )
        if _allow_test_backend:
            if type(backend) is not MockOCRBackend:
                raise TypeError(
                    "from_backend_for_tests requires exact MockOCRBackend"
                )
        elif type(backend) not in _PRODUCTION_BACKEND_TYPES:
            raise TypeError(
                "backend must be exact NullOCRBackend, TesseractOCRBackend, "
                "or WinOCRBackend; MockOCRBackend requires from_backend_for_tests"
            )
        self._backend = backend
        self._page_images = MappingProxyType(dict(page_images))
        self._native_texts = MappingProxyType(dict(native_texts or {}))
        self._caller_page_images = True  # current seam: images are caller-supplied
        self._caller_native_texts = bool(native_texts)
        self._dpi = default_dpi
        self._snapshot = snapshot
        self._results: dict[_Key, PortableRasterOCRResult] = {}

    @classmethod
    def from_backend(
        cls,
        backend: Optional[RasterOCRBackend] = None,
        page_images: Optional[Mapping[str, Image.Image]] = None,
        native_texts: Optional[Mapping[tuple[str, Optional[str]], str]] = None,
        default_dpi: int = 150,
        snapshot: Optional[PublishedSourceSnapshot] = None,
    ) -> "PortableRasterOCRProducer":
        active_backend = backend if backend is not None else NullOCRBackend()
        return cls(
            backend=active_backend,
            page_images=page_images or {},
            native_texts=native_texts,
            default_dpi=default_dpi,
            snapshot=snapshot,
            _allow_test_backend=False,
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def from_backend_for_tests(
        cls,
        backend: MockOCRBackend,
        page_images: Optional[Mapping[str, Image.Image]] = None,
        native_texts: Optional[Mapping[tuple[str, Optional[str]], str]] = None,
        default_dpi: int = 150,
        snapshot: Optional[PublishedSourceSnapshot] = None,
    ) -> "PortableRasterOCRProducer":
        """Test-only entry: allows MockOCRBackend. Never a production path."""

        return cls(
            backend=backend,
            page_images=page_images or {},
            native_texts=native_texts,
            default_dpi=default_dpi,
            snapshot=snapshot,
            _allow_test_backend=True,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> PortableRasterOCRAuthority:
        return PortableRasterOCRAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: PortableRasterOCRSelector,
        result: PortableRasterOCRResult,
    ) -> PortableRasterOCRResult:
        self._results[selector.key] = result
        return result

    def publish(
        self, selector: PortableRasterOCRSelector
    ) -> PortableRasterOCRResult:
        if type(selector) is not PortableRasterOCRSelector:
            raise TypeError("selector must be PortableRasterOCRSelector")

        # 1. Validate Lineage against snapshot if bound
        if self._snapshot is not None:
            snap = getattr(self._snapshot, "snapshot", self._snapshot)
            rev = getattr(self._snapshot, "revision", None)
            snap_doc = getattr(snap, "document_id", None) or getattr(rev, "document_id", None)
            snap_rev = getattr(snap, "revision_id", None) or getattr(rev, "revision_id", None)
            snap_sha = getattr(snap, "source_sha256", None) or getattr(rev, "source_sha256", None)
            snap_id = getattr(snap, "snapshot_id", None)

            if (
                selector.document_id != snap_doc
                or selector.revision_id != snap_rev
                or selector.source_sha256 != snap_sha
                or selector.snapshot_id != snap_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        OCR_LINEAGE_MISMATCH,
                        "lineage_mismatch_with_snapshot",
                    ),
                )

        # 2. Check Backend Availability: Fail Closed
        if not self._backend.is_available():
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    OCR_BACKEND_UNAVAILABLE,
                    f"backend_{self._backend.name}_not_installed",
                ),
            )

        # 3. Retrieve Source Page Image
        img = self._page_images.get(selector.page_id)
        if img is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    OCR_SOURCE_IMAGE_MISSING,
                    f"no_image_for_page_{selector.page_id}",
                ),
            )

        # 4. Crop target region if specified
        target_img = img
        crop_offset_pt = (0.0, 0.0)
        if selector.target_region_pt is not None:
            pt_to_px = float(self._dpi) / 72.0
            x0, y0, x1, y1 = selector.target_region_pt
            crop_box = (
                int(max(0, math.floor(x0 * pt_to_px))),
                int(max(0, math.floor(y0 * pt_to_px))),
                int(min(img.width, math.ceil(x1 * pt_to_px))),
                int(min(img.height, math.ceil(y1 * pt_to_px))),
            )
            if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                target_img = img.crop(crop_box)
                crop_offset_pt = (
                    float(crop_box[0]) * (72.0 / float(self._dpi)),
                    float(crop_box[1]) * (72.0 / float(self._dpi)),
                )

        # 5. Perform OCR Extraction
        try:
            raw_lines = self._backend.extract_lines(target_img, dpi=self._dpi)
        except Exception as exc:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OCR_BACKEND_UNAVAILABLE,
                    f"extraction_error: {str(exc)}",
                ),
            )

        if crop_offset_pt != (0.0, 0.0):
            dx, dy = crop_offset_pt
            adjusted_lines = []
            for line in raw_lines:
                adj_pt = (
                    round(line.bbox_pt[0] + dx, 4),
                    round(line.bbox_pt[1] + dy, 4),
                    round(line.bbox_pt[2] + dx, 4),
                    round(line.bbox_pt[3] + dy, 4),
                ) if line.bbox_pt else None
                adjusted_lines.append(
                    OCRLine(
                        text=line.text,
                        confidence=line.confidence,
                        bbox_px=line.bbox_px,
                        bbox_pt=adj_pt,
                    )
                )
            raw_lines = tuple(adjusted_lines)

        full_text = " ".join(line.text for line in raw_lines if line.text).strip()
        if not full_text:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    OCR_NO_TEXT_DETECTED,
                ),
            )

        # 5. Native Text Reconciliation
        native_key = (selector.page_id, selector.viewport_id)
        native_text = self._native_texts.get(native_key)
        resolved_text, recon_status, recon_reasons = reconcile_native_and_ocr_text(
            native_text, full_text
        )

        if recon_status == "conflict_manual_review":
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OCR_NATIVE_CONFLICT,
                    *recon_reasons,
                ),
            )

        # Average confidence only across lines that actually carry one --
        # a backend that supplies no confidence at all (e.g. WinOCR) must
        # never have one invented via an average that includes fabricated
        # zeros or defaults.
        scored_confidences = [line.confidence for line in raw_lines if line.confidence is not None]
        avg_conf: Optional[float] = (
            round(sum(scored_confidences) / len(scored_confidences), 4)
            if scored_confidences
            else None
        )

        # 6. Publish RasterOCREvidenceRecord
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": selector.viewport_id,
            "target_region_pt": selector.target_region_pt,
            "full_text": resolved_text or full_text,
            "backend_name": self._backend.name,
            "backend_version": self._backend.version,
            "dpi": self._dpi,
            "confidence": avg_conf,
            "reconciliation_status": recon_status,
        }
        record_id = stable_contract_id(
            "raster_ocr_evidence", payload, digest_chars=32
        )
        record = RasterOCREvidenceRecord(
            record_id=record_id,
            lines=raw_lines,
            **payload,
        )
        # OCR evidence never mints CORROBORATED/FIRM. Caller page images and
        # caller native-text maps are diagnostic inputs only.
        reasons: list[str] = [OCR_EXTRACTION_RESOLVED, OCR_PROVISIONAL_CANDIDATE_ONLY]
        reasons.extend(recon_reasons)
        if avg_conf is None:
            reasons.append(OCR_CONFIDENCE_UNAVAILABLE_FROM_BACKEND)
        if self._caller_page_images:
            reasons.append(OCR_CALLER_PAGE_IMAGES_NOT_AUTHORITY)
        if self._caller_native_texts:
            reasons.append(OCR_CALLER_NATIVE_TEXT_NOT_AUTHORITY)
        result = PortableRasterOCRResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=tuple(dict.fromkeys(reasons)),
            record=record,
        )
        return self._store(selector, result)


__all__ = [
    "DocumentSnapshotLineage",
    "MockOCRBackend",
    "NullOCRBackend",
    "OCRBackend",
    "OCRCapabilityReport",
    "OCRLine",
    "OCR_BACKEND_UNAVAILABLE",
    "OCR_CALLER_NATIVE_TEXT_NOT_AUTHORITY",
    "OCR_CALLER_PAGE_IMAGES_NOT_AUTHORITY",
    "OCR_EXTRACTION_RESOLVED",
    "OCR_LINEAGE_MISMATCH",
    "OCR_NATIVE_CONFLICT",
    "OCR_NO_TEXT_DETECTED",
    "OCR_PROVISIONAL_CANDIDATE_ONLY",
    "OCR_CONFIDENCE_UNAVAILABLE_FROM_BACKEND",
    "OCR_SCOPE_UNAVAILABLE",
    "OCR_SOURCE_IMAGE_MISSING",
    "PORTABLE_RASTER_OCR_SCHEMA_VERSION",
    "PortableRasterOCRAuthority",
    "PortableRasterOCRProducer",
    "PortableRasterOCRResult",
    "PortableRasterOCRSelector",
    "RasterOCRBackend",
    "RasterOCREvidenceRecord",
    "TesseractOCRBackend",
    "WinOCRBackend",
    "detect_ocr_capabilities",
    "normalize_text_for_reconciliation",
    "reconcile_native_and_ocr_text",
]
