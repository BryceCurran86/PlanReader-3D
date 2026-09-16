from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


@dataclasses.dataclass(frozen=True)
class CrossSheetOpeningRegistrationRecord:
    record_id: str
    schema_version: str
    plan_opening_record_id: str
    elevation_observation_ids: tuple[str, ...]
    plan_document_id: str
    elevation_document_id: str
    # etc...


@dataclasses.dataclass(frozen=True)
class CrossSheetOpeningRegistrationResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: CrossSheetOpeningRegistrationRecord | None
    schema_version: str = "1.0.0"


class CrossSheetOpeningRegistrationSelector:
    """Selects an EXACT registration between a plan physical opening and an elevation/section observation."""
    def __init__(
        self,
        *,
        plan_opening_record_id: str,
        elevation_document_id: str,
        elevation_revision_id: str,
        elevation_source_sha256: str,
        elevation_snapshot_id: str,
        elevation_observation_id: str,  # The observation of the elevation marker/object
        decision_scope_id: str,
    ) -> None:
        self.plan_opening_record_id = plan_opening_record_id
        self.elevation_document_id = elevation_document_id
        self.elevation_revision_id = elevation_revision_id
        self.elevation_source_sha256 = elevation_source_sha256
        self.elevation_snapshot_id = elevation_snapshot_id
        self.elevation_observation_id = elevation_observation_id
        self.decision_scope_id = decision_scope_id

    @property
    def key(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.plan_opening_record_id,
            self.elevation_document_id,
            self.elevation_revision_id,
            self.elevation_source_sha256,
            self.elevation_snapshot_id,
            self.elevation_observation_id,
            self.decision_scope_id,
        )


_AUTHORITY_SEAL = object()


class CrossSheetOpeningRegistrationAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, str, str, str, str, str, str], CrossSheetOpeningRegistrationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("Authority is producer-owned")
        self._results = dict(results)

    def resolve(self, selector: CrossSheetOpeningRegistrationSelector) -> CrossSheetOpeningRegistrationResult:
        if selector.key in self._results:
            return self._results[selector.key]
        return CrossSheetOpeningRegistrationResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=("cross_sheet_registration_unresolved",),
            record=None,
        )


class CrossSheetOpeningRegistrationProducer:
    def __init__(self, source_visibility: SourceVisibilityProducer, *, _seal: object = None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("Producer is system-owned")
        self._source_visibility = source_visibility
        self._results: dict[tuple[str, str, str, str, str, str, str], CrossSheetOpeningRegistrationResult] = {}

    @classmethod
    def from_source_visibility_producer(cls, src: SourceVisibilityProducer) -> CrossSheetOpeningRegistrationProducer:
        return cls(src, _seal=_AUTHORITY_SEAL)

    def authority(self) -> CrossSheetOpeningRegistrationAuthority:
        return CrossSheetOpeningRegistrationAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def publish_scope(self, selector: CrossSheetOpeningRegistrationSelector) -> CrossSheetOpeningRegistrationResult:
        raise NotImplementedError("Draft test contract - production not implemented yet")
