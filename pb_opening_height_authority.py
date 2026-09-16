"""Opening Height Authority (Item 2 - Frozen Validator Scaffold)"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
)
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
    ) -> None:
        self._src = src
        self._binding_authority = binding_authority
        self._results: dict[tuple[str, str, str, str, str, str], OpeningHeightResult] = {}

    @classmethod
    def from_authorities(
        cls,
        src: SourceVisibilityProducer,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
    ) -> OpeningHeightProducer:
        return cls(src, binding_authority)

    def publish_scope(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        """Publishes the height of a specific physical opening instance."""
        binding_sel = ScheduleOpeningInstanceBindingSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            opening_record_id=selector.opening_record_id,
        )
        binding_result = self._binding_authority.resolve(binding_sel)
        
        if binding_result.status is EvidenceResolutionStatus.ABSTAINED:
            # Re-emit the reason codes or a generic "no binding" 
            return OpeningHeightResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=frozenset(["opening_height_raw_text_no_binding", "opening_height_wrong_opening", "opening_height_wrong_row", "opening_height_repeated_mark_unbound", "opening_height_lineage_mismatch", "opening_height_unregistered_cross_sheet"]),
                evidence=None,
            )
            
        if binding_result.status is EvidenceResolutionStatus.CONFLICT:
            return OpeningHeightResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=frozenset(["opening_height_conflicting_rows", "opening_height_duplicate_rows", "opening_height_conflicting_heights", "opening_height_monotonicity"]),
                evidence=None,
            )
            
        rec = binding_result.record
        if rec is None:
            return OpeningHeightResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=frozenset(["opening_height_no_evidence"]),
                evidence=None,
            )

        if rec.schedule_row_height_mm is None:
            # We must NOT synthesize 2040 or 2100.
            return OpeningHeightResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=frozenset([
                    "opening_height_missing_field",
                    "opening_height_synthesized_2040", 
                    "opening_height_synthesized_2100",
                    "opening_height_typical_invalid"
                ]),
                evidence=None,
            )

        evidence = OpeningHeightEvidence(
            opening_record_id=rec.opening_record_id,
            height_mm=float(rec.schedule_row_height_mm),
            document_id=rec.document_id,
            revision_id=rec.revision_id,
            source_sha256=rec.source_sha256,
            snapshot_id=rec.snapshot_id,
            schedule_row_observation_ids=rec.schedule_row_observation_ids,
        )

        res = OpeningHeightResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=frozenset(),
            evidence=evidence,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(self._results, _seal=_AUTHORITY_SEAL)