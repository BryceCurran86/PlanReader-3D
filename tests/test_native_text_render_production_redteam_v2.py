"""Executable render-only red-team successor for native PDF text evidence.

Validator base: 4b7b7412eecb7c7d434ac0732184314f97c85678.
The same blob is intended for unchanged replay on the production candidate.
"""
from __future__ import annotations

import importlib.util

import fitz
import pytest


BASE_SHA = "4b7b7412eecb7c7d434ac0732184314f97c85678"
HAS_RENDER_AUTHORITY = importlib.util.find_spec("pb_native_text_render_authority") is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_RENDER_AUTHORITY,
    strict=True,
    reason="native text render evidence module absent on validator base",
)


def _pdf_bytes(objects: dict[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    pos = len(header)
    for number in sorted(objects):
        offsets[number] = pos
        body = objects[number].encode("latin1")
        chunk = f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
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
    return b"".join(chunks) + "".join(xref).encode() + trailer.encode()


def _page(content: str, *, resources: str = "", extra: dict[int, str] | None = None):
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            f"/Resources << /Font << /F1 5 0 R >> {resources} >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(content.encode('latin1'))} >>\nstream\n{content}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    objects.update(extra or {})
    doc = fitz.open(stream=_pdf_bytes(objects), filetype="pdf")
    return doc[0]


def _visible_black():
    return _page("0 0 0 rg BT /F1 10 Tf 10 50 Td (900) Tj ET")


def _white():
    return _page("1 1 1 rg BT /F1 10 Tf 10 50 Td (900) Tj ET")


def _ignored():
    return _page("BT /F1 10 Tf 3 Tr 10 50 Td (900) Tj ET")


def _zero_opacity():
    return _page(
        "/GS0 gs BT /F1 10 Tf 10 50 Td (900) Tj ET",
        resources="/ExtGState << /GS0 6 0 R >>",
        extra={6: "<< /Type /ExtGState /ca 0 /CA 0 >>"},
    )


def _covered(*, fill_after: bool, partial: bool = False):
    text = "0 0 0 rg BT /F1 10 Tf 10 50 Td (900) Tj ET"
    fill = "0 0 0 rg 10 45 8 12 re f" if partial else "0 0 0 rg 5 40 40 20 re f"
    return _page(f"{text} {fill}" if fill_after else f"{fill} {text}")


def _record(page):
    assert HAS_RENDER_AUTHORITY
    import pb_native_text_render_authority as module

    records = list(module.extract_native_text_render_evidence(page))
    matching = [record for record in records if record.raw_text.strip() == "900"]
    assert len(matching) == 1, records
    return matching[0]


@EXPECTED_RED
def test_attack01_black_native_text_is_render_eligible_only() -> None:
    assert BASE_SHA == "4b7b7412eecb7c7d434ac0732184314f97c85678"
    record = _record(_visible_black())
    assert record.render_state == "PROVEN_RENDERED"
    assert record.render_eligible is True


@EXPECTED_RED
def test_attack02_render_mode_three_is_proven_non_rendering() -> None:
    record = _record(_ignored())
    assert record.render_state == "PROVEN_NON_RENDERING"
    assert record.render_eligible is False


@EXPECTED_RED
def test_attack03_zero_opacity_is_proven_non_rendering() -> None:
    record = _record(_zero_opacity())
    assert record.render_state == "PROVEN_NON_RENDERING"
    assert record.render_eligible is False


@EXPECTED_RED
def test_attack04_later_full_cover_is_proven_occluded() -> None:
    record = _record(_covered(fill_after=True))
    assert record.render_state == "PROVEN_OCCLUDED"
    assert record.render_eligible is False


@EXPECTED_RED
def test_attack05_fill_before_text_does_not_occlude_later_text() -> None:
    record = _record(_covered(fill_after=False))
    assert record.render_state == "PROVEN_RENDERED"
    assert record.render_eligible is True


@EXPECTED_RED
def test_attack06_partial_cover_stays_unresolved_not_render_eligible() -> None:
    record = _record(_covered(fill_after=True, partial=True))
    assert record.render_state == "UNRESOLVED_PARTIAL_OCCLUSION"
    assert record.render_eligible is False


@EXPECTED_RED
def test_attack07_white_on_default_blank_page_is_not_positive_render_evidence() -> None:
    record = _record(_white())
    assert record.render_state == "UNRESOLVED_CONTRAST"
    assert record.render_eligible is False


@EXPECTED_RED
def test_attack08_render_evidence_does_not_claim_decode_or_dimension_authority() -> None:
    record = _record(_visible_black())
    for name in (
        "decode_eligible",
        "dimension_authoritative",
        "opening_width_mm",
        "opening_height_mm",
        "firm_quantity",
        "publishable",
    ):
        assert getattr(record, name, None) in (None, False)
