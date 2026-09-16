"""TEST-ONLY interface scaffold for producer-owned physical opening height."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
)
from pb_schedule_row_height_authority import ScheduleRowHeightAuthority
from pb_source_visibility_authority import SourceVisibilityProducer

OPENING_HEIGHT_SCHEMA_VERSION = "1.0.0"
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


class OpeningHeightAuthority:
    def __init__(
        self,
        results: Mapping[_Key, OpeningHeightResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("OpeningHeightAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        if type(selector) is not OpeningHeightSelector:
            raise TypeError("selector must be OpeningHeightSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return OpeningHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["opening_height_no_evidence"]),
            evidence=None,
        )


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
            raise TypeError(
                "OpeningHeightProducer must be obtained from from_authorities()"
            )
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
    ) -> OpeningHeightProducer:
        return cls(
            source_visibility_producer,
            binding_authority,
            row_height_authority,
            _seal=_PRODUCER_SEAL,
        )

    def publish_scope(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        if type(selector) is not OpeningHeightSelector:
            raise TypeError("selector must be OpeningHeightSelector")
        return OpeningHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["not_implemented"]),
            evidence=None,
        )

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )
