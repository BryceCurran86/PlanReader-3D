import sys, os, json, time, tempfile, hashlib
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fitz
import pb_planreader_3d_app as app_mod
import pb_auto_geometry_v1219 as auto
import pb_autopilot_v1223 as autopilot
pdf = Path(sys.argv[1]); out = sys.argv[2]
res = {}
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    with patch.object(app_mod, "DB_PATH", Path(tmp)/"t.db"):
        setattr(app_mod, "_pb_local_db_initialized_v1215", False)
        app_mod.init_local_db()
        app = SimpleNamespace(lquery=app_mod.lquery, lexecute=app_mod.lexecute, local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp, workspace_setting=app_mod.workspace_setting,
            set_workspace_setting=app_mod.set_workspace_setting, auto_detect_scale=app_mod.auto_detect_scale, fitz=fitz)
        app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'W','x','x')")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,1,?,?,?,0)", (pdf.name, str(pdf), sha))
        t=time.time(); n,msg = app_mod.index_document_pages(1); res['index']=(n,msg,round(time.time()-t,1)); print('indexed',res['index'],flush=True)
        t=time.time(); tri = autopilot.triage_workspace(app,1); res['triage']={k:tri[k] for k in('kept','discarded')}; res['triage_pages']=tri['pages']; print('triage',res['triage'],round(time.time()-t,1),flush=True)
        t=time.time(); r = app_mod.process_document(1); res['render']=(r, round(time.time()-t,1)); print('rendered',res['render'],flush=True)
        t=time.time(); report = auto.analyse_workspace(app,1); res['analyse_s']=round(time.time()-t,1); print('analysed',res['analyse_s'],flush=True)
        rows = [dict(r) for r in app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")]
        res['takeoff_rows']=[{k:r.get(k) for k in ('element','quantity','unit','source_page','quantity_status','origin','row_role','section','location','confidence','notes') } for r in rows]
        for r in res['takeoff_rows']: r['notes']=(r['notes'] or '')[:200]
        res['report']={k:report[k] for k in report if k in ('selected_pages','auto_takeoff_rows','coverage_lifecycle','semantic_conflicts','footprint')}
json.dump(res, open(out,'w'), indent=1, default=str)
print('wrote',len(res['takeoff_rows']),'rows',flush=True)
