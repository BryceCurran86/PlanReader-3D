"""Independent test-first gate for producer-owned PDF text integrity (#330).

Base: post-#331 main 507c57db16be515e2432c695341bdea1e71b3fd7.
Production files changed: 0.

This suite deliberately separates source-word existence from trustworthy text:
source bytes ≠ native word ≠ correct decode ≠ visible text ≠ semantic authority.
"""
from __future__ import annotations

import importlib.util

import pytest

from pb_drawing_ocr_evidence_layer import EvidenceMethod
from pb_figured_dimension_authority import parse_figured_dimension_mm
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_vector_geometry_v130 import extract_native_page
from tests.pdf_text_integrity_test_support import (
    BASE_SHA,
    control_character_pdf_bytes,
    ingest_source,
    ingest_visibility,
    malformed_tounicode_pdf_bytes,
    open_page,
    selector_for_word,
    simple_text_pdf_bytes,
    text_and_fill_pdf_bytes,
    type3_text_pdf_bytes,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="producer-owned PDF text-integrity/visibility authority is not implemented on current main",
)


def _has_text_integrity_module() -> bool:
    return importlib.util.find_spec("pb_pdf_text_integrity_authority") is not None


def _future_module():
    if not _has_text_integrity_module():
        raise AssertionError("pb_pdf_text_integrity_authority is absent")
    import pb_pdf_text_integrity_authority as mod  # type: ignore

    return mod


def _require_future_resolution_api(mod) -> None:
    """Keep the gate implementation-neutral while requiring a real authority surface."""

    public = {
        name
        for name in dir(mod)
        if not name.startswith("_")
    }
    if not public.intersection(
        {
            "PdfTextIntegrityAuthority",
            "PdfTextIntegrityProducer",
            "SourceTextIntegrityAuthority",
            "SourceTextIntegrityProducer",
            "resolve_text_integrity",
        }
    ):
        raise AssertionError("no producer-owned text-integrity authority API is exposed")


# ---------------------------------------------------------------------------
# Current-main locks — expected GREEN
# ---------------------------------------------------------------------------


def test_branch_bound_to_post_identity_main() -> None:
    assert BASE_SHA == "507c57db16be515e2432c695341bdea1e71b3fd7"


def test_current_source_authority_proves_native_word_existence_only() -> None:
    producer, published, authority = ingest_source(
        simple_text_pdf_bytes("900"), document_id="text-word-exists"
    )
    selector = selector_for_word(published, authority, text="900")
    result = authority.resolve(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.observation is not None
    assert result.observation.observation_kind == "native_pdf_word"
    assert result.observation.raw_text == "900"
    assert result.semantic_enumeration_complete is None
    assert result.decision_scope_complete is None
    assert not _has_text_integrity_module()
    assert producer.current_revision_id("text-word-exists") == published.revision.revision_id


def test_current_visibility_authority_has_no_text_resolver() -> None:
    _, _, visibility = ingest_visibility(
        simple_text_pdf_bytes("900"), document_id="text-no-visible-resolver"
    )
    assert hasattr(visibility, "resolve_visible")
    for name in (
        "resolve_visible_text",
        "resolve_trusted_text",
        "resolve_text_integrity",
    ):
        assert not hasattr(visibility, name)
    assert not _has_text_integrity_module()


def test_current_native_extractor_words_are_raw_not_authority_words() -> None:
    doc, page = open_page(simple_text_pdf_bytes("900"))
    try:
        native = extract_native_page(page)
    finally:
        doc.close()
    assert any(word.get("text") == "900" for word in native.get("words", ()))
    assert "authority_words" not in native
    assert "text_visibility_diagnostics" not in native


def test_figured_parser_can_parse_text_without_proving_text_integrity() -> None:
    # This is a deliberate hazard lock: measurement grammar is not decoding authority.
    assert parse_figured_dimension_mm("900") == 900.0
    assert not _has_text_integrity_module()


def test_ocr_and_native_text_are_distinct_provenance_methods() -> None:
    assert EvidenceMethod.NATIVE_TEXT.value != EvidenceMethod.RASTER_OCR.value
    assert EvidenceMethod.RECONCILED.value not in {
        EvidenceMethod.NATIVE_TEXT.value,
        EvidenceMethod.RASTER_OCR.value,
    }


def test_text_integrity_does_not_exist_via_opening_capabilities() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def test_raw_pdf_fixtures_decode_without_minting_authority() -> None:
    # Fixtures must be usable by future producer tests, but successful library
    # decoding here is explicitly not a trust claim.
    for payload in (
        malformed_tounicode_pdf_bytes(),
        control_character_pdf_bytes(),
        type3_text_pdf_bytes(),
        text_and_fill_pdf_bytes(fill_after_text=True),
    ):
        doc, page = open_page(payload)
        try:
            assert page.rect.width > 0
        finally:
            doc.close()
    assert not _has_text_integrity_module()


# ---------------------------------------------------------------------------
# Issue #330 acceptance attacks — strict EXPECTED RED
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_producer_owned_trusted_text_authority_exists() -> None:
    mod = _future_module()
    _require_future_resolution_api(mod)


@EXPECTED_RED
def test_attack02_missing_tounicode_cannot_silently_become_trusted_native_text() -> None:
    _future_module()
    payload = simple_text_pdf_bytes("900")
    producer, published, authority = ingest_source(payload, document_id="text-missing-tounicode")
    selector = selector_for_word(published, authority, text="900")
    assert selector.observation_id
    raise AssertionError("missing /ToUnicode decoding path has no producer-owned trust verdict")


@EXPECTED_RED
def test_attack03_malformed_cmap_fails_closed() -> None:
    _future_module()
    payload = malformed_tounicode_pdf_bytes()
    assert payload
    raise AssertionError("malformed CMap is not independently detected and blocked")


@EXPECTED_RED
def test_attack04_control_or_unprintable_decoding_fails_closed() -> None:
    _future_module()
    payload = control_character_pdf_bytes()
    assert payload
    raise AssertionError("control/unprintable decoded text lacks an integrity rejection path")


@EXPECTED_RED
def test_attack05_visual_vs_encoded_mismatch_is_conflict_not_authority() -> None:
    _future_module()
    raise AssertionError("visual glyph versus encoded Unicode mismatch is not independently reconciled")


@EXPECTED_RED
def test_attack06_type3_vector_glyph_text_is_quarantined() -> None:
    _future_module()
    payload = type3_text_pdf_bytes()
    doc, page = open_page(payload)
    try:
        # The source is intentionally observable; the missing result is a
        # producer-owned classification that it is safe semantic text.
        assert page.rect.width > 0
    finally:
        doc.close()
    raise AssertionError("Type-3/vector-glyph text has no current trusted-text quarantine verdict")


@EXPECTED_RED
def test_attack07_later_opaque_occlusion_blocks_text_authority() -> None:
    _future_module()
    payload = text_and_fill_pdf_bytes(fill_after_text=True)
    assert payload
    raise AssertionError("later opaque occlusion is not part of current producer-owned text authority")


@EXPECTED_RED
def test_attack08_fill_before_text_does_not_falsely_mark_later_text_occluded() -> None:
    _future_module()
    payload = text_and_fill_pdf_bytes(fill_after_text=False)
    assert payload
    raise AssertionError("paint-order-aware text visibility authority is not implemented")


@EXPECTED_RED
def test_attack09_unresolved_clip_or_visibility_state_cannot_firm_text() -> None:
    _future_module()
    raise AssertionError("unknown text clipping/visibility cannot currently be represented as a trusted-text blocker")


@EXPECTED_RED
def test_attack10_ocr_fallback_keeps_separate_provenance() -> None:
    _future_module()
    assert EvidenceMethod.NATIVE_TEXT.value != EvidenceMethod.RASTER_OCR.value
    raise AssertionError("producer-owned trusted-text authority does not yet preserve OCR fallback provenance")


@EXPECTED_RED
def test_attack11_low_confidence_ocr_fallback_is_not_trusted_text() -> None:
    _future_module()
    raise AssertionError("low-confidence OCR fallback has no trusted-text fail-closed gate")


@EXPECTED_RED
def test_attack12_native_vs_ocr_conflict_blocks_instead_of_strengthening() -> None:
    _future_module()
    raise AssertionError("native/OCR contradiction has no producer-owned text-integrity conflict resolver")


@EXPECTED_RED
def test_attack13_page_revision_source_and_snapshot_laundering_are_blocked() -> None:
    _future_module()
    raise AssertionError("trusted-text authority does not yet authenticate all source-scope selectors")


@EXPECTED_RED
def test_attack14_same_visible_string_from_different_source_bytes_is_not_same_receipt() -> None:
    _future_module()
    payload_a = simple_text_pdf_bytes("900")
    payload_b = text_and_fill_pdf_bytes(fill_after_text=False)
    assert payload_a != payload_b
    raise AssertionError("trusted-text receipt identity is not yet bound to immutable source bytes")


@EXPECTED_RED
def test_attack15_deterministic_replay_produces_same_text_integrity_identity() -> None:
    _future_module()
    payload = simple_text_pdf_bytes("900")
    assert payload == bytes(payload)
    raise AssertionError("deterministic trusted-text receipt replay is not implemented")


@EXPECTED_RED
def test_attack16_trusted_text_alone_does_not_unlock_opening_dimensions() -> None:
    _future_module()
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    raise AssertionError("future trusted text must retain the downstream firewall")
