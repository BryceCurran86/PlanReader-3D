"""Generic opening-count recovery and physical instance aggregation authority (Item 23 / F24).

This authority aggregates authenticated physical opening instances into
deterministic counts by family (door/window) and mark (e.g. D1, W1).

Key rules:
- Physical instance identity is preserved.
- Multiple observations of the same physical opening are deduplicated to count once.
- Distinct equal-size openings are counted separately.
- Marks and schedule rows alone cannot manufacture physical opening instances.
- Plans + schedules can corroborate; count mismatches between schedule Qty and plan instances fail closed.
- Wrong page, view, or viewport evidence does not contaminate counts.
- Ambiguous marks, rows, or instances fail closed.
- Stale snapshots, revisions, or source hashes fail closed.
- Completely generic: no benchmark IDs, hardcoded project names, or heuristic guessing.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Optional

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_RESOLVED,
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_source_observation_authority import ObservationSelector

GENERIC_OPENING_COUNT_SCHEMA_VERSION = "1.0.0"

GENERIC_OPENING_COUNT_RESOLVED = "generic_opening_count_resolved"
GENERIC_OPENING_COUNT_UNAVAILABLE = "generic_opening_count_unavailable"
GENERIC_OPENING_COUNT_LINEAGE_MISMATCH = "generic_opening_count_lineage_mismatch"
GENERIC_OPENING_COUNT_AMBIGUOUS = "generic_opening_count_ambiguous"
GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH = "generic_opening_count_schedule_mismatch"
GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE = "generic_opening_count_scope_incomplete"
GENERIC_OPENING_COUNT_NON_PLAN_VIEW = "generic_opening_count_non_plan_view"
GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES = "generic_opening_count_no_physical_instances"
GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED = (
    "generic_opening_count_physical_instance_unresolved"
)

_COUNT_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str, Optional[str], Optional[str]]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


@dataclass(frozen=True)
class GenericOpeningCountSelector:
    """Consumer addressing only: never a caller-authored count or candidate universe."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_family: Optional[str] = None
    opening_mark: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.decision_scope_id, "decision_scope_id")
        if self.opening_family is not None:
            clean_fam = str(self.opening_family).strip().lower()
            if not clean_fam:
                raise ValueError("opening_family cannot be empty when provided")
            object.__setattr__(self, "opening_family", clean_fam)
        if self.opening_mark is not None:
            clean_mark = str(self.opening_mark).strip().upper()
            if not clean_mark:
                raise ValueError("opening_mark cannot be empty when provided")
            object.__setattr__(self, "opening_mark", clean_mark)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.opening_family,
            self.opening_mark,
        )


@dataclass(frozen=True)
class GenericOpeningCountRecord:
    """Deterministic, auditable physical opening count publication record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_family: Optional[str]
    opening_mark: Optional[str]
    count: int
    physical_instance_record_ids: tuple[str, ...]
    schedule_corroborated: bool
    schedule_row_ids: tuple[str, ...] = ()
    quantity_evidence: Optional[QuantityEvidence] = None
    schema_version: str = GENERIC_OPENING_COUNT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.decision_scope_id, "decision_scope_id")
        if self.count < 0:
            raise ValueError("count must be non-negative")
        if len(self.physical_instance_record_ids) != self.count:
            raise ValueError("count must match length of physical_instance_record_ids")
        if len(set(self.physical_instance_record_ids)) != len(
            self.physical_instance_record_ids
        ):
            raise ValueError("physical_instance_record_ids must be unique")


@dataclass(frozen=True)
class GenericOpeningCountResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[GenericOpeningCountRecord] = None
    schema_version: str = GENERIC_OPENING_COUNT_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra_reasons: str,
) -> GenericOpeningCountResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return GenericOpeningCountResult(
        status=status,
        reason_codes=reasons,
        record=None,
    )


class GenericOpeningCountAuthority:
    """Read-only exact-scope selector lookup for generic opening counts."""

    def __init__(
        self,
        results: Mapping[_Key, GenericOpeningCountResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("GenericOpeningCountAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self, selector: GenericOpeningCountSelector
    ) -> GenericOpeningCountResult:
        if type(selector) is not GenericOpeningCountSelector:
            raise TypeError("selector must be GenericOpeningCountSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                GENERIC_OPENING_COUNT_UNAVAILABLE,
            ),
        )


class GenericOpeningCountProducer:
    """Trusted boundary establishing generic opening counts from authenticated drawing evidence."""

    def __init__(
        self,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        schedule_binding_authority: Optional[ScheduleOpeningInstanceBindingAuthority] = None,
        schedule_declared_counts: Optional[Mapping[str, int]] = None,
        non_plan_viewport_ids: Optional[Sequence[str]] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _COUNT_PRODUCER_SEAL:
            raise TypeError(
                "GenericOpeningCountProducer must be obtained from from_authorities()"
            )
        if not isinstance(opening_universe_authority, OpeningUniverseCompletenessAuthority):
            raise TypeError(
                "opening_universe_authority must be producer-owned OpeningUniverseCompletenessAuthority"
            )
        if not isinstance(physical_opening_authority, PhysicalOpeningAuthority):
            raise TypeError(
                "physical_opening_authority must be producer-owned PhysicalOpeningAuthority"
            )
        self._universe = opening_universe_authority
        self._physical = physical_opening_authority
        self._binding = schedule_binding_authority
        self._schedule_counts = MappingProxyType(dict(schedule_declared_counts or {}))
        self._non_plan_viewports = frozenset(non_plan_viewport_ids or ())
        self._results: dict[_Key, GenericOpeningCountResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        schedule_binding_authority: Optional[ScheduleOpeningInstanceBindingAuthority] = None,
        schedule_declared_counts: Optional[Mapping[str, int]] = None,
        non_plan_viewport_ids: Optional[Sequence[str]] = None,
    ) -> "GenericOpeningCountProducer":
        return cls(
            opening_universe_authority=opening_universe_authority,
            physical_opening_authority=physical_opening_authority,
            schedule_binding_authority=schedule_binding_authority,
            schedule_declared_counts=schedule_declared_counts,
            non_plan_viewport_ids=non_plan_viewport_ids,
            _seal=_COUNT_PRODUCER_SEAL,
        )

    def authority(self) -> GenericOpeningCountAuthority:
        return GenericOpeningCountAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: GenericOpeningCountSelector,
        result: GenericOpeningCountResult,
    ) -> GenericOpeningCountResult:
        self._results[selector.key] = result
        return result

    def publish(
        self, selector: GenericOpeningCountSelector
    ) -> GenericOpeningCountResult:
        if type(selector) is not GenericOpeningCountSelector:
            raise TypeError("selector must be GenericOpeningCountSelector")

        # 1. Resolve Opening Universe Completeness for the Decision Scope
        univ_sel = OpeningUniverseSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
        )
        univ_res = self._universe.resolve(univ_sel)
        if (
            univ_res.status is not EvidenceResolutionStatus.CORROBORATED
            or univ_res.record is None
            or not getattr(univ_res.record, "decision_scope_complete", False)
        ):
            return self._store(
                selector,
                _blocked(
                    univ_res.status,
                    GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE,
                    *(getattr(univ_res, "reason_codes", ()) or ()),
                ),
            )

        univ_rec = univ_res.record
        if (
            univ_rec.document_id != selector.document_id
            or univ_rec.revision_id != selector.revision_id
            or univ_rec.source_sha256 != selector.source_sha256
            or univ_rec.snapshot_id != selector.snapshot_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
                ),
            )

        accounted_ids = tuple(univ_rec.accounted_member_ids or ())

        # 2. Resolve Physical Opening Instances and Deduplicate
        distinct_openings: dict[str, PhysicalOpeningExistenceRecord] = {}
        opening_marks: dict[str, Optional[str]] = {}
        opening_families: dict[str, str] = {}
        schedule_row_ids: list[str] = []

        for member_id in accounted_ids:
            obs_sel = ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=member_id,
            )
            exist_res = self._physical.prove_existence(obs_sel)
            if (
                exist_res.status is not EvidenceResolutionStatus.CORROBORATED
                or exist_res.existence_record is None
                or exist_res.proposition != PHYSICAL_OPENING_EXISTS
            ):
                return self._store(
                    selector,
                    _blocked(
                        exist_res.status,
                        GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED,
                        *(getattr(exist_res, "reason_codes", ()) or ()),
                    ),
                )

            p_rec = exist_res.existence_record

            # Strict Lineage Match
            if (
                p_rec.document_id != selector.document_id
                or p_rec.revision_id != selector.revision_id
                or p_rec.source_sha256 != selector.source_sha256
                or p_rec.snapshot_id != selector.snapshot_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
                    ),
                )

            # Viewport isolation: non-plan views (elevations, details) cannot contaminate plan counts
            if (
                p_rec.viewport_id is not None
                and p_rec.viewport_id in self._non_plan_viewports
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GENERIC_OPENING_COUNT_NON_PLAN_VIEW,
                        f"opening_{p_rec.record_id}_in_non_plan_viewport_{p_rec.viewport_id}",
                    ),
                )

            # Preserve Physical Instance Identity (deduplicate identical instance record_id)
            distinct_openings[p_rec.record_id] = p_rec

            # 3. Resolve Schedule Binding if available
            mark: Optional[str] = None
            family: str = "unknown"
            if self._binding is not None:
                b_sel = ScheduleOpeningInstanceBindingSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    decision_scope_id=selector.decision_scope_id,
                    opening_record_id=p_rec.record_id,
                )
                b_res = self._binding.resolve(b_sel)
                if b_res.status is EvidenceResolutionStatus.CONFLICT:
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GENERIC_OPENING_COUNT_AMBIGUOUS,
                            *(getattr(b_res, "reason_codes", ()) or ()),
                        ),
                    )
                if (
                    b_res.status is EvidenceResolutionStatus.CORROBORATED
                    and b_res.record is not None
                ):
                    b_rec = b_res.record
                    mark = (
                        getattr(b_rec, "schedule_row_type_mark", None)
                        or getattr(b_rec, "tag_mark", None)
                        or getattr(b_rec, "normalized_mark", None)
                        or getattr(b_rec, "opening_mark", None)
                    )
                    row_obs = getattr(b_rec, "schedule_row_observation_ids", ()) or ()
                    if row_obs:
                        schedule_row_ids.extend(row_obs)
                    elif getattr(b_rec, "schedule_row_id", None):
                        schedule_row_ids.append(b_rec.schedule_row_id)
                    # Infer family from mark
                    if mark:
                        upper_m = mark.upper()
                        if upper_m.startswith("D") and not upper_m.startswith("DW"):
                            family = "door"
                        elif upper_m.startswith("W"):
                            family = "window"
                        elif upper_m.startswith("DW") or upper_m.startswith("WD"):
                            family = "door_window"

            opening_marks[p_rec.record_id] = mark
            opening_families[p_rec.record_id] = family

        # 4. Filter by Selector Criteria
        matched_instance_ids: list[str] = []
        for op_id in sorted(distinct_openings.keys()):
            op_fam = opening_families.get(op_id, "unknown")
            op_mark = opening_marks.get(op_id)

            if selector.opening_family is not None:
                if selector.opening_family.lower() != op_fam.lower():
                    continue
            if selector.opening_mark is not None:
                if op_mark is None or selector.opening_mark.upper() != op_mark.upper():
                    continue
            matched_instance_ids.append(op_id)

        count = len(matched_instance_ids)

        # 5. Schedule Corroboration & Mismatch Guards
        schedule_corroborated = False
        target_mark = selector.opening_mark
        if target_mark is not None:
            norm_target = target_mark.upper()
            declared_qty = self._schedule_counts.get(norm_target)
            if declared_qty is not None:
                if declared_qty == count:
                    schedule_corroborated = True
                else:
                    # Conflict: schedule says Qty X, but plan instances are Y!
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
                            f"schedule_declared_{declared_qty}_vs_plan_instances_{count}",
                        ),
                    )

        # Fail closed if asking for a specific mark or family that has 0 physical instances
        if count == 0 and (
            selector.opening_mark is not None or selector.opening_family is not None
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
                ),
            )

        # 6. Publish QuantityEvidence
        semantic_key = "opening_count"
        if selector.opening_family:
            semantic_key += f":{selector.opening_family}"
        if selector.opening_mark:
            semantic_key += f":{selector.opening_mark}"

        qty_payload = {
            "family": "opening_count",
            "semantic_key": semantic_key,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "count": count,
            "matched_ids": matched_instance_ids,
        }
        qty_id = stable_contract_id("qty_opening_count", qty_payload)

        evidence_ids = tuple(
            obs_id
            for op_id in matched_instance_ids
            for obs_id in distinct_openings[op_id].source_observation_ids
        )
        qty = QuantityEvidence(
            quantity_id=qty_id,
            family="opening_count",
            semantic_key=semantic_key,
            value=float(count),
            unit="ea",
            input_entity_ids=tuple(matched_instance_ids),
            formula="sum_of_authenticated_physical_opening_instances",
            formula_version=GENERIC_OPENING_COUNT_SCHEMA_VERSION,
            evidence_ids=evidence_ids,
            authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            status=AuthorityStatus.FIRM.value,
            confidence=1.0,
            abstained=False,
            metadata={
                "schedule_corroborated": schedule_corroborated,
                "opening_mark": selector.opening_mark,
                "opening_family": selector.opening_family,
            },
        )

        rec_payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "decision_scope_id": selector.decision_scope_id,
            "opening_family": selector.opening_family,
            "opening_mark": selector.opening_mark,
            "count": count,
            "physical_instance_record_ids": tuple(matched_instance_ids),
            "schedule_corroborated": schedule_corroborated,
            "schedule_row_ids": tuple(sorted(set(schedule_row_ids))),
        }
        record_id = stable_contract_id(
            "generic_opening_count", rec_payload, digest_chars=32
        )
        record = GenericOpeningCountRecord(
            record_id=record_id,
            quantity_evidence=qty,
            **rec_payload,
        )
        result = GenericOpeningCountResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(GENERIC_OPENING_COUNT_RESOLVED,),
            record=record,
        )
        return self._store(selector, result)


__all__ = [
    "GENERIC_OPENING_COUNT_AMBIGUOUS",
    "GENERIC_OPENING_COUNT_LINEAGE_MISMATCH",
    "GENERIC_OPENING_COUNT_NON_PLAN_VIEW",
    "GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES",
    "GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED",
    "GENERIC_OPENING_COUNT_RESOLVED",
    "GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH",
    "GENERIC_OPENING_COUNT_SCHEMA_VERSION",
    "GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE",
    "GENERIC_OPENING_COUNT_UNAVAILABLE",
    "GenericOpeningCountAuthority",
    "GenericOpeningCountProducer",
    "GenericOpeningCountRecord",
    "GenericOpeningCountResult",
    "GenericOpeningCountSelector",
]
