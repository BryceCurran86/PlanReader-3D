"""A workspace written by an early PlanReader keeps working: tolerant reads, strict new writes.

The composed production app (the Docker entry point) starts on a database
whose take-off table has the early, minimal shape: no finish, status,
source, inclusion, confidence, notes, role, commercial-authority or
provenance columns, legacy units (``m2``, ``sqm``, ``lin m``) and a NULL
quantity. Startup must migrate it in place. The workspace is then
reprocessed, every read path the estimator uses runs, the schedule is saved
unchanged, and automatic geometry re-runs:

- no read path fails on the legacy rows;
- the legacy rows survive every stage, with units normalised;
- automatic rows are still published and replaced (not duplicated).
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

_COMPOSED_RUN = r'''
import json, os, sys, traceback
from pathlib import Path
sys.path.insert(0, REPO)
os.chdir(REPO)
import fitz
import pb_planreader_3d_app as core

# The database an early release left behind: its take-off table and rows.
core.init_local_db()
ws = core.create_standalone_workspace("PB-LEGACY", "Legacy workspace", "b", "")
conn = core.local_connect()
conn.execute("PRAGMA foreign_keys=OFF")
conn.execute("DROP TABLE takeoff_rows")
conn.execute("""CREATE TABLE takeoff_rows(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER NOT NULL,
    section TEXT, element TEXT, location TEXT, substrate TEXT, quantity REAL, unit TEXT, created_at TEXT, updated_at TEXT)""")
legacy = [("Internal", "Walls", "Kitchen", "Plasterboard", 18.0, "m2"),
          ("Internal", "Ceilings", "Kitchen", "Plasterboard", None, "sqm"),
          ("Internal", "Skirting", "Kitchen", "Timber", 12.0, "lin m"),
          ("Internal", "Floor area", "Level 1", "Other", 85.0, "sq m")]
conn.executemany("INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'2025-01-01','2025-01-01')",
                 [(ws, *row) for row in legacy])
conn.commit()
conn.close()

# Production startup on that database; the first init migrates it in place.
import pb_planreader_v133_app as entry
import pb_no_ai_takeoff_v1216 as noai
from pb_commercial_export_preflight_v163 import derive_export_preflight
from pb_production_3d_adapter import planreader_workspace_to_canonical
app = entry.app
app.init_local_db()

pdf = Path(os.environ["PLANREADER_DATA_DIR"]) / "plans.pdf"
doc = fitz.open()
mm = 72 / 25.4
ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
page = doc.new_page(width=842, height=595)
for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)), ((ox + w, oy + h), (ox, oy + h)),
             ((ox, oy + h), (ox, oy)), ((ox + split, oy), (ox + split, oy + h))):
    page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
page.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
page.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
page.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
doc.save(pdf)
doc.close()

def legacy_rows():
    # Identified by content: the early rows carry no source reference.
    return [dict(r) for r in app.lquery(
        """SELECT section,element,location,substrate,quantity,unit FROM takeoff_rows
           WHERE workspace_id=? AND COALESCE(source_reference,'')='' ORDER BY element""", (ws,))]

def auto_rows():
    return app.lquery("SELECT COUNT(*) AS n FROM takeoff_rows WHERE workspace_id=? AND source_reference LIKE 'PB Auto Geometry%'", (ws,))[0]["n"]

stages = {"migrated": legacy_rows()}
doc_id = app.lexecute("INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                      (ws, pdf.name, "application/pdf", str(pdf), 0, "", app.now_stamp()))
app.index_document_pages(doc_id)
app.process_document(doc_id, force=False)
app.run_planreader_autopilot(ws, force=True)
stages["reprocessed"] = legacy_rows()
auto_after_reprocess = auto_rows()

reads = {}
for name, read in {
    "review dataframe": lambda: len(app.dataframe_for_takeoff(ws)),
    "per-level summary": lambda: len(app.per_level_summary(ws)),
    "take-off QA issues": lambda: len(app.takeoff_accuracy_issues(ws)),
    "mapper targets": lambda: len(app.takeoff_rows_for_mapper(ws)),
    "commercial export preflight": lambda: type(derive_export_preflight(app, ws)).__name__,
    "canonical 3D adapter": lambda: len(planreader_workspace_to_canonical(app, ws).project.buildings),
}.items():
    try:
        reads[name] = {"ok": True, "value": read()}
    except Exception:
        reads[name] = {"ok": False, "error": traceback.format_exc()[-1200:]}

editor_cols = ["id"] + list(app.TAKEOFF_COLUMNS) + ["row_role"]
frame = app.ldf("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (ws,)).reindex(columns=editor_cols)
noai.save_schedule_batched(app, ws, frame.to_dict("records"))
stages["schedule saved"] = legacy_rows()
app.run_auto_geometry(ws)
stages["automatic re-run"] = legacy_rows()
print("RESULT=" + json.dumps({"stages": stages, "reads": reads, "auto_after_reprocess": auto_after_reprocess,
                              "auto_after_rerun": auto_rows()}, default=str))
'''


class LegacyWorkspaceTests(unittest.TestCase):
    def test_early_workspace_survives_migration_reprocess_reads_save_and_rerun(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            script = Path(tmp) / "legacy.py"
            script.write_text(f"REPO = {str(REPO)!r}\n" + textwrap.dedent(_COMPOSED_RUN), encoding="utf-8")
            env = dict(os.environ, PLANREADER_DATA_DIR=str(Path(tmp) / "data"), PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, str(script)], cwd=str(REPO), env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", timeout=900)
        payload = [line for line in result.stdout.splitlines() if line.startswith("RESULT=")]
        self.assertTrue(payload, f"exit {result.returncode}\nSTDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}")
        outcome = json.loads(payload[0][len("RESULT="):])

        for name, read in outcome["reads"].items():
            with self.subTest(read=name):
                self.assertTrue(read["ok"], read.get("error"))

        expected = [
            {"section": "Internal", "element": "Ceilings", "location": "Kitchen", "substrate": "Plasterboard", "quantity": None, "unit": "m²"},
            {"section": "Internal", "element": "Floor area", "location": "Level 1", "substrate": "Other", "quantity": 85.0, "unit": "m²"},
            {"section": "Internal", "element": "Skirting", "location": "Kitchen", "substrate": "Timber", "quantity": 12.0, "unit": "lm"},
            {"section": "Internal", "element": "Walls", "location": "Kitchen", "substrate": "Plasterboard", "quantity": 18.0, "unit": "m²"},
        ]
        for stage, rows in outcome["stages"].items():
            with self.subTest(stage=stage):
                if stage in ("schedule saved", "automatic re-run"):
                    # The schedule save stores an empty quantity as 0 for every row
                    # (pb_no_ai_takeoff_v1216._takeoff_values), not only legacy ones.
                    expected[0] = dict(expected[0], quantity=0.0)
                self.assertEqual(rows, expected, "legacy rows must survive, units normalised")

        self.assertGreater(outcome["auto_after_reprocess"], 0, "automatic rows must still be published")
        self.assertEqual(outcome["auto_after_rerun"], outcome["auto_after_reprocess"], "and replaced, not duplicated")


if __name__ == "__main__":
    unittest.main()
