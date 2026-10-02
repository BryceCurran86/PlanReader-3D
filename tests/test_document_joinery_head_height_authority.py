from __future__ import annotations

import fitz

from pb_document_joinery_head_height_authority import (
    JOINERY_HEAD_HEIGHT_CONFLICT,
    JOINERY_HEAD_HEIGHT_RESOLVED,
    JOINERY_HEAD_HEIGHT_UNAVAILABLE,
    DocumentJoineryHeadHeightProducer,
    _parse_joinery_head_height_mm,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf(*lines_by_page: tuple[str, ...]) -> bytes:
    doc = fitz.open()
    try:
        for page_lines in lines_by_page:
            page = doc.new_page(width=500.0, height=300.0)
            y = 50.0
            for line in page_lines:
                page.insert_text((40.0, y), line, fontsize=9.0)
                y += 24.0
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(payload: bytes, name: str):
    source = SourceVisibilityProducer(
        producer_method="joinery-head-height-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="joinery-head:" + name,
        source_bytes=payload,
        source_locator="fixture:" + name,
    )
    return source, published


def test_parser_requires_universal_joinery_head_height_semantics() -> None:
    assert _parse_joinery_head_height_mm("JOINERY HEIGHTS TO BE 2100 AFL U.N.O.") == 2100.0
    assert _parse_joinery_head_height_mm("Joinery height to be 2400 mm A.F.L. UNO") == 2400.0
    assert _parse_joinery_head_height_mm("JOINERY HEIGHTS TO BE 2100 AFL") is None
    assert _parse_joinery_head_height_mm("DOOR HEIGHT 2100") is None
    assert _parse_joinery_head_height_mm("2100 AFL U.N.O.") is None


def test_repeated_identical_universal_notes_corroborate_one_document_claim() -> None:
    source, published = _ingest(
        _pdf(
            ("ELEVATION", "JOINERY HEIGHTS TO BE 2100 AFL U.N.O."),
            ("SECTION", "JOINERY HEIGHTS TO BE 2100 AFL U.N.O."),
        ),
        "same",
    )
    producer = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(source)
    result = producer.publish_revision(published.revision.revision_id)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (JOINERY_HEAD_HEIGHT_RESOLVED,)
    assert result.evidence is not None
    assert result.evidence.head_height_mm == 2100.0
    assert result.evidence.units == "mm"
    assert result.evidence.datum == "AFL"
    assert result.evidence.scope == "document_joinery_uno"
    assert len(result.evidence.source_page_ids) == 2
    assert result.evidence.source_text_observation_ids


def test_conflicting_universal_joinery_notes_fail_closed() -> None:
    source, published = _ingest(
        _pdf(
            ("JOINERY HEIGHTS TO BE 2100 AFL U.N.O.",),
            ("JOINERY HEIGHTS TO BE 2400 AFL U.N.O.",),
        ),
        "conflict",
    )
    result = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(
        source
    ).publish_revision(published.revision.revision_id)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert JOINERY_HEAD_HEIGHT_CONFLICT in result.reason_codes


def test_non_universal_or_unrelated_dimensions_do_not_create_head_height() -> None:
    source, published = _ingest(
        _pdf(
            ("JOINERY HEIGHTS TO BE 2100 AFL", "WINDOW 1200 x 1810"),
        ),
        "none",
    )
    result = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(
        source
    ).publish_revision(published.revision.revision_id)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert JOINERY_HEAD_HEIGHT_UNAVAILABLE in result.reason_codes


def test_authority_replays_only_published_producer_result() -> None:
    source, published = _ingest(
        _pdf(("JOINERY HEIGHTS TO BE 2100 AFL U.N.O.",)),
        "authority",
    )
    producer = DocumentJoineryHeadHeightProducer.from_source_visibility_producer(source)
    produced = producer.publish_revision(published.revision.revision_id)
    authority = producer.authority()
    replay = authority.resolve(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
    )
    assert replay == produced
