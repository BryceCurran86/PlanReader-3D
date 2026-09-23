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

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_raster_visible_segment_detector import (
    RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION,
    detect_axis_aligned_raster_segments,
)
from pb_pdf_text_integrity_authority import (
    PdfTextIntegrityAuthority,
    PdfTextIntegrityReceipt,
    _PDF_TEXT_AUTHORITY_SEAL,
    build_pdf_text_integrity_receipt,
    classify_native_word_integrity,
)
from pb_source_observation_authority import (
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
    SourceRevisionRecord,
)
from pb_vector_geometry_v130 import extract_native_page


SOURCE_VISIBILITY_SCHEMA_VERSION = "1.2.0"
NATIVE_PDF_VISIBLE_SEGMENT = "native_pdf_visible_segment"
RASTER_PDF_SEGMENT = "raster_pdf_segment"
RASTER_PDF_VISIBLE_SEGMENT = "raster_pdf_visible_segment"
VISIBLE_SEGMENT_ORIGIN_KIND = "producer_visibility_no_active_clip"
RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND = (
    "producer_visibility_exact_rectangular_clip"
)
RASTER_SEGMENT_ORIGIN_KIND = "producer_raster_page_render_segment"
RASTER_VISIBLE_SEGMENT_ORIGIN_KIND = "producer_raster_visibility"
VISIBLE_SOURCE_OBSERVATION_EXISTS = "visible_source_observation_exists"
RASTER_RENDER_DPI = 144

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


@dataclass(frozen=True)
class PublishedVisibleSourceSnapshot:
    revision: SourceRevisionRecord
    coverage: SourceDecodeCoverageRecord
    snapshot: ProducerSnapshotRecord
    base_source_snapshot_id: str
    visible_observation_ids: tuple[str, ...]
    text_observation_ids: tuple[str, ...] = ()
    ocr_tag_observation_ids: tuple[str, ...] = ()
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


def _exact_clip_rect(
    segment: Mapping[str, object],
) -> Optional[tuple[float, float, float, float]]:
    value = segment.get("clip_exact_rect")
    if value is None:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in (x0, y0, x1, y1)):
        return None
    if x1 < x0 or y1 < y0:
        return None
    return (x0, y0, x1, y1)


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
                reason_codes=(VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,),
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


def _raster_segment_observation_id(
    *,
    document_id: str,
    revision_id: str,
    page_id: str,
    partition_id: str,
    image_sha256: str,
    detector_version: str,
    pixel_geometry: Sequence[float],
    geometry: Sequence[float],
    index: int,
) -> str:
    payload = {
        "document_id": document_id,
        "revision_id": revision_id,
        "page_id": page_id,
        "partition_id": partition_id,
        "kind": RASTER_PDF_SEGMENT,
        "image_sha256": image_sha256,
        "detector_version": detector_version,
        "pixel_geometry": tuple(float(v) for v in pixel_geometry),
        "geometry": tuple(float(v) for v in geometry),
        "index": int(index),
    }
    return stable_contract_id("source_observation", payload, digest_chars=32)


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
        self._text_integrity_receipts: dict[
            tuple[str, str], PdfTextIntegrityReceipt
        ] = {}
        self._published_by_revision: dict[str, PublishedVisibleSourceSnapshot] = {}

    def authority(self) -> "SourceVisibilityAuthority":
        return SourceVisibilityAuthority(
            self._producer.authority(),
            self._visibility_receipts,
            self._raster_visibility_receipts,
            _seal=_VISIBILITY_AUTHORITY_SEAL,
        )

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
            _seal=_OPENING_DIMENSION_AUTHORITY_SEAL,
        )

    def ingest_native_pdf_bytes(
        self,
        *,
        document_id: str,
        source_bytes: bytes | bytearray | memoryview,
        source_locator: str,
    ) -> PublishedVisibleSourceSnapshot:
        immutable_bytes = bytes(source_bytes)
        base: PublishedSourceSnapshot = self._producer.ingest_native_pdf_bytes(
            document_id=document_id,
            source_bytes=immutable_bytes,
            source_locator=source_locator,
        )
        cached = self._published_by_revision.get(base.revision.revision_id)
        if cached is not None:
            return cached

        snapshot = base.snapshot
        visible_ids: list[str] = []
        visible_specs: list[dict[str, object]] = []
        text_receipts: list[tuple[str, PdfTextIntegrityReceipt]] = []
        pdf = fitz.open(stream=immutable_bytes, filetype="pdf")
        try:
            for page_index in range(int(pdf.page_count)):
                page_number = page_index + 1
                page_id = str(page_number)
                partition_id = f"page:{page_number}"
                page = pdf.load_page(page_index)
                native = extract_native_page(page)
                for word in native.get("words") or ():
                    raw_text = str(word.get("text") or "")
                    geometry = tuple(float(value) for value in (word.get("bbox") or ()))
                    primitive_ref = f"word:{word.get('id')}"
                    parent_id = _native_word_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=primitive_ref,
                        raw_text=raw_text,
                        geometry=geometry,
                    )
                    decision = classify_native_word_integrity(page, word)
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
                                geometry=geometry,
                                decision=decision,
                            ),
                        )
                    )
                for segment in native.get("segments") or ():
                    decision = classify_native_segment_visibility(segment)
                    if not decision.visible:
                        continue
                    raw_segment_id = str(segment.get("id") or "").strip()
                    if not raw_segment_id:
                        continue
                    parent_ref = f"segment:{raw_segment_id}"
                    parent_id = _native_parent_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=parent_ref,
                        geometry=decision.geometry,
                    )
                    visible_ref = f"visible:{parent_ref}"
                    origin_kind = (
                        RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND
                        if VISIBILITY_PROVEN_RECTANGULAR_CLIP in decision.reason_codes
                        else VISIBLE_SEGMENT_ORIGIN_KIND
                    )
                    visible_id = _visible_observation_id(
                        document_id=base.revision.document_id,
                        revision_id=base.revision.revision_id,
                        page_id=page_id,
                        partition_id=partition_id,
                        primitive_ref=visible_ref,
                        parent_observation_id=parent_id,
                        geometry=decision.geometry,
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
                            "geometry": decision.geometry,
                            "viewport_id": None,
                            "observation_id": visible_id,
                        }
                    )
                    visible_ids.append(visible_id)
        finally:
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
                def _inside_image_region(segment) -> bool:
                    x0, y0, x1, y1 = segment.geometry_pt
                    midpoint_x = (x0 + x1) / 2.0
                    midpoint_y = (y0 + y1) / 2.0
                    for rx0, ry0, rx1, ry1 in image_regions:
                        if (
                            rx0 <= midpoint_x <= rx1
                            and ry0 <= midpoint_y <= ry1
                        ):
                            return True
                    return False

                segments = tuple(
                    segment for segment in segments if _inside_image_region(segment)
                )
            if len(segments) < 6:
                continue

            segment_specs: list[dict[str, object]] = []
            visible_specs: list[dict[str, object]] = []
            page_receipts: list[
                tuple[str, RasterSegmentVisibilityReceipt]
            ] = []

            for index, segment in enumerate(segments):
                segment_id = _raster_segment_observation_id(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    page_id=page_id,
                    partition_id=page_parent.source_partition_id,
                    image_sha256=image_sha256,
                    detector_version=RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION,
                    pixel_geometry=segment.pixel_geometry,
                    geometry=segment.geometry_pt,
                    index=index,
                )
                segment_ref = (
                    f"raster_segment:{image_sha256}:"
                    f"{RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION}:{index}"
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
                            image_sha256=image_sha256,
                            dpi=RASTER_RENDER_DPI,
                            pixel_geometry=tuple(segment.pixel_geometry),
                            geometry=tuple(segment.geometry_pt),
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

        updated = PublishedVisibleSourceSnapshot(
            revision=replace(published.revision),
            coverage=replace(published.coverage),
            snapshot=replace(snapshot),
            base_source_snapshot_id=published.base_source_snapshot_id,
            visible_observation_ids=tuple(sorted(set(visible_ids))),
            text_observation_ids=tuple(published.text_observation_ids),
            ocr_tag_observation_ids=tuple(published.ocr_tag_observation_ids),
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
