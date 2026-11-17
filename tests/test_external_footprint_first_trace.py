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
    assert result["topology"]["source_gap_witness_count"] >= 0
    assert len(result["topology"]["source_gap_witnesses_sample"]) <= 64
    assert all(w["can_issue_area"] is False and
               w["source_path_side_partition_proven"] is False
               for w in result["topology"]["source_gap_witnesses_sample"])
    assert "magenta" in result["overlay"]["legend"]
    assert json_path.exists() and json_path.stat().st_size > 200
    assert png_path.exists() and png_path.stat().st_size > 200
    assert result["exterior"]["source_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()


def test_raster_candidate_with_no_original_wall_ink_abstains(tmp_path):
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace,
        bound_native_drawings_to_footprint,
    )

    sha = "a" * 64
    trace = ExternalFootprintTrace(
        source_sha256=sha,
        page_index=1,
        status="CANDIDATE",
        reason="visual_only",
        polygon_pdf_pts=((10, 10), (100, 10), (100, 100), (10, 100)),
        bbox_pdf_pts=(10, 10, 100, 100),
    )
    # Both native paths are genuine source rows, but neither contributes
    # source wall paint within the raster candidate's local viewport.
    drawings = (
        {"rect": fitz.Rect(300, 300, 310, 310),
         "layer": "Enclosure_WallExternal",
         "fill": (0, 0, 0),
         "items": (("l", fitz.Point(300, 300), fitz.Point(310, 310)),)},
        {"rect": fitz.Rect(20, 20, 30, 30),
         "layer": "Annotations",
         "fill": None, "color": (0.8, 0.8, 0.8),
         "items": (("l", fitz.Point(20, 20), fitz.Point(30, 30)),)},
    )
    result = bound_native_drawings_to_footprint(
        drawings, trace=trace, expected_source_sha256=sha,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "bounded_source_viewport_has_no_native_wall_ink"
    assert result.wall_native_primitive_count == 0
    assert result.drawings == ()
    assert result.selected_source_path_indices == ()
    assert result.source_total_paths == len(drawings)
    assert result.commercial_publishable is False


def test_raster_candidate_empty_native_list_cannot_be_candidate():
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace,
        bound_native_drawings_to_footprint,
    )

    sha = "b" * 64
    trace = ExternalFootprintTrace(
        sha, 1, "CANDIDATE", "visual_only",
        bbox_pdf_pts=(0, 0, 100, 100),
    )
    result = bound_native_drawings_to_footprint(
        (), trace=trace, expected_source_sha256=sha,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "bounded_source_viewport_has_no_native_wall_ink"
    assert result.wall_native_primitive_count == 0
    assert result.source_total_paths == 0
    assert result.commercial_publishable is False


def test_original_acacia_regional_sha_pins_are_distinct_and_fail_closed():
    """Source-backed SHA identities, no private PDF bytes committed."""
    from tools.run_original_footprint_first import _enforce_original_source_sha_pin

    brisbane = "435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a"
    sydney = "f5ac166a21c9348c5ee55a7e518ec487140e9888d8af21fa39dbc5a9ca28000e"
    melbourne = "fcc5e032968f62028dd4254db61bb676582027655881ecbad7a21001ef12cd2a"
    assert len({brisbane, sydney, melbourne}) == 3
    assert _enforce_original_source_sha_pin(brisbane, brisbane) is True
    assert _enforce_original_source_sha_pin(brisbane, None) is False
    for different_original in (sydney, melbourne):
        with pytest.raises(ValueError, match="original_footprint_source_sha256_mismatch"):
            _enforce_original_source_sha_pin(different_original, brisbane)


@pytest.mark.parametrize("bad", [
    "a" * 63, "a" * 65, "A" * 64, "g" * 64, "", 123, True,
])
def test_original_footprint_sha_pin_requires_full_lowercase_hex(bad):
    from tools.run_original_footprint_first import _enforce_original_source_sha_pin

    with pytest.raises(ValueError, match="original_footprint_expected_sha256_invalid"):
        _enforce_original_source_sha_pin("a" * 64, bad)


def test_original_footprint_runner_fails_before_geometry_or_files_on_wrong_pin(
    tmp_path, monkeypatch,
):
    import tools.run_original_footprint_first as runner

    original = _plan(tmp_path, walls=True)
    invoked = []

    def never_trace(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("must refuse foreign revision before tracing")

    monkeypatch.setattr(runner, "trace_external_footprint_first", never_trace)
    destination = tmp_path / "pinned_output"
    with pytest.raises(ValueError, match="original_footprint_source_sha256_mismatch"):
        runner.run(original, 0, destination, expected_sha256="f" * 64)
    assert invoked == []
    assert not destination.exists()


def test_original_footprint_runner_reports_verified_source_pin_without_firm(tmp_path):
    from tools.run_original_footprint_first import run

    original = _plan(tmp_path, walls=True)
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    output, report, overlay = run(
        original, 0, tmp_path / "pinned_result", expected_sha256=sha,
    )
    assert output["source_sha256"] == sha
    assert output["source_sha_pin_verified"] is True
    assert output["commercial_quantity_rows"] == 0
    assert output["topology"]["room_quantity_authorized"] is False
    assert report.is_file() and overlay.is_file()


def test_original_page_title_pin_blocks_wrong_page_before_tracing(tmp_path, monkeypatch):
    import tools.run_original_footprint_first as runner

    original = _plan(tmp_path, walls=True)
    with fitz.open(original) as document:
        document[0].insert_text((40, 30), "Floor Plan", fontsize=12)
        document.saveIncr()
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    destination = tmp_path / "wrong_page_result"
    calls = []

    def never_trace(*args, **kwargs):
        calls.append(True)
        raise AssertionError("wrong source page must never trace")

    monkeypatch.setattr(runner, "trace_external_footprint_first", never_trace)
    with pytest.raises(ValueError, match="original_footprint_original_page_title_mismatch"):
        runner.run(
            original, 0, destination, expected_sha256=sha,
            expected_drawing_title="Site Plan",
        )
    assert calls == []
    assert not destination.exists()


def test_original_page_title_pin_verified_on_matching_floor_plan(tmp_path):
    from tools.run_original_footprint_first import run

    original = _plan(tmp_path, walls=True)
    with fitz.open(original) as document:
        document[0].insert_text((40, 30), "Floor Plan", fontsize=12)
        document.saveIncr()
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    result, report, overlay = run(
        original, 0, tmp_path / "verified_page_result",
        expected_sha256=sha, expected_drawing_title="Floor Plan",
    )
    assert result["source_sha_pin_verified"] is True
    assert result["source_page_title_verified"] is True
    assert result["commercial_quantity_rows"] == 0
    assert report.exists() and overlay.exists()


@pytest.mark.parametrize("invalid_title", ["", " ", "a" * 101, 17, True])
def test_original_page_title_pin_rejects_invalid_expectations(invalid_title):
    from tools.run_original_footprint_first import _verify_original_drawing_title

    with pytest.raises(ValueError, match="original_footprint_expected_page_title_invalid"):
        _verify_original_drawing_title(b"not a pdf", 0, invalid_title)


def test_unattempted_original_gap_review_does_not_report_false_zero(tmp_path):
    from tools.run_original_footprint_first import run

    original = _plan(tmp_path, walls=False)
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    result, report, overlay = run(
        original, 0, tmp_path / "abstained_original", expected_sha256=sha,
    )
    assert result["exterior"]["status"] == "ABSTAINED"
    assert result["bounded_source"]["status"] == "ABSTAINED"
    assert result["topology"]["status"] == "ABSTAINED"
    assert result["topology"]["gap_review_performed"] is False
    assert result["topology"]["unresolved_collinear_gap_count"] is None
    assert result["topology"]["source_gap_witness_count"] is None
    assert result["topology"]["room_quantity_authorized"] is False
    assert result["commercial_quantity_rows"] == 0
    assert report.exists() and overlay.exists()


def test_acacia_wrapped_window_and_door_schedule_page_title(tmp_path):
    """Original Acacia p10 has Window / and Door Schedule on separate PDF lines."""
    from tools.run_original_footprint_first import _verify_original_drawing_title

    pdf = tmp_path / "original_schedule.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((30, 45), "Window\\nand Door Schedule")
        document.save(pdf)
    raw = pdf.read_bytes()
    assert _verify_original_drawing_title(
        raw, 0, "Window and Door Schedule",
    ) is True
    with pytest.raises(ValueError, match="original_footprint_original_page_title_mismatch"):
        _verify_original_drawing_title(raw, 0, "Setout Plan")
