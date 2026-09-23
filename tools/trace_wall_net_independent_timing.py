from __future__ import annotations
import argparse, json, time
from pathlib import Path
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer

def emit(stage,start,**kw):
    print(json.dumps({"stage":stage,"seconds":round(time.perf_counter()-start,3),**kw},default=str),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf",type=Path)
    ap.add_argument("--document-id",required=True)
    ap.add_argument("--page-id",required=True)
    ap.add_argument("--mode",choices=("source","wall","semantic"),required=True)
    a=ap.parse_args()
    raw=a.pdf.read_bytes()
    t=time.perf_counter()
    source=SourceVisibilityProducer(producer_method="independent-stage-timing",producer_version="1")
    pub=source.ingest_native_pdf_bytes(document_id=a.document_id,source_bytes=raw,source_locator=str(a.pdf))
    emit("source_ingest",t,visible=len(pub.visible_observation_ids))
    if a.mode=="source": return 0
    current=source.published_snapshot_for_revision(pub.revision.revision_id)
    if a.mode=="wall":
        t=time.perf_counter()
        wp=PhysicalWallCandidateProducer.from_source_visibility_producer(source,page_ids=(a.page_id,))
        emit("wall_build",t)
        t=time.perf_counter()
        wr=wp.authority().resolve_scope(PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,snapshot_id=current.snapshot.snapshot_id,
            page_id=a.page_id,decision_scope_id=f"wall-source:page-{a.page_id}"
        ))
        emit("wall_resolve",t,status=getattr(wr.status,"value",wr.status),walls=len(wr.records or ()),complete=wr.scope_complete,reasons=list(wr.reason_codes or ()))
        return 0
    t=time.perf_counter()
    sp=SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    sr=sp.publish_page_scope(revision_id=current.revision.revision_id,decision_scope_id=f"timing:{a.page_id}",page_ids=(a.page_id,))
    emit("semantic",t,status=getattr(sr.status,"value",sr.status),record=sr.record is not None,
         count=len(sr.record.representative_observation_ids) if sr.record else 0,
         complete=bool(sr.record.physical_opening_universe_complete) if sr.record else False,
         reasons=list(sr.reason_codes or ()))
    return 0
if __name__=="__main__": raise SystemExit(main())
