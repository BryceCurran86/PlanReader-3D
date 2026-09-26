"""Processing several documents analyses the workspace once, with the same result.

Every processed document triggered a whole-workspace analysis
(pb_auto_geometry_v1219 wraps process_document), so "Process selected
documents" re-analysed every earlier document again for each later one: with
3 real documents (145 pages) analysis ran 3x for 27.2 s of a 37.8 s batch.
Inside document_batch each processed document records its workspace, and the
batch analyses each workspace once and then syncs the drawing register, as the
last per-document analysis was followed by a register sync.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import pb_auto_geometry_v1219 as auto
import pb_no_ai_takeoff_v1216 as noai
import pb_planreader_3d_app as app_mod

REPO = Path(__file__).resolve().parents[1]
WORKSPACE_OF = {1: 10, 2: 10, 3: 20, 99: 10}


class _App:
    """Records processing, analysis and register syncs in order."""

    def __init__(self):
        self.events = []

    def index_document_pages(self, document_id, *args, **kwargs):
        return 0, "Indexed"

    def process_document(self, document_id, force=False, page_ids=None, progress_cb=None):
        self.events.append(("process", document_id))
        if document_id == 99:
            raise RuntimeError("render failed")
        return 1, "Processed"

    def lquery(self, sql, params=()):
        if "FROM documents" in sql:
            workspace_id = WORKSPACE_OF.get(int(params[0]))
            return [{"workspace_id": workspace_id}] if workspace_id else []
        return []

    def sync_drawing_register_v1225(self, workspace_id):
        self.events.append(("sync", workspace_id))


class DocumentBatchTests(unittest.TestCase):
    def setUp(self):
        self._saved = (auto.analyse_workspace, noai.no_ai_takeoff_panel,
                       noai.__dict__.get("_pb_auto_geometry_panel_v1219", None))
        self.app = _App()
        auto.apply(self.app)
        self.failing = set()

        def analyse(app_obj, workspace_id):
            self.app.events.append(("analyse", workspace_id))
            if workspace_id in self.failing:
                raise RuntimeError("heuristic failed")
            return {}

        auto.analyse_workspace = analyse

    def tearDown(self):
        auto.analyse_workspace, noai.no_ai_takeoff_panel, flag = self._saved
        if flag is None:
            noai.__dict__.pop("_pb_auto_geometry_panel_v1219", None)
        else:
            noai._pb_auto_geometry_panel_v1219 = flag

    def test_without_a_batch_each_document_is_analysed_as_before(self):
        self.app.process_document(1)
        self.app.process_document(2)

        self.assertEqual(self.app.events, [("process", 1), ("analyse", 10), ("process", 2), ("analyse", 10)])

    def test_a_batch_analyses_each_workspace_once_then_syncs_its_register(self):
        with self.app.document_batch():
            for document_id in (1, 2, 3):
                self.app.process_document(document_id)
            self.assertEqual([e for e in self.app.events if e[0] != "process"], [], "nothing is analysed mid-batch")

        self.assertEqual(self.app.events[3:], [("analyse", 10), ("sync", 10), ("analyse", 20), ("sync", 20)])

    def test_a_document_that_fails_does_not_stop_the_others_being_analysed(self):
        with self.app.document_batch():
            for document_id in (99, 3):
                try:
                    self.app.process_document(document_id)
                except RuntimeError:
                    pass  # the documents page records the error and carries on

        self.assertEqual(self.app.events, [("process", 99), ("process", 3), ("analyse", 20), ("sync", 20)])

    def test_processed_documents_are_analysed_even_when_the_batch_is_interrupted(self):
        with self.assertRaises(KeyError):
            with self.app.document_batch():
                self.app.process_document(1)
                raise KeyError("interrupted")

        self.assertEqual(self.app.events, [("process", 1), ("analyse", 10), ("sync", 10)])

    def test_a_failed_analysis_still_syncs_and_analyses_the_next_workspace(self):
        self.failing.add(10)
        with self.app.document_batch():
            self.app.process_document(1)
            self.app.process_document(3)

        self.assertEqual(self.app.events[2:], [("analyse", 10), ("sync", 10), ("analyse", 20), ("sync", 20)])

    def test_nested_batches_analyse_once_when_the_outer_batch_ends(self):
        with self.app.document_batch():
            with self.app.document_batch():
                self.app.process_document(1)
            self.assertEqual(self.app.events, [("process", 1)])
            self.app.process_document(2)

        self.assertEqual(self.app.events, [("process", 1), ("process", 2), ("analyse", 10), ("sync", 10)])

    def test_an_empty_batch_analyses_nothing(self):
        with self.app.document_batch():
            pass

        self.assertEqual(self.app.events, [])


class DocumentsPageUsesTheBatchTests(unittest.TestCase):
    def test_process_selected_documents_runs_inside_one_batch(self):
        tree = ast.parse((REPO / "pb_planreader_3d_app.py").read_text(encoding="utf-8"))
        page = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "project_documents_page")
        batches = [n for n in ast.walk(page) if isinstance(n, ast.With)
                   and any(isinstance(i.context_expr, ast.Call) and getattr(i.context_expr.func, "id", "") == "document_batch"
                           for i in n.items)]
        self.assertEqual(len(batches), 1)
        calls = [n for n in ast.walk(batches[0]) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "process_document"]
        self.assertEqual(len(calls), 1, "the processing loop runs inside the batch")

    def test_the_core_default_batch_changes_nothing(self):
        with app_mod.document_batch():
            pass


_COMPOSED_RUN = r'''
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, REPO)
os.chdir(REPO)
import fitz
import pb_planreader_v133_app as entry
import pb_auto_geometry_v1219 as auto
app = entry.app
app.init_local_db()
data = Path(os.environ["PLANREADER_DATA_DIR"])
assert sys.modules["pb_planreader_3d_app"].document_batch is app.document_batch, "the documents page sees the batch"

mm = 72 / 25.4
ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
plan_pdf, elevation_pdf = data / "plan.pdf", data / "elevation.pdf"
doc = fitz.open(); plan = doc.new_page(width=842, height=595)
for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)), ((ox + w, oy + h), (ox, oy + h)),
             ((ox, oy + h), (ox, oy)), ((ox + split, oy), (ox + split, oy + h))):
    plan.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
plan.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
plan.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
plan.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
doc.save(plan_pdf); doc.close()
doc = fitz.open(); elevation = doc.new_page(width=842, height=595)
eh = 27 * mm
for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + eh)), ((ox + w, oy + eh), (ox, oy + eh)), ((ox, oy + eh), (ox, oy))):
    elevation.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
elevation.insert_text(fitz.Point(ox, oy + eh + 40), "NORTH ELEVATION   SCALE 1:100", fontsize=9)
elevation.insert_text(fitz.Point(ox, oy + eh + 60), "LINEABOARD CLADDING 42.5 m2", fontsize=9)
doc.save(elevation_pdf); doc.close()

ws = app.create_standalone_workspace("PB-BATCH", "Batch analysis", "b", "")
docs = [app.lexecute("INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                     (ws, pdf.name, "application/pdf", str(pdf), 0, "", "2026-09-27T00:00:00")) for pdf in (plan_pdf, elevation_pdf)]
for d in docs:
    app.index_document_pages(d)
analyses = []
chain = auto.analyse_workspace
def counted(app_obj, workspace_id):
    analyses.append(workspace_id)
    return chain(app_obj, workspace_id)
auto.analyse_workspace = counted
if MODE == "batch":
    with app.document_batch():
        for d in docs:
            app.process_document(d, force=False)
else:
    for d in docs:
        app.process_document(d, force=False)

STAMPS = {"saved_at", "analysed_at", "generated_at", "updated_at", "created_at", "completed_at", "uploaded_at",
          "source_signature", "model_mass_id", "image_path", "id"}
def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in STAMPS}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(data), "DATA")
        try:
            parsed = json.loads(value)
        except ValueError:
            return value
        return clean(parsed) if isinstance(parsed, (dict, list)) else value
    return value
def table(sql):
    return sorted(json.dumps(clean(dict(r)), sort_keys=True, default=str) for r in app.lquery(sql, (ws,)))
state = {
    "analyses": len(analyses),
    "takeoff_rows": table("SELECT * FROM takeoff_rows WHERE workspace_id=?"),
    "model_masses": table("SELECT * FROM model_masses WHERE workspace_id=?"),
    "pages": table("SELECT * FROM pages WHERE workspace_id=?"),
    "register_items": table("SELECT * FROM register_items WHERE workspace_id=?"),
    "settings": {r["key"]: clean(r["value"]) for r in app.lquery("SELECT key,value FROM workspace_settings WHERE workspace_id=?", (ws,))},
}
print("STATE " + json.dumps(state, sort_keys=True, default=str))
'''


class ComposedBatchEquivalenceTests(unittest.TestCase):
    def _run(self, mode):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as data:
            script = f"REPO = {str(REPO)!r}\nMODE = {mode!r}\n" + textwrap.dedent(_COMPOSED_RUN)
            env = dict(os.environ, PLANREADER_DATA_DIR=data, STREAMLIT_LOGGER_LEVEL="error", PYTHONIOENCODING="utf-8")
            done = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True,
                                  encoding="utf-8", timeout=900)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        line = next(l for l in done.stdout.splitlines() if l.startswith("STATE "))
        return json.loads(line[len("STATE "):])

    def test_batch_processing_ends_in_the_same_state_with_one_analysis(self):
        each, batch = self._run("each"), self._run("batch")

        self.assertEqual((each.pop("analyses"), batch.pop("analyses")), (2, 1))
        self.assertTrue(each["takeoff_rows"], "the documents produce automatic take-off rows")
        for part in each:
            self.assertEqual(batch[part], each[part], part)


if __name__ == "__main__":
    unittest.main()
