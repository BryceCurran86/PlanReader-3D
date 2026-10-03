from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import fitz

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wall_scope_funnel_report.py"
_spec = importlib.util.spec_from_file_location("wall_scope_funnel_report", _SCRIPT)
funnel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(funnel)


def _pdf(*, label: bool, pages: int = 1) -> bytes:
    doc = fitz.open()
    try:
        for _ in range(pages):
            page = doc.new_page(width=320.0, height=240.0)
            for a, b in (
                ((40, 40), (280, 40)),
                ((280, 40), (280, 200)),
                ((280, 200), (40, 200)),
                ((40, 200), (40, 40)),
            ):
                page.draw_line(a, b, width=1.2)
            if label:
                page.draw_rect(
                    fitz.Rect(118.5, 111.3, 133.0, 121.0),
                    color=None,
                    fill=(1, 1, 1),
                )
                page.insert_text((120, 118), "FT2", fontsize=6)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_report_funnel_fields_and_walls_flag() -> None:
    data = _pdf(label=False)
    report = funnel.wall_scope_funnel(data)

    assert report["source_sha256"] == hashlib.sha256(data).hexdigest()
    (row,) = report["pages"]
    assert row["page_id"] == "1"
    assert row["raw_segments"] == 4
    assert row["annotation_mask_edges_proven"] == 0
    assert row["filtered_segments"] == 4
    assert row["scope_status"] == "corroborated"
    assert row["scope_complete"] is True
    assert row["candidate_records"] == 4
    assert row["complexity_exceeded"] is False
    assert row["yields_canonical_walls"] is True
    assert report["pages_yielding_canonical_walls"] == 1


def test_report_is_deterministic_and_content_addressed() -> None:
    data = _pdf(label=True)
    assert funnel.wall_scope_funnel(data) == funnel.wall_scope_funnel(data)


def test_report_counts_proven_mask_edges_only_when_proof_exists() -> None:
    report = funnel.wall_scope_funnel(_pdf(label=True))
    (row,) = report["pages"]
    # Never claims more mask edges than rectangle edges, and the filtered count
    # is exactly the raw count minus the proven mask edges.
    assert 0 <= row["annotation_mask_edges_proven"] <= 4
    assert row["filtered_segments"] == row["raw_segments"] - row["annotation_mask_edges_proven"]
    if not report["mask_proof_available"]:
        assert row["annotation_mask_edges_proven"] == 0


def test_page_selection_limits_report_to_requested_pages() -> None:
    report = funnel.wall_scope_funnel(_pdf(label=False, pages=3), ["2"])
    assert [row["page_id"] for row in report["pages"]] == ["2"]


def test_main_writes_json_output(tmp_path, capsys) -> None:
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(_pdf(label=False))
    out = tmp_path / "report.json"
    assert funnel.main([str(pdf), "--output", str(out)]) == 0
    assert out.exists()
    assert "candidate records:" in capsys.readouterr().out
