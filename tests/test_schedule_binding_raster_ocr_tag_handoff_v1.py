from __future__ import annotations

import inspect

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_TAGS,
    BINDING_NO_CONTAINED_TAG,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_opening_candidate_authority import authenticate_viewport_decision
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    SCOPE,
    _draw_opening,
    _insert_schedule_table,
    _opening_selector,
)


def _fixture(*, native_tag: str | None = None) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    if native_tag is not None:
        page.insert_text(fitz.Point(112.0, 106.0), native_tag, color=(0, 0, 0))
    _insert_schedule_table(
        page,
        (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
    )
    payload = doc.tobytes()
    doc.close()
    return payload


def _page_observation_id(source: SourceVisibilityProducer, published) -> str:
    authority = source._producer.authority()  # test-only introspection
    for observation_id in published.snapshot.observation_ids:
        resolved = authority.resolve(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            resolved.observation is not None
            and resolved.observation.observation_kind == "native_pdf_page"
            and resolved.observation.page_id == "1"
        ):
            return observation_id
    raise AssertionError("fixture must expose native page observation")


def _viewport_decision(source: SourceVisibilityProducer, published):
    page_observation_id = _page_observation_id(source, published)
    selector = ViewportViewClassSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        viewport_id="page:1",
    )
    view_producer = ViewportViewClassProducer.create()
    view_producer.publish(
        selector,
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=(page_observation_id,),
    )
    viewport = SegmentedViewport(
        view_id="page:1",
        page_number=1,
        view_type=VIEW_KIND_FLOOR_PLAN,
        label="FLOOR PLAN",
        title_bbox=(0.0, 0.0, 80.0, 20.0),
        bounding_box=(0.0, 0.0, 700.0, 650.0),
        status="resolved",
        boundary_source="page_scope",
        confidence=1.0,
    )
    decision = authenticate_viewport_decision(
        viewport=viewport,
        view_class_authority=view_producer.authority(),
        selector=selector,
    )
    assert decision.status is EvidenceResolutionStatus.CORROBORATED
    return decision


def _ocr_line(text: str, bbox_pt: tuple[float, float, float, float]) -> OCRLine:
    scale = 300.0 / 72.0
    x0, y0, x1, y1 = bbox_pt
    return OCRLine(
        text=text,
        confidence=0.99,
        bbox_px=(x0 * scale, y0 * scale, x1 * scale, y1 * scale),
        bbox_pt=(999.0, 999.0, 1000.0, 1000.0),
    )


def _ingest(document_id: str, *, native_tag: str | None = None):
    source = SourceVisibilityProducer(
        producer_method="ocr-binding-regression",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_fixture(native_tag=native_tag),
        source_locator=f"memory://{document_id}.pdf",
    )
    return source, published


def _augment(source, published, lines):
    old_selector = _opening_selector(published, source.authority())
    opening_observation_id = old_selector.observation_id
    decision = _viewport_decision(source, published)
    tags, updated = source.augment_with_raster_ocr_tags_for_tests(
        published.revision.revision_id,
        viewport_decision=decision,
        backend=MockOCRBackend(tuple(lines)),
    )
    selector = ObservationSelector(
        document_id=updated.revision.document_id,
        revision_id=updated.revision.revision_id,
        source_sha256=updated.revision.source_sha256,
        snapshot_id=updated.snapshot.snapshot_id,
        observation_id=opening_observation_id,
    )
    return tags, updated, selector


def _bind(source, selector):
    producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    return producer.publish_scope(
        opening_selector=selector,
        decision_scope_id=SCOPE,
    )


def test_ocr_tag_inside_aperture_binds_existing_native_schedule_row() -> None:
    source, published = _ingest("ocr-plan-tag-positive")
    tags, updated, selector = _augment(
        source,
        published,
        (_ocr_line("W1", (112.0, 102.0, 126.0, 108.0)),),
    )

    assert len(tags) == 1
    assert tags[0].observation_id in updated.ocr_tag_observation_ids
    # Existing physical evidence remains valid after the OCR-derived snapshot.
    assert _opening_selector(updated, source.authority()).observation_id == selector.observation_id

    result = _bind(source, selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "W1"
    assert result.record.tag_observation_id == tags[0].observation_id
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100


def test_ocr_tag_outside_aperture_does_not_bind() -> None:
    source, published = _ingest("ocr-plan-tag-outside")
    _tags, _updated, selector = _augment(
        source,
        published,
        (_ocr_line("W1", (180.0, 102.0, 194.0, 108.0)),),
    )

    result = _bind(source, selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes


def test_overlapping_native_and_ocr_observation_of_same_mark_is_not_false_conflict() -> None:
    source, published = _ingest("ocr-native-duplicate", native_tag="W1")
    _tags, _updated, selector = _augment(
        source,
        published,
        (_ocr_line("W1", (111.0, 101.0, 127.0, 109.0)),),
    )

    result = _bind(source, selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "W1"


def test_distinct_ocr_marks_in_same_aperture_remain_ambiguous() -> None:
    source, published = _ingest("ocr-plan-tag-conflict")
    _tags, _updated, selector = _augment(
        source,
        published,
        (
            _ocr_line("W1", (104.0, 102.0, 116.0, 108.0)),
            _ocr_line("W2", (122.0, 102.0, 134.0, 108.0)),
        ),
    )

    result = _bind(source, selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_TAGS in result.reason_codes



def test_distinct_same_mark_ocr_boxes_are_not_collapsed() -> None:
    source, published = _ingest("ocr-same-mark-distinct")
    _tags, _updated, selector = _augment(
        source,
        published,
        (
            _ocr_line("W1", (102.0, 102.0, 113.0, 108.0)),
            _ocr_line("W1", (126.0, 102.0, 137.0, 108.0)),
        ),
    )

    result = _bind(source, selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_TAGS in result.reason_codes

def test_production_ocr_handoff_accepts_no_backend_or_caller_text() -> None:
    params = set(inspect.signature(SourceVisibilityProducer.augment_with_raster_ocr_tags).parameters)
    assert params == {"self", "revision_id", "viewport_decision"}
