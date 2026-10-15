"""Source-fragment overlap cannot be substituted for physical W4 equivalence."""
from types import SimpleNamespace as Node

from pb_g17_w4_equivalence_competitor_shadow import (
    _positive_collinear_source_overlap,
    compare_g17_to_ordinary_w4_shadow,
)


def fragment(edge_id, geometry, raw):
    return Node(edge_id=edge_id, geometry=geometry, source_primitive_ids=(raw,))


def record(wall_id, fragments, raw, *, identity=None):
    return Node(
        wall_candidate_id=wall_id,
        physical_identity=Node(
            source_primitive_ids=tuple(raw),
            candidate_identity_id=identity or "w2:" + wall_id,
            usable=True,
        ),
        source_edge_fragments=tuple(fragments),
    )


def flank(*records, positive=True):
    return Node(source_ink_supported=positive, exact_coordinate_records=tuple(records))


def test_only_positive_collinear_overlap_is_a_geometric_candidate():
    a = (0., 1., 10., 1.)
    assert _positive_collinear_source_overlap(a, (3., 1., 6., 1.))
    assert _positive_collinear_source_overlap((1., 0., 1., 10.), (1., 5., 1., 12.))
    assert not _positive_collinear_source_overlap(a, (10., 1., 12., 1.))
    assert not _positive_collinear_source_overlap(a, (3., 1.2, 6., 1.2))
    assert not _positive_collinear_source_overlap(a, (3., 0., 3., 5.))
    assert not _positive_collinear_source_overlap((0., 0., 0., 0.), (0., 0., 0., 0.))
    assert not _positive_collinear_source_overlap((0., 0., float("inf"), 0.), a)


def test_enumerates_all_competing_w4_members_without_selecting_host():
    source = flank(record("g17", [fragment("g0", (0., 1., 10., 1.), "raster_opening_primitive:abc")],
                          ("raster_opening_primitive:abc",)))
    ordinary = [
        record("w2", [fragment("w2e", (5., 1., 9., 1.), "raster_segment:two")], ("raster_segment:two",)),
        record("w1", [fragment("w1e", (2., 1., 7., 1.), "raster_segment:one")], ("raster_segment:one",)),
        record("w3", [fragment("w3e", (2., 2., 7., 2.), "raster_segment:three")], ("raster_segment:three",)),
    ]
    report = compare_g17_to_ordinary_w4_shadow([source], ordinary)
    row = report["flanks"][0]
    assert [r["w4_wall_candidate_id"] for r in row["competing_ordinary_w4"]] == ["w1", "w2"]
    assert row["source_ancestry_shared_w4"] == []
    assert row["first_blocker"] == "ordinary_w4_same_source_ancestry_unavailable"
    assert report["ordinary_w4_records_examined"] == 3
    assert not any(report[k] for k in (
        "physical_wall_role_granted", "physical_wall_equivalence_granted",
        "host_binding_granted", "metric_quantity_granted",
        "ordinary_w4_universe_complete_proven",
    ))
    assert compare_g17_to_ordinary_w4_shadow([source], tuple(reversed(ordinary))) == report


def test_direct_ancestry_and_unique_match_still_cannot_grant_equivalence():
    source = flank(record("g", [fragment("g0", (0., 0., 8., 0.), "raw:a")], ("raw:a",)))
    ordinary = [record("w", [fragment("w0", (0., 0., 8., 0.), "raw:a")], ("raw:a",))]
    report = compare_g17_to_ordinary_w4_shadow([source], ordinary)
    row = report["flanks"][0]
    assert len(row["source_ancestry_shared_w4"]) == 1
    assert row["first_blocker"] == "cross_scope_wall_role_and_equivalence_unproven"
    assert not row["physical_wall_equivalence_granted"]
    assert not row["competing_ordinary_w4"][0]["independently_proven_cross_source_equivalence"]


def test_non_solid_original_flank_remains_unavailable_even_with_matching_wall():
    ordinary = [record("w", [fragment("w0", (0., 0., 8., 0.), "raw:a")], ("raw:a",))]
    report = compare_g17_to_ordinary_w4_shadow([flank(positive=False)], ordinary)
    assert not report["flanks"][0]["competing_ordinary_w4"]
    assert report["flanks"][0]["first_blocker"] == "g17_original_source_ink_unavailable"


def test_duplicates_and_unmatched_source_edges_are_not_dropped_or_elected():
    source = flank(record("g", [
        fragment("g0", (0., 1., 5., 1.), "g17:one"),
        fragment("g1", (0., 2., 5., 2.), "g17:two"),
    ], ("g17:one", "g17:two")))
    ordinary = [
        record("w", [fragment("w0", (0., 1., 5., 1.), "segment:a")], ("segment:a",), identity="wall:a"),
        record("w", [fragment("w1", (0., 1., 5., 1.), "segment:b")], ("segment:b",), identity="wall:b"),
    ]
    report = compare_g17_to_ordinary_w4_shadow([source], ordinary)
    assert report["ordinary_w4_candidate_address_collisions"] == ["w"]
    assert len(report["flanks"][0]["competing_ordinary_w4"]) == 2
    assert report["flanks"][0]["unmatched_g17_source_edges"] == ["g1"]
    assert report["flanks"][0]["g17_edge_count"] == 2
    assert not report["host_binding_granted"]


def test_coincident_g17_graph_addresses_are_reported_as_blocker():
    source = flank(
        record("ga", [fragment("split_0", (0., 0., 5., 0.), "g17:a")], ("g17:a",)),
        record("gb", [fragment("split_0", (0., 1., 5., 1.), "g17:b")], ("g17:b",)),
    )
    row = compare_g17_to_ordinary_w4_shadow([source], [])["flanks"][0]
    assert row["duplicate_g17_edge_addresses"] == ["split_0"]
    assert row["first_blocker"] == "g17_graph_edge_address_collision"
    assert not row["physical_wall_equivalence_granted"]
