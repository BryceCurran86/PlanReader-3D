"""Pure-function tests for the layered floor-plan first-gate census (diagnostic only)."""
from __future__ import annotations

from types import SimpleNamespace

import fitz

from tools.diag_layered_floor_plan_first_gate import (
    figured_dimension_face_ties,
    is_wall_layer,
    ring_figured_box_ties,
    layer_census,
    wall_layer_axis_faces,
)


def _filled_wall(layer: str, x0: float, y0: float, x1: float, y1: float, dx: float = 0.0, dy: float = 0.0) -> dict:
    rect = fitz.Rect(x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    return {"layer": layer, "fill": (0.0, 0.0, 0.0), "items": [("re", rect)]}


def _dim(orientation: str, a: tuple[float, float], b: tuple[float, float]) -> SimpleNamespace:
    return SimpleNamespace(orientation=orientation, endpoints_pt=(a, b))


def test_wall_layer_predicate_is_a_case_insensitive_substring_on_camel_case_names():
    assert is_wall_layer("Enclosure_WallInternal")
    assert is_wall_layer("Structure_WallRetaining")
    assert not is_wall_layer("Interior_Joinery")
    assert not is_wall_layer("Finish_Floor")
    assert not is_wall_layer(None)
    assert not is_wall_layer("")


def test_layer_census_counts_drawings_and_existing_w2_exclusions_separately():
    drawings = [
        {"layer": "Enclosure_WallInternal"},
        {"layer": "Enclosure_WallInternal"},
        {"layer": "Annotation_FloorPlan"},  # excluded by the existing dimension/annotation rule
        {"layer": "Interior_Joinery"},  # not excluded today: the pollution this tool measures
        {"layer": None},
    ]
    census = layer_census(drawings)
    assert census["Enclosure_WallInternal"] == {"drawings": 2, "excluded_by_existing_w2_layer_rules": 0}
    assert census["Annotation_FloorPlan"] == {"drawings": 1, "excluded_by_existing_w2_layer_rules": 1}
    assert census["Interior_Joinery"] == {"drawings": 1, "excluded_by_existing_w2_layer_rules": 0}
    assert census[""] == {"drawings": 1, "excluded_by_existing_w2_layer_rules": 0}


def test_only_filled_wall_layer_paths_yield_faces():
    drawings = [
        _filled_wall("Enclosure_WallInternal", 10, 20, 20, 120),
        {"layer": "Enclosure_WallInternal", "fill": None, "items": [("re", fitz.Rect(0, 0, 5, 5))]},  # outline only
        _filled_wall("Interior_Joinery", 50, 50, 60, 90),  # right shape, wrong layer
    ]
    vertical, horizontal = wall_layer_axis_faces(drawings)
    assert sorted(v[0] for v in vertical) == [10.0, 20.0]
    assert sorted(h[0] for h in horizontal) == [20.0, 120.0]


def test_straight_line_items_of_a_filled_wall_path_are_faces_and_diagonals_are_not():
    row = {
        "layer": "Enclosure_WallExternal",
        "fill": (0.0, 0.0, 0.0),
        "items": [
            ("l", fitz.Point(0, 0), fitz.Point(0, 40)),
            ("l", fitz.Point(0, 40), fitz.Point(10, 40)),
            ("l", fitz.Point(10, 40), fitz.Point(25, 55)),  # diagonal: never an axis face
        ],
    }
    vertical, horizontal = wall_layer_axis_faces([row])
    assert vertical == [(0.0, 0.0, 40.0)]
    assert horizontal == [(40.0, 0.0, 10.0)]


def test_dimension_tie_needs_both_extents_on_a_face_of_the_matching_axis():
    drawings = [_filled_wall("Enclosure_WallInternal", 100, 0, 110, 300), _filled_wall("Enclosure_WallInternal", 200, 0, 210, 300)]
    vertical, horizontal = wall_layer_axis_faces(drawings)
    both = _dim("horizontal", (110.0, 500.0), (200.0, 500.0))
    one_off = _dim("horizontal", (110.0, 500.0), (260.0, 500.0))
    wrong_axis = _dim("vertical", (110.0, 500.0), (200.0, 500.0))
    result = figured_dimension_face_ties([both, one_off, wrong_axis], vertical, horizontal, tolerance_pt=0.05)
    assert result == {"figured_dimensions": 3, "both_extents_on_wall_layer_face": 1}


def test_dimension_tie_tolerance_is_a_hard_bound():
    vertical, horizontal = wall_layer_axis_faces([_filled_wall("Enclosure_WallInternal", 100, 0, 110, 300)])
    near = _dim("horizontal", (110.04, 0.0), (100.0, 0.0))
    far = _dim("horizontal", (110.4, 0.0), (100.0, 0.0))
    assert figured_dimension_face_ties([near], vertical, horizontal, tolerance_pt=0.05)["both_extents_on_wall_layer_face"] == 1
    assert figured_dimension_face_ties([far], vertical, horizontal, tolerance_pt=0.05)["both_extents_on_wall_layer_face"] == 0
    assert figured_dimension_face_ties([far], vertical, horizontal, tolerance_pt=0.5)["both_extents_on_wall_layer_face"] == 1


def test_tie_count_is_translation_and_input_order_invariant():
    def build(dx: float, dy: float, order: int):
        walls = [
            _filled_wall("Enclosure_WallInternal", 100, 0, 110, 300, dx, dy),
            _filled_wall("Enclosure_WallInternal", 200, 0, 210, 300, dx, dy),
            _filled_wall("Interior_Joinery", 140, 10, 150, 50, dx, dy),
        ]
        dims = [
            _dim("horizontal", (110.0 + dx, 500.0 + dy), (200.0 + dx, 500.0 + dy)),
            _dim("horizontal", (150.0 + dx, 500.0 + dy), (160.0 + dx, 500.0 + dy)),
        ]
        if order:
            walls.reverse()
            dims.reverse()
        vertical, horizontal = wall_layer_axis_faces(walls)
        return figured_dimension_face_ties(dims, vertical, horizontal, tolerance_pt=0.05)

    baseline = build(0.0, 0.0, 0)
    assert baseline == {"figured_dimensions": 2, "both_extents_on_wall_layer_face": 1}
    assert build(317.25, -88.5, 0) == baseline
    assert build(0.0, 0.0, 1) == baseline


def test_inputs_are_not_mutated():
    drawings = [_filled_wall("Enclosure_WallInternal", 10, 20, 20, 120)]
    before = [dict(row) for row in drawings]
    layer_census(drawings)
    wall_layer_axis_faces(drawings)
    assert drawings == before


def _ring(x0, y0, x1, y1):
    return SimpleNamespace(bbox_pdf_pts=(x0, y0, x1, y1))


def test_ring_figured_box_ties_counts_unique_competing_and_absent_pairs():
    dims = [
        _dim("horizontal", (100.0, 500.0), (185.0, 500.0)),
        _dim("vertical", (900.0, 40.0), (900.0, 142.0)),
        _dim("vertical", (880.0, 40.0), (880.0, 160.0)),
        _dim("horizontal", (300.0, 500.0), (340.0, 500.0)),
    ]
    unique = _ring(100.0, 40.0, 185.0, 142.0)
    competing_dims = dims + [_dim("vertical", (910.0, 40.2), (910.0, 142.2))]
    assert ring_figured_box_ties([unique], dims, tolerance_pt=0.5)["unique_figured_box_pair"] == 1
    assert ring_figured_box_ties([unique], competing_dims, tolerance_pt=0.5)["competing_figured_box_pairs"] == 1
    assert ring_figured_box_ties([_ring(0.0, 0.0, 50.0, 50.0)], dims, tolerance_pt=0.5)["no_figured_box_pair"] == 1
    # tolerance is a hard bound
    assert ring_figured_box_ties([_ring(100.0, 40.0, 186.0, 142.0)], dims, tolerance_pt=0.5)["no_figured_box_pair"] == 1
