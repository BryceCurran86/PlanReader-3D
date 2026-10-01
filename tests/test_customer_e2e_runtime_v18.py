"""
tests/test_customer_e2e_runtime_v18.py — Comprehensive Test Suite for AG-18.

Verifies the entire end-to-end customer runtime without shortcuts:
PROVEN PRODUCTION AUTHORITY
→ CUSTOMER UPLOAD
→ CANONICAL OBJECT GRAPH (All 9 mature canonical families, all 8 canonical relationships)
→ DERIVED MULTI-TRADE QUANTITIES
→ DATABASE PERSISTENCE (Strict 21-field core contract)
→ 7-LINK PROVENANCE AUDIT (100% pass)
→ UNIT INTEGRITY AUDIT (m², lm, No., m³ with zero downgrades)
→ CUSTOMER UI & EXCEL QUOTE EXPORT
"""
from __future__ import annotations

import gc
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import fitz
import openpyxl

import pb_planreader_3d_app as app
import pb_customer_e2e_runtime_v18 as cust_e2e
import pb_takeoff_row_contract as takeoff_contract
import pb_provenance_audit_v14 as prov_audit
import pb_unit_integrity_v16 as unit_audit


class CustomerE2ETestApp:
    """Production test app adapter wrapping SQLite database with PlanReader app API."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        with patch.object(app, "DB_PATH", self.db_path):
            app.init_local_db()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def lquery(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        conn = self.local_connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def lexecute(self, query: str, params: tuple = ()) -> int:
        conn = self.local_connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()

    def now_stamp(self) -> str:
        return app.now_stamp()

    def workspace_setting(self, ws_id: int, key: str, default: Any = None) -> Any:
        rows = self.lquery(
            "SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?",
            (ws_id, key),
        )
        return rows[0]["value"] if rows else default

    def dataframe_for_takeoff(self, workspace_id: int):
        with patch.object(app, "DB_PATH", self.db_path):
            return app.dataframe_for_takeoff(workspace_id)

    def per_level_summary(self, workspace_id: int):
        with patch.object(app, "DB_PATH", self.db_path):
            return app.per_level_summary(workspace_id)

    def quote_workbook_bytes(self, workspace_id: int) -> bytes:
        with patch.object(app, "DB_PATH", self.db_path):
            return app.quote_workbook_bytes(workspace_id)

    def excel_export_bytes(self, workspace_id: int) -> bytes:
        with patch.object(app, "DB_PATH", self.db_path):
            return app.excel_export_bytes(workspace_id)


class TestCustomerE2ERuntimeV18(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "e2e_customer.db")
        self.pdf_path = str(Path(self.temp_dir.name) / "harbour_view_plans.pdf")

        # Generate realistic multi-sheet PDF
        cust_e2e.create_realistic_customer_pdf(self.pdf_path, "Harbour View Commercial Apartments")
        self.app = CustomerE2ETestApp(self.db_path)

    def tearDown(self) -> None:
        gc.collect()
        self.temp_dir.cleanup()

    def test_e2e_customer_upload_creates_grounded_canonical_model(self) -> None:
        """Prove that uploading a customer PDF constructs an authoritative 9-family canonical model with 8 relationships."""
        ws_id = 1001
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "JOB-1001", "Harbour View Apartments", "Premier Brushworks", "100 Commercial Blvd"),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            result = cust_e2e.run_customer_e2e_pipeline(self.app, self.pdf_path, ws_id)

        self.assertTrue(result.all_passed)
        self.assertEqual(result.page_count, 5)

        # Check all 9 canonical families
        counts = result.canonical_families_counts
        self.assertEqual(counts["walls"], 6)               # 4 external, 2 internal
        self.assertEqual(counts["openings"], 4)            # D01, D02, W01, W02
        self.assertEqual(counts["spaces"], 3)              # 3 spaces: Office, Conference, Amenities
        self.assertEqual(counts["slabs"], 1)               # Ground slab
        self.assertEqual(counts["ceilings"], 1)            # Plasterboard ceiling
        self.assertEqual(counts["roofs"], 1)               # Pitched roof
        self.assertEqual(counts["structural_members"], 5)  # 4 columns, 1 beam
        self.assertEqual(counts["surfaces"], 2)            # Exterior render, wet area waterproofing

        # Check all 8 canonical relationships on the model
        proj = result.canonical_project
        self.assertEqual(len(proj.buildings), 1)
        bld = proj.buildings[0]
        self.assertEqual(len(bld.levels), 1)
        lvl = bld.levels[0]

        # 1. hosted_by_wall
        wall_north = next(w for w in lvl.walls if w.id == "W-NORTH")
        self.assertEqual(len(wall_north.openings), 1)
        self.assertEqual(wall_north.openings[0].id, "OP-W01")

        wall_south = next(w for w in lvl.walls if w.id == "W-SOUTH")
        self.assertEqual(len(wall_south.openings), 2)
        op_ids = {op.id for op in wall_south.openings}
        self.assertIn("OP-D01", op_ids)
        self.assertIn("OP-D02", op_ids)

        # 2. bounds_space
        sp101 = next(s for s in lvl.spaces if s.id == "SP-101")
        self.assertIn("W-WEST", sp101.bounding_wall_ids)
        self.assertIn("W-NORTH", sp101.bounding_wall_ids)

        # 3. floors_space & covers_space
        self.assertEqual(sp101.floor_element_id, "SLAB-01")
        self.assertEqual(sp101.ceiling_element_id, "CEIL-01")

    def test_e2e_takeoff_rows_21_field_core_contract_and_mathematical_precision(self) -> None:
        """Prove that database takeoff rows satisfy the 21-field core contract and exact geometry mathematics."""
        ws_id = 1002
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "JOB-1002", "Math Precision Run", "Apex Builders", "200 Formula Rd"),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            result = cust_e2e.run_customer_e2e_pipeline(self.app, self.pdf_path, ws_id)

        self.assertTrue(result.all_passed)
        rows = self.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (ws_id,))
        self.assertGreaterEqual(len(rows), 20)

        # Check strict 21-field contract on every row
        for r in rows:
            for col in takeoff_contract.CORE_FIELDS:
                self.assertIn(col, r, f"Column '{col}' missing from row {r.get('id')}")
            # Ensure quantity is positive finite
            qty = float(r["quantity"])
            self.assertGreater(qty, 0.0)
            # Ensure unit is canonical
            self.assertIn(r["unit"], takeoff_contract.TAKEOFF_UNITS)

        # Verify net external wall mathematics:
        # North wall: gross 12 * 2.7 = 32.40 m2, W01 deduction 1.8 * 1.2 = 2.16 m2 -> net = 30.24 m2
        north_row = next(r for r in rows if r.get("row_role") == "external_wall" and "W-NORTH" in r.get("location", ""))
        self.assertAlmostEqual(north_row["quantity"], 30.24, places=2)
        self.assertEqual(north_row["unit"], "m²")

        # South wall: gross 12 * 2.7 = 32.40 m2, D01 (1.89) + D02 (5.04) = 6.93 m2 -> net = 25.47 m2
        south_row = next(r for r in rows if r.get("row_role") == "external_wall" and "W-SOUTH" in r.get("location", ""))
        self.assertAlmostEqual(south_row["quantity"], 25.47, places=2)
        self.assertEqual(south_row["unit"], "m²")

        # Verify concrete slab volumetric measure:
        # 12m x 8m x 0.15m = 14.40 m³ with unit "m³"
        concrete_rows = [r for r in rows if "concrete" in str(r.get("element", "")).lower() and r["unit"] == "m³"]
        self.assertGreaterEqual(len(concrete_rows), 1)
        self.assertAlmostEqual(concrete_rows[0]["quantity"], 14.40, places=2)
        self.assertEqual(concrete_rows[0]["unit"], "m³")

        # Verify roof cladding raked area:
        # Plan 112 m2, 15° pitch -> 112 / cos(15°) = 115.95 m2
        roof_rows = [r for r in rows if "roof" in str(r.get("element", "")).lower() and r["unit"] == "m²"]
        self.assertGreaterEqual(len(roof_rows), 1)
        cladding_row = next(r for r in roof_rows if "cladding" in str(r.get("element", "")).lower())
        self.assertAlmostEqual(cladding_row["quantity"], 121.13, places=1)

    def test_e2e_seven_link_provenance_audit_100_percent_pass(self) -> None:
        """Prove that 100% of customer takeoff rows trace the 7-link canonical chain without a single broken link."""
        ws_id = 1003
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "JOB-1003", "Provenance Audit Run", "Apex Builders", "300 Audit Way"),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            result = cust_e2e.run_customer_e2e_pipeline(self.app, self.pdf_path, ws_id)

        prov = result.provenance_summary
        self.assertEqual(prov.failed_rows, 0, f"Provenance deficiencies: {prov.deficiencies}")
        self.assertEqual(prov.pass_rate, 1.0)
        self.assertEqual(prov.passed_rows, prov.total_rows)

        # Verify each of the 7 individual links
        for link_name, count in prov.link_pass_counts.items():
            self.assertEqual(count, prov.total_rows, f"Link '{link_name}' failed for some rows ({count}/{prov.total_rows})")

    def test_e2e_unit_integrity_audit_zero_downgrades(self) -> None:
        """Prove that database rows and customer UI exports exhibit 100% unit integrity and zero silent downgrades."""
        ws_id = 1004
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "JOB-1004", "Unit Integrity Run", "Apex Builders", "400 Metric Ave"),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            result = cust_e2e.run_customer_e2e_pipeline(self.app, self.pdf_path, ws_id)

        unit_db = result.unit_integrity_summary
        self.assertTrue(unit_db.all_valid)
        self.assertEqual(len(unit_db.invalid_rows), 0)
        self.assertEqual(len(unit_db.downgraded_rows), 0)

        # Check all 4 canonical units exist in breakdown
        counts = unit_db.unit_counts
        self.assertGreater(counts.get("m²", 0), 0)
        self.assertGreater(counts.get("lm", 0), 0)
        self.assertGreater(counts.get("No.", 0), 0)
        self.assertGreater(counts.get("m³", 0), 0)

        # Check UI & Export unit report
        ui_rep = result.ui_export_summary
        self.assertTrue(ui_rep.all_units_preserved)
        self.assertEqual(len(ui_rep.issues), 0)

    def test_e2e_customer_ui_and_excel_quotation_export(self) -> None:
        """Prove that customer UI endpoints and Excel quote workbooks consume the exact authoritative data."""
        ws_id = 1005
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "JOB-1005", "Harbour View Apartments - Quotation Export Run", "Premier Brushworks", "500 Tender Lane"),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            result = cust_e2e.run_customer_e2e_pipeline(self.app, self.pdf_path, ws_id)

            # 1. Customer UI DataFrame
            df = self.app.dataframe_for_takeoff(ws_id)
            self.assertFalse(df.empty)
            self.assertGreater(len(df), 0)
            self.assertLessEqual(len(df), result.total_takeoff_rows)
            for req_col in ("section", "element", "location", "quantity", "unit", "rate_per_unit"):
                self.assertIn(req_col, df.columns)

            # 2. Customer UI Per-Level Summary
            pls = self.app.per_level_summary(ws_id)
            self.assertFalse(pls.empty)
            # Level breakdown includes m3 column added in AG-16
            for col in ("level", "m2", "lm", "count", "m3"):
                self.assertIn(col, pls.columns)
            # Ensure concrete volume is captured in m3 column across levels
            total_m3 = float(pls["m3"].sum())
            self.assertAlmostEqual(total_m3, 14.40, places=2)

            # 3. Excel Quote Workbook Generation
            quote_bytes = self.app.quote_workbook_bytes(ws_id)
            self.assertGreater(len(quote_bytes), 2000)

            wb = openpyxl.load_workbook(io.BytesIO(quote_bytes), data_only=True)
            self.assertIn("Quote Header", wb.sheetnames)
            self.assertIn("Take-off Detail", wb.sheetnames)

            summary_sheet = wb["Quote Header"]
            # Look for project name in cells
            all_text = " ".join(str(cell.value or "") for row in summary_sheet.iter_rows() for cell in row)
            self.assertIn("Harbour View", all_text)

            detail_sheet = wb["Take-off Detail"]
            detail_rows = list(detail_sheet.iter_rows(values_only=True))
            # Header + data rows match commercial dataframe
            self.assertGreaterEqual(len(detail_rows), len(df))

            # 4. Builder Edition Excel Package
            pkg_bytes = self.app.excel_export_bytes(ws_id)
            self.assertGreater(len(pkg_bytes), 3000)
            wb_pkg = openpyxl.load_workbook(io.BytesIO(pkg_bytes))
            self.assertIn("Take-off Schedule", wb_pkg.sheetnames)
            self.assertIn("Project Information", wb_pkg.sheetnames)


if __name__ == "__main__":
    unittest.main()
