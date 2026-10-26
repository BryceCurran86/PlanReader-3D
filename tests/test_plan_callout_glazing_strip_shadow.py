"""Positive proofs, shadow-only invariants and ownership for the plan callout -> glazing strip shadow."""
from __future__ import annotations

from dataclasses import fields, replace

import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from plan_callout_strip_fixture import (
    ABST, CAND, OWNERSHIP, Sheet, add_window, by_mark, ink_of, run, scope_for, three_windows,
    types_of, words_of,
)


def test_three_consistent_windows_are_candidates_with_every_condition_passed():
    result = run(three_windows())
    got = by_mark(result)
    assert {m: c.status for m, c in got.items()} == {"W1": CAND, "W2": CAND, "W3": CAND}
    for c in got.values():
        assert [name for name, _ in c.conditions] == list(shadow.CONDITION_NAMES)
        assert all(state == shadow.PASSED for _, state in c.conditions)
        assert c.strip_id is not None and c.ring.status is CAND
        assert "source_correspondence_candidate_not_authority" in c.reason_codes
        assert "elevation_viewport_unproven" in c.reason_codes
    strips = {s.strip_id: s for s in result.strips}
    assert strips[got["W1"].strip_id].panel_count == 3 and strips[got["W3"].strip_id].panel_count == 5
    assert abs(strips[got["W1"].strip_id].frame_along[1] - strips[got["W1"].strip_id].frame_along[0] - 204.0) < 0.05
    assert len(got["W1"].ring.ink_ids) == 12          # six edges drawn twice


def test_every_grant_is_false_and_enforced_at_construction():
    result = run(three_windows())
    for f in fields(result):
        if f.name.endswith("_granted") or f.name.endswith("_allowed"):
            assert getattr(result, f.name) is False, f.name
    assert result.shadow_only is True and result.text_trust_verified_by_this_module is False
    for flag in shadow._GRANT_FLAGS:
        with pytest.raises(ValueError, match="grant"):
            replace(result, **{flag: True})
    with pytest.raises(ValueError):
        replace(result, shadow_only=False)
    with pytest.raises(ValueError):
        replace(result, text_trust_verified_by_this_module=True)


def test_a_candidate_cannot_be_built_with_an_unevaluated_condition():
    c = next(iter(by_mark(run(three_windows())).values()))
    broken = tuple((name, shadow.NOT_EVALUATED if i == 4 else state) for i, (name, state) in enumerate(c.conditions))
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(c, conditions=broken)
    with pytest.raises(ValueError, match="CANDIDATE"):
        replace(c, strip_id=None)


def test_a_lone_window_abstains_because_no_cross_window_consistency_exists():
    sheet = Sheet()
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    got = by_mark(run(sheet))["W1"]
    assert got.status is ABST and got.strip_id is None
    assert "fewer_than_two_scale_eligible_tags" in got.reason_codes
    conditions = dict(got.conditions)
    assert conditions["scale_consistent_strip_unique"] == shadow.FAILED
    assert conditions["callout_beside_fingerprint_strip"] == shadow.NOT_EVALUATED


@pytest.mark.parametrize("axis", ["H", "V"])
@pytest.mark.parametrize("side", [+1, -1])
def test_strip_orientation_and_callout_side_do_not_change_the_outcome(axis, side):
    sheet = Sheet(size=(1400.0, 1400.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, axis=axis, side=side)
    add_window(sheet, 1, "W2", panels=3, length=232.0, axis=axis, side=side)
    got = by_mark(run(sheet))
    assert got["W1"].status is CAND and got["W2"].status is CAND


def test_replay_is_deterministic_and_does_not_mutate_its_inputs():
    sheet = three_windows()
    pdf = sheet.pdf()
    ink, words, types = tuple(ink_of(pdf)), tuple(words_of(pdf)), tuple(types_of(sheet))
    scope = scope_for(sheet)
    first = shadow.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=words, elevation_types=types)
    again = shadow.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=words, elevation_types=types)
    assert first == again
    assert (ink, words, types) == (tuple(ink_of(pdf)), tuple(words_of(pdf)), tuple(types_of(sheet)))
    assert {c.record_id for c in first.correspondences} == {c.record_id for c in again.correspondences}


def test_every_record_id_carries_document_revision_snapshot_and_page_ownership():
    sheet = three_windows()
    base = run(sheet)
    for field_name in ("document_id", "revision_id", "snapshot_id", "source_sha256"):
        other = replace(OWNERSHIP, **{field_name: "b" * 64 if field_name == "source_sha256" else "other"})
        changed = run(sheet, ownership=other)
        assert {c.record_id for c in changed.correspondences}.isdisjoint({c.record_id for c in base.correspondences}), field_name
        assert {s.strip_id for s in changed.strips}.isdisjoint({s.strip_id for s in base.strips}), field_name
    assert base.ownership == OWNERSHIP and base.plan_page_id == "1" and base.elevation_page_id == "2"
    assert base.elevation_viewport_id is None
    assert all(c.plan_viewport_id == "view_plan" for c in base.correspondences)


def test_scope_quanta_must_be_positive_numbers():
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            shadow.PlanCalloutStripScope(
                ownership=OWNERSHIP, plan_page_id="1", elevation_page_id="2", callout_mark_pattern="W.",
                coordinate_quantum_pt=bad, dimension_quantum_mm=5.0)


# --- the elevation width on a rotated page ------------------------------------------------


@pytest.mark.parametrize("rotation,expected", [(0, 1900.0), (180, 1900.0), (90, 3600.0), (270, 3600.0)])
def test_display_width_follows_the_page_rotation_not_the_record_axis_label(rotation, expected):
    # native frame 215 x 408 pt with the record labelling native x = 1900 mm, native y = 3600 mm
    width, reason = shadow.display_horizontal_width_mm(rotation, (138.0, 1645.0, 353.0, 2053.0), 1900.0, 3600.0)
    assert (width, reason) == (expected, "")


def test_a_swapped_axis_label_is_detected_and_read_correctly():
    # the same physical frame, but the record labelled its axes the other way round: the 408 pt native-y
    # extent is still the 3600 mm one, and on a /Rotate 90 page native y is display-horizontal
    assert shadow.display_horizontal_width_mm(90, (138.0, 1645.0, 353.0, 2053.0), 3600.0, 1900.0) == (3600.0, "")
    assert shadow.display_horizontal_width_mm(0, (138.0, 1645.0, 353.0, 2053.0), 3600.0, 1900.0) == (1900.0, "")


def test_a_square_frame_or_an_unverifiable_label_abstains_instead_of_picking_an_axis():
    assert shadow.display_horizontal_width_mm(90, (0.0, 0.0, 100.0, 100.0), 2000.0, 2000.0) == (None, "frame_axis_ambiguous")
    assert shadow.display_horizontal_width_mm(90, (0.0, 0.0, 100.0, 200.0), 2000.0, 2000.0) == (None, "frame_axis_unverified")
    assert shadow.display_horizontal_width_mm(45, (0.0, 0.0, 100.0, 200.0), 1000.0, 2000.0) == (None, "page_rotation_unavailable")
    assert shadow.display_horizontal_width_mm(0, (0.0, 0.0, 0.0, 200.0), 1000.0, 2000.0) == (None, "elevation_frame_degenerate")
