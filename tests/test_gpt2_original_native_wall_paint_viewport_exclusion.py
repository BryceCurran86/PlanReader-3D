"""Independent original OFFICE wall paint confirms a real viewport exclusion."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_painted_wall_viewport_exclusion_shadow import (
    audit_original_painted_stroke_view_membership as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
VIEW = (251.51998901367188, 471.200073, 1195.439941, 1946.479980)


def _single_stroke(x):
    doc = fitz.open()
    page = doc.new_page(width=200, height=120)
    page.draw_line((x, 20), (x, 90), color=(0, 0, 0), width=0.48)
    raw = doc.tobytes()
    doc.close()
    return raw


def _result(data, **overrides):
    kwargs = {
        "expected_sha256": hashlib.sha256(data).hexdigest(),
        "page_1_based": 1,
        "source_native_path_item_id": "d0i0",
        "supplied_source_viewport_bbox_pdf_pts": (40, 10, 100, 100),
        "supplied_source_viewport_id": "independently-authenticated-source-view",
    }
    kwargs.update(overrides)
    return audit(data, **kwargs)


@pytest.mark.parametrize("x,status", [
    (50., "original_painted_stroke_inside_viewport"),
    (39., "original_painted_stroke_excluded_from_viewport"),
    (40., "original_painted_stroke_straddles_viewport"),
])
def test_painted_native_stroke_respects_original_viewport_without_expansion(x, status):
    result = _result(_single_stroke(x))
    assert result["status"] == status
    assert result["source_original_viewport_ownership_granted"] is False
    assert result["source_physical_structural_wall_role_granted"] is False
    assert result["new_firm_quantities"] == 0


def test_paint_half_width_outside_gap_is_not_a_source_wall_claim():
    result = _result(_single_stroke(39.))
    assert result["minimum_source_paint_to_viewport_gap_pdf_pts"] == pytest.approx(
        0.76, abs=0.00001
    )


@pytest.mark.parametrize("bad", [
    {"expected_sha256": "0" * 64},
    {"source_native_path_item_id": "d999i0"},
    {"source_native_path_item_id": "d0i99"},
    {"source_native_path_item_id": "d-1i0"},
    {"supplied_source_viewport_bbox_pdf_pts": (40, 10, 40, 100)},
])
def test_corrupt_pdf_scope_or_native_path_cannot_supply_ink_owner(bad):
    with pytest.raises(ValueError):
        _result(_single_stroke(50.), **bad)


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private original drawing not provisioned")
def test_original_office_left_wall_is_actually_outside_owned_p11_plan_view():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    def original(native):
        return audit(
            raw, expected_sha256=SHA, page_1_based=11,
            source_native_path_item_id=native,
            supplied_source_viewport_bbox_pdf_pts=VIEW,
            supplied_source_viewport_id="source_plan_view_c57aa3592e81d66ad2fa5a92",
        )

    excluded = original("d2666i0")
    assert excluded["status"] == "original_painted_stroke_excluded_from_viewport"
    assert excluded["original_native_line_width_pdf_pts"] == pytest.approx(0.48)
    assert excluded["source_line_endpoints_native_pdf_pts"][0][0] == pytest.approx(
        251.0399932861328
    )
    assert excluded["minimum_source_paint_to_viewport_gap_pdf_pts"] == pytest.approx(
        0.23999573, abs=0.00001
    )
    assert original("d3062i0")["status"] == "original_painted_stroke_inside_viewport"
    assert original("d2863i0")["status"] == (
        "original_painted_stroke_straddles_viewport"
    )
    assert excluded["new_firm_quantities"] == 0
