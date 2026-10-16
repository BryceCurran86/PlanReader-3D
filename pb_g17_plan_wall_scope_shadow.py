"""Original 300-DPI drawing topology, isolated from sealed wall/host producers.

This source-addressed observer retains the full primitive and opening census.
Original paint and F.07 prove source ownership, never structural role or metric
authority. Serialized output cannot be consumed as a physical-wall universe.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import math

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_migration_provider_envelope import ProviderContext
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_physical_wall_candidate_authority import (
    MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS, PhysicalWallCandidateRecord,
    PhysicalWallSourceEdgeFragment,
)
from pb_physical_wall_identity import DuplicateW4CandidateAddress, collect_physical_wall_identities
from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI, SourceVisibilityProducer,
    _axis_aligned_geometry_fully_covered_by_rect_union,
)
from pb_viewport_migration_adapter import adapt_f07_viewport_to_migration
from pb_viewport_segmentation import segment_source_page_viewports
from pb_wall_room_topology_junction_classifier import classify_junctions, deduplicate_coincident_edges
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_stage_a import (
    DEFAULT_GAP_SNAP_TOLERANCE_PT, build_wall_graph_for_viewport,
)
from pb_wall_room_topology_wall_assembly import W4SourceCandidateAddressCollision, assemble_wall_candidates


def _rgb(png):
    decoded = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise RuntimeError("original_g17_image_decode_failed")
    return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)


def _paint(image, full, pixels):
    """Actual complete source-lattice line, without projecting new geometry."""
    if len(pixels) != 4 or not all(math.isfinite(v) for v in pixels):
        raise RuntimeError("original_g17_pixel_lattice_unproven")
    x1, y1, x2, y2 = pixels
    lo_x,hi_x = math.floor(min(x1,x2)),math.ceil(max(x1,x2))
    lo_y,hi_y = math.floor(min(y1,y2)),math.ceil(max(y1,y2))
    if min(lo_x,lo_y) < 0 or hi_x >= image.shape[1] or hi_y >= image.shape[0]:
        raise RuntimeError("original_g17_pixel_outside_frame")
    if not ((y1 == y2 and x1 != x2) or (x1 == x2 and y1 != y2)):
        return {"status":"unsupported_axis_line", "original_solid_and_unchanged":False}
    # Neutral source runs can have half-cell centerlines. Require EVERY
    # bracketing pixel, never round onto the more favourable painted row.
    region = (slice(lo_y,hi_y+1),slice(lo_x,hi_x+1))
    a,b = image[region].reshape(-1,3),full[region].reshape(-1,3)
    gray = cv2.cvtColor(a.reshape(1,-1,3), cv2.COLOR_RGB2GRAY)[0]
    solid, equal = gray < MASS_THRESHOLD, np.all(a == b, axis=1)
    return {"status":"evaluated", "pixel_count":len(a),
        "solid_pixel_count":int(solid.sum()), "unchanged_pixel_count":int(equal.sum()),
        "original_pixel_cover_bbox":(lo_x,lo_y,hi_x,hi_y),
        "original_solid_and_unchanged":bool(np.all(solid & equal))}


def _infill_edge_opening_ids(edge,infill_intervals):
    """Exact source interval union, never spanning two different apertures."""
    from pb_g17_dual_dpi_source_correspondence_shadow import _axis_line
    from pb_g17_w4_equivalence_competitor_shadow import _positive_collinear_source_overlap
    geometry=tuple(edge[k] for k in ("x1","y1","x2","y2"))
    axis=_axis_line(geometry)
    if axis is None:
        return ()
    groups={}
    for interval in infill_intervals:
        owner=interval.get('physical_opening_id')
        if (not owner or interval['source_primitive_id'] not in edge[LINEAGE_KEY]['source_primitive_ids']
                or not _positive_collinear_source_overlap(geometry,interval['geometry'])):
            continue
        value=_axis_line(interval['geometry'])
        groups.setdefault(owner,[]).append((value[1],value[2]))
    owners=[]
    for owner,spans in sorted(groups.items()):
        covered=axis[1]
        for lo,hi in sorted(spans):
            if lo>covered+1e-6:
                break
            covered=max(covered,hi)
        if covered>=axis[2]-1e-6:
            owners.append(owner)
    return tuple(owners)


def _graph(segments, *, root, scope_id, tolerance, infill_intervals=(), infill_endpoint_opposition=False,
           preserve_overlapping_spans_shadow=False, immutable_exact_endpoints_shadow=False,
           partition_exact_collinear_overlaps_shadow=False):
    graph = build_wall_graph_for_viewport(segments, gap_snap_tolerance_pt=tolerance,
        exact_endpoint_index_shadow=(tolerance == 0.0), exact_split_parent_lineage_shadow=True,
        **({"preserve_overlapping_spans_shadow": True} if preserve_overlapping_spans_shadow else {}),
        **({"immutable_exact_endpoints_shadow": True} if immutable_exact_endpoints_shadow else {}),
        **({"partition_exact_collinear_overlaps_shadow": True} if partition_exact_collinear_overlaps_shadow else {}))
    junctions, relationships = classify_junctions(graph,
        document_id=root["document_id"], page_id=root["page_id"], viewport_id=scope_id)
    deduped, removed = deduplicate_coincident_edges(graph)
    # Optional source-owned candidate experiment. Keep every original edge and
    # relationship; only the ADDITIONAL W4 union receives opposing boundaries.
    infill_edges = {
        str(e["id"])
        for e in deduped["edges"]
        if _infill_edge_opening_ids(e,infill_intervals)
    }
    opposed = tuple(r for r in relationships
        if r.relationship_type.value == "continues_as"
        and ((r.from_edge_id in infill_edges) != (r.to_edge_id in infill_edges)))
    opposed_ids = {r.relationship_id for r in opposed}
    whole_edge_opposed = opposed
    endpoint_opposed = []
    endpoint_outcomes = []
    if infill_endpoint_opposition:
        from pb_g17_infill_endpoint_opposition_shadow import _endpoint_infill_witnesses
        edges_by_id = {str(e['id']):e for e in deduped['edges']}
        junctions_by_id = {j.node_id:j for j in junctions}
        for relationship in relationships:
            if relationship.relationship_type.value!='continues_as':
                continue
            junction = junctions_by_id[relationship.via_junction_id]
            sides = []
            for eid in (relationship.from_edge_id,relationship.to_edge_id):
                edge = edges_by_id.get(eid)
                sides.append(() if edge is None else _endpoint_infill_witnesses(
                    edge,junction.position_pt,infill_intervals,tolerance=tolerance))
            opposed_at_endpoint = bool(sides[0]) != bool(sides[1])
            endpoint_outcomes.append(dict(relationship_id=relationship.relationship_id,
                from_edge_endpoint_witnesses=sides[0],to_edge_endpoint_witnesses=sides[1],
                endpoint_opposition_present=opposed_at_endpoint,
                whole_edge_opposition_present=relationship.relationship_id in opposed_ids))
            if opposed_at_endpoint and relationship.relationship_id not in opposed_ids:
                endpoint_opposed.append(relationship)
                opposed_ids.add(relationship.relationship_id)
        opposed = (*opposed,*endpoint_opposed)
    consumed = tuple(r for r in relationships if r.relationship_id not in opposed_ids)
    abstained_chains = []
    identities = None
    try:
        walls, _ = assemble_wall_candidates(deduped,junctions,consumed,
            viewport_id=scope_id, identity_abstention_shadow=True,
            abstained_chain_rows=abstained_chains)
        identities = collect_physical_wall_identities(walls,deduped)
    except (W4SourceCandidateAddressCollision,DuplicateW4CandidateAddress):
        # The entire candidate address ambiguity remains unavailable. Other
        # exceptions propagate; no arbitrary error becomes an empty success.
        pass
    records = ()
    if identities is not None:
        edges = {str(e["id"]):e for e in deduped["edges"]}
        records = tuple(PhysicalWallCandidateRecord(w.candidate_id, w, identities[w.candidate_id],
            source_edge_fragments=tuple(PhysicalWallSourceEdgeFragment(
                str(eid), tuple(float(edges[str(eid)][k]) for k in ("x1","y1","x2","y2")),
                tuple(sorted(edges[str(eid)][LINEAGE_KEY]["source_primitive_ids"])))
                for eid in sorted(identities[w.candidate_id].edge_ids)))
            for w in sorted(walls, key=lambda w:w.candidate_id))
    # The complete source preparation losses and W3 alternatives remain visible.
    result = {"snap_tolerance_pt":tolerance, "w2_edge_count":len(graph["edges"]),
        "w2_edges":[{"edge_id":str(e["id"]),
            "geometry":tuple(e[k] for k in ("x1","y1","x2","y2")),
            "source_primitive_ids":tuple(sorted(e[LINEAGE_KEY]["source_primitive_ids"]))}
            for e in graph["edges"]],
        "w2_excluded_segments":graph["excluded_segments"],
        "w2_snap_collapsed_fragments":graph["snap_collapsed_fragments"],
        "w3_junctions":[asdict(j) for j in junctions],
        "w3_relationships":[asdict(r) for r in relationships],
        "source_infill_edge_ids":tuple(sorted(infill_edges)),
        "source_opposed_continuations":[asdict(r) for r in opposed],
        "w3_coincident_edge_removals":tuple(sorted(removed)),
        "w4_abstained_chains":abstained_chains,
        "w4_identity_unavailable":identities is None,
        "w4_records":[asdict(r) for r in records]}
    if infill_endpoint_opposition:
        result.update(source_whole_edge_opposed_continuations=[asdict(r) for r in whole_edge_opposed],
            source_endpoint_opposed_continuations=[asdict(r) for r in endpoint_opposed],
            source_endpoint_opposition_outcomes=endpoint_outcomes)
    return result


def build_g17_plan_wall_scope_shadow(source, *, revision_id: str, page_id: str,
                                     preserve_overlapping_spans_shadow: bool = False,
                                     immutable_exact_endpoints_shadow: bool = False,
                                     partition_exact_collinear_overlaps_shadow: bool = False) -> dict:
    """Only original producer and source addresses; never caller evidence bodies."""
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("actual SourceVisibilityProducer required")
    if type(preserve_overlapping_spans_shadow) is not bool:
        raise ValueError("overlap preservation shadow must be explicit boolean")
    if type(immutable_exact_endpoints_shadow) is not bool:
        raise ValueError("immutable exact endpoint shadow must be explicit boolean")
    if type(partition_exact_collinear_overlaps_shadow) is not bool:
        raise ValueError("exact collinear partition shadow must be explicit boolean")
    if partition_exact_collinear_overlaps_shadow and not (preserve_overlapping_spans_shadow and immutable_exact_endpoints_shadow):
        raise ValueError("exact collinear partition shadow requires exact source-incidence policies")
    if (type(page_id) is not str or not page_id.isdecimal()
            or int(page_id) < 1 or str(int(page_id)) != page_id):
        raise ValueError("canonical_original_page_address_required")
    pub = source.published_snapshot_for_revision(revision_id)
    if (pub is None or source._producer.current_revision_id(pub.revision.document_id) != revision_id
            or int(page_id) not in pub.coverage.decoded_pages or int(page_id) in pub.coverage.failed_pages):
        raise ValueError("current_decoded_original_source_required")
    root = {k:getattr(pub.revision,k) for k in ("document_id","revision_id","source_sha256")}
    root.update(snapshot_id=pub.snapshot.snapshot_id, page_id=page_id)
    def original():
        data = source._producer._store.source_bytes_by_revision.get(revision_id)
        if not data or sha256(data).hexdigest() != root["source_sha256"]:
            raise RuntimeError("original_g17_source_bytes_changed")
    original()
    visibility = source.authority()
    ids = tuple(pub.raster_opening_primitive_observation_ids)
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicated_original_g17_observation_address")
    report = dict(root, status=EvidenceResolutionStatus.ABSTAINED.value,
        reason_codes=["g17_structural_role_and_competing_physical_identity_unproven"],
        source_viewport_ownership_id=None, source_viewport_id=None, source_viewport_bbox=None,
        source_primitive_count=0, source_primitive_dispositions=[], source_positive_graph_primitive_count=0,
        physical_openings=[], raster_candidate_closure=None,
        shared_source_opening_identity_checks=[],
        default_w2_w3_w4=None, exact_coordinate_w2_w3_w4=None,
        scope_complete=False, structural_wall_role_granted=False,
        physical_wall_equivalence_granted=False, host_granted=False, metric_quantity_granted=False)
    if len(ids) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        report["reason_codes"] = ["original_g17_source_primitive_cap_exceeded"]
        return report
    def observations():
        result = {}
        for oid in ids:
            address = ObservationSelector(root["document_id"],revision_id,root["source_sha256"],root["snapshot_id"],oid)
            resolved = visibility.resolve_raster_opening_primitive(address)
            if resolved.status is not EvidenceResolutionStatus.CORROBORATED or resolved.observation is None:
                raise RuntimeError("original_g17_source_primitive_integrity_failure")
            result[oid] = resolved.observation
        return result
    all_source = observations()
    page_source = {i:o for i,o in all_source.items() if o.page_id == page_id}
    report["source_primitive_count"] = len(page_source)
    dpi = RASTER_OPENING_PRIMITIVE_RENDER_DPI
    image_png, parent, frame = source._producer.render_native_page_png(
        **root, dpi=float(dpi), include_native_frame=True, images_only=True)
    full_png, full_parent, full_frame = source._producer.render_native_page_png(
        **root, dpi=float(dpi), include_native_frame=True)
    if parent != full_parent or frame != full_frame or frame.rotation != 0:
        report["reason_codes"] = ["original_g17_source_render_frame_unavailable"]
        return report
    image, full = _rgb(image_png), _rgb(full_png)
    if image.shape != full.shape:
        raise RuntimeError("original_g17_source_raster_frames_contradict")
    image_sha = sha256(image_png).hexdigest()
    regions = source._producer.native_page_image_regions(**root)
    original_receipts = {oid:source._raster_opening_primitive_receipts.get((root["snapshot_id"],oid))
                         for oid in all_source}
    rows = []
    for oid, observation in sorted(page_source.items()):
        receipt = source._raster_opening_primitive_receipts.get((root["snapshot_id"],oid))
        if (receipt is None or receipt.dpi != dpi or receipt.render_sha256 != image_sha
                or len(receipt.pixel_geometry) != 4
                or any(not math.isclose(float(p),float(g)*dpi/72.,rel_tol=0,abs_tol=1e-6)
                       for p,g in zip(receipt.pixel_geometry,observation.geometry))):
            raise RuntimeError("original_g17_pixel_render_receipt_unproven")
        if not observation.source_primitive_ref.startswith("visible:raster_opening_primitive:"):
            raise RuntimeError("original_g17_source_namespace_contradiction")
        owned = _axis_aligned_geometry_fully_covered_by_rect_union(observation.geometry, regions)
        rows.append({"observation_id":oid,
            "source_primitive_id":observation.source_primitive_ref[len("visible:"):],
            "source_parent_ids":tuple(observation.derivation_parent_ids),
            "observation_kind":observation.observation_kind, "geometry":tuple(observation.geometry),
            "inside_original_image_regions":owned,
            "source_paint":_paint(image,full,receipt.pixel_geometry)})
    report["source_primitive_dispositions"] = rows
    views = segment_source_page_viewports(source,revision_id=revision_id,page_id=page_id,
                                          physical_plan_view_shadow=True)
    context = ProviderContext(run_id="g17-original-plan-shadow", workspace_id="source-shadow",
        project_id="source-shadow",document_id=root["document_id"],source_sha256=root["source_sha256"],
        revision_id=revision_id,current_revision_id=revision_id,selected_pages=(int(page_id)-1,),
        owned_viewport_ids=tuple(v.view_id for v in views),evidence_snapshot_id=root["snapshot_id"],
        owned_page_numbers=(int(page_id),),viewport_page_ownership=tuple((v.view_id,int(page_id)) for v in views))
    adapted = [adapt_f07_viewport_to_migration(views,viewport_id=v.view_id,context=context,page_no=int(page_id))
               for v in views if v.view_type in ("floor_plan","floor_finish_plan")]
    plans = [p for p in adapted if not p.abstained]
    if len(plans) != 1:
        report["reason_codes"] = ["source_owned_g17_drawing_view_unavailable_or_competing"]
    else:
        plan = plans[0].ownership_proof
        report.update(source_viewport_ownership_id=plan.ownership_id,
                      source_viewport_id=plan.viewport_id, source_viewport_bbox=plan.bbox)
        segments = []
        for row in rows:
            x1,y1,x2,y2 = row["geometry"]
            inside = (plan.bbox[0] <= min(x1,x2) <= max(x1,x2) <= plan.bbox[2]
                      and plan.bbox[1] <= min(y1,y2) <= max(y1,y2) <= plan.bbox[3])
            overlaps = not (max(x1,x2)<plan.bbox[0] or min(x1,x2)>plan.bbox[2]
                            or max(y1,y2)<plan.bbox[1] or min(y1,y2)>plan.bbox[3])
            row["drawing_disposition"] = "inside" if inside else "crossing" if overlaps else "outside"
            if inside and row["inside_original_image_regions"] and row["source_paint"]["original_solid_and_unchanged"]:
                segments.append({"id":row["source_primitive_id"],"x1":x1,"y1":y1,"x2":x2,"y2":y2,
                    "kind":"line","kind_present":True,"layer":"","dashes":"","width":0.,"width_present":False})
        report["source_positive_graph_primitive_count"] = len(segments)
        for name,tol in (("default_w2_w3_w4",DEFAULT_GAP_SNAP_TOLERANCE_PT),("exact_coordinate_w2_w3_w4",0.)):
            scope_id = stable_contract_id("g17-original-plan-wall-shadow",dict(root,
                viewport_ownership_id=plan.ownership_id,snap_tolerance_pt=tol))
            report[name] = _graph(segments,root=root,scope_id=scope_id,tolerance=tol)
        if preserve_overlapping_spans_shadow:
            guarded_scope = stable_contract_id("g17-original-plan-wall-shadow", dict(root,
                viewport_ownership_id=plan.ownership_id, snap_tolerance_pt=0.,
                preserve_overlapping_spans_shadow=True))
            report["overlap_preserving_exact_w2_w3_w4"] = _graph(segments,
                root=root,scope_id=guarded_scope,tolerance=0.,preserve_overlapping_spans_shadow=True)
        if immutable_exact_endpoints_shadow:
            immutable_scope = stable_contract_id("g17-original-plan-wall-shadow", dict(root,
                viewport_ownership_id=plan.ownership_id, snap_tolerance_pt=0.,
                preserve_overlapping_spans_shadow=preserve_overlapping_spans_shadow,
                immutable_exact_endpoints_shadow=True))
            report["immutable_endpoint_exact_w2_w3_w4"] = _graph(segments,
                root=root,scope_id=immutable_scope,tolerance=0.,
                preserve_overlapping_spans_shadow=preserve_overlapping_spans_shadow,
                immutable_exact_endpoints_shadow=True)
        if partition_exact_collinear_overlaps_shadow:
            partition_scope = stable_contract_id("g17-original-plan-wall-shadow", dict(root,
                viewport_ownership_id=plan.ownership_id, snap_tolerance_pt=0.,
                preserve_overlapping_spans_shadow=True, immutable_exact_endpoints_shadow=True,
                partition_exact_collinear_overlaps_shadow=True))
            report["partitioned_exact_w2_w3_w4"] = _graph(segments,
                root=root,scope_id=partition_scope,tolerance=0.,
                preserve_overlapping_spans_shadow=True,immutable_exact_endpoints_shadow=True,
                partition_exact_collinear_overlaps_shadow=True)
    opening = source.physical_opening_authority()
    physical = {}
    proof_addresses = {}
    for oid in sorted(page_source):
        address = ObservationSelector(root["document_id"],revision_id,root["source_sha256"],root["snapshot_id"],oid)
        proof = opening.prove_existence(address)
        r = proof.existence_record
        if proof.status is EvidenceResolutionStatus.CORROBORATED and proof.proposition == PHYSICAL_OPENING_EXISTS and r is not None:
            physical[r.record_id] = r
            proof_addresses[r.record_id] = address
    for rid,r in sorted(physical.items()):
        own = set(r.source_observation_ids)
        dispositions = {row["observation_id"]:row for row in rows}
        graph_owners = {}
        graph_abstentions = {}
        for name in ("default_w2_w3_w4", "exact_coordinate_w2_w3_w4"):
            graph = report[name]
            owners = {}
            abstentions = {}
            if graph is not None:
                for record in graph["w4_records"]:
                    for raw in record["physical_identity"]["source_primitive_ids"]:
                        owners.setdefault(raw, []).append(record["wall_candidate_id"])
                for chain in graph["w4_abstained_chains"]:
                    for fragment in chain["actual_owned_w3_fragment_rows"]:
                        for raw in (fragment.get("primitive_lineage") or {}).get("source_primitive_ids",()):
                            abstentions.setdefault(raw,[]).append(chain["record_id"])
            graph_owners[name] = {oid:sorted(owners.get(
                dispositions.get(oid,{}).get("source_primitive_id"),())) for oid in sorted(own)}
            graph_abstentions[name] = {oid:sorted(set(abstentions.get(
                dispositions.get(oid,{}).get("source_primitive_id"),()))) for oid in sorted(own)}
        report["physical_openings"].append({"record":asdict(r),
            "source_w4_owners":graph_owners,
            "source_w4_abstained_chain_ids":graph_abstentions,
            "shared_source_competitors":{other:sorted(own & set(p.source_observation_ids))
                for other,p in sorted(physical.items()) if other != rid and own & set(p.source_observation_ids)}})
        for other,p in sorted(physical.items()):
            shared = sorted(own & set(p.source_observation_ids))
            if other > rid and shared:
                comparison = opening.compare_identity(proof_addresses[rid],proof_addresses[other])
                report["shared_source_opening_identity_checks"].append({
                    "left_opening_id":rid,"right_opening_id":other,
                    "shared_source_observation_ids":shared,
                    "producer_identity_comparison":asdict(comparison),
                    "shared_source_is_host_transfer_authority":False})
    if page_source:
        address = ObservationSelector(root["document_id"],revision_id,root["source_sha256"],root["snapshot_id"],next(iter(page_source)))
        report["raster_candidate_closure"] = asdict(opening.assess_raster_candidate_closure(address))
    original()
    if (source.published_snapshot_for_revision(revision_id) != pub or observations() != all_source
            or original_receipts != {oid:source._raster_opening_primitive_receipts.get(
                (root["snapshot_id"],oid)) for oid in all_source}):
        raise RuntimeError("original_g17_scope_source_changed_during_read")
    return report
