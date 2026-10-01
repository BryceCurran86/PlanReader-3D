"""Read-only coverage registry adapters for audit and customer runtime.

All joins remain exact identity joins against an already-built
CoverageRegistrySummaryV1. This module never admits physical objects, creates
quantity links, changes commercial authority, reads benchmark truth, or
performs heuristic matching.

AG-09 adds a customer/runtime lifecycle publication over the same immutable
registry records:

DETECTED -> AUTHENTICATED -> CANONICALIZED -> QUANTIFIED -> PUBLISHED

The optional renderer-facing DISPLAYED stage remains QA-only and is not part
of the customer takeoff coverage headline. Unsupported families are reported
as unavailable rather than zero.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from pb_audit_coverage_record import (
    AuditObjectRecord,
    CoverageState,
    REFUSED_PHYSICAL_STATES,
)
from pb_takeoff_coverage_registry import CoverageObjectRecordV1, CoverageRegistrySummaryV1


REASON_NOT_IN_REGISTRY_UNIVERSE = "not_in_registry_admitted_object_universe"
REASON_SCENE_OBJECT_ID_MISSING = "scene_object_id_missing"


class RegistryCoverageRecordProviderV1:
    """CoverageRecordProvider backed only by exact registry object identity."""

    def __init__(self, summary: CoverageRegistrySummaryV1) -> None:
        if not isinstance(summary, CoverageRegistrySummaryV1):
            raise TypeError("summary must be CoverageRegistrySummaryV1")
        index: dict[str, CoverageObjectRecordV1] = {}
        for record in summary.object_records:
            if record.object_id in index:
                raise ValueError(f"duplicate registry object_id: {record.object_id}")
            index[record.object_id] = record
        self._summary = summary
        self._records = MappingProxyType(index)

    @property
    def summary(self) -> CoverageRegistrySummaryV1:
        return self._summary

    def record_for(self, obj: Mapping[str, Any]) -> AuditObjectRecord:
        object_id = str(obj.get("id") or "").strip()
        object_type = str(obj.get("type") or "UNKNOWN")
        geometry = obj.get("geometry") or {}
        geometry_basis = str(geometry.get("basis") or "none")

        if not object_id:
            return AuditObjectRecord(
                object_id="UNKNOWN",
                object_type=object_type,
                coverage_state=CoverageState.ABSTAINED,
                reason_code=REASON_SCENE_OBJECT_ID_MISSING,
                geometry_basis=geometry_basis,
            )

        record = self._records.get(object_id)
        if record is None:
            return AuditObjectRecord(
                object_id=object_id,
                object_type=object_type,
                coverage_state=CoverageState.ABSTAINED,
                reason_code=REASON_NOT_IN_REGISTRY_UNIVERSE,
                geometry_basis=geometry_basis,
            )

        state = CoverageState(record.coverage_state)
        reason_code = record.reason_codes[0] if record.reason_codes else None

        # Renderer-facing uncertainty may only lower trust. It never changes the
        # registry result and never raises a coverage state.
        refusal = obj.get("refusal_reason")
        physical_state = str(obj.get("physical_state") or "")
        unresolved = tuple(sorted(str(v) for v in (obj.get("unresolved_attributes") or ())))

        if state is CoverageState.ACCOUNTED:
            if refusal:
                state = CoverageState.ABSTAINED
                reason_code = str(refusal)
            elif physical_state in REFUSED_PHYSICAL_STATES:
                state = CoverageState.ABSTAINED
                reason_code = physical_state
            elif unresolved:
                state = CoverageState.PARTIAL
                reason_code = "scene_unresolved:" + ",".join(unresolved)

        provenance = copy.deepcopy(dict(record.provenance))
        provenance.update(
            {
                "coverage_registry_producer": record.producer,
                "coverage_registry_owning_authority": record.owning_authority,
                "coverage_registry_reason_codes": list(record.reason_codes),
            }
        )

        return AuditObjectRecord(
            object_id=record.object_id,
            object_type=object_type,
            coverage_state=state,
            reason_code=reason_code,
            source_pages=record.source_pages,
            provenance=provenance,
            takeoff_row_ids=record.takeoff_row_ids,
            geometry_basis=geometry_basis,
            coverage_basis=record.coverage_basis,
            expected_family_completeness=record.expected_family_completeness,
        )



class RuntimeCoverageStage(str, Enum):
    DETECTED = "DETECTED"
    AUTHENTICATED = "AUTHENTICATED"
    CANONICALIZED = "CANONICALIZED"
    QUANTIFIED = "QUANTIFIED"
    PUBLISHED = "PUBLISHED"


RUNTIME_COVERAGE_STAGE_ORDER = (
    RuntimeCoverageStage.DETECTED,
    RuntimeCoverageStage.AUTHENTICATED,
    RuntimeCoverageStage.CANONICALIZED,
    RuntimeCoverageStage.QUANTIFIED,
    RuntimeCoverageStage.PUBLISHED,
)

RUNTIME_COVERAGE_UNAVAILABLE = "coverage_registry_summary_unavailable"
RUNTIME_COVERAGE_PARTIAL = "coverage_registry_scope_partial"
RUNTIME_COVERAGE_AVAILABLE = "coverage_registry_scope_available"


@dataclass(frozen=True)
class RuntimeCoverageObjectReport:
    object_id: str
    object_type: str
    producer: str
    owning_authority: str
    source_document_id: str
    source_sha256: str
    highest_stage_reached: RuntimeCoverageStage
    died_at_stage: RuntimeCoverageStage | None
    death_reason: str | None
    stage_evaluations: Mapping[str, bool]
    evidence_ids: tuple[str, ...]
    geometry_ids: tuple[str, ...]
    quantity_ids: tuple[str, ...]
    takeoff_row_ids: tuple[str, ...]
    coverage_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "producer": self.producer,
            "owning_authority": self.owning_authority,
            "source_document_id": self.source_document_id,
            "source_sha256": self.source_sha256,
            "highest_stage_reached": self.highest_stage_reached.value,
            "died_at_stage": (
                self.died_at_stage.value if self.died_at_stage is not None else None
            ),
            "death_reason": self.death_reason,
            "stage_evaluations": dict(self.stage_evaluations),
            "evidence_ids": list(self.evidence_ids),
            "geometry_ids": list(self.geometry_ids),
            "quantity_ids": list(self.quantity_ids),
            "takeoff_row_ids": list(self.takeoff_row_ids),
            "coverage_state": self.coverage_state,
        }


@dataclass(frozen=True)
class RuntimeCoverageLifecycleReport:
    status: str
    reason_codes: tuple[str, ...]
    registry_run_id: str
    source_document_id: str
    source_sha256: str
    stage_counts: Mapping[str, int]
    object_reports: tuple[RuntimeCoverageObjectReport, ...]
    coverage_basis: str
    expected_family_completeness: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "registry_run_id": self.registry_run_id,
            "source_document_id": self.source_document_id,
            "source_sha256": self.source_sha256,
            "stage_counts": dict(self.stage_counts),
            "object_reports": [report.to_dict() for report in self.object_reports],
            "coverage_basis": self.coverage_basis,
            "expected_family_completeness": self.expected_family_completeness,
        }


def _reference_contains_id(reference: object, identifier: str) -> bool:
    text = str(reference or "")
    clean = str(identifier or "").strip()
    if not text or not clean:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(clean)}(?![A-Za-z0-9_])",
        text,
    ) is not None


def _row_publishes_identifier(row: Mapping[str, Any], identifier: str) -> bool:
    clean = str(identifier or "").strip()
    if not clean:
        return False
    for field in ("quantity_id", "row_id", "coverage_row_id"):
        if str(row.get(field) or "").strip() == clean:
            return True
    return _reference_contains_id(row.get("source_reference"), clean)


def _record_is_published(
    record: CoverageObjectRecordV1,
    published_takeoff_rows: Sequence[Mapping[str, Any]],
) -> bool:
    if not record.takeoff_row_ids:
        return False
    for row_id in record.takeoff_row_ids:
        if any(
            _row_publishes_identifier(row, row_id)
            for row in published_takeoff_rows
            if isinstance(row, Mapping)
        ):
            return True
    return False


def audit_registry_runtime_lifecycle(
    summary: CoverageRegistrySummaryV1,
    *,
    published_takeoff_rows: Sequence[Mapping[str, Any]] = (),
) -> RuntimeCoverageLifecycleReport:
    """Trace one producer-owned registry universe through customer publication.

    Registry admission is already producer-owned physical/authenticated scope,
    so every object record proves DETECTED and AUTHENTICATED. Later stages are
    exact dependency checks only:

    CANONICALIZED: one-or-more explicit geometry ids
    QUANTIFIED: one-or-more explicit quantity ids
    PUBLISHED: a registry takeoff-row id is present in the customer row source
               identity or explicit quantity-id field
    """
    if not isinstance(summary, CoverageRegistrySummaryV1):
        raise TypeError("summary must be CoverageRegistrySummaryV1")

    stage_counts = {stage.value: 0 for stage in RUNTIME_COVERAGE_STAGE_ORDER}
    object_reports: list[RuntimeCoverageObjectReport] = []

    for record in summary.object_records:
        flags = {
            RuntimeCoverageStage.DETECTED.value: True,
            RuntimeCoverageStage.AUTHENTICATED.value: True,
            RuntimeCoverageStage.CANONICALIZED.value: False,
            RuntimeCoverageStage.QUANTIFIED.value: False,
            RuntimeCoverageStage.PUBLISHED.value: False,
        }
        stage_counts[RuntimeCoverageStage.DETECTED.value] += 1
        stage_counts[RuntimeCoverageStage.AUTHENTICATED.value] += 1
        highest = RuntimeCoverageStage.AUTHENTICATED
        died_at: RuntimeCoverageStage | None = None
        death_reason: str | None = None

        canonicalized = bool(record.geometry_ids)
        flags[RuntimeCoverageStage.CANONICALIZED.value] = canonicalized
        if not canonicalized:
            died_at = RuntimeCoverageStage.CANONICALIZED
            death_reason = "explicit_canonical_geometry_link_unavailable"
        else:
            stage_counts[RuntimeCoverageStage.CANONICALIZED.value] += 1
            highest = RuntimeCoverageStage.CANONICALIZED

            quantified = bool(record.quantity_ids)
            flags[RuntimeCoverageStage.QUANTIFIED.value] = quantified
            if not quantified:
                died_at = RuntimeCoverageStage.QUANTIFIED
                death_reason = "explicit_quantity_link_unavailable"
            else:
                stage_counts[RuntimeCoverageStage.QUANTIFIED.value] += 1
                highest = RuntimeCoverageStage.QUANTIFIED

                published = _record_is_published(record, published_takeoff_rows)
                flags[RuntimeCoverageStage.PUBLISHED.value] = published
                if not published:
                    died_at = RuntimeCoverageStage.PUBLISHED
                    death_reason = "customer_takeoff_row_not_found"
                else:
                    stage_counts[RuntimeCoverageStage.PUBLISHED.value] += 1
                    highest = RuntimeCoverageStage.PUBLISHED

        object_reports.append(
            RuntimeCoverageObjectReport(
                object_id=record.object_id,
                object_type=record.object_type,
                producer=record.producer,
                owning_authority=record.owning_authority,
                source_document_id=record.source_document_id,
                source_sha256=record.source_sha256,
                highest_stage_reached=highest,
                died_at_stage=died_at,
                death_reason=death_reason,
                stage_evaluations=MappingProxyType(flags),
                evidence_ids=record.evidence_ids,
                geometry_ids=record.geometry_ids,
                quantity_ids=record.quantity_ids,
                takeoff_row_ids=record.takeoff_row_ids,
                coverage_state=record.coverage_state,
            )
        )

    scope_complete = (
        summary.object_universe_complete
        and summary.quantity_evidence_universe_complete
        and summary.takeoff_output_row_universe_complete
    )
    status = RUNTIME_COVERAGE_AVAILABLE if scope_complete else RUNTIME_COVERAGE_PARTIAL
    reasons = list(summary.reason_codes)
    if not scope_complete:
        reasons.append(RUNTIME_COVERAGE_PARTIAL)

    return RuntimeCoverageLifecycleReport(
        status=status,
        reason_codes=tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason))),
        registry_run_id=summary.manifest.registry_run_id,
        source_document_id=summary.manifest.source_document_id,
        source_sha256=summary.manifest.source_sha256,
        stage_counts=MappingProxyType(stage_counts),
        object_reports=tuple(object_reports),
        coverage_basis=summary.coverage_basis,
        expected_family_completeness=summary.expected_family_completeness,
    )


def build_runtime_coverage_publication(
    summaries: Sequence[CoverageRegistrySummaryV1],
    *,
    published_takeoff_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build customer-safe AG-09 coverage metadata from supplied live registries."""
    valid = tuple(
        summary
        for summary in summaries
        if isinstance(summary, CoverageRegistrySummaryV1)
    )
    if not valid:
        return {
            "status": "unavailable",
            "reason_codes": [RUNTIME_COVERAGE_UNAVAILABLE],
            "stage_counts": {stage.value: None for stage in RUNTIME_COVERAGE_STAGE_ORDER},
            "registry_reports": [],
            "coverage_basis": None,
            "expected_family_completeness": "UNKNOWN",
        }

    reports = tuple(
        audit_registry_runtime_lifecycle(
            summary,
            published_takeoff_rows=published_takeoff_rows,
        )
        for summary in valid
    )
    counts = {
        stage.value: sum(report.stage_counts[stage.value] for report in reports)
        for stage in RUNTIME_COVERAGE_STAGE_ORDER
    }
    status = (
        RUNTIME_COVERAGE_AVAILABLE
        if all(report.status == RUNTIME_COVERAGE_AVAILABLE for report in reports)
        else RUNTIME_COVERAGE_PARTIAL
    )
    reasons = tuple(
        dict.fromkeys(
            reason
            for report in reports
            for reason in report.reason_codes
        )
    )
    return {
        "status": status,
        "reason_codes": list(reasons),
        "stage_counts": counts,
        "registry_reports": [report.to_dict() for report in reports],
        "coverage_basis": "EXPLICIT_DEPENDENCIES_ONLY",
        "expected_family_completeness": "UNKNOWN",
    }


__all__ = [
    "REASON_NOT_IN_REGISTRY_UNIVERSE",
    "REASON_SCENE_OBJECT_ID_MISSING",
    "RUNTIME_COVERAGE_AVAILABLE",
    "RUNTIME_COVERAGE_PARTIAL",
    "RUNTIME_COVERAGE_STAGE_ORDER",
    "RUNTIME_COVERAGE_UNAVAILABLE",
    "RegistryCoverageRecordProviderV1",
    "RuntimeCoverageLifecycleReport",
    "RuntimeCoverageObjectReport",
    "RuntimeCoverageStage",
    "audit_registry_runtime_lifecycle",
    "build_runtime_coverage_publication",
]
