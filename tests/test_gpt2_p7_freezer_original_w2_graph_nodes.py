"""Original producer W2 graph replay is identity-gated, not wall repair."""
from types import SimpleNamespace as N
import pytest
from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
    trace_exact_source_w2_nodes as trace,
)


def fixture():
    edge = {
        "id": "split_1", "x1": 0.0, "y1": 0.0,
        "x2": 10.0, "y2": 0.0, "a": 0, "b": 1,
        "primitive_lineage": {"source_primitive_ids": ["d2i0"]},
    }
    graph = {
        "edges": [edge],
        "nodes": [
            {"id": 0, "x": .2, "y": .1, "samples": 2, "degree": 1},
            {"id": 1, "x": 10., "y": 0., "samples": 1, "degree": 1},
        ]
    }
    wall = N(candidate_id="wall_source_1", centerline_pts=((.2,.1),(10.,0.)))
    fragment = N(
        edge_id="split_1", geometry=(0.,0.,10.,0.),
        source_primitive_ids=("d2i0",)
    )
    scope = N(records=(
        N(wall_candidate_id="wall_source_1",wall_candidate=wall,
          source_edge_fragments=(fragment,)),
    ))
    return scope, graph, (wall,)


def test_original_source_replay_reports_snapped_centroid_without_grant():
    scope, graph, walls = fixture()
    result = trace(
        original_wall_scope=scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=("wall_source_1",)
    )
    assert result["status"] == "EXACT_ORIGINAL_W2_W4_REPLAY_NODES_OBSERVED"
    assert result["original_w4_candidate_count"] == 1
    node = result["selected_original_w4_node_rows"][0][
        "w2_surviving_fragment_nodes"][0]["endpoints"][0]
    assert node["source_snap_samples"] == 2
    assert node["original_source_endpoint_pdf_pts"] == [0.,0.]
    assert node["w2_graph_snapped_node_pdf_pts"] == [.2,.1]
    assert node["original_endpoint_vs_snapped_node_displacement_pt"] > 0
    assert node["exact_node_incident_original_source_edges"][0][
        "original_indexed_parent_ids"] == ["d2i0"]
    assert not result["source_structural_role_granted"]
    assert not result["room_or_metric_published"]


@pytest.mark.parametrize("corrupt,reason", [
    ("wall_path","original_w4_centerline_replay_drift"),
    ("w2_parent","original_w2_fragment_source_or_geometry_drift"),
    ("w2_geometry","original_w2_fragment_source_or_geometry_drift"),
    ("missing_node","original_w2_endpoint_snap_node_unavailable"),
    ("foreign_wall","original_w4_candidate_universe_drift"),
    ("duplicate_node","original_w2_graph_duplicate_identity"),
])
def test_original_production_source_parity_defects_fail_closed(corrupt, reason):
    scope, graph, walls = fixture()
    if corrupt == "wall_path":
        walls = (N(candidate_id="wall_source_1",
                   centerline_pts=((.5,.1),(10.,0.))),)
    elif corrupt == "w2_parent":
        scope.records[0].source_edge_fragments[0].source_primitive_ids = ("forged",)
    elif corrupt == "w2_geometry":
        scope.records[0].source_edge_fragments[0].geometry = (0.,0.,9.,0.)
    elif corrupt == "missing_node":
        graph["nodes"] = graph["nodes"][1:]
    elif corrupt == "foreign_wall":
        walls = (N(candidate_id="foreign_wall",
                   centerline_pts=((.2,.1),(10.,0.))),)
    elif corrupt == "duplicate_node":
        graph["nodes"].append(dict(graph["nodes"][0]))
    with pytest.raises(ValueError, match=reason):
        trace(original_wall_scope=scope, graph=graph,
              reconstructed_walls=walls, selected_wall_ids=("wall_source_1",))


def test_unknown_or_duplicate_original_wall_selector_never_grants():
    scope, graph, walls = fixture()
    for keys in (
        ("wall_source_1", "wall_source_1"),
        ("foreign",),
        (),
    ):
        with pytest.raises(ValueError):
            trace(original_wall_scope=scope, graph=graph,
                  reconstructed_walls=walls, selected_wall_ids=keys)



def test_mixed_exact_source_coordinates_at_one_w2_node_are_diagnostic_only():
    scope, graph, walls = fixture()
    # Three original source lines are grouped at one W2 snapped node,
    # but the source-native endpoints are distinct.
    for num, x in (("other_a", -1.), ("other_b", 1.)):
        graph["edges"].append({
            "id": num, "a": 0, "b": 1,
            "x1": x, "y1": 0., "x2": 10., "y2": 0.,
            "primitive_lineage": {"source_primitive_ids": ["native_"+num]},
        })
    got=trace(
        original_wall_scope=scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=("wall_source_1",)
    )
    node=got["selected_original_w4_node_rows"][0][
        "w2_surviving_fragment_nodes"][0]["endpoints"][0]
    assert node["retained_native_coordinate_cluster_count"] == 3
    assert node["mixed_original_coordinates_at_snapped_node"]
    assert [x["retained_incident_endpoint_count"]
            for x in node["retained_original_coordinate_groups"]] == [1,1,1]
    assert all("indexed_parent_source_ids" in x for x in node["retained_original_coordinate_groups"])
    assert not node["snap_samples_equal_retained_incidents"]
    assert not got["source_structural_role_granted"]


def test_genuine_replayed_w3_ambiguous_junction_cannot_grant_wall():
    scope, graph, walls = fixture()
    j = N(
        node_id="junc_native_1", position_pt=(.2,.1),
        junction_type=N(value="ambiguous"),
        status=N(value="abstained"),
        reason_codes=("original_source_role_unresolved",),
        incident_wall_candidate_ids=("split_1",),
    )
    got=trace(
        original_wall_scope=scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=("wall_source_1",),
        junctions=(j,),
    )
    node=got["selected_original_w4_node_rows"][0][
        "w2_surviving_fragment_nodes"][0]["endpoints"][0]
    assert node["replayed_original_w3_junction_candidates"] == [{
        "original_w3_node_identity":"junc_native_1",
        "original_w3_junction_type":"ambiguous",
        "original_w3_junction_status":"abstained",
        "original_w3_reason_codes":["original_source_role_unresolved"],
        "w3_incident_edge_ids":["split_1"],
        "source_structural_role_granted":False,
    }]
    assert not got["room_or_metric_published"]


def test_foreign_or_nonfinite_w3_junction_replay_fails_closed():
    scope, graph, walls = fixture()
    j = N(node_id="junk",position_pt=(float("nan"),0.))
    with pytest.raises(ValueError,match="original_w3_junction_position_invalid"):
        trace(original_wall_scope=scope,graph=graph,
              reconstructed_walls=walls,selected_wall_ids=("wall_source_1",),
              junctions=(j,))
