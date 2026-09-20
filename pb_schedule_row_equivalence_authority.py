"""Producer-owned schedule-row equivalence authority.

This authority answers one narrow question: do two authenticated schedule-row
observation sets represent the same rendered source row?

Positive equivalence requires the same immutable source scope and an exact
match of the authenticated trusted text + geometry multiset for every word.
Equal mark/count/dimensions alone never prove equivalence.

This is intended to collapse duplicate PDF text-layer representations of the
same visual row while keeping genuinely repeated schedule rows distinct.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SCHEDULE_ROW_EQUIVALENCE_SCHEMA_VERSION = "1.0.0"

SCHEDULE_ROW_EQUIVALENCE_RESOLVED = "schedule_row_equivalence_resolved"
SCHEDULE_ROW_EQUIVALENCE_DISTINCT = "schedule_row_equivalence_distinct"
SCHEDULE_ROW_EQUIVALENCE_UNAVAILABLE = "schedule_row_equivalence_unavailable"
SCHEDULE_ROW_EQUIVALENCE_SCOPE_MISMATCH = "schedule_row_equivalence_scope_mismatch"
SCHEDULE_ROW_EQUIVALENCE_TEXT_UNRESOLVED = "schedule_row_equivalence_text_unresolved"

_AUTHORITY_SEAL = object()


@dataclass(frozen=True)
class ScheduleRowSelector:
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
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not self.schedule_row_observation_ids:
            raise ValueError("schedule_row_observation_ids must be non-empty")
        cleaned = tuple(
            str(value).strip()
            for value in self.schedule_row_observation_ids
            if str(value).strip()
        )
        if len(cleaned) != len(self.schedule_row_observation_ids):
            raise ValueError("schedule_row_observation_ids contain empty values")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("schedule_row_observation_ids must be unique")
        object.__setattr__(self, "schedule_row_observation_ids", tuple(sorted(cleaned)))


@dataclass(frozen=True)
class ScheduleRowEquivalenceResult:
    status: EvidenceResolutionStatus
    proven_same: bool
    reason_codes: tuple[str, ...]
    schema_version: str = SCHEDULE_ROW_EQUIVALENCE_SCHEMA_VERSION


class ScheduleRowEquivalenceAuthority:
    """Resolve row equivalence from producer-owned text-integrity evidence."""

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "ScheduleRowEquivalenceAuthority must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source_visibility_producer = source_visibility_producer

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "ScheduleRowEquivalenceAuthority":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_AUTHORITY_SEAL)

    @staticmethod
    def _scope(selector: ScheduleRowSelector) -> tuple[str, str, str, str, str]:
        return (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.schedule_page_id,
        )

    def _canonical_row(
        self,
        selector: ScheduleRowSelector,
    ) -> Optional[tuple[tuple[str, tuple[float, ...]], ...]]:
        text_integrity = self._source_visibility_producer.text_integrity_authority()
        cells: list[tuple[str, tuple[float, ...]]] = []
        for observation_id in selector.schedule_row_observation_ids:
            result = text_integrity.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.trusted_text is None
                or result.receipt is None
                or result.receipt.page_id != selector.schedule_page_id
            ):
                return None
            cells.append(
                (
                    str(result.trusted_text),
                    tuple(float(value) for value in result.receipt.geometry),
                )
            )
        return tuple(sorted(cells, key=repr))

    def compare(
        self,
        left: ScheduleRowSelector,
        right: ScheduleRowSelector,
    ) -> ScheduleRowEquivalenceResult:
        if type(left) is not ScheduleRowSelector or type(right) is not ScheduleRowSelector:
            raise TypeError("left/right must be ScheduleRowSelector")

        if self._scope(left) != self._scope(right):
            return ScheduleRowEquivalenceResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                proven_same=False,
                reason_codes=(
                    SCHEDULE_ROW_EQUIVALENCE_DISTINCT,
                    SCHEDULE_ROW_EQUIVALENCE_SCOPE_MISMATCH,
                ),
            )

        left_row = self._canonical_row(left)
        right_row = self._canonical_row(right)
        if left_row is None or right_row is None:
            return ScheduleRowEquivalenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proven_same=False,
                reason_codes=(SCHEDULE_ROW_EQUIVALENCE_TEXT_UNRESOLVED,),
            )

        if left_row == right_row:
            return ScheduleRowEquivalenceResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                proven_same=True,
                reason_codes=(SCHEDULE_ROW_EQUIVALENCE_RESOLVED,),
            )

        return ScheduleRowEquivalenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proven_same=False,
            reason_codes=(SCHEDULE_ROW_EQUIVALENCE_DISTINCT,),
        )


__all__ = [
    "SCHEDULE_ROW_EQUIVALENCE_DISTINCT",
    "SCHEDULE_ROW_EQUIVALENCE_RESOLVED",
    "SCHEDULE_ROW_EQUIVALENCE_SCHEMA_VERSION",
    "SCHEDULE_ROW_EQUIVALENCE_SCOPE_MISMATCH",
    "SCHEDULE_ROW_EQUIVALENCE_TEXT_UNRESOLVED",
    "SCHEDULE_ROW_EQUIVALENCE_UNAVAILABLE",
    "ScheduleRowEquivalenceAuthority",
    "ScheduleRowEquivalenceResult",
    "ScheduleRowSelector",
]
