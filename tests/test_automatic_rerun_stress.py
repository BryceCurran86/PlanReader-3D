"""Ten automatic re-runs in the composed production app change nothing but publication stamps.

upload -> index -> render -> autopilot, then the estimator adds a manual
take-off row, a 3D surface edit and an opening, then automatic geometry
re-runs ten times with unchanged inputs. Runs 1, 2, 3 and 10 are compared:

- automatic rows: same count, keys, quantities and source references, no duplicates
- manual row: untouched, timestamps included
- 3D model: same masses (ids and geometry), opening and surface metadata
- no cumulative drift: page calibration, workspace setting keys
- timestamps: only each generator's publication stamp moves, never backwards
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKED_RUNS = (1, 2, 3, 10)

_COMPOSED_RUN = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, REPO)
os.chdir(REPO)
import fitz
import pb_planreader_v133_app as entry
import pb_3d_surface_editor_v1212 as surface
app = entry.app
app.init_local_db()

pdf = Path(os.environ["PLANREADER_DATA_DIR"]) / "plans.pdf"
doc = fitz.open()
mm = 72 / 25.4
ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
plan = doc.new_page(width=842, height=595)
for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)), ((ox + w, oy + h), (ox, oy + h)),
             ((ox, oy + h), (ox, oy)), ((ox + split, oy), (ox + split, oy + h))):
    plan.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
plan.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
plan.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
plan.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
elevation = doc.new_page(width=842, height=595)
eh = 27 * mm
for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + eh)), ((ox + w, oy + eh), (ox, oy + eh)), ((ox, oy + eh), (ox, oy))):
    elevation.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
elevation.insert_text(fitz.Point(ox, oy + eh + 40), "NORTH ELEVATION   SCALE 1:100", fontsize=9)
elevation.insert_text(fitz.Point(ox, oy + eh + 60), "LINEABOARD CLADDING 42.5 m2", fontsize=9)
doc.save(pdf)
doc.close()

ws = app.create_standalone_workspace("PB-STRESS", "Rerun stress", "b", "")
doc_id = app.lexecute("INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                      (ws, pdf.name, "application/pdf", str(pdf), 0, "", app.now_stamp()))
app.index_document_pages(doc_id)
app.process_document(doc_id, force=False)
app.run_planreader_autopilot(ws, force=True)

# Estimator work.
manual_id = app.lexecute("""INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,finish_system,quantity,unit,
        quantity_status,source_page,source_reference,inclusion_status,coats,coverage_m2_per_litre,productivity_m2_per_hour,
        rate_per_unit,confidence,notes,row_role,created_at,updated_at)
    VALUES(?,'Internal','Walls','Kitchen','Plasterboard','Low sheen',18.0,'m²','Measured','A101','Estimator manual entry',
        'INCLUSION',2,12,8,4.5,'Measured','site measure','','2026-09-01T08:00:00','2026-09-01T08:00:00')""", (ws,))
mass_id = app.lquery("SELECT id FROM model_masses WHERE workspace_id=? ORDER BY id", (ws,))[0]["id"]
overrides = surface._load_overrides(app, ws)
overrides[f"mass:{mass_id}:front"] = {"substrate": "EC1", "status": "Complete", "progress_pct": 60.0, "notes": "Estimator: first coat"}
surface._save_overrides(app, ws, overrides)
app.lexecute("INSERT INTO model_openings(workspace_id,mass_id,label,opening_type,face,offset_x,offset_z,width,height,count,notes,source_reference,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (ws, mass_id, "Door D01", "Door", "Front", 1.0, 0.0, 0.9, 2.1, 1, "", "Site measure", app.now_stamp()))

def snapshot():
    rows = [dict(r) for r in app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY source_reference,element,location", (ws,))]
    return {
        "auto": [{k: r[k] for k in ("section", "element", "location", "substrate", "quantity", "unit", "quantity_status",
                                    "source_reference", "inclusion_status", "row_role", "created_at", "updated_at")}
                 for r in rows if (r["source_reference"] or "").startswith("PB ")],
        "manual": [r for r in rows if r["id"] == manual_id],
        "masses": [dict(r) for r in app.lquery("SELECT id,label,x,y,z,width,depth,height,source_reference,created_at FROM model_masses WHERE workspace_id=? ORDER BY id", (ws,))],
        "openings": [dict(r) for r in app.lquery("SELECT id,mass_id,label FROM model_openings WHERE workspace_id=? ORDER BY id", (ws,))],
        "surfaces": json.loads(app.workspace_setting(ws, "3d_surface_editor_v1212", "{}")).get("surfaces"),
        "pages": [dict(r) for r in app.lquery("SELECT id,px_per_m,scale_text,page_type,selected FROM pages WHERE workspace_id=? ORDER BY id", (ws,))],
        "settings": sorted(r["key"] for r in app.lquery("SELECT key FROM workspace_settings WHERE workspace_id=?", (ws,))),
    }

runs = {}
for run in range(1, 11):
    app.run_auto_geometry(ws)
    if run in (1, 2, 3, 10):
        runs[run] = snapshot()
print("RESULT=" + json.dumps(runs, default=str))
'''


def _without_stamps(auto_rows):
    return [{k: v for k, v in row.items() if k not in ("created_at", "updated_at")} for row in auto_rows]


class AutomaticRerunStressTests(unittest.TestCase):
    def test_ten_reruns_change_nothing_but_publication_stamps(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            script = Path(tmp) / "rerun_stress.py"
            script.write_text(f"REPO = {str(REPO)!r}\n" + textwrap.dedent(_COMPOSED_RUN), encoding="utf-8")
            env = dict(os.environ, PLANREADER_DATA_DIR=str(Path(tmp) / "data"), PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, str(script)], cwd=str(REPO), env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", timeout=1200)
        payload = [line for line in result.stdout.splitlines() if line.startswith("RESULT=")]
        self.assertTrue(payload, f"exit {result.returncode}\nSTDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}")
        runs = {int(k): v for k, v in json.loads(payload[0][len("RESULT="):]).items()}
        first = runs[1]

        self.assertTrue(first["auto"], "the document must publish automatic rows")
        keys = [(r["source_reference"], r["element"], r["location"]) for r in first["auto"]]
        self.assertEqual(len(keys), len(set(keys)), "no duplicate automatic rows")
        self.assertEqual(len(first["masses"]), 1)
        self.assertEqual(len(first["manual"]), 1)
        self.assertEqual(first["manual"][0]["created_at"], "2026-09-01T08:00:00")

        previous_stamps = {}
        for run in CHECKED_RUNS:
            with self.subTest(run=run):
                state = runs[run]
                self.assertEqual(_without_stamps(state["auto"]), _without_stamps(first["auto"]))
                self.assertEqual(state["manual"], first["manual"], "the estimator's row is never rewritten")
                self.assertEqual(state["masses"], first["masses"], "same mass ids, geometry and created_at")
                self.assertEqual(state["openings"], first["openings"])
                self.assertEqual(state["surfaces"], first["surfaces"])
                self.assertEqual(state["pages"], first["pages"], "no calibration drift")
                self.assertEqual(state["settings"], first["settings"], "no accumulating settings")
                # Each generator publishes its batch under one stamp that never goes backwards.
                families = {}
                for row in state["auto"]:
                    families.setdefault(row["source_reference"].split(" · ")[0], set()).add((row["created_at"], row["updated_at"]))
                for family, stamps in families.items():
                    self.assertEqual(len(stamps), 1, f"{family}: one publication stamp per run")
                    created, updated = stamps.pop()
                    self.assertEqual(created, updated)
                    self.assertGreaterEqual(created, previous_stamps.get(family, ""), f"{family}: stamps never go backwards")
                    previous_stamps[family] = created


if __name__ == "__main__":
    unittest.main()
