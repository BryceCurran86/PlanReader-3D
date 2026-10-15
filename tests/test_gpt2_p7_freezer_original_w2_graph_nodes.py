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



def test_source_native_snap_cluster_spans_more_than_running_centroid_radius():
    scope, graph, walls = fixture()
    # Source-native endpoint extent is intentionally > the 2.5pt centroid
    # admission radius. Audit that fact but do NOT change source W2 graph.
    for index, x in enumerate((0., 2.880005)):
        graph["edges"].append({
            "id": f"split_lookalike_{index}",
            "a": 0, "b": 1,
            "x1": x, "y1": 0., "x2": 10., "y2": 0.,
            "primitive_lineage": {
                "source_primitive_ids": [f"d_native_{index}"]
            },
        })
    prior = [(row["id"], row["a"], row["b"]) for row in graph["edges"]]
    result = trace(
        original_wall_scope=scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=("wall_source_1",)
    )
    node = result["selected_original_w4_node_rows"][0][
        "w2_surviving_fragment_nodes"][0]["endpoints"][0]
    assert node["source_native_retained_endpoint_diameter_pdf_pt"] == pytest.approx(2.880005)
    assert node["producer_nominal_gap_snap_tolerance_pdf_pt"] == 2.5
    assert node["diameter_exceeds_nominal_tolerance_diagnostic_only"]
    assert node["centroid_snap_cluster_membership_not_reversed_or_changed"]
    assert [(row["id"], row["a"], row["b"]) for row in graph["edges"]] == prior
    assert not result["source_structural_role_granted"]


def test_source_native_single_coordinate_cluster_does_not_claim_problem():
    scope, graph, walls = fixture()
    result = trace(
        original_wall_scope=scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=("wall_source_1",)
    )
    node = result["selected_original_w4_node_rows"][0][
        "w2_surviving_fragment_nodes"][0]["endpoints"][0]
    assert node["source_native_retained_endpoint_diameter_pdf_pt"] == 0.
    assert not node["diameter_exceeds_nominal_tolerance_diagnostic_only"]
    assert not result["room_or_metric_published"]



def _original_stage_a_source(x1, y1, x2, y2, identity):
    return {
        "id": identity, "x1": float(x1), "y1": float(y1),
        "x2": float(x2), "y2": float(y2), "kind": "line",
        "width": .48, "stroke": (0.,0.,0.), "layer": "",
        "dashes": "",
    }


def test_original_all_split_snap_samples_include_collapsed_edges():
    from pb_wall_room_topology_stage_a import (
        _segments_to_point_pairs, split_segments_at_intersections,
        _point_pairs_to_segment_dicts, _snap_geometry_indexed,
    )
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        inspect_all_original_snap_inputs_for_selected_nodes,
    )
    source = [_original_stage_a_source(0., 0., 1., 0., "original_short")]
    split = _point_pairs_to_segment_dicts(
        split_segments_at_intersections(_segments_to_point_pairs(source)),
        source_segments=source,
    )
    snapped = _snap_geometry_indexed(
        split, include_endpoint_assignments=True
    )
    assert not snapped["edges"], "short snap-collapsed original source has zero edges"
    assert snapped["nodes"][0]["samples"] == 2
    result = inspect_all_original_snap_inputs_for_selected_nodes(
        graph=snapped, scoped_inputs=source, selected_node_ids=(0,)
    )
    row = result["selected_original_node_rows"][0]
    assert row["original_producer_snap_sample_count"] == 2
    assert len(row["all_original_split_endpoint_receipts"]) == 2
    assert all("original_short" in record["original_source_primitive_ids"]
               for record in row["all_original_split_endpoint_receipts"])
    assert row["all_input_samples_independently_recovered"]
    assert not result["new_firm_or_physical_room"]


def test_original_all_split_snap_assignments_parity_and_no_mutation():
    from pb_wall_room_topology_stage_a import (
        build_wall_graph_for_viewport,
    )
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        inspect_all_original_snap_inputs_for_selected_nodes as inspect,
    )
    inputs = [
        _original_stage_a_source(0.,0.,10.,0.,"parent_A"),
        _original_stage_a_source(0.,1.,10.,1.,"parent_B"),
    ]
    before = repr(inputs)
    graph = build_wall_graph_for_viewport(inputs)
    result = inspect(
        graph=graph,scoped_inputs=inputs,selected_node_ids=(0,)
    )
    assert result["status"] == "ORIGINAL_W2_ALL_SPLIT_ENDPOINT_INPUTS_REPLAY_VERIFIED"
    assert result["selected_original_node_rows"][0]["all_input_samples_independently_recovered"]
    assert repr(inputs)==before
    graph["nodes"][0]["x"] += .01
    with pytest.raises(ValueError,match="original_snap_node_centroid_or_sample_drift"):
        inspect(graph=graph,scoped_inputs=inputs,selected_node_ids=(0,))


def test_original_all_split_input_rejects_foreign_selected_nodes_and_sample_drift():
    from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        inspect_all_original_snap_inputs_for_selected_nodes as inspect,
    )
    inputs = [_original_stage_a_source(0.,0.,10.,0.,"parent_A")]
    graph = build_wall_graph_for_viewport(inputs)
    with pytest.raises(ValueError,match="original_selected_snap_node_unavailable"):
        inspect(graph=graph,scoped_inputs=inputs,selected_node_ids=(999,))
    graph["nodes"][0]["samples"] += 1
    with pytest.raises(ValueError,match="original_snap_node_centroid_or_sample_drift"):
        inspect(graph=graph,scoped_inputs=inputs,selected_node_ids=(0,))



def test_original_source_graphic_style_preserves_all_competing_parent_records():
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        _indexed_original_source_style_receipts,
    )
    source = {
        "source_primitive_ids": ["d2i0", "d1i0"],
        "source_records": [
            {"id": "d1i0", "kind": "line", "kind_present": True,
             "stroke_present": True, "stroke": (0.,0.,0.),
             "width_present": True, "width": .48,
             "fill_present": False, "layer_present": True, "layer": "WALL",
             "page_coords_present": True,
             "x1": 0., "y1": 0., "x2": 1., "y2": 0.},
            {"id": "d2i0", "kind": "line", "kind_present": True,
             "stroke_present": False, "fill_present": True,
             "fill": (1.,1.,1.), "width_present": False,
             "page_coords_present": True,
             "x1": 0., "y1": 0., "x2": 1., "y2": 0.},
        ],
    }
    initial = repr(source)
    result = _indexed_original_source_style_receipts(source)
    assert result["status"] == "ORIGINAL_SPLIT_SOURCE_STYLE_RECEIPTS_COMPLETE"
    assert result["original_indexed_source_ids"] == ["d1i0", "d2i0"]
    assert not result["source_record_ids_missing_from_inventory"]
    assert len(result["source_style_records"]) == 2
    assert result["source_style_records"][0]["source_stroke_present"]
    assert not result["source_style_records"][1]["source_stroke_present"]
    assert result["source_style_records"][1]["source_fill"] == (1.,1.,1.)
    assert not result["physical_wall_or_annotation_role_granted"]
    assert repr(source) == initial


def test_original_source_graphic_style_conflicts_and_foreign_parent_fail_closed():
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        _indexed_original_source_style_receipts as style,
    )
    records = [
        {"id": "d1i0", "width_present": True, "width": .24},
        {"id": "d1i0", "width_present": True, "width": .48},
    ]
    result = style({"source_primitive_ids": ["d1i0"], "source_records": records})
    assert result["status"] == "ORIGINAL_SPLIT_SOURCE_STYLE_CONFLICT"
    assert result["competing_record_id_conflicts"] == ["d1i0"]
    assert len(result["source_style_records"]) == 2
    result = style({"source_primitive_ids": ["foreign"], "source_records": records})
    assert result["status"] == "ORIGINAL_SPLIT_SOURCE_STYLE_INCOMPLETE"
    assert result["source_record_ids_missing_from_inventory"] == ["foreign"]
    assert result["unindexed_source_record_ids"] == ["d1i0"]
    assert not result["physical_wall_or_annotation_role_granted"]


def test_missing_original_graphics_is_unknown_not_absent_paint():
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        _indexed_original_source_style_receipts as style,
    )
    for raw in (None, {}, {"source_primitive_ids": ["d1i0"],
                            "source_records": [{"id": None}]}):
        result = style(raw)
        assert result["status"] != "ORIGINAL_SPLIT_SOURCE_STYLE_RECEIPTS_COMPLETE"
        assert not result["physical_wall_or_annotation_role_granted"]


def test_real_split_input_trace_reports_source_styles_without_electing_roles():
    from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        inspect_all_original_snap_inputs_for_selected_nodes as inspect,
    )
    source = [_original_stage_a_source(0.,0.,10.,0.,"source_style_positive")]
    graph = build_wall_graph_for_viewport(source)
    before = repr(source)
    report = inspect(graph=graph,scoped_inputs=source,selected_node_ids=(0,))
    node = report["selected_original_node_rows"][0]
    assert node["all_input_samples_independently_recovered"]
    assert node["original_split_inputs_without_complete_style_receipts"] == []
    receipt = node["all_original_split_endpoint_receipts"][0][
        "original_split_input_graphic_style_receipt"
    ]
    assert receipt["status"] == "ORIGINAL_SPLIT_SOURCE_STYLE_RECEIPTS_COMPLETE"
    assert receipt["original_indexed_source_ids"] == ["source_style_positive"]
    assert not receipt["physical_wall_or_annotation_role_granted"]
    assert repr(source) == before



def test_source_graphic_receipts_reorder_preserves_original_style_candidates():
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        _indexed_original_source_style_receipts as style,
    )
    records=[
        {"id":"d10i0","stroke_present":True,"stroke":[.5,.5,.5]},
        {"id":"d20i0","stroke_present":True,"stroke":[0.,0.,0.]},
    ]
    before=repr(records)
    a=style({"source_primitive_ids":["d20i0","d10i0"],
             "source_records":records})
    b=style({"source_primitive_ids":["d10i0","d20i0"],
             "source_records":list(reversed(records))})
    assert a["status"] == b["status"] == "ORIGINAL_SPLIT_SOURCE_STYLE_RECEIPTS_COMPLETE"
    assert a["original_indexed_source_ids"]==b["original_indexed_source_ids"]
    assert {x["original_primitive_id"]: x["source_stroke"]
            for x in a["source_style_records"]} == {
        x["original_primitive_id"]: x["source_stroke"]
        for x in b["source_style_records"]
    }
    a["source_style_records"][0]["source_stroke"][0] = 77
    assert repr(records) == before
    assert all(not x["style_is_not_structural_or_drafting_role"] is False
               for x in b["source_style_records"])
    assert not b["physical_wall_or_annotation_role_granted"]



def test_independent_original_indexed_parent_ink_matches_producer_source_geometry():
    import fitz
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        verify_original_indexed_split_parent_ink as verify,
    )
    originals=[{"type":"s","color":(0.,0.,0.),"width":.48,
                "items":[("l",fitz.Point(0,0),fitz.Point(10,0))]}]
    style={
        "original_primitive_id":"d0i0",
        "original_native_geometry":[0.,0.,10.,0.],
        "original_native_page_coords_present":True,
    }
    node=[{"all_original_split_endpoint_receipts":[
        {"original_split_input_graphic_style_receipt":{
            "source_style_records":[style]}}
    ]}]
    before=repr(originals)
    result=verify(originals,node)
    assert result["original_indexed_parent_sources_all_correlated"]
    assert result["distinct_producer_source_parent_record_count"]==1
    assert result["original_indexed_parent_receipts"][0][
        "independent_original_pdf_source_status"] == (
        "INDEXED_ORIGINAL_INK_FULL_SOURCE_SPAN"
    )
    assert not result["source_structural_wall_role_granted"]
    assert repr(originals)==before


def test_independent_native_source_rejects_foreign_and_noncollinear_original_parent():
    import fitz
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        verify_original_indexed_split_parent_ink as verify,
    )
    ink=[{"type":"s","items":[
        ("l",fitz.Point(0,0),fitz.Point(10,0))]}]
    def record(identity,coords,present=True):
        return {
            "original_primitive_id":identity,
            "original_native_geometry":coords,
            "original_native_page_coords_present":present,
        }
    node=[{"all_original_split_endpoint_receipts":[{
        "original_split_input_graphic_style_receipt":{
            "source_style_records":[
                record("d0i0",[0.,1.,10.,1.]),
                record("d999i0",[0.,0.,10.,0.]),
                record("d0i0",[None,None,None,None],False),
            ]
        }}]}]
    result=verify(ink,node)
    statuses={q["independent_original_pdf_source_status"] for q in
              result["original_indexed_parent_receipts"]}
    assert statuses=={
        "INDEXED_SOURCE_GEOMETRY_CONFLICT",
        "INDEXED_SOURCE_LOOKUP_UNAVAILABLE",
        "PRODUCER_NATIVE_COORDS_UNAVAILABLE",
    }
    assert not result["original_indexed_parent_sources_all_correlated"]
    assert not result["room_or_metric_published"]


def test_original_split_ink_reversal_does_not_invent_second_physical_wall():
    import fitz
    from tools.diag_gpt2_p7_freezer_original_w2_graph_nodes import (
        verify_original_indexed_split_parent_ink as verify,
    )
    ink=[{"type":"f","fill":(1.,1.,1.),"items":[
        ("l",fitz.Point(10,0),fitz.Point(0,0))]}]
    rec={"original_primitive_id":"d0i0",
         "original_native_geometry":[0.,0.,10.,0.],
         "original_native_page_coords_present":True}
    node=[{"all_original_split_endpoint_receipts":[{
        "original_split_input_graphic_style_receipt":{
            "source_style_records":[rec,rec]}}]}]
    result=verify(ink,node)
    assert result["distinct_producer_source_parent_record_count"]==1
    assert result["original_indexed_parent_sources_all_correlated"]
    assert result["original_indexed_parent_receipts"][0][
        "independent_original_pdf_ink_evidence"][
        "original_native_paint_metadata_candidate_only"]["native_fill_color"] == [1.,1.,1.]
    assert not result["source_structural_wall_role_granted"]
