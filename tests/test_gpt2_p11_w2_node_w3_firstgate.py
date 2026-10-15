"""Fail-closed W2 graph/ W3 junction vs source fragment and W4 receipts."""
from types import SimpleNamespace
import pytest

from tools.diag_gpt2_p11_w2_graph_node_firstgate import (
    _endpoint_receipt, trace_original_w2_graph_nodes,
)


def fixture(*, node_shift=(0.2, 0.1), source_parent="d1i0", wrong_path=False):
    graph = {
        "nodes": [
            {"id":0, "x":0., "y":0., "degree":1},
            {"id":1, "x":10. + node_shift[0], "y":node_shift[1], "degree":2},
            {"id":2, "x":20., "y":0., "degree":1},
        ],
        "edges": [
            {"id":"e0","a":0,"b":1,"x1":0.,"y1":0.,"x2":10.,"y2":0.,
             "primitive_lineage":{"source_primitive_ids":("d1i0",)}},
            {"id":"e1","a":1,"b":2,"x1":10.,"y1":0.,"x2":20.,"y2":0.,
             "primitive_lineage":{"source_primitive_ids":("d1i0",)}},
        ],
    }
    def fragment(edge_id, geometry):
        return SimpleNamespace(
            edge_id=edge_id, geometry=geometry,
            source_primitive_ids=(source_parent,),
        )
    pts=((0.,0.),(10.+node_shift[0],node_shift[1]),(20.,0.))
    rec=SimpleNamespace(
        wall_candidate_id="wall-1",
        wall_candidate=SimpleNamespace(centerline_pts=pts),
        source_edge_fragments=(
            fragment("e0",(0.,0.,10.,0.)),
            fragment("e1",(10.,0.,20.,0.)),
        ),
    )
    scope=SimpleNamespace(records=(rec,))
    candidate=SimpleNamespace(
        candidate_id="wall-1",
        centerline_pts=pts if not wrong_path else ((0.,0.),(10.,0.),(20.,0.)),
    )
    negative=[{
        "source_w4_wall_id":"wall-1",
        "shadow_subedge_pdf_pts":[[0.,0.],[10.2,0.1]],
        "first_original_w2_w4_planar_geometry_gate":{
            "first_geometry_path_disagreement":
                "w4_candidate_path_has_no_surviving_w2_or_indexed_native_span"
        },
    }]
    w3=[SimpleNamespace(
        node_id="j1",position_pt=pts[1],status=SimpleNamespace(value="candidate"),
        junction_type=SimpleNamespace(value="l_corner"),
        incident_wall_candidate_ids=("e0","e1"),
    )]
    return scope,negative,graph,w3,[candidate]


def test_snapped_w2_node_displacement_retained_as_source_negative_not_room():
    scope,negative,graph,w3,w4=fixture()
    report=trace_original_w2_graph_nodes(
        original_wall_scope=scope,first_failures=negative,
        graph=graph,junctions=w3,assembled_walls=w4,
    )
    assert report["reconstructed_w2_surviving_edge_count"] == 2
    assert report["native_negative_w4_face_subedge_count"] == 1
    row,=report["original_w2_node_junction_first_gate_rows"]
    assert row["producer_w4_vs_replayed_w2_w3_path_equal"]
    assert not row["physical_wall_role_granted"]
    ends=row["w2_surviving_fragments"][0]["w2_graph_node_endpoints"]
    assert ends[1]["w2_edge_vs_graph_node_displacement_pt"] > 0.2
    assert ends[1]["w3_at_snapped_node_candidates"][0]["junction_source_node_id"] == "j1"
    assert report["new_commercial_quantities"]==[]


def test_source_exact_node_coordinate_still_not_structural_wall():
    scope,negative,graph,w3,w4=fixture(node_shift=(0.,0.))
    output=trace_original_w2_graph_nodes(
        original_wall_scope=scope,first_failures=negative,graph=graph,
        junctions=w3,assembled_walls=w4,
    )
    assert output["original_w2_node_junction_first_gate_rows"][0][
        "w2_surviving_fragments"][0]["w2_graph_node_endpoints"][1][
        "w2_edge_vs_graph_node_displacement_pt"] == 0.
    assert output["new_physical_wall_approved"] is False


def test_foreign_original_w2_parent_never_matches_replayed_graph():
    scope,negative,graph,w3,w4=fixture(source_parent="foreign-d2i0")
    with pytest.raises(ValueError,match="source_owned_w2_primitive_parent_lineage_drift"):
        trace_original_w2_graph_nodes(
            original_wall_scope=scope,first_failures=negative,graph=graph,
            junctions=w3,assembled_walls=w4,
        )


def test_w4_path_derived_from_wrong_node_is_rejected_not_rekeyed():
    scope,negative,graph,w3,w4=fixture(wrong_path=True)
    with pytest.raises(ValueError,match="original_w4_candidate_path_differs"):
        trace_original_w2_graph_nodes(
            original_wall_scope=scope,first_failures=negative,graph=graph,
            junctions=w3,assembled_walls=w4,
        )


def test_source_graph_missing_surviving_fragment_not_approvable():
    scope,negative,graph,w3,w4=fixture()
    graph["edges"].pop()
    with pytest.raises(ValueError,match="surviving_fragment_missing"):
        trace_original_w2_graph_nodes(
            original_wall_scope=scope,first_failures=negative,graph=graph,
            junctions=w3,assembled_walls=w4,
        )


def test_equal_candidate_id_not_enough_when_source_geometry_changes():
    scope,negative,graph,w3,w4=fixture()
    graph["edges"][0]["x2"]=10.5
    with pytest.raises(ValueError,match="fragment_geometry_drift"):
        trace_original_w2_graph_nodes(
            original_wall_scope=scope,first_failures=negative,graph=graph,
            junctions=w3,assembled_walls=w4,
        )


def test_replayed_node_is_not_allowed_to_disappear_or_duplicate():
    scope,negative,graph,w3,w4=fixture()
    graph["nodes"].append(dict(graph["nodes"][1]))
    with pytest.raises(ValueError,match="duplicate_node_index"):
        trace_original_w2_graph_nodes(
            original_wall_scope=scope,first_failures=negative,graph=graph,
            junctions=w3,assembled_walls=w4,
        )
