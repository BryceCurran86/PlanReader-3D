"""Auto-geometry take-off row contract (Subscription Take-off crash regression).

The room-face wrapper around _build_unit_rows used to append hand-built
13-value tuples, so _replace_auto_rows() failed with
"Incorrect number of bindings supplied. The current statement uses 21, and
there are 13 supplied." These tests pin the 21-field row contract at every
producer and at the publication boundary, and run the real sequence:
selected pages -> automatic geometry -> unit/facade rows -> take-off
publication -> 3D envelope mass.
"""
from __future__ import annotations

import sqlite3
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
import pb_planreader_3d_app as app_mod
from pb_production_3d_adapter import planreader_workspace_to_canonical
import pb_room_face_takeoff as room_face
import pb_selected_evidence_floor_v1226 as selected_evidence
import pb_unit_floor_area_gate_v1221 as unit_gate

RENDER_ZOOM = 2.0
PX_PER_M_1_100 = RENDER_ZOOM * 2834.646 / 100.0
_PATCHED = ("_build_unit_rows", "_build_facade_rows", "_auto_calibrate_page")


def _write_plan(pdf_path: Path, png_path: Path | None) -> None:
    """Native-vector 1:100 plan: 10 m x 6 m outline split into two labelled rooms."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    mm = 72 / 25.4
    ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
    for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)),
                 ((ox + w, oy + h), (ox, oy + h)), ((ox, oy + h), (ox, oy)),
                 ((ox + split, oy), (ox + split, oy + h))):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
    page.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
    page.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
    if png_path is not None:
        page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)).save(png_path)
    doc.save(pdf_path)
    doc.close()


def _room_face_row(**changes):
    row = {
        "workspace_id": 1, "section": "Internal", "element": "Floor area", "location": "LOUNGE",
        "substrate": "Other", "unit": "m²", "quantity": 36.0, "quantity_status": "Measured",
        "source_page": 1, "source_reference": f"{room_face.SOURCE_PREFIX} · A101 · page:1",
        "confidence": "Derived", "notes": "Room area from calibrated vector face extraction.",
        "row_role": "floor_area",
    }
    row.update(changes)
    return row


class _Workspace:
    """Real app schema on a temporary database, with module patches restored."""

    def __init__(self, root: Path):
        self.root = root
        # The production app functions the wrapper chain calls, on the temp database.
        self.app = SimpleNamespace(
            lquery=app_mod.lquery, lexecute=app_mod.lexecute, local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp, workspace_setting=app_mod.workspace_setting,
            set_workspace_setting=app_mod.set_workspace_setting,
            auto_detect_scale=app_mod.auto_detect_scale, fitz=fitz,
        )

    def add_document(self, pdf_path: Path) -> None:
        app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'Contract','x','x')")
        app_mod.lexecute(
            "INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,1,?,?,'sha',3)",
            (pdf_path.name, str(pdf_path)),
        )

    def add_page(self, page_id: int, page_type: str, label: str, text: str, *, image: Path | None = None) -> None:
        app_mod.lexecute(
            """INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,scale_text,px_per_m,
                   image_path,render_zoom,extracted_text,selected)
               VALUES(?,1,1,?,?,?,'1:100',?,?,?,?,1)""",
            (page_id, page_id, label, page_type, PX_PER_M_1_100, str(image) if image else None, RENDER_ZOOM, text),
        )

    def pages(self):
        return [dict(p) for p in app_mod.lquery("SELECT * FROM pages WHERE workspace_id=1 ORDER BY id")]


@contextmanager
def _workspace():
    saved = {name: getattr(auto, name) for name in _PATCHED}
    saved_db_flag = getattr(app_mod, "_pb_local_db_initialized_v1215", None)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            patch.object(app_mod, "DB_PATH", Path(tmp) / "planreader.db"):
        setattr(app_mod, "_pb_local_db_initialized_v1215", False)
        app_mod.init_local_db()
        try:
            yield _Workspace(Path(tmp))
        finally:
            for name, fn in saved.items():
                setattr(auto, name, fn)
            if saved_db_flag is not None:
                setattr(app_mod, "_pb_local_db_initialized_v1215", saved_db_flag)
            else:
                app_mod.__dict__.pop("_pb_local_db_initialized_v1215", None)


def _apply_production_chain(app) -> None:
    # Same order as pb_planreader_v126_app.py startup.
    for module in (guard, unit_gate, context_floorarea, selected_evidence, room_face):
        module.apply(app)


class TakeoffRowContractTests(unittest.TestCase):
    def test_takeoff_row_has_exactly_the_insert_fields(self):
        row = auto._takeoff_row(
            workspace_id=1, section="Internal", element="Floor area", location="Unit 1", substrate="Other",
            quantity=12.345, status="Measured", source_page="A101",
            source_reference=f"{auto.SOURCE_PREFIX} · unit", confidence="Documented", notes="n", row_role="floor_area",
        )
        self.assertEqual(len(row), 21)
        self.assertEqual(auto.TAKEOFF_ROW_FIELD_COUNT, 21)
        self.assertEqual(auto._TAKEOFF_INSERT.count("?"), 21)
        columns = auto._TAKEOFF_INSERT.split("(", 1)[1].split(")", 1)[0].split(",")
        self.assertEqual(tuple(columns), auto.TAKEOFF_ROW_FIELDS)
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("unit")], "m²")
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("quantity")], 12.35)
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("inclusion_status")], "INCLUSION")

    def test_build_unit_rows_emits_only_canonical_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            rows, summary = auto._build_unit_rows(ws.app, 1, ws.pages())
        self.assertEqual(len(rows), 1)
        self.assertTrue(all(len(r) == auto.TAKEOFF_ROW_FIELD_COUNT for r in rows))
        self.assertEqual(summary[0]["label"], "Unit 1")

    def test_build_facade_rows_emits_only_canonical_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            rows, _facades = auto._build_facade_rows(ws.app, 1, ws.pages())
        self.assertEqual(len(rows), 1)
        self.assertTrue(all(len(r) == auto.TAKEOFF_ROW_FIELD_COUNT for r in rows))
        self.assertEqual(rows[0][auto.TAKEOFF_ROW_FIELDS.index("quantity")], 42.5)

    def test_room_face_row_maps_every_field_by_name(self):
        row = room_face.room_row_to_auto_takeoff_row(auto, _room_face_row())
        fields = dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
        self.assertEqual(len(row), 21)
        self.assertEqual(fields["unit"], "m²")
        self.assertEqual(fields["quantity"], 36.0)
        self.assertEqual(fields["quantity_status"], "Measured")
        self.assertEqual(fields["source_page"], "1")
        self.assertEqual(fields["confidence"], "Derived")
        self.assertEqual(fields["row_role"], "floor_area")
        self.assertEqual(fields["inclusion_status"], "INCLUSION")
        self.assertTrue(fields["source_reference"].startswith(auto.SOURCE_PREFIX))
        self.assertIn(room_face.SOURCE_PREFIX, fields["source_reference"])

    def test_uncalibrated_room_is_not_published_as_zero(self):
        self.assertIsNone(room_face.room_row_to_auto_takeoff_row(auto, _room_face_row(quantity=None)))

    def test_room_face_row_without_unit_fails_loudly(self):
        row = _room_face_row()
        del row["unit"]
        with self.assertRaises(KeyError):
            room_face.room_row_to_auto_takeoff_row(auto, row)

    def test_replace_auto_rows_accepts_generated_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            ws.add_page(2, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            unit_rows, _ = auto._build_unit_rows(ws.app, 1, ws.pages())
            facade_rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
            auto._replace_auto_rows(ws.app, 1, unit_rows + facade_rows)
            stored = app_mod.lquery("SELECT quantity,unit,created_at FROM takeoff_rows ORDER BY id")
        self.assertEqual([r["quantity"] for r in stored], [85.4, 42.5])
        self.assertTrue(all(r["unit"] == "m²" and r["created_at"] for r in stored))

    def test_legacy_13_value_row_fails_before_touching_sqlite(self):
        legacy = (1, "Internal", "Floor area", "LOUNGE", "Other", "m²", 36.0, "Measured", 1,
                  f"{room_face.SOURCE_PREFIX} · A101 · page:1", "Derived", "notes", "floor_area")
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            good, _ = auto._build_unit_rows(ws.app, 1, ws.pages())
            auto._replace_auto_rows(ws.app, 1, good)
            with self.assertRaises(auto.TakeoffRowContractError) as caught:
                auto._replace_auto_rows(ws.app, 1, good + [legacy])
            remaining = app_mod.lquery("SELECT COUNT(*) AS n FROM takeoff_rows")[0]["n"]
        message = str(caught.exception)
        self.assertIn("row 1", message)
        self.assertIn("13 values", message)
        self.assertIn("expected 21", message)
        self.assertIn(room_face.SOURCE_PREFIX, message)
        self.assertNotIsInstance(caught.exception, sqlite3.ProgrammingError)
        self.assertEqual(remaining, 1, "the existing batch must survive a rejected publication")

    def test_row_outside_the_auto_batch_prefix_is_rejected(self):
        row = list(auto._takeoff_row(
            workspace_id=1, section="Internal", element="Floor area", location="LOUNGE", substrate="Other",
            quantity=36.0, status="Measured", source_page="1",
            source_reference=f"{room_face.SOURCE_PREFIX} · A101 · page:1", confidence="Derived", notes="n",
        ))
        with self.assertRaises(auto.TakeoffRowContractError) as caught:
            auto._validate_auto_rows([tuple(row)], 1)
        self.assertIn("would not be replaced on re-run", str(caught.exception))


class AuthoritativeSchemaTests(unittest.TestCase):
    def test_auto_geometry_row_is_the_app_takeoff_column_contract(self):
        # One schema: the app's editable take-off columns, framed by the owner
        # and audit columns every 21-value writer in the app uses.
        self.assertEqual(
            auto.TAKEOFF_ROW_FIELDS,
            ("workspace_id", *app_mod.TAKEOFF_COLUMNS, "row_role", "created_at", "updated_at"),
        )
        with _workspace():
            columns = {row["name"] for row in app_mod.lquery("PRAGMA table_info(takeoff_rows)")}
        self.assertTrue(set(auto.TAKEOFF_ROW_FIELDS) <= columns)

    def test_sqlite_round_trip_preserves_every_field_in_order(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            ws.add_page(2, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            unit_rows, _ = auto._build_unit_rows(ws.app, 1, ws.pages())
            facade_rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
            room_row = room_face.room_row_to_auto_takeoff_row(auto, _room_face_row())
            produced = unit_rows + facade_rows + [room_row]
            auto._replace_auto_rows(ws.app, 1, produced)
            stored = app_mod.lquery(
                f"SELECT {','.join(auto.TAKEOFF_ROW_FIELDS)} FROM takeoff_rows WHERE workspace_id=1 ORDER BY id"
            )
        self.assertEqual(len(stored), len(produced))
        audit = {"created_at", "updated_at"}
        for expected, row in zip(produced, stored):
            for index, name in enumerate(auto.TAKEOFF_ROW_FIELDS):
                if name in audit:
                    self.assertTrue(row[name])
                else:
                    self.assertEqual(row[name], expected[index], name)


class AutomaticGeometryEndToEndTests(unittest.TestCase):
    def test_manual_floor_measurement_suppresses_matching_room_face_row(self):
        with _workspace() as ws:
            pdf, png = ws.root / "plan.pdf", ws.root / "plan_p1.png"
            _write_plan(pdf, png)
            ws.add_document(pdf)
            ws.add_page(1, "Floor Plan", "A101", "GROUND FLOOR PLAN", image=png)
            app_mod.lexecute(
                """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,
                       quantity_status,source_reference,row_role,created_at,updated_at)
                   VALUES(1,'Internal','Floor area','Lounge','Other',35.0,'m²','Measured',
                          'Takeoff Studio · manual polygon','floor_area','x','x')"""
            )
            _apply_production_chain(ws.app)
            auto.analyse_workspace(ws.app, 1)
            rows = app_mod.lquery("SELECT location,source_reference FROM takeoff_rows WHERE workspace_id=1 ORDER BY id")
        auto_rooms = [r["location"] for r in rows if room_face.SOURCE_PREFIX in (r["source_reference"] or "")]
        self.assertNotIn("LOUNGE", auto_rooms, "the manual Lounge measurement must take priority")
        self.assertIn("BEDROOM", auto_rooms)
        self.assertIn("Takeoff Studio · manual polygon", [r["source_reference"] for r in rows])


    def test_plan_to_takeoff_rows_to_3d_mass_with_production_wrappers(self):
        with _workspace() as ws:
            pdf, png = ws.root / "plan.pdf", ws.root / "plan_p1.png"
            _write_plan(pdf, png)
            ws.add_document(pdf)
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2", image=png)
            ws.add_page(2, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            _apply_production_chain(ws.app)
            self.assertIs(auto._build_unit_rows.__name__, "_build_unit_rows_with_room_faces")

            report = auto.analyse_workspace(ws.app, 1)
            first = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1 ORDER BY id")
            masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=1")

            again = auto.analyse_workspace(ws.app, 1)
            second = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1 ORDER BY id")
            masses_again = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=1")

        room_rows = [r for r in first if room_face.SOURCE_PREFIX in (r["source_reference"] or "")]
        self.assertGreaterEqual(len(room_rows), 1, "room-face rows must reach the take-off table")
        self.assertTrue(all(r["unit"] == "m²" and r["quantity"] > 0 for r in room_rows))
        self.assertTrue(all(r["source_reference"].startswith(auto.SOURCE_PREFIX) for r in first))
        self.assertEqual(report["auto_takeoff_rows"], len(first))
        self.assertTrue(any(r["element"] == "External walls / cladding" for r in first))
        self.assertIsNotNone(report["model_mass_id"], "the 3D envelope mass must be generated")
        self.assertEqual(len(masses), 1)
        self.assertAlmostEqual(masses[0]["width"], 10.0, delta=0.5)
        self.assertAlmostEqual(masses[0]["depth"], 6.0, delta=0.5)
        # Re-running replaces the batch instead of duplicating it.
        self.assertEqual(len(second), len(first))
        self.assertEqual(again["model_mass_id"], report["model_mass_id"])
        self.assertEqual(len(masses_again), 1)


class RealDocumentWorkflowTests(unittest.TestCase):
    """upload -> index -> render -> automatic geometry -> persistence -> review -> 3D."""

    def test_uploaded_plan_reaches_takeoff_review_and_3d_model(self):
        import pb_no_ai_takeoff_v1216 as noai

        missing = object()
        saved_panel = noai.no_ai_takeoff_panel
        saved_flag = getattr(noai, "_pb_auto_geometry_panel_v1219", missing)
        with _workspace() as ws, patch.object(app_mod, "WORKSPACE_DIR", ws.root / "workspaces"):
            try:
                pdf = ws.root / "upload_plan.pdf"
                _write_plan(pdf, None)
                app = ws.app
                app.index_document_pages = app_mod.index_document_pages
                app.process_document = app_mod.process_document
                auto.apply(app)  # wraps index/process exactly as at startup
                _apply_production_chain(app)

                workspace_id = app_mod.create_standalone_workspace("PB-T902", "Contract workflow", "b", "")
                document_id = app_mod.lexecute(
                    """INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (workspace_id, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
                )
                app.index_document_pages(document_id)
                count, message = app.process_document(document_id, force=False)
                report = auto._setting_get(app, workspace_id)
                rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (workspace_id,))
                review = app_mod.dataframe_for_takeoff(workspace_id)
                masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (workspace_id,))
                ws_result = planreader_workspace_to_canonical(app, workspace_id)
                viewer_payload = project_to_viewer_payload(ws_result.project)
                viewer_html = generate_bim_viewer_html(viewer_payload)

                app.process_document(document_id, force=True)
                rows_again = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (workspace_id,))
                masses_again = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (workspace_id,))
            finally:
                noai.no_ai_takeoff_panel = saved_panel
                if saved_flag is missing:
                    noai.__dict__.pop("_pb_auto_geometry_panel_v1219", None)
                else:
                    noai._pb_auto_geometry_panel_v1219 = saved_flag

        self.assertEqual(count, 1, message)
        self.assertTrue(report, "automatic geometry must have run and saved its report")
        by_location = {r["location"]: r for r in rows if room_face.SOURCE_PREFIX in (r["source_reference"] or "")}
        self.assertEqual(set(by_location), {"LOUNGE", "BEDROOM"})
        self.assertAlmostEqual(by_location["LOUNGE"]["quantity"], 36.0, delta=1.0)
        self.assertAlmostEqual(by_location["BEDROOM"]["quantity"], 24.0, delta=1.0)
        for row in by_location.values():
            self.assertEqual((row["unit"], row["row_role"], row["section"]), ("m²", "floor_area", "Internal"))
        self.assertEqual(report["auto_takeoff_rows"], len(rows))
        self.assertIsNotNone(review)
        self.assertEqual(len(masses), 1)
        self.assertEqual(report["model_mass_id"], masses[0]["id"])
        self.assertEqual(len(rows_again), len(rows), "re-processing must replace, not duplicate")
        self.assertEqual(len(masses_again), 1)
        self.assertIsNotNone(ws_result.project)
        self.assertGreaterEqual(len(ws_result.project.buildings), 1)
        self.assertIn("levels", viewer_payload)
        self.assertEqual(viewer_payload["project_name"], f"Workspace #{workspace_id} Canonical BIM Model")
        self.assertIn("THREE", viewer_html)
        self.assertGreater(len(viewer_html), 5000)

    def test_persisted_failed_workspace_recovers_cleanly_on_reprocess(self):
        """A workspace created during an abort/crash cleanly recovers on re-process."""
        import pb_no_ai_takeoff_v1216 as noai

        missing = object()
        saved_panel = noai.no_ai_takeoff_panel
        saved_flag = getattr(noai, "_pb_auto_geometry_panel_v1219", missing)
        with _workspace() as ws, patch.object(app_mod, "WORKSPACE_DIR", ws.root / "workspaces"):
            try:
                pdf = ws.root / "recovery_plan.pdf"
                _write_plan(pdf, None)
                app = ws.app
                app.index_document_pages = app_mod.index_document_pages
                app.process_document = app_mod.process_document
                auto.apply(app)
                _apply_production_chain(app)

                workspace_id = app_mod.create_standalone_workspace("PB-RECOVER", "Recovery test", "b", "")
                document_id = app_mod.lexecute(
                    """INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (workspace_id, pdf.name, "application/pdf", str(pdf), 0, "", app_mod.now_stamp()),
                )
                app.index_document_pages(document_id)

                # Prior manual takeoff row exists
                app_mod.lexecute(
                    """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,
                           quantity_status,source_reference,row_role,created_at,updated_at)
                       VALUES(?,'Internal','Feature wall','Meeting Room','Timber',15.0,'m²','Measured',
                              'Manual Entry · estimator','wall_finish','x','x')""",
                    (workspace_id,),
                )
                self.assertEqual(len(app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (workspace_id,))), 0)

                # Re-process under fixed runtime
                count, message = app.process_document(document_id, force=True)
                rows = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (workspace_id,))
                manual_rows = [r for r in rows if "Manual Entry" in (r["source_reference"] or "")]
                auto_rows = [r for r in rows if auto.SOURCE_PREFIX in (r["source_reference"] or "")]
                masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=?", (workspace_id,))
                ws_result = planreader_workspace_to_canonical(app, workspace_id)
                viewer_html = generate_bim_viewer_html(project_to_viewer_payload(ws_result.project))
            finally:
                noai.no_ai_takeoff_panel = saved_panel
                if saved_flag is missing:
                    noai.__dict__.pop("_pb_auto_geometry_panel_v1219", None)
                else:
                    noai._pb_auto_geometry_panel_v1219 = saved_flag

        self.assertEqual(count, 1, message)
        self.assertEqual(len(manual_rows), 1, "Pre-existing manual takeoff rows must survive re-processing")
        self.assertEqual(manual_rows[0]["quantity"], 15.0)
        self.assertGreaterEqual(len(auto_rows), 2, "Automatic geometry rows must be generated")
        self.assertEqual(len(masses), 1, "3D model mass must be created on recovery")
        self.assertIn("THREE", viewer_html)


if __name__ == "__main__":
    unittest.main()
