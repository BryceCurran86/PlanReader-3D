"""Live source-owned physical-opening-void composition.

This layer composes existing sealed authorities only. It does not invent width,
height, vertical placement, scale, host geometry, completeness, or commercial
deduction. Every positive void is replayed through PhysicalOpeningVoidProducer
from the exact source-owned opening/host/completeness lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_height_authority import (
    OpeningHeightProducer,
    OpeningHeightSelector,
)
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_physical_opening_void_authority import (
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidProducer,
    PhysicalOpeningVoidSelector,
)
from pb_physical_scale_authority import (
    PhysicalScaleProducer,
    PhysicalScaleSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_schedule_row_height_authority import (
    ScheduleRowHeightProducer,
    ScheduleRowHeightSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION = "1.0.0"
LIVE_PHYSICAL_OPENING_VOID_RESOLVED = "live_physical_opening_void_composition_resolved"
LIVE_PHYSICAL_OPENING_VOID_PARTIAL = "live_physical_opening_void_composition_partial"
LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE = "live_physical_opening_void_composition_unavailable"
LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE = "live_physical_opening_void_upstream_incomplete"


@dataclass(frozen=True)
class LivePhysicalOpeningVoidTrace:
    opening_identity_id: str
    representative_observation_id: str
    page_id: str
    decision_scope_id: str
    width_status: EvidenceResolutionStatus
    width_reason_codes: tuple[str, ...]
    width_record_id: Optional[str]
    schedule_binding_status: EvidenceResolutionStatus
    schedule_binding_reason_codes: tuple[str, ...]
    schedule_binding_record_id: Optional[str]
    height_status: EvidenceResolutionStatus
    height_reason_codes: tuple[str, ...]
    height_record_id: Optional[str]
    vertical_status: EvidenceResolutionStatus
    vertical_reason_codes: tuple[str, ...]
    vertical_record_id: Optional[str]
    scale_status: EvidenceResolutionStatus
    scale_reason_codes: tuple[str, ...]
    scale_record_id: Optional[str]
    void_status: EvidenceResolutionStatus
    void_reason_codes: tuple[str, ...]
    void_record_id: Optional[str]


@dataclass(frozen=True)
class LivePhysicalOpeningVoidComposition:
    revision_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    traces: tuple[LivePhysicalOpeningVoidTrace, ...]
    physical_opening_void_authorities: Mapping[str, PhysicalOpeningVoidAuthority]
    void_selectors: Mapping[str, PhysicalOpeningVoidSelector]
    schema_version: str = LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION


def _reason_tuple(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def compose_live_physical_opening_voids(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
) -> LivePhysicalOpeningVoidComposition:
    """Compose the exact sealed prerequisite chain for every proven opening."""
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    if published is None:
        return LivePhysicalOpeningVoidComposition(
            revision_id=wall_opening_composition.revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE,),
            traces=(),
            physical_opening_void_authorities=MappingProxyType({}),
            void_selectors=MappingProxyType({}),
        )

    semantic_record = wall_opening_composition.semantic_enumeration_result.record
    if semantic_record is None:
        return LivePhysicalOpeningVoidComposition(
            revision_id=wall_opening_composition.revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(
                LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE,
                *wall_opening_composition.semantic_enumeration_result.reason_codes,
            ),
            traces=(),
            physical_opening_void_authorities=MappingProxyType({}),
            void_selectors=MappingProxyType({}),
        )

    physical = wall_opening_composition.physical_opening_authority
    expected_opening_ids = tuple(semantic_record.physical_opening_record_ids)
    opening_selectors: dict[str, ObservationSelector] = {}
    opening_pages: dict[str, str] = {}
    representative_by_opening: dict[str, str] = {}
    existence_by_opening = {}
    for observation_id in semantic_record.representative_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = physical.prove_existence(selector)
        record = existence.existence_record
        if record is None:
            continue
        opening_selectors[record.record_id] = selector
        opening_pages[record.record_id] = str(record.page_id)
        representative_by_opening[record.record_id] = observation_id
        existence_by_opening[record.record_id] = existence

    if not opening_selectors:
        return LivePhysicalOpeningVoidComposition(
            revision_id=wall_opening_composition.revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE,),
            traces=(),
            physical_opening_void_authorities=MappingProxyType({}),
            void_selectors=MappingProxyType({}),
        )

    schedule_binding_producer = (
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    schedule_results = {}
    for opening_id, opening_selector in opening_selectors.items():
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        if binding_selector is None:
            continue
        schedule_results[opening_id] = schedule_binding_producer.publish_scope(
            opening_selector=opening_selector,
            decision_scope_id=binding_selector.decision_scope_id,
        )
    schedule_binding_authority = schedule_binding_producer.authority()

    row_height_producer = ScheduleRowHeightProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    row_vertical_producer = (
        ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    for result in schedule_results.values():
        record = result.record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
        ):
            continue
        row_height_producer.publish_scope(
            ScheduleRowHeightSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                schedule_page_id=record.schedule_page_id,
                schedule_row_observation_ids=record.schedule_row_observation_ids,
            )
        )
        row_vertical_producer.publish_scope(
            ScheduleRowVerticalPlacementSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                schedule_page_id=record.schedule_page_id,
                schedule_row_observation_ids=record.schedule_row_observation_ids,
            )
        )

    height_producer = OpeningHeightProducer.from_authorities(
        source_visibility_producer,
        schedule_binding_authority,
        row_height_producer.authority(),
    )
    vertical_producer = OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=schedule_binding_authority,
        row_vertical_placement_authority=row_vertical_producer.authority(),
    )
    height_results = {}
    vertical_results = {}
    for opening_id in opening_selectors:
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        if binding_selector is None:
            continue
        height_selector = OpeningHeightSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=binding_selector.decision_scope_id,
            opening_record_id=opening_id,
        )
        vertical_selector = OpeningVerticalPlacementSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=binding_selector.decision_scope_id,
            opening_record_id=opening_id,
        )
        height_results[opening_id] = height_producer.publish_scope(height_selector)
        vertical_results[opening_id] = vertical_producer.publish_scope(vertical_selector)

    scale_producer = PhysicalScaleProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    scale_results = {}
    for opening_id, existence in existence_by_opening.items():
        page_id = opening_pages[opening_id]
        source_result = existence.source_observation
        source_observation = (
            getattr(source_result, "observation", None)
            if source_result is not None
            else None
        )
        record = existence.existence_record
        viewport_id = (
            getattr(source_observation, "viewport_id", None)
            or getattr(record, "viewport_id", None)
        )
        scale_results[opening_id] = scale_producer.publish_scope(
            PhysicalScaleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=page_id,
                viewport_id=viewport_id,
            )
        )

    dimension_authority = source_visibility_producer.opening_dimension_authority()
    height_authority = height_producer.authority()
    vertical_authority = vertical_producer.authority()
    scale_authority = scale_producer.authority()

    void_producers: dict[str, PhysicalOpeningVoidProducer] = {}
    void_authorities: dict[str, PhysicalOpeningVoidAuthority] = {}
    for page_id in wall_opening_composition.page_ids:
        universe_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                page_id
            )
        )
        if universe_authority is None:
            continue
        producer = PhysicalOpeningVoidProducer.from_authorities(
            physical_opening_authority=physical,
            opening_universe_authority=universe_authority,
            host_binding_authority=wall_opening_composition.opening_host_binding_authority,
            host_frame_authority=wall_opening_composition.opening_host_frame_authority,
            opening_dimension_authority=dimension_authority,
            opening_height_authority=height_authority,
            vertical_placement_authority=vertical_authority,
            physical_scale_authority=scale_authority,
        )
        void_producers[page_id] = producer

    traces: list[LivePhysicalOpeningVoidTrace] = []
    void_selectors: dict[str, PhysicalOpeningVoidSelector] = {}
    for opening_id, opening_selector in opening_selectors.items():
        page_id = opening_pages[opening_id]
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        producer = void_producers.get(page_id)
        if binding_selector is None or producer is None:
            continue

        width = dimension_authority.resolve_width(opening_selector)
        schedule = schedule_results.get(opening_id)
        height = height_results.get(opening_id)
        vertical = vertical_results.get(opening_id)
        scale = scale_results.get(opening_id)

        selector = PhysicalOpeningVoidSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=binding_selector.decision_scope_id,
            opening_identity_id=opening_id,
        )
        void_selectors[opening_id] = selector
        void = producer.publish(
            opening_selector=opening_selector,
            selector=selector,
        )

        width_record_id = getattr(width, "dimension_record_id", None)
        schedule_record = getattr(schedule, "record", None)
        height_evidence = getattr(height, "evidence", None)
        vertical_evidence = getattr(vertical, "evidence", None)
        scale_evidence = getattr(scale, "evidence", None)
        height_record_id = (
            stable_contract_id(
                "opening_height_evidence",
                height_evidence,
                digest_chars=32,
            )
            if height_evidence is not None
            else None
        )
        vertical_record_id = (
            stable_contract_id(
                "opening_vertical_placement_evidence",
                vertical_evidence,
                digest_chars=32,
            )
            if vertical_evidence is not None
            else None
        )
        traces.append(
            LivePhysicalOpeningVoidTrace(
                opening_identity_id=opening_id,
                representative_observation_id=representative_by_opening[opening_id],
                page_id=page_id,
                decision_scope_id=binding_selector.decision_scope_id,
                width_status=width.status,
                width_reason_codes=_reason_tuple(width.reason_codes),
                width_record_id=width_record_id,
                schedule_binding_status=(
                    schedule.status
                    if schedule is not None
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                schedule_binding_reason_codes=_reason_tuple(
                    getattr(schedule, "reason_codes", ("schedule_binding_unavailable",))
                ),
                schedule_binding_record_id=(
                    schedule_record.record_id if schedule_record is not None else None
                ),
                height_status=(
                    height.status
                    if height is not None
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                height_reason_codes=_reason_tuple(
                    getattr(height, "reason_codes", ("opening_height_unavailable",))
                ),
                height_record_id=height_record_id,
                vertical_status=(
                    vertical.status
                    if vertical is not None
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                vertical_reason_codes=_reason_tuple(
                    getattr(
                        vertical,
                        "reason_codes",
                        ("opening_vertical_placement_unavailable",),
                    )
                ),
                vertical_record_id=vertical_record_id,
                scale_status=(
                    scale.status
                    if scale is not None
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                scale_reason_codes=_reason_tuple(
                    getattr(scale, "reason_codes", ("physical_scale_unavailable",))
                ),
                scale_record_id=(
                    scale_evidence.record_id if scale_evidence is not None else None
                ),
                void_status=void.status,
                void_reason_codes=_reason_tuple(void.reason_codes),
                void_record_id=void.record.record_id if void.record is not None else None,
            )
        )

    for page_id, producer in void_producers.items():
        void_authorities[page_id] = producer.authority()

    traced_opening_ids = {trace.opening_identity_id for trace in traces}
    expected_opening_id_set = set(expected_opening_ids)
    upstream_complete = (
        bool(expected_opening_id_set)
        and set(opening_selectors) == expected_opening_id_set
        and traced_opening_ids == expected_opening_id_set
    )
    has_conflict = any(
        trace.void_status is EvidenceResolutionStatus.CONFLICT for trace in traces
    )
    all_resolved = upstream_complete and all(
        trace.void_status is EvidenceResolutionStatus.CORROBORATED
        and trace.void_record_id is not None
        for trace in traces
    )
    if all_resolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_PHYSICAL_OPENING_VOID_RESOLVED,)
    elif has_conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (
            LIVE_PHYSICAL_OPENING_VOID_PARTIAL,
            *(reason for trace in traces for reason in trace.void_reason_codes),
        )
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_PHYSICAL_OPENING_VOID_PARTIAL,
            *(
                (LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE,)
                if not upstream_complete
                else ()
            ),
            *(reason for trace in traces for reason in trace.void_reason_codes),
        )

    return LivePhysicalOpeningVoidComposition(
        revision_id=wall_opening_composition.revision_id,
        status=status,
        reason_codes=_reason_tuple(reasons),
        traces=tuple(traces),
        physical_opening_void_authorities=MappingProxyType(dict(void_authorities)),
        void_selectors=MappingProxyType(dict(void_selectors)),
    )


__all__ = [
    "LIVE_PHYSICAL_OPENING_VOID_PARTIAL",
    "LIVE_PHYSICAL_OPENING_VOID_RESOLVED",
    "LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION",
    "LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE",
    "LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE",
    "LivePhysicalOpeningVoidComposition",
    "LivePhysicalOpeningVoidTrace",
    "compose_live_physical_opening_voids",
]
