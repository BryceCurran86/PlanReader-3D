from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_page_view_class_adapter import (
    build_source_page_view_class_authority,
    page_viewport_id,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassSelector,
)


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    page.insert_text((50, 50), text, fontsize=12)
    payload = doc.tobytes()
    doc.close()
    return payload


def _resolve(text: str):
    source = SourceVisibilityProducer(
        producer_method="page-view-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="page-view",
        source_bytes=_pdf(text),
        source_locator="memory://page-view.pdf",
    )
    authority = build_source_page_view_class_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    return authority.resolve(
        ViewportViewClassSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            viewport_id=page_viewport_id("1"),
        )
    )


def test_authenticated_strong_floor_plan_text_publishes_page_view_class() -> None:
    result = _resolve("GROUND FLOOR PLAN")
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.view_kind == VIEW_KIND_FLOOR_PLAN
    assert result.record.evidence_observation_ids


def test_weak_generic_plan_fallback_does_not_establish_commercial_floor_plan() -> None:
    result = _resolve("SITE PLAN")
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
