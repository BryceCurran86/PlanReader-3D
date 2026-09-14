from __future__ import annotations

import math

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


def _nested_form_page(
    *,
    parent_matrix: str = "2 0 0 2 10 20",
    child_matrix: str = "0 1 -1 0 5 0",
    page_prefix: str = "",
) -> fitz.Page:
    page_stream = f"q {page_prefix} /F1 Do Q".strip()
    child_stream = "0 0 m 10 0 l S"
    parent_stream = "q /F2 Do Q"
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
            f"/Matrix [{parent_matrix}] "
            "/Resources << /XObject << /F2 6 0 R >> >> "
            f"/Length {len(parent_stream)} >>\nstream\n{parent_stream}\nendstream"
        ),
        6: (
            "<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] "
            f"/Matrix [{child_matrix}] /Resources << >> "
            f"/Length {len(child_stream)} >>\nstream\n{child_stream}\nendstream"
        ),
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _single_form_page(matrix: str = "2 0 0 3 10 20") -> fitz.Page:
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


def _cycle_page() -> fitz.Page:
    page_stream = "/A Do"
    a_stream = "/B Do"
    b_stream = "/A Do"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            "/Resources << /XObject << /A 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream)} >>\nstream\n{page_stream}\nendstream",
        5: (
            "<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] "
            "/Resources << /XObject << /B 6 0 R >> >> "
            f"/Length {len(a_stream)} >>\nstream\n{a_stream}\nendstream"
        ),
        6: (
            "<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] "
            "/Resources << /XObject << /A 5 0 R >> >> "
            f"/Length {len(b_stream)} >>\nstream\n{b_stream}\nendstream"
        ),
    }
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _type3_page() -> fitz.Page:
    char_stream = "0 0 500 500 re S"
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


def _line_tuple(native: dict) -> tuple[float, float, float, float]:
    line = next(item for item in native["segments"] if item["kind"] == "line")
    return line["x1"], line["y1"], line["x2"], line["y2"]


def _assert_line_close(
    actual: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
) -> None:
    assert actual == pytest.approx(expected, abs=1e-5)


# ISSUE 1 ---------------------------------------------------------------------


def test_single_form_matrix_is_applied_to_canonical_page_geometry() -> None:
    native = vg.extract_native_page(_single_form_page())
    _assert_line_close(_line_tuple(native), (10.0, 280.0, 30.0, 280.0))


def test_nested_form_matrices_are_applied_in_parent_child_order() -> None:
    native = vg.extract_native_page(_nested_form_page())
    _assert_line_close(_line_tuple(native), (20.0, 280.0, 20.0, 260.0))


def test_page_ctm_plus_nested_forms_matches_equivalent_flattened_geometry() -> None:
    nested = vg.extract_native_page(
        _nested_form_page(page_prefix="1 0 0 1 30 40 cm")
    )
    flattened = vg.extract_native_page(_page_with_content("50 60 m 50 80 l S", media=300))
    _assert_line_close(_line_tuple(nested), _line_tuple(flattened))


def test_transform_order_is_not_commutative() -> None:
    parent_then_child = vg.extract_native_page(_nested_form_page())
    swapped = vg.extract_native_page(
        _nested_form_page(
            parent_matrix="0 1 -1 0 5 0",
            child_matrix="2 0 0 2 10 20",
        )
    )
    assert _line_tuple(parent_then_child) != pytest.approx(_line_tuple(swapped), abs=1e-5)


def test_form_provenance_fingerprint_changes_when_matrix_changes() -> None:
    a = vg.extract_native_page(_single_form_page("2 0 0 3 10 20"))
    b = vg.extract_native_page(_single_form_page("2 0 0 3 11 20"))
    assert a["form_provenance_fingerprint"]
    assert b["form_provenance_fingerprint"]
    assert a["form_provenance_fingerprint"] != b["form_provenance_fingerprint"]


# ISSUE 2 ---------------------------------------------------------------------


def test_form_xobject_cycle_fails_closed_with_deterministic_diagnostics() -> None:
    with pytest.raises(vg.NativeGeometryIntegrityError) as caught:
        vg.extract_native_page(_cycle_page())
    diagnostics = caught.value.diagnostics
    assert diagnostics["status"] == "unresolved"
    assert diagnostics["reason"] == "form_xobject_cycle"
    assert diagnostics["cycle_xrefs"][0] == diagnostics["cycle_xrefs"][-1]
    assert len(diagnostics["cycle_xrefs"]) >= 3


# ISSUE 3 ---------------------------------------------------------------------


def _visible_lines(native: dict) -> list[dict]:
    return [item for item in native["visible_segments"] if item["kind"] == "line"]


def test_clip_line_fully_inside_preserves_raw_and_visible_geometry() -> None:
    page = _page_with_content("q 0 0 80 80 re W n 10 20 m 40 20 l S Q")
    native = vg.extract_native_page(page)
    assert _line_tuple(native) == pytest.approx((10.0, 80.0, 40.0, 80.0))
    visible = _visible_lines(native)
    assert len(visible) == 1
    _assert_line_close(
        (visible[0]["x1"], visible[0]["y1"], visible[0]["x2"], visible[0]["y2"]),
        (10.0, 80.0, 40.0, 80.0),
    )
    assert visible[0]["clip_ids"]


def test_clip_line_partially_visible_is_clipped_only_in_visible_representation() -> None:
    page = _page_with_content("q 0 0 50 50 re W n -10 25 m 100 25 l S Q")
    native = vg.extract_native_page(page)
    raw = _line_tuple(native)
    _assert_line_close(raw, (-10.0, 75.0, 100.0, 75.0))
    visible = _visible_lines(native)
    assert len(visible) == 1
    clipped = visible[0]
    _assert_line_close(
        (clipped["x1"], clipped["y1"], clipped["x2"], clipped["y2"]),
        (0.0, 75.0, 50.0, 75.0),
    )
    _assert_line_close(_line_tuple(native), raw)


def test_clip_line_fully_outside_is_retained_raw_but_not_visible() -> None:
    page = _page_with_content("q 0 0 50 50 re W n -10 75 m 100 75 l S Q")
    native = vg.extract_native_page(page)
    _assert_line_close(_line_tuple(native), (-10.0, 25.0, 100.0, 25.0))
    assert _visible_lines(native) == []
    assert native["clip_provenance"]


def test_nested_rectangular_clips_intersect_visibility() -> None:
    page = _page_with_content(
        "q 0 0 80 80 re W n q 20 20 40 40 re W n "
        "-10 30 m 100 30 l S Q Q"
    )
    native = vg.extract_native_page(page)
    visible = _visible_lines(native)
    assert len(visible) == 1
    _assert_line_close(
        (visible[0]["x1"], visible[0]["y1"], visible[0]["x2"], visible[0]["y2"]),
        (20.0, 70.0, 60.0, 70.0),
    )
    assert len(visible[0]["clip_ids"]) == 2


def test_clip_graphics_state_restore_does_not_leak_to_later_line() -> None:
    page = _page_with_content(
        "q 0 0 50 50 re W n -10 25 m 100 25 l S Q "
        "-10 75 m 100 75 l S"
    )
    native = vg.extract_native_page(page)
    visible = _visible_lines(native)
    assert len(visible) == 2
    clipped = next(item for item in visible if item["clip_ids"])
    unclipped = next(item for item in visible if not item["clip_ids"])
    _assert_line_close(
        (clipped["x1"], clipped["y1"], clipped["x2"], clipped["y2"]),
        (0.0, 75.0, 50.0, 75.0),
    )
    _assert_line_close(
        (unclipped["x1"], unclipped["y1"], unclipped["x2"], unclipped["y2"]),
        (-10.0, 25.0, 100.0, 25.0),
    )


# ISSUE 4 ---------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "verified current hazard: PyMuPDF exposes Type-3 glyph strokes through "
        "get_drawings(); safe glyph-origin attribution is deferred rather than "
        "using a spatial heuristic that could delete architectural geometry"
    ),
)
def test_type3_glyph_vectors_do_not_enter_architectural_segment_pool() -> None:
    native = vg.extract_native_page(_type3_page())
    lines = [item for item in native["segments"] if item["kind"] in {"line", "rect_edge"}]
    assert len(lines) == 1
    assert native["text_vector_primitives"]


# ISSUE 5 ---------------------------------------------------------------------


def test_zero_length_and_near_zero_sources_remain_auditable_without_nan() -> None:
    page = _page_with_content(
        "10 10 m 10 10 l S "
        "20 20 m 20.1 20 l S "
        "30 30 m 40 30 l S"
    )
    native = vg.extract_native_page(page)
    source = native["source_primitives"]
    assert len(source) == 3

    zero, short, valid = source
    assert zero["geometry_status"] == "DEGENERATE"
    assert zero["length_pt"] == 0.0
    assert zero["active_geometry"] is False

    assert short["geometry_status"] == "GEOMETRIC"
    assert short["length_pt"] > 0.0
    assert short["active_geometry"] is False
    assert short["inactive_reason"] == "legacy_subpoint_filter"

    assert valid["geometry_status"] == "GEOMETRIC"
    assert valid["active_geometry"] is True
    assert all(math.isfinite(float(item[key])) for item in source for key in ("x1", "y1", "x2", "y2"))


def test_exact_zero_length_does_not_enter_active_segments_or_snap_graph() -> None:
    page = _page_with_content("10 10 m 10 10 l S 20 20 m 40 20 l S")
    native = vg.extract_native_page(page)
    assert len(native["segments"]) == 1
    graph = vg.snap_geometry(native["segments"])
    assert len(graph["edges"]) == 1
    assert all(edge["a"] != edge["b"] for edge in graph["edges"])


def test_repeated_identical_rectangle_points_are_audited_as_degenerate_edges() -> None:
    page = _page_with_content("20 20 0 10 re S")
    native = vg.extract_native_page(page)
    rect_edges = [item for item in native["source_primitives"] if item["kind"] == "rect_edge"]
    assert len(rect_edges) == 4
    assert sum(item["geometry_status"] == "DEGENERATE" for item in rect_edges) == 2


def test_transformed_zero_length_primitive_remains_degenerate() -> None:
    page = _page_with_content("q 2 0 0 3 10 20 cm 5 5 m 5 5 l S Q")
    native = vg.extract_native_page(page)
    assert len(native["source_primitives"]) == 1
    source = native["source_primitives"][0]
    assert source["geometry_status"] == "DEGENERATE"
    assert source["length_pt"] == 0.0
    assert source["active_geometry"] is False


def test_degenerate_member_does_not_pollute_valid_geometry() -> None:
    page = _page_with_content(
        "10 10 m 10 10 l S "
        "10 20 m 80 20 l S "
        "10 30 m 80 30 l S"
    )
    native = vg.extract_native_page(page)
    assert len(native["source_primitives"]) == 3
    assert len(native["segments"]) == 2
    pairs = vg.detect_wall_pairs(native["segments"])
    assert isinstance(pairs, list)
    assert all(math.isfinite(float(pair["gap_pt"])) for pair in pairs)
