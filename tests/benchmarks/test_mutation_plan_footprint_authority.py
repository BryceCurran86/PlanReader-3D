"""Mutation tests for page-local plan-footprint publication authority.

Synthetic fixtures only.  These tests protect against cross-view geometry
contamination where an elevation bay sum is combined with a section span and
published as a floor/slab footprint.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _save_doc(doc: fitz.Document, path: Path) -> Path:
    doc.save(str(path))
    doc.close()
    return path


def _make_cross_view_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()

    elevation = doc.new_page()
    elevation.insert_text(
        (72, 72),
        "\n".join(
            [
                "ELEVATION E-01",
                "SCALE 1:100",
                "2,200",
                "2,200",
                "3,450",
                "3,450",
                "3,450",
                "3,450",
            ]
        ),
        fontsize=11,
    )

    section = doc.new_page()
    section.insert_text(
        (72, 72),
        "\n".join(
            [
                "SECTION A-A",
                "SCALE 1:25",
                "8,201",
                "125mm thick reinforced concrete surface bed on blinding layer",
                "1000 gauge polythene D.P.M.",
                "B.R.C. MESH A142",
                "150mm wide bituminous felt D.P.C.",
            ]
        ),
        fontsize=11,
    )

    return _save_doc(doc, tmp_path / "cross_view.pdf")


def _make_plan_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "GROUND FLOOR PLAN",
                "SCALE 1:100",
                "10,000",
                "6,000",
                "125mm thick reinforced concrete surface bed on blinding layer",
                "1000 gauge polythene D.P.M.",
                "B.R.C. MESH A142",
            ]
        ),
        fontsize=11,
    )
    return _save_doc(doc, tmp_path / "plan.pdf")


def test_plan_footprint_context_accepts_plans_not_services_layouts() -> None:
    ex = GenericPlanReaderExtractor()
    assert ex._has_plan_footprint_context("GROUND FLOOR PLAN")
    assert ex._has_plan_footprint_context("FOUNDATION PLAN")
    assert ex._has_plan_footprint_context("FOUNDATION LAYOUT")
    assert ex._has_plan_footprint_context("SLAB LAYOUT")

    assert not ex._has_plan_footprint_context("ELEVATION E-01")
    assert not ex._has_plan_footprint_context("SECTION A-A")
    assert not ex._has_plan_footprint_context("Electrical Power Layout")
    assert not ex._has_plan_footprint_context("Soil Waste Water Drainage Layout")


def test_elevation_bay_sum_cannot_borrow_section_span_for_floor_area(tmp_path: Path) -> None:
    pdf_path = _make_cross_view_pdf(tmp_path)

    # The legacy geometry helper can still demonstrate the dangerous numerical
    # combination: 2.2 + 2.2 + 4*3.45 = 18.2m and 18.2*8.201 = 149.26m2.
    ex = GenericPlanReaderExtractor()
    length_m, width_m = ex._detect_outer_envelope(
        [2.2, 2.2, 3.45, 3.45, 3.45, 3.45],
        8.201,
        True,
    )
    assert length_m == 18.2
    assert width_m == 8.201
    assert round(length_m * width_m, 2) == 149.26

    preds = ex.extract_from_pdf(pdf_path, collect_item35_shadow=False)
    pred_map = {p.tag: p for p in preds}

    for tag in (
        "floor_screed",
        "substructure_surface_bed",
        "substructure_bed_dpm",
        "substructure_a142_mesh",
        "damp_proof_course",
    ):
        assert tag not in pred_map


def test_real_plan_context_still_publishes_floor_bound_quantities(tmp_path: Path) -> None:
    pdf_path = _make_plan_pdf(tmp_path)
    preds = GenericPlanReaderExtractor().extract_from_pdf(
        pdf_path,
        collect_item35_shadow=False,
    )
    pred_map = {p.tag: p for p in preds}

    assert pred_map["floor_screed"].quantity == 60.0
    assert pred_map["substructure_surface_bed"].quantity == 60.0
    assert pred_map["substructure_bed_dpm"].quantity == 60.0
    assert pred_map["substructure_a142_mesh"].quantity == 60.0
