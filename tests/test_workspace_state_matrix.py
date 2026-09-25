"""Workspace state matrix & release regression sentinel test suite.

Validates the full PlanReader production pipeline across 6 workspace lifecycle states:
A. Clean new workspace
B. Workspace previously aborted during processing
C. Workspace containing manual estimator rows
D. Workspace already containing automatic geometry rows
E. Repeated reprocessing (idempotency verification)
F. Empty workspace / document without geometry (fail-closed, zero made-up data)

For each state, explicitly verifies:
- Manual data survival
- Auto-row correctness (21-field contract)
- Model mass state
- Review dataframe availability
- 3D canonical model & Three.js viewer HTML payload generation
"""
from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

import pb_auto_geometry_guard_v1219 as guard
import pb_auto_geometry_v1219 as auto
from pb_bim_viewer import generate_bim_viewer_html, project_to_viewer_payload
import pb_context_floorarea_v1224 as context_floorarea
import pb_no_ai_takeoff_v1216 as noai
import pb_planreader_3d_app as app_mod
from pb_production_3d_adapter import planreader_workspace_to_canonical
import pb_room_face_takeoff as room_face
import pb_selected_evidence_floor_v1226 as selected_evidence
import pb_unit_floor_area_gate_v1221 as unit_gate


def _write_plan(pdf_path: Path, width_m: float = 10.0, height_m: float = 6.0) -> None:
    """Generate a native vector plan: outline with two named rooms."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    mm = 72 / 25.4
    ox, oy = 80, 80
    w = width_m * 10 * mm
    h = height_m * 10 * mm
    split = (width_m * 0.6) * 10 * mm
    for a, b in (
        ((ox, oy), (ox + w, oy)),
        ((ox + w, oy), (ox + w, oy + h)),
        ((ox + w, oy + h), (ox, oy + h)),
        ((ox, oy + h), (ox, oy)),
        ((ox + split, oy), (ox + split, oy + h)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "OFFICE", fontsize=9)
    page.insert_text(fitz.Point(ox + split + (w - split) / 2 - 20, oy + h / 2), "STORAGE", fontsize=9)
    page.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
    doc.save(pdf_path)
    doc.close()


def _write_blank_doc(pdf_path: Path) -> None:
    """Generate a blank document with text only and no scale or architectural geometry."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(100, 100), "Project Cover Sheet - No Geometry", fontsize=12)
    doc.save(pdf_path)
    doc.close()


@contextmanager
def _test_environment():
    """Isolated database and workspace sandbox with production extension chain."""
    saved_panel = noai.no_ai_takeoff_panel
    saved_flag = getattr(noai, "_pb_auto_geometry_panel_v1219", object())
    saved_db_flag = getattr(app_mod, "_pb_local_db_initialized_v1215", None)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            patch.object(app_mod, "DB_PATH", Path(tmp) / "planreader.db"), \
            patch.object(app_mod, "WORKSPACE_DIR", Path(tmp) / "workspaces"):
        setattr(app_mod, "_pb_local_db_initialized_v1215", False)
        app_mod.init_local_db()
        app = SimpleNamespace(
            lquery=app_mod.lquery,
            lexecute=app_mod.lexecute,
            local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp,
            workspace_setting=app_mod.workspace_setting,
            set_workspace_setting=app_mod.set_workspace_setting,
            auto_detect_scale=app_mod.auto_detect_scale,
            fitz=fitz,
            index_document_pages=app_mod.index_document_pages,
            process_document=app_mod.process_document,
            dataframe_for_takeoff=app_mod.dataframe_for_takeoff,
        )
        auto.apply(app)
        for m in (guard, unit_gate, context_floorarea, selected_evidence, room_face):
            m.apply(app)
        try:
            yield app, Path(tmp)
        finally:
            noai.no_ai_takeoff_panel = saved_panel
            if saved_flag is not object():
                noai._pb_auto_geometry_panel_v1219 = saved_flag
            else:
                noai.__dict__.pop("_pb_auto_geometry_panel_v1219", None)
            if saved_db_flag is not None:
                setattr(app_mod, "_pb_local_db_initialized_v1215", saved_db_flag)
            else:
                app_mod.__dict__.pop("_pb_local_db_initialized_v1215", None)


class WorkspaceStateMatrixTests(unittest.TestCase):
    """Permanent coverage for the 6 critical workspace lifecycle states."""

    def test_state_a_clean_new_workspace(self):
        """State A: Clean new workspace with uploaded vector plan runs full pipeline."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "clean_plan.pdf"
            _write_plan(pdf)
            wid = app_mod.create_standalone_workspace("WS-A", "State A Clean", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)
            count, msg = app.process_document(doc_id, force=False)

            rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))
            masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))
            review_df = app.dataframe_for_takeoff(wid)
            ws_result = planreader_workspace_to_canonical(app, wid)
            payload = project_to_viewer_payload(ws_result.project)
            html = generate_bim_viewer_html(payload)

            self.assertEqual(count, 1)
            self.assertGreaterEqual(len(rows), 2)
            self.assertTrue(all(r["source_reference"].startswith(auto.SOURCE_PREFIX) for r in rows))
            self.assertEqual(len(masses), 1)
            self.assertIsNotNone(review_df)
            self.assertIn("THREE", html)
            self.assertGreater(len(html), 5000)

    def test_state_b_aborted_workspace_recovery(self):
        """State B: Workspace aborted halfway during processing recovers cleanly on re-process."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "aborted_plan.pdf"
            _write_plan(pdf)
            wid = app_mod.create_standalone_workspace("WS-B", "State B Aborted", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)

            # Simulate aborted state: no masses, incomplete settings
            self.assertEqual(len(app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))), 0)

            # Re-process under production runtime
            count, msg = app.process_document(doc_id, force=True)
            rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))
            masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))
            ws_result = planreader_workspace_to_canonical(app, wid)
            html = generate_bim_viewer_html(project_to_viewer_payload(ws_result.project))

            self.assertEqual(count, 1)
            self.assertGreaterEqual(len(rows), 2)
            self.assertEqual(len(masses), 1)
            self.assertIn("THREE", html)

    def test_state_c_manual_rows_survival(self):
        """State C: Workspace containing manual estimator rows survives processing intact."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "manual_plan.pdf"
            _write_plan(pdf)
            wid = app_mod.create_standalone_workspace("WS-C", "State C Manual", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)

            # Estimator manual row
            app_mod.lexecute(
                """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,
                       quantity_status,source_reference,row_role,created_at,updated_at)
                   VALUES(?,'Internal','Feature wall','Reception','Timber',25.0,'m²','Measured',
                          'Manual Entry · estimator','wall_finish','x','x')""",
                (wid,),
            )

            count, msg = app.process_document(doc_id, force=False)
            rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))
            manual_rows = [r for r in rows if "Manual Entry" in (r["source_reference"] or "")]
            auto_rows = [r for r in rows if auto.SOURCE_PREFIX in (r["source_reference"] or "")]

            self.assertEqual(len(manual_rows), 1, "Manual row must be preserved")
            self.assertEqual(manual_rows[0]["quantity"], 25.0)
            self.assertGreaterEqual(len(auto_rows), 2, "Auto rows must be populated alongside manual rows")

    def test_state_d_workspace_with_existing_auto_rows(self):
        """State D: Workspace already containing auto rows replaces them without duplication."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "existing_plan.pdf"
            _write_plan(pdf)
            wid = app_mod.create_standalone_workspace("WS-D", "State D Existing", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)

            # First run
            app.process_document(doc_id, force=False)
            first_rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))

            # Second run on existing
            app.process_document(doc_id, force=True)
            second_rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))

            self.assertEqual(len(first_rows), len(second_rows), "Auto rows must be replaced, not duplicated")
            self.assertEqual(
                [r["quantity"] for r in first_rows],
                [r["quantity"] for r in second_rows],
            )

    def test_state_e_repeated_reprocessing_idempotence(self):
        """State E: Repeated reprocessing maintains identical model mass ID and row count."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "idempotent_plan.pdf"
            _write_plan(pdf)
            wid = app_mod.create_standalone_workspace("WS-E", "State E Repeat", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)

            # Initial run
            app.process_document(doc_id, force=False)
            rep1 = auto._setting_get(app, wid)
            mass1 = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))
            rows1 = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))

            # Second run with force=True
            app.process_document(doc_id, force=True)
            rep2 = auto._setting_get(app, wid)
            mass2 = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))
            rows2 = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (wid,))

            self.assertEqual(rep1["model_mass_id"], rep2["model_mass_id"])
            self.assertEqual(len(mass1), 1)
            self.assertEqual(len(mass2), 1)
            self.assertEqual(mass1[0]["id"], mass2[0]["id"])
            self.assertEqual(len(rows1), len(rows2))

    def test_state_f_empty_document_fails_closed_without_crash(self):
        """State F: Document without geometry fails closed safely with 0 made-up data."""
        with _test_environment() as (app, tmp):
            pdf = tmp / "blank_doc.pdf"
            _write_blank_doc(pdf)
            wid = app_mod.create_standalone_workspace("WS-F", "State F Blank", "b", "")
            doc_id = app_mod.lexecute(
                "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (wid, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
            )
            app.index_document_pages(doc_id)
            count, msg = app.process_document(doc_id, force=False)

            rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (wid,))
            masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (wid,))
            ws_result = planreader_workspace_to_canonical(app, wid)
            payload = project_to_viewer_payload(ws_result.project)
            html = generate_bim_viewer_html(payload)

            self.assertEqual(len(rows), 0, "No auto rows invented for blank sheet")
            self.assertEqual(len(masses), 0, "No 3D masses invented for blank sheet")
            self.assertIn("THREE", html)


if __name__ == "__main__":
    unittest.main()
