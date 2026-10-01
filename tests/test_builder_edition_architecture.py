"""Test Suite for Builder Edition Architecture & Multi-Trade Aggregator (AG-30).

Tests:
1. Composite trade package classification across 11 master trade disciplines.
2. Commercial pricing engine: direct costs, preliminaries, contingency, builder margin, and contract sum.
3. Bill of Quantities (BoQ) hierarchical export.
4. Project health and completeness audit dashboard.
5. Strict compliance with 21-field core takeoff row contract in SQLite across a multi-trade project.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_builder_edition_architecture as builder
import pb_takeoff_row_contract as takeoff_contract


class TestBuilderEditionArchitecture(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 1313
        self.now = "2026-10-01T20:30:00"

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

    def test_composite_trade_package_classification(self) -> None:
        """Verify accurate classification of rows into master trade packages."""
        sample_rows = [
            {"element": "Concrete slab on ground", "substrate": "25 MPa Concrete", "section": "Substructure"},
            {"element": "Soffit formwork", "substrate": "Plywood formwork", "section": "Structure"},
            {"element": "PT slab supply & installation", "substrate": "12.7mm strand in flat duct", "section": "Structure"},
            {"element": "Structural steel beam 310UB40.4", "substrate": "Grade 300 steel", "section": "Structure"},
            {"element": "Face brickwork skin", "substrate": "Selected clay face bricks", "section": "External"},
            {"element": "Timber wall framing 90x45", "substrate": "MGP10 pine", "section": "Structure"},
            {"element": "Engineered timber flooring", "substrate": "Floating timber", "section": "Internal"},
            {"element": "Plasterboard wall lining", "substrate": "13mm plasterboard", "section": "Internal"},
            {"element": "Acrylic wall painting", "substrate": "2 coats low sheen acrylic", "section": "Internal"},
            {"element": "Sanitary sewer drainage pipework", "substrate": "100mm PVC-DWV", "section": "Substructure"},
            {"element": "Distribution switchboard DB-1", "substrate": "Sheet steel enclosure", "section": "Internal"},
        ]

        expected_packages = [
            "01_substructure",
            "02_concrete_formwork",
            "03_post_tensioning",
            "04_structural_steel",
            "05_masonry",
            "06_carpentry",
            "07_flooring_tiling",
            "08_linings_plasterboard",
            "09_painting",
            "10_plumbing_drainage",
            "11_electrical_comms",
        ]

        for row, exp in zip(sample_rows, expected_packages):
            classified = builder.classify_trade_package(row)
            self.assertEqual(classified, exp, f"Failed for {row['element']}: got {classified}, expected {exp}")

    def test_commercial_pricing_engine(self) -> None:
        """Verify direct costs, preliminaries (8%), contingency (5%), builder margin (15%), and contract sum."""
        engine = builder.BuilderEditionEngine(
            builder_margin_pct=15.0,
            preliminaries_pct=8.0,
            contingency_pct=5.0,
        )

        rows = [
            # Concrete: 100 m² @ $95/m² = $9,500
            {"element": "Concrete slab on ground", "substrate": "25 MPa", "section": "Substructure", "quantity": 100.0, "unit": "m²", "rate_per_unit": 95.0, "quantity_status": "Measured"},
            # Steel: 2.0 t @ $4,500/t = $9,000
            {"element": "Structural steel beam 310UB40.4", "substrate": "Grade 300", "section": "Structure", "quantity": 2.0, "unit": "item", "rate_per_unit": 4500.0, "quantity_status": "Measured"},
            # Brickwork: 120 m² @ $110/m² = $13,200
            {"element": "Face brickwork skin", "substrate": "Clay bricks", "section": "External", "quantity": 120.0, "unit": "m²", "rate_per_unit": 110.0, "quantity_status": "Measured"},
        ]

        estimate = engine.aggregate_and_price_workspace(rows, self.ws_id, "JOB-2026-BUILDER", "Commercial Residence")

        # Direct cost: 9,500 + 9,000 + 13,200 = $31,700.00
        self.assertEqual(estimate.direct_cost_subtotal, 31700.00)

        # Prelims: 31,700 * 0.08 = $2,536.00
        self.assertEqual(estimate.preliminaries_amount, 2536.00)

        # Contingency: 31,700 * 0.05 = $1,585.00
        self.assertEqual(estimate.contingency_amount, 1585.00)

        # Base with overheads: 31,700 + 2,536 + 1,585 = $35,821.00
        # Margin (15%): 35,821 * 0.15 = $5,373.15
        self.assertEqual(estimate.builder_margin_amount, 5373.15)

        # Grand Total Contract Sum: 35,821 + 5,373.15 = $41,194.15
        self.assertEqual(estimate.grand_total_contract_sum, 41194.15)

    def test_bill_of_quantities_csv_export(self) -> None:
        """Verify BoQ CSV generation with hierarchical structure and summary footer."""
        engine = builder.BuilderEditionEngine()
        rows = [
            {"element": "Concrete slab on ground", "substrate": "25 MPa", "section": "Substructure", "quantity": 50.0, "unit": "m²", "rate_per_unit": 100.0, "quantity_status": "Measured"},
            {"element": "Face brickwork skin", "substrate": "Clay bricks", "section": "External", "quantity": 80.0, "unit": "m²", "rate_per_unit": 120.0, "quantity_status": "Measured"},
        ]
        estimate = engine.aggregate_and_price_workspace(rows, self.ws_id)
        csv_text = engine.export_bill_of_quantities_csv(estimate)

        self.assertIn("--- 01 Substructure & Groundworks ---", csv_text)
        self.assertIn("--- 05 Masonry, Brickwork & Blockwork ---", csv_text)
        self.assertIn("GRAND TOTAL CONTRACT SUM", csv_text)
        self.assertIn("Direct Cost Subtotal", csv_text)

    def test_project_health_audit_dashboard(self) -> None:
        """Verify health metrics: completeness, active packages, readiness score, and warning detection."""
        engine = builder.BuilderEditionEngine()

        # Healthy project: 5 packages, 100% measured, 100% rated
        healthy_rows = [
            {"element": "Concrete slab on ground", "quantity": 100.0, "unit": "m²", "rate_per_unit": 90.0, "quantity_status": "Measured"},
            {"element": "Structural steel beam", "quantity": 1.0, "unit": "item", "rate_per_unit": 4000.0, "quantity_status": "Measured"},
            {"element": "Face brickwork skin", "quantity": 100.0, "unit": "m²", "rate_per_unit": 110.0, "quantity_status": "Measured"},
            {"element": "Timber wall framing", "quantity": 80.0, "unit": "m²", "rate_per_unit": 65.0, "quantity_status": "Measured"},
            {"element": "Sanitary sewer drainage", "quantity": 30.0, "unit": "lm", "rate_per_unit": 85.0, "quantity_status": "Measured"},
        ]
        health = engine.audit_project_health(healthy_rows, self.ws_id)
        self.assertTrue(health.healthy)
        self.assertEqual(health.pricing_completeness_pct, 100.0)
        self.assertGreaterEqual(health.readiness_score_pct, 80.0)
        self.assertEqual(len(health.warnings), 0)

        # Unhealthy project: unrated items and high provisional count
        unhealthy_rows = [
            {"element": "Concrete slab", "quantity": 100.0, "unit": "m²", "rate_per_unit": 0.0, "quantity_status": "Provisional"},
            {"element": "Concrete slab", "quantity": 100.0, "unit": "m²", "rate_per_unit": 0.0, "quantity_status": "Provisional"},
        ]
        bad_health = engine.audit_project_health(unhealthy_rows, self.ws_id)
        self.assertFalse(bad_health.healthy)
        self.assertLess(bad_health.pricing_completeness_pct, 50.0)
        self.assertGreater(len(bad_health.warnings), 0)

    def test_sqlite_multi_trade_round_trip(self) -> None:
        """Verify database publication and 21-field core contract compliance across multi-trade project."""
        multi_trade_rows = [
            {
                "workspace_id": self.ws_id, "section": "Substructure", "element": "Concrete slab on ground",
                "location": "Ground Floor", "substrate": "25 MPa Concrete", "finish_system": "Trowel finish",
                "quantity": 150.0, "unit": "m²", "quantity_status": "Measured", "source_page": "S101",
                "source_reference": "Builder Edition v2.0", "inclusion_status": "INCLUSION", "coats": 1,
                "coverage_m2_per_litre": 0.0, "productivity_m2_per_hour": 0.0, "rate_per_unit": 95.0,
                "confidence": "Verified", "notes": "Concrete slab on ground 100mm.", "row_role": "floor_area",
                "created_at": self.now, "updated_at": self.now,
            },
            {
                "workspace_id": self.ws_id, "section": "Structure", "element": "Structural steel 310UB40.4",
                "location": "First Floor Framing", "substrate": "Grade 300 Steel", "finish_system": "Shop primed",
                "quantity": 30.0, "unit": "lm", "quantity_status": "Measured", "source_page": "S201",
                "source_reference": "Builder Edition v2.0", "inclusion_status": "INCLUSION", "coats": 1,
                "coverage_m2_per_litre": 0.0, "productivity_m2_per_hour": 0.0, "rate_per_unit": 180.0,
                "confidence": "Verified", "notes": "Steel beam runs.", "row_role": "",
                "created_at": self.now, "updated_at": self.now,
            },
            {
                "workspace_id": self.ws_id, "section": "External", "element": "Face brickwork veneer",
                "location": "External Perimeter", "substrate": "Selected face bricks", "finish_system": "Stretcher bond",
                "quantity": 180.0, "unit": "m²", "quantity_status": "Measured", "source_page": "A101",
                "source_reference": "Builder Edition v2.0", "inclusion_status": "INCLUSION", "coats": 1,
                "coverage_m2_per_litre": 0.0, "productivity_m2_per_hour": 0.0, "rate_per_unit": 115.0,
                "confidence": "Verified", "notes": "External face brick skin.", "row_role": "external_wall",
                "created_at": self.now, "updated_at": self.now,
            },
        ]

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
            conn.executemany(insert_sql, multi_trade_rows)
            conn.commit()

            cur = conn.execute("SELECT * FROM takeoff_rows WHERE workspace_id=?", (self.ws_id,))
            db_rows = cur.fetchall()
            self.assertEqual(len(db_rows), 3)

            cols = [d[0] for d in cur.description]
            self.assertEqual(len(cols), 22)  # id + 21 core fields

            for r in db_rows:
                row_dict = dict(zip(cols, r))
                self.assertEqual(row_dict["workspace_id"], self.ws_id)
                self.assertIn(row_dict["unit"], takeoff_contract.TAKEOFF_UNITS)
                self.assertTrue(row_dict["quantity"] > 0.0)
                self.assertTrue(row_dict["rate_per_unit"] > 0.0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
