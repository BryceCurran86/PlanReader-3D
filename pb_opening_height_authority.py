"""Opening Height Authority (Item 2 - Frozen Validator Scaffold)"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority, ScheduleOpeningInstanceBindingSelector
)
from pb_schedule_row_height_authority import ScheduleRowHeightAuthority, ScheduleRowHeightSelector
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
        binding_selector = ScheduleOpeningInstanceBindingSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            opening_record_id=selector.opening_record_id,
        )
        binding_result = self._binding_authority.resolve(binding_selector)
        if binding_result.status != EvidenceResolutionStatus.CORROBORATED or binding_result.record is None:
            # Re-emit upstream failure status (which propagates CONFLICTs vs ABSTAINs correctly)
            return OpeningHeightResult(
                status=binding_result.status,
                reason_codes=frozenset(["opening_height_upstream_abstained" if binding_result.status == EvidenceResolutionStatus.ABSTAINED else "opening_height_upstream_conflict"]),
                evidence=None,
            )
            
        row_height_selector = ScheduleRowHeightSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            schedule_page_id=binding_result.record.schedule_page_id,
            schedule_row_observation_ids=binding_result.record.schedule_row_observation_ids,
        )
        row_height_result = self._row_height_authority.resolve(row_height_selector)
        
        if row_height_result.status != EvidenceResolutionStatus.CORROBORATED or row_height_result.evidence is None:
            # Bubble up reason codes from row height
            return OpeningHeightResult(
                status=row_height_result.status,
                reason_codes=row_height_result.reason_codes,
                evidence=None,
            )
            
        evidence = OpeningHeightEvidence(
            opening_record_id=selector.opening_record_id,
            height_mm=row_height_result.evidence.height_mm,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            schedule_row_observation_ids=row_height_result.evidence.schedule_row_observation_ids,
        )
        
        return OpeningHeightResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=frozenset(["opening_height_resolved"]),
            evidence=evidence,
        )

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(self._results, _seal=_AUTHORITY_SEAL)