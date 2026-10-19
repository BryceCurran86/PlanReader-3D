"""Source-first OFFICE wall ink: retain competing inside/boundary/outside strokes."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_parallel_wall_ink_rivals_shadow import (
    audit_original_parallel_wall_ink_rivals as audit,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
VIEW11 = (251.51998901367188, 471.200073, 1195.439941, 1946.479980)


def _drawing():
    pdf = fitz.open()
    p = pdf.new_page(width=200, height=200)
    p.draw_line((40, 20), (40, 100), color=(0, 0, 0), width=0.48)
    p.draw_line((40.48, 20), (40.48, 100), color=(0, 0, 0), width=0.48)
    p.draw_line((40.48, 20), (40.48, 100), color=(0, 0, 0), width=0.48)
    p.draw_line((44, 20), (44, 100), color=(0, 0, 0), width=0.48)
    raw = pdf.tobytes()
    pdf.close()
    return raw


def _run(raw, **kwargs):
    return audit(
        raw,
        expected_sha256=kwargs.pop("expected_sha256", hashlib.sha256(raw).hexdigest()),
        page_1_based=kwargs.pop("page_1_based", 1),
        reference_native_path_item_id=kwargs.pop(
            "reference_native_path_item_id", "d0i0"
        ),
        independently_supplied_viewport_pdf_pts=kwargs.pop(
            "independently_supplied_viewport_pdf_pts",
            (40.48, 10., 90., 150.)
        ),
        maximum_parallel_offset_pdf_pts=kwargs.pop(
            "maximum_parallel_offset_pdf_pts", 1.
        ),
        **kwargs,
    )


def test_source_parallel_census_preserves_two_equal_ink_tracks_not_closest():
    out = _run(_drawing())
    rivals = out["original_ink_rivals"]
    assert len(rivals) == 3
    assert {r["original_native_path_item_id"] for r in rivals} == {
        "d0i0", "d1i0", "d2i0"
    }
    assert len([r for r in rivals
                if r["signed_parallel_offset_from_reference_pdf_pts"] > 0]) == 2
    assert len([r for r in rivals
                if r["original_painted_viewport_relation"] == "straddles"]) == 2
    assert all(r["source_physical_wall_role_granted"] is False for r in rivals)
    assert out["new_firm_quantities"] == 0


@pytest.mark.parametrize("changes", [
    {"expected_sha256":"0"*64},
    {"reference_native_path_item_id":"d-1i0"},
    {"reference_native_path_item_id":"d999i0"},
    {"maximum_parallel_offset_pdf_pts":float("inf")},
    {"maximum_parallel_offset_pdf_pts":0},
    {"maximum_native_paths":1},
    {"maximum_rivals":1},
])
def test_foreign_or_unbounded_wall_source_cannot_produce_rival_census(changes):
    with pytest.raises(ValueError):
        _run(_drawing(), **changes)


@pytest.mark.skipif(not SOURCE.exists(), reason="private source PDF missing")
def test_original_office_page11_has_real_ink_siblings_at_viewport_boundary():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    out = audit(
        raw, expected_sha256=SHA, page_1_based=11,
        reference_native_path_item_id="d2666i0",
        independently_supplied_viewport_pdf_pts=VIEW11,
        maximum_parallel_offset_pdf_pts=0.6,
    )
    indexed = {r["original_native_path_item_id"]:r for r in out["original_ink_rivals"]}
    assert indexed["d2666i0"]["original_painted_viewport_relation"] == "excluded"
    assert indexed["d2657i0"]["original_painted_viewport_relation"] == "straddles"
    assert indexed["d3567i0"]["original_painted_viewport_relation"] == "straddles"
    assert indexed["d2657i0"]["signed_parallel_offset_from_reference_pdf_pts"] == pytest.approx(
        0.480, abs=0.0001
    )
    assert indexed["d3567i0"]["original_fixed_coordinate_pdf_pts"] == pytest.approx(
        251.519989, abs=0.0001
    )
    assert out["original_wall_or_finished_face_owner_elected"] is False
    assert out["new_firm_quantities"] == 0


@pytest.mark.skipif(not SOURCE.exists(), reason="private source PDF missing")
def test_original_page7_has_corresponding_native_wall_ink_tracks_not_wall_proof():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    out = audit(
        raw, expected_sha256=SHA, page_1_based=7,
        reference_native_path_item_id="d52248i0",
        independently_supplied_viewport_pdf_pts=(173.52, 471.2, 1117., 1600.),
        maximum_parallel_offset_pdf_pts=0.6,
    )
    ids = {r["original_native_path_item_id"] for r in out["original_ink_rivals"]}
    assert "d52239i0" in ids
    assert "d52248i0" in ids
    assert out["new_firm_quantities"] == 0
