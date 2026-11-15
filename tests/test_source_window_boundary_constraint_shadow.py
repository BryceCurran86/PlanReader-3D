"""Tests for source-owned window boundary constraints (P4 shadow).

Validates:
- External window versus glazed door sill continuity.
- Window sill closes 2D floor/room boundary while deducting opening void from wall.
- Challenge gates: missing jambs, foreign layers, one-end-short, unhosted.
- Real 3Laurel page 2 authentic window opening with exact source path IDs.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_wall_body_junction_graph_shadow import (
    SourcePathProvenance,
    SourceWallBodyRecord,
    GEOMETRY_OBSERVED,
)
from pb_source_window_boundary_constraint_shadow import (
    authenticate_window_boundary_constraint,
    REASON_FOREIGN_LAYER,
    REASON_GLAZED_DOOR,
    REASON_MISSING_JAMB,
    REASON_ONE_END_SHORT,
    REASON_UNHOSTED,
    REASON_WINDOW_VALID,
)


def _body(
    source_id: int, bounds: tuple[float, float, float, float]
) -> SourceWallBodyRecord:
    prov = SourcePathProvenance(
        native_path_ids=(source_id,),
        native_source_layers=("Enclosure_WallExternal",),
        viewport_id="vp1",
        page_index=0,
        geometry_kind=GEOMETRY_OBSERVED,
        role="exterior_outer_face_candidate",
    )
    return SourceWallBodyRecord(
        body_id=f"body:{source_id}",
        provenance=prov,
        bounds_pdf_pts=bounds,
        long_axis="h",
        status=EvidenceResolutionStatus.CANDIDATE,
        reason="test_body",
    )


def test_external_window_vs_glazed_door_sill_continuity():
    """Window closes 2D room boundary; glazed door connects floor."""
    left_wall = _body(1, (100.0, 100.0, 200.0, 110.0))
    right_wall = _body(2, (250.0, 100.0, 350.0, 110.0))

    left_jamb = {
        "rect": fitz.Rect(199.5, 100.0, 200.5, 110.0),
        "path_index": 10,
        "layer": "Enclosure_WallExternal",
    }
    right_jamb = {
        "rect": fitz.Rect(249.5, 100.0, 250.5, 110.0),
        "path_index": 11,
        "layer": "Enclosure_WallExternal",
    }
    sill = [{
        "rect": fitz.Rect(200.0, 100.0, 250.0, 100.5),
        "path_index": 12,
        "layer": "Enclosure_WallExternal",
    }]

    # Case A: Window callout W01
    win_res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="W01",
    )
    assert win_res.status == EvidenceResolutionStatus.CANDIDATE
    assert win_res.reason == REASON_WINDOW_VALID
    assert win_res.is_window_not_door is True
    assert win_res.closes_2d_room_boundary is True
    assert win_res.deducts_from_wall_surface is True
    assert win_res.measurement_authorized is False

    # Case B: Glazed Door callout D01 / SGD
    door_res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="D01 SGD",
    )
    assert door_res.status == EvidenceResolutionStatus.CANDIDATE
    assert door_res.reason == REASON_GLAZED_DOOR
    assert door_res.is_window_not_door is False
    assert door_res.closes_2d_room_boundary is False
    assert door_res.deducts_from_wall_surface is True


def test_challenge_segmented_glazing_missing_jamb_abstains():
    """Aperture with missing jamb fails closed."""
    left_wall = _body(1, (100.0, 100.0, 200.0, 110.0))
    right_wall = _body(2, (250.0, 100.0, 350.0, 110.0))
    sill = [{
        "rect": fitz.Rect(200.0, 100.0, 250.0, 100.5),
        "path_index": 12,
        "layer": "Enclosure_WallExternal",
    }]

    res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=None,
        right_jamb_drawing=None,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="W01",
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == REASON_MISSING_JAMB
    assert res.closes_2d_room_boundary is False


def test_challenge_foreign_layer_competitor_ink_abstains():
    """Sill drawing on competitor layer (e.g. Interior_Joinery) is rejected."""
    left_wall = _body(1, (100.0, 100.0, 200.0, 110.0))
    right_wall = _body(2, (250.0, 100.0, 350.0, 110.0))
    left_jamb = {
        "rect": fitz.Rect(199.5, 100.0, 200.5, 110.0),
        "path_index": 10,
        "layer": "Enclosure_WallExternal",
    }
    right_jamb = {
        "rect": fitz.Rect(249.5, 100.0, 250.5, 110.0),
        "path_index": 11,
        "layer": "Enclosure_WallExternal",
    }
    sill = [{
        "rect": fitz.Rect(200.0, 100.0, 250.0, 100.5),
        "path_index": 12,
        "layer": "Interior_Joinery",
    }]

    res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="W01",
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == REASON_FOREIGN_LAYER
    assert res.closes_2d_room_boundary is False


def test_challenge_one_end_short_sill_line_abstains():
    """Sill line that stops short of right jamb fails closed."""
    left_wall = _body(1, (100.0, 100.0, 200.0, 110.0))
    right_wall = _body(2, (250.0, 100.0, 350.0, 110.0))
    left_jamb = {
        "rect": fitz.Rect(199.5, 100.0, 200.5, 110.0),
        "path_index": 10,
        "layer": "Enclosure_WallExternal",
    }
    right_jamb = {
        "rect": fitz.Rect(249.5, 100.0, 250.5, 110.0),
        "path_index": 11,
        "layer": "Enclosure_WallExternal",
    }
    # Sill only reaches 230, not 250!
    sill = [{
        "rect": fitz.Rect(200.0, 100.0, 230.0, 100.5),
        "path_index": 12,
        "layer": "Enclosure_WallExternal",
    }]

    res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="W01",
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == REASON_ONE_END_SHORT
    assert res.closes_2d_room_boundary is False


def test_challenge_unhosted_aperture_abstains():
    """Aperture with missing structural wall bodies fails closed."""
    left_jamb = {
        "rect": fitz.Rect(199.5, 100.0, 200.5, 110.0),
        "path_index": 10,
        "layer": "Enclosure_WallExternal",
    }
    right_jamb = {
        "rect": fitz.Rect(249.5, 100.0, 250.5, 110.0),
        "path_index": 11,
        "layer": "Enclosure_WallExternal",
    }
    sill = [{
        "rect": fitz.Rect(200.0, 100.0, 250.0, 100.5),
        "path_index": 12,
        "layer": "Enclosure_WallExternal",
    }]

    res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=None,
        right_wall_body=None,
        callout_tag="W01",
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == REASON_UNHOSTED
    assert res.closes_2d_room_boundary is False


def test_real_3laurel_page2_window_path_ids_authentic():
    """Verify authentic 3Laurel page 2 window opening at x=307.636..333.431."""
    left_wall = _body(1183, (285.101, 457.753, 307.636, 460.305))
    right_wall = _body(1192, (333.431, 457.753, 356.392, 460.305))

    left_jamb = {
        "rect": fitz.Rect(307.636, 457.470, 307.636, 460.588),
        "path_index": 1451,
        "layer": "Enclosure_WallExternal",
    }
    right_jamb = {
        "rect": fitz.Rect(333.431, 457.470, 333.431, 460.588),
        "path_index": 1452,
        "layer": "Enclosure_WallExternal",
    }
    sill = [{
        "rect": fitz.Rect(307.636, 457.470, 333.431, 457.470),
        "path_index": 1450,
        "layer": "Enclosure_WallExternal",
    }]

    res = authenticate_window_boundary_constraint(
        sill_drawings=sill,
        left_jamb_drawing=left_jamb,
        right_jamb_drawing=right_jamb,
        left_wall_body=left_wall,
        right_wall_body=right_wall,
        callout_tag="1,800 - 910 asw",
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.reason == REASON_WINDOW_VALID
    assert res.is_window_not_door is True
    assert res.closes_2d_room_boundary is True
    assert res.deducts_from_wall_surface is True
    assert res.left_jamb_path_id == 1451
    assert res.right_jamb_path_id == 1452
    assert res.sill_path_ids == (1450,)
    assert round(res.clear_width_pts, 2) == 25.79  # 910mm at 1:100 scale (25.795 pt)
    assert res.measurement_authorized is False
    assert res.physical_opening_authenticated is False
