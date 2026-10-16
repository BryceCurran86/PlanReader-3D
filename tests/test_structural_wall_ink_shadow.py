"""Structural wall-ink shadow: positives, look-alike negatives, ambiguity, metamorphic and invariance tests."""
from __future__ import annotations

import copy
import itertools
import random

import pytest

import pb_structural_wall_ink_shadow as ink
from pb_structural_wall_ink_shadow import (
    NOT_WALL_INK,
    REASON_DASHED_OR_PATTERNED,
    REASON_RULED_RING,
    REASON_LIGHTER_INK,
    REASON_NO_PARTNER,
    REASON_OUTLINED_GLYPH_RUN,
    REASON_SCOPE_TOO_LARGE,
    REASON_SHEET_FRAME_RING,
    UNPROVEN,
    WALL_NETWORK_INK_CANDIDATE,
    classify_structural_wall_ink,
)

PAGE = (842.0, 595.0)
BLACK = (0.0, 0.0, 0.0)
GREY = (0.6, 0.6, 0.6)


def seg(ident, x1, y1, x2, y2, *, width=0.96, stroke=BLACK, dashes="[] 0", path=None, fill=None):
    return {
        "id": ident, "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), "kind": "line",
        "stroke": stroke, "stroke_present": stroke is not None, "width": width, "width_present": True,
        "dashes": dashes, "fill": fill, "fill_present": fill is not None,
        "path_index": ident if path is None else path,
    }


def strip(prefix, x0, y0, x1, y1, **kw):
    """One drawn wall piece: two long faces plus two end caps, like a stroked wall outline."""
    return [
        seg(f"{prefix}.a", x0, y0, x1, y0, path=f"{prefix}", **kw),
        seg(f"{prefix}.b", x1, y0, x1, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.c", x1, y1, x0, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.d", x0, y1, x0, y0, path=f"{prefix}", **kw),
    ]


def building(ox=100.0, oy=100.0, w=300.0, h=200.0, t=2.6, **kw):
    out = []
    out += strip("top", ox, oy, ox + w, oy + t, **kw)
    out += strip("bot", ox, oy + h - t, ox + w, oy + h, **kw)
    out += strip("left", ox, oy + t, ox + t, oy + h - t, **kw)
    out += strip("right", ox + w - t, oy + t, ox + w, oy + h - t, **kw)
    out += strip("part", ox + w / 2 - t / 2, oy + t, ox + w / 2 + t / 2, oy + h - t, **kw)
    return out


def run(segments, page=PAGE):
    return classify_structural_wall_ink(segments, page_width=page[0], page_height=page[1])


def labels(report):
    return {d.source_primitive_id: d.classification for d in report.decisions}


def reasons(report):
    return {d.source_primitive_id: d.reason_codes for d in report.decisions}


# ---------------------------------------------------------------- positives
def test_paired_face_building_network_is_a_candidate():
    report = run(building())
    got = labels(report)
    assert set(got.values()) == {WALL_NETWORK_INK_CANDIDATE}
    assert report.network_count == 1
    assert report.shadow_only is True and report.live_effect is False and report.wall_authority_granted is False


def test_filled_strip_walls_are_candidates_including_end_caps():
    segs = []
    for name, (x0, y0, x1, y1) in {
        "t": (100, 100, 400, 102.6), "b": (100, 297.4, 400, 300), "l": (100, 102.6, 102.6, 297.4),
        "r": (397.4, 102.6, 400, 297.4),
    }.items():
        segs += [dict(s, stroke=None, stroke_present=False, width=None, fill=BLACK, fill_present=True)
                 for s in strip(name, x0, y0, x1, y1)]
    got = labels(run(segs))
    assert set(got.values()) == {WALL_NETWORK_INK_CANDIDATE}


def test_walls_drawn_as_one_heavy_line_are_found_when_they_form_a_network():
    heavy = dict(width=0.6)
    segs = [seg("w1", 100, 100, 400, 100, **heavy), seg("w2", 400, 100, 400, 300, **heavy),
            seg("w3", 400, 300, 100, 300, **heavy), seg("w4", 100, 300, 100, 100, **heavy),
            seg("w5", 250, 100, 250, 300, **heavy)]
    # lighter ink of the same drawing: fixtures drawn with a thin line
    segs += [seg("f1", 120, 120, 160, 120, width=0.24), seg("f2", 160, 120, 160, 150, width=0.24)]
    report = run(segs)
    got = labels(report)
    assert all(got[f"w{i}"] == WALL_NETWORK_INK_CANDIDATE for i in range(1, 6))
    assert got["f1"] == got["f2"] == UNPROVEN
    assert REASON_HEAVIEST_SINGLE in reasons(report)["w1"]


REASON_HEAVIEST_SINGLE = ink.REASON_HEAVIEST_SINGLE_STROKE_NETWORK


def test_a_door_sized_gap_in_a_wall_keeps_both_sides_in_one_network():
    t = 2.6
    segs = []
    segs += strip("tl", 100, 100, 215, 100 + t)
    segs += strip("tr", 215 + 24.0, 100, 400, 100 + t)          # about 24 pt opening in the top wall
    segs += strip("bot", 100, 300 - t, 400, 300)
    segs += strip("left", 100, 100 + t, 100 + t, 300 - t)
    segs += strip("right", 400 - t, 100 + t, 400, 300 - t)
    report = run(segs)
    got = labels(report)
    assert set(got.values()) == {WALL_NETWORK_INK_CANDIDATE}
    assert any(ink.REASON_CONTINUED_ACROSS_GAP in r for r in reasons(report).values()) or report.network_count == 1


# ---------------------------------------------------------------- look-alike negatives
def test_sheet_frame_ring_is_a_negative_and_does_not_take_the_building_with_it():
    frame = [seg("fr1", 20, 20, 822, 20, width=1.4), seg("fr2", 822, 20, 822, 575, width=1.4),
             seg("fr3", 822, 575, 20, 575, width=1.4), seg("fr4", 20, 575, 20, 20, width=1.4)]
    report = run(building() + frame)
    got = labels(report)
    assert all(got[f"fr{i}"] == NOT_WALL_INK for i in range(1, 5))
    assert all(REASON_SHEET_FRAME_RING in reasons(report)[f"fr{i}"] for i in range(1, 5))
    assert all(got[d] == WALL_NETWORK_INK_CANDIDATE for d in got if not d.startswith("fr"))


def test_far_apart_parallel_lines_are_not_a_wall_pair():
    # a room's two sides, 60 pt apart and long enough that only the thickness bound (not the aspect rule) refuses them
    segs = [seg("p1", 60, 100, 800, 100), seg("p2", 60, 160, 800, 160)]
    report = run(segs)
    assert labels(report) == {"p1": UNPROVEN, "p2": UNPROVEN}
    assert all(REASON_NO_PARTNER in r for r in reasons(report).values())     # not even paired


def test_a_small_paired_structure_is_an_island_not_a_building_network():
    cabinet = strip("cab", 500, 400, 540, 402.6)
    report = run(cabinet)
    assert set(labels(report).values()) == {UNPROVEN}
    rs = reasons(report)
    assert ink.REASON_SMALL_ISLAND in rs["cab.a"] and ink.REASON_SMALL_ISLAND in rs["cab.c"]   # the two long faces


def test_primitives_shorter_than_a_face_run_are_unproven():
    ticks = [seg(f"t{i}", 500 + 10 * i, 500, 501.2 + 10 * i, 500) for i in range(4)]
    got = labels(run(building() + ticks))
    assert all(got[f"t{i}"] == UNPROVEN for i in range(4))
    assert all(ink.REASON_BELOW_MIN_LENGTH in reasons(run(building() + ticks))[f"t{i}"] for i in range(4))


def test_lone_dimension_string_with_ticks_is_not_a_wall_network():
    segs = [seg("dim", 100, 80, 400, 80, width=0.24)]
    segs += [seg(f"tick{i}", 100 + 50 * i, 76, 100 + 50 * i, 84, width=0.24) for i in range(7)]
    got = labels(run(building() + segs))
    assert got["dim"] == UNPROVEN
    assert all(got[f"tick{i}"] != WALL_NETWORK_INK_CANDIDATE for i in range(7))


def test_lighter_ink_copy_of_the_building_is_unproven_not_a_candidate():
    segs = building() + [dict(s, id="g_" + s["id"], path="g_" + str(s["path_index"]), stroke=GREY) for s in building()]
    report = run(segs)
    got = labels(report)
    assert all(got[d] == UNPROVEN for d in got if d.startswith("g_"))
    assert all(REASON_LIGHTER_INK in reasons(report)[d] for d in got if d.startswith("g_"))


def test_dashed_strokes_are_a_typed_negative():
    segs = [seg(f"c{i}", 100, 100 + 20 * i, 400, 100 + 20 * i, dashes="[3 3] 0") for i in range(3)]
    report = run(building() + segs)
    got = labels(report)
    assert all(got[f"c{i}"] == NOT_WALL_INK and REASON_DASHED_OR_PATTERNED in reasons(report)[f"c{i}"] for i in range(3))


def _letter(prefix, x, base_y, h=8.0):
    return [seg(f"{prefix}.1", x, base_y - h, x, base_y, width=0.96, path=prefix),
            seg(f"{prefix}.2", x, base_y - h, x + 4, base_y - h, width=0.96, path=prefix),
            seg(f"{prefix}.3", x + 4, base_y - h, x + 4, base_y, width=0.96, path=prefix)]


def test_outlined_lettering_on_a_baseline_is_a_negative():
    word = list(itertools.chain.from_iterable(_letter(f"L{i}", 500 + 7 * i, 520) for i in range(6)))
    report = run(building() + word)
    got = labels(report)
    assert all(got[s["id"]] == NOT_WALL_INK for s in word)
    assert all(REASON_OUTLINED_GLYPH_RUN in reasons(report)[s["id"]] for s in word)


def test_two_small_paths_are_not_enough_to_call_lettering():
    two = list(itertools.chain.from_iterable(_letter(f"L{i}", 500 + 7 * i, 520) for i in range(2)))
    got = labels(run(building() + two))
    assert all(got[s["id"]] != NOT_WALL_INK for s in two)


def test_wall_pieces_are_never_called_lettering_when_they_are_long():
    got = labels(run(building()))
    assert NOT_WALL_INK not in got.values()


# ---------------------------------------------------------------- invariance / metamorphic
def _decisions(report):
    return {d.source_primitive_id: (d.classification, d.reason_codes) for d in report.decisions}


def test_input_order_does_not_change_any_decision():
    base = building() + [seg("dim", 100, 80, 400, 80, width=0.24)]
    expected = _decisions(run(base))
    rng = random.Random(7)
    for _ in range(5):
        shuffled = list(base)
        rng.shuffle(shuffled)
        assert _decisions(run(shuffled)) == expected


def test_decisions_are_deterministic_and_inputs_are_not_mutated():
    base = building() + [seg("dim", 100, 80, 400, 80, width=0.24)]
    frozen = copy.deepcopy(base)
    first, second = run(base), run(base)
    assert first == second
    assert base == frozen


def test_translation_does_not_change_decisions():
    base = building()
    moved = [dict(s, x1=s["x1"] + 37.5, x2=s["x2"] + 37.5, y1=s["y1"] + 11.25, y2=s["y2"] + 11.25) for s in base]
    assert _decisions(run(moved)) == _decisions(run(base))


def test_a_quarter_turn_does_not_change_decisions():
    base = building()
    turned = [dict(s, x1=-s["y1"], y1=s["x1"], x2=-s["y2"], y2=s["x2"]) for s in base]
    turned = [dict(s, x1=s["x1"] + 600, x2=s["x2"] + 600) for s in turned]
    assert _decisions(run(turned, page=(PAGE[1], PAGE[0]))) == _decisions(run(base))


def test_uniform_scale_of_the_drawing_and_sheet_does_not_change_decisions():
    base = building() + [seg("dim", 100, 80, 400, 80, width=0.24)]
    factor = 1.5
    scaled = [dict(s, x1=s["x1"] * factor, y1=s["y1"] * factor, x2=s["x2"] * factor, y2=s["y2"] * factor,
                   width=s["width"] * factor) for s in base]
    assert _decisions(run(scaled, page=(PAGE[0] * factor, PAGE[1] * factor))) == _decisions(run(base))


def test_splitting_wall_faces_into_pieces_does_not_change_the_decision():
    base = building()
    expected = {s["id"]: labels(run(base))[s["id"]] for s in base}
    pieces = []
    owner = {}
    for s in base:
        n = 3
        for k in range(n):
            f0, f1 = k / n, (k + 1) / n
            pid = f"{s['id']}#{k}"
            pieces.append(dict(s, id=pid, x1=s["x1"] + (s["x2"] - s["x1"]) * f0, y1=s["y1"] + (s["y2"] - s["y1"]) * f0,
                               x2=s["x1"] + (s["x2"] - s["x1"]) * f1, y2=s["y1"] + (s["y2"] - s["y1"]) * f1))
            owner[pid] = s["id"]
    got = labels(run(pieces))
    assert all(got[pid] == expected[owner[pid]] for pid in owner)


def test_unrelated_content_and_a_larger_sheet_do_not_change_the_building():
    base = building()
    expected = {k: v for k, v in _decisions(run(base)).items()}
    extra = [seg(f"far{i}", 600, 40 + 9 * i, 700, 40 + 9 * i, width=0.24) for i in range(20)]
    after = _decisions(run(base + extra))
    assert all(after[k] == v for k, v in expected.items())


# ---------------------------------------------------------------- bounds and input hygiene
def test_oversized_input_is_returned_entirely_unproven():
    original = ink.MAX_STRUCTURAL_INK_SEGMENTS
    try:
        ink.MAX_STRUCTURAL_INK_SEGMENTS = 5
        report = run(building())
    finally:
        ink.MAX_STRUCTURAL_INK_SEGMENTS = original
    assert set(labels(report).values()) == {UNPROVEN}
    assert all(REASON_SCOPE_TOO_LARGE in r for r in reasons(report).values())


def test_duplicate_ids_and_bad_pages_are_rejected():
    dup = [seg("a", 0, 0, 10, 0), seg("a", 0, 5, 10, 5)]
    with pytest.raises(ValueError):
        run(dup)
    with pytest.raises(ValueError):
        classify_structural_wall_ink([], page_width=0.0, page_height=100.0)
    with pytest.raises(ValueError):
        classify_structural_wall_ink([], page_width=float("nan"), page_height=100.0)


def test_segments_without_graphic_state_are_retained_as_unproven():
    odd = {"id": "x", "x1": 0.0, "y1": 0.0, "x2": 50.0, "y2": 0.0}
    nogeo = {"id": "y"}
    report = run(building() + [odd, nogeo])
    assert labels(report)["x"] == UNPROVEN and labels(report)["y"] == UNPROVEN


def test_class_table_reports_ink_classes_and_candidate_counts():
    report = run(building())
    assert report.class_table
    assert sum(row.candidate_segment_count for row in report.class_table) == len(building())


def test_a_room_sized_box_alone_is_an_island_but_a_short_wall_return_on_a_building_is_a_candidate():
    box = (strip("b1", 500, 400, 570, 402.6) + strip("b2", 500, 467.4, 570, 470)
           + strip("b3", 500, 402.6, 502.6, 467.4) + strip("b4", 567.4, 402.6, 570, 467.4))
    alone = run(box)
    assert set(labels(alone).values()) == {UNPROVEN}                       # below building scale: retained, not proven
    stub = strip("stub", 150, 102.6, 152.6, 127.6)                          # a 25 pt return (9.6 thicknesses) off the top wall
    got = labels(run(building() + stub))
    assert all(got[s["id"]] == WALL_NETWORK_INK_CANDIDATE for s in stub)


def test_a_short_paired_run_touching_the_building_is_judged_on_its_own_length():
    # two separate 10 pt faces 1 pt apart (10 thicknesses long) hanging off the top wall, each its own path
    pair = [seg("pair1", 200, 102.6, 200, 112.6), seg("pair2", 201, 102.6, 201, 112.6)]
    got = labels(run(building() + pair))
    assert got["pair1"] == got["pair2"] == WALL_NETWORK_INK_CANDIDATE
    # and a single 10 pt line of another ink class with no partner is not
    lone = labels(run(building() + [seg("lone", 200, 102.6, 200, 112.6, width=0.5)]))
    assert lone["lone"] == UNPROVEN


def _box(prefix, x0, y0, x1, y1):
    return strip(prefix, x0, y0, x1, y1, width=0.96)


def test_glyph_sized_pieces_touching_the_wall_network_are_never_rejected_but_an_isolated_row_is():
    # three 6 pt posts standing on the inside face of the top wall (their top edges lie on the wall face)
    posts = list(itertools.chain.from_iterable(_box(f"post{i}", 150 + 14 * i, 102.6, 156 + 14 * i, 108.6) for i in range(3)))
    # the same posts as a free row in the middle of a room, touching nothing
    free = list(itertools.chain.from_iterable(_box(f"free{i}", 150 + 14 * i, 200, 156 + 14 * i, 206) for i in range(3)))
    report = run(building() + posts + free)
    got, why = labels(report), reasons(report)
    assert all(got[s["id"]] == UNPROVEN and ink.REASON_GLYPH_RUN_ATTACHED in why[s["id"]] for s in posts)
    assert all(got[s["id"]] == NOT_WALL_INK for s in free)


def test_a_touching_chain_of_small_pieces_is_attached_as_a_whole():
    # one baseline row of three pieces; only P1 stands on the wall, P2 touches P1 only, P3 touches P2 only
    p1 = _box("p1", 150, 102.6, 156, 108.6)
    p2 = _box("p2", 156, 105.6, 162, 108.6)
    p3 = _box("p3", 162, 105.6, 168, 108.6)
    got = labels(run(building() + p1 + p2 + p3))
    assert all(got[s["id"]] == UNPROVEN for s in p1 + p2 + p3)
    # P2 and P3 alone, with nothing standing on a wall, are an isolated row of small paths
    alone = labels(run(building() + p2 + p3 + _box("p4", 168, 105.6, 174, 108.6)))
    assert all(alone[s["id"]] == NOT_WALL_INK for s in p2 + p3)


# ---------------------------------------------------------------- opening-gap evidence
def _door_building(gap=24.0, t=2.6):
    segs = []
    segs += strip("tl", 100, 100, 215, 100 + t)
    segs += strip("tr", 215 + gap, 100, 400, 100 + t)
    segs += strip("bot", 100, 300 - t, 400, 300)
    segs += strip("left", 100, 100 + t, 100 + t, 300 - t)
    segs += strip("right", 400 - t, 100 + t, 400, 300 - t)
    return segs


def test_a_door_sized_interruption_is_reported_as_a_gap_on_both_faces():
    report = run(_door_building())
    top = [g for g in report.opening_gaps if g.end_a[0] < 220 < g.end_b[0] and g.end_a[1] < 110]
    assert len(top) == 2                                                    # one per face line
    assert all(abs(g.gap_length_pt - 24.0) < 0.01 and abs(g.thickness_pt - 2.6) < 0.01 for g in top)
    assert all(g.source_primitive_id_a.startswith("tl.") and g.source_primitive_id_b.startswith("tr.") for g in top)
    # evidence of an interruption only: nothing about the opening kind, host, frame or size is claimed
    assert not any(hasattr(g, attr) for g in top for attr in ("kind", "host", "frame", "width_mm"))


def test_a_wide_gap_needs_the_partner_face_to_be_interrupted_too():
    t = 2.6
    wide = 100.0                                                             # 38 thicknesses: not a door-sized face gap
    both = _door_building(gap=wide)
    assert any(abs(g.gap_length_pt - wide) < 0.01 for g in run(both).opening_gaps)
    # the same gap on one face only (the other face runs straight through) is not accepted
    one_face = []
    one_face += [seg("a1", 100, 100, 215, 100), seg("a2", 215 + wide, 100, 400, 100)]
    one_face += [seg("a3", 100, 100 + t, 400, 100 + t)]
    one_face += strip("bot", 100, 300 - t, 400, 300) + strip("left", 100, 100 + t, 100 + t, 300 - t)
    one_face += strip("right", 400 - t, 100 + t, 400, 300 - t)
    assert not [g for g in run(one_face).opening_gaps if abs(g.gap_length_pt - wide) < 0.01]


def _overhang_building(wide=100.0, left_overhang=4.0, right_overhang=0.0, t=2.6):
    """A top wall interrupted by an opening ``wide`` apart; the lower face of the left piece stops ``left_overhang`` short
    of the upper face (a jamb symbol or an end cap), so the two faces' gap ends do not line up to a point."""
    segs = [seg("a1", 100, 100, 215, 100), seg("a2", 215 + wide, 100, 400, 100),
            seg("c1", 100, 100 + t, 215 - left_overhang, 100 + t), seg("c2", 215 + wide + right_overhang, 100 + t, 400, 100 + t)]
    segs += strip("bot", 100, 300 - t, 400, 300) + strip("left", 100, 100 + t, 100 + t, 300 - t)
    segs += strip("right", 400 - t, 100 + t, 400, 300 - t)
    return segs


def _gaps_of_length(report, length):
    return [g for g in report.opening_gaps if abs(g.gap_length_pt - length) < 0.01]


def test_a_wide_opening_is_found_when_a_jamb_symbol_makes_the_partner_face_ends_overhang():
    t = 2.6
    wide = 100.0                                                             # 38 thicknesses: needs the partner face
    exact = run(_overhang_building(left_overhang=0.0))
    assert _gaps_of_length(exact, wide)                                      # aligned ends: accepted as before
    overhung = run(_overhang_building(left_overhang=4.0, right_overhang=3.0))
    got = _gaps_of_length(overhung, wide)
    assert got, "an overhang of a jamb symbol must not hide the opening"
    assert all(abs(g.thickness_pt - t) < 0.01 for g in got)
    assert {g.source_primitive_id_a for g in got} <= {"a1", "c1"} and {g.source_primitive_id_b for g in got} <= {"a2", "c2"}
    # both faces report it, each against the other: the upper face's 100 pt and the lower face's 107 pt
    assert _gaps_of_length(overhung, 107.0)


def test_a_partner_face_ending_further_than_the_face_gap_bound_does_not_make_the_wide_opening():
    far = run(_overhang_building(left_overhang=ink.MAX_FACE_GAP_PT + 4.0))
    assert not _gaps_of_length(far, 100.0)


def test_the_bound_applies_to_the_far_side_of_the_opening_as_well():
    assert _gaps_of_length(run(_overhang_building(left_overhang=0.0, right_overhang=ink.MAX_FACE_GAP_PT - 2.0)), 100.0)
    assert not _gaps_of_length(run(_overhang_building(left_overhang=0.0, right_overhang=ink.MAX_FACE_GAP_PT + 4.0)), 100.0)


def test_partner_faces_may_also_run_a_symbol_length_into_the_opening():
    # the lower faces run 4 pt and 3 pt INTO the opening (an end cap or a door frame): still the same wall, interrupted
    got = _gaps_of_length(run(_overhang_building(left_overhang=-4.0, right_overhang=-3.0)), 100.0)
    assert got and {g.source_primitive_id_a for g in got} <= {"a1", "c1"}
    # but a partner face that fills most of the opening is a wall through the opening, not an interruption of it
    through = _overhang_building(left_overhang=-70.0, right_overhang=-20.0)
    assert not _gaps_of_length(run(through), 100.0)
    # 20 pt (7.7 thicknesses) into the opening is already more than a jamb symbol: refused
    assert not _gaps_of_length(run(_overhang_building(left_overhang=-20.0)), 100.0)


def test_a_parallel_line_beside_the_partner_face_does_not_block_the_opening():
    # a fixture line 3 pt inside the room, running across the whole opening, is not on the partner face's line
    got = _gaps_of_length(run(_overhang_building(left_overhang=4.0) + [seg("fixture", 150, 105.6, 360, 105.6)]), 100.0)
    assert got and {g.source_primitive_id_a for g in got} <= {"a1", "c1"}


def test_a_wide_opening_is_refused_when_solid_wall_ink_runs_through_the_partner_line():
    t = 2.6
    segs = [seg("a1", 100, 100, 215, 100), seg("a2", 315, 100, 400, 100),
            seg("c1", 100, 100 + t, 400, 100 + t)]                           # the other face runs straight through
    segs += strip("bot", 100, 300 - t, 400, 300) + strip("left", 100, 100 + t, 100 + t, 300 - t)
    segs += strip("right", 400 - t, 100 + t, 400, 300 - t)
    assert not _gaps_of_length(run(segs), 100.0)


def test_the_overhang_opening_rule_is_deterministic_order_and_translation_invariant():
    base = _overhang_building(left_overhang=4.0)
    expected = run(base).opening_gaps
    shuffled = list(base)
    random.Random(11).shuffle(shuffled)
    assert run(shuffled).opening_gaps == expected
    moved = [dict(s, x1=s["x1"] + 13.0, x2=s["x2"] + 13.0, y1=s["y1"] - 7.0, y2=s["y2"] - 7.0) for s in base]
    got = run(moved).opening_gaps
    assert [(round(g.end_a[0] - 13.0, 3), round(g.end_a[1] + 7.0, 3), g.gap_length_pt) for g in got] == [
        (g.end_a[0], g.end_a[1], g.gap_length_pt) for g in expected]


def test_the_overhang_opening_rule_is_invariant_to_a_quarter_turn_splitting_and_unrelated_content():
    base = _overhang_building(left_overhang=4.0, right_overhang=3.0)
    expected = sorted(g.gap_length_pt for g in run(base).opening_gaps)
    assert 100.0 in expected and 107.0 in expected
    turned = [dict(s, x1=-s["y1"] + 700.0, y1=s["x1"], x2=-s["y2"] + 700.0, y2=s["x2"]) for s in base]
    assert sorted(g.gap_length_pt for g in run(turned, page=(PAGE[1] + 200, PAGE[0])).opening_gaps) == expected
    split = []
    for s in base:
        mx, my = (s["x1"] + s["x2"]) / 2, (s["y1"] + s["y2"]) / 2
        split.append(dict(s, id=s["id"] + ".1", x2=mx, y2=my))
        split.append(dict(s, id=s["id"] + ".2", x1=mx, y1=my))
    assert sorted(g.gap_length_pt for g in run(split).opening_gaps) == expected
    far = [dict(s, id="far." + s["id"], x1=s["x1"] + 1000.0, x2=s["x2"] + 1000.0) for s in _overhang_building(left_overhang=0.0)]
    got = run(base + far, page=(2200.0, PAGE[1])).opening_gaps
    assert sorted(g.gap_length_pt for g in got if g.end_a[0] < 900.0) == expected


def test_collinear_walls_far_apart_are_not_one_interrupted_wall():
    t = 2.6
    segs = strip("w1", 100, 100, 160, 100 + t) + strip("w2", 160 + 300.0, 100, 700, 100 + t)   # 115 thicknesses apart
    assert not [g for g in run(segs).opening_gaps]


def test_gap_evidence_is_deterministic_and_order_invariant():
    base = _door_building()
    expected = run(base).opening_gaps
    shuffled = list(base)
    random.Random(3).shuffle(shuffled)
    assert run(shuffled).opening_gaps == expected
    assert run(base).opening_gaps == expected


def test_a_short_face_finds_a_much_longer_partner_from_either_side():
    # the long face's midpoint is far from the short face's cell: pairing must still be symmetric
    segs = [seg("short", 100, 100, 215, 100), seg("long", 100, 102.6, 700, 102.6)]
    report = run(segs)
    assert REASON_NO_PARTNER not in reasons(report)["short"]
    assert REASON_NO_PARTNER not in reasons(report)["long"]


# ---------------------------------------------------------------- ruled rings: schedules, legends, title blocks, grilles
def _table(prefix="tb", x0=500.0, y0=100.0, w=200.0, h=300.0, rows=5, ring_width=1.5, row_width=0.48, span=1.0, columns=0):
    """A framed table: a ring of single heavy strokes around ``rows`` thin parallel rule lines (and optional column rules)."""
    out = [seg(f"{prefix}.top", x0, y0, x0 + w, y0, width=ring_width), seg(f"{prefix}.right", x0 + w, y0, x0 + w, y0 + h, width=ring_width),
           seg(f"{prefix}.bottom", x0 + w, y0 + h, x0, y0 + h, width=ring_width), seg(f"{prefix}.left", x0, y0 + h, x0, y0, width=ring_width)]
    pitch = h / (rows + 1)
    margin = w * (1.0 - span) / 2.0
    for i in range(rows):
        y = y0 + pitch * (i + 1)
        out.append(seg(f"{prefix}.row{i}", x0 + margin, y, x0 + w - margin, y, width=row_width))
    for j in range(columns):
        x = x0 + w * (j + 1) / (columns + 1)
        out.append(seg(f"{prefix}.col{j}", x, y0 + 1.0, x, y0 + h - 1.0, width=row_width))
    return out


def _heavy_building(prefix="hb", x0=100.0, y0=100.0, w=300.0, h=250.0, ring_width=1.5):
    """A building drawn as single heavy strokes, with two full-span partitions of the same heavy class touching the ring."""
    return [seg(f"{prefix}.top", x0, y0, x0 + w, y0, width=ring_width), seg(f"{prefix}.right", x0 + w, y0, x0 + w, y0 + h, width=ring_width),
            seg(f"{prefix}.bottom", x0 + w, y0 + h, x0, y0 + h, width=ring_width), seg(f"{prefix}.left", x0, y0 + h, x0, y0, width=ring_width),
            seg(f"{prefix}.p1", x0, y0 + h / 3, x0 + w, y0 + h / 3, width=ring_width), seg(f"{prefix}.p2", x0, y0 + 2 * h / 3, x0 + w, y0 + 2 * h / 3, width=ring_width)]


def test_a_framed_table_is_a_typed_negative_with_its_rule_lines_and_is_never_a_wall_network():
    report = run(_table())
    got, why = labels(report), reasons(report)
    assert set(got.values()) == {NOT_WALL_INK}
    assert all(REASON_RULED_RING in why[i] for i in got)                       # the ring AND every rule line carry the reason
    assert not report.ids_with(WALL_NETWORK_INK_CANDIDATE)


def test_a_table_with_column_rules_is_the_same_negative():
    got = labels(run(_table(columns=2)))
    assert set(got.values()) == {NOT_WALL_INK}


def test_a_building_ring_with_partitions_of_its_own_class_is_not_a_table():
    got = labels(run(_heavy_building()))
    assert set(got.values()) == {WALL_NETWORK_INK_CANDIDATE}


def test_a_building_ring_with_fewer_than_four_lighter_full_span_lines_is_not_a_table():
    for rows in (1, 2, 3):
        got = labels(run(_table(rows=rows)))
        assert WALL_NETWORK_INK_CANDIDATE in got.values() and REASON_RULED_RING not in {r for rs in reasons(run(_table(rows=rows))).values() for r in rs}
    assert set(labels(run(_table(rows=4))).values()) == {NOT_WALL_INK}


def test_rule_lines_that_do_not_span_the_ring_do_not_make_it_a_table():
    got = labels(run(_table(rows=6, span=0.6)))
    assert WALL_NETWORK_INK_CANDIDATE in got.values()
    assert not any(REASON_RULED_RING in r for r in reasons(run(_table(rows=6, span=0.6))).values())


def test_a_double_rule_counts_once_so_three_double_rules_are_not_a_table():
    rows = []
    for i, y in enumerate((175.0, 250.0, 325.0)):
        rows.append(seg(f"dr{i}a", 500.0, y, 700.0, y, width=0.48))
        rows.append(seg(f"dr{i}b", 500.0, y + 0.5, 700.0, y + 0.5, width=0.48))
    ring = [t for t in _table(rows=0)]
    got = labels(run(ring + rows))
    assert WALL_NETWORK_INK_CANDIDATE in got.values()


def test_a_table_whose_rows_are_double_rules_is_still_a_table():
    # five rows, each a double rule 0.5 pt apart: a hairline duplicate is one row, never the two faces of a wall
    ring = _table(rows=0)
    rows = []
    for i in range(5):
        y = 100.0 + 50.0 * (i + 1)
        rows += [seg(f"dr{i}a", 500.0, y, 700.0, y, width=0.48), seg(f"dr{i}b", 500.0, y + 0.5, 700.0, y + 0.5, width=0.48)]
    assert set(labels(run(ring + rows)).values()) == {NOT_WALL_INK}


def test_rule_lines_outside_the_ring_are_not_its_rows():
    stray = [seg(f"stray{i}", 500.0, 450.0 + 20 * i, 700.0, 450.0 + 20 * i, width=0.48) for i in range(6)]
    got = labels(run(_table(rows=1) + stray))
    assert WALL_NETWORK_INK_CANDIDATE in got.values()


def test_a_table_drawn_with_a_paired_face_frame_is_the_same_negative():
    t = 2.6
    x0, y0, w, h = 500.0, 100.0, 200.0, 300.0
    frame = (strip("fa", x0, y0, x0 + w, y0 + t) + strip("fb", x0, y0 + h - t, x0 + w, y0 + h)
             + strip("fc", x0, y0 + t, x0 + t, y0 + h - t) + strip("fd", x0 + w - t, y0 + t, x0 + w, y0 + h - t))
    rows = [seg(f"r{i}", x0 + t, y0 + 50.0 * (i + 1), x0 + w - t, y0 + 50.0 * (i + 1), width=0.48) for i in range(5)]
    got = labels(run(frame + rows))
    assert set(got.values()) == {NOT_WALL_INK}


def test_a_ring_with_a_heavy_interior_wall_of_its_own_class_is_a_building_even_with_rule_lines():
    # the interior wall touches the ring and is part of its component, so the component is not a pure ring
    wall = [seg("heavy.wall", 600.0, 100.0, 600.0, 300.0, width=1.5)]
    got = labels(run(_table(rows=5) + wall))
    assert WALL_NETWORK_INK_CANDIDATE in got.values()
    assert not any(REASON_RULED_RING in r for r in reasons(run(_table(rows=5) + wall)).values())


def test_lines_hugging_the_frame_are_part_of_the_frame_not_rows():
    hugging = [seg(f"hug{i}", 500.0, 100.0 + 1.5 * (i + 1), 700.0, 100.0 + 1.5 * (i + 1), width=0.48) for i in range(5)]
    got = labels(run(_table(rows=3) + hugging))
    assert WALL_NETWORK_INK_CANDIDATE in got.values()


def test_a_paired_face_frame_in_the_same_ink_class_as_its_rows_is_judged_as_a_paired_component():
    t = 2.6
    x0, y0, w, h = 500.0, 100.0, 200.0, 300.0
    frame = (strip("fa", x0, y0, x0 + w, y0 + t, width=0.48) + strip("fb", x0, y0 + h - t, x0 + w, y0 + h, width=0.48)
             + strip("fc", x0, y0 + t, x0 + t, y0 + h - t, width=0.48) + strip("fd", x0 + w - t, y0 + t, x0 + w, y0 + h - t, width=0.48))
    rows = [seg(f"r{i}", x0 + t, y0 + 50.0 * (i + 1), x0 + w - t, y0 + 50.0 * (i + 1), width=0.48) for i in range(5)]
    assert set(labels(run(frame + rows)).values()) == {NOT_WALL_INK}
    assert WALL_NETWORK_INK_CANDIDATE in set(labels(run(frame + rows[:3])).values())


def test_a_pure_heavy_ring_with_thin_partitions_drawn_as_two_faces_is_a_building_not_a_table():
    t = 2.6
    ring = [seg("hr.top", 100, 100, 400, 100, width=1.5), seg("hr.right", 400, 100, 400, 300, width=1.5),
            seg("hr.bottom", 400, 300, 100, 300, width=1.5), seg("hr.left", 100, 300, 100, 100, width=1.5)]
    # four full-height partitions in the same colour but a thinner class, each drawn as two faces a wall thickness apart
    partitions = []
    for i, x in enumerate((160.0, 220.0, 280.0, 340.0)):
        partitions += strip(f"tp{i}", x - t / 2, 101.0, x + t / 2, 299.0, width=0.37)
    report = run(ring + partitions)
    assert not any(REASON_RULED_RING in r for r in reasons(report).values())
    assert all(labels(report)[s_["id"]] == WALL_NETWORK_INK_CANDIDATE for s_ in ring)
    # the same ring around four SINGLE thin rules (no wall thickness apart) is a table
    singles = [seg(f"sr{i}", 100.0, 100.0 + 40.0 * (i + 1), 400.0, 100.0 + 40.0 * (i + 1), width=0.37) for i in range(4)]
    assert set(labels(run(ring + singles)).values()) == {NOT_WALL_INK}


def test_a_table_beside_a_building_does_not_change_the_building_and_is_not_changed_by_it():
    house, table = building(), _table()
    alone_b, alone_t = labels(run(house)), labels(run(table))
    both = labels(run(house + table))
    assert {k: v for k, v in both.items() if k in alone_b} == alone_b
    assert {k: v for k, v in both.items() if k in alone_t} == alone_t


def test_the_ruled_ring_rule_is_invariant_to_order_translation_quarter_turn_scale_splitting_and_unrelated_content():
    base = _heavy_building() + _table()
    expected = labels(run(base))
    shuffled = list(base)
    random.Random(21).shuffle(shuffled)
    assert labels(run(shuffled)) == expected
    moved = [dict(s, x1=s["x1"] + 13.0, x2=s["x2"] + 13.0, y1=s["y1"] - 7.0, y2=s["y2"] - 7.0) for s in base]
    assert labels(run(moved)) == expected
    turned = [dict(s, x1=-s["y1"] + 900.0, y1=s["x1"], x2=-s["y2"] + 900.0, y2=s["x2"]) for s in base]
    assert labels(run(turned, page=(PAGE[1] + 400, PAGE[0]))) == expected
    k = 2.0
    scaled = [dict(s, x1=s["x1"] * k, y1=s["y1"] * k, x2=s["x2"] * k, y2=s["y2"] * k, width=s["width"] * k) for s in base]
    assert labels(run(scaled, page=(PAGE[0] * k, PAGE[1] * k))) == expected
    split = []
    for s in base:
        mx, my = (s["x1"] + s["x2"]) / 2, (s["y1"] + s["y2"]) / 2
        split.append(dict(s, id=s["id"] + ".1", x2=mx, y2=my))
        split.append(dict(s, id=s["id"] + ".2", x1=mx, y1=my))
    got = labels(run(split))
    assert {k2: v for k2, v in got.items() if k2.startswith("tb.")} and all(v == NOT_WALL_INK for k2, v in got.items() if k2.startswith("tb."))
    assert all(v == WALL_NETWORK_INK_CANDIDATE for k2, v in got.items() if k2.startswith("hb."))
    far = _table(prefix="far", x0=1500.0, y0=100.0)
    both = labels(run(base + far, page=(2200.0, 900.0)))
    assert {k2: v for k2, v in both.items() if k2 in expected} == expected


def test_the_ruled_ring_rule_is_deterministic_and_does_not_mutate_its_input():
    base = _heavy_building() + _table()
    before = copy.deepcopy(base)
    first = run(base)
    assert base == before and run(base) == first



# ---------------------------------------------------------------- glyph-sized runs (label ink with ancestry)
def test_a_word_of_outlined_glyphs_is_one_run_with_its_ancestry_and_a_second_line_is_another():
    line1 = list(itertools.chain.from_iterable(_letter(f"A{i}", 500 + 7 * i, 520) for i in range(5)))
    line2 = list(itertools.chain.from_iterable(_letter(f"B{i}", 500 + 7 * i, 560) for i in range(4)))
    report = run(building() + line1 + line2)
    runs = report.glyph_runs
    assert len(runs) == 2
    first, second = sorted(runs, key=lambda r: r.bbox[1])
    assert first.path_count == 5 and second.path_count == 4
    assert first.segment_count == 15 and second.segment_count == 12
    assert first.source_primitive_ids == tuple(sorted(s["id"] for s in line1))
    assert abs(first.glyph_height_pt - 8.0) < 0.01 and abs(first.baseline_y_pt - 520.0) < 0.01
    assert first.bbox == (500.0, 512.0, 532.0, 520.0)
    assert first.touches_wall_network is False


def test_a_run_standing_on_a_wall_says_so_and_is_not_text_by_itself():
    posts = list(itertools.chain.from_iterable(_box(f"post{i}", 150 + 14 * i, 102.6, 156 + 14 * i, 108.6) for i in range(3)))
    report = run(building() + posts)
    assert len(report.glyph_runs) == 1 and report.glyph_runs[0].touches_wall_network is True


def test_glyph_runs_are_invariant_to_translation_and_input_order_and_are_deterministic():
    word = list(itertools.chain.from_iterable(_letter(f"A{i}", 500 + 7 * i, 520) for i in range(5)))
    base = run(building() + word).glyph_runs
    moved = [dict(s, x1=s["x1"] + 11.0, x2=s["x2"] + 11.0, y1=s["y1"] + 5.0, y2=s["y2"] + 5.0) for s in building() + word]
    got = run(moved).glyph_runs
    assert [(g.path_count, g.segment_count, g.source_primitive_ids) for g in got] == [
        (g.path_count, g.segment_count, g.source_primitive_ids) for g in base]
    assert got[0].bbox == (base[0].bbox[0] + 11.0, base[0].bbox[1] + 5.0, base[0].bbox[2] + 11.0, base[0].bbox[3] + 5.0)
    shuffled = list(building() + word)
    random.Random(5).shuffle(shuffled)
    assert run(shuffled).glyph_runs == base
