from __future__ import annotations
import argparse, json, time
from pathlib import Path

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_opening_host_binding_authority import OpeningHostWallUniverseProducer


def stamp(name, start, **extra):
    print(json.dumps({"stage":name,"seconds":round(time.perf_counter()-start,3),**extra},default=str), flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf",type=Path)
    ap.add_argument("--document-id",required=True)
    ap.add_argument("--page-id",required=True)
    a=ap.parse_args()
    raw=a.pdf.read_bytes()

    t=time.perf_counter()
    source=SourceVisibilityProducer(producer_method="wall-net-stage-timing",producer_version="1")
    published=source.ingest_native_pdf_bytes(document_id=a.document_id,source_bytes=raw,source_locator=str(a.pdf))
    stamp("source_visibility_ingest",t,visible=len(published.visible_observation_ids),snapshot=published.snapshot.snapshot_id)

    t=time.perf_counter()
    wallp=PhysicalWallCandidateProducer.from_source_visibility_producer(source,page_ids=(a.page_id,))
    stamp("physical_wall_candidate_build",t)

    t=time.perf_counter()
    wr=wallp.authority().resolve_scope(PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=source.published_snapshot_for_revision(published.revision.revision_id).snapshot.snapshot_id,
        page_id=a.page_id,
        decision_scope_id=f"wall-source:page-{a.page_id}",
    ))
    stamp("physical_wall_candidate_resolve",t,status=getattr(wr.status,"value",wr.status),walls=len(wr.records or ()),complete=wr.scope_complete,reasons=list(wr.reason_codes or ()))

    current=source.published_snapshot_for_revision(published.revision.revision_id)
    t=time.perf_counter()
    sem=SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    sr=sem.publish_page_scope(revision_id=published.revision.revision_id,decision_scope_id=f"timing:{a.page_id}",page_ids=(a.page_id,))
    stamp("semantic_opening_enumeration",t,status=getattr(sr.status,"value",sr.status),record=sr.record is not None,reasons=list(sr.reason_codes or ()),count=len(sr.record.representative_observation_ids) if sr.record else 0)

    t=time.perf_counter()
    hu=OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(wallp.authority()).authority()
    from pb_opening_host_binding_authority import OpeningHostWallUniverseSelector
    ur=hu.resolve_scope(OpeningHostWallUniverseSelector(
        document_id=current.revision.document_id,revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,snapshot_id=current.snapshot.snapshot_id,
        page_id=a.page_id,decision_scope_id=f"wall-source:page-{a.page_id}"
    ))
    stamp("host_wall_universe",t,status=getattr(ur.status,"value",ur.status),walls=len(ur.records or ()),complete=ur.scope_complete,reasons=list(ur.reason_codes or ()))
    return 0

if __name__=="__main__": raise SystemExit(main())
