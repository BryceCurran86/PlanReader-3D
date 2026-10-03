import sys, json, time, hashlib, threading, os
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
import ctypes
from ctypes import wintypes
class PMC(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
_k=ctypes.WinDLL('kernel32',use_last_error=True); _p=ctypes.WinDLL('psapi',use_last_error=True)
_k.GetCurrentProcess.restype=wintypes.HANDLE
_p.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]; _p.GetProcessMemoryInfo.restype=wintypes.BOOL
def peak_ws():
    c=PMC(); c.cb=ctypes.sizeof(c)
    ok=_p.GetProcessMemoryInfo(_k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PeakWorkingSetSize if ok else -1
pdf = sys.argv[1]; out = sys.argv[2]
import pb_planreader_pdf_extractor as m
ex = m.GenericPlanReaderExtractor()
t = time.time()
preds = ex.extract_from_pdf(pdf)
el = time.time() - t
print('elapsed', round(el,1), 'peak_rss_mb', round(peak_ws()/1e6), 'preds', len(preds), flush=True)
def jd(o):
    try: return json.loads(json.dumps(o, default=lambda x: getattr(x,'to_dict',lambda: str(x))()))
    except Exception as e: return {'unserializable': str(e)}
res = dict(
  source_sha256=hashlib.sha256(open(pdf,'rb').read()).hexdigest(), elapsed_s=el, peak_rss_mb=peak_ws()/1e6,
  extraction_status=jd(ex.extraction_status),
  predictions=[dict(tag=p.tag, trade=p.trade_type, qty=p.quantity, unit=p.unit, page=p.source_page, conf=p.confidence, desc=p.description, meta_keys=sorted((p.metadata or {}).keys()), deriv=(p.metadata or {}).get('derivation')) for p in preds],
  source_opening_callouts_live=jd(ex.source_opening_callouts_live),
  canonical_openings_live=jd(ex.canonical_openings_live),
  canonical_walls_live={k:(v if k!='walls' else len(v)) for k,v in jd(ex.canonical_walls_live).items()},
  canonical_rooms_live={k:(v if k!='rooms' else len(v)) for k,v in jd(ex.canonical_rooms_live).items()},
  canonical_floors_live=jd(ex.canonical_floors_live),
  canonical_ceilings_live=jd(ex.canonical_ceilings_live),
  canonical_slabs_live=jd(ex.canonical_slabs_live),
  canonical_roofs_live=jd(ex.canonical_roofs_live),
  canonical_building_live=jd(ex.canonical_building_live),
  physical_net_wall_live=jd(ex.physical_net_wall_live),
  coverage_registry_summaries_live=jd(ex.coverage_registry_summaries_live),
  coverage_family_gaps_live=jd(ex.coverage_family_gaps_live),
  performance_trace=jd(ex.performance_trace),
)
json.dump(res, open(out,'w'), indent=1, default=str)
print('wrote', out, flush=True)
