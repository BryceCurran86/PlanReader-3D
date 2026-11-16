"""Synthetic source-role, heavy-stroke, junction and false-bridge tests."""
from __future__ import annotations

import fitz
import pytest

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_source_heavy_stroke_strips,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_wall_role_and_junction_shadow import (
    ROLE_ATTACHED_STRUCTURE,
    ROLE_DIAGONAL_BRIDGE,
    ROLE_EXCLUSION,
    ROLE_EXTERIOR_OUTER_FACE,
    ROLE_INTERNAL_WALL,
    classify_native_path_role,
    identify_source_wall_junctions_and_roles,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA, strip


def _stroke(a, b, *, width=1.92, color=(0.0, 0.0, 0.0), opacity=1.0, dashes="", layer=""):
    return {
        "type": "s",
        "layer": layer,
        "fill": None,
        "color": color,
        "width": width,
        "stroke_opacity": opacity,
        "dashes": dashes,
        "rect": fitz.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])),
        "items": (("l", fitz.Point(*a), fitz.Point(*b)),),
    }


def test_heavy_black_strokes_are_wall_bands_not_double_line_dependent():
    walls = [
        _stroke((100, 100), (400, 100)),
        _stroke((400, 100), (400, 350)),
        _stroke((400, 350), (100, 350)),
        _stroke((100, 350), (100, 100)),
    ]
    assert len(_collect_source_heavy_stroke_strips(walls)) == 4
    result = build_layered_wall_doorway_room_rings(
        walls, source_sha256=SHA, page_index=0,
        source_heavy_stroke_wall_bands=True,
    )
    assert result.wall_strip_count >= 4
    assert all(not ring.commercial_projection_allowed for ring in result.rings)
    negatives = [
        _stroke((0, 0), (50, 0), width=0.48),
        _stroke((0, 10), (60, 10), color=(0.1, 0.9, 0.1)),
        _stroke((0, 20), (60, 20), opacity=0.5),
        _stroke((0, 30), (60, 30), width=1.92, color=(0.8, 0.1, 0.0)),
        _stroke((0, 40), (10, 40), width=1.92),
        _stroke((0, 50), (40, 90), width=1.92),
    ]
    assert _collect_source_heavy_stroke_strips(negatives) == []


def test_default_off_heavy_stroke_flag_does_not_change_named_wall_rooms():
    rows = strip(0, 0, 100, 2) + strip(0, 2, 2, 98) + strip(0, 98, 100, 100) + strip(98, 2, 100, 98)
    off = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    on = build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0, source_heavy_stroke_wall_bands=True,
    )
    assert off.wall_strip_count == on.wall_strip_count
    assert off.unresolved_gap_count == on.unresolved_gap_count


def test_dashed_green_title_and_dimension_layers_are_exclusions():
    assert classify_native_path_role(
        _stroke((0, 0), (80, 0), dashes="[3 2] 0"), 0,
    ) == ROLE_EXCLUSION
    assert classify_native_path_role(
        _stroke((0, 10), (80, 10), color=(0.1, 0.9, 0.1)), 1,
    ) == ROLE_EXCLUSION
    assert classify_native_path_role(
        _stroke((0, 20), (80, 20), layer="A-ANNO-DIMS"), 2,
    ) == ROLE_EXCLUSION
    title = _stroke((10, 700), (200, 700), layer="Title_Block")
    title["rect"] = fitz.Rect(10, 700, 200, 710)
    assert classify_native_path_role(
        title, 3, page_bounds=(0.0, 0.0, 400.0, 800.0),
    ) == ROLE_EXCLUSION


def test_diagonal_furniture_and_dimension_leaders_are_rejected_bridges():
    assert classify_native_path_role(
        _stroke((210, 130), (800, 490), width=0.2), 0,
    ) == ROLE_DIAGONAL_BRIDGE
    assert classify_native_path_role(
        _stroke((300, 200), (420, 340), layer="Dimension"), 1,
    ) == ROLE_EXCLUSION


def test_explicit_wall_layer_is_internal_until_outer_face_is_owned():
    row = strip(0, 0, 100, 2)[0]
    assert classify_native_path_role(row, 0) == ROLE_INTERNAL_WALL
    assert classify_native_path_role(
        row, 0, exterior_owner_indices=frozenset({0}),
    ) == ROLE_EXTERIOR_OUTER_FACE
    assert classify_native_path_role(
        row, 0, attached_indices=frozenset({0}),
    ) == ROLE_ATTACHED_STRUCTURE


def test_three_unwitnessed_collinear_gaps_are_not_invented_doors():
    rows = (
        strip(0, 0, 400, 2)
        + strip(0, 2, 2, 298)
        + strip(0, 298, 400, 300)
        + strip(398, 2, 400, 20)
        + strip(398, 50, 400, 70)
        + strip(398, 120, 400, 140)
        + strip(398, 242, 400, 298)
    )
    report = identify_source_wall_junctions_and_roles(
        rows, source_sha256=SHA, page_index=0,
    )
    assert report.measurement_authorized is False
    assert report.commercial_publishable is False
    assert report.invented_door_bridge_count >= 3
    assert all(span["can_issue_area"] is False for span in report.unresolved_open_spans)
    assert all(span["missing_jamb_opening_evidence"] for span in report.unresolved_open_spans)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert result.closures == ()


def test_wide_unwitnessed_span_is_still_not_a_door_with_roles():
    rows = (
        strip(0, 0, 400, 2)
        + strip(0, 2, 2, 298)
        + strip(0, 298, 400, 300)
        + strip(398, 2, 400, 20)
        + strip(398, 242, 400, 298)
    )
    report = identify_source_wall_junctions_and_roles(
        rows, source_sha256=SHA, page_index=0,
    )
    widths = [
        span["gap_interval_pdf_pts"][1] - span["gap_interval_pdf_pts"][0]
        for span in report.unresolved_open_spans
    ]
    assert any(width == pytest.approx(222.0) for width in widths)
    assert all(span["opening_authenticated"] is False for span in report.unresolved_open_spans)


def test_raster_hull_is_not_a_wall_and_report_stays_abstained():
    trace = ExternalFootprintTrace(
        source_sha256=SHA, page_index=0, status="CANDIDATE",
        reason="test", polygon_pdf_pts=((100, 100), (400, 100), (400, 350), (100, 350)),
        bbox_pdf_pts=(100, 100, 400, 350), candidate_count=1,
    )
    report = identify_source_wall_junctions_and_roles(
        [], source_sha256=SHA, page_index=0, trace=trace,
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.filled_strip_count == 0
    assert report.heavy_stroke_band_count == 0
    assert report.measurement_authorized is False


def test_heavy_stroke_closed_rectangle_has_no_invented_bridge():
    walls = [
        _stroke((100, 100), (400, 100)),
        _stroke((400, 100), (400, 350)),
        _stroke((400, 350), (100, 350)),
        _stroke((100, 350), (100, 100)),
    ]
    report = identify_source_wall_junctions_and_roles(
        walls, source_sha256=SHA, page_index=0,
    )
    assert report.heavy_stroke_band_count == 4
    assert report.invented_door_bridge_count == 0
    assert report.rejected_diagonal_bridge_count == 0
    assert report.to_dict()["can_issue_area"] is False
    assert report.to_dict()["measurement_authorized"] is False
