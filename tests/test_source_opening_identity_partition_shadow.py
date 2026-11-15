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


def test_shared_jamb_vertex_without_aperture_stays_ambiguous() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    hinge = replace(
        _hosted(geom=(50.0, 50.0, 50.0, 50.85), opening_id="hinge"),
        host_wall_id=None,
        host_binding_record_id=None,
        host_frame_record_id=None,
        evidence_ids=("hinge",),
    )
    assert compare_live_canonical_opening_identity(hosted, hinge) == AMBIGUOUS


def test_shared_jamb_with_issued_host_receipt_is_the_same_opening() -> None:
    hosted = replace(
        _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted"),
        host_binding_record_id="opening_host_binding_v3_issued",
        evidence_ids=("hosted", "opening_host_binding_v3_issued"),
    )
    hinge = replace(
        _hosted(geom=(50.0, 50.0, 50.0, 50.85), opening_id="hinge"),
        host_binding_record_id="opening_host_binding_v3_issued",
        evidence_ids=("hinge", "opening_host_binding_v3_issued"),
    )
    assert compare_live_canonical_opening_identity(hosted, hinge) == SAME


def test_closed_tip_without_aperture_stays_ambiguous() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    tip = _hosted(geom=(49.72, 25.0, 52.5, 25.0), opening_id="tip")
    assert compare_live_canonical_opening_identity(hosted, tip) == AMBIGUOUS


def test_cross_page_identical_coordinates_are_distinct() -> None:
    page_three = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="page-3")
    page_nineteen = replace(page_three, page_id="19", canonical_opening_id="page-19", physical_opening_id="page-19")
    assert compare_live_canonical_opening_identity(page_three, page_nineteen) == DISTINCT


def test_different_viewports_on_the_same_page_are_distinct() -> None:
    first = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="vp-a")
    second = replace(
        _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="vp-b"),
        viewport_id="vp-other",
    )
    assert compare_live_canonical_opening_identity(first, second) == DISTINCT


def test_missing_viewport_does_not_prove_same() -> None:
    first = replace(_hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="a"), viewport_id=None)
    second = replace(_hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="b"), viewport_id=None)
    assert compare_live_canonical_opening_identity(first, second) == AMBIGUOUS


def test_adjacent_shared_jamb_doorways_stay_ambiguous() -> None:
    first = replace(
        _hosted(geom=(0.0, 0.0, 10.0, 0.0), opening_id="door-a"),
        host_binding_record_id="opening_host_binding_v3_a",
        evidence_ids=("door-a", "opening_host_binding_v3_a"),
    )
    second = replace(
        _hosted(geom=(10.0, 0.0, 10.0, 8.0), opening_id="door-b"),
        host_binding_record_id="opening_host_binding_v3_b",
        evidence_ids=("door-b", "opening_host_binding_v3_b"),
    )
    assert compare_live_canonical_opening_identity(first, second) == AMBIGUOUS


def test_crossing_segments_stay_ambiguous() -> None:
    first = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="a")
    second = _hosted(geom=(50.0, 49.2, 50.0, 52.5), opening_id="b")
    assert compare_live_canonical_opening_identity(first, second) == AMBIGUOUS


def test_clusters_do_not_join_a_shared_jamb_without_aperture() -> None:
    hosted = _hosted(geom=(49.72, 50.0, 52.5, 50.0), opening_id="hosted")
    hinge = replace(
        _hosted(geom=(50.0, 50.0, 50.0, 50.85), opening_id="hinge"),
        host_wall_id=None,
        host_binding_record_id=None,
        host_frame_record_id=None,
        evidence_ids=("hinge",),
    )
    tip = replace(
        _hosted(geom=(49.72, 25.0, 52.5, 25.0), opening_id="tip"),
        host_wall_id=None,
        host_binding_record_id=None,
        host_frame_record_id=None,
        evidence_ids=("tip",),
    )
    clusters = cluster_live_canonical_opening_identities((hinge, hosted, tip))
    members = {frozenset(cluster) for cluster in clusters}
    assert frozenset({"hosted"}) in members
    assert frozenset({"hinge"}) in members
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
    assert rows[0]["identities"]["extra-b"] == AMBIGUOUS
    assert rows[0]["area_m2"] == rows[1]["area_m2"]
