"""A finish-bearing room face needs wall evidence on every edge (#4764 7225222738, C06/C08). Synthetic only."""
from __future__ import annotations

import copy
import hashlib
from types import SimpleNamespace

import fitz
import pytest

from pb_finish_face_wall_support_shadow import face_wall_support
from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_migration_contracts import EvidenceResolutionStatus

CANDIDATE, ABSTAINED = EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED
BLACK, GREY, WHITE, GREEN = (0, 0, 0), (0.55, 0.55, 0.55), (1, 1, 1), (0, 0.8, 0)
FACE = ((50, 50), (164, 50), (164, 164), (50, 164))
OUTER = ((44, 44), (170, 44), (170, 170), (44, 170))


def _loop(points):
    return list(zip(points, points[1:] + points[:1]))


def _draw(lines=(), bars=(), *, colour=BLACK, fill=None, shift=(0.0, 0.0), turn=False, reverse=False, split=False):
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    def move(point):
        x, y = point[0] + shift[0], point[1] + shift[1]
        return (600 - y, x) if turn else (x, y)

    pieces = []
    for a, b in lines:
        if split:
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            pieces += [(a, middle), (middle, b)]
        else:
            pieces.append((a, b))
    for a, b in (pieces[::-1] if reverse else pieces):
        page.draw_line(move(a), move(b), color=colour, width=0.7)
    for x0, y0, x1, y1 in bars:
        corners = [move((x0, y0)), move((x1, y1))]
        rect = fitz.Rect(min(c[0] for c in corners), min(c[1] for c in corners),
                         max(c[0] for c in corners), max(c[1] for c in corners))
        page.draw_rect(rect, color=None, fill=fill, width=0)
    drawings = page.get_drawings()
    data = document.tobytes()
    document.close()
    return data, drawings, [move(p) for p in FACE]


DOUBLE = _loop(list(OUTER)) + _loop(list(FACE))
BARS = [(44, 44, 170, 50), (44, 164, 170, 170), (44, 50, 50, 164), (164, 50, 170, 164)]


def _support(face, drawings, closures=()):
    return face_wall_support(face, drawings, closures)


@pytest.mark.parametrize("colour", [BLACK, GREY], ids=["black", "grey"])
def test_a_double_line_room_is_on_paired_wall_evidence_whatever_its_colour(colour):
    _data, drawings, face = _draw(DOUBLE, colour=colour)
    result = _support(face, drawings)
    assert result["status"] is CANDIDATE and result["unsupported_share"] < 0.01
    assert all(edge["paired"] > 0.99 * edge["length"] and edge["filled"] == 0 for edge in result["edges"])


@pytest.mark.parametrize("fill", [BLACK, GREY], ids=["black", "grey"])
def test_a_room_of_solid_wall_bars_is_on_filled_evidence(fill):
    _data, drawings, face = _draw(bars=BARS, fill=fill)
    result = _support(face, drawings)
    # grey bars: any visible non-white fill counts (the builder alone only reads dark bars)
    assert result["status"] is CANDIDATE
    assert all(edge["filled"] > 0.99 * edge["length"] for edge in result["edges"])


def test_bars_support_only_the_edge_they_run_along_and_touch():
    _data, drawings, face = _draw(bars=[BARS[2], BARS[3]], fill=GREY)  # the left and right bars only
    assert [edge["filled"] > 0 for edge in _support(face, drawings)["edges"]] == [False, True, False, True]
    away = [(41, 44, 47, 170), (167, 44, 173, 170), (44, 41, 170, 47), (44, 167, 170, 173)]  # 3 pt behind the outline
    _data, drawings, face = _draw(bars=away, fill=GREY)
    assert _support(face, drawings)["unsupported_share"] == 1.0


def _grid_cell():
    return [((100, 20), (100, 400)), ((134, 60), (134, 260)), ((40, 100), (300, 100)), ((20, 134), (220, 134))]


def test_a_cell_between_single_crossing_lines_is_not_a_walled_room():
    _data, drawings, _face = _draw(_grid_cell(), colour=GREY)
    result = _support(((100, 100), (134, 100), (134, 134), (100, 134)), drawings)
    assert result["status"] is ABSTAINED and result["unsupported_share"] > 0.99
    assert all(edge["unsupported"] > 0.99 * edge["length"] for edge in result["edges"])


@pytest.mark.parametrize("case", ["white-masks", "green-double-lines", "green-bars", "three-line-hatch"])
def test_look_alikes_are_not_wall_evidence(case):
    if case == "white-masks":
        _data, drawings, face = _draw(bars=BARS, fill=WHITE)
    elif case == "green-double-lines":
        _data, drawings, face = _draw(DOUBLE, colour=GREEN)
    elif case == "green-bars":
        _data, drawings, face = _draw(bars=BARS, fill=GREEN)
    else:
        middle = _loop([(47, 47), (167, 47), (167, 167), (47, 167)])
        _data, drawings, face = _draw(DOUBLE + middle)
    result = _support(face, drawings)
    assert result["status"] is ABSTAINED and result["unsupported_share"] > 0.9


def test_a_band_inside_the_face_does_not_support_it():
    _data, drawings, _face = _draw(DOUBLE)
    result = _support(OUTER, drawings)  # the outer outline: its wall pair lies inside the face
    assert result["status"] is ABSTAINED and result["unsupported_share"] > 0.9


def test_one_open_side_is_reported_on_that_edge_only():
    lines = [line for line in DOUBLE if line != ((170, 44), (170, 170))]  # the right wall loses its outer line
    _data, drawings, face = _draw(lines)
    result = _support(face, drawings)
    assert result["status"] is ABSTAINED
    assert [edge["unsupported"] > 1.0 for edge in result["edges"]] == [False, True, False, False]


def test_walls_that_only_end_on_an_edge_do_not_support_it():
    # the right side is one single line; two double walls run into it from outside, end on, not along it
    lines = [line for line in DOUBLE if line not in (((170, 44), (170, 170)),)]
    lines += [((164, 80), (260, 80)), ((164, 86), (260, 86)), ((164, 130), (260, 130)), ((164, 136), (260, 136))]
    _data, drawings, face = _draw(lines)
    result = _support(face, drawings)
    assert result["status"] is ABSTAINED and result["edges"][1]["paired"] == 0


def _draw_mixed(groups):
    """Line groups, each in its own ink."""
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    for lines, colour in groups:
        for a, b in lines:
            page.draw_line(a, b, color=colour, width=0.7)
    drawings = page.get_drawings()
    document.close()
    return drawings


def test_a_partner_must_be_drawn_in_the_same_ink():
    drawings = _draw_mixed([(_loop(list(FACE)), BLACK), (_loop(list(OUTER)), GREY)])
    assert _support(FACE, drawings)["status"] is ABSTAINED


def test_other_ink_nearby_does_not_spoil_a_wall():
    # equipment or drafting lines in other ink, inside the room or behind the wall, do not matter
    drawings = _draw_mixed([(DOUBLE, BLACK), (_loop([(53, 53), (161, 53), (161, 161), (53, 161)]), (0.2, 0.2, 0.8)),
                            (_loop([(41, 41), (173, 41), (173, 173), (41, 173)]), GREY)])
    assert _support(FACE, drawings)["status"] is CANDIDATE


def test_a_second_partner_position_makes_only_its_stretch_ambiguous():
    drawings = _draw_mixed([(DOUBLE + [((167, 60), (167, 90))], BLACK)])
    result = _support(FACE, drawings)
    right = result["edges"][1]
    assert result["status"] is ABSTAINED and right["unsupported"] == pytest.approx(30, abs=0.5)
    assert right["paired"] == pytest.approx(right["length"] - 30, abs=0.5)
    assert [edge["unsupported"] < 0.5 for edge in result["edges"]] == [True, False, True, True]


def test_a_face_drawn_two_or_three_times_a_little_apart_is_one_face():
    extra = _loop([(49.5, 49.5), (164.5, 49.5), (164.5, 164.5), (49.5, 164.5)])  # the inner face drawn twice
    outer = (_loop([(43.6, 43.6), (170.4, 43.6), (170.4, 170.4), (43.6, 170.4)])
             + _loop([(42.7, 42.7), (171.3, 42.7), (171.3, 171.3), (42.7, 171.3)]))  # the outer face three times
    drawings = _draw_mixed([(DOUBLE + extra + outer, BLACK)])
    assert _support(FACE, drawings)["status"] is CANDIDATE


def test_a_line_just_inside_the_room_does_not_break_the_wall_behind():
    inside = _loop([(50.9, 50.9), (163.1, 50.9), (163.1, 163.1), (50.9, 163.1)])
    thick = _loop([(42.5, 42.5), (171.5, 42.5), (171.5, 171.5), (42.5, 171.5)])  # a 7.5 pt wall
    for outer in (_loop(list(OUTER)), thick):
        drawings = _draw_mixed([(_loop(list(FACE)) + outer + inside, BLACK)])
        assert _support(FACE, drawings)["status"] is CANDIDATE


def _cut(lines, piece):
    out = []
    for a, b in lines:
        steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) // piece))
        points = [(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps) for i in range(steps + 1)]
        out += list(zip(points, points[1:]))
    return out


def test_walls_drawn_as_short_pieces_still_pair_but_short_ticks_do_not():
    assert _support(FACE, _draw_mixed([(_cut(DOUBLE, 5.0), BLACK)]))["status"] is CANDIDATE
    ticks = [((170, y), (170, y + 4)) for y in range(50, 164, 12)]  # 4 pt marks where a second face would be
    drawings = _draw_mixed([(_loop(list(FACE)) + ticks, BLACK)])
    assert _support(FACE, drawings)["edges"][1]["paired"] == 0


def _door_lines():
    lines = [line for line in DOUBLE if line not in (((170, 44), (170, 170)), ((164, 50), (164, 164)))]
    return lines + [((170, 44), (170, 90)), ((170, 120), (170, 170)), ((164, 50), (164, 90)),
                    ((164, 120), (164, 164)), ((164, 90), (170, 90)), ((164, 120), (170, 120))]


def test_a_doorway_counts_only_through_a_closure_the_caller_gives():
    _data, drawings, face = _draw(_door_lines())
    without = _support(face, drawings)
    assert without["status"] is ABSTAINED
    assert without["edges"][1]["unsupported"] == pytest.approx(30, abs=0.5)
    closure = SimpleNamespace(horizontal=False, band=(164.0, 170.0), gap_interval=(90.0, 120.0))
    closed = _support(face, drawings, [closure])
    assert closed["status"] is CANDIDATE and closed["edges"][1]["closure"] == pytest.approx(30, abs=0.5)
    beside = SimpleNamespace(horizontal=False, band=(190.0, 196.0), gap_interval=(90.0, 120.0))
    assert _support(face, drawings, [beside])["status"] is ABSTAINED  # a closure on another wall line is no use
    across = SimpleNamespace(horizontal=True, band=(164.0, 170.0), gap_interval=(90.0, 120.0))
    assert _support(face, drawings, [across])["status"] is ABSTAINED  # nor one running the other way


@pytest.mark.parametrize("options", [dict(shift=(137.25, 61.5)), dict(turn=True), dict(reverse=True), dict(split=True)],
                         ids=["shift", "quarter-turn", "order", "split"])
def test_the_result_does_not_depend_on_position_turn_order_or_splitting(options):
    _data, drawings, face = _draw(DOUBLE, **options)
    result = _support(face, drawings)
    assert result["status"] is CANDIDATE and result["unsupported_share"] < 0.01


def test_it_is_deterministic_and_changes_nothing():
    _data, drawings, face = _draw(DOUBLE)
    before = copy.deepcopy([(d.get("color"), d.get("fill"), list(d["items"])) for d in drawings])
    assert _support(face, drawings) == _support(face, drawings)
    assert [(d.get("color"), d.get("fill"), list(d["items"])) for d in drawings] == before
    assert face_wall_support(((0, 0), (10, 10), (10, 0), (0, 10)), drawings)["status"] is ABSTAINED  # self-crossing


def test_real_builder_rings_with_their_doorway_closures_are_supported():
    # two double-wall rooms sharing a wall with a doorway: the builder's own rings and closures
    lines = (_loop([(44, 44), (290, 44), (290, 170), (44, 170)]) + _loop([(50, 50), (164, 50), (164, 164), (50, 164)])
             + _loop([(170, 50), (284, 50), (284, 164), (170, 164)]))
    lines = [line for line in lines if line not in (((164, 50), (164, 164)), ((170, 164), (170, 50)))]
    lines += [((164, 50), (164, 90)), ((164, 120), (164, 164)), ((170, 50), (170, 90)), ((170, 120), (170, 164)),
              ((164, 90), (170, 90)), ((164, 120), (170, 120))]
    data, drawings, _face = _draw(lines)
    built = build_from_pdf_bytes(data, source_sha256=hashlib.sha256(data).hexdigest(), page_index=0,
                                 dark_painted_wall_source=True)
    rings = [ring for ring in built.rings if ring.status is EvidenceResolutionStatus.CANDIDATE]
    assert len(rings) == 2 and built.closures
    for ring in rings:
        assert face_wall_support(ring.polygon_pdf_pts, drawings, built.closures)["status"] is CANDIDATE
