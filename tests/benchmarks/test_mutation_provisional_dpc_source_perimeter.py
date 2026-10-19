"""DPC provisional source perimeter cannot masquerade as complete takeoff."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _plan(tmp_path: Path, *, incomplete_verandah: bool) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    lines = ["GROUND FLOOR PLAN", "SCALE 1:100", "10,000", "6,000",
             "bituminous damp proof course under external walls"]
    if incomplete_verandah:
        lines.append("VERANDAH")
    for index, line in enumerate(lines):
        page.insert_text((72, 58 + 28 * index), line, fontsize=11)
    path = tmp_path / f"dpc_{int(incomplete_verandah)}.pdf"
    doc.save(path)
    doc.close()
    return path


def _dpc(path: Path):
    output = GenericPlanReaderExtractor().extract_from_pdf(
        path, collect_item35_shadow=False,
    )
    return {row.tag: row for row in output}["damp_proof_course"]


def test_complete_single_floor_perimeter_still_admitted_at_original_confidence(tmp_path: Path):
    item = _dpc(_plan(tmp_path, incomplete_verandah=False))
    assert item.quantity == pytest.approx(32.0)
    assert item.metadata["dpc_envelope_resolution"] == "confirmed_external"
    assert item.metadata["commercial_perimeter_authorized"] is True
    assert item.confidence == pytest.approx(0.90)


def test_partial_compound_fallback_dpc_remains_numeric_but_provisional(tmp_path: Path):
    item = _dpc(_plan(tmp_path, incomplete_verandah=True))
    assert item.quantity == pytest.approx(32.0)
    assert item.metadata["dpc_envelope_resolution"] == "fallback_wall"
    assert item.metadata["commercial_perimeter_authorized"] is False
    assert item.confidence == pytest.approx(0.45)
