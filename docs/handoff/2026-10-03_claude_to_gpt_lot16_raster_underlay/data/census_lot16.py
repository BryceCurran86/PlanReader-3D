import sys, json, hashlib, time, collections
sys.path.insert(0, r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication')
from pathlib import Path
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
pdf = Path(r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf')
pages = [int(x) for x in sys.argv[1].split(',')]
payload = pdf.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
t=time.time(); print("start",flush=True)
src = SourceVisibilityProducer(producer_method="census", producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
    source_locator="memory://x.pdf", page_ids=tuple(str(p) for p in pages))
print("ingested",round(time.time()-t,1),flush=True)
wo = compose_live_wall_opening_authority(source_visibility_producer=src, revision_id=pub.revision.revision_id, page_ids=tuple(str(p) for p in pages))
print('wall_opening', wo.status.value, list(wo.reason_codes)[:12], round(time.time()-t,1),'s')
sem = wo.semantic_enumeration_result
print('semantic', sem.status.value, list(sem.reason_codes)[:8], 'record' , sem.record is not None)
if sem.record is not None:
    print(' representative_obs', len(sem.record.representative_observation_ids), 'physical_ids', len(sem.record.physical_opening_record_ids))
print('wall scopes', [(w.page_id,w.status.value,w.scope_complete,len(w.wall_candidate_ids)) for w in wo.wall_scopes])
print('opening bindings', collections.Counter((b.status.value, tuple(b.reason_codes)[:1]) for b in wo.opening_bindings))
print('host frames', collections.Counter((b.status.value, tuple(b.reason_codes)[:1]) for b in wo.host_frames))
pv = compose_live_physical_opening_voids(source_visibility_producer=src, wall_opening_composition=wo)
print('void comp', pv.status.value, list(pv.reason_codes)[:10], 'canon', len(pv.canonical_openings), 'traces', len(pv.traces))
for name in ['width','schedule_binding','height','vertical','scale','void']:
    c = collections.Counter((getattr(tr,name+'_status').value, (getattr(tr,name+'_reason_codes')[:1] or ('',))[0]) for tr in pv.traces)
    print(' ',name, dict(c))
out=[]
for o in pv.canonical_openings:
    out.append(dict(id=o.canonical_opening_id[:12], page=o.page_id, vp=o.viewport_id, cls=o.semantic_class, pat=o.structural_pattern, kind=o.opening_kind, mark=o.type_mark, host=bool(o.host_wall_id), w=o.width_m, h=o.height_m, a=o.area_m2, geomc=o.geometry_complete, bbox=[round(x) for x in (o.source_geometries[0] if o.source_geometries else ())]))
json.dump(out, open(sys.argv[2],'w'), indent=1)
print('wrote', len(out))
