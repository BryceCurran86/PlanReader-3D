"""Native PDF text render-authority red-team (test-first only).

Exact base: post-#331 main 507c57db16be515e2432c695341bdea1e71b3fd7.

The GREEN tests pin deterministic PyMuPDF 1.28.0 source/render facts. The
EXPECTED-RED tests define a future producer-owned text-render evidence layer.
No opening dimension or commercial authority is implemented here.
"""
from __future__ import annotations

import importlib.util
from typing import Iterable

import fitz
import pytest


BASE_SHA = "507c57db16be515e2432c695341bdea1e71b3fd7"

EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="Native producer-owned text render authority is not implemented",
)


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


def _page_with_content(
    content: str,
    *,
    extra_resources: str = "",
    extra_objects: dict[int, str] | None = None,
) -> fitz.Page:
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            f"/Resources << /Font << /F1 5 0 R >> {extra_resources} >> "
            "/Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(content.encode('latin1'))} >>\nstream\n{content}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    objects.update(extra_objects or {})
    document = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return document[0]


def _visible_black_page() -> fitz.Page:
    return _page_with_content("0 0 0 rg BT /F1 10 Tf 10 50 Td (900) Tj ET")


def _white_text_page() -> fitz.Page:
    return _page_with_content("1 1 1 rg BT /F1 10 Tf 10 50 Td (900) Tj ET")


def _ignored_text_page() -> fitz.Page:
    # PDF text rendering mode 3 = neither fill nor stroke.
    return _page_with_content("BT /F1 10 Tf 3 Tr 10 50 Td (900) Tj ET")


def _zero_opacity_text_page() -> fitz.Page:
    content = "/GS0 gs BT /F1 10 Tf 10 50 Td (900) Tj ET"
    return _page_with_content(
        content,
        extra_resources="/ExtGState << /GS0 6 0 R >>",
        extra_objects={6: "<< /Type /ExtGState /ca 0 /CA 0 >>"},
    )


def _text_and_opaque_fill_page(*, fill_after_text: bool, partial: bool = False) -> fitz.Page:
    text = "0 0 0 rg BT /F1 10 Tf 10 50 Td (900) Tj ET"
    # Text bbox sits around x=10..27 and page-space y around 42..52. PDF
    # coordinates are bottom-origin, so this rectangle fully covers that area.
    if partial:
        fill = "0 0 0 rg 10 45 8 12 re f"
    else:
        fill = "0 0 0 rg 5 40 40 20 re f"
    content = f"{text} {fill}" if fill_after_text else f"{fill} {text}"
    return _page_with_content(content)


def _words(page: fitz.Page) -> list[tuple]:
    return list(page.get_text("words") or [])


def _word_texts(page: fitz.Page) -> tuple[str, ...]:
    return tuple(str(word[4]) for word in _words(page) if len(word) >= 5)


def _text_trace_for_900(page: fitz.Page) -> dict:
    traces = list(page.get_texttrace() or [])
    for trace in traces:
        chars = trace.get("chars") or ()
        text = "".join(chr(int(char[0])) for char in chars if char)
        if "900" in text:
            return trace
    raise AssertionError("expected 900 in get_texttrace()")


def _bboxlog(page: fitz.Page) -> list[tuple]:
    return list(page.get_bboxlog() or [])


def _bboxlog_entry_for_seq(page: fitz.Page, seqno: int) -> tuple:
    logs = _bboxlog(page)
    assert 0 <= seqno < len(logs)
    return logs[seqno]


def _rect(value) -> fitz.Rect:
    return fitz.Rect(*map(float, value))


def _fully_contains(outer, inner) -> bool:
    a = _rect(outer)
    b = _rect(inner)
    return a.x0 <= b.x0 and a.y0 <= b.y0 and a.x1 >= b.x1 and a.y1 >= b.y1


def _future_records(page: fitz.Page) -> Iterable[object]:
    if importlib.util.find_spec("pb_native_text_render_authority") is None:
        raise AssertionError("pb_native_text_render_authority is absent")
    import pb_native_text_render_authority as mod  # type: ignore

    return mod.extract_native_text_render_evidence(page)


def _future_900_record(page: fitz.Page):
    records = list(_future_records(page))
    for record in records:
        text = str(getattr(record, "raw_text", getattr(record, "text", "")))
        if text.strip() == "900":
            return record
    raise AssertionError(f"future render authority did not publish 900: {records!r}")


def _state(record: object) -> str:
    value = getattr(record, "render_state", getattr(record, "status", ""))
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# Current-main deterministic PyMuPDF seam — GREEN
# ---------------------------------------------------------------------------


def test_exact_base_and_pinned_low_level_apis_exist() -> None:
    assert BASE_SHA == "507c57db16be515e2432c695341bdea1e71b3fd7"
    page = _visible_black_page()
    assert callable(getattr(page, "get_texttrace", None))
    assert callable(getattr(page, "get_bboxlog", None))


def test_visible_black_text_has_normal_paint_trace_and_matching_seqno() -> None:
    page = _visible_black_page()
    assert "900" in _word_texts(page)
    trace = _text_trace_for_900(page)
    assert float(trace["opacity"]) > 0.0
    assert int(trace["type"]) <= 1
    seqno = int(trace["seqno"])
    entry = _bboxlog_entry_for_seq(page, seqno)
    assert entry[0] in {"fill-text", "stroke-text"}


def test_render_mode_3_text_is_extractable_but_bboxlog_marks_ignore_text() -> None:
    page = _ignored_text_page()
    assert "900" in _word_texts(page)
    trace = _text_trace_for_900(page)
    entry = _bboxlog_entry_for_seq(page, int(trace["seqno"]))
    assert entry[0] == "ignore-text"
    assert int(trace["type"]) > 1


def test_zero_opacity_text_is_extractable_but_trace_opacity_is_zero() -> None:
    page = _zero_opacity_text_page()
    assert "900" in _word_texts(page)
    trace = _text_trace_for_900(page)
    assert float(trace["opacity"]) == pytest.approx(0.0)


def test_later_full_opaque_fill_has_higher_sequence_and_covers_text_bbox() -> None:
    page = _text_and_opaque_fill_page(fill_after_text=True)
    trace = _text_trace_for_900(page)
    text_seq = int(trace["seqno"])
    text_bbox = trace["bbox"]
    logs = _bboxlog(page)

    later_cover = [
        (index, entry)
        for index, entry in enumerate(logs)
        if index > text_seq
        and entry[0] == "fill-path"
        and _fully_contains(entry[1], text_bbox)
    ]
    assert later_cover, (text_seq, text_bbox, logs)


def test_opaque_fill_before_text_has_lower_sequence_not_later_occlusion() -> None:
    page = _text_and_opaque_fill_page(fill_after_text=False)
    trace = _text_trace_for_900(page)
    text_seq = int(trace["seqno"])
    text_bbox = trace["bbox"]
    logs = _bboxlog(page)

    containing_fills = [
        index
        for index, entry in enumerate(logs)
        if entry[0] == "fill-path" and _fully_contains(entry[1], text_bbox)
    ]
    assert containing_fills
    assert all(index < text_seq for index in containing_fills)


def test_partial_later_fill_is_not_full_cover_proof() -> None:
    page = _text_and_opaque_fill_page(fill_after_text=True, partial=True)
    trace = _text_trace_for_900(page)
    text_seq = int(trace["seqno"])
    text_bbox = trace["bbox"]
    logs = _bboxlog(page)
    later_full = [
        index
        for index, entry in enumerate(logs)
        if index > text_seq
        and entry[0] == "fill-path"
        and _fully_contains(entry[1], text_bbox)
    ]
    assert later_full == []


def test_white_text_is_real_paint_but_trace_does_not_prove_contrast() -> None:
    page = _white_text_page()
    assert "900" in _word_texts(page)
    trace = _text_trace_for_900(page)
    assert float(trace["opacity"]) == pytest.approx(1.0)
    assert int(trace["type"]) <= 1
    color = tuple(float(v) for v in trace["color"])
    assert color == pytest.approx((1.0, 1.0, 1.0))
    entry = _bboxlog_entry_for_seq(page, int(trace["seqno"]))
    assert entry[0] in {"fill-text", "stroke-text"}
    # These facts prove a paint operation, not readable contrast against the
    # final background. Future authority must keep this separate.


# ---------------------------------------------------------------------------
# Future producer-owned render evidence — EXPECTED RED
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_visible_black_text_may_be_render_eligible() -> None:
    record = _future_900_record(_visible_black_page())
    assert _state(record) == "PROVEN_RENDERED"
    assert bool(getattr(record, "render_eligible", True)) is True


@EXPECTED_RED
def test_attack02_ignore_text_is_proven_non_rendering() -> None:
    record = _future_900_record(_ignored_text_page())
    assert _state(record) == "PROVEN_NON_RENDERING"
    assert bool(getattr(record, "render_eligible", False)) is False


@EXPECTED_RED
def test_attack03_zero_opacity_text_is_proven_non_rendering() -> None:
    record = _future_900_record(_zero_opacity_text_page())
    assert _state(record) == "PROVEN_NON_RENDERING"
    assert bool(getattr(record, "render_eligible", False)) is False


@EXPECTED_RED
def test_attack04_later_full_opaque_cover_is_proven_occluded() -> None:
    record = _future_900_record(_text_and_opaque_fill_page(fill_after_text=True))
    assert _state(record) == "PROVEN_OCCLUDED"
    assert bool(getattr(record, "render_eligible", False)) is False


@EXPECTED_RED
def test_attack05_fill_before_text_does_not_occlude_later_text() -> None:
    record = _future_900_record(_text_and_opaque_fill_page(fill_after_text=False))
    assert _state(record) == "PROVEN_RENDERED"
    assert bool(getattr(record, "render_eligible", True)) is True


@EXPECTED_RED
def test_attack06_partial_cover_does_not_become_proven_full_occlusion() -> None:
    record = _future_900_record(
        _text_and_opaque_fill_page(fill_after_text=True, partial=True)
    )
    assert _state(record) in {
        "UNRESOLVED_PARTIAL_OCCLUSION",
        "UNRESOLVED_OCCLUSION",
    }
    assert bool(getattr(record, "render_eligible", False)) is False


@EXPECTED_RED
def test_attack07_white_on_blank_background_is_not_positive_measurement_render_evidence() -> None:
    record = _future_900_record(_white_text_page())
    assert _state(record) in {
        "UNRESOLVED_CONTRAST",
        "PROVEN_LOW_CONTRAST",
    }
    assert bool(getattr(record, "render_eligible", False)) is False


@EXPECTED_RED
def test_attack08_render_record_does_not_claim_decode_or_dimension_authority() -> None:
    record = _future_900_record(_visible_black_page())
    forbidden_positive_fields = (
        "decode_eligible",
        "dimension_authoritative",
        "opening_width_mm",
        "opening_height_mm",
        "firm_quantity",
        "publishable",
    )
    for name in forbidden_positive_fields:
        value = getattr(record, name, None)
        assert value in (None, False)
