"""Production acceptance tests for producer-owned PDF text-integrity authority.

These tests are intentionally NOT xfailed. The first test-only commit is
expected RED on post-#331 main because the authority does not exist yet.
"""
from __future__ import annotations

from typing import Mapping

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


TRUSTED_TEXT = "trusted_pdf_text"


def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    pos = len(header)
    for number in sorted(objects):
        offsets[number] = pos
        body = objects[number].encode("latin1")
        chunk = f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)
    xref_pos = pos
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        if number in offsets:
            xref.append(f"{offsets[number]:010d} 00000 n \n")
        else:
            xref.append("0000000000 00000 f \n")
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    )
    return b"".join(chunks) + "".join(xref).encode("ascii") + trailer.encode("ascii")


def _simple_text_pdf(*, color: str = "0 0 0 rg", fill_after: bool | None = None) -> bytes:
    text = f"{color} BT /F1 12 Tf 40 120 Td (900) Tj ET"
    fill = "0 0 0 rg 35 112 45 18 re f"
    if fill_after is True:
        stream = f"{text} {fill}"
    elif fill_after is False:
        stream = f"{fill} {text}"
    else:
        stream = text
    return _pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def _type3_pdf() -> bytes:
    char_stream = "500 0 0 0 500 500 d1 0 0 500 500 re S 0 0 m 500 500 l S"
    page_stream = "BT /F3 20 Tf 40 100 Td (A) Tj ET"
    return _pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F3 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
            5: (
                "<< /Type /Font /Subtype /Type3 /Name /F3 /FontBBox [0 0 500 500] "
                "/FontMatrix [0.001 0 0 0.001 0 0] /CharProcs << /A 6 0 R >> "
                "/Encoding << /Type /Encoding /Differences [65 /A] >> "
                "/FirstChar 65 /LastChar 65 /Widths [500] /Resources << >> >>"
            ),
            6: f"<< /Length {len(char_stream)} >>\nstream\n{char_stream}\nendstream",
        }
    )


def _malformed_cmap_pdf() -> bytes:
    page_stream = "BT /F1 12 Tf 40 120 Td (900) Tj ET"
    cmap = "begincmap /CMapType 2 def 1 begincodespacerange <00> <FF> endcodespacerange 1 beginbfchar <39> <0039> endbfchar GARBAGE endcmap"
    return _pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>",
            6: f"<< /Length {len(cmap)} >>\nstream\n{cmap}\nendstream",
        }
    )


def _control_text_pdf() -> bytes:
    stream = r"BT /F1 12 Tf 40 120 Td (\001900\002) Tj ET"
    return _pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def _ingest(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="pdf-text-integrity-production-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    authority = producer.text_integrity_authority()
    return producer, published, authority


def _word_selectors(published):
    return [
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.text_observation_ids
    ]


def _first_result(payload: bytes, *, document_id: str):
    _producer, published, authority = _ingest(payload, document_id=document_id)
    selectors = _word_selectors(published)
    assert selectors
    return authority, selectors[0], authority.resolve_text(selectors[0])


def test_standard_base14_visible_text_is_trusted_without_guessing() -> None:
    _authority, _selector, result = _first_result(
        _simple_text_pdf(), document_id="text-trusted-base14"
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == TRUSTED_TEXT
    assert result.trusted_text == "900"
    assert result.receipt is not None
    assert result.receipt.decode_status == "known_standard_encoding"
    assert result.receipt.visibility_status == "proven_visible"


def test_white_on_white_text_fails_closed() -> None:
    _authority, _selector, result = _first_result(
        _simple_text_pdf(color="1 1 1 rg"), document_id="text-white-hidden"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "text_low_contrast_default_page" in result.reason_codes


def test_later_opaque_fill_occludes_text_but_earlier_fill_does_not() -> None:
    _a1, _s1, hidden = _first_result(
        _simple_text_pdf(fill_after=True), document_id="text-fill-after"
    )
    assert hidden.status is not EvidenceResolutionStatus.CORROBORATED
    assert hidden.trusted_text is None
    assert "text_occluded_by_later_paint" in hidden.reason_codes

    _a2, _s2, visible = _first_result(
        _simple_text_pdf(fill_after=False), document_id="text-fill-before"
    )
    assert visible.status is EvidenceResolutionStatus.CORROBORATED
    assert visible.trusted_text == "900"


def test_type3_vector_glyph_text_is_not_trusted() -> None:
    _authority, _selector, result = _first_result(
        _type3_pdf(), document_id="text-type3"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert any(code in result.reason_codes for code in ("text_type3_font_untrusted", "text_render_mode_untrusted"))


def test_malformed_tounicode_is_blocked_even_if_library_extracts_text() -> None:
    _authority, _selector, result = _first_result(
        _malformed_cmap_pdf(), document_id="text-bad-cmap"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "text_tounicode_malformed" in result.reason_codes


def test_control_characters_are_not_trusted_semantic_text() -> None:
    _authority, _selector, result = _first_result(
        _control_text_pdf(), document_id="text-control-chars"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert any(code in result.reason_codes for code in ("text_unicode_untrusted", "text_decode_mismatch"))


def test_source_hash_laundering_is_rejected_by_same_authority_chain() -> None:
    authority, selector, original = _first_result(
        _simple_text_pdf(), document_id="text-hash-launder"
    )
    assert original.status is EvidenceResolutionStatus.CORROBORATED
    forged = ObservationSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256="0" * 64,
        snapshot_id=selector.snapshot_id,
        observation_id=selector.observation_id,
    )
    result = authority.resolve_text(forged)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "source_hash_mismatch" in result.reason_codes


def test_text_integrity_replay_is_deterministic() -> None:
    authority, selector, first = _first_result(
        _simple_text_pdf(), document_id="text-deterministic"
    )
    second = authority.resolve_text(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED


def test_text_integrity_authority_is_read_only_and_does_not_unlock_dimensions() -> None:
    producer, published, authority = _ingest(
        _simple_text_pdf(), document_id="text-firewall"
    )
    assert producer is not None and published.text_observation_ids
    assert callable(authority.resolve_text)
    for writer_name in (
        "ingest_native_pdf_bytes",
        "publish_derived_observation",
        "publish_text",
        "write",
    ):
        assert not hasattr(authority, writer_name)

    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
