"""Read immutable original PDF native area text as UNBOUND candidates only.

Generated PDFs are synthetic. No confidential PDF, benchmark values or
producer-issued FIRM measurements are bundled with this test.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib

import fitz
import pytest

from pb_explicit_floor_area_evidence import (
    extract_unbound_component_areas_from_original_pdf,
)


def _source(*, with_second_page: bool = True) -> bytes:
    doc = fitz.open()
    try:
        plan = doc.new_page(width=595, height=842)
        plan.insert_text(
            (30, 80),
            "UPPER LIVING AREA:\n42.75m2\nGARAGE AREA: 18.50m2\nTOTAL FLOOR AREA: 61.25m2",
            fontsize=10,
        )
        if with_second_page:
            # Native drawings/image-only pages without area text are not OCRed.
            page = doc.new_page(width=595, height=842)
            page.draw_rect(fitz.Rect(100, 100, 400, 400))
        return doc.tobytes()
    finally:
        doc.close()


def _read(payload: bytes, *, sha: str | None = None):
    return extract_unbound_component_areas_from_original_pdf(
        payload,
        expected_source_sha256=sha or hashlib.sha256(payload).hexdigest(),
        revision_id="independent-revision",
    )


def test_original_pdf_bytes_issue_two_unbound_component_candidates_only():
    payload = _source()
    rows = _read(payload)
    assert {(r.label, r.area_m2) for r in rows} == {
        ("UPPER LIVING", 42.75), ("GARAGE", 18.50),
    }
    assert len(rows) == 2
    assert all(row.binding == "unbound" for row in rows)
    assert all(row.source_sha256 == hashlib.sha256(payload).hexdigest()
               for row in rows)
    assert all(row.source_page == 1 for row in rows)
    assert all(row.source_block_id.startswith("original-pdf-page-1-text-block-")
               for row in rows)
    assert all(len(row.source_text_bbox_pdf_pts or ()) == 4 for row in rows)
    assert all(not hasattr(row, "quantity_id") for row in rows)


def test_original_source_parse_is_deterministic_and_no_original_pdf_mutation():
    payload = _source()
    before = hashlib.sha256(payload).hexdigest()
    first = _read(payload)
    assert _read(payload) == first
    assert hashlib.sha256(payload).hexdigest() == before


def test_raster_without_native_area_words_does_not_hallucinate_extra_rows():
    assert len(_read(_source(with_second_page=False))) == 2
    assert len(_read(_source(with_second_page=True))) == 2


@pytest.mark.parametrize("bad_sha", ["b" * 64, "g" * 64, "none", "", 17])
def test_wrong_untyped_or_missing_pdf_source_sha_fails_closed(bad_sha):
    payload = _source()
    with pytest.raises(ValueError, match="source SHA"):
        extract_unbound_component_areas_from_original_pdf(
            payload, expected_source_sha256=bad_sha,
            revision_id="independent-revision"
        )


@pytest.mark.parametrize("bad_bytes", [b"not a PDF", b"", "not-bytes", bytearray(b"bad")])
def test_non_pdf_or_mutable_bytes_cannot_issue_source_corroboration(bad_bytes):
    import hashlib
    digest = (hashlib.sha256(bad_bytes).hexdigest()
              if isinstance(bad_bytes, (bytes, bytearray)) else "a" * 64)
    with pytest.raises(ValueError):
        extract_unbound_component_areas_from_original_pdf(
            bad_bytes, expected_source_sha256=digest,
            revision_id="independent-revision"
        )


@pytest.mark.parametrize("bad_revision", ["", " padded ", None, True, 29])
def test_original_pdf_requires_canonical_revision_identity(bad_revision):
    payload = _source()
    with pytest.raises(ValueError, match="revision"):
        extract_unbound_component_areas_from_original_pdf(
            payload, expected_source_sha256=hashlib.sha256(payload).hexdigest(),
            revision_id=bad_revision,
        )


def test_source_text_candidate_cannot_be_forged_from_caller_label_or_area():
    payload = _source()
    assert all(row.area_m2 in (42.75, 18.5) for row in _read(payload))
    assert all(row.label not in ("UNKNOWN", "TOTAL FLOOR")
               for row in _read(payload))



def test_pdf_page_with_only_raster_printed_area_word_cannot_be_native_measured():
    from io import BytesIO
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (480, 140), "white")
    painter = ImageDraw.Draw(image)
    painter.text((20, 30), "RASTER COURT AREA: 31.25m2", fill="black")
    buf = BytesIO()
    image.save(buf, format="PNG")
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(20, 20, 500, 160), stream=buf.getvalue())
        payload = doc.tobytes()
    finally:
        doc.close()
    assert _read(payload) == ()  # No OCR or invented native words allowed.


def test_source_native_text_rotation_does_not_change_raw_unbound_area_semantics():
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 150), "UPPER COURT AREA: 13.5m2", fontsize=11)
        payload_before = doc.tobytes()
        page.set_rotation(90)
        payload_rotated = doc.tobytes()
    finally:
        doc.close()
    a = _read(payload_before)
    b = _read(payload_rotated)
    assert len(a) == len(b) == 1
    assert a[0].area_m2 == b[0].area_m2 == 13.5
    assert a[0].source_block_line_index == b[0].source_block_line_index == 0
    assert a[0].binding == b[0].binding == "unbound"


def test_generated_native_text_receipts_preserve_different_line_ordinal():
    rows = _read(_source())
    assert len(rows) == 2
    assert {row.source_block_line_index for row in rows} == {0, 2}
    assert rows[0].source_text_bbox_pdf_pts == rows[1].source_text_bbox_pdf_pts
