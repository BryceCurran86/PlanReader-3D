"""Read-only: per-W4-candidate typed semantic evidence (production typed-negative shadow atoms) for p7 viewport scope and p11 page scope."""
import hashlib, json, sys, time
from collections import Counter, defaultdict
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
repo=sys.argv[1]; out=sys.argv[2]; sys.path.insert(0,repo)
from pathlib import Path
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
from pb_source_visibility_authority import SourceVisibilityProducer
PDF=Path(f"{repo}/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
payload=PDF.read_bytes(); sha=hashlib.sha256(payload).hexdigest()
source=SourceVisibilityProducer(producer_method="live-physical-net-wall",producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
pub=source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}",source_bytes=payload,source_locator="memory://x.pdf",page_ids=("7","11"))
res={}
def per_record(scope):
    atoms_by_edge=defaultdict(list)
    kinds=Counter()
    for a in scope.typed_semantic_evidence_atoms or ():
        md=dict(getattr(a,"metadata",{}) or {})
        e=str(md.get("target_edge_id") or "")
        atoms_by_edge[e].append((str(getattr(a,"kind","")),str(md.get("polarity") or ""),getattr(getattr(a,"status",None),"value",str(getattr(a,"status",None))),tuple(getattr(a,"reason_codes",()) or ())))
        kinds[(str(getattr(a,"kind","")),str(md.get("polarity") or ""))]+=1
    rows=[]
    for r in scope.records:
        w=r.wall_candidate
        edge_ids=list(dict.fromkeys(list(getattr(w,"face_a_segment_ids",()) or ())+list(getattr(w,"face_b_segment_ids",()) or ())))
        per_edge=[atoms_by_edge.get(e,[]) for e in edge_ids]
        def all_edges(kind,pol):
            return bool(edge_ids) and all(any(k==kind and p==pol for k,p,_s,_r in ea) for ea in per_edge)
        def any_edge(kind,pol):
            return any(any(k==kind and p==pol for k,p,_s,_r in ea) for ea in per_edge)
        rows.append({"wall_candidate_id":r.wall_candidate_id,"n_edges":len(edge_ids),
            "support_wall_all":all_edges("physical_wall_linework","supporting"),"support_wall_any":any_edge("physical_wall_linework","supporting"),
            "opp_any":sorted({k for ea in per_edge for k,p,_s,_r in ea if p=="opposing"}),
            "opp_all":sorted({k for k in ("grid","furniture","hatch_or_pattern","dimension_annotation","glazing","table_or_schedule_frame","symbol","annotation_border") if all_edges(k,"opposing")}),
            "centerline":[list(map(float,p)) for p in getattr(w,"centerline_pts",())],"source_primitive_ids":list(r.physical_identity.source_primitive_ids)})
    return rows,{f"{k}|{p}":v for (k,p),v in kinds.items()}
t=time.time()
prod7=PhysicalWallCandidateProducer.from_authenticated_viewports(source,page_ids=("7",)); auth7=prod7.authority()
pubd=source.published_snapshot_for_revision(pub.revision.revision_id)
sel=auth7.selectors_for_authenticated_viewports(document_id=pubd.revision.document_id,revision_id=pubd.revision.revision_id,source_sha256=pubd.revision.source_sha256,snapshot_id=pubd.snapshot.snapshot_id,page_id="7",view_type=DrawingViewType.FLOOR_PLAN.value)[0]
sc=auth7.resolve_scope(sel); rows,k=per_record(sc); res["p7_viewport"]={"rows":rows,"atom_kinds":k}
print("p7",len(rows),k,round(time.time()-t,1),flush=True)
prod11=PhysicalWallCandidateProducer.from_source_visibility_producer(source,page_ids=("11",)); auth11=prod11.authority()
pubd=source.published_snapshot_for_revision(pub.revision.revision_id)
sel=PhysicalWallCandidateSelector(document_id=pubd.revision.document_id,revision_id=pubd.revision.revision_id,source_sha256=pubd.revision.source_sha256,snapshot_id=pubd.snapshot.snapshot_id,page_id="11",decision_scope_id=_decision_scope_id("11"))
sc=auth11.resolve_scope(sel); rows,k=per_record(sc); res["p11_page"]={"rows":rows,"atom_kinds":k}
print("p11",len(rows),k,round(time.time()-t,1),flush=True)
json.dump(res,open(out,"w"))
print("saved",out)
