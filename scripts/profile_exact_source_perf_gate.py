#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, resource, subprocess, sys, time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--pdf", required=True)
parser.add_argument("--pages", required=True, help="1-based inclusive comma/range, e.g. 41-45")
parser.add_argument("--label", required=True)
parser.add_argument("--wall-only", action="store_true")
parser.add_argument("--scale-only", action="store_true")
args=parser.parse_args()
repo=Path(args.repo).resolve()
sys.path.insert(0,str(repo))

import fitz
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_gross_wall_geometry_composition import compose_live_gross_wall_geometry
from pb_live_whole_wall_role_composition import compose_live_whole_wall_roles
from pb_live_external_physical_net_wall_publication import compose_live_external_physical_net_wall_publication
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
import pb_physical_wall_candidate_authority as wall_candidates
import pb_live_wall_opening_authority_composition as wall_composition
import pb_wall_room_topology_stage_a as topology_stage_a
import pb_physical_scale_authority as scale_authority

def pagespec(text):
    out=[]
    for part in text.split(","):
        if "-" in part:
            a,b=map(int,part.split("-",1)); out.extend(range(a,b+1))
        else: out.append(int(part))
    return tuple(dict.fromkeys(out))

def status(v):
    return getattr(v,"value",str(v))

def canon_hash(obj):
    payload=json.dumps(obj,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(payload).hexdigest()

stage_calls={}
_HIGH_FREQUENCY_STAGE_NAMES = {
    "openings.prove_existence",
    "openings._visible_snapshot_records",
    "openings._visible_candidates_for",
    "openings._visible_all_structural_candidates",
    "openings._visible_structural_candidates",
    "openings._visible_generic_correlated_candidates",
}

def timed(name, fn):
    def wrapper(*a, **k):
        started=time.perf_counter()
        call_no=stage_calls.get(name, {"calls":0})["calls"] + 1
        sampled = (
            name not in _HIGH_FREQUENCY_STAGE_NAMES
            or call_no == 1
            or call_no % 1000 == 0
        )
        if sampled:
            print(f"PERF_STAGE_START name={name} call={call_no}", flush=True)
        try:
            return fn(*a, **k)
        finally:
            elapsed=time.perf_counter()-started
            row=stage_calls.setdefault(name, {"calls":0, "total_s":0.0, "max_s":0.0})
            row["calls"] += 1
            row["total_s"] += elapsed
            row["max_s"] = max(row["max_s"], elapsed)
            if sampled:
                print(
                    f"PERF_STAGE_END name={name} call={call_no} elapsed_s={elapsed:.6f} total_s={row['total_s']:.6f}",
                    flush=True,
                )
    return wrapper

def wrap_module_function(module, attr, label):
    if hasattr(module, attr):
        original=getattr(module, attr)
        setattr(module, attr, timed(label, original))

for attr in (
    "_visible_observations_by_page",
    "_source_page_segments",
    "_build_scope_result",
    "_assemble_scope_result",
    "_proven_filled_wall_strips",
    "_filter_proven_wall_strip_geometry",
    "build_wall_graph_for_viewport",
    "classify_junctions",
    "assemble_wall_topology",
    "collect_physical_wall_identities",
    "resolve_physical_wall_equivalence",
    "_producer_wall_strip_relation_overrides",
    "_producer_shared_source_face_relation_overrides",
    "_producer_opening_relation_overrides",
):
    wrap_module_function(wall_candidates, attr, f"walls.{attr}")

wrap_module_function(
    wall_composition,
    "build_semantic_opening_inventory_completeness",
    "openings.build_semantic_opening_inventory_completeness",
)

def wrap_method(cls, attr, label):
    original=getattr(cls, attr)
    setattr(cls, attr, timed(label, original))

wrap_method(
    wall_composition.SemanticOpeningEnumerationProducer,
    "publish_page_scope",
    "openings.semantic_publish_page_scope",
)
wrap_method(
    wall_composition.PhysicalOpeningAuthority,
    "prove_existence",
    "openings.prove_existence",
)
for attr in (
    "_visible_snapshot_records",
    "_visible_candidates_for",
):
    wrap_method(
        wall_composition.PhysicalOpeningAuthority,
        attr,
        f"openings.{attr}",
    )

for attr in (
    "filter_structural_segments",
    "split_segments_at_intersections",
    "snap_geometry",
    "_snap_geometry_indexed",
    "merge_collinear_degree_two_nodes",
    "_merge_collinear_degree_two_nodes_indexed",
):
    wrap_module_function(topology_stage_a, attr, f"topology.{attr}")
wrap_method(
    wall_composition.OpeningHostBindingProducer,
    "publish",
    "openings.host_binding_publish",
)
wrap_method(
    wall_composition.OpeningHostFrameProducer,
    "publish",
    "openings.host_frame_publish",
)
scale_authority.PhysicalScaleProducer._scope_bbox = staticmethod(
    timed("scale._scope_bbox", scale_authority.PhysicalScaleProducer._scope_bbox)
)
for attr in ("_trusted_words", "_visible_segments", "publish_scope"):
    wrap_method(
        scale_authority.PhysicalScaleProducer,
        attr,
        f"scale.{attr}",
    )

page_ids=tuple(str(p) for p in pagespec(args.pages))
page_indices=[int(p)-1 for p in page_ids]
pdf=Path(args.pdf)
payload=pdf.read_bytes()
source_sha=hashlib.sha256(payload).hexdigest()
source=SourceVisibilityProducer(producer_method="exact-source-perf-gate",producer_version="1")
timings={}
repo_head = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()
partial={"label":args.label,"repo":str(repo),"repo_head":repo_head,"source_sha256":source_sha,"pages":list(page_ids),"timings":timings,"stage_calls":stage_calls}
def emit():
    print("PERF_GATE_JSON="+json.dumps(partial,sort_keys=True,default=str), flush=True)
t=time.perf_counter()
published=source.ingest_native_pdf_bytes(
    document_id=f"diag:{source_sha[:24]}",
    source_bytes=payload,
    source_locator=f"memory://{pdf.name}",
    page_ids=page_ids,
)
timings["source_ingest_s"]=time.perf_counter()-t
partial["visible_segment_count"]=len(published.visible_observation_ids)
emit()

refreshed=source.published_snapshot_for_revision(published.revision.revision_id)
assert refreshed is not None

scale_producer=PhysicalScaleProducer.from_source_visibility_producer(source)
scale_rows=[]
for page_id in page_ids:
    sel=PhysicalScaleSelector(
        document_id=refreshed.revision.document_id,
        revision_id=refreshed.revision.revision_id,
        source_sha256=refreshed.revision.source_sha256,
        snapshot_id=refreshed.snapshot.snapshot_id,
        page_id=page_id,
    )
    t=time.perf_counter()
    segs=scale_producer._visible_segments(sel,refreshed)
    elapsed=time.perf_counter()-t
    scale_rows.append({"page_id":page_id,"normalized_visible_segments":len(segs),"elapsed_s":elapsed})
    partial["scale_rows"]=scale_rows
    timings["scale_normalization_total_s"]=sum(x["elapsed_s"] for x in scale_rows)
    emit()

if args.scale_only:
    publish_rows=[]
    for page_id in page_ids:
        sel=PhysicalScaleSelector(
            document_id=refreshed.revision.document_id,
            revision_id=refreshed.revision.revision_id,
            source_sha256=refreshed.revision.source_sha256,
            snapshot_id=refreshed.snapshot.snapshot_id,
            page_id=page_id,
        )
        t=time.perf_counter()
        result=scale_producer.publish_scope(sel)
        elapsed=time.perf_counter()-t
        publish_rows.append({
            "page_id":page_id,
            "status":status(result.status),
            "reason_codes":list(result.reason_codes),
            "elapsed_s":elapsed,
        })
        partial["scale_publish_rows"]=publish_rows
        emit()
    print(json.dumps(partial,sort_keys=True,default=str))
    raise SystemExit(0)

t=time.perf_counter()
wall=compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=page_ids,
)
timings["wall_opening_composition_s"]=time.perf_counter()-t
partial["peak_rss_kb"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
emit()

if args.wall_only:
    print(json.dumps(partial,sort_keys=True,default=str))
    raise SystemExit(0)

t=time.perf_counter()
voids=compose_live_physical_opening_voids(
    source_visibility_producer=source,
    wall_opening_composition=wall,
)
timings["physical_opening_void_s"]=time.perf_counter()-t
emit()

t=time.perf_counter()
gross=compose_live_gross_wall_geometry(
    source_visibility_producer=source,
    wall_opening_composition=wall,
    physical_void_composition=voids,
)
timings["gross_wall_s"]=time.perf_counter()-t
emit()

t=time.perf_counter()
roles=compose_live_whole_wall_roles(gross_wall_composition=gross)
timings["whole_wall_role_s"]=time.perf_counter()-t
emit()

t=time.perf_counter()
pub=compose_live_external_physical_net_wall_publication(
    wall_opening_composition=wall,
    physical_void_composition=voids,
    gross_wall_composition=gross,
    whole_wall_role_composition=roles,
)
timings["net_wall_publication_s"]=time.perf_counter()-t
emit()

wall_scopes=[]
for trace in wall.wall_scopes:
    selector=wall.physical_wall_candidate_authority.selector_for_decision_scope(
        document_id=refreshed.revision.document_id,
        revision_id=refreshed.revision.revision_id,
        source_sha256=refreshed.revision.source_sha256,
        snapshot_id=refreshed.snapshot.snapshot_id,
        page_id=trace.page_id,
        decision_scope_id=f"wall-source:page-{trace.page_id}",
    )
    resolved=wall.physical_wall_candidate_authority.resolve_scope(selector) if selector else None
    eq=getattr(resolved,"equivalence",None)
    wall_scopes.append({
        "page_id":trace.page_id,
        "status":status(trace.status),
        "reason_codes":list(trace.reason_codes),
        "scope_complete":trace.scope_complete,
        "wall_candidate_ids":list(trace.wall_candidate_ids),
        "representative_wall_ids":list(getattr(eq,"representative_wall_ids",()) or ()),
        "ambiguous_wall_ids":list(getattr(eq,"ambiguous_wall_ids",()) or ()),
        "pair_classifications":[list(x) for x in (getattr(eq,"pair_classifications",()) or ())],
    })

authority={
 "wall_status":status(wall.status),
 "wall_reason_codes":list(wall.reason_codes),
 "wall_scopes":wall_scopes,
 "opening_bindings":[{
   "opening_identity_id":x.opening_identity_id,"page_id":x.page_id,
   "status":status(x.status),"reason_codes":list(x.reason_codes),
   "record_id":x.record_id,"host_wall_id":x.host_wall_id,
   "member_wall_candidate_ids":list(x.member_wall_candidate_ids)
 } for x in wall.opening_bindings],
 "host_frames":[{
   "opening_identity_id":x.opening_identity_id,"status":status(x.status),
   "reason_codes":list(x.reason_codes),"record_id":x.record_id,
   "host_wall_id":x.host_wall_id,"whole_wall_candidate_ids":list(x.whole_wall_candidate_ids)
 } for x in wall.host_frames],
 "void_status":status(voids.status),"void_reason_codes":list(voids.reason_codes),
 "void_traces":[x.__dict__ for x in voids.traces],
 "gross_status":status(gross.status),"gross_reason_codes":list(gross.reason_codes),
 "gross_traces":[x.__dict__ for x in gross.traces],
 "role_status":status(roles.status),"role_reason_codes":list(roles.reason_codes),
 "role_traces":[x.__dict__ for x in roles.traces],
 "publication_status":status(pub.status),"publication_reason_codes":list(pub.reason_codes),
 "external_wall_ids":list(pub.external_wall_ids),
 "gross_geometry_record_ids":list(pub.gross_geometry_record_ids),
 "whole_wall_role_record_ids":list(pub.whole_wall_role_record_ids),
 "physical_void_record_ids":list(pub.physical_void_record_ids),
 "opening_universe_record_ids":list(pub.opening_universe_record_ids),
 "quantity_evidence":None if pub.quantity_evidence is None else pub.quantity_evidence.__dict__,
}

peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

extractor=GenericPlanReaderExtractor()
t=time.perf_counter()
preds=extractor.extract_from_pdf(pdf,pages=page_indices,collect_item35_shadow=False)
timings["commercial_extraction_s"]=time.perf_counter()-t
emit()

pred_payload=[p.to_dict() for p in preds]
out={
 "label":args.label,
 "repo":str(repo),
 "source_sha256":source_sha,
 "pages":list(page_ids),
 "visible_segment_count":sum(1 for oid in refreshed.visible_observation_ids),
 "scale_rows":scale_rows,
 "timings":timings,
 "peak_memory_bytes":peak,
 "authority_fingerprint":canon_hash(authority),
 "prediction_fingerprint":canon_hash(pred_payload),
 "prediction_count":len(pred_payload),
 "physical_net_wall_live":extractor.physical_net_wall_live,
 "authority":authority,
}
print(json.dumps(out,sort_keys=True,default=str))
