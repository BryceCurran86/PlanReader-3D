import sys, os, json, hashlib, collections, math
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
from pathlib import Path
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_opening_label_dimension_authority import _gap_span, _dot
pdf = Path(r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf')
payload = pdf.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
src = SourceVisibilityProducer(producer_method="candgap", producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("3",))
rev = pub.revision.revision_id
if len(sys.argv)>2 and sys.argv[2]=='aug':
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
    PhysicalWallCandidateProducer.from_source_visibility_producer(src, page_ids=("3",))
snap = src.published_snapshot_for_revision(rev)
from collections import Counter as _C
print('snapshot observation kinds sample:', len(getattr(snap,'visible_observation_ids',()) or ()), [a for a in dir(snap) if 'observation' in a][:6])
sem = SemanticOpeningEnumerationProducer.from_source_visibility_producer(src)
res = sem.publish_page_scope(revision_id=rev, decision_scope_id="scratch", page_ids=("3",))
physical = src.physical_opening_authority(); vis = src.authority()
sel0 = ObservationSelector(document_id=snap.revision.document_id, revision_id=rev, source_sha256=snap.revision.source_sha256, snapshot_id=snap.snapshot.snapshot_id, observation_id=res.record.representative_observation_ids[0])
cs = physical.visible_candidate_structures(sel0)
print('candidates', len(cs.candidates), collections.Counter(c.structural_pattern for c in cs.candidates))
rows=[]
for c in cs.candidates:
    recs=[]
    for oid in c.source_observation_ids:
        r=vis.resolve_visible(ObservationSelector(document_id=snap.revision.document_id, revision_id=rev, source_sha256=snap.revision.source_sha256, snapshot_id=snap.snapshot.snapshot_id, observation_id=oid))
        if r.observation is not None: recs.append(r.observation)
    g=_gap_span(recs)
    if g is None: continue
    cx=(g.axis[0]*(g.along_min+g.along_max)/2 + g.normal[0]*g.cross_center, g.axis[1]*(g.along_min+g.along_max)/2 + g.normal[1]*g.cross_center)
    rows.append(dict(width=g.along_max-g.along_min, center=[round(cx[0],1),round(cx[1],1)], axis=[round(v,3) for v in g.axis], n=len(c.source_observation_ids), pattern=c.structural_pattern))
widths=sorted(r['width'] for r in rows)
print('with gap', len(rows))
import statistics
print('width quantiles', [round(widths[int(q*(len(widths)-1))],1) for q in (0,.1,.25,.5,.75,.9,1)])
print('candidates with width <=150pt:', sum(1 for w in widths if w<=150), ' <=80:', sum(1 for w in widths if w<=80), ' >300:', sum(1 for w in widths if w>300))
json.dump(rows, open(sys.argv[1],'w'))
# distance of each callout to the nearest small-gap candidate center
import pb_source_plan_opening_callout as co, fitz
d=fitz.open(stream=payload, filetype='pdf')
callouts=co.extract_source_plan_opening_callouts(d[2], source_sha256=sha, source_page=3)
small=[r for r in rows if r['width']<=250]
for c in callouts:
    cx=(c.bbox[0]+c.bbox[2])/2; cy=(c.bbox[1]+c.bbox[3])/2
    near=sorted(((math.hypot(r['center'][0]-cx, r['center'][1]-cy), r['width']) for r in small))[:3]
    print(c.raw_callout, 'expected_gap_pt~', round(max(c.width_mm,c.height_mm)/100*2.834645669/ (100/100) / 1 ,1), 'nearest small-gap candidates (dist,width):', [(round(a),round(b)) for a,b in near])
