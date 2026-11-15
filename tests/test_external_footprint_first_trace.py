"""Owner mandatory external-footprint-first ordering and fail-closed diagnostics."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

import pb_live_physical_net_wall_integration as live
from pb_external_footprint_first_trace import trace_external_footprint_first


def _plan(tmp_path: Path, *, walls: bool) -> Path:
    p = tmp_path / "house.pdf"
    d = fitz.open()
    page = d.new_page(width=1100, height=780)
    if walls:
        # Building walls: painted outline plus a joined cross partition.
        page.draw_rect(fitz.Rect(210, 130, 800, 490), color=(0, 0, 0), width=4)
        page.draw_line((510, 130), (510, 490), color=(0, 0, 0), width=3)
        page.draw_line((210, 305), (800, 305), color=(0, 0, 0), width=3)
        # Detached title/legend box below house is not a wall.
        page.draw_rect(fitz.Rect(10, 685, 1090, 765), color=(0, 0, 0), width=1)
    else:
        page.insert_text((25, 40), "EMPTY DRAWING", fontsize=13)
    d.save(p)
    d.close()
    return p


def test_sha_pinned_first_footprint_candidate_has_no_commercial_authority(tmp_path):
    path = _plan(tmp_path, walls=True)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    (result,) = trace_external_footprint_first(
        raw, source_sha256=sha, page_indices=(0,),
    )
    assert result.status == "CANDIDATE"
    assert result.source_sha256 == sha
    assert result.page_index == 0
    assert result.polygon_pdf_pts
    assert result.measurement_authorized is False
    assert result.commercial_publishable is False
    assert result.bbox_pdf_pts
    assert 190 < result.bbox_pdf_pts[0] < 230
    assert 780 < result.bbox_pdf_pts[2] < 830
    assert result.to_dict()["measurement_authorized"] is False


def test_empty_pdf_page_explicitly_abstains(tmp_path):
    path = _plan(tmp_path, walls=False)
    raw = path.read_bytes()
    (result,) = trace_external_footprint_first(
        raw, source_sha256=hashlib.sha256(raw).hexdigest(),
        page_indices=(0,),
    )
    assert result.status == "ABSTAINED"
    assert result.polygon_pdf_pts == ()
    assert result.reason == "external_footprint_no_closed_wall_ink_candidate"


def test_foreign_source_sha_rejected(tmp_path):
    raw = _plan(tmp_path, walls=True).read_bytes()
    with pytest.raises(ValueError, match="original_source_sha_mismatch"):
        trace_external_footprint_first(raw, source_sha256="0" * 64, page_indices=(0,))


@pytest.mark.parametrize("pages", [(), (0, 0), (-1,), ("0",)])
def test_nonunique_or_invalid_page_scopes_refused(tmp_path, pages):
    raw = _plan(tmp_path, walls=True).read_bytes()
    with pytest.raises(ValueError, match="unique_topology_pages"):
        trace_external_footprint_first(
            raw, source_sha256=hashlib.sha256(raw).hexdigest(), page_indices=pages,
        )


def test_original_production_collector_calls_exterior_before_wall_or_room(tmp_path, monkeypatch):
    path = _plan(tmp_path, walls=True)
    calls = []
    original = live.trace_external_footprint_first

    def trace(*args, **kwargs):
        calls.append("exterior")
        return original(*args, **kwargs)

    class StopAfterFirstGeometry(Exception):
        pass

    def wall(*args, **kwargs):
        calls.append("wall_opening")
        assert calls == ["exterior", "wall_opening"]
        raise StopAfterFirstGeometry

    monkeypatch.setattr(live, "trace_external_footprint_first", trace)
    monkeypatch.setattr(live, "compose_live_wall_opening_authority", wall)
    with pytest.raises(StopAfterFirstGeometry):
        live.collect_live_physical_net_wall_claim(path, pages=(0,), topology_pages=(0,))
    assert calls == ["exterior", "wall_opening"]

def test_bounded_source_viewport_preserves_original_path_indices(tmp_path):
    from pb_external_footprint_first_trace import (
        bound_native_drawings_to_footprint,
    )

    path = _plan(tmp_path, walls=True)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    (trace,) = trace_external_footprint_first(
        raw, source_sha256=sha, page_indices=(0,),
    )
    with fitz.open(stream=raw, filetype="pdf") as doc:
        original_drawings = tuple(doc[0].get_drawings())
    cropped = bound_native_drawings_to_footprint(
        original_drawings, trace=trace, expected_source_sha256=sha,
    )
    assert cropped.status == "CANDIDATE"
    assert len(cropped.drawings) == len(original_drawings)
    assert cropped.selected_source_path_indices
    for i in range(len(original_drawings)):
        if i in cropped.selected_source_path_indices:
            assert cropped.drawings[i] is original_drawings[i]
        else:
            assert cropped.drawings[i].get("items") == ()
    assert cropped.source_total_paths == len(original_drawings)
    assert cropped.commercial_publishable is False


def test_bounded_viewport_rejects_foreign_revision(tmp_path):
    from pb_external_footprint_first_trace import (
        bound_native_drawings_to_footprint,
    )

    raw = _plan(tmp_path, walls=True).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    trace = trace_external_footprint_first(
        raw, source_sha256=sha, page_indices=(0,),
    )[0]
    with pytest.raises(ValueError, match="source_revision_mismatch"):
        bound_native_drawings_to_footprint(
            (), trace=trace, expected_source_sha256="f" * 64,
        )


def test_bounded_viewport_does_not_bypass_20000_source_primitives(tmp_path):
    from pb_external_footprint_first_trace import (
        bound_native_drawings_to_footprint,
    )

    raw = _plan(tmp_path, walls=True).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    trace = trace_external_footprint_first(
        raw, source_sha256=sha, page_indices=(0,),
    )[0]
    # One authentic path index with 20001 candidate item operations:
    # the cap is on primitives, NOT count of path containers.
    heavy = {
        "rect": fitz.Rect(250, 150, 330, 240),
        "layer": "WALL",
        "fill": None,
        "color": (0, 0, 0),
        "items": (("l", (0, 0), (1, 1)),) * 20_001,
    }
    result = bound_native_drawings_to_footprint(
        (heavy,), trace=trace, expected_source_sha256=sha,
    )
    assert result.status == "ABSTAINED"
    assert result.wall_native_primitive_count > 20_000
    assert result.drawings == ()
    assert result.selected_source_path_indices == ()
    assert result.reason == "bounded_source_viewport_exceeds_20000_primitive_cap"

def test_read_only_original_footprint_first_cli_does_not_mint_quantities(tmp_path):
    from tools.run_original_footprint_first import run

    pdf = _plan(tmp_path, walls=True)
    result, json_path, png_path = run(pdf, 0, tmp_path / "private_result")
    assert result["stage_order"][0] == "source_hashed_exterior_ink_contour"
    assert result["bounded_source"]["source_path_indices_preserved"] is True
    assert result["commercial_quantity_rows"] == 0
    assert result["topology"]["room_quantity_authorized"] is False
    assert json_path.exists() and json_path.stat().st_size > 200
    assert png_path.exists() and png_path.stat().st_size > 200
    assert result["exterior"]["source_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
