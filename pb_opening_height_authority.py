"""Producer-owned physical opening height authority.

A physical opening height is published only when two independent upstream
propositions agree on the same immutable lineage:

1. ``ScheduleOpeningInstanceBindingAuthority`` proves which exact schedule row
   governs the exact G17 physical opening instance.
2. ``ScheduleRowHeightAuthority`` proves that exact row carries an explicit
   rough/structural-opening HEIGHT with source-backed unit semantics.

Neither raw schedule numbers nor caller-provided heights are accepted here.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_schedule_row_height_authority import (
    ScheduleRowHeightAuthority,
    ScheduleRowHeightSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer

OPENING_HEIGHT_SCHEMA_VERSION = "1.0.0"
OPENING_HEIGHT_RESOLVED = "opening_height_resolved"
OPENING_HEIGHT_SOURCE_SCOPE_UNAVAILABLE = "opening_height_source_scope_unavailable"
OPENING_HEIGHT_UPSTREAM_INCONSISTENT = "opening_height_upstream_inconsistent"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


@dataclasses.dataclass(frozen=True)
class OpeningHeightEvidence:
    opening_record_id: str
    height_mm: float
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    schedule_header_observation_ids: tuple[str, ...]
    units: str
    source_units: str
    dimension_basis: str
    basis_source: str
    schema_version: str = OPENING_HEIGHT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class OpeningHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: OpeningHeightEvidence | None = None
    schema_version: str = OPENING_HEIGHT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class OpeningHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
            "opening_record_id",
        ):
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.opening_record_id,
        )


def _blocked(status: EvidenceResolutionStatus, *reasons: str) -> OpeningHeightResult:
    cleaned = frozenset(str(reason) for reason in reasons if str(reason))
    return OpeningHeightResult(
        status=status,
        reason_codes=cleaned or frozenset(["opening_height_unavailable"]),
        evidence=None,
    )


class OpeningHeightAuthority:
    def __init__(self, results: Mapping[_Key, OpeningHeightResult], *, _seal: object = None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("OpeningHeightAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        if type(selector) is not OpeningHeightSelector:
            raise TypeError("selector must be OpeningHeightSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _blocked(EvidenceResolutionStatus.ABSTAINED, "opening_height_no_evidence")


class OpeningHeightProducer:
    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_height_authority: ScheduleRowHeightAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("OpeningHeightProducer must be obtained from from_authorities()")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        if type(binding_authority) is not ScheduleOpeningInstanceBindingAuthority:
            raise TypeError("binding_authority must be producer-owned")
        if type(row_height_authority) is not ScheduleRowHeightAuthority:
            raise TypeError("row_height_authority must be producer-owned")
        self._source_visibility_producer = source_visibility_producer
        self._binding_authority = binding_authority
        self._row_height_authority = row_height_authority
        self._results: dict[_Key, OpeningHeightResult] = {}

    @classmethod
    def from_authorities(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_height_authority: ScheduleRowHeightAuthority,
    ) -> "OpeningHeightProducer":
        return cls(
            source_visibility_producer,
            binding_authority,
            row_height_authority,
            _seal=_PRODUCER_SEAL,
        )

    def publish_scope(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        if type(selector) is not OpeningHeightSelector:
            raise TypeError("selector must be OpeningHeightSelector")
        key = selector.key
        existing = self._results.get(key)
        if existing is not None:
            return existing

        published = self._source_visibility_producer.published_snapshot_for_revision(selector.revision_id)
        if (
            published is None
            or published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
        ):
            return self._store(
                key,
                _blocked(EvidenceResolutionStatus.ABSTAINED, OPENING_HEIGHT_SOURCE_SCOPE_UNAVAILABLE),
            )

        binding_selector = ScheduleOpeningInstanceBindingSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            opening_record_id=selector.opening_record_id,
        )
        binding_result = self._binding_authority.resolve(binding_selector)
        if binding_result.status is not EvidenceResolutionStatus.CORROBORATED or binding_result.record is None:
            return self._store(key, _blocked(binding_result.status, *binding_result.reason_codes))
        binding = binding_result.record
        if (
            binding.document_id != selector.document_id
            or binding.revision_id != selector.revision_id
            or binding.source_sha256 != selector.source_sha256
            or binding.snapshot_id != selector.snapshot_id
            or binding.decision_scope_id != selector.decision_scope_id
            or binding.opening_record_id != selector.opening_record_id
        ):
            return self._store(
                key,
                _blocked(EvidenceResolutionStatus.CONFLICT, OPENING_HEIGHT_UPSTREAM_INCONSISTENT),
            )

        row_height_selector = ScheduleRowHeightSelector(
            document_id=binding.document_id,
            revision_id=binding.revision_id,
            source_sha256=binding.source_sha256,
            snapshot_id=binding.snapshot_id,
            schedule_page_id=binding.schedule_page_id,
            schedule_row_observation_ids=binding.schedule_row_observation_ids,
        )
        row_height_result = self._row_height_authority.resolve(row_height_selector)
        if row_height_result.status is not EvidenceResolutionStatus.CORROBORATED or row_height_result.evidence is None:
            return self._store(key, _blocked(row_height_result.status, *row_height_result.reason_codes))
        row_height = row_height_result.evidence
        if (
            row_height.schedule_page_id != binding.schedule_page_id
            or tuple(sorted(row_height.schedule_row_observation_ids)) != tuple(sorted(binding.schedule_row_observation_ids))
            or row_height.units != "mm"
            or row_height.dimension_basis != "rough_opening"
        ):
            return self._store(
                key,
                _blocked(EvidenceResolutionStatus.CONFLICT, OPENING_HEIGHT_UPSTREAM_INCONSISTENT),
            )

        result = OpeningHeightResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=frozenset([OPENING_HEIGHT_RESOLVED]),
            evidence=OpeningHeightEvidence(
                opening_record_id=binding.opening_record_id,
                height_mm=row_height.height_mm,
                document_id=binding.document_id,
                revision_id=binding.revision_id,
                source_sha256=binding.source_sha256,
                snapshot_id=binding.snapshot_id,
                schedule_page_id=binding.schedule_page_id,
                schedule_row_observation_ids=row_height.schedule_row_observation_ids,
                schedule_header_observation_ids=row_height.header_observation_ids,
                units=row_height.units,
                source_units=row_height.source_units,
                dimension_basis=row_height.dimension_basis,
                basis_source=row_height.basis_source,
            ),
        )
        return self._store(key, result)

    def _store(self, key: _Key, result: OpeningHeightResult) -> OpeningHeightResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("opening-height producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(MappingProxyType(dict(self._results)), _seal=_AUTHORITY_SEAL)


__all__ = [
    "OPENING_HEIGHT_RESOLVED",
    "OPENING_HEIGHT_SCHEMA_VERSION",
    "OPENING_HEIGHT_SOURCE_SCOPE_UNAVAILABLE",
    "OPENING_HEIGHT_UPSTREAM_INCONSISTENT",
    "OpeningHeightAuthority",
    "OpeningHeightEvidence",
    "OpeningHeightProducer",
    "OpeningHeightResult",
    "OpeningHeightSelector",
]
