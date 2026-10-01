"""Test Suite for Structural Steel Trade Authority Engine (AG-24).

Tests:
1. Primary steel beams and columns: length (lm), tonnage (t), and coating surface (m²).
2. Secondary purlins and girts (lm).
3. Structural cross-bracing bays (No. / lm).
4. Standard connection, base plate, and cleat allowances (t).
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

import pb_structural_steel_trade_authority as steel
import pb_takeoff_row_contract as takeoff_contract


class TestStructuralSteelTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 707
        self.now = "2026-10-01T17:30:00"

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

    def test_primary_steel_member_calculations(self) -> None:
        """Verify beams and columns: length (lm), tonnage (item), and coating area (m²)."""
        # Beam: 4 No., 310UB40.4, 7.5m long (Total 30m)
        # 40.4 kg/m, surface area 0.99 m²/m
        beam_spec = steel.SteelMemberSpec(
            element_type="beam",
            element_id="B_310UB40",
            section_mark="310UB40.4",
            description="Floor trimmers",
            section="Structure",
            count=4,
            length_m=7.5,
            mass_kg_per_m=40.4,
            surface_area_m2_per_m=0.99,
            coating="Shop primed (zinc phosphate)",
            source_page="Structural S201",
        )
        items = steel.calculate_primary_member_items(beam_spec)
        self.assertEqual(len(items), 3)  # lm run, tonnage item, coating m²

        # 1. Linear run
        lm_item = next(i for i in items if i.unit == "lm")
        self.assertEqual(lm_item.quantity, 30.0)

        # 2. Tonnage: 30m * 40.4 kg/m = 1212.0 kg = 1.212 tonnes
        ton_item = next(i for i in items if i.unit == "item")
        self.assertEqual(ton_item.quantity, 1.212)
        self.assertIn("1212.0 kg", ton_item.notes)

        # 3. Coating: 30m * 0.99 m²/m = 29.7 m²
        coat_item = next(i for i in items if i.unit == "m²")
        self.assertEqual(coat_item.quantity, 29.7)
        self.assertIn("Shop primed", coat_item.finish_system)

        # Column: 6 No., 200UC46.2, 3.5m high (Total 21m)
        # 46.2 kg/m, surface area 1.18 m²/m
        col_spec = steel.SteelMemberSpec(
            element_type="column",
            element_id="C_200UC46",
            section_mark="200UC46.2",
            description="Perimeter columns",
            section="Structure",
            count=6,
            length_m=3.5,
            mass_kg_per_m=46.2,
            surface_area_m2_per_m=1.18,
            coating="Hot-dip galvanized (HDG)",
            source_page="Structural S201",
        )
        col_items = steel.calculate_primary_member_items(col_spec)
        self.assertEqual(len(col_items), 3)
        col_lm = next(i for i in col_items if i.unit == "lm")
        self.assertEqual(col_lm.quantity, 21.0)
        col_ton = next(i for i in col_items if i.unit == "item")
        # 21m * 46.2 kg/m = 970.2 kg = 0.970 tonnes
        self.assertEqual(col_ton.quantity, 0.970)

    def test_purlins_girts_and_bracing(self) -> None:
        """Verify cold-formed purlins, girts, and structural cross-bracing."""
        # Purlins: 10 runs of 18m C15015 (Total 180m, 3.6 kg/m)
        purlin_spec = steel.SteelMemberSpec(
            element_type="purlin",
            element_id="PURLIN_01",
            section_mark="C15015",
            description="Roof purlins",
            section="Roof",
            count=10,
            length_m=18.0,
            mass_kg_per_m=3.6,
            source_page="Structural S202",
        )
        purlin_items = steel.calculate_purlin_and_girt_items(purlin_spec)
        self.assertEqual(len(purlin_items), 1)
        self.assertEqual(purlin_items[0].quantity, 180.0)
        self.assertEqual(purlin_items[0].unit, "lm")
        # 180 * 3.6 = 648 kg = 0.648 tonnes
        self.assertIn("0.648 t", purlin_items[0].notes)

        # Bracing: 4 bays of 20mm round rod cross-bracing
        bracing_spec = steel.SteelMemberSpec(
            element_type="bracing",
            element_id="BRACE_01",
            section_mark="20mm Round Bar Cross-Bracing",
            description="Roof tie bracing",
            section="Roof",
            count=4,
            length_m=0.0,
            source_page="Structural S202",
        )
        bracing_items = steel.calculate_bracing_items(bracing_spec)
        self.assertEqual(len(bracing_items), 1)
        self.assertEqual(bracing_items[0].quantity, 4.0)
        self.assertEqual(bracing_items[0].unit, "No.")

    def test_connection_fittings_allowance(self) -> None:
        """Verify standard 10% connection allowance calculation."""
        primary_specs = [
            steel.SteelMemberSpec(
                element_type="beam",
                element_id="B1",
                section_mark="310UB40.4",
                description="Beam",
                count=4,
                length_m=10.0,  # 40m * 40.4 kg/m = 1616 kg = 1.616 t
                mass_kg_per_m=40.4,
            ),
            steel.SteelMemberSpec(
                element_type="column",
                element_id="C1",
                section_mark="200UC46.2",
                description="Column",
                count=4,
                length_m=5.0,   # 20m * 46.2 kg/m = 924 kg = 0.924 t
                mass_kg_per_m=46.2,
            ),
        ]
        # Total primary = 1.616 + 0.924 = 2.540 tonnes
        # 10% connection allowance = 0.254 tonnes
        conn_row = steel.calculate_connection_fittings_allowance(
            primary_specs, self.ws_id, self.now, allowance_pct=10.0
        )
        self.assertIsNotNone(conn_row)
        self.assertEqual(conn_row["quantity"], 0.25)
        self.assertEqual(conn_row["unit"], "item")
        self.assertIn("10.0% connection allowance", conn_row["notes"])

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that steel takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            steel.SteelMemberSpec(
                element_type="beam",
                element_id="BEAM_01",
                section_mark="310UB40.4",
                description="Beams",
                count=2,
                length_m=8.0,
                mass_kg_per_m=40.4,
                surface_area_m2_per_m=0.99,
            ),
            steel.SteelMemberSpec(
                element_type="purlin",
                element_id="PURLIN_01",
                section_mark="C15015",
                description="Purlins",
                count=5,
                length_m=12.0,
                mass_kg_per_m=3.6,
            ),
        ]

        rows = steel.generate_workspace_steel_takeoff(specs, self.ws_id, self.now, include_connections=True)
        # 3 rows from beam + 1 from purlin + 1 from connections = 5 rows
        self.assertEqual(len(rows), 5)

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
