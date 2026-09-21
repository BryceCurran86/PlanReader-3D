from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_REGISTERED_PATH_UNIVERSE_COMPLETE,
    SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
        ((320.0, 20.0), (380.0, 20.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def test_semantic_enumeration_disposes_examined_noncandidate_geometry() -> None:
    source = SourceVisibilityProducer(
        producer_method="semantic-integration-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="semantic-disposition",
        source_bytes=_pdf(),
        source_locator="memory://semantic-disposition.pdf",
    )
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    result = producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="scope:page:1",
        page_ids=("1",),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert len(result.record.physical_opening_record_ids) == 1
    assert len(result.record.opening_support_observation_ids) == 6
    assert result.record.residual_visible_observation_ids == ()
    assert result.record.structural_enumeration_complete is True
    assert result.record.physical_opening_universe_complete is True
    assert SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE in result.reason_codes
    assert SEMANTIC_OPENING_REGISTERED_PATH_UNIVERSE_COMPLETE in result.reason_codes
