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
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
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
    return {
        **result,
        "original_source_sha256": published.revision.source_sha256,
        "original_f07_view_id": selected.view_id,
        "original_source_owned_viewport_scope_verified": True,
        "original_source_ink_segment_count": len(raw),
        "original_source_viewport_owned_segment_count": len(owned),
        "original_w2_graph_input_segment_count": len(candidates),
        "new_commercial_quantities": [],
    }
