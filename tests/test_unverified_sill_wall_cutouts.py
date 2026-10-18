"""Regression guards: inferred window elevations and review-only positions are not holes."""
import json

import pytest

from pb_opening_deductions_v134 import normalise_opening
from pb_opening_geometry_v137 import attach_openings
from pb_unified_building_v139 import _opening_rects, build_figure


class RegisterApp:
    def __init__(self, register):
        self.register = register
        self.saved = None

    def workspace_setting(self, workspace_id, key, default):
        return json.dumps(self.register)

    def set_workspace_setting(self, workspace_id, key, value):
        self.saved = json.loads(value)

    normalise_opening = staticmethod(normalise_opening)


def test_legacy_window_does_not_invent_sill_count_or_wall_cutout():
    app = RegisterApp([{
        "id": "W01", "kind": "Window", "wall_ref": "N01",
        "width_m": 1.2, "height_m": 1.5,
    }])
    attached = attach_openings(app, 1, [{"wall_ref": "N01", "length_m": 6.0}])
    assert len(attached) == 1
    window = attached[0]
    assert window["quantity"] == 0
    assert window["area_m2"] == 0.0
    assert window["sill_m"] is None
    assert "Visual centre placement" in window["geometry_status"]
    assert _opening_rects(attached, "N01", 6.0, 3.0) == []
    assert app.saved == attached


def test_legacy_door_has_floor_threshold_but_not_a_proven_location():
    app = RegisterApp([{
        "id": "D01", "kind": "Door", "wall_ref": "N01",
        "width_m": 0.9, "height_m": 2.1, "quantity": 1,
    }])
    attached = attach_openings(app, 1, [{"wall_ref": "N01", "length_m": 6.0}])
    assert attached[0]["sill_m"] == 0.0
    assert _opening_rects(attached, "N01", 6.0, 3.0) == []


@pytest.mark.parametrize("extra", [
    {"offset_m": 1.0},  # unknown sill
    {"sill_m": 0.9},    # unknown wall position
    {"offset_m": float("nan"), "sill_m": 0.9},
    {"offset_m": 1.0, "sill_m": True},
    {"offset_m": -1.0, "sill_m": 0.9},
    {"offset_m": 5.2, "sill_m": 0.9},  # extends beyond wall
    {"offset_m": 1.0, "sill_m": 2.5},  # extends above wall
    {"offset_m": 1.0, "sill_m": 0.9,
     "geometry_status": "Visual centre placement; position needs elevation evidence"},
])
def test_3d_geometry_rejects_unproven_cutout(extra):
    row = {"resolved_wall_ref": "N01", "width_m": 1.2, "height_m": 1.0, **extra}
    assert _opening_rects([row], "N01", 6.0, 3.0) == []


def test_explicit_finite_position_sill_and_dimensions_allow_real_cutout():
    row = {
        "resolved_wall_ref": "N01", "width_m": 1.2,
        "height_m": 1.0, "offset_m": 2.0, "sill_m": 0.9,
        "geometry_status": "Position verified against elevation",
    }
    assert _opening_rects([row], "N01", 6.0, 3.0) == [(2.0, 3.2, 0.9, 1.9)]


def test_outline_label_stays_with_its_own_valid_opening():
    unknown = {
        "resolved_wall_ref": "N01", "label": "Unplaced W01",
        "width_m": 1.0, "height_m": 1.0, "sill_m": None, "offset_m": 0.0,
    }
    known = {
        "resolved_wall_ref": "N01", "label": "Verified W02",
        "width_m": 1.0, "height_m": 1.0, "sill_m": 0.9, "offset_m": 3.0,
    }
    wall = {
        "wall_ref": "N01", "side": "North", "a": (0.0, 0.0),
        "b": (6.0, 0.0), "height_m": 3.0,
        "openings": [unknown, known],
    }
    figure = build_figure([wall])
    outlines = [trace.name for trace in figure.data if trace.type == "scatter3d"]
    assert outlines == ["Verified W02"]
