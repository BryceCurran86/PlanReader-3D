"""Fail-closed original exterior soffit source words: no area by inference."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_exterior_overhead_soffit_source_census_shadow import (
    audit_exterior_overhead_source_census_shadow as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic(*, include_material=True, include_total=True):
    doc = fitz.open()
    page = doc.new_page()
    if include_material:
        page.insert_text((80, 140), "STP")
        page.insert_text((80, 185), "STP STRAMIT PREMIER 300 SOFFIT CLADDING")
    page.insert_text((80, 245), "1000 2000 3000")
    if include_total:
        page.insert_text((80, 270), "6000")
    data = doc.tobytes()
    doc.close()
    return data


def test_synthetic_original_text_arithmetic_is_not_metric_or_material_authority():
    raw = _synthetic()
    result = audit(
        raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
        page_number=1, material_code="STP",
    )
    assert result["status"] == "original_exterior_overhead_source_candidates_only"
    assert len(result["all_original_code_word_candidates"]) == 2
    assert len(result["original_soffit_material_description_candidates"]) == 1
    candidates = [c for c in result["all_competing_figured_arithmetic_chains"]
                  if c["arithmetic_total_untrusted"] == 6000]
    assert len(candidates) == 1
    assert candidates[0]["component_printed_values_untrusted"] == (1000, 2000, 3000)
    assert candidates[0]["source_extension_lines_proven"] is False
    assert candidates[0]["source_ink_line_correspondence_candidates"] == ()
    assert result["source_canopy_union_overlap_proven"] is False
    assert result["source_fascia_or_gutter_quantity_proven"] is False
    assert result["source_contractor_scope_proven"] is False
    assert result["exterior_soffit_area_m2"] is None
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("bad", [
    {"include_material": False, "include_total": True},
    {"include_material": True, "include_total": False},
])
def test_missing_material_or_figured_total_cannot_publish_soffit(bad):
    raw = _synthetic(**bad)
    result = audit(
        raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
        page_number=1, material_code="STP",
    )
    assert result["new_firm_quantities"] == 0
    assert result["exterior_soffit_area_m2"] is None
    if not bad["include_material"]:
        assert result["status"] == "source_material_mark_unavailable"
    else:
        assert result["all_competing_figured_arithmetic_chains"] == ()


def test_changed_sha_wrong_page_and_untrusted_code_never_claim_authority():
    raw = _synthetic()
    sha = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="immutable_original_pdf_source_sha"):
        audit(raw + b"changed", expected_sha256=sha,
              page_number=1, material_code="STP")
    with pytest.raises(ValueError, match="positive_original_page_number"):
        audit(raw, expected_sha256=sha, page_number=0, material_code="STP")
    with pytest.raises(ValueError, match="original_source_page_out_of_range"):
        audit(raw, expected_sha256=sha, page_number=2, material_code="STP")
    with pytest.raises(ValueError, match="literal_original_material_code"):
        audit(raw, expected_sha256=sha, page_number=1, material_code="stp")


def test_source_legend_code_in_compound_block_does_not_infer_roof_trade():
    raw = _synthetic()
    result = audit(raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
                   page_number=1, material_code="IPF1")
    assert result["status"] == "source_material_mark_unavailable"
    assert result["original_soffit_material_description_candidates"] == ()
    assert result["exterior_soffit_area_m2"] is None


@pytest.mark.skipif(
    not ORIGINAL.is_file(),
    reason="private source absent from public GitHub CI: source-positive NOT run",
)
def test_original_a253_stp_figured_chain_and_rival_numbers_are_not_soffit_area():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = audit(raw, expected_sha256=SHA, page_number=18, material_code="STP")
    assert result["status"] == "original_exterior_overhead_source_candidates_only"
    addresses = {tuple(row["source_word_address"])
                 for row in result["all_original_code_word_candidates"]}
    assert addresses == {
        (18, 32, 0, 0), (18, 53, 1, 0), (18, 54, 1, 0),
        (18, 62, 8, 0), (18, 108, 0, 0),
    }
    definitions = result["original_soffit_material_description_candidates"]
    assert len(definitions) == 1
    assert definitions[0]["material_code_word_address"] == (18, 108, 0, 0)
    assert {"STRAMIT", "PREMIER", "300", "SOFFIT", "CLADDING"} <= set(
        definitions[0]["native_description_literals_untrusted"]
    )
    exact = [c for c in result["all_competing_figured_arithmetic_chains"]
             if c["component_source_word_addresses"]
             == tuple((18, 10, line, 0) for line in range(5))]
    assert len(exact) == 1
    assert sorted(exact[0]["component_printed_values_untrusted"]) == [
        4325, 4325, 8500, 8500, 8500,
    ]
    assert exact[0]["arithmetic_total_untrusted"] == 34150
    assert (18, 11, 0, 0) in exact[0]["rival_total_source_word_addresses"]
    # Five individually inked black dimension segments and a separate
    # full-length native black overall line (not fabricated PDF-scale m2).
    ink = exact[0]["source_ink_line_correspondence_candidates"]
    assert len(ink) >= 1
    assert any(
        set(row["original_ink_component_path_item_ids"])
        == {(4131, 0), (4115, 0), (4111, 0), (4107, 0), (4122, 0)}
        and row["original_ink_overall_path_item_id"] == (4140, 0)
        for row in ink
    )
    assert all(not row["physical_soffit_dimension_axis_proven"]
               and not row["firm_metric_authority"] for row in ink)
    num_addresses = {tuple(r["source_word_address"])
                     for r in result["original_figured_number_candidates"]}
    assert (18, 12, 1, 0) in num_addresses  # 6150 has no proven extension-line span
    assert (18, 53, 0, 0) in num_addresses  # 4960 is not automatically canopy width
    assert (18, 54, 0, 0) in num_addresses
    assert not result["physical_overhead_surface_polygon_proven"]
    assert result["exterior_soffit_area_m2"] is None
    assert result["new_firm_quantities"] == 0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SHA


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private original unavailable")
def test_original_a120_signage_cld3_cannot_alias_a253_premade_stp():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    cld = audit(raw, expected_sha256=SHA, page_number=9, material_code="CLD3")
    stp = audit(raw, expected_sha256=SHA, page_number=18, material_code="STP")
    assert len(cld["all_original_code_word_candidates"]) == 4
    assert all(r["source_word_address"][0] == 9
               for r in cld["all_original_code_word_candidates"])
    assert all(r["source_word_address"][0] == 18
               for r in stp["all_original_code_word_candidates"])
    assert cld["original_soffit_material_description_candidates"] == ()
    assert cld["source_canopy_union_overlap_proven"] is False
    assert cld["exterior_soffit_area_m2"] is None
    assert stp["exterior_soffit_area_m2"] is None
