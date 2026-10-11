"""A snapped node pair never proves original source lines physically identical."""
from copy import deepcopy
import pytest

from pb_wall_room_topology_junction_classifier import deduplicate_coincident_edges
from tools.diag_gptmax_raster_positive_pixel_source import (
    _nonpublishing_w3_snap_pair_source_losses,
)


def graph():
    a = dict(id="edge-a", a=0, b=1, x1=10.0, y1=10.0,
             x2=20.0, y2=10.0,
             primitive_lineage={"source_primitive_ids": ["original-source-a"]})
    b = dict(id="edge-b", a=1, b=0, x1=20.0, y1=11.0,
             x2=10.0, y2=11.0,
             primitive_lineage={"source_primitive_ids": ["original-source-b"]})
    return {"nodes": [
        {"id": 0, "degree": 2}, {"id": 1, "degree": 2}],
        "edges": [a, b]}


def audit(original):
    output, removed = deduplicate_coincident_edges(original)
    return _nonpublishing_w3_snap_pair_source_losses(original, output, removed)


def test_real_dedup_node_alias_is_not_original_geometry_equivalence():
    source = graph()
    before = deepcopy(source)
    rows = audit(source)
    assert len(rows) == 1
    row = rows[0]
    assert row["removed_edge_id"] == "edge-b"
    assert row["retained_edge_id"] == "edge-a"
    assert row["max_endpoint_displacement_pt"] == 1.0
    assert row["source_parent_sets_disjoint"]
    assert row["same_actual_snapped_node_pair"]
    assert all(row[k] is False for k in
               ("physically_distinct_wall_lines_proven",
                "source_parent_transfer_allowed","host_publication_allowed"))
    assert before == source


def test_exact_same_original_geometry_is_still_not_a_new_host():
    source = graph()
    source["edges"][1].update(x1=20.0, y1=10.0, x2=10.0, y2=10.0)
    row, = audit(source)
    assert row["max_endpoint_displacement_pt"] == 0.0
    assert row["host_publication_allowed"] is False


@pytest.mark.parametrize("mutator", [
    lambda g: g["edges"][1].update(id="edge-a"),
    lambda g: g["edges"][1].update(x1=float("inf")),
    lambda g: g["edges"][1].update(x1=True),
    lambda g: g["edges"][1].update(x1=20.0, y1=11.0, x2=20.0, y2=11.0),
    lambda g: g["edges"][1].update(primitive_lineage={
        "source_primitive_ids": ["duplicate", "duplicate"]}),
    lambda g: g["edges"][1].update(primitive_lineage={
        "source_primitive_ids": [False]}),
])
def test_bad_source_edge_receipt_fail_closed(mutator):
    source = graph()
    mutator(source)
    with pytest.raises((TypeError, ValueError)):
        audit(source)


def test_cross_node_pair_does_not_create_a_false_removed_edge():
    source = graph()
    source["nodes"].append({"id": 2, "degree": 1})
    source["edges"][1]["b"] = 2
    assert audit(source) == []


@pytest.mark.parametrize("damage", [
    "geometry", "tiny_geometry", "parent", "foreign_id", "blank_id",
    "missing_removed", "overlap", "duplicate_removed", "non_string_removed",
    "foreign_node", "boolean_node", "duplicate_node", "missing_node",
])
def test_actual_w3_output_must_partition_and_preserve_original_w2(damage):
    original = graph()
    output, removed = deduplicate_coincident_edges(original)
    output = deepcopy(output)
    if damage == "geometry": output["edges"][0]["y1"] += 1
    elif damage == "tiny_geometry": output["edges"][0]["y1"] += 1e-10
    elif damage == "parent":
        output["edges"][0]["primitive_lineage"]["source_primitive_ids"] = ["borrowed"]
    elif damage == "foreign_id": output["edges"][0]["id"] = "foreign"
    elif damage == "blank_id": output["edges"][0]["id"] = " "
    elif damage == "missing_removed": removed = []
    elif damage == "overlap": removed = ["edge-a"]
    elif damage == "duplicate_removed": removed.append(removed[0])
    elif damage == "non_string_removed": removed = [None]
    elif damage == "foreign_node": original["edges"][1]["b"] = 17
    elif damage == "boolean_node": original["edges"][1]["b"] = False
    elif damage == "duplicate_node": original["nodes"].append(deepcopy(original["nodes"][0]))
    else: original["nodes"].pop()
    before = deepcopy((original, output, removed))
    with pytest.raises(ValueError):
        _nonpublishing_w3_snap_pair_source_losses(original, output, removed)
    assert (original, output, removed) == before


def test_missing_parent_inventory_stays_negative_without_disjointness_claim():
    original = graph()
    original["edges"][1]["primitive_lineage"]["source_primitive_ids"] = []
    row, = audit(original)
    assert row["removed_source_observation_ids"] == []
    assert row["source_parent_inventory_complete"] is False
    assert row["source_parent_sets_disjoint"] is False
    assert row["host_publication_allowed"] is False


def test_complete_original_census_has_deterministic_loss_order_without_mutation():
    original = graph()
    third = deepcopy(original["edges"][1])
    third.update(id="edge-c", y1=12., y2=12.)
    third["primitive_lineage"]["source_primitive_ids"] = ["original-source-c"]
    original["edges"].append(third)
    output, removed = deduplicate_coincident_edges(original)
    before = deepcopy((original, output, removed))
    expected = _nonpublishing_w3_snap_pair_source_losses(original, output, removed)
    assert expected == _nonpublishing_w3_snap_pair_source_losses(original, output, list(reversed(removed)))
    assert (original, output, removed) == before


def test_finite_source_coordinates_cannot_yield_infinite_displacement():
    original = graph()
    original["edges"][0].update(x1=-1e308, y1=-1e308, x2=-1e308, y2=1e308)
    original["edges"][1].update(x1=1e308, y1=1e308, x2=1e308, y2=-1e308)
    with pytest.raises(ValueError, match="displacement"):
        audit(original)
