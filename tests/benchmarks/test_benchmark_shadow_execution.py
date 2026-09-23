"""Benchmark extraction executes the same production Item35 path as normal extraction."""

from __future__ import annotations

import fitz

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def test_benchmark_uses_normal_production_extractor_path(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "drawing.pdf"
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    page.insert_text(
        fitz.Point(40, 40),
        "GROUND FLOOR PLAN\n"
        "SCALE 1:100\n"
        "DRAWING NO: AD-01\n"
        "12,000\n"
        "6,000\n"
        "FLOOR AREA - 72.00M2\n"
        "D.P.M. under floor bed\n",
    )
    doc.save(pdf_path)
    doc.close()

    normal = GenericPlanReaderExtractor()
    normal_predictions = [item.to_dict() for item in normal.extract_from_pdf(pdf_path)]
    assert normal_predictions
    assert normal.item35_authority_shadow["reason"] != "not_collected"

    calls = []

    class RecordingExtractor:
        def extract_from_pdf(self, path, pages=None, *, collect_item35_shadow=True):
            calls.append((path, pages, collect_item35_shadow))
            return []

    monkeypatch.setattr(
        "pb_benchmark_accuracy_engine.GenericPlanReaderExtractor",
        RecordingExtractor,
    )
    engine = BenchmarkAccuracyEngine(output_dir=tmp_path / "reports")
    assert engine.extract_quantities_from_pdf(pdf_path, pages=[0]) == []
    assert calls == [(pdf_path, [0], True)]
