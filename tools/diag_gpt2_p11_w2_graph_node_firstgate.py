"""Source-owned W2 node / W3 junction receipts for W4-native-negative face edges.

Additive only: replay the real original source page, original source plan view,
and the exact W2 graph construction used by the W4 producer. Every referenced
fragment must agree with the already-produced W4 wall source record. A
different reconstruction ABSTAINS; none is authority to move or label a wall.
"""
from __future__ import annotations

import math

from pb_physical_wall_candidate_authority import (
    _decision_scope_id, _source_page_segments,
    _segment_fully_inside_bbox, _segment_lies_on_bbox_edge,
    _partition_opening_local_supplemental_segments,
    _filter_repeated_non_physical_drafting_primitives,
    _proven_filled_wall_strips, _filter_proven_wall_strip_geometry,
    is_structural_candidate_segment,
    _authenticated_viewports_from_rows, _viewport_decision_scope_id,
    _viewport_sibling_set_fingerprint,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from pb_viewport_segmentation import (
    segment_source_page_viewports, segmented_viewport_producer_fingerprint,
    _producer_fingerprint_payload, is_segment_page_viewports_product,
)


def _endpoint_receipt(edge, nodes, *, label):
    node_id = edge["a"] if label == "a" else edge["b"]
    n = nodes.get(node_id)
    if n is None:
        raise ValueError("w2_graph_endpoint_node_missing")
    raw = (
        (float(edge["x1"]), float(edge["y1"]))
        if label == "a" else
        (float(edge["x2"]), float(edge["y2"]))
    )
    node = (float(n["x"]), float(n["y"]))
    return {
        "w2_graph_node_index": node_id,
        "w2_graph_edge_endpoint_pdf_pts": list(raw),
        "w2_graph_snapped_node_pdf_pts": list(node),
        "w2_edge_vs_graph_node_displacement_pt": round(math.dist(raw, node), 9),
        "w2_graph_node_degree": n.get("degree"),
        "w2_graph_node_snap_input_sample_count": n.get("samples"),
        "w2_graph_node_merged_into_edge": n.get("merged_into_edge"),
    }


def trace_original_w2_graph_nodes(*, original_wall_scope, first_failures,
                                  graph, junctions, assembled_walls):
    """Strict identities before classifying graph-node and W4 path divergence."""
    producer = {x.wall_candidate_id: x for x in original_wall_scope.records}
    if len(producer) != len(original_wall_scope.records):
        raise ValueError("original_w4_producer_duplicated_wall_id")
    by_id = {str(e["id"]): e for e in graph["edges"] if not e.get("_removed")}
    if len(by_id) != len([e for e in graph["edges"] if not e.get("_removed")]):
        raise ValueError("replayed_w2_graph_duplicate_edge_id")
    nodes = {n["id"]: n for n in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise ValueError("replayed_w2_graph_duplicate_node_index")
    assembly = {x.candidate_id: x for x in assembled_walls}
    if len(assembly) != len(assembled_walls):
        raise ValueError("replayed_w4_assembly_duplicate_candidate")
    if set(assembly) != set(producer):
        raise ValueError("source_owned_w2_w3_w4_candidate_universe_drift")

    node_active_edge_source_universe = {}
    for source_edge in by_id.values():
        for endpoint_name in ("a", "b"):
            raw_point = (
                [float(source_edge["x1"]), float(source_edge["y1"])]
                if endpoint_name == "a" else
                [float(source_edge["x2"]), float(source_edge["y2"])]
            )
            node_active_edge_source_universe.setdefault(
                source_edge[endpoint_name], []
            ).append({
                "source_w2_edge_id": str(source_edge["id"]),
                "source_graph_incident_endpoint": endpoint_name,
                "original_preserved_w2_edge_endpoint_pdf_pts": raw_point,
                "original_indexed_source_primitive_ids": sorted(
                    str(p) for p in (
                        source_edge.get("primitive_lineage") or {}
                    ).get("source_primitive_ids", ())
                ),
            })
    for source_rows in node_active_edge_source_universe.values():
        source_rows.sort(key=lambda x: (
            x["source_w2_edge_id"], x["source_graph_incident_endpoint"]
        ))

    incidents = {}
    for item in junctions:
        center = tuple(round(float(v), 6) for v in item.position_pt)
        incidents.setdefault(center, []).append({
            "junction_source_node_id": item.node_id,
            "junction_type": item.junction_type.value,
            "junction_status": item.status.value,
            "w3_incident_edge_ids": sorted(item.incident_wall_candidate_ids),
        })

    rows = []
    for edge in first_failures:
        wall_id = edge["source_w4_wall_id"]
        rec = producer.get(wall_id)
        if rec is None:
            raise ValueError("original_negative_w4_wall_unavailable")
        expected_path = tuple(tuple(x) for x in rec.wall_candidate.centerline_pts)
        replay_path = tuple(tuple(x) for x in assembly[wall_id].centerline_pts)
        if expected_path != replay_path:
            raise ValueError("original_w4_candidate_path_differs_from_w2_w3_replay")
        fragment_rows=[]
        for frag in rec.source_edge_fragments:
            source_edge=by_id.get(str(frag.edge_id))
            if source_edge is None:
                raise ValueError("source_owned_w2_surviving_fragment_missing_from_graph")
            geometry=tuple(float(source_edge[k]) for k in ("x1","y1","x2","y2"))
            if geometry != tuple(float(v) for v in frag.geometry):
                raise ValueError("source_owned_w2_fragment_geometry_drift")
            w2parents=set((source_edge.get("primitive_lineage") or {}).get("source_primitive_ids",()))
            if set(frag.source_primitive_ids)!=set(str(p) for p in w2parents):
                raise ValueError("source_owned_w2_primitive_parent_lineage_drift")
            endpoints=[_endpoint_receipt(source_edge,nodes,label=label) for label in ("a","b")]
            for end in endpoints:
                k=tuple(round(float(x),6) for x in end["w2_graph_snapped_node_pdf_pts"])
                end["w3_at_snapped_node_candidates"] = incidents.get(k,[])
                node_id=end["w2_graph_node_index"]
                end["all_original_source_incident_w2_edges_at_same_graph_node"] = (
                    node_active_edge_source_universe.get(node_id, [])
                )
                end["original_source_incidence_count"] = len(
                    node_active_edge_source_universe.get(node_id, [])
                )
            fragment_rows.append({
                "source_owned_w2_fragment_id":str(frag.edge_id),
                "source_w2_fragment_line_pdf_pts": list(geometry),
                "source_w2_original_primitive_ids": sorted(w2parents),
                "w2_graph_node_endpoints":endpoints,
                "full_w2_replayed_lineage_parity":True,
            })
        if not fragment_rows:
            raise ValueError("unsupported_w4_wall_has_no_surviving_w2_fragments")
        rows.append({
            "source_w4_wall_id":wall_id,
            "source_negative_face_subedge_pdf_pts":edge["shadow_subedge_pdf_pts"],
            "source_w4_centerline_pdf_pts":[list(x) for x in expected_path],
            "original_native_ink_supports_negative_subedge":False,
            "source_w2_full_span_supports_negative_subedge":False,
            "w2_surviving_fragments":fragment_rows,
            "producer_w4_vs_replayed_w2_w3_path_equal":True,
            "physical_wall_role_granted":False,
            "physical_room_granted":False,
            "metric_quantity_granted":False,
        })
    return {
        "reconstructed_w2_surviving_edge_count":len(by_id),
        "reconstructed_w2_node_count":len(nodes),
        "reconstructed_w3_junction_count":len(junctions),
        "reconstructed_w4_candidate_count":len(assembled_walls),
        "native_negative_w4_face_subedge_count":len(first_failures),
        "original_w2_node_junction_first_gate_rows":rows,
        "new_physical_wall_approved":False,
        "new_commercial_quantities":[],
        "diagnostic_only":True,
    }


def audit_exact_producer_f07_sibling_receipts(*, viewports, published,
                                             source_page, original_w4_scope_id):
    """Retain all independently resegmented source-stamped sibling details."""
    auth = _authenticated_viewports_from_rows(viewports)
    if auth is None:
        raise ValueError("source_f07_original_sibling_source_seal_unavailable")
    all_views, eligible = auth
    if len({v.view_id for v in all_views}) != len(all_views):
        raise ValueError("source_f07_duplicate_sibling_view_identity")
    sibling = _viewport_sibling_set_fingerprint(all_views)
    rows=[]
    expected=[]
    for view in sorted(all_views, key=lambda v: v.view_id):
        if not is_segment_page_viewports_product(view):
            raise ValueError("source_f07_mutated_after_producer_seal")
        derived=(
            _viewport_decision_scope_id(
                published=published,page_id=str(source_page),viewport=view,
                sibling_set_fingerprint=sibling,
            ) if view in eligible else None
        )
        if derived == original_w4_scope_id:
            expected.append(view.view_id)
        rows.append({
            "original_f07_sibling_view_id":view.view_id,
            "original_f07_sibling_view_type":view.view_type,
            "full_source_viewport_producer_payload":_producer_fingerprint_payload(view),
            "full_source_viewport_fingerprint":
                segmented_viewport_producer_fingerprint(view),
            "recomputed_source_scope_id_if_eligible":derived,
            "diagnostic_producer_seal_valid":True,
        })
    if len(expected)!=1:
        raise ValueError("source_f07_independent_replay_scope_exact_parity_unavailable")
    return {
        "all_original_source_stamped_sibling_count":len(rows),
        "all_original_source_f07_siblings":rows,
        "all_siblings_source_fingerprint":sibling,
        "source_scope_target_f07_view_id":expected[0],
        "first_w4_scope_id":original_w4_scope_id,
        "independent_f07_scope_id_replay_matches_original_w4":True,
        "same_original_producer_cache_claimed":False,
        "no_physical_room_role_granted":True,
    }


def audit_original_incident_source_roles(*, graph_rows, original_owned_segments,
                                         w2_graph_input_segments):
    """Preserve ALL native source parents at W2-displaced W4 face endpoints.

    Source classification is a candidate filter, never an independent
    structural wall proof. Unknown source stays unavailable, not invented.
    """
    raw = {}
    for seg in original_owned_segments:
        key=str(seg.get("id") or "")
        if key:
            raw.setdefault(key, []).append(seg)
    filtered = {}
    for seg in w2_graph_input_segments:
        key=str(seg.get("id") or "")
        if key:
            filtered.setdefault(key, []).append(seg)
    hits={}
    for case in graph_rows:
        atom=case["source_negative_face_subedge_pdf_pts"]
        for f in case["w2_surviving_fragments"]:
            for endpoint in f["w2_graph_node_endpoints"]:
                p=endpoint["w2_graph_snapped_node_pdf_pts"]
                if not any(
                    math.dist(p,[float(v) for v in vertex])<0.00001
                    for vertex in atom
                ):
                    continue
                node=endpoint["w2_graph_node_index"]
                incidents=endpoint["all_original_source_incident_w2_edges_at_same_graph_node"]
                rows=[]
                for edge in incidents:
                    for sid in edge["original_indexed_source_primitive_ids"]:
                        rows.append((edge["source_w2_edge_id"],sid))
                record=hits.setdefault(node,{
                    "graph_node_index":node,
                    "snapped_node_pdf_pts":list(p),
                    "snap_input_sample_count":
                        endpoint.get("w2_graph_node_snap_input_sample_count"),
                    "original_indexed_source_candidate_roles":[],
                    "structural_role_independently_proven":False,
                    "no_source_node_repair_authorized":True,
                })
                if record["snapped_node_pdf_pts"]!=list(p):
                    raise ValueError("displaced_source_node_identity_conflict")
                for w2_edge, primitive_id in sorted(set(rows)):
                    before=raw.get(primitive_id,[])
                    after=filtered.get(primitive_id,[])
                    if not before:
                        raise ValueError("original_w2_graph_primitive_not_in_source_view")
                    for segment in before:
                        candidate,reasons=is_structural_candidate_segment(segment)
                        geometry=[segment.get(k) for k in ("x1","y1","x2","y2")]
                        item={
                            "w2_split_edge_id":w2_edge,
                            "source_native_primitive_id":primitive_id,
                            "source_observation_id":segment.get("source_observation_id"),
                            "original_source_line_pdf_pts":geometry,
                            "original_source_kind":segment.get("kind"),
                            "original_source_layer":segment.get("layer"),
                            "original_source_path_index":segment.get("path_index"),
                            "original_source_stroke":segment.get("stroke"),
                            "original_source_stroke_width":segment.get("width"),
                            "original_source_fill":segment.get("fill"),
                            "retained_in_existing_w2_graph_input":
                                any(x is segment or x==segment for x in after),
                            "current_producer_structural_candidate_filter":bool(candidate),
                            "candidate_filter_reasons":list(reasons),
                            "physical_wall_role_source_proven":False,
                        }
                        if item not in record["original_indexed_source_candidate_roles"]:
                            record["original_indexed_source_candidate_roles"].append(item)
    for node in hits.values():
        node["original_indexed_source_candidate_roles"].sort(
            key=lambda x:(x["source_native_primitive_id"],x["w2_split_edge_id"]))
    return {
        "displaced_w2_original_source_node_role_cases": [
            hits[k] for k in sorted(hits)
        ],
        "new_structural_wall_approved":False,
        "new_physical_room_approved":False,
    }


def replay_graph_for_original_source_scope(*, source, published, pdf_bytes,
                                           original_wall_scope, source_page:int,
                                           first_failures):
    """Second producer-only reconstruction; first W4 authority stays immutable."""
    if not first_failures:
        return {"status":"no_original_source_negative_subedges",
                "original_w2_node_junction_first_gate_rows":[],
                "new_commercial_quantities":[],"diagnostic_only":True}
    page_id=str(source_page)
    raw,_,width,height=_source_page_segments(
        source_producer=source,published=published,source_bytes=pdf_bytes,
        page_id=page_id,decision_scope_id=_decision_scope_id(page_id),
    )
    raw,_=_partition_opening_local_supplemental_segments(raw)
    f07=tuple(segment_source_page_viewports(
        source,revision_id=published.revision.revision_id,page_id=page_id,
        physical_plan_view_shadow=True,
    ))
    auth=_authenticated_viewports_from_rows(f07)
    if auth is None:
        raise ValueError("original_f07_source_plan_sibling_scope_unavailable")
    siblings,eligible=auth
    fp=_viewport_sibling_set_fingerprint(siblings)
    same=[v for v in eligible if _viewport_decision_scope_id(
        published=published,page_id=page_id,viewport=v,
        sibling_set_fingerprint=fp,
    )==original_wall_scope.decision_scope_id]
    if len(same)!=1:
        raise ValueError("independent_f07_sibling_source_scope_parity_unavailable")
    selected=same[0]
    owned=[]
    for segment in raw:
        owners=[v for v in eligible if v.bounding_box is not None
                and _segment_fully_inside_bbox(segment,v.bounding_box)]
        if (len(owners)==1 and owners[0].view_id==selected.view_id
                and not _segment_lies_on_bbox_edge(segment,selected.bounding_box)):
            s=dict(segment)
            s["viewport_id"]=original_wall_scope.decision_scope_id
            owned.append(s)
    motif=_filter_repeated_non_physical_drafting_primitives(
        owned,page_width=width,page_height=height,
    )
    strips=_proven_filled_wall_strips(motif)
    inputs=_filter_proven_wall_strip_geometry(motif,strips)
    graph=build_wall_graph_for_viewport(inputs)
    junctions,relationships=classify_junctions(
        graph,document_id=original_wall_scope.document_id,
        page_id=page_id,viewport_id=original_wall_scope.decision_scope_id,
    )
    assembled,_=assemble_wall_candidates(
        graph,junctions,relationships,
        viewport_id=original_wall_scope.decision_scope_id,
    )
    f07_receipt=audit_exact_producer_f07_sibling_receipts(
        viewports=siblings,published=published,source_page=source_page,
        original_w4_scope_id=original_wall_scope.decision_scope_id,
    )
    proof=trace_original_w2_graph_nodes(
        original_wall_scope=original_wall_scope,
        first_failures=first_failures,
        graph=graph,junctions=junctions,assembled_walls=assembled,
    )
    roles=audit_original_incident_source_roles(
        graph_rows=proof["original_w2_node_junction_first_gate_rows"],
        original_owned_segments=owned,w2_graph_input_segments=inputs,
    )
    return {
        "status":"original_w2_w3_graph_lineage_replay_exact_parity",
        "original_original_source_node_drawing_roles":roles,
        "original_owned_plan_source_segment_count":len(owned),
        "original_w2_graph_input_segment_count":len(inputs),
        "independently_replayed_f07_original_sibling_receipts":f07_receipt,
        **proof,
    }
