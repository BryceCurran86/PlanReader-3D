"""Deterministic parity & invalidation tests for text-clip, symbol-cmap, viewport & semantic-label caches."""
from __future__ import annotations

import fitz

import pb_pdf_text_integrity_authority as text_auth
import pb_viewport_segmentation as vp_seg


def test_source_embedded_symbol_byte_glyph_unique_lookup_exact(monkeypatch) -> None:
    """Precomputed unique_byte_by_cp matches exact single-byte vs ambiguous-byte behavior."""
    class DummyPage:
        parent = object()

    page = DummyPage()
    font = (42, "ttf", "TrueType", "SymFont")

    import pb_pdf_source_symbol_font_authority as sym_mod

    # 0x41 -> 0x41 (unique, gid=10), 0x42 & 0x43 -> 0x42 (ambiguous!), 0x44 -> 0x44 (mismatch gid)
    monkeypatch.setattr(
        sym_mod,
        "_unique_source_tounicode",
        lambda doc, xref: ({0x41: 0x41, 0x42: 0x42, 0x43: 0x42, 0x44: 0x44}, "parsed_one_byte_bfrange_candidates"),
    )
    monkeypatch.setattr(
        sym_mod,
        "_source_truetype_symbol_subtables",
        lambda prog: ({0x41: 10, 0x42: 11, 0x43: 12, 0x44: 13}, "unique_symbol_gid_candidates"),
    )
    page.parent = type("Doc", (), {"extract_font": lambda self, x: (None, None, None, b"fake")})()

    assert text_auth._source_embedded_symbol_byte_glyph_reasons(page, {"chars": [(0x41, 10)]}, font) == ()
    assert text_auth._source_embedded_symbol_byte_glyph_reasons(page, {"chars": [(0x42, 11)]}, font) == (
        text_auth.TEXT_GLYPH_MAPPING_UNVERIFIED,
    )
    assert text_auth._source_embedded_symbol_byte_glyph_reasons(page, {"chars": [(0x44, 99)]}, font) == (
        text_auth.TEXT_GLYPH_UNICODE_MISMATCH,
    )


def test_rotated_raw_unclipped_text_immutable_page_caches_read_contents(monkeypatch) -> None:
    """Immutable fitz.Page caches raw unclipped check across words without re-reading contents."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 50), "FLOOR PLAN")
    page.set_rotation(90)
    pdf_bytes = doc.tobytes()
    doc.close()

    ro_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        ro_page = ro_doc[0]
        calls = {"unclipped": 0}

        import tools.diag_original_pdf_active_clip_operator_authority as clip_mod

        monkeypatch.setattr(text_auth, "_native_word_is_present", lambda p, nw: True)

        def fake_unclipped(p):
            calls["unclipped"] += 1
            return True

        monkeypatch.setattr(clip_mod, "source_page_all_native_text_unclipped", fake_unclipped)

        r1 = text_auth._text_clip_reasons(
            ro_page, (10, 10, 50, 20), 0, native_word={"text": "FLOOR"}, source_raw_no_active_text_clip_shadow=True
        )
        r2 = text_auth._text_clip_reasons(
            ro_page, (60, 10, 100, 20), 1, native_word={"text": "PLAN"}, source_raw_no_active_text_clip_shadow=True
        )
        assert r1 == ()
        assert r2 == ()
        assert calls["unclipped"] == 1
    finally:
        ro_doc.close()


def test_segment_page_viewports_cache_exact_and_mutation_isolated() -> None:
    """Bounded LRU cache returns stamped, mutation-isolated viewports across reopened docs."""
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.draw_rect(fitz.Rect(40, 40, 760, 560))
    page.insert_text((300, 540), "FLOOR PLAN", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    vp_seg._SEGMENT_PAGE_VIEWPORTS_CACHE.clear()
    d1 = fitz.open(stream=pdf_bytes, filetype="pdf")
    d2 = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        v1 = vp_seg.segment_page_viewports(d1[0], page_number=1)
        assert len(vp_seg._SEGMENT_PAGE_VIEWPORTS_CACHE) == 1
        for vp in v1:
            assert vp_seg.is_segment_page_viewports_product(vp)
        # Mutate returned viewport to verify cached copy is isolated
        if v1:
            v1[0].label = "TAMPERED"

        v2 = vp_seg.segment_page_viewports(d2[0], page_number=1)
        assert len(v2) == len(v1)
        for vp in v2:
            assert vp_seg.is_segment_page_viewports_product(vp)
            assert vp.label != "TAMPERED"
    finally:
        d1.close()
        d2.close()
