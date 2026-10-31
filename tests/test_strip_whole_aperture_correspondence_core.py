"""The pure decision: which whole-aperture record, if any, may correspond to a callout-identified strip."""
from __future__ import annotations

import copy
import random
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
from pb_structural_whole_opening_aperture_authority import (
    AMBIGUOUS_MULTI_LAYER_OFFSET,
    APERTURE_EXTENT_INCOMPLETE,
    FILL_MASK_BOUNDARY_UNPROVEN,
    HOST_WALL_CONTINUITY_PROVEN,
    STRUCTURAL_TERMINAL_JAMB_PROVEN,
    TERMINAL_ROLE_UNPROVEN,
    WALL_CONTINUITY_MISSING,
)
from strip_whole_aperture_fixture import (
    ABST, CAND, CONF, CORR, INK, PROVEN, Q, clean_window, evaluate, inventory, nomination, one, record,
    signature, sub, transform,
)


# ---- the positive case ---------------------------------------------------------------------------------------
def test_one_proven_equal_extent_record_with_its_runs_set_aside_is_a_candidate():
    whole, posts = clean_window()
    runs = [record((100.0, 162.0), band=(197.5, 198.22), rid="run-1"), record((160.0, 232.0), rid="run-2"),
            record((230.0, 304.0), rid="run-3"), record((100.0, 304.0), band=(200.0, 200.72), rid="dup-of-nothing")]
    c = one(nomination(), [whole, *runs[:3]], posts)
    assert c.status is CAND and c.reason_codes == (shadow.WHOLE_APERTURE_CORRESPONDED,)
    assert len(c.equal_record_ids) == 1 and c.unvetoed_rival_record_ids == () and len(c.vetoed_rival_record_ids) == 3
    assert c.linkage_basis == shadow.LINKAGE_SPAN_EQUALITY_ONLY
    assert {r.relation for r in c.relations} == {shadow.RELATION_EQUAL, shadow.RELATION_NESTED}
    assert all(r.vetoed_by_subdivision_ids for r in c.relations if r.relation == shadow.RELATION_NESTED)


def test_a_record_that_names_the_strip_ink_is_linked_by_observation_identity():
    c = one(nomination(), [record((100.0, 304.0), glazing=("g1", "zz"))])
    assert c.status is CAND and c.linkage_basis == shadow.LINKAGE_OBSERVATION_IDENTITY
    assert c.relations[0].shared_strip_ink_ids == ("g1",)


def test_the_page_receipt_is_shadow_only_and_names_its_standing_limits():
    out = evaluate(nomination(), [record((100.0, 304.0))])
    assert out.shadow_only is True and out.standing_limits == shadow.STANDING_LIMITS
    assert all(getattr(out, name) is False for name in shadow._GRANT_FLAGS)
    assert "equal_extent_is_location_not_identity_of_a_physical_opening" in out.standing_limits


# ---- absence, duplicates and conflicts -----------------------------------------------------------------------
def test_no_equal_extent_record_abstains():
    c = one(nomination(), [record((500.0, 700.0))])
    assert c.status is ABST and c.reason_codes == (shadow.NO_EQUAL_EXTENT_APERTURE,)


def test_only_a_smaller_positive_record_inside_the_strip_is_a_conflict_not_a_correspondence():
    c = one(nomination(), [record((100.0, 200.0))])
    assert c.status is CONF and set(c.reason_codes) == {shadow.NO_EQUAL_EXTENT_APERTURE, shadow.NESTED_APERTURES_NOT_VETOED}


def test_no_records_at_all_abstains():
    c = one(nomination(), [])
    assert c.status is ABST and c.reason_codes == (shadow.NO_EQUAL_EXTENT_APERTURE,)


def test_two_different_readings_of_the_same_extent_conflict_and_are_both_retained():
    a = record((100.0, 304.0), rid="same-id")
    b = record((100.0, 304.0), band=(199.0, 199.72), rid="same-id", lo=("other-jamb",))
    out = evaluate(nomination(), [a, b])
    c = out.correspondences[0]
    assert c.status is CONF and shadow.DUPLICATE_EQUAL_EXTENT_APERTURES in c.reason_codes
    assert len(c.equal_record_ids) == 2 and shadow.APERTURE_RECORD_IDS_NOT_UNIQUE in out.page_reason_codes


def test_identical_repeats_of_one_record_collapse_to_one_reading():
    r = record((100.0, 304.0))
    out = evaluate(nomination(), [r, r, copy.deepcopy(r)])
    assert out.correspondences[0].status is CAND and out.aperture_record_count == 1
    assert shadow.APERTURE_RECORD_IDS_NOT_UNIQUE not in out.page_reason_codes


# ---- the authority's own structural proof is required ---------------------------------------------------------
@pytest.mark.parametrize("reason", [TERMINAL_ROLE_UNPROVEN, APERTURE_EXTENT_INCOMPLETE, WALL_CONTINUITY_MISSING,
                                    FILL_MASK_BOUNDARY_UNPROVEN, AMBIGUOUS_MULTI_LAYER_OFFSET])
def test_an_equal_extent_record_that_the_authority_does_not_prove_abstains(reason):
    r = record((100.0, 304.0), status=ABST, reasons=(reason,))
    c = one(nomination(), [r])
    assert c.status is ABST and shadow.EQUAL_EXTENT_STRUCTURE_NOT_PROVEN in c.reason_codes


def test_a_candidate_record_that_carries_an_ambiguity_reason_is_not_proven():
    r = record((100.0, 304.0), reasons=(*PROVEN, AMBIGUOUS_MULTI_LAYER_OFFSET))
    assert one(nomination(), [r]).status is ABST


@pytest.mark.parametrize("missing", [STRUCTURAL_TERMINAL_JAMB_PROVEN, HOST_WALL_CONTINUITY_PROVEN])
def test_both_the_jamb_proof_and_the_wall_continuity_proof_are_required(missing):
    r = record((100.0, 304.0), reasons=tuple(x for x in PROVEN if x != missing))
    assert one(nomination(), [r]).status is ABST


def test_an_authority_conflict_on_the_equal_extent_record_is_preserved():
    assert one(nomination(), [record((100.0, 304.0), status=CONF)]).status is CONF


def test_a_corroborated_equal_extent_record_is_accepted_like_a_candidate():
    assert one(nomination(), [record((100.0, 304.0), status=CORR)]).status is CAND


# ---- the glass band must lie inside the strip ------------------------------------------------------------------
@pytest.mark.parametrize("band", [(196.0, 196.72), (203.5, 204.22), (196.7, 197.42)])
def test_an_equal_extent_record_whose_glass_band_is_not_inside_the_strip_band_abstains(band):
    c = one(nomination(), [record((100.0, 304.0), band=band)])
    # a band that merely overlaps the strip is still a different pair of lines: it must not be taken as this strip's
    assert c.status is ABST
    assert shadow.EQUAL_EXTENT_BAND_NOT_WITHIN_STRIP_BAND in c.reason_codes or shadow.NO_EQUAL_EXTENT_APERTURE in c.reason_codes


def test_an_aperture_record_that_links_a_different_glazing_strip_abstains():
    c = one(nomination(), [record((100.0, 304.0), glazing=("somebody-else",))])
    assert c.status is ABST and shadow.APERTURE_LINKS_DIFFERENT_GLAZING in c.reason_codes


# ---- rivals ----------------------------------------------------------------------------------------------------
def test_a_nested_record_that_the_authority_does_not_account_for_stays_a_rival_and_blocks():
    whole, posts = clean_window()
    nested = record((100.0, 200.0), rid="odd-run", status=ABST, reasons=(TERMINAL_ROLE_UNPROVEN,))
    c = one(nomination(), [whole, nested], posts)
    assert c.status is ABST and shadow.NESTED_APERTURES_NOT_VETOED in c.reason_codes
    assert len(c.unvetoed_rival_record_ids) == 1 and c.vetoed_rival_record_ids == ()


def test_a_positive_nested_rival_that_nothing_accounts_for_is_a_conflict():
    whole, posts = clean_window()
    c = one(nomination(), [whole, record((100.0, 200.0), rid="odd-run")], posts)
    assert c.status is CONF and shadow.NESTED_APERTURES_NOT_VETOED in c.reason_codes


def test_runs_cut_by_the_equal_records_own_discriminated_posts_are_set_aside_and_named():
    whole, posts = clean_window()
    runs = [record((100.0, 162.0), rid="a"), record((160.0, 232.0), rid="b"), record((230.0, 304.0), rid="c"),
            record((100.0, 232.0), rid="d"), record((162.0, 304.0), rid="e")]
    c = one(nomination(), [whole, *runs], posts)
    assert c.status is CAND and len(c.vetoed_rival_record_ids) == 5
    named = {x for r in c.relations for x in r.vetoed_by_subdivision_ids}
    assert named == {p.record_id for p in posts}


@pytest.mark.parametrize("end", [199.0, 161.0, 229.9, 300.0])
def test_a_run_with_an_end_that_is_not_on_a_cut_is_not_set_aside(end):
    whole, posts = clean_window()
    c = one(nomination(), [whole, record((100.0, end), rid="x")], posts)
    assert c.status is CONF and c.vetoed_rival_record_ids == ()


def test_a_post_the_equal_record_does_not_list_cuts_nothing():
    whole, posts = clean_window()
    unlisted = replace(whole, discriminated_subdivision_ids=(posts[0].record_id,))
    c = one(nomination(), [unlisted, record((230.0, 304.0), rid="y")], posts)
    assert c.status is CONF           # the run starts on the unlisted post's edge
    assert one(nomination(), [unlisted, record((160.0, 304.0), rid="z")], posts).status is CAND   # the listed post cuts


@pytest.mark.parametrize("change", [
    {"internal": False}, {"status": ABST}, {"axis": "V"},
])
def test_a_subdivision_that_is_not_an_internal_positive_same_axis_post_cuts_nothing(change):
    whole, posts = clean_window()
    bad = [replace(posts[0], **{("is_internal_subdivision" if k == "internal" else k): v for k, v in change.items()}),
           posts[1]]
    c = one(nomination(), [whole, record((100.0, 162.0), rid="a")], bad)
    assert c.status is CONF


def test_a_subdivision_outside_the_equal_extent_cuts_nothing():
    whole = record((100.0, 304.0), subs=["far"])
    far = sub((400.0, 402.0), sid="far")
    c = one(nomination(), [whole, record((100.0, 402.0), rid="long")], [far])
    assert c.status is CONF


def test_a_containing_record_is_a_rival_and_is_never_set_aside():
    whole, posts = clean_window()
    c = one(nomination(), [whole, record((20.0, 380.0), rid="long")], posts)
    assert c.status is CONF and shadow.CONTAINING_APERTURES_NOT_VETOED in c.reason_codes
    assert [r.relation for r in c.relations].count(shadow.RELATION_CONTAINING) == 1


def test_a_partly_overlapping_record_is_a_rival_and_is_never_set_aside():
    whole, posts = clean_window()
    c = one(nomination(), [whole, record((250.0, 400.0), rid="next")], posts)
    assert c.status is CONF and shadow.OVERLAPPING_APERTURES_NOT_VETOED in c.reason_codes


def test_an_unproven_rival_blocks_without_claiming_a_conflict():
    whole, posts = clean_window()
    rival = record((250.0, 400.0), rid="next", status=ABST, reasons=(WALL_CONTINUITY_MISSING,))
    c = one(nomination(), [whole, rival], posts)
    assert c.status is ABST and shadow.OVERLAPPING_APERTURES_NOT_VETOED in c.reason_codes


# ---- look-alikes that are not rivals ---------------------------------------------------------------------------
@pytest.mark.parametrize("other", [
    record((100.0, 304.0), axis="V", rid="other-axis"),
    record((100.0, 304.0), band=(260.0, 260.72), rid="other-wall"),
    record((304.0, 400.0), rid="adjacent-window"),
    record((20.0, 100.0), rid="adjacent-left"),
    record((304.05, 400.0), rid="adjacent-within-tolerance"),
    record((500.0, 700.0), rid="far"),
])
def test_records_that_cannot_be_a_reading_of_this_strips_ink_are_ignored(other):
    whole, posts = clean_window()
    c = one(nomination(), [whole, other], posts)
    assert c.status is CAND and len(c.relations) == 1


def test_an_overlap_just_past_the_tolerance_is_a_rival():
    whole, posts = clean_window()
    c = one(nomination(), [whole, record((303.7, 400.0), rid="close")], posts)
    assert c.status is CONF


def test_the_equal_extent_tolerance_is_a_quarter_of_the_coordinate_quantum():
    eq = Q / 4.0
    assert one(nomination(), [record((100.0 + eq * 0.9, 304.0 - eq * 0.9))]).status is CAND
    c = one(nomination(), [record((100.0 + eq * 1.5, 304.0))])
    assert c.status is CONF and shadow.NO_EQUAL_EXTENT_APERTURE in c.reason_codes      # a shorter record is a rival


# ---- the page inventory ----------------------------------------------------------------------------------------
def test_an_incomplete_stroke_inventory_abstains_every_strip():
    out = evaluate(nomination(), [record((100.0, 304.0))], inv=inventory(complete=False))
    assert out.correspondences[0].status is ABST
    assert shadow.PAGE_STROKE_INVENTORY_INCOMPLETE in out.correspondences[0].reason_codes


def test_strip_ink_that_the_authority_never_saw_abstains():
    c = one(nomination(ink=("g1", "ghost")), [record((100.0, 304.0))], inv=inventory(ink=("g1",)))
    assert c.status is ABST and shadow.STRIP_INK_NOT_IN_STROKE_INVENTORY in c.reason_codes


@pytest.mark.parametrize("box, blocked", [
    ((150.0, 199.0, 155.0, 201.0), True),         # inside the strip
    ((150.0, 190.0, 155.0, 196.0), False),        # below the strip band and the glass band
    ((80.0, 199.0, 99.0, 201.0), False),          # beside the strip
    ((304.0, 199.0, 310.0, 201.0), True),         # touching the end of the frame
    ((150.0, 203.0, 155.0, 208.0), True),         # touching the strip band
    ((150.0, 150.0, 155.0, 160.0), False),        # unrelated
])
def test_source_ink_the_producer_did_not_admit_inside_the_strip_region_abstains(box, blocked):
    c = one(nomination(), [record((100.0, 304.0))], inv=inventory(boxes=[box]))
    assert (c.status is ABST) is blocked
    assert (shadow.UNADMITTED_INK_IN_STRIP_REGION in c.reason_codes) is blocked


def test_the_wall_band_of_the_equal_record_widens_the_unadmitted_ink_region():
    wide = record((100.0, 304.0), band=(199.0, 202.72))
    nom = nomination(band=(198.0, 204.0))
    assert one(nom, [wide], inv=inventory(boxes=[(150.0, 204.5, 155.0, 206.0)])).status is CAND
    assert one(nom, [wide], inv=inventory(boxes=[(150.0, 203.0, 155.0, 206.0)])).status is ABST


# ---- the nomination --------------------------------------------------------------------------------------------
def test_an_incomplete_strip_extent_abstains():
    assert one(nomination(extent_complete=False), [record((100.0, 304.0))]).status is ABST


def test_a_strip_claimed_by_two_different_callouts_abstains_and_keeps_both_claims():
    claims = (shadow.CalloutClaim("W1", "tag-1", "corr-1"), shadow.CalloutClaim("W2", "tag-2", "corr-2"))
    c = one(nomination(claims=claims), [record((100.0, 304.0))])
    assert c.status is ABST and shadow.STRIP_CLAIMED_BY_MULTIPLE_CALLOUTS in c.reason_codes and len(c.claims) == 2


@pytest.mark.parametrize("bad", [
    {"axis": "x"}, {"axis": "h"}, {"band": (5.0, 5.0)}, {"band": (float("nan"), 1.0)}, {"frame_along": (304.0, 100.0)},
    {"frame_along": (0.0, float("inf"))}, {"ink_ids": ()}, {"ink_ids": ("a", "a")}, {"ink_ids": ("",)},
    {"claims": ()}, {"extent_complete": 1}, {"strip_id": ""},
])
def test_a_malformed_nomination_abstains_with_a_typed_reason(bad):
    nom = replace(nomination(), **bad)
    c = one(nom, [record((100.0, 304.0))])
    assert c.status is ABST and c.reason_codes == (shadow.STRIP_NOMINATION_INVALID,)


def test_a_strip_is_nominated_once():
    with pytest.raises(ValueError):
        evaluate([nomination(), nomination()], [record((100.0, 304.0))])


@pytest.mark.parametrize("quantum", [0.0, -1.0, float("nan"), float("inf"), True, None, "0.24"])
def test_the_coordinate_quantum_must_be_a_positive_finite_number(quantum):
    with pytest.raises(ValueError):
        evaluate(nomination(), [record((100.0, 304.0))], quantum=quantum)


# ---- the page ----------------------------------------------------------------------------------------------------
def test_a_record_of_this_page_with_foreign_ownership_makes_the_whole_page_abstain():
    foreign = record((100.0, 304.0), own=shadow.ApertureOwnership("doc-2", "rev-1", "snap-1", "a" * 64, "7"))
    out = evaluate([nomination(), nomination(strip_id="strip-2")], [foreign, record((100.0, 304.0))])
    assert shadow.APERTURE_RECORD_OWNERSHIP_MISMATCH in out.page_reason_codes
    assert all(c.status is ABST for c in out.correspondences)


@pytest.mark.parametrize("field", ["revision_id", "snapshot_id", "source_sha256"])
def test_every_ownership_field_of_every_page_record_is_checked(field):
    wrong = replace(record((100.0, 304.0)), **{field: "other"})
    out = evaluate(nomination(), [wrong])
    assert shadow.APERTURE_RECORD_OWNERSHIP_MISMATCH in out.page_reason_codes


def test_a_foreign_subdivision_of_this_page_also_makes_the_page_abstain():
    foreign = sub((160.0, 162.0), own=shadow.ApertureOwnership("doc-2", "rev-1", "snap-1", "a" * 64, "7"))
    out = evaluate(nomination(), [record((100.0, 304.0))], [foreign])
    assert shadow.APERTURE_RECORD_OWNERSHIP_MISMATCH in out.page_reason_codes


def test_records_of_another_page_are_ignored_whatever_their_ownership():
    other_page = replace(record((100.0, 304.0), rid="p9"), page_id="9", document_id="elsewhere")
    out = evaluate(nomination(), [record((100.0, 304.0)), other_page])
    assert out.correspondences[0].status is CAND and out.aperture_record_count == 1


@pytest.mark.parametrize("bad", [
    {"aperture_span_along": (float("nan"), 5.0)}, {"aperture_span_along": (10.0, 10.0)},
    {"aperture_span_along": (10.0, 5.0)}, {"wall_band_across": (1.0, float("inf"))}, {"axis": "Z"},
    {"record_id": ""}, {"aperture_span_along": (1e13, 2e13)}, {"aperture_span_along": (True, 5.0)},
])
def test_an_invalid_aperture_record_makes_the_page_abstain_instead_of_being_guessed_around(bad):
    out = evaluate(nomination(), [record((100.0, 304.0)), replace(record((100.0, 304.0), rid="other"), **bad)])
    assert shadow.APERTURE_RECORD_INVALID in out.page_reason_codes
    assert all(c.status is ABST for c in out.correspondences)


def test_two_subdivisions_that_share_one_id_are_not_a_usable_cut():
    a, b = sub((160.0, 162.0), sid="dup"), sub((200.0, 202.0), sid="dup")
    out = evaluate(nomination(), [record((100.0, 304.0))], [a, b])
    assert shadow.APERTURE_RECORD_INVALID in out.page_reason_codes and out.correspondences[0].status is ABST


def test_the_budgets_abstain_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(shadow, "_MAX_RECORDS", 2)
    out = evaluate(nomination(), [record((100.0, 304.0)), record((1.0, 2.0), rid="b"), record((3.0, 4.0), rid="c")])
    assert shadow.APERTURE_BUDGET_EXCEEDED_CODE in out.page_reason_codes
    monkeypatch.setattr(shadow, "_MAX_STRIPS", 1)
    out = evaluate([nomination(), nomination(strip_id="s2")], [])
    assert shadow.APERTURE_BUDGET_EXCEEDED_CODE in out.page_reason_codes and len(out.correspondences) == 2


# ---- invariance ------------------------------------------------------------------------------------------------
def _scenario():
    whole, posts = clean_window()
    runs = [record((100.0, 162.0), rid="a"), record((160.0, 232.0), rid="b"), record((230.0, 304.0), rid="c"),
            record((100.0, 200.0), rid="odd"), record((250.0, 400.0), rid="next", status=ABST, reasons=(WALL_CONTINUITY_MISSING,)),
            record((20.0, 380.0), rid="long")]
    nom2 = nomination(frame=(500.0, 704.0), band=(197.0, 203.0), strip_id="strip-2", ink=("h1", "h2"),
                      claims=(shadow.CalloutClaim("W2", "tag-2", "corr-2"),))
    second = record((500.0, 704.0), rid="second")
    inv = inventory(ink=INK + ("h1", "h2"), boxes=[(150.0, 190.0, 155.0, 196.0), (900.0, 199.0, 905.0, 201.0)])
    return [nomination(), nom2], [whole, *runs, second], posts, inv


def test_the_scenario_has_the_mixed_results_the_invariance_tests_rely_on():
    sig = signature(evaluate(*_scenario()))
    assert [row[1] for row in sig] == [CONF, CAND]


@pytest.mark.parametrize("kwargs", [
    {"along": 1000.0}, {"across": -37.5}, {"along": 12.5, "across": 100.0}, {"scale": 2.0}, {"swap_axes": True},
    {"scale": 0.5, "swap_axes": True, "along": 8.0},
])
def test_translation_axis_exchange_and_uniform_scale_do_not_change_any_decision(kwargs):
    base = _scenario()
    moved = transform(base, **kwargs)
    quantum = Q * kwargs.get("scale", 1.0)
    assert signature(evaluate(*moved, quantum=quantum)) == signature(evaluate(*base))


def test_input_order_does_not_change_any_decision_or_id():
    noms, records, subs, inv = _scenario()
    expected = evaluate(noms, records, subs, inv)
    rng = random.Random(7)
    for _ in range(6):
        shuffled = (rng.sample(noms, len(noms)), rng.sample(records, len(records)), rng.sample(subs, len(subs)), inv)
        got = evaluate(*shuffled)
        assert sorted(got.correspondences, key=lambda c: c.strip_id) == sorted(expected.correspondences, key=lambda c: c.strip_id)


def test_splitting_the_strip_ink_into_more_admitted_segments_does_not_change_the_decision():
    noms, records, subs, inv = _scenario()
    split = [replace(noms[0], ink_ids=INK + tuple(f"{i}-part{k}" for i in INK for k in (1, 2)))] + noms[1:]
    inv2 = replace(inv, admitted_observation_ids=inv.admitted_observation_ids | {f"{i}-part{k}" for i in INK for k in (1, 2)})
    assert signature(evaluate(split, records, subs, inv2)) == signature(evaluate(noms, records, subs, inv))


def test_unrelated_content_and_a_wider_page_do_not_change_any_decision_or_id():
    noms, records, subs, inv = _scenario()
    base = evaluate(noms, records, subs, inv)
    extra = [record((2000.0 + 10 * k, 2100.0 + 10 * k), band=(5000.0, 5000.72), rid=f"junk-{k}") for k in range(40)]
    extra += [record((100.0, 304.0), axis="V", rid="v-junk"), replace(record((100.0, 304.0), rid="p3"), page_id="3")]
    more_boxes = tuple((x, y, x + 3.0, y + 3.0) for x, y in ((5000.0, 5000.0), (-900.0, 40.0), (1e4, 1e4)))
    wider = replace(inv, unadmitted_ink=inv.unadmitted_ink + tuple(shadow.InkItem(b, None, True) for b in more_boxes))
    got = evaluate(noms, records + extra, subs + [sub((3000.0, 3002.0), sid="far-sub")], wider)
    assert got.correspondences == base.correspondences


def test_replay_is_deterministic_and_ids_are_stable():
    first = evaluate(*_scenario())
    second = evaluate(*_scenario())
    assert first == second
    ids = {c.record_id for c in first.correspondences}
    assert len(ids) == 2 and all(i.startswith("shadow_strip_whole_aperture_correspondence_") for i in ids)
    assert one(nomination(), [record((100.0, 304.0))]).record_id == "shadow_strip_whole_aperture_correspondence_" + \
        one(nomination(), [record((100.0, 304.0))]).record_id.rsplit("_", 1)[1]


def test_a_changed_decision_changes_the_correspondence_id():
    assert one(nomination(), [record((100.0, 304.0))]).record_id != one(nomination(), []).record_id


def test_nothing_the_caller_passed_in_is_mutated():
    noms, records, subs, inv = _scenario()
    snapshot = copy.deepcopy((noms, records, subs, inv))
    evaluate(noms, records, subs, inv)
    assert (noms, records, subs, inv) == snapshot


# ---- the receipts ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("flag", shadow._GRANT_FLAGS)
def test_the_page_receipt_refuses_every_grant(flag):
    out = evaluate(nomination(), [record((100.0, 304.0))])
    with pytest.raises(ValueError):
        replace(out, **{flag: True})


def test_the_page_receipt_must_stay_in_shadow_and_carry_the_fixed_limits():
    out = evaluate(nomination(), [record((100.0, 304.0))])
    with pytest.raises(ValueError):
        replace(out, shadow_only=False)
    with pytest.raises(ValueError):
        replace(out, standing_limits=())


def test_a_candidate_cannot_be_forged_with_a_rival_or_without_one_equal_record():
    c = one(nomination(), [record((100.0, 304.0))])
    with pytest.raises(ValueError):
        replace(c, unvetoed_rival_record_ids=("x",))
    with pytest.raises(ValueError):
        replace(c, equal_record_ids=())
    with pytest.raises(ValueError):
        replace(c, linkage_basis=None)
    with pytest.raises(ValueError):
        replace(c, reason_codes=(shadow.NO_EQUAL_EXTENT_APERTURE,))


# ---- the bridge from the nominator's receipt ---------------------------------------------------------------------
def _strip(strip_id, **kw):
    base = dict(strip_id=strip_id, axis="H", band=(197.0, 203.0), frame_along=(100.0, 304.0), extent_complete=True,
                ink_ids=("a", "b"), plan_viewport_id="vp")
    base.update(kw)
    return SimpleNamespace(**base)


def _corr(mark, strip_id, status=CAND, obs=None, rec=None):
    return SimpleNamespace(tag_mark=mark, tag_observation_id=obs or f"obs-{mark}", status=status, strip_id=strip_id,
                           record_id=rec or f"rec-{mark}")


def test_only_strips_a_candidate_callout_names_are_nominated_and_every_claim_is_kept():
    receipt = SimpleNamespace(strips=(_strip("s1"), _strip("s2"), _strip("s3")), correspondences=(
        _corr("W2", "s1"), _corr("W1", "s1"), _corr("W3", "s2", status=ABST), _corr("W4", None, status=CAND)))
    noms = shadow.nominations_from_callout_receipt(receipt)
    assert [n.strip_id for n in noms] == ["s1"]
    assert [c.tag_mark for c in noms[0].claims] == ["W1", "W2"]
    assert noms[0].ink_ids == ("a", "b") and noms[0].plan_viewport_id == "vp"


def test_a_receipt_with_a_repeated_strip_id_is_refused():
    with pytest.raises(ValueError):
        shadow.nominations_from_callout_receipt(SimpleNamespace(strips=(_strip("s1"), _strip("s1")), correspondences=()))


# ---- paint order of source ink the producer could not admit -----------------------------------------------------------
def _fill(sequence, box=(150.0, 199.0, 155.0, 201.0), stroked=False):
    return shadow.InkItem(box, sequence, stroked)


def _ink(sequence, box=(120.0, 200.0, 140.0, 200.72)):
    return shadow.InkItem(box, sequence, True)


def test_an_unstroked_fill_painted_before_every_admitted_item_of_the_region_cannot_cover_them():
    inv = inventory(unadmitted=[_fill(5)], admitted_ink=[_ink(10), _ink(40)])
    c = one(nomination(), [record((100.0, 304.0))], inv=inv)
    assert c.status is CAND


@pytest.mark.parametrize("pending, admitted", [
    (_fill(10), [_ink(10), _ink(40)]),                    # painted at the same point as an admitted item
    (_fill(11), [_ink(10), _ink(40)]),                    # painted after an admitted item: it may cover it
    (_fill(None), [_ink(10)]),                            # no readable position in the paint order
    (_fill(5, stroked=True), [_ink(10)]),                 # unadmitted stroked ink is real ink, not a backdrop
    (_fill(5), []),                                       # nothing admitted in the region to compare with
    (_fill(5), [_ink(None)]),                             # an admitted item with no readable position
])
def test_every_other_unadmitted_item_in_the_region_still_stops_the_correspondence(pending, admitted):
    c = one(nomination(), [record((100.0, 304.0))], inv=inventory(unadmitted=[pending], admitted_ink=admitted))
    assert c.status is ABST and shadow.UNADMITTED_INK_IN_STRIP_REGION in c.reason_codes


def test_admitted_ink_outside_the_region_does_not_define_the_paint_order_comparison():
    far = _ink(1, box=(900.0, 200.0, 920.0, 200.72))
    inv = inventory(unadmitted=[_fill(5)], admitted_ink=[_ink(10), far])
    assert one(nomination(), [record((100.0, 304.0))], inv=inv).status is CAND


def test_one_late_unadmitted_item_among_early_ones_still_stops_the_correspondence():
    inv = inventory(unadmitted=[_fill(2), _fill(3), _fill(99, box=(200.0, 199.0, 210.0, 201.0))], admitted_ink=[_ink(10)])
    assert one(nomination(), [record((100.0, 304.0))], inv=inv).status is ABST


def test_the_paint_order_comparison_does_not_depend_on_item_order():
    items = [_fill(2), _fill(3)]
    admitted = [_ink(10), _ink(30), _ink(20)]
    rng = random.Random(3)
    for _ in range(5):
        inv = inventory(unadmitted=rng.sample(items, 2), admitted_ink=rng.sample(admitted, 3))
        assert one(nomination(), [record((100.0, 304.0))], inv=inv).status is CAND


def test_an_admitted_fill_in_the_region_does_not_define_the_paint_order_comparison():
    background = shadow.InkItem((0.0, 0.0, 900.0, 900.0), 1, False)           # for example a page-sized white fill
    inv = inventory(unadmitted=[_fill(5)], admitted_ink=[background, _ink(10)])
    assert one(nomination(), [record((100.0, 304.0))], inv=inv).status is CAND
    inv = inventory(unadmitted=[_fill(5)], admitted_ink=[background])            # no admitted stroke to compare with
    assert one(nomination(), [record((100.0, 304.0))], inv=inv).status is ABST


def test_each_relation_reports_how_far_its_ends_are_from_the_strip_without_using_it_to_decide():
    whole, posts = clean_window()
    near = record((100.96, 304.0), rid="near-miss")          # an end just over one stroke width inside the strip
    c = one(nomination(), [whole, near], posts)
    offsets = {r.record_id: r.end_offsets for r in c.relations}
    assert offsets["near-miss"] == (0.96, 0.0) and offsets[whole.record_id] == (0.0, 0.0)
    assert c.status is CONF and shadow.NESTED_APERTURES_NOT_VETOED in c.reason_codes
