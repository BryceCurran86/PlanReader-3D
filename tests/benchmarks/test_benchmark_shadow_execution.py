"""Canonical benchmark must execute production Item35 authority."""

from __future__ import annotations

import fitz

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine


def test_benchmark_executes_item35_production_authority(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "drawing.pdf"
    doc = fitz.open()
    doc.new_page(width=700, height=650)
    doc.save(pdf_path)
    doc.close()

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
