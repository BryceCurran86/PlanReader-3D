"""Authority-boundary regressions for declared aggregate floor-area claims.

All geometry and quantities here are synthetic. A printed aggregate may be
retained for reconciliation, but it must not select or replace physical
geometry/quantity authority.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _build_pdf(
    tmp_path: Path,
    *,
    name: str,
    declared_area: float | None,
    dimensions: tuple[str, ...] = ("10,000", "6,000"),
    wall_rows: tuple[str, str] | None = None,
    include_substructure: bool = True,
    include_slab: bool = True,
    include_pitch: bool = True,
) -> Path:
    lines = ["GROUND FLOOR PLAN", "SCALE 1:100", *dimensions]
    if declared_area is not None:
        lines.append(f"TOTAL FLOOR AREA: {declared_area}m2")
    if wall_rows is not None:
        lines.extend(wall_rows)
    if include_substructure:
        lines.extend([
            "DAMP PROOF MEMBRANE TO SURFACE BED",
            "T12@200 EW MESH A142 TOP",
        ])
    if include_slab:
        lines.append("150mm THICK RC SLAB")
    if include_pitch:
        lines.append("30 deg pitch")

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    y = 50
    for line in lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 22
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


def _extract(path: Path):
    ex = GenericPlanReaderExtractor()
    preds = ex.extract_from_pdf(path, collect_item35_shadow=False)
    return ex, {p.tag: p for p in preds}


def test_declared_total_without_geometry_is_retained_but_mints_no_floor_quantities(tmp_path: Path):
    path = _build_pdf(
        tmp_path,
        name="declared_only.pdf",
        declared_area=240.0,
        dimensions=(),
        include_substructure=True,
        include_slab=True,
        include_pitch=False,
    )
    ex, preds = _extract(path)

    assert ex.declared_floor_area_claims
    claim = ex.declared_floor_area_claims[0]
    assert claim["declared_floor_area_m2"] == pytest.approx(240.0)
    assert claim["declared_floor_area_binding"] == "unbound"
    assert claim["declared_floor_area_role"] == "declared_floor_area_reconciliation_only"
    for tag in (
        "floor_screed",
        "reinforced_floor_slab",
        "substructure_bed_dpm",
        "substructure_a142_mesh",
        "substructure_surface_bed",
    ):
        assert tag not in preds


def test_declared_total_mutation_cannot_change_physical_dimensions_or_quantities(tmp_path: Path):
    base_ex, base = _extract(_build_pdf(
        tmp_path, name="base.pdf", declared_area=None
    ))
    low_ex, low = _extract(_build_pdf(
        tmp_path, name="declared_low.pdf", declared_area=42.0
    ))
    high_ex, high = _extract(_build_pdf(
        tmp_path, name="declared_high.pdf", declared_area=999.0
    ))

    physical_tags = (
        "floor_screed",
        "reinforced_floor_slab",
        "substructure_bed_dpm",
        "substructure_a142_mesh",
        "substructure_surface_bed",
        "perimeter_walling",
        "gable_walling",
    )
    for tag in physical_tags:
        assert tag in base and tag in low and tag in high
        assert low[tag].quantity == pytest.approx(base[tag].quantity)
        assert high[tag].quantity == pytest.approx(base[tag].quantity)
        assert low[tag].dimensions == base[tag].dimensions
        assert high[tag].dimensions == base[tag].dimensions

    # Roof authority reads the independently reconstructed floor dimensions;
    # changing only a declared total cannot alter that input or shadow result.
    assert low["floor_screed"].dimensions == high["floor_screed"].dimensions
    assert low_ex.roof_covering_shadow == high_ex.roof_covering_shadow
    assert base_ex.roof_covering_shadow == low_ex.roof_covering_shadow


def test_declared_total_is_metadata_only_not_area_authority(tmp_path: Path):
    ex, preds = _extract(_build_pdf(
        tmp_path, name="metadata.pdf", declared_area=999.0
    ))
    floor = preds["floor_screed"]
    assert floor.quantity == pytest.approx(60.0)
    assert floor.metadata["structural_bed_area_m2"] == pytest.approx(60.0)
    assert floor.metadata["derived_footprint_area_m2"] == pytest.approx(60.0)
    assert floor.metadata["declared_floor_area_m2"] == pytest.approx(999.0)
    assert floor.metadata["declared_floor_area_binding"] == "unbound"
    assert floor.metadata["declared_floor_area_role"] == "declared_floor_area_reconciliation_only"
    assert floor.metadata["declared_floor_area_reconciliation_status"] == "declared_area_discrepancy"
    assert "area_authority" not in floor.metadata
    assert ex.declared_floor_area_claims[0]["declared_floor_area_m2"] == pytest.approx(999.0)


def test_declared_total_cannot_suppress_component_clear_floor_calculation(tmp_path: Path):
    _ex, preds = _extract(_build_pdf(
        tmp_path,
        name="clear_floor.pdf",
        declared_area=999.0,
        dimensions=("12,000", "8,000", "2,000"),
        wall_rows=("200 11,600 200", "200 7,600 200"),
        include_substructure=False,
        include_slab=False,
        include_pitch=False,
    ))
    floor = preds["floor_screed"]
    assert floor.metadata["floor_finish_area_derivation"] == "component_clear_main_plus_evidenced_verandah"
    assert floor.quantity != pytest.approx(999.0)
    assert floor.metadata["structural_bed_area_m2"] != pytest.approx(999.0)


def test_declared_metadata_has_no_replacement_priority():
    existing = SimpleNamespace(quantity=100.0, metadata={})
    declared_meta = {
        "declared_floor_area_m2": 500.0,
        "declared_floor_area_binding": "unbound",
        "declared_floor_area_role": "declared_floor_area_reconciliation_only",
    }
    assert GenericPlanReaderExtractor._should_replace_slab_bound_quantity(
        existing, 90.0, declared_meta
    ) is False
    assert GenericPlanReaderExtractor._should_replace_slab_bound_quantity(
        existing, 110.0, declared_meta
    ) is True


def test_declared_area_value_cannot_choose_between_competing_dimension_sets(tmp_path: Path):
    # Same physical dimension text, different declared totals: geometry result
    # must remain identical because declared area is not a selection input.
    _a_ex, a = _extract(_build_pdf(
        tmp_path,
        name="ambiguous_a.pdf",
        declared_area=80.0,
        dimensions=("12,000", "10,000", "9,600", "8,000"),
        include_substructure=False,
        include_slab=False,
        include_pitch=False,
    ))
    _b_ex, b = _extract(_build_pdf(
        tmp_path,
        name="ambiguous_b.pdf",
        declared_area=96.0,
        dimensions=("12,000", "10,000", "9,600", "8,000"),
        include_substructure=False,
        include_slab=False,
        include_pitch=False,
    ))
    assert a["floor_screed"].dimensions == b["floor_screed"].dimensions
    assert a["floor_screed"].quantity == pytest.approx(b["floor_screed"].quantity)
