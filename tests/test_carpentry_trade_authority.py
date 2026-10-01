"""Test Suite for Carpentry Trade Authority Engine (AG-27).

Tests:
1. Wall framing: frame area (m²), wall plates (lm), studs (No.), noggings (lm).
2. Subfloor framing: structural particleboard flooring (m²) and joists (lm).
3. Roof framing: prefabricated trusses (No.) and battens (lm).
4. External cladding and eaves: cladding (m²), eaves lining (m²), and fascia (lm).
5. Strict compliance with 21-field core takeoff row contract in SQLite.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_carpentry_trade_authority as carpentry
import pb_takeoff_row_contract as takeoff_contract


class TestCarpentryTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 1010
        self.now = "2026-10-01T19:00:00"

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """CREATE TABLE takeoff_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    section TEXT,
                    element TEXT,
                    location TEXT,
                    substrate TEXT,
                    finish_system TEXT,
                    quantity REAL,
                    unit TEXT,
                    quantity_status TEXT,
                    source_page TEXT,
                    source_reference TEXT,
                    inclusion_status TEXT,
                    coats INTEGER,
                    coverage_m2_per_litre REAL,
                    productivity_m2_per_hour REAL,
                    rate_per_unit REAL,
                    confidence TEXT,
                    notes TEXT,
                    row_role TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )"""
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self) -> None:
        gc.collect()
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except OSError:
            pass

    def test_wall_framing_calculations(self) -> None:
        """Verify wall frame area, wall plates (3x length), studs count, and noggings."""
        spec = carpentry.CarpentryElementSpec(
            element_type="wall_frame",
            element_id="FRAME_EXT_N",
            description="North external stud wall",
            section="External",
            length_m=12.0,
            height_m=2.7,
            stud_spacing_mm=450,
            openings=[{"width": 1.8, "height": 1.2}],
            source_page="Framing Plan A102",
        )
        items = carpentry.calculate_wall_framing_items(spec)
        self.assertEqual(len(items), 4)  # Frame m², plates lm, studs No., noggings lm

        # 1. Gross framing area: 12.0 * 2.7 = 32.4 m²
        frame_area = items[0]
        self.assertEqual(frame_area.quantity, 32.4)
        self.assertEqual(frame_area.unit, "m²")
        self.assertEqual(frame_area.row_role, "external_wall")

        # 2. Plates: 3 * 12.0 = 36.0 lm
        plates = items[1]
        self.assertEqual(plates.quantity, 36.0)
        self.assertEqual(plates.unit, "lm")

        # 3. Studs count: (12 / 0.45 = 27) + 1 = 28 base + 4 jamb/corner = 32 studs
        studs = items[2]
        self.assertEqual(studs.quantity, 32.0)
        self.assertEqual(studs.unit, "No.")

        # 4. Noggings: 12.0 lm
        noggings = items[3]
        self.assertEqual(noggings.quantity, 12.0)
        self.assertEqual(noggings.unit, "lm")

    def test_subfloor_and_roof_framing(self) -> None:
        """Verify structural sheet flooring, floor joists, roof trusses, and battens."""
        # Subfloor: 80 m² floor
        sub_spec = carpentry.CarpentryElementSpec(
            element_type="subfloor",
            element_id="FLOOR_L1",
            description="First floor joists and subfloor",
            area_m2=80.0,
            source_page="Framing Plan A103",
        )
        sub_items = carpentry.calculate_subfloor_framing_items(sub_spec)
        self.assertEqual(len(sub_items), 2)
        sheet_floor = sub_items[0]
        self.assertEqual(sheet_floor.quantity, 80.0)
        self.assertEqual(sheet_floor.row_role, "floor_area")
        joists = sub_items[1]
        self.assertEqual(joists.quantity, 192.0)  # 80 * 2.4 = 192 lm

        # Roof: 15m run, 8m span (120 m² roof plane)
        roof_spec = carpentry.CarpentryElementSpec(
            element_type="roof_frame",
            element_id="ROOF_01",
            description="Truss roof layout",
            length_m=15.0,
            width_m=8.0,
            source_page="Roof Truss Layout S301",
        )
        roof_items = carpentry.calculate_roof_framing_items(roof_spec)
        self.assertEqual(len(roof_items), 2)
        # 15 / 0.9 + 1 = 18 trusses
        trusses = roof_items[0]
        self.assertEqual(trusses.quantity, 18.0)
        self.assertEqual(trusses.unit, "No.")
        battens = roof_items[1]
        self.assertEqual(battens.quantity, 150.0)  # 120 * 1.25 = 150 lm

    def test_cladding_and_eaves(self) -> None:
        """Verify weatherboard cladding, eaves soffit lining, and timber fascia."""
        # Cladding: 50 m² gross - 8 m² openings = 42 m² net
        clad_spec = carpentry.CarpentryElementSpec(
            element_type="cladding",
            element_id="CLAD_EXT",
            description="Upper storey FC weatherboards",
            area_m2=50.0,
            openings=[{"area": 8.0}],
            source_page="Architectural Elevations A201",
        )
        clad_items = carpentry.calculate_eaves_and_cladding_items(clad_spec)
        self.assertEqual(len(clad_items), 1)
        self.assertEqual(clad_items[0].quantity, 42.0)
        self.assertEqual(clad_items[0].unit, "m²")

        # Eaves: 40 lm perimeter, 0.60m overhang
        eave_spec = carpentry.CarpentryElementSpec(
            element_type="eaves",
            element_id="EAVES_01",
            description="Perimeter roof overhang",
            perimeter_lm=40.0,
            overhang_width_m=0.60,
            source_page="Architectural Roof Plan A104",
        )
        eave_items = carpentry.calculate_eaves_and_cladding_items(eave_spec)
        self.assertEqual(len(eave_items), 2)
        # Eave lining: 40 * 0.60 = 24.0 m²
        lining = eave_items[0]
        self.assertEqual(lining.quantity, 24.0)
        self.assertEqual(lining.unit, "m²")
        # Fascia: 40.0 lm
        fascia = eave_items[1]
        self.assertEqual(fascia.quantity, 40.0)
        self.assertEqual(fascia.unit, "lm")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that carpentry takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            carpentry.CarpentryElementSpec(
                element_type="wall_frame",
                element_id="FRAME_01",
                description="Internal partition frame",
                section="Internal",
                length_m=10.0,
                height_m=2.7,
            ),
            carpentry.CarpentryElementSpec(
                element_type="subfloor",
                element_id="SUBFLOOR_01",
                description="First floor substrate",
                area_m2=50.0,
            ),
        ]

        rows = carpentry.generate_workspace_carpentry_takeoff(specs, self.ws_id, self.now)
        # Frame: 4 rows + Subfloor: 2 rows = 6 rows
        self.assertEqual(len(rows), 6)

        insert_sql = """
            INSERT INTO takeoff_rows (
                workspace_id, section, element, location, substrate, finish_system,
                quantity, unit, quantity_status, source_page, source_reference,
                inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                rate_per_unit, confidence, notes, row_role, created_at, updated_at
            ) VALUES (
                :workspace_id, :section, :element, :location, :substrate, :finish_system,
                :quantity, :unit, :quantity_status, :source_page, :source_reference,
                :inclusion_status, :coats, :coverage_m2_per_litre, :productivity_m2_per_hour,
                :rate_per_unit, :confidence, :notes, :row_role, :created_at, :updated_at
            )
        """

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(insert_sql, rows)
            conn.commit()

            cur = conn.execute("SELECT * FROM takeoff_rows WHERE workspace_id=?", (self.ws_id,))
            db_rows = cur.fetchall()
            self.assertEqual(len(db_rows), len(rows))

            cols = [d[0] for d in cur.description]
            self.assertEqual(len(cols), 22)  # id + 21 core fields

            for r in db_rows:
                row_dict = dict(zip(cols, r))
                self.assertEqual(row_dict["workspace_id"], self.ws_id)
                self.assertIn(row_dict["unit"], takeoff_contract.TAKEOFF_UNITS)
                self.assertIn(row_dict["inclusion_status"], ("INCLUSION", "PROVISIONAL"))
                self.assertTrue(row_dict["quantity"] > 0.0)
                self.assertTrue(len(row_dict["notes"]) > 5)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
