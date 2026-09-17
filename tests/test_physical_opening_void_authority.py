"""Production regressions for the physical opening void authority."""
from __future__ import annotations

import dataclasses
import inspect
from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_height_authority import OpeningHeightProducer, OpeningHeightSelector
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessProducer,
)
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
    PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED,
    PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidProducer,
    PhysicalOpeningVoidSelector,
)
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_schedule_row_height_authority import ScheduleRowHeightProducer, ScheduleRowHeightSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SCOPE = "wall-source:page-1"


def _pdf(*, width_text: str = "900", height_text: str = "2100") -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760.0, height=650.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((145.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((145.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((145.0, 100.0), (145.0, 110.0)),
            ((100.0, 70.0), (145.0, 70.0)),
            ((100.0, 70.0), (100.0, 100.0)),
            ((145.0, 70.0), (145.0, 100.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        page.insert_text(fitz.Point(112.0, 65.0), width_text)
        page.insert_text(fitz.Point(112.0, 106.0), "W1")

        headings = (
            "MARK",
            "ROWDTH-MM",
            "ROHT-MM",
            "ROUGH-OPENING-SILL-MM",
            "ROUGH-OPENING-HEAD-MM",
        )
        values = ("W1", "900", height_text, "900", "3000")
        xs = (50.0, 150.0, 250.0, 350.0, 550.0)
        for text, x in zip(headings, xs):
            page.insert_text(fitz.Point(x, 500.0), text)
        for text, x in zip(values, xs):
            page.insert_text(fitz.Point(x, 530.0), text)

        # The 45 pt opening span represents 900 mm.  This independent 1000 mm
        # native scale bar therefore spans exactly 50 source points.
        bar_x0 = 300.0
        bar_x1 = bar_x0 + 50.0
        bar_y = 250.0
        page.draw_line(fitz.Point(bar_x0, bar_y), fitz.Point(bar_x1, bar_y), width=1.0)
        page.draw_line(
            fitz.Point(bar_x0, bar_y - 8.0),
            fitz.Point(bar_x0, bar_y + 8.0),
            width=1.0,
        )
        page.draw_line(
            fitz.Point(bar_x1, bar_y - 8.0),
            fitz.Point(bar_x1, bar_y + 8.0),
            width=1.0,
        )
        page.insert_text(fitz.Point(bar_x0 - 2.0, bar_y + 24.0), "0")
        page.insert_text(fitz.Point(bar_x1 - 4.0, bar_y + 24.0), "1m")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _opening_selector(published, physical: PhysicalOpeningAuthority) -> ObservationSelector:
    resolved = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS and result.existence_record is not None:
            resolved.setdefault(result.existence_record.record_id, selector)
    assert len(resolved) == 1
    return next(iter(resolved.values()))


def _complete_opening_universe(source, published):
    visible = source.authority()
    primitives = []
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        observation = visible.resolve_visible(selector).observation
        if observation is None or observation.observation_kind != "native_pdf_visible_segment":
            continue
        primitives.append(
            SimpleNamespace(
                primitive_id=observation.observation_id,
                page_id=observation.page_id,
                geometry=observation.geometry,
                layer="native-pdf-visible",
                clip_known=True,
                clip_present=False,
                clip=None,
            )
        )
    producer = OpeningUniverseCompletenessProducer(
        producer_method="physical-opening-void-production-test",
        producer_version="1.0",
    )
    record = producer.publish_enumeration(
        decision_scope_id=SCOPE,
        decision_scope_kind="full-source-page",
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_ids=("1",),
        viewport_id=None,
        coverage=published.coverage,
        source_primitives=tuple(primitives),
        enumerated_primitives=tuple(primitives),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )
    assert record.decision_scope_complete
    return producer.authority()


def _fixture(*, width_text: str = "900", height_text: str = "2100"):
    source = SourceVisibilityProducer(
        producer_method="physical-opening-void-production-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="physical-opening-void-production",
        source_bytes=_pdf(width_text=width_text, height_text=height_text),
        source_locator="memory://physical-opening-void-production.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    opening_selector = _opening_selector(published, physical)
    opening = physical.prove_existence(opening_selector)
    assert opening.existence_record is not None

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source
    ).authority()
    wall_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_universe_selector = OpeningHostWallUniverseSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id=SCOPE,
    )
    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=wall_universe,
    )
    host = host_producer.publish(
        opening_left_selector=opening_selector,
        opening_right_selector=opening_selector,
        host_universe_selector=host_universe_selector,
    )
    assert host.status is EvidenceResolutionStatus.CORROBORATED
    assert host.record is not None
    host_selector = OpeningHostBindingSelector(
        document_id=host.record.document_id,
        revision_id=host.record.revision_id,
        source_sha256=host.record.source_sha256,
        snapshot_id=host.record.snapshot_id,
        page_id=host.record.page_id,
        decision_scope_id=host.record.decision_scope_id,
        opening_identity_id=host.record.opening_identity_id,
    )
    frame_producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=host_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    frame = frame_producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=host_selector,
    )
    assert frame.status is EvidenceResolutionStatus.CORROBORATED

    schedule_binding = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source
    )
    schedule = schedule_binding.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=SCOPE,
    )
    assert schedule.status is EvidenceResolutionStatus.CORROBORATED
    assert schedule.record is not None

    row_height = ScheduleRowHeightProducer.from_source_visibility_producer(source)
    row_height_selector = ScheduleRowHeightSelector(
        document_id=schedule.record.document_id,
        revision_id=schedule.record.revision_id,
        source_sha256=schedule.record.source_sha256,
        snapshot_id=schedule.record.snapshot_id,
        schedule_page_id=schedule.record.schedule_page_id,
        schedule_row_observation_ids=schedule.record.schedule_row_observation_ids,
    )
    row_height.publish_scope(row_height_selector)
    height_producer = OpeningHeightProducer.from_authorities(
        source,
        schedule_binding.authority(),
        row_height.authority(),
    )
    height_selector = OpeningHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id=SCOPE,
        opening_record_id=opening.existence_record.record_id,
    )
    height_producer.publish_scope(height_selector)

    row_vertical = ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(source)
    row_vertical_selector = ScheduleRowVerticalPlacementSelector(
        document_id=schedule.record.document_id,
        revision_id=schedule.record.revision_id,
        source_sha256=schedule.record.source_sha256,
        snapshot_id=schedule.record.snapshot_id,
        schedule_page_id=schedule.record.schedule_page_id,
        schedule_row_observation_ids=schedule.record.schedule_row_observation_ids,
    )
    row_vertical.publish_scope(row_vertical_selector)
    vertical_producer = OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=schedule_binding.authority(),
        row_vertical_placement_authority=row_vertical.authority(),
    )
    vertical_selector = OpeningVerticalPlacementSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id=SCOPE,
        opening_record_id=opening.existence_record.record_id,
    )
    vertical_producer.publish_scope(vertical_selector)

    scale_producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    scale_selector = PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=None,
    )
    scale = scale_producer.publish_scope(scale_selector)
    assert scale.status is EvidenceResolutionStatus.CORROBORATED

    selector = PhysicalOpeningVoidSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id=SCOPE,
        opening_identity_id=opening.existence_record.record_id,
    )
    producer = PhysicalOpeningVoidProducer.from_authorities(
        physical_opening_authority=physical,
        opening_universe_authority=_complete_opening_universe(source, published),
        host_binding_authority=host_producer.authority(),
        host_frame_authority=frame_producer.authority(),
        opening_dimension_authority=source.opening_dimension_authority(),
        opening_height_authority=height_producer.authority(),
        vertical_placement_authority=vertical_producer.authority(),
        physical_scale_authority=scale_producer.authority(),
    )
    return producer, opening_selector, selector


def test_real_source_chain_resolves_wall_local_metric_void_and_replays() -> None:
    producer, opening_selector, selector = _fixture()
    result = producer.publish(opening_selector=opening_selector, selector=selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == frozenset([PHYSICAL_OPENING_VOID_RESOLVED])
    assert result.record is not None
    assert result.record.coordinate_unit == "metre"
    assert result.record.profile_kind == "rectangular_rough_opening"
    assert result.record.u1 - result.record.u0 == pytest.approx(0.9, abs=1e-9)
    assert result.record.z0 == pytest.approx(0.9)
    assert result.record.z1 == pytest.approx(3.0)
    assert producer.authority().resolve(selector) == result


def test_cross_wired_opening_identity_fails_closed() -> None:
    producer, opening_selector, selector = _fixture()
    result = producer.publish(
        opening_selector=opening_selector,
        selector=dataclasses.replace(selector, opening_identity_id="other-opening"),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH in result.reason_codes
    assert result.record is None


def test_missing_height_and_conflicting_source_width_never_mint_void() -> None:
    missing_height, opening_selector, selector = _fixture(height_text="")
    height_result = missing_height.publish(
        opening_selector=opening_selector,
        selector=selector,
    )
    assert height_result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED in height_result.reason_codes

    conflicting_width, opening_selector2, selector2 = _fixture(width_text="1000")
    width_result = conflicting_width.publish(
        opening_selector=opening_selector2,
        selector=selector2,
    )
    assert width_result.status is EvidenceResolutionStatus.CONFLICT
    assert PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT in width_result.reason_codes


def test_authority_and_producer_are_sealed_and_have_no_raw_truth_surface() -> None:
    with pytest.raises(TypeError):
        PhysicalOpeningVoidAuthority({})
    forbidden = {
        "host_wall_id",
        "width_mm",
        "height_mm",
        "u0",
        "u1",
        "z0",
        "z1",
        "scale",
        "mm_per_point",
        "profile",
        "deductible",
    }
    assert not (set(inspect.signature(PhysicalOpeningVoidProducer.publish).parameters) & forbidden)
