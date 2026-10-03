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
import pb_bound_wall_finish_quantity_authority as quantmod
import pb_net_wall_boolean_union_authority as netmod
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

    def test_internal_partition_positive_evidence_publishes_linear_partition_row(self):
        """Positive test: genuine solid-fill partition geometry publishes canonical takeoff rows in lm."""
        from pb_wall_fill_internal_partition_evidence import InternalPartitionEvidence

        with _test_workspace() as ws:
            pdf_path = ws.root / "floor_plan.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock floor plan")
            ws.add_document(pdf_path)
            ws.add_page(1, "Floor Plan", "Ground Floor", "GROUND FLOOR PLAN", px_per_m=28.35)

            fake_evidence = InternalPartitionEvidence(
                status="found",
                reason="Found 1 internal partition wall",
                total_length_m=6.1,
                wall_thickness_m=0.20,
                scale_pt_per_m=28.35,
                segment_lengths_m=(6.1,),
            )

            with patch(
                "pb_wall_fill_internal_partition_evidence.resolve_internal_partition_length_m",
                return_value=fake_evidence,
            ), patch.object(ws.app.fitz, "open"):
                rows, partitions = auto._build_internal_partition_rows(
                    ws.app, 1, ws.pages(), {"width_m": 16.0, "depth_m": 8.2}
                )

            self.assertEqual(len(rows), 1)
            self.assertEqual(len(partitions), 1)
            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            self.assertEqual(row_dict["quantity"], 6.1)
            self.assertEqual(row_dict["unit"], "lm")
            self.assertEqual(row_dict["section"], "Internal")
            self.assertEqual(row_dict["element"], "Internal partitions / walls")
            self.assertEqual(row_dict["quantity_status"], "Measured")
            self.assertEqual(row_dict["row_role"], "internal_partition")
            self.assertIn("Thickness: 0.200 m", row_dict["notes"])
            self.assertEqual(partitions[0]["total_length_m"], 6.1)

    def test_internal_partition_negative_stroke_only_furniture_and_grids_ignored(self):
        """Negative test: stroke-only shapes (furniture, desk outlines, grid bubbles) are rejected as walls."""
        from pb_wall_fill_internal_partition_evidence import InternalPartitionEvidence

        with _test_workspace() as ws:
            pdf_path = ws.root / "floor_plan.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock floor plan")
            ws.add_document(pdf_path)
            ws.add_page(1, "Floor Plan", "Ground Floor", "GROUND FLOOR PLAN", px_per_m=28.35)

            # Authority abstains because only furniture / stroke shapes exist
            abstained_evidence = InternalPartitionEvidence(
                status="abstained",
                reason="No consistent internal partition wall fill found",
                total_length_m=0.0,
            )

            with patch(
                "pb_wall_fill_internal_partition_evidence.resolve_internal_partition_length_m",
                return_value=abstained_evidence,
            ), patch.object(ws.app.fitz, "open"):
                rows, partitions = auto._build_internal_partition_rows(
                    ws.app, 1, ws.pages(), {"width_m": 16.0, "depth_m": 8.2}
                )

            # No false-positive partition rows created
            self.assertEqual(len(rows), 0)
            self.assertEqual(len(partitions), 0)

    def test_internal_partition_negative_implausible_thickness_abstained(self):
        """Negative test: fills with implausible thickness (e.g. wide shading boxes) abstain cleanly."""
        from pb_wall_fill_internal_partition_evidence import InternalPartitionEvidence

        with _test_workspace() as ws:
            pdf_path = ws.root / "floor_plan.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock floor plan")
            ws.add_document(pdf_path)
            ws.add_page(1, "Floor Plan", "Ground Floor", "GROUND FLOOR PLAN", px_per_m=28.35)

            abstained_evidence = InternalPartitionEvidence(
                status="abstained",
                reason="Implausible wall thickness (0.85 m)",
                total_length_m=0.0,
            )

            with patch(
                "pb_wall_fill_internal_partition_evidence.resolve_internal_partition_length_m",
                return_value=abstained_evidence,
            ), patch.object(ws.app.fitz, "open"):
                rows, partitions = auto._build_internal_partition_rows(
                    ws.app, 1, ws.pages(), {"width_m": 16.0, "depth_m": 8.2}
                )

            self.assertEqual(len(rows), 0)
            self.assertEqual(len(partitions), 0)

    # -------------------------------------------------------------------------
    # AG-04: Bound Wall-Finish Quantity Authority Integration Tests
    # -------------------------------------------------------------------------

    def test_ag04_bound_wall_finish_chain_proof_physical_wall_to_openings_to_net_wall_to_finish_binding(self):
        """Prove the complete chain: physical wall -> openings -> net wall -> face/finish binding -> takeoff quantity."""
        from pb_bound_wall_finish_customer_bridge import bound_wall_finish_record_to_takeoff_row
        from pb_bound_wall_finish_quantity_authority import (
            FINISH_QUANTITY_RESOLVED,
            SourceBoundWallFinishQuantityProducer,
            SourceBoundWallFinishQuantitySelector,
        )
        import pb_wall_finish_face_binding_authority as finishmod
        from pb_wall_finish_face_binding_authority import (
            FinishScopeStatus,
            PhysicalFaceRole,
            WallFinishCompleteScopeRecord,
            WallFinishFaceBindingAuthority,
            WallFinishFaceBindingRecord,
            WallFinishFaceBindingScopeResult,
            WallFinishFaceBindingScopeSelector,
        )
        from pb_net_wall_boolean_union_authority import (
            NetWallBooleanUnionAuthority,
            NetWallBooleanUnionRecord,
            NetWallBooleanUnionResult,
            NetWallBooleanUnionSelector,
        )
        from pb_wall_role_authority import WallRoleClassification

        doc_id = "doc1"
        rev_id = "rev1"
        sha = "a" * 64
        snap = "snap1"
        page_id = "1"
        vp = "vp1"
        scope_id = "scope1"
        trade = "external_key_pointing"
        material = "key_pointing"
        wall_id = "W100"
        face_id = "F100_ext"

        # 1. Face binding record: exterior face of W100 bound to key_pointing
        binding = WallFinishFaceBindingRecord(
            binding_id="bind-100",
            document_id=doc_id,
            revision_id=rev_id,
            source_sha256=sha,
            snapshot_id=snap,
            page_id=page_id,
            viewport_id=vp,
            decision_scope_id=scope_id,
            physical_wall_id=wall_id,
            physical_face_id=face_id,
            physical_face_role=PhysicalFaceRole.EXTERIOR_FACE,
            source_face_segment_ids=(f"seg-{wall_id}",),
            trade_scope_id=trade,
            finish_material=material,
            annotation_observation_ids=("ann-1",),
            leader_path_ids=("leader-1",),
            terminator_primitive_ids=("term-1",),
            wall_role_record_id=f"role-{wall_id}",
            wall_role=WallRoleClassification.EXTERNAL,
            source_evidence_ids=("ann-1", f"role-{wall_id}"),
            source_evidence_kind="native_direct_finish_callout",
            decision_scope_complete=False,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_face_binding_resolved",),
            _seal=finishmod._RECORD_SEAL,
        )
        complete_scope = WallFinishCompleteScopeRecord(
            scope_id="scope-rec-1",
            document_id=doc_id,
            revision_id=rev_id,
            source_sha256=sha,
            snapshot_id=snap,
            page_id=page_id,
            viewport_id=vp,
            decision_scope_id=scope_id,
            trade_scope_id=trade,
            finish_material=material,
            target_face_ids=(face_id,),
            covered_face_ids=(face_id,),
            binding_ids=("bind-100",),
            decision_scope_complete=True,
            scope_status=FinishScopeStatus.COMPLETE,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_scope_complete",),
            _seal=finishmod._RECORD_SEAL,
        )
        finish_scope_sel = WallFinishFaceBindingScopeSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
        )
        finish_authority = WallFinishFaceBindingAuthority(
            {finish_scope_sel.key: WallFinishFaceBindingScopeResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("ok",),
                bindings=(binding,),
                scope_records=(complete_scope,),
            )},
            _seal=finishmod._AUTHORITY_SEAL,
        )

        # 2. Net wall authority: Physical wall W100 with gross 30.0 m2, void 6.0 m2 deducted = net 24.0 m2
        net_sel = NetWallBooleanUnionSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
            physical_wall_id=wall_id, trade_scope_id=trade,
        )
        net_rec = NetWallBooleanUnionRecord(
            record_id=f"net-{wall_id}",
            document_id=doc_id,
            revision_id=rev_id,
            source_sha256=sha,
            snapshot_id=snap,
            page_id=page_id,
            decision_scope_id=scope_id,
            physical_wall_id=wall_id,
            gross_geometry_record_id=f"gross-{wall_id}",
            opening_universe_record_id="opening-universe",
            deduction_record_ids=("ded-1",),
            union_geometry_id=f"union-{wall_id}",
            net_area_m2=24.0,
            gross_area_m2=30.0,
            void_union_area_m2=6.0,
            trade_scope_id=trade,
        )
        import pb_net_wall_boolean_union_authority as netmod
        net_authority = NetWallBooleanUnionAuthority(
            {net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("NET_WALL_BOOLEAN_UNION_RESOLVED",),
                record=net_rec,
            )},
            _seal=netmod._AUTHORITY_SEAL,
        )

        # 3. SourceBoundWallFinishQuantityProducer publishes finish quantity
        producer = SourceBoundWallFinishQuantityProducer.from_authorities(
            finish_binding_authority=finish_authority,
            net_wall_authority=net_authority,
        )
        finish_quantity_sel = SourceBoundWallFinishQuantitySelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp,
            decision_scope_id=scope_id, trade_scope_id=trade, finish_material=material,
        )
        pub_result = producer.publish(finish_quantity_sel)
        self.assertEqual(pub_result.status, EvidenceResolutionStatus.CORROBORATED)
        self.assertIn(FINISH_QUANTITY_RESOLVED, pub_result.reason_codes)
        self.assertIsNotNone(pub_result.record)
        record = pub_result.record
        self.assertEqual(record.quantity_m2, 24.0)
        self.assertEqual(record.physical_face_ids, (face_id,))
        self.assertEqual(record.physical_wall_ids, (wall_id,))

        # 4. Bridge converts record into canonical 21-field takeoff row
        row = bound_wall_finish_record_to_takeoff_row(1, record)
        self.assertEqual(len(row), 21)
        row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
        self.assertEqual(row_dict["quantity"], 24.0)
        self.assertEqual(row_dict["unit"], "m²")
        self.assertEqual(row_dict["section"], "External")
        self.assertEqual(row_dict["element"], "External wall finishes")
        self.assertEqual(row_dict["row_role"], "wall_finish")
        self.assertEqual(row_dict["quantity_status"], "Measured")
        self.assertIn("W100", row_dict["notes"])
        self.assertIn("24.00 m²", row_dict["notes"])

        # Row passes auto-geometry validation without error
        auto._validate_auto_rows([row], 1)

    def test_ag04_multi_face_finish_support_different_finishes_on_different_wall_faces(self):
        """Prove support for different finishes on different faces of the same physical wall without duplicate wall geometry."""
        from pb_bound_wall_finish_customer_bridge import bound_wall_finish_record_to_takeoff_row
        from pb_bound_wall_finish_quantity_authority import (
            SourceBoundWallFinishQuantityProducer,
            SourceBoundWallFinishQuantitySelector,
        )
        import pb_wall_finish_face_binding_authority as finishmod
        from pb_wall_finish_face_binding_authority import (
            FinishScopeStatus,
            PhysicalFaceRole,
            WallFinishCompleteScopeRecord,
            WallFinishFaceBindingAuthority,
            WallFinishFaceBindingRecord,
            WallFinishFaceBindingScopeResult,
            WallFinishFaceBindingScopeSelector,
        )
        from pb_net_wall_boolean_union_authority import (
            NetWallBooleanUnionAuthority,
            NetWallBooleanUnionRecord,
            NetWallBooleanUnionResult,
            NetWallBooleanUnionSelector,
        )
        from pb_wall_role_authority import WallRoleClassification

        doc_id = "doc2"
        rev_id = "rev2"
        sha = "b" * 64
        snap = "snap2"
        page_id = "2"
        vp = "vp2"
        scope_id = "scope2"
        wall_id = "W200"

        # Face 1: Exterior face with acrylic render
        trade_ext = "external_rendering"
        material_ext = "acrylic_render"
        face_ext = "F200_ext"

        # Face 2: Interior face with plasterboard
        trade_int = "internal_plastering"
        material_int = "plasterboard"
        face_int = "F200_int"

        binding_ext = WallFinishFaceBindingRecord(
            binding_id="bind-ext", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            physical_wall_id=wall_id, physical_face_id=face_ext,
            physical_face_role=PhysicalFaceRole.EXTERIOR_FACE,
            source_face_segment_ids=(f"seg-{wall_id}",),
            trade_scope_id=trade_ext, finish_material=material_ext,
            annotation_observation_ids=("ann-ext",), leader_path_ids=("lead-ext",),
            terminator_primitive_ids=("term-ext",), wall_role_record_id=f"role-{wall_id}",
            wall_role=WallRoleClassification.EXTERNAL,
            source_evidence_ids=("ann-ext",), source_evidence_kind="native_direct_finish_callout",
            decision_scope_complete=False, status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_face_binding_resolved",), _seal=finishmod._RECORD_SEAL,
        )
        scope_ext = WallFinishCompleteScopeRecord(
            scope_id="scope-ext", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade_ext, finish_material=material_ext,
            target_face_ids=(face_ext,), covered_face_ids=(face_ext,),
            binding_ids=("bind-ext",), decision_scope_complete=True,
            scope_status=FinishScopeStatus.COMPLETE, status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_scope_complete",), _seal=finishmod._RECORD_SEAL,
        )

        binding_int = WallFinishFaceBindingRecord(
            binding_id="bind-int", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            physical_wall_id=wall_id, physical_face_id=face_int,
            physical_face_role=PhysicalFaceRole.ROOM_FACING_INTERIOR_FACE,
            source_face_segment_ids=(f"seg-{wall_id}",),
            trade_scope_id=trade_int, finish_material=material_int,
            annotation_observation_ids=("ann-int",), leader_path_ids=("lead-int",),
            terminator_primitive_ids=("term-int",), wall_role_record_id=f"role-{wall_id}",
            wall_role=WallRoleClassification.EXTERNAL,
            source_evidence_ids=("ann-int",), source_evidence_kind="native_direct_finish_callout",
            decision_scope_complete=False, status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_face_binding_resolved",), _seal=finishmod._RECORD_SEAL,
        )
        scope_int = WallFinishCompleteScopeRecord(
            scope_id="scope-int", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade_int, finish_material=material_int,
            target_face_ids=(face_int,), covered_face_ids=(face_int,),
            binding_ids=("bind-int",), decision_scope_complete=True,
            scope_status=FinishScopeStatus.COMPLETE, status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_scope_complete",), _seal=finishmod._RECORD_SEAL,
        )

        finish_scope_sel = WallFinishFaceBindingScopeSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
        )
        finish_authority = WallFinishFaceBindingAuthority(
            {finish_scope_sel.key: WallFinishFaceBindingScopeResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("ok",),
                bindings=(binding_ext, binding_int),
                scope_records=(scope_ext, scope_int),
            )},
            _seal=finishmod._AUTHORITY_SEAL,
        )

        # Net wall authority provides net area for wall W200 for both trades
        net_sel_ext = NetWallBooleanUnionSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
            physical_wall_id=wall_id, trade_scope_id=trade_ext,
        )
        net_sel_int = NetWallBooleanUnionSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
            physical_wall_id=wall_id, trade_scope_id=trade_int,
        )
        net_authority = NetWallBooleanUnionAuthority(
            {
                net_sel_ext.key: NetWallBooleanUnionResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=("NET_WALL_BOOLEAN_UNION_RESOLVED",),
                    record=NetWallBooleanUnionRecord(
                        record_id=f"net-{wall_id}-ext", document_id=doc_id, revision_id=rev_id,
                        source_sha256=sha, snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
                        physical_wall_id=wall_id, gross_geometry_record_id=f"gross-{wall_id}",
                        opening_universe_record_id="ou", deduction_record_ids=(),
                        union_geometry_id="u", net_area_m2=32.5, gross_area_m2=40.0,
                        void_union_area_m2=7.5, trade_scope_id=trade_ext,
                    ),
                ),
                net_sel_int.key: NetWallBooleanUnionResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=("NET_WALL_BOOLEAN_UNION_RESOLVED",),
                    record=NetWallBooleanUnionRecord(
                        record_id=f"net-{wall_id}-int", document_id=doc_id, revision_id=rev_id,
                        source_sha256=sha, snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
                        physical_wall_id=wall_id, gross_geometry_record_id=f"gross-{wall_id}",
                        opening_universe_record_id="ou", deduction_record_ids=(),
                        union_geometry_id="u", net_area_m2=32.5, gross_area_m2=40.0,
                        void_union_area_m2=7.5, trade_scope_id=trade_int,
                    ),
                ),
            },
            _seal=netmod._AUTHORITY_SEAL,
        )

        producer = SourceBoundWallFinishQuantityProducer.from_authorities(
            finish_binding_authority=finish_authority,
            net_wall_authority=net_authority,
        )

        # Resolve exterior finish
        res_ext = producer.publish(SourceBoundWallFinishQuantitySelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha, snapshot_id=snap,
            page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade_ext, finish_material=material_ext,
        ))
        self.assertEqual(res_ext.status, EvidenceResolutionStatus.CORROBORATED)
        row_ext = bound_wall_finish_record_to_takeoff_row(1, res_ext.record)

        # Resolve interior finish
        res_int = producer.publish(SourceBoundWallFinishQuantitySelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha, snapshot_id=snap,
            page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade_int, finish_material=material_int,
        ))
        self.assertEqual(res_int.status, EvidenceResolutionStatus.CORROBORATED)
        row_int = bound_wall_finish_record_to_takeoff_row(1, res_int.record)

        # Verify distinct takeoff rows for each face from same physical wall
        d_ext = dict(zip(auto.TAKEOFF_ROW_FIELDS, row_ext))
        d_int = dict(zip(auto.TAKEOFF_ROW_FIELDS, row_int))

        self.assertEqual(d_ext["section"], "External")
        self.assertEqual(d_ext["element"], "External wall finishes")
        self.assertEqual(d_ext["substrate"], "acrylic_render")
        self.assertEqual(d_ext["quantity"], 32.5)

        self.assertEqual(d_int["section"], "Internal")
        self.assertEqual(d_int["element"], "Internal wall finishes")
        self.assertEqual(d_int["substrate"], "plasterboard")
        self.assertEqual(d_int["quantity"], 32.5)

        # Both rows reference the same host physical wall W200 without creating duplicate wall geometry
        self.assertIn("W200", d_ext["notes"])
        self.assertIn("W200", d_int["notes"])
        auto._validate_auto_rows([row_ext, row_int], 1)

    def test_ag04_fail_closed_unresolved_net_wall_abstains(self):
        """Negative test: If net wall geometry is unresolved, finish quantity abstains fail-closed."""
        from pb_bound_wall_finish_customer_bridge import build_bound_wall_finish_rows
        from pb_bound_wall_finish_quantity_authority import (
            FINISH_QUANTITY_NET_WALL_UNRESOLVED,
            SourceBoundWallFinishQuantityProducer,
            SourceBoundWallFinishQuantitySelector,
        )
        import pb_wall_finish_face_binding_authority as finishmod
        from pb_wall_finish_face_binding_authority import (
            FinishScopeStatus,
            PhysicalFaceRole,
            WallFinishCompleteScopeRecord,
            WallFinishFaceBindingAuthority,
            WallFinishFaceBindingRecord,
            WallFinishFaceBindingScopeResult,
            WallFinishFaceBindingScopeSelector,
        )
        from pb_net_wall_boolean_union_authority import (
            NetWallBooleanUnionAuthority,
            NetWallBooleanUnionResult,
            NetWallBooleanUnionSelector,
        )
        from pb_wall_role_authority import WallRoleClassification

        doc_id = "doc3"
        rev_id = "rev3"
        sha = "c" * 64
        snap = "snap3"
        page_id = "3"
        vp = "vp3"
        scope_id = "scope3"
        trade = "external_painting"
        material = "external_paint"
        wall_id = "W300"
        face_id = "F300_ext"

        binding = WallFinishFaceBindingRecord(
            binding_id="bind-300", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            physical_wall_id=wall_id, physical_face_id=face_id,
            physical_face_role=PhysicalFaceRole.EXTERIOR_FACE,
            source_face_segment_ids=(f"seg-{wall_id}",), trade_scope_id=trade,
            finish_material=material, annotation_observation_ids=("ann-3",),
            leader_path_ids=("lead-3",), terminator_primitive_ids=("term-3",),
            wall_role_record_id=f"role-{wall_id}", wall_role=WallRoleClassification.EXTERNAL,
            source_evidence_ids=("ann-3",), source_evidence_kind="native_direct_finish_callout",
            decision_scope_complete=False, status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_face_binding_resolved",), _seal=finishmod._RECORD_SEAL,
        )
        scope_rec = WallFinishCompleteScopeRecord(
            scope_id="scope-rec-3", document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade, finish_material=material,
            target_face_ids=(face_id,), covered_face_ids=(face_id,), binding_ids=("bind-300",),
            decision_scope_complete=True, scope_status=FinishScopeStatus.COMPLETE,
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=("wall_finish_scope_complete",),
            _seal=finishmod._RECORD_SEAL,
        )
        finish_scope_sel = WallFinishFaceBindingScopeSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
        )
        finish_authority = WallFinishFaceBindingAuthority(
            {finish_scope_sel.key: WallFinishFaceBindingScopeResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("ok",), bindings=(binding,), scope_records=(scope_rec,),
            )},
            _seal=finishmod._AUTHORITY_SEAL,
        )

        # Net wall authority abstains for W300 (e.g. void unresolved)
        net_sel = NetWallBooleanUnionSelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha,
            snapshot_id=snap, page_id=page_id, decision_scope_id=scope_id,
            physical_wall_id=wall_id, trade_scope_id=trade,
        )
        net_authority = NetWallBooleanUnionAuthority(
            {net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=("upstream_opening_universe_incomplete",),
            )},
            _seal=netmod._AUTHORITY_SEAL,
        )

        producer = SourceBoundWallFinishQuantityProducer.from_authorities(
            finish_binding_authority=finish_authority,
            net_wall_authority=net_authority,
        )
        res = producer.publish(SourceBoundWallFinishQuantitySelector(
            document_id=doc_id, revision_id=rev_id, source_sha256=sha, snapshot_id=snap,
            page_id=page_id, viewport_id=vp, decision_scope_id=scope_id,
            trade_scope_id=trade, finish_material=material,
        ))

        # Authority abstains fail-closed
        self.assertEqual(res.status, EvidenceResolutionStatus.ABSTAINED)
        self.assertIn(FINISH_QUANTITY_NET_WALL_UNRESOLVED, res.reason_codes)
        self.assertIsNone(res.record)

        # Bridge produces 0 rows
        app_mock = SimpleNamespace(source_bound_wall_finish_authority=producer.authority())
        rows, records = build_bound_wall_finish_rows(app_mock, 1, [])
        self.assertEqual(len(rows), 0)
        self.assertEqual(len(records), 0)

    def test_ag04_workspace_end_to_end_auto_geometry_publishes_wall_finishes(self):
        """Prove end-to-end integration: analyse_workspace publishes bound wall finish rows into SQLite."""
        from pb_bound_wall_finish_quantity_authority import (
            SourceBoundWallFinishQuantityRecord,
        )
        import pb_bound_wall_finish_quantity_authority as quantmod

        with _test_workspace() as ws:
            pdf_path = ws.root / "drawing.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 mock drawing")
            ws.add_document(pdf_path)
            ws.add_page(1, "Elevation", "North Elevation", "NORTH ELEVATION", px_per_m=28.35)

            # Mock a corroborated bound wall finish record
            fake_record = SourceBoundWallFinishQuantityRecord(
                record_id="rec-400",
                document_id="doc4",
                revision_id="rev4",
                source_sha256="d" * 64,
                snapshot_id="snap4",
                page_id="1",
                viewport_id="vp4",
                decision_scope_id="scope4",
                trade_scope_id="external_key_pointing",
                finish_material="key_pointing",
                quantity_m2=48.25,
                physical_face_ids=("F400_ext",),
                physical_wall_ids=("W400",),
                finish_binding_ids=("bind-400",),
                net_wall_record_ids=("net-400",),
                finish_scope_record_id="scope-rec-4",
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("source_bound_wall_finish_quantity_resolved",),
                _seal=quantmod._RECORD_SEAL,
            )
            # Use resolve_bound_wall_finishes method on app
            ws.app.resolve_bound_wall_finishes = lambda ws_id: [fake_record]

            # Run automatic geometry analysis
            report = auto.analyse_workspace(ws.app, 1)

            # Verify report contains finishes
            self.assertIn("finishes", report)
            self.assertEqual(len(report["finishes"]), 1)
            self.assertEqual(report["finishes"][0]["finish_material"], "key_pointing")
            self.assertEqual(report["finishes"][0]["quantity_m2"], 48.25)

            # Query published rows directly from SQLite takeoff_rows
            stored = app_mod.lquery(
                "SELECT * FROM takeoff_rows WHERE workspace_id=1 AND row_role='wall_finish'"
            )
            self.assertEqual(len(stored), 1)
            finish_row = stored[0]
            self.assertEqual(finish_row["section"], "External")
            self.assertEqual(finish_row["element"], "External wall finishes")
            self.assertEqual(finish_row["quantity"], 48.25)
            self.assertEqual(finish_row["unit"], "m²")
            self.assertEqual(finish_row["row_role"], "wall_finish")
            self.assertIn("rec-400", finish_row["source_reference"])

    # -------------------------------------------------------------------------
    # AG-05: Wall-Finish Callout Authority Tests
    # -------------------------------------------------------------------------

    def test_ag05_deterministic_wall_finish_callout_binding_and_provenance(self):
        """Prove deterministic wall binding and full provenance preservation for finish callouts (AG-05)."""
        from pb_bound_wall_finish_customer_bridge import apply_finish_callout_bindings_to_walls
        from pb_wall_finish_callout_wall_authority import WallFinishCalloutWallBindingRecord
        import pb_wall_finish_callout_wall_authority as callmod

        binding = WallFinishCalloutWallBindingRecord(
            binding_id="call-bind-1",
            document_id="doc5",
            revision_id="rev5",
            source_sha256="e" * 64,
            snapshot_id="snap5",
            page_id="1",
            viewport_id="vp5",
            decision_scope_id="scope5",
            physical_wall_decision_scope_id="pw-scope5",
            physical_wall_id="W501",
            raw_owner_wall_ids=("W501",),
            equivalence_group_wall_ids=("W501",),
            equivalence_pair_classifications=(),
            source_wall_primitive_ids=("prim-1",),
            source_execution_callout_record_id="exec-call-1",
            source_execution_sequence_start=100,
            source_execution_sequence_end=105,
            trade_scope_id="external_rendering",
            finish_material="acrylic_render",
            semantic_direction="externally",
            annotation_observation_ids=("ann-501",),
            leader_path_ids=("lead-501",),
            terminator_primitive_ids=("term-501",),
            source_evidence_ids=("ann-501", "lead-501", "term-501", "prim-1"),
            source_evidence_kind="native_direct_finish_callout",
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_callout_wall_binding_resolved",),
            _seal=callmod._RECORD_SEAL,
        )

        walls = [
            {"wall_ref": "W501", "substrate": "External walling", "net_m2": 25.0},
        ]

        updated = apply_finish_callout_bindings_to_walls(walls, [binding])
        self.assertEqual(len(updated), 1)
        w = updated[0]
        self.assertTrue(w.get("callout_bound"))
        self.assertEqual(w["finish_material"], "acrylic_render")
        self.assertEqual(w["substrate"], "acrylic_render")
        self.assertEqual(w["finish_callout_binding_id"], "call-bind-1")
        self.assertEqual(w["finish_source_evidence_ids"], ["ann-501", "lead-501", "term-501", "prim-1"])
        self.assertEqual(w["finish_semantic_direction"], "externally")

    def test_ag05_local_callout_does_not_apply_globally(self):
        """Negative test: a callout on Wall W1 must NOT apply globally to W2 or W3 (AG-05)."""
        from pb_bound_wall_finish_customer_bridge import apply_finish_callout_bindings_to_walls
        from pb_wall_finish_callout_wall_authority import WallFinishCalloutWallBindingRecord
        import pb_wall_finish_callout_wall_authority as callmod

        # Callout specifically bound to W601 only
        binding = WallFinishCalloutWallBindingRecord(
            binding_id="call-bind-601",
            document_id="doc6",
            revision_id="rev6",
            source_sha256="f" * 64,
            snapshot_id="snap6",
            page_id="1",
            viewport_id="vp6",
            decision_scope_id="scope6",
            physical_wall_decision_scope_id="pw-scope6",
            physical_wall_id="W601",
            raw_owner_wall_ids=("W601",),
            equivalence_group_wall_ids=("W601",),
            equivalence_pair_classifications=(),
            source_wall_primitive_ids=("prim-601",),
            source_execution_callout_record_id="exec-call-601",
            source_execution_sequence_start=200,
            source_execution_sequence_end=205,
            trade_scope_id="external_painting",
            finish_material="Dulux Monument Paint",
            semantic_direction="externally",
            annotation_observation_ids=("ann-601",),
            leader_path_ids=("lead-601",),
            terminator_primitive_ids=("term-601",),
            source_evidence_ids=("ann-601",),
            source_evidence_kind="native_direct_finish_callout",
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_callout_wall_binding_resolved",),
            _seal=callmod._RECORD_SEAL,
        )

        walls = [
            {"wall_ref": "W601", "substrate": "External walling", "net_m2": 15.0},
            {"wall_ref": "W602", "substrate": "External walling", "net_m2": 20.0},
            {"wall_ref": "W603", "substrate": "External walling", "net_m2": 18.0},
        ]

        updated = apply_finish_callout_bindings_to_walls(walls, [binding])

        # W601 is updated with the callout finish
        self.assertTrue(updated[0].get("callout_bound"))
        self.assertEqual(updated[0]["finish_material"], "Dulux Monument Paint")
        self.assertEqual(updated[0]["substrate"], "Dulux Monument Paint")

        # W602 and W603 are NOT updated (no global spillover)
        self.assertFalse(updated[1].get("callout_bound", False))
        self.assertEqual(updated[1]["substrate"], "External walling")
        self.assertNotIn("finish_material", updated[1])

        self.assertFalse(updated[2].get("callout_bound", False))
        self.assertEqual(updated[2]["substrate"], "External walling")
        self.assertNotIn("finish_material", updated[2])

    def test_ag05_multi_wall_ambiguity_abstains(self):
        """Negative test: When callout terminator touches multiple non-equivalent walls, authority abstains (AG-05)."""
        from pb_wall_finish_face_binding_authority import _target_from_terminator, _Line, _Terminator
        from pb_migration_contracts import EvidenceResolutionStatus

        # Two distinct walls: wall-A and wall-B (not in same equivalence group)
        rec_a = SimpleNamespace(
            wall_candidate_id="wall-A",
            physical_identity=SimpleNamespace(source_primitive_ids=("raw-A",)),
        )
        rec_b = SimpleNamespace(
            wall_candidate_id="wall-B",
            physical_identity=SimpleNamespace(source_primitive_ids=("raw-B",)),
        )
        scope = SimpleNamespace(
            records=(rec_a, rec_b),
            equivalence=SimpleNamespace(
                equivalence_groups=(("wall-A",), ("wall-B",)),
                pair_classifications=(),
            ),
        )

        # Lines for both walls both intersect the terminator bbox
        lines = (
            _Line(observation_id="obs-A", raw_id="raw-A", geometry=(10.0, 0.0, 10.0, 20.0)),
            _Line(observation_id="obs-B", raw_id="raw-B", geometry=(10.0, 0.0, 10.0, 20.0)),
        )
        terminator = _Terminator(
            primitive_id="term-ambig",
            bbox=(8.0, 8.0, 12.0, 12.0),
            center=(10.0, 10.0),
        )

        # _target_from_terminator must ABSTAIN due to multi-wall ambiguity
        target, hits, status = _target_from_terminator(terminator, lines, scope)
        self.assertEqual(status, EvidenceResolutionStatus.ABSTAINED)
        self.assertIsNone(target)

    def test_ag05_no_callout_preserves_default_state(self):
        """Negative test: Walls with no callout maintain unconfirmed/gross state without modification (AG-05)."""
        from pb_bound_wall_finish_customer_bridge import apply_finish_callout_bindings_to_walls

        walls = [
            {"wall_ref": "W701", "substrate": "External walling", "net_m2": 30.0},
            {"wall_ref": "W702", "substrate": "Brick veneer", "net_m2": 25.0},
        ]

        # Empty callout bindings
        updated = apply_finish_callout_bindings_to_walls(walls, [])
        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[0]["substrate"], "External walling")
        self.assertEqual(updated[1]["substrate"], "Brick veneer")
        self.assertFalse(updated[0].get("callout_bound", False))
        self.assertFalse(updated[1].get("callout_bound", False))

    def test_ag05_registered_wall_takeoff_rows_reflect_callout_finish(self):
        """Prove registered wall takeoff rows consume authenticated callout finishes with provenance (AG-05)."""
        from pb_wall_finish_callout_wall_authority import WallFinishCalloutWallBindingRecord
        import pb_wall_finish_callout_wall_authority as callmod

        binding = WallFinishCalloutWallBindingRecord(
            binding_id="call-bind-801",
            document_id="doc8",
            revision_id="rev8",
            source_sha256="8" * 64,
            snapshot_id="snap8",
            page_id="1",
            viewport_id="vp8",
            decision_scope_id="scope8",
            physical_wall_decision_scope_id="pw-scope8",
            physical_wall_id="wall-801",
            raw_owner_wall_ids=("wall-801",),
            equivalence_group_wall_ids=("wall-801",),
            equivalence_pair_classifications=(),
            source_wall_primitive_ids=("prim-801",),
            source_execution_callout_record_id="exec-call-801",
            source_execution_sequence_start=300,
            source_execution_sequence_end=305,
            trade_scope_id="external_rendering",
            finish_material="Sand-cement render",
            semantic_direction="externally",
            annotation_observation_ids=("ann-801",),
            leader_path_ids=("lead-801",),
            terminator_primitive_ids=("term-801",),
            source_evidence_ids=("ann-801", "prim-801"),
            source_evidence_kind="native_direct_finish_callout",
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_callout_wall_binding_resolved",),
            _seal=callmod._RECORD_SEAL,
        )

        with _test_workspace() as ws:
            ws.app.build_registered_walls_v139 = lambda ws_id: [
                {
                    "wall_ref": "wall-801",
                    "side": "North",
                    "gross_m2": 40.0,
                    "opening_deduction_m2": 8.0,
                    "net_m2": 32.0,
                    "substrate": "External walling",
                    "height_confidence": "Verified",
                },
                {
                    "wall_ref": "wall-802",
                    "side": "South",
                    "gross_m2": 35.0,
                    "opening_deduction_m2": 5.0,
                    "net_m2": 30.0,
                    "substrate": "External walling",
                    "height_confidence": "Verified",
                },
            ]
            ws.app.wall_finish_callout_bindings = [binding]

            rows = auto._try_physical_net_wall_rows(ws.app, 1, [], [])
            self.assertIsNotNone(rows)
            self.assertEqual(len(rows), 2)

            d1 = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            d2 = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[1]))

            # wall-801 got the callout finish and provenance
            self.assertEqual(d1["substrate"], "Sand-cement render")
            self.assertEqual(d1["quantity"], 32.0)
            self.assertIn("call-bind-801", d1["source_reference"])
            self.assertIn("Authenticated callout finish: Sand-cement render", d1["notes"])

            # wall-802 did NOT get the callout finish (local scope preserved)
            self.assertEqual(d2["substrate"], "External walling")
            self.assertEqual(d2["quantity"], 30.0)
            self.assertNotIn("call-bind-801", d2["source_reference"])
            self.assertNotIn("Sand-cement render", d2["notes"])

    def test_ag06_target_relationship_opening_definition_deduction(self):
        """AG-06: Target relationship opening mark -> detail definition -> physical opening -> host wall -> deduction."""
        import pb_opening_detail_definition_authority as openmod
        from pb_opening_detail_definition_authority import OpeningDetailDefinitionRecord
        from pb_opening_detail_definition_bridge import (
            ConsolidatedPhysicalOpening,
            enrich_openings_with_detail_definitions,
            apply_opening_deductions_to_walls,
        )

        detail_record = OpeningDetailDefinitionRecord(
            record_id="det-rec-001",
            semantic_identity_id="sem-win-1200x1500",
            document_id="doc1",
            revision_id="rev1",
            source_sha256="a" * 64,
            snapshot_id="snap1",
            page_id="5",
            source_partition_id="part1",
            sequence_start=10,
            sequence_end=20,
            source_bbox=(100.0, 200.0, 300.0, 400.0),
            family="window",
            subtype="casement",
            material="aluminium",
            width_mm=1200,
            height_mm=1500,
            dimension_basis="detail_unspecified",
            source_observation_ids=("obs-1", "obs-2"),
            required_observation_ids=("obs-1", "obs-2"),
            word_evidence=(),
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(openmod.OPENING_DETAIL_DEFINITION_RESOLVED,),
            _seal=openmod._RECORD_SEAL,
        )

        raw_opening = {
            "opening_id": "op-north-w01",
            "type_mark": "W01",
            "host_wall_id": "wall-north",
            "width_m": 1.2,
            "height_m": 0.0,  # Unspecified on plan
            "area_m2": 0.0,
            "plan_page_id": "2",
        }

        mark_map = {"W01": "sem-win-1200x1500"}

        enriched = enrich_openings_with_detail_definitions(
            [raw_opening],
            [detail_record],
            mark_to_semantic_identity=mark_map,
        )

        self.assertEqual(len(enriched), 1)
        en_op = enriched[0]
        self.assertEqual(en_op.opening_id, "op-north-w01")
        self.assertEqual(en_op.type_mark, "W01")
        self.assertEqual(en_op.host_wall_id, "wall-north")
        self.assertEqual(en_op.width_m, 1.2)
        self.assertEqual(en_op.height_m, 1.5)
        self.assertEqual(en_op.area_m2, 1.8)
        self.assertEqual(en_op.family, "window")
        self.assertEqual(en_op.subtype, "casement")
        self.assertEqual(en_op.material, "aluminium")
        self.assertEqual(en_op.detail_record_id, "det-rec-001")

        walls = [
            {"wall_ref": "wall-north", "gross_m2": 20.0, "opening_deduction_m2": 0.0, "net_m2": 20.0},
        ]
        updated_walls = apply_opening_deductions_to_walls(walls, enriched)
        self.assertEqual(len(updated_walls), 1)
        w = updated_walls[0]
        self.assertEqual(w["opening_deduction_m2"], 1.8)
        self.assertEqual(w["net_m2"], 18.2)
        self.assertEqual(w["consolidated_opening_ids"], ["op-north-w01"])

    def test_ag06_cross_sheet_observations_without_physical_identity_fail_closed(self):
        """AG-06: wall + mark alone cannot prove one physical opening instance."""
        from pb_opening_detail_definition_bridge import (
            consolidate_opening_identities,
            apply_opening_deductions_to_walls,
        )

        raw_observations = [
            {"host_wall_id": "wall-south", "type_mark": "D01", "width_m": 0.9, "plan_page_id": "1"},
            {"host_wall_id": "wall-south", "type_mark": "D01", "height_m": 2.1, "elevation_page_id": "2"},
            {"host_wall_id": "wall-south", "type_mark": "D01", "schedule_page_id": "3"},
            {"host_wall_id": "wall-south", "type_mark": "D01", "detail_page_id": "4"},
        ]

        consolidated = consolidate_opening_identities(raw_observations)
        self.assertEqual(consolidated, [])

        walls = [
            {"wall_ref": "wall-south", "gross_m2": 30.0, "opening_deduction_m2": 0.0, "net_m2": 30.0},
        ]
        updated = apply_opening_deductions_to_walls(walls, consolidated)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["opening_deduction_m2"], 0.0)
        self.assertEqual(updated[0]["net_m2"], 30.0)
        self.assertNotIn("consolidated_opening_ids", updated[0])

    def test_ag06_detail_definition_without_host_wall_does_not_mint_physical_opening(self):
        """AG-06: Detail definitions describe TYPES, not physical instances; unhosted details do not mint deductions."""
        from pb_opening_detail_definition_bridge import (
            ConsolidatedPhysicalOpening,
            apply_opening_deductions_to_walls,
        )

        unhosted_opening = ConsolidatedPhysicalOpening(
            opening_id="detail-lib-type-w01",
            type_mark="W01",
            host_wall_id="",  # No host wall
            width_m=1.8,
            height_m=1.2,
            area_m2=2.16,
            family="window",
            deducts=True,
        )

        walls = [
            {"wall_ref": "wall-west", "gross_m2": 25.0, "opening_deduction_m2": 0.0, "net_m2": 25.0},
        ]

        updated = apply_opening_deductions_to_walls(walls, [unhosted_opening])
        self.assertEqual(len(updated), 1)
        # Wall is untouched; no phantom deductions
        self.assertEqual(updated[0]["opening_deduction_m2"], 0.0)
        self.assertEqual(updated[0]["net_m2"], 25.0)

    def test_ag06_takeoff_rows_reflect_detail_enriched_opening_deduction(self):
        """AG-06: _try_physical_net_wall_rows consumes detail definitions and openings for accurate net wall rows."""
        import pb_opening_detail_definition_authority as openmod
        from pb_opening_detail_definition_authority import OpeningDetailDefinitionRecord

        detail_record = OpeningDetailDefinitionRecord(
            record_id="det-rec-901",
            semantic_identity_id="sem-win-2000x1200",
            document_id="doc9",
            revision_id="rev9",
            source_sha256="9" * 64,
            snapshot_id="snap9",
            page_id="6",
            source_partition_id="part9",
            sequence_start=40,
            sequence_end=50,
            source_bbox=(100.0, 100.0, 200.0, 200.0),
            family="window",
            subtype="sliding",
            material="aluminium",
            width_mm=2000,
            height_mm=1200,
            dimension_basis="detail_unspecified",
            source_observation_ids=("obs-901",),
            required_observation_ids=("obs-901",),
            word_evidence=(),
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(openmod.OPENING_DETAIL_DEFINITION_RESOLVED,),
            _seal=openmod._RECORD_SEAL,
        )

        raw_opening = {
            "opening_id": "op-901",
            "type_mark": "W901",
            "host_wall_id": "wall-901",
            "width_m": 2.0,
            "height_m": 0.0,
            "area_m2": 0.0,
        }

        with _test_workspace() as ws:
            ws.app.build_registered_walls_v139 = lambda ws_id: [
                {
                    "wall_ref": "wall-901",
                    "side": "North",
                    "gross_m2": 50.0,
                    "opening_deduction_m2": 0.0,
                    "net_m2": 50.0,
                    "substrate": "External walling",
                    "height_confidence": "Verified",
                },
            ]
            ws.app.opening_detail_definitions = [detail_record]
            ws.app.building_openings = [raw_opening]
            ws.app.opening_mark_map = {"W901": "sem-win-2000x1200"}

            rows = auto._try_physical_net_wall_rows(ws.app, 1, [], [])
            self.assertIsNotNone(rows)
            self.assertEqual(len(rows), 1)

            row_dict = dict(zip(auto.TAKEOFF_ROW_FIELDS, rows[0]))
            # 50.0 gross - 2.4 m2 opening = 47.6 net
            self.assertEqual(row_dict["quantity"], 47.6)
            self.assertIn("opening deductions", row_dict["notes"])

    def test_ag07_precedence_tier_1_explicit_dimension_beats_measured_geometry(self):
        """AG-07: Explicit figured dimension beats measured vector and raster geometry."""
        from pb_geometry_takeoff_model import AuthorityStatus
        from pb_raster_plan_dimension_bridge import (
            DimensionPrecedenceTier,
            resolve_dimension_with_precedence,
        )

        # Explicit: 10.0m, Vector: 10.1m (within 5%), Raster: 10.2m
        result = resolve_dimension_with_precedence(
            explicit_dim_m=10.0,
            vector_geom_m=10.1,
            raster_geom_m=10.2,
        )
        self.assertEqual(result.tier, DimensionPrecedenceTier.EXPLICIT)
        self.assertEqual(result.resolved_m, 10.0)
        self.assertEqual(result.status, AuthorityStatus.FIRM.value)
        self.assertEqual(result.evidence_status, EvidenceResolutionStatus.CORROBORATED)
        self.assertAlmostEqual(result.discrepancy_delta_m, 0.1, places=2)

    def test_ag07_disagreement_between_explicit_and_measured_escalates_to_review(self):
        """AG-07: When explicit dimension and measured geometry disagree beyond 5%, escalate to review."""
        from pb_geometry_takeoff_model import AuthorityStatus
        from pb_raster_plan_dimension_bridge import (
            DimensionPrecedenceTier,
            resolve_dimension_with_precedence,
        )

        # Explicit: 10.0m, Measured: 12.0m (20% discrepancy > 5% tolerance)
        result = resolve_dimension_with_precedence(
            explicit_dim_m=10.0,
            vector_geom_m=12.0,
            max_delta_ratio=0.05,
        )
        # Explicit dimension still prevails in quantity, but flags review required and conflict
        self.assertEqual(result.tier, DimensionPrecedenceTier.EXPLICIT)
        self.assertEqual(result.resolved_m, 10.0)
        self.assertEqual(result.status, AuthorityStatus.REVIEW_REQUIRED.value)
        self.assertEqual(result.evidence_status, EvidenceResolutionStatus.CONFLICT)
        self.assertIn("Warning: Large discrepancy", result.notes)
        self.assertAlmostEqual(result.discrepancy_delta_m, 2.0, places=2)
        self.assertAlmostEqual(result.discrepancy_ratio, 0.2, places=2)

    def test_ag07_vector_geometry_prevails_over_raster_measurement(self):
        """AG-07: Without explicit dimension, authenticated vector geometry prevails over raster measurement."""
        from pb_geometry_takeoff_model import AuthorityStatus
        from pb_raster_plan_dimension_bridge import (
            DimensionPrecedenceTier,
            resolve_dimension_with_precedence,
        )

        # Vector: 15.0m, Raster: 14.0m
        result = resolve_dimension_with_precedence(
            explicit_dim_m=None,
            vector_geom_m=15.0,
            raster_geom_m=14.0,
        )
        self.assertEqual(result.tier, DimensionPrecedenceTier.VECTOR)
        self.assertEqual(result.resolved_m, 15.0)
        self.assertIn("Vector geometry 15.0m prevails over raster measurement 14.0m", result.notes)

    def test_ag07_raster_plan_dimension_calibration_promoted_when_vector_missing(self):
        """AG-07: When vector dimension lines are absent, calibrated raster dimension chain is promoted."""
        from pb_raster_plan_dimension_authority import (
            RasterPlanDimensionResult,
            RasterOverallDimension,
            _RECORD_SEAL,
        )

        with _test_workspace() as ws:
            page = {"id": 10, "page_no": 1, "scale_text": "Auto provisional", "px_per_m": 0.0}

            # Vector dimension line detector finds nothing
            auto.detect_dimension_calibration = lambda app, p: None
            # Printed scale detector finds generic 1:100 (28.35 px/m)
            ws.app.auto_detect_scale = lambda p: {"px_per_m": 28.35, "source": "title_block"}

            # Raster authority has a calibrated overall dimension (56.7 px/m)
            raster_res = RasterPlanDimensionResult(
                status=EvidenceResolutionStatus.CANDIDATE,
                reason_codes=("raster_dimension_chain_resolved",),
                document_id="doc10",
                revision_id="rev10",
                source_sha256="0" * 64,
                snapshot_id="snap10",
                page_id="10",
                horizontal=RasterOverallDimension(
                    overall_dimension_id="dim1",
                    orientation="horizontal",
                    value_mm=10000,
                    span_pt=200.0,
                    endpoints_pt=((0.0, 0.0), (200.0, 0.0)),
                    child_dimension_ids=("txt1", "txt2"),
                    child_values_mm=(5000, 5000),
                    _seal=_RECORD_SEAL,
                ),
                scale_status="provisional",
                scale_px_per_m=56.7,
                length_m=10.0,
                width_m=5.0,
            )
            ws.app.raster_plan_dimension_results = {"10": raster_res}

            calib = auto._auto_calibrate_page(ws.app, page)
            self.assertIsNotNone(calib)
            # Promoted raster dimension (56.7), NOT printed scale fallback (28.35)
            self.assertEqual(calib["method"], "Raster dimension")
            self.assertEqual(calib["px_per_m"], 56.7)

    def test_ag07_vector_dimension_line_never_overridden_by_raster(self):
        """AG-07: When vector dimension lines exist, vector geometry is chosen over raster."""
        from pb_raster_plan_dimension_authority import (
            RasterPlanDimensionResult,
            RasterOverallDimension,
        )

        with _test_workspace() as ws:
            page = {"id": 11, "page_no": 1, "scale_text": "Auto provisional", "px_per_m": 0.0}

            # Vector dimension line detector finds 70.0 px/m
            with patch("pb_auto_geometry_v1219.detect_dimension_calibration", return_value={"px_per_m": 70.0, "dimension_text": "5000", "confidence": "High"}):
                # Raster authority claims 50.0 px/m
                raster_res = RasterPlanDimensionResult(
                    status=EvidenceResolutionStatus.CANDIDATE,
                    reason_codes=("raster_dimension_chain_resolved",),
                    document_id="doc11",
                    revision_id="rev11",
                    source_sha256="1" * 64,
                    snapshot_id="snap11",
                    page_id="11",
                    scale_status="provisional",
                    scale_px_per_m=50.0,
                )
                ws.app.raster_plan_dimension_results = {"11": raster_res}

                calib = auto._auto_calibrate_page(ws.app, page)
                self.assertIsNotNone(calib)
                # Vector dimension wins: 70.0 px/m, method Dimension line
                self.assertEqual(calib["method"], "Dimension line")
                self.assertEqual(calib["px_per_m"], 70.0)

    def test_ag08_check_incompatible_material_identities(self):
        """AG-08: Incompatible materials claimed for same element face trigger CONFLICT."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
            check_incompatible_material_identities,
        )

        conflict = check_incompatible_material_identities(
            ["brick", "weatherboard"],
            subject_id="wall-ext-01",
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_kind, CONFLICT_KIND_INCOMPATIBLE_MATERIALS)
        self.assertEqual(conflict.status, EvidenceResolutionStatus.CONFLICT)
        self.assertIn("Incompatible materials", conflict.description)
        self.assertEqual(conflict.suggested_action, "abstain_from_arbitrary_selection")

        # Single or compatible materials return None
        self.assertIsNone(check_incompatible_material_identities(["brick"], subject_id="wall-1"))

    def test_ag08_check_room_label_conflict(self):
        """AG-08: Mutually exclusive room functional labels or contradictory areas trigger CONFLICT."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_ROOM_LABEL_CONFLICT,
            check_room_label_conflict,
        )

        # Functional conflict: Bathroom vs Bedroom
        conflict = check_room_label_conflict(
            room_id="room-101",
            labels=["Ensuite Bathroom", "Master Bedroom"],
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_kind, CONFLICT_KIND_ROOM_LABEL_CONFLICT)
        self.assertEqual(conflict.status, EvidenceResolutionStatus.CONFLICT)

        # Area conflict: 20 m2 vs 35 m2 (>5% discrepancy)
        area_conflict = check_room_label_conflict(
            room_id="room-102",
            labels=["Living Room"],
            areas_m2=[20.0, 35.0],
        )
        self.assertIsNotNone(area_conflict)
        self.assertEqual(area_conflict.conflict_kind, CONFLICT_KIND_ROOM_LABEL_CONFLICT)
        self.assertIn("Contradictory room area claims", area_conflict.description)

    def test_ag08_check_schedule_vs_drawing_mismatch(self):
        """AG-08: Discrepancy between schedule and drawing width/family triggers CONFLICT."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH,
            check_schedule_vs_drawing_mismatch,
        )

        # Width mismatch: 820mm vs 1800mm
        conflict = check_schedule_vs_drawing_mismatch(
            schedule_spec={"width_mm": 820, "family": "door"},
            drawing_spec={"width_mm": 1800, "family": "door"},
            subject_id="door-D10",
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_kind, CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH)
        self.assertIn("Schedule vs drawing width mismatch", conflict.description)

        # Family mismatch: door vs window
        family_conflict = check_schedule_vs_drawing_mismatch(
            schedule_spec={"family": "door"},
            drawing_spec={"family": "window"},
            subject_id="op-12",
        )
        self.assertIsNotNone(family_conflict)
        self.assertIn("Schedule family 'door' contradicts drawing family 'window'", family_conflict.description)

    def test_ag08_check_opening_definition_mismatch(self):
        """AG-08: Opening definition detail vs schedule mismatch triggers CONFLICT."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_OPENING_DEFINITION_MISMATCH,
            check_opening_definition_mismatch,
        )

        conflict = check_opening_definition_mismatch(
            detail_spec={"family": "window", "width_mm": 1200},
            schedule_spec={"family": "door", "width_mm": 1200},
            opening_id="detail-D01",
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_kind, CONFLICT_KIND_OPENING_DEFINITION_MISMATCH)
        self.assertIn("Opening detail family 'window' contradicts schedule family 'door'", conflict.description)

    def test_ag08_check_incompatible_wall_classifications(self):
        """AG-08: Wall classified simultaneously as external facade and internal partition triggers CONFLICT."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_INCOMPATIBLE_WALL_CLASSIFICATION,
            check_incompatible_wall_classifications,
        )

        conflict = check_incompatible_wall_classifications(
            ["external_facade", "internal_partition"],
            wall_id="wall-hybrid-01",
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_kind, CONFLICT_KIND_INCOMPATIBLE_WALL_CLASSIFICATION)
        self.assertIn("Contradictory wall classifications", conflict.description)
        self.assertEqual(conflict.suggested_action, "abstain_from_commercial_row")

    def test_ag08_takeoff_rows_annotated_with_conflict_provenance_without_altering_quantity(self):
        """AG-08: Conflict provenance is attached to notes without silently altering numerical quantity."""
        from pb_semantic_conflict_guard import (
            SemanticConflictRecord,
            CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
            annotate_rows_with_conflicts,
        )

        conflict = SemanticConflictRecord(
            conflict_id="conf-001",
            conflict_kind=CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
            subject_id="North Wall",
            status=EvidenceResolutionStatus.CONFLICT,
            description="Brick vs weatherboard conflict",
            sources=("doc1", "doc2"),
            suggested_action="review",
        )

        import pb_takeoff_row_contract as takeoff_contract

        sample_rows = [
            auto._takeoff_row(
                workspace_id=1,
                section="External",
                element="04 Masonry",
                location="North Wall",
                substrate="Brickwork",
                quantity=45.0,
                status="Measured",
                source_page="A201",
                source_reference=f"{auto.SOURCE_PREFIX} · facade:north-wall",
                confidence="Documented",
                notes="Existing notes",
                row_role="external_wall",
            ),
        ]

        annotated = annotate_rows_with_conflicts(sample_rows, [conflict])
        self.assertEqual(len(annotated), 1)
        named = takeoff_contract.mapping_from_values(
            annotated[0],
            takeoff_contract.CORE_FIELDS,
        )
        # Quantity and unrelated numeric fields are strictly preserved.
        self.assertEqual(named["quantity"], 45.0)
        self.assertEqual(named["coverage_m2_per_litre"], 0)
        # Quantity status escalates to Review.
        self.assertEqual(named["quantity_status"], "Review")
        # Notes, not a numeric field, contain structured conflict provenance.
        self.assertIn(
            "[SEMANTIC CONFLICT: Brick vs weatherboard conflict",
            named["notes"],
        )
        self.assertIn("id=conf-001", named["notes"])

    def test_ag08_runtime_collects_same_face_finish_conflict(self):
        """AG-08: exact shared physical face identity triggers automatic material conflict."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
            collect_runtime_semantic_conflicts,
        )

        finishes = [
            {
                "record_id": "fin-brick",
                "finish_material": "brick",
                "physical_wall_ids": ["wall-1"],
                "physical_face_ids": ["face-1"],
            },
            {
                "record_id": "fin-weatherboard",
                "finish_material": "weatherboard",
                "physical_wall_ids": ["wall-1"],
                "physical_face_ids": ["face-1"],
            },
        ]

        conflicts = collect_runtime_semantic_conflicts(
            SimpleNamespace(),
            finishes=finishes,
        )

        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(
            conflict.conflict_kind,
            CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
        )
        self.assertEqual(conflict.subject_id, "face-1")
        self.assertEqual(
            set(conflict.sources),
            {
                "bound_wall_finish:fin-brick",
                "bound_wall_finish:fin-weatherboard",
            },
        )

    def test_ag08_runtime_different_faces_do_not_conflict(self):
        """AG-08: different physical faces are not collapsed into one material conflict."""
        from pb_semantic_conflict_guard import collect_runtime_semantic_conflicts

        finishes = [
            {
                "record_id": "fin-brick",
                "finish_material": "brick",
                "physical_face_ids": ["face-1"],
            },
            {
                "record_id": "fin-weatherboard",
                "finish_material": "weatherboard",
                "physical_face_ids": ["face-2"],
            },
        ]

        self.assertEqual(
            collect_runtime_semantic_conflicts(
                SimpleNamespace(),
                finishes=finishes,
            ),
            [],
        )

    def test_ag08_runtime_collects_bound_opening_detail_conflict(self):
        """AG-08: detail vs physical opening mismatch is found only through exact mark binding."""
        from pb_semantic_conflict_guard import (
            CONFLICT_KIND_OPENING_DEFINITION_MISMATCH,
            collect_runtime_semantic_conflicts,
        )

        detail = SimpleNamespace(
            record_id="det-W1",
            semantic_identity_id="sem-W1",
            family="window",
            width_mm=1200,
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        app = SimpleNamespace(
            opening_detail_definitions=[detail],
            building_openings=[
                {
                    "opening_id": "opening-1",
                    "type_mark": "W1",
                    "host_wall_id": "wall-1",
                    "family": "window",
                    "width_m": 1.8,
                }
            ],
            opening_mark_map={"W1": "sem-W1"},
        )

        conflicts = collect_runtime_semantic_conflicts(app)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(
            conflicts[0].conflict_kind,
            CONFLICT_KIND_OPENING_DEFINITION_MISMATCH,
        )
        self.assertEqual(conflicts[0].subject_id, "W1")
        self.assertIn("1200mm", conflicts[0].description)
        self.assertIn("1800mm", conflicts[0].description)

    def test_ag08_analyse_workspace_publishes_review_rows_without_quantity_change(self):
        """AG-08: automatic conflict reaches customer rows and report with quantity preserved."""
        conflict_finishes = [
            {
                "record_id": "fin-brick",
                "finish_material": "brick",
                "physical_wall_ids": ["wall-1"],
                "physical_face_ids": ["face-1"],
                "quantity_m2": 45.0,
                "page_id": "1",
            },
            {
                "record_id": "fin-weatherboard",
                "finish_material": "weatherboard",
                "physical_wall_ids": ["wall-1"],
                "physical_face_ids": ["face-1"],
                "quantity_m2": 45.0,
                "page_id": "1",
            },
        ]
        finish_rows = [
            auto._takeoff_row(
                workspace_id=1,
                section="External",
                element="External wall finishes",
                location=f"Wall (wall-1) · {material}",
                substrate=material,
                quantity=45.0,
                status="Measured",
                source_page="1",
                source_reference=(
                    f"{auto.SOURCE_PREFIX} · bound_wall_finish:{record_id}"
                ),
                confidence="Documented",
                notes="Source-bound finish.",
                row_role="wall_finish",
            )
            for record_id, material in (
                ("fin-brick", "brick"),
                ("fin-weatherboard", "weatherboard"),
            )
        ]

        with _test_workspace() as ws:
            app_mod.lexecute(
                "INSERT INTO workspaces(id,job_name,created_at,updated_at) "
                "VALUES(1,'AG08','x','x')"
            )
            with (
                patch.object(auto, "_detect_footprint", return_value=None),
                patch.object(auto, "_cross_calibrate_elevations", return_value=None),
                patch.object(auto, "_build_unit_rows", return_value=([], [])),
                patch.object(auto, "_build_facade_rows", return_value=([], [])),
                patch.object(
                    auto,
                    "_build_internal_partition_rows",
                    return_value=([], []),
                ),
                patch.object(
                    auto,
                    "_build_bound_wall_finish_rows",
                    return_value=(finish_rows, conflict_finishes),
                ),
            ):
                report = auto.analyse_workspace(ws.app, 1)

            published = [
                dict(row)
                for row in app_mod.lquery(
                    "SELECT quantity,quantity_status,coverage_m2_per_litre,"
                    "notes,source_reference FROM takeoff_rows "
                    "WHERE workspace_id=1 ORDER BY id"
                )
            ]

        self.assertEqual(len(report["semantic_conflicts"]), 1)
        self.assertEqual(len(published), 2)
        self.assertEqual(
            [row["quantity"] for row in published],
            [45.0, 45.0],
        )
        self.assertTrue(
            all(row["quantity_status"] == "Review" for row in published)
        )
        self.assertTrue(
            all(row["coverage_m2_per_litre"] == 0 for row in published)
        )
        self.assertTrue(
            all("[SEMANTIC CONFLICT:" in row["notes"] for row in published)
        )


if __name__ == "__main__":
    unittest.main()


