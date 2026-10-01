"""Read-only adapter from take-off coverage registry v1 to the 3D audit provider.

This bridge is shadow-only. It performs exact object-id lookup against an
already-built CoverageRegistrySummaryV1. It never admits physical objects,
creates quantity links, changes commercial authority, or performs heuristic
matching.
"""
from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Mapping

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


__all__ = [
    "REASON_NOT_IN_REGISTRY_UNIVERSE",
    "REASON_SCENE_OBJECT_ID_MISSING",
    "RegistryCoverageRecordProviderV1",
]
