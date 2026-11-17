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


@pytest.mark.parametrize("width,height", [
    (100., 0.), (100., -1.), (100., float("nan")),
    (100., float("inf")), (float("nan"), 100.), (0., 100.),
])
def test_acacia_bounded_raster_rejects_invalid_page_axes(width, height):
    from pb_external_footprint_first_trace import _bounded_raster_scale
    with pytest.raises(ValueError, match="external_footprint_invalid_page_dimensions"):
        _bounded_raster_scale(width, height)


@pytest.mark.parametrize("width,height", [(4000., 1000.), (1000., 4000.), (12000., 8000.)])
def test_acacia_raster_cap_never_exceeds_2400px(width, height):
    from pb_external_footprint_first_trace import _bounded_raster_scale
    scale = _bounded_raster_scale(width, height)
    assert 0. < scale <= 1.8
    assert max(width, height) * scale <= 2400. + 1e-9


def test_two_disconnected_buildings_do_not_get_selected_as_one_external_footprint(tmp_path):
    path = tmp_path / "two_buildings.pdf"
    doc = fitz.open()
    page = doc.new_page(width=1100, height=780)
    page.draw_rect(fitz.Rect(125, 130, 480, 470), color=(0, 0, 0), width=4)
    page.draw_rect(fitz.Rect(615, 130, 970, 470), color=(0, 0, 0), width=4)
    doc.save(path)
    doc.close()
    raw = path.read_bytes()
    (result,) = trace_external_footprint_first(
        raw, source_sha256=hashlib.sha256(raw).hexdigest(), page_indices=(0,),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "external_footprint_competing_disjoint_envelopes"
    assert result.candidate_count >= 2
    assert result.polygon_pdf_pts == ()
    assert result.commercial_publishable is False
    assert result.measurement_authorized is False


def test_nested_raster_outlines_from_one_thick_wall_are_not_competing():
    from pb_external_footprint_first_trace import _competing_disjoint_envelopes
    ranked = ((10000., (100, 100, 220, 190), object()),
              (9500., (104, 103, 212, 184), object()))
    assert _competing_disjoint_envelopes(ranked) is False


def test_refined_footprint_recalculates_bbox_after_false_top_box_removal(monkeypatch):
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace, refine_external_footprint_against_wall_ink,
    )
    from pb_source_unsupported_rectangular_detour_shadow import RectangularDetourCollapseReceipt
    import pb_source_unsupported_rectangular_detour_shadow as detours

    candidate = ExternalFootprintTrace(
        "a" * 64, 0, "CANDIDATE", "visual_only",
        polygon_pdf_pts=((0., 100.), (40., 100.), (40., 40.),
                         (70., 40.), (70., 100.), (200., 100.),
                         (200., 300.), (0., 300.)),
        bbox_pdf_pts=(0., 40., 200., 300.),
    )
    expected = ((0., 100.), (40., 100.), (70., 100.),
                (200., 100.), (200., 300.), (0., 300.))
    monkeypatch.setattr(
        detours, "collapse_unsupported_rectangular_detours",
        lambda polygon, members: RectangularDetourCollapseReceipt(
            original_vertex_count=8, repaired_vertex_count=6,
            collapsed_detour_count=1, polygon_pdf_pts=expected,
            reason_codes=("collapsed_unsupported_rectangular_detour",),
        ),
    )
    refined, receipt = refine_external_footprint_against_wall_ink(candidate, ())
    assert receipt["collapsed_detour_count"] == 1
    assert refined.polygon_pdf_pts == expected
    assert refined.bbox_pdf_pts == (0., 100., 200., 300.)
    assert refined.source_sha256 == candidate.source_sha256
    assert refined.page_index == candidate.page_index
    assert refined.commercial_publishable is False
    assert refined.measurement_authorized is False


def test_unrepaired_footprint_keeps_its_original_raster_bbox():
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace, refine_external_footprint_against_wall_ink,
    )
    candidate = ExternalFootprintTrace(
        "a" * 64, 0, "CANDIDATE", "visual_only",
        polygon_pdf_pts=((0., 100.), (200., 100.), (200., 300.), (0., 300.)),
        bbox_pdf_pts=(-2., 98., 202., 302.),
    )
    refined, receipt = refine_external_footprint_against_wall_ink(candidate, ())
    assert receipt["collapsed_detour_count"] == 0
    assert refined.bbox_pdf_pts == candidate.bbox_pdf_pts


def test_refine_seam_collapses_unmatched_stub_and_outward_tip():
    """NE unmatched stub + NW tip must both land through refine, not only the helper."""
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace, refine_external_footprint_against_wall_ink,
    )

    candidate = ExternalFootprintTrace(
        "e" * 64, 1, "CANDIDATE", "visual_only",
        polygon_pdf_pts=(
            (328.0, 140.0),
            (328.0, 449.0),
            (311.0, 450.0),
            (910.0, 450.0),
            (903.9, 448.9),
            (903.9, 140.0),
        ),
        bbox_pdf_pts=(310.0, 138.0, 912.0, 452.0),
    )
    # Named dark wall paths so wall_ink_segments_from_drawings keeps them.
    drawings = (
        {
            "layer": "Enclosure_WallExternal",
            "color": (0.05, 0.05, 0.05),
            "fill": None,
            "items": (
                ("l", fitz.Point(328.0, 140.0), fitz.Point(328.0, 449.0)),
                ("l", fitz.Point(328.0, 449.0), fitz.Point(904.0, 449.0)),
                ("l", fitz.Point(331.0, 449.5), fitz.Point(311.0, 449.5)),
                ("l", fitz.Point(904.0, 140.0), fitz.Point(904.0, 449.0)),
                ("l", fitz.Point(328.0, 140.0), fitz.Point(904.0, 140.0)),
            ),
        },
    )
    refined, receipt = refine_external_footprint_against_wall_ink(candidate, drawings)
    assert receipt["collapsed_detour_count"] >= 1
    codes = set(receipt["reason_codes"])
    assert "collapsed_outward_corner_tip_excursion" in codes
    assert "collapsed_unmatched_morphological_corner_stub" in codes
    assert (311.0, 450.0) not in refined.polygon_pdf_pts
    assert (910.0, 450.0) not in refined.polygon_pdf_pts
    assert (328.0, 450.0) in refined.polygon_pdf_pts
    assert (903.9, 450.0) in refined.polygon_pdf_pts or (904.0, 450.0) in {
        (round(x, 1), round(y, 1)) for x, y in refined.polygon_pdf_pts
    }
    assert receipt["measurement_authorized"] is False
    assert receipt["commercial_publishable"] is False


def test_mid_gray_doorway_evidence_does_not_count_as_wall_support_primitives():
    """Gray glazing/doorway strokes stay indexable but never alone authorize a scope."""
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace,
        bound_native_drawings_to_footprint,
    )

    sha = "d" * 64
    trace = ExternalFootprintTrace(
        sha, 0, "CANDIDATE", "visual_only",
        polygon_pdf_pts=((10., 10.), (100., 10.), (100., 100.), (10., 100.)),
        bbox_pdf_pts=(10., 10., 100., 100.),
    )
    gray_only = (
        {
            "rect": fitz.Rect(20, 20, 80, 80),
            "layer": "Enclosure_WallExternal",
            "fill": None,
            "color": (0.55, 0.55, 0.55),
            "items": tuple(
                ("l", fitz.Point(20 + i, 20), fitz.Point(20 + i, 80))
                for i in range(30)
            ),
        },
    )
    result = bound_native_drawings_to_footprint(
        gray_only, trace=trace, expected_source_sha256=sha,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "bounded_source_viewport_has_no_native_wall_ink"
    assert result.wall_native_primitive_count == 0
    assert result.commercial_publishable is False


@pytest.mark.parametrize("coords", [
    (40., 40., 20., 50.), (40., 40., 50., 20.),
])
def test_inverted_native_path_bbox_cannot_authenticate_wall_ink(coords):
    from types import SimpleNamespace
    from pb_external_footprint_first_trace import (
        ExternalFootprintTrace, bound_native_drawings_to_footprint,
    )
    sha = "c" * 64
    trace = ExternalFootprintTrace(
        sha, 0, "CANDIDATE", "source_review",
        polygon_pdf_pts=((10., 10.), (100., 10.), (100., 100.), (10., 100.)),
        bbox_pdf_pts=(10., 10., 100., 100.),
    )
    invalid_source = {
        "rect": SimpleNamespace(x0=coords[0], y0=coords[1],
                                x1=coords[2], y1=coords[3]),
        "layer": "Enclosure_WallExternal",
        "color": (0., 0., 0.), "fill": (0., 0., 0.),
        "items": (("l", fitz.Point(20, 20), fitz.Point(80, 20)),),
    }
    result = bound_native_drawings_to_footprint(
        (invalid_source,), trace=trace, expected_source_sha256=sha,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "bounded_source_viewport_has_no_native_wall_ink"
    assert result.wall_native_primitive_count == 0
    assert result.selected_source_path_indices == ()
    assert result.commercial_publishable is False
