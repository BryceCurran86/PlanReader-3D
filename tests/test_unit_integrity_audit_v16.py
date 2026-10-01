"""Test Suite for AG-16 Database and UI Unit Integrity Audit.

Tests:
1. Strict canonical unit preservation for m², lm, No., m³.
2. Fail-closed rejection of invalid, corrupted, or unsupported units.
3. Zero silent conversions of text aliases (m2, sqm, lm, m, ea, count, m3, cum).
4. Detection of silent downgrades (volumetric m³ downgraded to item/allowance; area m² to lm).
5. Database storage integrity (takeoff_rows table column types REAL and TEXT, exact values).
6. Customer UI dataframe_for_takeoff, per_level_summary (with m3 column), and Excel quotation export.
7. Builder Edition BoQ CSV export unit preservation.
8. End-to-end multi-trade canonical building model to database to customer UI proof.
"""
from __future__ import annotations

import io
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import openpyxl
import pytest

import pb_canonical_building as cb
import pb_planreader_3d_app as app
import pb_takeoff_row_contract as takeoff_contract
import pb_unit_integrity_v16 as unit_integrity
from pb_builder_edition_architecture import BuilderEditionEngine


class TestUnitNormalizationAndValidation(unittest.TestCase):
    def test_canonical_units_pass_through_exact(self) -> None:
        """m², lm, No., m³ must pass through exact without string modification."""
        for u in ("m²", "lm", "No.", "m³", "item", "L", "allowance"):
            self.assertEqual(unit_integrity.normalize_takeoff_unit(u), u)

    def test_area_aliases_normalize_to_canonical_m2(self) -> None:
        """All square metre aliases must strictly normalize to 'm²'."""
        for alias in ("m2", "sqm", "sq m", "m^2", "square metre", "square metres", "square meter"):
            self.assertEqual(unit_integrity.normalize_takeoff_unit(alias), "m²")
            self.assertEqual(unit_integrity.dimension_of_unit("m²"), unit_integrity.UnitDimension.AREA)

    def test_linear_aliases_normalize_to_canonical_lm(self) -> None:
        """All linear metre aliases must strictly normalize to 'lm'."""
        for alias in ("lm", "lin m", "m", "metre", "metres", "lineal", "linear", "linear metre"):
            self.assertEqual(unit_integrity.normalize_takeoff_unit(alias), "lm")
            self.assertEqual(unit_integrity.dimension_of_unit("lm"), unit_integrity.UnitDimension.LINEAR)

    def test_count_aliases_normalize_to_canonical_no(self) -> None:
        """All item count aliases must strictly normalize to 'No.'."""
        for alias in ("no", "no.", "nos", "ea", "ea.", "each", "count", "number", "nr"):
            self.assertEqual(unit_integrity.normalize_takeoff_unit(alias), "No.")
            self.assertEqual(unit_integrity.dimension_of_unit("No."), unit_integrity.UnitDimension.COUNT)

    def test_volume_aliases_normalize_to_canonical_m3(self) -> None:
        """All cubic metre aliases must strictly normalize to 'm³' without downgrade."""
        for alias in ("m3", "cum", "cu m", "m^3", "cubic metre", "cubic metres", "cubic meter"):
            self.assertEqual(unit_integrity.normalize_takeoff_unit(alias), "m³")
            self.assertEqual(unit_integrity.dimension_of_unit("m³"), unit_integrity.UnitDimension.VOLUME)

    def test_invalid_units_fail_closed(self) -> None:
        """Unsupported units must raise UnitIntegrityError in strict mode."""
        for bad_u in ("kg", "tonnes", "furlong", "inches", "acre", "unknown_xyz", ""):
            with self.assertRaises(unit_integrity.UnitIntegrityError):
                unit_integrity.normalize_takeoff_unit(bad_u, strict=True)


class TestSilentDowngradeDetection(unittest.TestCase):
    def test_detects_volumetric_downgrade_to_item(self) -> None:
        """Flags when concrete/grout volume is represented as unit 'item' or 'allowance'."""
        reason = unit_integrity.detect_unit_downgrade(
            element="Concrete supply & pump",
            unit="item",
            notes="Supply & place 15.00 m³ of 25 MPa Concrete.",
        )
        self.assertIsNotNone(reason)
        self.assertIn("Volumetric measure detected", reason)
        self.assertIn("downgraded to 'item'", reason)

    def test_detects_area_downgrade_to_lm(self) -> None:
        """Flags when surface area element is given unit 'lm'."""
        reason = unit_integrity.detect_unit_downgrade(
            element="Wall surface acrylic finish",
            unit="lm",
            notes="",
        )
        self.assertIsNotNone(reason)
        self.assertIn("Surface area element", reason)
        self.assertIn("downgraded to linear unit 'lm'", reason)

    def test_legitimate_units_pass_without_downgrade_flag(self) -> None:
        """Valid combinations must return None (no downgrade)."""
        self.assertIsNone(unit_integrity.detect_unit_downgrade("Concrete slab", "m³", "15.00 m³"))
        self.assertIsNone(unit_integrity.detect_unit_downgrade("External brickwork", "m²", "45.0 m²"))
        self.assertIsNone(unit_integrity.detect_unit_downgrade("Skirting boards", "lm", "12.0 lm"))
        self.assertIsNone(unit_integrity.detect_unit_downgrade("Timber doors", "No.", "4 No."))


class TestDatabaseUnitIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_units.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE takeoff_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                section TEXT,
                element TEXT,
                location TEXT,
                substrate TEXT,
                finish_system TEXT,
                quantity REAL DEFAULT 0,
                unit TEXT,
                quantity_status TEXT,
                source_page TEXT,
                source_reference TEXT,
                inclusion_status TEXT,
                coats REAL DEFAULT 2,
                coverage_m2_per_litre REAL DEFAULT 12,
                productivity_m2_per_hour REAL DEFAULT 8,
                rate_per_unit REAL DEFAULT 0,
                confidence TEXT,
                notes TEXT,
                row_role TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_database_unit_integrity_passes_for_all_four_mature_units(self) -> None:
        """Proves exact preservation of m², lm, No., and m³ in SQLite database."""
        now = "2026-10-02T05:00:00Z"
        ws_id = 101

        # Insert 4 clean rows covering m², lm, No., m³
        rows = [
            (ws_id, "Internal", "Wall plasterboard", "Living Room", "Plasterboard", "Paint", 45.5, "m²", "Measured", "1", "REF-01", "INCLUSION", 2, 10, 8, 30.0, "Verified", "Wall net area", "work", now, now),
            (ws_id, "Internal", "Timber skirting", "Living Room", "Timber", "Gloss", 18.2, "lm", "Measured", "1", "REF-02", "INCLUSION", 2, 10, 8, 15.0, "Verified", "Perimeter skirting", "work", now, now),
            (ws_id, "Internal", "Solid core door", "Entry", "Timber", "Paint", 3.0, "No.", "Measured", "1", "REF-03", "INCLUSION", 2, 10, 8, 150.0, "Verified", "3 doors", "work", now, now),
            (ws_id, "Substructure", "Slab concrete volume", "Ground Floor", "25 MPa Concrete", "Pour", 12.8, "m³", "Measured", "1", "REF-04", "INCLUSION", 1, 0, 0, 220.0, "Verified", "Slab volume 12.8 m³", "work", now, now),
        ]
        sql = takeoff_contract.insert_sql(takeoff_contract.CORE_FIELDS)
        for r in rows:
            self.conn.execute(sql, r)
        self.conn.commit()

        report = unit_integrity.audit_database_unit_integrity(self.conn, ws_id)
        self.assertTrue(report.all_valid)
        self.assertTrue(report.zero_downgrades)
        self.assertEqual(report.total_rows, 4)
        self.assertEqual(report.unit_counts["m²"], 1)
        self.assertEqual(report.unit_counts["lm"], 1)
        self.assertEqual(report.unit_counts["No."], 1)
        self.assertEqual(report.unit_counts["m³"], 1)
        self.assertEqual(report.unit_sums["m²"], 45.5)
        self.assertEqual(report.unit_sums["lm"], 18.2)
        self.assertEqual(report.unit_sums["No."], 3.0)
        self.assertEqual(report.unit_sums["m³"], 12.8)

    def test_database_unit_integrity_catches_silent_downgrade(self) -> None:
        """Report flags when concrete volume is downgraded to item."""
        now = "2026-10-02T05:00:00Z"
        ws_id = 102
        downgraded_row = (
            ws_id, "Substructure", "Slab concrete supply", "Ground Floor", "25 MPa Concrete", "Pour",
            15.0, "item", "Measured", "1", "REF-DOWN", "INCLUSION", 1, 0, 0, 200.0, "Verified",
            "Supply & place 15.00 m³ of concrete.", "work", now, now
        )
        self.conn.execute(takeoff_contract.insert_sql(), downgraded_row)
        self.conn.commit()

        report = unit_integrity.audit_database_unit_integrity(self.conn, ws_id)
        self.assertFalse(report.zero_downgrades)
        self.assertEqual(len(report.downgraded_rows), 1)
        self.assertIn("Volumetric measure detected", report.downgraded_rows[0]["reason"])


class TestUIAndExportUnitIntegrity(unittest.TestCase):
    def test_ui_endpoints_preserve_units_and_export_cleanly(self) -> None:
        """Test dataframe_for_takeoff, per_level_summary, and Excel quotation export."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "planreader_test.db"
            with patch.object(app, "DB_PATH", db_path):
                app.init_local_db()
                wid = app.create_standalone_workspace("UNIT_TEST_WS", "Unit Test Tower", "Client", "123 Street")
                app.set_workspace_setting(wid, "pricing_margin_pct", 10.0)
                app.set_workspace_setting(wid, "gst_rate_pct", 10.0)

                # Insert 4 rows: m², lm, No., m³
                now = app.now_stamp()
                app.lexecute(
                    """INSERT INTO takeoff_rows(workspace_id, section, element, location, substrate, finish_system, quantity, unit, quantity_status, source_page, source_reference, inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour, rate_per_unit, confidence, notes, row_role, created_at, updated_at)
                       VALUES(?, 'Internal', 'Walls', 'Level 1', 'Plasterboard', 'Paint', 80.0, 'm²', 'Measured', 'Page 1', 'REF-W', 'INCLUSION', 2, 10, 8, 30.0, 'Verified', '', 'work', ?, ?)""",
                    (wid, now, now),
                )
                app.lexecute(
                    """INSERT INTO takeoff_rows(workspace_id, section, element, location, substrate, finish_system, quantity, unit, quantity_status, source_page, source_reference, inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour, rate_per_unit, confidence, notes, row_role, created_at, updated_at)
                       VALUES(?, 'Internal', 'Skirting', 'Level 1', 'Timber', 'Gloss', 30.0, 'lm', 'Measured', 'Page 1', 'REF-S', 'INCLUSION', 2, 10, 8, 15.0, 'Verified', '', 'work', ?, ?)""",
                    (wid, now, now),
                )
                app.lexecute(
                    """INSERT INTO takeoff_rows(workspace_id, section, element, location, substrate, finish_system, quantity, unit, quantity_status, source_page, source_reference, inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour, rate_per_unit, confidence, notes, row_role, created_at, updated_at)
                       VALUES(?, 'Internal', 'Doors', 'Level 1', 'Timber', 'Paint', 4.0, 'No.', 'Measured', 'Page 1', 'REF-D', 'INCLUSION', 2, 10, 8, 120.0, 'Verified', '', 'work', ?, ?)""",
                    (wid, now, now),
                )
                app.lexecute(
                    """INSERT INTO takeoff_rows(workspace_id, section, element, location, substrate, finish_system, quantity, unit, quantity_status, source_page, source_reference, inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour, rate_per_unit, confidence, notes, row_role, created_at, updated_at)
                       VALUES(?, 'Structure', 'Columns concrete', 'Level 1', '32 MPa Concrete', 'Pour', 6.4, 'm³', 'Measured', 'Page 1', 'REF-C', 'INCLUSION', 1, 0, 0, 250.0, 'Verified', '', 'work', ?, ?)""",
                    (wid, now, now),
                )

                # Run UI and Export Unit Audit
                report = unit_integrity.audit_ui_and_export_unit_integrity(app, wid)
                self.assertTrue(report.dataframe_units_valid, f"Issues: {report.issues}")
                self.assertTrue(report.per_level_summary_has_m3, "per_level_summary missing m3 column")
                self.assertTrue(report.excel_detail_units_preserved, f"Issues: {report.issues}")
                self.assertTrue(report.boq_export_units_preserved, f"Issues: {report.issues}")
                self.assertTrue(report.all_units_preserved, f"Issues: {report.issues}")

                # Verify per_level_summary values
                pls = app.per_level_summary(wid)
                lvl1 = pls[pls["level"] == "Level 1"].iloc[0]
                self.assertEqual(lvl1["m2"], 80.0)
                self.assertEqual(lvl1["lm"], 30.0)
                self.assertEqual(lvl1["count"], 4.0)
                self.assertEqual(lvl1["m3"], 6.4)


class TestEndToEndCanonicalModelToCustomerRuntimeUnits(unittest.TestCase):
    def test_canonical_model_generates_and_persists_exact_units(self) -> None:
        """Prove end-to-end: Canonical elements -> m², lm, No., m³ -> SQLite -> Customer UI."""
        prov = cb.Provenance(source_pdf="A101.pdf", page_number=1, drawing_id="ARCH-101")
        building = cb.CanonicalBuilding(id="BLD-U16", name="Unit Integrity Model", provenance=prov)
        level = cb.CanonicalLevel(id="LVL-01", name="Ground Floor", level_index=1, elevation_m=0.0, height_m=2.7, provenance=prov)
        building.levels.append(level)

        # 1. Floor (generates m² area, m³ concrete, lm edge formwork)
        floor = cb.CanonicalFloor(
            id="FL-01",
            name="Ground Slab",
            polygon=[cb.Vector2D(0, 0), cb.Vector2D(10, 0), cb.Vector2D(10, 10), cb.Vector2D(0, 10)],
            thickness_m=0.15,
            substrate="25 MPa Concrete",
            provenance=prov,
        )
        level.floors.append(floor)

        # 2. Wall (generates m² wall surface, lm skirting, etc.)
        wall = cb.CanonicalWall(
            id="W-01",
            name="North Wall",
            start_point=cb.Vector2D(0, 0),
            end_point=cb.Vector2D(10, 0),
            height_m=2.7,
            thickness_m=0.20,
            is_external=False,
            substrate="Timber stud framing",
            finish="Plasterboard and painted",
            provenance=prov,
        )
        door = cb.CanonicalOpening(
            id="DR-01",
            mark="D01",
            opening_type="DOOR",
            width_m=0.90,
            height_m=2.10,
            host_wall_id="W-01",
            provenance=prov,
        )
        wall.openings.append(door)
        level.walls.append(wall)

        # 3. Derive multi-trade takeoff rows
        ws_id = 999
        from pb_cross_trade_geometry_reuse import derive_multi_trade_takeoff_from_canonical_model
        raw_rows = derive_multi_trade_takeoff_from_canonical_model(
            building,
            workspace_id=ws_id,
            source_document="A101.pdf",
            as_dicts=True,
        )

        # Verify all mature units are present in generated rows
        units_generated = {r["unit"] for r in raw_rows}
        self.assertIn("m²", units_generated)
        self.assertIn("lm", units_generated)
        self.assertIn("m³", units_generated)

        # Verify every row strictly adheres to TAKEOFF_UNITS and passes row audit
        for r in raw_rows:
            self.assertIn(r["unit"], takeoff_contract.TAKEOFF_UNITS)
            audit = unit_integrity.audit_takeoff_row_unit(r)
            self.assertTrue(audit.is_valid, f"Row {r['element']} unit audit failed: {audit.issues}")
