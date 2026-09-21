"""Producer-owned semantic opening enumeration authority (Item 35).

This layer enumerates physical-opening entities from the COMPLETE authenticated
visible-segment universe owned by SourceVisibilityProducer. It deliberately
reuses PhysicalOpeningAuthority.prove_existence() as the only positive
physical-existence proposition; OCR text, schedule rows, caller candidate lists,
proximity ranking, and expected quantities never create an opening here.

V1 has two deliberately separate completeness concepts:

1. structural_enumeration_complete means every authority-visible segment in
   the exact document snapshot participated in at least one independently proven
   G17 physical-opening record and no source/physical conflict occurred.
2. physical_opening_universe_complete remains False in V1. Exhaustively
   enumerating one known structural representation is not proof that every
   possible physical-opening representation has been covered. Commercial count
   therefore remains fail-closed until a later authority proves that stronger
   proposition.

The useful output of this authority is the producer-owned semantic inventory:
unique physical-opening record ids, one representative source observation per
opening, the full support-observation set, and every residual visible observation
that still requires semantic disposition.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SEMANTIC_OPENING_ENUMERATION_SCHEMA_VERSION = "1.0.0"

SEMANTIC_OPENING_ENUMERATION_RESOLVED = "semantic_opening_enumeration_resolved"
SEMANTIC_OPENING_ENUMERATION_UNAVAILABLE = "semantic_opening_enumeration_unavailable"
SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE = (
    "semantic_opening_source_coverage_incomplete"
)
SEMANTIC_OPENING_VISIBLE_OBSERVATION_UNRESOLVED = (
    "semantic_opening_visible_observation_unresolved"
)
SEMANTIC_OPENING_PHYSICAL_CONFLICT = "semantic_opening_physical_conflict"
SEMANTIC_OPENING_LINEAGE_MISMATCH = "semantic_opening_lineage_mismatch"
SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE = (
    "semantic_opening_residual_source_evidence"
)
SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE = (
    "semantic_opening_structural_enumeration_complete"
)
SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN = (
    "semantic_opening_universe_exhaustiveness_unproven"
)
SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS = "semantic_opening_no_visible_segments"
SEMANTIC_OPENING_PRODUCER_EQUIVOCATION = "semantic_opening_producer_equivocation"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _ordered_unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class SemanticOpeningEnumerationSelector:
    """Consumer lookup key. No evidence-shaped inputs are accepted."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
        ):
            if not _clean(getattr(self, name)):
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
        )


@dataclass(frozen=True)
class SemanticOpeningEnumerationRecord:
    """Immutable semantic inventory for one exact producer-owned document scope."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    decision_scope_kind: str
    page_ids: tuple[str, ...]
    visible_observation_ids: tuple[str, ...]
    physical_opening_record_ids: tuple[str, ...]
    representative_observation_ids: tuple[str, ...]
    opening_support_observation_ids: tuple[str, ...]
    residual_visible_observation_ids: tuple[str, ...]
    conflict_observation_ids: tuple[str, ...]
    structural_enumeration_complete: bool
    physical_opening_universe_complete: bool
    reason_codes: tuple[str, ...]
    schema_version: str = SEMANTIC_OPENING_ENUMERATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must be non-empty")
        if self.decision_scope_kind not in {"document", "pages"}:
            raise ValueError(
                "v1 semantic enumeration supports document or explicit page scope only"
            )
        if len(set(self.physical_opening_record_ids)) != len(
            self.physical_opening_record_ids
        ):
            raise ValueError("physical_opening_record_ids must be unique")
        if len(self.representative_observation_ids) != len(
            self.physical_opening_record_ids
        ):
            raise ValueError(
                "representative_observation_ids must map one-to-one to physical openings"
            )
        if set(self.representative_observation_ids) - set(
            self.opening_support_observation_ids
        ):
            raise ValueError(
                "representative observations must be opening-support observations"
            )
        if set(self.opening_support_observation_ids) & set(
            self.residual_visible_observation_ids
        ):
            raise ValueError(
                "opening support and residual visible observations must be disjoint"
            )
        if self.physical_opening_universe_complete:
            raise ValueError(
                "v1 cannot prove full physical-opening universe exhaustiveness"
            )


@dataclass(frozen=True)
class SemanticOpeningEnumerationResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[SemanticOpeningEnumerationRecord] = None
    schema_version: str = SEMANTIC_OPENING_ENUMERATION_SCHEMA_VERSION


class SemanticOpeningEnumerationAuthority:
    """Read-only exact-scope authority over producer-owned semantic inventories."""

    def __init__(
        self,
        results: Mapping[_Key, SemanticOpeningEnumerationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "SemanticOpeningEnumerationAuthority must be producer-owned"
            )
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: SemanticOpeningEnumerationSelector,
    ) -> SemanticOpeningEnumerationResult:
        if type(selector) is not SemanticOpeningEnumerationSelector:
            raise TypeError(
                "selector must be SemanticOpeningEnumerationSelector"
            )
        return self._results.get(
            selector.key,
            SemanticOpeningEnumerationResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SEMANTIC_OPENING_ENUMERATION_UNAVAILABLE,),
                record=None,
            ),
        )


class SemanticOpeningEnumerationProducer:
    """Trusted document-scope semantic opening enumerator.

    Callers select only a revision and name the decision scope. The producer
    obtains the complete visible-observation universe directly from its
    SourceVisibilityProducer; there is no API for supplying candidate ids,
    counts, marks, radii, row groups, or a narrowed observation subset.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "SemanticOpeningEnumerationProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source_visibility_producer = source_visibility_producer
        self._results: dict[_Key, SemanticOpeningEnumerationResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "SemanticOpeningEnumerationProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> SemanticOpeningEnumerationAuthority:
        return SemanticOpeningEnumerationAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: SemanticOpeningEnumerationSelector,
        result: SemanticOpeningEnumerationResult,
    ) -> SemanticOpeningEnumerationResult:
        prior = self._results.get(selector.key)
        if prior is not None and prior != result:
            raise RuntimeError(SEMANTIC_OPENING_PRODUCER_EQUIVOCATION)
        self._results[selector.key] = result
        return result

    def publish_document_scope(
        self,
        *,
        revision_id: str,
        decision_scope_id: str,
    ) -> SemanticOpeningEnumerationResult:
        """Enumerate the exact complete document snapshot for revision_id."""

        return self._publish_scope(
            revision_id=revision_id,
            decision_scope_id=decision_scope_id,
            decision_scope_kind="document",
            page_ids=None,
        )

    def publish_page_scope(
        self,
        *,
        revision_id: str,
        decision_scope_id: str,
        page_ids: tuple[str, ...],
    ) -> SemanticOpeningEnumerationResult:
        """Enumerate only an explicit set of source page addresses.

        Page IDs select scope only. They cannot inject observations,
        candidates, marks, counts, or expected quantities. The producer still
        obtains every visible observation from its own source snapshot and
        independently re-proves physical opening existence.
        """

        cleaned_pages = tuple(
            sorted(
                {_clean(page_id) for page_id in page_ids if _clean(page_id)},
                key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
            )
        )
        if not cleaned_pages:
            raise ValueError("page_ids must contain at least one page")
        return self._publish_scope(
            revision_id=revision_id,
            decision_scope_id=decision_scope_id,
            decision_scope_kind="pages",
            page_ids=cleaned_pages,
        )

    def _publish_scope(
        self,
        *,
        revision_id: str,
        decision_scope_id: str,
        decision_scope_kind: str,
        page_ids: Optional[tuple[str, ...]],
    ) -> SemanticOpeningEnumerationResult:
        revision_id = _clean(revision_id)
        decision_scope_id = _clean(decision_scope_id)
        if not revision_id:
            raise ValueError("revision_id must be a non-empty string")
        if not decision_scope_id:
            raise ValueError("decision_scope_id must be a non-empty string")
        if decision_scope_kind not in {"document", "pages"}:
            raise ValueError("unsupported semantic opening decision scope")

        published = self._source_visibility_producer.published_snapshot_for_revision(
            revision_id
        )
        if published is None:
            return SemanticOpeningEnumerationResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SEMANTIC_OPENING_ENUMERATION_UNAVAILABLE,),
                record=None,
            )

        selector = SemanticOpeningEnumerationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=decision_scope_id,
        )

        coverage = published.coverage
        decoded_pages = tuple(sorted({int(page) for page in coverage.decoded_pages}))
        source_complete = (
            str(coverage.state) == "complete"
            and int(coverage.total_pages) > 0
            and not tuple(coverage.failed_pages)
            and len(decoded_pages) == int(coverage.total_pages)
            and decoded_pages == tuple(range(1, int(coverage.total_pages) + 1))
        )
        if not source_complete:
            return self._store(
                selector,
                SemanticOpeningEnumerationResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE,),
                    record=None,
                ),
            )

        if decision_scope_kind == "document":
            scoped_page_ids = tuple(str(page) for page in decoded_pages)
        else:
            assert page_ids is not None
            decoded_page_ids = {str(page) for page in decoded_pages}
            if any(page_id not in decoded_page_ids for page_id in page_ids):
                return self._store(
                    selector,
                    SemanticOpeningEnumerationResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE,),
                        record=None,
                    ),
                )
            scoped_page_ids = tuple(page_ids)

        visibility = self._source_visibility_producer.authority()
        physical = PhysicalOpeningAuthority(visibility)
        allowed_pages = set(scoped_page_ids)

        opening_records: dict[str, PhysicalOpeningExistenceRecord] = {}
        representatives: dict[str, str] = {}
        support_ids: set[str] = set()
        unresolved_visible_ids: set[str] = set()
        conflict_ids: set[str] = set()
        lineage_mismatch = False
        scoped_visible_ids: list[str] = []
        unknown_scope_resolution = False

        for observation_id in tuple(sorted(set(published.visible_observation_ids))):
            obs_selector = ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=observation_id,
            )
            visible_result = visibility.resolve_visible(obs_selector)
            if (
                visible_result.status is not EvidenceResolutionStatus.CORROBORATED
                or visible_result.observation is None
            ):
                if decision_scope_kind == "document":
                    scoped_visible_ids.append(observation_id)
                    if visible_result.status is EvidenceResolutionStatus.CONFLICT:
                        conflict_ids.add(observation_id)
                    else:
                        unresolved_visible_ids.add(observation_id)
                else:
                    unknown_scope_resolution = True
                continue

            observation = visible_result.observation
            if str(observation.page_id) not in allowed_pages:
                continue
            scoped_visible_ids.append(observation_id)

            if (
                observation.document_id != selector.document_id
                or observation.revision_id != selector.revision_id
                or observation.source_sha256 != selector.source_sha256
                or observation.snapshot_id != selector.snapshot_id
            ):
                lineage_mismatch = True
                conflict_ids.add(observation_id)
                continue

            existence = physical.prove_existence(obs_selector)
            if (
                existence.status is EvidenceResolutionStatus.CORROBORATED
                and existence.proposition == PHYSICAL_OPENING_EXISTS
                and existence.existence_record is not None
            ):
                record = existence.existence_record
                if (
                    record.document_id != selector.document_id
                    or record.revision_id != selector.revision_id
                    or record.source_sha256 != selector.source_sha256
                    or record.snapshot_id != selector.snapshot_id
                    or str(record.page_id) not in allowed_pages
                ):
                    lineage_mismatch = True
                    conflict_ids.add(observation_id)
                    continue
                prior = opening_records.get(record.record_id)
                if prior is not None and prior != record:
                    lineage_mismatch = True
                    conflict_ids.add(observation_id)
                    continue
                opening_records[record.record_id] = record
                support_ids.update(record.source_observation_ids)
                representatives[record.record_id] = min(
                    record.source_observation_ids
                )
            elif existence.status is EvidenceResolutionStatus.CONFLICT:
                conflict_ids.add(observation_id)
            else:
                unresolved_visible_ids.add(observation_id)

        visible_ids = tuple(sorted(set(scoped_visible_ids)))
        residual_ids = set(visible_ids) - support_ids
        residual_ids.update(unresolved_visible_ids - support_ids)

        reasons: list[str] = []
        if not visible_ids:
            reasons.append(SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS)
        if unknown_scope_resolution:
            reasons.append(SEMANTIC_OPENING_VISIBLE_OBSERVATION_UNRESOLVED)
        if lineage_mismatch:
            reasons.append(SEMANTIC_OPENING_LINEAGE_MISMATCH)
        if conflict_ids:
            reasons.append(SEMANTIC_OPENING_PHYSICAL_CONFLICT)
        if residual_ids:
            reasons.append(SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE)

        structural_complete = bool(visible_ids) and not (
            unknown_scope_resolution
            or lineage_mismatch
            or conflict_ids
            or residual_ids
        )
        if structural_complete:
            reasons.append(SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE)

        reasons.append(SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN)

        opening_ids = tuple(sorted(opening_records))
        representative_ids = tuple(
            representatives[record_id] for record_id in opening_ids
        )

        payload = {
            "schema_version": SEMANTIC_OPENING_ENUMERATION_SCHEMA_VERSION,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "decision_scope_id": selector.decision_scope_id,
            "decision_scope_kind": decision_scope_kind,
            "page_ids": scoped_page_ids,
            "visible_observation_ids": visible_ids,
            "physical_opening_record_ids": opening_ids,
            "representative_observation_ids": representative_ids,
            "opening_support_observation_ids": tuple(sorted(support_ids)),
            "residual_visible_observation_ids": tuple(sorted(residual_ids)),
            "conflict_observation_ids": tuple(sorted(conflict_ids)),
            "structural_enumeration_complete": structural_complete,
            "physical_opening_universe_complete": False,
            "reason_codes": _ordered_unique(reasons),
        }
        record = SemanticOpeningEnumerationRecord(
            record_id=stable_contract_id(
                "semantic_opening_enumeration",
                payload,
                digest_chars=32,
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            decision_scope_kind=decision_scope_kind,
            page_ids=scoped_page_ids,
            visible_observation_ids=visible_ids,
            physical_opening_record_ids=opening_ids,
            representative_observation_ids=representative_ids,
            opening_support_observation_ids=tuple(sorted(support_ids)),
            residual_visible_observation_ids=tuple(sorted(residual_ids)),
            conflict_observation_ids=tuple(sorted(conflict_ids)),
            structural_enumeration_complete=structural_complete,
            physical_opening_universe_complete=False,
            reason_codes=_ordered_unique(reasons),
        )
        status = (
            EvidenceResolutionStatus.CONFLICT
            if conflict_ids or lineage_mismatch
            else EvidenceResolutionStatus.CORROBORATED
        )
        if unknown_scope_resolution and not (conflict_ids or lineage_mismatch):
            status = EvidenceResolutionStatus.ABSTAINED
        return self._store(
            selector,
            SemanticOpeningEnumerationResult(
                status=status,
                reason_codes=record.reason_codes,
                record=record,
            ),
        )


__all__ = [
    "SEMANTIC_OPENING_ENUMERATION_RESOLVED",
    "SEMANTIC_OPENING_ENUMERATION_SCHEMA_VERSION",
    "SEMANTIC_OPENING_ENUMERATION_UNAVAILABLE",
    "SEMANTIC_OPENING_LINEAGE_MISMATCH",
    "SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS",
    "SEMANTIC_OPENING_PHYSICAL_CONFLICT",
    "SEMANTIC_OPENING_PRODUCER_EQUIVOCATION",
    "SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE",
    "SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE",
    "SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE",
    "SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN",
    "SEMANTIC_OPENING_VISIBLE_OBSERVATION_UNRESOLVED",
    "SemanticOpeningEnumerationAuthority",
    "SemanticOpeningEnumerationProducer",
    "SemanticOpeningEnumerationRecord",
    "SemanticOpeningEnumerationResult",
    "SemanticOpeningEnumerationSelector",
]
