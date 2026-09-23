"""Live source-owned net-wall Boolean-union composition.

Joins the already sealed physical-opening-void, opening-universe, authorized
opening-deduction, and gross-wall-geometry authorities. The public boundary
contains only upstream producer-owned compositions; callers cannot supply wall
areas, opening areas, void polygons, counts, completeness flags, or deduction
booleans.

Unknown gross geometry, incomplete opening universe, unresolved deductions,
wrong frames, or invalid void geometry remain unknown through the existing
NetWallBooleanUnionProducer. Gross area is never silently relabelled as net.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_live_gross_wall_geometry_composition import (
    LiveGrossWallGeometryComposition,
)
from pb_live_opening_deduction_composition import (
    LiveOpeningDeductionComposition,
)
from pb_live_physical_opening_void_composition import (
    LivePhysicalOpeningVoidComposition,
)
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionProducer,
    NetWallBooleanUnionSelector,
)


LIVE_NET_WALL_SCHEMA_VERSION = "1.0.0"
LIVE_NET_WALL_RESOLVED = "live_net_wall_boolean_composition_resolved"
LIVE_NET_WALL_PARTIAL = "live_net_wall_boolean_composition_partial"
LIVE_NET_WALL_UNAVAILABLE = "live_net_wall_boolean_composition_unavailable"
LIVE_NET_WALL_UPSTREAM_MISMATCH = "live_net_wall_boolean_upstream_mismatch"


@dataclass(frozen=True)
class LiveNetWallTrace:
    physical_wall_id: str
    target_scope_id: str
    page_id: str
    decision_scope_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record_id: str | None
    gross_wall_record_id: str | None
    opening_deduction_record_ids: tuple[str, ...]
    physical_void_record_ids: tuple[str, ...]
    gross_area_m2: float | None
    void_union_area_m2: float | None
    net_area_m2: float | None


@dataclass(frozen=True)
class LiveNetWallBooleanComposition:
    revision_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    traces: tuple[LiveNetWallTrace, ...]
    net_wall_authorities: Mapping[str, NetWallBooleanUnionAuthority]
    net_wall_selectors: Mapping[tuple[str, str], NetWallBooleanUnionSelector]
    schema_version: str = LIVE_NET_WALL_SCHEMA_VERSION


def _reasons(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def compose_live_net_wall_boolean_union(
    *,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
    physical_void_composition: LivePhysicalOpeningVoidComposition,
    opening_deduction_composition: LiveOpeningDeductionComposition,
    gross_wall_composition: LiveGrossWallGeometryComposition,
) -> LiveNetWallBooleanComposition:
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )
    if type(physical_void_composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError(
            "physical_void_composition must be LivePhysicalOpeningVoidComposition"
        )
    if type(opening_deduction_composition) is not LiveOpeningDeductionComposition:
        raise TypeError(
            "opening_deduction_composition must be LiveOpeningDeductionComposition"
        )
    if type(gross_wall_composition) is not LiveGrossWallGeometryComposition:
        raise TypeError(
            "gross_wall_composition must be LiveGrossWallGeometryComposition"
        )

    revision_id = wall_opening_composition.revision_id
    if any(
        value != revision_id
        for value in (
            physical_void_composition.revision_id,
            opening_deduction_composition.revision_id,
            gross_wall_composition.revision_id,
        )
    ):
        return LiveNetWallBooleanComposition(
            revision_id=revision_id,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(LIVE_NET_WALL_UPSTREAM_MISMATCH,),
            traces=(),
            net_wall_authorities=MappingProxyType({}),
            net_wall_selectors=MappingProxyType({}),
        )

    gross_authority = gross_wall_composition.gross_wall_geometry_authority
    if gross_authority is None:
        return LiveNetWallBooleanComposition(
            revision_id=revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_NET_WALL_UNAVAILABLE,),
            traces=(),
            net_wall_authorities=MappingProxyType({}),
            net_wall_selectors=MappingProxyType({}),
        )

    targets = tuple(opening_deduction_composition.target_scope_ids)
    if not targets:
        return LiveNetWallBooleanComposition(
            revision_id=revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_NET_WALL_UNAVAILABLE,),
            traces=(),
            net_wall_authorities=MappingProxyType({}),
            net_wall_selectors=MappingProxyType({}),
        )

    producers: dict[str, NetWallBooleanUnionProducer] = {}
    results = {}
    selectors: dict[tuple[str, str], NetWallBooleanUnionSelector] = {}

    for gross_trace in gross_wall_composition.traces:
        page_id = gross_trace.page_id
        void_authority = (
            physical_void_composition.physical_opening_void_authorities.get(page_id)
        )
        deduction_authority = (
            opening_deduction_composition.deduction_authorities.get(page_id)
        )
        universe_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                page_id
            )
        )
        if (
            void_authority is None
            or deduction_authority is None
            or universe_authority is None
        ):
            continue

        producer = producers.get(page_id)
        if producer is None:
            producer = NetWallBooleanUnionProducer.from_authorities(
                physical_void_authority=void_authority,
                opening_deduction_authority=deduction_authority,
                opening_universe_authority=universe_authority,
                gross_wall_authority=gross_authority,
            )
            producers[page_id] = producer

        for target_scope_id in targets:
            selector = NetWallBooleanUnionSelector(
                document_id=wall_opening_composition.semantic_enumeration_result.record.document_id,
                revision_id=revision_id,
                source_sha256=wall_opening_composition.semantic_enumeration_result.record.source_sha256,
                snapshot_id=wall_opening_composition.semantic_enumeration_result.record.snapshot_id,
                page_id=page_id,
                decision_scope_id=gross_trace.decision_scope_id,
                physical_wall_id=gross_trace.physical_wall_id,
                trade_scope_id=target_scope_id,
            )
            selectors[(gross_trace.physical_wall_id, target_scope_id)] = selector
            results[selector.key] = producer.publish(selector)

    if not selectors:
        return LiveNetWallBooleanComposition(
            revision_id=revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_NET_WALL_UNAVAILABLE,),
            traces=(),
            net_wall_authorities=MappingProxyType({}),
            net_wall_selectors=MappingProxyType({}),
        )

    traces: list[LiveNetWallTrace] = []
    for selector in selectors.values():
        result = results.get(selector.key)
        if result is None:
            continue
        record = result.record
        traces.append(
            LiveNetWallTrace(
                physical_wall_id=selector.physical_wall_id,
                target_scope_id=selector.trade_scope_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                status=result.status,
                reason_codes=_reasons(result.reason_codes),
                record_id=getattr(record, "record_id", None),
                gross_wall_record_id=getattr(
                    record, "gross_wall_record_id", None
                ),
                opening_deduction_record_ids=tuple(
                    getattr(record, "opening_deduction_record_ids", ()) or ()
                ),
                physical_void_record_ids=tuple(
                    getattr(record, "physical_void_record_ids", ()) or ()
                ),
                gross_area_m2=(
                    float(record.gross_area_m2)
                    if record is not None
                    else None
                ),
                void_union_area_m2=(
                    float(record.void_union_area_m2)
                    if record is not None
                    else None
                ),
                net_area_m2=(
                    float(record.net_area_m2)
                    if record is not None
                    and record.net_area_m2 is not None
                    else None
                ),
            )
        )

    all_resolved = bool(traces) and len(traces) == len(selectors) and all(
        trace.status is EvidenceResolutionStatus.CORROBORATED
        and trace.record_id is not None
        and trace.net_area_m2 is not None
        for trace in traces
    )
    any_conflict = any(
        trace.status is EvidenceResolutionStatus.CONFLICT for trace in traces
    )
    if all_resolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_NET_WALL_RESOLVED,)
    elif any_conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (
            LIVE_NET_WALL_PARTIAL,
            *(reason for trace in traces for reason in trace.reason_codes),
        )
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_NET_WALL_PARTIAL,
            *(reason for trace in traces for reason in trace.reason_codes),
        )

    return LiveNetWallBooleanComposition(
        revision_id=revision_id,
        status=status,
        reason_codes=_reasons(reasons),
        traces=tuple(traces),
        net_wall_authorities=MappingProxyType(
            {
                page_id: producer.authority()
                for page_id, producer in producers.items()
            }
        ),
        net_wall_selectors=MappingProxyType(dict(selectors)),
    )


__all__ = [
    "LIVE_NET_WALL_PARTIAL",
    "LIVE_NET_WALL_RESOLVED",
    "LIVE_NET_WALL_SCHEMA_VERSION",
    "LIVE_NET_WALL_UNAVAILABLE",
    "LIVE_NET_WALL_UPSTREAM_MISMATCH",
    "LiveNetWallBooleanComposition",
    "LiveNetWallTrace",
    "compose_live_net_wall_boolean_union",
]
