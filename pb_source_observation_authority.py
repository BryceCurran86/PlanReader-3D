"""G17 phase-1 producer-owned source-observation authority.

This module intentionally establishes only the proposition that a producer-owned
source observation exists with immutable lineage to an exact source revision and
published producer snapshot.

It does *not* establish physical-opening existence, opening identity, universe
completeness, opening dimensions, host binding, physical void, or net wall area.
Heuristic, OCR, CV, schedule, reconstructed, and derived observations therefore
remain ``PHYSICAL_OPENING_EXISTENCE_UNRESOLVED`` even when their source
observation existence is corroborated.

The producer/consumer split is structural in this in-process implementation.  It
is not claimed as a security boundary against equally privileged same-process
code; the merged G17 architecture requires a separate process/credential/store
boundary for that stronger threat model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import re
from typing import Iterable, Optional, Sequence

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    canonical_contract_json,
    stable_contract_id,
)


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

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DERIVED_ORIGIN_KINDS = frozenset({"derived", "normalized"})


class ProducerIntegrityError(RuntimeError):
    """Producer-owned records violate an immutable identity/integrity rule."""


def _nonempty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _optional_nonempty(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _nonempty(value, field_name)


def _sha256_hex(value: str, field_name: str) -> str:
    clean = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{field_name} must be a 64-character lowercase SHA-256 digest")
    return clean


def _geometry_tuple(values: Iterable[float]) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("geometry coordinates must be finite")
    return result


def _unique_nonempty(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    cleaned = tuple(_nonempty(value, field_name) for value in values)
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} values must be unique")
    return cleaned


def _content_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_contract_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRevisionRecord:
    """Immutable producer-owned identity for exact ingested source bytes."""

    document_id: str
    revision_id: str
    source_sha256: str
    source_locator: str
    partition_ids: tuple[str, ...]
    ingestion_id: str
    producer_method: str
    producer_version: str
    producer_generation: int
    supersedes_revision_id: Optional[str] = None
    invalidation_conditions: tuple[str, ...] = (
        "source_bytes_change",
        "source_partition_inventory_change",
        "producer_method_or_version_change",
    )
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _nonempty(self.document_id, "document_id")
        _nonempty(self.revision_id, "revision_id")
        object.__setattr__(self, "source_sha256", _sha256_hex(self.source_sha256, "source_sha256"))
        _nonempty(self.source_locator, "source_locator")
        object.__setattr__(self, "partition_ids", _unique_nonempty(self.partition_ids, "partition_id"))
        _nonempty(self.ingestion_id, "ingestion_id")
        _nonempty(self.producer_method, "producer_method")
        _nonempty(self.producer_version, "producer_version")
        if int(self.producer_generation) < 1:
            raise ValueError("producer_generation must be >= 1")
        object.__setattr__(self, "producer_generation", int(self.producer_generation))
        object.__setattr__(
            self,
            "supersedes_revision_id",
            _optional_nonempty(self.supersedes_revision_id, "supersedes_revision_id"),
        )


@dataclass(frozen=True)
class SourceObservationInput:
    """Trusted producer-ingestion input, never accepted by the consumer API."""

    source_partition_id: str
    page_id: str
    observation_kind: str
    source_primitive_ref: str
    raw_text: str = ""
    geometry: tuple[float, ...] = ()
    viewport_id: Optional[str] = None
    origin_kind: str = "native"
    derivation_parent_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.source_partition_id, "source_partition_id")
        _nonempty(self.page_id, "page_id")
        _nonempty(self.observation_kind, "observation_kind")
        _nonempty(self.source_primitive_ref, "source_primitive_ref")
        object.__setattr__(self, "viewport_id", _optional_nonempty(self.viewport_id, "viewport_id"))
        object.__setattr__(self, "origin_kind", _nonempty(self.origin_kind, "origin_kind").lower())
        object.__setattr__(self, "geometry", _geometry_tuple(self.geometry))
        object.__setattr__(
            self,
            "derivation_parent_ids",
            _unique_nonempty(self.derivation_parent_ids, "derivation_parent_id"),
        )
        if self.origin_kind in _DERIVED_ORIGIN_KINDS and not self.derivation_parent_ids:
            raise ValueError("derived/normalized observation requires at least one lineage parent")


@dataclass(frozen=True)
class SourceObservationRecord:
    """Immutable published producer observation bound to revision and snapshot."""

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
    invalidation_conditions: tuple[str, ...] = (
        "source_revision_changes",
        "producer_snapshot_changes",
        "source_primitive_changes",
        "lineage_parent_unavailable",
    )
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.RAW
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _nonempty(self.observation_id, "observation_id")
        _nonempty(self.document_id, "document_id")
        _nonempty(self.revision_id, "revision_id")
        object.__setattr__(self, "source_sha256", _sha256_hex(self.source_sha256, "source_sha256"))
        _nonempty(self.source_partition_id, "source_partition_id")
        _nonempty(self.page_id, "page_id")
        object.__setattr__(self, "viewport_id", _optional_nonempty(self.viewport_id, "viewport_id"))
        _nonempty(self.observation_kind, "observation_kind")
        _nonempty(self.source_primitive_ref, "source_primitive_ref")
        object.__setattr__(self, "geometry", _geometry_tuple(self.geometry))
        object.__setattr__(self, "origin_kind", _nonempty(self.origin_kind, "origin_kind").lower())
        object.__setattr__(
            self,
            "derivation_parent_ids",
            _unique_nonempty(self.derivation_parent_ids, "derivation_parent_id"),
        )
        _nonempty(self.producer_method, "producer_method")
        _nonempty(self.producer_version, "producer_version")
        if int(self.producer_generation) < 1:
            raise ValueError("producer_generation must be >= 1")
        object.__setattr__(self, "producer_generation", int(self.producer_generation))
        _nonempty(self.snapshot_id, "snapshot_id")
        object.__setattr__(
            self,
            "observation_payload_sha256",
            _sha256_hex(self.observation_payload_sha256, "observation_payload_sha256"),
        )


@dataclass(frozen=True)
class ProducerSnapshotRecord:
    """Immutable producer publication boundary for one exact source revision."""

    snapshot_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    observation_ids: tuple[str, ...]
    producer_method: str
    producer_version: str
    producer_generation: int
    invalidation_conditions: tuple[str, ...] = (
        "source_revision_changes",
        "observation_identity_collision",
        "producer_integrity_failure",
    )
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    schema_version: str = SOURCE_OBSERVATION_AUTHORITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _nonempty(self.snapshot_id, "snapshot_id")
        _nonempty(self.document_id, "document_id")
        _nonempty(self.revision_id, "revision_id")
        object.__setattr__(self, "source_sha256", _sha256_hex(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "observation_ids", _unique_nonempty(self.observation_ids, "observation_id"))
        _nonempty(self.producer_method, "producer_method")
        _nonempty(self.producer_version, "producer_version")
        if int(self.producer_generation) < 1:
            raise ValueError("producer_generation must be >= 1")
        object.__setattr__(self, "producer_generation", int(self.producer_generation))


@dataclass(frozen=True)
class ObservationSelector:
    """Consumer-supplied lookup selector; contains no authority record body."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    observation_id: str

    def __post_init__(self) -> None:
        _nonempty(self.document_id, "document_id")
        _nonempty(self.revision_id, "revision_id")
        object.__setattr__(self, "source_sha256", _sha256_hex(self.source_sha256, "source_sha256"))
        _nonempty(self.snapshot_id, "snapshot_id")
        _nonempty(self.observation_id, "observation_id")


@dataclass(frozen=True)
class SourceObservationAuthorityResult:
    """Typed Phase-1 authority result.  Never proves physical-opening existence."""

    status: EvidenceResolutionStatus
    proposition: Optional[str]
    physical_opening_existence: str
    reason_codes: tuple[str, ...]
    source_revision: Optional[SourceRevisionRecord] = None
    snapshot: Optional[ProducerSnapshotRecord] = None
    observation: Optional[SourceObservationRecord] = None


class _SourceObservationStore:
    """Producer-owned mutable backing state; consumers receive read access only."""

    def __init__(self) -> None:
        self.revisions: dict[str, SourceRevisionRecord] = {}
        self.source_bytes_by_revision: dict[str, bytes] = {}
        self.current_revision_by_document: dict[str, str] = {}
        self.snapshots: dict[str, ProducerSnapshotRecord] = {}
        self.observations_by_snapshot: dict[tuple[str, str], SourceObservationRecord] = {}
        self.observation_fingerprint_by_id: dict[str, str] = {}
        self.observation_revision_by_id: dict[str, str] = {}
        self.snapshot_payload_fingerprint: dict[str, str] = {}
        self._next_generation = 1

    def allocate_generation(self) -> int:
        generation = self._next_generation
        self._next_generation += 1
        return generation


def _observation_identity_payload(revision: SourceRevisionRecord, value: SourceObservationInput) -> dict[str, object]:
    return {
        "document_id": revision.document_id,
        "revision_id": revision.revision_id,
        "source_partition_id": value.source_partition_id,
        "page_id": value.page_id,
        "viewport_id": value.viewport_id,
        "observation_kind": value.observation_kind,
        "source_primitive_ref": value.source_primitive_ref,
    }


def _observation_content_payload(
    revision: SourceRevisionRecord,
    value: SourceObservationInput,
    *,
    producer_method: str,
    producer_version: str,
) -> dict[str, object]:
    return {
        **_observation_identity_payload(revision, value),
        "source_sha256": revision.source_sha256,
        "raw_text": value.raw_text,
        "geometry": value.geometry,
        "origin_kind": value.origin_kind,
        "derivation_parent_ids": value.derivation_parent_ids,
        "producer_method": producer_method,
        "producer_version": producer_version,
    }


def _record_content_payload(record: SourceObservationRecord) -> dict[str, object]:
    return {
        "document_id": record.document_id,
        "revision_id": record.revision_id,
        "source_partition_id": record.source_partition_id,
        "page_id": record.page_id,
        "viewport_id": record.viewport_id,
        "observation_kind": record.observation_kind,
        "source_primitive_ref": record.source_primitive_ref,
        "source_sha256": record.source_sha256,
        "raw_text": record.raw_text,
        "geometry": record.geometry,
        "origin_kind": record.origin_kind,
        "derivation_parent_ids": record.derivation_parent_ids,
        "producer_method": record.producer_method,
        "producer_version": record.producer_version,
    }


class SourceObservationProducer:
    """Trusted writer side of the G17 phase-1 source-observation boundary."""

    def __init__(self, *, producer_method: str, producer_version: str) -> None:
        self._producer_method = _nonempty(producer_method, "producer_method")
        self._producer_version = _nonempty(producer_version, "producer_version")
        self._store = _SourceObservationStore()

    def current_revision_id(self, document_id: str) -> Optional[str]:
        return self._store.current_revision_by_document.get(_nonempty(document_id, "document_id"))

    def authority(self) -> "SourceObservationAuthority":
        return SourceObservationAuthority(self._store)

    def ingest_source(
        self,
        *,
        document_id: str,
        source_bytes: bytes | bytearray | memoryview,
        source_locator: str,
        partition_ids: Sequence[str],
    ) -> SourceRevisionRecord:
        """Ingest exact bytes once and publish their immutable source revision.

        ``bytes(...)`` deliberately detaches producer state from a mutable caller
        buffer before hashing and storage, preventing a hash/decode time-of-check
        versus time-of-use gap inside this phase-1 store.
        """

        document_id = _nonempty(document_id, "document_id")
        source_locator = _nonempty(source_locator, "source_locator")
        partitions = _unique_nonempty(partition_ids, "partition_id")
        if not partitions:
            raise ValueError("partition_ids must contain at least one producer-owned partition")
        if not isinstance(source_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("source_bytes must be bytes-like")
        immutable_bytes = bytes(source_bytes)
        if not immutable_bytes:
            raise ValueError("source_bytes must not be empty")

        source_sha256 = hashlib.sha256(immutable_bytes).hexdigest()
        revision_id = stable_contract_id(
            "source_revision",
            {"document_id": document_id, "source_sha256": source_sha256},
            digest_chars=32,
        )
        ingestion_id = stable_contract_id(
            "source_ingestion",
            {
                "document_id": document_id,
                "revision_id": revision_id,
                "source_sha256": source_sha256,
                "source_locator": source_locator,
                "partition_ids": partitions,
                "producer_method": self._producer_method,
                "producer_version": self._producer_version,
            },
            digest_chars=32,
        )

        existing = self._store.revisions.get(revision_id)
        if existing is not None:
            if (
                self._store.source_bytes_by_revision.get(revision_id) != immutable_bytes
                or existing.source_locator != source_locator
                or existing.partition_ids != partitions
                or existing.ingestion_id != ingestion_id
            ):
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: source revision identity reused with different producer content"
                )
            self._store.current_revision_by_document[document_id] = revision_id
            return replace(existing)

        previous_revision_id = self._store.current_revision_by_document.get(document_id)
        generation = self._store.allocate_generation()
        record = SourceRevisionRecord(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            source_locator=source_locator,
            partition_ids=partitions,
            ingestion_id=ingestion_id,
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
            supersedes_revision_id=previous_revision_id,
        )
        self._store.revisions[revision_id] = record
        self._store.source_bytes_by_revision[revision_id] = immutable_bytes
        self._store.current_revision_by_document[document_id] = revision_id
        return replace(record)

    def publish_snapshot(
        self,
        *,
        revision_id: str,
        observations: Sequence[SourceObservationInput],
    ) -> ProducerSnapshotRecord:
        """Publish producer observations atomically for one current revision.

        This is a trusted producer-writer operation.  The consumer authority API
        has no corresponding record-body argument and cannot call through this
        method by holding only a ``SourceObservationAuthority``.
        """

        revision_id = _nonempty(revision_id, "revision_id")
        revision = self._store.revisions.get(revision_id)
        if revision is None:
            raise ValueError(f"unknown source revision: {revision_id}")
        if self._store.current_revision_by_document.get(revision.document_id) != revision_id:
            raise ValueError("cannot publish observations for a stale source revision")

        values = tuple(observations)
        prepared: dict[str, tuple[SourceObservationInput, str]] = {}
        for value in values:
            if not isinstance(value, SourceObservationInput):
                raise TypeError("observations must contain SourceObservationInput values")
            if value.source_partition_id not in revision.partition_ids:
                raise ValueError("source observation partition is not owned by the source revision")
            observation_id = stable_contract_id(
                "source_observation",
                _observation_identity_payload(revision, value),
                digest_chars=32,
            )
            fingerprint = _content_sha256(
                _observation_content_payload(
                    revision,
                    value,
                    producer_method=self._producer_method,
                    producer_version=self._producer_version,
                )
            )
            prior_prepared = prepared.get(observation_id)
            if prior_prepared is not None and prior_prepared[1] != fingerprint:
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: duplicate observation id has different content"
                )
            prepared[observation_id] = (value, fingerprint)

        available_parent_ids = set(self._store.observation_fingerprint_by_id) | set(prepared)
        for observation_id, (value, _) in prepared.items():
            for parent_id in value.derivation_parent_ids:
                if parent_id == observation_id or parent_id not in available_parent_ids:
                    raise ValueError(f"lineage parent is unavailable: {parent_id}")
                parent_revision = self._store.observation_revision_by_id.get(parent_id)
                if parent_revision is not None and parent_revision != revision_id:
                    raise ValueError("lineage parent must belong to the same source revision")

        for observation_id, (_, fingerprint) in prepared.items():
            prior_fingerprint = self._store.observation_fingerprint_by_id.get(observation_id)
            if prior_fingerprint is not None and prior_fingerprint != fingerprint:
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: duplicate observation id has different content"
                )

        observation_pairs = tuple(sorted((observation_id, fp) for observation_id, (_, fp) in prepared.items()))
        snapshot_payload = {
            "document_id": revision.document_id,
            "revision_id": revision.revision_id,
            "source_sha256": revision.source_sha256,
            "producer_method": self._producer_method,
            "producer_version": self._producer_version,
            "observations": observation_pairs,
        }
        snapshot_id = stable_contract_id("source_snapshot", snapshot_payload, digest_chars=32)
        snapshot_fingerprint = _content_sha256(snapshot_payload)

        existing_snapshot = self._store.snapshots.get(snapshot_id)
        if existing_snapshot is not None:
            if self._store.snapshot_payload_fingerprint.get(snapshot_id) != snapshot_fingerprint:
                raise ProducerIntegrityError(
                    f"{PRODUCER_INTEGRITY_FAILURE}: snapshot id reused with different content"
                )
            return replace(existing_snapshot)

        generation = self._store.allocate_generation()
        snapshot = ProducerSnapshotRecord(
            snapshot_id=snapshot_id,
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            observation_ids=tuple(observation_id for observation_id, _ in observation_pairs),
            producer_method=self._producer_method,
            producer_version=self._producer_version,
            producer_generation=generation,
        )

        records: list[SourceObservationRecord] = []
        for observation_id in snapshot.observation_ids:
            value, fingerprint = prepared[observation_id]
            record = SourceObservationRecord(
                observation_id=observation_id,
                document_id=revision.document_id,
                revision_id=revision.revision_id,
                source_sha256=revision.source_sha256,
                source_partition_id=value.source_partition_id,
                page_id=value.page_id,
                viewport_id=value.viewport_id,
                observation_kind=value.observation_kind,
                source_primitive_ref=value.source_primitive_ref,
                raw_text=value.raw_text,
                geometry=value.geometry,
                origin_kind=value.origin_kind,
                derivation_parent_ids=value.derivation_parent_ids,
                producer_method=self._producer_method,
                producer_version=self._producer_version,
                producer_generation=generation,
                snapshot_id=snapshot_id,
                observation_payload_sha256=fingerprint,
            )
            records.append(record)

        self._store.snapshots[snapshot_id] = snapshot
        self._store.snapshot_payload_fingerprint[snapshot_id] = snapshot_fingerprint
        for record in records:
            self._store.observations_by_snapshot[(snapshot_id, record.observation_id)] = record
            self._store.observation_fingerprint_by_id[record.observation_id] = record.observation_payload_sha256
            self._store.observation_revision_by_id[record.observation_id] = record.revision_id

        return replace(snapshot)


class SourceObservationAuthority:
    """Read-only consumer view over producer-owned phase-1 source observations."""

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
        """Resolve a selector against producer-owned records only.

        No caller-created observation body, hash assertion, completeness boolean,
        candidate list, ``CORROBORATED`` atom, or semantic relationship proof is
        accepted by this API.
        """

        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be an ObservationSelector")

        current_revision_id = self._store.current_revision_by_document.get(selector.document_id)
        if current_revision_id is None:
            return self._blocked(SOURCE_UNAVAILABLE)
        if current_revision_id != selector.revision_id:
            return self._blocked(STALE_REVISION)

        revision = self._store.revisions.get(selector.revision_id)
        source_bytes = self._store.source_bytes_by_revision.get(selector.revision_id)
        if revision is None or source_bytes is None or revision.document_id != selector.document_id:
            return self._integrity_failure()
        actual_source_hash = hashlib.sha256(source_bytes).hexdigest()
        if actual_source_hash != revision.source_sha256:
            return self._integrity_failure()
        if selector.source_sha256 != revision.source_sha256:
            return self._blocked(SOURCE_HASH_MISMATCH)

        snapshot = self._store.snapshots.get(selector.snapshot_id)
        if snapshot is None:
            return self._blocked(SNAPSHOT_MISMATCH)
        if (
            snapshot.document_id != revision.document_id
            or snapshot.revision_id != revision.revision_id
            or snapshot.source_sha256 != revision.source_sha256
            or self._store.snapshot_payload_fingerprint.get(snapshot.snapshot_id) is None
        ):
            return self._integrity_failure()

        record = self._store.observations_by_snapshot.get((snapshot.snapshot_id, selector.observation_id))
        if record is None:
            if selector.observation_id in self._store.observation_fingerprint_by_id:
                return self._blocked(SNAPSHOT_MISMATCH)
            return self._blocked(OBSERVATION_UNAVAILABLE)

        if selector.observation_id not in snapshot.observation_ids:
            return self._integrity_failure()
        expected_fingerprint = self._store.observation_fingerprint_by_id.get(record.observation_id)
        actual_fingerprint = _content_sha256(_record_content_payload(record))
        if (
            expected_fingerprint is None
            or actual_fingerprint != expected_fingerprint
            or record.observation_payload_sha256 != expected_fingerprint
            or record.document_id != revision.document_id
            or record.revision_id != revision.revision_id
            or record.source_sha256 != revision.source_sha256
            or record.snapshot_id != snapshot.snapshot_id
            or record.producer_generation != snapshot.producer_generation
        ):
            return self._integrity_failure()

        for parent_id in record.derivation_parent_ids:
            if (
                parent_id not in self._store.observation_fingerprint_by_id
                or self._store.observation_revision_by_id.get(parent_id) != revision.revision_id
            ):
                return self._blocked(LINEAGE_UNAVAILABLE)

        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=SOURCE_OBSERVATION_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=("producer_owned_source_observation_resolved",),
            source_revision=replace(revision),
            snapshot=replace(snapshot),
            observation=replace(record),
        )


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
    "SourceObservationAuthority",
    "SourceObservationAuthorityResult",
    "SourceObservationInput",
    "SourceObservationProducer",
    "SourceObservationRecord",
    "SourceRevisionRecord",
]
