from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_schedule_opening_instance_binding_authority import _row_groups_for_page, _schedule_entries_for_page

@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, str, str, str, tuple[str, ...]]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.schedule_page_id,
            self.schedule_row_observation_ids,
        )

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
        results: Mapping[tuple[str, str, str, str, str, tuple[str, ...]], ScheduleRowHeightResult],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("Authority is producer-owned")
        self._results = dict(results)

    def resolve(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        if selector.key in self._results:
            return self._results[selector.key]
        return ScheduleRowHeightResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=frozenset(["schedule_row_height_no_evidence"]),
            evidence=None,
        )

def _blocked(status: EvidenceResolutionStatus, reason: str) -> ScheduleRowHeightResult:
    return ScheduleRowHeightResult(
        status=status,
        reason_codes=frozenset([reason]),
        evidence=None,
    )

class ScheduleRowHeightProducer:
    def __init__(self, visibility_producer: SourceVisibilityProducer) -> None:
        self._visibility_producer = visibility_producer
        self._results: dict[tuple[str, str, str, str, str, tuple[str, ...]], ScheduleRowHeightResult] = {}

    @classmethod
    def from_source_visibility_producer(cls, visibility_producer: SourceVisibilityProducer) -> ScheduleRowHeightProducer:
        return cls(visibility_producer)

    def publish_scope(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        key = selector.key
        if key in self._results:
            return self._results[key]
            
        published = self._visibility_producer.published_snapshot_for_revision(selector.revision_id)
        if published is None or published.revision.document_id != selector.document_id or published.snapshot.snapshot_id != selector.snapshot_id:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "schedule_row_height_upstream_abstained"))

        text_integrity = self._visibility_producer.text_integrity_authority()
        
        page_words: list[tuple[str, str, tuple[float, ...]]] = []
        for observation_id in published.text_observation_ids:
            text_result = text_integrity.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                text_result.status is not EvidenceResolutionStatus.CORROBORATED
                or text_result.trusted_text is None
                or text_result.receipt is None
            ):
                continue
            if text_result.receipt.page_id != selector.schedule_page_id:
                continue
            page_words.append(
                (
                    observation_id,
                    text_result.trusted_text,
                    tuple(float(value) for value in text_result.receipt.geometry),
                )
            )
            
        if not page_words:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "schedule_row_height_upstream_abstained"))
            
        try:
            page_no = int(selector.schedule_page_id)
        except (TypeError, ValueError):
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "schedule_row_height_upstream_abstained"))
            
        page_rows = _row_groups_for_page(page_words)
        if not page_rows:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "schedule_row_height_upstream_abstained"))
            
        target_ids_set = set(selector.schedule_row_observation_ids)
        target_entry = None
        
        for entry, ids in _schedule_entries_for_page(page_rows, page_no):
            if set(ids) == target_ids_set:
                target_entry = entry
                break
                
        if target_entry is None:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "schedule_row_height_upstream_abstained"))
            
        # Check height field semantics
        raw_text = " ".join([t[1] for t in page_words if t[0] in target_ids_set])
        if "/" in raw_text and any(c.isdigit() for c in raw_text):
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "opening_height_ambiguous_units"))

        if target_entry.height_mm is None:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, "opening_height_missing_field"))
            
        evidence = ScheduleRowHeightEvidence(
            schedule_row_observation_ids=selector.schedule_row_observation_ids,
            height_mm=float(target_entry.height_mm),
            raw_text="...", # We can extract the raw text if needed
            units="mm",
            dimension_basis=target_entry.dimension_basis,
            basis_source=target_entry.basis_source,
        )
        
        return self._store(
            key,
            ScheduleRowHeightResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=frozenset(["schedule_row_height_resolved"]),
                evidence=evidence,
            )
        )

    def _store(self, key: tuple[str, str, str, str, str, tuple[str, ...]], result: ScheduleRowHeightResult) -> ScheduleRowHeightResult:
        self._results[key] = result
        return result

    def authority(self) -> ScheduleRowHeightAuthority:
        return ScheduleRowHeightAuthority(self._results, _seal=_AUTHORITY_SEAL)
