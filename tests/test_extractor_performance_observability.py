from __future__ import annotations

import fitz

import pb_planreader_pdf_extractor as extractor_mod
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _blank_pdf(tmp_path):
    path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()
    return path


def _prediction_payload(predictions):
    return [prediction.to_dict() for prediction in predictions]


def test_extractor_performance_trace_is_diagnostic_only(tmp_path, monkeypatch):
    pdf = _blank_pdf(tmp_path)

    baseline = GenericPlanReaderExtractor()
    baseline_predictions = baseline.extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )

    monkeypatch.setenv("PLANREADER_EXTRACTOR_PROGRESS", "1")
    instrumented = GenericPlanReaderExtractor()
    instrumented_predictions = instrumented.extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )

    assert _prediction_payload(instrumented_predictions) == _prediction_payload(
        baseline_predictions
    )

    trace = instrumented.performance_trace
    assert trace["version"] == "extractor-performance-v1"
    assert trace["total_pages"] == 1
    assert trace["elapsed_seconds"] >= 0.0

    events = trace["events"]
    stages = [event["stage"] for event in events]
    assert stages[0] == "extract_start"
    assert "cross_page_pre_scan_page" in stages
    assert "cross_page_pre_scan_complete" in stages
    assert "main_page_analysis_start" in stages
    assert "main_page_analysis_page" in stages
    assert "main_page_analysis_complete" in stages
    assert "drawing_ocr_reconciliation_start" in stages
    assert "physical_net_wall_live_start" in stages
    assert "ceiling_lining_live_start" in stages
    assert "roof_covering_shadow_start" in stages
    assert stages[-1] == "extract_complete"

    page_events = [event for event in events if "page" in event]
    assert page_events
    assert all(event["page"] == 1 for event in page_events)
    assert all(event["total_pages"] == 1 for event in page_events)

    elapsed = [event["elapsed_seconds"] for event in events]
    assert elapsed == sorted(elapsed)


def test_performance_memory_probe_failure_cannot_change_extraction(
    tmp_path,
    monkeypatch,
):
    pdf = _blank_pdf(tmp_path)

    baseline = GenericPlanReaderExtractor().extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )

    def _raise_memory_probe():
        raise RuntimeError("diagnostic probe failed")

    monkeypatch.setattr(
        extractor_mod,
        "_best_effort_process_memory_mb",
        _raise_memory_probe,
    )

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )

    assert _prediction_payload(predictions) == _prediction_payload(baseline)
    assert extractor.performance_trace["events"]
    assert extractor.performance_trace["events"][-1]["stage"] == "extract_complete"


def test_progress_output_is_opt_in(tmp_path, monkeypatch, capsys):
    pdf = _blank_pdf(tmp_path)

    monkeypatch.delenv("PLANREADER_EXTRACTOR_PROGRESS", raising=False)
    GenericPlanReaderExtractor().extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )
    assert "[PlanReaderPerf]" not in capsys.readouterr().out

    monkeypatch.setenv("PLANREADER_EXTRACTOR_PROGRESS", "true")
    GenericPlanReaderExtractor().extract_from_pdf(
        pdf,
        collect_item35_shadow=False,
    )
    output = capsys.readouterr().out
    assert "[PlanReaderPerf] stage=extract_start" in output
    assert "[PlanReaderPerf] stage=extract_complete" in output


def test_drawing_page_classification_is_cached_per_page(tmp_path, monkeypatch):
    path = tmp_path / "two-pages.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()

    extractor = GenericPlanReaderExtractor()
    original = extractor.is_drawing_page
    calls = {"count": 0}

    def counted(page_text, page=None):
        calls["count"] += 1
        return original(page_text, page)

    monkeypatch.setattr(extractor, "is_drawing_page", counted)
    extractor.extract_from_pdf(path, collect_item35_shadow=False)

    assert calls["count"] == 2


def _pdf_with_raster(tmp_path, name, display_rect):
    path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=1000, height=1000)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 500, 500), False)
    pix.clear_with(255)
    page.insert_image(fitz.Rect(*display_rect), stream=pix.tobytes("png"))
    doc.save(path)
    doc.close()
    return path


def test_large_raster_gate_ignores_high_resolution_tiny_logo(tmp_path):
    path = _pdf_with_raster(
        tmp_path,
        "tiny-logo.pdf",
        (10, 10, 60, 60),
    )
    doc = fitz.open(path)
    try:
        assert not GenericPlanReaderExtractor._page_has_large_raster(doc[0])
    finally:
        doc.close()


def test_large_raster_gate_accepts_page_significant_raster(tmp_path):
    path = _pdf_with_raster(
        tmp_path,
        "raster-plan.pdf",
        (100, 100, 900, 900),
    )
    doc = fitz.open(path)
    try:
        assert GenericPlanReaderExtractor._page_has_large_raster(doc[0])
    finally:
        doc.close()
