"""Opening-occupancy separation of callout claimants in the plan callout -> glazing strip shadow.

A claimant found by location alone stays a rival unless a source-owned opening occupancy accounts for it
elsewhere. These tests pin what separates a claimant, everything that must NOT, that a separated claimant is
retained on the record, and that the default (no occupancy) result is untouched. Synthetic drawings only.
"""
from __future__ import annotations

import math
import random

import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from plan_callout_strip_fixture import (
    ABST, CAND, CONF, GAP, HEX_H, OWNERSHIP, Sheet, add_window, by_mark, ink_of, run, scope_for, three_windows,
    types_of, words_of,
)

D1_CENTRE = (100.0, 305.52 + GAP + HEX_H)
W1_CENTRE = (164.0, 305.52 + GAP + HEX_H)           # the first window's own callout (strip 60..264, band 300..305.52)
# a door gap: along x 80..120, face band 6 pt either side of the callout's centre line
D1_APERTURE = dict(along=(80.0, 120.0), normal_range=(D1_CENTRE[1] - 6.0, D1_CENTRE[1] + 6.0))


def _word_id(pdf_words, text):
    return next(w.observation_id for w in pdf_words if w.text == text)


def _occ(word_id, *, along=D1_APERTURE["along"], normal_range=D1_APERTURE["normal_range"], axis=(1.0, 0.0),
         normal=(0.0, 1.0), ids=("door-a", "door-b", "door-c", "door-d", "door-e", "door-f"), record="door-record",
         anchor=None, basis=shadow.OCCUPANCY_BASIS_ENVELOPE, ownership=OWNERSHIP, competing=0):
    box = anchor or (D1_CENTRE[0] - 6.0, D1_CENTRE[1] - 6.0, D1_CENTRE[0] + 6.0, D1_CENTRE[1] + 6.0)
    return shadow.ClaimantOccupancy(
        ownership=ownership, word_observation_id=word_id, occupied_record_id=record, occupied_observation_ids=tuple(ids),
        aperture_axis=axis, aperture_normal=normal, aperture_along=along, aperture_normal_range=normal_range,
        anchor_box=box, basis=basis, competing_candidate_count=competing)


def _sheet_with_door():
    sheet = three_windows()
    sheet.callout(D1_CENTRE, "D1")
    return sheet


def _run_with(sheet, occupancies, *, evaluated=True, **kw):
    return run(sheet, claimant_occupancy=tuple(occupancies), claimant_occupancy_evaluated=evaluated, **kw)


def _d1(sheet):
    return _word_id(words_of(sheet.pdf()), "D1")


# ------------------------------------------------------------------------------------
# positive: a separated claimant is retained, the strip's own correspondence survives
# ------------------------------------------------------------------------------------

def test_a_door_callout_anchored_in_an_other_opening_is_separated_and_retained():
    sheet = _sheet_with_door()
    base = by_mark(run(sheet))
    assert base["W1"].status is CONF                                    # location alone keeps it a rival
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet))]))
    w1 = got["W1"]
    assert w1.status is CAND
    assert shadow.CLAIMANT_SEPARATED_REASON in w1.reason_codes
    assert w1.rival_callout_ids == ()
    # the hexagon is both a six-edge ring and a visible envelope: both entries are kept, each with its witness
    assert {(s.word_observation_id, s.entry, s.occupied_record_id) for s in w1.separated_claimants} == {
        (_d1(sheet), "ring", "door-record"), (_d1(sheet), "exclusion", "door-record")}
    assert all(s.strip_id == w1.strip_id for s in w1.separated_claimants)
    assert dict(w1.numbers)["separated_claimants"] == 1.0 and dict(w1.numbers)["other_callout_claimants"] == 0.0
    # the door callout itself is still reported, and nothing else moved
    assert got["D1"].tag_observation_id == _d1(sheet)
    for mark in ("W2", "W3"):
        assert got[mark].record_id == base[mark].record_id
        assert got[mark].separated_claimants == ()


def test_the_default_result_is_identical_with_no_occupancy_and_with_an_empty_unevaluated_one():
    sheet = _sheet_with_door()
    plain = run(sheet)
    empty = _run_with(sheet, [], evaluated=False)
    assert [c.record_id for c in plain.correspondences] == [c.record_id for c in empty.correspondences]
    assert all(c.separated_claimants == () for c in plain.correspondences)
    assert "claimant_occupancy" not in "".join(plain.page_reason_codes)


def test_an_evaluated_empty_inventory_separates_nothing():
    sheet = _sheet_with_door()
    got = by_mark(_run_with(sheet, [], evaluated=True))
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


# ------------------------------------------------------------------------------------
# what must NOT separate a claimant
# ------------------------------------------------------------------------------------

def test_an_occupied_opening_that_shares_ink_with_the_strip_never_separates():
    sheet = _sheet_with_door()
    strip_ink = shadow_strip_ink(sheet)
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet), ids=(strip_ink[0], "x1", "x2"))]))
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


def test_an_aperture_that_touches_the_strip_never_separates():
    sheet = _sheet_with_door()
    # the face band reaches down onto the strip's band (y 300..305.52)
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet), normal_range=(303.0, D1_CENTRE[1] + 6.0))]))
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


def test_an_anchor_outside_the_occupied_aperture_never_separates_the_entry():
    sheet = _sheet_with_door()
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet), along=(300.0, 340.0))]))       # aperture elsewhere on the wall
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


def test_an_occupancy_for_another_word_does_not_separate_this_one():
    sheet = _sheet_with_door()
    other = _word_id(words_of(sheet.pdf()), "W2")
    got = by_mark(_run_with(sheet, [_occ(other)]))
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


def test_a_rival_without_any_occupancy_keeps_the_strip_in_conflict_even_when_another_is_separated():
    sheet = _sheet_with_door()
    sheet.callout((230.0, 305.52 + GAP + HEX_H), "D2")          # inside the strip's extent, away from D1's
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet))]))
    assert got["W1"].status is CONF
    assert _word_id(words_of(sheet.pdf()), "D2") in got["W1"].rival_callout_ids
    assert {s.word_observation_id for s in got["W1"].separated_claimants} == {_d1(sheet)}


def test_two_occupancy_inputs_for_one_word_are_rejected():
    sheet = _sheet_with_door()
    with pytest.raises(ValueError):
        _run_with(sheet, [_occ(_d1(sheet)), _occ(_d1(sheet), record="other")])


def test_an_occupancy_of_another_document_revision_snapshot_or_source_is_rejected():
    sheet = _sheet_with_door()
    foreign = shadow.SourceOwnership("doc-2", "rev-1", "snap-1", "a" * 64, shadow.PRODUCER_INPUT_PROVENANCE)
    with pytest.raises(ValueError):
        _run_with(sheet, [_occ(_d1(sheet), ownership=foreign)])


def test_occupancy_records_without_an_evaluated_inventory_are_rejected():
    sheet = _sheet_with_door()
    with pytest.raises(ValueError):
        _run_with(sheet, [_occ(_d1(sheet))], evaluated=False)


@pytest.mark.parametrize("bad", [
    dict(competing=1), dict(ids=()), dict(ids=("a", "a")), dict(basis="nearest"), dict(record=""),
    dict(along=(120.0, 80.0)), dict(axis=(2.0, 0.0)), dict(normal=(1.0, 0.0)),
    dict(anchor=(5.0, 5.0, 1.0, 1.0)), dict(anchor=(0.0, 0.0, math.nan, 1.0)),
])
def test_a_malformed_occupancy_cannot_be_built(bad):
    with pytest.raises(ValueError):
        _occ("w", **bad)


def test_a_non_tuple_or_foreign_typed_occupancy_input_is_rejected():
    sheet = _sheet_with_door()
    with pytest.raises(ValueError):
        scope_for(sheet, claimant_occupancy=[_occ("w")], claimant_occupancy_evaluated=True)
    with pytest.raises(ValueError):
        scope_for(sheet, claimant_occupancy=("w",), claimant_occupancy_evaluated=True)
    with pytest.raises(ValueError):
        scope_for(sheet, claimant_occupancy=(), claimant_occupancy_evaluated=1)


# ------------------------------------------------------------------------------------
# the callout's own tag occupying another opening
# ------------------------------------------------------------------------------------

def test_a_callout_whose_own_tag_occupies_another_opening_abstains():
    sheet = three_windows()
    w1 = _word_id(words_of(sheet.pdf()), "W1")
    centre = W1_CENTRE
    occ = _occ(w1, along=(centre[0] - 30.0, centre[0] + 30.0), normal_range=(centre[1] - 6.0, centre[1] + 6.0),
               anchor=(centre[0] - 6.0, centre[1] - 6.0, centre[0] + 6.0, centre[1] + 6.0))
    got = by_mark(_run_with(sheet, [occ]))["W1"]
    assert got.status is ABST and got.reason_codes == (shadow.CALLOUT_OCCUPIES_OTHER_OPENING,)
    assert dict(got.conditions)["callout_beside_fingerprint_strip"] == shadow.FAILED


def test_the_callouts_own_occupancy_of_the_strips_own_opening_is_not_a_reason_to_abstain():
    sheet = three_windows()
    strip_ink = shadow_strip_ink(sheet)
    w1 = _word_id(words_of(sheet.pdf()), "W1")
    centre = W1_CENTRE
    occ = _occ(w1, ids=(strip_ink[0], "x1"), along=(centre[0] - 30.0, centre[0] + 30.0), normal_range=(centre[1] - 6.0, centre[1] + 6.0),
               anchor=(centre[0] - 6.0, centre[1] - 6.0, centre[0] + 6.0, centre[1] + 6.0))
    assert by_mark(_run_with(sheet, [occ]))["W1"].status is CAND


# ------------------------------------------------------------------------------------
# the other claimant routes: exclusion envelopes, unresolved rings, untrusted words
# ------------------------------------------------------------------------------------

def _exclusion(word_id, bbox, *, trusted=True, reason="visible_callout_envelope", ink=("ink-ex",)):
    return shadow.CalloutExclusion(record_id="ex-" + word_id[-6:], word_observation_id=word_id, bbox=bbox,
                                   reason_codes=(reason,), label_trusted=trusted, visible_ink_ids=ink)


def test_an_exclusion_envelope_claimant_is_separated_by_the_same_witness_and_retained():
    sheet = three_windows()
    sheet.text((94.0, 322.0), "D1")                  # a tag with no six-edge ring: only its envelope claims
    pdf_words = words_of(sheet.pdf())
    d1 = _word_id(pdf_words, "D1")
    box = (88.0, 312.0, 112.0, 328.0)
    plain = by_mark(run(sheet, native_curve_exclusions=(_exclusion(d1, box),)))
    assert plain["W1"].status is CONF
    occ = _occ(d1, along=(80.0, 120.0), normal_range=(314.0, 326.0), anchor=box)
    got = by_mark(_run_with(sheet, [occ], native_curve_exclusions=(_exclusion(d1, box),)))["W1"]
    assert got.status is CAND and shadow.CLAIMANT_SEPARATED_REASON in got.reason_codes
    assert [(s.entry, s.entry_id) for s in got.separated_claimants] == [("exclusion", "ex-" + d1[-6:])]


def test_a_second_envelope_of_the_same_word_outside_the_aperture_stays_an_uncertain_claimant():
    sheet = three_windows()
    sheet.text((94.0, 322.0), "D1")
    d1 = _word_id(words_of(sheet.pdf()), "D1")
    inside = (88.0, 312.0, 112.0, 328.0)
    stray = (200.0, 312.0, 224.0, 328.0)               # another envelope of the same word, inside the strip's extent
    ex = (_exclusion(d1, inside), shadow.CalloutExclusion(
        record_id="ex-stray", word_observation_id=d1, bbox=stray,
        reason_codes=("native_curve_callout_visibility_unproven",), label_trusted=True,
        native_primitive_refs=("native:path:1:item:0",)))
    occ = _occ(d1, along=(80.0, 120.0), normal_range=(314.0, 326.0), anchor=inside)
    got = by_mark(_run_with(sheet, [occ], native_curve_exclusions=ex))["W1"]
    # the proven envelope is separated; the stray one is not anchored in the aperture, so it keeps W1 uncertain
    assert got.status is ABST and "strip_has_unresolved_callout_envelope" in got.reason_codes
    assert [(s.entry, s.entry_id) for s in got.separated_claimants] == [("exclusion", "ex-" + d1[-6:])]


def test_an_untrusted_word_is_never_separated():
    sheet = three_windows()
    sheet.callout(D1_CENTRE, "D9")
    pdf_words = words_of(sheet.pdf())
    d9 = next(w for w in pdf_words if w.text == "D9")
    trusted = [w for w in pdf_words if w.text != "D9"]
    unknown = shadow.PlanTextObservation(d9.observation_id, "", d9.bbox)
    base = by_mark(run(sheet, words=trusted, untrusted_plan_words=(unknown,)))["W1"]
    assert base.status is ABST and "strip_has_claimant_with_untrusted_label" in base.reason_codes
    got = by_mark(run(sheet, words=trusted, untrusted_plan_words=(unknown,),
                      claimant_occupancy=(_occ(d9.observation_id),), claimant_occupancy_evaluated=True))["W1"]
    assert got.status is ABST and got.separated_claimants == ()


# ------------------------------------------------------------------------------------
# metamorphic, ordering, replay, no mutation
# ------------------------------------------------------------------------------------

def test_translating_the_plan_and_the_occupancy_gives_the_same_decisions():
    plain, moved = _sheet_with_door(), None
    dx, dy = 37.0, -11.0
    # a translated sheet: every strip, callout and the occupancy aperture/anchor move together
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0, dx=dx, dy=dy)
    add_window(sheet, 1, "W2", panels=3, length=232.0, dx=dx, dy=dy)
    add_window(sheet, 2, "W3", panels=5, length=120.0, dx=dx, dy=dy)
    sheet.callout((D1_CENTRE[0] + dx, D1_CENTRE[1] + dy), "D1")
    occ = _occ(_d1(sheet), along=(80.0 + dx, 120.0 + dx), normal_range=(D1_APERTURE["normal_range"][0] + dy,
                                                                        D1_APERTURE["normal_range"][1] + dy),
               anchor=(D1_CENTRE[0] + dx - 6.0, D1_CENTRE[1] + dy - 6.0, D1_CENTRE[0] + dx + 6.0, D1_CENTRE[1] + dy + 6.0))
    moved = by_mark(_run_with(sheet, [occ]))
    base = by_mark(_run_with(plain, [_occ(_d1(plain))]))
    assert {m: (c.status, c.reason_codes) for m, c in moved.items()} == {m: (c.status, c.reason_codes) for m, c in base.items()}
    assert {s.entry for s in moved["W1"].separated_claimants} == {"ring", "exclusion"}


def test_a_rotated_aperture_frame_contains_the_same_anchor():
    sheet = _sheet_with_door()
    cx, cy = D1_CENTRE
    # the same rectangle expressed in a frame whose along axis is +y and whose normal is -x
    occ = _occ(_d1(sheet), axis=(0.0, 1.0), normal=(-1.0, 0.0), along=(cy - 6.0, cy + 6.0), normal_range=(-120.0, -80.0))
    got = by_mark(_run_with(sheet, [occ]))["W1"]
    assert got.status is CAND and {s.word_observation_id for s in got.separated_claimants} == {_d1(sheet)}


def test_the_input_order_of_ink_words_types_and_occupancy_does_not_change_a_decision():
    sheet = _sheet_with_door()
    pdf = sheet.pdf()
    d1 = _word_id(words_of(pdf), "D1")
    occs = [_occ(d1), _occ(_word_id(words_of(pdf), "W3"), along=(700.0, 740.0), normal_range=(10.0, 20.0),
                           anchor=(710.0, 12.0, 720.0, 18.0), record="far")]
    base = _run_with(sheet, occs)
    rng = random.Random(7)
    for _ in range(5):
        ink, words, types, shuffled = list(ink_of(pdf)), list(words_of(pdf)), list(types_of(sheet)), list(occs)
        for seq in (ink, words, types, shuffled):
            rng.shuffle(seq)
        again = _run_with(sheet, shuffled, ink=ink, words=words, types=types)
        assert [c.record_id for c in again.correspondences] == [c.record_id for c in base.correspondences]


def test_replay_is_deterministic_and_the_record_id_binds_the_separation():
    sheet = _sheet_with_door()
    a = _run_with(sheet, [_occ(_d1(sheet))])
    b = _run_with(sheet, [_occ(_d1(sheet))])
    assert a == b
    other = _run_with(sheet, [_occ(_d1(sheet), record="a-different-opening")])
    assert by_mark(a)["W1"].record_id != by_mark(other)["W1"].record_id
    assert by_mark(a)["W1"].record_id != by_mark(run(sheet))["W1"].record_id


def test_the_scope_and_its_inputs_are_not_mutated():
    sheet = _sheet_with_door()
    pdf = sheet.pdf()
    ink, words, types = ink_of(pdf), words_of(pdf), types_of(sheet)
    scope = scope_for(sheet, claimant_occupancy=(_occ(_word_id(words, "D1")),), claimant_occupancy_evaluated=True)
    before = (list(ink), list(words), list(types), scope)
    shadow.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=words, elevation_types=types)
    assert (ink, words, types, scope) == before


def test_a_separated_claimant_is_not_a_grant():
    sheet = _sheet_with_door()
    result = _run_with(sheet, [_occ(_d1(sheet))])
    for name in shadow._GRANT_FLAGS:
        assert getattr(result, name) is False
    for c in result.correspondences:
        if c.status is CAND:
            assert "source_correspondence_candidate_not_authority" in c.reason_codes


def test_the_adapter_flag_must_be_an_explicit_bool():
    for bad in (1, 0, None, "true", [True]):
        with pytest.raises(TypeError):
            shadow.audit_plan_callout_to_glazing_strip_from_source(
                object(), revision_id="r", plan_page_id=1, elevation_page_id=2, callout_mark_pattern=".",
                panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0, claimant_occupancy=bad)


def test_the_binders_containment_tolerance_is_the_one_mirrored_here():
    import pb_schedule_opening_instance_binding_authority as binder
    assert shadow._OCCUPANCY_CONTAINMENT_TOL == binder._COORD_TOL


# ------------------------------------------------------------------------------------
# helpers that need the sheet's strips
# ------------------------------------------------------------------------------------

def shadow_strip_ink(sheet):
    """The ink ids of the first window's strip, as the shadow itself inventories them."""
    result = run(sheet)
    strip = min((s for s in result.strips if s.axis == "H" and s.panel_count == 3), key=lambda s: s.frame_along[0])
    return list(strip.ink_ids)


# ------------------------------------------------------------------------------------
# more look-alikes, the anchor choice, provenance of the basis
# ------------------------------------------------------------------------------------

def test_an_anchor_in_the_along_range_but_outside_the_face_band_never_separates_the_entry():
    sheet = _sheet_with_door()
    got = by_mark(_run_with(sheet, [_occ(_d1(sheet), normal_range=(D1_CENTRE[1] + 8.0, D1_CENTRE[1] + 20.0))]))
    assert got["W1"].status is CONF and got["W1"].separated_claimants == ()


def test_an_untrusted_word_with_an_undecidable_ring_is_never_separated_even_when_an_occupancy_names_it():
    sheet = three_windows()
    sheet.callout(D1_CENTRE, "D9", extra_ring=True)         # two rings round one word: the ring is not unique
    pdf_words = words_of(sheet.pdf())
    d9 = next(w for w in pdf_words if w.text == "D9")
    trusted = [w for w in pdf_words if w.text != "D9"]
    unknown = shadow.PlanTextObservation(d9.observation_id, "", d9.bbox)
    plain = by_mark(run(sheet, words=trusted, untrusted_plan_words=(unknown,)))["W1"]
    assert plain.status is ABST
    named = by_mark(run(sheet, words=trusted, untrusted_plan_words=(unknown,),
                        claimant_occupancy=(_occ(d9.observation_id),), claimant_occupancy_evaluated=True))["W1"]
    assert named.status is ABST and named.separated_claimants == ()
    assert named.reason_codes == plain.reason_codes


def test_a_separated_claimant_records_what_the_occupancy_anchored():
    sheet = _sheet_with_door()
    for basis in (shadow.OCCUPANCY_BASIS_ENVELOPE, shadow.OCCUPANCY_BASIS_TEXT):
        got = by_mark(_run_with(sheet, [_occ(_d1(sheet), basis=basis)]))["W1"]
        assert {s.basis for s in got.separated_claimants} == {basis}


def _word(oid, text, box=(0.0, 0.0, 10.0, 10.0)):
    return shadow.PlanTextObservation(oid, text, box)


def _envelope(word_id, box, *, trusted=True, reason="visible_callout_envelope", rid=None):
    return shadow.CalloutExclusion(
        record_id=rid or f"ex-{word_id}-{box[0]}", word_observation_id=word_id, bbox=box, reason_codes=(reason,),
        label_trusted=trusted, visible_ink_ids=("ink",) if reason == "visible_callout_envelope" else (),
        native_primitive_refs=() if reason == "visible_callout_envelope" else ("native:path:0:item:0",))


def test_the_anchor_is_the_proven_envelope_when_there_is_exactly_one_else_the_text_box():
    words = [_word("w2", "D2", (50, 50, 60, 60)), _word("w1", "D1", (0, 0, 10, 10)), _word("x", "NOTE", (5, 5, 6, 6))]
    env = (-3.0, -3.0, 13.0, 13.0)
    anchors = shadow._occupancy_anchors(words, [_envelope("w1", env)])
    assert anchors == [("w1", env, shadow.OCCUPANCY_BASIS_ENVELOPE), ("w2", (50, 50, 60, 60), shadow.OCCUPANCY_BASIS_TEXT)]


def test_a_word_with_two_distinct_proven_envelopes_has_no_anchor_and_keeps_its_claims():
    words = [_word("w1", "D1")]
    two = [_envelope("w1", (-3.0, -3.0, 13.0, 13.0)), _envelope("w1", (-4.0, -4.0, 14.0, 14.0))]
    assert shadow._occupancy_anchors(words, two) == []
    assert shadow._occupancy_anchors(words, [two[0], two[0]]) == [("w1", two[0].bbox, shadow.OCCUPANCY_BASIS_ENVELOPE)]


def test_a_native_curve_or_untrusted_envelope_never_anchors_a_word():
    words = [_word("w1", "D1", (0, 0, 10, 10))]
    for ex in (_envelope("w1", (-3.0, -3.0, 13.0, 13.0), reason="native_curve_callout_visibility_unproven"),
               _envelope("w1", (-3.0, -3.0, 13.0, 13.0), trusted=False)):
        assert shadow._occupancy_anchors(words, [ex]) == [("w1", (0, 0, 10, 10), shadow.OCCUPANCY_BASIS_TEXT)]
