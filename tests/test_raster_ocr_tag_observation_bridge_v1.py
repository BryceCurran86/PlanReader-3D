"""Adversarial tests for the producer-owned raster-OCR -> TagObservation bridge.

The source PDF ingestion, immutable page raster boundary, SourceObservationAuthority,
viewport authentication, and OpeningIdentityResolver are real.  Only OCR engine
output is mocked, through an explicit test-only factory that production construction
rejects.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    OCRLine,
    PortableRasterOCRSelector,
)
from pb_raster_ocr_tag_observation_bridge import RasterOCRTagObservationProducer
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_opening_candidate_authority import (
    IdentityState,
    OpeningIdentityResolver,
    authenticate_viewport_decision,
)
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)
from tests.test_source_opening_universe_evidence_v1 import make_candidate


def _ingest_pages(document_id: str, page_count: int = 1):
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=1000, height=1000)
    payload = doc.tobytes()
    doc.close()

    producer = SourceObservationProducer(
        producer_method="test_producer",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    authority = producer.authority()

    page_ids = {}
    for obs_id in published.snapshot.observation_ids:
        resolved = authority.resolve(
            ObservationSelector(
                document_id=document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=obs_id,
            )
        )
        if (
            resolved.observation is not None
            and resolved.observation.observation_kind == "native_pdf_page"
        ):
            page_ids[resolved.observation.page_id] = obs_id

    return producer, authority, published, page_ids


def _viewport_decision(
    *,
    published,
    page_observation_id: str,
    page_number: int = 1,
    viewport_id: str = "vp_1",
    view_kind: str = VIEW_KIND_FLOOR_PLAN,
):
    selector = ViewportViewClassSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        viewport_id=viewport_id,
    )
    producer = ViewportViewClassProducer.create()
    producer.publish(
        selector,
        view_kind=view_kind,
        evidence_observation_ids=(page_observation_id,),
    )
    viewport = SegmentedViewport(
        view_id=viewport_id,
        page_number=page_number,
        view_type=view_kind,
        label="TEST VIEW",
        title_bbox=(0.0, 0.0, 50.0, 20.0),
        bounding_box=(0.0, 0.0, 1000.0, 1000.0),
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )
    return authenticate_viewport_decision(
        viewport=viewport,
        view_class_authority=producer.authority(),
        selector=selector,
    )


def _selector(published, *, page_id: str = "1", viewport_id: str = "vp_1"):
    return PortableRasterOCRSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
    )


def _line(text: str, bbox_px, confidence=None) -> OCRLine:
    return OCRLine(
        text=text,
        confidence=confidence,
        bbox_px=tuple(float(v) for v in bbox_px),
        # Deliberately bogus: bridge must ignore backend/caller bbox_pt and
        # recompute page-space geometry from trusted raster DPI + bbox_px.
        bbox_pt=(900.0, 900.0, 999.0, 999.0),
    )


def _test_bridge(source_producer, lines):
    return RasterOCRTagObservationProducer.create_for_tests(
        source_producer=source_producer,
        backend=MockOCRBackend(tuple(lines)),
        dpi=72,
    )


def test_end_to_end_uses_immutable_source_page_and_internal_native_page_parent() -> None:
    producer, authority, published, page_ids = _ingest_pages("doc_bridge_safe")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )
    assert decision.status == EvidenceResolutionStatus.CORROBORATED

    bridge = _test_bridge(
        producer,
        [_line("D-1", (100.0, 100.0, 120.0, 115.0), confidence=0.97)],
    )
    tags, final_snapshot = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )

    assert len(tags) == 1
    tag = tags[0]
    assert tag.raw_tag_text == "D-1"
    # bbox_pt supplied by the mocked OCR line was bogus; producer recomputes
    # geometry from bbox_px against its own immutable 72-DPI page raster.
    assert tag.bounding_box == (100.0, 100.0, 120.0, 115.0)
    assert tag.snapshot_id == final_snapshot
    assert tag.viewport_id == "vp_1"
    assert tag._seal is not None

    resolved = authority.resolve(
        ObservationSelector(
            document_id=tag.document_id,
            revision_id=tag.revision_id,
            source_sha256=tag.source_sha256,
            snapshot_id=final_snapshot,
            observation_id=tag.observation_id,
        )
    )
    assert resolved.status == EvidenceResolutionStatus.CORROBORATED
    assert resolved.observation is not None
    assert resolved.observation.page_id == "1"
    assert resolved.observation.source_partition_id == "page:1"
    assert resolved.observation.derivation_parent_ids == (page_ids["1"],)


def test_production_api_rejects_mock_backend_and_accepts_no_caller_ocr_lines_or_parent_ids() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_no_injection")
    line = _line("W-1", (10.0, 10.0, 30.0, 25.0))

    with pytest.raises(TypeError):
        RasterOCRTagObservationProducer.create(
            source_producer=producer,
            backend=MockOCRBackend((line,)),
            dpi=72,
        )

    bridge = _test_bridge(producer, [line])
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )

    # These were the exact unsafe caller-controlled seams in the original PR.
    with pytest.raises(TypeError):
        bridge.publish(
            selector=_selector(published),
            viewport_decision=decision,
            ocr_lines=(line,),
        )
    with pytest.raises(TypeError):
        bridge.publish(
            selector=_selector(published),
            viewport_decision=decision,
            page_observation_id="caller_chosen_parent",
        )
    with pytest.raises(TypeError):
        bridge.publish(
            selector=_selector(published),
            viewport_decision=decision,
            source_partition_id="caller:partition",
        )


def test_swapped_page_scope_cannot_mint_tag_or_choose_a_page_parent() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_page_swap", page_count=2)
    decision_page_1 = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
        page_number=1,
    )
    bridge = _test_bridge(
        producer,
        [_line("D-2", (200.0, 200.0, 220.0, 214.0), confidence=0.9)],
    )

    tags, final_snapshot = bridge.publish(
        selector=_selector(published, page_id="2"),
        viewport_decision=decision_page_1,
    )

    assert tags == ()
    assert final_snapshot == published.snapshot.snapshot_id


def test_cross_source_viewport_decision_cannot_mint_tag() -> None:
    producer_a, _, published_a, pages_a = _ingest_pages("doc_bridge_source_a")
    producer_b, _, published_b, _ = _ingest_pages("doc_bridge_source_b")
    decision_a = _viewport_decision(
        published=published_a,
        page_observation_id=pages_a["1"],
        viewport_id="vp_shared_name",
    )
    bridge_b = _test_bridge(
        producer_b,
        [_line("W-1", (300.0, 300.0, 315.0, 312.0))],
    )

    tags, final_snapshot = bridge_b.publish(
        selector=_selector(published_b, viewport_id="vp_shared_name"),
        viewport_decision=decision_a,
    )

    assert tags == ()
    assert final_snapshot == published_b.snapshot.snapshot_id


def test_non_floor_plan_viewport_publishes_nothing() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_elevation")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
        view_kind=VIEW_KIND_ELEVATION,
    )
    assert decision.status != EvidenceResolutionStatus.CORROBORATED

    bridge = _test_bridge(
        producer,
        [_line("W-1", (10.0, 10.0, 30.0, 25.0))],
    )
    tags, final_snapshot = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )

    assert tags == ()
    assert final_snapshot == published.snapshot.snapshot_id


def test_duplicate_detections_collapse_by_overlap_not_fixed_point_distance() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_dupe")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )
    bridge = _test_bridge(
        producer,
        [
            _line("D-2", (200.0, 200.0, 220.0, 214.0), confidence=0.9),
            _line("D-2", (201.0, 200.5, 221.0, 214.5), confidence=0.6),
        ],
    )
    tags, _ = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )

    assert len(tags) == 1
    assert tags[0].bounding_box == (200.0, 200.0, 220.0, 214.0)


def test_distinct_nonoverlapping_marks_are_preserved_even_when_close_and_same_text() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_distinct")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )
    bridge = _test_bridge(
        producer,
        [
            _line("W-1", (300.0, 300.0, 315.0, 312.0)),
            _line("W-1", (316.0, 300.0, 331.0, 312.0)),
        ],
    )
    tags, _ = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )

    assert len(tags) == 2
    assert [tag.raw_tag_text for tag in tags] == ["W-1", "W-1"]


def test_none_confidence_never_blocks_publication() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_no_confidence")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )
    bridge = _test_bridge(
        producer,
        [_line("D-1", (5.0, 5.0, 20.0, 18.0), confidence=None)],
    )
    tags, _ = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )

    assert len(tags) == 1
    assert tags[0].raw_tag_text == "D-1"


def test_bridge_tag_integrates_with_unmodified_identity_resolver_without_special_authority() -> None:
    producer, _, published, page_ids = _ingest_pages("doc_bridge_resolver")
    decision = _viewport_decision(
        published=published,
        page_observation_id=page_ids["1"],
    )
    bridge = _test_bridge(
        producer,
        [_line("D-1", (100.0, 100.0, 120.0, 115.0), confidence=0.95)],
    )
    tags, final_snapshot = bridge.publish(
        selector=_selector(published),
        viewport_decision=decision,
    )
    assert len(tags) == 1

    candidate = make_candidate(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=final_snapshot,
        page_id="1",
        viewport_id="vp_1",
        geometry=(95.0, 95.0, 125.0, 125.0),
    )
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=list(tags),
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )

    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
