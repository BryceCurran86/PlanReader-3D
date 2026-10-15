"""Fail-closed independent original W2 graph node replay for source-owned W4 walls.

This is read-only source diagnosis. A W2 node centroid is not a structural
wall classification, source room closure, or permission to change W2 snapping.
"""
from __future__ import annotations

import hashlib
import math

import fitz

from pb_physical_wall_candidate_authority import (
    _source_page_segments, _decision_scope_id, _all_viewports,
    _authenticated_viewports_from_rows, _viewport_sibling_set_fingerprint,
    _viewport_decision_scope_id, _segment_fully_inside_bbox,
    _segment_lies_on_bbox_edge, _filter_repeated_non_physical_drafting_primitives,
    _proven_filled_wall_strips, _filter_proven_wall_strip_geometry,
    _assemble_source_owned_w4_identities_or_unavailable,
)
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport, DEFAULT_GAP_SNAP_TOLERANCE_PT,
    filter_structural_segments, _segments_to_point_pairs,
    split_segments_at_intersections, _point_pairs_to_segment_dicts,
    _snap_geometry_indexed,
)
from pb_wall_room_topology_junction_classifier import classify_junctions


def trace_exact_source_w2_nodes(*, original_wall_scope, graph, reconstructed_walls,
                                selected_wall_ids, junctions=()):
    """Require exact whole W4 candidate parity and every selected W2 lineage."""
    source_records = tuple(original_wall_scope.records)
    expected = {r.wall_candidate_id: r for r in source_records}
    actual = {w.candidate_id: w for w in reconstructed_walls}
    if len(expected) != len(source_records) or len(actual) != len(reconstructed_walls):
        raise ValueError("original_w4_candidate_identity_collision")
    if set(expected) != set(actual) or not expected:
        raise ValueError("original_w4_candidate_universe_drift")
    for key, rec in expected.items():
        if (tuple(tuple(pt) for pt in rec.wall_candidate.centerline_pts)
                != tuple(tuple(pt) for pt in actual[key].centerline_pts)):
            raise ValueError("original_w4_centerline_replay_drift")
    wall_ids = tuple(selected_wall_ids)
    if not wall_ids or len(wall_ids) != len(set(wall_ids)):
        raise ValueError("selected_original_w4_id_missing_or_duplicate")
    if any(key not in expected for key in wall_ids):
        raise ValueError("original_selected_w4_wall_not_in_producer")
    active = [e for e in graph["edges"] if not e.get("_removed")]
    edges = {str(e["id"]): e for e in active}
    nodes = {node["id"]: node for node in graph["nodes"]}
    if len(edges) != len(active) or len(nodes) != len(graph["nodes"]):
        raise ValueError("original_w2_graph_duplicate_identity")
    junction_by_position = {}
    for j in junctions:
        position = tuple(round(float(v), 6) for v in j.position_pt)
        if len(position) != 2 or not all(math.isfinite(v) for v in position):
            raise ValueError("original_w3_junction_position_invalid")
        junction_by_position.setdefault(position, []).append({
            "original_w3_node_identity": str(j.node_id),
            "original_w3_junction_type": j.junction_type.value,
            "original_w3_junction_status": j.status.value,
            "original_w3_reason_codes": list(j.reason_codes),
            "w3_incident_edge_ids": sorted(j.incident_wall_candidate_ids),
            "source_structural_role_granted": False,
        })
    rows = []
    for wall_id in wall_ids:
        producer = expected[wall_id]
        fragments = tuple(producer.source_edge_fragments)
        if not fragments or len(fragments) > 1024:
            raise ValueError("original_w2_source_fragment_universe_unavailable")
        snap_records = []
        for frag in fragments:
            edge = edges.get(str(frag.edge_id))
            if edge is None:
                raise ValueError("original_w2_fragment_id_not_replayed")
            coord = tuple(float(edge[k]) for k in ("x1", "y1", "x2", "y2"))
            parents = tuple(sorted(
                str(x) for x in (edge.get("primitive_lineage") or {}).get(
                    "source_primitive_ids", ()
                )
            ))
            if coord != tuple(frag.geometry) or parents != tuple(sorted(frag.source_primitive_ids)):
                raise ValueError("original_w2_fragment_source_or_geometry_drift")
            endpoints = []
            for label, geometry in (
                ("a", coord[:2]), ("b", coord[2:])
            ):
                node_id = edge[label]
                node = nodes.get(node_id)
                if node is None:
                    raise ValueError("original_w2_endpoint_snap_node_unavailable")
                snapped = (float(node["x"]), float(node["y"]))
                if not all(math.isfinite(v) for v in (*geometry, *snapped)):
                    raise ValueError("original_w2_graph_node_nonfinite")
                incidence = []
                for other in active:
                    for key, raw in (
                        ("a", (float(other["x1"]), float(other["y1"]))),
                        ("b", (float(other["x2"]), float(other["y2"]))),
                    ):
                        if other[key] == node_id:
                            incidence.append({
                                "w2_source_edge_id": str(other["id"]),
                                "original_endpoint_pdf_pts": list(raw),
                                "original_indexed_parent_ids": sorted(
                                    str(p) for p in (
                                        other.get("primitive_lineage") or {}
                                    ).get("source_primitive_ids", ())
                                ),
                            })
                incidence.sort(key=lambda row: (
                    row["w2_source_edge_id"],
                    row["original_endpoint_pdf_pts"],
                ))
                # Rounded native-coordinate groups are read-only; they never
                # change W2 source identity or the producer's 2.5pt snapping.
                raw_groups = {}
                for item in incidence:
                    xy = item["original_endpoint_pdf_pts"]
                    key = tuple(round(v, 6) for v in xy)
                    raw_groups.setdefault(key, []).append(item)
                coordinate_groups = [
                    {
                        "native_coordinate_6dp_report_only": list(key),
                        "original_retained_source_edge_ids": [
                            x["w2_source_edge_id"] for x in values
                        ],
                        "retained_incident_endpoint_count": len(values),
                        "indexed_parent_source_ids": sorted({
                            p for x in values for p in x["original_indexed_parent_ids"]
                        }),
                    }
                    for key, values in sorted(raw_groups.items())
                ]
                source_native_coords = [
                    tuple(row["native_coordinate_6dp_report_only"])
                    for row in coordinate_groups
                ]
                retained_diameter = max(
                    (math.dist(a, b) for a in source_native_coords
                     for b in source_native_coords), default=0.
                )
                endpoints.append({
                    "w2_graph_node_id": node_id,
                    "w2_source_edge_endpoint": label,
                    "original_source_endpoint_pdf_pts": list(geometry),
                    "w2_graph_snapped_node_pdf_pts": list(snapped),
                    "original_endpoint_vs_snapped_node_displacement_pt": math.dist(
                        geometry, snapped
                    ),
                    "source_snap_samples": node.get("samples"),
                    "source_node_degree": node.get("degree"),
                    "retained_original_coordinate_groups": coordinate_groups,
                    "retained_native_coordinate_cluster_count": len(coordinate_groups),
                    "mixed_original_coordinates_at_snapped_node": len(coordinate_groups) > 1,
                    "source_native_retained_endpoint_diameter_pdf_pt": retained_diameter,
                    "producer_nominal_gap_snap_tolerance_pdf_pt": DEFAULT_GAP_SNAP_TOLERANCE_PT,
                    "diameter_exceeds_nominal_tolerance_diagnostic_only": (
                        retained_diameter > DEFAULT_GAP_SNAP_TOLERANCE_PT
                    ),
                    "centroid_snap_cluster_membership_not_reversed_or_changed": True,
                    "snap_samples_equal_retained_incidents": (
                        len(incidence) == node.get("samples")
                    ),
                    "replayed_original_w3_junction_candidates": junction_by_position.get(
                        tuple(round(v, 6) for v in snapped), []
                    ),
                    "exact_node_incident_original_source_edges": incidence,
                })
            snap_records.append({
                "original_surviving_w2_edge_id": str(frag.edge_id),
                "original_indexed_parent_ids": list(parents),
                "original_w2_edge_pdf_pts": list(coord),
                "endpoints": endpoints,
                "physical_role_authenticated": False,
            })
        rows.append({
            "original_source_w4_wall_id": wall_id,
            "original_w4_centerline_pdf_pts": [
                list(p) for p in producer.wall_candidate.centerline_pts
            ],
            "w2_surviving_fragment_nodes": snap_records,
            "original_w2_to_w4_replay_parity": True,
            "source_structural_role_granted": False,
            "room_or_metric_published": False,
        })
    return {
        "status": "EXACT_ORIGINAL_W2_W4_REPLAY_NODES_OBSERVED",
        "original_reconstructed_w2_node_count": len(nodes),
        "original_reconstructed_w2_edge_count": len(edges),
        "original_w4_candidate_count": len(expected),
        "selected_original_w4_node_rows": rows,
        "source_structural_role_granted": False,
        "room_or_metric_published": False,
        "diagnostic_only": True,
    }


def inspect_all_original_snap_inputs_for_selected_nodes(*, graph, scoped_inputs,
                                                     selected_node_ids):
    """Replay W2's exact splitter and running-centroid assignments, no edits.

    Unlike post-merge surviving edges, assignments cover BOTH endpoints of
    every original split fragment, even if W2 collapsed or merged that edge.
    """
    structural, _excluded = filter_structural_segments(scoped_inputs)
    points = _segments_to_point_pairs(structural)
    split_pairs = split_segments_at_intersections(points)
    split = _point_pairs_to_segment_dicts(
        split_pairs, source_segments=structural,
    )
    snapped = _snap_geometry_indexed(
        split, tolerance_pt=DEFAULT_GAP_SNAP_TOLERANCE_PT,
        include_endpoint_assignments=True,
    )
    actual = graph["nodes"]
    expected = snapped["nodes"]
    if len(actual) != len(expected):
        raise ValueError("original_snap_node_universe_drift")
    for a, b in zip(actual, expected):
        if (a["id"], a["x"], a["y"], a["samples"]) != (
            b["id"], b["x"], b["y"], b["samples"]
        ):
            raise ValueError("original_snap_node_centroid_or_sample_drift")
    ids = set(selected_node_ids)
    if not ids or any(type(n) is not int or not 0 <= n < len(actual) for n in ids):
        raise ValueError("original_selected_snap_node_unavailable")
    assigned = {node_id: [] for node_id in sorted(ids)}
    mapping = snapped["endpoint_snap_assignments"]
    if len(mapping) != len(split):
        raise ValueError("original_split_endpoint_assignments_incomplete")
    for item in split:
        a, b = mapping[item["id"]]
        for endpoint, target, coords in (
            ("a", a, [item["x1"], item["y1"]]),
            ("b", b, [item["x2"], item["y2"]]),
        ):
            if target not in assigned:
                continue
            assigned[target].append({
                "original_split_segment_id": item["id"],
                "original_split_endpoint": endpoint,
                "original_native_split_endpoint_pdf_pts": coords,
                "original_source_primitive_ids": list(
                    (item.get("primitive_lineage") or {}).get(
                        "source_primitive_ids", ()
                    )
                ),
                "input_contributes_to_snapped_node_not_wall_role": True,
            })
    rows = []
    for node_id, receipts in sorted(assigned.items()):
        node = actual[node_id]
        if len(receipts) != node["samples"]:
            raise ValueError("original_snap_input_sample_count_drift")
        groups = {}
        for receipt in receipts:
            raw = receipt["original_native_split_endpoint_pdf_pts"]
            key = tuple(round(float(value), 6) for value in raw)
            groups.setdefault(key, []).append(receipt)
        grouped = [{
            "original_split_input_coordinate_6dp_report_only": list(key),
            "original_split_input_sample_count": len(recs),
            "original_split_input_source_ids": sorted({
                src for rec in recs for src in rec["original_source_primitive_ids"]
            }),
            "original_split_input_fragment_ids": [
                f"{rec['original_split_segment_id']}:{rec['original_split_endpoint']}"
                for rec in recs
            ],
        } for key, recs in sorted(groups.items())]
        rows.append({
            "original_w2_node_id": node_id,
            "original_snapped_position_pdf_pts": [node["x"], node["y"]],
            "original_producer_snap_sample_count": node["samples"],
            "all_input_samples_independently_recovered": True,
            "original_split_input_coordinate_groups": grouped,
            "all_original_split_endpoint_receipts": receipts,
            "source_wall_or_room_role_granted": False,
        })
    return {
        "status": "ORIGINAL_W2_ALL_SPLIT_ENDPOINT_INPUTS_REPLAY_VERIFIED",
        "original_W2_premerge_node_count": len(expected),
        "original_split_segment_count": len(split),
        "selected_original_node_rows": rows,
        "new_firm_or_physical_room": False,
        "diagnostic_only": True,
    }


def audit_original_complete_link_counterfactual(*, scoped_inputs,
                                                original_snap_input_census,
                                                original_wall_scope):
    """True original source-graph counterfactual; never changes live W2.

    Retains EVERY original split input and its source ancestry. The alternative
    node membership is a geometry diagnostic, not physical-wall evidence.
    """
    structural, _excluded = filter_structural_segments(scoped_inputs)
    point_pairs = _segments_to_point_pairs(structural)
    split_pairs = split_segments_at_intersections(point_pairs)
    split = _point_pairs_to_segment_dicts(
        split_pairs, source_segments=structural,
    )
    alternate_snapped = _snap_geometry_indexed(
        split, tolerance_pt=DEFAULT_GAP_SNAP_TOLERANCE_PT,
        include_endpoint_assignments=True,
        complete_link_snap_shadow=True,
    )
    assignments = alternate_snapped["endpoint_snap_assignments"]
    original_rows = original_snap_input_census["selected_original_node_rows"]
    alternative_nodes = {v["id"]:v for v in alternate_snapped["nodes"]}
    original_wall_paths = [
        (r.wall_candidate_id,
         tuple(tuple(v) for v in r.wall_candidate.centerline_pts))
        for r in original_wall_scope.records
    ]
    alternative_full = build_wall_graph_for_viewport(
        scoped_inputs, complete_link_snap_shadow=True,
    )
    report = []
    for node in original_rows:
        alternative_membership = {}
        for item in node["all_original_split_endpoint_receipts"]:
            source_fragment_id = item["original_split_segment_id"]
            endpoint = item["original_split_endpoint"]
            pair = assignments.get(source_fragment_id)
            if pair is None:
                raise ValueError("original_w2_counterfactual_split_fragment_missing")
            counter_node = pair[0 if endpoint=="a" else 1]
            alternative_membership.setdefault(counter_node, []).append(item)
        if sum(map(len, alternative_membership.values())) != node[
            "original_producer_snap_sample_count"
        ]:
            raise ValueError("counterfactual_original_sample_universe_drift")
        report.append({
            "original_w2_node_id": node["original_w2_node_id"],
            "original_snap_sample_count": node["original_producer_snap_sample_count"],
            "alternative_source_sample_count": sum(
                map(len, alternative_membership.values())
            ),
            "alternate_w2_node_memberships": [
                {
                    "alternate_w2_node_id": idx,
                    "alternate_position_pdf_pts": [
                        alternative_nodes[idx]["x"],
                        alternative_nodes[idx]["y"],
                    ],
                    "original_source_input_sample_count": len(items),
                    "original_split_source_input_ids": sorted(
                        f"{it['original_split_segment_id']}:{it['original_split_endpoint']}"
                        for it in items
                    ),
                } for idx, items in sorted(alternative_membership.items())
            ],
            "physical_wall_or_node_role_granted": False,
        })
    return {
        "status": "SOURCE_OWNED_COUNTERFACTUAL_GRAPH_COMPLETE",
        "original_selected_w2_node_count": len(report),
        "alternate_w2_node_count": len(alternate_snapped["nodes"]),
        "alternate_merged_w2_node_count": len(alternative_full["nodes"]),
        "alternate_w2_edge_count": len(alternative_full["edges"]),
        "complete_link_snap_observations": alternate_snapped[
            "complete_link_snap_shadow"
        ],
        "original_selected_w4_centerline_count": len(original_wall_paths),
        "selected_source_node_counterfactuals": report,
        "original_source_input_items_preserved": True,
        "structural_or_annotation_roles_assigned": False,
        "new_source_room_or_metric": False,
        "diagnostic_only": True,
    }


def replay_original_page7_graph(*, source, published, source_bytes,
                                original_wall_scope, original_w4_ids):
    if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
        raise ValueError("original_source_sha_mismatch")
    page_id = str(original_wall_scope.page_id)
    page_no = int(page_id)
    if page_no != 7 or original_wall_scope.source_sha256 != published.revision.source_sha256:
        raise ValueError("original_requested_source_page_or_sha_conflict")
    raw, _source_observations, width, height = _source_page_segments(
        source_producer=source,
        published=published,
        source_bytes=source_bytes,
        page_id=page_id,
        decision_scope_id=_decision_scope_id(page_id),
    )
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        page = document[page_no - 1]
        viewports = _all_viewports(page, page_number=page_no)
    auth = _authenticated_viewports_from_rows(viewports)
    if auth is None:
        raise ValueError("original_source_owned_page_viewports_unavailable")
    siblings, eligible = auth
    fingerprint = _viewport_sibling_set_fingerprint(siblings)
    matching = [v for v in eligible if _viewport_decision_scope_id(
        published=published,
        page_id=page_id,
        viewport=v,
        sibling_set_fingerprint=fingerprint,
    ) == original_wall_scope.decision_scope_id]
    if len(matching) != 1:
        raise ValueError("original_f07_viewport_scope_identity_mismatch")
    selected = matching[0]
    owned = []
    for original in raw:
        owners = [
            view for view in eligible
            if view.bounding_box is not None
            and _segment_fully_inside_bbox(original, view.bounding_box)
        ]
        if (len(owners) == 1 and owners[0].view_id == selected.view_id
                and not _segment_lies_on_bbox_edge(original, selected.bounding_box)):
            s = dict(original)
            s["viewport_id"] = original_wall_scope.decision_scope_id
            owned.append(s)
    filtered = _filter_repeated_non_physical_drafting_primitives(
        owned, page_width=width, page_height=height
    )
    strips = _proven_filled_wall_strips(filtered)
    candidates = _filter_proven_wall_strip_geometry(filtered, strips)
    graph = build_wall_graph_for_viewport(candidates)
    junctions, relationships = classify_junctions(
        graph,
        document_id=original_wall_scope.document_id,
        page_id=page_id,
        viewport_id=original_wall_scope.decision_scope_id,
    )
    assembled = _assemble_source_owned_w4_identities_or_unavailable(
        graph=graph, junctions=junctions,
        relationships=relationships, scope_id=original_wall_scope.decision_scope_id,
    )
    if assembled is None:
        raise ValueError("original_replayed_w4_identity_unavailable")
    walls, _junctions, _identities = assembled
    result = trace_exact_source_w2_nodes(
        original_wall_scope=original_wall_scope, graph=graph,
        reconstructed_walls=walls, selected_wall_ids=original_w4_ids,
        junctions=junctions,
    )
    selected_node_ids = {
        endpoint["w2_graph_node_id"]
        for wall in result["selected_original_w4_node_rows"]
        for fragment in wall["w2_surviving_fragment_nodes"]
        for endpoint in fragment["endpoints"]
    }
    snap_input_census = inspect_all_original_snap_inputs_for_selected_nodes(
        graph=graph, scoped_inputs=candidates,
        selected_node_ids=selected_node_ids,
    )
    guarded = audit_original_complete_link_counterfactual(
        scoped_inputs=candidates,
        original_snap_input_census=snap_input_census,
        original_wall_scope=original_wall_scope,
    )
    return {
        **result,
        "original_complete_link_snap_counterfactual": guarded,
        "original_all_split_input_snap_provenance": snap_input_census,
        "original_source_sha256": published.revision.source_sha256,
        "original_f07_view_id": selected.view_id,
        "original_source_owned_viewport_scope_verified": True,
        "original_source_ink_segment_count": len(raw),
        "original_source_viewport_owned_segment_count": len(owned),
        "original_w2_graph_input_segment_count": len(candidates),
        "new_commercial_quantities": [],
    }
