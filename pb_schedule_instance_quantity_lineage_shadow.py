"""Shadow evidence bridge: schedule-mark-to-instance lineage and dimension-basis separation.

Implements Work Order Items 14 & 15 as a pure, read-only, default-off shadow
module with zero commercial writes or authority promotion:
- Item 14: Resolves authenticated schedule rows to physical opening instances
  with full document, revision, source SHA-256, source-page, and viewport
  lineage. Fails closed on cross-revision/SHA mismatches, duplicate canonical
  schedule marks, missing lineage, or unlabelled instances.
- Item 15: Strictly distinguishes leaf dimensions, frame dimensions, rough
  opening (wall-void) dimensions, clear opening dimensions, unknown-basis
  dimensions, and instance-anchored installed opening quantities. Never
  silently converts between bases, applies hardcoded frame allowances, or
  fabricates installed openings from schedule row counts.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_evidence_v170 import (
    DIMENSION_BASIS_CLEAR_OPENING,
    DIMENSION_BASIS_FRAME,
    DIMENSION_BASIS_LEAF,
    DIMENSION_BASIS_ROUGH_OPENING,
    DIMENSION_BASIS_UNKNOWN,
)
from pb_opening_schedule_v171 import ScheduleEntry

SCHEMA_VERSION = "1.0.0"

CLASS_LEAF_DIMENSION = "leaf_dimension"
CLASS_FRAME_DIMENSION = "frame_dimension"
CLASS_ROUGH_OPENING_DIMENSION = "rough_opening_dimension"
CLASS_CLEAR_OPENING_DIMENSION = "clear_opening_dimension"
CLASS_UNKNOWN_BASIS_DIMENSION = "unknown_basis_dimension"
CLASS_INSTALLED_OPENING_QUANTITY = "installed_opening_quantity"

_BASIS_TO_CLASS = {
    DIMENSION_BASIS_LEAF: CLASS_LEAF_DIMENSION,
    DIMENSION_BASIS_FRAME: CLASS_FRAME_DIMENSION,
    DIMENSION_BASIS_ROUGH_OPENING: CLASS_ROUGH_OPENING_DIMENSION,
    DIMENSION_BASIS_CLEAR_OPENING: CLASS_CLEAR_OPENING_DIMENSION,
    DIMENSION_BASIS_UNKNOWN: CLASS_UNKNOWN_BASIS_DIMENSION,
}
_VALID_BASES = frozenset(_BASIS_TO_CLASS)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MARK_PARTS_RE = re.compile(r"^([EI]?[DW]|WD|DW)(\d{1,4})$", re.IGNORECASE)


def _require_str(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_sha256(value: object, field_name: str) -> str:
    clean = _require_str(value, field_name).lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{field_name} must be a 64-char hex sha256")
    return clean


def _normalize_basis(value: object) -> str:
    clean = str(value or "").strip().lower()
    if not clean:
        return DIMENSION_BASIS_UNKNOWN
    if clean not in _VALID_BASES:
        raise ValueError(f"unsupported dimension_basis: {value!r}")
    return clean


def _validate_optional_mm(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive int or None")
    return value


def canonical_opening_mark_key(mark: object) -> tuple[str, int] | None:
    """Return canonical (prefix, integer_number) key so D1 and D01 match safely."""
    if type(mark) is not str:
        return None
    match = _MARK_PARTS_RE.fullmatch(mark.strip())
    if not match:
        return None
    return (match.group(1).upper(), int(match.group(2)))


def canonical_opening_mark_label(mark: object) -> str | None:
    key = canonical_opening_mark_key(mark)
    if key is None:
        return None
    return f"{key[0]}{key[1]}"


@dataclass(frozen=True)
class ScheduleMarkRowCandidate:
    document_id: str
    revision_id: str
    source_sha256: str
    schedule_page_id: str
    schedule_viewport_id: str
    row_observation_ids: tuple[str, ...]
    type_mark: str
    width_mm: int | None = None
    height_mm: int | None = None
    dimension_basis: str = DIMENSION_BASIS_UNKNOWN
    basis_source: str = ""
    schedule_count: int | None = None
    schedule_count_explicit: bool = False
    parse_source: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _require_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _require_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _require_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "schedule_page_id", _require_str(self.schedule_page_id, "schedule_page_id"))
        object.__setattr__(
            self, "schedule_viewport_id", _require_str(self.schedule_viewport_id, "schedule_viewport_id")
        )
        obs = tuple(sorted({_require_str(item, "row_observation_ids") for item in self.row_observation_ids}))
        if not obs:
            raise ValueError("row_observation_ids must be non-empty")
        object.__setattr__(self, "row_observation_ids", obs)
        clean_mark = _require_str(self.type_mark, "type_mark").upper()
        if canonical_opening_mark_key(clean_mark) is None:
            raise ValueError(f"invalid opening type_mark: {self.type_mark!r}")
        object.__setattr__(self, "type_mark", clean_mark)
        object.__setattr__(self, "width_mm", _validate_optional_mm(self.width_mm, "width_mm"))
        object.__setattr__(self, "height_mm", _validate_optional_mm(self.height_mm, "height_mm"))
        object.__setattr__(self, "dimension_basis", _normalize_basis(self.dimension_basis))
        object.__setattr__(self, "basis_source", str(self.basis_source or "").strip())
        if type(self.schedule_count_explicit) is not bool:
            raise TypeError("schedule_count_explicit must be a bool")
        if self.schedule_count is not None:
            if isinstance(self.schedule_count, bool) or not isinstance(self.schedule_count, int) or self.schedule_count < 1:
                raise ValueError("schedule_count must be a positive int or None")
        if self.schedule_count_explicit and self.schedule_count is None:
            raise ValueError("schedule_count_explicit=True requires schedule_count")

    @classmethod
    def from_schedule_entry(
        cls,
        entry: ScheduleEntry,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        schedule_page_id: str,
        schedule_viewport_id: str,
        row_observation_ids: Sequence[str],
    ) -> "ScheduleMarkRowCandidate":
        return cls(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            schedule_page_id=schedule_page_id,
            schedule_viewport_id=schedule_viewport_id,
            row_observation_ids=tuple(row_observation_ids),
            type_mark=entry.type_mark,
            width_mm=entry.width_mm,
            height_mm=entry.height_mm,
            dimension_basis=entry.dimension_basis or DIMENSION_BASIS_UNKNOWN,
            basis_source=entry.basis_source,
            schedule_count=entry.count if entry.count_explicit else None,
            schedule_count_explicit=bool(entry.count_explicit),
            parse_source=entry.parse_source,
            description=entry.description,
        )


@dataclass(frozen=True)
class PhysicalOpeningInstanceCandidate:
    instance_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    plan_page_id: str
    plan_viewport_id: str
    physical_evidence_ids: tuple[str, ...]
    plan_tag_mark: str | None = None
    plan_tag_observation_id: str | None = None
    host_wall_id: str | None = None
    plan_width_mm: int | None = None
    plan_height_mm: int | None = None
    plan_dimension_basis: str = DIMENSION_BASIS_UNKNOWN
    plan_dimension_evidence_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance_id", _require_str(self.instance_id, "instance_id"))
        object.__setattr__(self, "document_id", _require_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _require_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _require_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "plan_page_id", _require_str(self.plan_page_id, "plan_page_id"))
        object.__setattr__(self, "plan_viewport_id", _require_str(self.plan_viewport_id, "plan_viewport_id"))
        ev = tuple(sorted({_require_str(item, "physical_evidence_ids") for item in self.physical_evidence_ids}))
        if not ev:
            raise ValueError("physical_evidence_ids must be non-empty")
        object.__setattr__(self, "physical_evidence_ids", ev)
        if self.plan_tag_mark is not None:
            clean_tag = str(self.plan_tag_mark).strip().upper()
            object.__setattr__(self, "plan_tag_mark", clean_tag or None)
        if self.plan_tag_observation_id is not None:
            clean_obs = str(self.plan_tag_observation_id).strip()
            object.__setattr__(self, "plan_tag_observation_id", clean_obs or None)
        if self.host_wall_id is not None:
            clean_wall = str(self.host_wall_id).strip()
            object.__setattr__(self, "host_wall_id", clean_wall or None)
        object.__setattr__(self, "plan_width_mm", _validate_optional_mm(self.plan_width_mm, "plan_width_mm"))
        object.__setattr__(self, "plan_height_mm", _validate_optional_mm(self.plan_height_mm, "plan_height_mm"))
        object.__setattr__(self, "plan_dimension_basis", _normalize_basis(self.plan_dimension_basis))
        if self.plan_dimension_evidence_id is not None:
            clean_dim_ev = str(self.plan_dimension_evidence_id).strip()
            object.__setattr__(self, "plan_dimension_evidence_id", clean_dim_ev or None)


@dataclass(frozen=True)
class TypedDimensionWitness:
    witness_id: str
    dimension_class: str
    dimension_basis: str
    width_mm: int | None
    height_mm: int | None
    source_kind: str
    source_page_id: str
    source_viewport_id: str
    source_observation_ids: tuple[str, ...]
    basis_source: str
    wall_void_deduction_eligible: bool
    frame_adjustment_applied: bool = False


@dataclass(frozen=True)
class InstalledOpeningQuantityShadow:
    record_id: str
    quantity_class: str
    instance_id: str
    printed_mark: str | None
    canonical_mark: str | None
    document_id: str
    revision_id: str
    source_sha256: str
    plan_page_id: str
    plan_viewport_id: str
    plan_tag_observation_id: str | None
    schedule_page_id: str | None
    schedule_viewport_id: str | None
    schedule_row_observation_ids: tuple[str, ...]
    installed_count: int
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    leaf_dimension: TypedDimensionWitness | None = None
    frame_dimension: TypedDimensionWitness | None = None
    rough_opening_dimension: TypedDimensionWitness | None = None
    clear_opening_dimension: TypedDimensionWitness | None = None
    unknown_basis_dimension: TypedDimensionWitness | None = None
    wall_void_deduction_eligible: bool = False
    schedule_declared_count_note: int | None = None
    commercial_authority_granted: bool = False


@dataclass(frozen=True)
class UnmatchedScheduleMarkShadow:
    document_id: str
    revision_id: str
    source_sha256: str
    schedule_page_id: str
    schedule_viewport_id: str
    type_mark: str
    canonical_mark: str
    row_observation_ids: tuple[str, ...]
    installed_count: int = 0
    reason_code: str = "schedule_only_non_instance_no_physical_opening"


@dataclass(frozen=True)
class ScheduleCountDiscrepancyShadow:
    document_id: str
    revision_id: str
    source_sha256: str
    canonical_mark: str
    schedule_declared_count: int
    physical_instance_count: int
    reason_code: str


@dataclass(frozen=True)
class ScheduleInstanceQuantityLineageReport:
    schema_version: str
    installed_openings: tuple[InstalledOpeningQuantityShadow, ...]
    unmatched_schedule_marks: tuple[UnmatchedScheduleMarkShadow, ...]
    count_discrepancies: tuple[ScheduleCountDiscrepancyShadow, ...]
    commercial_authority_granted: bool = False


def _make_dimension_witness(
    *,
    basis: str,
    width_mm: int | None,
    height_mm: int | None,
    source_kind: str,
    source_page_id: str,
    source_viewport_id: str,
    source_observation_ids: tuple[str, ...],
    basis_source: str,
) -> TypedDimensionWitness:
    dim_class = _BASIS_TO_CLASS[basis]
    deduction_eligible = (
        basis == DIMENSION_BASIS_ROUGH_OPENING
        and width_mm is not None
        and height_mm is not None
    )
    witness_id = stable_contract_id(
        "opening_dimension_witness",
        {
            "dimension_class": dim_class,
            "dimension_basis": basis,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "source_kind": source_kind,
            "source_page_id": source_page_id,
            "source_viewport_id": source_viewport_id,
            "source_observation_ids": source_observation_ids,
            "basis_source": basis_source,
        },
    )
    return TypedDimensionWitness(
        witness_id=witness_id,
        dimension_class=dim_class,
        dimension_basis=basis,
        width_mm=width_mm,
        height_mm=height_mm,
        source_kind=source_kind,
        source_page_id=source_page_id,
        source_viewport_id=source_viewport_id,
        source_observation_ids=source_observation_ids,
        basis_source=basis_source,
        wall_void_deduction_eligible=deduction_eligible,
        frame_adjustment_applied=False,
    )


def _witnesses_conflict_same_basis(
    left: TypedDimensionWitness, right: TypedDimensionWitness,
) -> bool:
    if left.dimension_basis != right.dimension_basis:
        return False
    if left.width_mm is not None and right.width_mm is not None and left.width_mm != right.width_mm:
        return True
    if left.height_mm is not None and right.height_mm is not None and left.height_mm != right.height_mm:
        return True
    return False


def _merge_same_basis_witnesses(
    primary: TypedDimensionWitness, secondary: TypedDimensionWitness,
) -> TypedDimensionWitness:
    width = primary.width_mm if primary.width_mm is not None else secondary.width_mm
    height = primary.height_mm if primary.height_mm is not None else secondary.height_mm
    obs = tuple(sorted(set(primary.source_observation_ids) | set(secondary.source_observation_ids)))
    basis_src = primary.basis_source or secondary.basis_source
    return _make_dimension_witness(
        basis=primary.dimension_basis,
        width_mm=width,
        height_mm=height,
        source_kind=f"{primary.source_kind}+{secondary.source_kind}",
        source_page_id=primary.source_page_id,
        source_viewport_id=primary.source_viewport_id,
        source_observation_ids=obs,
        basis_source=basis_src,
    )


def resolve_schedule_instance_quantity_lineage(
    *,
    schedule_rows: Sequence[ScheduleMarkRowCandidate],
    physical_instances: Sequence[PhysicalOpeningInstanceCandidate],
) -> ScheduleInstanceQuantityLineageReport:
    """Resolve schedule marks to physical instances with page/viewport lineage and basis separation."""
    # Reject duplicate physical instance identities fail-closed.
    seen_instance_ids: set[str] = set()
    for inst in physical_instances:
        if inst.instance_id in seen_instance_ids:
            raise ValueError(f"duplicate_physical_opening_instance_id:{inst.instance_id}")
        seen_instance_ids.add(inst.instance_id)

    # Index schedule rows strictly by (document_id, revision_id, source_sha256, canonical_key).
    # Any duplicate canonical mark inside the same document+revision+sha256 (even if
    # printed as D1 vs D01 or across two viewports/pages) is retained as a CONFLICT.
    rows_by_scope_and_mark: dict[
        tuple[str, str, str, tuple[str, int]], list[ScheduleMarkRowCandidate]
    ] = {}
    for row in schedule_rows:
        key = canonical_opening_mark_key(row.type_mark)
        assert key is not None
        scope_mark = (row.document_id, row.revision_id, row.source_sha256, key)
        rows_by_scope_and_mark.setdefault(scope_mark, []).append(row)

    matched_scope_marks: set[tuple[str, str, str, tuple[str, int]]] = set()
    instance_count_by_scope_mark: dict[tuple[str, str, str, tuple[str, int]], int] = {}
    installed_records: list[InstalledOpeningQuantityShadow] = []

    ordered_instances = sorted(
        physical_instances,
        key=lambda item: (
            item.document_id, item.revision_id, item.source_sha256,
            item.plan_page_id, item.plan_viewport_id, item.instance_id,
        ),
    )

    for inst in ordered_instances:
        slots: dict[str, TypedDimensionWitness | None] = {
            DIMENSION_BASIS_LEAF: None,
            DIMENSION_BASIS_FRAME: None,
            DIMENSION_BASIS_ROUGH_OPENING: None,
            DIMENSION_BASIS_CLEAR_OPENING: None,
            DIMENSION_BASIS_UNKNOWN: None,
        }
        reasons: list[str] = []
        plan_witness: TypedDimensionWitness | None = None
        if inst.plan_width_mm is not None or inst.plan_height_mm is not None:
            if inst.plan_dimension_evidence_id:
                plan_witness = _make_dimension_witness(
                    basis=inst.plan_dimension_basis,
                    width_mm=inst.plan_width_mm,
                    height_mm=inst.plan_height_mm,
                    source_kind="plan_direct",
                    source_page_id=inst.plan_page_id,
                    source_viewport_id=inst.plan_viewport_id,
                    source_observation_ids=(inst.plan_dimension_evidence_id,),
                    basis_source=f"plan:{inst.plan_dimension_basis}",
                )
                slots[inst.plan_dimension_basis] = plan_witness
            else:
                reasons.append("plan_dimension_missing_evidence_id")

        mark_key = canonical_opening_mark_key(inst.plan_tag_mark) if inst.plan_tag_mark else None
        canon_label = canonical_opening_mark_label(inst.plan_tag_mark) if mark_key else None

        schedule_page_id: str | None = None
        schedule_viewport_id: str | None = None
        schedule_obs_ids: tuple[str, ...] = ()
        schedule_count_note: int | None = None

        if not inst.plan_tag_mark or not inst.plan_tag_observation_id or mark_key is None:
            status = EvidenceResolutionStatus.ABSTAINED
            reasons.append("unlabelled_physical_instance_no_schedule_binding")
        else:
            scope_mark = (inst.document_id, inst.revision_id, inst.source_sha256, mark_key)
            instance_count_by_scope_mark[scope_mark] = (
                instance_count_by_scope_mark.get(scope_mark, 0) + 1
            )
            matching_rows = rows_by_scope_and_mark.get(scope_mark, [])
            if not matching_rows:
                status = EvidenceResolutionStatus.ABSTAINED
                reasons.append("no_matching_schedule_row_in_same_source_revision")
            elif len(matching_rows) > 1:
                matched_scope_marks.add(scope_mark)
                status = EvidenceResolutionStatus.CONFLICT
                reasons.append("conflicting_duplicate_schedule_mark")
            else:
                matched_scope_marks.add(scope_mark)
                row = matching_rows[0]
                schedule_page_id = row.schedule_page_id
                schedule_viewport_id = row.schedule_viewport_id
                schedule_obs_ids = row.row_observation_ids
                schedule_count_note = row.schedule_count if row.schedule_count_explicit else None

                if row.width_mm is None and row.height_mm is None:
                    status = EvidenceResolutionStatus.ABSTAINED
                    reasons.append("schedule_dimensions_abstained_or_blank")
                else:
                    sched_witness = _make_dimension_witness(
                        basis=row.dimension_basis,
                        width_mm=row.width_mm,
                        height_mm=row.height_mm,
                        source_kind="schedule",
                        source_page_id=row.schedule_page_id,
                        source_viewport_id=row.schedule_viewport_id,
                        source_observation_ids=row.row_observation_ids,
                        basis_source=row.basis_source,
                    )
                    existing_same_basis = slots[row.dimension_basis]
                    if existing_same_basis is not None:
                        if _witnesses_conflict_same_basis(existing_same_basis, sched_witness):
                            status = EvidenceResolutionStatus.CONFLICT
                            reasons.append("same_basis_dimension_conflict")
                            # Clear conflicted slot so no downstream caller can consume one side.
                            slots[row.dimension_basis] = None
                        else:
                            slots[row.dimension_basis] = _merge_same_basis_witnesses(
                                sched_witness, existing_same_basis,
                            )
                            status = EvidenceResolutionStatus.CORROBORATED
                            reasons.append("schedule_instance_lineage_resolved")
                            reasons.append(f"basis_{row.dimension_basis}_preserved")
                    else:
                        slots[row.dimension_basis] = sched_witness
                        status = EvidenceResolutionStatus.CORROBORATED
                        reasons.append("schedule_instance_lineage_resolved")
                        reasons.append(f"basis_{row.dimension_basis}_preserved")
                        if plan_witness is not None and plan_witness.dimension_basis != row.dimension_basis:
                            reasons.append("distinct_dimension_bases_preserved_separately")

        ro_witness = slots[DIMENSION_BASIS_ROUGH_OPENING]
        deduction_eligible = (
            status == EvidenceResolutionStatus.CORROBORATED
            and ro_witness is not None
            and ro_witness.wall_void_deduction_eligible
        )
        if status == EvidenceResolutionStatus.CORROBORATED and not deduction_eligible:
            reasons.append("not_rough_opening_wall_void_deduction_ineligible")

        ordered_reasons = tuple(dict.fromkeys(reasons))
        record_id = stable_contract_id(
            "installed_opening_quantity_shadow",
            {
                "instance_id": inst.instance_id,
                "document_id": inst.document_id,
                "revision_id": inst.revision_id,
                "source_sha256": inst.source_sha256,
                "plan_page_id": inst.plan_page_id,
                "plan_viewport_id": inst.plan_viewport_id,
                "plan_tag_observation_id": inst.plan_tag_observation_id,
                "schedule_page_id": schedule_page_id,
                "schedule_viewport_id": schedule_viewport_id,
                "schedule_row_observation_ids": schedule_obs_ids,
                "status": status.value,
                "reason_codes": ordered_reasons,
            },
        )
        installed_records.append(
            InstalledOpeningQuantityShadow(
                record_id=record_id,
                quantity_class=CLASS_INSTALLED_OPENING_QUANTITY,
                instance_id=inst.instance_id,
                printed_mark=inst.plan_tag_mark,
                canonical_mark=canon_label,
                document_id=inst.document_id,
                revision_id=inst.revision_id,
                source_sha256=inst.source_sha256,
                plan_page_id=inst.plan_page_id,
                plan_viewport_id=inst.plan_viewport_id,
                plan_tag_observation_id=inst.plan_tag_observation_id,
                schedule_page_id=schedule_page_id,
                schedule_viewport_id=schedule_viewport_id,
                schedule_row_observation_ids=schedule_obs_ids,
                installed_count=1,
                status=status,
                reason_codes=ordered_reasons,
                leaf_dimension=slots[DIMENSION_BASIS_LEAF],
                frame_dimension=slots[DIMENSION_BASIS_FRAME],
                rough_opening_dimension=slots[DIMENSION_BASIS_ROUGH_OPENING],
                clear_opening_dimension=slots[DIMENSION_BASIS_CLEAR_OPENING],
                unknown_basis_dimension=slots[DIMENSION_BASIS_UNKNOWN],
                wall_void_deduction_eligible=deduction_eligible,
                schedule_declared_count_note=schedule_count_note,
                commercial_authority_granted=False,
            )
        )

    # Unmatched schedule rows NEVER create installed opening instances.
    unmatched: list[UnmatchedScheduleMarkShadow] = []
    discrepancies: list[ScheduleCountDiscrepancyShadow] = []
    for scope_mark, rows in sorted(rows_by_scope_and_mark.items()):
        doc_id, rev_id, sha, mark_key = scope_mark
        canon_label = f"{mark_key[0]}{mark_key[1]}"
        if scope_mark not in matched_scope_marks:
            for row in sorted(rows, key=lambda r: (r.schedule_page_id, r.schedule_viewport_id, r.row_observation_ids)):
                unmatched.append(
                    UnmatchedScheduleMarkShadow(
                        document_id=doc_id,
                        revision_id=rev_id,
                        source_sha256=sha,
                        schedule_page_id=row.schedule_page_id,
                        schedule_viewport_id=row.schedule_viewport_id,
                        type_mark=row.type_mark,
                        canonical_mark=canon_label,
                        row_observation_ids=row.row_observation_ids,
                        installed_count=0,
                    )
                )
        if len(rows) == 1 and rows[0].schedule_count_explicit and rows[0].schedule_count is not None:
            actual_instances = instance_count_by_scope_mark.get(scope_mark, 0)
            if actual_instances != rows[0].schedule_count:
                discrepancies.append(
                    ScheduleCountDiscrepancyShadow(
                        document_id=doc_id,
                        revision_id=rev_id,
                        source_sha256=sha,
                        canonical_mark=canon_label,
                        schedule_declared_count=rows[0].schedule_count,
                        physical_instance_count=actual_instances,
                        reason_code="schedule_declared_count_differs_from_physical_instances",
                    )
                )

    return ScheduleInstanceQuantityLineageReport(
        schema_version=SCHEMA_VERSION,
        installed_openings=tuple(installed_records),
        unmatched_schedule_marks=tuple(unmatched),
        count_discrepancies=tuple(discrepancies),
        commercial_authority_granted=False,
    )


__all__ = [
    "CLASS_CLEAR_OPENING_DIMENSION",
    "CLASS_FRAME_DIMENSION",
    "CLASS_INSTALLED_OPENING_QUANTITY",
    "CLASS_LEAF_DIMENSION",
    "CLASS_ROUGH_OPENING_DIMENSION",
    "CLASS_UNKNOWN_BASIS_DIMENSION",
    "InstalledOpeningQuantityShadow",
    "PhysicalOpeningInstanceCandidate",
    "SCHEMA_VERSION",
    "ScheduleCountDiscrepancyShadow",
    "ScheduleInstanceQuantityLineageReport",
    "ScheduleMarkRowCandidate",
    "TypedDimensionWitness",
    "UnmatchedScheduleMarkShadow",
    "canonical_opening_mark_key",
    "canonical_opening_mark_label",
    "resolve_schedule_instance_quantity_lineage",
]
