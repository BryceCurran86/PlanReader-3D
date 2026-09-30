"""End-to-end wiring tests for the declared-area/geometry authority boundary."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _save_corroborated_compound_plan(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((60, 45), "GROUND FLOOR PLAN", fontsize=12)
    page.insert_text((500, 45), "DRAWING NO SYN-F30", fontsize=9)
    page.insert_text((300, 190), "FLOOR AREA - 162.69M2", fontsize=10)

    # Two same-axis horizontal dimensions. The old size-ranked heuristic would
    # incorrectly pair 15.95 with the internal/sub-chain 11.05.
    page.insert_text((240, 80), "15,950", fontsize=10)
    page.insert_text((240, 105), "11,050", fontsize=10)
    page.insert_text((240, 130), "4,300", fontsize=10)

    # The orthogonal overall direction is native rotated text.
    page.insert_text((90, 360), "8,200", fontsize=10, rotate=90)
    page.insert_text((120, 360), "7,800", fontsize=10, rotate=90)
    page.insert_text((150, 360), "4,600", fontsize=10, rotate=90)

    # A separately figured width is spatially bound to the named secondary
    # strip.  No prose states "2m wide verandah"; the binding is geometric.
    page.insert_text((90, 440), "2,000", fontsize=10, rotate=90)
    page.insert_text((300, 430), "VERANDAH", fontsize=10)

    doc.save(path)
    doc.close()
    return path


def _save_uncorroborated_plain_plan(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((60, 45), "GROUND FLOOR PLAN", fontsize=12)
    page.insert_text((240, 80), "10,000", fontsize=10)
    page.insert_text((240, 105), "8,000", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_declared_area_does_not_drive_wall_or_floor_geometry(tmp_path: Path):
    pdf = _save_corroborated_compound_plan(tmp_path / "compound.pdf")
    predictions = GenericPlanReaderExtractor().extract_from_pdf(pdf)
    by_tag = {prediction.tag: prediction for prediction in predictions}

    floor = by_tag["floor_screed"]
    wall = by_tag["perimeter_walling"]

    # The declared 162.69m2 claim cannot select the 15.95 x 8.2 pair.
    # Independent dimension selection remains authoritative, even when that
    # reconstruction disagrees with the printed aggregate.
    assert floor.quantity == pytest.approx(176.25)
    assert floor.dimensions == pytest.approx([15.95, 11.05])
    assert floor.metadata["derived_footprint_area_m2"] == pytest.approx(176.2475)
    assert floor.metadata["declared_floor_area_m2"] == pytest.approx(162.69)
    assert floor.metadata["declared_floor_area_binding"] == "unbound"
    assert floor.metadata["declared_floor_area_reconciliation_status"] == (
        "declared_area_discrepancy"
    )
    assert "envelope_authority" not in floor.metadata
    assert "area_authority" not in floor.metadata

    assert wall.dimensions[0] == pytest.approx(54.0)
    # No opening was detected on this synthetic plan, so the fail-closed
    # opening-deduction gate may block final publication. The independently
    # selected wall geometry remains visible through dimensions/gross metadata.
    assert wall.metadata["gross_area_m2"] == pytest.approx(54.0 * 2.8)
    assert "envelope_authority" not in wall.metadata


def test_no_explicit_floor_area_preserves_legacy_envelope_path(tmp_path: Path):
    pdf = _save_uncorroborated_plain_plan(tmp_path / "plain.pdf")
    predictions = GenericPlanReaderExtractor().extract_from_pdf(pdf)
    by_tag = {prediction.tag: prediction for prediction in predictions}

    floor = by_tag["floor_screed"]
    assert floor.dimensions == pytest.approx([10.0, 8.0])
    assert floor.quantity == pytest.approx(80.0)
    assert "envelope_authority" not in floor.metadata
