from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace

import fitz

import pb_wall_finish_face_binding_authority as m
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_role_authority import WallRoleProducer, WallRoleSelector


def make_pdf(path: Path) -> None:
    doc=fitz.open(); page=doc.new_page(width=300,height=200)
    for a,b in [((50,50),(250,50)),((250,50),(250,150)),((250,150),(50,150)),((50,150),(50,50)),((150,50),(150,150))]:
        page.draw_line(fitz.Point(*a),fitz.Point(*b),color=(0,0,0),width=1)
    page.insert_text(fitz.Point(80,100),"wall key to finish externally",fontsize=8,color=(0,0,0))
    page.draw_line(fitz.Point(80,100),fitz.Point(52,100),color=(0,0,0),width=.5)
    page.draw_circle(fitz.Point(50,100),2,color=(0,0,0),fill=(0,0,0),width=.5)
    doc.save(path); doc.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"x.pdf"; make_pdf(path)
        source=SourceVisibilityProducer(producer_method="debug",producer_version="1")
        pub0=source.ingest_native_pdf_bytes(document_id="debug",source_bytes=path.read_bytes(),source_locator=str(path))
        walls=PhysicalWallCandidateProducer.from_source_visibility_producer(source,page_ids=("1",)).authority()
        pub=source.published_snapshot_for_revision(pub0.revision.revision_id)
        assert pub is not None
        scope=walls.resolve_scope(PhysicalWallCandidateSelector(
            document_id=pub.revision.document_id,revision_id=pub.revision.revision_id,
            source_sha256=pub.revision.source_sha256,snapshot_id=pub.snapshot.snapshot_id,
            page_id="1",decision_scope_id="wall-source:page-1"))
        print("SCOPE",scope.status,scope.scope_complete,len(scope.records),scope.reason_codes,flush=True)
        roles=WallRoleProducer.from_source_topology(physical_wall_candidate_authority=walls)
        role_ids={}
        for rec in scope.records:
            rr=roles.publish(WallRoleSelector(
                document_id=pub.revision.document_id,revision_id=pub.revision.revision_id,
                source_sha256=pub.revision.source_sha256,snapshot_id=pub.snapshot.snapshot_id,
                page_id="1",decision_scope_id="wall-source:page-1",physical_wall_id=rec.wall_candidate_id))
            print("ROLE",rec.wall_candidate_id,rr.status,rr.reason_codes,None if rr.record is None else rr.record.role,flush=True)
            if rr.status is EvidenceResolutionStatus.CORROBORATED and rr.record is not None:
                role_ids[rec.wall_candidate_id]=rr.record
        doc=fitz.open(path); page=doc[0]
        blocks=m._trusted_finish_blocks(source,pub,"1")
        lines=m._page_visible_lines(source,pub,"1",page=page)
        terms=m._filled_terminators(page,8.0,visible_raw_ids={line.raw_id for line in lines})
        print("BLOCKS",blocks,flush=True)
        print("LINES",[(x.observation_id,x.raw_id,x.path_id,x.geometry) for x in lines],flush=True)
        print("TERMS",terms,flush=True)
        for block in blocks:
            paths=m._leader_paths(block[4],lines,terms)
            print("PATHS",paths,flush=True)
            for leader_ids,term in paths:
                target=m._target_from_terminator(term,lines,scope,eligible_wall_ids=set(role_ids))
                print("TARGET",target,flush=True)
        doc.close()


if __name__=="__main__":
    main()
