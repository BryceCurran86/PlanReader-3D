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


def _jamb_stub_room(stub, *, drawn=True):
    """The right wall has a doorway starting ``stub`` pt below the top inner corner; the closure spans the doorway."""
    lines = [line for line in DOUBLE if line not in (((170, 44), (170, 170)), ((164, 50), (164, 164)))]
    lines += [((170, 44), (170, 50 + stub)), ((170, 110), (170, 170)), ((164, 110), (164, 164))]
    if drawn:
        lines += [((164, 50), (164, 50 + stub))]
    _data, drawings, face = _draw(lines)
    closure = SimpleNamespace(horizontal=False, band=(164.0, 170.0), gap_interval=(50.0 + stub, 110.0))
    return _support(face, drawings, [closure])


def test_a_drawn_door_jamb_stub_no_longer_than_the_wall_is_thick_is_part_of_it():
    result = _jamb_stub_room(5.0)
    assert result["status"] is CANDIDATE and result["edges"][1]["wall_end"] == pytest.approx(5, abs=0.5)


@pytest.mark.parametrize("stub,drawn", [(5.0, False), (7.5, True)], ids=["not-drawn", "longer-than-the-wall"])
def test_a_stub_without_drawn_geometry_or_longer_than_the_wall_is_not(stub, drawn):
    result = _jamb_stub_room(stub, drawn=drawn)
    assert result["status"] is ABSTAINED and result["edges"][1]["wall_end"] == 0


NOTCHED = ((50, 50), (100, 50), (100, 100), (106, 100), (106, 50), (164, 50), (164, 164), (50, 164))


@pytest.mark.parametrize("cap", [True, False], ids=["capped", "open"])
def test_the_drawn_end_of_a_partition_is_part_of_it_and_an_open_end_is_not(cap):
    lines = [((44, 44), (170, 44)), ((170, 44), (170, 170)), ((170, 170), (44, 170)), ((44, 170), (44, 44)),
             ((50, 50), (100, 50)), ((106, 50), (164, 50)), ((164, 50), (164, 164)), ((164, 164), (50, 164)),
             ((50, 164), (50, 50)), ((100, 50), (100, 100)), ((106, 50), (106, 100))]
    if cap:
        lines.append(((100, 100), (106, 100)))
    drawings = _draw_mixed([(lines, BLACK)])
    result = _support(NOTCHED, drawings)
    assert result["status"] is (CANDIDATE if cap else ABSTAINED)
    assert (result["edges"][2]["wall_end"] > 5.5) is cap


@pytest.mark.parametrize("cap", [[((100, 100), (102, 100)), ((104, 100), (106, 100))], [((100, 100), (103, 100))]],
                         ids=["dashed", "half"])
def test_a_partly_drawn_end_is_not_a_wall_end(cap):
    partition = [((100, 50), (100, 100)), ((106, 50), (106, 100))]
    drawings = _draw_mixed([([line for line in DOUBLE] + partition + cap, BLACK)])
    assert _support(NOTCHED, drawings)["edges"][2]["wall_end"] == 0


def test_a_break_in_the_middle_of_a_wall_is_reported_not_filled():
    lines = [line for line in DOUBLE if line != ((170, 44), (170, 170))] + [((170, 44), (170, 100)), ((170, 104), (170, 170))]
    drawings = _draw_mixed([(lines, BLACK)])
    right = _support(FACE, drawings)["edges"][1]
    assert right["wall_end"] == 0 and right["unsupported"] == pytest.approx(4, abs=0.5)


def test_a_drawn_end_in_another_ink_is_not_the_same_wall():
    lines = [line for line in DOUBLE]
    partition = [((100, 50), (100, 100)), ((106, 50), (106, 100))]
    drawings = _draw_mixed([(lines + partition, BLACK), ([((100, 100), (106, 100))], GREY)])
    assert _support(NOTCHED, drawings)["edges"][2]["wall_end"] == 0


def _thick_room(gap, extra=(), *, colour=BLACK):
    """A room in walls ``gap`` pt thick drawn as two closed outlines (the corners give each pair its returns)."""
    outer = [(50 - gap, 50 - gap), (164 + gap, 50 - gap), (164 + gap, 164 + gap), (50 - gap, 164 + gap)]
    return _draw_mixed([(_loop(list(FACE)) + _loop(outer) + list(extra), colour)])


def test_a_thick_wall_is_only_a_separate_candidate():
    result = _support(FACE, _thick_room(11.0))
    assert result["status"] is ABSTAINED and result["unsupported_share"] > 0.99
    assert result["wide_candidate_share"] > 0.99
    assert all(edge["wide_candidate"] > 0.99 * edge["length"] for edge in result["edges"])


@pytest.mark.parametrize("case", ["too-thick", "normal", "hatch", "no-returns", "other-ink", "short-partner"])
def test_thick_wall_look_alikes_are_not_candidates(case):
    if case == "too-thick":
        drawings = _thick_room(15.0)
    elif case == "normal":
        drawings = _thick_room(6.0)
    elif case == "hatch":
        steps = [_loop([(50 - g, 50 - g), (164 + g, 50 - g), (164 + g, 164 + g), (50 - g, 164 + g)]) for g in (22.0,)]
        drawings = _thick_room(11.0, [line for loop in steps for line in loop])
    elif case == "no-returns":
        drawings = _draw_mixed([([((20, 50), (200, 50)), ((20, 39), (200, 39))], BLACK)])
        assert _support(((50, 50), (164, 50), (164, 100), (50, 100)), drawings)["wide_candidate_share"] == 0
        return
    elif case == "other-ink":
        drawings = _draw_mixed([(_loop(list(FACE)), BLACK),
                                (_loop([(39, 39), (175, 39), (175, 175), (39, 175)]), GREY)])
    else:
        ticks = [((175, 60), (175, 90)), ((164, 60), (175, 60)), ((164, 90), (175, 90))]
        drawings = _draw_mixed([(_loop(list(FACE)) + ticks, BLACK)])
        assert _support(FACE, drawings)["edges"][1]["wide_candidate"] == 0
        return
    assert _support(FACE, drawings)["wide_candidate_share"] == 0


@pytest.mark.parametrize("gaps", [(3.0, 6.0, 11.0), (9.0, 12.5)], ids=["close-hatch", "two-wide-faces"])
def test_several_faces_behind_are_never_a_wide_wall(gaps):
    extra = [line for g in gaps[1:] for line in _loop([(50 - g, 50 - g), (164 + g, 50 - g), (164 + g, 164 + g),
                                                        (50 - g, 164 + g)])]
    assert _support(FACE, _thick_room(gaps[0], extra))["wide_candidate_share"] == 0


def test_a_return_that_does_not_cross_the_whole_wall_is_not_one():
    pair = [((40, 50), (180, 50)), ((40, 39), (180, 39))]
    half = [((40, 45), (40, 50)), ((180, 39), (180, 45))]
    face = ((50, 50), (170, 50), (170, 100), (50, 100))
    assert _support(face, _draw_mixed([(pair + half, BLACK)]))["edges"][0]["wide_candidate"] == 0


def test_a_drawn_end_cap_is_a_wall_return():
    pair = [((40, 50), (180, 50)), ((40, 39), (180, 39))]
    face = ((50, 50), (170, 50), (170, 100), (50, 100))
    assert _support(face, _draw_mixed([(pair, BLACK)]))["edges"][0]["wide_candidate"] == 0
    capped = pair + [((40, 39), (40, 50)), ((180, 39), (180, 50))]
    assert _support(face, _draw_mixed([(capped, BLACK)]))["edges"][0]["wide_candidate"] > 119


def test_lines_that_never_run_beside_an_edge_change_nothing():
    # short lines past the end of the right wall, stepping from its face to its outer line
    ladder = [((x, 172), (x, 188)) for x in (165, 166, 167, 168, 169)]
    plain = _support(FACE, _draw_mixed([(DOUBLE, BLACK)]))
    crowded = _support(FACE, _draw_mixed([(DOUBLE + ladder, BLACK)]))
    assert crowded["status"] is plain["status"] is CANDIDATE
    assert crowded["edges"] == plain["edges"]


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


# Panel candidate: a white-filled strip drawn on both long sides (8.6 pt, too thick to count as a pair).
PANEL_OUTER = ((41.4, 41.4), (172.6, 41.4), (172.6, 172.6), (41.4, 172.6))
PANEL_BARS = [(41.4, 41.4, 172.6, 50), (41.4, 164, 172.6, 172.6), (41.4, 50, 50, 164), (164, 50, 172.6, 164)]
PANEL_LINES = _loop(list(PANEL_OUTER)) + _loop(list(FACE))


def _panel(face_lines=PANEL_LINES, bars=PANEL_BARS, **options):
    _data, drawings, face = _draw(face_lines, bars, fill=WHITE, **options)
    return _support(face, drawings)


@pytest.mark.parametrize("options", [{}, {"turn": True}, {"shift": (213.5, 91.25)}, {"reverse": True}, {"split": True}],
                         ids=["plain", "turned", "shifted", "reversed", "split"])
def test_white_panel_walls_are_reported_as_candidates_and_never_counted(options):
    result = _panel(**options)
    assert result["status"] is ABSTAINED and result["unsupported_share"] > 0.99
    assert result["panel_candidate_share"] > 0.9


@pytest.mark.parametrize("lines,bars", [
    (_loop(list(FACE)), PANEL_BARS),  # a mask: only the near side is drawn
    (PANEL_LINES, [(50, 50, 70, 58.6)]),  # a short box (equipment): shorter than three times its thickness
    (_loop([(30, 30), (184, 30), (184, 184), (30, 184)]) + _loop(list(FACE)),
     [(30, 30, 184, 50), (30, 164, 184, 184), (30, 50, 50, 164), (164, 50, 184, 164)]),  # 20 pt: too thick
], ids=["one_side", "short_box", "too_thick"])
def test_look_alikes_are_not_panel_candidates(lines, bars):
    assert _panel(lines, bars)["panel_candidate_share"] == 0.0


def test_a_strip_inside_the_room_is_not_a_panel_wall_of_it():
    inside = _loop([(58.6, 58.6), (155.4, 58.6), (155.4, 155.4), (58.6, 155.4)]) + _loop(list(FACE))
    bars = [(50, 50, 164, 58.6), (50, 155.4, 164, 164), (50, 58.6, 58.6, 155.4), (155.4, 58.6, 164, 155.4)]
    assert _panel(inside, bars)["panel_candidate_share"] == 0.0
