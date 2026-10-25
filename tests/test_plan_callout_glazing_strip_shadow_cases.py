"""Negatives, ambiguity, look-alikes and metamorphic invariants for the callout -> strip shadow."""
from __future__ import annotations

import random

import fitz
import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from plan_callout_strip_fixture import (
    ABST, CAND, CONF, GAP, HEX_H, MM_PER_PT, Sheet, add_window, by_mark, decision, ink_of, run, three_windows, types_of, words_of,
)


def reasons(result, mark):
    return by_mark(result)[mark].reason_codes


# ------------------------------------------------------------------------------------
# the elevation fingerprint and the cross-window consistency
# ------------------------------------------------------------------------------------

def test_panel_count_that_disagrees_with_the_elevation_abstains_and_the_others_stay_candidates():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, elevation_panels=4)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    got = by_mark(run(sheet))
    assert got["W1"].status is ABST and "no_count_matching_strip" in got["W1"].reason_codes
    assert got["W2"].status is CAND and got["W3"].status is CAND


def test_length_that_disagrees_with_the_common_ratio_abstains_for_that_window_only():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0, width_mm=120.0 * MM_PER_PT * 1.25)
    got = by_mark(run(sheet))
    assert got["W1"].status is CAND and got["W2"].status is CAND
    assert got["W3"].status is ABST and "no_scale_consistent_strip" in got["W3"].reason_codes
    assert got["W3"].count_matching_strip_ids and got["W3"].strip_id is None


def test_the_tagged_type_must_have_exactly_one_elevation_record():
    sheet = three_windows()
    result = run(sheet, types=[t for t in types_of(sheet) if t.type_mark != "W2"])
    assert by_mark(result)["W2"].status is ABST and "elevation_type_record_missing" in reasons(result, "W2")
    dup = types_of(sheet) + [shadow.ElevationTypeObservation("W1", "record:other", 3600.0, 3)]
    result = run(sheet, types=dup)
    assert by_mark(result)["W1"].status is CONF and "elevation_type_record_ambiguous" in reasons(result, "W1")
    assert by_mark(result)["W2"].status is CAND and by_mark(result)["W3"].status is CAND


def test_an_unresolved_elevation_width_abstains_with_the_adapters_reason():
    sheet = three_windows()
    types = [t if t.type_mark != "W1" else shadow.ElevationTypeObservation(
        "W1", t.record_id, None, 3, unresolved_reason="frame_axis_ambiguous") for t in types_of(sheet)]
    got = by_mark(run(sheet, types=types))
    assert got["W1"].status is ABST and "frame_axis_ambiguous" in got["W1"].reason_codes


def test_a_single_panel_window_is_never_measurable_even_when_the_length_matches():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=1, length=41.04)
    got = by_mark(run(sheet))
    assert got["W3"].status is ABST and "single_panel_fingerprint_unmeasurable" in got["W3"].reason_codes
    assert got["W1"].status is CAND and got["W2"].status is CAND


def test_strips_one_and_a_half_percent_apart_are_separated_by_the_quantum_tolerance():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W4", panels=3, length=206.88)          # 1.4 percent longer, same panel count
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    got = by_mark(run(sheet))
    assert {m: c.status for m, c in got.items()} == {"W1": CAND, "W3": CAND, "W4": CAND}
    assert got["W1"].strip_id != got["W4"].strip_id
    assert len(got["W1"].count_matching_strip_ids) == 2        # both were retained as rivals
    assert got["W4"].strip_id in got["W1"].rival_strip_ids


def test_two_tags_whose_fingerprints_land_on_one_strip_are_both_conflicts():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W4", panels=3, length=206.88, width_mm=204.0 * MM_PER_PT)    # prints W1's width
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    got = by_mark(run(sheet))
    assert got["W1"].status is CONF and got["W4"].status is CONF
    assert "fingerprint_strip_claimed_by_several_tags" in got["W1"].reason_codes
    assert got["W3"].status is ABST or got["W3"].status is CAND      # decided on its own conditions


def test_two_identical_strips_for_one_tag_are_a_conflict_with_both_retained():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    twin, _ = add_window(sheet, 1, "W9", panels=3, length=204.0, callout=False, elevation=False)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    got = by_mark(run(sheet))
    assert got["W1"].status is CONF and got["W1"].strip_id is None
    assert "several_scale_consistent_strips" in got["W1"].reason_codes
    assert len(got["W1"].scale_consistent_strip_ids) == 2 and len(got["W1"].rival_strip_ids) == 2


def test_a_strip_without_both_end_posts_has_no_measurable_extent():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    s = sheet.strip("H", 440.0, 300.0, panels=3, frame_len=232.0, end_posts=False)
    sheet.callout(((s["frame"][0] + s["frame"][1]) / 2 + 2.0, s["band"][1] + GAP + HEX_H), "W2")
    sheet.elevation_frame("W2", (460.0, 100.0, 580.0, 220.0), 3, 232.0 * MM_PER_PT)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    result = run(sheet)
    incomplete = [s for s in result.strips if not s.extent_complete]
    assert len(incomplete) == 1 and incomplete[0].panel_count == 3
    got = by_mark(result)["W2"]
    assert got.status is ABST and dict(got.numbers)["count_matching_strips_without_complete_extent"] >= 1.0


# ------------------------------------------------------------------------------------
# the location filter can only remove a candidate
# ------------------------------------------------------------------------------------

def _two_with_custom_w1_callout(centre, **callout):
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, callout=False)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    sheet.callout(centre, "W1", **callout)
    return sheet


def test_callout_beyond_the_strip_end_abstains_and_the_fingerprint_strip_is_kept_as_a_rival():
    sheet = _two_with_custom_w1_callout((330.0, 305.52 + GAP + HEX_H))
    got = by_mark(run(sheet))["W1"]
    assert got.status is ABST and "callout_not_at_fingerprint_strip" in got.reason_codes
    assert got.scale_consistent_strip_ids and set(got.scale_consistent_strip_ids) <= set(got.rival_strip_ids)


def test_callout_straddling_the_strip_end_abstains_because_a_vertex_lies_outside_the_extent():
    got = by_mark(run(_two_with_custom_w1_callout((264.0, 305.52 + GAP + HEX_H))))["W1"]
    assert got.status is ABST and "callout_not_at_fingerprint_strip" in got.reason_codes


def test_callout_overlapping_the_strip_band_abstains():
    got = by_mark(run(_two_with_custom_w1_callout((164.0, 302.76))))["W1"]
    assert got.status is ABST and "callout_not_at_fingerprint_strip" in got.reason_codes


def test_the_gap_between_callout_and_strip_is_data_not_a_threshold():
    near = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + 1.0 + HEX_H))))["W1"]
    far = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + 30.0 + HEX_H))))["W1"]
    assert near.status is CAND and far.status is CAND
    assert dict(near.numbers)["callout_normal_gap_pt"] == pytest.approx(1.0, abs=0.05)
    assert dict(far.numbers)["callout_normal_gap_pt"] == pytest.approx(30.0, abs=0.05)


def test_a_ring_missing_one_edge_abstains():
    got = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + GAP + HEX_H), drop_edge=2)))["W1"]
    assert got.status is ABST and "callout_ring_not_found" in got.reason_codes
    assert dict(got.conditions)["callout_ring_unique"] == shadow.FAILED


def test_a_second_ring_around_the_same_word_is_a_conflict_not_a_choice():
    got = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + GAP + HEX_H), extra_ring=True)))["W1"]
    assert got.status is CONF and "callout_ring_not_unique" in got.reason_codes


def test_single_ink_and_double_ink_rings_are_the_same_callout():
    single = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + GAP + HEX_H), ink_twice=False)))["W1"]
    double = by_mark(run(_two_with_custom_w1_callout((164.0, 305.52 + GAP + HEX_H), ink_twice=True)))["W1"]
    assert single.status is CAND and double.status is CAND
    assert len(single.ring.ink_ids) == 6 and len(double.ring.ink_ids) == 12


def test_the_same_tag_printed_twice_on_the_plan_page_is_never_resolved():
    sheet = three_windows()
    sheet.text((700.0, 600.0), "W1")
    got = by_mark(run(sheet))
    assert got["W1"].status is ABST and "tag_not_unique_on_plan_page" in got["W1"].reason_codes
    assert len([c for c in run(sheet).correspondences if c.tag_mark == "W1"]) == 2


# ------------------------------------------------------------------------------------
# exclusivity runs over every callout ring on the page, not over the tags asked about
# ------------------------------------------------------------------------------------

def test_a_door_callout_inside_the_strip_extent_is_a_rival_claimant_and_forces_a_conflict():
    sheet = three_windows()
    sheet.callout((100.0, 305.52 + GAP + HEX_H), "D1")           # same side, same strip extent
    result = run(sheet)
    got = by_mark(result)
    assert got["W1"].status is CONF and "strip_has_other_callout_claimants" in got["W1"].reason_codes
    assert got["D1"].tag_observation_id in got["W1"].rival_callout_ids
    assert got["D1"].status is ABST and "elevation_type_record_missing" in got["D1"].reason_codes
    assert got["W2"].status is CAND and got["W3"].status is CAND


def test_a_claimant_on_the_other_side_of_the_strip_is_still_a_claimant():
    sheet = three_windows()
    sheet.callout((100.0, 300.0 - GAP - HEX_H), "D1")
    assert by_mark(run(sheet))["W1"].status is CONF


def test_every_callout_on_the_page_is_reported_whichever_tags_a_caller_cares_about():
    sheet = three_windows()
    sheet.callout((100.0, 305.52 + GAP + HEX_H), "D1")
    assert sorted(by_mark(run(sheet))) == ["D1", "W1", "W2", "W3"]


# ------------------------------------------------------------------------------------
# viewports
# ------------------------------------------------------------------------------------

def test_a_callout_outside_every_resolved_viewport_abstains():
    result = run(three_windows(), viewports=())
    assert {c.status for c in result.correspondences} == {ABST}
    assert all("callout_outside_resolved_plan_viewport" in c.reason_codes for c in result.correspondences)


def test_a_strip_in_another_viewport_than_its_callout_abstains():
    top = shadow.PlanViewportRef("view_strips", (0.0, 290.0, 1400.0, 307.0))
    bottom = shadow.PlanViewportRef("view_callouts", (0.0, 308.0, 1400.0, 900.0))
    result = run(three_windows(), viewports=(top, bottom))
    assert {c.status for c in result.correspondences} == {ABST}
    assert all("strip_outside_callout_viewport" in c.reason_codes for c in result.correspondences)


def test_expanding_the_viewport_does_not_change_any_decision():
    base = run(three_windows())
    big = shadow.PlanViewportRef("view_plan", (-500.0, -500.0, 9000.0, 9000.0))
    assert decision(run(three_windows(), viewports=(big,))) == decision(base)


def test_overlapping_viewports_leave_the_callout_without_a_unique_viewport():
    a = shadow.PlanViewportRef("a", (0.0, 0.0, 1400.0, 900.0))
    b = shadow.PlanViewportRef("b", (0.0, 0.0, 1400.0, 900.0))
    assert {c.status for c in run(three_windows(), viewports=(a, b)).correspondences} == {ABST}


# ------------------------------------------------------------------------------------
# look-alikes that must never be a glazing strip
# ------------------------------------------------------------------------------------

def test_equally_spaced_parallel_lines_are_not_a_glazing_strip():
    sheet = Sheet()
    for k in range(5):
        sheet.line((200.0, 300.0 + 1.4 * k), (404.0, 300.0 + 1.4 * k))
    assert run(sheet).strips == ()


def test_a_door_leaf_and_swing_arc_is_not_a_strip():
    sheet = Sheet()
    sheet.line((300.0, 300.0), (300.0, 360.0))
    sheet.plan.draw_sector(fitz.Point(300.0, 300.0), fitz.Point(360.0, 300.0), 90, color=(0, 0, 0), width=0.48)
    assert run(sheet).strips == ()


def test_a_wall_of_two_double_inked_faces_without_a_pane_box_is_not_a_strip():
    sheet = Sheet()
    sheet.line((200.0, 300.0), (404.0, 300.0), double=True)
    sheet.line((200.0, 305.52), (404.0, 305.52), double=True)
    assert run(sheet).strips == ()


def test_panes_drawn_in_a_different_line_weight_than_their_frame_are_not_mixed_into_a_strip():
    sheet = Sheet()
    sheet.strip("H", 200.0, 300.0, panels=3, frame_len=204.0, width=0.48, pane_width=0.24)
    assert run(sheet).strips == ()


def test_a_dimension_chain_of_ticks_parallel_to_a_strip_does_not_add_a_strip():
    sheet = three_windows()
    for x in (60.0, 120.0, 180.0, 264.0):
        sheet.line((x, 282.0), (x, 292.0))
    sheet.line((60.0, 287.0), (264.0, 287.0))
    assert len(run(sheet).strips) == len(run(three_windows()).strips) == 3


# ------------------------------------------------------------------------------------
# metamorphic invariants: the decision may not depend on where, how big, or in what order
# ------------------------------------------------------------------------------------

BASE = {"W1": CAND, "W2": CAND, "W3": CAND}


def _shifted(dx, dy):
    sheet = Sheet(size=(1800.0, 1300.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, dx=dx, dy=dy)
    add_window(sheet, 1, "W2", panels=3, length=232.0, dx=dx, dy=dy)
    add_window(sheet, 2, "W3", panels=5, length=120.0, dx=dx, dy=dy)
    return sheet


@pytest.mark.parametrize("dx,dy", [(137.0, 211.0), (137.37, 211.11), (0.003, 0.003), (0.123, 0.0)])
def test_translation_of_the_whole_plan_does_not_change_any_decision(dx, dy):
    reference = decision(run(_shifted(0.0, 0.0)))
    assert {m: v[0] for m, v in reference.items()} == BASE
    assert decision(run(_shifted(dx, dy))) == reference


def test_axis_swap_of_the_plan_gives_the_same_decisions():
    sheet = Sheet(size=(1400.0, 1400.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, axis="V")
    add_window(sheet, 1, "W2", panels=3, length=232.0, axis="V")
    add_window(sheet, 2, "W3", panels=5, length=120.0, axis="V")
    assert decision(run(sheet)) == decision(run(three_windows()))


def test_a_uniform_scale_of_every_elevation_width_gives_the_same_decisions():
    sheet = three_windows()
    assert decision(run(sheet, types=types_of(sheet, width_scale=1.7))) == decision(run(sheet))


def test_unrelated_content_cannot_move_a_decision_even_when_it_outnumbers_the_strokes():
    base = decision(run(three_windows()))
    noisy = three_windows()
    rng = random.Random(7)
    for _ in range(800):
        x, y = rng.uniform(20, 1380), rng.uniform(560, 880)
        noisy.line((x, y), (x + rng.uniform(5, 40), y + rng.uniform(-3, 3)), width=0.1)
    for _ in range(40):
        x, y = rng.uniform(20, 1380), rng.uniform(560, 880)
        noisy.line((x, y), (x + rng.uniform(5, 40), y), width=0.48)
    assert decision(run(noisy)) == base


def test_collinear_splitting_of_every_frame_line_does_not_change_a_decision():
    base = run(three_windows())

    class Splitting(Sheet):
        def line(self, a, b, page=None, double=False, **kw):
            if (abs(a[1] - b[1]) < 1e-9 and abs(a[0] - b[0]) > 6.0) or (abs(a[0] - b[0]) < 1e-9 and abs(b[1] - a[1]) > 6.0):
                mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
                super().line(a, mid, page, double, **kw)
                super().line(mid, b, page, double, **kw)
            else:
                super().line(a, b, page, double, **kw)

    sheet = Splitting(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    result = run(sheet)
    assert decision(result) == decision(base)
    assert [(s.axis, s.panel_count, s.frame_along) for s in result.strips] == \
           [(s.axis, s.panel_count, s.frame_along) for s in base.strips]


def test_input_order_of_ink_words_and_types_does_not_change_a_decision():
    sheet = three_windows()
    pdf = sheet.pdf()
    base = run(sheet)
    reversed_result = run(sheet, ink=list(reversed(ink_of(pdf))), words=list(reversed(words_of(pdf))),
                          types=list(reversed(types_of(sheet))))
    assert decision(reversed_result) == decision(base)
    assert {c.record_id for c in reversed_result.correspondences} == {c.record_id for c in base.correspondences}
    assert [s.strip_id for s in reversed_result.strips] == [s.strip_id for s in base.strips]


def test_a_page_over_the_ink_budget_abstains_for_every_tag_instead_of_raising(monkeypatch):
    monkeypatch.setattr(shadow, "_MAX_INK", 10)
    result = run(three_windows())
    assert result.strips == () and "stroke_budget_exceeded" in result.page_reason_codes
    assert {c.status for c in result.correspondences} == {ABST}
    assert all("stroke_budget_exceeded" in c.reason_codes for c in result.correspondences)


def test_untrusted_plan_text_is_carried_as_a_caveat_on_every_candidate():
    result = run(three_windows(), untrusted_plan_text_count=3)
    assert "callout_universe_limited_to_trusted_text" in result.page_reason_codes
    for c in result.correspondences:
        assert c.status is CAND and "callout_universe_limited_to_trusted_text" in c.reason_codes
