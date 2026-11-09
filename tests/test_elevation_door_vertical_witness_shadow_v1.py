"""Source-neutral proof for the elevation vertical witness SHADOW (plain numbers, no private drawing)."""
from __future__ import annotations

import copy
import random
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_elevation_door_vertical_witness_shadow as shadow
from pb_elevation_door_vertical_witness_shadow import (
    DatumLevel, ElevOutline, ElevationDatum, PlanSpan, Scope,
    assess_elevation_vertical_witness_shadow, calibrate_datum, register_plan_to_elevation, resolve_vertical_witness,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
MM = 35.28                      # mm per page point for the scene (a 1:100 sheet)
FFL = 277.57
SPACING_2100 = 2100.0 / MM
SCOPE = Scope("doc", "rev", "a" * 64, "snap")
SILL = 2.26                     # drawn sill band under a door leaf, pt


def make_datum(scale=1.0, ffl=FFL, **over):
    ffl_y = ffl * scale
    levels = (
        DatumLevel("JOINERY", ffl_y - scale * SPACING_2100, over.get("joinery_mm", 2100.0)),
        DatumLevel("FCL", ffl_y - scale * 2700.0 / MM, 2700.0),
        DatumLevel("TP", ffl_y - scale * 2740.0 / MM, 2740.0),
    )
    return ElevationDatum(ffl_y, levels)


# plan spans along one facade axis (plan points) and what the drawn elevation shows for the ones that are visible
PLAN = {
    "entry": (300.29, 334.31, "door_sill"),       # 34.02 wide; leaf head on JOINERY, leaf base above FFL, frame base on FFL
    "garage": (359.42, 493.73, "door_ffl"),       # 134.31 wide; head on JOINERY, base on FFL
    "win1": (120.0, 168.64, "window"),            # 48.64 wide; head on JOINERY, sill above FFL
    "win2": (200.0, 248.64, "window"),
}


def make_scene(*, sign=-1, offset=984.285, plan_shift=0.0, scale=1.0, extra_plan=(), drop_outlines=()):
    d = make_datum(scale)
    plan, outlines = [], []
    for rid, (a0, a1, kind) in PLAN.items():
        plan.append(PlanSpan(rid, scale * a0 + plan_shift, scale * a1 + plan_shift))
        if rid in drop_outlines:
            continue
        pa0, pa1 = scale * a0, scale * a1
        x0, x1 = (pa0 + offset * scale, pa1 + offset * scale) if sign > 0 else (-pa1 + offset * scale, -pa0 + offset * scale)
        head = d.levels[0].y
        if kind == "door_sill":
            outlines.append(ElevOutline("o_" + rid, x0, x1, head, d.ffl_y - scale * SILL, d.ffl_y))
        elif kind == "door_ffl":
            outlines.append(ElevOutline("o_" + rid, x0, x1, head, d.ffl_y))
        else:
            outlines.append(ElevOutline("o_" + rid, x0, x1, head, d.ffl_y - scale * 30.0))
    plan.extend(extra_plan)
    # plan translation must not move the elevation: re-anchor the registration offset by compensating the plan shift
    return plan, outlines, d


def run(record_id, plan, outlines, datum, *, plan_scope=SCOPE, elevation_scope=SCOPE):
    return resolve_vertical_witness(record_id, plan, outlines, datum, plan_scope=plan_scope, elevation_scope=elevation_scope)


def test_door_with_a_sill_band_gets_the_printed_datum_height_and_a_separate_leaf_height():
    plan, outlines, d = make_scene()
    r = run("entry", plan, outlines, d)
    assert r.status is CAND and r.reason_codes == (shadow.CANDIDATE_REASON,)
    assert r.opening_height_mm == 2100.0 and r.head_level_name == "JOINERY"
    # leaf-vs-opening confusion: the drawn leaf (head to leaf base) is shorter and is NEVER reported as the opening height
    assert r.leaf_height_mm == pytest.approx(2100.0 - SILL * MM, abs=1.0)
    assert r.leaf_height_mm != r.opening_height_mm
    assert r.status is not EvidenceResolutionStatus.CORROBORATED
    assert r.mm_per_pt == pytest.approx(MM, rel=1e-3)


def test_garage_door_on_ffl_is_a_candidate_and_windows_are_not_doors():
    plan, outlines, d = make_scene()
    assert run("garage", plan, outlines, d).opening_height_mm == 2100.0
    for w in ("win1", "win2"):
        r = run(w, plan, outlines, d)
        assert r.status is ABST and r.reason_codes == (shadow.BASE_NOT_ON_FFL,)   # head on datum, sill above FFL


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("plan_shift", [0.0, 123.4, -500.0])
def test_mirror_scale_and_translation_metamorphic(sign, scale, plan_shift):
    plan, outlines, d = make_scene(sign=sign, scale=scale, plan_shift=plan_shift)
    r = run("entry", plan, outlines, d)
    assert r.status is CAND, r.reason_codes
    assert r.opening_height_mm == 2100.0 and r.head_level_name == "JOINERY"


def test_input_order_invariance_and_stable_ids():
    plan, outlines, d = make_scene()
    ref = run("entry", plan, outlines, d)
    for seed in range(8):
        rng = random.Random(seed)
        p, o = list(plan), list(outlines)
        rng.shuffle(p), rng.shuffle(o)
        other = run("entry", p, o, d)
        assert other == ref and other.result_id == ref.result_id


def test_unrelated_content_and_viewport_expansion_do_not_change_the_result():
    plan, outlines, d = make_scene()
    ref = run("entry", plan, outlines, d)
    rng = random.Random(3)
    extra_plan = [PlanSpan(f"far{i}", 5000 + i * 90 + rng.uniform(0, 3), 5000 + i * 90 + 17.3 + rng.uniform(0, 3)) for i in range(60)]
    extra_out = [ElevOutline(f"farout{i}", 9000 + i * 70, 9000 + i * 70 + 21.1, 100.0, 140.0) for i in range(60)]
    # a far outline with exactly the same width as a real one must not create a rival registration
    extra_out.append(ElevOutline("twin", 4000.0, 4034.02, 100.0, 140.0))
    other = run("entry", plan + extra_plan, outlines + extra_out, d)
    assert (other.status, other.outline_id, other.opening_height_mm) == (ref.status, ref.outline_id, ref.opening_height_mm)


def test_deterministic_replay_and_no_mutation():
    plan, outlines, d = make_scene()
    snap = copy.deepcopy((plan, outlines, d))
    first, second = run("entry", plan, outlines, d), run("entry", plan, outlines, d)
    assert first == second and first.result_id == second.result_id
    assert (plan, outlines, d) == snap
    other_record = run("garage", plan, outlines, d)
    assert other_record.result_id != first.result_id                          # ids are content-derived


# ------------------------------------------------------------------------------ negatives

def test_duplicate_physical_candidate_holds_both_with_no_winner():
    plan, outlines, d = make_scene(extra_plan=[PlanSpan("entry_dup", 300.29, 334.31)])
    a, b = run("entry", plan, outlines, d), run("entry_dup", plan, outlines, d)
    for r, other in ((a, "entry_dup"), (b, "entry")):
        assert r.status is CONF and r.reason_codes == (shadow.MULTIPLE_PLAN_RECORDS,)
        assert r.competing_plan_record_ids == (other,)
        assert r.opening_height_mm is None


def test_nested_frame_record_of_a_different_width_is_not_silently_merged():
    plan, outlines, d = make_scene(extra_plan=[PlanSpan("entry_frame", 299.44, 335.15)])
    assert run("entry", plan, outlines, d).status is CAND
    frame = run("entry_frame", plan, outlines, d)
    assert frame.status is ABST and frame.reason_codes == (shadow.NO_OUTLINE,)


def test_interior_doorway_has_no_outline_and_never_borrows_one():
    interior = PlanSpan("interior", 150.0, 174.66)                   # 24.66 wide, no drawn outline anywhere
    behind = PlanSpan("behind_garage_door", 380.0, 406.36)           # projects behind the garage door, different width
    plan, outlines, d = make_scene(extra_plan=[interior, behind])
    for rid in ("interior", "behind_garage_door"):
        r = run(rid, plan, outlines, d)
        assert r.status is ABST and r.reason_codes == (shadow.NO_OUTLINE,) and r.opening_height_mm is None


def test_wrong_elevation_does_not_witness_this_door():
    plan, outlines, d = make_scene()
    other_view = [ElevOutline("x1", 50.0, 70.0, d.levels[0].y, d.ffl_y), ElevOutline("x2", 120.0, 190.0, d.levels[0].y, d.ffl_y)]
    r = run("entry", plan, other_view, d)
    assert r.status is ABST and r.reason_codes == (shadow.REGISTRATION_INSUFFICIENT,)


def test_single_anchor_scene_is_not_a_registration():
    plan, outlines, d = make_scene()
    r = run("entry", plan, outlines[:1], d)
    assert r.status is ABST and r.reason_codes == (shadow.REGISTRATION_INSUFFICIENT,)


def test_symmetric_scene_is_an_ambiguous_registration():
    plan = [PlanSpan("a", 100.0, 134.0), PlanSpan("b", 192.68, 241.32), PlanSpan("c", 300.0, 334.0)]
    d = make_datum()
    out = [ElevOutline("o" + n, x0 + 500.0, x1 + 500.0, d.levels[0].y, d.ffl_y) for n, (x0, x1) in (("a", (100, 134)), ("b", (192.68, 241.32)), ("c", (300, 334)))]
    reg, why = register_plan_to_elevation(plan, out)
    assert reg is None and why == shadow.REGISTRATION_AMBIGUOUS
    r = run("a", plan, out, d)
    assert r.status is CONF and r.reason_codes == (shadow.REGISTRATION_AMBIGUOUS,)


@pytest.mark.parametrize("field", ["document_id", "revision_id", "source_sha256", "snapshot_id"])
def test_foreign_or_stale_elevation_scope_abstains(field):
    plan, outlines, d = make_scene()
    foreign = Scope(**{**SCOPE.__dict__, field: "other"})
    r = run("entry", plan, outlines, d, elevation_scope=foreign)
    assert r.status is ABST and r.reason_codes == (shadow.FOREIGN_SCOPE,)


def test_competing_explicit_height_on_the_outline_conflicts():
    plan, outlines, d = make_scene()

    def with_explicit(height):
        return [ElevOutline(o.outline_id, o.x0, o.x1, o.y_head, o.y_base_leaf, o.y_base_frame, height)
                if o.outline_id == "o_entry" else o for o in outlines]

    r = run("entry", plan, with_explicit(2400.0), d)
    assert r.status is CONF and r.reason_codes == (shadow.COMPETING_HEIGHTS,) and r.opening_height_mm is None
    assert run("entry", plan, with_explicit(2100.0), d).status is CAND     # an agreeing stated height is not a conflict


def test_two_outlines_at_the_registered_interval_conflict():
    plan, outlines, d = make_scene()
    twin = ElevOutline("o_twin", outlines[0].x0, outlines[0].x1, d.levels[0].y, d.ffl_y)
    r = run(outlines[0].outline_id[2:], plan, outlines + [twin], d)
    assert r.status is CONF and r.reason_codes == (shadow.COMPETING_OUTLINES,)


def test_head_off_datum_and_base_off_ffl_abstain():
    plan, outlines, d = make_scene()
    bad_head = [ElevOutline(o.outline_id, o.x0, o.x1, o.y_head + (1.0 if o.outline_id == "o_entry" else 0.0), o.y_base_leaf, o.y_base_frame)
                for o in outlines]
    assert run("entry", plan, bad_head, d).reason_codes == (shadow.HEAD_NOT_ON_DATUM,)
    bad_base = [ElevOutline(o.outline_id, o.x0, o.x1, o.y_head, o.y_base_leaf, None) if o.outline_id == "o_entry" else o for o in outlines]
    r = run("entry", plan, bad_base, d)
    assert r.status is ABST and r.reason_codes == (shadow.BASE_NOT_ON_FFL,)


def test_datum_that_does_not_self_calibrate_abstains():
    plan, outlines, _ = make_scene()
    bad = make_datum(joinery_mm=2400.0)                           # printed value contradicts the drawn spacing
    assert calibrate_datum(bad) is None
    r = run("entry", plan, outlines, bad)
    assert r.status is ABST and r.reason_codes == (shadow.DATUM_SCALE_INCONSISTENT,)
    empty = ElevationDatum(FFL, ())
    assert run("entry", plan, outlines, empty).reason_codes == (shadow.DATUM_UNAVAILABLE,)


def test_scale_calibration_uses_only_the_printed_chain():
    assert calibrate_datum(make_datum()) == pytest.approx(MM, rel=1e-3)
    assert calibrate_datum(make_datum(scale=2.0)) == pytest.approx(MM / 2.0, rel=1e-3)


# ------------------------------------------------------------------ default-off / isolation

def test_adapter_is_default_off_and_strictly_boolean():
    sentinel = object()
    assert assess_elevation_vertical_witness_shadow(sentinel) == ()
    assert assess_elevation_vertical_witness_shadow(sentinel, enabled=False) == ()
    for bad in (1, "yes", None, 0):
        with pytest.raises(TypeError):
            assess_elevation_vertical_witness_shadow(sentinel, enabled=bad)
    plan, outlines, d = make_scene()
    rows = assess_elevation_vertical_witness_shadow(
        [{"plan": plan, "outlines": outlines, "datum": d, "plan_scope": SCOPE, "elevation_scope": SCOPE}], enabled=True)
    assert {r.record_id for r in rows} == set(PLAN) and any(r.is_candidate for r in rows)


def test_module_carries_no_project_or_id_special_cases():
    text = Path(shadow.__file__).read_text(encoding="utf-8").lower()
    for token in ("3laurel", "lot16", "maryborough", "22e7e155", "a93486dc", "reference_takeoff", "boq"):
        assert token not in text, token


# ------------------------------------------------------------------ extractor (pure, synthetic drawing)
from tools.diag_elevation_door_vertical_witness_shadow import extract_views   # noqa: E402


def synthetic_page(*, bad_figure=False):
    lines, rects, words = [], [], []
    base = 300.0
    for x, mm in ((100.0, 2740.0), (120.0, 2700.0), (140.0, 2100.0)):
        top = base - mm / MM
        lines += [(x, top, x, base), (x - 6, top, x + 6, top), (x - 6, base, x + 6, base)]
        shown = "2,400" if (bad_figure and mm == 2100.0) else f"{int(mm):,}"
        words.append((x + 2, (top + base) / 2 - 10, x + 10, (top + base) / 2 + 10, shown))
    head = base - 2100.0 / MM
    # nested door: frame parts (same fill, touching) around an inner leaf rect, plus a window
    frame = (0.6, 0.6, 0.6)
    rects += [(198.4, head - 0.85, 235.6, head, frame), (198.4, head, 199.9, base, frame), (234.1, head, 235.6, base, frame)]
    leaf = (0.3, 0.3, 0.3)
    rects += [(196.9, head - 8.0, 237.1, base, (0.7, 0.7, 0.7))]            # one grey surround rect, as drawn on a real sheet
    rects += [(200.0, head, 234.0, base - 2.26, leaf)]
    rects += [(300.0, head, 349.0, base - 20.0, (0.4, 0.4, 0.4))]
    return lines, rects, words


def test_extractor_reads_the_figured_chain_and_keeps_nested_frame_and_leaf_apart():
    views = extract_views(*synthetic_page())
    assert len(views) == 1
    view = views[0]
    assert [lv.figured_mm for lv in view["datum"].levels] == [2740.0, 2700.0, 2100.0]
    assert calibrate_datum(view["datum"]) == pytest.approx(MM, rel=1e-3)
    spans = {(round(o.x0, 1), round(o.x1, 1)): o for o in view["outlines"]}
    assert (200.0, 234.0) in spans                                        # the inner leaf is its own outline
    assert any(abs(o.x0 - 198.4) < 0.01 and abs(o.x1 - 235.6) < 0.01 for o in view["outlines"])   # and the frame is another
    assert spans[(200.0, 234.0)].y_base_frame == pytest.approx(300.0)     # frame base found for the leaf
    assert (300.0, 349.0) in spans                                        # a window is still an outline


def test_extracted_view_gives_a_witness_for_the_leaf_and_not_for_the_frame_record():
    view = extract_views(*synthetic_page())[0]
    plan = [PlanSpan("leaf_rec", 100.0, 134.0), PlanSpan("frame_rec", 98.4, 135.6), PlanSpan("win", 200.0, 249.0)]
    # elevation x = plan a + 100 (sign +1)
    leaf = run("leaf_rec", plan, view["outlines"], view["datum"])
    assert leaf.status is CAND and leaf.opening_height_mm == 2100.0 and leaf.leaf_height_mm != leaf.opening_height_mm
    frame = run("frame_rec", plan, view["outlines"], view["datum"])
    assert frame.status is ABST and frame.reason_codes == (shadow.HEAD_NOT_ON_DATUM,)   # frame head is above the datum


def test_a_contaminated_chain_is_extracted_but_never_calibrates():
    view = extract_views(*synthetic_page(bad_figure=True))[0]
    assert calibrate_datum(view["datum"]) is None
    plan = [PlanSpan("leaf_rec", 100.0, 134.0), PlanSpan("win", 200.0, 249.0)]
    assert run("leaf_rec", plan, view["outlines"], view["datum"]).reason_codes == (shadow.DATUM_SCALE_INCONSISTENT,)


def test_extractor_ignores_text_and_ticks_that_do_not_form_a_chain():
    lines, rects, words = synthetic_page()
    assert extract_views([], rects, words) == []                        # no dimension lines
    assert extract_views(lines, rects, []) == []                        # no figured values
    assert extract_views(lines[:3], rects, words) == []                 # one dimension is not a chain


# ------------------------------------------------------------------ original source (private PDF, skipped when absent)
import hashlib   # noqa: E402
import os        # noqa: E402

ORIGINAL_SHA256 = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"


def _original_pdf():
    for candidate in (os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF"),
                      "documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def test_original_source_witness_is_read_only_unique_and_keeps_interior_doors_out():
    pdf = _original_pdf()
    if pdf is None:
        pytest.skip("private original PDF not available")
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        pytest.skip("original PDF hash differs")
    from tools.diag_elevation_door_vertical_witness_shadow import run as run_tool

    report = run_tool(pdf, 3, [4, 5], ORIGINAL_SHA256, focus=("22e7e155", "1cd959cc", "be1e67bf", "9d4dc1b3", "a93486dc"))
    assert report["shadow_only"] is True and report["benchmark_score_granted"] is False
    registered = [v for v in report["views"] if v.get("registered_axes")]
    assert len(registered) >= 2
    assert all(len(v["registered_axes"]) == 1 for v in registered)          # never two competing axes
    candidates = {c["record"]: c for c in report["candidates"]}
    assert {"22e7e155", "a93486dc"} <= set(candidates)
    for record in ("22e7e155", "a93486dc"):
        assert candidates[record]["opening_height_mm"] == 2100.0
    assert candidates["22e7e155"]["leaf_height_mm"] != candidates["22e7e155"]["opening_height_mm"]   # leaf is separate
    assert not {"be1e67bf", "9d4dc1b3", "1cd959cc"} & set(candidates)       # interior doors and the frame record: no witness
    focus = {(r["record"], r["status"]) for r in report["focus_rows"] if r["record"] in ("1cd959cc", "be1e67bf", "9d4dc1b3")}
    assert all(status != "candidate" for _, status in focus)


# ------------------------------------------------------------------ MAX review 6732228656: defects 1 to 3
NAN, INF = float("nan"), float("inf")


@pytest.mark.parametrize("bad", [NAN, INF, -INF, True, "2100", None])
def test_datum_fails_closed_on_non_finite_or_non_numeric_values(bad):
    good = make_datum()
    for broken in (
        ElevationDatum(bad, good.levels),
        ElevationDatum(good.ffl_y, (DatumLevel("J", bad, 2100.0),) + good.levels[1:]),
        ElevationDatum(good.ffl_y, (DatumLevel("J", good.levels[0].y, bad),) + good.levels[1:]),
    ):
        assert calibrate_datum(broken) is None
        plan, outlines, _ = make_scene()
        r = run("entry", plan, outlines, broken)
        assert r.status is ABST and r.reason_codes in ((shadow.DATUM_SCALE_INCONSISTENT,), (shadow.DATUM_UNAVAILABLE,))
        assert r.opening_height_mm is None


def test_zero_or_negative_spacing_and_value_fail_closed():
    good = make_datum()
    assert calibrate_datum(ElevationDatum(FFL, (DatumLevel("J", FFL, 2100.0),))) is None            # zero spacing
    assert calibrate_datum(ElevationDatum(FFL, (DatumLevel("J", FFL + 5.0, 2100.0),))) is None       # head below FFL
    assert calibrate_datum(ElevationDatum(FFL, (DatumLevel("J", good.levels[0].y, 0.0),))) is None   # zero value
    assert calibrate_datum(ElevationDatum(FFL, (DatumLevel("J", good.levels[0].y, -2100.0),))) is None


@pytest.mark.parametrize("mutate", ["plan_nan", "plan_inverted", "outline_nan", "outline_inverted", "head_below_base",
                                    "frame_inf", "explicit_nan", "explicit_zero", "empty_id"])
def test_invalid_plan_or_outline_geometry_abstains_before_any_selection(mutate):
    plan, outlines, d = make_scene()
    o = outlines[0]
    if mutate == "plan_nan":
        plan[0] = PlanSpan(plan[0].record_id, NAN, plan[0].a1)
    elif mutate == "plan_inverted":
        plan[0] = PlanSpan(plan[0].record_id, plan[0].a1, plan[0].a0)
    elif mutate == "outline_nan":
        outlines[0] = ElevOutline(o.outline_id, NAN, o.x1, o.y_head, o.y_base_leaf, o.y_base_frame)
    elif mutate == "outline_inverted":
        outlines[0] = ElevOutline(o.outline_id, o.x1, o.x0, o.y_head, o.y_base_leaf, o.y_base_frame)
    elif mutate == "head_below_base":
        outlines[0] = ElevOutline(o.outline_id, o.x0, o.x1, o.y_base_leaf + 1.0, o.y_base_leaf, o.y_base_frame)
    elif mutate == "frame_inf":
        outlines[0] = ElevOutline(o.outline_id, o.x0, o.x1, o.y_head, o.y_base_leaf, INF)
    elif mutate == "explicit_nan":
        outlines[0] = ElevOutline(o.outline_id, o.x0, o.x1, o.y_head, o.y_base_leaf, o.y_base_frame, NAN)
    elif mutate == "explicit_zero":
        outlines[0] = ElevOutline(o.outline_id, o.x0, o.x1, o.y_head, o.y_base_leaf, o.y_base_frame, 0.0)
    else:
        plan[0] = PlanSpan("", plan[0].a0, plan[0].a1)
    r = run("entry", plan, outlines, d)
    assert r.status is ABST and r.reason_codes == (shadow.INVALID_INPUT,) and r.opening_height_mm is None
    assert register_plan_to_elevation(plan, outlines) == (None, shadow.INVALID_INPUT)


def test_duplicate_record_or_outline_identity_conflicts_instead_of_silently_picking_one():
    plan, outlines, d = make_scene()
    dup_plan = plan + [PlanSpan("entry", 700.0, 733.0)]          # same record_id, DIFFERENT geometry
    r = run("entry", dup_plan, outlines, d)
    assert r.status is CONF and r.reason_codes == (shadow.DUPLICATE_IDENTITY,) and r.opening_height_mm is None
    assert run("entry", list(reversed(dup_plan)), outlines, d) == r                      # order cannot choose either
    dup_out = outlines + [ElevOutline(outlines[0].outline_id, 5.0, 25.0, d.levels[0].y, d.ffl_y)]
    r2 = run("entry", plan, dup_out, d)
    assert r2.status is CONF and r2.reason_codes == (shadow.DUPLICATE_IDENTITY,)
    assert register_plan_to_elevation(dup_plan, outlines) == (None, shadow.DUPLICATE_IDENTITY)


# ---- cross-view gate (defect 3)
def _view(plan, outlines, datum, scope=SCOPE):
    return {"plan": plan, "outlines": outlines, "datum": datum, "plan_scope": SCOPE, "elevation_scope": scope}


def test_cross_view_competing_candidates_conflict_and_cannot_be_cherry_picked():
    plan, outlines, d = make_scene()
    d2 = ElevationDatum(d.ffl_y, (DatumLevel("HEAD", d.ffl_y - 2400.0 / MM, 2400.0),))   # a second view with another printed head
    out2 = [ElevOutline(o.outline_id + "b", o.x0, o.x1, d2.levels[0].y, o.y_base_leaf, o.y_base_frame) for o in outlines]
    rows = assess_elevation_vertical_witness_shadow([_view(plan, outlines, d), _view(plan, out2, d2)], enabled=True)
    by = {r.record_id: r for r in rows}
    assert len(rows) == len(PLAN)                                  # one result per record, not per view
    assert by["entry"].status is CONF and by["entry"].reason_codes == (shadow.COMPETING_VIEWS,)
    assert by["entry"].opening_height_mm is None
    assert by["garage"].status is CONF                             # seen by both views as well
    swapped = assess_elevation_vertical_witness_shadow([_view(plan, out2, d2), _view(plan, outlines, d)], enabled=True)
    assert swapped == rows                                         # view order cannot choose


def test_cross_view_one_candidate_with_a_blind_or_empty_other_view_stays_a_candidate():
    plan, outlines, d = make_scene()
    elsewhere = [ElevOutline("x1", 5000.0, 5020.0, d.levels[0].y, d.ffl_y), ElevOutline("x2", 5100.0, 5170.0, d.levels[0].y, d.ffl_y)]
    broken_datum = make_datum(joinery_mm=2400.0)                  # a view-level failure says nothing about the record
    foreign = Scope("doc", "other", "a" * 64, "snap")
    for second in (_view(plan, elsewhere, d), _view(plan, outlines, broken_datum), _view(plan, outlines, d, foreign)):
        rows = {r.record_id: r for r in assess_elevation_vertical_witness_shadow([_view(plan, outlines, d), second], enabled=True)}
        assert rows["entry"].is_candidate and rows["entry"].opening_height_mm == 2100.0, rows["entry"].reason_codes


def test_cross_view_candidate_plus_record_level_conflict_elsewhere_conflicts():
    plan, outlines, d = make_scene()
    twin = [outlines[0], ElevOutline("o_twin", outlines[0].x0, outlines[0].x1, d.levels[0].y, d.ffl_y)] + list(outlines[1:])
    rows = {r.record_id: r for r in assess_elevation_vertical_witness_shadow([_view(plan, outlines, d), _view(plan, twin, d)], enabled=True)}
    assert rows["entry"].status is CONF and rows["entry"].reason_codes == (shadow.COMPETING_VIEWS,)


def test_cross_view_all_abstain_reports_the_most_specific_gate_deterministically():
    plan, outlines, d = make_scene()
    bad_head = [ElevOutline(o.outline_id, o.x0, o.x1, o.y_head + 1.0, o.y_base_leaf, o.y_base_frame) for o in outlines]
    rows = assess_elevation_vertical_witness_shadow([_view(plan, bad_head, d), _view(plan, [], d)], enabled=True)
    entry = {r.record_id: r for r in rows}["entry"]
    assert entry.status is ABST and entry.reason_codes == (shadow.HEAD_NOT_ON_DATUM,)
    assert assess_elevation_vertical_witness_shadow([_view(plan, [], d), _view(plan, bad_head, d)], enabled=True) == rows


def test_overflowing_ratio_cannot_slip_past_the_scale_tolerance():
    # tiny but non-zero spacing with a huge finite printed value: ratio overflows to infinity, and inf/inf is NaN,
    # which compares False against any tolerance. The mean must be rejected explicitly.
    huge = ElevationDatum(FFL, (DatumLevel("J", FFL - 1e-13, 1e300),))
    assert calibrate_datum(huge) is None
    plan, outlines, _ = make_scene()
    assert run("entry", plan, outlines, huge).reason_codes == (shadow.DATUM_SCALE_INCONSISTENT,)


def test_cross_view_view_level_conflicts_do_not_poison_a_clean_candidate():
    plan, outlines, d = make_scene()
    # a second view whose registration is ambiguous (symmetric scene) and which contains the same record id
    sym_plan = [PlanSpan("entry", 100.0, 134.0), PlanSpan("b", 192.68, 241.32), PlanSpan("c", 300.0, 334.0)]
    sym_out = [ElevOutline("s" + n, x0 + 500.0, x1 + 500.0, d.levels[0].y, d.ffl_y)
               for n, (x0, x1) in (("a", (100, 134)), ("b", (192.68, 241.32)), ("c", (300, 334)))]
    assert run("entry", sym_plan, sym_out, d).reason_codes == (shadow.REGISTRATION_AMBIGUOUS,)   # view-level conflict
    # and a view with a repeated identity (also a view-level conflict)
    dup_plan = plan + [PlanSpan("entry", 700.0, 733.0)]
    assert run("entry", dup_plan, outlines, d).reason_codes == (shadow.DUPLICATE_IDENTITY,)
    for second in (_view(sym_plan, sym_out, d), _view(dup_plan, outlines, d)):
        rows = {r.record_id: r for r in assess_elevation_vertical_witness_shadow([_view(plan, outlines, d), second], enabled=True)}
        assert rows["entry"].is_candidate and rows["entry"].opening_height_mm == 2100.0, rows["entry"].reason_codes


# ------------------------------------------------------------------ source-owned adapter (receipts)
import fitz   # noqa: E402

import pb_elevation_source_owned_witness_adapter as adapter   # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer   # noqa: E402


def test_only_the_adapter_and_tools_may_import_the_shadow_and_nothing_imports_the_adapter():
    root = Path(__file__).resolve().parents[1]
    importers = sorted(p.name for p in root.glob("*.py")
                       if p.name != "pb_elevation_door_vertical_witness_shadow.py"
                       and "pb_elevation_door_vertical_witness_shadow" in p.read_text(encoding="utf-8", errors="ignore"))
    assert importers == ["pb_elevation_source_owned_witness_adapter.py"]
    adapter_importers = [p.name for p in root.glob("*.py")
                         if p.name != "pb_elevation_source_owned_witness_adapter.py"
                         and "pb_elevation_source_owned_witness_adapter" in p.read_text(encoding="utf-8", errors="ignore")]
    assert adapter_importers == []


def test_receipts_flow_from_drawn_facts_to_the_witness_result():
    lines, rects, words = synthetic_page()
    lines = [(*l, f"line{i}") for i, l in enumerate(lines)]
    rects = [(*r, (f"rect{i}a", f"rect{i}b")) for i, r in enumerate(rects)]
    words = [(*w, f"word{i}") for i, w in enumerate(words)]
    view = adapter.extract_views(lines, rects, words)[0]
    assert view["datum"].receipt_ids and all(lv.receipt_ids for lv in view["datum"].levels)
    assert any(i.startswith("word") for lv in view["datum"].levels for i in lv.receipt_ids)     # the printed figure is a receipt
    leaf = [o for o in view["outlines"] if abs(o.x0 - 200.0) < 0.01 and abs(o.x1 - 234.0) < 0.01][0]
    assert leaf.receipt_ids and all(i.startswith("rect") for i in leaf.receipt_ids)
    plan = [PlanSpan("leaf_rec", 100.0, 134.0), PlanSpan("frame_rec", 98.4, 135.6), PlanSpan("win", 200.0, 249.0)]
    result = run("leaf_rec", plan, view["outlines"], view["datum"])
    assert result.is_candidate and result.source_observation_ids
    assert set(result.source_observation_ids) >= set(leaf.receipt_ids) | set(view["datum"].receipt_ids)
    assert any(i.startswith("word") for i in result.source_observation_ids)
    assert run("frame_rec", plan, view["outlines"], view["datum"]).source_observation_ids == ()   # no receipts for a non-candidate


def _synthetic_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    base = 300.0
    for x, mm in ((100.0, 2740.0), (120.0, 2700.0), (140.0, 2100.0)):
        top = base - mm / MM
        page.draw_line((x, top), (x, base), color=(0, 0, 0), width=0.4)
        page.draw_line((x - 6, top), (x + 6, top), color=(0, 0, 0), width=0.4)
        page.draw_line((x - 6, base), (x + 6, base), color=(0, 0, 0), width=0.4)
        page.insert_text((x + 9, (top + base) / 2 + 8), f"{int(mm):,}", fontsize=7, rotate=90)
    head = base - 2100.0 / MM
    # CAD exports draw a filled rectangle as a closed line path, not as an `re` operator; do the same here
    def fill_rect(x0, y0, x1, y1, fill):
        page.draw_polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], color=None, fill=fill, closePath=True)

    fill_rect(196.9, head - 8.0, 237.1, base, (0.7, 0.7, 0.7))
    fill_rect(200.0, head, 234.0, base - 2.26, (0.3, 0.3, 0.3))
    fill_rect(300.0, head, 349.0, base - 20.0, (0.4, 0.4, 0.4))
    return doc.tobytes()


def test_synthetic_pdf_through_the_real_producers_gives_source_owned_views_with_receipts():
    payload = _synthetic_pdf()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = __import__("hashlib").sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://synthetic.pdf", page_ids=(1,))
    page = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    assert page is not None and page.scope.source_sha256 == sha and page.scope.revision_id == initial.revision.revision_id
    assert page.lines and page.rects and page.words
    assert all(r[5] for r in page.rects)                        # every rect names the observations that draw it
    views = adapter.source_owned_views(page)
    assert len(views) == 1
    view = views[0]
    assert [lv.figured_mm for lv in view["datum"].levels] == [2740.0, 2700.0, 2100.0]
    assert calibrate_datum(view["datum"]) == pytest.approx(MM, rel=2e-2)
    leaf = [o for o in view["outlines"] if abs(o.x0 - 200.0) < 0.1 and abs(o.x1 - 234.0) < 0.1]
    assert leaf and leaf[0].receipt_ids and leaf[0].y_base_frame == pytest.approx(300.0, abs=0.1)
    # a foreign revision refuses the whole page: no facts without an intact lineage
    assert adapter.read_source_owned_page(source, revision_id="source_revision_foreign", page_id="1") is None


def test_page_filter_never_mixes_facts_from_another_page():
    doc = fitz.open(stream=_synthetic_pdf(), filetype="pdf")
    page2 = doc.new_page(width=600, height=400)
    page2.draw_line((50.0, 100.0), (50.0, 300.0), color=(0, 0, 0), width=0.4)
    page2.insert_text((60, 200), "3,000", fontsize=7, rotate=90)
    page2.draw_polyline([(400.0, 150.0), (440.0, 150.0), (440.0, 250.0), (400.0, 250.0), (400.0, 150.0)],
                        color=None, fill=(0.2, 0.2, 0.2), closePath=True)
    payload = doc.tobytes()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = __import__("hashlib").sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://two.pdf", page_ids=(1, 2))
    one = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    two = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="2")
    assert "3,000" not in {w[4] for w in one.words} and "3,000" in {w[4] for w in two.words}
    assert not any(abs(r[0] - 400.0) < 0.1 for r in one.rects) and any(abs(r[0] - 400.0) < 0.1 for r in two.rects)
    assert {l[4] for l in one.lines}.isdisjoint({l[4] for l in two.lines})         # no shared observation ids
    assert len(adapter.source_owned_views(one)) == 1 and adapter.source_owned_views(two) == []


def test_original_source_owned_path_reproduces_the_diagnostic_result_and_names_its_receipts():
    pdf = _original_pdf()
    if pdf is None:
        pytest.skip("private original PDF not available")
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        pytest.skip("original PDF hash differs")
    from tools.diag_elevation_door_vertical_witness_shadow import run as run_tool

    focus = ("22e7e155", "1cd959cc", "be1e67bf", "9d4dc1b3", "a93486dc")
    owned = run_tool(pdf, 3, [4, 5], ORIGINAL_SHA256, focus=focus, source_owned=True)
    diagnostic = run_tool(pdf, 3, [4, 5], ORIGINAL_SHA256, focus=focus, source_owned=False)
    assert owned["input_path"] == "source_owned" and diagnostic["input_path"] == "pymupdf_diagnostic"
    assert [c["record"] for c in owned["candidates"]] == [c["record"] for c in diagnostic["candidates"]] == ["22e7e155", "a93486dc"]
    assert all(c["receipt_count"] > 0 and c["opening_height_mm"] == 2100.0 for c in owned["candidates"])
    assert all(c["text_trust"] in ("corroborated", "raw_unverified_diagnostic_only") for c in owned["candidates"])   # trust is always stated
    assert all(c["text_trust"] == "" for c in diagnostic["candidates"])        # the PyMuPDF path claims no text trust
    assert all(c["leaf_height_mm"] != c["opening_height_mm"] for c in owned["candidates"] if c["record"] == "22e7e155")
    offsets = lambda r: sorted((v["page"], v["view"], v.get("offset")) for v in r["views"] if v.get("registered_axes"))
    assert offsets(owned) == offsets(diagnostic)                          # the same unique registrations
    held = {(r["record"], r["status"]) for r in owned["focus_rows"] if r["record"] in ("1cd959cc", "be1e67bf", "9d4dc1b3")}
    assert all(status != "candidate" for _, status in held)               # frame record and interior doors still out


def test_enclosing_frame_receipts_are_part_of_the_leaf_outline_receipts():
    lines, rects, words = synthetic_page()
    rects = [(*r, (f"rect{i}a", f"rect{i}b")) for i, r in enumerate(rects)]
    view = adapter.extract_views(lines, rects, words)[0]
    leaf = [o for o in view["outlines"] if abs(o.x0 - 200.0) < 0.01 and abs(o.x1 - 234.0) < 0.01][0]
    assert leaf.y_base_frame == pytest.approx(300.0)
    surround_index = next(i for i, r in enumerate(rects) if abs(r[0] - 196.9) < 0.01)
    assert {f"rect{surround_index}a", f"rect{surround_index}b"} <= set(leaf.receipt_ids)       # the frame that gives its base


def test_an_ambiguous_figure_beside_a_dimension_line_is_not_read():
    lines, rects, words = synthetic_page()
    x = 140.0
    top = 300.0 - 2100.0 / MM
    extra = (x + 2, (top + 300.0) / 2 - 10, x + 10, (top + 300.0) / 2 + 10, "2,000")      # a second figure on the same dimension
    view = adapter.extract_views(lines, rects, words + [extra])[0]
    assert [lv.figured_mm for lv in view["datum"].levels] == [2740.0, 2700.0]               # the ambiguous dimension is dropped


def _two_view_source(payload: bytes):
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = __import__("hashlib").sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://s.pdf", page_ids=(1,))
    return source, initial.revision.revision_id


def test_a_diagonal_fill_path_is_not_an_axis_aligned_outline():
    doc = fitz.open(stream=_synthetic_pdf(), filetype="pdf")
    page = doc[0]
    page.draw_polyline([(400.0, 150.0), (450.0, 150.0), (470.0, 250.0), (420.0, 250.0), (400.0, 150.0)],
                       color=None, fill=(0.2, 0.2, 0.2), closePath=True)      # skewed quad: diagonal edges
    source, revision_id = _two_view_source(doc.tobytes())
    page_facts = adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")
    assert not any(abs(r[0] - 400.0) < 0.1 for r in page_facts.rects)
    assert any(abs(r[0] - 200.0) < 0.1 for r in page_facts.rects)                 # the real leaf is still there


def test_a_path_whose_edges_disagree_on_fill_is_not_a_single_outline():
    import dataclasses

    source, revision_id = _two_view_source(_synthetic_pdf())
    real = source.native_paint_facts

    def mixed(selector, *, observation_ids):
        facts = list(real(selector, observation_ids=observation_ids))
        leaf_path = next(f.path_index for f in facts if f.fill is not None and abs(f.geometry[0] - 200.0) < 0.1)
        flipped = False
        for i, f in enumerate(facts):
            if f.path_index == leaf_path and not flipped:
                facts[i] = dataclasses.replace(f, fill=(0.9, 0.9, 0.9))
                flipped = True
        return tuple(facts)

    source.native_paint_facts = mixed
    page = adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")
    assert not any(abs(r[0] - 200.0) < 0.1 and abs(r[2] - 234.0) < 0.1 for r in page.rects)


def test_a_segment_without_a_corroborated_visibility_receipt_is_not_used():
    import types

    source, revision_id = _two_view_source(_synthetic_pdf())
    real_authority = source.authority()
    baseline = adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")
    dropped = {baseline.lines[0][4]}

    class Doubt:
        def __getattr__(self, name):
            return getattr(real_authority, name)

        def resolve_visible(self, selector):
            result = real_authority.resolve_visible(selector)
            if selector.observation_id in dropped:
                return types.SimpleNamespace(status=EvidenceResolutionStatus.ABSTAINED, observation=result.observation)
            return result

    source.authority = lambda: Doubt()
    page = adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")
    assert dropped.isdisjoint({l[4] for l in page.lines})
    assert len(page.lines) == len(baseline.lines) - 1


# ------------------------------------------------------------------ MAX review 6733270532: untrusted text must fail closed
def _words_with_reasons(reasons, *, status=None):
    """Read the synthetic page while the text authority reports every word as untrusted with `reasons`."""
    import dataclasses
    import types

    source, revision_id = _two_view_source(_synthetic_pdf())
    real = source.text_integrity_authority()
    forced = status if status is not None else EvidenceResolutionStatus.ABSTAINED

    class Doubt:
        def __getattr__(self, name):
            return getattr(real, name)

        def resolve_text(self, selector):
            r = real.resolve_text(selector)
            receipt = dataclasses.replace(r.receipt, trusted=False, reason_codes=tuple(reasons))
            return types.SimpleNamespace(status=forced, receipt=receipt, trusted_text=None)

    source.text_integrity_authority = lambda: Doubt()
    return adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")


def test_an_untrusted_word_with_no_stated_reason_is_never_a_datum_word():
    # An empty reason set is a subset of every set; it must not pass the raw fallback.
    page = _words_with_reasons(())
    assert page.words == ()
    assert adapter.source_owned_views(page) == []                       # no figured chain, so no view at all


@pytest.mark.parametrize("reasons", [("something_unknown",), ("text_glyph_mapping_unverified", "something_unknown"),
                                     ("text_clip_state_unresolved", "text_glyph_mapping_unverified", "other")])
def test_unknown_or_mixed_reasons_are_not_accepted_as_raw_text(reasons):
    assert _words_with_reasons(reasons).words == ()


@pytest.mark.parametrize("reasons", [("text_glyph_mapping_unverified",), ("text_clip_state_unresolved",),
                                     ("text_glyph_mapping_unverified", "text_clip_state_unresolved")])
def test_only_approved_reasons_give_raw_text_and_it_is_tagged_unverified(reasons):
    page = _words_with_reasons(reasons)
    assert page.words and {w[6] for w in page.words} == {"raw_unverified"}
    views = adapter.source_owned_views(page)
    assert views and all(lv.text_trust == "raw_unverified" for lv in views[0]["datum"].levels)


def test_a_non_abstained_untrusted_word_is_not_raw_fallback():
    page = _words_with_reasons(("text_glyph_mapping_unverified",), status=EvidenceResolutionStatus.CONFLICT)
    assert page.words == ()


def test_real_producer_words_carry_an_explicit_trust_tag():
    source, revision_id = _two_view_source(_synthetic_pdf())
    page = adapter.read_source_owned_page(source, revision_id=revision_id, page_id="1")
    assert page.words and {w[6] for w in page.words} <= {"corroborated", "raw_unverified"}


def _trust_scene(trust_values):
    lines, rects, words = synthetic_page()
    tagged = []
    for i, w in enumerate(words):
        tagged.append((*w, f"word{i}", trust_values[i % len(trust_values)]))
    return adapter.extract_views(lines, rects, tagged)[0], tagged


def test_text_trust_reaches_the_result_and_never_makes_a_candidate_stronger():
    plan = [PlanSpan("leaf_rec", 100.0, 134.0), PlanSpan("frame_rec", 98.4, 135.6), PlanSpan("win", 200.0, 249.0)]
    for trust, expected in ((["corroborated"], "corroborated"), (["corroborated", "raw_unverified"], "raw_unverified_diagnostic_only"),
                            (["raw_unverified"], "raw_unverified_diagnostic_only")):
        view, _ = _trust_scene(trust)
        r = run("leaf_rec", plan, view["outlines"], view["datum"])
        assert r.status is CAND and r.text_trust == expected and r.status is not EvidenceResolutionStatus.CORROBORATED
    # a plain tuple with no trust tag claims nothing
    lines, rects, words = synthetic_page()
    view = adapter.extract_views(lines, rects, words)[0]
    assert run("leaf_rec", plan, view["outlines"], view["datum"]).text_trust == ""
    assert shadow.datum_text_trust(view["datum"]) == ""


def test_text_trust_is_part_of_the_result_identity():
    plan = [PlanSpan("leaf_rec", 100.0, 134.0), PlanSpan("frame_rec", 98.4, 135.6), PlanSpan("win", 200.0, 249.0)]
    a_view, _ = _trust_scene(["corroborated"])
    b_view, _ = _trust_scene(["raw_unverified"])
    a = run("leaf_rec", plan, a_view["outlines"], a_view["datum"])
    b = run("leaf_rec", plan, b_view["outlines"], b_view["datum"])
    assert a.result_id != b.result_id                                   # a raw-text result can never alias a verified one
