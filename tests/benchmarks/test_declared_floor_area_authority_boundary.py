"""Regression tests for declared floor-area authority separation.

All dimensions and quantities are synthetic. Printed area claims are source
evidence only and must never become physical geometry or quantity authority.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import ExtractedPrediction, GenericPlanReaderExtractor


def _build_pdf(tmp_path: Path, name: str, lines: list[str]) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((60, 60), "\n".join(lines), fontsize=11)
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


def _physical_plan_lines(declared_area: float) -> list[str]:
    return [
        "GROUND FLOOR PLAN",
        "SCALE 1:100",
        "10,000",
        "6,000",
        f"TOTAL FLOOR AREA: {declared_area:.2f}m2",
        "25 deg pitch",
        "DAMP PROOF MEMBRANE TO SURFACE BED",
        "B.R.C. MESH A142",
        "150mm THICK RC SLAB",
        "Surface bed on well compacted hardcore",
    ]


def _pred_map(path: Path):
    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(path, collect_item35_shadow=False)
    return extractor, {p.tag: p for p in preds}


def test_unbound_declared_total_cannot_create_physical_quantities(tmp_path: Path) -> None:
    path = _build_pdf(
        tmp_path,
        "declared_only.pdf",
        [
            "GROUND FLOOR PLAN",
            "TOTAL FLOOR AREA: 297.50m2",
            "DAMP PROOF MEMBRANE TO SURFACE BED",
            "B.R.C. MESH A142",
            "150mm THICK RC SLAB",
        ],
    )
    extractor, preds = _pred_map(path)

    for tag in (
        "floor_screed",
        "reinforced_floor_slab",
        "substructure_bed_dpm",
        "substructure_a142_mesh",
        "substructure_surface_bed",
        "perimeter_walling",
        "gable_walling",
    ):
        assert tag not in preds

    assert extractor.declared_floor_area_claims == [
        {
            "declared_floor_area_m2": 297.5,
            "declared_floor_area_source_pages": [1],
            "declared_floor_area_raw_evidence": ["FLOOR AREA: 297.50m2"],
            "declared_floor_area_evidence_role": "declared_source_area_claim",
            "declared_floor_area_binding": "unbound",
        }
    ]
    assert extractor.extraction_status["declared_floor_area"] == (
        "evidence_present_reconciliation_only"
    )


def test_declared_total_does_not_change_geometry_bound_outputs(tmp_path: Path) -> None:
    matching = _build_pdf(tmp_path, "matching.pdf", _physical_plan_lines(60.0))
    conflicting = _build_pdf(tmp_path, "conflicting.pdf", _physical_plan_lines(75.0))

    ex_a, a = _pred_map(matching)
    ex_b, b = _pred_map(conflicting)

    required = (
        "floor_screed",
        "reinforced_floor_slab",
        "substructure_bed_dpm",
        "substructure_a142_mesh",
        "substructure_surface_bed",
        "perimeter_walling",
        "gable_walling",
    )
    for tag in required:
        assert tag in a and tag in b
        assert a[tag].quantity == pytest.approx(b[tag].quantity)
        assert a[tag].dimensions == b[tag].dimensions

    assert a["floor_screed"].quantity == pytest.approx(60.0)
    assert b["floor_screed"].quantity == pytest.approx(60.0)
    assert a["reinforced_floor_slab"].quantity == pytest.approx(60.0)
    assert b["reinforced_floor_slab"].quantity == pytest.approx(60.0)
    assert a["substructure_bed_dpm"].quantity == pytest.approx(60.0)
    assert b["substructure_bed_dpm"].quantity == pytest.approx(60.0)
    assert a["substructure_a142_mesh"].quantity == pytest.approx(60.0)
    assert b["substructure_a142_mesh"].quantity == pytest.approx(60.0)
    assert a["substructure_surface_bed"].quantity == pytest.approx(60.0)
    assert b["substructure_surface_bed"].quantity == pytest.approx(60.0)

    meta = b["floor_screed"].metadata
    assert meta["structural_bed_area_m2"] == pytest.approx(60.0)
    assert meta["derived_footprint_area_m2"] == pytest.approx(60.0)
    assert meta["declared_floor_area_m2"] == pytest.approx(75.0)
    assert meta["declared_floor_area_binding"] == "unbound"
    assert meta["declared_floor_area_evidence_role"] == "declared_source_area_claim"
    assert "area_authority" not in meta
    assert ex_a.declared_floor_area_claims[0]["declared_floor_area_m2"] == pytest.approx(60.0)
    assert ex_b.declared_floor_area_claims[0]["declared_floor_area_m2"] == pytest.approx(75.0)


def test_declared_total_cannot_suppress_component_clear_floor_geometry(tmp_path: Path) -> None:
    path = _build_pdf(
        tmp_path,
        "clear_floor.pdf",
        [
            "GROUND FLOOR PLAN",
            "SCALE 1:100",
            "12,000",
            "8,000",
            "2,000mm wide verandah finished in screed",
            "200 11,600 200",
            "200 7,600 200",
            "TOTAL FLOOR AREA: 999.00m2",
            "D.P.M. under floor bed",
            "A142 mesh reinforcement to floor bed",
            "100mm R.C. slab on well compacted hardcore",
        ],
    )
    _extractor, preds = _pred_map(path)
    floor = preds["floor_screed"]
    assert floor.quantity == pytest.approx(112.16)
    assert floor.metadata["structural_bed_area_m2"] == pytest.approx(120.0)
    assert floor.metadata["main_clear_floor_area_m2"] == pytest.approx(88.16)
    assert floor.metadata["open_verandah_floor_area_m2"] == pytest.approx(24.0)
    assert floor.metadata["declared_floor_area_m2"] == pytest.approx(999.0)
    assert floor.metadata["declared_floor_area_binding"] == "unbound"
    assert preds["substructure_bed_dpm"].quantity == pytest.approx(120.0)
    assert preds["substructure_a142_mesh"].quantity == pytest.approx(120.0)
    assert preds["substructure_surface_bed"].quantity == pytest.approx(120.0)


def test_legacy_explicit_metadata_has_no_replacement_privilege() -> None:
    existing = ExtractedPrediction(
        tag="substructure_bed_dpm",
        trade_type="finishes",
        description="existing geometry",
        quantity=100.0,
        unit="SM",
        confidence=0.9,
        source_page=1,
        metadata={"area_authority": "geometry"},
    )
    assert GenericPlanReaderExtractor._should_replace_slab_bound_quantity(
        existing,
        90.0,
        {"area_authority": "explicit_drawing_floor_area"},
    ) is False
    assert GenericPlanReaderExtractor._should_replace_slab_bound_quantity(
        existing,
        110.0,
        {"declared_floor_area_m2": 999.0, "declared_floor_area_binding": "unbound"},
    ) is True


def test_conflicting_declared_totals_remain_visible_without_publication(tmp_path: Path) -> None:
    doc = fitz.open()
    for value in (80.0, 95.0):
        page = doc.new_page(width=842, height=595)
        page.insert_text(
            (60, 60),
            f"GROUND FLOOR PLAN\nTOTAL FLOOR AREA: {value:.2f}m2",
            fontsize=11,
        )
    path = tmp_path / "conflicting_claims.pdf"
    doc.save(path)
    doc.close()

    extractor, preds = _pred_map(path)
    assert "floor_screed" not in preds
    assert [c["declared_floor_area_m2"] for c in extractor.declared_floor_area_claims] == [80.0, 95.0]
    assert extractor.extraction_status["declared_floor_area"] == (
        "conflicting_declared_claims_reconciliation_only"
    )
