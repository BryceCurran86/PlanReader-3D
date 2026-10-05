"""Live source-owned physical-opening-void composition.

This layer composes existing sealed authorities only. It does not invent width,
height, vertical placement, scale, host geometry, completeness, or commercial
deduction. Every positive void is replayed through PhysicalOpeningVoidProducer
from the exact source-owned opening/host/completeness lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
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
from pb_opening_kind_authority import (
    OPENING_KIND_CONFLICT,
    resolve_opening_kind,
)
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
)
from pb_opening_elevation_frame_area_authority import (
    OpeningElevationFrameAreaProducer,
    OpeningElevationFrameAreaSelector,
)
from pb_opening_label_semantic_authority import (
    OPENING_LABEL_SEMANTIC_CONFLICT,
    OpeningLabelSemanticProducer,
)
from pb_opening_tag_normalization import normalize_opening_tag
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_page_view_class_source_adapter import page_viewport_id
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


LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION = "1.1.0"
LIVE_PHYSICAL_OPENING_VOID_RESOLVED = "live_physical_opening_void_composition_resolved"
LIVE_PHYSICAL_OPENING_VOID_PARTIAL = "live_physical_opening_void_composition_partial"
LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE = "live_physical_opening_void_composition_unavailable"
LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE = "live_physical_opening_void_upstream_incomplete"


@dataclass(frozen=True)
class LiveCanonicalOpeningObject:
    """Persistent physical opening identity with optional authenticated geometry."""

    canonical_opening_id: str
    physical_opening_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    semantic_class: str
    structural_pattern: str
    representative_observation_id: str
    source_observation_ids: tuple[str, ...]
    source_lineage_root_ids: tuple[str, ...]
    source_geometries: tuple[tuple[float, ...], ...]
    host_wall_id: Optional[str]
    host_binding_record_id: Optional[str]
    host_frame_record_id: Optional[str]
    wall_local_frame_id: Optional[str]
    profile_kind: Optional[str]
    coordinate_unit: Optional[str]
    u0: Optional[float]
    u1: Optional[float]
    z0: Optional[float]
    z1: Optional[float]
    width_m: Optional[float]
    height_m: Optional[float]
    area_m2: Optional[float]
    area_basis: Optional[str]
    figured_area_record_id: Optional[str]
    opening_void_record_id: Optional[str]
    opening_universe_record_id: Optional[str]
    width_record_id: Optional[str]
    height_record_id: Optional[str]
    vertical_placement_record_id: Optional[str]
    scale_record_id: Optional[str]
    schedule_binding_record_id: Optional[str]
    opening_kind: Optional[str]
    type_mark: Optional[str]
    schedule_page_id: Optional[str]
    schedule_declared_width_mm: Optional[int]
    schedule_declared_height_mm: Optional[int]
    schedule_declared_count: Optional[int]
    schedule_count_explicit: bool
    schedule_row_observation_ids: tuple[str, ...]
    tag_observation_id: Optional[str]
    evidence_ids: tuple[str, ...]
    geometry_complete: bool
    schedule_row_dimension_basis: str = ""
    schedule_row_basis_source: str = ""
    schema_version: str = LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_opening_id": self.canonical_opening_id,
            "physical_opening_id": self.physical_opening_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "semantic_class": self.semantic_class,
            "structural_pattern": self.structural_pattern,
            "representative_observation_id": self.representative_observation_id,
            "source_observation_ids": list(self.source_observation_ids),
            "source_lineage_root_ids": list(self.source_lineage_root_ids),
            "source_geometries": [list(g) for g in self.source_geometries],
            "host_wall_id": self.host_wall_id,
            "host_binding_record_id": self.host_binding_record_id,
            "host_frame_record_id": self.host_frame_record_id,
            "wall_local_frame_id": self.wall_local_frame_id,
            "profile_kind": self.profile_kind,
            "coordinate_unit": self.coordinate_unit,
            "u0": self.u0,
            "u1": self.u1,
            "z0": self.z0,
            "z1": self.z1,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "area_m2": self.area_m2,
            "area_basis": self.area_basis,
            "figured_area_record_id": self.figured_area_record_id,
            "opening_void_record_id": self.opening_void_record_id,
            "opening_universe_record_id": self.opening_universe_record_id,
            "width_record_id": self.width_record_id,
            "height_record_id": self.height_record_id,
            "vertical_placement_record_id": self.vertical_placement_record_id,
            "scale_record_id": self.scale_record_id,
            "schedule_binding_record_id": self.schedule_binding_record_id,
            "opening_kind": self.opening_kind,
            "type_mark": self.type_mark,
            "schedule_page_id": self.schedule_page_id,
            "schedule_declared_width_mm": self.schedule_declared_width_mm,
            "schedule_declared_height_mm": self.schedule_declared_height_mm,
            "schedule_declared_count": self.schedule_declared_count,
            "schedule_count_explicit": self.schedule_count_explicit,
            "schedule_row_observation_ids": list(self.schedule_row_observation_ids),
            "tag_observation_id": self.tag_observation_id,
            "evidence_ids": list(self.evidence_ids),
            "geometry_complete": self.geometry_complete,
            "schedule_row_dimension_basis": self.schedule_row_dimension_basis,
            "schedule_row_basis_source": self.schedule_row_basis_source,
            "schema_version": self.schema_version,
        }


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
    canonical_openings: tuple[LiveCanonicalOpeningObject, ...] = ()
    schema_version: str = LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION


def _reason_tuple(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _canonical_provenance_ids(values) -> tuple[str, ...]:
    """Deterministic set-like provenance union for one canonical object."""
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in values
                if value is not None and str(value).strip()
            }
        )
    )


def _canonical_opening_area(
    *,
    width_m: Optional[float],
    height_m: Optional[float],
    figured_label_evidence,
    elevation_frame_record=None,
    schedule_record=None,
    geometry_complete: bool = True,
) -> tuple[Optional[float], Optional[str], Optional[str]]:
    """Resolve customer-facing opening area without inventing axis order.

    Existing fully-resolved width+height geometry remains authoritative when the
    physical opening geometry is complete. Otherwise an explicitly based outer-
    frame schedule may provide gross frame area. Failing that, a corroborated
    unordered two-axis figured label may provide only its order-invariant
    product. None of these paths back-fills width_m or height_m.
    """

    figured_record_id = (
        str(figured_label_evidence.evidence_id)
        if figured_label_evidence is not None
        else None
    )

    if geometry_complete and width_m is not None and height_m is not None:
        return (
            float(width_m) * float(height_m),
            "resolved_opening_geometry",
            figured_record_id,
        )

    if elevation_frame_record is not None:
        try:
            elevation_area_m2 = float(elevation_frame_record.area_m2)
        except (TypeError, ValueError, OverflowError):
            elevation_area_m2 = 0.0
        if math.isfinite(elevation_area_m2) and elevation_area_m2 > 0.0:
            return (
                elevation_area_m2,
                "authenticated_elevation_frame",
                str(elevation_frame_record.record_id),
            )

    if (
        schedule_record is not None
        and str(
            getattr(schedule_record, "schedule_row_dimension_basis", "") or ""
        ).strip().lower() == "frame"
        and getattr(schedule_record, "schedule_row_width_mm", None) is not None
        and getattr(schedule_record, "schedule_row_height_mm", None) is not None
    ):
        try:
            frame_width_mm = float(schedule_record.schedule_row_width_mm)
            frame_height_mm = float(schedule_record.schedule_row_height_mm)
        except (TypeError, ValueError, OverflowError):
            frame_width_mm = 0.0
            frame_height_mm = 0.0
        if (
            math.isfinite(frame_width_mm)
            and math.isfinite(frame_height_mm)
            and frame_width_mm > 0.0
            and frame_height_mm > 0.0
        ):
            return (
                (frame_width_mm / 1000.0) * (frame_height_mm / 1000.0),
                "authenticated_frame_schedule",
                None,
            )

    if (
        figured_label_evidence is not None
        and getattr(figured_label_evidence, "area_m2", None) is not None
        and getattr(figured_label_evidence, "axis_order_resolved", None) is False
    ):
        value = float(figured_label_evidence.area_m2)
        if math.isfinite(value) and value > 0.0:
            return (
                value,
                str(
                    getattr(
                        figured_label_evidence,
                        "basis",
                        "figured_opening_label",
                    )
                ),
                figured_record_id,
            )

    return None, None, figured_record_id


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
            canonical_openings=(),
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
            canonical_openings=(),
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
            canonical_openings=(),
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

    scale_producer = source_visibility_producer.physical_scale_producer()
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
    label_dimension_producer = (
        OpeningLabelDimensionProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    label_dimension_results = {
        opening_id: label_dimension_producer.publish_scope(opening_selector)
        for opening_id, opening_selector in opening_selectors.items()
    }
    label_semantic_producer = (
        OpeningLabelSemanticProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    label_semantic_results = {
        opening_id: label_semantic_producer.publish_scope(opening_selector)
        for opening_id, opening_selector in opening_selectors.items()
    }
    elevation_frame_area_authority = (
        OpeningElevationFrameAreaProducer.from_source_visibility_producer(
            source_visibility_producer
        ).authority()
    )
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
    canonical_openings: list[LiveCanonicalOpeningObject] = []
    kind_conflict_opening_ids: set[str] = set()
    void_selectors: dict[str, PhysicalOpeningVoidSelector] = {}
    binding_by_opening = {
        str(trace.opening_identity_id): trace
        for trace in wall_opening_composition.opening_bindings
        if trace.opening_identity_id
    }
    frame_by_opening = {
        str(trace.opening_identity_id): trace
        for trace in wall_opening_composition.host_frames
        if trace.opening_identity_id
    }
    for opening_id, opening_selector in opening_selectors.items():
        page_id = opening_pages[opening_id]
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        producer = void_producers.get(page_id)
        if binding_selector is None or producer is None:
            continue

        width = dimension_authority.resolve_width(opening_selector)
        figured_label = label_dimension_results.get(opening_id)
        figured_label_evidence = getattr(figured_label, "evidence", None)
        semantic_label = label_semantic_results.get(opening_id)
        semantic_label_evidence = getattr(semantic_label, "evidence", None)
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
        normalized_schedule_tag = (
            normalize_opening_tag(schedule_record.tag_mark)
            if schedule_record is not None
            else None
        )
        normalized_plan_tag = normalize_opening_tag(
            getattr(schedule, "authenticated_tag_mark", None)
        )
        plan_tag_kind = (
            "window"
            if normalized_plan_tag is not None
            and normalized_plan_tag.trade_type == "windows"
            else (
                "door"
                if normalized_plan_tag is not None
                and normalized_plan_tag.trade_type == "doors"
                else None
            )
        )
        schedule_trade_type = None
        opening_kind = None
        type_mark = None
        schedule_page_id = None
        schedule_declared_width_mm = None
        schedule_declared_height_mm = None
        schedule_declared_count = None
        schedule_count_explicit = False
        schedule_row_dimension_basis = ""
        schedule_row_basis_source = ""
        schedule_row_observation_ids: tuple[str, ...] = ()
        tag_observation_id = (
            str(getattr(schedule, "authenticated_tag_observation_id", "") or "")
            or None
        )
        if normalized_plan_tag is not None:
            type_mark = normalized_plan_tag.tag
        if schedule_record is not None and normalized_schedule_tag is not None:
            schedule_trade_type = normalized_schedule_tag.trade_type
            type_mark = normalized_schedule_tag.tag
            schedule_page_id = str(schedule_record.schedule_page_id)
            schedule_declared_width_mm = schedule_record.schedule_row_width_mm
            schedule_declared_height_mm = schedule_record.schedule_row_height_mm
            schedule_declared_count = schedule_record.schedule_row_count
            schedule_count_explicit = bool(
                schedule_record.schedule_row_count_explicit
            )
            schedule_row_dimension_basis = str(
                schedule_record.schedule_row_dimension_basis or ""
            )
            schedule_row_basis_source = str(
                schedule_record.schedule_row_basis_source or ""
            )
            schedule_row_observation_ids = tuple(
                schedule_record.schedule_row_observation_ids
            )
            tag_observation_id = (
                str(schedule_record.tag_observation_id)
                if schedule_record.tag_observation_id
                else tag_observation_id
            )
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
        existence_record = existence_by_opening[opening_id].existence_record
        semantic_label_kind = (
            getattr(semantic_label_evidence, "semantic_kind", None)
            if semantic_label_evidence is not None
            else (
                getattr(figured_label_evidence, "semantic_kind", None)
                if figured_label_evidence is not None
                else None
            )
        )
        label_kind_values = tuple(
            value
            for value in (plan_tag_kind, semantic_label_kind)
            if value in {"door", "window"}
        )
        label_kind_conflict = len(set(label_kind_values)) > 1
        combined_label_kind = (
            label_kind_values[0]
            if label_kind_values and not label_kind_conflict
            else None
        )
        kind_resolution = resolve_opening_kind(
            structural_pattern=(
                existence_record.structural_pattern
                if existence_record is not None
                else None
            ),
            schedule_trade_type=schedule_trade_type,
            label_kind=combined_label_kind,
        )
        opening_kind = kind_resolution.opening_kind
        elevation_frame_record = None
        if type_mark and opening_kind in {"door", "window"}:
            elevation_frame_result = elevation_frame_area_authority.resolve(
                OpeningElevationFrameAreaSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    type_mark=type_mark,
                )
            )
            candidate_frame_record = elevation_frame_result.record
            if (
                elevation_frame_result.status is EvidenceResolutionStatus.CORROBORATED
                and candidate_frame_record is not None
                and candidate_frame_record.opening_kind == opening_kind
            ):
                elevation_frame_record = candidate_frame_record
        if (
            label_kind_conflict
            or OPENING_KIND_CONFLICT in kind_resolution.reason_codes
            or OPENING_LABEL_SEMANTIC_CONFLICT
            in tuple(getattr(semantic_label, "reason_codes", ()))
        ):
            kind_conflict_opening_ids.add(opening_id)
            opening_kind = None
        void_record = void.record
        binding_trace = binding_by_opening.get(opening_id)
        frame_trace = frame_by_opening.get(opening_id)

        source_geometries: list[tuple[float, ...]] = []
        existence_result = existence_by_opening[opening_id]
        source_result = getattr(existence_result, "source_observation", None)
        representative_observation = (
            getattr(source_result, "observation", None)
            if source_result is not None
            else None
        )
        if (
            representative_observation is not None
            and getattr(representative_observation, "geometry", None)
        ):
            source_geometries.append(
                tuple(
                    float(value)
                    for value in representative_observation.geometry
                )
            )

        host_wall_id = None
        host_binding_record_id = None
        host_frame_record_id = None
        if (
            binding_trace is not None
            and binding_trace.status is EvidenceResolutionStatus.CORROBORATED
            and binding_trace.host_wall_id
        ):
            host_wall_id = str(binding_trace.host_wall_id)
            host_binding_record_id = binding_trace.record_id
        if (
            frame_trace is not None
            and frame_trace.status is EvidenceResolutionStatus.CORROBORATED
            and frame_trace.host_wall_id
        ):
            host_wall_id = str(frame_trace.host_wall_id)
            host_frame_record_id = frame_trace.record_id

        if void_record is not None:
            host_wall_id = str(void_record.host_wall_id)
            host_binding_record_id = str(void_record.host_binding_record_id)

        width_m = None
        if (
            width.status is EvidenceResolutionStatus.CORROBORATED
            and getattr(width, "value_mm", None) is not None
        ):
            width_m = float(width.value_mm) / 1000.0
        height_m = None
        if (
            height is not None
            and height.status is EvidenceResolutionStatus.CORROBORATED
            and height_evidence is not None
        ):
            height_m = float(height_evidence.height_mm) / 1000.0

        u0 = float(void_record.u0) if void_record is not None else None
        u1 = float(void_record.u1) if void_record is not None else None
        z0 = float(void_record.z0) if void_record is not None else None
        z1 = float(void_record.z1) if void_record is not None else None
        if void_record is not None:
            width_m = u1 - u0
            height_m = z1 - z0
        area_m2, area_basis, figured_area_record_id = _canonical_opening_area(
            width_m=width_m,
            height_m=height_m,
            figured_label_evidence=figured_label_evidence,
            elevation_frame_record=elevation_frame_record,
            schedule_record=schedule_record,
            geometry_complete=void_record is not None,
        )

        if existence_record is not None:
            evidence_ids = _canonical_provenance_ids(
                (
                    existence_record.record_id,
                    *existence_record.source_observation_ids,
                    *existence_record.source_lineage_root_ids,
                    host_binding_record_id,
                    host_frame_record_id,
                    width_record_id,
                    height_record_id,
                    vertical_record_id,
                    (
                        scale_evidence.record_id
                        if scale_evidence is not None
                        else None
                    ),
                    (
                        schedule_record.record_id
                        if schedule_record is not None
                        else None
                    ),
                    tag_observation_id,
                    *schedule_row_observation_ids,
                    figured_area_record_id,
                    *(
                        elevation_frame_record.source_observation_ids
                        if elevation_frame_record is not None
                        else ()
                    ),
                    *(
                        figured_label_evidence.source_text_observation_ids
                        if figured_label_evidence is not None
                        else ()
                    ),
                    *(
                        semantic_label_evidence.source_text_observation_ids
                        if semantic_label_evidence is not None
                        else ()
                    ),
                    *(
                        semantic_label_evidence.legend_observation_ids
                        if semantic_label_evidence is not None
                        else ()
                    ),
                    (
                        void_record.record_id
                        if void_record is not None
                        else None
                    ),
                )
            )
            canonical_openings.append(
                LiveCanonicalOpeningObject(
                    canonical_opening_id=existence_record.record_id,
                    physical_opening_id=existence_record.record_id,
                    document_id=existence_record.document_id,
                    revision_id=existence_record.revision_id,
                    source_sha256=existence_record.source_sha256,
                    snapshot_id=existence_record.snapshot_id,
                    page_id=existence_record.page_id,
                    viewport_id=(
                        str(existence_record.viewport_id)
                        if existence_record.viewport_id is not None
                        else page_viewport_id(existence_record.page_id)
                    ),
                    semantic_class=existence_record.semantic_class,
                    structural_pattern=existence_record.structural_pattern,
                    representative_observation_id=representative_by_opening[opening_id],
                    source_observation_ids=tuple(
                        existence_record.source_observation_ids
                    ),
                    source_lineage_root_ids=tuple(
                        existence_record.source_lineage_root_ids
                    ),
                    source_geometries=tuple(source_geometries),
                    host_wall_id=host_wall_id,
                    host_binding_record_id=host_binding_record_id,
                    host_frame_record_id=host_frame_record_id,
                    wall_local_frame_id=(
                        str(void_record.wall_local_frame_id)
                        if void_record is not None
                        else None
                    ),
                    profile_kind=(
                        str(void_record.profile_kind)
                        if void_record is not None
                        else None
                    ),
                    coordinate_unit=(
                        str(void_record.coordinate_unit)
                        if void_record is not None
                        else None
                    ),
                    u0=u0,
                    u1=u1,
                    z0=z0,
                    z1=z1,
                    width_m=width_m,
                    height_m=height_m,
                    area_m2=area_m2,
                    area_basis=area_basis,
                    figured_area_record_id=figured_area_record_id,
                    opening_void_record_id=(
                        str(void_record.record_id)
                        if void_record is not None
                        else None
                    ),
                    opening_universe_record_id=(
                        str(void_record.opening_universe_record_id)
                        if void_record is not None
                        else None
                    ),
                    width_record_id=width_record_id,
                    height_record_id=height_record_id,
                    vertical_placement_record_id=vertical_record_id,
                    scale_record_id=(
                        str(scale_evidence.record_id)
                        if scale_evidence is not None
                        else None
                    ),
                    schedule_binding_record_id=(
                        str(schedule_record.record_id)
                        if schedule_record is not None
                        else None
                    ),
                    opening_kind=opening_kind,
                    type_mark=type_mark,
                    schedule_page_id=schedule_page_id,
                    schedule_declared_width_mm=schedule_declared_width_mm,
                    schedule_declared_height_mm=schedule_declared_height_mm,
                    schedule_declared_count=schedule_declared_count,
                    schedule_count_explicit=schedule_count_explicit,
                    schedule_row_observation_ids=schedule_row_observation_ids,
                    tag_observation_id=tag_observation_id,
                    evidence_ids=evidence_ids,
                    geometry_complete=void_record is not None,
                    schedule_row_dimension_basis=schedule_row_dimension_basis,
                    schedule_row_basis_source=schedule_row_basis_source,
                )
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
    has_conflict = bool(kind_conflict_opening_ids) or any(
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
            *(
                (OPENING_KIND_CONFLICT,)
                if kind_conflict_opening_ids
                else ()
            ),
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
        canonical_openings=tuple(canonical_openings),
        physical_opening_void_authorities=MappingProxyType(dict(void_authorities)),
        void_selectors=MappingProxyType(dict(void_selectors)),
    )


__all__ = [
    "LIVE_PHYSICAL_OPENING_VOID_PARTIAL",
    "LIVE_PHYSICAL_OPENING_VOID_RESOLVED",
    "LIVE_PHYSICAL_OPENING_VOID_SCHEMA_VERSION",
    "LIVE_PHYSICAL_OPENING_VOID_UNAVAILABLE",
    "LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE",
    "LiveCanonicalOpeningObject",
    "LivePhysicalOpeningVoidComposition",
    "LivePhysicalOpeningVoidTrace",
    "compose_live_physical_opening_voids",
]
