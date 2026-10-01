"""
PlanReader AG-15: Cross-Trade Geometry Reuse Runtime Parity Test Suite.

Proves that:
1. One physical canonical building object feeds multiple trades without rediscovery:
   - Wall: masonry, plaster, paint, tile, insulation, skirting (6 trades from 1 wall)
   - Slab: concrete, formwork, reinforcement, membrane (4 trades from 1 slab)
   - Roof: roofing, insulation, capping, gutters (4 trades from 1 roof)
2. Every derived trade quantity preserves identical host object identity and mathematical lineage.
3. Multi-trade takeoff rows satisfy the canonical 21-field contract and pass the 7-link provenance audit.
4. Database persistence and query parity in SQLite without duplicate extraction passes.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from typing import Any, Dict, List

import pb_canonical_building as cb
from pb_cross_trade_geometry_reuse import (
    DerivedTradeQuantity,
    derive_wall_trade_quantities,
    derive_slab_trade_quantities,
    derive_roof_trade_quantities,
    derive_space_trade_quantities,
    derive_multi_trade_takeoff_from_canonical_model,
    to_takeoff_rows,
)
from pb_provenance_audit_v14 import (
    audit_takeoff_row_provenance,
    audit_takeoff_rows_provenance_chain,
    audit_workspace_takeoff_provenance,
)
import pb_takeoff_row_contract as takeoff_contract


class MockDatabaseApp:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS takeoff_rows (
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
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER,
                file_name TEXT,
                path TEXT
            )"""
        )
        self._conn.commit()

    def lquery(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(query, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def lexecute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)
        self._conn.commit()


class TestCrossTradeReuseRuntimeParityV15(unittest.TestCase):
    def test_ag15_wall_geometry_feeds_six_trades_without_rediscovery(self) -> None:
        """Prove 1 physical CanonicalWall feeds: masonry, plaster, paint, tile, insulation, skirting."""
        prov = cb.Provenance(source_pdf="3LAUREL.pdf", page_number=1, drawing_id="A-101")
        wall = cb.CanonicalWall(
            id="W-BATH-01",
            name="Bathroom Boundary Wall",
            start_point=cb.Vector2D(0.0, 0.0),
            end_point=cb.Vector2D(6.0, 0.0),
            height_m=2.7,
            thickness_m=0.23,
            is_external=False,
            substrate="Timber stud framing",
            finish="Ceramic Wall Tiles",
            provenance=prov,
        )
        door = cb.CanonicalOpening(
            id="OP-D01",
            mark="D01",
            opening_type="DOOR",
            width_m=0.82,
            height_m=2.04,
            host_wall_id="W-BATH-01",
            deduction_authority=True,
            provenance=prov,
        )
        wall.openings.append(door)

        # Net area = 6.0m * 2.7m - (0.82 * 2.04) = 16.20 - 1.67 = 14.53 m2
        net_m2 = wall.net_area_m2()
        self.assertAlmostEqual(net_m2, 14.53, places=2)

        # Derive multiple trades with zero geometric rediscovery
        specs = {
            "include_masonry": True,
            "include_plaster": True,
            "include_paint": True,
            "include_tile": True,
            "include_insulation": True,
            "include_skirting": True,
        }
        trade_quants = derive_wall_trade_quantities(wall, specs=specs)
        self.assertEqual(len(trade_quants), 6)

        trade_map = {q.trade_family: q for q in trade_quants}
        self.assertIn("masonry", trade_map)
        self.assertIn("plaster", trade_map)
        self.assertIn("paint", trade_map)
        self.assertIn("tile", trade_map)
        self.assertIn("insulation", trade_map)
        self.assertIn("skirting", trade_map)

        # 1. Masonry: Net wall area
        self.assertEqual(trade_map["masonry"].quantity, 14.53)
        self.assertEqual(trade_map["masonry"].unit, "m²")

        # 2. Plaster: Net wall area
        self.assertEqual(trade_map["plaster"].quantity, 14.53)
        self.assertEqual(trade_map["plaster"].unit, "m²")

        # 3. Paint: Net wall area
        self.assertEqual(trade_map["paint"].quantity, 14.53)
        self.assertEqual(trade_map["paint"].unit, "m²")

        # 4. Tile: Net wall area (wet area wall)
        self.assertEqual(trade_map["tile"].quantity, 14.53)
        self.assertEqual(trade_map["tile"].unit, "m²")

        # 5. Insulation: Net wall area
        self.assertEqual(trade_map["insulation"].quantity, 14.53)
        self.assertEqual(trade_map["insulation"].unit, "m²")

        # 6. Skirting: 6.0m length - 0.82m door deduction = 5.18 lm
        self.assertEqual(trade_map["skirting"].quantity, 5.18)
        self.assertEqual(trade_map["skirting"].unit, "lm")

        # Verify all 6 trades strictly preserve host object identity
        for q in trade_quants:
            self.assertEqual(q.host_object_id, "W-BATH-01")
            self.assertEqual(q.host_object_type, "WALL")

    def test_ag15_slab_geometry_feeds_four_trades_without_rediscovery(self) -> None:
        """Prove 1 physical CanonicalFloor feeds: concrete, formwork, reinforcement, membrane."""
        prov = cb.Provenance(source_pdf="3LAUREL.pdf", page_number=1, drawing_id="A-101")
        floor = cb.CanonicalFloor(
            id="FL-SLAB-01",
            name="Ground Concrete Slab",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(12.0, 0.0), cb.Vector2D(12.0, 8.0), cb.Vector2D(0.0, 8.0)],
            thickness_m=0.100,
            substrate="25 MPa Concrete",
            provenance=prov,
        )

        # Area = 12.0 * 8.0 = 96.0 m2; Perimeter = 40.0 lm; Thickness = 0.100m
        self.assertEqual(floor.effective_area_m2(), 96.0)
        self.assertEqual(floor.perimeter_lm(), 40.0)

        trade_quants = derive_slab_trade_quantities(floor)
        self.assertEqual(len(trade_quants), 4)

        trade_map = {q.trade_family: q for q in trade_quants}
        self.assertIn("concrete", trade_map)
        self.assertIn("formwork", trade_map)
        self.assertIn("reinforcement", trade_map)
        self.assertIn("membrane", trade_map)

        # 1. Concrete: 96.0 m2 * 0.100m = 9.60 m3 (unit: item)
        self.assertEqual(trade_map["concrete"].quantity, 9.60)
        self.assertEqual(trade_map["concrete"].unit, "item")

        # 2. Formwork: 40.0 lm * 0.100m = 4.00 m2
        self.assertEqual(trade_map["formwork"].quantity, 4.00)
        self.assertEqual(trade_map["formwork"].unit, "m²")

        # 3. Reinforcement: 96.0 m2 * 1.10 lap factor = 105.60 m2
        self.assertEqual(trade_map["reinforcement"].quantity, 105.60)
        self.assertEqual(trade_map["reinforcement"].unit, "m²")

        # 4. Membrane: 96.00 m2
        self.assertEqual(trade_map["membrane"].quantity, 96.00)
        self.assertEqual(trade_map["membrane"].unit, "m²")

        # Verify all 4 trades strictly preserve host object identity
        for q in trade_quants:
            self.assertEqual(q.host_object_id, "FL-SLAB-01")
            self.assertEqual(q.host_object_type, "SLAB")

    def test_ag15_roof_geometry_feeds_four_trades_without_rediscovery(self) -> None:
        """Prove 1 physical CanonicalRoof feeds: roofing, insulation, capping, gutters."""
        prov = cb.Provenance(source_pdf="3LAUREL.pdf", page_number=1, drawing_id="A-101")
        roof = cb.CanonicalRoof(
            id="RF-PITCH-01",
            name="Main Pitched Gable Roof",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(10.0, 0.0), cb.Vector2D(10.0, 6.0), cb.Vector2D(0.0, 6.0)],
            pitch_deg=22.5,
            substrate="Colorbond Custom Orb Corrugated Sheet Metal",
            provenance=prov,
        )

        # Plan area = 60.0 m2; raked area = 60.0 / cos(22.5 deg) ~= 64.94 m2; perimeter = 32.0 lm; ridge = 32 * 0.25 = 8.0 lm
        trade_quants = derive_roof_trade_quantities(roof)
        self.assertEqual(len(trade_quants), 4)

        trade_map = {q.trade_family: q for q in trade_quants}
        self.assertIn("roofing", trade_map)
        self.assertIn("insulation", trade_map)
        self.assertIn("capping", trade_map)
        self.assertIn("gutters", trade_map)

        # 1. Roofing: 64.94 m2
        self.assertAlmostEqual(trade_map["roofing"].quantity, 64.94, places=1)
        self.assertEqual(trade_map["roofing"].unit, "m²")

        # 2. Insulation: 64.94 m2
        self.assertAlmostEqual(trade_map["insulation"].quantity, 64.94, places=1)
        self.assertEqual(trade_map["insulation"].unit, "m²")

        # 3. Capping: 8.00 lm
        self.assertEqual(trade_map["capping"].quantity, 8.00)
        self.assertEqual(trade_map["capping"].unit, "lm")

        # 4. Gutters: 32.00 lm
        self.assertEqual(trade_map["gutters"].quantity, 32.00)
        self.assertEqual(trade_map["gutters"].unit, "lm")

        # Verify all 4 trades strictly preserve host object identity
        for q in trade_quants:
            self.assertEqual(q.host_object_id, "RF-PITCH-01")
            self.assertEqual(q.host_object_type, "ROOF")

    def test_ag15_full_model_cross_trade_takeoff_audit_and_persistence(self) -> None:
        """Prove that multi-trade takeoff from canonical model passes 100% 7-link audit and persists in SQLite."""
        proj = cb.CanonicalProject(id="PRJ-AG15", name="AG-15 Cross Trade Project")
        bldg = cb.CanonicalBuilding(id="BLD-01", name="Main Complex")
        lvl = cb.CanonicalLevel(id="LVL-01", name="Ground Floor", level_index=0, elevation_m=0.0, height_m=2.7)

        prov = cb.Provenance(source_pdf="3LAUREL_ARCHITECTURAL_REV_B.pdf", page_number=1, drawing_id="A-101")

        wall = cb.CanonicalWall(
            id="W-01",
            name="External Wall",
            start_point=cb.Vector2D(0.0, 0.0),
            end_point=cb.Vector2D(10.0, 0.0),
            height_m=2.7,
            thickness_m=0.23,
            is_external=True,
            substrate="Brick veneer",
            finish="Face brickwork",
            provenance=prov,
        )
        floor = cb.CanonicalFloor(
            id="FL-01",
            name="Ground Slab",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(10.0, 0.0), cb.Vector2D(10.0, 6.0), cb.Vector2D(0.0, 6.0)],
            thickness_m=0.100,
            substrate="25 MPa Concrete",
            provenance=prov,
        )
        roof = cb.CanonicalRoof(
            id="RF-01",
            name="Gable Roof",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(10.0, 0.0), cb.Vector2D(10.0, 6.0), cb.Vector2D(0.0, 6.0)],
            pitch_deg=22.5,
            substrate="Colorbond Corrugated Sheet",
            provenance=prov,
        )
        space = cb.CanonicalSpace(
            id="SP-01",
            name="Main Room",
            room_number="101",
            boundary_polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(6.0, 0.0), cb.Vector2D(6.0, 5.0), cb.Vector2D(0.0, 5.0)],
            height_m=2.7,
            provenance=prov,
        )

        lvl.walls.append(wall)
        lvl.floors.append(floor)
        lvl.roofs.append(roof)
        lvl.spaces.append(space)
        bldg.levels.append(lvl)
        proj.buildings.append(bldg)

        # Derive all multi-trade takeoff rows directly from the canonical model
        rows = derive_multi_trade_takeoff_from_canonical_model(
            proj,
            workspace_id=88,
            source_document="3LAUREL_ARCHITECTURAL_REV_B.pdf",
            specs={"include_tile": True},
            as_dicts=True,
        )

        self.assertGreaterEqual(len(rows), 15, "Expected comprehensive cross-trade takeoff rows")

        # 1. Verify strict 21-field contract
        for r in rows:
            self.assertEqual(len(r), 21)
            self.assertEqual(r["workspace_id"], 88)
            self.assertTrue(r["quantity"] > 0.0)
            self.assertIn(r["unit"], takeoff_contract.TAKEOFF_UNITS)

        # 2. Run AG-14 7-link provenance audit
        summary = audit_takeoff_rows_provenance_chain(
            rows,
            workspace_id=88,
            known_docs=["3LAUREL_ARCHITECTURAL_REV_B.pdf"],
        )
        self.assertEqual(
            summary.passed_rows,
            summary.total_rows,
            f"Cross-trade rows failed provenance audit: {summary.deficiencies[:5]}",
        )
        self.assertEqual(summary.pass_rate, 1.0)

        # 3. Test persistence into SQLite database
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            app = MockDatabaseApp(tmp.name)
            app.lexecute(
                "INSERT INTO documents (workspace_id, file_name, path) VALUES (?, ?, ?)",
                (88, "3LAUREL_ARCHITECTURAL_REV_B.pdf", "/uploads/3LAUREL_ARCHITECTURAL_REV_B.pdf"),
            )

            # Insert all rows
            insert_sql = """INSERT INTO takeoff_rows (
                workspace_id, section, element, location, substrate, finish_system,
                quantity, unit, quantity_status, source_page, source_reference,
                inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                rate_per_unit, confidence, notes, row_role, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

            for r in rows:
                app.lexecute(insert_sql, tuple(r[k] for k in takeoff_contract.CORE_FIELDS))

            # Run workspace audit on database
            ws_summary = audit_workspace_takeoff_provenance(app, 88)
            self.assertEqual(ws_summary.total_rows, len(rows))
            self.assertEqual(ws_summary.passed_rows, len(rows))
            self.assertEqual(ws_summary.pass_rate, 1.0)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
