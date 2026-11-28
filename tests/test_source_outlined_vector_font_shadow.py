"""Tests for producer-owned outlined and vector-font text recognition shadow authority (Item 26)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_outlined_vector_font_shadow import (
    GLYPH_BASELINE_ALIGNED,
    GLYPH_INK_CANDIDATE,
    GLYPH_KERNING_REGULAR,
    GLYPH_RUN_CORROBORATED,
    ISOLATED_PATH_NOT_RUN,
    NOT_GLYPH_INK,
    PATH_EXTENT_OVER_BOUND,
    SOURCE_OUTLINED_TEXT_RESOLVED,
    SOURCE_OUTLINED_TEXT_UNAVAILABLE,
    STRUCTURAL_STROKE_CONTACT_VETO,
    UNPROVEN,
    SourceOutlinedGlyphRunRecord,
    SourceOutlinedVectorFontAuthority,
    SourceOutlinedVectorFontProducer,
    SourceOutlinedVectorFontSelector,
    classify_outlined_text_ink,
)


def _seg(ident, x1, y1, x2, y2, *, path=None):
    return {
        "id": ident,
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "path_index": ident if path is None else path,
    }


def _make_letter(prefix, bx, by):
    # Small 3-segment character glyph (~2x6 pt)
    return [
        _seg(f"{prefix}.1", bx, by, bx + 1.0, by - 6.0, path=prefix),
        _seg(f"{prefix}.2", bx + 1.0, by - 6.0, bx + 2.0, by, path=prefix),
        _seg(f"{prefix}.3", bx + 0.5, by - 3.0, bx + 1.5, by - 3.0, path=prefix),
    ]


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedVectorFontProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedVectorFontAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedGlyphRunRecord(
            record_id="rec-1",
            run_id="run-1",
            orientation="horizontal",
            glyph_count=5,
            bounding_box=(0.0, 0.0, 50.0, 10.0),
            segment_ids=("s1", "s2"),
            reason_codes=(),
        )


def test_synthetic_positive_outlined_glyph_run():
    # 5 character glyphs along baseline y=100.0, spaced with 3 pt gaps
    segs = []
    for i in range(5):
        segs.extend(_make_letter(f"L{i}", 100.0 + 6.0 * i, 100.0))

    clf = classify_outlined_text_ink(segs, page_width=500.0, page_height=500.0)
    assert clf["status"] == "CLASSIFICATION_COMPLETE"
    assert clf["total_source_segments"] == 15
    assert clf["glyph_candidate_segment_count"] == 15
    assert clf["would_remain_after_withholding"] == 0
    assert clf["glyph_run_count"] == 1

    run = clf["glyph_runs"][0]
    assert run["glyph_count"] == 5
    assert run["orientation"] == "horizontal"
    assert GLYPH_BASELINE_ALIGNED in run["reason_codes"]
    assert GLYPH_KERNING_REGULAR in run["reason_codes"]
    assert GLYPH_RUN_CORROBORATED in run["reason_codes"]

    for s in segs:
        assert clf["classifications"][s["id"]] == GLYPH_INK_CANDIDATE


def test_structural_long_stroke_contact_veto():
    # Glyph touching a 50 pt wall line
    wall_seg = _seg("wall_1", 100.0, 100.0, 150.0, 100.0, path="wall_path")
    glyph_segs = _make_letter("L_touch", 100.5, 100.5)

    all_segs = [wall_seg] + glyph_segs
    clf = classify_outlined_text_ink(all_segs, page_width=500.0, page_height=500.0)

    # Wall segment is not a glyph (extent over bound)
    assert clf["classifications"]["wall_1"] == NOT_GLYPH_INK
    assert PATH_EXTENT_OVER_BOUND in clf["reason_receipts"]["wall_1"]

    # Glyph touching wall is vetoed and classified UNPROVEN
    for s in glyph_segs:
        assert clf["classifications"][s["id"]] == UNPROVEN
        assert STRUCTURAL_STROKE_CONTACT_VETO in clf["reason_receipts"][s["id"]]


def test_oversized_path_classified_not_glyph():
    # Path with 30 pt segment: too large for text glyph
    large_seg = _seg("large_stroke", 0.0, 0.0, 30.0, 0.0, path="p_large")
    clf = classify_outlined_text_ink([large_seg], page_width=500.0, page_height=500.0)
    assert clf["classifications"]["large_stroke"] == NOT_GLYPH_INK
    assert PATH_EXTENT_OVER_BOUND in clf["reason_receipts"]["large_stroke"]


def test_isolated_glyph_path_not_in_run():
    # Only 1 letter (requires >= 3 for a run)
    segs = _make_letter("solo", 50.0, 50.0)
    clf = classify_outlined_text_ink(segs, page_width=500.0, page_height=500.0)
    assert clf["glyph_run_count"] == 0
    for s in segs:
        assert clf["classifications"][s["id"]] == UNPROVEN
        assert ISOLATED_PATH_NOT_RUN in clf["reason_receipts"][s["id"]]


def test_irregular_kerning_breaks_run():
    # 2 letters close together, 3rd letter far away (gap = 40 pt > 15 pt max gap)
    l1 = _make_letter("L1", 10.0, 50.0)
    l2 = _make_letter("L2", 15.0, 50.0)
    l3 = _make_letter("L3", 60.0, 50.0)  # far gap
    all_segs = l1 + l2 + l3

    clf = classify_outlined_text_ink(all_segs, page_width=500.0, page_height=500.0)
    # Neither cluster has >= 3 members, so no run formed
    assert clf["glyph_run_count"] == 0
    assert clf["glyph_candidate_segment_count"] == 0


def test_authority_resolution_and_selector():
    producer = SourceOutlinedVectorFontProducer.create()
    segs = []
    for i in range(4):
        segs.extend(_make_letter(f"L{i}", 200.0 + 8.0 * i, 300.0))

    producer.register_page_vector_segments(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        segments=segs,
        page_width=842.0,
        page_height=595.0,
    )
    authority = producer.authority()

    sel = SourceOutlinedVectorFontSelector(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
    )
    res = authority.resolve(sel)
    assert res.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOURCE_OUTLINED_TEXT_RESOLVED in res.reason_codes
    assert res.total_segments == 12
    assert res.withheld_segment_count == 12
    assert res.retained_segment_count == 0
    assert len(res.records) == 1
    assert res.records[0].glyph_count == 4
    assert res.records[0].status == EvidenceResolutionStatus.CANDIDATE.value
    assert res.records[0].commercial_projection_allowed is False
    assert res.records[0].takeoff_eligible is False

    # Unregistered selector
    sel_unreg = SourceOutlinedVectorFontSelector(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="99",
    )
    res_unreg = authority.resolve(sel_unreg)
    assert res_unreg.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_OUTLINED_TEXT_UNAVAILABLE in res_unreg.reason_codes


def test_extract_outlined_vector_font_ocr_witnesses_wires_multi_dpi_and_abstains_missing_finishes():
    import fitz
    from pb_source_outlined_vector_font_shadow import (
        OutlinedVectorFontOcrWitnessBundle,
        extract_outlined_vector_font_ocr_witnesses,
    )
    from pb_source_vector_outlined_text_ocr_shadow import OcrRawToken

    class _FakePage:
        def __init__(self, body_words: int, drawings: int):
            self.rect = fitz.Rect(0.0, 0.0, 1000.0, 700.0)
            self._body_words = body_words
            self._drawings = drawings

        def get_text(self, mode):
            assert mode == "words"
            return [(100.0, 100.0, 120.0, 110.0, "W", 0, 0, 0)] * self._body_words

        def get_drawings(self):
            return [{}] * self._drawings

        def get_images(self):
            return []

        def get_pixmap(self, dpi, clip, alpha=False):
            class _Pix:
                def tobytes(self, fmt):
                    return f"dpi={dpi}".encode("ascii")

            return _Pix()

    def _fake_ocr(png_bytes: bytes):
        dpi = int(png_bytes.decode("ascii").split("=")[1])
        scale = dpi / 72.0
        return [
            OcrRawToken("3600", (100 * scale, 100 * scale, 140 * scale, 112 * scale), 0.96),
            OcrRawToken("D01", (200 * scale, 150 * scale, 230 * scale, 162 * scale), 0.94),
        ]

    # Page 0: native-font page (not outlined -> skipped); Page 1: outlined vector sheet
    p_native = _FakePage(body_words=120, drawings=800)
    p_outlined = _FakePage(body_words=2, drawings=1500)
    bundle = extract_outlined_vector_font_ocr_witnesses(
        [(0, p_native), (1, p_outlined)],
        source_sha256="b" * 64,
        render_dpis=(144, 216),
        ocr_callable=_fake_ocr,
        finish_specification_present=False,
    )
    assert isinstance(bundle, OutlinedVectorFontOcrWitnessBundle)
    assert bundle.status == "REVIEW_ONLY_OUTLINED_OCR_WITNESSES"
    assert bundle.commercial_projection_allowed is False
    assert bundle.takeoff_eligible is False
    assert bundle.shadow_only is True
    assert len(bundle.body_assessments) == 2
    assert bundle.body_assessments[0].outlined_text_suspected is False
    assert bundle.body_assessments[1].outlined_text_suspected is True
    # Only the outlined page underwent OCR extraction.
    assert len(bundle.extractions) == 1
    assert bundle.extractions[0].page_index == 1
    assert "3600" in bundle.cross_sheet_review.corroborated_dimension_tokens
    assert "D01" in bundle.cross_sheet_review.corroborated_opening_marks
    assert bundle.cross_sheet_review.finish_authority_status == "ABSTAINED"
    assert bundle.cross_sheet_review.finish_authority_reason == "material_specification_missing"


def test_extract_outlined_vector_font_ocr_witnesses_skips_all_native_pages_cleanly():
    import fitz
    from pb_source_outlined_vector_font_shadow import extract_outlined_vector_font_ocr_witnesses

    class _NativePage:
        rect = fitz.Rect(0.0, 0.0, 1000.0, 700.0)

        def get_text(self, mode):
            return [(100.0, 100.0, 120.0, 110.0, "NATIVE", 0, 0, 0)] * 80

        def get_drawings(self):
            return [{}] * 900

        def get_images(self):
            return []

    bundle = extract_outlined_vector_font_ocr_witnesses(
        [(0, _NativePage())],
        source_sha256="c" * 64,
        render_dpis=(144, 216),
    )
    assert bundle.status == EvidenceResolutionStatus.ABSTAINED.value
    assert bundle.extractions == ()
    assert bundle.commercial_projection_allowed is False


def test_admit_and_extract_outlined_drawing_set_shadow_consumer_wiring():
    from dataclasses import replace
    import hashlib
    import fitz
    from pb_source_outlined_vector_font_shadow import (
        OutlinedDrawingSetIngestionShadowBundle,
        admit_and_extract_outlined_drawing_set_shadow,
    )

    doc = fitz.open()
    for title in ("SITE PLAN", "GROUND FLOOR PLAN", "NORTH ELEVATION"):
        page = doc.new_page(width=1000.0, height=700.0)
        page.insert_text((820.0, 640.0), title, fontsize=9)
        page.insert_text((820.0, 665.0), "SCALE 1:100", fontsize=9)
        shape = page.new_shape()
        for j in range(600):
            x = 50.0 + (j % 50) * 12.0
            y = 50.0 + (j // 50) * 12.0
            shape.draw_line(fitz.Point(x, y), fitz.Point(x + 8.0, y))
            shape.finish(color=(0, 0, 0), width=0.5)
        shape.commit()
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    import struct
    from pb_source_vector_outlined_text_ocr_shadow import OcrRawToken

    def _fake_ocr(png: bytes):
        pw, _ph = struct.unpack(">II", png[16:24])
        scale = pw / 800.0  # clip width is 800 pts
        return (
            OcrRawToken(text="3600", confidence=0.96, bbox_px=(100.0 * scale, 100.0 * scale, 140.0 * scale, 112.0 * scale)),
            OcrRawToken(text="W01", confidence=0.93, bbox_px=(220.0 * scale, 150.0 * scale, 245.0 * scale, 162.0 * scale)),
        )

    res = admit_and_extract_outlined_drawing_set_shadow(
        pdf_bytes,
        expected_source_sha256=sha,
        finish_specification_present=False,
        render_dpis=(144, 216),
        ocr_callable=_fake_ocr,
    )
    assert isinstance(res, OutlinedDrawingSetIngestionShadowBundle)
    assert res.status == "ADMITTED_AND_EXTRACTED_SHADOW"
    # Picks GROUND FLOOR PLAN (1) and NORTH ELEVATION (2), never SITE PLAN (0)
    assert res.selected_page_indices == (1, 2)
    assert res.admission_report.sheet_assessments[0].detected_role == "site_or_cover"
    assert res.admission_report.finish_authority_status == "ABSTAINED"
    assert res.admission_report.finish_authority_reason == "material_specification_missing"
    assert res.ocr_witness_bundle is not None
    assert "3600" in res.ocr_witness_bundle.cross_sheet_review.corroborated_dimension_tokens
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
    assert res.shadow_only is True
    with pytest.raises(ValueError):
        replace(res, commercial_projection_allowed=True)

    # Negative: primitive cap overflow abstains before any OCR runs
    capped = admit_and_extract_outlined_drawing_set_shadow(
        pdf_bytes,
        expected_source_sha256=sha,
        max_drawings_per_page=500,
        ocr_callable=_fake_ocr,
    )
    assert capped.status == "ABSTAINED"
    assert "source_primitive_cap_exceeded" in capped.reason_codes
    assert capped.ocr_witness_bundle is None

