"""Test Suite for Concreting Trade Authority Engine (AG-21).

Tests:
1. Ground slab & suspended slab trade calculations.
2. Strip footing, pad footing, and bored pier calculations.
3. RC column count, concrete volume, and formwork area.
4. RC beam run, concrete volume, and 3-sided formwork area.
5. RC stairs flights, steps, and formwork.
6. Strict compliance with 21-field core takeoff row contract.
7. End-to-end SQLite insertion and round-trip verification.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_concreting_trade_authority as concrete
import pb_takeoff_row_contract as takeoff_contract


class TestConcretingTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 404
        self.now = "2026-10-01T16:00:00"

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

    def test_slab_concrete_trade_derivation(self) -> None:
        """Verify ground-bearing and suspended slab trade item calculations."""
        # 1. Ground slab: 150 m², 100mm thick, 50m perimeter
        ground_spec = concrete.ConcreteElementSpec(
            element_type="slab",
            element_id="SLAB_GF_01",
            section="Substructure",
            description="Ground floor slab",
            area_m2=150.0,
            thickness_m=0.100,
            perimeter_lm=50.0,
            is_suspended=False,
            source_page="Structural S101",
        )
        items = concrete.calculate_slab_concrete_items(ground_spec)
        self.assertEqual(len(items), 4)  # Area, supply/pump, edge formwork, DPM

        area_item = next(i for i in items if i.unit == "m²" and i.row_role == "floor_area")
        self.assertEqual(area_item.quantity, 150.0)
        self.assertIn("Concrete volume: 15.00 m³", area_item.notes)

        pump_item = next(i for i in items if i.unit == "item")
        self.assertEqual(pump_item.quantity, 15.0)  # 15 m³
        self.assertIn("15.00 m³", pump_item.notes)

        edge_form = next(i for i in items if i.unit == "lm")
        self.assertEqual(edge_form.quantity, 50.0)
        self.assertIn("5.00 m²", edge_form.notes)  # 50m * 0.1m = 5m²

        dpm_item = next(i for i in items if "Damp-proof membrane" in i.element)
        self.assertEqual(dpm_item.quantity, 165.0)  # 150 * 1.10 = 165 m²

        # 2. Suspended slab: 120 m², 200mm thick, suspended
        susp_spec = concrete.ConcreteElementSpec(
            element_type="slab",
            element_id="SLAB_L1_01",
            section="Structure",
            description="Level 1 suspended slab",
            area_m2=120.0,
            thickness_m=0.200,
            perimeter_lm=44.0,
            is_suspended=True,
            source_page="Structural S102",
        )
        susp_items = concrete.calculate_slab_concrete_items(susp_spec)
        self.assertEqual(len(susp_items), 4)  # Area, supply, edge form, soffit form

        soffit_form = next(i for i in susp_items if "soffit formwork" in i.element)
        self.assertEqual(soffit_form.quantity, 120.0)
        self.assertEqual(soffit_form.unit, "m²")

    def test_footings_and_piers_derivation(self) -> None:
        """Verify strip footings, pad footings, and bored piers."""
        # Strip footing: 40m long, 0.4m wide, 0.5m deep
        strip_spec = concrete.ConcreteElementSpec(
            element_type="footing_strip",
            element_id="SF_01",
            section="Substructure",
            description="Perimeter strip footing",
            length_m=40.0,
            width_m=0.400,
            thickness_m=0.500,
            source_page="Structural S101",
        )
        strip_items = concrete.calculate_footing_concrete_items(strip_spec)
        self.assertEqual(len(strip_items), 2)
        strip_lm = next(i for i in strip_items if i.unit == "lm")
        self.assertEqual(strip_lm.quantity, 40.0)
        self.assertIn("8.00 m³", strip_lm.notes)  # 40 * 0.4 * 0.5 = 8.0 m³

        # Pad footings: 6 No., 1.2m x 1.2m x 0.6m
        pad_spec = concrete.ConcreteElementSpec(
            element_type="footing_pad",
            element_id="PF_01",
            section="Substructure",
            description="Column pad footings",
            count=6,
            length_m=1.2,
            width_m=1.2,
            thickness_m=0.6,
            source_page="Structural S101",
        )
        pad_items = concrete.calculate_footing_concrete_items(pad_spec)
        pad_count = next(i for i in pad_items if i.unit == "No.")
        self.assertEqual(pad_count.quantity, 6.0)
        self.assertIn("5.18 m³", pad_count.notes)  # 6 * 1.2 * 1.2 * 0.6 = 5.184 m³

        # Bored piers: 8 No., 450mm dia x 3.0m deep
        pier_spec = concrete.ConcreteElementSpec(
            element_type="bored_pier",
            element_id="BP_01",
            section="Substructure",
            description="Bored piers to bedrock",
            count=8,
            width_m=0.450,
            height_m=3.0,
            source_page="Structural S101",
        )
        pier_items = concrete.calculate_footing_concrete_items(pier_spec)
        pier_count = next(i for i in pier_items if i.unit == "No.")
        self.assertEqual(pier_count.quantity, 8.0)
        # 8 * pi * 0.225^2 * 3.0 = 3.82 m³
        self.assertIn("3.82 m³", pier_count.notes)

    def test_columns_beams_and_stairs_derivation(self) -> None:
        """Verify RC columns, beams, and stairs calculations."""
        # Columns: 4 No., 0.35m x 0.35m x 2.7m
        col_spec = concrete.ConcreteElementSpec(
            element_type="column",
            element_id="COL_01",
            section="Structure",
            description="Ground floor RC columns",
            count=4,
            length_m=0.35,
            width_m=0.35,
            height_m=2.7,
            source_page="Structural S102",
        )
        col_items = concrete.calculate_column_concrete_items(col_spec)
        self.assertEqual(len(col_items), 2)
        col_no = next(i for i in col_items if i.unit == "No.")
        self.assertEqual(col_no.quantity, 4.0)
        col_form = next(i for i in col_items if i.unit == "m²")
        # 4 * (2 * (0.35 + 0.35)) * 2.7 = 15.12 m²
        self.assertEqual(col_form.quantity, 15.12)

        # Beams: 25m long, 0.4m wide, 0.6m deep
        beam_spec = concrete.ConcreteElementSpec(
            element_type="beam",
            element_id="BEAM_01",
            section="Structure",
            description="Transfer beams",
            length_m=25.0,
            width_m=0.400,
            thickness_m=0.600,
            source_page="Structural S102",
        )
        beam_items = concrete.calculate_beam_concrete_items(beam_spec)
        self.assertEqual(len(beam_items), 2)
        beam_lm = next(i for i in beam_items if i.unit == "lm")
        self.assertEqual(beam_lm.quantity, 25.0)
        beam_form = next(i for i in beam_items if i.unit == "m²")
        # 25 * (0.4 + 2 * 0.6) = 25 * 1.6 = 40.0 m²
        self.assertEqual(beam_form.quantity, 40.0)

        # Stairs: 2 flights, 2.7m storey height
        stair_spec = concrete.ConcreteElementSpec(
            element_type="stairs",
            element_id="STAIR_01",
            section="Structure",
            description="Core stairs",
            count=2,
            width_m=1.0,
            height_m=2.7,
            source_page="Structural S102",
        )
        stair_items = concrete.calculate_stairs_concrete_items(stair_spec)
        stair_flights = next(i for i in stair_items if i.unit == "No.")
        self.assertEqual(stair_flights.quantity, 2.0)
        stair_form = next(i for i in stair_items if i.unit == "m²")
        self.assertTrue(stair_form.quantity > 0.0)

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that concrete takeoff rows strictly satisfy 21-field core contract in SQLite."""
        specs = [
            concrete.ConcreteElementSpec(
                element_type="slab",
                element_id="SLAB_GF",
                section="Substructure",
                description="Ground slab",
                area_m2=100.0,
                thickness_m=0.100,
                perimeter_lm=40.0,
            ),
            concrete.ConcreteElementSpec(
                element_type="footing_strip",
                element_id="FOOTING_01",
                section="Substructure",
                description="Strip footing",
                length_m=30.0,
                width_m=0.400,
                thickness_m=0.450,
            ),
            concrete.ConcreteElementSpec(
                element_type="column",
                element_id="COL_01",
                section="Structure",
                description="Columns",
                count=4,
                length_m=0.35,
                width_m=0.35,
                height_m=2.7,
            ),
        ]

        rows = concrete.generate_workspace_concrete_takeoff(specs, self.ws_id, self.now)
        self.assertGreater(len(rows), 5)

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
            # Core 21 fields (plus autoincrement id = 22 columns)
            self.assertEqual(len(cols), 22)

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
