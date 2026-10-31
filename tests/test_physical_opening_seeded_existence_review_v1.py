"""Review of ab8087d4c: layers merge only on a verified shared host face; a solid face across the gap is never excused.

Written failing first against ab8087d4c (see the PR record), then passing with the change."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    LAYERED_FACES_OF_ONE_GAP,
    SEEDED_OPENING_INK_UNACCOUNTED,
    SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,
    _merge_layered_structures,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_physical_opening_seeded_existence_v1 import (
    FLUSH_MIDDLE,
    FLUSH_OUTER,
    GLAZING,
    LAYERED,
    PLAIN,
    _fixture,
    _ids,
    _selector,
)

CORR = EvidenceResolutionStatus.CORROBORATED
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT

POSES = [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)},
         {"angle_deg": 180.0, "offset": (300.0, 400.0)}, {"mirror": True, "offset": (300.0, 0.0)}]
FLUSH_OUTER_ONE = (((100.0, 100.0), (140.0, 100.0)),)
SPLIT_MIDDLE = (((100.0, 105.0), (120.0, 105.0)), ((120.0, 105.0), (140.0, 105.0)))
HALF_MIDDLE = (((100.0, 105.0), (122.0, 105.0)),)


def _faces_and_jambs(offsets):
    lines = []
    for offset in offsets:
        lines += [((20.0, offset), (100.0, offset)), ((140.0, offset), (220.0, offset))]
    for low, high in zip(offsets, offsets[1:]):
        lines += [((100.0, low), (100.0, high)), ((140.0, low), (140.0, high))]
    return tuple(lines)


LAYERED_THREE = _faces_and_jambs((100.0, 105.0, 110.0, 115.0))


@pytest.mark.parametrize("kw", POSES)
def test_layers_that_share_a_host_face_are_one_opening_in_every_pose(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    result = physical.seeded_candidate_structures(_selector(published, members[6]), members)
    assert result.status is CAND and len(result.candidates) == 1
    assert LAYERED_FACES_OF_ONE_GAP in result.candidates[0].reason_codes
    assert set(result.candidates[0].source_observation_ids) == set(members)


@pytest.mark.parametrize("kw", [{}, {"mirror": True, "offset": (300.0, 0.0)}])
def test_a_chain_of_layers_each_sharing_a_face_with_the_next_is_one_opening(kw):
    physical, published, ids, kw = _fixture(LAYERED_THREE, **kw)
    members = _ids(ids, LAYERED_THREE, kw)
    selector = _selector(published, members[0])
    result = physical.seeded_candidate_structures(selector, members)
    assert len(result.candidates) == 1 and set(result.candidates[0].source_observation_ids) == set(members)
    proof = physical.prove_seeded_existence(selector, members)
    assert proof.status is CORR and set(proof.existence_record.source_observation_ids) == set(members)


ANOTHER_SHARED_RIGHT_PIECE = ((150.0, 105.0), (190.0, 105.0))       # a different line on the very offset the layers share
STACK = tuple(dict.fromkeys(_faces_and_jambs((100.0, 105.0, 110.0, 115.0)) + _faces_and_jambs((105.0, 108.0))
                            + _faces_and_jambs((200.0, 210.0)) + (ANOTHER_SHARED_RIGHT_PIECE,)))


def _layer_ids(ids, kw, low, high):
    pieces = [((20.0, low), (100.0, low)), ((140.0, low), (220.0, low)),
              ((20.0, high), (100.0, high)), ((140.0, high), (220.0, high))]
    jambs = [((100.0, low), (100.0, high)), ((140.0, low), (140.0, high))]
    return _ids(ids, pieces, kw), _ids(ids, jambs, kw)


def _unit(kw=None):
    """One page holding the lines of several candidate layers, and a real candidate to copy the source identity from."""
    physical, published, ids, kw = _fixture(STACK, **(kw or {}))
    pieces, jambs = _layer_ids(ids, kw, 100.0, 105.0)
    selector = _selector(published, pieces[0])
    failure, _source, _records, by_id, _restricted = physical._seeded_universe(selector, pieces + jambs)
    assert failure is None
    base = physical.seeded_candidate_structures(selector, pieces + jambs).candidates[0]

    def layer(name, low, high, **changes):
        p, j = _layer_ids(ids, kw, low, high)
        return replace(base, candidate_id=name, source_observation_ids=tuple(sorted(p + j)), **changes)

    return ids, kw, by_id, base, layer, lambda *c: _merge_layered_structures(tuple(c), by_id)


@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"mirror": True, "offset": (300.0, 0.0)}])
def test_structures_that_share_only_a_jamb_are_not_merged(kw):
    ids, kw, by_id, base, layer, merge = _unit(kw)
    _pieces, jambs = _layer_ids(ids, kw, 100.0, 105.0)
    near = layer("near", 100.0, 105.0)
    far_pieces, _far_jambs = _layer_ids(ids, kw, 200.0, 210.0)
    # a second host at another depth that rests on the SAME two jamb lines: they share a jamb and nothing else
    other = replace(base, candidate_id="other", source_observation_ids=tuple(sorted(far_pieces + jambs)))
    assert set(near.source_observation_ids) & set(other.source_observation_ids) == set(jambs)
    merged = merge(near, other)
    assert sorted(c.candidate_id for c in merged) == ["near", "other"]
    assert all(LAYERED_FACES_OF_ONE_GAP not in c.reason_codes for c in merged)


@pytest.mark.parametrize("kw", [{}, {"mirror": True, "offset": (300.0, 0.0)}])
def test_layers_on_opposite_sides_of_a_shared_face_merge_and_the_result_is_order_independent(kw):
    ids, kw, by_id, base, layer, merge = _unit(kw)
    a, b, d = layer("a", 100.0, 105.0), layer("b", 105.0, 110.0), layer("d", 110.0, 115.0)
    one = merge(a, b)
    assert len(one) == 1 and LAYERED_FACES_OF_ONE_GAP in one[0].reason_codes
    assert merge(b, a) == one
    chain = merge(d, b, a)
    assert len(chain) == 1 and set(chain[0].source_observation_ids) == (
        set(a.source_observation_ids) | set(b.source_observation_ids) | set(d.source_observation_ids))
    assert len(merge(a, d)) == 2          # not adjacent: nothing between them is claimed


@pytest.mark.parametrize("kw", [{}, {"mirror": True, "offset": (300.0, 0.0)}])
def test_a_bridge_cannot_chain_inconsistent_layers_into_one_opening(kw):
    ids, kw, by_id, base, layer, merge = _unit(kw)
    a, b, c = layer("a", 100.0, 105.0), layer("b", 105.0, 110.0), layer("c", 105.0, 108.0)
    # b and c lie on the same side of the face they share with a: two depth readings of one wall, not stacked layers
    result = merge(a, b, c)
    assert sorted(x.candidate_id for x in result) == ["a", "b", "c"]
    assert all(LAYERED_FACES_OF_ONE_GAP not in x.reason_codes for x in result)
    assert [x.candidate_id for x in merge(c, b, a)] == [x.candidate_id for x in result]


def test_a_face_piece_that_is_not_the_same_line_on_both_layers_is_not_a_shared_face():
    ids, kw, by_id, base, layer, merge = _unit()
    a, b = layer("a", 100.0, 105.0), layer("b", 105.0, 110.0)
    shared_right = ids[frozenset(((140.0, 105.0), (220.0, 105.0)))]
    different = ids[frozenset(ANOTHER_SHARED_RIGHT_PIECE)]
    swapped = replace(b, source_observation_ids=tuple(sorted((set(b.source_observation_ids) - {shared_right}) | {different})))
    assert sorted(c.candidate_id for c in merge(a, swapped)) == ["a", "b"]


@pytest.mark.parametrize("field,value", [("snapshot_id", "another-snapshot"), ("page_id", "another-page"),
                                         ("document_id", "another-document"), ("revision_id", "another-revision"),
                                         ("source_sha256", "0" * 64), ("viewport_id", "another-viewport"),
                                         ("structural_pattern", "another-pattern")])
def test_layers_from_different_sources_pages_or_viewports_are_never_one_opening(field, value):
    ids, kw, by_id, base, layer, merge = _unit()
    a, b = layer("a", 100.0, 105.0), layer("b", 105.0, 110.0, **{field: value})
    assert len(merge(a, layer("b2", 105.0, 110.0))) == 1
    assert sorted(c.candidate_id for c in merge(a, b)) == ["a", "b"]


@pytest.mark.parametrize("kw", POSES)
@pytest.mark.parametrize("name,extra", [("outer_both", FLUSH_OUTER), ("outer_one", FLUSH_OUTER_ONE),
                                        ("shared", FLUSH_MIDDLE), ("split_shared", SPLIT_MIDDLE),
                                        ("half_shared", HALF_MIDDLE), ("all", FLUSH_OUTER + FLUSH_MIDDLE)])
def test_solid_face_ink_across_the_gap_is_refused_in_every_pose_even_when_named(kw, name, extra):
    physical, published, ids, kw = _fixture(LAYERED + extra, **kw)
    members = _ids(ids, LAYERED, kw)
    ink = _ids(ids, extra, kw)
    selector = _selector(published, members[6])
    for accounted in ((), ink):
        proof = physical.prove_seeded_existence(selector, members, accounted)
        assert proof.status is ABST and proof.existence_record is None, name
        assert proof.reason_codes == (SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,), name
    # naming the solid face as a MEMBER does not make it part of the opening either
    assert physical.prove_seeded_existence(selector, members + ink).existence_record is None, name


@pytest.mark.parametrize("extra", [FLUSH_OUTER_ONE, FLUSH_OUTER])
def test_a_plain_opening_with_solid_face_ink_across_its_gap_is_refused_even_when_named(extra):
    physical, published, ids, kw = _fixture(PLAIN + extra)
    members = _ids(ids, PLAIN, kw)
    flush = _ids(ids, extra, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[4]), members, flush)
    assert proof.status is ABST and proof.reason_codes == (SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,)


@pytest.mark.parametrize("kw", POSES)
def test_glazing_that_is_not_on_a_face_survives_when_named_in_every_pose(kw):
    near_face = (((104.0, 100.4), (136.0, 100.4)), ((104.0, 109.6), (136.0, 109.6)), ((120.0, 102.0), (120.0, 108.0)))
    physical, published, ids, kw = _fixture(LAYERED + GLAZING + near_face, **kw)
    members = _ids(ids, LAYERED, kw)
    glass = _ids(ids, GLAZING + near_face, kw)
    selector = _selector(published, members[6])
    assert physical.prove_seeded_existence(selector, members).reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
    named = physical.prove_seeded_existence(selector, members, glass)
    assert named.status is CORR and LAYERED_FACES_OF_ONE_GAP in named.existence_record.structural_reason_codes


def _rect_fixture(*, stroke, fill):
    producer = SourceVisibilityProducer(producer_method="seeded-existence-test", producer_version="1.0")
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for x0, x1 in ((20, 100), (140, 220)):
        page.draw_rect(fitz.Rect(x0, 100, x1, 110), color=stroke, fill=fill)
    payload = doc.tobytes()
    doc.close()
    published = producer.ingest_native_pdf_bytes(document_id="seeded-existence-rects", source_bytes=payload,
                                                 source_locator="memory://seeded-existence-rects.pdf")
    ids = {}
    for observation_id, record in producer.authority().authenticated_visible_observations(published):
        g = record.geometry
        ids[frozenset(((round(g[0], 2), round(g[1], 2)), (round(g[2], 2), round(g[3], 2))))] = observation_id
    return producer.physical_opening_authority(), published, ids


def test_an_unstroked_white_fill_boundary_still_opposes_the_seeded_proof_as_it_opposes_the_page_proof():
    physical, published, ids = _rect_fixture(stroke=None, fill=(1, 1, 1))
    members = _ids(ids, PLAIN, {})
    selector = _selector(published, members[4])
    page = physical.prove_existence(selector)
    seeded = physical.prove_seeded_existence(selector, members)
    assert page.status is ABST and page.reason_codes == ("native_unstroked_fill_boundary_opposes_opening",)
    assert seeded.status is ABST and seeded.existence_record is None
    assert seeded.reason_codes == page.reason_codes and seeded.opposing_evidence_atoms


def test_the_same_boundary_drawn_as_stroked_linework_is_not_opposed():
    physical, published, ids = _rect_fixture(stroke=(0, 0, 0), fill=None)
    members = _ids(ids, PLAIN, {})
    selector = _selector(published, members[4])
    page, seeded = physical.prove_existence(selector), physical.prove_seeded_existence(selector, members)
    assert page.status is CORR and seeded.status is CORR and seeded.existence_record == page.existence_record


@pytest.mark.parametrize("scenario", ["scope_conflict", "scope_abstained", "not_promotable", "no_decision"])
def test_a_viewport_scope_that_is_not_promotable_stops_the_seeded_proof(monkeypatch, scenario):
    import pb_physical_opening_viewport_scope_authority as scope_module

    physical, published, ids, kw = _fixture(PLAIN)
    members = _ids(ids, PLAIN, kw)
    selector = _selector(published, members[4])
    assert physical.prove_seeded_existence(selector, members).status is CORR

    def fake(**kwargs):
        candidate = kwargs["candidates"][0]
        status = {"scope_conflict": CONF, "scope_abstained": ABST}.get(scenario, CORR)
        decisions = {} if scenario == "no_decision" else {
            candidate.candidate_id: SimpleNamespace(viewport_id="viewport-1", promotable=scenario != "not_promotable")}
        return SimpleNamespace(status=status, reason_codes=("opening_candidate_viewport_scope_unresolved",),
                               decisions=decisions, authenticated_viewports=("viewport-1",))

    monkeypatch.setattr(scope_module, "classify_opening_candidate_viewport_scopes", fake)
    proof = physical.prove_seeded_existence(selector, members)
    assert proof.status is ABST and proof.existence_record is None


def test_members_resolved_from_another_snapshot_are_refused_by_the_authority_that_owns_this_one():
    physical, published, ids, kw = _fixture(PLAIN)
    other_physical, other_published, other_ids, other_kw = _fixture(PLAIN)
    members = _ids(ids, PLAIN, kw)
    foreign = _ids(other_ids, PLAIN, other_kw)
    selector = _selector(published, members[4])
    for bad in (foreign, members[:3] + foreign[3:]):
        proof = physical.prove_seeded_existence(selector, bad)
        assert proof.status is ABST and proof.existence_record is None
    assert physical.prove_seeded_existence(selector, members, foreign[:1]).status is ABST


def test_an_omitted_stroke_inside_the_gap_is_opposition_the_caller_must_name():
    physical, published, ids, kw = _fixture(PLAIN + GLAZING)
    members = _ids(ids, PLAIN, kw)
    glass = _ids(ids, GLAZING, kw)
    selector = _selector(published, members[4])
    assert physical.prove_seeded_existence(selector, members).reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
    assert physical.prove_seeded_existence(selector, members, glass).status is CORR
