"""Test Suite for Plumbing Trade Authority Engine (AG-28).

Tests:
1. Sanitary fixtures, tapware, and rough-in service points (No.).
2. Underground sewer drainage pipework (lm) and inspection openings (No.).
3. Hot and cold water reticulation pipework (lm).
4. Vertical soil/waste stacks (lm) and cast-in fire collars (No.).
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

import pb_plumbing_trade_authority as plumbing
import pb_takeoff_row_contract as takeoff_contract


class TestPlumbingTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 1111
        self.now = "2026-10-01T19:30:00"

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

    def test_fixture_calculations(self) -> None:
        """Verify fixture counts and associated rough-in points."""
        wc_spec = plumbing.PlumbingFixtureSpec(
            fixture_type="wc",
            fixture_mark="WC-01",
            description="Back-to-wall toilet suite",
            location="Powder Room",
            count=2,
            source_page="Hydraulic H101",
        )
        items = plumbing.calculate_fixture_items(wc_spec)
        self.assertEqual(len(items), 2)  # Fixture supply/install + rough-in point

        fix_item = items[0]
        self.assertEqual(fix_item.quantity, 2.0)
        self.assertEqual(fix_item.unit, "No.")
        self.assertIn("Back-to-wall", fix_item.element)

        rough_item = items[1]
        self.assertEqual(rough_item.quantity, 2.0)
        self.assertEqual(rough_item.unit, "No.")

    def test_drainage_and_water_pipe_calculations(self) -> None:
        """Verify drainage runs, inspection openings, and hot/cold water reticulation."""
        # 1. Drainage: 35.0 lm of 100mm PVC
        drain_spec = plumbing.PlumbingPipeRunSpec(
            system_type="drainage",
            nominal_dia_mm=100,
            material="PVC-DWV",
            description="Main sewer line to boundary",
            section="Substructure",
            length_m=35.0,
            source_page="Hydraulic Drainage H102",
        )
        drain_items = plumbing.calculate_drainage_items(drain_spec)
        self.assertEqual(len(drain_items), 2)

        pipe_run = drain_items[0]
        self.assertEqual(pipe_run.quantity, 35.0)
        self.assertEqual(pipe_run.unit, "lm")

        ios = drain_items[1]
        self.assertEqual(ios.unit, "No.")
        self.assertEqual(ios.quantity, 2.0)  # 35 / 15 = 2.33 -> 2

        # 2. Cold water: 45.0 lm of 20mm PEX
        cold_spec = plumbing.PlumbingPipeRunSpec(
            system_type="cold_water",
            nominal_dia_mm=20,
            material="PEX-a",
            description="Cold water main line",
            section="Internal",
            length_m=45.0,
            source_page="Hydraulic H103",
        )
        cold_items = plumbing.calculate_water_supply_items(cold_spec)
        self.assertEqual(len(cold_items), 1)
        self.assertEqual(cold_items[0].quantity, 45.0)
        self.assertEqual(cold_items[0].unit, "lm")

    def test_stacks_and_fire_collars(self) -> None:
        """Verify vertical soil stack runs and cast-in slab fire collars."""
        stack_spec = plumbing.PlumbingPipeRunSpec(
            system_type="stack",
            nominal_dia_mm=100,
            material="PVC-DWV",
            description="Sanitary soil stack through shaft",
            section="Structure",
            length_m=9.0,  # 3 storeys
            is_lagged=True,
            source_page="Hydraulic Riser Diagram H201",
        )
        stack_items = plumbing.calculate_stack_and_penetration_items(stack_spec)
        self.assertEqual(len(stack_items), 2)

        stack_run = stack_items[0]
        self.assertEqual(stack_run.quantity, 9.0)
        self.assertEqual(stack_run.unit, "lm")
        self.assertIn("acoustic insulation wrap", stack_run.element)

        collars = stack_items[1]
        self.assertEqual(collars.quantity, 3.0)  # 9.0 / 3.0 = 3 collars
        self.assertEqual(collars.unit, "No.")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that plumbing takeoff rows satisfy 21-field core contract in SQLite."""
        fixtures = [
            plumbing.PlumbingFixtureSpec(
                fixture_type="basin",
                fixture_mark="BASIN-01",
                description="Countertop basin",
                location="Bathroom",
                count=2,
            ),
        ]
        pipes = [
            plumbing.PlumbingPipeRunSpec(
                system_type="drainage",
                nominal_dia_mm=100,
                material="PVC-DWV",
                description="Under-slab drainage",
                length_m=20.0,
            ),
        ]

        rows = plumbing.generate_workspace_plumbing_takeoff(fixtures, pipes, self.ws_id, self.now)
        # Fixtures: 2 items (fixture + rough-in) + Pipes: 2 items (run + IOs) = 4 items
        self.assertEqual(len(rows), 4)

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
