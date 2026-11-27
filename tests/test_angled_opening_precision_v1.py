"""Openings in angled walls with source-coordinate precision, default off (#4764 7215518648, geometry task C14). Synthetic."""
from __future__ import annotations

import math
import random

import fitz
import pytest

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_coordinate_precision import source_coordinate_tolerance
from pb_source_visibility_authority import SourceVisibilityProducer

# the repository's host fixture: two wall faces broken by an opening with two jambs
OPENING = (((20.0, 80.0), (120.0, 80.0)), ((160.0, 80.0), (280.0, 80.0)), ((20.0, 100.0), (120.0, 100.0)),
           ((160.0, 100.0), (280.0, 100.0)), ((120.0, 80.0), (120.0, 100.0)), ((160.0, 80.0), (160.0, 100.0)))
CENTRE = (150.0, 90.0)


def _pdf(segments=OPENING, *, angle=0.0, scale=1.0, mirror=False):
    document = fitz.open()
    side = 900.0 * max(1.0, scale)
    page = document.new_page(width=side, height=side)
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def move(point):
        x, y = point[0] - CENTRE[0], point[1] - CENTRE[1]
        x = -x if mirror else x
        x, y = x * scale, y * scale
        return fitz.Point(side / 2 + x * cos - y * sin, side / 2 + x * sin + y * cos)

    shape = page.new_shape()
    for start, end in segments:
        shape.draw_line(move(start), move(end))
    shape.finish(width=1.0, closePath=False)
    shape.commit()
    data = document.tobytes()
    document.close()
    return data


def _found(data, *, precise=True):
    source = SourceVisibilityProducer(producer_method="angled-opening-test", producer_version="1",
                                      angled_opening_precision_shadow=precise)
    published = source.ingest_native_pdf_bytes(document_id="angled", source_bytes=data, source_locator="memory://a.pdf")
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
                                                      revision_id=published.revision.revision_id, page_ids=("1",))
    hosted = sum(t.status.value == "corroborated" and t.host_wall_id is not None for t in composition.opening_bindings)
    return len(composition.opening_bindings), hosted


def test_default_off_keeps_the_historical_answer():
    assert _found(_pdf(), precise=False) == (1, 1)
    assert _found(_pdf(angle=30.0), precise=False) == (0, 0)


@pytest.mark.parametrize("kwargs", [dict(angle=a) for a in (0, 15, 30, 45, 60, 89.5, 90, 135, 180, 271.25)]
                         + [dict(scale=0.25), dict(scale=3.0), dict(mirror=True), dict(angle=30, mirror=True),
                            dict(angle=52.5, scale=2.0)],
                         ids=lambda kw: "-".join(f"{k}{v}" for k, v in kw.items()))
def test_the_opening_is_found_and_hosted_at_any_angle_scale_and_mirror(kwargs):
    assert _found(_pdf(**kwargs)) == (1, 1)


def _tilted_right_face(degrees):
    turn = math.radians(degrees)
    end = (160.0 + 120.0 * math.cos(turn), 80.0 + 120.0 * math.sin(turn))
    return (OPENING[0], ((160.0, 80.0), end), *OPENING[2:])


@pytest.mark.parametrize("segments", [
    _tilted_right_face(0.1),                                                   # nearly, but not, the same line
    (OPENING[0], ((160.0, 80.01), (280.0, 80.01)), *OPENING[2:]),              # offset by a hundredth of a point
], ids=["tilted-0.1deg", "offset-0.01pt"])
@pytest.mark.parametrize("angle", [0.0, 30.0])
def test_near_collinear_faces_are_not_joined(segments, angle):
    assert _found(_pdf(segments, angle=angle))[0] == 0


T_JUNCTION = (((20.0, 80.0), (280.0, 80.0)), ((20.0, 100.0), (120.0, 100.0)), ((140.0, 100.0), (280.0, 100.0)),
              ((120.0, 100.0), (120.0, 200.0)), ((140.0, 100.0), (140.0, 200.0)))
DASHED_GRID = tuple(((x0, y), (x0 + 12.0, y)) for y in (60.0, 80.0, 100.0, 120.0) for x0 in (40.0, 60.0, 80.0, 100.0)) + \
    tuple(((x, 50.0), (x, 130.0)) for x in (46.0, 66.0, 86.0, 106.0))


@pytest.mark.parametrize("segments", [T_JUNCTION, DASHED_GRID], ids=["t-junction", "dashed-grid"])
def test_look_alikes_give_the_same_answer_at_every_angle(segments):
    reference = _found(_pdf(segments))
    assert all(_found(_pdf(segments, angle=angle)) == reference for angle in (30.0, 45.0, 117.0))


def test_input_order_and_face_splitting_do_not_change_an_angled_answer():
    split = OPENING[1:] + (((20.0, 80.0), (70.0, 80.0)), ((70.0, 80.0), (120.0, 80.0)))
    for segments in (list(OPENING), list(split)):
        for seed in (1, 2):
            order = random.Random(seed).sample(segments, len(segments))
            assert _found(_pdf(order, angle=33.0)) == (1, 1)


def test_the_tolerance_is_representation_error_not_a_drawing_tolerance():
    assert source_coordinate_tolerance([(0.0, 0.0, 500.0, 500.0)], floor=1e-6) == pytest.approx(4 * 2.0 ** -23 * 500)
    assert source_coordinate_tolerance([(0.0, 0.0, 1.0, 1.0)], floor=1e-6) == 1e-6
    assert source_coordinate_tolerance([(0.0, 0.0, 5000.0, 0.0)], floor=1e-6) < 0.01
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="m", producer_version="1", angled_opening_precision_shadow=1)
