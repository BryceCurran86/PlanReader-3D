"""Executable successor to historical PDF text-integrity validator #338.

Baseline current main keeps the 16 future-authority attacks strict XFAIL.
When replayed on a production implementation, ``pytest --runxfail`` converts
those attacks into concrete requirements without module-absence locks or
placeholder failures.
"""
from __future__ import annotations

import importlib
import importlib.util

import pytest

from pb_drawing_ocr_evidence_layer import EvidenceMethod
from pb_figured_dimension_authority import parse_figured_dimension_mm
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page
from tests.pdf_text_integrity_replay_support import (
    BASE_SHA,
    clipped_text_pdf_bytes,
    control_character_pdf_bytes,
    ingest_source,
    malformed_tounicode_pdf_bytes,
    open_page,
    selector_for_word,
    simple_text_pdf_bytes,
    text_and_fill_pdf_bytes,
    type3_text_pdf_bytes,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="producer-owned PDF text-integrity authority is not present on baseline main",
)


def _future_module():
    if importlib.util.find_spec("pb_pdf_text_integrity_authority") is None:
        raise AssertionError("producer-owned PDF text-integrity module is absent")
    return importlib.import_module("pb_pdf_text_integrity_authority")


def _ingest_text(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="pdf-text-integrity-executable-validator",
        producer_version="2.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    factory = getattr(producer, "text_integrity_authority", None)
    assert callable(factory), "producer-owned text-integrity query surface is missing"
    authority = factory()
    observation_ids = tuple(getattr(published, "text_observation_ids", ()))
    assert observation_ids, "producer did not publish native text observation selectors"
    selectors = tuple(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in observation_ids
    )
    return producer, published, authority, selectors


def _first_text_result(payload: bytes, *, document_id: str):
    producer, published, authority, selectors = _ingest_text(
        payload, document_id=document_id
    )
    selector = selectors[0]
    return producer, published, authority, selector, authority.resolve_text(selector)


# ---------------------------------------------------------------------------
# Baseline locks. These remain valid both before and after text-integrity work.
# ---------------------------------------------------------------------------


def test_branch_bound_to_current_main() -> None:
    assert BASE_SHA == "e27ffad284b05123ffacbbe123c69823c5367dee"


def test_source_authority_native_word_is_raw_substrate_only() -> None:
    producer, published, authority = ingest_source(
        simple_text_pdf_bytes("900"), document_id="text-word-substrate"
    )
    selector = selector_for_word(published, authority, text="900")
    result = authority.resolve(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.observation is not None
    assert result.observation.observation_kind == "native_pdf_word"
    assert result.observation.raw_text == "900"
    assert result.semantic_enumeration_complete is None
    assert result.decision_scope_complete is None
    assert producer.current_revision_id("text-word-substrate") == published.revision.revision_id


def test_source_visibility_remains_separate_from_text_semantics() -> None:
    producer = SourceVisibilityProducer(
        producer_method="pdf-text-integrity-executable-validator",
        producer_version="2.0",
    )
    producer.ingest_native_pdf_bytes(
        document_id="text-visibility-separation",
        source_bytes=simple_text_pdf_bytes("900"),
        source_locator="memory://text-visibility-separation.pdf",
    )
    visibility = producer.authority()
    assert callable(visibility.resolve_visible)
    assert not hasattr(visibility, "resolve_dimension")


def test_native_extractor_words_are_not_semantic_authority_records() -> None:
    doc, page = open_page(simple_text_pdf_bytes("900"))
    try:
        native = extract_native_page(page)
    finally:
        doc.close()
    assert any(word.get("text") == "900" for word in native.get("words", ()))
    assert "authority_words" not in native
    assert "opening_dimensions" not in native


def test_figured_parser_is_not_decode_or_visibility_authority() -> None:
    assert parse_figured_dimension_mm("900") == 900.0


def test_native_and_ocr_provenance_methods_remain_distinct() -> None:
    assert EvidenceMethod.NATIVE_TEXT.value != EvidenceMethod.RASTER_OCR.value
    assert EvidenceMethod.RECONCILED.value not in {
        EvidenceMethod.NATIVE_TEXT.value,
        EvidenceMethod.RASTER_OCR.value,
    }


def test_downstream_opening_capabilities_remain_locked() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def test_adversarial_pdf_fixtures_decode_as_source_material() -> None:
    for payload in (
        malformed_tounicode_pdf_bytes(),
        control_character_pdf_bytes(),
        type3_text_pdf_bytes(),
        text_and_fill_pdf_bytes(fill_after_text=True),
        clipped_text_pdf_bytes(),
    ):
        doc, page = open_page(payload)
        try:
            assert page.rect.width > 0
        finally:
            doc.close()


# ---------------------------------------------------------------------------
# Historical #338 attack semantics, repaired into executable requirements.
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_producer_owned_trusted_text_authority_exists() -> None:
    _producer, _published, authority, _selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack01-text-authority"
    )
    assert callable(authority.resolve_text)
    for writer in ("ingest_native_pdf_bytes", "publish_derived_observation", "write"):
        assert not hasattr(authority, writer)


@EXPECTED_RED
def test_attack02_missing_tounicode_requires_a_narrow_known_encoding_proof() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        simple_text_pdf_bytes("900"), document_id="attack02-standard-encoding"
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text == "900"
    assert result.receipt is not None
    assert result.receipt.decode_status == "known_standard_encoding"


@EXPECTED_RED
def test_attack03_malformed_cmap_fails_closed() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        malformed_tounicode_pdf_bytes(), document_id="attack03-malformed-cmap"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "text_tounicode_malformed" in result.reason_codes


@EXPECTED_RED
def test_attack04_control_or_unprintable_decoding_fails_closed() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        control_character_pdf_bytes(), document_id="attack04-control-text"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert any(
        code in result.reason_codes
        for code in ("text_unicode_untrusted", "text_decode_mismatch")
    )


@EXPECTED_RED
def test_attack05_visual_vs_encoded_mismatch_is_not_trusted() -> None:
    mod = _future_module()

    class MismatchPage:
        def get_texttrace(self):
            return [
                {
                    "chars": tuple((ord(char),) for char in "901"),
                    "bbox": (0.0, 0.0, 30.0, 10.0),
                }
            ]

    decision = mod.classify_native_word_integrity(
        MismatchPage(),
        {"text": "900", "bbox": (0.0, 0.0, 30.0, 10.0)},
    )
    assert decision.trusted is False
    assert decision.reason_codes


@EXPECTED_RED
def test_attack06_type3_vector_glyph_text_is_quarantined() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        type3_text_pdf_bytes(), document_id="attack06-type3"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert any(
        code in result.reason_codes
        for code in ("text_type3_font_untrusted", "text_render_mode_untrusted")
    )


@EXPECTED_RED
def test_attack07_later_opaque_occlusion_blocks_text_authority() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        text_and_fill_pdf_bytes(fill_after_text=True),
        document_id="attack07-later-occlusion",
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "text_occluded_by_later_paint" in result.reason_codes


@EXPECTED_RED
def test_attack08_fill_before_text_is_not_misclassified_as_later_occlusion() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        text_and_fill_pdf_bytes(fill_after_text=False),
        document_id="attack08-earlier-fill",
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text == "900"


@EXPECTED_RED
def test_attack09_unresolved_clip_state_cannot_firm_text() -> None:
    _p, _published, _authority, _selector, result = _first_text_result(
        clipped_text_pdf_bytes(), document_id="attack09-clip"
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert "text_clip_state_unresolved" in result.reason_codes


@EXPECTED_RED
def test_attack10_ocr_fallback_cannot_enter_native_text_authority() -> None:
    _p, _published, authority, _selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack10-ocr-separation"
    )
    assert EvidenceMethod.NATIVE_TEXT.value != EvidenceMethod.RASTER_OCR.value
    for name in ("resolve_ocr", "resolve_ocr_text", "resolve_reconciled_text"):
        assert not hasattr(authority, name)


@EXPECTED_RED
def test_attack11_low_confidence_caller_ocr_cannot_mint_trusted_text() -> None:
    _p, published, authority, selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack11-low-confidence-ocr"
    )
    selector = selectors[0]

    class CallerOcrClaim:
        document_id = selector.document_id
        revision_id = selector.revision_id
        source_sha256 = selector.source_sha256
        snapshot_id = selector.snapshot_id
        observation_id = "caller-ocr-observation"
        raw_text = "900"
        confidence = 0.01
        method = EvidenceMethod.RASTER_OCR.value

    result = authority.resolve_text(CallerOcrClaim())
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.trusted_text is None
    assert published.revision.document_id == selector.document_id


@EXPECTED_RED
def test_attack12_caller_ocr_contradiction_cannot_rewrite_native_result() -> None:
    _p, _published, authority, selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack12-ocr-conflict"
    )
    selector = selectors[0]
    baseline = authority.resolve_text(selector)
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    assert baseline.trusted_text == "900"

    class ContradictoryOcrClaim:
        document_id = selector.document_id
        revision_id = selector.revision_id
        source_sha256 = selector.source_sha256
        snapshot_id = selector.snapshot_id
        observation_id = selector.observation_id
        raw_text = "901"
        confidence = 0.99
        method = EvidenceMethod.RASTER_OCR.value

    with pytest.raises((TypeError, AttributeError)):
        authority.resolve_text(ContradictoryOcrClaim())
    for name in ("reconcile", "resolve_reconciled_text"):
        assert not hasattr(authority, name)


@EXPECTED_RED
def test_attack13_revision_source_and_snapshot_laundering_are_blocked() -> None:
    _p, _published, authority, selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack13-scope-laundering"
    )
    selector = selectors[0]
    forged = (
        ObservationSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256="0" * 64,
            snapshot_id=selector.snapshot_id,
            observation_id=selector.observation_id,
        ),
        ObservationSelector(
            document_id=selector.document_id,
            revision_id="revision-forged",
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            observation_id=selector.observation_id,
        ),
        ObservationSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id="snapshot-forged",
            observation_id=selector.observation_id,
        ),
    )
    for forged_selector in forged:
        result = authority.resolve_text(forged_selector)
        assert result.status is not EvidenceResolutionStatus.CORROBORATED
        assert result.trusted_text is None


@EXPECTED_RED
def test_attack14_same_string_from_different_source_bytes_has_distinct_receipt() -> None:
    _p1, published_a, _a1, _s1, result_a = _first_text_result(
        simple_text_pdf_bytes(), document_id="attack14-source-a"
    )
    _p2, published_b, _a2, _s2, result_b = _first_text_result(
        text_and_fill_pdf_bytes(fill_after_text=False), document_id="attack14-source-b"
    )
    assert result_a.status is EvidenceResolutionStatus.CORROBORATED
    assert result_b.status is EvidenceResolutionStatus.CORROBORATED
    assert result_a.receipt is not None and result_b.receipt is not None
    assert published_a.revision.source_sha256 != published_b.revision.source_sha256
    assert result_a.receipt.receipt_id != result_b.receipt.receipt_id


@EXPECTED_RED
def test_attack15_deterministic_replay_preserves_text_integrity_identity() -> None:
    _p, _published, authority, selector, first = _first_text_result(
        simple_text_pdf_bytes(), document_id="attack15-deterministic"
    )
    second = authority.resolve_text(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.receipt is not None and second.receipt is not None
    assert first.receipt.receipt_id == second.receipt.receipt_id


@EXPECTED_RED
def test_attack16_trusted_text_alone_does_not_unlock_opening_dimensions() -> None:
    _p, _published, _authority, _selectors = _ingest_text(
        simple_text_pdf_bytes(), document_id="attack16-firewall"
    )
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
