"""Synthetic proof for the page-11 -> page-7 floor-correspondence diagnostic (pure geometry; no PDF, no benchmark input)."""
from __future__ import annotations

import copy
import json
import random

import pytest

from tools import diag_ft3_p11_p7_floor_correspondence as d

PITCH = 34.02


def seg(x1, y1, x2, y2):
    return {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}


def room(x0, y0, x1, y1, t=5.28, gaps=()):
    """Double-line walls (face + second face behind it). gaps: (side, lo, hi) openings removed from the FACE and second-face lines."""
    sides = {
        "x0": [(x0, y0, x0, y1), (x0 - t, y0 - t, x0 - t, y1 + t)],
        "x1": [(x1, y0, x1, y1), (x1 + t, y0 - t, x1 + t, y1 + t)],
        "y0": [(x0, y0, x1, y0), (x0 - t, y0 - t, x1 + t, y0 - t)],
        "y1": [(x0, y1, x1, y1), (x0 - t, y1 + t, x1 + t, y1 + t)],
    }
    out = []
    for name, pairs in sides.items():
        for a, b, c, e in pairs:
            segs = [(a, b, c, e)]
            for gname, lo, hi in gaps:
                if gname != name:
                    continue
                nxt = []
                for sa, sb, sc, se in segs:
                    if sa == sc:  # vertical: gap interval is along y
                        pieces = [(sb, min(se, lo)), (max(sb, hi), se)]
                        nxt += [(sa, p, sc, q) for p, q in pieces if q > p]
                    else:
                        pieces = [(sa, min(sc, lo)), (max(sa, hi), sc)]
                        nxt += [(p, sb, q, se) for p, q in pieces if q > p]
                segs = nxt
            out += [seg(*s) for s in segs]
    return out


def tile_grid(x0, y0, x1, y1, pitch=PITCH):
    out = []
    x = x0
    while x <= x1:
        out.append(seg(x, y0, x, y1))
        x += pitch
    y = y0
    while y <= y1:
        out.append(seg(x0, y, x1, y))
        y += pitch
    return out


def moved(segs, dx, dy):
    return [seg(s["x1"] + dx, s["y1"] + dy, s["x2"] + dx, s["y2"] + dy) for s in segs]


def mapped(segs, mat, scale=1.0, dx=0.0, dy=0.0):
    a, b, c, e = (scale * v for v in mat)
    return [seg(a * s["x1"] + b * s["y1"] + dx, c * s["x1"] + e * s["y1"] + dy, a * s["x2"] + b * s["y2"] + dx, c * s["x2"] + e * s["y2"] + dy) for s in segs]


# an aperiodic plan: three wall-bounded rooms with unequal sizes and an opening
PLAN = (
    room(173.04, 1382.72, 316.80, 1585.04, gaps=(("y0", 230.0, 280.0),))
    + room(340.5, 1390.0, 560.2, 1600.0)
    + room(600.0, 1100.0, 733.0, 1301.0)
    + room(210.0, 700.0, 330.0, 951.0)
)
SHEET_A = PLAN + [seg(60, 60, 60, 400), seg(95, 60, 95, 400)]  # page-7-like: plan walls (typed grid evidence is excluded upstream)
TRUE_T = (-78.0, 0.0)  # p11 -> p7


def sheet_b():
    """page-11-like: the same walls in a frame shifted by +78 plus an unrelated annotation block (grid excluded upstream)."""
    extras = [seg(1300, 100, 1300, 900), seg(1340, 100, 1340, 900), seg(1300, 100, 1340, 100)]
    return moved(PLAN, 78.0, 0.0) + extras


def lines_of(segs):
    return d.build_lines(segs)


def best_of(src_segs, dst_segs, **kw):
    return d.rank_registrations(lines_of(src_segs), lines_of(dst_segs), **kw)


# ---------------------------------------------------------------------------------------------- positives
def test_registration_recovers_exact_rigid_transform_with_margin():
    rows = best_of(sheet_b(), SHEET_A)
    top = rows[0]
    assert (top["orientation"], top["scale"], top["dx"], top["dy"]) == ("identity", 1.0, TRUE_T[0], TRUE_T[1])
    assert top["min_support_pt"] > 2 * rows[1]["min_support_pt"]
    null = d.null_support(lines_of(sheet_b()), lines_of(SHEET_A), trials=60)
    assert top["min_support_pt"] > 20 * max(null["max"], 1e-9)


def test_exact_box_correspondence_is_wall_bounded_on_both_sheets_with_registered_opening():
    box_support = (251.04, 1382.72, 394.80, 1585.04)  # the box on page 11
    corr = d.box_correspondence(box_support, lines_support=lines_of(sheet_b()), lines_target=lines_of(SHEET_A), orientation="identity", translation=TRUE_T)
    assert corr["wall_bounded_on_both_sheets"] is True
    assert corr["wall_evidence_identical_on_both_sheets"] is True
    assert corr["side_kinds"]["y0"] == "with_openings"
    assert {corr["side_kinds"][k] for k in ("x0", "x1", "y1")} == {"full"}
    assert corr["sides"]["y0"]["covered_interval_iou"] == pytest.approx(1.0, abs=1e-6)


def test_box_side_on_the_outer_face_of_a_wall_is_still_a_wall_side():
    # the measured box edge lies on the OUTER face of the east wall (second face 5.28 pt inside it)
    plan = room(100, 100, 300, 260)
    outer = (100 - 5.28, 100 - 5.28, 300 + 5.28, 260 + 5.28)
    corr = d.box_correspondence(outer, lines_support=lines_of(plan), lines_target=lines_of(plan), orientation="identity", translation=(0.0, 0.0))
    assert corr["wall_bounded_on_both_sheets"] is True
    assert all(k == "full" for k in corr["side_kinds"].values())


def test_classify_unique_owner():
    corr = {"wall_bounded_on_both_sheets": True, "wall_evidence_identical_on_both_sheets": True}
    out = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 54.8}], other_labelled_boxes_overlapping=0, material_code="FT3",
                           authority_blockers=list(d.STANDING_AUTHORITY_BLOCKERS))
    assert out["status"] == "candidate"  # geometric ownership only; the diagnostic never emits corroborated
    assert out["authenticated_physical_wall_face_equivalence"] is False
    assert out["authority_blockers"] == list(d.STANDING_AUTHORITY_BLOCKERS)
    assert out["finish_codes_in_box"] == {"FT3": 1}


# ------------------------------------------------------------------------- look-alike negatives / ambiguity
def test_periodic_grid_only_is_not_a_unique_registration():
    grid_a = tile_grid(0, 0, 400, 400)
    grid_b = tile_grid(0, 0, 400, 400)
    rows = best_of(grid_b, grid_a, identity_only=True, identity_scales=(1.0,))
    top = rows[0]
    assert top["next_distinct_min_support_pt"] is not None
    assert top["next_distinct_min_support_pt"] >= 0.5 * top["min_support_pt"]  # alias translations by one pitch stay competitive


def test_identical_repeated_rooms_retain_equally_supported_alternatives():
    repeated = room(100, 100, 220, 260) + room(400, 100, 520, 260) + room(700, 100, 820, 260)
    rows = best_of(repeated, repeated, identity_only=True, identity_scales=(1.0,))
    top = rows[0]
    assert top["next_distinct_min_support_pt"] >= 0.6 * top["min_support_pt"]  # translation by the repeat step is a competitor


def test_open_plan_box_without_walls_is_not_wall_bounded_and_abstains():
    # box sides lie on thin dimension/grid-like lines with no second face behind them
    sheet = tile_grid(0, 0, 400, 400, pitch=100.0)
    corr = d.box_correspondence((100, 100, 300, 300), lines_support=lines_of(sheet), lines_target=lines_of(sheet), orientation="identity", translation=(0.0, 0.0))
    assert corr["wall_bounded_on_both_sheets"] is False
    out = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 40.0}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert out["status"] == "abstained" and "box_not_wall_bounded_on_both_sheets" in out["reason_codes"]


def test_wrong_registration_fails_the_box_test():
    box_support = (251.04, 1382.72, 394.80, 1585.04)
    for alt in ((0.0, 0.0), (-78.0, 136.08), (-43.92, 0.0)):
        corr = d.box_correspondence(box_support, lines_support=lines_of(sheet_b()), lines_target=lines_of(SHEET_A), orientation="identity", translation=alt)
        assert corr["wall_bounded_on_both_sheets"] is False, alt


def test_competing_finish_codes_conflict_and_other_code_abstains():
    corr = {"wall_bounded_on_both_sheets": True, "wall_evidence_identical_on_both_sheets": True}
    mixed = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 30}, {"code": "FT2", "margin_pt": 30}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert mixed["status"] == "conflict"
    other = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "EPX", "margin_pt": 30}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert other["status"] == "abstained" and "box_owned_by_other_finish_code" in other["reason_codes"]
    none = d.classify_floor(corr, registration_unique=True, marks_inside=[], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert none["status"] == "abstained" and "no_finish_mark_in_box" in none["reason_codes"]
    near = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 1.0}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert near["status"] == "abstained" and "mark_too_close_to_box_side" in near["reason_codes"]
    unregistered = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 30, "registered_region": False}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert unregistered["status"] == "abstained" and "mark_in_unregistered_region" in unregistered["reason_codes"]
    overlap = d.classify_floor(corr, registration_unique=True, marks_inside=[{"code": "FT3", "margin_pt": 30}], other_labelled_boxes_overlapping=1, material_code="FT3")
    assert overlap["status"] == "abstained"
    unreg = d.classify_floor(corr, registration_unique=False, marks_inside=[{"code": "FT3", "margin_pt": 30}], other_labelled_boxes_overlapping=0, material_code="FT3")
    assert unreg["status"] == "abstained" and "registration_not_unique" in unreg["reason_codes"]


# -------------------------------------------------------------------------------------------- metamorphic
@pytest.mark.parametrize("shift", [(0.0, 0.0), (37.5, -912.25), (-400.0, 1500.0)])
def test_translation_metamorphic(shift):
    src = moved(sheet_b(), *shift)
    rows = best_of(src, SHEET_A)
    assert (rows[0]["orientation"], rows[0]["scale"]) == ("identity", 1.0)
    assert rows[0]["dx"] == pytest.approx(TRUE_T[0] - shift[0], abs=0.1)
    assert rows[0]["dy"] == pytest.approx(TRUE_T[1] - shift[1], abs=0.1)


@pytest.mark.parametrize("name", ["rot90", "rot180", "rot270", "mirror_x", "mirror_y", "transpose"])
def test_orientation_metamorphic(name):
    src = mapped(sheet_b(), d.D4[name], dx=2000.0, dy=3000.0)
    rows = best_of(src, SHEET_A)
    inverse = {"rot90": "rot270", "rot270": "rot90"}.get(name, name)  # the map that brings the rotated sheet back
    assert rows[0]["orientation"] == inverse


@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_scale_metamorphic_identity_orientation(scale):
    src = mapped(sheet_b(), d.D4["identity"], scale=1.0 / scale)  # sheet B drawn at 1/scale relative to A
    rows = best_of(src, SHEET_A)
    assert rows[0]["orientation"] == "identity" and rows[0]["scale"] == scale


# ---------------------------------------------------------------------------------------------- invariance
def test_split_and_input_order_invariance():
    base = best_of(sheet_b(), SHEET_A)
    rng = random.Random(7)
    pieces = []
    for s in sheet_b():
        if abs(s["y1"] - s["y2"]) < 1e-9 and abs(s["x2"] - s["x1"]) > 20:
            mid = (s["x1"] + s["x2"]) / 2 + rng.uniform(-3, 3)
            pieces += [seg(s["x1"], s["y1"], mid, s["y2"]), seg(mid, s["y1"], s["x2"], s["y2"])]
        else:
            pieces.append(s)
    rng.shuffle(pieces)
    other = best_of(pieces, SHEET_A)
    assert [(r["orientation"], r["scale"], r["dx"], r["dy"], r["min_support_pt"]) for r in base] == [
        (r["orientation"], r["scale"], r["dx"], r["dy"], r["min_support_pt"]) for r in other
    ]


def test_unrelated_content_and_viewport_expansion_do_not_move_or_weaken_the_winner():
    base = best_of(sheet_b(), SHEET_A)[0]
    far = [seg(5000 + i * 17.3, 4000, 5000 + i * 17.3, 4300) for i in range(30)] + [seg(5000, 4000 + j * 11.7, 5500, 4000 + j * 11.7) for j in range(20)]
    grown = best_of(sheet_b() + far, SHEET_A + moved(far, 9000, 7000))[0]
    assert (grown["dx"], grown["dy"]) == (base["dx"], base["dy"])
    assert grown["min_support_pt"] >= base["min_support_pt"] - 1e-6


def test_deterministic_replay_and_no_mutation():
    a, b = sheet_b(), copy.deepcopy(SHEET_A)
    snapshot = copy.deepcopy((a, b))
    one = json.dumps(best_of(a, b), sort_keys=True)
    two = json.dumps(best_of(a, b), sort_keys=True)
    assert one == two
    assert (a, b) == snapshot
    n1 = d.null_support(lines_of(a), lines_of(b), trials=40)
    n2 = d.null_support(lines_of(a), lines_of(b), trials=40)
    assert n1 == n2


# ----------------------------------------------------------------------------------------------- helpers
def test_point_margin_and_box_translation():
    box = (0.0, 0.0, 10.0, 20.0)
    assert d.point_margin((5, 5), box) == 5.0
    assert d.point_margin((12, 5), box) == -2.0
    assert d.translate_box(box, "identity", (3.0, -4.0)) == (3.0, -4.0, 13.0, 16.0)
    assert d.translate_box(box, "rot90", (0.0, 0.0)) == (-20.0, 0.0, 0.0, 10.0)


def test_interval_iou_is_split_invariant():
    a = [(0.0, 10.0), (20.0, 30.0)]
    b = [(0.0, 4.0), (4.0, 10.0), (20.0, 25.0), (25.0, 30.0)]
    assert d.interval_iou(a, b) == pytest.approx(1.0)
    assert d.interval_iou(a, [(0.0, 10.0)]) == pytest.approx(0.5)


# ------------------------------------------------------------------------------- ownership and face equivalence
def _segments(segs):
    return {f"p{i}": s for i, s in enumerate(segs)}


def test_side_ownership_flags_shared_and_unowned_primitives():
    segs = _segments([seg(100, 100, 100, 260), seg(100, 100, 100, 180), seg(300, 100, 300, 260), seg(100, 100, 300, 100), seg(100, 260, 300, 260)])
    owners = {"p0": ["w1"], "p1": ["w1", "w2"], "p2": ["w3"], "p3": ["w4"]}  # p4 (the y1 side) is unowned
    out = d.side_ownership((100, 100, 300, 260), segs, owners, {"w3": True})
    assert out["x0"]["owned_by_multiple_candidates"] == 1 and out["x0"]["distinct_candidates"] == 2
    assert out["x1"] == {"primitives_on_side": 1, "unowned_by_any_w4_candidate": 0, "owned_by_multiple_candidates": 0, "distinct_candidates": 1, "grid_opposed_candidates": 1}
    assert out["y1"]["unowned_by_any_w4_candidate"] == 1
    blockers = d.ownership_blockers({"7": out})
    assert "page_7_box_side_primitive_claimed_by_several_w4_candidates" in blockers
    assert "page_7_box_side_primitive_unowned_by_w4" in blockers


def test_clean_unique_ownership_has_no_ownership_blockers():
    segs = _segments([seg(100, 100, 100, 260), seg(300, 100, 300, 260), seg(100, 100, 300, 100), seg(100, 260, 300, 260)])
    owners = {"p0": ["a"], "p1": ["b"], "p2": ["c"], "p3": ["d"]}
    assert d.ownership_blockers({"7": d.side_ownership((100, 100, 300, 260), segs, owners, {})}) == []


def test_ownership_is_invariant_to_primitive_splitting_and_order():
    whole = _segments([seg(100, 100, 100, 260)])
    split = _segments([seg(100, 180, 100, 260), seg(100, 100, 100, 180)])
    a = d.side_ownership((100, 100, 300, 260), whole, {"p0": ["w"]}, {})
    b = d.side_ownership((100, 100, 300, 260), split, {"p0": ["w"], "p1": ["w"]}, {})
    assert a["x0"]["distinct_candidates"] == b["x0"]["distinct_candidates"] == 1
    assert a["x0"]["owned_by_multiple_candidates"] == b["x0"]["owned_by_multiple_candidates"] == 0


def test_face_equivalence_retains_every_alternative_and_periodic_cells_are_not_unique_identity():
    cell = lambda x, y: [[x, y], [x + 34.0, y], [x + 34.0, y + 34.0], [x, y + 34.0]]
    faces = {f"c{i}": cell(i * 34.0, 0.0) for i in range(5)}  # a periodic row of identical cells
    exact = d.face_equivalence(cell(0.0, 0.0), faces, (68.0, 0.0), top=5)
    assert exact[0]["face_id"] == "c2" and exact[0]["iou"] == pytest.approx(1.0)
    shifted = d.face_equivalence(cell(0.0, 0.0), faces, (68.0 + 34.0, 0.0), top=5)
    assert shifted[0]["face_id"] == "c3" and shifted[0]["iou"] == pytest.approx(1.0)  # an alias translation is equally 'exact'
    partial = d.face_equivalence(cell(0.0, 0.0), faces, (85.0, 0.0), top=5)
    assert [r["face_id"] for r in partial[:2]] == ["c2", "c3"]  # half-overlaps both neighbours: both retained, none elected
    assert partial[0]["iou"] == pytest.approx(partial[1]["iou"], abs=1e-6)
