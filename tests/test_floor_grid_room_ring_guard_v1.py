"""Synthetic guard for the Office failure mode (#4764 7236315096): floor-grid lines inside a room.

In the centreline face route a floor-tile grid drawn in the wall graph splits a room into tile cells. The
doorway-closing ring route must keep the room whole with the grid present, a single tile cell must not pass the
wall-support check, narrow rooms must still close, and ruled drafting cells must not become rooms. Synthetic only.
"""
from __future__ import annotations

import fitz
import pytest
from shapely.geometry import Point, Polygon, box
from test_layered_door_jamb_returns_v1 import ROOM_PROBE, SHA, Scene, _build, _room

from pb_finish_face_wall_support_shadow import face_wall_support
from pb_labelled_ring_ownership_shadow import labelled_ring_ownership
from pb_layered_wall_doorway_room_ring_shadow import (
    build_layered_wall_doorway_room_rings,
)
from pb_room_ring_candidate_union_shadow import union_room_ring_candidates

GRID_INK = (0.5, 0.5, 0.5)
ROOM = (165.0, 106.5, 258.0, 220.0)  # the Scene's room interior (along, across), horizontal layout


def grid_rows(pitch):
    x0, y0, x1, y1 = ROOM
    rows = []
    x = x0 + pitch
    while x < x1 - 0.5:
        rows.append({"layer": "", "fill": None, "color": GRID_INK, "width": 0.24, "items": [("l", fitz.Point(x, y0), fitz.Point(x, y1))]})
        x += pitch
    y = y0 + pitch
    while y < y1 - 0.5:
        rows.append({"layer": "", "fill": None, "color": GRID_INK, "width": 0.24, "items": [("l", fitz.Point(x0, y), fitz.Point(x1, y))]})
        y += pitch
    return rows


@pytest.mark.parametrize("pitch", [17.0, 34.0], ids=["17pt", "34pt"])
def test_a_floor_grid_leaves_the_door_closed_room_whole(pitch):
    scene = Scene()
    rows = scene.rows + grid_rows(pitch)
    plain, gridded = _build(scene.rows), _build(rows)
    room, same = _room(plain, scene), _room(gridded, scene)
    assert room is not None and same is not None and same.status.value == "candidate"
    assert Polygon(same.polygon_pdf_pts).symmetric_difference(Polygon(room.polygon_pdf_pts)).area < 0.5
    default = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True)
    record = labelled_ring_ownership({"ROOM": scene.map(*ROOM_PROBE)},
                                     union_room_ring_candidates(default, gridded), rows)["ROOM"]
    assert record["status"].value == "candidate" and record["measurement_authority"] is False
    assert Polygon(record["polygon_pdf_pts"]).area > 0.9 * Polygon(room.polygon_pdf_pts).area


def test_one_tile_cell_is_not_wall_supported():
    scene = Scene()
    rows = scene.rows + grid_rows(17.0)
    cell = [(182.0, 123.5), (199.0, 123.5), (199.0, 140.5), (182.0, 140.5)]  # an interior cell: no wall on any side
    support = face_wall_support(cell, rows)
    assert support["reason"] == "face_edge_without_wall_evidence" and support["unsupported_share"] > 0.99


def _dark(rect):
    return {"layer": "", "fill": (0.2, 0.2, 0.2), "color": None, "fill_opacity": 1.0,
            "items": [("re", fitz.Rect(rect), 1)], "rect": fitz.Rect(rect)}


def _rings(rows):
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True)


@pytest.mark.parametrize("width", [30.0, 60.0], ids=["narrow", "wider"])
def test_a_narrow_room_of_dark_walls_still_closes(width):
    inner = box(100.0, 100.0, 100.0 + width, 300.0)
    walls = [(94.0, 94.0, 106.0 + width, 100.0), (94.0, 300.0, 106.0 + width, 306.0),
             (94.0, 100.0, 100.0, 300.0), (100.0 + width, 100.0, 106.0 + width, 300.0)]
    result = _rings([_dark(r) for r in walls])
    holding = [r for r in result.rings if Polygon(r.polygon_pdf_pts).contains(Point(100.0 + width / 2, 200.0))]
    assert len(holding) == 1 and Polygon(holding[0].polygon_pdf_pts).symmetric_difference(inner).area < 1.0


@pytest.mark.parametrize("pitch,row_count", [(12.0, 4), (6.0, 4), (6.0, 1)], ids=["rows_12pt", "rows_6pt", "one_6pt_row"])
def test_ruled_drafting_cells_are_not_rooms(pitch, row_count):
    bottom = 100.0 + pitch * row_count
    rows = []
    for x in (100.0, 140.0, 180.0, 220.0):
        rows.append({"layer": "", "fill": None, "color": (0.0, 0.0, 0.0), "width": 0.5,
                     "items": [("l", fitz.Point(x, 100.0), fitz.Point(x, bottom))]})
    for i in range(row_count + 1):
        rows.append({"layer": "", "fill": None, "color": (0.0, 0.0, 0.0), "width": 0.5,
                     "items": [("l", fitz.Point(100.0, 100.0 + pitch * i), fitz.Point(220.0, 100.0 + pitch * i))]})
    assert _rings(rows).rings == ()
