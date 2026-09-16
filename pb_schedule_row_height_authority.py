from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import SourceObservationAuthority

@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightEvidence:
    """Proven semantic height extracted directly from schedule row observations."""
    schedule_row_observation_ids: tuple[str, ...]
    height_mm: float
    raw_text: str
    units: str
    dimension_basis: str
    basis_source: str

@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: ScheduleRowHeightEvidence | None = None

_AUTHORITY_SEAL = object()

class ScheduleRowHeightAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], ScheduleRowHeightResult],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("Authority is producer-owned")
        self._results = dict(results)

    def resolve(self, schedule_row_observation_ids: tuple[str, ...]) -> ScheduleRowHeightResult:
        if schedule_row_observation_ids in self._results:
            return self._results[schedule_row_observation_ids]
        return ScheduleRowHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["schedule_row_height_no_evidence"]),
            evidence=None,
        )

class ScheduleRowHeightProducer:
    def __init__(self, observation_authority: SourceObservationAuthority) -> None:
        self._observation_authority = observation_authority
        self._results: dict[tuple[str, ...], ScheduleRowHeightResult] = {}

    @classmethod
    def from_observation_authority(cls, observation_authority: SourceObservationAuthority) -> ScheduleRowHeightProducer:
        return cls(observation_authority)

    def publish_scope(self, schedule_row_observation_ids: tuple[str, ...]) -> ScheduleRowHeightResult:
        """Publishes proven height semantics from raw schedule row observations."""
        return ScheduleRowHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["not_implemented"]),
            evidence=None,
        )

    def authority(self) -> ScheduleRowHeightAuthority:
        return ScheduleRowHeightAuthority(self._results, _seal=_AUTHORITY_SEAL)
