"""Conservative source-inset and dimension-caption audit negatives."""
import hashlib
import math
from types import SimpleNamespace

import fitz
import pytest

from tools import diag_gpt2_original_mixed_amenities_insets as diag


def build_page(*lines):
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=400)
    for i, line in enumerate(lines):
        page.insert_text((40, 40 + 22 * i), line, fontsize=10)
    return pdf, page


def test_same_source_page_plan_and_elevation_title_lines_preserved():
    pdf, page = build_page("INTERNAL ELEVATIONS - AMENITIES", "PROP. PWD PLAN",
                           "PWD - ELEVATION 1", "3570", "2200")
    try:
        lines = diag._original_native_lines(page, 1)
        combined = " ".join(x["native_raw_line_text"] for x in lines)
        assert "PWD PLAN" in combined
        assert "ELEVATION 1" in combined
        assert "3570" in combined and "2200" in combined
        assert all(not x["source_line_proves_room_or_viewport"] for x in lines)
        assert all(not x["semantic_dimension_target_authenticated"] for x in lines)
    finally:
        pdf.close()


@pytest.mark.parametrize("bad", [
    None, (), (0, 1, 0, 2), (5, 10, 4, 11),
    (float("nan"), 1, 3, 4), (float("inf"), 1, 3, 4),
    ("x", 0, 4, 10), "0 0 10 10",
])
def test_no_unbounded_or_invalid_native_bbox_recycled(bad):
    assert diag._finite_rect(bad) is None


def test_native_lines_order_independent_of_extractor_word_order():
    pdf, page = build_page("PROP. PWD PLAN", "3570")
    try:
        original = page.get_text("words")
        wrapped = SimpleNamespace(get_text=lambda kind: list(reversed(original)))
        a = diag._original_native_lines(page, 4)
        b = diag._original_native_lines(wrapped, 4)
        assert a == b
    finally:
        pdf.close()


def test_missing_revision_or_pdf_sha_fails_before_page_selection():
    with pytest.raises(ValueError, match="original-source-sha-mismatch"):
        diag.audit(b"wrong original source", expected_sha256="0" * 64)


def test_out_of_range_and_duplicate_source_page_refuses():
    pdf, page = build_page("PROP. PWD PLAN", "3570")
    data = pdf.tobytes()
    pdf.close()
    sha = hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="duplicate-source-page-address"):
        diag.audit(data, expected_sha256=sha, source_pages=(1, 1))
    with pytest.raises(ValueError, match="source-page-out-of-range"):
        diag.audit(data, expected_sha256=sha, source_pages=(1, 2))


def test_local_caption_only_is_not_producer_room_or_sized_floor(monkeypatch):
    pdf, page = build_page("PROP. PWD PLAN", "3570", "2200")
    try:
        monkeypatch.setattr(diag, "extract_view_title_anchors", lambda p: [
            SimpleNamespace(text="PROP. PWD PLAN", bbox=(20.,20.,200.,50.),
                            direction=(1.,0.), view_type="floor_plan")
        ])
        monkeypatch.setattr(diag, "segment_page_viewports", lambda p, page_number: [
            SimpleNamespace(view_id="view_p1_1", label="PROP. PWD PLAN",
                            view_type="floor_plan", status="unsupported",
                            boundary_source="none", bounding_box=None)
        ])
        monkeypatch.setattr(diag, "is_authoritative_derived_viewport", lambda p: False)
        monkeypatch.setattr(diag, "validate_non_overlapping_viewports", lambda x: True)
        ledger = diag._all_local_view_evidence(page, 1)
        assert ledger["new_viewport_authentications"] == 0
        assert ledger["original_native_view_title_anchors"][0]["title_alone_proves_viewport"] is False
        assert ledger["existing_f07_viewports"][0]["native_viewport_bbox_pdf_pts"] is None
        assert ledger["existing_f07_viewports"][0]["original_local_view_role_granted_by_this_report"] is False
    finally:
        pdf.close()


def test_caption_does_not_own_cross_page_room_geometry():
    pdf, page = build_page("PWD PLAN", "3570 2200", "PWD - ELEVATION 1")
    try:
        lines = diag._original_native_lines(page, 26)
        assert lines
        assert all(not x["source_line_proves_room_or_viewport"] for x in lines)
        assert all(not x["semantic_dimension_target_authenticated"] for x in lines)
    finally:
        pdf.close()
