"""Review-only core: two traced wall-end sections of one doorway, any drawing convention, through the owner contract.

Synthetic scenes only: no private drawing, project name, benchmark value or file name is an input. Every scene is a plain
list of native path rows shaped like ``page.get_drawings()`` output. The same rule is exercised on solid strips, outlined
walls (two stroked face lines, or one hairline), cavity pockets, straight gaps, perpendicular corners, coincident
junctions and the face of a passing wall, and under translation, rotation, mirroring and scaling.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path

import fitz
import pytest

import pb_source_door_wall_end_sections as core
from pb_opening_two_wall_contact_tags import (
    DetectedOpeningContacts,
    OpeningWallContact,
    TracedWallSection,
    tag_opening_to_two_wall_sections,
)
from pb_source_door_wall_end_sections import (
    GATE_ANCHOR_MISSING,
    GATE_ANCHORS_DISAGREE,
    GATE_END_EDGE_MISSING,
    GATE_END_SIDES_COMPETING,
    GATE_ENDS_NOT_OPPOSED,
    GATE_FACE_NOT_END,
    GATE_GROUP_INVALID,
    GATE_GROUPS_OVERLAP,
    GATE_NO_ANCHORS,
    GATE_NOT_COLLINEAR,
    GATE_OPENING_PATHS_MISSING,
    GATE_ROW_UNREADABLE,
    GATE_WALL_THROUGH_OPENING,
    TOL,
    Blocked,
    WallEndReceipt,
    build_contract_inputs,
)

SCOPE = ("a" * 64, "revision-a", "page-3")
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)


# ---------------------------------------------------------------------------------------------------------------------
# row builders
# ---------------------------------------------------------------------------------------------------------------------


def poly(x0, y0, x1, y1, *, fill=BLACK):
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    items = tuple(("l", fitz.Point(*corners[i]), fitz.Point(*corners[(i + 1) % 4])) for i in range(4))
    return {"layer": "", "rect": fitz.Rect(x0, y0, x1, y1), "type": "f", "fill": fill, "color": None, "items": items}


def line(x0, y0, x1, y1):
    return {"layer": "", "rect": fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), "type": "s",
            "fill": None, "color": BLACK, "width": 0.48, "items": (("l", fitz.Point(x0, y0), fitz.Point(x1, y1)),)}


def pocket(x_end, x_far, y0, y1, lip=0.57):
    pts = [(x_far, y0), (x_end, y0), (x_end, y0 + lip), (x_far + 1.4, y0 + lip), (x_far + 1.4, y1 - lip),
           (x_end, y1 - lip), (x_end, y1), (x_far, y1)]
    items = tuple(("l", fitz.Point(*pts[i]), fitz.Point(*pts[(i + 1) % len(pts)])) for i in range(len(pts)))
    return {"layer": "", "rect": fitz.Rect(min(x_far, x_end), y0, max(x_far, x_end), y1), "type": "f",
            "fill": BLACK, "color": None, "items": items}


def leaf():
    return line(11.1, 95.0, 34.9, 95.0)


def result(rows, receipt):
    built = build_contract_inputs(rows, receipt)
    if isinstance(built, Blocked):
        return built.reason, None
    contacts, sections = built
    tag = tag_opening_to_two_wall_sections(contacts, sections)
    return tag.reason, tag


def receipt(first, second, anchors, *, opening=(0,), opening_id="opening-a", scope=SCOPE):
    return WallEndReceipt(opening_id, scope, opening, first, second, tuple(anchors))


CAPS = ((10.0, 99.7, 11.1, 102.3), (34.9, 99.7, 36.0, 102.3))
OK = "source_wall_ends_and_opening_contacts_match"


# scenes: rows list, then the receipt. Opening path ids live at the END of the row list so wall ids are stable.
def strip_scene():
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 60.0, 102.0), leaf()]
    return rows, receipt((0,), (1,), CAPS, opening=(2,))


def outlined_scene():
    rows = [line(0.0, 100.0, 10.0, 100.0), line(0.0, 102.0, 10.0, 102.0),
            line(36.0, 100.0, 60.0, 100.0), line(36.0, 102.0, 60.0, 102.0), leaf()]
    return rows, receipt((0, 1), (2, 3), CAPS, opening=(4,))


def outlined_with_end_cap_scene():
    rows = [line(0.0, 100.0, 10.0, 100.0), line(0.0, 102.0, 10.0, 102.0), line(10.0, 100.0, 10.0, 102.0),
            line(36.0, 100.0, 60.0, 100.0), line(36.0, 102.0, 60.0, 102.0), line(36.0, 100.0, 36.0, 102.0), leaf()]
    return rows, receipt((0, 1, 2), (3, 4, 5), CAPS, opening=(6,))


def hairline_scene():
    rows = [line(0.0, 101.0, 10.0, 101.0), line(36.0, 101.0, 60.0, 101.0), leaf()]
    return rows, receipt((0,), (1,), ((10.0, 100.0, 11.0, 102.0), (35.0, 100.0, 36.0, 102.0)), opening=(2,))


def pocket_scene():
    rows = [pocket(10.0, 0.0, 100.0, 102.55), pocket(36.0, 60.0, 100.0, 102.55), leaf()]
    anchors = ((10.0, 99.7, 11.1, 102.9), (10.0, 99.9, 11.1, 102.6), (34.9, 101.8, 36.0, 102.9))
    return rows, receipt((0,), (1,), anchors, opening=(2,))


def corner_scene():
    """Wall A runs left and ends at x=10; wall B runs down and ends at y=100: a corner doorway, contacts apart."""
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(10.0, 80.0, 12.0, 100.0), leaf()]
    anchors = ((10.0, 99.7, 11.1, 102.3), (9.7, 100.0, 12.3, 101.1))
    return rows, receipt((0,), (1,), anchors, opening=(2,))


def junction_scene():
    """The two wall ends meet at ONE point: contacts coincide."""
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(9.0, 80.0, 11.0, 101.0), leaf()]
    anchors = ((10.0, 100.0, 11.0, 102.0), (9.0, 101.0, 11.0, 102.0))
    return rows, receipt((0,), (1,), anchors, opening=(2,))


def face_scene():
    """The doorway ends at the FACE of a long wall that passes by: no wall section ends there."""
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 60.0, 38.0, 140.0), leaf()]
    return rows, receipt((0,), (1,), CAPS, opening=(2,))


STRAIGHT = [strip_scene, outlined_scene, outlined_with_end_cap_scene, hairline_scene, pocket_scene]
ALL = STRAIGHT + [corner_scene, junction_scene]


# ---------------------------------------------------------------------------------------------------------------------
# positives: one rule, every convention
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scene", STRAIGHT)
def test_straight_doorway_is_tagged_for_every_wall_convention(scene):
    reason, tag = result(*scene())
    assert reason == OK
    assert tag.status == "TWO_WALL_SECTIONS_TAGGED" and tag.contact_geometry == "STRAIGHT_GAP"
    assert len(tag.wall_section_ids) == 2 and tag.wall_section_ids[0] != tag.wall_section_ids[1]
    assert tag.physical_host_authorized is False and tag.measurement_authorized is False


def test_perpendicular_corner_doorway_is_an_angled_opening():
    reason, tag = result(*corner_scene())
    assert reason == OK and tag.contact_geometry == "ANGLED_OPENING"
    assert len(tag.wall_section_ids) == 2


def test_two_wall_ends_meeting_at_one_point_are_a_wall_junction():
    reason, tag = result(*junction_scene())
    assert reason == OK and tag.contact_geometry == "WALL_JUNCTION"


def test_section_ids_follow_the_native_paths_not_the_receipt_order():
    rows, rec = strip_scene()
    flipped = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids,
                             rec.second_wall_end_path_ids, rec.first_wall_end_path_ids, rec.anchors)
    assert result(rows, rec)[1].wall_section_ids == result(rows, flipped)[1].wall_section_ids


def test_core_output_is_exactly_the_owner_contract_output_for_hand_built_inputs():
    rows, rec = strip_scene()
    tag = result(rows, rec)[1]
    ids = [core.stable_contract_id("native_wall_end_section", {"scope": list(SCOPE), "native_path_ids": [i]})
           for i in (0, 1)]
    sections = (TracedWallSection(ids[0], SCOPE, (0,), (0.0, 101.0), (10.0, 101.0)),
                TracedWallSection(ids[1], SCOPE, (1,), (60.0, 101.0), (36.0, 101.0)))
    direct = tag_opening_to_two_wall_sections(
        DetectedOpeningContacts("opening-a", SCOPE, (2,), OpeningWallContact((10.0, 101.0), (0,)),
                                OpeningWallContact((36.0, 101.0), (1,))), sections)
    assert (direct.status, direct.contact_geometry, direct.wall_section_ids) == (
        tag.status, tag.contact_geometry, tag.wall_section_ids) == (
        "TWO_WALL_SECTIONS_TAGGED", "STRAIGHT_GAP", (ids[0], ids[1]))


# ---------------------------------------------------------------------------------------------------------------------
# metamorphic and invariance
# ---------------------------------------------------------------------------------------------------------------------


def transform_rows(rows, fn):
    out = []
    for row in rows:
        new = dict(row)
        new["items"] = tuple((it[0], *[fitz.Point(*fn(p.x, p.y)) for p in it[1:]]) for it in row["items"])
        corners = [fn(row["rect"].x0, row["rect"].y0), fn(row["rect"].x1, row["rect"].y1)]
        new["rect"] = fitz.Rect(min(c[0] for c in corners), min(c[1] for c in corners),
                                max(c[0] for c in corners), max(c[1] for c in corners))
        out.append(new)
    return out


def transform_anchors(anchors, fn):
    out = []
    for x0, y0, x1, y1 in anchors:
        a, b = fn(x0, y0), fn(x1, y1)
        out.append((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
    return tuple(out)


TRANSFORMS = {
    "translate": lambda x, y: (x + 1234.5, y - 987.25),
    "rotate90": lambda x, y: (-y, x),
    "rotate180": lambda x, y: (-x, -y),
    "rotate270": lambda x, y: (y, -x),
    "mirror_x": lambda x, y: (-x, y),
    "mirror_y": lambda x, y: (x, -y),
    "swap": lambda x, y: (y, x),
}


@pytest.mark.parametrize("name", sorted(TRANSFORMS))
@pytest.mark.parametrize("scene", ALL)
def test_tag_is_invariant_under_translation_rotation_and_mirroring(name, scene):
    rows, rec = scene()
    fn = TRANSFORMS[name]
    moved_rec = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, rec.first_wall_end_path_ids,
                               rec.second_wall_end_path_ids, transform_anchors(rec.anchors, fn))
    base = result(rows, rec)[1]
    moved = result(transform_rows(rows, fn), moved_rec)[1]
    assert (moved.status, moved.reason, moved.contact_geometry, moved.wall_section_ids) == (
        base.status, base.reason, base.contact_geometry, base.wall_section_ids)


@pytest.mark.parametrize("factor", [0.5, 2.0, 7.0])
@pytest.mark.parametrize("scene", ALL)
def test_exactly_coincident_geometry_is_scale_invariant(factor, scene):
    rows, rec = scene()
    fn = lambda x, y: (x * factor, y * factor)  # noqa: E731
    scaled_rec = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, rec.first_wall_end_path_ids,
                                rec.second_wall_end_path_ids, transform_anchors(rec.anchors, fn))
    base = result(rows, rec)[1]
    scaled = result(transform_rows(rows, fn), scaled_rec)[1]
    assert (scaled.status, scaled.contact_geometry) == (base.status, base.contact_geometry)


@pytest.mark.parametrize("scene", ALL)
def test_unrelated_rows_and_replay_do_not_change_the_tag(scene):
    rows, rec = scene()
    base = result(rows, rec)[1]
    noisy = list(rows) + [poly(500 + 30 * i, 500, 520 + 30 * i, 502) for i in range(30)]
    noisy += [line(5.0, 99.9, 60.0, 99.9), line(-50.0, 101.0, 200.0, 101.0)]
    assert result(noisy, rec)[1] == base
    assert result(copy.deepcopy(rows), rec)[1] == base


@pytest.mark.parametrize("scene", ALL)
def test_inputs_are_not_mutated(scene):
    rows, rec = scene()
    before = copy.deepcopy(rows)
    result(rows, rec)
    assert rows == before


def test_a_nearer_competing_row_is_never_chosen_over_the_named_wall_end():
    rows, rec = strip_scene()
    base = result(rows, rec)[1]
    rows += [poly(10.0, 100.0, 12.0, 102.0), poly(34.0, 100.0, 36.0, 102.0)]  # strips sitting in the doorway
    assert result(rows, rec)[1] == base


# ---------------------------------------------------------------------------------------------------------------------
# negatives: each stops at its own named gate
# ---------------------------------------------------------------------------------------------------------------------


def test_the_face_of_a_passing_wall_is_not_a_wall_end():
    reason, tag = result(*face_scene())
    assert reason == GATE_FACE_NOT_END and tag is None


def test_face_guard_boundary_is_a_scale_free_ratio():
    ratio = core.END_THICKNESS_TO_OPENING_EDGE_RATIO
    edge = 2.6  # the opening edge's extent across the wall (CAPS)
    rows, rec = strip_scene()
    inside = edge * ratio - 0.05
    rows[1] = poly(36.0, 101.0 - inside / 2.0, 60.0, 101.0 + inside / 2.0)
    assert result(rows, rec)[0] == OK
    outside = edge * ratio + 0.05
    rows[1] = poly(36.0, 101.0 - outside / 2.0, 60.0, 101.0 + outside / 2.0)
    assert result(rows, rec)[0] == GATE_FACE_NOT_END
    # a cap covering only part of the wall thickness still meets a normal wall end
    rows, rec = strip_scene()
    rec = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, rec.first_wall_end_path_ids,
                         rec.second_wall_end_path_ids, ((10.0, 100.0, 11.1, 100.85), (34.9, 100.0, 36.0, 100.85)))
    assert result(rows, rec)[0] == OK


def test_invalid_groups_receipts_and_anchors_are_named():
    rows, rec = strip_scene()
    for first in ((), (0, 0), (9,), (-1,), (True,), [0], (0.0,)):
        bad = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, first,
                             rec.second_wall_end_path_ids, rec.anchors)
        assert result(rows, bad)[0] == GATE_GROUP_INVALID
    overlap = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (0,), rec.anchors)
    assert result(rows, overlap)[0] == GATE_GROUPS_OVERLAP
    for opening in ((), (9,), (0,), (1,), [2]):
        bad = WallEndReceipt(rec.opening_id, rec.scope, opening, (0,), (1,), rec.anchors)
        assert result(rows, bad)[0] == GATE_OPENING_PATHS_MISSING
    for anchors in ((), ((1.0, 2.0),), ((float("nan"), 0.0, 1.0, 1.0),), ((2.0, 0.0, 1.0, 1.0),),
                    ((True, 0, 1, 1),), (None,)):
        bad = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), anchors)
        assert result(rows, bad)[0] == GATE_NO_ANCHORS


def test_unreadable_wall_rows_are_named():
    for bad_rect in (None, fitz.Rect(10.0, 100.0, 0.0, 102.0), (0.0, 102.0, 10.0, 100.0),
                     (0.0, 100.0, float("nan"), 102.0), (0.0, 100.0), "abc", 5):
        rows, rec = strip_scene()
        rows[0] = {**rows[0], "rect": bad_rect}
        assert result(rows, rec)[0] == GATE_ROW_UNREADABLE
    rows, rec = strip_scene()
    rows[1] = "not a row"
    assert result(rows, rec)[0] == GATE_ROW_UNREADABLE


def test_an_opening_edge_must_meet_each_wall_end_within_the_contract_tolerance():
    rows, rec = strip_scene()

    def with_anchors(a, b):
        return WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), (a, b))

    assert result(rows, with_anchors((10.0 + TOL - 1e-6, 99.7, 11.1, 102.3), CAPS[1]))[0] == OK
    assert result(rows, with_anchors((10.0 + TOL + 1e-3, 99.7, 11.1, 102.3), CAPS[1]))[0] == GATE_ANCHOR_MISSING
    assert result(rows, with_anchors(CAPS[0], (34.9, 99.7, 36.0 - TOL - 1e-3, 102.3)))[0] == GATE_ANCHOR_MISSING
    assert result(rows, with_anchors(CAPS[0], (34.9, 103.0, 36.0, 105.0)))[0] == GATE_ANCHOR_MISSING  # beside the wall
    assert result(rows, with_anchors(CAPS[0], (34.9, 102.0, 36.0, 104.0)))[0] == GATE_ANCHOR_MISSING  # touches only
    assert result(rows, with_anchors((50.0, 0.0, 51.0, 1.0), CAPS[1]))[0] == GATE_ANCHOR_MISSING


def test_one_edge_cannot_stand_for_both_ends_and_a_missing_edge_names_the_side():
    rows, rec = strip_scene()
    only_left = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), (CAPS[0],))
    assert result(rows, only_left)[0] == GATE_ANCHOR_MISSING
    only_right = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), (CAPS[1],))
    assert result(rows, only_right)[0] == GATE_ANCHOR_MISSING


def test_edges_that_disagree_at_one_wall_end_are_competing_and_coincident_edges_are_one():
    rows, rec = strip_scene()

    def with_anchors(*anchors):
        return WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), tuple(anchors))

    assert result(rows, with_anchors(CAPS[0], (10.0, 99.9, 11.1, 102.6), CAPS[1]))[0] == OK
    assert result(rows, with_anchors(CAPS[0], (10.0 + 0.1, 99.9, 11.1, 102.6), CAPS[1]))[0] == OK
    assert result(rows, with_anchors((9.83, 99.7, 11.1, 102.3), (10.17, 99.9, 11.1, 102.6), CAPS[1]))[0] == (
        GATE_ANCHORS_DISAGREE)


def test_a_group_met_on_two_sides_is_competing_not_chosen():
    rows, rec = strip_scene()
    # a second edge meeting the same strip at its far end as well
    both_ends = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                               (CAPS[0], CAPS[1], (-1.1, 99.7, 0.0, 102.3)))
    assert result(rows, both_ends)[0] == GATE_END_SIDES_COMPETING


def test_wall_end_must_reach_its_faces_at_the_edge():
    p = fitz.Point
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": (("l", p(36.0, 100.0), p(60.0, 100.0)), ("l", p(36.0, 102.0), p(60.0, 102.0)),
                                    ("l", p(60.0, 100.0), p(60.0, 102.0)))}      # two face lines, no end cap
    assert result(rows, rec)[0] == OK     # face lines that end at the opening edge are themselves the wall end
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": (("l", p(36.0, 100.0), p(60.0, 100.0)), ("l", p(60.0, 100.0), p(60.0, 102.0)))}
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING   # only one face reaches the opening edge
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": ()}
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = outlined_scene()
    rows[2] = line(36.0, 100.0, 60.0, 100.0)
    rows[3] = line(40.0, 102.0, 60.0, 102.0)            # one face line stops short of the doorway end
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = outlined_scene()
    rows[2] = line(36.0, 100.0, 60.0, 100.0)
    rows[3] = line(36.0 + TOL + 1e-3, 102.0, 60.0, 102.0)
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = outlined_scene()
    rows[3] = line(36.0 + TOL - 1e-3, 102.0, 60.0, 102.0)
    assert result(rows, rec)[0] == OK


def test_slanted_or_one_lip_ends_do_not_count():
    p = fitz.Point
    for items in (
        [("l", p(36.0, 100.0), p(36.2, 102.0))],
        [("l", p(36.2, 102.0), p(36.0, 100.0))],
        [("l", p(36.0, 100.5), p(36.0, 102.0))],     # misses the low face by half a point
        [("l", p(36.0, 100.0), p(36.0, 101.5))],     # misses the high face by half a point
        [("l", p(36.0, 100.0), p(36.0, 100.0)), ("l", p(36.0, 102.0), p(36.0, 102.0))],   # points, not an edge
    ):
        rows, rec = strip_scene()
        far = [("l", p(60.0, 100.0), p(60.0, 102.0)), ("l", p(60.0, 100.0), p(37.0, 100.0)),
               ("l", p(60.0, 102.0), p(37.0, 102.0))]
        rows[1] = {**rows[1], "items": tuple(far + items)}
        assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = strip_scene()
    far = [("l", p(60.0, 100.0), p(60.0, 102.0)), ("l", p(60.0, 100.0), p(36.0, 100.0)),
           ("l", p(60.0, 102.0), p(36.0, 102.0))]
    rows[1] = {**rows[1], "items": tuple(far + [("l", p(36.0, 100.0 + TOL - 1e-3), p(36.0, 102.0 - TOL + 1e-3))])}
    assert result(rows, rec)[0] == OK


def test_wall_end_rows_may_be_tuples_rects_and_quads_and_curves_draw_no_end():
    p = fitz.Point
    rows, rec = strip_scene()
    rows[0] = {**rows[0], "items": (("l", (0.0, 100.0), (10.0, 100.0)), ("l", (10.0, 100.0), (10.0, 102.0)),
                                    ("l", (10.0, 102.0), (0.0, 102.0)), ("l", (0.0, 102.0), (0.0, 100.0)))}
    rows[1] = {**rows[1], "items": (("re", fitz.Rect(36.0, 100.0, 60.0, 102.0)),)}
    assert result(rows, rec)[0] == OK
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": (("qu", fitz.Quad(p(36.0, 100.0), p(60.0, 100.0), p(36.0, 102.0), p(60.0, 102.0))),)}
    assert result(rows, rec)[0] == OK
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": (("c", p(36, 100), p(40, 100), p(40, 102), p(36, 102)),)}
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = strip_scene()
    rows[1] = {**rows[1], "items": (("l", object(), object()), ("l", (float("nan"), 0.0), (1.0, 0.0)), (), "x")}
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING


def test_wall_ends_that_face_the_same_way_or_touch_are_not_a_gap():
    rows, rec = strip_scene()
    rows[1] = poly(-24.0, 100.0, -14.0, 102.0)       # a second strip whose end also faces +x
    same_way = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                              ((10.0, 99.7, 11.1, 102.3), (-14.0, 99.7, -12.9, 102.3)))
    assert result(rows, same_way)[0] == GATE_ENDS_NOT_OPPOSED
    rows, rec = strip_scene()
    rows[1] = poly(20.0, 100.0, 30.0, 102.0)         # two walls in a row, both ends facing +x, a positive gap between
    in_a_row = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                              ((10.0, 99.7, 11.1, 102.3), (30.0, 99.7, 31.1, 102.3)))
    assert result(rows, in_a_row)[0] == GATE_ENDS_NOT_OPPOSED
    rows, rec = strip_scene()
    rows[1] = poly(10.0, 100.0, 60.0, 102.0)          # no gap: the ends touch
    touching = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                              ((10.0, 99.7, 11.1, 102.3), (9.0, 99.7, 10.0, 102.3)))
    assert result(rows, touching)[0] == GATE_ENDS_NOT_OPPOSED


def test_walls_offset_across_the_gap_are_not_collinear():
    rows, rec = strip_scene()
    rows[1] = poly(36.0, 110.0, 60.0, 112.0)
    offset = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                            (CAPS[0], (34.9, 109.7, 36.0, 112.3)))
    assert result(rows, offset)[0] == GATE_NOT_COLLINEAR
    rows, rec = strip_scene()
    rows[1] = poly(36.0, 102.0, 60.0, 104.0)         # shares only an edge line, no common thickness
    edge = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                          (CAPS[0], (34.9, 101.7, 36.0, 104.3)))
    assert result(rows, edge)[0] == GATE_NOT_COLLINEAR
    rows, rec = hairline_scene()
    rows[1] = line(36.0, 101.5, 60.0, 101.5)
    two_lines = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                               ((10.0, 100.0, 11.0, 102.0), (35.0, 100.0, 36.0, 102.0)))
    assert result(rows, two_lines)[0] == GATE_NOT_COLLINEAR


def test_a_perpendicular_wall_that_runs_through_the_other_contact_is_not_a_corner_doorway():
    rows = [poly(0.0, 94.0, 10.0, 96.0), poly(10.0, 80.0, 12.0, 100.0), leaf()]
    anchors = ((10.0, 93.7, 11.1, 96.3), (9.7, 100.0, 12.3, 101.1))
    assert result(rows, receipt((0,), (1,), anchors, opening=(2,)))[0] == GATE_WALL_THROUGH_OPENING


def test_a_gap_just_over_the_contract_tolerance_is_a_gap():
    rows, rec = strip_scene()
    rows[1] = poly(11.0, 100.0, 60.0, 102.0)         # one point of gap, far under any scale-relative rule
    one_edge = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), (CAPS[0],))
    assert result(rows, one_edge)[0] == OK
    for gap, expected in ((TOL + 1e-3, OK), (TOL - 1e-3, GATE_ENDS_NOT_OPPOSED)):
        rows[1] = poly(10.0 + gap, 100.0, 60.0, 102.0)
        spanning = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                                  ((10.0, 99.7, 10.0 + gap, 102.3),))   # one edge spans the whole hairline gap
        assert result(rows, spanning)[0] == expected


def test_non_finite_and_inverted_opening_edges_are_rejected_before_any_geometry():
    rows, rec = strip_scene()
    for anchors in (((0.0, 0.0, float("inf"), 1.0),), ((0.0, 2.0, 1.0, 1.0),), ((2.0, 0.0, 1.0, 1.0),),
                    ((0.0, float("-inf"), 1.0, 1.0),)):
        bad = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), anchors)
        assert result(rows, bad)[0] == GATE_NO_ANCHORS


def test_a_hairline_wall_needs_an_opening_edge_that_crosses_its_line():
    rows, rec = hairline_scene()
    left = (10.0, 100.0, 11.0, 102.0)

    def with_right(anchor):
        return WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,), (left, anchor))

    assert result(rows, with_right((35.0, 100.0, 36.0, 102.0)))[0] == OK
    assert result(rows, with_right((35.0, 102.5, 36.0, 103.0)))[0] == GATE_ANCHOR_MISSING      # beside the line
    assert result(rows, with_right((35.0, 101.0 + TOL + 1e-3, 36.0, 103.0)))[0] == GATE_ANCHOR_MISSING
    assert result(rows, with_right((35.0, 101.0 + TOL - 1e-3, 36.0, 103.0)))[0] == OK
    assert result(rows, with_right((35.0, 99.0, 36.0, 101.0 - TOL - 1e-3)))[0] == GATE_ANCHOR_MISSING
    assert result(rows, with_right((35.0, 99.0, 36.0, 101.0 - TOL + 1e-3)))[0] == OK


def test_only_face_lines_parallel_to_the_wall_count_as_a_wall_end():
    rows, rec = outlined_scene()
    rows[2] = line(36.0, 100.0, 60.0, 100.0 + TOL + 0.12)   # leaves the end line at a slant: not a face line
    assert result(rows, rec)[0] == GATE_END_EDGE_MISSING
    rows, rec = outlined_scene()
    rows[2] = line(36.0, 100.0, 60.0, 100.0 + TOL - 0.01)   # within the tolerance it is still parallel
    assert result(rows, rec)[0] == OK


def test_end_thickness_guard_uses_the_widest_opening_edge_and_never_blocks_hairlines():
    rows, rec = strip_scene()
    rows[1] = poly(36.0, 96.0, 60.0, 106.0)           # 10 thick: 3.8 x the full cap, 10 x a 1.0 cap
    two_edges = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                               (CAPS[0], (34.9, 100.5, 36.0, 101.5), (34.9, 99.7, 36.0, 102.3)))
    assert result(rows, two_edges)[0] == OK
    # a wall thinner than the contract tolerance has no thickness to compare: it is never a "face"
    rows, rec = strip_scene()
    rows[0] = poly(0.0, 101.0, 10.0, 101.1)
    rows[1] = poly(36.0, 101.0, 60.0, 101.1)
    tiny = WallEndReceipt(rec.opening_id, rec.scope, rec.opening_native_path_ids, (0,), (1,),
                          ((10.0, 101.0, 11.1, 101.01), (34.9, 101.0, 36.0, 101.01)))
    assert result(rows, tiny)[0] == OK


def test_scope_is_carried_into_every_section_and_contact():
    rows, rec = strip_scene()
    other = WallEndReceipt(rec.opening_id, ("b" * 64, "revision-a", "page-3"), rec.opening_native_path_ids,
                           rec.first_wall_end_path_ids, rec.second_wall_end_path_ids, rec.anchors)
    assert result(rows, rec)[1].wall_section_ids != result(rows, other)[1].wall_section_ids


# ---------------------------------------------------------------------------------------------------------------------
# structure guards
# ---------------------------------------------------------------------------------------------------------------------

MODULE_PATH = Path(core.__file__)


def test_core_imports_only_the_contract_and_stable_ids():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert {n for n in imported if n.startswith("pb_")} == {"pb_migration_contracts", "pb_opening_two_wall_contact_tags"}


def test_core_has_no_project_layer_or_drawing_literal():
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    forbidden = ("laurel", "maryborough", "lot16", "acacia", "enclosure_", "2100", "720", "870", "annotation_",
                 "layer", "014e9f68")
    # the word "layer" only appears in prose about drawing conventions? it must not be read as a field
    assert [w for w in forbidden if w in source and w != "layer"] == []
    assert 'get("layer")' not in source and "['layer']" not in source
