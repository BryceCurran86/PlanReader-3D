"""Structural room-region shadow: positives, look-alike negatives, ambiguity, metamorphic and invariance tests."""
from __future__ import annotations

import copy
from dataclasses import replace
import random

import pytest

import pb_structural_room_region_shadow as rooms
from pb_structural_partition_ink_shadow import classify_attached_partition_ink
from pb_structural_room_region_shadow import (
    RegionLabelInput,
    chord_id,
    derive_structural_room_regions,
)
from pb_structural_wall_ink_shadow import (
    WALL_NETWORK_INK_CANDIDATE,
    GlyphSizedRun,
    OpeningGapCandidate,
    StructuralInkDecision,
    classify_structural_wall_ink,
)

PAGE = (842.0, 595.0)
BLACK = (0.0, 0.0, 0.0)
GREY = (0.42, 0.42, 0.42)
T = 2.6
INNER_W, INNER_H = 300.0 - 2 * T, 200.0 - 2 * T                      # shell interior, face to face


def seg(ident, x1, y1, x2, y2, *, width=0.96, stroke=BLACK, path=None):
    return {
        "id": ident, "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), "kind": "line",
        "stroke": stroke, "stroke_present": True, "width": width, "width_present": True,
        "dashes": "[] 0", "fill": None, "fill_present": False, "path_index": ident if path is None else path,
    }


def strip(prefix, x0, y0, x1, y1, **kw):
    return [
        seg(f"{prefix}.a", x0, y0, x1, y0, path=f"{prefix}", **kw),
        seg(f"{prefix}.b", x1, y0, x1, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.c", x1, y1, x0, y1, path=f"{prefix}", **kw),
        seg(f"{prefix}.d", x0, y1, x0, y0, path=f"{prefix}", **kw),
    ]


def shell(ox=100.0, oy=100.0, w=300.0, h=200.0, prefix="", top_gap=None):
    out = []
    if top_gap is None:
        out += strip(f"{prefix}top", ox, oy, ox + w, oy + T)
    else:
        lo, hi = top_gap
        out += strip(f"{prefix}tl", ox, oy, lo, oy + T) + strip(f"{prefix}tr", hi, oy, ox + w, oy + T)
    out += strip(f"{prefix}bot", ox, oy + h - T, ox + w, oy + h)
    out += strip(f"{prefix}left", ox, oy + T, ox + T, oy + h - T)
    out += strip(f"{prefix}right", ox + w - T, oy + T, ox + w, oy + h - T)
    return out


def partition(prefix="part", x=250.0, door=None, **kw):
    if door is None:
        return strip(prefix, x - T / 2, 100 + T, x + T / 2, 300 - T, **kw)
    lo, hi = door
    return strip(prefix + "a", x - T / 2, 100 + T, x + T / 2, lo, **kw) + strip(prefix + "b", x - T / 2, hi, x + T / 2, 300 - T, **kw)


def build(segments, *, with_partition_report=False, page=PAGE, labels=()):
    ink = classify_structural_wall_ink(segments, page_width=page[0], page_height=page[1])
    part = classify_attached_partition_ink(segments, ink, page_width=page[0], page_height=page[1]) if with_partition_report else None
    return ink, part, derive_structural_room_regions(segments, ink, part, labels=labels)


def areas(report):
    return sorted(round(r.area_pt2) for r in report.regions)


def approx(value, expected, tol=1.0):
    return abs(value - expected) <= tol


def augmented(ink, ids):
    extra = tuple(StructuralInkDecision(i, WALL_NETWORK_INK_CANDIDATE, ("test_fixture",), None, 99) for i in ids)
    return replace(ink, decisions=ink.decisions + extra)


# ---------------------------------------------------------------- positives
def test_a_closed_shell_is_one_region_whose_area_is_the_face_to_face_interior():
    _, _, report = build(shell())
    assert len(report.regions) == 1
    region = report.regions[0]
    assert approx(region.area_pt2, INNER_W * INNER_H, 2.0) and region.hole_count == 0
    assert approx(region.gross_area_pt2, region.area_pt2, 1e-6) and region.inradius_pt > 90.0
    assert region.closure_chord_ids == () and region.boundary_tier_counts[1] == 0
    assert region.multi_label is False and region.labels == ()


def test_an_internal_partition_makes_two_regions_that_share_it():
    _, _, report = build(shell() + partition())
    assert len(report.regions) == 2
    each = (INNER_W - T) / 2 * INNER_H
    assert all(approx(r.area_pt2, each, 2.0) for r in report.regions)
    faces = [{i for i in r.boundary_primitive_ids if i in ("part.b", "part.d")} for r in report.regions]
    assert sorted(map(sorted, faces)) == [["part.b"], ["part.d"]]          # each room runs along its own face of the partition


def test_a_doorway_is_closed_only_by_its_typed_chord_and_the_chord_is_reported():
    scene = shell() + partition(door=(160.0, 184.0))
    ink, _, with_chord = build(scene)
    assert len(with_chord.regions) == 2 and with_chord.chord_ids
    assert all(r.closure_chord_ids for r in with_chord.regions)           # each room names the chord that closes its door
    bare = derive_structural_room_regions(scene, replace(ink, opening_gaps=()))
    assert len(bare.regions) == 1 and bare.chord_ids == ()                # nothing is closed without a typed chord
    assert bare.regions[0].area_pt2 > 0.97 * INNER_W * INNER_H - 600


def test_a_doorway_in_an_attached_partition_is_closed_by_the_joint_reading_gap():
    scene = shell() + partition(door=(160.0, 184.0), width=0.37, stroke=GREY)
    ink, part, report = build(scene, with_partition_report=True)
    assert not ink.opening_gaps or all(abs(g.end_a[0] - 248.7) > 1.5 for g in ink.opening_gaps)   # structural gaps do not see it
    assert len(report.regions) == 2 and all(r.closure_chord_ids for r in report.regions)
    tier0_only = derive_structural_room_regions(scene, ink)                                    # no partition ink, no partition gaps
    assert len(tier0_only.regions) == 1


def test_regions_are_listed_largest_first():
    scene = shell() + partition(x=180.0)
    _, _, report = build(scene)
    sizes = [r.area_pt2 for r in report.regions]
    assert len(sizes) == 2 and sizes == sorted(sizes, reverse=True) and sizes[0] > 2 * sizes[1]


def test_a_hairline_break_between_collinear_wall_pieces_is_closed_by_the_barrier_not_left_as_a_leak():
    scene = shell(top_gap=(215.0, 218.0))                                    # a 3 pt break, narrower than the barrier is wide
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    no_chords = derive_structural_room_regions(scene, replace(ink, opening_gaps=()))
    assert len(no_chords.regions) == 1 and no_chords.chord_ids == ()


def test_an_external_opening_leaves_the_room_open_unless_its_gap_was_typed():
    scene = shell(top_gap=(215.0, 239.0))
    ink, _, closed = build(scene)
    assert len(closed.regions) == 1 and closed.regions[0].closure_chord_ids
    open_ = derive_structural_room_regions(scene, replace(ink, opening_gaps=()))
    assert open_.regions == ()                                             # the envelope leaks to the page exterior


def test_attached_partitions_separate_rooms_and_are_counted_as_tier_one():
    scene = shell() + partition(width=0.37, stroke=GREY)
    ink, with_part, report = build(scene, with_partition_report=True)
    assert len(report.regions) == 2
    assert all(r.boundary_tier_counts[1] >= 1 for r in report.regions)
    without = derive_structural_room_regions(scene, ink)                   # tier 0 only: the lighter partition is not a barrier
    assert len(without.regions) == 1


def test_a_closed_cell_smaller_than_twenty_five_closure_squares_is_counted_not_listed():
    scene = shell()
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    box = [seg("bx.1", 200, 150, 215, 150), seg("bx.2", 215, 150, 215, 165), seg("bx.3", 215, 165, 200, 165), seg("bx.4", 200, 165, 200, 150)]
    report = derive_structural_room_regions(scene + box, augmented(ink, [s["id"] for s in box]))
    assert report.discarded_fragment_count == 1 and len(report.regions) == 1


def test_a_free_standing_pillar_is_a_hole_in_the_room_not_a_second_region():
    scene = shell()
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    pillar = [seg("pl.1", 200, 150, 230, 150), seg("pl.2", 230, 150, 230, 180), seg("pl.3", 230, 180, 200, 180), seg("pl.4", 200, 180, 200, 150)]
    report = derive_structural_room_regions(scene + pillar, augmented(ink, [s["id"] for s in pillar]))
    rooms_ = [r for r in report.regions if r.area_pt2 > 10000]
    assert len(rooms_) == 1 and rooms_[0].hole_count == 1
    assert approx(rooms_[0].gross_area_pt2 - rooms_[0].area_pt2, 30.0 * 30.0, 8.0)
    bare = derive_structural_room_regions(scene, ink).regions[0]
    assert bare.polygon == rooms_[0].polygon and bare.region_id != rooms_[0].region_id      # the hole is part of the identity


def test_exterior_interior_and_wall_body_faces_are_told_apart():
    core = [seg("core", 100, 100 + T / 2, 400, 100 + T / 2, width=1.92)]
    scene = shell() + partition() + core
    _, _, report = build(scene)
    exterior = set(report.exterior_adjacent_primitive_ids)
    interior = set(report.interior_only_primitive_ids)
    inside = set(report.within_wall_body_primitive_ids)
    assert {"top.a", "bot.c", "left.d", "right.b"} <= exterior            # the outer faces look onto the page exterior
    assert {"top.c", "part.b", "part.d", "bot.a"} <= interior             # inner faces and the partition look into rooms only
    assert "core" in inside                                                # a core line inside a wall body touches neither
    assert not (exterior & interior) and not (exterior & inside) and not (interior & inside)


def test_boundary_evidence_kinds_tell_paired_faces_single_strokes_and_attached_partitions_apart():
    _, _, paired = build(shell() + partition(width=0.37, stroke=GREY), with_partition_report=True)
    kinds = [dict(r.boundary_evidence_kinds) for r in paired.regions]
    assert kinds == [{rooms.KIND_PAIRED_FACE: 3, rooms.KIND_PARTITION: 1}] * 2          # three shell faces and one grey partition face each
    assert all(rooms.KIND_SINGLE_STROKE not in k for k in kinds)
    # walls drawn as ONE heavy line each: a closed box of single strokes is a single-stroke boundary, not a paired-face one
    lines = [seg("w1", 100, 100, 400, 100, width=1.5), seg("w2", 400, 100, 400, 300, width=1.5),
             seg("w3", 400, 300, 100, 300, width=1.5), seg("w4", 100, 300, 100, 100, width=1.5)]
    _, _, single = build(lines)
    assert len(single.regions) == 1
    assert dict(single.regions[0].boundary_evidence_kinds) == {rooms.KIND_SINGLE_STROKE: 4}


# ---------------------------------------------------------------- labels
def _label(label_id, text, x0, y0, x1, y1, trust="not_supplied"):
    return RegionLabelInput(label_id, text, (x0, y0, x1, y1), trust, (f"{label_id}.w",))


def test_a_label_whose_centre_stands_in_a_room_is_a_candidate_of_that_room_only():
    scene = shell() + partition()
    left, right = _label("l1", "BED 1", 150, 195, 190, 205), _label("l2", "BED 2", 300, 195, 340, 205)
    outside = _label("l3", "OUTSIDE", 500, 500, 540, 510)
    _, _, report = build(scene, labels=[left, right, outside])
    by_name = {tuple(l.text for l in r.labels): r for r in report.regions}
    assert set(by_name) == {("BED 1",), ("BED 2",)}                        # OUTSIDE is in no region
    assert all(not r.multi_label for r in report.regions)
    assert by_name[("BED 1",)].labels[0].centre == (170.0, 200.0)


def test_a_label_inside_a_wall_body_belongs_to_no_room_and_a_straddling_one_is_flagged():
    scene = shell() + partition()
    in_wall = _label("w", "ON WALL", 245, 195, 255, 205)
    straddle = _label("s", "BED 1", 140, 195, 260, 205)                    # centre in the left room, box crosses the partition
    _, _, report = build(scene, labels=[in_wall, straddle])
    placed = [(r, l) for r in report.regions for l in r.labels]
    assert [l.label_id for _, l in placed] == ["s"] and placed[0][1].bbox_crosses_boundary is True


def test_two_labels_in_one_open_area_are_reported_together_and_the_area_is_never_split():
    one = _label("a", "LIVING", 150, 150, 190, 160)
    two = _label("b", "DINING", 300, 150, 340, 160)
    _, _, report = build(shell(), labels=[one, two])
    assert len(report.regions) == 1 and report.regions[0].multi_label is True
    assert {l.text for l in report.regions[0].labels} == {"LIVING", "DINING"}


def test_the_text_trust_verdict_is_passed_through_unread():
    lab = _label("t", "KITCHEN", 150, 150, 190, 160, trust="text_glyph_mapping_unverified")
    _, _, report = build(shell(), labels=[lab])
    assert report.regions[0].labels[0].trust == "text_glyph_mapping_unverified"
    assert build(shell(), labels=[_label("t", "KITCHEN", 150, 150, 190, 160)])[2].regions[0].labels[0].trust == "not_supplied"


def test_outlined_lettering_runs_standing_in_a_room_are_listed_by_ancestry_not_as_text():
    ink = classify_structural_wall_ink(shell() + partition(), page_width=PAGE[0], page_height=PAGE[1])
    runs = (GlyphSizedRun((150.0, 150.0, 190.0, 158.0), 5, 15, 158.0, 8.0, False, ("g1",)),
            GlyphSizedRun((600.0, 150.0, 640.0, 158.0), 5, 15, 158.0, 8.0, False, ("g2",)))
    report = derive_structural_room_regions(shell() + partition(), replace(ink, glyph_runs=runs))
    placed = [(r, g) for r in report.regions for g in r.glyph_runs]
    assert len(placed) == 1 and placed[0][1].index == 0 and placed[0][1].path_count == 5
    assert not hasattr(placed[0][1], "text")


# ---------------------------------------------------------------- degenerate and bounded inputs
def test_no_structural_ink_and_empty_input_give_an_empty_report_with_a_reason():
    empty = derive_structural_room_regions([], classify_structural_wall_ink([], page_width=PAGE[0], page_height=PAGE[1]))
    assert empty.regions == () and empty.reason_codes == (rooms.REASON_NO_STRUCTURAL_INK,)


def test_duplicate_ids_are_rejected():
    scene = shell()
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    with pytest.raises(ValueError):
        derive_structural_room_regions(scene + [dict(scene[0])], ink)


def test_reports_that_describe_other_segments_are_refused():
    scene = shell() + partition(width=0.37, stroke=GREY)
    ink, part, _ = build(scene, with_partition_report=True)
    with pytest.raises(ValueError):
        derive_structural_room_regions(shell(), ink, part)                   # the partition ids are not in these segments
    with pytest.raises(ValueError):
        derive_structural_room_regions(scene[:-8], ink)


def test_an_oversized_input_is_refused_with_a_reason_instead_of_being_truncated(monkeypatch):
    scene = shell()
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    monkeypatch.setattr(rooms, "MAX_REGION_INPUT_PRIMITIVES", 5)
    out = derive_structural_room_regions(scene, ink)
    assert out.regions == () and out.reason_codes == (rooms.REASON_SCOPE_TOO_LARGE,)


def test_zero_length_primitives_are_ignored_and_the_shadow_flags_grant_nothing():
    scene = shell() + [seg("dot", 150, 150, 150, 150)]
    ink = classify_structural_wall_ink(scene, page_width=PAGE[0], page_height=PAGE[1])
    out = derive_structural_room_regions(scene, augmented(ink, ["dot"]))
    assert len(out.regions) == 1
    assert out.shadow_only is True and out.live_effect is False
    assert out.room_authority_granted is False and out.scale_authority_granted is False


def test_the_chord_identity_does_not_depend_on_which_end_is_called_first():
    gap = OpeningGapCandidate((10.0, 20.0), (34.0, 20.0), 24.0, 2.6, "a", "b")
    swapped = OpeningGapCandidate((34.0, 20.0), (10.0, 20.0), 24.0, 2.6, "b", "a")
    assert chord_id(gap) == chord_id(swapped)


# ---------------------------------------------------------------- invariance and metamorphic tests
def _scene():
    return shell() + partition(door=(160.0, 184.0))


def _labels():
    return [_label("l1", "BED 1", 150, 195, 190, 205), _label("l2", "BED 2", 300, 195, 340, 205)]


def test_input_order_does_not_change_the_report_and_runs_are_deterministic():
    base = _scene()
    expected = build(base, labels=_labels())[2]
    shuffled = list(base)
    random.Random(9).shuffle(shuffled)
    assert build(shuffled, labels=list(reversed(_labels())))[2] == expected
    assert build(base, labels=_labels())[2] == expected


def test_inputs_are_not_mutated():
    base = _scene()
    before = copy.deepcopy(base)
    ink, part, _ = build(base, with_partition_report=True)
    snapshot = copy.deepcopy((ink, part))
    derive_structural_room_regions(base, ink, part, labels=_labels())
    assert base == before and (ink, part) == snapshot


def test_translation_moves_every_region_and_changes_nothing_else():
    base = _scene()
    expected = build(base, labels=_labels())[2]
    dx, dy = 13.0, -7.0
    moved = [dict(s, x1=s["x1"] + dx, x2=s["x2"] + dx, y1=s["y1"] + dy, y2=s["y2"] + dy) for s in base]
    labels = [replace(lab, bbox=(lab.bbox[0] + dx, lab.bbox[1] + dy, lab.bbox[2] + dx, lab.bbox[3] + dy)) for lab in _labels()]
    got = build(moved, labels=labels)[2]
    assert [round(r.area_pt2, 1) for r in got.regions] == [round(r.area_pt2, 1) for r in expected.regions]
    assert [[l.text for l in r.labels] for r in got.regions] == [[l.text for l in r.labels] for r in expected.regions]
    assert [len(r.closure_chord_ids) for r in got.regions] == [len(r.closure_chord_ids) for r in expected.regions]
    for g, e in zip(got.regions, expected.regions):
        assert approx(g.bbox[0] - e.bbox[0], dx, 0.02) and approx(g.bbox[1] - e.bbox[1], dy, 0.02)


def test_a_quarter_turn_does_not_change_areas_labels_or_chords():
    base = _scene()
    expected = build(base, labels=_labels())[2]
    turned = [dict(s, x1=-s["y1"] + 700.0, y1=s["x1"], x2=-s["y2"] + 700.0, y2=s["x2"]) for s in base]
    labels = [replace(lab, bbox=(-lab.bbox[3] + 700.0, lab.bbox[0], -lab.bbox[1] + 700.0, lab.bbox[2])) for lab in _labels()]
    got = build(turned, labels=labels, page=(PAGE[1] + 200, PAGE[0]))[2]
    assert [round(r.area_pt2, 1) for r in got.regions] == [round(r.area_pt2, 1) for r in expected.regions]
    assert sorted(tuple(l.text for l in r.labels) for r in got.regions) == sorted(tuple(l.text for l in r.labels) for r in expected.regions)
    assert sorted(len(r.closure_chord_ids) for r in got.regions) == sorted(len(r.closure_chord_ids) for r in expected.regions)


def test_uniform_scale_of_the_drawing_scales_areas_by_the_square():
    base = shell() + partition()
    expected = build(base, labels=_labels())[2]
    k = 2.0
    scaled = [dict(s, x1=s["x1"] * k, y1=s["y1"] * k, x2=s["x2"] * k, y2=s["y2"] * k, width=s["width"] * k) for s in base]
    labels = [replace(lab, bbox=tuple(v * k for v in lab.bbox)) for lab in _labels()]
    got = build(scaled, labels=labels, page=(PAGE[0] * k, PAGE[1] * k))[2]
    assert len(got.regions) == len(expected.regions) == 2
    for g, e in zip(got.regions, expected.regions):
        assert approx(g.area_pt2 / e.area_pt2, k * k, 0.02)
    assert sorted(tuple(l.text for l in r.labels) for r in got.regions) == sorted(tuple(l.text for l in r.labels) for r in expected.regions)


def test_splitting_wall_faces_into_pieces_does_not_change_the_regions():
    base = shell() + partition()
    expected = build(base)[2]
    split = []
    for s in base:
        mx, my = (s["x1"] + s["x2"]) / 2, (s["y1"] + s["y2"]) / 2
        split.append(dict(s, id=s["id"] + ".1", x2=mx, y2=my))
        split.append(dict(s, id=s["id"] + ".2", x1=mx, y1=my))
    got = build(split)[2]
    assert [r.region_id for r in got.regions] == [r.region_id for r in expected.regions]
    assert [r.polygon for r in got.regions] == [r.polygon for r in expected.regions]


def test_unrelated_content_far_away_and_a_larger_sheet_do_not_change_the_building_regions():
    base = _scene()
    expected = build(base, labels=_labels())[2]
    far = shell(ox=1000.0, oy=100.0, prefix="far.") + partition("farp", x=1150.0)
    got = build(base + far, labels=_labels(), page=(2000.0, 900.0))[2]
    near_ids = {r.region_id for r in expected.regions}
    assert near_ids <= {r.region_id for r in got.regions}
    assert len(got.regions) == len(expected.regions) + 2                     # the far building adds its own rooms, nothing else moves


def test_a_wall_as_thick_as_the_pairing_bound_is_still_one_barrier_not_a_slit_region():
    thick = 7.5
    scene = []
    scene += strip("top", 100, 100, 400, 100 + thick) + strip("bot", 100, 300 - thick, 400, 300)
    scene += strip("left", 100, 100 + thick, 100 + thick, 300 - thick) + strip("right", 400 - thick, 100 + thick, 400, 300 - thick)
    _, _, report = build(scene)
    assert len(report.regions) == 1 and report.discarded_fragment_count == 0
