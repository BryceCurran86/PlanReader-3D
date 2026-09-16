"""TEST-ONLY interface scaffold for schedule-row height semantics.

Production is intentionally absent on the frozen-validator branch.  The types
and public surface define the authority contract that production must satisfy.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION = "1.0.0"
_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, tuple[str, ...]]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "schedule_page_id",
        ):
            _require_nonempty(getattr(self, name), name)
        if not self.schedule_row_observation_ids:
            raise ValueError("schedule_row_observation_ids must be non-empty")
        if len(set(self.schedule_row_observation_ids)) != len(self.schedule_row_observation_ids):
            raise ValueError("schedule_row_observation_ids must be unique")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.schedule_page_id,
            tuple(sorted(self.schedule_row_observation_ids)),
        )


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightEvidence:
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    header_observation_ids: tuple[str, ...]
    height_mm: float
    raw_text: str
    units: str
    source_units: str
    dimension_basis: str
    basis_source: str
    schema_version: str = SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: ScheduleRowHeightEvidence | None = None
    schema_version: str = SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION


class ScheduleRowHeightAuthority:
    def __init__(
        self,
        results: Mapping[_Key, ScheduleRowHeightResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("ScheduleRowHeightAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        if type(selector) is not ScheduleRowHeightSelector:
            raise TypeError("selector must be ScheduleRowHeightSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return ScheduleRowHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["schedule_row_height_no_evidence"]),
            evidence=None,
        )


class ScheduleRowHeightProducer:
    def __init__(
        self,
        visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "ScheduleRowHeightProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("visibility_producer must be producer-owned")
        self._visibility_producer = visibility_producer
        self._results: dict[_Key, ScheduleRowHeightResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        visibility_producer: SourceVisibilityProducer,
    ) -> ScheduleRowHeightProducer:
        return cls(visibility_producer, _seal=_PRODUCER_SEAL)

    def publish_scope(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        if type(selector) is not ScheduleRowHeightSelector:
            raise TypeError("selector must be ScheduleRowHeightSelector")
        return ScheduleRowHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["not_implemented"]),
            evidence=None,
        )

    def authority(self) -> ScheduleRowHeightAuthority:
        return ScheduleRowHeightAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )
