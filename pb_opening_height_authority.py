"""Opening Height Authority (TEST/VALIDATOR BRANCH ONLY)"""
from __future__ import annotations

from dataclasses import dataclass

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


@dataclass(frozen=True)
class ScheduleOpeningInstanceBindingRecord:
    # Dummy mock of #383 record for validator lane
    tag_mark: str
    schedule_row_width_mm: float
    schedule_row_height_mm: float
    opening_record_id: str
    page_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class OpeningHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: OpeningHeightEvidence | None = None


@dataclass(frozen=True)
class OpeningHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str


class OpeningHeightAuthority:
    def __init__(self, _seal: object) -> None:
        pass

    def resolve(self, selector: OpeningHeightSelector) -> OpeningHeightResult:
        raise NotImplementedError("Validator only")


class OpeningHeightProducer:
    @classmethod
    def from_source_visibility_producer(
        cls, src: SourceVisibilityProducer
    ) -> OpeningHeightProducer:
        return cls()

    def publish_scope(self, selector: OpeningHeightSelector, decision_scope_id: str) -> OpeningHeightResult:
        raise NotImplementedError("Validator only")

    def authority(self) -> OpeningHeightAuthority:
        return OpeningHeightAuthority(_seal=object())