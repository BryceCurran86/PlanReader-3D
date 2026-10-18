"""The all-page census tool reports counts and coordinates only, and is faithful to the module.

Synthetic page only: no customer PDF is read. The tool is a diagnostic; it cannot publish a viewport.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import pytest

import pb_viewport_segmentation as v
from tools import diag_f07_text_cell_plan_frame_census as census

TITLE = "GROUND FLOOR PLAN"
FIXTURE_LABEL = "T-1"
FRAME = (40.0, 30.0, 760.0, 520.0)


def _write_lattice_plan(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=800.0, height=600.0)
    page.draw_rect(fitz.Rect(*FRAME), color=(0, 0, 0), width=1.0)
    for row in range(6):
        for col in range(8):
            rect = fitz.Rect(80 + col * 80, 60 + row * 40, 120 + col * 80, 80 + row * 40)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            page.insert_text((rect.x0 + 3, rect.y0 + 15), FIXTURE_LABEL, fontsize=6.0)
    page.insert_text((60.0, 505.0), TITLE, fontsize=11.0)
    path.write_bytes(doc.tobytes())
    doc.close()


@pytest.fixture()
def lattice_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "private_client_name_plan_set.pdf"
    _write_lattice_plan(path)
    return path


def test_census_reports_the_shadow_effect_page_and_frame_evidence(lattice_pdf: Path):
    report = census.census_pdf(lattice_pdf)
    assert report["page_count"] == 1
    page = report["pages"][0]
    assert page["default_equals_flag_false"] is True
    assert page["receipt_without_flag"] is False
    assert page["shadow_changes_viewports"] is True
    change = page["shadow_changes"][0]
    assert change["after"]["status"] == "resolved"
    assert change["after"]["native_bbox"] == pytest.approx(list(FRAME))
    assert change["after"]["shadow_receipt_counts"] == {"table_veto_lifted_frames": 1, "near_nested_rival_frames": 0}
    frames = page["legacy_table_frames"]
    assert len(frames) == 1 and frames[0]["legacy_table"] and frames[0]["cell_family_branch"]
    assert frames[0]["shadow_table"] is False and frames[0]["shadow_lifts_table_status"] is True
    family = frames[0]["qualifying_families"][0]
    assert family["cells"] == 48 and family["edge_connected_fraction"] == 0.0 and family["text_bearing_fraction"] == 1.0

    summary = census.summarise([report], with_baseline=False)
    assert summary["pages"] == 1 and summary["pages_shadow_changes_viewports"] == 1
    assert summary["legacy_table_frames_cell_family_branch"] == 1
    assert summary["legacy_table_frames_lifted_by_shadow"] == 1
    assert summary["sources_with_any_cell_family_table_frame"] == [report["source_id"]]


def test_report_holds_counts_and_coordinates_only(lattice_pdf: Path):
    text = json.dumps(census.census_pdf(lattice_pdf))
    for forbidden in (TITLE, FIXTURE_LABEL, "private_client_name", "plan_set", str(lattice_pdf.parent)):
        assert forbidden not in text
    assert "label" not in text  # no viewport label field is emitted


def test_main_writes_json_and_markdown_and_compares_with_a_baseline_module(lattice_pdf: Path, tmp_path: Path):
    output = tmp_path / "census.json"
    markdown = tmp_path / "census.md"
    try:
        code = census.main([
            "--pdf", str(lattice_pdf), "--baseline-module", str(Path(v.__file__)),
            "--output", str(output), "--markdown", str(markdown),
        ])
    finally:
        sys.modules.pop("pb_viewport_segmentation_baseline", None)
    assert code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["has_baseline"] is True
    assert report["summary"]["pages_default_equals_baseline_module"] == 1
    assert report["summary"]["pages_default_equals_flag_false"] == 1
    assert report["constants"]["near_nested_band_containment_fraction"] == v._NEAR_NESTED_BAND_CONTAINMENT_FRACTION
    table = markdown.read_text(encoding="utf-8")
    assert table.splitlines()[0].startswith("| source |") and "**total**" in table


def test_main_requires_a_pdf(tmp_path: Path):
    with pytest.raises(SystemExit):
        census.main(["--output", str(tmp_path / "x.json")])
