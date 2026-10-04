import sys, os, hashlib, collections
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
from pathlib import Path
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
pdf = Path(r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf')
payload = pdf.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
src = SourceVisibilityProducer(producer_method="rprobe", producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("3",))
rev = pub.revision.revision_id
PhysicalWallCandidateProducer.from_source_visibility_producer(src, page_ids=("3",))
snap = src.published_snapshot_for_revision(rev); vis = src.authority()
kinds=collections.Counter(); rows=[]
for oid in snap.visible_observation_ids:
    r = vis.resolve_visible(ObservationSelector(document_id=snap.revision.document_id, revision_id=rev, source_sha256=snap.revision.source_sha256, snapshot_id=snap.snapshot.snapshot_id, observation_id=oid))
    o = r.observation
    if o is None: continue
    kinds[(getattr(o,'observation_kind',None) or getattr(o,'kind_name',None) or type(o).__name__, getattr(o,'origin_kind',None))]+=1
    g=o.geometry
    if len(g)==4: rows.append((getattr(o,'observation_kind',None), [round(v,1) for v in g]))
print(kinds.most_common(8))
def near(g, box): 
    xs=(g[0],g[2]); ys=(g[1],g[3]); return max(xs)>=box[0] and min(xs)<=box[2] and max(ys)>=box[1] and min(ys)<=box[3]
box=(525,185,600,205)
sel=[(k,g) for k,g in rows if near(g,box)]
print('visible segments in window-gap box:', len(sel))
for k,g in sel[:40]: print(' ',k,g)
