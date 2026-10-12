"""Original PDF-backed full foreground source; optional W2/W4 is nonpublishing."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_migration_contracts import EvidenceResolutionStatus, canonical_contract_json
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_junction_classifier import classify_junctions, deduplicate_coincident_edges
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from tools.gptmax_full_foreground_run_source import FullForegroundSourceProducer


def _default_source(source_bytes, source_sha, page_id):
    producer = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = producer.ingest_native_pdf_bytes(document_id=f"live-source:{source_sha[:32]}",
        source_bytes=source_bytes, source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(page_id,))
    published = producer.augment_with_raster_visible_segments(published.revision.revision_id,
        page_ids=(page_id,))
    records = []
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(published.revision.document_id, published.revision.revision_id,
            published.revision.source_sha256, published.snapshot.snapshot_id, observation_id)
        result = producer.authority().resolve_visible(selector)
        if result.status != EvidenceResolutionStatus.CORROBORATED or result.observation is None:
            raise ValueError("ordinary source-visible observation unavailable")
        if len(result.observation.geometry) != 4:
            raise ValueError("ordinary source-visible geometry unavailable")
        records.append(result.observation)
    return producer, published, tuple(records)


def _trace_sources(records, *, exact_endpoint_shadow=False, exact_endpoint_index_shadow=False,
        w4_identity_abstention_shadow=False):
    """Experimental candidates only; input receipts are checked by the caller."""
    if type(exact_endpoint_shadow) is not bool:
        raise ValueError("exact endpoint shadow mode must be explicit boolean")
    if type(exact_endpoint_index_shadow) is not bool:
        raise ValueError("exact endpoint index shadow must be explicit boolean")
    if exact_endpoint_index_shadow and not exact_endpoint_shadow:
        raise ValueError("exact endpoint index shadow requires exact endpoint mode")
    if type(w4_identity_abstention_shadow) is not bool:
        raise ValueError("W4 identity abstention shadow must be explicit boolean")
    records = tuple(sorted(records, key=lambda r:r.observation_id))
    source_ids = frozenset(r.observation_id for r in records)
    if len(records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("experimental source primitive count exceeds safety bound")
    if len(source_ids) != len(records):
        raise ValueError("duplicate experimental source observation address")
    source_hashes = {r.source_sha256 for r in records}
    pages = {r.page_id for r in records}
    if len(source_hashes) > 1 or len(pages) > 1:
        raise ValueError("foreign experimental source scope")
    segments = []
    for record in sorted(records, key=lambda r: r.observation_id):
        geometry = record.geometry
        if (len(geometry) != 4 or any(isinstance(v,bool) or not isinstance(v,(int,float))
                or not math.isfinite(v) for v in geometry) or geometry[:2] == geometry[2:]):
            raise ValueError("invalid experimental source geometry")
        segments.append(dict(id=record.observation_id, x1=geometry[0], y1=geometry[1],
            x2=geometry[2], y2=geometry[3], document_id=record.document_id, page_id=record.page_id,
            viewport_id="full-page-pixel-shadow", kind=record.observation_kind,
            source_observation_id=record.observation_id))
    # Diagnostic-only control: reuse the existing W2 stack with exact endpoint
    # joins. The ordinary source report continues using its unchanged default.
    if exact_endpoint_index_shadow:
        graph = build_wall_graph_for_viewport(segments, gap_snap_tolerance_pt=0.0,
            exact_endpoint_index_shadow=True)
    elif exact_endpoint_shadow:
        graph = build_wall_graph_for_viewport(segments, gap_snap_tolerance_pt=0.0)
    else:
        graph = build_wall_graph_for_viewport(segments)
    deduped, removed = deduplicate_coincident_edges(graph)
    junctions, relationships = classify_junctions(deduped, document_id="source-pixel-shadow",
        page_id=next(iter(pages),"1"), viewport_id="full-page-pixel-shadow")
    abstentions = []
    walls, edge_map = assemble_wall_candidates(deduped, junctions, relationships,
        viewport_id="full-page-pixel-shadow", **(
            dict(identity_abstention_shadow=True, abstained_chain_rows=abstentions)
            if w4_identity_abstention_shadow else {}))
    abstained_by_edge = {}
    if w4_identity_abstention_shadow:
        actual_edges = {str(e['id']): e for e in deduped['edges']}
        if len({r['record_id'] for r in abstentions}) != len(abstentions):
            raise ValueError('W4 abstention record address collision')
        for row in abstentions:
            for fragment in row['actual_owned_w3_fragment_rows']:
                key = fragment['edge_id']
                actual = actual_edges.get(key)
                parents = (fragment.get('primitive_lineage') or {}).get('source_primitive_ids')
                if (actual is None or key in abstained_by_edge
                        or fragment['primitive_lineage'] != actual.get('primitive_lineage')
                        or fragment['w2_fragment_geometry_pt'] != [actual[k] for k in ('x1','y1','x2','y2')]
                        or not isinstance(parents, (tuple,list)) or not parents
                        or any(not isinstance(p,str) or not p for p in parents)
                        or len(set(parents)) != len(parents) or not set(parents) <= source_ids):
                    raise ValueError('unowned or contradictory W4 abstained fragment')
                fragment['source_observation_ids'] = sorted(parents)
                abstained_by_edge[key] = row
        candidate_edges = [eid for w in walls for eid in w.face_a_segment_ids]
        if (len(set(candidate_edges)) != len(candidate_edges)
                or set(candidate_edges) & abstained_by_edge.keys()
                or set(candidate_edges) | abstained_by_edge.keys() != actual_edges.keys()):
            raise ValueError('W4 shadow did not partition all actual retained edges')
    all_owners = defaultdict(list)
    for wall in walls:
        for edge_id in wall.face_a_segment_ids:
            all_owners[edge_id].append(wall.candidate_id)
    edge_rows = []
    by_parent = defaultdict(list)
    removed_set = set(removed)
    retained_ids = {str(e["id"]) for e in deduped["edges"]}
    for edge in graph["edges"]:
        edge_id = str(edge["id"])
        parents = edge.get("primitive_lineage",{}).get("source_primitive_ids",())
        if not isinstance(parents,(list,tuple)) or len(set(parents)) != len(parents):
            raise ValueError("contradictory experimental W2 parent inventory")
        if any(p not in source_ids for p in parents):
            raise ValueError("foreign experimental W2 source parent")
        row = {"edge_id":edge_id,"source_observation_ids":sorted(parents),
            "w2_fragment_geometry_pt":[edge["x1"],edge["y1"],edge["x2"],edge["y2"]],
            "w3_retained":edge_id in retained_ids,"w3_removed":edge_id in removed_set,
            "experimental_w4_candidate_ids":sorted(all_owners.get(edge_id,())),
            "physical_host_authority":False}
        if w4_identity_abstention_shadow:
            row['w4_candidate_membership_available'] = edge_id not in abstained_by_edge
            row['w4_abstained_chain_record_ids'] = ([abstained_by_edge[edge_id]['record_id']]
                if edge_id in abstained_by_edge else [])
        edge_rows.append(row)
        for parent in parents:
            by_parent[parent].append(edge_id)
    collapsed = []
    collapsed_by_parent = defaultdict(list)
    for fragment in graph.get("snap_collapsed_fragments",()):
        parents = fragment.get("primitive_lineage",{}).get("source_primitive_ids",())
        if not isinstance(parents,(list,tuple)) or len(set(parents)) != len(parents):
            raise ValueError("contradictory experimental collapsed parent inventory")
        row = {"fragment_id":fragment["id"],"reason":fragment["reason"],
            "source_observation_ids":sorted(parents),
            "source_fragment_geometry_pt":[fragment[k] for k in ("x1","y1","x2","y2")],
            "physical_host_authority":False}
        collapsed.append(row)
        for parent in parents:
            if parent not in source_ids:
                raise ValueError("foreign experimental collapsed parent")
            collapsed_by_parent[parent].append(row["fragment_id"])
    census = [{"source_observation_id":r.observation_id,
        "w2_edge_ids":sorted(by_parent[r.observation_id]),
        "snap_collapsed_fragment_ids":sorted(collapsed_by_parent[r.observation_id]),
        "first_observed_stage":("w2_edges_observed" if by_parent[r.observation_id]
            else "w2_snap_collapsed" if collapsed_by_parent[r.observation_id]
            else "w2_parent_unmapped"),"physical_host_authority":False} for r in records]
    counts = Counter(w.candidate_id for w in walls)
    result = {"input_source_count":len(records),"all_w2_edges":edge_rows,
        "all_snap_collapsed_fragments":collapsed,"source_parent_census":census,
        "all_experimental_w4_candidates":[{"candidate_id":w.candidate_id,
            "w2_edge_ids":list(w.face_a_segment_ids), "centerline_pt":w.centerline_pts,
            "status":w.status.value,"physical_host_authority":False} for w in walls],
        "w4_candidate_address_collisions":sorted(k for k,v in counts.items() if v>1),
        "w4_edge_map_consistent":(set(edge_map)==set(all_owners)
            and all(edge_map.get(k) in v for k,v in all_owners.items())),
        "scope_authority":"full-page diagnostic only; no authenticated floor-plan viewport",
        "physical_equivalence_proven":False,"host_publication_allowed":False}
    if w4_identity_abstention_shadow:
        result.update(all_w4_abstained_chain_rows=abstentions,
            all_actual_w3_edges_have_w4_chain_disposition=True,
            w4_candidate_universe_complete=not abstentions,
            w4_source_parent_inventory_validated=True,
            structural_source_universe_complete=False,
            opening_count_publication_allowed=False,metric_quantity_publication_allowed=False)
    return result


def original_full_foreground_report(source_bytes: bytes, *, expected_source_sha: str,
        page_id: str, expected_render_sha: str | None = None, trace=False):
    shadow = FullForegroundSourceProducer(source_bytes, expected_source_sha=expected_source_sha,page_id=page_id)
    normal, ordinary, original_records = _default_source(source_bytes,expected_source_sha,page_id)
    original_bytes = canonical_contract_json([asdict(r) for r in original_records]).encode()
    published = shadow.nominate()
    png,parent,frame = shadow._verify_render()
    render_sha = sha256(png).hexdigest()
    if expected_render_sha is not None and (not isinstance(expected_render_sha,str)
            or len(expected_render_sha) != 64 or render_sha != expected_render_sha):
        raise ValueError("pixel source render SHA mismatch")
    selectors = shadow.selectors()
    results = shadow.authority().resolve_many(selectors)
    if any(r.status != EvidenceResolutionStatus.CORROBORATED or r.observation is None for r in results):
        raise ValueError("owned pixel source receipt failed reauthentication")
    # The established visibility reader cannot consume the separate shadow kind.
    if any(normal.authority().resolve_visible(s).status == EvidenceResolutionStatus.CORROBORATED for s in selectors):
        raise ValueError("pixel source shadow unexpectedly promoted to ordinary visibility")
    records = tuple(r.observation for r in results)
    after = normal.augment_with_raster_visible_segments(ordinary.revision.revision_id,page_ids=(page_id,))
    if after != ordinary:
        raise ValueError("ordinary source snapshot changed during pixel nomination")
    after_records = [normal.authority().resolve_visible(ObservationSelector(
        ordinary.revision.document_id,ordinary.revision.revision_id,ordinary.revision.source_sha256,
        ordinary.snapshot.snapshot_id,r.observation_id)).observation for r in original_records]
    if canonical_contract_json([asdict(r) for r in after_records]).encode() != original_bytes:
        raise ValueError("ordinary source observations changed during pixel nomination")
    report = {"schema_version":"1.0.0","inventory_kind":"all_complete_original_foreground_runs","source_sha256":expected_source_sha,
        "page_id":page_id,"render_sha256":render_sha,"render_dpi":144,
        "native_page_frame":asdict(frame),"native_page_parent_observation_id":parent.observation_id,
        "shadow_source_snapshot":asdict(published),"primitive_safety_cap":MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "ordinary_source_snapshot":asdict(ordinary),
        "ordinary_visible_source_records":[asdict(r) for r in original_records],
        "original_source_render_reauthenticated":True,"ordinary_source_snapshot_unchanged":True,
        "ordinary_source_record_count":len(original_records),
        "ordinary_source_records_sha256":sha256(original_bytes).hexdigest(),
        "ordinary_visibility_rejects_shadow_kind":True,"authenticated_pixel_source_count":len(records),
        "authenticated_pixel_source_records":[{"source_observation":asdict(r),
            "pixel_receipt":asdict(shadow._proofs[r.observation_id]),
            "proposition":"source_observation_exists", "source_pixels_authenticated":True,
            "ordinary_visible_segment_authority":False,"physical_wall_authority":False,
            "host_publication_allowed":False} for r in records],
        "source_universe_completeness_proven":False,"physical_equivalence_proven":False,
        "host_publication_allowed":False,"opening_count_publication_allowed":False,
        "metric_quantity_publication_allowed":False,"benchmark_accuracy":None}
    report["experimental_w2_w4"] = _trace_sources(original_records+records) if trace else None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",required=True,type=Path)
    parser.add_argument("--page-id",required=True)
    parser.add_argument("--expected-source-sha",required=True)
    parser.add_argument("--expected-render-sha")
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--trace-w2-w4",action="store_true",help="Experimental whole-page W2/W4 replay; no host authority")
    args = parser.parse_args()
    report = original_full_foreground_report(args.pdf.read_bytes(),page_id=args.page_id,
        expected_source_sha=args.expected_source_sha,expected_render_sha=args.expected_render_sha,
        trace=args.trace_w2_w4)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in ("source_sha256","render_sha256",
        "authenticated_pixel_source_count","ordinary_source_record_count","ordinary_source_snapshot_unchanged")}))


if __name__ == "__main__":
    main()
