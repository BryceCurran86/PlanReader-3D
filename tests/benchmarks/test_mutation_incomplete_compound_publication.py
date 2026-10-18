"""Fail-closed production quantities when a known source component is unfigured.

All PDFs here are synthetic. These are not benchmark plans, expected gold
outputs, or original-source quantity authorizations.
"""
from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _plan(tmp_path: Path, *, unfigured_verandah: bool) -> Path:
    lines = [
        "GROUND FLOOR PLAN",
        "SCALE 1:100",
        "10,000",
        "6,000",
        "125mm thick reinforced concrete surface bed on blinding layer",
        "1000 gauge polythene D.P.M.",
        "B.R.C. MESH A142",
    ]
    if unfigured_verandah:
        lines.append("VERANDAH")
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    for idx, line in enumerate(lines):
        page.insert_text((72, 55 + 28 * idx), line, fontsize=11)
    path = tmp_path / ("unfigured_verandah.pdf" if unfigured_verandah else "complete.pdf")
    doc.save(path)
    doc.close()
    return path


def test_unfigured_verandah_cannot_publish_partial_sum_as_complete_floor(tmp_path: Path) -> None:
    predictions = GenericPlanReaderExtractor().extract_from_pdf(
        _plan(tmp_path, unfigured_verandah=True), collect_item35_shadow=False,
    )
    by_tag = {prediction.tag: prediction for prediction in predictions}
    assert "floor_screed" not in by_tag
    assert "substructure_surface_bed" not in by_tag
    assert "substructure_bed_dpm" not in by_tag
    assert "substructure_a142_mesh" not in by_tag
    assert "reinforced_floor_slab" not in by_tag
    # Partial source authority is not an area of zero or a guessed width.
    # Upstream source room production must first resolve the verandah dimensions.


def test_complete_same_figured_envelope_retains_original_slab_and_dpm(tmp_path: Path) -> None:
    predictions = GenericPlanReaderExtractor().extract_from_pdf(
        _plan(tmp_path, unfigured_verandah=False), collect_item35_shadow=False,
    )
    by_tag = {prediction.tag: prediction for prediction in predictions}
    assert by_tag["floor_screed"].quantity == pytest.approx(60.0)
    assert by_tag["substructure_surface_bed"].quantity == pytest.approx(60.0)
    assert by_tag["substructure_bed_dpm"].quantity == pytest.approx(60.0)
    assert by_tag["substructure_a142_mesh"].quantity == pytest.approx(60.0)
