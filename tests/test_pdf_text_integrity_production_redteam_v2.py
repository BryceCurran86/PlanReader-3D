"""Independent executable production validator for PDF text integrity (#330).

Validator base: e27ffad284b05123ffacbbe123c69823c5367dee
Production candidate: 752d5b8cbe0b0cc3e45c68fa27cc9ece54cfa47e
Historical attack source: PR #338 @ 9d16e97a47da1e9ef5d7e939c658185e5b8ed841

The 16 historical attack intents are preserved, but placeholder failures and
"module must be absent" assertions are removed.  On the validator base the
suite is controlled XFAIL because the public producer-owned text authority is
not present.  With ``--runxfail`` that absence becomes a genuine behavioral
failure at the public API boundary.  When replayed on production, every test
executes against only:

    SourceVisibilityProducer(...)
      -> ingest_native_pdf_bytes(...)
      -> text_integrity_authority()
      -> resolve_text(ObservationSelector(...))

No private producer state or caller-constructed trusted receipt is used.
"""
from __future__ import annotations

import inspect
from typing import Mapping

import pytest

from pb_drawing_ocr_evidence_layer import EvidenceMethod
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "e27ffad284b05123ffacbbe123c69823c5367dee"
PRODUCTION_SHA = "752d5b8cbe0b0cc3e45c68fa27cc9ece54cfa47e"
TRUSTED_TEXT = "trusted_pdf_text"
HAS_TEXT_AUTHORITY = callable(
    getattr(SourceVisibilityProducer, "text_integrity_authority", None)
)
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_TEXT_AUTHORITY,
    strict=True,
    reason="producer-owned PDF text-integrity authority is absent on validator base",
)


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


def _simple_text_pdf(
    *,
    literal: str = "900",
    color: str = "0 0 0 rg",
    fill_after: bool | None = None,
) -> bytes:
    text = f"{color} BT /F1 12 Tf 40 120 Td ({literal}) Tj ET"
    fill = "1 1 1 rg 35 112 45 18 re f"
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


def _base14_non_ascii_pdf() -> bytes:
    # Base14 without ToUnicode is allowed only for the narrow printable-ASCII path.
    return _simple_text_pdf(literal=r"\200900")


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
    cmap = (
        "begincmap /CMapType 2 def 1 begincodespacerange <00> <FF> "
        "endcodespacerange 1 beginbfchar <39> <0039> endbfchar GARBAGE endcmap"
    )
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


def _valid_tounicode_visual_mismatch_pdf() -> bytes:
    # Code 0x39 renders the Helvetica glyph "9" while ToUnicode claims "A".
    # A valid CMap must not be allowed to turn that encoded/render contradiction
    # into positive semantic authority merely because extraction is consistent.
    page_stream = "BT /F1 12 Tf 40 120 Td <39> Tj ET"
    cmap = "\n".join(
        (
            "/CIDInit /ProcSet findresource begin",
            "12 dict begin",
            "begincmap",
            "/CMapName /Mismatch def",
            "/CMapType 2 def",
            "1 begincodespacerange",
            "<00> <FF>",
            "endcodespacerange",
            "1 beginbfchar",
            "<39> <0041>",
            "endbfchar",
            "endcmap",
            "CMapName currentdict /CMap defineresource pop",
            "end",
            "end",
        )
    )
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
            6: f"<< /Length {len(cmap.encode('latin1'))} >>\nstream\n{cmap}\nendstream",
        }
    )


def _clipped_text_pdf() -> bytes:
    # The clip covers the whole page, so the text may remain visually present,
    # but production has no per-text clip receipt and must stay fail-closed.
    stream = "0 0 300 200 re W n 0 0 0 rg BT /F1 12 Tf 40 120 Td (900) Tj ET"
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
    assert HAS_TEXT_AUTHORITY, (
        "SourceVisibilityProducer.text_integrity_authority() is the missing "
        "producer-owned behavior on the validator base"
    )
    producer = SourceVisibilityProducer(
        producer_method="gpt2-pdf-text-integrity-production-redteam-v2",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    authority = producer.text_integrity_authority()
    return producer, published, authority


def _word_selectors(published) -> list[ObservationSelector]:
    observation_ids = tuple(getattr(published, "text_observation_ids", ()) or ())
    assert observation_ids, "producer did not publish any native text observation ids"
    return [
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in observation_ids
    ]


def _first_result(payload: bytes, *, document_id: str):
    producer, published, authority = _ingest(payload, document_id=document_id)
    selector = _word_selectors(published)[0]
    return producer, published, authority, selector, authority.resolve_text(selector)


def _assert_blocked(result) -> None:
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None


def _forged_selector(selector: ObservationSelector, **changes: str) -> ObservationSelector:
    values = {
        "document_id": selector.document_id,
        "revision_id": selector.revision_id,
        "source_sha256": selector.source_sha256,
        "snapshot_id": selector.snapshot_id,
        "observation_id": selector.observation_id,
    }
    values.update(changes)
    return ObservationSelector(**values)


@EXPECTED_RED
def test_attack01_producer_owned_read_only_trusted_text_authority_exists() -> None:
    assert BASE_SHA == "e27ffad284b05123ffacbbe123c69823c5367dee"
    assert PRODUCTION_SHA == "752d5b8cbe0b0cc3e45c68fa27cc9ece54cfa47e"
    producer, published, authority, _selector, result = _first_result(
        _simple_text_pdf(), document_id="v2-attack01"
    )
    assert producer is not None and published.text_observation_ids
    assert callable(authority.resolve_text)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == TRUSTED_TEXT
    assert result.trusted_text == "900"
    for writer_name in (
        "ingest_native_pdf_bytes",
        "publish_derived_observation",
        "publish_text",
        "write",
    ):
        assert not hasattr(authority, writer_name)


@EXPECTED_RED
def test_attack02_unsupported_or_ambiguous_decoding_fails_closed_but_narrow_base14_ascii_is_safe() -> None:
    _p1, _pub1, _a1, _s1, safe = _first_result(
        _simple_text_pdf(), document_id="v2-attack02-safe"
    )
    assert safe.status is EvidenceResolutionStatus.CORROBORATED
    assert safe.trusted_text == "900"
    assert safe.receipt is not None
    assert safe.receipt.decode_status == "known_standard_encoding"

    _p2, _pub2, _a2, _s2, unsupported = _first_result(
        _base14_non_ascii_pdf(), document_id="v2-attack02-unsupported"
    )
    _assert_blocked(unsupported)
    # Fail-closed behavior is the authority contract.  The exact diagnostic
    # reason taxonomy is intentionally not frozen by this independent validator.
    assert unsupported.reason_codes


@EXPECTED_RED
def test_attack03_malformed_tounicode_fails_closed() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _malformed_cmap_pdf(), document_id="v2-attack03"
    )
    _assert_blocked(result)
    assert "text_tounicode_malformed" in result.reason_codes


@EXPECTED_RED
def test_attack04_control_or_unprintable_unicode_fails_closed() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _control_text_pdf(), document_id="v2-attack04"
    )
    _assert_blocked(result)
    assert any(
        reason in result.reason_codes
        for reason in ("text_unicode_untrusted", "text_decode_mismatch")
    )


@EXPECTED_RED
def test_attack05_encoded_render_mismatch_cannot_become_positive_authority() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _valid_tounicode_visual_mismatch_pdf(), document_id="v2-attack05"
    )
    _assert_blocked(result)


@EXPECTED_RED
def test_attack06_type3_vector_glyph_text_is_quarantined() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _type3_pdf(), document_id="v2-attack06"
    )
    _assert_blocked(result)
    assert any(
        reason in result.reason_codes
        for reason in ("text_type3_font_untrusted", "text_render_mode_untrusted")
    )


@EXPECTED_RED
def test_attack07_later_opaque_paint_blocks_text() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _simple_text_pdf(fill_after=True), document_id="v2-attack07"
    )
    _assert_blocked(result)
    assert "text_occluded_by_later_paint" in result.reason_codes


@EXPECTED_RED
def test_attack08_fill_before_text_does_not_falsely_occlude_later_text() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _simple_text_pdf(fill_after=False), document_id="v2-attack08"
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text == "900"
    assert result.receipt is not None
    assert result.receipt.visibility_status == "proven_visible"


@EXPECTED_RED
def test_attack09_unresolved_clipping_or_render_state_fails_closed() -> None:
    _p, _pub, _authority, _selector, result = _first_result(
        _clipped_text_pdf(), document_id="v2-attack09"
    )
    _assert_blocked(result)
    assert "text_clip_state_unresolved" in result.reason_codes


@EXPECTED_RED
def test_attack10_ocr_provenance_cannot_be_laundered_into_native_text_authority() -> None:
    _p, _pub, authority, selector, native = _first_result(
        _simple_text_pdf(), document_id="v2-attack10"
    )
    assert native.status is EvidenceResolutionStatus.CORROBORATED
    assert EvidenceMethod.NATIVE_TEXT.value != EvidenceMethod.RASTER_OCR.value
    signature = inspect.signature(authority.resolve_text)
    assert tuple(signature.parameters) == ("selector",)
    for name in ("resolve_ocr", "resolve_text_with_ocr", "publish_ocr", "ingest_ocr"):
        assert not hasattr(authority, name)
    forged = _forged_selector(
        selector, observation_id=f"ocr:{selector.observation_id}"
    )
    _assert_blocked(authority.resolve_text(forged))


@EXPECTED_RED
def test_attack11_low_confidence_ocr_cannot_become_trusted_native_text() -> None:
    _p, _pub, authority, selector, _native = _first_result(
        _simple_text_pdf(), document_id="v2-attack11"
    )
    signature = inspect.signature(authority.resolve_text)
    assert "ocr_confidence" not in signature.parameters
    assert "ocr_text" not in signature.parameters
    forged = _forged_selector(
        selector, observation_id=f"low-confidence-ocr:{selector.observation_id}"
    )
    blocked = authority.resolve_text(forged)
    _assert_blocked(blocked)


@EXPECTED_RED
def test_attack12_native_ocr_contradiction_cannot_strengthen_native_authority() -> None:
    _p, _pub, authority, selector, native = _first_result(
        _malformed_cmap_pdf(), document_id="v2-attack12"
    )
    _assert_blocked(native)
    assert EvidenceMethod.RECONCILED.value not in {
        EvidenceMethod.NATIVE_TEXT.value,
        EvidenceMethod.RASTER_OCR.value,
    }
    signature = inspect.signature(authority.resolve_text)
    assert tuple(signature.parameters) == ("selector",)
    assert not hasattr(authority, "reconcile_ocr")
    assert authority.resolve_text(selector) == native


@EXPECTED_RED
def test_attack13_page_revision_source_and_snapshot_laundering_fail_closed() -> None:
    _p, _pub, authority, selector, original = _first_result(
        _simple_text_pdf(), document_id="v2-attack13"
    )
    assert original.status is EvidenceResolutionStatus.CORROBORATED
    assert original.receipt is not None
    assert original.receipt.page_id == "1"
    assert not hasattr(selector, "page_id")

    for forged in (
        _forged_selector(selector, document_id="other-document"),
        _forged_selector(selector, revision_id="other-revision"),
        _forged_selector(selector, source_sha256="0" * 64),
        _forged_selector(selector, snapshot_id="other-snapshot"),
    ):
        _assert_blocked(authority.resolve_text(forged))


@EXPECTED_RED
def test_attack14_identical_visible_strings_from_different_source_bytes_do_not_share_receipt_identity() -> None:
    _p1, _pub1, _a1, _s1, first = _first_result(
        _simple_text_pdf(), document_id="v2-attack14"
    )
    _p2, _pub2, _a2, _s2, second = _first_result(
        _simple_text_pdf(fill_after=False), document_id="v2-attack14"
    )
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert second.status is EvidenceResolutionStatus.CORROBORATED
    assert first.trusted_text == second.trusted_text == "900"
    assert first.receipt is not None and second.receipt is not None
    assert first.receipt.source_sha256 != second.receipt.source_sha256
    assert first.receipt.receipt_id != second.receipt.receipt_id


@EXPECTED_RED
def test_attack15_deterministic_replay_returns_identical_producer_owned_results() -> None:
    payload = _simple_text_pdf()
    producer, published, authority = _ingest(payload, document_id="v2-attack15")
    selector = _word_selectors(published)[0]
    first = authority.resolve_text(selector)
    second = authority.resolve_text(selector)
    replayed = producer.ingest_native_pdf_bytes(
        document_id="v2-attack15",
        source_bytes=payload,
        source_locator="memory://v2-attack15.pdf",
    )
    replay_selector = _word_selectors(replayed)[0]
    third = producer.text_integrity_authority().resolve_text(replay_selector)
    assert first == second == third
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.receipt is not None


@EXPECTED_RED
def test_attack16_trusted_text_alone_keeps_downstream_opening_capabilities_locked() -> None:
    _p, _pub, _authority, _selector, trusted = _first_result(
        _simple_text_pdf(), document_id="v2-attack16"
    )
    assert trusted.status is EvidenceResolutionStatus.CORROBORATED
    assert trusted.trusted_text == "900"
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
