"""Floor-grid lattice negative evidence (report only). Synthetic PyMuPDF-style drawing rows."""
from __future__ import annotations

import copy
import random
from types import SimpleNamespace

import fitz
import pytest

from pb_floor_grid_linework_shadow import (
    floor_grid_boundary_shares,
    floor_grid_lattices,
    grid_only_wall_ids,
)

GREY = (0.5, 0.5, 0.5)
BLACK = (0.0, 0.0, 0.0)


def stroke(a, b, color=GREY, width=0.24):
    return {"layer": "", "fill": None, "color": color, "width": width, "stroke_opacity": 1.0,
            "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def grid(x0, y0, pitch_x, pitch_y, nx, ny, color=GREY, split=False):
    x1, y1 = x0 + pitch_x * (nx - 1), y0 + pitch_y * (ny - 1)
    rows = []
    for i in range(nx):
        x = x0 + pitch_x * i
        parts = [(y0, y1)] if not split else [(y0, (y0 + y1) / 2), ((y0 + y1) / 2, y1)]
        rows += [stroke((x, a), (x, b), color) for a, b in parts]
    for j in range(ny):
        y = y0 + pitch_y * j
        parts = [(x0, x1)] if not split else [(x0, (x0 + x1) / 2), ((x0 + x1) / 2, x1)]
        rows += [stroke((a, y), (b, y), color) for a, b in parts]
    return rows


def summary(lattices):
    return [(r["pitch_x_pt"], r["pitch_y_pt"], r["rules_x"], r["rules_y"], len(r["items"])) for r in lattices]


@pytest.mark.parametrize("kwargs,expected", [
    ({}, (34.0, 34.0, 5, 6, 11)),
    ({"split": True}, (34.0, 34.0, 5, 6, 22)),
    ({"pitch_x": 34.0, "pitch_y": 17.0}, (34.0, 17.0, 5, 6, 11)),
], ids=["square", "split_pieces", "rectangular"])
def test_a_light_tile_grid_is_one_lattice(kwargs, expected):
    args = {"pitch_x": 34.0, "pitch_y": 34.0, "split": False, **kwargs}
    rows = grid(100.0, 100.0, args["pitch_x"], args["pitch_y"], 5, 6, split=args["split"])
    [record] = floor_grid_lattices(rows)
    assert summary([record]) == [expected] and record["wall_authority"] is False


def test_two_rooms_with_offset_grids_stay_two_lattices():
    rows = grid(100.0, 100.0, 34.0, 34.0, 5, 5) + grid(300.0, 111.0, 34.0, 34.0, 5, 5)
    assert [r[2:4] for r in summary(floor_grid_lattices(rows))] == [(5, 5), (5, 5)]


def test_shifted_shuffled_and_untouched_input():
    rows = grid(100.0, 100.0, 34.0, 34.0, 5, 6) + grid(400.0, 300.0, 17.0, 17.0, 6, 4)
    before = copy.deepcopy(rows)
    first = floor_grid_lattices(rows)
    order = list(range(len(rows)))
    random.Random(7).shuffle(order)
    shuffled = floor_grid_lattices([rows[i] for i in order])
    assert summary(shuffled) == summary(first) and rows == before
    assert [r["items"] for r in first] == [tuple(sorted((order[p], i) for p, i in r["items"])) for r in shuffled]
    moved = grid(113.5, 191.25, 34.0, 34.0, 5, 6) + grid(413.5, 391.25, 17.0, 17.0, 6, 4)
    assert summary(floor_grid_lattices(moved)) == summary(first)


@pytest.mark.parametrize("rows", [
    grid(100.0, 100.0, 34.0, 34.0, 5, 5, color=BLACK),  # a black grid: dark pens are never flagged
    [r for x in (100.0, 106.0, 200.0, 206.0, 300.0, 306.0) for r in [stroke((x, 100.0), (x, 400.0))]]
    + [stroke((100.0, y), (306.0, y)) for y in (100.0, 106.0, 250.0, 256.0, 400.0, 406.0)],  # double-line walls
    [stroke((100.0, 100.0 + 10 * i), (160.0, 100.0 + 10 * i)) for i in range(12)]
    + [stroke((100.0, 100.0), (100.0, 210.0)), stroke((160.0, 100.0), (160.0, 210.0))],  # stair treads, two stringers
    [stroke((100.0 + 10 * i, 100.0), (130.0 + 10 * i, 130.0)) for i in range(10)],  # diagonal hatch
    [stroke((x, 100.0), (x, 400.0)) for x in (100.0, 160.0, 250.0, 270.0, 400.0)]
    + [stroke((100.0, y), (400.0, y)) for y in (100.0, 130.0, 220.0, 400.0)],  # irregular structural grid
    grid(100.0, 100.0, 34.0, 34.0, 3, 6),  # only three rules one way
    grid(100.0, 100.0, 6.0, 6.0, 8, 8),  # hatch pitch
], ids=["black", "double_walls", "stairs", "diagonal", "irregular", "three_rules", "hatch_pitch"])
def test_look_alikes_are_not_lattices(rows):
    assert floor_grid_lattices(rows) == []


def test_filled_shapes_never_make_a_grid():
    rows = [{**r, "fill": (0.9, 0.9, 0.9), "fill_opacity": 1.0} for r in grid(100.0, 100.0, 34.0, 34.0, 5, 5)]
    assert floor_grid_lattices(rows) == []


def test_stepped_lines_that_only_touch_two_others_are_not_a_grid():
    rows = []
    for i in range(6):  # a stair-section profile: each rule meets two others only
        x, y = 105.0 + 17.0 * i, 100.0 + 17.0 * i
        rows += [stroke((x - 1.0, y), (x + 18.0, y)), stroke((x, y - 18.0), (x, y + 1.0))]
    assert floor_grid_lattices(rows) == []


def test_walls_on_the_same_lines_are_not_flagged():
    rows = grid(100.0, 100.0, 34.0, 34.0, 5, 5)
    wall = stroke((100.0, 100.0), (236.0, 100.0), color=BLACK, width=0.48)  # a dark wall face on a grid line
    lattices = floor_grid_lattices(rows + [wall])
    assert all((len(rows), 0) not in r["items"] for r in lattices) and len(lattices) == 1


def test_tile_cells_are_all_grid_and_walls_are_not():
    walls = [stroke(a, b, color=BLACK, width=0.48) for a, b in
             (((134.0, 90.0), (134.0, 260.0)), ((100.0, 134.0), (270.0, 134.0)))]  # dark faces over two grid lines
    rows = grid(100.0, 100.0, 34.0, 34.0, 6, 6) + walls
    lattices = floor_grid_lattices(rows)
    cell = [(168.0, 168.0), (202.0, 168.0), (202.0, 202.0), (168.0, 202.0)]
    on_walls = [(134.0, 134.0), (168.0, 134.0), (168.0, 168.0), (134.0, 168.0)]  # two sides are wall faces
    room = [(100.5, 100.5), (130.0, 100.5), (130.0, 130.0), (100.5, 130.0)]  # off the grid lines
    cell_share, wall_share, room_share = floor_grid_boundary_shares([cell + cell[:1], on_walls, room], rows, lattices)
    assert cell_share == pytest.approx(1.0) and wall_share == pytest.approx(0.5) and room_share == 0.0


def test_grid_only_walls_need_every_primitive_on_the_grid():
    rows = grid(100.0, 100.0, 34.0, 34.0, 5, 5) + [stroke((50.0, 50.0), (90.0, 50.0), color=BLACK)]
    lattices = floor_grid_lattices(rows)

    def wall(name, *primitives):
        return SimpleNamespace(wall_candidate_id=name,
                               physical_identity=SimpleNamespace(source_primitive_ids=primitives))

    walls = [wall("on_grid", "d0i0", "d1i0"), wall("mixed", "d0i0", "d10i0"), wall("raster", "raster_segment:1"),
             wall("rect_edge", "d0i0e1"), wall("empty")]
    assert grid_only_wall_ids(walls, lattices) == ("on_grid",)
