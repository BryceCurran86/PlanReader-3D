"""Tests for component-local wall-scope completeness shadow authority."""
from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_component_completeness_authority import (
    WALL_COMPONENT_BOUNDARY_WALL,
    WALL_COMPONENT_COMPLETE,
    WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE,
    WALL_COMPONENT_WITHHELD_GEOMETRY_UNAVAILABLE,
    _derive_scope_results,
)
from pb_wall_room_topology_contracts import JunctionType


def _wall(
    wall_id: str,
    *,
    raw_id: str,
    p1=(10.0, 10.0),
    p2=(40.0, 10.0),
    end_nodes=("n1", "n2"),
    junctions=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            centerline_pts=(p1, p2),
            end_node_ids=end_nodes,
            junction_types=junctions,
        ),
        physical_identity=SimpleNamespace(
            source_primitive_ids=(raw_id,),
        ),
    )


def _scope(
    *records,
    boundary_obs=(),
    ambiguous_obs=(),
    groups=(),
    bbox=(0.0, 0.0, 100.0, 100.0),
):
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=False,
        records=records,
        scope_kind="viewport",
        viewport_bbox=bbox,
        scope_boundary_observation_ids=tuple(boundary_obs),
        ambiguous_source_observation_ids=tuple(ambiguous_obs),
        equivalence=SimpleNamespace(equivalence_groups=tuple(groups)),
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        decision_scope_id="wall-source:viewport:1:vp:abc",
    )


def _seg(raw_id, x1, y1, x2, y2, *, obs=""):
    return {
        "id": raw_id,
        "source_observation_id": obs,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def test_unrelated_cropped_component_does_not_poison_isolated_component() -> None:
    a = _wall("wall-a", raw_id="raw-a", p1=(10.0, 20.0), p2=(40.0, 20.0), end_nodes=("a1", "a2"))
    b = _wall("wall-b", raw_id="raw-b", p1=(60.0, 60.0), p2=(90.0, 60.0), end_nodes=("b1", "b2"))
    scope = _scope(a, b, boundary_obs=("withheld-b",))
    segments = (
        _seg("raw-a", 10.0, 20.0, 40.0, 20.0, obs="obs-a"),
        _seg("raw-b", 60.0, 60.0, 90.0, 60.0, obs="obs-b"),
        _seg("raw-withheld", 0.0, 60.0, 65.0, 60.0, obs="withheld-b"),
    )

    results = _derive_scope_results(
        scope=scope,
        page_segments=segments,
        page_width=100.0,
        page_height=100.0,
    )

    assert results["wall-a"].status is EvidenceResolutionStatus.CORROBORATED
    assert results["wall-a"].record is not None
    assert results["wall-a"].reason_codes == (WALL_COMPONENT_COMPLETE,)

    assert results["wall-b"].status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE in results["wall-b"].reason_codes


def test_wall_component_with_dangling_end_on_viewport_boundary_abstains() -> None:
    wall = _wall(
        "wall-edge",
        raw_id="raw-edge",
        p1=(10.0, 30.0),
        p2=(100.0, 30.0),
        end_nodes=("e1", "e2"),
    )
    scope = _scope(wall)
    results = _derive_scope_results(
        scope=scope,
        page_segments=(_seg("raw-edge", 10.0, 30.0, 100.0, 30.0, obs="obs-edge"),),
        page_width=100.0,
        page_height=100.0,
    )
    assert results["wall-edge"].status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_COMPONENT_BOUNDARY_WALL in results["wall-edge"].reason_codes


def test_missing_withheld_geometry_blocks_every_component_fail_closed() -> None:
    a = _wall("wall-a", raw_id="raw-a")
    b = _wall("wall-b", raw_id="raw-b", p1=(60.0, 70.0), p2=(90.0, 70.0), end_nodes=("b1", "b2"))
    scope = _scope(a, b, boundary_obs=("missing",))
    segments = (
        _seg("raw-a", 10.0, 10.0, 40.0, 10.0, obs="obs-a"),
        _seg("raw-b", 60.0, 70.0, 90.0, 70.0, obs="obs-b"),
    )
    results = _derive_scope_results(
        scope=scope,
        page_segments=segments,
        page_width=100.0,
        page_height=100.0,
    )
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in results.values())
    assert all(
        WALL_COMPONENT_WITHHELD_GEOMETRY_UNAVAILABLE in r.reason_codes
        for r in results.values()
    )


def test_positive_equivalence_members_share_component_completeness_fate() -> None:
    a = _wall("wall-a", raw_id="raw-a", p1=(10.0, 50.0), p2=(40.0, 50.0), end_nodes=("a1", "a2"))
    b = _wall("wall-b", raw_id="raw-b", p1=(10.0, 55.0), p2=(40.0, 55.0), end_nodes=("b1", "b2"))
    scope = _scope(
        a,
        b,
        boundary_obs=("withheld",),
        groups=(("wall-a", "wall-b"),),
    )
    segments = (
        _seg("raw-a", 10.0, 50.0, 40.0, 50.0, obs="obs-a"),
        _seg("raw-b", 10.0, 55.0, 40.0, 55.0, obs="obs-b"),
        _seg("raw-x", 20.0, 0.0, 20.0, 52.0, obs="withheld"),
    )
    results = _derive_scope_results(
        scope=scope,
        page_segments=segments,
        page_width=100.0,
        page_height=100.0,
    )
    assert results["wall-a"].status is EvidenceResolutionStatus.ABSTAINED
    assert results["wall-b"].status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE in results["wall-a"].reason_codes


def test_disjoint_withheld_primitive_is_recorded_as_checked_evidence() -> None:
    wall = _wall("wall-a", raw_id="raw-a", p1=(10.0, 20.0), p2=(40.0, 20.0))
    scope = _scope(wall, ambiguous_obs=("withheld",))
    segments = (
        _seg("raw-a", 10.0, 20.0, 40.0, 20.0, obs="obs-a"),
        _seg("raw-x", 80.0, 60.0, 80.0, 90.0, obs="withheld"),
    )
    result = _derive_scope_results(
        scope=scope,
        page_segments=segments,
        page_width=100.0,
        page_height=100.0,
    )["wall-a"]
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.checked_withheld_observation_ids == ("withheld",)
    assert result.record.disjoint_withheld_observation_ids == ("withheld",)
