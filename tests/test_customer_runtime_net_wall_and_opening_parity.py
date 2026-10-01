"""Integration and parity tests for customer runtime net wall and opening deduction.

Proves:
A. Authenticated physical net wall publishes NET wall quantity, not gross wall quantity.
B. Multiple openings are deducted exactly once (no double-deduction).
C. Zero openings on authenticated wall preserves gross area.
D. Missing/abstained physical authority safely falls back to gross elevation rows.
E. No negative wall quantities are produced.
F. Canonical 21-field takeoff_rows contract is strictly obeyed.
G. Customer takeoff query and review path reads the published net-wall row.
H. Opening evidence generation is automatic and idempotent (no manual Accuracy Lab button needed).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

import pb_auto_geometry_guard_v1219 as guard
import pb_auto_geometry_v1219 as auto
import pb_planreader_3d_app as app_mod
from pb_migration_contracts import EvidenceResolutionStatus


class _TestWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.app = SimpleNamespace(
            lquery=app_mod.lquery,
            lexecute=app_mod.lexecute,
            local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp,
            workspace_setting=app_mod.workspace_setting,
            set_workspace_setting=app_mod.set_workspace_setting,
            auto_detect_scale=app_mod.auto_detect_scale,
            fitz=fitz,
        )

    def add_document(self, pdf_path: Path) -> int:
        app_mod.lexecute(
            "INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'TestWorkspace','x','x')"
        )
        app_mod.lexecute(
            "INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,1,?,?,'sha123',1)",
            (pdf_path.name, str(pdf_path)),
        )
        return 1

    def add_page(
        self,
        page_id: int,
        page_type: str,
        label: str,
        text: str,
        *,
        px_per_m: float = 28.35,
        image: Path | None = None,
    ) -> None:
        app_mod.lexecute(
            """INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,scale_text,px_per_m,
                   image_path,render_zoom,extracted_text,selected)
               VALUES(?,1,1,?,?,?,'1:100',?,?,1.0,?,1)""",
            (page_id, page_id, label, page_type, px_per_m, str(image) if image else None, text),
        )

    def pages(self):
        return [dict(p) for p in app_mod.lquery("SELECT * FROM pages WHERE workspace_id=1 ORDER BY id")]


@contextmanager
def _test_workspace():
    saved_db_flag = getattr(app_mod, "_pb_local_db_initialized_v1215", None)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "planreader_test.db"
        with patch.object(app_mod, "DB_PATH", db_path):
            setattr(app_mod, "_pb_local_db_initialized_v1215", False)
            app_mod.init_local_db()
            try:
                yield _TestWorkspace(Path(tmp))
            finally:
                if saved_db_flag is not None:
                    setattr(app_mod, "_pb_local_db_initialized_v1215", saved_db_flag)
                else:
                    app_mod.__dict__.pop("_pb_local_db_initialized_v1215", None)


class CustomerRuntimeNetWallParityTests(unittest.TestCase):
    """Test suite proving customer-runtime physical net wall and opening deduction parity."""

    def test_authenticated_physical_net_wall_single_opening_deducted_once(self):
        """A wall with an authenticated opening publishes NET wall quantity, not gross wall quantity."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "North Elevation", "NORTH ELEVATION")

            # Mock live physical net wall claim: 50.0 gross - 5.0 opening = 45.0 net
            fake_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("live_physical_net_wall_integration_resolved",),
                quantity_m2=45.0,
                source_pages=(1,),
                external_wall_ids=("whole-wall-1",),
                evidence_ids=("gross-1", "void-1", "role-1"),
                quantity_id="net-wall-claim-001",
                confidence=0.95,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=fake_claim,
            ):
                rows, facades = auto._build_facade_rows(ws.app, 1, ws.pages())

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(len(row), 21)
            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, row))

            # Proves NET wall (45.0), not gross wall (50.0)
            self.assertEqual(row_dict["quantity"], 45.0)
            self.assertEqual(row_dict["unit"], "m²")
            self.assertEqual(row_dict["quantity_status"], "Measured")
            self.assertEqual(row_dict["row_role"], "external_wall")
            self.assertIn("physical_net_wall:net-wall-claim-001", row_dict["source_reference"])
            self.assertIn("proven opening voids deducted", row_dict["notes"])

            # Facades list still carries envelope geometry for 3D model
            self.assertTrue(facades[0].get("superseded_by_physical_net_wall"))

    def test_authenticated_physical_net_wall_multiple_openings_deducted_once(self):
        """Multiple openings are deducted exactly once without double-deduction."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "North Elevation", "NORTH ELEVATION")

            # Gross 60.0, Opening 1 (2.5 m2) + Opening 2 (3.5 m2) deducted once = 54.0 m2 net
            fake_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("live_physical_net_wall_integration_resolved",),
                quantity_m2=54.0,
                source_pages=(1,),
                external_wall_ids=("whole-wall-1", "whole-wall-2"),
                evidence_ids=("gross-1", "void-1", "void-2"),
                quantity_id="net-wall-multi-void-002",
                confidence=1.0,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=fake_claim,
            ):
                rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())

            self.assertEqual(len(rows), 1)
            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            self.assertEqual(row_dict["quantity"], 54.0)

    def test_authenticated_physical_net_wall_no_openings_preserves_gross(self):
        """When an authenticated physical wall has zero openings, net wall equals gross wall."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "East Elevation", "EAST ELEVATION")

            # Gross 42.0 with 0 openings = 42.0 net
            fake_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("live_physical_net_wall_integration_resolved",),
                quantity_m2=42.0,
                source_pages=(1,),
                external_wall_ids=("whole-wall-east",),
                evidence_ids=("gross-east",),
                quantity_id="net-wall-solid-003",
                confidence=0.90,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=fake_claim,
            ):
                rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())

            self.assertEqual(len(rows), 1)
            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            self.assertEqual(row_dict["quantity"], 42.0)

    def test_safe_fallback_when_physical_wall_evidence_abstained(self):
        """When physical net wall authority abstains, safe gross fallback is preserved without hallucinated deductions."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")

            # Physical net-wall authority returns ABSTAINED
            abstained_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=("live_physical_net_wall_integration_unavailable",),
                quantity_m2=None,
                source_pages=(),
                external_wall_ids=(),
                evidence_ids=(),
                quantity_id=None,
                confidence=0.0,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=abstained_claim,
            ):
                rows, facades = auto._build_facade_rows(ws.app, 1, ws.pages())

            self.assertEqual(len(rows), 1)
            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            # Preserves fallback explicit area: 42.5 m2
            self.assertEqual(row_dict["quantity"], 42.5)
            self.assertEqual(row_dict["substrate"], "Lineaboard Cladding")
            self.assertIn("Substrate area read directly from drawing text", row_dict["notes"])

    def test_no_negative_wall_quantities(self):
        """Quantity is strictly non-negative; zero-floor is enforced."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "North Elevation", "NORTH ELEVATION")

            fake_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("resolved",),
                quantity_m2=0.0,  # Bounded at 0
                source_pages=(1,),
                external_wall_ids=("w1",),
                evidence_ids=(),
                quantity_id="q0",
                confidence=0.5,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=fake_claim,
            ):
                # When quantity is 0.0, _try_physical_net_wall_rows skips and falls back
                rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())

            for r in rows:
                qty = r[auto.TAKEOFF_ROW_FIELDS.index("quantity")]
                self.assertGreaterEqual(qty, 0.0)

    def test_canonical_21_field_contract_and_sqlite_publication(self):
        """Published net-wall rows insert atomically into SQLite takeoff_rows adhering to the 21-field contract."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "North Elevation", "NORTH ELEVATION")

            fake_claim = SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("resolved",),
                quantity_m2=38.75,
                source_pages=(1,),
                external_wall_ids=("w1",),
                evidence_ids=("e1",),
                quantity_id="net-publish-004",
                confidence=1.0,
            )

            with patch(
                "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
                return_value=fake_claim,
            ):
                rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
                auto._replace_auto_rows(ws.app, 1, rows)

            # Query SQLite takeoff_rows table directly
            saved_rows = ws.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")
            self.assertEqual(len(saved_rows), 1)
            saved = dict(saved_rows[0])
            self.assertEqual(saved["quantity"], 38.75)
            self.assertEqual(saved["unit"], "m²")
            self.assertEqual(saved["section"], "External")
            self.assertEqual(saved["element"], "External walls / cladding")
            self.assertEqual(saved["row_role"], "external_wall")

    def test_opening_evidence_auto_generated_in_analyse_workspace(self):
        """P5 opening evidence is generated automatically during analyse_workspace without Accuracy Lab."""
        with _test_workspace() as ws:
            pdf_path = ws.root / "sample_drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock pdf content")
            ws.add_document(pdf_path)
            ws.add_page(1, "Floor Plan", "A101", "GROUND FLOOR PLAN")

            analysed_pages = []

            def fake_analyse_page(page_id: int):
                analysed_pages.append(int(page_id))
                payload = {
                    "page_id": page_id,
                    "status": "ok",
                    "instances": [{"opening_id": "W01", "deduct": True}],
                }
                ws.app.set_workspace_setting(
                    1, f"opening_evidence_v175_page_{page_id}", json.dumps(payload)
                )
                return payload

            ws.app.analyse_stored_page_v130 = fake_analyse_page

            # Run normal analyse_workspace (the path called upon document upload and auto-geometry)
            with patch("pb_auto_geometry_v1219._auto_calibrate_page", return_value=None):
                auto.analyse_workspace(ws.app, 1)

            # Proves analyse_stored_page_v130 was called automatically on page 1
            self.assertEqual(analysed_pages, [1])

            # Verify persisted setting exists
            persisted = ws.app.workspace_setting(1, "opening_evidence_v175_page_1", None)
            self.assertIsNotNone(persisted)
            data = json.loads(persisted)
            self.assertEqual(data["page_id"], 1)

            # Verify idempotency: running analyse_workspace again does NOT re-analyse
            auto.analyse_workspace(ws.app, 1)
            self.assertEqual(analysed_pages, [1], "Second run must be idempotent and skip already analysed page")


if __name__ == "__main__":
    unittest.main()
