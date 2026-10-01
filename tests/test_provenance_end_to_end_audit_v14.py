"""
PlanReader AG-14: Provenance End-to-End Audit Authority Test Suite.

Proves that:
1. Every customer-visible number generated across all 9 mature canonical families
   satisfies the full 7-link provenance chain:
   SOURCE DOCUMENT → PAGE/VIEW → EVIDENCE → PHYSICAL OBJECT → CANONICAL OBJECT → QUANTITY → TAKEOFF ROW.
2. Any row with a broken or missing link fails closed and is rejected with explicit diagnostic deficiency codes.
3. Workspace-level database audit verifies persisted SQLite takeoff rows and cross-checks known uploaded documents.
4. Customer runtime auto geometry rows and canonical BIM rows both achieve full provenance parity.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from typing import Any, Dict, List

import pb_canonical_building as cb
from pb_auto_geometry_v1219 import _try_physical_net_wall_rows
from pb_opening_detail_definition_bridge import ConsolidatedPhysicalOpening
from pb_provenance_audit_v14 import (
    ProvenanceLink,
    audit_takeoff_row_provenance,
    audit_takeoff_rows_provenance_chain,
    audit_workspace_takeoff_provenance,
)
import pb_takeoff_row_contract as takeoff_contract


class MockAuditApp:
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

    def build_registered_walls_v139(self, ws_id: int):
        op1 = ConsolidatedPhysicalOpening(
            opening_id="win_N01",
            type_mark="W01",
            host_wall_id="N01",
            width_m=1.5,
            height_m=1.2,
            area_m2=1.8,
            plan_page_id="1",
            elevation_page_id="3",
        )
        return [
            {
                "wall_ref": "N01",
                "side": "North",
                "gross_m2": 30.0,
                "net_m2": 28.2,
                "opening_deduction_m2": 1.8,
                "height_status": "Measured 2.70m",
                "height_confidence": "Verified",
                "plan_page_id": "1",
                "elevation_page_id": "3",
                "source_document": "3LAUREL_ARCHITECTURAL_REV_B.pdf",
                "openings": [op1],
            }
        ]


class TestProvenanceEndToEndAuditV14(unittest.TestCase):
    def test_ag14_seven_link_provenance_passes_for_all_mature_canonical_families(self) -> None:
        """Prove that rows generated across all mature families pass 100% of 7-link checks."""
        proj = cb.CanonicalProject(id="PRJ-AG14", name="AG-14 Provenance Audit Project")
        bldg = cb.CanonicalBuilding(id="BLD-01", name="Main Residence")
        lvl = cb.CanonicalLevel(id="LVL-01", name="Ground Floor", level_index=0, elevation_m=0.0, height_m=2.7)

        prov = cb.Provenance(
            source_pdf="3LAUREL_ARCHITECTURAL_REV_B.pdf",
            page_number=1,
            drawing_id="A-101",
            contributing_evidence=["plan_measured", "detail_record"],
        )

        # Family 1: Wall (External with finishes & Internal Partition)
        wall_ext = cb.CanonicalWall(
            id="W-EXT-01",
            name="External Wall",
            start_point=cb.Vector2D(0.0, 0.0),
            end_point=cb.Vector2D(10.0, 0.0),
            height_m=2.7,
            thickness_m=0.23,
            is_external=True,
            substrate="Brick veneer",
            provenance=prov,
        )
        wall_ext.face_a = cb.WallFace(face_id="A", finish="Face brickwork", finish_code="BRK-01", substrate="Clay face brick", area_net_m2=24.84)
        wall_ext.face_b = cb.WallFace(face_id="B", finish="Interior paint", finish_code="PNT-01", substrate="Plasterboard", area_net_m2=24.84)

        wall_int = cb.CanonicalWall(
            id="W-INT-01",
            name="Internal Partition",
            start_point=cb.Vector2D(0.0, 0.0),
            end_point=cb.Vector2D(0.0, 5.0),
            height_m=2.7,
            thickness_m=0.09,
            is_external=False,
            substrate="Timber stud framing",
            provenance=prov,
        )

        # Family 2 & 3: Opening & Door / Window
        op_win = cb.CanonicalOpening(
            id="OP-W01",
            mark="W01",
            opening_type="WINDOW",
            width_m=1.80,
            height_m=1.20,
            sill_height_m=0.90,
            head_height_m=2.10,
            host_wall_id="W-EXT-01",
            plan_page_id="1",
            schedule_page_id="2",
            detail_record_id="det_w01",
            opening_classification="Aluminium sliding window",
            deduction_authority=True,
            provenance=prov,
        )
        op_win.derive_trade_quantities(include_ancillary=True)
        wall_ext.openings.append(op_win)

        op_door = cb.CanonicalOpening(
            id="OP-D01",
            mark="D01",
            opening_type="DOOR",
            width_m=0.82,
            height_m=2.04,
            sill_height_m=0.0,
            head_height_m=2.04,
            host_wall_id="W-INT-01",
            plan_page_id="1",
            schedule_page_id="2",
            opening_classification="Internal hollow core door",
            deduction_authority=True,
            provenance=prov,
        )
        op_door.derive_trade_quantities(include_ancillary=True)
        wall_int.openings.append(op_door)

        # Family 4: Room (Space with finish assignments)
        space = cb.CanonicalSpace(
            id="SP-01",
            name="Living Room",
            room_number="101",
            boundary_polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(6.0, 0.0), cb.Vector2D(6.0, 5.0), cb.Vector2D(0.0, 5.0)],
            height_m=2.7,
            finish_assignments={"floor": "Selected Timber Flooring"},
            provenance=prov,
        )
        space.derive_trade_quantities()

        # Family 5: Floor / Slab
        floor = cb.CanonicalFloor(
            id="FL-01",
            name="Ground Slab",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(10.0, 0.0), cb.Vector2D(10.0, 5.0), cb.Vector2D(0.0, 5.0)],
            thickness_m=0.100,
            substrate="Reinforced Concrete",
            provenance=prov,
        )
        floor.derive_trade_quantities()

        # Family 6: Ceiling
        ceiling = cb.CanonicalCeiling(
            id="CL-01",
            name="Plasterboard Ceiling",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(6.0, 0.0), cb.Vector2D(6.0, 5.0), cb.Vector2D(0.0, 5.0)],
            substrate="Plasterboard on battens",
            provenance=prov,
        )
        ceiling.derive_trade_quantities()

        # Family 7: Roof
        roof = cb.CanonicalRoof(
            id="RF-01",
            name="Gable Roof",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(10.0, 0.0), cb.Vector2D(10.0, 6.0), cb.Vector2D(0.0, 6.0)],
            pitch_deg=22.5,
            substrate="Colorbond Custom Orb",
            provenance=prov,
        )
        roof.derive_trade_quantities()

        # Family 8: Finish Surface
        surface = cb.CanonicalFinishSurface(
            id="SURF-01",
            name="Acoustic Slatting",
            parent_element_id="W-INT-01",
            surface_area_m2=13.50,
            orientation="INT_NORTH",
            substrate="Plasterboard",
            finish="Timber slat paneling",
            provenance=prov,
        )
        surface.derive_trade_quantities()

        # Family 9: Column & Structural Member
        col = cb.CanonicalColumn(
            id="COL-01",
            name="Portico Column",
            center=cb.Vector2D(10.0, 0.0),
            width_m=0.35,
            depth_m=0.35,
            height_m=2.7,
            substrate="Reinforced Concrete",
            provenance=prov,
        )
        col.derive_trade_quantities()

        sm = cb.CanonicalStructuralMember(
            id="SM-01",
            name="Steel Beam Lintel",
            member_type="BEAM",
            section_spec="200UB25",
            length_m=6.0,
            host_wall_id="W-EXT-01",
            provenance=prov,
        )
        sm.derive_trade_quantities()

        # Ancillary: Parapet, Balcony, Soffit
        parapet = cb.CanonicalParapet(
            id="PAR-01",
            start_point=cb.Vector2D(0.0, 0.0),
            end_point=cb.Vector2D(10.0, 0.0),
            height_m=0.6,
            provenance=prov,
        )
        balcony = cb.CanonicalBalcony(
            id="BAL-01",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(4.0, 0.0), cb.Vector2D(4.0, 3.0), cb.Vector2D(0.0, 3.0)],
            provenance=prov,
        )
        soffit = cb.CanonicalSoffit(
            id="SOF-01",
            polygon=[cb.Vector2D(0.0, 0.0), cb.Vector2D(6.5, 0.0), cb.Vector2D(6.5, 1.0), cb.Vector2D(0.0, 1.0)],
            provenance=prov,
        )

        lvl.walls.extend([wall_ext, wall_int])
        lvl.spaces.append(space)
        lvl.floors.append(floor)
        lvl.ceilings.append(ceiling)
        lvl.roofs.append(roof)
        lvl.surfaces.append(surface)
        lvl.columns.append(col)
        lvl.structural_members.append(sm)
        lvl.parapets.append(parapet)
        lvl.balconies.append(balcony)
        lvl.soffits.append(soffit)

        bldg.levels.append(lvl)
        proj.buildings.append(bldg)
        proj.recompute_relationships()

        rows = proj.generate_takeoff_rows(workspace_id=1)
        self.assertGreaterEqual(len(rows), 25, "Expected comprehensive takeoff across all families")

        summary = audit_takeoff_rows_provenance_chain(
            rows,
            workspace_id=1,
            known_docs=["3LAUREL_ARCHITECTURAL_REV_B.pdf"],
        )

        self.assertEqual(
            summary.passed_rows,
            summary.total_rows,
            f"Failed {summary.failed_rows}/{summary.total_rows} rows: {summary.deficiencies[:5]}",
        )
        self.assertEqual(summary.pass_rate, 1.0)
        self.assertEqual(len(summary.deficiencies), 0)

        # Verify all 7 links had 100% pass counts
        for link in ProvenanceLink:
            self.assertEqual(
                summary.link_pass_counts[link.value],
                summary.total_rows,
                f"Link {link.value} had incomplete coverage",
            )

    def test_ag14_each_individual_link_fails_closed_when_broken(self) -> None:
        """Verify that a broken link anywhere in the 7 links causes immediate rejection."""
        base_valid_row = {
            "id": 1,
            "workspace_id": 1,
            "section": "External",
            "element": "External walls / cladding",
            "location": "External perimeter · W1",
            "substrate": "Brick veneer",
            "finish_system": "Face brickwork",
            "quantity": 27.0,
            "unit": "m²",
            "quantity_status": "Measured",
            "source_page": "1",
            "source_reference": "PB Canonical BIM · wall:W1",
            "inclusion_status": "INCLUSION",
            "coats": 1,
            "coverage_m2_per_litre": 0.0,
            "productivity_m2_per_hour": 0.0,
            "rate_per_unit": 0.0,
            "confidence": "Documented",
            "notes": "Net wall area 27.00 m² (Gross 27.00 m² less opening deductions 0.00 m²). [Doc: sample.pdf · Sheet: A01]",
            "row_role": "external_wall",
            "created_at": "2026-10-02T00:00:00",
            "updated_at": "2026-10-02T00:00:00",
        }

        # 0. Base valid
        r0 = audit_takeoff_row_provenance(base_valid_row)
        self.assertTrue(r0.complete_chain)
        self.assertEqual(len(r0.deficiencies), 0)

        # 1. Break Link 1 (Source Document)
        r1 = audit_takeoff_row_provenance(dict(base_valid_row, notes="Area 27.00 m²", source_reference="arbitrary_calc"))
        self.assertFalse(r1.complete_chain)
        self.assertIn("Link 1: Missing SOURCE DOCUMENT trace", r1.deficiencies)

        # 2. Break Link 2 (Page / View)
        r2 = audit_takeoff_row_provenance(dict(base_valid_row, source_page=""))
        self.assertFalse(r2.complete_chain)
        self.assertIn("Link 2: Missing PAGE/VIEW trace", r2.deficiencies)

        # 3. Break Link 3 (Evidence)
        r3 = audit_takeoff_row_provenance(dict(base_valid_row, notes="Doc: sample.pdf", quantity_status="Estimated"))
        self.assertFalse(r3.complete_chain)
        self.assertIn("Link 3: Missing EVIDENCE trace", r3.deficiencies)

        # 4. Break Link 4 (Physical Object)
        r4 = audit_takeoff_row_provenance(dict(base_valid_row, location=""))
        self.assertFalse(r4.complete_chain)
        self.assertIn("Link 4: Missing PHYSICAL OBJECT trace", r4.deficiencies)

        # 5. Break Link 5 (Canonical Object)
        r5 = audit_takeoff_row_provenance(dict(base_valid_row, source_reference="User Override", row_role=""))
        self.assertFalse(r5.complete_chain)
        self.assertIn("Link 5: Missing CANONICAL OBJECT trace", r5.deficiencies)

        # 6. Break Link 6 (Quantity)
        r6_zero = audit_takeoff_row_provenance(dict(base_valid_row, quantity=0.0))
        self.assertFalse(r6_zero.complete_chain)
        self.assertTrue(any("Link 6: Invalid QUANTITY" in d for d in r6_zero.deficiencies))

        r6_unit = audit_takeoff_row_provenance(dict(base_valid_row, unit="gallons"))
        self.assertFalse(r6_unit.complete_chain)
        self.assertTrue(any("Link 6: Invalid QUANTITY" in d for d in r6_unit.deficiencies))

        # 7. Break Link 7 (Takeoff Row Core Fields)
        row_missing_field = dict(base_valid_row)
        del row_missing_field["substrate"]
        r7 = audit_takeoff_row_provenance(row_missing_field)
        self.assertFalse(r7.complete_chain)
        self.assertTrue(any("Link 7: Missing core takeoff fields" in d for d in r7.deficiencies))

    def test_ag14_workspace_database_audit_end_to_end(self) -> None:
        """Verify database workspace audit querying SQLite and cross-checking documents."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            app = MockAuditApp(tmp.name)
            app.lexecute("INSERT INTO documents (workspace_id, file_name, path) VALUES (?, ?, ?)", (1, "sample_plans.pdf", "/uploads/sample_plans.pdf"))
            
            # Insert 2 passing rows and 1 deficient row
            app.lexecute(
                """INSERT INTO takeoff_rows (
                    workspace_id, section, element, location, substrate, finish_system,
                    quantity, unit, quantity_status, source_page, source_reference,
                    inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                    rate_per_unit, confidence, notes, row_role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    1, "External", "Wall", "Perimeter · W1", "Brick", "Paint",
                    45.5, "m²", "Measured", "p.1", "PB Canonical BIM · wall:W1",
                    "INCLUSION", 1, 0, 0, 0, "Documented", "Net wall 45.5 m² [Doc: sample_plans.pdf]", "external_wall", "2026-10-02", "2026-10-02"
                )
            )
            app.lexecute(
                """INSERT INTO takeoff_rows (
                    workspace_id, section, element, location, substrate, finish_system,
                    quantity, unit, quantity_status, source_page, source_reference,
                    inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                    rate_per_unit, confidence, notes, row_role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    1, "Internal", "Door", "D01 · on W1", "Timber", "Paint",
                    1.0, "No.", "Measured", "p.1", "PB Canonical BIM · opening:D01",
                    "INCLUSION", 1, 0, 0, 0, "Documented", "Door D01 measured [Doc: sample_plans.pdf]", "door", "2026-10-02", "2026-10-02"
                )
            )
            # Deficient row: missing doc, zero qty
            app.lexecute(
                """INSERT INTO takeoff_rows (
                    workspace_id, section, element, location, substrate, finish_system,
                    quantity, unit, quantity_status, source_page, source_reference,
                    inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                    rate_per_unit, confidence, notes, row_role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    1, "Unknown", "Ghost", "Nowhere", "Unknown", "None",
                    0.0, "m²", "Estimated", "", "Custom Calc",
                    "INCLUSION", 1, 0, 0, 0, "Low", "No doc no evidence", "", "2026-10-02", "2026-10-02"
                )
            )

            summary = audit_workspace_takeoff_provenance(app, 1)
            self.assertEqual(summary.total_rows, 3)
            self.assertEqual(summary.passed_rows, 2)
            self.assertEqual(summary.failed_rows, 1)
            self.assertAlmostEqual(summary.pass_rate, 0.6667, places=3)
            self.assertTrue(len(summary.deficiencies) > 0)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def test_ag14_auto_geometry_customer_runtime_provenance_parity(self) -> None:
        """Prove that customer runtime net wall auto geometry rows pass the 7-link audit."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            app = MockAuditApp(tmp.name)
            ws_id = 42
            rows = _try_physical_net_wall_rows(app, ws_id, [], {})
            self.assertIsNotNone(rows)
            self.assertEqual(len(rows), 1)

            report = audit_takeoff_row_provenance(
                rows[0],
                known_docs=["3LAUREL_ARCHITECTURAL_REV_B.pdf"],
            )
            self.assertTrue(
                report.complete_chain,
                f"Customer runtime row failed 7-link provenance: {report.deficiencies}",
            )
            self.assertEqual(report.quantity, 28.2)
            self.assertEqual(report.unit, "m²")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
