"""Live source-derived whole-wall role composition.

Consumes only the already producer-owned gross-wall composition and replays
each exact gross-wall target through WholeWallRoleProducer. No caller role,
perimeter flag, wall membership, quantity, or benchmark expectation enters
this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_live_gross_wall_geometry_composition import (
    LiveGrossWallGeometryComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification
from pb_whole_wall_role_authority import (
    WholeWallRoleAuthority,
    WholeWallRoleProducer,
    WholeWallRoleSelector,
)

LIVE_WHOLE_WALL_ROLE_SCHEMA_VERSION = "1.0.0"
LIVE_WHOLE_WALL_ROLE_RESOLVED = "live_whole_wall_role_composition_resolved"
LIVE_WHOLE_WALL_ROLE_PARTIAL = "live_whole_wall_role_composition_partial"
LIVE_WHOLE_WALL_ROLE_UNAVAILABLE = "live_whole_wall_role_composition_unavailable"


@dataclass(frozen=True)
class LiveWholeWallRoleTrace:
    physical_wall_id: str
    page_id: str
    decision_scope_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record_id: str | None
    role: WallRoleClassification | None


@dataclass(frozen=True)
class LiveWholeWallRoleComposition:
    revision_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    traces: tuple[LiveWholeWallRoleTrace, ...]
    whole_wall_role_authority: WholeWallRoleAuthority | None
    role_selectors: Mapping[str, WholeWallRoleSelector]
    schema_version: str = LIVE_WHOLE_WALL_ROLE_SCHEMA_VERSION


def _reasons(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def compose_live_whole_wall_roles(
    *,
    gross_wall_composition: LiveGrossWallGeometryComposition,
) -> LiveWholeWallRoleComposition:
    if type(gross_wall_composition) is not LiveGrossWallGeometryComposition:
        raise TypeError(
            "gross_wall_composition must be LiveGrossWallGeometryComposition"
        )

    candidate_authority = (
        gross_wall_composition.physical_wall_candidate_authority
    )
    gross_authority = gross_wall_composition.gross_wall_geometry_authority
    if candidate_authority is None or gross_authority is None:
        return LiveWholeWallRoleComposition(
            revision_id=gross_wall_composition.revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_WHOLE_WALL_ROLE_UNAVAILABLE,),
            traces=(),
            whole_wall_role_authority=None,
            role_selectors=MappingProxyType({}),
        )

    producer = WholeWallRoleProducer.from_authorities(
        physical_wall_candidate_authority=candidate_authority,
        gross_wall_geometry_authority=gross_authority,
    )
    selectors: dict[str, WholeWallRoleSelector] = {}
    results = {}
    duplicate_wall_ids: set[str] = set()

    selector_mismatches: set[str] = set()
    for gross_trace in gross_wall_composition.traces:
        wall_id = str(gross_trace.physical_wall_id)
        gross_selector = gross_wall_composition.gross_selectors.get(wall_id)
        if (
            gross_selector is None
            or gross_selector.revision_id != gross_wall_composition.revision_id
            or gross_selector.page_id != gross_trace.page_id
            or gross_selector.decision_scope_id != gross_trace.decision_scope_id
            or gross_selector.physical_wall_id != wall_id
        ):
            selector_mismatches.add(wall_id)
            continue
        selector = WholeWallRoleSelector(
            document_id=gross_selector.document_id,
            revision_id=gross_selector.revision_id,
            source_sha256=gross_selector.source_sha256,
            snapshot_id=gross_selector.snapshot_id,
            page_id=gross_selector.page_id,
            decision_scope_id=gross_selector.decision_scope_id,
            physical_wall_id=wall_id,
        )
        existing = selectors.get(wall_id)
        if existing is not None and existing != selector:
            duplicate_wall_ids.add(wall_id)
            continue
        selectors[wall_id] = selector
        results[wall_id] = producer.publish(selector)

    if duplicate_wall_ids or selector_mismatches or not selectors:
        return LiveWholeWallRoleComposition(
            revision_id=gross_wall_composition.revision_id,
            status=(
                EvidenceResolutionStatus.CONFLICT
                if duplicate_wall_ids or selector_mismatches
                else EvidenceResolutionStatus.ABSTAINED
            ),
            reason_codes=(
                LIVE_WHOLE_WALL_ROLE_PARTIAL
                if duplicate_wall_ids or selector_mismatches
                else LIVE_WHOLE_WALL_ROLE_UNAVAILABLE,
                *(
                    f"duplicate_physical_wall_id:{wall_id}"
                    for wall_id in sorted(duplicate_wall_ids)
                ),
                *(
                    f"gross_role_selector_mismatch:{wall_id}"
                    for wall_id in sorted(selector_mismatches)
                ),
            ),
            traces=(),
            whole_wall_role_authority=producer.authority(),
            role_selectors=MappingProxyType(dict(selectors)),
        )

    traces: list[LiveWholeWallRoleTrace] = []
    for wall_id, selector in sorted(selectors.items()):
        result = results[wall_id]
        record = result.record
        traces.append(
            LiveWholeWallRoleTrace(
                physical_wall_id=wall_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                status=result.status,
                reason_codes=_reasons(result.reason_codes),
                record_id=record.record_id if record is not None else None,
                role=record.role if record is not None else None,
            )
        )

    all_resolved = bool(traces) and all(
        trace.status is EvidenceResolutionStatus.CORROBORATED
        and trace.record_id is not None
        and trace.role is not None
        for trace in traces
    )
    any_conflict = any(
        trace.status is EvidenceResolutionStatus.CONFLICT for trace in traces
    )
    if all_resolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_WHOLE_WALL_ROLE_RESOLVED,)
    elif any_conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (
            LIVE_WHOLE_WALL_ROLE_PARTIAL,
            *(reason for trace in traces for reason in trace.reason_codes),
        )
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_WHOLE_WALL_ROLE_PARTIAL,
            *(reason for trace in traces for reason in trace.reason_codes),
        )

    return LiveWholeWallRoleComposition(
        revision_id=gross_wall_composition.revision_id,
        status=status,
        reason_codes=_reasons(reasons),
        traces=tuple(traces),
        whole_wall_role_authority=producer.authority(),
        role_selectors=MappingProxyType(dict(selectors)),
    )


__all__ = [
    "LIVE_WHOLE_WALL_ROLE_PARTIAL",
    "LIVE_WHOLE_WALL_ROLE_RESOLVED",
    "LIVE_WHOLE_WALL_ROLE_SCHEMA_VERSION",
    "LIVE_WHOLE_WALL_ROLE_UNAVAILABLE",
    "LiveWholeWallRoleComposition",
    "LiveWholeWallRoleTrace",
    "compose_live_whole_wall_roles",
]
