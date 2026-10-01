"""Test Suite for Formwork Trade Authority Engine (AG-22).

Tests:
1. Suspended soffit formwork, drop panels, and cantilevers.
2. Slab edge formwork by depth band.
3. Double-faced concrete wall formwork and window/door blockouts.
4. Rectangular and circular column formwork with propping allowances.
5. Beam sides and soffit formwork.
6. Stepdown rebates and service penetrations.
7. Strict compliance with 21-field core takeoff row contract in SQLite.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_formwork_trade_authority as formwork
import pb_takeoff_row_contract as takeoff_contract


class TestFormworkTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 505
        self.now = "2026-10-01T16:30:00"

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

    def test_soffit_formwork_calculations(self) -> None:
        """Verify suspended flat soffit, cantilever, and drop panel formwork."""
        # 1. Standard flat soffit: 200 m², 3.0m propping
        spec1 = formwork.FormworkElementSpec(
            element_type="soffit",
            element_id="SOFFIT_L1",
            section="Structure",
            description="Level 1 suspended slab soffit",
            area_m2=200.0,
            propping_height_m=3.0,
            source_page="Structural S102",
        )
        items1 = formwork.calculate_soffit_formwork_items(spec1)
        self.assertEqual(len(items1), 1)
        self.assertEqual(items1[0].quantity, 200.0)
        self.assertEqual(items1[0].unit, "m²")
        self.assertIn("propping up to 3.0m", items1[0].finish_system)

        # 2. Cantilever balcony soffit
        spec2 = formwork.FormworkElementSpec(
            element_type="soffit",
            element_id="BALC_01",
            section="Structure",
            description="Cantilever balcony",
            area_m2=35.0,
            is_cantilever=True,
            source_page="Structural S102",
        )
        items2 = formwork.calculate_soffit_formwork_items(spec2)
        self.assertEqual(items2[0].quantity, 35.0)
        self.assertIn("Cantilever balcony", items2[0].element)

        # 3. Drop panels: 4 No., 2.0m x 2.0m with 150mm drop
        spec3 = formwork.FormworkElementSpec(
            element_type="soffit",
            element_id="DROPS_01",
            section="Structure",
            description="Column drop panels",
            area_m2=100.0,
            count=4,
            length_m=2.0,
            width_m=2.0,
            depth_m=0.150,
            source_page="Structural S102",
        )
        items3 = formwork.calculate_soffit_formwork_items(spec3)
        self.assertEqual(len(items3), 2)  # Soffit + Drop panels
        drop_item = next(i for i in items3 if "Drop panel" in i.element)
        # Base: 4 * (2 * 2) = 16 m²; Edges: 4 * (2 * (2 + 2)) * 0.15 = 4 * 8 * 0.15 = 4.8 m²
        # Total: 16 + 4.8 = 20.8 m²
        self.assertEqual(drop_item.quantity, 20.8)

    def test_edge_and_wall_formwork_calculations(self) -> None:
        """Verify slab edge formwork and double-faced wall formwork with openings."""
        # Slab edge: 60 lm perimeter, 200mm deep
        edge_spec = formwork.FormworkElementSpec(
            element_type="edge",
            element_id="EDGE_01",
            section="Structure",
            description="Slab edge",
            perimeter_lm=60.0,
            depth_m=0.200,
            source_page="Structural S101",
        )
        edge_items = formwork.calculate_edge_formwork_items(edge_spec)
        self.assertEqual(len(edge_items), 1)
        self.assertEqual(edge_items[0].quantity, 60.0)
        self.assertEqual(edge_items[0].unit, "lm")
        self.assertIn("Contact area: 12.00 m²", edge_items[0].notes)

        # Wall: 20m long, 3.0m high, 2 openings (W01: 2.0x1.5=3.0m², D01: 1.0x2.1=2.1m²)
        wall_spec = formwork.FormworkElementSpec(
            element_type="wall",
            element_id="WALL_CORE_01",
            section="Structure",
            description="Lift core wall",
            length_m=20.0,
            height_m=3.0,
            depth_m=0.200,
            openings=[
                {"width": 2.0, "height": 1.5, "area": 3.0},
                {"width": 1.0, "height": 2.1, "area": 2.1},
            ],
            source_page="Structural S102",
        )
        wall_items = formwork.calculate_wall_formwork_items(wall_spec)
        # 1 wall item + 2 blockout items
        self.assertEqual(len(wall_items), 3)

        wall_face_item = wall_items[0]
        # Gross face: 20 * 3 = 60 m²
        # Deductions: 3.0 + 2.1 = 5.1 m²
        # Net face: 60 - 5.1 = 54.9 m²
        # Double-faced: 54.9 * 2 = 109.8 m²
        self.assertEqual(wall_face_item.quantity, 109.8)
        self.assertEqual(wall_face_item.unit, "m²")

        # Check blockout 1: 2 * (2.0 + 1.5) = 7.0 lm
        b1 = next(i for i in wall_items if "2000×1500" in i.element)
        self.assertEqual(b1.quantity, 7.0)
        self.assertEqual(b1.unit, "lm")

    def test_columns_beams_stepdowns_penetrations(self) -> None:
        """Verify column boxes, beam sides/soffits, stepdowns, and pipe penetrations."""
        # Rectangular columns: 6 No., 400x400mm, 3.2m high
        col_spec = formwork.FormworkElementSpec(
            element_type="column",
            element_id="COL_01",
            section="Structure",
            description="Columns",
            count=6,
            width_m=0.400,
            depth_m=0.400,
            height_m=3.2,
            source_page="Structural S102",
        )
        col_items = formwork.calculate_column_formwork_items(col_spec)
        self.assertEqual(len(col_items), 1)
        # 6 * (2 * (0.4 + 0.4)) * 3.2 = 6 * 1.6 * 3.2 = 30.72 m²
        self.assertEqual(col_items[0].quantity, 30.72)
        self.assertEqual(col_items[0].unit, "m²")

        # High column test (> 3.6m): 2 No., 400x400mm, 4.2m high
        high_col = formwork.FormworkElementSpec(
            element_type="column",
            element_id="COL_HIGH",
            section="Structure",
            description="High lobby columns",
            count=2,
            width_m=0.400,
            depth_m=0.400,
            height_m=4.2,
            source_page="Structural S102",
        )
        high_items = formwork.calculate_column_formwork_items(high_col)
        self.assertEqual(len(high_items), 2)  # Area + High propping allowance
        high_allow = next(i for i in high_items if "high column propping" in i.element)
        self.assertEqual(high_allow.quantity, 2.0)
        self.assertEqual(high_allow.unit, "No.")

        # Beams: 15m long, 0.4m wide, 0.5m deep
        beam_spec = formwork.FormworkElementSpec(
            element_type="beam",
            element_id="BEAM_01",
            section="Structure",
            description="Band beams",
            length_m=15.0,
            width_m=0.400,
            depth_m=0.500,
            source_page="Structural S102",
        )
        beam_items = formwork.calculate_beam_formwork_items(beam_spec)
        # 15 * (0.4 + 2 * 0.5) = 15 * 1.4 = 21.0 m²
        self.assertEqual(beam_items[0].quantity, 21.0)
        self.assertEqual(beam_items[0].unit, "m²")

        # Stepdown rebate: 25 lm, 50mm drop
        step_spec = formwork.FormworkElementSpec(
            element_type="stepdown",
            element_id="STEP_01",
            section="Structure",
            description="Balcony stepdowns",
            length_m=25.0,
            depth_m=0.050,
            source_page="Structural S102",
        )
        step_items = formwork.calculate_stepdowns_and_penetrations(step_spec)
        self.assertEqual(step_items[0].quantity, 25.0)
        self.assertEqual(step_items[0].unit, "lm")

        # Penetrations: 12 No., 150mm dia
        pen_spec = formwork.FormworkElementSpec(
            element_type="penetration",
            element_id="PEN_01",
            section="Structure",
            description="Plumbing pipe penetrations",
            count=12,
            width_m=0.150,
            is_circular=True,
            source_page="Structural S102",
        )
        pen_items = formwork.calculate_stepdowns_and_penetrations(pen_spec)
        self.assertEqual(pen_items[0].quantity, 12.0)
        self.assertEqual(pen_items[0].unit, "No.")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that formwork takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            formwork.FormworkElementSpec(
                element_type="soffit",
                element_id="SOFFIT_01",
                section="Structure",
                description="Slab soffit",
                area_m2=150.0,
            ),
            formwork.FormworkElementSpec(
                element_type="edge",
                element_id="EDGE_01",
                section="Structure",
                description="Edge formwork",
                perimeter_lm=50.0,
                depth_m=0.200,
            ),
            formwork.FormworkElementSpec(
                element_type="column",
                element_id="COL_01",
                section="Structure",
                description="Columns",
                count=4,
                width_m=0.35,
                depth_m=0.35,
                height_m=2.7,
            ),
            formwork.FormworkElementSpec(
                element_type="stepdown",
                element_id="REBATE_01",
                section="Structure",
                description="Shower rebates",
                length_m=12.0,
                depth_m=0.050,
            ),
        ]

        rows = formwork.generate_workspace_formwork_takeoff(specs, self.ws_id, self.now)
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
            self.assertEqual(len(db_rows), 4)

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
