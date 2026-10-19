"""Frame composition preserves scope, equivalence and graph conflicts."""
from dataclasses import replace
from itertools import permutations
from types import SimpleNamespace as Obj

import pytest

import pb_opening_host_frame_authority as frame
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class
from test_raster_connected_host_frame import _fixture, _scope


@pytest.mark.parametrize("field,value", [("document_id", "foreign"),
    ("revision_id", "stale"), ("source_sha256", "0"*64), ("snapshot_id", "old"),
    ("page_id", "9"), ("decision_scope_id", "other"), ("proposition", "unknown"),
    ("scope_complete", True), ("equivalence", None), ("status", Status.ABSTAINED)])
def test_supplemental_scope_cannot_borrow_selected_frame_scope(field, value):
    _, _, producer, bound = _fixture()
    scope = _scope(producer, bound)
    supplemental = replace(scope, scope_complete=False)
    supplemental = replace(supplemental, **{field: value})
    producer._supplemental_walls = Obj(resolve_scope=lambda _: supplemental)
    assert producer._scope_records_by_id(scope, bound[0][3]) == {}


def test_conflicting_wall_id_cannot_be_resolved_by_ordinary_record_first():
    _, _, producer, bound = _fixture()
    scope = _scope(producer, bound)
    original = scope.records[0]
    altered = replace(original, wall_candidate=replace(original.wall_candidate,
        centerline_pts=tuple((x, y+1.) for x,y in original.wall_candidate.centerline_pts)))
    for records in ((original, altered), (altered, original)):
        supplemental = replace(scope, scope_complete=False, records=records)
        producer._supplemental_walls = Obj(resolve_scope=lambda _: supplemental)
        assert producer._scope_records_by_id(scope, bound[0][3]) == {}
    producer._supplemental_walls = None
    assert producer._scope_records_by_id(replace(scope, records=(original, altered)), bound[0][3]) == {}


def test_consistent_source_aliases_do_not_duplicate_or_mutate_frame_records():
    _, _, producer, bound = _fixture()
    scope = _scope(producer, bound)
    before = repr(scope)
    supplemental = replace(scope, scope_complete=False)
    producer._supplemental_walls = Obj(resolve_scope=lambda _: supplemental)
    assert producer._scope_records_by_id(scope, bound[0][3]) == {
        r.wall_candidate_id:r for r in scope.records}
    assert repr(scope) == before


@pytest.mark.parametrize("other", [Class.SAME_PHYSICAL_WALL.value, "invalid"])
def test_pair_conflict_is_order_invariant_and_never_distinct(other):
    rows = (("a", "b", Class.DISTINCT_PHYSICAL_WALLS.value), ("b", "a", other))
    for ordered in permutations(rows):
        result = frame._pair_lookup(Obj(pair_classifications=ordered))
        assert result[("a", "b")] is Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def test_identical_pair_receipts_preserve_distinct_proof():
    row = ("a", "b", Class.DISTINCT_PHYSICAL_WALLS.value)
    assert frame._pair_lookup(Obj(pair_classifications=(row,row)))[("a","b")] is Class.DISTINCT_PHYSICAL_WALLS


def test_overlapping_equivalence_groups_cannot_pick_first_alias():
    for groups in permutations((("a", "b"), ("a", "c"))):
        assert frame._band_node(("a",), Obj(equivalence_groups=groups)) is None
    assert frame._band_node(("a",), Obj(equivalence_groups=(("a", "b"),))) == (("a", "b"),)


def _edge(binding_id, opening_id, left="a", right="b"):
    return frame._ScopeBinding(opening=Obj(record_id=opening_id), geometry=Obj(length=40.),
        binding=Obj(record_id=binding_id), left_node=((left,),), right_node=((right,),))


def test_parallel_opening_edges_cannot_collapse_to_one_path():
    a, b = _edge("binding-a", "opening-a"), _edge("binding-b", "opening-b")
    for ordered in ((a,b),(b,a)):
        assert frame.OpeningHostFrameProducer._selected_component(ordered, a.binding) is None


def test_same_binding_id_cannot_describe_two_frame_edges():
    a, b = _edge("binding-a", "opening-a"), _edge("binding-a", "opening-a", right="c")
    assert frame.OpeningHostFrameProducer._selected_component((a,b), a.binding) is None


def test_exact_graph_replay_remains_idempotent():
    edge = _edge("binding-a", "opening-a")
    expected = frozenset((edge.left_node, edge.right_node))
    assert frame.OpeningHostFrameProducer._selected_component((edge,), edge.binding) == expected
    assert frame.OpeningHostFrameProducer._selected_component((edge,edge), edge.binding) == expected


@pytest.mark.parametrize("changes", [dict(axis=(2.,0.)),dict(normal=(1.,0.)),
    dict(normal=(0.,2.)), dict(origin=(float("nan"),0.)), dict(length=True),
    dict(thickness=-1.), dict(axis=("bad",0.))])
def test_invalid_source_basis_cannot_form_even_a_review_frame(changes):
    from pb_opening_host_binding_authority import _OpeningGeometry
    geometry = _OpeningGeometry(origin=(0.,0.),axis=(1.,0.),normal=(0.,1.),length=40.,thickness=10.)
    assert not frame._valid_aperture_geometry(replace(geometry, **changes))


@pytest.mark.parametrize("field", ["document_id", "revision_id", "source_sha256",
    "snapshot_id", "page_id", "decision_scope_id", "opening_identity_id"])
def test_local_review_frame_rechecks_exact_binding_selector(monkeypatch, field):
    _, _, producer, bound = _fixture()
    selector, _, binding_selector, _ = bound[0]
    authentic = producer._host.resolve(binding_selector)
    monkeypatch.setattr(producer._host, "resolve", lambda _: authentic)
    result = producer.local_source_frame_shadow(opening_selector=selector,
        host_binding_selector=replace(binding_selector, **{field:"foreign"}))
    assert result.status is Status.CONFLICT and result.evidence is None
