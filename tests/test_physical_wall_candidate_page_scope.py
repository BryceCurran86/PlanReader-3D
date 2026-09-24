from __future__ import annotations

import fitz
import pytest
from unittest.mock import patch

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


def test_native_only_page_scope_skips_raster_augmentation() -> None:
    source, published = _source()
    with patch.object(
        source,
        "augment_with_raster_visible_segments",
        wraps=source.augment_with_raster_visible_segments,
    ) as augment:
        authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source,
            page_ids=("2",),
            include_raster_fallback=False,
        ).authority()

    augment.assert_not_called()
    page_two = authority.resolve_scope(_selector(published, "2"))
    assert page_two.status is EvidenceResolutionStatus.CORROBORATED
    assert page_two.records
