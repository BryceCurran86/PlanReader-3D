"""Opening Height Authority (Item 2 - Frozen Validator Scaffold)"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
)
from pb_schedule_row_height_authority import ScheduleRowHeightAuthority
from pb_source_visibility_authority import SourceVisibilityProducer


@dataclasses.dataclass(frozen=True)
class OpeningHeightEvidence:
    """The genuine proven height of an opening, authenticated via schedule binding."""
    opening_record_id: str
    height_mm: float
    # Lineage
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    # Provenance
    schedule_row_observation_ids: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class OpeningHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: OpeningHeightEvidence | None = None


@dataclasses.dataclass(frozen=True)
class OpeningHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.opening_record_id,
        )


_AUTHORITY_SEAL = object()


class OpeningHeightAuthority:
    def __init__(self, results: Mapping[tuple[str, str, str, str, str, str], OpeningHeightResult], *, _seal: object) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("Authority is producer-owned")
        self._results = dict(results)

    def resolve(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        if selector.key in self._results:
            return self._results[selector.key]
        return OpeningHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["opening_height_no_evidence"]),
            evidence=None,
        )


class OpeningHeightProducer:
    def __init__(
        self,
        src: SourceVisibilityProducer,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_height_authority: ScheduleRowHeightAuthority,
    ) -> None:
        self._src = src
        self._binding_authority = binding_authority
        self._row_height_authority = row_height_authority
        self._results: dict[tuple[str, str, str, str, str, str], OpeningHeightResult] = {}

    @classmethod
    def from_authorities(
        cls,
        src: SourceVisibilityProducer,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_height_authority: ScheduleRowHeightAuthority,
    ) -> OpeningHeightProducer:
        return cls(src, binding_authority, row_height_authority)

    def publish_scope(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        """Publishes the height of a specific physical opening instance."""
        # For the validator test phase, this simply returns an unimplemented response.
        # Production (Item 3) will actually check binding_authority and build evidence.
        return OpeningHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["not_implemented"]),
            evidence=None,
        )

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(self._results, _seal=_AUTHORITY_SEAL)