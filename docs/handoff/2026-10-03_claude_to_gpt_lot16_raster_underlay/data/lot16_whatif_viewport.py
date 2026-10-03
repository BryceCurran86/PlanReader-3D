# SCRATCH what-if (no repo edit): treat the shadow title-block candidate as the authenticated floor-plan viewport for G17 gating only.
import sys, os, json, time, hashlib, collections
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
from pathlib import Path
import fitz
import pb_physical_opening_viewport_scope_authority as vsa
from pb_title_block_viewport_shadow import propose_title_block_floor_plan_viewport
from pb_viewport_segmentation import segment_page_viewports
orig = vsa._authenticated_viewports
def patched(page, *, page_number):
    f07 = segment_page_viewports(page, page_number=page_number)
    prop = propose_title_block_floor_plan_viewport(page, page_number=page_number, f07_viewports=f07)
    sv = prop.to_segmented_viewport()
    if sv is None: return orig(page, page_number=page_number)
    return (tuple(f07) + (sv,), (sv,))
if sys.argv[1] == 'patch': vsa._authenticated_viewports = patched
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
pdf = Path(r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf')
payload = pdf.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
src = SourceVisibilityProducer(producer_method="whatif", producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("3",))
t=time.time()
wo = compose_live_wall_opening_authority(source_visibility_producer=src, revision_id=pub.revision.revision_id, page_ids=("3",))
sem = wo.semantic_enumeration_result
print('mode',sys.argv[1],'elapsed',round(time.time()-t,1))
print('semantic', sem.status.value, list(sem.reason_codes)[:6], 'reps', len(sem.record.representative_observation_ids) if sem.record else None)
print('bindings', collections.Counter((b.status.value, tuple(b.reason_codes)[:1]) for b in wo.opening_bindings))
pv = compose_live_physical_opening_voids(source_visibility_producer=src, wall_opening_composition=wo)
print('canonical', len(pv.canonical_openings), collections.Counter(o.viewport_id for o in pv.canonical_openings))
json.dump([dict(id=o.canonical_opening_id, vp=o.viewport_id, pat=o.structural_pattern, geom=[round(x) for x in (o.source_geometries[0] if o.source_geometries else ())]) for o in pv.canonical_openings], open(sys.argv[2],'w'))
