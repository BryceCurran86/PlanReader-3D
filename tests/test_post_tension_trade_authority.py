"""Test Suite for Post-Tension (PT) Trade Authority Engine (AG-23).

Tests:
1. PT slab area, strand mass, ducting, live/dead anchorages, stressing, and grouting.
2. PT band beam runs, multi-strand anchorages, and tendon mass.
3. Strict compliance with 21-field core takeoff row contract in SQLite.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_post_tension_trade_authority as pt
import pb_takeoff_row_contract as takeoff_contract


class TestPostTensionTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 606
        self.now = "2026-10-01T17:00:00"

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

    def test_pt_slab_calculations(self) -> None:
        """Verify suspended PT slab items: area, strand tonnes, ducting, anchorages, stressing, and grouting."""
        spec = pt.PTExtractionSpec(
            element_type="pt_slab",
            element_id="PT_SLAB_L2",
            section="Structure",
            description="Level 2 PT slab",
            area_m2=400.0,
            thickness_m=0.200,
            tendon_density_kg_per_m2=3.5,
            strand_diameter_mm=12.7,
            strands_per_tendon=4,
            is_bonded=True,
            source_page="Structural PT S103",
        )
        items = pt.calculate_pt_slab_items(spec)
        # Expected items: area, strand weight, ducting, live ends, dead ends, stressing, grouting
        self.assertEqual(len(items), 7)

        # 1. Area item
        area_item = next(i for i in items if i.unit == "m²" and i.row_role == "floor_area")
        self.assertEqual(area_item.quantity, 400.0)

        # 2. Strand mass item: 400 m² * 3.5 kg/m² = 1400 kg = 1.4 tonnes
        strand_item = next(i for i in items if i.unit == "item" and "strand supply" in i.element)
        self.assertEqual(strand_item.quantity, 1.400)
        self.assertIn("1400.0 kg", strand_item.notes)

        # 3. Ducting item (lm)
        # 1400 kg / 0.785 kg/m = 1783.44 m strand. 1783.44 / 4 strands = 445.86 lm duct
        duct_item = next(i for i in items if i.unit == "lm" and "ducting" in i.element)
        self.assertEqual(duct_item.quantity, 445.86)

        # 4. Live ends and dead ends
        live_ends = next(i for i in items if "Live-end" in i.element)
        self.assertEqual(live_ends.unit, "No.")
        self.assertTrue(live_ends.quantity > 0)

        dead_ends = next(i for i in items if "Dead-end" in i.element)
        self.assertEqual(dead_ends.unit, "No.")
        self.assertEqual(dead_ends.quantity, live_ends.quantity)

        # 5. Stressing operations
        stressing = next(i for i in items if "stressing operations" in i.element)
        self.assertEqual(stressing.unit, "No.")

        # 6. Grouting
        grouting = next(i for i in items if "pressure grouting" in i.element)
        self.assertEqual(grouting.unit, "lm")
        self.assertEqual(grouting.quantity, duct_item.quantity)

    def test_pt_band_beam_calculations(self) -> None:
        """Verify PT band beam tendon runs and anchorages."""
        spec = pt.PTExtractionSpec(
            element_type="pt_band_beam",
            element_id="BB_01",
            section="Structure",
            description="Grid B PT Band Beam",
            length_m=30.0,
            width_m=1.200,
            thickness_m=0.450,
            strand_diameter_mm=12.7,
            source_page="Structural PT S103",
        )
        items = pt.calculate_pt_band_beam_items(spec)
        self.assertEqual(len(items), 2)  # Tendon supply/install run + anchorages

        beam_run = items[0]
        self.assertEqual(beam_run.quantity, 30.0)
        self.assertEqual(beam_run.unit, "lm")
        # 30m * 12 kg/m = 360 kg = 0.36 t
        self.assertIn("0.360 t", beam_run.notes)

        anchorages = items[1]
        self.assertEqual(anchorages.quantity, 4.0)
        self.assertEqual(anchorages.unit, "No.")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that PT takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            pt.PTExtractionSpec(
                element_type="pt_slab",
                element_id="PT_SLAB_01",
                section="Structure",
                description="Level 1 PT Slab",
                area_m2=250.0,
                thickness_m=0.200,
            ),
            pt.PTExtractionSpec(
                element_type="pt_band_beam",
                element_id="PT_BEAM_01",
                section="Structure",
                description="Band beam",
                length_m=20.0,
            ),
        ]

        rows = pt.generate_workspace_pt_takeoff(specs, self.ws_id, self.now)
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
