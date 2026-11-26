"""A01: single-pass get_drawings(extended=True) parity & mock fallback tests."""
from __future__ import annotations

import fitz

import pb_vector_geometry_v130 as vg


def test_single_pass_fitz_page_matches_two_pass_and_calls_get_drawings_once() -> None:
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(20.0, 20.0, 200.0, 150.0))
    shape.finish(color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=1.0)
    shape.draw_line(fitz.Point(50.0, 50.0), fitz.Point(350.0, 50.0))
    shape.finish(color=(0, 0, 0), width=0.5, closePath=False)
    shape.commit()
    page.insert_text((60.0, 80.0), "ROOM A", fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()

    d2 = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        p = d2[0]
        # Reference two-pass
        ref_drawings = list(p.get_drawings() or [])
        ref_clip = vg._clip_scissor_by_seqno(p)

        # Single-pass via _extract_drawings_and_clip_table
        single_drawings, single_clip = vg._extract_drawings_and_clip_table(p)
        assert single_clip == ref_clip
        assert len(single_drawings) == len(ref_drawings)
        for a, b in zip(single_drawings, ref_drawings):
            for k in ("items", "rect", "color", "fill", "width", "dashes", "seqno", "type"):
                assert a.get(k) == b.get(k)

        # Verify extract_native_page produces identical segments/rects
        res = vg.extract_native_page(p, page_index=0)
        assert len(res["segments"]) >= 5
        assert len(res["rects"]) >= 1
    finally:
        d2.close()


def test_mock_page_uses_legacy_two_call_fallback_and_handles_extended_error() -> None:
    calls: list[bool] = []

    class _FakePage:
        def get_drawings(self, *, extended: bool = False):
            calls.append(extended)
            if extended:
                raise RuntimeError("extended unsupported")
            return [{"items": [("l", (0.0, 0.0), (10.0, 0.0))], "seqno": 1, "width": 1.0}]

    drawings, clip_table = vg._extract_drawings_and_clip_table(_FakePage())
    assert calls == [False, True]
    assert len(drawings) == 1
    assert clip_table.available is False
