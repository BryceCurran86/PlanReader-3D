"""Bounded wall equivalence (default off; MAX 7240613240). Real resolver baseline, synthetic walls and paint."""
from __future__ import annotations

import copy
import random
from dataclasses import replace

import fitz
import pytest

from pb_bounded_wall_equivalence_shadow import (
    AMBIGUITY_BLOCKER,
    CONFLICT_BLOCKER,
    COVERED_FACE,
    KEPT_CONFLICT,
    KEPT_DIRECT,
    KEPT_NO_BODY,
    KEPT_NON_WALL,
    KEPT_PARTIAL_FACES,
    KEPT_PUBLISHED_FACE,
    KEPT_SEVERAL_BODIES,
    RELEASED,
    SourceWallBody,
    release_bounded_equivalence,
    source_wall_bodies,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _apply_trusted_relation_overrides,
    _decision_scope_id,
)
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    resolve_physical_wall_equivalence,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def wall(name, a, b, paths, viewport="v1"):
    prims = tuple(f"d{p}i0" if isinstance(p, int) else p for p in paths)
    return PhysicalWallIdentity(
        wall_candidate_id=name, viewport_id=viewport, candidate_identity_id=f"id-{name}",
        path_fingerprint=(a, b), source_primitive_ids=prims, edge_ids=(name,),
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def h(name, y, paths, x0=0.0, x1=100.0, **kw):
    return wall(name, (x0, y), (x1, y), paths, **kw)


def body(c0, c1, paths, along=(0.0, 100.0), horizontal=True):
    return SourceWallBody(horizontal, along, (c0, c1), frozenset(paths))


def run(identities, bodies, non_wall=()):
    baseline = resolve_physical_wall_equivalence(identities)
    result, counts, released = release_bounded_equivalence(identities, baseline, bodies, typed_non_wall_ids=non_wall)
    assert set(baseline.representative_wall_ids) <= set(result.representative_wall_ids)
    groups = [set(g) for g in result.equivalence_groups]
    for before_pair, after_pair in zip(baseline.pair_classifications, result.pair_classifications):
        if before_pair != after_pair:  # only faces of one released body become the same wall
            assert after_pair[:2] == before_pair[:2] and after_pair[2] == "same_physical_wall"
            assert any(set(after_pair[:2]) <= g for g in groups)
    assert len(baseline.pair_classifications) == len(result.pair_classifications)
    return baseline, result, counts, released


def test_a_chain_releases_only_the_wall_without_a_direct_rival():
    identities = [h("a", 0.0, [1]), h("b", 6.0, [2]), h("c", 200.0, [3])]
    baseline, result, counts, released = run(identities, [body(0.0, 3.0, {1, 11}), body(200.0, 203.0, {3, 13})])
    assert baseline.representative_wall_ids == ()  # one ambiguous component today
    assert released == ("c",) and counts == {RELEASED: 1, KEPT_DIRECT: 1, KEPT_NO_BODY: 1}
    assert "c" not in result.ambiguous_wall_ids and result.blockers_for("c") == ()


@pytest.mark.parametrize("identities,bodies", [
    ([h("a", 0.0, [1]), h("b", 5.0, [2])], []),  # two lines, no painted body
    ([h("a", 0.0, [1]), h("b", 9.0, [2])], [body(0.0, 6.0, {1}), body(9.0, 14.0, {2})]),  # cavity leaves
    ([h("a", 0.0, [1]), h("b", 5.0, [2])], [body(0.0, 2.0, {1}), body(5.0, 7.0, {2})]),  # narrow leaves 3 apart
    ([h("a", 0.0, [1]), h("b", 300.0, [2], viewport="v2")], [body(0.0, 3.0, {1}), body(300.0, 303.0, {2})]),
    ([h("a", 0.0, [1]), h("b", 5.0, [2])], [body(0.0, 2.0, {1}), body(5.0, 11.0, {2})]),  # a thick neighbour
    ([h("a", 0.0, [1]), h("b", 7.0, [2])], [body(0.0, 2.0, {1}), body(7.0, 13.0, {2})]),  # thick, wider apart
    ([h("a", 0.0, [1]), h("b", 10.0, [2])], [body(0.0, 2.0, {1}), body(10.0, 22.0, {2})]),  # only its width reaches
    ([h("a", 0.0, [1, 9]), h("b", 300.0, [9])], [body(0.0, 3.0, {1, 9})]),  # shared source paint
], ids=["no_body", "cavity", "narrow_close", "other_viewport", "thick_close",
        "thick_apart", "thick_reach", "shared_paint"])
def test_true_competitors_stay_abstained(identities, bodies):
    _baseline, _result, _counts, released = run(identities, bodies)
    assert released == ()


FACES = [body(0.0, 3.0, {1, 2})]


@pytest.mark.parametrize("identities", [
    [h("a", 0.0, [1]), h("b", 3.0, [2])],  # the two faces of one body
    [h("a", 0.0, [1]), h("b", 0.0, [2])],  # a duplicated face
], ids=["two_faces", "duplicated_face"])
def test_one_body_stretch_releases_exactly_one_wall(identities):
    _baseline, result, counts, released = run(identities, FACES)
    assert released == ("a",) and counts == {RELEASED: 1, COVERED_FACE: 1}
    assert "b" not in result.representative_wall_ids
    assert result.blockers_for("b") == ("equivalent_physical_wall_represented_by:a",)
    assert result.equivalence_groups == (("a", "b"),) and not {"a", "b"} & set(result.ambiguous_wall_ids)


def test_an_identical_copy_is_left_to_the_existing_rule():
    identities = [h("a", 0.0, [1]), h("b", 0.0, [1])]
    baseline, result, _counts, released = run(identities, FACES)
    assert baseline.representative_wall_ids == ("a",) and released == () and result is baseline


def test_a_rival_beside_either_face_keeps_the_whole_body_abstained():
    identities = [h("a", 0.0, [1]), h("b", 3.0, [2]), h("stray", 7.0, [9])]
    assert run(identities, FACES)[3] == ()


def test_a_rival_beside_only_one_face_stretch_keeps_the_body_abstained():
    identities = [h("a", 0.0, [1], 0.0, 95.0), h("b", 3.0, [2], 0.0, 100.0), h("short", 7.0, [9], 96.0, 130.0)]
    assert run(identities, FACES)[3] == ()


def test_a_typed_non_wall_is_never_released():
    identities = [h("a", 0.0, [1]), h("grid", 300.0, [2])]
    bodies = [body(0.0, 3.0, {1}), body(300.0, 303.0, {2})]
    assert run(identities, bodies, non_wall={"grid"})[3] == ("a",)


def test_faces_over_different_stretches_stay_abstained():
    identities = [h("a", 0.0, [1]), h("b", 3.0, [2], 0.0, 40.0)]
    _baseline, _result, counts, released = run(identities, FACES)
    assert released == () and counts == {KEPT_PARTIAL_FACES: 2}


def test_a_body_stretch_already_published_gains_nothing():
    identities = [h("a", 0.0, [1]), h("b", 3.0, [2])]
    baseline = resolve_physical_wall_equivalence(identities)
    given = replace(baseline, representative_wall_ids=("a",), abstained_wall_ids=("b",))
    result, counts, released = release_bounded_equivalence(identities, given, FACES)
    assert released == () and counts == {KEPT_PUBLISHED_FACE: 1} and result is given


def test_any_other_blocker_keeps_the_wall():
    identities = [h("a", 0.0, [1]), h("far", 200.0, [2])]
    baseline = resolve_physical_wall_equivalence(identities)
    blocked = replace(baseline, blocking_reasons_by_wall_id={
        **baseline.blocking_reasons_by_wall_id, "far": (AMBIGUITY_BLOCKER, "typed_negative_ink")})
    _result, _counts, released = release_bounded_equivalence(identities, blocked,
                                                            [body(0.0, 3.0, {1}), body(200.0, 203.0, {2})])
    assert released == ("a",)


def test_narrow_walls_far_apart_are_both_released():
    identities = [h("a", 0.0, [1]), h("b", 12.0, [2])]
    assert run(identities, [body(0.0, 2.0, {1}), body(12.0, 14.0, {2})])[3] == ("a", "b")


def test_junctions_and_end_to_end_pieces_do_not_compete():
    identities = [h("left", 0.0, [1], 0.0, 100.0), h("right", 0.0, [2], 100.0, 200.0),
                  wall("cross", (100.0, 0.0), (100.0, 80.0), [3])]
    bodies = [body(0.0, 3.0, {1, 2}, along=(0.0, 200.0)),
              body(100.0, 103.0, {3}, along=(0.0, 80.0), horizontal=False)]
    assert set(run(identities, bodies)[3]) >= {"left", "right"}


def test_a_drafting_grid_line_blocks_until_typed_as_non_wall():
    identities = [h("a", 0.0, [1]), h("grid", 4.0, [9])]
    bodies = [body(0.0, 3.0, {1})]
    assert run(identities, bodies)[3] == ()
    _baseline, _result, counts, released = run(identities, bodies, non_wall={"grid"})
    assert released == ("a",) and counts[KEPT_NON_WALL] == 1


@pytest.mark.parametrize("paths,bodies,outcome", [
    (["raster_segment:7"], [body(0.0, 3.0, {1})], KEPT_NO_BODY),
    ([1], [body(0.0, 3.0, {1}), body(-1.0, 4.0, {1})], KEPT_SEVERAL_BODIES),
    ([1], [body(0.0, 3.0, {1}, along=(0.0, 50.0))], KEPT_NO_BODY),  # the body covers half the wall
    ([1], [body(0.0, 3.0, {5})], KEPT_NO_BODY),  # the paint is not the wall's own source
], ids=["raster", "several_bodies", "partial_body", "foreign_paint"])
def test_ownership_must_be_unique_native_and_covering(paths, bodies, outcome):
    identities = [h("a", 0.0, paths), h("far", 200.0, [2])]
    _baseline, _result, counts, released = run(identities, [*bodies, body(200.0, 203.0, {2})])
    assert released == ("far",) and counts.get(outcome) == 1


def test_order_and_input_untouched():
    identities = [h("a", 0.0, [1]), h("b", 6.0, [2]), h("c", 200.0, [3]), h("d", 400.0, [4])]
    bodies = [body(0.0, 3.0, {1}), body(200.0, 203.0, {3}), body(400.0, 403.0, {4})]
    before = copy.deepcopy(identities)
    _b, _r, _c, released = run(identities, bodies)
    shuffled = identities[:]
    random.Random(3).shuffle(shuffled)
    assert run(shuffled, bodies[::-1])[3] == released == ("c", "d") and identities == before


def test_bodies_come_from_painted_pairs_with_their_paths():
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.draw_line((50, 60), (250, 60), color=(0, 0, 0), width=0.5)
    page.draw_line((50, 64), (250, 64), color=(0, 0, 0), width=0.5)
    drawings = page.get_drawings()
    document.close()
    [found] = source_wall_bodies(drawings)
    assert found.horizontal and found.across == pytest.approx((60.0, 64.0)) and found.path_indices == {0, 1}
    assert run([h("a", 60.0, [0], 50.0, 250.0), h("far", 150.0, [5], 50.0, 250.0)], [found])[3] == ("a",)


def _conflicted(identities, overrides):
    return _apply_trusted_relation_overrides(identities, resolve_physical_wall_equivalence(identities), overrides,
                                             allow_proven_same_over_distinct=True)


SAME, DISTINCT = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL, PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS


def test_a_component_wide_conflict_does_not_block_a_wall_outside_the_contradiction():
    identities = [h("p", 0.0, [1]), h("q", 3.0, [2]), h("r", 6.0, [3]), h("far", 200.0, [4])]
    given = _conflicted(identities, {("p", "q"): SAME, ("q", "r"): SAME, ("p", "r"): DISTINCT})
    assert given.blockers_for("far") == (CONFLICT_BLOCKER,) and given.representative_wall_ids == ()
    bodies = [body(0.0, 3.0, {1, 2}), body(6.0, 9.0, {3}), body(200.0, 203.0, {4})]
    _result, counts, released = release_bounded_equivalence(identities, given, bodies)
    assert released == ("far",) and counts[KEPT_CONFLICT] >= 2


def test_faces_the_source_calls_distinct_stay_blocked():
    identities = [h("a", 0.0, [1]), h("b", 3.0, [2]), h("x", 200.0, [3]), h("y", 203.0, [4])]
    given = _conflicted(identities, {("a", "b"): DISTINCT, ("x", "y"): SAME})
    assert CONFLICT_BLOCKER in given.blockers_for("a")
    _result, counts, released = release_bounded_equivalence(identities, given, [body(0.0, 3.0, {1, 2})])
    assert released == () and counts[KEPT_CONFLICT] == 2


def _pdf():
    document = fitz.open()
    page = document.new_page(width=700, height=700)
    for a, b in (((50, 100), (400, 100)), ((50, 104), (400, 104)), ((50, 112), (400, 112)),  # a wall with a stray line
                 ((50, 500), (400, 500)), ((50, 504), (400, 504))):  # a wall on its own
        page.draw_line(a, b, color=(0, 0, 0), width=0.5)
    data = document.tobytes()
    document.close()
    return data


def _published_y(scope):
    records = {r.wall_candidate_id: r for r in scope.records}
    return sorted(round(records[w].wall_candidate.centerline_pts[0][1]) for w in scope.equivalence.representative_wall_ids)


def test_the_producer_option_publishes_one_face_of_the_free_wall_and_defaults_off():
    source = SourceVisibilityProducer(producer_method="bounded-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="bounded", source_bytes=_pdf(),
                                               source_locator="memory://b.pdf", page_ids=("1",))
    selector = PhysicalWallCandidateSelector(
        document_id="bounded", revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1", decision_scope_id=_decision_scope_id("1"))
    plain = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    bounded = PhysicalWallCandidateProducer.from_source_visibility_bounded_equivalence_shadow(
        source, page_ids=("1",)).authority()
    off, on = plain.resolve_scope(selector), bounded.resolve_scope(selector)
    assert _published_y(off) == [] and len(_published_y(on)) == 1 and _published_y(on)[0] in (500, 504)
    assert [r.wall_candidate_id for r in off.records] == [r.wall_candidate_id for r in on.records]
    composed = compose_live_wall_opening_authority(source_visibility_producer=source,
                                                   revision_id=published.revision.revision_id, page_ids=("1",),
                                                   bounded_wall_equivalence_shadow=True)
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id).snapshot.snapshot_id
    forwarded = composed.physical_wall_candidate_authority.resolve_scope(replace(selector, snapshot_id=snapshot))
    assert len(forwarded.equivalence.representative_wall_ids) == 1
    with pytest.raises(TypeError):
        compose_live_wall_opening_authority(source_visibility_producer=source, revision_id=published.revision.revision_id,
                                            page_ids=("1",), bounded_wall_equivalence_shadow=1)
    with pytest.raises(ValueError):
        compose_live_wall_opening_authority(source_visibility_producer=source, revision_id=published.revision.revision_id,
                                            page_ids=("1",), bounded_wall_equivalence_shadow=True,
                                            typed_negative_ink_promotion_guard="owner_green_ink")
