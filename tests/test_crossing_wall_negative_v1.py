"""A wall crossing drawn through is not a door, default off (#4764 7219675205, geometry task C12). Synthetic only."""
from __future__ import annotations

import math
import random

import fitz
import pytest

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

CROSS_THROUGH = [((50, 200), (260, 200)), ((280, 200), (450, 200)), ((50, 220), (260, 220)), ((280, 220), (450, 220)),
                 ((260, 80), (260, 200)), ((260, 200), (260, 220)), ((260, 220), (260, 360)),
                 ((280, 80), (280, 200)), ((280, 200), (280, 220)), ((280, 220), (280, 360))]


def _wall(x0, x1, y, doors, thickness=20.0):
    edges = [x0] + [v for door in doors for v in door] + [x1]
    lines = []
    for a, b in zip(edges[::2], edges[1::2]):
        lines += [((a, y), (b, y)), ((a, y + thickness), (b, y + thickness))]
    for a, b in doors:
        lines += [((a, y), (a, y + thickness)), ((b, y), (b, y + thickness))]
    return lines


REAL_DOORS = {
    "single": _wall(50, 450, 200, [(200, 240)]),
    "t-stem-below": _wall(50, 450, 200, [(200, 240)]) + [((260, 220), (260, 360)), ((280, 220), (280, 360))],
    "stem-in-line-with-one-jamb": _wall(50, 450, 200, [(200, 240)]) + [((240, 220), (240, 360))],
    "stem-in-line-both-sides-one-jamb": _wall(50, 450, 200, [(200, 240)]) + [((240, 220), (240, 360)),
                                                                             ((240, 80), (240, 200))],
    "stems-in-line-below-both-jambs": _wall(50, 450, 200, [(200, 240)]) + [((200, 220), (200, 360)),
                                                                           ((240, 220), (240, 360))],
    "two-doors": _wall(50, 450, 200, [(150, 190), (300, 340)]),
    "stems-in-line-above-both-jambs": _wall(50, 450, 200, [(200, 240)]) + [((200, 80), (200, 200)),
                                                                           ((240, 80), (240, 200))],
    "jambs-overdrawn-inward": _wall(50, 450, 200, [(200, 240)]) + [((200, 200), (200, 208)), ((200, 220), (200, 212)),
                                                                   ((240, 200), (240, 208)), ((240, 220), (240, 212))],
    # short lining/architrave ticks carrying on past both faces: a door, because they stop within one wall thickness
    "lining-ticks-beyond-both-faces": _wall(50, 450, 200, [(200, 240)]) + [((200, 196), (200, 200)),
                                                                           ((200, 220), (200, 224)),
                                                                           ((240, 196), (240, 200)),
                                                                           ((240, 220), (240, 224))],
}


def _found(lines, *, on=True, angle=0.0, precision=False, seed=None):
    document = fitz.open()
    page = document.new_page(width=700, height=700)
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def move(point):
        x, y = point[0] - 250, point[1] - 220
        return fitz.Point(350 + x * cos - y * sin, 350 + x * sin + y * cos)

    shape = page.new_shape()
    ordered = list(lines) if seed is None else random.Random(seed).sample(list(lines), len(lines))
    for a, b in ordered:
        shape.draw_line(move(a), move(b))
    shape.finish(width=1.0, closePath=False)
    shape.commit()
    data = document.tobytes()
    document.close()
    source = SourceVisibilityProducer(producer_method="crossing-wall-test", producer_version="1",
                                      crossing_wall_negative_shadow=on, angled_opening_precision_shadow=precision)
    published = source.ingest_native_pdf_bytes(document_id="cross", source_bytes=data, source_locator="memory://x.pdf")
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
                                                      revision_id=published.revision.revision_id, page_ids=("1",))
    hosted = sum(t.status.value == "corroborated" and t.host_wall_id is not None for t in composition.opening_bindings)
    return len(composition.opening_bindings), hosted


def test_default_off_still_reads_the_crossing_as_a_door():
    assert _found(CROSS_THROUGH, on=False) == (1, 1)


@pytest.mark.parametrize("kwargs", [dict(), dict(angle=90.0), dict(angle=180.0), dict(seed=3),
                                    dict(angle=30.0, precision=True)], ids=["flat", "r90", "r180", "order", "r30"])
def test_the_crossing_is_not_a_door_with_the_option(kwargs):
    assert _found(CROSS_THROUGH, **kwargs) == (0, 0)


@pytest.mark.parametrize("name", sorted(REAL_DOORS))
def test_real_doors_are_unchanged_by_the_option(name):
    expected = _found(REAL_DOORS[name], on=False)
    assert expected[0] >= 1
    assert _found(REAL_DOORS[name]) == expected


def _split_stems(piece, overshoot=None):
    """The crossing wall's four outer stem pieces cut into short pieces (or shortened to ``overshoot`` beyond a face)."""
    lines = [line for line in CROSS_THROUGH if not (line[0][0] == line[1][0] and (line[1][1] <= 200 or line[0][1] >= 220))]
    for x in (260, 280):
        for face, far in ((200, 80 if overshoot is None else 200 - overshoot),
                          (220, 360 if overshoot is None else 220 + overshoot)):
            step = piece if far > face else -piece
            points = [face]
            while abs(far - points[-1]) > piece:
                points.append(points[-1] + step)
            points.append(far)
            lines += [((x, a), (x, b)) for a, b in zip(points, points[1:])]
    return lines


@pytest.mark.parametrize("seed", [None, 5])
def test_a_crossing_wall_cut_into_short_pieces_is_still_not_a_door(seed):
    assert _found(_split_stems(6.0), on=False)[0] >= 1
    assert _found(_split_stems(6.0), seed=seed) == (0, 0)


@pytest.mark.parametrize("overshoot,removed", [(6.0, False), (19.0, False), (20.0, True), (45.0, True)])
def test_only_lines_carrying_on_a_whole_wall_thickness_make_it_a_crossing(overshoot, removed):
    lines = _split_stems(8.0, overshoot=overshoot)
    before = _found(lines, on=False)
    assert before == (1, 1)
    assert _found(lines) == ((0, 0) if removed else before)


def test_the_option_must_be_a_boolean():
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="m", producer_version="1", crossing_wall_negative_shadow=1)
