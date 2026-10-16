"""Attached partition ink shadow: positives, look-alike negatives, ambiguity, metamorphic and invariance tests."""
from __future__ import annotations

import copy
import random

import pytest

import pb_structural_partition_ink_shadow as part
from pb_structural_partition_ink_shadow import (
    NOT_PARTITION_INK,
    PARTITION_INK_CANDIDATE,
    classify_attached_partition_ink,
)
from pb_structural_wall_ink_shadow import UNPROVEN, WALL_NETWORK_INK_CANDIDATE, classify_structural_wall_ink

PAGE = (842.0, 595.0)
BLACK = (0.0, 0.0, 0.0)
GREY = (0.42, 0.42, 0.42)
PLANK = (0.75, 0.75, 0.75)
PAPER = (1.0, 1.0, 1.0)


def seg(ident, x1, y1, x2, y2, *, width=0.96, stroke=BLACK, dashes="[] 0", path=None):
    return {
        "id": ident, "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), "kind": "line",
        "stroke": stroke, "stroke_present": stroke is not None, "width": width, "width_present": True,
        "dashes": dashes, "fill": None, "fill_present": False,
        "path_index": ident if path is None else path,
    }


def strip(prefix, x0, y0, x1, y1, **kw):
    return [
        seg(f"{prefix}.a", x0, y0, x1, y0, path=f"{prefix}", **kw),
        seg(f"{prefix}.b", x1, y0, x1, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.c", x1, y1, x0, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.d", x0, y1, x0, y0, path=f"{prefix}", **kw),
    ]


def black_shell(ox=100.0, oy=100.0, w=300.0, h=200.0, t=2.6, prefix=""):
    out = []
    out += strip(f"{prefix}top", ox, oy, ox + w, oy + t)
    out += strip(f"{prefix}bot", ox, oy + h - t, ox + w, oy + h)
    out += strip(f"{prefix}left", ox, oy + t, ox + t, oy + h - t)
    out += strip(f"{prefix}right", ox + w - t, oy + t, ox + w, oy + h - t)
    return out


def grey_partition(prefix="gp", x=250.0, y0=102.6, y1=297.4, t=2.6):
    """An internal partition drawn in a lighter grey: two long faces and two end caps, standing on the black shell."""
    return strip(prefix, x - t / 2, y0, x + t / 2, y1, width=0.37, stroke=GREY)


def planks(prefix="pl", x0=110.0, x1=390.0, y0=110.0, n=8, step=3.0):
    """A floor-finish field: n parallel lines ``step`` apart across a room, in a light grey."""
    return [seg(f"{prefix}{i}", x0, y0 + step * i, x1, y0 + step * i, width=0.43, stroke=PLANK) for i in range(n)]


def run(segments, page=PAGE):
    ink = classify_structural_wall_ink(segments, page_width=page[0], page_height=page[1])
    return ink, classify_attached_partition_ink(segments, ink, page_width=page[0], page_height=page[1])


def verdicts(report):
    return {d.source_primitive_id: d.classification for d in report.decisions}


# ---------------------------------------------------------------- positives
def test_lighter_ink_partitions_standing_on_the_black_shell_are_attached_partition_candidates():
    shell, partition = black_shell(), grey_partition()
    ink, report = run(shell + partition)
    got = verdicts(report)
    # the shell is structural (tier 0) and is not re-judged here; the grey partition was UNPROVEN as lighter ink
    assert all(ink.classification_of(s["id"]) == WALL_NETWORK_INK_CANDIDATE for s in shell)
    assert all(ink.classification_of(s["id"]) == UNPROVEN for s in partition)
    assert not set(got) & {s["id"] for s in shell}
    assert all(got[s["id"]] == PARTITION_INK_CANDIDATE for s in partition)
    assert all(d.reason_codes == (part.REASON_ATTACHED_PAIRED_NETWORK,) for d in report.decisions if d.classification == PARTITION_INK_CANDIDATE)


def test_an_internal_doorway_in_an_attached_partition_is_typed_like_an_external_one():
    shell = black_shell()
    door = strip("gpa", 248.7, 102.6, 251.3, 160.0, width=0.37, stroke=GREY) + strip("gpb", 248.7, 184.0, 251.3, 297.4, width=0.37, stroke=GREY)
    ink, report = run(shell + door)
    assert not [g for g in ink.opening_gaps if abs(g.end_a[0] - 248.7) < 1.5 and 150 < g.end_a[1] < 190]
    inside = [g for g in report.opening_gaps if abs(g.end_a[0] - g.end_b[0]) < 0.01 and 150 < g.end_a[1] < 190 and 240 < g.end_a[0] < 260]
    assert len(inside) == 2 and all(abs(g.gap_length_pt - 24.0) < 0.01 for g in inside)
    assert all(g.end_a in {g2.end_a for g2 in report.opening_gaps} for g in ink.opening_gaps)     # structural gaps are kept


# ---------------------------------------------------------------- look-alike negatives
def test_a_floor_plank_field_is_a_ladder_and_is_never_a_partition():
    shell, field = black_shell(), planks()
    ink, report = run(shell + field)
    got = verdicts(report)
    assert all(got[s["id"]] == NOT_PARTITION_INK for s in field)
    why = {d.source_primitive_id: d.reason_codes for d in report.decisions}
    assert why["pl3"] == (part.REASON_PARALLEL_LADDER,) and why["pl0"] == (part.REASON_PARALLEL_LADDER_EDGE,)
    assert why["pl7"] == (part.REASON_PARALLEL_LADDER_EDGE,)
    assert not report.ids_with(PARTITION_INK_CANDIDATE)


def test_the_partition_beside_a_plank_field_keeps_its_verdict():
    shell, partition, field = black_shell(), grey_partition(), planks(x0=110.0, x1=240.0)
    _, report = run(shell + partition + field)
    got = verdicts(report)
    assert all(got[s["id"]] == PARTITION_INK_CANDIDATE for s in partition)
    assert all(got[s["id"]] == NOT_PARTITION_INK for s in field)


def test_a_paired_grey_structure_that_stands_on_nothing_is_not_attached():
    shell = black_shell()
    island = strip("isl", 500, 400, 540, 402.6, width=0.37, stroke=GREY) + strip("isl2", 500, 450, 540, 452.6, width=0.37, stroke=GREY)
    _, report = run(shell + island)
    got = verdicts(report)
    assert all(got[s["id"]] == UNPROVEN for s in island)
    assert part.REASON_NOT_PAIRED_OR_NOT_ATTACHED in {r for d in report.decisions for r in d.reason_codes}


def test_a_wall_face_between_lines_of_another_ink_class_is_not_a_ladder_member():
    # plank-class lines 2.7 pt before and 3.7 pt after the partition's face: both sides have a partner, but of another class
    beside = [seg("beside0", 246.0, 110.0, 246.0, 290.0, width=0.43, stroke=PLANK),
              seg("beside1", 255.0, 110.0, 255.0, 290.0, width=0.43, stroke=PLANK)]
    _, report = run(black_shell() + grey_partition() + beside)
    got = verdicts(report)
    assert all(got[s["id"]] == PARTITION_INK_CANDIDATE for s in grey_partition())


def test_a_staggered_same_class_line_with_little_overlap_is_not_a_partner():
    # a grey line 6.7 pt outside the partition's left face that overlaps it over 20 pt of its 100 pt: not a partner on that side
    stagger = [seg("stagger", 242.0, 277.0, 242.0, 377.0, width=0.37, stroke=GREY)]
    _, report = run(black_shell() + grey_partition() + stagger)
    assert all(verdicts(report)[s["id"]] == PARTITION_INK_CANDIDATE for s in grey_partition())


def test_a_stub_too_short_for_its_distance_is_not_a_partner():
    # a 12 pt grey stub 3 pt beside the left face is only 4 thicknesses long: not a face partner (8 are required)
    stub = [seg("stub", 245.7, 150.0, 245.7, 162.0, width=0.37, stroke=GREY)]
    _, report = run(black_shell() + grey_partition() + stub)
    assert all(verdicts(report)[s["id"]] == PARTITION_INK_CANDIDATE for s in grey_partition())


def test_a_single_unpaired_grey_line_on_the_shell_is_not_a_partition():
    lone = [seg("lone", 250, 102.6, 250, 297.4, width=0.37, stroke=GREY)]
    _, report = run(black_shell() + lone)
    assert verdicts(report)["lone"] == UNPROVEN


def test_dashed_and_paper_coloured_and_zero_width_strokes_are_not_considered_at_all():
    # dashed strokes are typed negatives of the structural report and so never reach this module's decisions
    extras = [seg("dash", 250, 102.6, 250, 297.4, width=0.37, stroke=GREY, dashes="[3] 0"),
              seg("paper", 260, 102.6, 260, 297.4, width=0.37, stroke=PAPER),
              seg("hair", 270, 102.6, 270, 297.4, width=0.0, stroke=GREY),
              seg("stub", 280, 150.0, 280, 151.0, width=0.37, stroke=GREY)]
    _, report = run(black_shell() + extras)
    assert not {d.source_primitive_id for d in report.decisions} & {"dash", "paper", "hair", "stub"}


def test_a_lone_plank_pair_cannot_be_told_from_a_wall_pair_and_is_attached():
    pair = [seg("p0", 120, 150, 380, 150, width=0.43, stroke=PLANK), seg("p1", 120, 153, 380, 153, width=0.43, stroke=PLANK)]
    # it stands on nothing (floats in the room), so it is unproven; touching the left and right shell it would be a candidate
    _, floating = run(black_shell() + pair)
    assert verdicts(floating)["p0"] == UNPROVEN
    touching = [seg("p0", 102.6, 150, 397.4, 150, width=0.43, stroke=PLANK), seg("p1", 102.6, 153, 397.4, 153, width=0.43, stroke=PLANK)]
    _, attached = run(black_shell() + touching)
    assert verdicts(attached)["p0"] == verdicts(attached)["p1"] == PARTITION_INK_CANDIDATE


# ---------------------------------------------------------------- degenerate inputs
def test_no_structural_candidates_means_nothing_to_attach_to():
    tiny = strip("tiny", 100, 100, 160, 102.6) + strip("g", 100, 140, 160, 142.6, width=0.37, stroke=GREY)   # below building scale
    ink = classify_structural_wall_ink(tiny, page_width=PAGE[0], page_height=PAGE[1])
    assert not ink.ids_with(WALL_NETWORK_INK_CANDIDATE)
    out = classify_attached_partition_ink(tiny, ink, page_width=PAGE[0], page_height=PAGE[1])
    assert out.decisions == () and out.opening_gaps == () and out.reason_codes == (part.REASON_NO_STRUCTURAL_CANDIDATES,)


def test_a_separate_grey_building_is_not_attached_to_the_black_one():
    other = black_shell(ox=500.0, oy=300.0, w=250.0, h=150.0, prefix="o.")
    grey_building = [dict(s, stroke=GREY, width=0.37) for s in other]
    _, report = run(black_shell() + grey_building)
    assert not report.ids_with(PARTITION_INK_CANDIDATE)
    assert {verdicts(report)[s["id"]] for s in grey_building} == {UNPROVEN}


def test_duplicate_ids_are_rejected_and_empty_input_is_empty():
    shell = black_shell()
    ink = classify_structural_wall_ink(shell, page_width=PAGE[0], page_height=PAGE[1])
    with pytest.raises(ValueError):
        classify_attached_partition_ink(shell + [dict(shell[0])], ink, page_width=PAGE[0], page_height=PAGE[1])
    empty = classify_structural_wall_ink([], page_width=PAGE[0], page_height=PAGE[1])
    assert classify_attached_partition_ink([], empty, page_width=PAGE[0], page_height=PAGE[1]).decisions == ()


def test_a_report_that_describes_other_segments_is_refused():
    shell = black_shell()
    ink = classify_structural_wall_ink(shell, page_width=PAGE[0], page_height=PAGE[1])
    with pytest.raises(ValueError):
        classify_attached_partition_ink(shell[:-4], ink, page_width=PAGE[0], page_height=PAGE[1])


def test_shadow_flags_grant_nothing():
    _, report = run(black_shell() + grey_partition())
    assert report.shadow_only is True and report.live_effect is False and report.wall_authority_granted is False


# ---------------------------------------------------------------- invariance and metamorphic tests
def _scene():
    return black_shell() + grey_partition() + planks(x0=110.0, x1=240.0)


def test_input_order_does_not_change_any_decision_and_runs_are_deterministic():
    base = _scene()
    expected = run(base)[1]
    shuffled = list(base)
    random.Random(7).shuffle(shuffled)
    assert run(shuffled)[1] == expected
    assert run(base)[1] == expected


def test_inputs_are_not_mutated():
    base = _scene()
    before = copy.deepcopy(base)
    ink = classify_structural_wall_ink(base, page_width=PAGE[0], page_height=PAGE[1])
    snapshot = copy.deepcopy(ink)
    classify_attached_partition_ink(base, ink, page_width=PAGE[0], page_height=PAGE[1])
    assert base == before and ink == snapshot


def test_translation_and_a_quarter_turn_do_not_change_the_verdicts():
    base = _scene()
    expected = verdicts(run(base)[1])
    moved = [dict(s, x1=s["x1"] + 11.0, x2=s["x2"] + 11.0, y1=s["y1"] + 5.0, y2=s["y2"] + 5.0) for s in base]
    assert verdicts(run(moved)[1]) == expected
    turned = [dict(s, x1=-s["y1"] + 700.0, y1=s["x1"], x2=-s["y2"] + 700.0, y2=s["x2"]) for s in base]
    assert verdicts(run(turned, page=(PAGE[1] + 200, PAGE[0]))[1]) == expected


def test_uniform_scale_of_the_drawing_does_not_change_the_verdicts():
    base = black_shell() + grey_partition() + planks(x0=110.0, x1=240.0, step=1.5)
    expected = verdicts(run(base)[1])
    k = 2.0
    scaled = [dict(s, x1=s["x1"] * k, y1=s["y1"] * k, x2=s["x2"] * k, y2=s["y2"] * k, width=s["width"] * k) for s in base]
    assert verdicts(run(scaled, page=(PAGE[0] * k, PAGE[1] * k))[1]) == expected


def test_splitting_partition_faces_into_pieces_does_not_change_the_verdict():
    shell = black_shell()
    whole = grey_partition()
    split = []
    for s in whole:
        mx, my = (s["x1"] + s["x2"]) / 2, (s["y1"] + s["y2"]) / 2
        split.append(dict(s, id=s["id"] + ".1", x2=mx, y2=my))
        split.append(dict(s, id=s["id"] + ".2", x1=mx, y1=my))
    got = verdicts(run(shell + split)[1])
    assert all(v == PARTITION_INK_CANDIDATE for k, v in got.items() if k.startswith("gp."))


def test_unrelated_content_and_a_larger_sheet_do_not_change_the_building_verdicts():
    base = _scene()
    expected = verdicts(run(base)[1])
    far = black_shell(ox=1000.0, oy=100.0, prefix="far.") + grey_partition("far", x=1150.0, y0=102.6, y1=297.4)
    got = verdicts(run(base + far, page=(2000.0, 900.0))[1])
    assert {k: v for k, v in got.items() if k in expected} == expected
