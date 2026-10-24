"""Source-addressed review geometry and evidence packets, without promotion.

These projections use the existing physical/source authorities and canonical
opening graph. PDF coordinates never become metres. Source correspondence is
a review relationship, never physical SAME, signed-record migration or count.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import math
import re

from pb_migration_contracts import EvidenceResolutionStatus as Status, stable_contract_id
from pb_opening_host_binding_authority import _opening_geometry
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_nominal_opening_canonical_shadow import (
    build_nominal_opening_canonical_shadow, _build_approved_single_width_review,
)
from pb_geometry_takeoff_model import MeasurementRecord
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS


def _owned_opening(source, selector):
    if type(source) is not SourceVisibilityProducer or type(selector) is not ObservationSelector:
        raise TypeError("original producer and exact source selector required")
    result = source.physical_opening_authority().prove_existence(selector)
    return result.existence_record if result.status is Status.CORROBORATED else None


def aperture_geometry_shadow(source, selector):
    """An owned source-space polygon/axis, independent of nominal dimensions."""
    opening = _owned_opening(source, selector)
    if opening is None:
        return None
    g = _opening_geometry(source.physical_opening_authority(), opening)
    if g is None:
        return None
    def point(u, v):
        return (g.origin[0]+u*g.axis[0]+v*g.normal[0],
                g.origin[1]+u*g.axis[1]+v*g.normal[1])
    return {"opening_identity_id":opening.record_id,
            "coordinate_unit":"pdf_point", "page_id":opening.page_id,
            "origin_pt":g.origin, "axis_unit":g.axis, "normal_unit":g.normal,
            "span_pt":g.length, "band_thickness_pt":g.thickness,
            "polygon_pt":tuple(point(u,v) for u,v in (
                (0,-g.thickness/2),(g.length,-g.thickness/2),
                (g.length,g.thickness/2),(0,g.thickness/2))),
            "source_observation_ids":opening.source_observation_ids,
            "metric_geometry_resolved":False, "host_frame_authority_granted":False}


def transform_aperture_point_shadow(source, selector, point, *, to_page=False):
    """Round-trippable local aperture coordinates; no caller-built frame."""
    if type(to_page) is not bool:
        raise TypeError("coordinate direction requires explicit bool")
    if not isinstance(point,(tuple,list)) or len(point)!=2 or any(
            type(x) not in (int,float) or not math.isfinite(x) for x in point):
        raise ValueError("two finite source-coordinate values required")
    geometry = aperture_geometry_shadow(source,selector)
    if geometry is None:
        return None
    origin,axis,normal=(geometry[k] for k in ("origin_pt","axis_unit","normal_unit"))
    if to_page:
        return tuple(origin[i]+point[0]*axis[i]+point[1]*normal[i] for i in (0,1))
    delta=tuple(point[i]-origin[i] for i in (0,1))
    return (sum(delta[i]*axis[i] for i in (0,1)),sum(delta[i]*normal[i] for i in (0,1)))


def opening_source_lineage_packet(source, selector, *, additional_text_ids=()):
    """Export the complete authenticated parent DAG, including shared parents.

    It is an explanation artifact, not a deserializable authority. Native text
    can enter only through this opening's owned label-dimension producer.
    """
    opening=_owned_opening(source,selector)
    if opening is None:
        return None
    label=OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(selector)
    owned_text=() if label.evidence is None else label.evidence.source_text_observation_ids
    if set(additional_text_ids)-set(owned_text):
        raise ValueError("text observations must belong to this physical opening")
    roots=tuple(sorted(set(opening.source_observation_ids)|set(owned_text)))
    raw=source._producer.authority()
    records={}
    missing=[]
    pending=list(roots)
    while pending:
        oid=pending.pop()
        if oid in records or oid in missing:
            continue
        if len(records)+len(missing)>=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
            raise ValueError("source lineage packet exceeds topology safety budget")
        result=raw.resolve(replace(selector,observation_id=oid))
        observation=result.observation
        if result.status is not Status.CORROBORATED or observation is None:
            missing.append(oid)
            continue
        if (observation.page_id != opening.page_id or any(
                getattr(observation,k)!=getattr(opening,k) for k in (
                    "document_id","revision_id","source_sha256","snapshot_id"))):
            raise ValueError("foreign source parent in opening proof")
        records[oid]=asdict(observation)
        pending.extend(observation.derivation_parent_ids)
    packet = {"roots":roots, "observations":[records[k] for k in sorted(records)],
              "unresolved_parent_ids":tuple(sorted(missing)),
              "source_proof_closed":not missing, "authority_import_allowed":False}
    _, blockers = _source_support_signature({"physical_opening":asdict(opening),
        "opening_identity_id":opening.record_id, "page_id":opening.page_id,
        "source_lineage":packet})
    packet["source_proof_closed"] = not blockers
    packet["source_proof_blockers"] = blockers
    return packet


def _wall_review_rows(composition,page_id):
    """Keep ordinary and supplemental interpretations in separate source scopes."""
    rows=[]
    for kind,authority in (("ordinary",composition.physical_wall_candidate_authority),
            ("supplemental",composition.supplemental_physical_wall_candidate_authority)):
        if authority is None:
            continue
        for scope in authority._scopes.values():
            if scope.page_id!=page_id:
                continue
            for record in scope.records:
                rows.append({"scope":kind,"scope_complete":scope.scope_complete,
                    "wall_candidate_id":record.wall_candidate_id,
                    "polyline_pt":record.wall_candidate.centerline_pts,
                    "source_fragments":[asdict(f) for f in record.source_edge_fragments]})
    return sorted(rows,key=lambda r:(r["scope"],r["wall_candidate_id"]))


def build_opening_review_packets(source,composition,*,source_fragment_roles_shadow=False,
                                nominal_width_approvals=()):
    """Collect geometry, label, lineage and candidate-frame facts per opening.

    All physical openings are retained, including unhosted or unmeasured ones.
    Each packet names the next missing evidence, rather than completing it.
    """
    if type(source_fragment_roles_shadow) is not bool:
        raise TypeError("explicit fragment policy required")
    if not isinstance(nominal_width_approvals, (tuple, list)):
        raise TypeError("explicit per-opening width approval records required")
    approvals={}
    for approval in nominal_width_approvals:
        if type(approval) is not MeasurementRecord:
            raise TypeError("existing MeasurementRecord approval required")
        if approval.geometry_ref in approvals:
            raise ValueError("duplicate nominal width approval target")
        approvals[approval.geometry_ref]=approval
    opening_ids={t.opening_identity_id for t in composition.opening_bindings}
    if set(approvals)-opening_ids:
        raise ValueError("nominal width approval target absent from source composition")
    current_openings={}
    if approvals:
        from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
        voids=compose_live_physical_opening_voids(
            source_visibility_producer=source,wall_opening_composition=composition)
        current_openings={o.physical_opening_id:o for o in voids.canonical_openings}
    published=source.published_snapshot_for_revision(composition.revision_id)
    if published is None:
        raise ValueError("review source revision unavailable")
    labels=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    frames=OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority)
    wall_rows={page:_wall_review_rows(composition,page) for page in composition.page_ids}
    packets=[]
    frame_traces={f.opening_identity_id:f for f in composition.host_frames}
    for trace in composition.opening_bindings:
        selector=ObservationSelector(published.revision.document_id,composition.revision_id,
            published.revision.source_sha256,published.snapshot.snapshot_id,
            trace.representative_observation_id)
        opening=_owned_opening(source,selector)
        if opening is None and trace.opening_identity_id is None:
            packet={"opening_identity_id":None,"page_id":trace.page_id,
                "selector":asdict(selector),"physical_opening":None,"host":asdict(trace),
                "whole_wall_frame":None,"local_aperture_frame":None,"aperture_geometry":None,
                "nominal_axes":None,"figured_label":None,"canonical_nominal_review":None,
                "source_lineage":None,"source_related_wall_candidates":[],
                "next_required_evidence":["physical_opening_existence"],
                "takeoff_eligible":False,"deduction_authority":False}
            packet["packet_id"]=stable_contract_id("opening_source_review_shadow",packet,digest_chars=32)
            packets.append(packet)
            continue
        if opening is None or opening.record_id!=trace.opening_identity_id:
            raise ValueError("review opening failed original source authentication")
        axes=labels.ordered_compact_axes_shadow(selector)
        lineage=opening_source_lineage_packet(source,selector)
        canonical=build_nominal_opening_canonical_shadow(source,selector)
        if opening.record_id in approvals:
            canonical=_build_approved_single_width_review(source,selector,
                approval=approvals[opening.record_id],current_opening=current_openings.get(opening.record_id))
        binding=composition.binding_selectors.get(opening.record_id)
        local=None if binding is None else frames.local_source_frame_shadow(
            opening_selector=selector,host_binding_selector=binding,
            supplemental_wall_candidate_authority=composition.supplemental_physical_wall_candidate_authority,
            source_fragment_roles_shadow=source_fragment_roles_shadow)
        whole=frame_traces.get(opening.record_id)
        blockers=[]
        if lineage is None or not lineage["source_proof_closed"]:
            blockers.append("original_source_parent_lineage")
            if lineage is not None:
                blockers.extend(lineage.get("source_proof_blockers", ()))
        if not trace.host_wall_id: blockers.append("source_owned_unique_host")
        if whole is None or not whole.record_id: blockers.append("connected_whole_wall_frame")
        if (opening.record_id in approvals
                and not canonical.metadata["opening_kind_resolved"]):
            blockers.append("source_owned_filling_kind")
        if axes.evidence is None:
            blockers.append("owned_nominal_height" if opening.record_id in approvals
                            else "owned_ordered_nominal_dimensions")
        # Source-plan geometry cannot establish any of these missing facts.
        blockers.extend(("rough_opening_geometry","metric_wall_placement","opening_universe_completeness"))
        packet={"opening_identity_id":opening.record_id,"page_id":opening.page_id,
            "selector":asdict(selector),"physical_opening":asdict(opening),
            "host":asdict(trace),"whole_wall_frame":None if whole is None else asdict(whole),
            "local_aperture_frame":None if local is None else asdict(local),
            "aperture_geometry":aperture_geometry_shadow(source,selector),
            "nominal_axes":asdict(axes),
            "figured_label":asdict(labels.publish_scope(selector)),
            "canonical_nominal_review":None if canonical is None else canonical.to_dict(),
            "source_lineage":lineage,
            "next_required_evidence":blockers,
            "takeoff_eligible":False,"deduction_authority":False}
        own=set(opening.source_observation_ids)
        # Exact source-fragment membership is useful even for unbound openings.
        packet["source_related_wall_candidates"]=[r for r in wall_rows[opening.page_id]
            if r["wall_candidate_id"] in trace.member_wall_candidate_ids or any(
                own & set(f["source_primitive_ids"]) for f in r["source_fragments"])]
        packet["packet_id"]=stable_contract_id("opening_source_review_shadow",packet,digest_chars=32)
        packets.append(packet)
    return tuple(sorted(packets,key=lambda p:(p["page_id"] or "",p["opening_identity_id"] or p["packet_id"])))


def _source_support_signature(packet):
    """Check explanation-DAG structure; this never authenticates an import."""
    def blocked(reason):
        return None, (reason,)
    def identifiers(values):
        return (isinstance(values, (tuple, list)) and bool(values)
                and all(type(v) is str and v and v == v.strip() for v in values)
                and len(values) == len(set(values)))
    if not isinstance(packet, dict):
        return blocked("source_packet_malformed")
    opening, lineage = packet.get("physical_opening"), packet.get("source_lineage")
    if not isinstance(opening, dict) or not isinstance(lineage, dict):
        return blocked("physical_source_packet_unavailable")
    if (packet.get("opening_identity_id") != opening.get("record_id")
            or not opening.get("record_id") or packet.get("page_id") != opening.get("page_id")):
        return blocked("source_packet_opening_identity_mismatch")
    if (lineage.get("source_proof_closed") is not True
            or not isinstance(lineage.get("unresolved_parent_ids"), (tuple,list))
            or lineage["unresolved_parent_ids"]):
        return blocked("source_parent_closure_unproven")
    physical_roots = opening.get("source_observation_ids")
    roots = lineage.get("roots", physical_roots)
    if not identifiers(physical_roots) or not identifiers(roots) or not set(physical_roots) <= set(roots):
        return blocked("source_packet_roots_invalid")
    rows = lineage.get("observations")
    if not isinstance(rows, (tuple, list)) or len(rows) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        return blocked("source_parent_evidence_budget_exceeded")
    scope = ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")
    if any(type(opening.get(k)) is not str or not opening[k] for k in scope):
        return blocked("source_packet_scope_invalid")
    if len(opening["source_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in opening["source_sha256"]):
        return blocked("source_packet_scope_invalid")
    selector = packet.get("selector")
    if selector is not None and (not isinstance(selector, dict) or any(
            selector.get(k) != opening[k] for k in scope if k != "page_id")):
        return blocked("source_packet_selector_mismatch")
    by_id, parents = {}, {}
    edge_count = 0
    for row in rows:
        if not isinstance(row, dict):
            return blocked("source_parent_record_malformed")
        oid = row.get("observation_id")
        if type(oid) is not str or not oid or oid in by_id:
            return blocked("source_parent_identity_invalid_or_duplicate")
        if any(row.get(k) != opening[k] for k in scope):
            return blocked("source_parent_scope_mismatch")
        parent_ids = row.get("derivation_parent_ids", ())
        if parent_ids and not identifiers(parent_ids):
            return blocked("source_parent_links_malformed")
        if not isinstance(parent_ids, (tuple, list)):
            return blocked("source_parent_links_malformed")
        geometry = row.get("geometry")
        if (not isinstance(geometry, (tuple, list)) or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in geometry)
                or any(type(row.get(k)) is not str or not row[k]
                       for k in ("observation_kind", "source_primitive_ref"))):
            return blocked("source_parent_geometry_or_kind_invalid")
        edge_count += len(parent_ids)
        if len(rows) + edge_count > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
            return blocked("source_parent_evidence_budget_exceeded")
        by_id[oid], parents[oid] = row, tuple(parent_ids)
    if not set(roots) <= set(by_id) or any(set(p)-set(by_id) for p in parents.values()):
        return blocked("source_parent_records_missing")
    reachable, pending = set(), list(roots)
    while pending:
        oid = pending.pop()
        if oid not in reachable:
            reachable.add(oid)
            pending.extend(parents[oid])
    if reachable != set(by_id):
        return blocked("source_parent_records_unreachable")
    children = {oid:[] for oid in by_id}
    remaining = {oid:len(p) for oid,p in parents.items()}
    for oid, parent_ids in parents.items():
        for parent in parent_ids:
            children[parent].append(oid)
    ready = [oid for oid in by_id if not remaining[oid]]
    signatures = {}
    while ready:
        oid = ready.pop()
        row = by_id[oid]
        signatures[oid] = stable_contract_id("opening_source_parent_review", {
            "kind":row["observation_kind"], "source_primitive_ref":row["source_primitive_ref"],
            "geometry":tuple(row["geometry"]),
            "parents":tuple(sorted(signatures[p] for p in parents[oid]))}, digest_chars=32)
        for child in children[oid]:
            remaining[child] -= 1
            if not remaining[child]:
                ready.append(child)
    if len(signatures) != len(by_id):
        return blocked("source_parent_cycle")
    return ((opening["document_id"], opening["revision_id"], opening["source_sha256"],
             opening["page_id"], tuple(sorted(signatures[oid] for oid in physical_roots))), ())


def compare_opening_source_correspondence(original_packets,alternate_packets):
    """Retain all source-support matches, including many-to-many alternatives."""
    def signature(packet):
        return _source_support_signature(packet)[0]
    old={p["packet_id"]:signature(p) for p in original_packets}
    if len(old) != len(original_packets):
        raise ValueError("duplicate original review packet ID")
    alternate_ids=[p["packet_id"] for p in alternate_packets]
    if len(set(alternate_ids)) != len(alternate_ids):
        raise ValueError("duplicate alternate review packet ID")
    relationships=[]
    for new in alternate_packets:
        sig, blockers = _source_support_signature(new)
        exact={p["opening_identity_id"] for p in original_packets
               if sig is not None and old[p["packet_id"]]==sig}
        relationships.append({"alternate_opening_id":new["opening_identity_id"],
            "exact_source_support_original_ids":sorted(exact),
            "source_support_packet_complete":sig is not None,
            "source_support_blockers":list(blockers),
            "source_relationship":"exact_source_support" if exact else "additional_or_changed_source_support",
            "physical_identity_alias_granted":False,"signed_record_migration_granted":False})
    return relationships


def nominal_opening_obj_shadow(canonical):
    """Export an unplaced nominal 3D review face, without fabricating depth.

    The X/Z face has two triangles at Y=0. No sill, wall position, rough frame,
    storey or wall thickness is invented. This is an asset, not a placed model.
    """
    from pb_canonical_building import CanonicalOpening, ReviewState
    if type(canonical) is not CanonicalOpening:
        raise TypeError("existing canonical opening required")
    if (type(canonical.id) is not str or len(canonical.id) > 256
            or re.fullmatch(r"[A-Za-z0-9_.:-]+", canonical.id) is None):
        raise ValueError("safe nominal OBJ object identifier required")
    if (canonical.review_state is not ReviewState.REVIEW_REQUIRED
            or canonical.takeoff_eligible is not False or canonical.deduction_authority is not False
            or canonical.wall_id is not None or canonical.sill_height_m is not None
            or canonical.offset_along_wall_m is not None
            or canonical.metadata.get("dimension_basis")!="nominal_compact_HHWW"):
        raise ValueError("unplaced nominal review opening required")
    w,h=canonical.width_m,canonical.height_m
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (w,h)):
        raise ValueError("owned positive nominal axes required")
    return ("# Unplaced nominal opening review face; units metre\n"
            "# No depth, wall placement, sill or takeoff authority\n"
            f"o {canonical.id}\nv 0 0 0\nv {w:.9g} 0 0\nv {w:.9g} 0 {h:.9g}\nv 0 0 {h:.9g}\n"
            "f 1 2 3\nf 1 3 4\n")
