from __future__ import annotations

import fitz
import pytest
from unittest.mock import patch
from types import SimpleNamespace

import pb_physical_wall_candidate_authority as wall_candidate_module

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    try:
        for index in range(3):
            page = doc.new_page(width=320.0, height=240.0)
            y = 60.0 + index * 20.0
            page.draw_line((40.0, y), (280.0, y))
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _source():
    source = SourceVisibilityProducer(
        producer_method="page-scoped-wall-candidates-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="page-scoped-wall-candidates",
        source_bytes=_pdf_bytes(),
        source_locator="memory://page-scoped-wall-candidates.pdf",
    )
    return source, published


def _selector(published, page_id: str) -> PhysicalWallCandidateSelector:
    return PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
    )


def test_page_scope_materializes_only_requested_decoded_page() -> None:
    source, published = _source()
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("2",),
    ).authority()

    page_two = authority.resolve_scope(_selector(published, "2"))
    assert page_two.status is EvidenceResolutionStatus.CORROBORATED
    assert page_two.page_id == "2"
    assert page_two.records

    page_one = authority.resolve_scope(_selector(published, "1"))
    assert page_one.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE in page_one.reason_codes


def test_page_scope_limits_raster_augmentation_to_requested_pages() -> None:
    source, _ = _source()
    with patch.object(
        source,
        "augment_with_raster_visible_segments",
        wraps=source.augment_with_raster_visible_segments,
    ) as augment:
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
        )
    augment.assert_called_once()
    assert augment.call_args.args == (
        next(iter(source._published_by_revision)),
    )
    assert augment.call_args.kwargs["page_ids"] == ("2",)


def test_page_scope_rejects_undecoded_source_page_address() -> None:
    source, _ = _source()
    with pytest.raises(ValueError, match=PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE):
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("99",),
        )


def test_empty_page_scope_rejected_instead_of_falling_back_to_all_pages() -> None:
    source, _ = _source()
    with pytest.raises(ValueError, match="page_ids must contain at least one source page"):
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("", "  "),
        )



def test_page_scope_segments_viewports_once_for_all_wall_candidates() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        for y in (60.0, 100.0, 140.0, 180.0):
            page.draw_line((40.0, y), (280.0, y))
        payload = bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="page-scoped-wall-candidates-segmentation-test",
        producer_version="1",
    )
    source.ingest_native_pdf_bytes(
        document_id="page-scoped-wall-candidates-segmentation",
        source_bytes=payload,
        source_locator="memory://page-scoped-wall-candidates-segmentation.pdf",
    )

    original = wall_candidate_module.segment_page_viewports
    with patch.object(
        wall_candidate_module,
        "segment_page_viewports",
        wraps=original,
    ) as segment:
        authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("1",),
        ).authority()

    published = source.published_snapshot_for_revision(
        next(iter(source._published_by_revision))
    )
    assert published is not None
    result = authority.resolve_scope(_selector(published, "1"))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) >= 4
    segment.assert_called_once()

def test_page_segments_reused_across_page_and_viewport_wall_producers() -> None:
    source, _published = _source()
    original = wall_candidate_module.extract_native_page

    with patch.object(
        wall_candidate_module,
        "extract_native_page",
        wraps=original,
    ) as extract:
        first_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
        )
        current = source.published_snapshot_for_revision(
            next(iter(source._published_by_revision))
        )
        assert current is not None
        first_result = first_producer.authority().resolve_scope(_selector(current, "2"))
        assert first_result.status is EvidenceResolutionStatus.CORROBORATED
        # Source visibility already decoded this exact immutable page during
        # ingest, so wall reconstruction must reuse that producer-owned parse.
        assert extract.call_count == 0

        second_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
        )
        current_again = source.published_snapshot_for_revision(
            next(iter(source._published_by_revision))
        )
        assert current_again is not None
        second_result = second_producer.authority().resolve_scope(
            _selector(current_again, "2")
        )

        assert second_result == first_result
        assert extract.call_count == 0

        PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=("2",),
        )
        assert extract.call_count == 0


def test_page_segments_fall_back_to_native_decode_when_producer_cache_is_missing() -> None:
    source, _published = _source()
    source._producer._native_page_decode_cache.clear()
    original = wall_candidate_module.extract_native_page

    with patch.object(
        wall_candidate_module,
        "extract_native_page",
        wraps=original,
    ) as extract:
        producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
        )
        current = source.published_snapshot_for_revision(
            next(iter(source._published_by_revision))
        )
        assert current is not None
        result = producer.authority().resolve_scope(_selector(current, "2"))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert extract.call_count == 1


def test_page_viewport_segmentation_reused_for_authenticated_fallback() -> None:
    source, _published = _source()
    original = wall_candidate_module._all_viewports

    with patch.object(
        wall_candidate_module,
        "_all_viewports",
        wraps=original,
    ) as all_viewports:
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
        )
        assert all_viewports.call_count == 1

        PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=("2",),
        )

        # Page-scope assembly already authenticated the page viewport census.
        # The later room/viewport fallback must reuse that producer-owned result
        # instead of reopening and segmenting the same immutable page again.
        assert all_viewports.call_count == 1




def test_bounded_reference_viewports_do_not_crop_page_wall_scope() -> None:
    reference_rows = [
        SimpleNamespace(
            view_type=view_type,
            bounding_box=(10.0, 10.0, 90.0, 90.0),
        )
        for view_type in (
            DrawingViewType.LEGEND.value,
            DrawingViewType.SCHEDULE.value,
            DrawingViewType.SPECIFICATION.value,
        )
    ]
    floor_plan = SimpleNamespace(
        view_type=DrawingViewType.FLOOR_PLAN.value,
        bounding_box=(0.0, 0.0, 100.0, 100.0),
    )
    unknown = SimpleNamespace(
        view_type=DrawingViewType.UNKNOWN.value,
        bounding_box=(0.0, 0.0, 100.0, 100.0),
    )

    assert wall_candidate_module._wall_scope_relevant_viewports(reference_rows) == []
    assert wall_candidate_module._wall_scope_relevant_viewports(
        [*reference_rows, floor_plan, unknown]
    ) == [floor_plan, unknown]
