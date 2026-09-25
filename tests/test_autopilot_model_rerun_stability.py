"""Autopilot 3D model re-runs keep mass identity (pb_autopilot_v1223.build_autopilot_model).

Estimator openings, 3D surface edits and editable-3D corrections are keyed by
model_masses.id (AUTOINCREMENT, never reused). Re-running automatic geometry
must therefore update the autopilot masses in place: re-inserting them gave
every run new ids, deleted the estimator's openings, detached their surface
edits and accumulated orphaned automatic face metadata.
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
from types import SimpleNamespace
from unittest.mock import patch

import pb_auto_geometry_v1219 as auto
import pb_autopilot_accuracy_guard_v1223 as accuracy
import pb_autopilot_v1223 as autopilot
import pb_planreader_3d_app as app_mod

REPO = Path(__file__).resolve().parents[1]
SURFACES = "3d_surface_editor_v1212"
ESTIMATOR_SURFACE = {"substrate": "EC1", "status": "Complete", "progress_pct": 60.0,
                     "notes": "Estimator: first coat complete"}


class _Workspace:
    """Real app schema on a temporary database."""

    def __init__(self):
        self.app = SimpleNamespace(lquery=app_mod.lquery, lexecute=app_mod.lexecute,
                                   local_connect=app_mod.local_connect, now_stamp=app_mod.now_stamp)
        app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'Autopilot','x','x')")
        app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,1,'p.pdf','p.pdf','sha',2)")

    @staticmethod
    def select_floor_plans(*labels):
        app_mod.lexecute("DELETE FROM pages")
        for page_id, label in enumerate(labels, 1):
            app_mod.lexecute(
                """INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,extracted_text,selected,px_per_m)
                   VALUES(?,1,1,?,?,'Floor Plan',?,1,100.0)""",
                (page_id, page_id, label, label),
            )

    def build(self, width=20.0):
        report = {"footprint": {"width_m": width, "depth_m": 12.0, "page_id": 1},
                  "facades": [{"page_id": 9, "face": "front", "height_m": 6.0}]}
        # The production entry: the accuracy guard wraps the autopilot builder.
        return accuracy.build_autopilot_model(self.app, 1, report, {"occurrences": []}, [])

    @staticmethod
    def masses():
        rows = app_mod.lquery("SELECT id,level_name,width,source_reference FROM model_masses WHERE workspace_id=1 ORDER BY id")
        return {row["level_name"]: row for row in rows if row["source_reference"].startswith(autopilot.MODEL_SOURCE_PREFIX)}

    @staticmethod
    def surfaces():
        return json.loads(app_mod.workspace_setting(1, SURFACES, "{}"))["surfaces"]

    def edit_surface(self, surface_id, value):
        surfaces = self.surfaces()
        surfaces[surface_id] = dict(value)
        app_mod.set_workspace_setting(1, SURFACES, json.dumps({"surfaces": surfaces}))

    @staticmethod
    def add_opening(mass_id):
        # The 3D Building Model page's "Add opening" statement.
        return app_mod.lexecute(
            """INSERT INTO model_openings(workspace_id,mass_id,label,opening_type,face,offset_x,offset_z,width,height,count,notes,source_reference,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (1, mass_id, "Door D01", "Door", "Front", 1.0, 0.0, 0.9, 2.1, 1, "Estimator opening", "Site measure", "x"),
        )

    def add_legacy_envelope(self):
        """What pb_auto_geometry_v1219._refresh_auto_model publishes before autopilot runs."""
        mass_id = app_mod.lexecute(
            """INSERT INTO model_masses(workspace_id,label,level_name,x,y,z,width,depth,height,finish,source_reference,confidence,notes,created_at)
               VALUES(1,'Automatic building envelope','Ground',0,0,0,20,12,6,'External envelope',?,'Derived','','x')""",
            (f"{auto.MODEL_SOURCE_PREFIX} · floor:1",),
        )
        self.edit_surface(f"mass:{mass_id}:front", {"substrate": "OTHER", "status": "Provisional", "progress_pct": 0,
                                                     "notes": f"[AUTO v{auto.VERSION}] front: substrate to confirm"})
        return mass_id


class _TempDatabase:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        return _Workspace()

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()


class AutopilotModelRerunTests(unittest.TestCase):
    def test_rerun_updates_masses_in_place_and_keeps_estimator_work(self):
        with _TempDatabase() as ws:
            ws.select_floor_plans("GROUND FLOOR PLAN", "LEVEL 01 FLOOR PLAN")
            ws.build()
            first = ws.masses()
            ground, level_1 = first["Ground"]["id"], first["Level 1"]["id"]
            opening = ws.add_opening(ground)
            ws.edit_surface(f"mass:{level_1}:front", ESTIMATOR_SURFACE)
            envelope = ws.add_legacy_envelope()

            result = ws.build(width=22.0)
            second, surfaces = ws.masses(), ws.surfaces()
            openings = app_mod.lquery("SELECT id,mass_id FROM model_openings WHERE workspace_id=1")
            envelopes = app_mod.lquery("SELECT id FROM model_masses WHERE source_reference LIKE ?", (auto.MODEL_SOURCE_PREFIX + "%",))

            ws.add_legacy_envelope()
            ws.build(width=22.0)
            third, surfaces_third = ws.masses(), ws.surfaces()

        self.assertEqual(result["mass_ids"], [ground, level_1])
        self.assertEqual({k: v["id"] for k, v in second.items()}, {"Ground": ground, "Level 1": level_1})
        self.assertEqual({v["width"] for v in second.values()}, {22.0}, "re-run must refresh the geometry in place")
        self.assertEqual(openings, [{"id": opening, "mass_id": ground}])
        self.assertEqual(surfaces[f"mass:{level_1}:front"], ESTIMATOR_SURFACE)
        self.assertEqual(envelopes, [], "the legacy envelope is still replaced")
        self.assertNotIn(f"mass:{envelope}:front", surfaces)
        self.assertEqual(third, second)
        self.assertEqual(set(surfaces_third), set(surfaces), "re-runs must not accumulate face metadata")

    def test_vanished_level_is_removed_but_estimator_surface_edits_are_kept(self):
        with _TempDatabase() as ws:
            ws.select_floor_plans("GROUND FLOOR PLAN", "LEVEL 01 FLOOR PLAN")
            ws.build()
            before = ws.masses()
            level_1 = before["Level 1"]["id"]
            ws.edit_surface(f"mass:{level_1}:front", ESTIMATOR_SURFACE)
            automatic = {k for k, v in ws.surfaces().items()
                         if k.startswith(f"mass:{level_1}:") and v["notes"].startswith(autopilot.AUTO_NOTE_PREFIX)}
            self.assertEqual(automatic, {f"mass:{level_1}:{face}" for face in ("rear", "left", "right")})

            ws.select_floor_plans("GROUND FLOOR PLAN")
            ws.build()
            after, surfaces = ws.masses(), ws.surfaces()

        self.assertEqual(set(after), {"Ground"})
        self.assertEqual(after["Ground"]["id"], before["Ground"]["id"])
        level_1_keys = {k for k in surfaces if k.startswith(f"mass:{level_1}:")}
        self.assertEqual(level_1_keys, {f"mass:{level_1}:front"}, "only the estimator's edit survives its mass")
        self.assertEqual(surfaces[f"mass:{level_1}:front"], ESTIMATOR_SURFACE)

    def test_duplicate_autopilot_masses_collapse_to_the_first(self):
        with _TempDatabase() as ws:
            ws.select_floor_plans("GROUND FLOOR PLAN")
            ws.build()
            keep = ws.masses()["Ground"]["id"]
            app_mod.lexecute(
                """INSERT INTO model_masses(workspace_id,label,level_name,source_reference,confidence,created_at)
                   VALUES(1,'Automatic Ground','Ground',?,'Derived','x')""",
                (f"{autopilot.MODEL_SOURCE_PREFIX}Ground",),
            )
            ws.build()
            rows = app_mod.lquery("SELECT id FROM model_masses WHERE workspace_id=1")
        self.assertEqual(rows, [{"id": keep}])

    def test_orphaned_auto_surface_matches_only_automatic_metadata_of_missing_masses(self):
        auto_note = {"notes": f"[AUTO v{auto.VERSION}] front"}
        autopilot_note = {"notes": f"{autopilot.AUTO_NOTE_PREFIX} front"}
        live = {1}
        self.assertTrue(autopilot._orphaned_auto_surface("mass:5:front", auto_note, live))
        self.assertTrue(autopilot._orphaned_auto_surface("mass:5:front", autopilot_note, live))
        for surface_id, override in (
            ("mass:1:front", auto_note),             # mass still exists
            ("mass:5:front", ESTIMATOR_SURFACE),     # estimator-owned
            ("mass:5:front", {}),
            ("mass:5:front", "[AUTO v1.2.19]"),      # malformed override
            ("zone:5:front", auto_note),             # not a mass surface
            ("mass:x:front", auto_note),
            ("mass:5", auto_note),
        ):
            with self.subTest(surface_id=surface_id, override=override):
                self.assertFalse(autopilot._orphaned_auto_surface(surface_id, override, live))


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
ox, oy, w, h = 80, 80, 100 * mm, 60 * mm
for page_no, (height, title, note) in enumerate(((h, "GROUND FLOOR PLAN   SCALE 1:100", "UNIT 1   TOTAL AREA 85.4 m2"),
                                                  (27 * mm, "NORTH ELEVATION   SCALE 1:100", "LINEABOARD CLADDING 42.5 m2"))):
    page = doc.new_page(width=842, height=595)
    for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + height)),
                 ((ox + w, oy + height), (ox, oy + height)), ((ox, oy + height), (ox, oy))):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(ox, oy + height + 40), title, fontsize=9)
    page.insert_text(fitz.Point(ox, oy + height + 60), note, fontsize=9)
doc.save(pdf)
doc.close()

ws = app.create_standalone_workspace("PB-RERUN", "Autopilot rerun", "b", "")
doc_id = app.lexecute("INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                      (ws, pdf.name, "application/pdf", str(pdf), 0, "", app.now_stamp()))
app.index_document_pages(doc_id)
app.process_document(doc_id, force=False)
app.run_planreader_autopilot(ws, force=True)

def snapshot():
    masses = app.lquery("SELECT id,source_reference FROM model_masses WHERE workspace_id=? ORDER BY id", (ws,))
    surfaces = json.loads(app.workspace_setting(ws, "3d_surface_editor_v1212", "{}"))["surfaces"]
    openings = app.lquery("SELECT id,mass_id,label FROM model_openings WHERE workspace_id=? ORDER BY id", (ws,))
    return {"masses": masses, "surfaces": surfaces, "openings": openings}

stages = [snapshot()]
mass_id = stages[0]["masses"][0]["id"]
overrides = surface._load_overrides(app, ws)
overrides[f"mass:{mass_id}:front"] = {"substrate": "EC1", "status": "Complete", "progress_pct": 60.0, "notes": "Estimator: first coat"}
surface._save_overrides(app, ws, overrides)
app.lexecute("INSERT INTO model_openings(workspace_id,mass_id,label,opening_type,face,offset_x,offset_z,width,height,count,notes,source_reference,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (ws, mass_id, "Door D01", "Door", "Front", 1.0, 0.0, 0.9, 2.1, 1, "", "Site measure", app.now_stamp()))
stages.append(snapshot())
for _ in range(2):
    app.run_auto_geometry(ws)
    stages.append(snapshot())
print("RESULT=" + json.dumps(stages))
'''


class ComposedProductionRerunTests(unittest.TestCase):
    """upload -> index -> render -> autopilot -> estimator 3D edits -> re-run x2, in the Docker entry app."""

    def test_rerunning_automatic_geometry_keeps_the_3d_model_and_estimator_work(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            script = Path(tmp) / "composed_rerun.py"
            script.write_text(f"REPO = {str(REPO)!r}\n" + textwrap.dedent(_COMPOSED_RUN), encoding="utf-8")
            env = dict(os.environ, PLANREADER_DATA_DIR=str(Path(tmp) / "data"), PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, str(script)], cwd=str(REPO), env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", timeout=900)
        payload = [line for line in result.stdout.splitlines() if line.startswith("RESULT=")]
        self.assertTrue(payload, f"exit {result.returncode}\nSTDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}")
        initial, edited, *reruns = json.loads(payload[0][len("RESULT="):])

        self.assertEqual(len(initial["masses"]), 1)
        mass = initial["masses"][0]
        self.assertTrue(mass["source_reference"].startswith(autopilot.MODEL_SOURCE_PREFIX))
        estimator_key = f"mass:{mass['id']}:front"
        for stage in reruns:
            self.assertEqual(stage["masses"], initial["masses"], "re-runs must keep the autopilot mass identity")
            self.assertEqual(stage["openings"], edited["openings"], "the estimator's opening must survive")
            self.assertEqual(stage["surfaces"][estimator_key], edited["surfaces"][estimator_key])
            self.assertEqual(set(stage["surfaces"]), set(edited["surfaces"]), "no orphaned face metadata may accumulate")
            live = {m["id"] for m in stage["masses"]}
            self.assertTrue(all(int(key.split(":")[1]) in live for key in stage["surfaces"]))


if __name__ == "__main__":
    unittest.main()
