"""Rows the estimator merged in review stay merged across automatic re-runs.

Merging take-off rows (pb_takeoff_review_v1226.merge_rows) replaces the
inputs with one merged row and records the inputs' source references so the
generators that republish them can clean them up again. The review module
wrapped the no-AI, commercial, Studio and surface replacers, but not the
automatic-geometry publication: merged automatic inputs were removed only as
a side effect of the commercial refresh that runs after it. That refresh
records its own failures and carries on, so when it failed the merged inputs
stayed published beside the merged row and the floor area was double counted.

The composed production app runs in a subprocess because the startup chain
patches module globals.
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
import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, REPO)
os.chdir(REPO)
import fitz
import pb_planreader_v133_app as entry
import pb_premier_takeoff_v1225 as premier
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

ws = app.create_standalone_workspace("PB-MERGE", "Merge rerun", "b", "")
doc_id = app.lexecute("INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                      (ws, pdf.name, "application/pdf", str(pdf), 0, "", app.now_stamp()))
app.index_document_pages(doc_id)
app.process_document(doc_id, force=False)
app.run_planreader_autopilot(ws, force=True)

def floor_rows():
    return [dict(r) for r in app.lquery(
        "SELECT location,quantity,source_reference FROM takeoff_rows WHERE workspace_id=? AND row_role='floor_area' ORDER BY location", (ws,))]

stages = {"uploaded": floor_rows()}
room_ids = [r["id"] for r in app.lquery("SELECT id FROM takeoff_rows WHERE workspace_id=? AND source_reference LIKE '%PB RoomFace%'", (ws,))]
app.merge_takeoff_rows_v1226(ws, room_ids, {"location": "Living (merged)"})
stages["merged"] = floor_rows()
app.run_auto_geometry(ws)
stages["re-run"] = floor_rows()
with patch.object(premier, "build_pb_schedule", side_effect=RuntimeError("schedule builder failed")):
    report = app.run_auto_geometry(ws)
stages["re-run, commercial refresh failed"] = floor_rows()
print("RESULT=" + json.dumps({"stages": stages, "merged_inputs": room_ids, "pb_error": report.get("pb_takeoff_error")}))
'''


class MergedRowsSurviveAutomaticRerunTests(unittest.TestCase):
    def test_merged_automatic_inputs_are_not_republished(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            script = Path(tmp) / "merge_rerun.py"
            script.write_text(f"REPO = {str(REPO)!r}\n" + textwrap.dedent(_COMPOSED_RUN), encoding="utf-8")
            env = dict(os.environ, PLANREADER_DATA_DIR=str(Path(tmp) / "data"), PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, str(script)], cwd=str(REPO), env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", timeout=900)
        payload = [line for line in result.stdout.splitlines() if line.startswith("RESULT=")]
        self.assertTrue(payload, f"exit {result.returncode}\nSTDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}")
        outcome = json.loads(payload[0][len("RESULT="):])
        stages = outcome["stages"]

        self.assertEqual(len(outcome["merged_inputs"]), 2, "the synthetic plan must publish two room-face rows to merge")
        self.assertEqual(outcome["pb_error"], "schedule builder failed")
        merged = stages["merged"]
        self.assertIn("Living (merged)", {r["location"] for r in merged})
        self.assertFalse(any("PB RoomFace" in r["source_reference"] for r in merged))
        for stage in ("re-run", "re-run, commercial refresh failed"):
            with self.subTest(stage):
                rows = stages[stage]
                self.assertFalse(any("PB RoomFace" in r["source_reference"] for r in rows),
                                 "merged room-face inputs were republished beside the merged row")
                self.assertAlmostEqual(sum(r["quantity"] for r in rows), sum(r["quantity"] for r in merged), places=2)


if __name__ == "__main__":
    unittest.main()
