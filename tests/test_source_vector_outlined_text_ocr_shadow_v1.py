"""Tests for reusable generic vector-outlined text OCR shadow (Item 3)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_source_vector_outlined_text_ocr_shadow import (
    OcrRawToken,
    detect_outlined_text_drawing_body,
    extract_vector_outlined_text_multi_dpi_shadow,
    reconcile_outlined_cross_sheet_witness_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "c" * 64


def _make_blank_pdf_page():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    return doc, page


def test_multi_dpi_agreement_retains_agreed_tokens_and_rejects_single_dpi_and_conflicts():
    doc, page = _make_blank_pdf_page()
    try:
        calls = {"idx": 0}
        dpis = (144, 216, 288)

        def fake_ocr(_png: bytes):
            dpi = dpis[calls["idx"]]
            calls["idx"] += 1
            scale = dpi / 72.0
            tokens = [
                # Agreed across all 3 DPIs at PDF (50..80, 40..52)
                OcrRawToken("2400", (50 * scale, 40 * scale, 80 * scale, 52 * scale), 0.96),
                # Agreed across 2 of 3 DPIs at PDF (120..145, 40..52)
                OcrRawToken("D03", (120 * scale, 40 * scale, 145 * scale, 52 * scale), 0.92),
            ]
            if dpi == 144:
                # Single-DPI hallucination -> must be rejected
                tokens.append(OcrRawToken("9999", (200 * scale, 80 * scale, 230 * scale, 92 * scale), 0.90))
                # Conflicting token at (20..40, 100..112)
                tokens.append(OcrRawToken("1800", (20 * scale, 100 * scale, 40 * scale, 112 * scale), 0.91))
            elif dpi == 216:
                tokens.append(OcrRawToken("1850", (20 * scale, 100 * scale, 40 * scale, 112 * scale), 0.91))
            return tokens

        res = extract_vector_outlined_text_multi_dpi_shadow(
            page=page,
            source_sha256=_SHA,
            page_index=1,
            region_bbox_pts=(0.0, 0.0, 300.0, 200.0),
            render_dpis=dpis,
            ocr_callable=fake_ocr,
            min_dpi_agreement=2,
        )
        assert res.status == "CORROBORATED_MULTI_DPI_OUTLINED_TEXT_SHADOW"
        assert res.commercial_projection_allowed is False
        assert res.shadow_only is True
        norms = [t.normalized_text for t in res.agreed_tokens]
        assert norms == ["2400", "D03"]
        assert res.rejected_single_dpi_count == 1
        assert res.rejected_conflicting_count == 1

        # Cross-sheet review: dims & marks reconciled, missing finish spec MUST abstain
        rev = reconcile_outlined_cross_sheet_witness_shadow(
            extractions=(res,),
            expected_source_sha256=_SHA,
            finish_specification_present=False,
        )
        assert rev.status == "REVIEW_ONLY_OUTLINED_WITNESSES_RECONCILED"
        assert rev.corroborated_dimension_tokens == ("2400",)
        assert rev.corroborated_opening_marks == ("D03",)
        assert rev.finish_authority_status == "ABSTAINED"
        assert rev.finish_authority_reason == "material_specification_missing"
        assert rev.commercial_projection_allowed is False
    finally:
        doc.close()


def test_cross_revision_sha_mixing_abstains():
    doc, page = _make_blank_pdf_page()
    try:
        res = extract_vector_outlined_text_multi_dpi_shadow(
            page=page,
            source_sha256=_SHA,
            page_index=1,
            region_bbox_pts=(0.0, 0.0, 100.0, 100.0),
            render_dpis=(144, 216),
            ocr_callable=lambda _b: [OcrRawToken("2700", (10, 10, 40, 20), 0.95)],
        )
        rev = reconcile_outlined_cross_sheet_witness_shadow(
            extractions=(res,),
            expected_source_sha256="d" * 64,  # wrong revision/region SHA
        )
        assert rev.status == "ABSTAINED"
        assert "cross_revision_or_region_sha_mismatch" in rev.reason_codes
    finally:
        doc.close()


def test_detect_outlined_text_drawing_body_distinguishes_outlined_vs_native():
    fake_outlined = SimpleNamespace(
        rect=SimpleNamespace(width=1000.0, height=800.0),
        get_text=lambda _mode: [(850, 700, 950, 720, "TITLE")] * 150 + [(100, 100, 120, 110, "N")] * 4,
        get_drawings=lambda: [{}] * 2500,
        get_images=lambda: [],
    )
    a1 = detect_outlined_text_drawing_body(fake_outlined, page_index=1)
    assert a1.outlined_text_suspected is True
    assert a1.body_native_words == 4
    assert a1.border_native_words == 150

    fake_native = SimpleNamespace(
        rect=SimpleNamespace(width=1000.0, height=800.0),
        get_text=lambda _mode: [(100, 100, 140, 112, "WORD")] * 120,
        get_drawings=lambda: [{}] * 2500,
        get_images=lambda: [],
    )
    a2 = detect_outlined_text_drawing_body(fake_native, page_index=1)
    assert a2.outlined_text_suspected is False


def test_zero_job_specific_shared_source_rules():
    path = Path(__file__).resolve().parents[1] / "pb_source_vector_outlined_text_ocr_shadow.py"
    assert audit_shared_source(path.read_text(encoding="utf-8"), filename=path.name) == ()
