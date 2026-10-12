"""Plural W4 addresses cannot manufacture competing physical source ownership."""
from copy import deepcopy
from dataclasses import replace
import itertools
from types import SimpleNamespace as N

import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_physical_wall_identity import PhysicalWallIdentity, PhysicalWallEquivalenceResolution
from pb_physical_wall_candidate_authority import PhysicalWallSourceEdgeFragment


def scope(*, classification="same_physical_wall", foreign=False, partial=False):
    vp = "wall-source:page-1"
    coordinates = {
        "top": ((0., 0.), (20., 0.)), "right": ((20., 0.), (20., 10.)),
        "bottom": ((20., 10.), (0., 10.)), "left": ((0., 10.), (0., 0.)),
        "partition": ((10., 0.), (10., 10.)),
        "partition-alias": ((10., 10.), (10., 0.)),
    }
    if partial:
        coordinates["partition-alias"] = ((10., 8.), (10., 2.))
    records = []
    for name, points in coordinates.items():
        original = "partition" if name == "partition-alias" else name
        parents = ("foreign",) if foreign and name == "partition-alias" else (original,)
        path = tuple(sorted(points))
        identity = PhysicalWallIdentity(
            wall_candidate_id=name, viewport_id=vp, candidate_identity_id="id-" + original,
            path_fingerprint=path, source_primitive_ids=parents, edge_ids=("edge-" + name,),
            status=S.CORROBORATED,
        )
        records.append(N(wall_candidate_id=name, physical_identity=identity,
            wall_candidate=N(candidate_id=name, viewport_id=vp, centerline_pts=points)))
    pairs = (("partition", "partition-alias", classification),) if classification else ()
    equivalence = PhysicalWallEquivalenceResolution(
        scope_viewport_id=vp, representative_wall_ids=(), abstained_wall_ids=(),
        equivalence_groups=(("partition", "partition-alias"),), ambiguous_wall_ids=(),
        same_wall_ids=("partition", "partition-alias"), pair_classifications=pairs,
        blocking_reasons_by_wall_id={},
    )
    return N(status=S.CORROBORATED, scope_complete=True, records=tuple(records),
        document_id="doc", revision_id="rev", source_sha256="a" * 64, snapshot_id="snap",
        page_id="1", decision_scope_id=vp, equivalence=equivalence)


def test_complete_same_source_aliases_publish_both_rooms_and_retain_every_owner():
    original = scope()
    before = deepcopy(original)
    result = R._derive_scope(original)
    assert original == before
    assert result.status is S.CORROBORATED
    assert len(result.records) == 2
    for room in result.records:
        assert {"partition", "partition-alias"} <= set(room.bounding_wall_ids)
        assert {owner for owner, edge in room.boundary_wall_edges
                if edge[0][0] == edge[1][0] == 10.} == {"partition", "partition-alias"}
    assert R.SOURCE_ROOM_FACE_UNIVERSE_PARTIAL in result.reason_codes
    assert not result.face_universe_complete


@pytest.mark.parametrize("kwargs", [
    {"classification": None}, {"classification": "ambiguous_physical_equivalence"},
    {"classification": "distinct_physical_walls"}, {"foreign": True}, {"partial": True},
])
def test_unproven_or_partial_alias_still_abstains(kwargs):
    result = R._derive_scope(scope(**kwargs))
    assert result.records == ()
    assert result.status is S.ABSTAINED


@pytest.mark.parametrize("change", ["missing_identity", "blocked_identity", "foreign_scope",
    "missing_parents", "different_identity", "duplicate_source_address", "foreign_equivalence",
    "stale_path", "malformed_identity"])
def test_source_identity_integrity_cannot_be_borrowed(change):
    s = scope()
    alias = s.records[-1]
    if change == "missing_identity":
        del alias.physical_identity
    elif change == "blocked_identity":
        alias.physical_identity = replace(alias.physical_identity, status=S.ABSTAINED)
    elif change == "foreign_scope":
        alias.physical_identity = replace(alias.physical_identity, viewport_id="other")
    elif change == "missing_parents":
        alias.physical_identity = replace(alias.physical_identity, source_primitive_ids=())
    elif change == "different_identity":
        alias.physical_identity = replace(alias.physical_identity, candidate_identity_id="different")
    elif change == "duplicate_source_address":
        alias.wall_candidate_id = "partition"
    elif change == "stale_path":
        for record in s.records[-2:]:
            record.physical_identity = replace(record.physical_identity,
                path_fingerprint=((100., 0.), (100., 10.)))
    elif change == "malformed_identity":
        for record in s.records[-2:]:
            record.physical_identity = replace(record.physical_identity, candidate_identity_id=True)
    else:
        s.equivalence = replace(s.equivalence, scope_viewport_id="other")
    assert R._derive_scope(s).records == ()


def test_conflicting_or_omitted_pair_cannot_complete_a_three_owner_alias_group():
    s = scope()
    third = deepcopy(s.records[-1])
    third.wall_candidate_id = third.wall_candidate.candidate_id = "third"
    third.physical_identity = replace(third.physical_identity, wall_candidate_id="third")
    s.records += (third,)
    assert not R._derive_scope(s).records
    pairs = s.equivalence.pair_classifications + (
        ("partition", "third", "same_physical_wall"),
        ("partition-alias", "third", "same_physical_wall"),
    )
    s.equivalence = replace(s.equivalence, pair_classifications=pairs)
    assert len(R._derive_scope(s).records) == 2
    s.equivalence = replace(s.equivalence, pair_classifications=pairs + (
        ("third", "partition", "ambiguous_physical_equivalence"),))
    assert not R._derive_scope(s).records


def test_alias_permutation_transform_and_unrelated_content_preserve_physical_faces():
    base = scope()
    expected = R._derive_scope(base)
    for indices in itertools.permutations(range(3)):
        s = deepcopy(base)
        s.records = s.records[:3] + tuple(s.records[3 + i] for i in indices)
        assert R._derive_scope(s) == expected
    for transform in (lambda x, y: (x + 200., y - 50.),
                      lambda x, y: (-y, x), lambda x, y: (x * 2., y * 2.)):
        s = deepcopy(base)
        for r in s.records:
            points = tuple(transform(*p) for p in r.wall_candidate.centerline_pts)
            r.wall_candidate.centerline_pts = points
            r.physical_identity = replace(r.physical_identity, path_fingerprint=tuple(sorted(points)))
        result = R._derive_scope(s)
        assert len(result.records) == 2
        assert all({"partition", "partition-alias"} <= set(r.bounding_wall_ids) for r in result.records)
    assert R._derive_scope(base) == expected


def test_an_unrelated_open_source_run_does_not_change_the_alias_proof():
    s = scope()
    before = R._derive_scope(s)
    s.records += (N(wall_candidate_id="distant", wall_candidate=N(
        centerline_pts=((500., 500.), (600., 500.)))),)
    result = R._derive_scope(s)
    assert result.records == before.records
    assert result.reason_codes == before.reason_codes


def test_a_longer_source_owner_cannot_be_hidden_by_the_proven_aliases():
    s = scope()
    s.records += (N(wall_candidate_id="longer", wall_candidate=N(
        centerline_pts=((10., -10.), (10., 20.)))),)
    assert not R._derive_scope(s).records


def fragment_scope(*, remote=False, gap=False, foreign=False, extra_owner=False):
    s = scope(classification="ambiguous_physical_equivalence")
    # Same source interval, different complete W4 paths and source ancestry.
    # Keep the source edge proof separate from whole-wall equivalence.
    left, alias = s.records[-2:]
    alias.wall_candidate.centerline_pts = ((10., 10.), (10., 0.), (10., -10.))
    alias.physical_identity = replace(alias.physical_identity,
        candidate_identity_id="other-path", path_fingerprint=((10., -10.), (10., 0.), (10., 10.)),
        source_primitive_ids=("partition", "branch"))
    for r in (left, alias):
        geometry = (10., 0., 10., 10.)
        if remote and r is alias:
            geometry = (10., 20., 10., 30.)
        parents = ("foreign",) if foreign and r is alias else ("partition",)
        r.source_edge_fragments = (PhysicalWallSourceEdgeFragment(
            edge_id="actual-" + r.wall_candidate_id, geometry=geometry, source_primitive_ids=parents),)
        if gap and r is alias:
            r.source_edge_fragments = (
                PhysicalWallSourceEdgeFragment("lower", (10., 0., 10., 4.), parents),
                PhysicalWallSourceEdgeFragment("upper", (10., 6., 10., 10.), parents),
            )
        r.physical_identity = replace(r.physical_identity,
            edge_ids=tuple(f.edge_id for f in r.source_edge_fragments))
    if extra_owner:
        third = deepcopy(left)
        third.wall_candidate_id = third.wall_candidate.candidate_id = "independent"
        third.physical_identity = replace(third.physical_identity,
            wall_candidate_id="independent", source_primitive_ids=("independent-source",))
        third.source_edge_fragments = (PhysicalWallSourceEdgeFragment(
            "independent-edge", (10., 0., 10., 10.), ("independent-source",)),)
        s.records += (third,)
    return s


def test_exact_original_source_interval_resolves_ownership_without_wall_equivalence():
    s = fragment_scope()
    before = deepcopy(s)
    result = R._derive_scope(s)
    assert s == before
    assert len(result.records) == 2
    assert s.equivalence.pair_classifications[0][2] == "ambiguous_physical_equivalence"
    assert all({"partition", "partition-alias"} <= set(r.bounding_wall_ids) for r in result.records)


@pytest.mark.parametrize("kwargs", [{"remote": True}, {"gap": True},
    {"foreign": True}, {"extra_owner": True}])
def test_lineage_alone_or_partial_fragments_cannot_prove_a_source_interval(kwargs):
    assert not R._derive_scope(fragment_scope(**kwargs)).records


def test_source_interval_cannot_override_distinct_or_conflicting_source_facts():
    s = fragment_scope()
    s.equivalence = replace(s.equivalence, pair_classifications=(
        ("partition", "partition-alias", "distinct_physical_walls"),))
    assert not R._derive_scope(s).records
