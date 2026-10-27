"""Pure core of the plan tag -> opening occupancy shadow: containment, uniqueness, no ranking, invariants."""
from __future__ import annotations

import math
import random
from dataclasses import replace

import pytest

import pb_plan_tag_opening_occupancy_shadow as M
from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_source_plan_glazing_strip_callout_shadow import (
    OCCUPANCY_BASIS_ENVELOPE, OCCUPANCY_BASIS_TEXT, PRODUCER_INPUT_PROVENANCE, SourceOwnership,
)

OWN = SourceOwnership("doc", "rev", "snap", "a" * 64, PRODUCER_INPUT_PROVENANCE)
AX, NM = (1.0, 0.0), (0.0, 1.0)


def frame(x0, x1, y0, y1, axis=AX, normal=NM):
    return M.ApertureFrame(axis=axis, normal=normal, along=(x0, x1), normal_range=(y0, y1))


def cand(cid, x0, x1, y0, y1, members=None, **kw):
    return M.CandidateAperture(cid, tuple(sorted(members or (f"{cid}-m{i}" for i in range(6)))), frame(x0, x1, y0, y1, **kw))


def anchor(word, cx, cy, half=3.0, basis=OCCUPANCY_BASIS_ENVELOPE):
    return M.TagAnchor(word, (cx - half, cy - half, cx + half, cy + half), basis)


def proven(candidate, record="rec", status=S.CORROBORATED, ids=None, fr=None):
    return M.ExistenceFact(status, record if status is S.CORROBORATED else None,
                           tuple(ids if ids is not None else candidate.member_observation_ids),
                           fr if fr is not None else candidate.frame)


def run(candidates, anchors, facts=None, calls=None):
    facts = facts or {}

    def existence_for(c):
        if calls is not None:
            calls.append(c.candidate_id)
        return facts.get(c.candidate_id, proven(c, record="rec-" + c.candidate_id))
    return M.evaluate_occupancy(ownership=OWN, candidates=candidates, anchors=anchors, existence_for=existence_for)


def outcome(diags, word):
    return next(d.outcome for d in diags if d.word_observation_id == word)


# ------------------------------------------------------------------------------------
# the relation itself
# ------------------------------------------------------------------------------------

def test_an_anchor_inside_exactly_one_corroborated_aperture_is_occupied():
    c = cand("c1", 100, 140, 100, 110)
    occ, diags = run([c], [anchor("w", 120, 105)])
    assert [o.word_observation_id for o in occ] == ["w"] and outcome(diags, "w") == M.OUTCOME_OCCUPIED
    o = occ[0]
    assert o.occupied_record_id == "rec-c1" and o.occupied_observation_ids == c.member_observation_ids
    assert (o.aperture_along, o.aperture_normal_range, o.competing_candidate_count) == ((100, 140), (100, 110), 0)
    assert o.basis == OCCUPANCY_BASIS_ENVELOPE and o.ownership == OWN


def test_an_anchor_in_no_aperture_is_not_occupied_and_asks_the_producer_nothing():
    calls = []
    occ, diags = run([cand("c1", 100, 140, 100, 110)], [anchor("w", 300, 105)], calls=calls)
    assert occ == () and outcome(diags, "w") == M.OUTCOME_NONE and calls == []


def test_the_centre_decides_not_overlap():
    c = cand("c1", 100, 140, 100, 110)
    # the box overlaps the band but its centre is 0.5 outside the face band: the binder's rule says not contained
    _, diags = run([c], [M.TagAnchor("w", (110.0, 109.0, 130.0, 112.0), OCCUPANCY_BASIS_TEXT)])
    assert outcome(diags, "w") == M.OUTCOME_NONE
    _, diags = run([c], [M.TagAnchor("w", (110.0, 108.0, 130.0, 112.0), OCCUPANCY_BASIS_TEXT)])
    assert outcome(diags, "w") == M.OUTCOME_OCCUPIED


@pytest.mark.parametrize("cx,cy,inside", [
    (100.0, 105.0, True), (140.0, 105.0, True), (120.0, 100.0, True), (120.0, 110.0, True),
    (100.0 - 1e-7, 105.0, True), (140.0 + 1e-7, 105.0, True),
    (100.0 - 1e-5, 105.0, False), (140.0 + 1e-5, 105.0, False), (120.0, 100.0 - 1e-5, False), (120.0, 110.0 + 1e-5, False),
])
def test_the_boundary_follows_the_binders_tolerance(cx, cy, inside):
    c = cand("c1", 100, 140, 100, 110)
    _, diags = run([c], [M.TagAnchor("w", (cx, cy, cx, cy), OCCUPANCY_BASIS_TEXT)])
    assert (outcome(diags, "w") == M.OUTCOME_OCCUPIED) is inside


def test_containment_is_the_binders_own_function_on_random_frames_and_boxes():
    import pb_schedule_opening_instance_binding_authority as binder
    rng = random.Random(11)
    for _ in range(400):
        theta = rng.uniform(0, 2 * math.pi)
        axis = (math.cos(theta), math.sin(theta))
        normal = (-axis[1], axis[0])
        a0, n0 = rng.uniform(-200, 200), rng.uniform(-200, 200)
        a1, n1 = a0 + rng.uniform(1, 80), n0 + rng.uniform(1, 40)
        f = M.ApertureFrame(axis=axis, normal=normal, along=(a0, a1), normal_range=(n0, n1))
        ap = binder._OpeningAperture(axis=axis, normal=normal, along_min=a0, along_max=a1, normal_min=n0, normal_max=n1)
        x0, y0 = rng.uniform(-300, 300), rng.uniform(-300, 300)
        box = (x0, y0, x0 + rng.uniform(0, 30), y0 + rng.uniform(0, 30))
        assert M.frame_contains(f, box) == binder._aperture_contains_bbox(ap, box)
    assert M._CONTAINMENT_TOL == binder._COORD_TOL


# ------------------------------------------------------------------------------------
# uniqueness: contested, uncorroborated, mismatched; nothing is ranked
# ------------------------------------------------------------------------------------

def test_an_anchor_in_two_apertures_is_contested_even_when_both_are_corroborated():
    a, b = cand("c1", 100, 140, 100, 110), cand("c2", 90, 150, 95, 115)
    occ, diags = run([a, b], [anchor("w", 120, 105)])
    assert occ == () and outcome(diags, "w") == M.OUTCOME_CONTESTED
    assert next(d for d in diags if d.word_observation_id == "w").containing_candidate_ids == ("c1", "c2")


def test_a_corroborated_aperture_does_not_win_over_a_conflicting_one_that_also_contains_the_anchor():
    a, b = cand("c1", 100, 140, 100, 110), cand("c2", 90, 150, 95, 115)
    facts = {"c1": proven(a), "c2": M.ExistenceFact(S.CONFLICT, None, (), None)}
    occ, diags = run([a, b], [anchor("w", 120, 105)], facts)
    assert occ == () and outcome(diags, "w") == M.OUTCOME_CONTESTED
    assert dict(next(d for d in diags).containing_existence) == {"c1": "corroborated", "c2": "conflict"}


@pytest.mark.parametrize("status", [S.ABSTAINED, S.CONFLICT, S.CANDIDATE])
def test_a_single_containing_aperture_that_is_not_corroborated_does_not_occupy(status):
    c = cand("c1", 100, 140, 100, 110)
    occ, diags = run([c], [anchor("w", 120, 105)], {"c1": M.ExistenceFact(status, None, (), None)})
    assert occ == () and outcome(diags, "w") == M.OUTCOME_NOT_CORROBORATED


@pytest.mark.parametrize("status", [S.ABSTAINED, S.CONFLICT, S.CANDIDATE])
def test_a_status_that_is_not_corroborated_never_occupies_even_when_a_record_id_is_attached(status):
    c = cand("c1", 100, 140, 100, 110)
    fact = M.ExistenceFact(status, "rec-x", c.member_observation_ids, c.frame)
    occ, diags = run([c], [anchor("w", 120, 105)], {"c1": fact})
    assert occ == () and outcome(diags, "w") == M.OUTCOME_NOT_CORROBORATED


def test_a_corroborated_status_without_a_record_id_does_not_occupy():
    c = cand("c1", 100, 140, 100, 110)
    occ, diags = run([c], [anchor("w", 120, 105)], {"c1": M.ExistenceFact(S.CORROBORATED, None, (), None)})
    assert occ == () and outcome(diags, "w") == M.OUTCOME_NOT_CORROBORATED


def test_a_record_that_is_not_the_candidate_it_was_proven_from_does_not_occupy():
    c = cand("c1", 100, 140, 100, 110)
    for facts in (
        {"c1": proven(c, ids=("x", "y"))},                                          # different observations
        {"c1": proven(c, ids=c.member_observation_ids[:-1])},                      # a subset
        {"c1": proven(c, ids=c.member_observation_ids + ("extra",))},             # a superset
        {"c1": proven(c, ids=c.member_observation_ids + (c.member_observation_ids[0],))},   # a duplicate
        {"c1": proven(c, fr=frame(100, 140, 120, 130))},                          # its own aperture excludes the anchor
        {"c1": M.ExistenceFact(S.CORROBORATED, "rec", c.member_observation_ids, None)},   # no aperture
    ):
        occ, diags = run([c], [anchor("w", 120, 105)], facts)
        assert occ == () and outcome(diags, "w") == M.OUTCOME_RECORD_MISMATCH


def test_existence_is_read_once_per_candidate_and_only_for_candidates_that_contain_an_anchor():
    a, b, far = cand("c1", 100, 140, 100, 110), cand("c2", 100, 140, 100, 110), cand("c3", 500, 540, 100, 110)
    calls = []
    run([a, b, far], [anchor("w1", 120, 105), anchor("w2", 125, 106)], calls=calls)
    assert sorted(calls) == ["c1", "c2"]


def test_many_anchors_are_each_decided_independently():
    c1, c2 = cand("c1", 100, 140, 100, 110), cand("c2", 300, 340, 100, 110)
    occ, diags = run([c1, c2], [anchor("a", 120, 105), anchor("b", 320, 105), anchor("c", 700, 105)])
    assert {o.word_observation_id: o.occupied_record_id for o in occ} == {"a": "rec-c1", "b": "rec-c2"}
    assert outcome(diags, "c") == M.OUTCOME_NONE


def test_two_anchors_in_one_aperture_both_occupy_it():
    c = cand("c1", 100, 140, 100, 110)
    occ, _ = run([c], [anchor("a", 110, 105), anchor("b", 130, 105)])
    assert {o.word_observation_id for o in occ} == {"a", "b"} and {o.occupied_record_id for o in occ} == {"rec-c1"}


# ------------------------------------------------------------------------------------
# metamorphic, ordering, determinism
# ------------------------------------------------------------------------------------

def _world(dx=0.0, dy=0.0, scale=1.0):
    def f(x0, x1, y0, y1):
        return cand_scaled(x0, x1, y0, y1)

    def cand_scaled(x0, x1, y0, y1):
        return (x0 * scale + dx, x1 * scale + dx, y0 * scale + dy, y1 * scale + dy)
    cs = [cand(f"c{i}", *f(100 + 60 * i, 140 + 60 * i, 100, 110)) for i in range(4)]
    cs.append(cand("big", *f(90, 400, 95, 115)))                    # overlaps every other aperture
    anchors = [anchor("a", 120 * scale + dx, 105 * scale + dy, half=3 * scale),
               anchor("b", 180 * scale + dx, 105 * scale + dy, half=3 * scale),
               anchor("none", 20 * scale + dx, 50 * scale + dy, half=3 * scale)]
    return cs, anchors


def _summary(occ, diags):
    return ({o.word_observation_id: o.occupied_record_id for o in occ}, {d.word_observation_id: d.outcome for d in diags})


@pytest.mark.parametrize("dx,dy,scale", [(37.0, -11.0, 1.0), (0.0, 0.0, 2.0), (-500.0, 250.0, 0.5)])
def test_translation_and_scale_do_not_change_any_outcome(dx, dy, scale):
    assert _summary(*run(*_world())) == _summary(*run(*_world(dx, dy, scale)))


def test_a_quarter_turn_of_every_frame_and_anchor_does_not_change_any_outcome():
    cs, anchors = _world()
    turned_c = [M.CandidateAperture(c.candidate_id, c.member_observation_ids,
                                    M.ApertureFrame(axis=(0.0, 1.0), normal=(-1.0, 0.0), along=c.frame.along,
                                                    normal_range=c.frame.normal_range))
                for c in cs]
    turned_a = [M.TagAnchor(a.word_observation_id, (-a.anchor_box[3], a.anchor_box[0], -a.anchor_box[1], a.anchor_box[2]), a.basis)
                for a in anchors]
    assert _summary(*run(cs, anchors)) == _summary(*run(turned_c, turned_a))


def test_input_order_does_not_change_the_result():
    cs, anchors = _world()
    base = run(cs, anchors)
    rng = random.Random(3)
    for _ in range(6):
        a, b = list(cs), list(anchors)
        rng.shuffle(a); rng.shuffle(b)
        assert run(a, b) == base


def test_replay_is_identical_and_inputs_are_not_mutated():
    cs, anchors = _world()
    before = (list(cs), list(anchors))
    assert run(cs, anchors) == run(cs, anchors)
    assert (cs, anchors) == before


def test_unrelated_far_candidates_do_not_change_an_anchors_outcome():
    cs, anchors = _world()
    extra = [cand(f"far{i}", 5000 + 10 * i, 5030 + 10 * i, 5000, 5010) for i in range(30)]
    assert _summary(*run(cs + extra, anchors)) == _summary(*run(cs, anchors))


# ------------------------------------------------------------------------------------
# validation and the no-grant contract
# ------------------------------------------------------------------------------------

def test_duplicate_anchors_duplicate_candidates_and_a_frameless_candidate_are_refused():
    c = cand("c1", 100, 140, 100, 110)
    with pytest.raises(ValueError):
        run([c], [anchor("w", 120, 105), anchor("w", 121, 105)])
    with pytest.raises(ValueError):
        run([c, c], [anchor("w", 120, 105)])
    with pytest.raises(ValueError):
        run([M.CandidateAperture("c9", ("m",), None)], [anchor("w", 120, 105)])


@pytest.mark.parametrize("bad", [
    dict(word_observation_id=""), dict(basis="nearest"), dict(anchor_box=(1.0, 1.0, 0.0, 0.0)),
    dict(anchor_box=(0.0, 0.0, math.inf, 1.0)), dict(anchor_box=(0.0, 0.0, 1.0)),
])
def test_a_malformed_anchor_cannot_be_built(bad):
    args = dict(word_observation_id="w", anchor_box=(0.0, 0.0, 1.0, 1.0), basis=OCCUPANCY_BASIS_TEXT)
    args.update(bad)
    with pytest.raises(ValueError):
        M.TagAnchor(**args)


def _inventory(**kw):
    c = cand("c1", 100, 140, 100, 110)
    occ, diags = run([c], [anchor("w", 120, 105)])
    return M._inventory(OWN, S.CANDIDATE, (M.OCCUPANCY_CENSUS_PRODUCED,), 1, occ, diags)


def test_every_grant_flag_is_false_and_enforced():
    inv = _inventory()
    assert inv.shadow_only is True and inv.status is S.CANDIDATE and inv.record_id
    for name in M._GRANT_FLAGS:
        assert getattr(inv, name) is False
        with pytest.raises(ValueError):
            replace(inv, **{name: True})
    with pytest.raises(ValueError):
        replace(inv, shadow_only=False)
    with pytest.raises(ValueError):
        replace(inv, status=S.CORROBORATED)
    with pytest.raises(ValueError):
        replace(inv, status=S.CONFLICT)


def test_an_abstained_inventory_carries_no_occupancy_or_diagnostic_and_no_record_id():
    inv = M._inventory(OWN, S.ABSTAINED, (M.OCCUPANCY_DISABLED,), 0, (), ())
    assert inv.occupancies == () and inv.diagnostics == () and inv.record_id is None
    with pytest.raises(ValueError):
        replace(inv, occupancies=_inventory().occupancies)


def test_the_occupancies_and_the_occupied_diagnostics_must_name_the_same_words():
    inv = _inventory()
    with pytest.raises(ValueError):
        replace(inv, occupancies=())
    with pytest.raises(ValueError):
        replace(inv, diagnostics=())


def test_the_record_id_binds_the_outcomes_and_is_stable():
    c = cand("c1", 100, 140, 100, 110)
    a = M._inventory(OWN, S.CANDIDATE, ("x",), 1, *run([c], [anchor("w", 120, 105)]))
    b = M._inventory(OWN, S.CANDIDATE, ("x",), 1, *run([c], [anchor("w", 120, 105)]))
    other = M._inventory(OWN, S.CANDIDATE, ("x",), 1, *run([c], [anchor("w", 300, 105)]))
    assert a.record_id == b.record_id != other.record_id


def test_the_standing_limits_say_what_an_occupancy_is_not():
    assert M.TAG_TYPE_VS_INSTANCE_UNPROVED in M.STANDING_LIMITS
    assert M.OCCUPANCY_IS_LOCATION_NOT_KIND_OR_HOST in M.STANDING_LIMITS
