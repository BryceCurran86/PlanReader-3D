"""G17 phase-1 producer-owned source observation and immutable lineage boundary.

The strongest positive proposition here is ``SOURCE_OBSERVATION_EXISTS``.
Physical-opening existence, identity, semantic enumeration completeness,
decision-complete scope, dimensions, host binding, physical voids and net wall
area remain unavailable.  The in-process producer/query split prevents ordinary
consumer self-certification structurally; it is not a security boundary against
equal-privilege Python code.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Any, Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    canonical_contract_json,
    stable_contract_id,
)
from pb_vector_geometry_v130 import extract_native_page


SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION = "1.0.0"
SOURCE_OBSERVATION_EXISTS = "source_observation_exists"
PHYSICAL_OPENING_EXISTENCE_UNRESOLVED = "physical_opening_existence_unresolved"
SOURCE_UNAVAILABLE = "source_unavailable"
OBSERVATION_UNAVAILABLE = "observation_unavailable"
STALE_REVISION = "stale_revision"
SOURCE_HASH_MISMATCH = "source_hash_mismatch"
SNAPSHOT_MISMATCH = "snapshot_mismatch"
LINEAGE_UNAVAILABLE = "lineage_unavailable"
PRODUCER_INTEGRITY_FAILURE = "producer_integrity_failure"


class ProducerIntegrityError(RuntimeError):
    """Producer-owned records violate an immutable identity/integrity rule."""


def _nonempty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _finite_tuple(values: Sequence[float]) -> tuple[float, ...]:
    result = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("geometry values must be finite")
    return result


def _content_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_contract_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRevisionRecord:
    document_id: str
    revision_id: str
    source_sha256: str
    source_locator: str
    partition_ids: tuple[str, ...]
    producer_method: str
    producer_version: str
    producer_generation: int
    supersedes_revision_id: Optional[str] = None
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceDecodeCoverageRecord:
    document_id: str
    revision_id: str
    total_pages: int
    decoded_pages: tuple[int, ...]
    failed_pages: tuple[int, ...]
    state: str


@dataclass(frozen=True)
class ProducerSnapshotRecord:
    snapshot_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    observation_ids: tuple[str, ...]
    producer_method: str
    producer_version: str
    producer_generation: int
    parent_snapshot_id: Optional[str] = None
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceObservationRecord:
    observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    source_partition_id: str
    page_id: str
    viewport_id: Optional[str]
    observation_kind: str
    source_primitive_ref: str
    raw_text: str
    geometry: tuple[float, ...]
    origin_kind: str
    derivation_parent_ids: tuple[str, ...]
    producer_method: str
    producer_version: str
    producer_generation: int
    snapshot_id: str
    observation_payload_sha256: str
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.RAW
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class ObservationSelector:
    """Consumer selector only; never an authoritative observation body."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    observation_id: str


@dataclass(frozen=True)
class SourceObservationAuthorityResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    physical_opening_existence: str
    reason_codes: tuple[str, ...]
    source_revision: Optional[SourceRevisionRecord] = None
    snapshot: Optional[ProducerSnapshotRecord] = None
    observation: Optional[SourceObservationRecord] = None
    semantic_enumeration_complete: Optional[bool] = None
    decision_scope_complete: Optional[bool] = None


@dataclass(frozen=True)
class PublishedSourceSnapshot:
    revision: SourceRevisionRecord
    coverage: SourceDecodeCoverageRecord
    snapshot: ProducerSnapshotRecord


class _SourceObservationStore:
    def __init__(self) -> None:
        self.generation = 0
        self.revisions: dict[str, SourceRevisionRecord] = {}
        self.current_revision_by_document: dict[str, str] = {}
        self.source_bytes_by_revision: dict[str, bytes] = {}
        self.coverage_by_revision: dict[str, SourceDecodeCoverageRecord] = {}
        self.coverage_by_snapshot: dict[str, SourceDecodeCoverageRecord] = {}
        self.snapshots: dict[str, ProducerSnapshotRecord] = {}
        self.source_snapshot_by_revision: dict[str, str] = {}
        self.source_snapshot_by_revision_scope: dict[
            tuple[str, tuple[int, ...]], str
        ] = {}
        self.observations: dict[tuple[str, str], SourceObservationRecord] = {}
        self.record_fingerprints: dict[tuple[str, str], str] = {}

    def next_generation(self) -> int:
        self.generation += 1
        return self.generation


def _record_payload(record: SourceObservationRecord) -> dict[str, object]:
    return {
        "observation_id": record.observation_id,
        "document_id": record.document_id,
        "revision_id": record.revision_id,
        "source_sha256": record.source_sha256,
        "source_partition_id": record.source_partition_id,
        "page_id": record.page_id,
        "viewport_id": record.viewport_id,
        "observation_kind": record.observation_kind,
        "source_primitive_ref": record.source_primitive_ref,
        "raw_text": record.raw_text,
        "geometry": record.geometry,
        "origin_kind": record.origin_kind,
        "derivation_parent_ids": record.derivation_parent_ids,
        "producer_method": record.producer_method,
        "producer_version": record.producer_version,
    }


class SourceObservationProducer:
    """Trusted writer. Ordinary consumers should receive only ``authority()``."""

    def __init__(self, *, producer_method: str, producer_version: str) -> None:
        self._producer_method = _nonempty(producer_method, "producer_method")
        self._producer_version = _nonempty(producer_version, "producer_version")
        self._store = _SourceObservationStore()

    def authority(self) -> "SourceObservationAuthority":
        return SourceObservationAuthority(self._store)

    def current_revision_id(self, document_id: str) -> Optional[str]:
        return self._store.current_revision_by_document.get(str(document_id))

    def render_native_page_png(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        dpi: float = 300.0,
    ) -> tuple[bytes, SourceObservationRecord]:
        """Render one page from the exact immutable PDF bytes this producer ingested.

        This is the producer-owned raster boundary for downstream OCR. Callers
        address the page by immutable lineage only; they cannot supply page pixels,
        a page-parent observation id, or a source partition id. The native page
        parent and partition are resolved internally from snapshot_id and the
        producer's own observation store.

        Returns (png_bytes, native_pdf_page_observation). The returned observation
        is a defensive copy scoped to the requested snapshot.
        """

        document_id = _nonempty(document_id, "document_id")
        revision_id = _nonempty(revision_id, "revision_id")
        source_sha256 = _nonempty(source_sha256, "source_sha256")
        snapshot_id = _nonempty(snapshot_id, "snapshot_id")
        page_id = _nonempty(page_id, "page_id")
        dpi_value = float(dpi)
        if not math.isfinite(dpi_value) or dpi_value <= 0.0:
            raise ValueError("dpi must be a positive finite number")

        current = self._store.current_revision_by_document.get(document_id)
        if current is None:
            raise ValueError(SOURCE_UNAVAILABLE)
        if current != revision_id:
            raise ValueError(f"{STALE_REVISION}: revision is not current")

        revision = self._store.revisions.get(revision_id)
        source_bytes = self._store.source_bytes_by_revision.get(revision_id)
        if revision is None or source_bytes is None:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: source lineage unavailable"
            )
        if hashlib.sha256(source_bytes).hexdigest() != revision.source_sha256:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: immutable source hash changed"
            )
        if source_sha256 != revision.source_sha256:
            raise ValueError(SOURCE_HASH_MISMATCH)

        snapshot = self._store.snapshots.get(snapshot_id)
        if (
            snapshot is None
            or snapshot.document_id != document_id
            or snapshot.revision_id != revision_id
            or snapshot.source_sha256 != source_sha256
        ):
            raise ValueError(SNAPSHOT_MISMATCH)

        page_parents: list[SourceObservationRecord] = []
        for observation_id in snapshot.observation_ids:
            record = self._store.observations.get((snapshot_id, observation_id))
            if (
                record is not None
                and record.observation_kind == "native_pdf_page"
                and record.origin_kind == "native"
                and record.page_id == page_id
                and not record.derivation_parent_ids
            ):
                page_parents.append(record)

        if len(page_parents) != 1:
            raise ValueError(
                f"{LINEAGE_UNAVAILABLE}: expected exactly one native_pdf_page "
                f"parent for page {page_id}, found {len(page_parents)}"
            )
        page_parent = page_parents[0]
        if page_parent.source_partition_id not in revision.partition_ids:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: native page partition not in revision"
            )

        coverage = (
            self._store.coverage_by_snapshot.get(snapshot_id)
            or self._store.coverage_by_revision.get(revision_id)
        )
        try:
            page_number = int(page_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: invalid page id {page_id!r}") from exc
        if str(page_number) != page_id or page_number < 1:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: invalid page id {page_id!r}")
        if coverage is None or page_number not in coverage.decoded_pages:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: page {page_id} was not decoded")

        try:
            pdf = fitz.open(stream=source_bytes, filetype="pdf")
        except Exception as exc:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: stored PDF no longer decodes"
            ) from exc
        try:
            if page_number > int(pdf.page_count):
                raise ValueError(f"{SOURCE_UNAVAILABLE}: page {page_id} out of range")
            page = pdf.load_page(page_number - 1)
            scale = dpi_value / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            png_bytes = pix.tobytes("png")
        finally:
            pdf.close()

        return png_bytes, replace(page_parent)

    def native_page_image_regions(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
    ) -> tuple[tuple[float, float, float, float], ...]:
        """Return producer-derived embedded-image regions for one source page.

        Callers address immutable source lineage only. Image inventory and
        placement geometry are decoded from the exact stored PDF bytes.
        """

        document_id = _nonempty(document_id, "document_id")
        revision_id = _nonempty(revision_id, "revision_id")
        source_sha256 = _nonempty(source_sha256, "source_sha256")
        snapshot_id = _nonempty(snapshot_id, "snapshot_id")
        page_id = _nonempty(page_id, "page_id")

        current = self._store.current_revision_by_document.get(document_id)
        if current is None:
            raise ValueError(SOURCE_UNAVAILABLE)
        if current != revision_id:
            raise ValueError(f"{STALE_REVISION}: revision is not current")

        revision = self._store.revisions.get(revision_id)
        source_bytes = self._store.source_bytes_by_revision.get(revision_id)
        if revision is None or source_bytes is None:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: source lineage unavailable"
            )
        if hashlib.sha256(source_bytes).hexdigest() != revision.source_sha256:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: immutable source hash changed"
            )
        if source_sha256 != revision.source_sha256:
            raise ValueError(SOURCE_HASH_MISMATCH)

        snapshot = self._store.snapshots.get(snapshot_id)
        if (
            snapshot is None
            or snapshot.document_id != document_id
            or snapshot.revision_id != revision_id
            or snapshot.source_sha256 != source_sha256
        ):
            raise ValueError(SNAPSHOT_MISMATCH)

        try:
            page_number = int(page_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: invalid page id {page_id!r}") from exc
        if str(page_number) != page_id or page_number < 1:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: invalid page id {page_id!r}")

        coverage = (
            self._store.coverage_by_snapshot.get(snapshot_id)
            or self._store.coverage_by_revision.get(revision_id)
        )
        if coverage is None or page_number not in coverage.decoded_pages:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: page {page_id} was not decoded")

        try:
            pdf = fitz.open(stream=source_bytes, filetype="pdf")
        except Exception as exc:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: stored PDF no longer decodes"
            ) from exc
        try:
            if page_number > int(pdf.page_count):
                raise ValueError(f"{SOURCE_UNAVAILABLE}: page {page_id} out of range")
            page = pdf.load_page(page_number - 1)
            regions: set[tuple[float, float, float, float]] = set()
            for image in page.get_images(full=True) or ():
                if not image:
                    continue
                try:
                    xref = int(image[0])
                except (TypeError, ValueError):
                    continue
                try:
                    rects = page.get_image_rects(xref) or ()
                except Exception:
                    continue
                for rect in rects:
                    geometry = (
                        float(rect.x0),
                        float(rect.y0),
                        float(rect.x1),
                        float(rect.y1),
                    )
                    if not all(math.isfinite(value) for value in geometry):
                        continue
                    if geometry[2] <= geometry[0] or geometry[3] <= geometry[1]:
                        continue
                    regions.add(tuple(round(value, 4) for value in geometry))
            return tuple(sorted(regions))
        finally:
            pdf.close()


    def ingest_native_pdf_bytes(
        self,
        *,
        document_id: str,
        source_bytes: bytes | bytearray | memoryview,
        source_locator: str,
        page_ids: Optional[Sequence[object]] = None,
    ) -> PublishedSourceSnapshot:
        """Hash immutable PDF bytes and decode the document or an exact page scope.

        page_ids=None preserves historical whole-document ingestion. When
        page_ids is supplied, the full immutable PDF is still hashed and retained
        as the source revision, but native primitives are decoded only for the
        requested 1-based source pages. Coverage records only pages actually
        decoded, so document-scope completeness remains fail-closed while the
        explicit pages completeness contract can prove the requested scope.
        """

        document_id = _nonempty(document_id, "document_id")
        source_locator = _nonempty(source_locator, "source_locator")
        if not isinstance(source_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("source_bytes must be bytes-like")
        immutable_bytes = bytes(source_bytes)
        if not immutable_bytes:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: empty source bytes")

        digest = hashlib.sha256(immutable_bytes).hexdigest()
        revision_id = stable_contract_id(
            "source_revision",
            {"document_id": document_id, "source_sha256": digest},
            digest_chars=32,
        )

        try:
            pdf = fitz.open(stream=immutable_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"{SOURCE_UNAVAILABLE}: PDF decode failed") from exc

        pending: list[dict[str, Any]] = []
        decoded_pages: list[int] = []
        failed_pages: list[int] = []
        try:
            total_pages = int(pdf.page_count)
            partition_ids = tuple(f"page:{i + 1}" for i in range(total_pages))
            if page_ids is None:
                selected_pages = tuple(range(1, total_pages + 1))
                scoped = False
            else:
                try:
                    selected_pages = tuple(
                        sorted(
                            {
                                int(str(value).strip())
                                for value in page_ids
                                if str(value).strip()
                            }
                        )
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{SOURCE_UNAVAILABLE}: invalid source page scope"
                    ) from exc
                if (
                    not selected_pages
                    or any(page < 1 or page > total_pages for page in selected_pages)
                ):
                    raise ValueError(
                        f"{SOURCE_UNAVAILABLE}: invalid source page scope"
                    )
                scoped = True

            if not scoped:
                existing_snapshot_id = self._store.source_snapshot_by_revision.get(
                    revision_id
                )
            else:
                existing_snapshot_id = self._store.source_snapshot_by_revision_scope.get(
                    (revision_id, selected_pages)
                )
            if existing_snapshot_id is not None:
                coverage = (
                    self._store.coverage_by_snapshot.get(existing_snapshot_id)
                    or self._store.coverage_by_revision.get(revision_id)
                )
                if coverage is None:
                    raise ProducerIntegrityError(
                        f"{PRODUCER_INTEGRITY_FAILURE}: cached coverage unavailable"
                    )
                return PublishedSourceSnapshot(
                    revision=replace(self._store.revisions[revision_id]),
                    coverage=replace(coverage),
                    snapshot=replace(self._store.snapshots[existing_snapshot_id]),
                )

            for page_number in selected_pages:
                page_index = page_number - 1
                partition_id = f"page:{page_number}"
                try:
                    page = pdf.load_page(page_index)
                    native = extract_native_page(page)
                    decoded_pages.append(page_number)
                    pending.append(
                        {
                            "page_id": str(page_number),
                            "partition_id": partition_id,
                            "kind": "native_pdf_page",
                            "primitive_ref": f"page:{page_number}",
                            "raw_text": "",
                            "geometry": (
                                float(native["width"]),
                                float(native["height"]),
                            ),
                        }
                    )
                    for segment in native.get("segments") or []:
                        pending.append(
                            {
                                "page_id": str(page_number),
                                "partition_id": partition_id,
                                "kind": "native_pdf_segment",
                                "primitive_ref": f"segment:{segment.get('id')}",
                                "raw_text": "",
                                "geometry": (
                                    float(segment["x1"]),
                                    float(segment["y1"]),
                                    float(segment["x2"]),
                                    float(segment["y2"]),
                                ),
                            }
                        )
                    for word in native.get("words") or []:
                        pending.append(
                            {
                                "page_id": str(page_number),
                                "partition_id": partition_id,
                                "kind": "native_pdf_word",
                                "primitive_ref": f"word:{word.get('id')}",
                                "raw_text": str(word.get("text") or ""),
                                "geometry": _finite_tuple(word.get("bbox") or ()),
                            }
                        )
                    for rect_index, rect in enumerate(native.get("rects") or []):
                        pending.append(
                            {
                                "page_id": str(page_number),
                                "partition_id": partition_id,
                                "kind": "native_pdf_rect",
                                "primitive_ref": f"rect:{rect_index}",
                                "raw_text": "",
                                "geometry": _finite_tuple(rect.get("bbox") or ()),
                            }
                        )
                except Exception:
                    failed_pages.append(page_number)
        finally:
            pdf.close()

        existing_revision = self._store.revisions.get(revision_id)
        if existing_revision is not None:
            if existing_revision.source_sha256 != digest:
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: revision hash changed"
                )
            revision = existing_revision
        else:
            previous_revision = self._store.current_revision_by_document.get(
                document_id
            )
            revision_generation = self._store.next_generation()
            revision = SourceRevisionRecord(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=digest,
                source_locator=source_locator,
                partition_ids=partition_ids,
                producer_method=self._producer_method,
                producer_version=self._producer_version,
                producer_generation=revision_generation,
                supersedes_revision_id=previous_revision,
            )

        coverage = SourceDecodeCoverageRecord(
            document_id=document_id,
            revision_id=revision_id,
            total_pages=total_pages,
            decoded_pages=tuple(decoded_pages),
            failed_pages=tuple(failed_pages),
            state=(
                "complete"
                if not failed_pages and len(decoded_pages) == total_pages
                else "partial"
            ),
        )
        snapshot_payload: dict[str, object] = {
            "document_id": document_id,
            "revision_id": revision_id,
            "source_sha256": digest,
            "producer_method": self._producer_method,
            "producer_version": self._producer_version,
            "kind": "native_pdf_ingestion",
        }
        if scoped:
            snapshot_payload["kind"] = "native_pdf_ingestion_scoped"
            snapshot_payload["page_ids"] = selected_pages
        snapshot_id = stable_contract_id(
            "source_snapshot",
            snapshot_payload,
            digest_chars=32,
        )

        generation = self._store.next_generation()
        records: list[SourceObservationRecord] = []
        for item in pending:
            identity = {
                "document_id": document_id,
                "revision_id": revision_id,
                "partition_id": item["partition_id"],
                "page_id": item["page_id"],
                "kind": item["kind"],
                "primitive_ref": item["primitive_ref"],
                "raw_text": item["raw_text"],
                "geometry": item["geometry"],
            }
            observation_id = stable_contract_id(
                "source_observation", identity, digest_chars=32
            )
            record = SourceObservationRecord(
                observation_id=observation_id,
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=digest,
                source_partition_id=str(item["partition_id"]),
                page_id=str(item["page_id"]),
                viewport_id=None,
                observation_kind=str(item["kind"]),
                source_primitive_ref=str(item["primitive_ref"]),
                raw_text=str(item["raw_text"]),
                geometry=_finite_tuple(item["geometry"]),
                origin_kind="native",
                derivation_parent_ids=(),
                producer_method=self._producer_method,
                producer_version=self._producer_version,
                producer_generation=generation,
                snapshot_id=snapshot_id,
                observation_payload_sha256="",
            )
            fingerprint = _content_sha256(_record_payload(record))
            record = replace(record, observation_payload_sha256=fingerprint)
            records.append(record)

        snapshot = ProducerSnapshotRecord(
            snapshot_id=snapshot_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=digest,
            observation_ids=tuple(sorted(r.observation_id for r in records)),
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
        )
        self._commit(
            revision=revision,
            coverage=coverage,
            snapshot=snapshot,
            records=records,
            source_bytes=immutable_bytes,
            mark_source_snapshot=not scoped,
        )
        if scoped:
            self._store.source_snapshot_by_revision_scope[
                (revision_id, selected_pages)
            ] = snapshot.snapshot_id
        return PublishedSourceSnapshot(
            revision=replace(revision),
            coverage=replace(coverage),
            snapshot=replace(snapshot),
        )

    def publish_derived_observation(
        self,
        *,
        document_id: str,
        revision_id: str,
        base_snapshot_id: str,
        page_id: str,
        source_partition_id: str,
        observation_kind: str,
        source_primitive_ref: str,
        origin_kind: str,
        parent_observation_ids: Sequence[str],
        raw_text: str = "",
        geometry: Sequence[float] = (),
        viewport_id: Optional[str] = None,
        observation_id: Optional[str] = None,
    ) -> ProducerSnapshotRecord:
        """Trusted writer for derived evidence; parent lineage must be in base snapshot."""

        current = self._store.current_revision_by_document.get(document_id)
        if current != revision_id:
            raise ValueError(f"{STALE_REVISION}: revision is not current")
        base = self._store.snapshots.get(base_snapshot_id)
        if base is None or base.revision_id != revision_id or base.document_id != document_id:
            raise ValueError(f"{SNAPSHOT_MISMATCH}: base snapshot mismatch")
        parents = tuple(str(p) for p in parent_observation_ids)
        if not parents:
            raise ValueError(f"{LINEAGE_UNAVAILABLE}: derived observation needs parent")
        for parent_id in parents:
            if (base_snapshot_id, parent_id) not in self._store.observations:
                raise ValueError(f"{LINEAGE_UNAVAILABLE}: parent not in base snapshot")

        revision = self._store.revisions[revision_id]
        coverage = (
            self._store.coverage_by_snapshot.get(base_snapshot_id)
            or self._store.coverage_by_revision.get(revision_id)
        )
        if coverage is None:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: base snapshot coverage unavailable"
            )
        generation = self._store.next_generation()
        payload = {
            "document_id": document_id,
            "revision_id": revision_id,
            "page_id": page_id,
            "partition_id": source_partition_id,
            "kind": observation_kind,
            "primitive_ref": source_primitive_ref,
            "origin_kind": origin_kind,
            "parents": parents,
            "raw_text": raw_text,
            "geometry": _finite_tuple(geometry),
        }
        derived_id = observation_id or stable_contract_id(
            "source_observation", payload, digest_chars=32
        )
        snapshot_id = stable_contract_id(
            "source_snapshot",
            {
                "revision_id": revision_id,
                "base_snapshot_id": base_snapshot_id,
                "derived_observation_id": derived_id,
                "generation": generation,
            },
            digest_chars=32,
        )
        cloned = [
            replace(
                self._store.observations[(base_snapshot_id, obs_id)],
                snapshot_id=snapshot_id,
                producer_generation=generation,
            )
            for obs_id in base.observation_ids
        ]
        derived = SourceObservationRecord(
            observation_id=derived_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=revision.source_sha256,
            source_partition_id=_nonempty(source_partition_id, "source_partition_id"),
            page_id=_nonempty(page_id, "page_id"),
            viewport_id=str(viewport_id) if viewport_id is not None else None,
            observation_kind=_nonempty(observation_kind, "observation_kind"),
            source_primitive_ref=_nonempty(source_primitive_ref, "source_primitive_ref"),
            raw_text=str(raw_text or ""),
            geometry=_finite_tuple(geometry),
            origin_kind=_nonempty(origin_kind, "origin_kind"),
            derivation_parent_ids=parents,
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
            snapshot_id=snapshot_id,
            observation_payload_sha256="",
        )
        derived = replace(
            derived, observation_payload_sha256=_content_sha256(_record_payload(derived))
        )
        records = [*cloned, derived]
        ids = [r.observation_id for r in records]
        if len(ids) != len(set(ids)):
            by_id: dict[str, SourceObservationRecord] = {}
            for record in records:
                prior = by_id.get(record.observation_id)
                if prior is not None and _record_payload(prior) != _record_payload(record):
                    raise ProducerIntegrityError(
                        f"{PRODUCER_INTEGRITY_FAILURE}: duplicate observation id differs"
                    )
                by_id[record.observation_id] = record
            records = list(by_id.values())
        snapshot = ProducerSnapshotRecord(
            snapshot_id=snapshot_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=revision.source_sha256,
            observation_ids=tuple(sorted(r.observation_id for r in records)),
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
            parent_snapshot_id=base_snapshot_id,
        )
        self._commit(
            revision=revision,
            coverage=coverage,
            snapshot=snapshot,
            records=records,
            source_bytes=self._store.source_bytes_by_revision[revision_id],
            mark_source_snapshot=False,
        )
        return replace(snapshot)

    def publish_derived_observations(
        self,
        *,
        document_id: str,
        revision_id: str,
        base_snapshot_id: str,
        observations: Sequence[Mapping[str, Any]],
    ) -> ProducerSnapshotRecord:
        """Publish one producer-owned batch of derived observations.

        Every observation's parents must already exist in base_snapshot_id.
        The batch is committed as one immutable snapshot, avoiding repeated
        whole-snapshot cloning when a trusted producer derives many siblings
        from the same source evidence.
        """

        current = self._store.current_revision_by_document.get(document_id)
        if current != revision_id:
            raise ValueError(f"{STALE_REVISION}: revision is not current")
        base = self._store.snapshots.get(base_snapshot_id)
        if (
            base is None
            or base.revision_id != revision_id
            or base.document_id != document_id
        ):
            raise ValueError(f"{SNAPSHOT_MISMATCH}: base snapshot mismatch")
        if not observations:
            raise ValueError("observations must be non-empty")

        revision = self._store.revisions[revision_id]
        coverage = (
            self._store.coverage_by_snapshot.get(base_snapshot_id)
            or self._store.coverage_by_revision.get(revision_id)
        )
        if coverage is None:
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: base snapshot coverage unavailable"
            )
        generation = self._store.next_generation()

        prepared: list[dict[str, Any]] = []
        derived_ids: list[str] = []
        for raw in observations:
            page_id = _nonempty(str(raw.get("page_id") or ""), "page_id")
            source_partition_id = _nonempty(
                str(raw.get("source_partition_id") or ""),
                "source_partition_id",
            )
            observation_kind = _nonempty(
                str(raw.get("observation_kind") or ""),
                "observation_kind",
            )
            source_primitive_ref = _nonempty(
                str(raw.get("source_primitive_ref") or ""),
                "source_primitive_ref",
            )
            origin_kind = _nonempty(
                str(raw.get("origin_kind") or ""),
                "origin_kind",
            )
            parents = tuple(
                str(parent)
                for parent in (raw.get("parent_observation_ids") or ())
            )
            if not parents:
                raise ValueError(
                    f"{LINEAGE_UNAVAILABLE}: derived observation needs parent"
                )
            for parent_id in parents:
                if (base_snapshot_id, parent_id) not in self._store.observations:
                    raise ValueError(
                        f"{LINEAGE_UNAVAILABLE}: parent not in base snapshot"
                    )
            raw_text = str(raw.get("raw_text") or "")
            geometry = _finite_tuple(raw.get("geometry") or ())
            viewport_value = raw.get("viewport_id")
            viewport_id = (
                str(viewport_value) if viewport_value is not None else None
            )
            payload = {
                "document_id": document_id,
                "revision_id": revision_id,
                "page_id": page_id,
                "partition_id": source_partition_id,
                "kind": observation_kind,
                "primitive_ref": source_primitive_ref,
                "origin_kind": origin_kind,
                "parents": parents,
                "raw_text": raw_text,
                "geometry": geometry,
            }
            supplied_id = raw.get("observation_id")
            derived_id = (
                str(supplied_id)
                if supplied_id is not None
                else stable_contract_id(
                    "source_observation",
                    payload,
                    digest_chars=32,
                )
            )
            if not derived_id:
                raise ValueError("observation_id must be non-empty")
            prepared.append(
                {
                    "observation_id": derived_id,
                    "page_id": page_id,
                    "source_partition_id": source_partition_id,
                    "observation_kind": observation_kind,
                    "source_primitive_ref": source_primitive_ref,
                    "origin_kind": origin_kind,
                    "parents": parents,
                    "raw_text": raw_text,
                    "geometry": geometry,
                    "viewport_id": viewport_id,
                }
            )
            derived_ids.append(derived_id)

        if len(derived_ids) != len(set(derived_ids)):
            raise ProducerIntegrityError(
                f"{PRODUCER_INTEGRITY_FAILURE}: duplicate batch observation id"
            )

        snapshot_id = stable_contract_id(
            "source_snapshot",
            {
                "revision_id": revision_id,
                "base_snapshot_id": base_snapshot_id,
                "derived_observation_ids": tuple(sorted(derived_ids)),
                "generation": generation,
            },
            digest_chars=32,
        )

        cloned = [
            replace(
                self._store.observations[(base_snapshot_id, obs_id)],
                snapshot_id=snapshot_id,
                producer_generation=generation,
            )
            for obs_id in base.observation_ids
        ]
        derived_records: list[SourceObservationRecord] = []
        for item in prepared:
            record = SourceObservationRecord(
                observation_id=item["observation_id"],
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=revision.source_sha256,
                source_partition_id=item["source_partition_id"],
                page_id=item["page_id"],
                viewport_id=item["viewport_id"],
                observation_kind=item["observation_kind"],
                source_primitive_ref=item["source_primitive_ref"],
                raw_text=item["raw_text"],
                geometry=item["geometry"],
                origin_kind=item["origin_kind"],
                derivation_parent_ids=item["parents"],
                producer_method=self._producer_method,
                producer_version=self._producer_version,
                producer_generation=generation,
                snapshot_id=snapshot_id,
                observation_payload_sha256="",
            )
            record = replace(
                record,
                observation_payload_sha256=_content_sha256(
                    _record_payload(record)
                ),
            )
            derived_records.append(record)

        records = [*cloned, *derived_records]
        ids = [record.observation_id for record in records]
        if len(ids) != len(set(ids)):
            by_id: dict[str, SourceObservationRecord] = {}
            for record in records:
                prior = by_id.get(record.observation_id)
                if (
                    prior is not None
                    and _record_payload(prior) != _record_payload(record)
                ):
                    raise ProducerIntegrityError(
                        f"{PRODUCER_INTEGRITY_FAILURE}: "
                        "duplicate observation id differs"
                    )
                by_id[record.observation_id] = record
            records = list(by_id.values())

        snapshot = ProducerSnapshotRecord(
            snapshot_id=snapshot_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=revision.source_sha256,
            observation_ids=tuple(
                sorted(record.observation_id for record in records)
            ),
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
            parent_snapshot_id=base_snapshot_id,
        )
        self._commit(
            revision=revision,
            coverage=coverage,
            snapshot=snapshot,
            records=records,
            source_bytes=self._store.source_bytes_by_revision[revision_id],
            mark_source_snapshot=False,
        )
        return replace(snapshot)

    def _commit(
        self,
        *,
        revision: SourceRevisionRecord,
        coverage: SourceDecodeCoverageRecord,
        snapshot: ProducerSnapshotRecord,
        records: Sequence[SourceObservationRecord],
        source_bytes: bytes,
        mark_source_snapshot: bool,
    ) -> None:
        staged: dict[tuple[str, str], SourceObservationRecord] = {}
        for record in records:
            key = (snapshot.snapshot_id, record.observation_id)
            prior = staged.get(key)
            if prior is not None and _record_payload(prior) != _record_payload(record):
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: duplicate observation id differs"
                )
            staged[key] = record
        self._store.revisions[revision.revision_id] = revision
        self._store.current_revision_by_document[revision.document_id] = revision.revision_id
        self._store.source_bytes_by_revision[revision.revision_id] = bytes(source_bytes)
        self._store.coverage_by_revision[revision.revision_id] = coverage
        self._store.coverage_by_snapshot[snapshot.snapshot_id] = coverage
        self._store.snapshots[snapshot.snapshot_id] = snapshot
        for key, record in staged.items():
            self._store.observations[key] = record
            self._store.record_fingerprints[key] = record.observation_payload_sha256
        if mark_source_snapshot:
            self._store.source_snapshot_by_revision[revision.revision_id] = snapshot.snapshot_id


class SourceObservationAuthority:
    """Read-only consumer view over producer-owned records."""

    def __init__(self, store: _SourceObservationStore) -> None:
        self._store = store

    def _blocked(self, reason: str) -> SourceObservationAuthorityResult:
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(reason,),
        )

    def _integrity_failure(self) -> SourceObservationAuthorityResult:
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.CONFLICT,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(PRODUCER_INTEGRITY_FAILURE,),
        )

    def resolve(self, selector: ObservationSelector) -> SourceObservationAuthorityResult:
        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")
        current = self._store.current_revision_by_document.get(selector.document_id)
        if current is None:
            return self._blocked(SOURCE_UNAVAILABLE)
        if current != selector.revision_id:
            return self._blocked(STALE_REVISION)
        revision = self._store.revisions.get(selector.revision_id)
        source_bytes = self._store.source_bytes_by_revision.get(selector.revision_id)
        if revision is None or source_bytes is None:
            return self._integrity_failure()
        if hashlib.sha256(source_bytes).hexdigest() != revision.source_sha256:
            return self._integrity_failure()
        if selector.source_sha256 != revision.source_sha256:
            return self._blocked(SOURCE_HASH_MISMATCH)
        snapshot = self._store.snapshots.get(selector.snapshot_id)
        if (
            snapshot is None
            or snapshot.document_id != selector.document_id
            or snapshot.revision_id != selector.revision_id
            or snapshot.source_sha256 != selector.source_sha256
        ):
            return self._blocked(SNAPSHOT_MISMATCH)
        record = self._store.observations.get((selector.snapshot_id, selector.observation_id))
        if record is None:
            return self._blocked(OBSERVATION_UNAVAILABLE)
        if selector.observation_id not in snapshot.observation_ids:
            return self._integrity_failure()
        expected = self._store.record_fingerprints.get((selector.snapshot_id, selector.observation_id))
        actual = _content_sha256(_record_payload(record))
        if expected is None or expected != actual or record.observation_payload_sha256 != actual:
            return self._integrity_failure()
        for parent_id in record.derivation_parent_ids:
            if (selector.snapshot_id, parent_id) not in self._store.observations:
                return self._blocked(LINEAGE_UNAVAILABLE)
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=SOURCE_OBSERVATION_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=("producer_owned_source_observation_resolved",),
            source_revision=replace(revision),
            snapshot=replace(snapshot),
            observation=replace(record),
            semantic_enumeration_complete=None,
            decision_scope_complete=None,
        )

    def coverage(
        self, *, document_id: str, revision_id: str
    ) -> Optional[SourceDecodeCoverageRecord]:
        coverage = (
            self._store.coverage_by_snapshot.get(snapshot_id)
            or self._store.coverage_by_revision.get(revision_id)
        )
        if coverage is None or coverage.document_id != document_id:
            return None
        return replace(coverage)


__all__ = [
    "LINEAGE_UNAVAILABLE",
    "OBSERVATION_UNAVAILABLE",
    "PHYSICAL_OPENING_EXISTENCE_UNRESOLVED",
    "PRODUCER_INTEGRITY_FAILURE",
    "SNAPSHOT_MISMATCH",
    "SOURCE_HASH_MISMATCH",
    "SOURCE_OBSERVATION_EXISTS",
    "SOURCE_UNAVAILABLE",
    "STALE_REVISION",
    "ObservationSelector",
    "ProducerIntegrityError",
    "ProducerSnapshotRecord",
    "PublishedSourceSnapshot",
    "SourceDecodeCoverageRecord",
    "SourceObservationAuthority",
    "SourceObservationAuthorityResult",
    "SourceObservationProducer",
    "SourceObservationRecord",
    "SourceRevisionRecord",
]
