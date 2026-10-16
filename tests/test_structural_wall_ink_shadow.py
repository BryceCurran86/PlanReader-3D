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
