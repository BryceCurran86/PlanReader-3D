from __future__ import annotations

import fitz

from pb_vector_geometry_v130 import extract_native_page


def test_native_segments_preserve_pdf_drawing_sequence_number() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=200.0, height=120.0)
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(20.0, 20.0, 80.0, 60.0))
        shape.finish(fill=(1.0, 1.0, 1.0), color=None)
        shape.commit()
        payload = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    reopened = fitz.open(stream=payload, filetype="pdf")
    try:
        page = reopened[0]
        drawings = page.get_drawings()
        assert drawings
        expected_seqno = int(drawings[0]["seqno"])
        native = extract_native_page(page)
    finally:
        reopened.close()

    rect_edges = [
        segment
        for segment in native["segments"]
        if segment.get("kind") == "rect_edge"
    ]
    assert len(rect_edges) == 4
    assert {segment.get("sequence_number") for segment in rect_edges} == {
        expected_seqno
    }
