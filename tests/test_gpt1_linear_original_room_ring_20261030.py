"""Original PDF-scaled room identity must be byte-stable with linear ring work.

The legacy quadratic enumeration below is a test oracle for SMALL rings only.
No private source, benchmark truth, new scale, or customer FIRM is used.
"""
from __future__ import annotations

import math
import random

import pytest

from pb_migration_contracts import canonical_contract_json
from pb_room_area_quantity import _canonical_ring, _original_pdf_ring
from tests.test_room_area_quantity_v2 import _room, _scale, _scaled_qty


def _legacy_quadratic_oracle(points):
    original = _original_pdf_ring(points)
    if original is None:
        return ()
    pts = tuple((round(x, 8), round(y, 8)) for x, y in original)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if not pts:
        return ()
    rotations = [pts[i:] + pts[:i] for i in range(len(pts))]
    reversed_pts = tuple(reversed(pts))
    rotations.extend(
        reversed_pts[i:] + reversed_pts[:i] for i in range(len(reversed_pts))
    )
    return min(rotations)


def test_linear_ring_is_exactly_legacy_source_id_ring_for_random_originals():
    rng = random.Random(20261030)
    for size in range(3, 45):
        for _ in range(12):
            # Unique original x coordinates keep the original source parser
            # valid, while random y and fractional x test lexicographic ties.
            xs = rng.sample(range(-5000, 5000), size)
            points = tuple(
                (x + rng.choice((0.0, 1e-10, -1e-10)), rng.randint(-5, 5) / 3.0)
                for x in xs
            )
            before = tuple(points)
            assert _canonical_ring(points) == _legacy_quadratic_oracle(points)
            assert points == before


@pytest.mark.parametrize("points", (
    ((0.0, -0.0), (-0.0, 1.0), (1e-10, 0.0), (1.0, 1.0)),
    ((0.0, 0.0), (1e-9, 0.0), (2e-9, 0.0), (1.0, 1.0)),
    ((-0.0, 0.0), (1.0, 0.0), (1.0, -0.0), (0.0, 1.0)),
    ((1.0, 2.0), (1.0, 2.0000000001), (2.0, 1.0), (3.0, 0.0)),
))
def test_rounded_aliases_and_signed_zero_preserve_original_contract_bytes(points):
    assert canonical_contract_json(_canonical_ring(points)) == canonical_contract_json(
        _legacy_quadratic_oracle(points)
    )
    for offset in range(len(points)):
        rotated = points[offset:] + points[:offset]
        assert canonical_contract_json(_canonical_ring(rotated)) == canonical_contract_json(
            _legacy_quadratic_oracle(rotated)
        )


def test_original_ring_cyclic_winding_and_20k_vertex_work_is_bounded():
    # A real source primitive budget permits up to 20,000 vertices. The
    # former 2N full-rotation tuples were quadratic and could not survive it.
    points = tuple((float(i), float((i * i) % 104729)) for i in range(20000))
    before = points
    expected = _canonical_ring(points)
    assert len(expected) == len(points)
    assert _canonical_ring(points[12345:] + points[:12345]) == expected
    assert _canonical_ring(tuple(reversed(points))) == expected
    assert points == before


def test_real_scaled_room_producer_keeps_original_source_id_and_ring_signature():
    scale = _scale()
    points = tuple(
        (
            700.0 + 200.0 * math.cos(2.0 * math.pi * i / 256),
            700.0 + 200.0 * math.sin(2.0 * math.pi * i / 256),
        )
        for i in range(256)
    )
    variants = (
        points,
        points[79:] + points[:79],
        tuple(reversed(points)),
    )
    produced = tuple(_scaled_qty(room=_room(points=ring), scale=scale) for ring in variants)
    assert all(not item.abstained and item.status == "firm" for item in produced)
    assert len({item.quantity_id for item in produced}) == 1
    assert len({item.metadata["ring_signature"] for item in produced}) == 1
    assert len({item.value for item in produced}) == 1
    assert produced[0] == _scaled_qty(room=_room(points=points), scale=scale)
    translated = tuple((x + 13.0, y - 7.0) for x, y in points)
    shifted = _scaled_qty(room=_room(points=translated), scale=scale)
    assert shifted.abstained is False
    assert shifted.value == produced[0].value
    assert shifted.quantity_id != produced[0].quantity_id


@pytest.mark.parametrize("bad", (
    ((0.0, 0.0), (1.0, 0.0), (1.0, 0.0)),
    ((0.0, 0.0), (True, 1.0), (2.0, 2.0)),
    ((0.0, 0.0), (float("nan"), 1.0), (2.0, 2.0)),
    ((0.0, 0.0), (float("inf"), 1.0), (2.0, 2.0)),
    ((0.0, 0.0), (10 ** 400, 1.0), (2.0, 2.0)),
))
def test_original_invalid_source_ring_still_abstains_without_repair(bad):
    assert _canonical_ring(bad) == ()
