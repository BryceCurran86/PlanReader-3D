"""Live canonical opening identity is source geometry, not unique IDs."""
from __future__ import annotations

from dataclasses import replace

from pb_source_opening_identity_partition_shadow import (
    AMBIGUOUS,
    DISTINCT,
    SAME,
    cluster_live_canonical_opening_identities,
    compare_live_canonical_opening_identity,
    partition_unmapped_opening_outputs,
)
from tests.test_source_quarter_swing_opening_kind_shadow import _hosted


def test_different_ids_are_not_distinct_without_source_extents() -> None:
    left = replace(_hosted(geom=(0.0, 0.0, 1.0, 0.0), opening_id="a"), source_geometries=())
    right = replace(_hosted(geom=(10.0, 10.0, 11.0, 10.0), opening_id="b"), source_geometries=())
    assert compare_live_canonical_opening_identity(left, right) == AMBIGUOUS


def test_shared_jamb_vertex_is_the_same_opening() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    hinge = _hosted(geom=(50.0, 50.0, 50.0, 50.85), opening_id="hinge")
    assert compare_live_canonical_opening_identity(hosted, hinge) == SAME


def test_closed_tip_is_distinct_from_the_hinge_jamb() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    tip = _hosted(geom=(49.72, 25.0, 52.5, 25.0), opening_id="tip")
    assert compare_live_canonical_opening_identity(hosted, tip) == DISTINCT


def test_crossing_segments_stay_ambiguous() -> None:
    first = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="a")
    second = _hosted(geom=(50.0, 49.2, 50.0, 52.5), opening_id="b")
    assert compare_live_canonical_opening_identity(first, second) == AMBIGUOUS


def test_clusters_join_the_shared_jamb_only() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    hinge = _hosted(geom=(50.0, 50.0, 50.0, 50.85), opening_id="hinge")
    tip = _hosted(geom=(49.72, 25.0, 52.5, 25.0), opening_id="tip")
    clusters = cluster_live_canonical_opening_identities((hinge, hosted, tip))
    members = {frozenset(cluster) for cluster in clusters}
    assert frozenset({"hosted", "hinge"}) in members
    assert frozenset({"tip"}) in members


def test_unmapped_outputs_keep_equal_area_neighbours() -> None:
    first = replace(
        _hosted(geom=(0.0, 0.0, 2.0, 0.0), opening_id="extra-a"),
        area_m2=1.2,
        host_wall_id="wall-a",
    )
    second = replace(
        _hosted(geom=(50.0, 50.0, 52.0, 50.0), opening_id="extra-b"),
        area_m2=1.2,
        host_wall_id="wall-b",
    )
    matched = replace(_hosted(geom=(90.0, 90.0, 92.0, 90.0), opening_id="matched"))
    rows = partition_unmapped_opening_outputs(
        (first, second, matched),
        matched_physical_ids=("matched",),
    )
    assert len(rows) == 2
    assert {row["canonical_opening_id"] for row in rows} == {"extra-a", "extra-b"}
    assert rows[0]["identities"]["extra-b"] == DISTINCT
    assert rows[0]["area_m2"] == rows[1]["area_m2"]
