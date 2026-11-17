"""Live Plan Mapper tracing remains source-only and page-indexed.

No network/UI is required for source-neutral event tests.
"""
import ast
from pathlib import Path

from tests.test_new_source_trace_preview import _floor_plan
from pb_new_source_trace_preview import source_native_trace_preview


def test_live_trace_reports_page_count_progress_and_incremental_images(tmp_path):
    pdf = _floor_plan(tmp_path)
    events = []
    summary, png = source_native_trace_preview(
        pdf, 0, progress_callback=events.append,
    )
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert summary["document_page_count"] == 1
    assert events[0]["stage"] == "reading_original_page"
    assert events[-1]["stage"] == "trace_complete"
    stages = [event["stage"] for event in events]
    assert "classifying_page_ink" in stages
    assert "tracing_outer_boundary" in stages
    assert "resolving_wall_and_room_topology" in stages
    assert "drawing_wall_candidates" in stages
    assert "drawing_outer_boundary" in stages
    assert "drawing_openings_and_wall_ends" in stages
    assert "drawing_enclosed_room_candidates" in stages
    assert len([x for x in events if x.get("overlay_png")]) >= 4
    assert all(
        event["page_index"] == 0
        and event["page_number"] == 1
        and event["page_count"] == 1
        and event["source_only"] is True
        and event["physical_wall_authenticated"] is False
        and event["measurement_authorized"] is False
        for event in events
    )
    assert all(
        e["overlay_png"] is None or e["overlay_png"].startswith(b"\x89PNG")
        for e in events
    )
    fractions = [e["fraction"] for e in events]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0


def test_live_trace_callback_failure_cannot_abort_source_geometry(tmp_path):
    pdf = _floor_plan(tmp_path)
    observed = []

    def broken_renderer(event):
        observed.append(event["stage"])
        raise RuntimeError("simulated disconnected progress viewer")

    summary, png = source_native_trace_preview(
        pdf, 0, progress_callback=broken_renderer,
    )
    assert summary["quantity_authorized"] is False
    assert summary["commercial_publishable"] is False
    assert png.startswith(b"\x89PNG")
    assert observed[0] == "reading_original_page"
    assert observed[-1] == "trace_complete"


def test_original_plan_mapper_streamlit_page_and_overlay_are_wired():
    path = Path(__file__).resolve().parents[1] / "pb_planreader_3d_app.py"
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "plan_mapper_page"
    )
    body = ast.get_source_segment(src, fn)
    assert body is not None
    assert "progress_callback=_show_live_trace" in body
    assert "PDF page {page_number}{total}" in body
    assert "live_overlay.image(" in body
    assert "live_meter.progress(" in body
    assert "selected_pdf_page=int(page[\"page_no\"])" in body
    assert "Re-run new native wall trace" in body
