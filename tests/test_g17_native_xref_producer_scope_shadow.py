"""Source-neutral negative and exact type gates for producer-owned XRef bridge."""
import pytest

from pb_g17_native_xref_producer_scope_shadow import (
    producer_bound_g17_w4_native_xref_shadow as bridge,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from tests.test_raster_framed_opening_g17_contract import _prepare


def _fixture():
    source, published = _prepare(frame_lines=2)
    kwargs = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
    )
    source_scope = PhysicalWallCandidateSelector(
        **kwargs, page_id="1", decision_scope_id="wall-source:page-1",
    )
    ids = tuple(published.snapshot.observation_ids)
    selected = (ObservationSelector(**kwargs, observation_id=ids[0]),)
    return source, source_scope, selected


def test_reject_caller_made_authority_and_missing_opening_inventory():
    source, scope, selectors = _fixture()
    with pytest.raises(TypeError, match="existing sealed"):
        bridge(source, wall_authority={}, wall_selector=scope,
               opening_selectors=selectors)
    fake_wall = object.__new__(PhysicalWallCandidateAuthority)
    with pytest.raises(ValueError, match="selectors required"):
        bridge(source, wall_authority=fake_wall, wall_selector=scope,
               opening_selectors=())


def test_reject_foreign_source_root_without_using_wall_authority():
    source, scope, selectors = _fixture()
    fake_wall = object.__new__(PhysicalWallCandidateAuthority)
    from dataclasses import replace
    with pytest.raises(ValueError, match="roots differ"):
        bridge(source, wall_authority=fake_wall,
               wall_selector=replace(scope, source_sha256="0" * 64),
               opening_selectors=selectors)


def test_exact_source_with_unavailable_w4_scope_stays_abstained(monkeypatch):
    source, scope, selectors = _fixture()
    fake_wall = object.__new__(PhysicalWallCandidateAuthority)
    from types import SimpleNamespace as NS
    from pb_migration_contracts import EvidenceResolutionStatus
    monkeypatch.setattr(
        PhysicalWallCandidateAuthority, "resolve_scope",
        lambda self, s: NS(
            status=EvidenceResolutionStatus.ABSTAINED,
            scope_complete=False, proposition=None, equivalence=None,
        ),
    )
    result = bridge(source, wall_authority=fake_wall,
                    wall_selector=scope, opening_selectors=selectors)
    assert result["status"] == EvidenceResolutionStatus.ABSTAINED.value
    assert not result["original_producer_scope_verified"]
    assert not result["host_binding_granted"]
    assert not result["firm_area_granted"]
    assert not result["opening_count_granted"]
    assert not result["benchmark_score_granted"]


def test_real_synthetic_source_with_mock_w4_scope_stays_source_only(monkeypatch):
    """Exercise the full adapter, but never present a mocked wall as authority."""
    from types import SimpleNamespace as NS
    from pb_migration_contracts import EvidenceResolutionStatus
    from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
    from pb_physical_wall_candidate_authority import PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
    from tests.test_opening_local_g17_wall_shadow import address

    source, published = _prepare(frame_lines=2)
    selector = address(source, published)
    kwargs = dict(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    wall_selector = PhysicalWallCandidateSelector(**kwargs)
    local = build_opening_local_g17_wall_shadow(source, selector)
    assert len(local.flanks) == 2
    supplied_mock_wall = local.flanks[0].exact_coordinate_records[0]
    mocked_scope = NS(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        records=(supplied_mock_wall,), equivalence=object(), **kwargs,
    )
    monkeypatch.setattr(
        PhysicalWallCandidateAuthority, "resolve_scope",
        lambda self, s: mocked_scope,
    )
    fake_wall_authority = object.__new__(PhysicalWallCandidateAuthority)
    result = bridge(
        source, wall_authority=fake_wall_authority,
        wall_selector=wall_selector, opening_selectors=(selector,),
    )
    assert result["original_producer_scope_verified"]
    assert result["g17_source_edges_reissued"] > 0
    assert result["ordinary_w4_edges_reissued"] > 0
    assert not result["opening_roster_complete_proven"]
    assert not result["source_parent_equivalence_granted"]
    assert not result["host_binding_granted"]
    assert not result["firm_area_granted"]
    assert not result["opening_count_granted"]
    assert not result["benchmark_score_granted"]


def test_non_axis_w4_original_fragment_is_explicitly_excluded(monkeypatch):
    """A diagonal W4 edge cannot prevent independent axis-aligned source audit."""
    from dataclasses import replace
    from types import SimpleNamespace as NS
    from pb_migration_contracts import EvidenceResolutionStatus
    from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
    from pb_physical_wall_candidate_authority import (
        PhysicalWallSourceEdgeFragment,
        PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    )
    from tests.test_opening_local_g17_wall_shadow import address

    source, published = _prepare(frame_lines=2)
    selector = address(source, published)
    args = dict(
        document_id=selector.document_id, revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id, page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    wall_selector = PhysicalWallCandidateSelector(**args)
    native = build_opening_local_g17_wall_shadow(source, selector)
    wall = native.flanks[0].exact_coordinate_records[0]
    extra_edge = PhysicalWallSourceEdgeFragment(
        edge_id="diagonal-original",
        geometry=(0.0, 0.0, 1.0, 1.0),
        source_primitive_ids=("foreign-diagonal",),
    )
    wall = replace(
        wall, source_edge_fragments=(*wall.source_edge_fragments, extra_edge),
    )
    scope = NS(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        equivalence=object(), records=(wall,), **args,
    )
    monkeypatch.setattr(
        PhysicalWallCandidateAuthority, "resolve_scope",
        lambda self, selected: scope,
    )
    fake_authority = object.__new__(PhysicalWallCandidateAuthority)
    result = bridge(
        source, wall_authority=fake_authority,
        wall_selector=wall_selector, opening_selectors=(selector,),
    )
    assert result["original_producer_scope_verified"]
    assert result["ordinary_w4_non_axis_source_edges_excluded"] == [
        f"{wall.wall_candidate_id}:diagonal-original"
    ]
    assert not result["host_binding_granted"]
    assert not result["firm_area_granted"]


def test_original_source_byte_mutation_abstains_before_w4_promotion():
    """Even an apparently cached producer revision cannot erase a SHA error."""
    source, scope, selectors = _fixture()
    fake_authority = object.__new__(PhysicalWallCandidateAuthority)
    source._producer._store.source_bytes_by_revision[scope.revision_id] = (
        b"mutated source bytes"
    )
    with pytest.raises(ValueError, match="immutable original source PDF"):
        bridge(
            source, wall_authority=fake_authority,
            wall_selector=scope, opening_selectors=selectors,
        )


def test_duplicate_opening_selectors_are_not_equated_to_complete_source_roster(monkeypatch):
    """Openings must never be counted using caller-supplied repeated addresses."""
    from dataclasses import replace
    from types import SimpleNamespace as NS
    from pb_migration_contracts import EvidenceResolutionStatus
    from pb_physical_wall_candidate_authority import PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED

    source, scope, selectors = _fixture()
    fake_authority = object.__new__(PhysicalWallCandidateAuthority)
    fake_scope = NS(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        equivalence=object(),
        records=(),
        document_id=scope.document_id,
        revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        page_id=scope.page_id,
        decision_scope_id=scope.decision_scope_id,
    )
    monkeypatch.setattr(
        PhysicalWallCandidateAuthority, "resolve_scope",
        lambda self, selected: fake_scope,
    )
    result = bridge(
        source, wall_authority=fake_authority,
        wall_selector=scope, opening_selectors=(selectors[0], selectors[0]),
    )
    assert result["status"] == EvidenceResolutionStatus.ABSTAINED.value
    assert not result["opening_roster_complete_proven"]
    assert not result["host_binding_granted"]
    assert not result["opening_count_granted"]
