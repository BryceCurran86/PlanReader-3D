"""Adversarial tests for immutable-source raster text corroboration.

The source PDF ingestion, native text receipt, immutable page render and exact
native-word crop are real. Only OCR engine output is mocked through the
explicit test-only factory.
"""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    NativeTextIntegrityDecision,
    build_pdf_text_integrity_receipt,
)
from pb_portable_raster_ocr_authority import MockOCRBackend, NullOCRBackend, OCRLine
from pb_raster_text_corroboration_authority import (
    RASTER_TEXT_BACKEND_UNAVAILABLE,
    RASTER_TEXT_CORROBORATED,
    RASTER_TEXT_LINEAGE_MISMATCH,
    RASTER_TEXT_NATIVE_ALREADY_TRUSTED,
    RASTER_TEXT_NATIVE_BLOCKER_NOT_GLYPH_ONLY,
    RASTER_TEXT_OCR_AMBIGUOUS,
    RASTER_TEXT_OCR_MISMATCH,
    RASTER_TEXT_OCR_OUTPUT_INVALID,
    RASTER_TEXT_SOURCE_RENDER_UNAVAILABLE,
    RasterTextCorroborationAuthority,
    RasterTextCorroborationProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _source_with_word(text: str = "finish"):
    doc = fitz.open()
    page = doc.new_page(width=300.0, height=200.0)
    page.insert_text(fitz.Point(60.0, 100.0), text, fontsize=12)
    payload = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="raster-text-corroboration-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"doc:{text}",
        source_bytes=payload,
        source_locator=f"memory://{text}.pdf",
    )
    authority = source.text_integrity_authority()

    selected = None
    native_result = None
    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = authority.resolve_text(selector)
        if result.receipt is not None and result.receipt.raw_text == text:
            selected = selector
            native_result = result
            break

    assert selected is not None
    assert native_result is not None
    assert native_result.status is EvidenceResolutionStatus.CORROBORATED
    assert native_result.receipt is not None
    return source, published, selected, native_result.receipt


def _replacement_receipt(receipt, *, reasons, visibility_status):
    decision = NativeTextIntegrityDecision(
        trusted=False,
        raw_text=receipt.raw_text,
        decode_status="tounicode_glyph_unverified",
        visibility_status=visibility_status,
        reason_codes=tuple(reasons),
        font_xref=receipt.font_xref,
        font_subtype=receipt.font_subtype,
        font_name=receipt.font_name,
        sequence_number=receipt.sequence_number,
        trace_sequence_numbers=receipt.trace_sequence_numbers,
    )
    return build_pdf_text_integrity_receipt(
        parent_observation_id=receipt.parent_observation_id,
        document_id=receipt.document_id,
        revision_id=receipt.revision_id,
        source_sha256=receipt.source_sha256,
        page_id=receipt.page_id,
        source_partition_id=receipt.source_partition_id,
        geometry=receipt.geometry,
        decision=decision,
        block_no=receipt.block_no,
        line_no=receipt.line_no,
        word_no=receipt.word_no,
    )


def _force_glyph_only_block(source, selector, receipt):
    blocked = _replacement_receipt(
        receipt,
        reasons=(TEXT_GLYPH_MAPPING_UNVERIFIED,),
        visibility_status="proven_visible",
    )
    source._text_integrity_receipts[
        (selector.snapshot_id, selector.observation_id)
    ] = blocked
    return blocked


def _line(
    text: str,
    bbox_px=(1.0, 1.0, 8.0, 6.0),
    *,
    confidence=0.01,
) -> OCRLine:
    return OCRLine(
        text=text,
        confidence=confidence,
        bbox_px=tuple(float(value) for value in bbox_px),
        # Deliberately bogus. Only bbox_px inside the exact source-owned crop
        # can participate; backend bbox_pt is not authority.
        bbox_pt=(999.0, 999.0, 1000.0, 1000.0),
    )


def _producer(source, lines, *, dpi=72):
    return RasterTextCorroborationProducer.create_for_tests(
        source_visibility_producer=source,
        backend=MockOCRBackend(tuple(lines)),
        dpi=dpi,
    )


def test_exact_immutable_crop_and_unique_text_agreement_corroborate() -> None:
    source, _published, selector, native_receipt = _source_with_word("finish")
    blocked = _force_glyph_only_block(source, selector, native_receipt)

    result = _producer(source, [_line("FINISH")]).publish(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == RASTER_TEXT_CORROBORATED
    assert result.trusted_text == "finish"
    assert result.receipt is not None
    assert result.receipt.parent_observation_id == selector.observation_id
    assert result.receipt.native_text_integrity_receipt_id == blocked.receipt_id
    assert result.receipt.crop_bbox_pt == tuple(blocked.geometry)
    assert result.receipt.geometry == tuple(blocked.geometry)
    assert result.receipt.backend_name == "mock_ocr"
    assert result.receipt.dpi == 72
    # Confidence is diagnostic backend output only; a low score is neither a
    # positive nor negative authority criterion.
    assert result.receipt.ocr_text == "FINISH"


def test_native_trusted_word_does_not_enter_raster_rescue_path() -> None:
    source, _published, selector, _receipt = _source_with_word("finish")
    producer = _producer(
        source,
        [OCRLine(text="finish", confidence=1.0, bbox_px=(1.0, 1.0, 8.0, 6.0))],
    )

    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_NATIVE_ALREADY_TRUSTED,)


def test_only_glyph_mapping_unverified_is_eligible() -> None:
    source, _published, selector, native_receipt = _source_with_word("finish")
    blocked = _replacement_receipt(
        native_receipt,
        reasons=(
            TEXT_GLYPH_MAPPING_UNVERIFIED,
            TEXT_CLIP_STATE_UNRESOLVED,
        ),
        visibility_status="unresolved_or_blocked",
    )
    source._text_integrity_receipts[
        (selector.snapshot_id, selector.observation_id)
    ] = blocked

    result = _producer(source, [_line("finish")]).publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_NATIVE_BLOCKER_NOT_GLYPH_ONLY,)


def test_multiple_ocr_lines_are_ambiguous_not_ranked_by_confidence() -> None:
    source, _published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)

    result = _producer(
        source,
        [
            _line("finish", confidence=0.99),
            _line("finish", bbox_px=(9.0, 1.0, 15.0, 6.0), confidence=0.01),
        ],
    ).publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_OCR_AMBIGUOUS,)


def test_ocr_text_mismatch_abstains() -> None:
    source, _published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)

    result = _producer(source, [_line("f1nish")]).publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_OCR_MISMATCH,)


def test_backend_bbox_outside_exact_crop_is_not_accepted() -> None:
    source, _published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)

    result = _producer(
        source,
        [_line("finish", bbox_px=(0.0, 0.0, 10_000.0, 10_000.0))],
    ).publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_OCR_OUTPUT_INVALID,)


def test_stale_snapshot_lineage_abstains_before_ocr() -> None:
    source, published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)
    stale = replace(selector, snapshot_id=f"{published.snapshot.snapshot_id}-stale")

    result = _producer(source, [_line("finish")]).publish(stale)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_LINEAGE_MISMATCH,)


def test_unavailable_backend_fails_closed() -> None:
    source, _published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)

    producer = RasterTextCorroborationProducer.create(
        source_visibility_producer=source,
        backend=NullOCRBackend(),
        dpi=72,
    )
    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (RASTER_TEXT_BACKEND_UNAVAILABLE,)


def test_immutable_source_tamper_is_rejected_by_upstream_source_authority() -> None:
    source, published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)
    source._producer._store.source_bytes_by_revision[published.revision.revision_id] = (
        b"%PDF-1.7\n% tampered"
    )

    result = _producer(source, [_line("finish")]).publish(selector)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (RASTER_TEXT_NATIVE_PREREQUISITE_UNRESOLVED,)


def test_result_is_deterministic_and_authority_is_read_only() -> None:
    source, _published, selector, receipt = _source_with_word("finish")
    _force_glyph_only_block(source, selector, receipt)
    producer = _producer(source, [_line("finish")])

    first = producer.publish(selector)
    second = producer.publish(selector)
    resolved = producer.authority().resolve_text(selector)

    assert first == second == resolved
    assert first.receipt is not None

    with pytest.raises(TypeError):
        RasterTextCorroborationAuthority({})


def test_production_factory_rejects_mock_backend() -> None:
    source, _published, _selector, _receipt = _source_with_word("finish")

    with pytest.raises(TypeError):
        RasterTextCorroborationProducer.create(
            source_visibility_producer=source,
            backend=MockOCRBackend((_line("finish"),)),
            dpi=72,
        )
