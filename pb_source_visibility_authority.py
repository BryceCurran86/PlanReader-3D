"""Producer-owned PDF source-visibility authority for G17 source roots.

This layer is intentionally narrower than physical-opening authority. It proves
only that a native PDF segment is eligible as an authority-visible source
observation. It does not prove opening existence, identity, dimensions, host
binding, physical voids, deductions, or commercial quantities.

Visibility is deliberately conservative:
- clip association unknown -> not authority-visible
- active clips require exact axis-aligned rectangular shape proof from the
  extended PDF drawing path; PyMuPDF scissor alone is never authority
- clipped segments are published only when their full native geometry is
  contained by the proven rectangular clip intersection
- non-rectangular, partially intersecting, or otherwise unresolved clips
  remain fail-closed
- finite, non-degenerate segments with proven no-clip or proven-contained
  rectangular-clip state become native_pdf_visible_segment observations

Raw native observations remain preserved by ``SourceObservationProducer``.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
import hashlib
import math
from typing import Any, Mapping, Optional, Sequence

import fitz

from pb_native_page_frame import NativePageFrameUnresolved

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_raster_visible_segment_detector import (
    RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION,
    detect_axis_aligned_raster_segments,
)
from pb_raster_compact_wall_band_segments import (
    COMPACT_WALL_BAND_DETECTOR_VERSION,
    COMPACT_WALL_BAND_IDENTITY_VERSION,
    compact_band_has_same_visible_paint,
    compact_band_already_covered_by_source_line,
    detect_compact_raster_wall_band_segments,
)
from pb_raster_compact_partial_source_quarantine import (
    compact_band_has_partial_original_source_coverage,
    compact_band_crosses_original_source,
    compact_band_endpoint_on_original_source_interior,
)
from pb_raster_terminal_wall_band_segments import (
    TERMINAL_WALL_BAND_DETECTOR_VERSION,
    TERMINAL_WALL_BAND_IDENTITY_VERSION,
    detect_terminal_raster_wall_band_segments,
)
from pb_raster_opening_source_primitives import (
    RASTER_OPENING_PRIMITIVE_DETECTOR_VERSION,
    RASTER_LINE_RUN,
    RASTER_THIN_INK_RUN,
    RASTER_WALL_BAND_END,
    RASTER_WALL_BAND_FACE,
    RasterOpeningSourcePrimitive,
    detect_raster_opening_source_primitives,
)
from pb_pdf_text_integrity_authority import (
    PdfTextIntegrityAuthority,
    PdfTextIntegrityReceipt,
    _PDF_TEXT_AUTHORITY_SEAL,
    build_pdf_text_integrity_receipt,
    classify_native_word_integrity,
)
from pb_source_observation_authority import (
    NativePageImagePlacement,
    OBSERVATION_UNAVAILABLE,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PRODUCER_INTEGRITY_FAILURE,
    ObservationSelector,
    ProducerSnapshotRecord,
    PublishedSourceSnapshot,
    SourceDecodeCoverageRecord,
    SourceObservationAuthority,
    SourceObservationAuthorityResult,
    SourceObservationProducer,
    SourceObservationRecord,
    SourceRevisionRecord,
)
from pb_vector_geometry_v130 import extract_native_page, native_word_primitive_ref


SOURCE_VISIBILITY_SCHEMA_VERSION = "1.3.0"
NATIVE_PDF_VISIBLE_SEGMENT = "native_pdf_visible_segment"
RASTER_PDF_SEGMENT = "raster_pdf_segment"
RASTER_PDF_VISIBLE_SEGMENT = "raster_pdf_visible_segment"
RASTER_OPENING_PRIMITIVE_SEGMENT = "raster_opening_primitive_segment"
RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS = frozenset(
    (
        RASTER_WALL_BAND_FACE,
        RASTER_WALL_BAND_END,
        RASTER_LINE_RUN,
        RASTER_THIN_INK_RUN,
    )
)
VISIBLE_SEGMENT_ORIGIN_KIND = "producer_visibility_no_active_clip"
RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND = (
    "producer_visibility_exact_rectangular_clip"
)
RASTER_SEGMENT_ORIGIN_KIND = "producer_raster_page_render_segment"
RASTER_VISIBLE_SEGMENT_ORIGIN_KIND = "producer_raster_visibility"
RASTER_OPENING_PRIMITIVE_ORIGIN_KIND = "producer_raster_opening_source_primitive"
RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND = (
    "producer_raster_opening_primitive_visibility"
)
VISIBLE_SOURCE_OBSERVATION_EXISTS = "visible_source_observation_exists"
RASTER_RENDER_DPI = 144
RASTER_OPENING_PRIMITIVE_RENDER_DPI = 300
RASTER_OPENING_PRIMITIVE_IDENTITY_VERSION = "2.0.0"
# Frozen source-identity schema for raster primitives. Detector implementation
# version is provenance only; changing it must not churn physical/source ids
# when the producer-owned detected geometry is unchanged. Keep this value
# stable unless the physical identity contract itself is intentionally migrated.
RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION = "1.0.0"
# Raster detector and native image-region geometry are emitted to four decimal
# page-point precision. One least-significant unit is the only ownership slack.
_RASTER_GEOMETRY_QUANTIZATION_TOLERANCE_PT = 1e-4

VISIBILITY_CLIP_ASSOCIATION_UNKNOWN = "visibility_clip_association_unknown"
VISIBILITY_ACTIVE_CLIP_UNRESOLVED = "visibility_active_clip_unresolved"
VISIBILITY_GEOMETRY_INVALID = "visibility_geometry_invalid"
VISIBILITY_CLIP_STATE_INCONSISTENT = "visibility_clip_state_inconsistent"
VISIBILITY_PROVEN_NO_ACTIVE_CLIP = "visibility_proven_no_active_clip"
VISIBILITY_PROVEN_RECTANGULAR_CLIP = (
    "visibility_proven_rectangular_clip_contains_segment"
)
VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT = (
    "visibility_rectangular_clip_excludes_or_intersects_segment"
)
VISIBILITY_RECEIPT_UNAVAILABLE = "visibility_receipt_unavailable"
VISIBILITY_PARENT_MISMATCH = "visibility_parent_mismatch"


# Per-producer visibility derivation cache bound to one immutable source snapshot.
# Cached values contain only source-derived decisions and never outlive the
# SourceVisibilityProducer run that owns their snapshot/provenance state.
_VISIBILITY_PAGE_CACHE_MAX_PAGES = 24


@dataclass(frozen=True)
class _CachedVisibilityWord:
    raw_text: str
    geometry: tuple[float, ...]
    primitive_ref: str
    decision: Any
    block_no: Any
    line_no: Any
    word_no: Any


@dataclass(frozen=True)
class _CachedVisibleSegment:
    raw_segment_id: str
    geometry: tuple[float, float, float, float]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _CachedVisibilityPage:
    words: tuple[_CachedVisibilityWord, ...]
    visible_segments: tuple[_CachedVisibleSegment, ...]


def _derive_visibility_page(
    page: fitz.Page,
    *,
    native_page: Optional[Mapping[str, Any]] = None,
) -> _CachedVisibilityPage:
    native = native_page if native_page is not None else extract_native_page(page)
    words: list[_CachedVisibilityWord] = []
    visible_segments: list[_CachedVisibleSegment] = []
    for word in native.get("words") or ():
        raw_text = str(word.get("text") or "")
        geometry = tuple(float(value) for value in (word.get("bbox") or ()))
        words.append(
            _CachedVisibilityWord(
                raw_text=raw_text,
                geometry=geometry,
                primitive_ref=native_word_primitive_ref(word),
                decision=classify_native_word_integrity(page, word),
                block_no=word.get("block_no"),
                line_no=word.get("line_no"),
                word_no=word.get("word_no"),
            )
        )
    for segment in native.get("segments") or ():
        decision = classify_native_segment_visibility(segment)
        if not decision.visible:
            continue
        raw_segment_id = str(segment.get("id") or "").strip()
        if not raw_segment_id:
            continue
        visible_segments.append(
            _CachedVisibleSegment(
                raw_segment_id=raw_segment_id,
                geometry=tuple(float(value) for value in decision.geometry),
                reason_codes=tuple(decision.reason_codes),
            )
        )
    return _CachedVisibilityPage(
        words=tuple(words),
        visible_segments=tuple(visible_segments),
    )


# Structural in-process construction seal. This is not a security boundary
# against equal-privilege Python code; it prevents ordinary caller-provided
# receipt maps from self-certifying visibility through the public constructor.
_VISIBILITY_AUTHORITY_SEAL = object()


@dataclass(frozen=True)
class NativeSegmentVisibilityDecision:
    visible: bool
    geometry: tuple[float, float, float, float]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RasterSegmentVisibilityReceipt:
    parent_observation_id: str
    page_parent_observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    source_partition_id: str
    image_sha256: str
    dpi: int
    pixel_geometry: tuple[float, float, float, float]
    geometry: tuple[float, float, float, float]
    detector_version: str = RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION
    visibility_render_sha256: Optional[str] = None


@dataclass(frozen=True)
class RasterOpeningPrimitiveVisibilityReceipt:
    parent_observation_id: str
    page_parent_observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    source_partition_id: str
    render_sha256: str
    primitive_kind: str
    dpi: int
    pixel_geometry: tuple[float, float, float, float]
    geometry: tuple[float, float, float, float]
    detector_version: str = RASTER_OPENING_PRIMITIVE_DETECTOR_VERSION


@dataclass(frozen=True)
class PublishedVisibleSourceSnapshot:
    revision: SourceRevisionRecord
    coverage: SourceDecodeCoverageRecord
    snapshot: ProducerSnapshotRecord
    base_source_snapshot_id: str
    visible_observation_ids: tuple[str, ...]
    text_observation_ids: tuple[str, ...] = ()
    ocr_tag_observation_ids: tuple[str, ...] = ()
    raster_opening_primitive_observation_ids: tuple[str, ...] = ()
    schema_version: str = SOURCE_VISIBILITY_SCHEMA_VERSION


def _segment_geometry(segment: Mapping[str, object]) -> tuple[float, float, float, float]:
    try:
        geometry = (
            float(segment["x1"]),
            float(segment["y1"]),
            float(segment["x2"]),
            float(segment["y2"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(VISIBILITY_GEOMETRY_INVALID) from exc
    if not all(math.isfinite(value) for value in geometry):
        raise ValueError(VISIBILITY_GEOMETRY_INVALID)
    if math.hypot(geometry[2] - geometry[0], geometry[3] - geometry[1]) < 0.5:
        raise ValueError(VISIBILITY_GEOMETRY_INVALID)
    return geometry


def _finite_rect(
    value: object,
) -> Optional[tuple[float, float, float, float]]:
    if value is None:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in (x0, y0, x1, y1)):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _exact_clip_rect(
    segment: Mapping[str, object],
) -> Optional[tuple[float, float, float, float]]:
    return _finite_rect(segment.get("clip_exact_rect"))


def _geometry_fully_inside_rect(
    geometry: tuple[float, float, float, float],
    rect: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    x0, y0, x1, y1 = rect
    for x, y in ((geometry[0], geometry[1]), (geometry[2], geometry[3])):
        if (
            x < x0 - tolerance
            or x > x1 + tolerance
            or y < y0 - tolerance
            or y > y1 + tolerance
        ):
            return False
    return True


def _rect_fully_inside_rect(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def classify_native_segment_visibility(
    segment: Mapping[str, object],
) -> NativeSegmentVisibilityDecision:
    """Return the authority-visibility decision for one native segment.

    An active clip becomes positive only when the vector extractor has
    independently proven the actual clip path is an axis-aligned rectangle and
    the full segment lies inside the exact rectangular intersection. scissor
    remains diagnostic and is never accepted as clip-shape proof.
    """

    try:
        geometry = _segment_geometry(segment)
    except ValueError:
        return NativeSegmentVisibilityDecision(
            visible=False,
            geometry=(0.0, 0.0, 0.0, 0.0),
            reason_codes=(VISIBILITY_GEOMETRY_INVALID,),
        )

    clip_known = segment.get("clip_known") is True
    clip_present = segment.get("clip_present") is True
    clip = segment.get("clip")

    if not clip_known:
        return NativeSegmentVisibilityDecision(
            visible=False,
            geometry=geometry,
            reason_codes=(VISIBILITY_CLIP_ASSOCIATION_UNKNOWN,),
        )
    if clip_present:
        if segment.get("clip_shape_known") is not True:
            return NativeSegmentVisibilityDecision(
                visible=False,
                geometry=geometry,
                reason_codes=(VISIBILITY_ACTIVE_CLIP_UNRESOLVED,),
            )
        exact_rect = _exact_clip_rect(segment)
        if exact_rect is None:
            return NativeSegmentVisibilityDecision(
                visible=False,
                geometry=geometry,
                reason_codes=(VISIBILITY_CLIP_STATE_INCONSISTENT,),
            )

        # PyMuPDF's diagnostic scissor is never clip-shape authority. When
        # present, it may only veto the independently proven exact rectangle:
        # malformed scissor data, or a scissor that cannot contain the exact
        # clip intersection, is contradictory producer evidence and fails
        # closed. A missing scissor does not weaken the source-owned exact-path
        # proof and therefore is not itself a contradiction.
        if clip is not None:
            diagnostic_clip = _finite_rect(clip)
            if diagnostic_clip is None or not _rect_fully_inside_rect(
                exact_rect,
                diagnostic_clip,
            ):
                return NativeSegmentVisibilityDecision(
                    visible=False,
                    geometry=geometry,
                    reason_codes=(VISIBILITY_CLIP_STATE_INCONSISTENT,),
                )

        if not _geometry_fully_inside_rect(geometry, exact_rect):
            return NativeSegmentVisibilityDecision(
                visible=False,
                geometry=geometry,
                reason_codes=(VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,),
            )
        return NativeSegmentVisibilityDecision(
            visible=True,
            geometry=geometry,
            reason_codes=(VISIBILITY_PROVEN_RECTANGULAR_CLIP,),
        )
    if clip is not None:
        return NativeSegmentVisibilityDecision(
            visible=False,
            geometry=geometry,
            reason_codes=(VISIBILITY_CLIP_STATE_INCONSISTENT,),
        )
    return NativeSegmentVisibilityDecision(
        visible=True,
        geometry=geometry,
        reason_codes=(VISIBILITY_PROVEN_NO_ACTIVE_CLIP,),
    )


def _native_parent_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    primitive_ref: str,
    geometry: Sequence[float],
) -> str:
    identity = {
        "document_id": document_id,
        "revision_id": revision_id,
        "partition_id": partition_id,
        "page_id": page_id,
        "kind": "native_pdf_segment",
        "primitive_ref": primitive_ref,
        "raw_text": "",
        "geometry": tuple(float(value) for value in geometry),
    }
    return stable_contract_id("source_observation", identity, digest_chars=32)


def _native_word_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    primitive_ref: str,
    raw_text: str,
    geometry: Sequence[float],
) -> str:
    identity = {
        "document_id": document_id,
        "revision_id": revision_id,
        "partition_id": partition_id,
        "page_id": page_id,
        "kind": "native_pdf_word",
        "primitive_ref": primitive_ref,
        "raw_text": raw_text,
        "geometry": tuple(float(value) for value in geometry),
    }
    return stable_contract_id("source_observation", identity, digest_chars=32)


def _visible_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    primitive_ref: str,
    parent_observation_id: str,
    geometry: Sequence[float],
    origin_kind: str = VISIBLE_SEGMENT_ORIGIN_KIND,
) -> str:
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": NATIVE_PDF_VISIBLE_SEGMENT,
        "primitive_ref": primitive_ref,
        "origin_kind": origin_kind,
        "parents": (parent_observation_id,),
        "raw_text": "",
        "geometry": tuple(float(value) for value in geometry),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


def _canonical_raster_geometry(
    geometry: Sequence[float],
) -> tuple[float, float, float, float]:
    if len(geometry) != 4:
        raise ValueError(VISIBILITY_GEOMETRY_INVALID)
    values = tuple(round(float(value), 6) for value in geometry)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(VISIBILITY_GEOMETRY_INVALID)
    first = (values[0], values[1])
    second = (values[2], values[3])
    if second < first:
        first, second = second, first
    if first == second:
        raise ValueError(VISIBILITY_GEOMETRY_INVALID)
    return (first[0], first[1], second[0], second[1])


def _raster_segment_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    image_sha256: str,
    identity_version: str,
    pixel_geometry: Sequence[float],
    geometry: Sequence[float],
    index: int,
) -> str:
    """Stable raster source identity with detector version kept as provenance.

    The payload deliberately preserves the historical v1 identity shape so
    current source ids do not migrate. ``identity_version`` is frozen by this
    module; the live detector version is retained separately in the visibility
    receipt. Canonical producer ordering below keeps ``index`` stable whenever
    the detected geometry set is unchanged.
    """
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": RASTER_PDF_SEGMENT,
        "image_sha256": image_sha256,
        "detector_version": str(identity_version),
        "pixel_geometry": tuple(float(v) for v in pixel_geometry),
        "geometry": tuple(float(v) for v in geometry),
        "index": int(index),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


def _raster_segment_receipt_matches_parent(
    receipt: RasterSegmentVisibilityReceipt, parent: SourceObservationRecord,
) -> bool:
    """Bind registration facts to the authenticated immutable source parent.

    Detector version remains provenance; the historical identity version is
    fixed independently. A replaced receipt cannot change pixel geometry,
    render identity or DPI while borrowing an already verified source record.
    """
    try:
        parts = str(parent.source_primitive_ref).split(":")
        if len(parts) not in (4, 5) or parts[0] != "raster_segment":
            return False
        render_sha, identity_version, index = parts[1], parts[2], parts[-1]
        if (render_sha != receipt.image_sha256 or int(index) < 0
                or str(int(index)) != index):
            return False
        if identity_version == RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION:
            if (len(parts) != 4 or receipt.dpi != RASTER_RENDER_DPI
                    or receipt.visibility_render_sha256 is not None):
                return False
        elif identity_version in {COMPACT_WALL_BAND_IDENTITY_VERSION,
                                  TERMINAL_WALL_BAND_IDENTITY_VERSION}:
            full_hash = receipt.visibility_render_sha256
            if (len(parts) != 5 or receipt.dpi != RASTER_OPENING_PRIMITIVE_RENDER_DPI
                    or not isinstance(full_hash, str) or len(full_hash) != 64
                    or any(c not in '0123456789abcdef' for c in full_hash)
                    or parts[3] != full_hash):
                return False
        else:
            return False
        expected_geometry = tuple(round(float(value) * 72.0 / receipt.dpi, 6)
                                  for value in receipt.pixel_geometry)
        if expected_geometry != tuple(receipt.geometry):
            return False
        expected_id = _raster_segment_observation_id(
            document_id=receipt.document_id, revision_id=receipt.revision_id,
            page_id=receipt.page_id, partition_id=receipt.source_partition_id,
            image_sha256=receipt.image_sha256, identity_version=identity_version,
            pixel_geometry=receipt.pixel_geometry, geometry=receipt.geometry,
            index=int(index),
        )
        return expected_id == parent.observation_id
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False


def _axis_aligned_geometry_fully_covered_by_rect_union(
    geometry: Sequence[float],
    rects: Sequence[Sequence[float]],
    *,
    tolerance: float = _RASTER_GEOMETRY_QUANTIZATION_TOLERANCE_PT,
) -> bool:
    """Prove an axis-aligned segment is fully covered by source image regions.

    A midpoint hit is not source ownership: rendered vector annotation can cross
    a raster image and share its midpoint. Coverage may span multiple adjacent
    image tiles, which is common for tiled raster plan sheets.
    """
    x0, y0, x1, y1 = _canonical_raster_geometry(geometry)
    horizontal = abs(y1 - y0) <= tolerance
    vertical = abs(x1 - x0) <= tolerance
    if not horizontal and not vertical:
        return False

    if horizontal:
        start, end, fixed = x0, x1, (y0 + y1) / 2.0
    else:
        start, end, fixed = y0, y1, (x0 + x1) / 2.0

    covered: list[tuple[float, float]] = []
    for raw_rect in rects:
        rect = _finite_rect(raw_rect)
        if rect is None:
            continue
        rx0, ry0, rx1, ry1 = rect
        if horizontal:
            if not (ry0 - tolerance <= fixed <= ry1 + tolerance):
                continue
            first, second = max(start, rx0), min(end, rx1)
        else:
            if not (rx0 - tolerance <= fixed <= rx1 + tolerance):
                continue
            first, second = max(start, ry0), min(end, ry1)
        if second + tolerance >= first:
            covered.append((first, second))

    if not covered:
        return False
    covered.sort()
    cursor = start
    for first, second in covered:
        if first > cursor + tolerance:
            return False
        cursor = max(cursor, second)
        if cursor >= end - tolerance:
            return True
    return cursor >= end - tolerance


def _raster_visible_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    parent_observation_id: str,
    geometry: Sequence[float],
) -> str:
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": RASTER_PDF_VISIBLE_SEGMENT,
        "origin_kind": RASTER_VISIBLE_SEGMENT_ORIGIN_KIND,
        "parents": (parent_observation_id,),
        "geometry": tuple(float(v) for v in geometry),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


def _raster_opening_primitive_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    primitive: RasterOpeningSourcePrimitive,
) -> str:
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": RASTER_OPENING_PRIMITIVE_SEGMENT,
        "identity_version": RASTER_OPENING_PRIMITIVE_IDENTITY_VERSION,
        "primitive_kind": primitive.primitive_kind,
        "geometry": tuple(float(value) for value in primitive.geometry_pt),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


def _raster_opening_visible_primitive_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    parent_observation_id: str,
    primitive: RasterOpeningSourcePrimitive,
) -> str:
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": primitive.primitive_kind,
        "origin_kind": RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND,
        "parents": (parent_observation_id,),
        "primitive_kind": primitive.primitive_kind,
        "geometry": tuple(float(value) for value in primitive.geometry_pt),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


class SourceVisibilityProducer:
    """Trusted producer wrapper that mints visibility receipts from PDF bytes.

    The underlying generic ``SourceObservationProducer`` is deliberately not
    exposed. Ordinary consumers receive read-only producer-owned authorities.
    """

    def __init__(self, *, producer_method: str, producer_version: str) -> None:
        self._producer = SourceObservationProducer(
            producer_method=producer_method,
            producer_version=producer_version,
        )
        self._visibility_receipts: dict[tuple[str, str], str] = {}
        self._raster_visibility_receipts: dict[
            tuple[str, str], RasterSegmentVisibilityReceipt
        ] = {}
        self._raster_opening_primitive_receipts: dict[
            tuple[str, str], RasterOpeningPrimitiveVisibilityReceipt
        ] = {}
        self._visibility_page_cache: (
            "OrderedDict[tuple[str, str, int], _CachedVisibilityPage]"
        ) = OrderedDict()
        # One source-bound physical-opening authority per producer.  The
        # visibility authority it wraps is a live read-only view over this
        # producer's store/receipt maps, so later producer-owned augmentation is
        # visible without rebuilding opening candidate caches.
        self._physical_opening_authority_cache = None
        # Physical scale is likewise source-owned and selector-keyed. Reuse one
        # producer so wall, opening-void, and gross-wall compositions share the
        # same immutable page/viewport analysis instead of rescanning it.
        self._physical_scale_producer_cache = None
        # Physical-wall source-page reconstruction is deterministic for an
        # immutable published snapshot and decision scope. Keep this cache on
        # the source producer so page-wide wall authority and later authenticated
        # viewport fallback can reuse the same exact decoded source page without
        # introducing module-global state or weakening source lineage.
        self._physical_wall_page_segments_cache: dict[
            tuple[object, ...],
            tuple[tuple[dict[str, object], ...], tuple[str, ...], float, float],
        ] = {}
        # Page-scope wall assembly already segments the immutable native page to
        # evaluate scope boundaries. Reuse that exact producer-owned viewport
        # census if a later room fallback asks for authenticated viewport wall
        # scopes, rather than reopening and segmenting the same page again.
        self._physical_wall_page_viewports_cache: dict[
            tuple[str, str, str, str, str],
            object,
        ] = {}
        # Raster extraction is deterministic for immutable source bytes, the
        # fixed render DPI, and the detector version. Cache successful render
        # attempts per revision/page so repeated downstream compositions do not
        # rerender and republish the same page into ever-growing snapshots.
        self._raster_visibility_attempted_pages: set[tuple[str, str]] = set()
        self._raster_opening_primitive_attempted_pages: set[
            tuple[str, str]
        ] = set()
        self._text_integrity_receipts: dict[
            tuple[str, str], PdfTextIntegrityReceipt
        ] = {}
        self._native_paint_page_cache: OrderedDict = OrderedDict()
        self._native_dimension_component_page_cache: OrderedDict = OrderedDict()
        self._published_by_revision: dict[str, PublishedVisibleSourceSnapshot] = {}

    def authority(self) -> "SourceVisibilityAuthority":
        return SourceVisibilityAuthority(
            self._producer.authority(),
            self._visibility_receipts,
            self._raster_visibility_receipts,
            self._raster_opening_primitive_receipts,
            _seal=_VISIBILITY_AUTHORITY_SEAL,
        )

    def render_raster_opening_source_page(
        self,
        revision_id: str,
        page_id: str,
    ):
        """Return the producer-owned images-only raster evidence for one page.

        Callers may address only a current ingested revision/page. They cannot
        supply pixels, DPI, crop geometry, masks, thresholds, candidate bands,
        openings, or expected values. This is source evidence only; it grants no
        physical-opening proposition.
        """

        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            raise ValueError(OBSERVATION_UNAVAILABLE)
        clean_page_id = str(page_id).strip()
        if not clean_page_id:
            raise ValueError(OBSERVATION_UNAVAILABLE)
        decoded_page_ids = {
            str(int(value)) for value in published.coverage.decoded_pages
        }
        if clean_page_id not in decoded_page_ids:
            raise ValueError(OBSERVATION_UNAVAILABLE)

        png_bytes, page_parent, native_frame = (
            self._producer.render_native_page_png(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=clean_page_id,
                dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                include_native_frame=True,
                images_only=True,
            )
        )
        return (
            bytes(png_bytes),
            replace(page_parent),
            native_frame,
            RASTER_OPENING_PRIMITIVE_RENDER_DPI,
        )

    @staticmethod
    def _registration_scale_from_image_placements(
        placements: Sequence[NativePageImagePlacement],
    ) -> tuple[float, float] | None:
        """Return one page-wide anisotropy descriptor when tiles agree.

        This helper is registration evidence only. Raster primitive extraction
        remains page-coordinate based and does not depend on page-wide
        agreement; swing G17 consumes placement transforms locally per aperture.
        """

        factors: list[tuple[float, float]] = []
        for placement in placements:
            x0, y0, x1, y1 = placement.bbox_pt
            sx = (float(x1) - float(x0)) / float(placement.pixel_width)
            sy = (float(y1) - float(y0)) / float(placement.pixel_height)
            if (
                not math.isfinite(sx)
                or not math.isfinite(sy)
                or sx <= 0.0
                or sy <= 0.0
            ):
                continue
            reference = math.sqrt(sx * sy)
            factors.append((sx / reference, sy / reference))
        if not factors:
            return None
        first_x, first_y = factors[0]
        if any(
            not (
                math.isclose(x, first_x, rel_tol=1e-4, abs_tol=1e-6)
                and math.isclose(y, first_y, rel_tol=1e-4, abs_tol=1e-6)
            )
            for x, y in factors[1:]
        ):
            return None
        return (float(first_x), float(first_y))

    def native_unstroked_fill_evidence(
        self, selector: ObservationSelector, *, support_observation_ids: Sequence[str]
    ):
        """Reprove that all selected native edges are unpainted white-fill paths.

        Raw geometry remains available. These candidate opposing atoms neither
        assert physical non-existence nor close the opening candidate universe.
        Cached paint facts never replace observation/receipt authentication.
        """
        from pb_migration_contracts import EvidenceAtom
        from pb_vector_geometry_v130 import extract_native_page
        from pb_wall_room_topology_typed_negative_evidence import (
            KIND_ANNOTATION_BORDER, POLARITY_OPPOSING,
        )

        published = self.published_snapshot_for_revision(selector.revision_id)
        if (published is None or published.snapshot.snapshot_id != selector.snapshot_id
                or published.revision.document_id != selector.document_id
                or published.revision.source_sha256 != selector.source_sha256):
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        source_bytes = self._producer._store.source_bytes_by_revision.get(selector.revision_id)
        if not source_bytes or hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        selected = frozenset(str(i) for i in support_observation_ids)
        if not selected or selector.observation_id not in selected:
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        records = {}
        visibility = self.authority()
        for observation_id in sorted(selected):
            result = visibility.resolve_visible(replace(selector, observation_id=observation_id))
            if result.status is not EvidenceResolutionStatus.CORROBORATED or result.observation is None:
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            records[observation_id] = result.observation
        if any(r.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT for r in records.values()):
            return ()
        page_ids = {r.page_id for r in records.values()}
        if len(page_ids) != 1:
            return ()
        page_id = next(iter(page_ids))
        cache_key = (selector.source_sha256, page_id)
        paint = self._native_paint_page_cache.get(cache_key)
        if paint is None:
            try:
                with fitz.open(stream=source_bytes, filetype='pdf') as pdf:
                    page = pdf[int(page_id) - 1]
                    drawings = page.get_drawings()
                    segments = extract_native_page(page)['segments']
                    paint = {}
                    for segment in segments:
                        drawing = drawings[segment['path_index']]
                        paint[segment['id']] = (
                            tuple(segment[k] for k in ('x1','y1','x2','y2')),
                            segment['kind'], drawing.get('type'), drawing.get('color'),
                            drawing.get('fill'), drawing.get('fill_opacity'),
                            drawing.get('seqno'),
                        )
            except (ValueError, IndexError, KeyError, RuntimeError):
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            self._native_paint_page_cache[cache_key] = paint
            while len(self._native_paint_page_cache) > 2:
                self._native_paint_page_cache.popitem(last=False)
        self._native_paint_page_cache.move_to_end(cache_key)
        owned = []
        for observation_id, record in sorted(records.items()):
            primitive = record.source_primitive_ref.removeprefix('visible:segment:')
            facts = paint.get(primitive)
            if facts is None or tuple(record.geometry) != facts[0]:
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            geometry, kind, paint_type, color, fill, opacity, seqno = facts
            if (kind != 'rect_edge' or paint_type != 'f' or color is not None
                    or fill is None or tuple(fill) != (1.,1.,1.) or opacity != 1.):
                return ()
            owned.append((primitive, observation_id, geometry, seqno))
        metadata = dict(revision_id=selector.revision_id, source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id, polarity=POLARITY_OPPOSING,
            source_primitive_ids=tuple(sorted(p for p,_,_,_ in owned)),
            source_observation_ids=tuple(sorted(selected)),
            primitive_paint_ownership=tuple(owned),
            all_source_primitives_covered=True, paint_type='f', fill=(1.,1.,1.),
            fill_opacity=1., stroke=None)
        return (EvidenceAtom(evidence_id=stable_contract_id('native_unstroked_white_fill', metadata),
            document_id=selector.document_id, page_id=page_id, kind=KIND_ANNOTATION_BORDER,
            method='native_pdf_unstroked_fill_source_role', status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=('native_unstroked_white_fill_boundary',), metadata=metadata),)

    def native_dimension_cap_evidence(
        self, selector: ObservationSelector, *, opening_support_ids: Sequence[str]
    ):
        """Reprove exact native annotation opposition from this source only.

        Missing or damaged source receipts raise the existing integrity error;
        consumers must not mistake failed authentication for no opposition.
        Results are candidate EvidenceAtoms, never metric or non-existence authority.
        """
        from pb_native_dimension_cap_evidence import (
            compile_native_dimension_cap_components,
            native_dimension_cap_evidence_from_components,
        )

        published = self.published_snapshot_for_revision(selector.revision_id)
        if (published is None or published.snapshot.snapshot_id != selector.snapshot_id
                or published.revision.document_id != selector.document_id
                or published.revision.source_sha256 != selector.source_sha256):
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        visibility = self.authority()
        selected = frozenset(opening_support_ids)
        if selector.observation_id not in selected:
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        rows = visibility.authenticated_visible_observations(published)
        records = {i: r for i, r in rows if r.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT}
        if not selected or not selected <= records.keys():
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        page_id = records[selector.observation_id].page_id
        if any(records[i].page_id != page_id for i in selected):
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        segments = {i: tuple(r.geometry) for i, r in records.items() if r.page_id == page_id}
        source_bytes = self._producer._store.source_bytes_by_revision.get(selector.revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        try:
            with fitz.open(stream=source_bytes, filetype='pdf') as pdf:
                page = pdf[int(page_id) - 1]
                directions = {(bi, li): tuple(line.get('dir', (0., 0.)))
                    for bi, block in enumerate(page.get_text('dict', flags=fitz.TEXTFLAGS_WORDS)['blocks'])
                    for li, line in enumerate(block.get('lines', []))}
        except (ValueError, IndexError, RuntimeError):
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
        text_authority = self.text_integrity_authority()
        source_authority = self._producer.authority()
        words = []
        for observation_id in published.text_observation_ids:
            word_selector = replace(selector, observation_id=observation_id)
            source_result = source_authority.resolve(word_selector)
            record = source_result.observation
            if source_result.status is not EvidenceResolutionStatus.CORROBORATED or record is None:
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            if record.page_id != page_id:
                continue
            text = text_authority.resolve_text(word_selector)
            if text.receipt is None or text.status is EvidenceResolutionStatus.CONFLICT:
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            if text.status is not EvidenceResolutionStatus.CORROBORATED or text.receipt is None:
                continue
            receipt = text.receipt
            words.append(dict(id=observation_id, text=text.trusted_text,
                bbox=receipt.geometry,
                axis=directions.get((receipt.block_no, receipt.line_no), (0., 0.))))
        # Cache immutable geometry facts only. Every source byte, observation
        # and text receipt above is reauthenticated before even a cache hit.
        # The full authenticated inputs key the cache, not a caller's role or
        # a source address alone. Fresh EvidenceAtoms are built for each query.
        fingerprint = stable_contract_id('native_dimension_component_inputs', {
            'segments': tuple(sorted(segments.items())),
            'words': tuple(sorted((w['id'], w['text'], tuple(w['bbox']), tuple(w['axis']))
                for w in words)),
        })
        cache_key = (selector.source_sha256, selector.snapshot_id, page_id, fingerprint)
        components = self._native_dimension_component_page_cache.get(cache_key)
        if components is None:
            components = compile_native_dimension_cap_components(segments=segments, words=words)
            self._native_dimension_component_page_cache[cache_key] = components
            while len(self._native_dimension_component_page_cache) > 2:
                self._native_dimension_component_page_cache.popitem(last=False)
        self._native_dimension_component_page_cache.move_to_end(cache_key)
        return native_dimension_cap_evidence_from_components(components=components,
            selected_ids=tuple(selected), document_id=selector.document_id, page_id=page_id,
            revision_id=selector.revision_id, source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id)

    def raster_opening_image_placements(
        self,
        revision_id: str,
        page_id: str,
    ) -> tuple[NativePageImagePlacement, ...]:
        """Return producer-owned embedded-image registration evidence."""

        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            raise ValueError(OBSERVATION_UNAVAILABLE)
        clean_page_id = str(page_id).strip()
        if not clean_page_id:
            raise ValueError(OBSERVATION_UNAVAILABLE)
        return self._producer.native_page_image_placements(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=clean_page_id,
        )

    def raster_opening_registration_scale(
        self,
        revision_id: str,
        page_id: str,
    ) -> tuple[float, float] | None:
        """Return page-wide registration only when every image tile agrees.

        This is intentionally not a prerequisite for primitive publication.
        Local swing candidates use raster_opening_image_placements() instead.
        """

        return self._registration_scale_from_image_placements(
            self.raster_opening_image_placements(revision_id, page_id)
        )

    def physical_opening_authority(self):
        """Return one cached opening authority bound to this producer.

        The returned authority remains source-owned: callers cannot inject
        observations or candidate sets, and its underlying visibility reader
        sees only this producer's immutable lineage and producer-owned receipt
        maps.  Reuse prevents repeated page candidate/existence reconstruction
        across wall, semantic-opening, host-binding, and downstream live stages.
        """
        if self._physical_opening_authority_cache is None:
            from pb_physical_opening_authority import PhysicalOpeningAuthority

            self._physical_opening_authority_cache = (
                PhysicalOpeningAuthority.from_source_visibility_producer(self)
            )
        return self._physical_opening_authority_cache

    def physical_scale_producer(self):
        """Return one cached physical-scale producer bound to this source root."""
        if self._physical_scale_producer_cache is None:
            from pb_physical_scale_authority import PhysicalScaleProducer

            self._physical_scale_producer_cache = (
                PhysicalScaleProducer.from_source_visibility_producer(self)
            )
        return self._physical_scale_producer_cache

    def text_integrity_authority(self) -> PdfTextIntegrityAuthority:
        return PdfTextIntegrityAuthority(
            self._producer.authority(),
            self._text_integrity_receipts,
            _seal=_PDF_TEXT_AUTHORITY_SEAL,
        )

    def published_snapshot_for_revision(
        self, revision_id: str
    ) -> Optional[PublishedVisibleSourceSnapshot]:
        """Producer-owned lookup of a prior ingestion's own complete snapshot.

        Reads only this producer's own private cache -- there is no way for a
        caller to inject or narrow an entry here. Downstream consumers that
        need the COMPLETE, un-narrowable text-observation universe for a
        revision (rather than a caller-curated subset) must go through this,
        never accept an id list as an argument.
        """
        return self._published_by_revision.get(str(revision_id))

    def augment_with_raster_ocr_tags(
        self,
        revision_id: str,
        *,
        viewport_decision,
    ) -> tuple[tuple[object, ...], PublishedVisibleSourceSnapshot]:
        """Publish producer-owned OCR opening tags into this exact source snapshot.

        Callers provide only an already-authenticated viewport decision. OCR
        pixels, backend choice, parent observation ids, partition ids, tag text,
        geometry and expected quantities remain producer-owned. The returned
        tags are evidence only; this method does not bind them to openings or
        publish commercial counts.
        """
        return self._augment_with_raster_ocr_tags(
            revision_id,
            viewport_decision=viewport_decision,
            test_backend=None,
        )

    def augment_with_raster_ocr_tags_for_tests(
        self,
        revision_id: str,
        *,
        viewport_decision,
        backend,
    ) -> tuple[tuple[object, ...], PublishedVisibleSourceSnapshot]:
        """Deterministic test-only OCR handoff accepting exact MockOCRBackend."""
        from pb_portable_raster_ocr_authority import MockOCRBackend

        if type(backend) is not MockOCRBackend:
            raise TypeError("test OCR augmentation requires exact MockOCRBackend")
        return self._augment_with_raster_ocr_tags(
            revision_id,
            viewport_decision=viewport_decision,
            test_backend=backend,
        )

    def _augment_with_raster_ocr_tags(
        self,
        revision_id: str,
        *,
        viewport_decision,
        test_backend,
    ) -> tuple[tuple[object, ...], PublishedVisibleSourceSnapshot]:
        from pb_portable_raster_ocr_authority import PortableRasterOCRSelector
        from pb_raster_ocr_tag_observation_bridge import RasterOCRTagObservationProducer

        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            raise ValueError(OBSERVATION_UNAVAILABLE)

        page_id = str(getattr(getattr(viewport_decision, "viewport", None), "page_number", "") or "")
        viewport_id = str(getattr(getattr(viewport_decision, "viewport", None), "view_id", "") or "")
        if not page_id or not viewport_id:
            return (), published

        selector = PortableRasterOCRSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            viewport_id=viewport_id,
        )
        bridge = (
            RasterOCRTagObservationProducer.create_for_tests(
                source_producer=self._producer,
                backend=test_backend,
                dpi=300,
            )
            if test_backend is not None
            else RasterOCRTagObservationProducer.create(
                source_producer=self._producer,
                dpi=300,
            )
        )
        tags, final_snapshot_id = bridge.publish(
            selector=selector,
            viewport_decision=viewport_decision,
        )
        if not tags or final_snapshot_id == published.snapshot.snapshot_id:
            return tuple(tags), published

        snapshot = self._producer._store.snapshots.get(final_snapshot_id)
        if snapshot is None:
            raise RuntimeError(f"{PRODUCER_INTEGRITY_FAILURE}: OCR snapshot unavailable")

        old_snapshot_id = published.snapshot.snapshot_id
        for observation_id in published.visible_observation_ids:
            native_parent = self._visibility_receipts.get((old_snapshot_id, observation_id))
            if native_parent is not None:
                self._visibility_receipts[(final_snapshot_id, observation_id)] = native_parent
            raster_receipt = self._raster_visibility_receipts.get((old_snapshot_id, observation_id))
            if raster_receipt is not None:
                self._raster_visibility_receipts[(final_snapshot_id, observation_id)] = raster_receipt

        for observation_id in published.text_observation_ids:
            receipt = self._text_integrity_receipts.get((old_snapshot_id, observation_id))
            if receipt is not None:
                self._text_integrity_receipts[(final_snapshot_id, observation_id)] = receipt
        for observation_id in published.raster_opening_primitive_observation_ids:
            receipt = self._raster_opening_primitive_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if receipt is not None:
                self._raster_opening_primitive_receipts[
                    (final_snapshot_id, observation_id)
                ] = receipt

        tag_ids = tuple(
            dict.fromkeys(
                [
                    *published.ocr_tag_observation_ids,
                    *(str(getattr(tag, "observation_id", "")) for tag in tags),
                ]
            )
        )
        if any(not observation_id for observation_id in tag_ids):
            raise RuntimeError(f"{PRODUCER_INTEGRITY_FAILURE}: OCR tag id unavailable")

        updated = PublishedVisibleSourceSnapshot(
            revision=replace(published.revision),
            coverage=replace(published.coverage),
            snapshot=replace(snapshot),
            base_source_snapshot_id=published.base_source_snapshot_id,
            visible_observation_ids=tuple(published.visible_observation_ids),
            text_observation_ids=tuple(published.text_observation_ids),
            ocr_tag_observation_ids=tag_ids,
            raster_opening_primitive_observation_ids=tuple(
                published.raster_opening_primitive_observation_ids
            ),
        )
        self._published_by_revision[updated.revision.revision_id] = updated
        return tuple(tags), updated

    def authenticated_ocr_tag_observations(
        self,
        revision_id: str,
    ) -> tuple[object, ...]:
        """Return the producer-owned OCR tag universe for the current snapshot.

        Every returned observation is independently re-resolved and must be an
        OCR text observation derived directly from the immutable native page.
        """
        published = self._published_by_revision.get(str(revision_id))
        if published is None or not published.ocr_tag_observation_ids:
            return ()

        from pb_raster_ocr_tag_observation_bridge import (
            OCR_TAG_OBSERVATION_KIND,
            OCR_TAG_OBSERVATION_ORIGIN_KIND,
        )

        authority = self._producer.authority()
        records: list[object] = []
        for observation_id in published.ocr_tag_observation_ids:
            result = authority.resolve(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = result.observation
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or observation.observation_kind != OCR_TAG_OBSERVATION_KIND
                or observation.origin_kind != OCR_TAG_OBSERVATION_ORIGIN_KIND
                or len(observation.derivation_parent_ids) != 1
            ):
                raise RuntimeError(f"{PRODUCER_INTEGRITY_FAILURE}: invalid OCR tag observation")

            parent_result = authority.resolve(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation.derivation_parent_ids[0],
                )
            )
            parent = parent_result.observation
            if (
                parent_result.status is not EvidenceResolutionStatus.CORROBORATED
                or parent is None
                or parent.observation_kind != "native_pdf_page"
                or parent.origin_kind != "native"
                or parent.document_id != observation.document_id
                or parent.revision_id != observation.revision_id
                or parent.source_sha256 != observation.source_sha256
                or parent.page_id != observation.page_id
                or parent.source_partition_id != observation.source_partition_id
            ):
                raise RuntimeError(f"{PRODUCER_INTEGRITY_FAILURE}: OCR tag parent mismatch")
            records.append(observation)
        return tuple(records)

    def optional_content_state_for_scope(
        self,
        revision_id: str,
        *,
        page_ids: Sequence[str] | None = None,
    ) -> str:
        """Return producer-derived optional-content state for an exact source scope.

        "known_visible" is returned only when the immutable stored PDF has no
        Optional Content Groups at all. Any OCG presence, source mismatch, bad
        page address, or decode error remains "unresolved".
        """
        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            return "unresolved"
        decoded = {str(int(value)) for value in published.coverage.decoded_pages}
        requested = (
            decoded
            if page_ids is None
            else {
                str(page_id).strip()
                for page_id in page_ids
                if str(page_id).strip()
            }
        )
        if not requested or not requested <= decoded:
            return "unresolved"

        source_bytes = self._producer._store.source_bytes_by_revision.get(
            str(revision_id)
        )
        if not source_bytes:
            return "unresolved"
        if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return "unresolved"

        try:
            pdf = fitz.open(stream=source_bytes, filetype="pdf")
        except Exception:
            return "unresolved"
        try:
            try:
                ocgs = pdf.get_ocgs() or {}
            except Exception:
                return "unresolved"
            return "known_visible" if not ocgs else "unresolved"
        finally:
            pdf.close()

    def xobject_traversal_truncated_for_scope(
        self,
        revision_id: str,
        *,
        page_ids: Sequence[str] | None = None,
    ) -> bool:
        """Conservatively flag scopes containing unresolved Form XObjects.

        Native page extraction currently has no producer receipt proving that
        every Form XObject was semantically traversed. Therefore any Form
        XObject in a requested page, invalid page address, source mismatch, or
        decode failure is treated as truncated/unresolved. Image XObjects are
        handled separately by the raster visibility augmentation path.
        """
        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            return True
        decoded = {str(int(value)) for value in published.coverage.decoded_pages}
        requested = (
            decoded
            if page_ids is None
            else {
                str(page_id).strip()
                for page_id in page_ids
                if str(page_id).strip()
            }
        )
        if not requested or not requested <= decoded:
            return True

        source_bytes = self._producer._store.source_bytes_by_revision.get(
            str(revision_id)
        )
        if not source_bytes:
            return True
        if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return True

        try:
            pdf = fitz.open(stream=source_bytes, filetype="pdf")
        except Exception:
            return True
        try:
            for page_id in requested:
                try:
                    page_index = int(page_id) - 1
                except (TypeError, ValueError):
                    return True
                if page_index < 0 or page_index >= int(pdf.page_count):
                    return True
                try:
                    if pdf.load_page(page_index).get_xobjects():
                        return True
                except Exception:
                    return True
            return False
        finally:
            pdf.close()
    def opening_dimension_authority(self):
        """Return the read-only dimension resolver bound to this producer."""
        from pb_opening_dimension_authority import (
            OpeningDimensionAuthority,
            _OPENING_DIMENSION_AUTHORITY_SEAL,
        )

        return OpeningDimensionAuthority(
            self.authority(),
            self.text_integrity_authority(),
            physical_opening_authority=self.physical_opening_authority(),
            _seal=_OPENING_DIMENSION_AUTHORITY_SEAL,
        )

    def ingest_native_pdf_bytes(
        self,
        *,
        document_id: str,
        source_bytes: bytes | bytearray | memoryview,
        source_locator: str,
        page_ids: Sequence[str] | None = None,
    ) -> PublishedVisibleSourceSnapshot:
        immutable_bytes = bytes(source_bytes)
        base: PublishedSourceSnapshot = self._producer.ingest_native_pdf_bytes(
            document_id=document_id,
            source_bytes=immutable_bytes,
            source_locator=source_locator,
            page_ids=page_ids,
        )
        cached = self._published_by_revision.get(base.revision.revision_id)
        if cached is not None:
            return cached

        snapshot = base.snapshot
        visible_ids: list[str] = []
        visible_specs: list[dict[str, object]] = []
        text_receipts: list[tuple[str, PdfTextIntegrityReceipt]] = []
        pdf: Optional[fitz.Document] = None
        try:
            for page_number in base.coverage.decoded_pages:
                page_index = int(page_number) - 1
                page_id = str(page_number)
                partition_id = f"page:{page_number}"
                visibility_cache_key = (
                    base.revision.source_sha256,
                    base.snapshot.snapshot_id,
                    int(page_number),
                )
                derived = self._visibility_page_cache.get(visibility_cache_key)
                if derived is not None:
                    self._visibility_page_cache.move_to_end(visibility_cache_key)
                if derived is None:
                    if pdf is None:
                        pdf = fitz.open(stream=immutable_bytes, filetype="pdf")
                    page = pdf.load_page(page_index)
                    native_cached = self._producer._cached_native_page(
                        base.revision.source_sha256, int(page_number)
                    )
                    derived = _derive_visibility_page(
                        page,
                        native_page=(
                            None
                            if native_cached is None or native_cached.failed
                            else native_cached.native_page
                        ),
                    )
                    self._visibility_page_cache[visibility_cache_key] = derived
                    self._visibility_page_cache.move_to_end(visibility_cache_key)
                    while (
                        len(self._visibility_page_cache)
                        > _VISIBILITY_PAGE_CACHE_MAX_PAGES
                    ):
                        self._visibility_page_cache.popitem(last=False)

                for word in derived.words:
                    parent_id = _native_word_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=word.primitive_ref,
                        raw_text=word.raw_text,
                        geometry=word.geometry,
                    )
                    text_receipts.append(
                        (
                            parent_id,
                            build_pdf_text_integrity_receipt(
                                parent_observation_id=parent_id,
                                document_id=base.revision.document_id,
                                revision_id=base.revision.revision_id,
                                source_sha256=base.revision.source_sha256,
                                page_id=page_id,
                                source_partition_id=partition_id,
                                geometry=word.geometry,
                                decision=word.decision,
                                block_no=word.block_no,
                                line_no=word.line_no,
                                word_no=word.word_no,
                            ),
                        )
                    )
                for segment in derived.visible_segments:
                    parent_ref = f"segment:{segment.raw_segment_id}"
                    parent_id = _native_parent_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=parent_ref,
                        geometry=segment.geometry,
                    )
                    visible_ref = f"visible:{parent_ref}"
                    origin_kind = (
                        RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND
                        if VISIBILITY_PROVEN_RECTANGULAR_CLIP in segment.reason_codes
                        else VISIBLE_SEGMENT_ORIGIN_KIND
                    )
                    visible_id = _visible_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=visible_ref,
                        parent_observation_id=parent_id,
                        geometry=segment.geometry,
                        origin_kind=origin_kind,
                    )
                    visible_specs.append(
                        {
                            "page_id": page_id,
                            "source_partition_id": partition_id,
                            "observation_kind": NATIVE_PDF_VISIBLE_SEGMENT,
                            "source_primitive_ref": visible_ref,
                            "origin_kind": origin_kind,
                            "parent_observation_ids": (parent_id,),
                            "raw_text": "",
                            "geometry": segment.geometry,
                            "viewport_id": None,
                            "observation_id": visible_id,
                        }
                    )
                    visible_ids.append(visible_id)
        finally:
            if pdf is not None:
                pdf.close()

        if visible_specs:
            snapshot = self._producer.publish_derived_observations(
                document_id=base.revision.document_id,
                revision_id=base.revision.revision_id,
                base_snapshot_id=base.snapshot.snapshot_id,
                observations=visible_specs,
            )

        published = PublishedVisibleSourceSnapshot(
            revision=replace(base.revision),
            coverage=replace(base.coverage),
            snapshot=replace(snapshot),
            base_source_snapshot_id=base.snapshot.snapshot_id,
            visible_observation_ids=tuple(sorted(set(visible_ids))),
            text_observation_ids=tuple(sorted({item[0] for item in text_receipts})),
        )
        source_authority = self._producer.authority()
        for visible_id in published.visible_observation_ids:
            result = source_authority.resolve(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=visible_id,
                )
            )
            if result.observation is None or len(result.observation.derivation_parent_ids) != 1:
                raise RuntimeError(f"{PRODUCER_INTEGRITY_FAILURE}: visible receipt missing parent")
            self._visibility_receipts[
                (published.snapshot.snapshot_id, visible_id)
            ] = result.observation.derivation_parent_ids[0]

        for observation_id, receipt in text_receipts:
            result = source_authority.resolve(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = result.observation
            if (
                observation is None
                or result.status != EvidenceResolutionStatus.CORROBORATED
                or observation.observation_kind != "native_pdf_word"
                or observation.origin_kind != "native"
                or observation.observation_id != receipt.parent_observation_id
                or observation.document_id != receipt.document_id
                or observation.revision_id != receipt.revision_id
                or observation.source_sha256 != receipt.source_sha256
                or observation.page_id != receipt.page_id
                or observation.source_partition_id != receipt.source_partition_id
                or observation.raw_text != receipt.raw_text
                or tuple(observation.geometry) != tuple(receipt.geometry)
            ):
                raise RuntimeError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: text integrity receipt parent mismatch"
                )
            key = (published.snapshot.snapshot_id, observation_id)
            prior = self._text_integrity_receipts.get(key)
            if prior is not None and prior != receipt:
                raise RuntimeError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: text integrity receipt differs"
                )
            self._text_integrity_receipts[key] = receipt

        self._published_by_revision[published.revision.revision_id] = published
        return published



    def augment_with_raster_visible_segments(
        self,
        revision_id: str,
        *,
        page_ids: Sequence[str] | None = None,
    ) -> PublishedVisibleSourceSnapshot:
        """Add source-bound raster visible segments where native visibility is absent.

        Callers may optionally address source pages, but cannot supply pixels,
        line segments, DPI, detector thresholds, marks, counts, or expected
        quantities. Rendering, detection, geometry, and lineage remain
        producer-owned.
        """

        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            raise ValueError(OBSERVATION_UNAVAILABLE)

        source_authority = self._producer.authority()
        old_snapshot_id = published.snapshot.snapshot_id
        completed_attempt_keys: set[tuple[str, str]] = set()
        pages_with_visible: set[str] = set()
        for observation_id in published.visible_observation_ids:
            result = source_authority.resolve(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=old_snapshot_id,
                    observation_id=observation_id,
                )
            )
            if result.observation is not None:
                pages_with_visible.add(str(result.observation.page_id))

        snapshot = published.snapshot
        visible_ids = list(published.visible_observation_ids)
        new_receipts: dict[str, RasterSegmentVisibilityReceipt] = {}

        decoded_page_ids = {
            str(int(value)) for value in published.coverage.decoded_pages
        }
        if page_ids is None:
            selected_page_ids = decoded_page_ids
        else:
            selected_page_ids = {
                str(page_id).strip()
                for page_id in page_ids
                if str(page_id).strip()
            }
            if not selected_page_ids:
                raise ValueError("page_ids must contain at least one source page")
            if not selected_page_ids <= decoded_page_ids:
                raise ValueError(OBSERVATION_UNAVAILABLE)

        for page_number in sorted(
            {int(value) for value in selected_page_ids}
        ):
            page_id = str(page_number)
            raster_attempt_key = (published.revision.revision_id, page_id)
            if raster_attempt_key in self._raster_visibility_attempted_pages:
                continue

            image_regions = self._producer.native_page_image_regions(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                page_id=page_id,
            )
            if page_id in pages_with_visible and not image_regions:
                continue

            png_bytes, page_parent = self._producer.render_native_page_png(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                page_id=page_id,
                dpi=float(RASTER_RENDER_DPI),
            )
            image_sha256 = hashlib.sha256(png_bytes).hexdigest()
            segments = detect_axis_aligned_raster_segments(
                png_bytes,
                dpi=RASTER_RENDER_DPI,
            )

            if page_id in pages_with_visible and image_regions:
                segments = tuple(
                    segment
                    for segment in segments
                    if _axis_aligned_geometry_fully_covered_by_rect_union(
                        segment.geometry_pt, image_regions
                    )
                )

            # Visibility publishes each proven source-owned primitive regardless
            # of whether enough neighbouring primitives exist to prove a wall or
            # opening. Object-completeness gates belong downstream. Re-sort using
            # the detector's historical v1 canonical ordering so detector output
            # iteration order cannot affect the frozen raster identity index.
            segments = tuple(
                sorted(
                    segments,
                    key=lambda segment: (
                        str(segment.orientation),
                        tuple(float(value) for value in segment.geometry_pt),
                        tuple(float(value) for value in segment.pixel_geometry),
                    ),
                )
            )

            packets = [
                (index, segment, image_sha256, RASTER_RENDER_DPI,
                 RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION, RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION, None)
                for index, segment in enumerate(segments)
            ]
            if image_regions:
                try:
                    compact_render = self._producer.render_native_page_png(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=snapshot.snapshot_id, page_id=page_id,
                        dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                        include_native_frame=True, images_only=True,
                    )
                except NativePageFrameUnresolved:
                    compact_render = None
                if compact_render is not None:
                    compact_png, compact_parent, compact_frame = compact_render
                if compact_render is not None and compact_parent.observation_id != page_parent.observation_id:
                    raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                # Match the existing G17 source-frame limitation. A page
                # rotation requires its own independently proved transform.
                if compact_render is not None and int(compact_frame.rotation) == 0:
                    registration_scale = self.raster_opening_registration_scale(
                        published.revision.revision_id, page_id,
                    ) or (1.0, 1.0)
                    compact_segments = detect_compact_raster_wall_band_segments(
                        compact_png, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                        registration_scale=registration_scale,
                    )
                    compact_segments = tuple(sorted(compact_segments, key=lambda item: (
                        item.orientation, item.geometry_pt, item.pixel_geometry,
                    )))
                    terminal_segments = detect_terminal_raster_wall_band_segments(
                        compact_png, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                        registration_scale=registration_scale,
                    )
                    full_visibility_hash = None
                    if compact_segments or terminal_segments:
                        import cv2
                        import numpy as np
                        full_png, full_parent = self._producer.render_native_page_png(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=snapshot.snapshot_id, page_id=page_id,
                            dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                        )
                        if full_parent.observation_id != page_parent.observation_id:
                            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                        isolated = cv2.imdecode(np.frombuffer(compact_png, np.uint8), cv2.IMREAD_GRAYSCALE)
                        full = cv2.imdecode(np.frombuffer(full_png, np.uint8), cv2.IMREAD_GRAYSCALE)
                        if isolated is None or full is None:
                            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                        compact_segments = tuple(s for s in compact_segments
                            if compact_band_has_same_visible_paint(s, isolated, full)
                            and not compact_band_already_covered_by_source_line(
                                s, segments, full, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                                source_dpi=RASTER_RENDER_DPI)
                            # Do not let a partial duplicate compete with an
                            # already-visible ordinary raster source at W2.
                            # Do not crop the residual into an invented edge.
                            and not compact_band_has_partial_original_source_coverage(
                                s, segments, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                                source_dpi=RASTER_RENDER_DPI)
                            and not compact_band_crosses_original_source(
                                s, segments, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                                source_dpi=RASTER_RENDER_DPI)
                            and not compact_band_endpoint_on_original_source_interior(
                                s, segments, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                                source_dpi=RASTER_RENDER_DPI))
                        terminal_segments = tuple(s for s in terminal_segments
                            if compact_band_has_same_visible_paint(s, isolated, full))
                        full_visibility_hash = hashlib.sha256(full_png).hexdigest()
                    compact_hash = hashlib.sha256(compact_png).hexdigest()
                    packets.extend(
                        (index, segment, compact_hash, RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                         COMPACT_WALL_BAND_IDENTITY_VERSION, COMPACT_WALL_BAND_DETECTOR_VERSION,
                         full_visibility_hash)
                        for index, segment in enumerate(compact_segments)
                        if _axis_aligned_geometry_fully_covered_by_rect_union(
                            segment.geometry_pt, image_regions,
                        )
                    )
                    packets.extend(
                        (index, segment, compact_hash, RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                         TERMINAL_WALL_BAND_IDENTITY_VERSION, TERMINAL_WALL_BAND_DETECTOR_VERSION,
                         full_visibility_hash)
                        for index, segment in enumerate(terminal_segments)
                        if _axis_aligned_geometry_fully_covered_by_rect_union(
                            segment.geometry_pt, image_regions,
                        )
                    )
            # Both producer-owned detectors have completed. Preserve every
            # historical ordinary index; supplemental lines have their own
            # render/identity namespace and are appended as new observations.
            completed_attempt_keys.add(raster_attempt_key)
            if not packets:
                continue

            segment_specs: list[dict[str, object]] = []
            visible_specs: list[dict[str, object]] = []
            page_receipts: list[
                tuple[str, RasterSegmentVisibilityReceipt]
            ] = []

            for index, segment, render_hash, render_dpi, identity_version, detector_version, visibility_hash in packets:
                segment_id = _raster_segment_observation_id(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    page_id=page_id,
                    partition_id=page_parent.source_partition_id,
                    image_sha256=render_hash,
                    identity_version=identity_version,
                    pixel_geometry=segment.pixel_geometry,
                    geometry=segment.geometry_pt,
                    index=index,
                )
                segment_ref = (
                    f"raster_segment:{render_hash}:"
                    f"{identity_version}:{index}"
                )
                if visibility_hash is not None:
                    segment_ref = (
                        f"raster_segment:{render_hash}:{identity_version}:{visibility_hash}:{index}"
                    )
                segment_specs.append(
                    {
                        "page_id": page_id,
                        "source_partition_id": page_parent.source_partition_id,
                        "observation_kind": RASTER_PDF_SEGMENT,
                        "source_primitive_ref": segment_ref,
                        "origin_kind": RASTER_SEGMENT_ORIGIN_KIND,
                        "parent_observation_ids": (
                            page_parent.observation_id,
                        ),
                        "raw_text": "",
                        "geometry": segment.geometry_pt,
                        "viewport_id": None,
                        "observation_id": segment_id,
                    }
                )

                visible_ref = f"visible:{segment_ref}"
                visible_id = _raster_visible_observation_id(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    page_id=page_id,
                    partition_id=page_parent.source_partition_id,
                    parent_observation_id=segment_id,
                    geometry=segment.geometry_pt,
                )
                visible_specs.append(
                    {
                        "page_id": page_id,
                        "source_partition_id": page_parent.source_partition_id,
                        "observation_kind": RASTER_PDF_VISIBLE_SEGMENT,
                        "source_primitive_ref": visible_ref,
                        "origin_kind": RASTER_VISIBLE_SEGMENT_ORIGIN_KIND,
                        "parent_observation_ids": (segment_id,),
                        "raw_text": "",
                        "geometry": segment.geometry_pt,
                        "viewport_id": None,
                        "observation_id": visible_id,
                    }
                )
                page_receipts.append(
                    (
                        visible_id,
                        RasterSegmentVisibilityReceipt(
                            parent_observation_id=segment_id,
                            page_parent_observation_id=page_parent.observation_id,
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            page_id=page_id,
                            source_partition_id=page_parent.source_partition_id,
                            image_sha256=render_hash,
                            dpi=render_dpi,
                            pixel_geometry=tuple(segment.pixel_geometry),
                            geometry=tuple(segment.geometry_pt),
                            detector_version=detector_version,
                            visibility_render_sha256=visibility_hash,
                        ),
                    )
                )

            snapshot = self._producer.publish_derived_observations(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                base_snapshot_id=snapshot.snapshot_id,
                observations=segment_specs,
            )
            snapshot = self._producer.publish_derived_observations(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                base_snapshot_id=snapshot.snapshot_id,
                observations=visible_specs,
            )
            for visible_id, receipt in page_receipts:
                visible_ids.append(visible_id)
                new_receipts[visible_id] = receipt

        if snapshot.snapshot_id == old_snapshot_id:
            self._raster_visibility_attempted_pages.update(completed_attempt_keys)
            return published

        final_snapshot_id = snapshot.snapshot_id
        for observation_id in published.visible_observation_ids:
            native_parent = self._visibility_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if native_parent is not None:
                self._visibility_receipts[
                    (final_snapshot_id, observation_id)
                ] = native_parent
            raster_receipt = self._raster_visibility_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if raster_receipt is not None:
                self._raster_visibility_receipts[
                    (final_snapshot_id, observation_id)
                ] = raster_receipt

        for observation_id in published.text_observation_ids:
            receipt = self._text_integrity_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if receipt is not None:
                self._text_integrity_receipts[
                    (final_snapshot_id, observation_id)
                ] = receipt

        for observation_id, receipt in new_receipts.items():
            self._raster_visibility_receipts[
                (final_snapshot_id, observation_id)
            ] = receipt
        for observation_id in published.raster_opening_primitive_observation_ids:
            receipt = self._raster_opening_primitive_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if receipt is not None:
                self._raster_opening_primitive_receipts[
                    (final_snapshot_id, observation_id)
                ] = receipt

        updated = PublishedVisibleSourceSnapshot(
            revision=replace(published.revision),
            coverage=replace(published.coverage),
            snapshot=replace(snapshot),
            base_source_snapshot_id=published.base_source_snapshot_id,
            visible_observation_ids=tuple(sorted(set(visible_ids))),
            text_observation_ids=tuple(published.text_observation_ids),
            ocr_tag_observation_ids=tuple(published.ocr_tag_observation_ids),
            raster_opening_primitive_observation_ids=tuple(
                published.raster_opening_primitive_observation_ids
            ),
        )
        self._published_by_revision[updated.revision.revision_id] = updated
        self._raster_visibility_attempted_pages.update(completed_attempt_keys)
        return updated

    def augment_with_raster_opening_primitives(
        self,
        revision_id: str,
        *,
        page_ids: Sequence[str] | None = None,
    ) -> PublishedVisibleSourceSnapshot:
        """Publish source-owned raster primitives without granting opening authority.

        The renderer is producer-owned and images-only. Callers can address pages
        but cannot provide pixels, DPI, geometry, primitive roles, gaps, openings,
        hosts, dimensions, or quantities. Published primitives are intentionally
        isolated from visible_observation_ids so existing G17 paths cannot consume
        them until an explicit authority-promotion step does so.
        """

        published = self._published_by_revision.get(str(revision_id))
        if published is None:
            raise ValueError(OBSERVATION_UNAVAILABLE)

        old_snapshot_id = published.snapshot.snapshot_id
        snapshot = published.snapshot
        primitive_ids = list(
            published.raster_opening_primitive_observation_ids
        )
        new_receipts: dict[
            str, RasterOpeningPrimitiveVisibilityReceipt
        ] = {}

        decoded_page_ids = {
            str(int(value)) for value in published.coverage.decoded_pages
        }
        if page_ids is None:
            selected_page_ids = decoded_page_ids
        else:
            selected_page_ids = {
                str(page_id).strip()
                for page_id in page_ids
                if str(page_id).strip()
            }
            if not selected_page_ids:
                raise ValueError("page_ids must contain at least one source page")
            if not selected_page_ids <= decoded_page_ids:
                raise ValueError(OBSERVATION_UNAVAILABLE)

        for page_number in sorted({int(value) for value in selected_page_ids}):
            page_id = str(page_number)
            attempt_key = (published.revision.revision_id, page_id)
            if attempt_key in self._raster_opening_primitive_attempted_pages:
                continue

            image_regions = self._producer.native_page_image_regions(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                page_id=page_id,
            )
            if not image_regions:
                self._raster_opening_primitive_attempted_pages.add(attempt_key)
                continue

            png_bytes, page_parent, native_frame = self._producer.render_native_page_png(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                page_id=page_id,
                dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                include_native_frame=True,
                images_only=True,
            )
            self._raster_opening_primitive_attempted_pages.add(attempt_key)
            if int(getattr(native_frame, "rotation", 0) or 0) != 0:
                continue

            registration_scale = self.raster_opening_registration_scale(
                published.revision.revision_id,
                page_id,
            )
            primitives = detect_raster_opening_source_primitives(
                png_bytes,
                dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                registration_scale=(
                    registration_scale
                    if registration_scale is not None
                    else (1.0, 1.0)
                ),
            )
            if not primitives:
                continue
            render_sha256 = hashlib.sha256(png_bytes).hexdigest()

            parent_specs: list[dict[str, object]] = []
            visible_specs: list[dict[str, object]] = []
            page_receipts: list[
                tuple[str, RasterOpeningPrimitiveVisibilityReceipt]
            ] = []
            for index, primitive in enumerate(primitives):
                parent_id = _raster_opening_primitive_observation_id(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    page_id=page_id,
                    partition_id=page_parent.source_partition_id,
                    primitive=primitive,
                )
                parent_ref = (
                    f"raster_opening_primitive:{render_sha256}:"
                    f"{RASTER_OPENING_PRIMITIVE_IDENTITY_VERSION}:"
                    f"{primitive.primitive_kind}:{index}"
                )
                parent_specs.append(
                    {
                        "page_id": page_id,
                        "source_partition_id": page_parent.source_partition_id,
                        "observation_kind": RASTER_OPENING_PRIMITIVE_SEGMENT,
                        "source_primitive_ref": parent_ref,
                        "origin_kind": RASTER_OPENING_PRIMITIVE_ORIGIN_KIND,
                        "parent_observation_ids": (page_parent.observation_id,),
                        "raw_text": "",
                        "geometry": primitive.geometry_pt,
                        "viewport_id": None,
                        "observation_id": parent_id,
                    }
                )
                visible_id = _raster_opening_visible_primitive_id(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    page_id=page_id,
                    partition_id=page_parent.source_partition_id,
                    parent_observation_id=parent_id,
                    primitive=primitive,
                )
                visible_specs.append(
                    {
                        "page_id": page_id,
                        "source_partition_id": page_parent.source_partition_id,
                        "observation_kind": primitive.primitive_kind,
                        "source_primitive_ref": f"visible:{parent_ref}",
                        "origin_kind": RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND,
                        "parent_observation_ids": (parent_id,),
                        "raw_text": "",
                        "geometry": primitive.geometry_pt,
                        "viewport_id": None,
                        "observation_id": visible_id,
                    }
                )
                page_receipts.append(
                    (
                        visible_id,
                        RasterOpeningPrimitiveVisibilityReceipt(
                            parent_observation_id=parent_id,
                            page_parent_observation_id=page_parent.observation_id,
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            page_id=page_id,
                            source_partition_id=page_parent.source_partition_id,
                            render_sha256=render_sha256,
                            primitive_kind=primitive.primitive_kind,
                            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                            pixel_geometry=tuple(primitive.pixel_geometry),
                            geometry=tuple(primitive.geometry_pt),
                        ),
                    )
                )

            snapshot = self._producer.publish_derived_observations(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                base_snapshot_id=snapshot.snapshot_id,
                observations=parent_specs,
            )
            snapshot = self._producer.publish_derived_observations(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                base_snapshot_id=snapshot.snapshot_id,
                observations=visible_specs,
            )
            for visible_id, receipt in page_receipts:
                primitive_ids.append(visible_id)
                new_receipts[visible_id] = receipt

        if snapshot.snapshot_id == old_snapshot_id:
            return published

        final_snapshot_id = snapshot.snapshot_id
        for observation_id in published.visible_observation_ids:
            native_parent = self._visibility_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if native_parent is not None:
                self._visibility_receipts[(final_snapshot_id, observation_id)] = (
                    native_parent
                )
            raster_receipt = self._raster_visibility_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if raster_receipt is not None:
                self._raster_visibility_receipts[
                    (final_snapshot_id, observation_id)
                ] = raster_receipt

        for observation_id in published.text_observation_ids:
            text_receipt = self._text_integrity_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if text_receipt is not None:
                self._text_integrity_receipts[
                    (final_snapshot_id, observation_id)
                ] = text_receipt

        for observation_id in published.raster_opening_primitive_observation_ids:
            receipt = self._raster_opening_primitive_receipts.get(
                (old_snapshot_id, observation_id)
            )
            if receipt is not None:
                self._raster_opening_primitive_receipts[
                    (final_snapshot_id, observation_id)
                ] = receipt
        for observation_id, receipt in new_receipts.items():
            self._raster_opening_primitive_receipts[
                (final_snapshot_id, observation_id)
            ] = receipt

        updated = PublishedVisibleSourceSnapshot(
            revision=replace(published.revision),
            coverage=replace(published.coverage),
            snapshot=replace(snapshot),
            base_source_snapshot_id=published.base_source_snapshot_id,
            visible_observation_ids=tuple(published.visible_observation_ids),
            text_observation_ids=tuple(published.text_observation_ids),
            ocr_tag_observation_ids=tuple(published.ocr_tag_observation_ids),
            raster_opening_primitive_observation_ids=tuple(
                sorted(set(primitive_ids))
            ),
        )
        self._published_by_revision[updated.revision.revision_id] = updated
        return updated


class SourceVisibilityAuthority:
    """Read-only authority for producer-receipted visible segment observations.

    Obtain instances from ``SourceVisibilityProducer.authority()``. Direct
    construction with caller-provided receipt maps is rejected.
    """

    def __init__(
        self,
        source_authority: SourceObservationAuthority,
        visibility_receipts: Mapping[tuple[str, str], str],
        raster_visibility_receipts: Mapping[
            tuple[str, str], RasterSegmentVisibilityReceipt
        ],
        raster_opening_primitive_receipts: Mapping[
            tuple[str, str], RasterOpeningPrimitiveVisibilityReceipt
        ],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _VISIBILITY_AUTHORITY_SEAL:
            raise TypeError(
                "SourceVisibilityAuthority must be obtained from "
                "SourceVisibilityProducer.authority()"
            )
        self._source_authority = source_authority
        self._visibility_receipts = visibility_receipts
        self._raster_visibility_receipts = raster_visibility_receipts
        self._raster_opening_primitive_receipts = (
            raster_opening_primitive_receipts
        )

    def _blocked(self, reason: str) -> SourceObservationAuthorityResult:
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(reason,),
        )

    def _conflict(self, reason: str) -> SourceObservationAuthorityResult:
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.CONFLICT,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(reason,),
        )

    def resolve_raster_opening_primitive(
        self,
        selector: ObservationSelector,
    ) -> SourceObservationAuthorityResult:
        """Authenticate one isolated raster-opening source primitive.

        This reader proves source ownership only. A successful result is not a
        physical opening, host, dimension, or quantity proposition.
        """

        receipt = self._raster_opening_primitive_receipts.get(
            (selector.snapshot_id, selector.observation_id)
        )
        if receipt is None:
            return self._blocked(VISIBILITY_RECEIPT_UNAVAILABLE)

        result = self._source_authority.resolve(selector)
        observation = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
        ):
            return result
        if (
            observation.observation_kind not in RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS
            or observation.observation_kind != receipt.primitive_kind
            or observation.origin_kind
            != RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND
            or observation.viewport_id is not None
            or observation.derivation_parent_ids
            != (receipt.parent_observation_id,)
            or observation.document_id != receipt.document_id
            or observation.revision_id != receipt.revision_id
            or observation.source_sha256 != receipt.source_sha256
            or observation.page_id != receipt.page_id
            or observation.source_partition_id != receipt.source_partition_id
            or observation.raw_text
            or tuple(observation.geometry) != tuple(receipt.geometry)
        ):
            return self._conflict(PRODUCER_INTEGRITY_FAILURE)

        parent_result = self._source_authority.resolve(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=receipt.parent_observation_id,
            )
        )
        parent = parent_result.observation
        if (
            parent_result.status is not EvidenceResolutionStatus.CORROBORATED
            or parent is None
            or parent.observation_kind != RASTER_OPENING_PRIMITIVE_SEGMENT
            or parent.origin_kind != RASTER_OPENING_PRIMITIVE_ORIGIN_KIND
            or parent.derivation_parent_ids
            != (receipt.page_parent_observation_id,)
            or parent.document_id != observation.document_id
            or parent.revision_id != observation.revision_id
            or parent.source_sha256 != observation.source_sha256
            or parent.page_id != observation.page_id
            or parent.source_partition_id != observation.source_partition_id
            or parent.raw_text
            or parent.geometry != observation.geometry
            or observation.source_primitive_ref
            != f"visible:{parent.source_primitive_ref}"
        ):
            return self._conflict(VISIBILITY_PARENT_MISMATCH)

        page_result = self._source_authority.resolve(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=receipt.page_parent_observation_id,
            )
        )
        page_parent = page_result.observation
        if (
            page_result.status is not EvidenceResolutionStatus.CORROBORATED
            or page_parent is None
            or page_parent.observation_kind != "native_pdf_page"
            or page_parent.origin_kind != "native"
            or page_parent.derivation_parent_ids
            or page_parent.document_id != observation.document_id
            or page_parent.revision_id != observation.revision_id
            or page_parent.source_sha256 != observation.source_sha256
            or page_parent.page_id != observation.page_id
            or page_parent.source_partition_id != observation.source_partition_id
        ):
            return self._conflict(VISIBILITY_PARENT_MISMATCH)
        return result

    def visible_observation_ids_for_snapshot(self, snapshot_id: str) -> frozenset[str]:
        """Return producer-receipted visible ids for one immutable snapshot.

        This is an addressing index only.  Consumers must still call
        ``resolve_visible`` for every returned id before using its observation.
        """
        snapshot_id = str(snapshot_id)
        ids = {
            observation_id
            for (receipt_snapshot_id, observation_id) in self._visibility_receipts
            if receipt_snapshot_id == snapshot_id
        }
        ids.update(
            observation_id
            for (receipt_snapshot_id, observation_id) in self._raster_visibility_receipts
            if receipt_snapshot_id == snapshot_id
        )
        return frozenset(ids)

    def raster_opening_primitive_observation_ids_for_snapshot(
        self, snapshot_id: str
    ) -> frozenset[str]:
        """Address isolated raster observations without granting authority.

        Include the sealed snapshot inventory as well as the receipt index so
        a missing receipt cannot hide an opening from a completeness audit.
        Every returned ID must still pass ``resolve_visible``.
        """
        snapshot_id = str(snapshot_id)
        ids = {
            observation_id
            for receipt_snapshot_id, observation_id
            in self._raster_opening_primitive_receipts
            if receipt_snapshot_id == snapshot_id
        }
        store = self._source_authority._store
        snapshot = store.snapshots.get(snapshot_id)
        if snapshot is not None:
            for observation_id in snapshot.observation_ids:
                record = store.observations.get((snapshot_id, observation_id))
                if (
                    record is None
                    or record.origin_kind
                    == RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND
                ):
                    ids.add(observation_id)
        return frozenset(ids)

    def visible_observation_ids_for_page(
        self,
        snapshot_id: str,
        page_id: str,
    ) -> frozenset[str]:
        """Return receipt-backed visible ids addressable to one source page.

        Addressing is not authority. Every returned id must still pass
        resolve_visible() before its observation can be used.
        """
        snapshot_id = str(snapshot_id)
        page_id = str(page_id)
        store = self._source_authority._store
        snapshot = store.snapshots.get(snapshot_id)
        if snapshot is None:
            return frozenset()

        ids: set[str] = set()
        for receipt_snapshot_id, observation_id in self._visibility_receipts:
            if receipt_snapshot_id != snapshot_id:
                continue
            record = store.observations.get((snapshot_id, observation_id))
            if (
                record is not None
                and str(record.page_id) == page_id
                and store.snapshot_contains_observation(snapshot, observation_id)
            ):
                ids.add(str(observation_id))
        for (
            receipt_snapshot_id,
            observation_id,
        ), receipt in self._raster_visibility_receipts.items():
            if (
                receipt_snapshot_id == snapshot_id
                and str(receipt.page_id) == page_id
            ):
                record = store.observations.get((snapshot_id, observation_id))
                if (
                    record is not None
                    and str(record.page_id) == page_id
                    and store.snapshot_contains_observation(
                        snapshot, observation_id
                    )
                ):
                    ids.add(str(observation_id))
        return frozenset(ids)

    def authenticated_visible_observations(
        self, published: "PublishedVisibleSourceSnapshot"
    ) -> tuple[tuple[str, object], ...]:
        """Bulk-authenticate the producer-owned visible universe for one snapshot.

        This is semantically equivalent to resolving every visible id separately,
        but validates shared revision/source/snapshot integrity once and reuses
        the producer-owned identity-bound verified-record cache. Cache misses or
        replaced/tampered records fall back to scalar source authority validation.
        Receipt and full parent-lineage predicates remain unchanged.
        """
        if type(published) is not PublishedVisibleSourceSnapshot:
            raise TypeError("published must be PublishedVisibleSourceSnapshot")

        store = self._source_authority._store
        document_id = str(published.revision.document_id)
        revision_id = str(published.revision.revision_id)
        source_sha256 = str(published.revision.source_sha256)
        snapshot_id = str(published.snapshot.snapshot_id)

        current = store.current_revision_by_document.get(document_id)
        revision = store.revisions.get(revision_id)
        source_bytes = store.source_bytes_by_revision.get(revision_id)
        snapshot = store.snapshots.get(snapshot_id)
        if (
            current != revision_id
            or revision is None
            or source_bytes is None
            or revision.source_sha256 != source_sha256
            or not store.source_bytes_match_revision(
                revision_id, source_bytes, source_sha256
            )
            or snapshot is None
            or snapshot.document_id != document_id
            or snapshot.revision_id != revision_id
            or snapshot.source_sha256 != source_sha256
        ):
            raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)

        def _record(observation_id: str):
            observation_id = str(observation_id)
            key = (snapshot_id, observation_id)
            record = store.observations.get(key)
            if record is None or not store.snapshot_contains_observation(
                snapshot, observation_id
            ):
                raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            expected = store.record_fingerprints.get(key)
            cached = store.verified_resolution_cache.get(key)
            if not (
                expected is not None
                and cached is not None
                and cached[0] is revision
                and cached[1] is snapshot
                and cached[2] is record
                and cached[3] == expected
                and all(
                    (snapshot_id, parent_id) in store.observations
                    for parent_id in record.derivation_parent_ids
                )
            ):
                resolved = self._source_authority.resolve(
                    ObservationSelector(
                        document_id=document_id,
                        revision_id=revision_id,
                        source_sha256=source_sha256,
                        snapshot_id=snapshot_id,
                        observation_id=observation_id,
                    )
                )
                if (
                    resolved.status is not EvidenceResolutionStatus.CORROBORATED
                    or resolved.observation is None
                ):
                    raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                record = store.observations.get(key)
                if record is None:
                    raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
            return record

        rows: list[tuple[str, object]] = []
        for observation_id in published.visible_observation_ids:
            observation_id = str(observation_id)
            expected_parent = self._visibility_receipts.get(
                (snapshot_id, observation_id)
            )
            raster_receipt = self._raster_visibility_receipts.get(
                (snapshot_id, observation_id)
            )
            if expected_parent is None and raster_receipt is None:
                raise RuntimeError(VISIBILITY_RECEIPT_UNAVAILABLE)

            observation = _record(observation_id)
            if expected_parent is not None:
                if (
                    observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
                    or observation.origin_kind not in (
                        VISIBLE_SEGMENT_ORIGIN_KIND,
                        RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND,
                    )
                    or observation.viewport_id is not None
                    or observation.derivation_parent_ids != (expected_parent,)
                ):
                    raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                parent = _record(expected_parent)
                if (
                    parent.observation_kind != "native_pdf_segment"
                    or parent.origin_kind != "native"
                    or parent.document_id != observation.document_id
                    or parent.revision_id != observation.revision_id
                    or parent.source_sha256 != observation.source_sha256
                    or parent.page_id != observation.page_id
                    or parent.source_partition_id != observation.source_partition_id
                    or parent.geometry != observation.geometry
                    or observation.source_primitive_ref
                    != f"visible:{parent.source_primitive_ref}"
                ):
                    raise RuntimeError(VISIBILITY_PARENT_MISMATCH)
            else:
                assert raster_receipt is not None
                if (
                    observation.observation_kind != RASTER_PDF_VISIBLE_SEGMENT
                    or observation.origin_kind != RASTER_VISIBLE_SEGMENT_ORIGIN_KIND
                    or observation.viewport_id is not None
                    or observation.derivation_parent_ids
                    != (raster_receipt.parent_observation_id,)
                    or observation.document_id != raster_receipt.document_id
                    or observation.revision_id != raster_receipt.revision_id
                    or observation.source_sha256 != raster_receipt.source_sha256
                    or observation.page_id != raster_receipt.page_id
                    or observation.source_partition_id
                    != raster_receipt.source_partition_id
                    or tuple(observation.geometry) != tuple(raster_receipt.geometry)
                ):
                    raise RuntimeError(PRODUCER_INTEGRITY_FAILURE)
                parent = _record(raster_receipt.parent_observation_id)
                if (
                    parent.observation_kind != RASTER_PDF_SEGMENT
                    or not _raster_segment_receipt_matches_parent(raster_receipt, parent)
                    or parent.origin_kind != RASTER_SEGMENT_ORIGIN_KIND
                    or parent.derivation_parent_ids
                    != (raster_receipt.page_parent_observation_id,)
                    or parent.document_id != observation.document_id
                    or parent.revision_id != observation.revision_id
                    or parent.source_sha256 != observation.source_sha256
                    or parent.page_id != observation.page_id
                    or parent.source_partition_id != observation.source_partition_id
                    or parent.geometry != observation.geometry
                    or observation.source_primitive_ref
                    != f"visible:{parent.source_primitive_ref}"
                ):
                    raise RuntimeError(VISIBILITY_PARENT_MISMATCH)
                page_parent = _record(raster_receipt.page_parent_observation_id)
                if (
                    page_parent.observation_kind != "native_pdf_page"
                    or page_parent.origin_kind != "native"
                    or page_parent.derivation_parent_ids
                    or page_parent.document_id != observation.document_id
                    or page_parent.revision_id != observation.revision_id
                    or page_parent.source_sha256 != observation.source_sha256
                    or page_parent.page_id != observation.page_id
                    or page_parent.source_partition_id != observation.source_partition_id
                ):
                    raise RuntimeError(VISIBILITY_PARENT_MISMATCH)

            rows.append((observation_id, replace(observation)))
        return tuple(rows)

    def resolve_visible(self, selector: ObservationSelector) -> SourceObservationAuthorityResult:
        expected_parent = self._visibility_receipts.get(
            (selector.snapshot_id, selector.observation_id)
        )
        raster_receipt = self._raster_visibility_receipts.get(
            (selector.snapshot_id, selector.observation_id)
        )
        if expected_parent is None and raster_receipt is None:
            return self._blocked(VISIBILITY_RECEIPT_UNAVAILABLE)

        result = self._source_authority.resolve(selector)
        observation = result.observation
        if observation is None or result.status != EvidenceResolutionStatus.CORROBORATED:
            return result

        if expected_parent is not None:
            if (
                observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
                or observation.origin_kind not in (
                    VISIBLE_SEGMENT_ORIGIN_KIND,
                    RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND,
                )
                or observation.viewport_id is not None
                or observation.derivation_parent_ids != (expected_parent,)
            ):
                return self._conflict(PRODUCER_INTEGRITY_FAILURE)

            parent_result = self._source_authority.resolve(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=expected_parent,
                )
            )
            parent = parent_result.observation
            if parent is None or parent_result.status != EvidenceResolutionStatus.CORROBORATED:
                return self._blocked(OBSERVATION_UNAVAILABLE)
            if (
                parent.observation_kind != "native_pdf_segment"
                or parent.origin_kind != "native"
                or parent.document_id != observation.document_id
                or parent.revision_id != observation.revision_id
                or parent.source_sha256 != observation.source_sha256
                or parent.page_id != observation.page_id
                or parent.source_partition_id != observation.source_partition_id
                or parent.geometry != observation.geometry
                or observation.source_primitive_ref
                != f"visible:{parent.source_primitive_ref}"
            ):
                return self._conflict(VISIBILITY_PARENT_MISMATCH)
        else:
            assert raster_receipt is not None
            if (
                observation.observation_kind != RASTER_PDF_VISIBLE_SEGMENT
                or observation.origin_kind != RASTER_VISIBLE_SEGMENT_ORIGIN_KIND
                or observation.viewport_id is not None
                or observation.derivation_parent_ids
                != (raster_receipt.parent_observation_id,)
                or observation.document_id != raster_receipt.document_id
                or observation.revision_id != raster_receipt.revision_id
                or observation.source_sha256 != raster_receipt.source_sha256
                or observation.page_id != raster_receipt.page_id
                or observation.source_partition_id
                != raster_receipt.source_partition_id
                or tuple(observation.geometry) != tuple(raster_receipt.geometry)
            ):
                return self._conflict(PRODUCER_INTEGRITY_FAILURE)

            parent_result = self._source_authority.resolve(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=raster_receipt.parent_observation_id,
                )
            )
            parent = parent_result.observation
            if parent is None or parent_result.status != EvidenceResolutionStatus.CORROBORATED:
                return self._blocked(OBSERVATION_UNAVAILABLE)
            if (
                parent.observation_kind != RASTER_PDF_SEGMENT
                or not _raster_segment_receipt_matches_parent(raster_receipt, parent)
                or parent.origin_kind != RASTER_SEGMENT_ORIGIN_KIND
                or parent.derivation_parent_ids
                != (raster_receipt.page_parent_observation_id,)
                or parent.document_id != observation.document_id
                or parent.revision_id != observation.revision_id
                or parent.source_sha256 != observation.source_sha256
                or parent.page_id != observation.page_id
                or parent.source_partition_id != observation.source_partition_id
                or parent.geometry != observation.geometry
                or observation.source_primitive_ref
                != f"visible:{parent.source_primitive_ref}"
            ):
                return self._conflict(VISIBILITY_PARENT_MISMATCH)

            page_result = self._source_authority.resolve(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=raster_receipt.page_parent_observation_id,
                )
            )
            page_parent = page_result.observation
            if page_parent is None or page_result.status != EvidenceResolutionStatus.CORROBORATED:
                return self._blocked(OBSERVATION_UNAVAILABLE)
            if (
                page_parent.observation_kind != "native_pdf_page"
                or page_parent.origin_kind != "native"
                or page_parent.derivation_parent_ids
                or page_parent.document_id != observation.document_id
                or page_parent.revision_id != observation.revision_id
                or page_parent.source_sha256 != observation.source_sha256
                or page_parent.page_id != observation.page_id
                or page_parent.source_partition_id != observation.source_partition_id
            ):
                return self._conflict(VISIBILITY_PARENT_MISMATCH)

        return replace(
            result,
            proposition=VISIBLE_SOURCE_OBSERVATION_EXISTS,
            reason_codes=("producer_owned_visible_source_observation_resolved",),
        )


__all__ = [
    "NATIVE_PDF_VISIBLE_SEGMENT",
    "RASTER_PDF_SEGMENT",
    "RASTER_PDF_VISIBLE_SEGMENT",
    "RASTER_RENDER_DPI",
    "RASTER_SEGMENT_ORIGIN_KIND",
    "RASTER_VISIBLE_SEGMENT_ORIGIN_KIND",
    "RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND",
    "SOURCE_VISIBILITY_SCHEMA_VERSION",
    "VISIBLE_SEGMENT_ORIGIN_KIND",
    "VISIBLE_SOURCE_OBSERVATION_EXISTS",
    "VISIBILITY_ACTIVE_CLIP_UNRESOLVED",
    "VISIBILITY_CLIP_ASSOCIATION_UNKNOWN",
    "VISIBILITY_CLIP_STATE_INCONSISTENT",
    "VISIBILITY_GEOMETRY_INVALID",
    "VISIBILITY_PARENT_MISMATCH",
    "VISIBILITY_PROVEN_NO_ACTIVE_CLIP",
    "VISIBILITY_PROVEN_RECTANGULAR_CLIP",
    "VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT",
    "VISIBILITY_RECEIPT_UNAVAILABLE",
    "NativeSegmentVisibilityDecision",
    "RasterSegmentVisibilityReceipt",
    "PublishedVisibleSourceSnapshot",
    "SourceVisibilityAuthority",
    "SourceVisibilityProducer",
    "classify_native_segment_visibility",
]
