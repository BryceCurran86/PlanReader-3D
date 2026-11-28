"""Curved wall candidates from paired concentric arcs (report only). Synthetic PyMuPDF drawings."""
from __future__ import annotations

import copy
import math

import fitz
import pytest

from pb_curved_wall_pair_shadow import (
    REASON_DOOR,
    REASON_PAIR,
    REASON_RINGS,
    curved_wall_pairs,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status

BLACK, RED = (0, 0, 0), (1, 0, 0)


def draw_arc(page, centre, radius, start_deg, sweep_deg, colour=BLACK, pieces=None):
    count = pieces or max(1, math.ceil(abs(sweep_deg) / 90.0))
    step = math.radians(sweep_deg / count)
    k = 4.0 / 3.0 * math.tan(step / 4.0)
    shape = page.new_shape()
    for i in range(count):
        a, b = math.radians(start_deg) + i * step, math.radians(start_deg) + (i + 1) * step
        p0 = (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))
        p3 = (centre[0] + radius * math.cos(b), centre[1] + radius * math.sin(b))
        p1 = (p0[0] - k * radius * math.sin(a), p0[1] + k * radius * math.cos(a))
        p2 = (p3[0] + k * radius * math.sin(b), p3[1] - k * radius * math.cos(b))
        shape.draw_bezier(p0, p1, p2, p3)
    shape.finish(color=colour, width=0.7, closePath=False)
    shape.commit()


def drawings(arcs=(), lines=()):
    document = fitz.open()
    page = document.new_page(width=800, height=800)
    for arc in arcs:
        draw_arc(page, **arc)
    for a, b in lines:
        page.draw_line(a, b, color=BLACK, width=0.7)
    found = page.get_drawings()
    document.close()
    return found


def wall(centre=(400, 400), radius=120, thickness=6, start=10, sweep=90, **extra):
    return [{"centre": centre, "radius": radius, "start_deg": start, "sweep_deg": sweep, **extra},
            {"centre": centre, "radius": radius + thickness, "start_deg": start, "sweep_deg": sweep, **extra}]


@pytest.mark.parametrize("kwargs", [{}, {"centre": (233.5, 517.25)}, {"start": 200}, {"start": 330, "sweep": 120},
                                    {"pieces": 3}, {"start": 100, "sweep": -90}],
                         ids=["plain", "moved", "turned", "wraps", "split", "clockwise"])
def test_a_curved_double_face_is_one_candidate(kwargs):
    found = curved_wall_pairs(drawings(wall(**kwargs)))
    assert len(found) == 1
    row = found[0]
    assert row["status"] is Status.CANDIDATE and row["reason"] == REASON_PAIR and row["wall_authority"] is False
    assert abs(row["inner_radius_pt"] - 120) < 0.8 and abs(row["outer_radius_pt"] - 126) < 0.8
    overlap = sum(hi - lo for lo, hi in row["angle_intervals_deg"])
    assert abs(overlap - abs(kwargs.get("sweep", 90))) < 2


@pytest.mark.parametrize("arcs", [
    [{"centre": (400, 400), "radius": 120, "start_deg": 0, "sweep_deg": 90}],  # one face only
    wall(thickness=20),  # too thick
    wall(sweep=20),  # too short an overlap
    [wall()[0], {**wall()[1], "colour": RED}],  # mixed ink
    wall(sweep=360),  # a column or table
    wall(radius=10, thickness=4),  # a small symbol
    [wall()[0], {**wall()[1], "centre": (405, 400)}],  # not concentric
], ids=["one_face", "too_thick", "too_short", "mixed_ink", "circles", "symbol", "offset_centres"])
def test_look_alikes_give_nothing(arcs):
    assert curved_wall_pairs(drawings(arcs)) == []


def test_three_rings_abstain():
    arcs = [*wall(), {"centre": (400, 400), "radius": 132, "start_deg": 10, "sweep_deg": 90}]
    found = curved_wall_pairs(drawings(arcs))
    assert found and all(r["status"] is Status.ABSTAINED and r["reason"] == REASON_RINGS for r in found)


def test_a_double_door_swing_abstains():
    arcs = wall(radius=60, thickness=2, start=0)
    found = curved_wall_pairs(drawings(arcs, lines=[((400, 400), (460, 400))]))
    assert [r["reason"] for r in found] == [REASON_DOOR] and found[0]["status"] is Status.ABSTAINED


def test_order_and_inputs():
    rows = drawings(wall() + wall(centre=(200, 200), start=180))
    before = copy.deepcopy(rows)
    forward = curved_wall_pairs(rows)
    backward = curved_wall_pairs(list(reversed(rows)))
    assert rows == before and len(forward) == 2
    strip = lambda items: [{k: v for k, v in r.items() if k != "source_path_indices"} for r in items]
    assert strip(forward) == strip(backward)
    assert curved_wall_pairs(rows) == forward
