"""Independent behavioral identity attack for Physical Opening Void V2.

TEST ONLY / NEVER MERGE. Two genuine same-lineage physical openings have identical
nominal dimensions. Each must resolve on its own; cross-wiring opening A with the
void selector for opening B must fail closed on exact physical identity.
"""
from __future__ import annotations

import importlib
import importlib.util
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
from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_schedule_opening_instance_binding_authority import ScheduleOpeningInstanceBindingProducer
from pb_schedule_row_height_authority import ScheduleRowHeightProducer, ScheduleRowHeightSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


MODULE_NAME = "pb_physical_opening_void_authority"
HAS_VOID_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_VOID_AUTHORITY,
    strict=True,
    reason="Physical Opening Void V2 production is absent on the validator branch",
)
SCOPE = "wall-source:page-1"


def _pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760.0, height=650.0)
        for y in (100.0, 110.0):
            for x0, x1 in ((20.0, 100.0), (145.0, 260.0), (305.0, 430.0)):
                page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), width=1.0)
        for x in (100.0, 145.0, 260.0, 305.0):
            page.draw_line(fitz.Point(x, 100.0), fitz.Point(x, 110.0), width=1.0)
        for x0, x1, mark in ((100.0, 145.0, "W1"), (260.0, 305.0, "W2")):
            page.draw_line(fitz.Point(x0, 70.0), fitz.Point(x1, 70.0), width=1.0)
            page.draw_line(fitz.Point(x0, 70.0), fitz.Point(x0, 100.0), width=1.0)
            page.draw_line(fitz.Point(x1, 70.0), fitz.Point(x1, 100.0), width=1.0)
            page.insert_text(fitz.Point(x0 + 12.0, 65.0), "900")
            page.insert_text(fitz.Point(x0 + 12.0, 106.0), mark)

        headings = (
            "MARK",
            "ROWDTH-MM",
            "ROHT-MM",
            "ROUGH-OPENING-SILL-MM",
            "ROUGH-OPENING-HEAD-MM",
        )
        xs = (50.0, 150.0, 250.0, 350.0, 550.0)
        for text, x in zip(headings, xs):
            page.insert_text(fitz.Point(x, 500.0), text)
        for row_y, mark in ((530.0, "W1"), (550.0, "W2")):
            for text, x in zip((mark, "900", "2100", "900", "3000"), xs):
                page.insert_text(fitz.Point(x, row_y), text)

        page.draw_line(fitz.Point(500.0, 250.0), fitz.Point(550.0, 250.0), width=1.0)
        page.draw_line(fitz.Point(500.0, 242.0), fitz.Point(500.0, 258.0), width=1.0)
        page.draw_line(fitz.Point(550.0, 242.0), fitz.Point(550.0, 258.0), width=1.0)
        page.insert_text(fitz.Point(498.0, 274.0), "0")
        page.insert_text(fitz.Point(546.0, 274.0), "1m")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _selectors(published, physical: PhysicalOpeningAuthority) -> tuple[ObservationSelector, ...]:
    by_id: dict[str, ObservationSelector] = {}
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
            by_id.setdefault(result.existence_record.record_id, selector)
    assert len(by_id) == 2, f"expected two physical openings, got {len(by_id)}"
    return tuple(by_id[key] for key in sorted(by_id))


def _universe(source, published):
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
        producer_method="physical-opening-void-cross-identity-validator",
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


def _chain():
    mod = importlib.import_module(MODULE_NAME)
    source = SourceVisibilityProducer(
        producer_method="physical-opening-void-cross-identity-validator",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="physical-opening-void-cross-identity",
        source_bytes=_pdf(),
        source_locator="memory://physical-opening-void-cross-identity.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    opening_selectors = _selectors(published, physical)
    openings = tuple(physical.prove_existence(selector) for selector in opening_selectors)
    assert all(item.existence_record is not None for item in openings)

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    wall_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_scope = OpeningHostWallUniverseSelector(
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
    host_selectors = []
    for opening_selector in opening_selectors:
        host = host_producer.publish(
            opening_left_selector=opening_selector,
            opening_right_selector=opening_selector,
            host_universe_selector=host_scope,
        )
        assert host.status is EvidenceResolutionStatus.CORROBORATED
        assert host.record is not None
        host_selectors.append(
            OpeningHostBindingSelector(
                document_id=host.record.document_id,
                revision_id=host.record.revision_id,
                source_sha256=host.record.source_sha256,
                snapshot_id=host.record.snapshot_id,
                page_id=host.record.page_id,
                decision_scope_id=host.record.decision_scope_id,
                opening_identity_id=host.record.opening_identity_id,
            )
        )

    # Snapshot the host authority only after both valid host records exist.
    frame_producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=host_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    for opening_selector, host_selector in zip(opening_selectors, host_selectors):
        frame = frame_producer.publish(
            opening_selector=opening_selector,
            host_binding_selector=host_selector,
        )
        assert frame.status is EvidenceResolutionStatus.CORROBORATED

    binding = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    row_height = ScheduleRowHeightProducer.from_source_visibility_producer(source)
    row_vertical = ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(source)
    for opening_selector in opening_selectors:
        schedule = binding.publish_scope(opening_selector=opening_selector, decision_scope_id=SCOPE)
        assert schedule.status is EvidenceResolutionStatus.CORROBORATED
        assert schedule.record is not None
        row_height.publish_scope(
            ScheduleRowHeightSelector(
                document_id=schedule.record.document_id,
                revision_id=schedule.record.revision_id,
                source_sha256=schedule.record.source_sha256,
                snapshot_id=schedule.record.snapshot_id,
                schedule_page_id=schedule.record.schedule_page_id,
                schedule_row_observation_ids=schedule.record.schedule_row_observation_ids,
            )
        )
        row_vertical.publish_scope(
            ScheduleRowVerticalPlacementSelector(
                document_id=schedule.record.document_id,
                revision_id=schedule.record.revision_id,
                source_sha256=schedule.record.source_sha256,
                snapshot_id=schedule.record.snapshot_id,
                schedule_page_id=schedule.record.schedule_page_id,
                schedule_row_observation_ids=schedule.record.schedule_row_observation_ids,
            )
        )

    height = OpeningHeightProducer.from_authorities(source, binding.authority(), row_height.authority())
    vertical = OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=binding.authority(),
        row_vertical_placement_authority=row_vertical.authority(),
    )
    void_selectors = []
    for opening in openings:
        record = opening.existence_record
        assert record is not None
        height.publish_scope(
            OpeningHeightSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                decision_scope_id=SCOPE,
                opening_record_id=record.record_id,
            )
        )
        vertical.publish_scope(
            OpeningVerticalPlacementSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                decision_scope_id=SCOPE,
                opening_record_id=record.record_id,
            )
        )
        void_selectors.append(
            mod.PhysicalOpeningVoidSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                page_id=record.page_id,
                decision_scope_id=SCOPE,
                opening_identity_id=record.record_id,
            )
        )

    scale = PhysicalScaleProducer.from_source_visibility_producer(source)
    scale_result = scale.publish_scope(
        PhysicalScaleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=None,
        )
    )
    assert scale_result.status is EvidenceResolutionStatus.CORROBORATED

    producer = mod.PhysicalOpeningVoidProducer.from_authorities(
        physical_opening_authority=physical,
        opening_universe_authority=_universe(source, published),
        host_binding_authority=host_producer.authority(),
        host_frame_authority=frame_producer.authority(),
        opening_dimension_authority=source.opening_dimension_authority(),
        opening_height_authority=height.authority(),
        vertical_placement_authority=vertical.authority(),
        physical_scale_authority=scale.authority(),
    )
    return mod, producer, opening_selectors, tuple(void_selectors)


@EXPECTED_RED
def test_two_real_openings_positive_individually_but_cross_wire_fails_closed() -> None:
    mod, producer, opening_selectors, void_selectors = _chain()
    positives = tuple(
        producer.publish(opening_selector=opening_selector, selector=void_selector)
        for opening_selector, void_selector in zip(opening_selectors, void_selectors)
    )
    assert len(positives) == 2
    assert all(item.status is EvidenceResolutionStatus.CORROBORATED for item in positives)
    assert all(item.record is not None for item in positives)
    assert tuple(item.record.opening_identity_id for item in positives) == tuple(
        selector.opening_identity_id for selector in void_selectors
    )

    for opening_selector, void_selector in (
        (opening_selectors[1], void_selectors[0]),
        (opening_selectors[0], void_selectors[1]),
    ):
        result = producer.publish(opening_selector=opening_selector, selector=void_selector)
        assert result.status is EvidenceResolutionStatus.CONFLICT
        assert mod.PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH in result.reason_codes
        assert result.record is None
