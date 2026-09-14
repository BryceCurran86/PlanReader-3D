from __future__ import annotations

import fitz
import pytest

import pb_vector_geometry_v130 as vg


def _pdf_bytes(objects: dict[int, str]) -> bytes:
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


def _page_with_content(content: str, *, media: int = 100) -> fitz.Page:
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {media} {media}] "
            "/Resources << >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(content.encode('latin1'))} >>\nstream\n{content}\nendstream",
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _type3_page() -> fitz.Page:
    # Two draw operations inside one glyph deliberately prove that glyph
    # provenance cannot be inferred from a single immediately preceding path.
    char_stream = "0 0 500 500 re S 0 0 m 500 500 l S"
    page_stream = "BT /F3 20 Tf 10 50 Td (A) Tj ET\n10 10 m 90 10 l S"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            "/Resources << /Font << /F3 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
        5: (
            "<< /Type /Font /Subtype /Type3 /Name /F3 /FontBBox [0 0 500 500] "
            "/FontMatrix [0.001 0 0 0.001 0 0] "
            "/CharProcs << /A 6 0 R >> "
            "/Encoding << /Type /Encoding /Differences [65 /A] >> "
            "/FirstChar 65 /LastChar 65 /Widths [500] /Resources << >> >>"
        ),
        6: f"<< /Length {len(char_stream)} >>\nstream\n{char_stream}\nendstream",
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _text_and_fill_page(*, fill_after_text: bool) -> fitz.Page:
    text = "BT /F1 10 Tf 10 50 Td (FIRE) Tj ET"
    fill = "0 0 0 rg 5 40 45 20 re f"
    page_stream = f"{text} {fill}" if fill_after_text else f"{fill} {text}"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _single_form_page(matrix: str) -> fitz.Page:
    page_stream = "q /F1 Do Q"
    form_stream = "0 0 m 10 0 l S"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
            "/Resources << /XObject << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
        5: (
            "<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] "
            f"/Matrix [{matrix}] /Resources << >> "
            f"/Length {len(form_stream)} >>\nstream\n{form_stream}\nendstream"
        ),
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _line_tuple(segment: dict) -> tuple[float, float, float, float]:
    return segment["x1"], segment["y1"], segment["x2"], segment["y2"]


def test_authority_segments_use_rectangular_visible_geometry_not_raw_source() -> None:
    native = vg.extract_native_page(
        _page_with_content("q 0 0 50 50 re W n -10 25 m 100 25 l S Q")
    )
    raw_line = next(item for item in native["segments"] if item["kind"] == "line")
    authoritative = [item for item in native["authority_segments"] if item["kind"] == "line"]

    assert _line_tuple(raw_line) == pytest.approx((-10.0, 75.0, 100.0, 75.0))
    assert len(authoritative) == 1
    assert _line_tuple(authoritative[0]) == pytest.approx((0.0, 75.0, 50.0, 75.0))
    assert authoritative[0]["authority_geometry_status"] == "PROVEN_VISIBLE"


def test_fully_clipped_source_cannot_enter_authority_segments() -> None:
    native = vg.extract_native_page(
        _page_with_content("q 0 0 50 50 re W n -10 75 m 100 75 l S Q")
    )
    assert any(item["kind"] == "line" for item in native["segments"])
    assert [item for item in native["authority_segments"] if item["kind"] == "line"] == []


def test_nonrectangular_clip_is_unresolved_and_blocks_authority_geometry() -> None:
    native = vg.extract_native_page(
        _page_with_content("q 0 0 m 80 0 l 40 80 l h W n -10 25 m 100 25 l S Q")
    )
    assert any(item["kind"] == "line" for item in native["segments"])
    assert [item for item in native["authority_segments"] if item["kind"] == "line"] == []
    assert any(
        item["status"] == "unresolved" and item["reason"] == "nonrectangular_clip_shape"
        for item in native["visibility_diagnostics"]
    )


def test_type3_glyph_paths_are_provenance_quarantined_not_spatially_guessed() -> None:
    native = vg.extract_native_page(_type3_page())

    assert native["text_vector_primitives"]
    assert all(item["origin_class"] == "TYPE3_GLYPH_VECTOR" for item in native["text_vector_primitives"])

    authority = native["authority_segments"]
    assert len([item for item in authority if item["kind"] == "line"]) == 1
    assert not any(item["kind"] == "rect_edge" for item in authority)
    assert all(item.get("origin_class") != "TYPE3_GLYPH_VECTOR" for item in authority)


def test_later_opaque_rect_fill_marks_text_occluded_and_removes_it_from_authority_words() -> None:
    native = vg.extract_native_page(_text_and_fill_page(fill_after_text=True))

    assert any(word["text"] == "FIRE" for word in native["words"])
    assert not any(word["text"] == "FIRE" for word in native["authority_words"])
    assert any(
        item["status"] == "PROVEN_OCCLUDED" and item["text"] == "FIRE"
        for item in native["text_visibility_diagnostics"]
    )


def test_fill_before_text_does_not_occlude_later_text() -> None:
    native = vg.extract_native_page(_text_and_fill_page(fill_after_text=False))

    assert any(word["text"] == "FIRE" for word in native["authority_words"])
    assert not any(
        item["status"] == "PROVEN_OCCLUDED" and item["text"] == "FIRE"
        for item in native["text_visibility_diagnostics"]
    )


def test_nonuniform_form_transform_is_diagnostic_not_global_sheet_quarantine() -> None:
    native = vg.extract_native_page(_single_form_page("2 0 0 3 10 20"))
    diagnostics = native["form_transform_diagnostics"]

    assert any(
        item["transform_class"] == "NON_SIMILARITY_AFFINE" and item["scope"] == "FORM_XOBJECT"
        for item in diagnostics
    )
    # Local source geometry remains observable; this is evidence about a Form
    # transform, not proof that the whole architectural sheet was distorted.
    assert native["segments"]


def test_uniform_rotated_form_transform_is_similarity_not_distortion() -> None:
    native = vg.extract_native_page(_single_form_page("0 2 -2 0 10 20"))
    diagnostics = native["form_transform_diagnostics"]
    assert diagnostics
    assert all(item["transform_class"] != "NON_SIMILARITY_AFFINE" for item in diagnostics)
