"""Tests for genuine source-owned Maryborough Office FT3 floor finish chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (9.05352 m2),
   1 customer row, and verified sealed run.
2. Floor subset authority returns the identical verified 1-quantity / 1-row result.
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing source words (get_text empty)
   - missing dimension witness ('3570')
   - missing door callout ('D15')
   - missing finish mark ('FT3')
   - competing finish marks in box ('EPX' + 'FT3')
   - missing wall bounding on support or target sheet
   - shifted / un-unique registration translation
   - conflicting correspondence record
4. Exact seal and customer row bijection passing verify_sealed_customer_output.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

import pb_maryborough_customer_authority as authority
import pb_maryborough_floor_area_customer as floor_authority
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_cross_view_floor_correspondence_shadow import (
    COMPETING_FINISH_CODES_IN_BOX,
    REGISTRATION_NOT_UNIQUE,
    BOX_NOT_WALL_BOUNDED,
    DOORWAY_TRANSITION_UNAVAILABLE,
    DIMENSION_WITNESS_UNAVAILABLE,
    EvidenceResolutionStatus,
    SourceCrossViewFloorCorrespondenceRecord,
    authenticate_maryborough_office_cross_sheet_correspondence,
    resolve_cross_sheet_floor_correspondence_for_claim,
)

VALID_SYNTHETIC_OBSERVATIONS = {
    "door_observations": [{"callout": "D15"}],
    "schedule_observations": [{"door_callout": "D15", "door_width_mm": 920.0}],
    "dimension_witness_observations": [{"code": "3570"}, {"code": "2536"}],
    "room_label_observations": [{"label": "OFFICE"}],
}


@pytest.fixture
def maryborough_pdf_path() -> Path:
    path = Path(
        os.environ.get(
            "PLANREADER_ORIGINAL_MARYBOROUGH",
            "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
        )
    )
    if not path.is_file():
        pytest.skip("private original Maryborough PDF unavailable in test environment")
    return path


def test_genuine_maryborough_office_ft3_complete_chain(maryborough_pdf_path):
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.reason_codes == ("source_owned_physical_quantity_resolved",)
    assert len(result.quantities) == 1
    assert len(result.traces) == 1
    assert len(result.customer_rows) == 1
    assert result.sealed_run is not None

    q = result.quantities[0]
    assert q.family == "floor_finish_area"
    assert q.value == 9.05352
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert authority.OFFICE_PHYSICAL_FLOOR_ID in q.input_entity_ids

    row = result.customer_rows[0]
    assert row["quantity"] == 9.05352
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["row_role"] == "floor_area"

    # Verify 1-to-1 sealed customer output
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_genuine_maryborough_office_ft3_floor_subset_chain(maryborough_pdf_path):
    result = floor_authority.issue_original_maryborough_floor_customer_areas(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.reason_codes == ("source_owned_physical_quantity_resolved",)
    assert len(result.quantities) == 1
    assert len(result.customer_rows) == 1
    assert result.sealed_run is not None

    q = result.quantities[0]
    assert q.value == 9.05352
    assert q.unit == "m2"

    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_missing_drawing_geometry_abstains_fails_closed(maryborough_pdf_path):
    """MAX review exact repro: native drawings empty and raster backend unavailable."""
    def fail_pixmap(*_args, **_kwargs):
        raise RuntimeError("geometry backend unavailable")

    with patch.object(fitz.Page, "get_drawings", return_value=[]), \
         patch.object(fitz.Page, "get_cdrawings", return_value=[]), \
         patch.object(fitz.Page, "get_pixmap", side_effect=fail_pixmap):
        result = authority.issue_all_original_maryborough_customer_quantities(
            maryborough_pdf_path,
            workspace_id=1,
        )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.traces == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_empty_observations_abstain_fails_closed(maryborough_pdf_path, monkeypatch):
    monkeypatch.setattr(fitz.Page, "get_text", lambda *_args, **_kwargs: [])
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.traces == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_dimension_word_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            # Filter out dimension word '3570'
            return [w for w in words if w[4] != "3570"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_door_callout_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            # Filter out door callout 'D15'
            return [w for w in words if w[4] != "D15"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_ft3_finish_mark_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            # Filter out finish mark 'FT3'
            return [w for w in words if w[4] != "FT3"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_competing_finish_marks_in_box_conflicts_and_abstains():
    """Verify competing finish codes in the Office box trigger CONFLICT."""
    from tests.test_source_cross_view_floor_correspondence_shadow import support_sheet, TARGET_SHEET
    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET
    # Competing marks inside box
    competing_marks = [
        {"code": "FT3", "x": 300.0, "y": 1450.0, "registered_region": True},
        {"code": "EPX", "x": 310.0, "y": 1460.0, "registered_region": True},
    ]
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256="sha1",
        snapshot_id="snap1",
        canonical_floor_id="floor1",
        physical_room_id="room1",
        source_room_face_record_id="face1",
        support_segments=sup_segs,
        target_segments=tgt_segs,
        marks=competing_marks,
        **VALID_SYNTHETIC_OBSERVATIONS,
    )
    assert cr.status == EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FINISH_CODES_IN_BOX in cr.reason_codes
    assert not cr.commercial_projection_allowed


def test_missing_wall_bounding_abstains():
    """Verify missing wall primitive causes failure to wall-bound on both sheets."""
    from tests.test_source_cross_view_floor_correspondence_shadow import support_sheet, TARGET_SHEET
    # Filter out x0 wall segments (x ~ 251.04) from support_sheet
    sup_segs = [
        s for s in support_sheet()
        if not (abs(s["x1"] - 251.04) < 1.0 and abs(s["x2"] - 251.04) < 1.0)
    ]
    tgt_segs = TARGET_SHEET
    marks = [{"code": "FT3", "x": 300.0, "y": 1450.0, "registered_region": True}]
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256="sha1",
        snapshot_id="snap1",
        canonical_floor_id="floor1",
        physical_room_id="room1",
        source_room_face_record_id="face1",
        support_segments=sup_segs,
        target_segments=tgt_segs,
        marks=marks,
        **VALID_SYNTHETIC_OBSERVATIONS,
    )
    assert cr.status == EvidenceResolutionStatus.ABSTAINED
    assert BOX_NOT_WALL_BOUNDED in cr.reason_codes
    assert not cr.commercial_projection_allowed


def test_shifted_registration_abstains():
    """Verify shifted registration hypothesis fails registration check."""
    # Segments placed with dx = 0.0 instead of -78.0
    sup_segs = [
        {"x1": 251.04, "y1": 1382.72, "x2": 251.04, "y2": 1585.04},
        {"x1": 394.80, "y1": 1382.72, "x2": 394.80, "y2": 1585.04},
        {"x1": 251.04, "y1": 1382.72, "x2": 394.80, "y2": 1382.72},
        {"x1": 251.04, "y1": 1585.04, "x2": 394.80, "y2": 1585.04},
    ]
    tgt_segs = [
        {"x1": 251.04, "y1": 1382.72, "x2": 251.04, "y2": 1585.04},
        {"x1": 394.80, "y1": 1382.72, "x2": 394.80, "y2": 1585.04},
        {"x1": 251.04, "y1": 1382.72, "x2": 394.80, "y2": 1382.72},
        {"x1": 251.04, "y1": 1585.04, "x2": 394.80, "y2": 1585.04},
    ]
    marks = [{"code": "FT3", "x": 300.0, "y": 1450.0, "registered_region": True}]
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256="sha1",
        snapshot_id="snap1",
        canonical_floor_id="floor1",
        physical_room_id="room1",
        source_room_face_record_id="face1",
        support_segments=sup_segs,
        target_segments=tgt_segs,
        marks=marks,
        registration_translation=(-78.0, 0.0),  # expected -78.0 but segments are at 0.0
        **VALID_SYNTHETIC_OBSERVATIONS,
    )
    assert cr.status == EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_NOT_UNIQUE in cr.reason_codes
    assert not cr.commercial_projection_allowed


def test_conflicting_correspondence_abstains(maryborough_pdf_path, monkeypatch):
    import pb_maryborough_customer_authority as auth_mod

    def blocked_correspondence(*args, **kwargs):
        return SourceCrossViewFloorCorrespondenceRecord(
            record_id="rec_conflict",
            canonical_floor_id=authority.OFFICE_PHYSICAL_FLOOR_ID,
            physical_room_id=authority.OFFICE_PHYSICAL_ROOM_ID,
            source_room_face_record_id="face_conflict",
            support_page_id="11",
            target_page_id="7",
            support_dimension_box_pdf_pts=(0, 0, 0, 0),
            target_box_pdf_pts=(0, 0, 0, 0),
            registration_orientation="0",
            registration_scale=1.0,
            registration_translation_pdf_pts=(0.0, 0.0),
            registration_support_pt=(0.0, 0.0),
            registration_runner_up_support_pt=(0.0, 0.0),
            registration_null_support_pt=(0.0, 0.0),
            wall_bounded_on_both_sheets=True,
            wall_evidence_identical_on_both_sheets=True,
            side_kinds=(),
            finish_codes_in_box=(),
            material_code="FT3",
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=("conflicting_cross_sheet_correspondence",),
            authority_blockers=("conflicting_cross_sheet_correspondence",),
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )

    monkeypatch.setattr(
        auth_mod,
        "authenticate_maryborough_office_cross_sheet_correspondence",
        blocked_correspondence,
    )
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_no_door_observation_abstains():
    """Verify missing door observation in synthetic test fails closed without bypass."""
    from tests.test_source_cross_view_floor_correspondence_shadow import support_sheet, TARGET_SHEET
    marks = [{"code": "FT3", "x": 300.0, "y": 1450.0, "registered_region": True}]
    obs = dict(VALID_SYNTHETIC_OBSERVATIONS)
    obs["door_observations"] = []
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256="sha1",
        snapshot_id="snap1",
        canonical_floor_id="floor1",
        physical_room_id="room1",
        source_room_face_record_id="face1",
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        marks=marks,
        **obs,
    )
    assert cr.status == EvidenceResolutionStatus.ABSTAINED
    assert DOORWAY_TRANSITION_UNAVAILABLE in cr.reason_codes
    assert not cr.commercial_projection_allowed


def test_no_dimension_witness_observation_abstains():
    """Verify missing dimension witness in synthetic test fails closed."""
    from tests.test_source_cross_view_floor_correspondence_shadow import support_sheet, TARGET_SHEET
    marks = [{"code": "FT3", "x": 300.0, "y": 1450.0, "registered_region": True}]
    obs = dict(VALID_SYNTHETIC_OBSERVATIONS)
    obs["dimension_witness_observations"] = []
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256="sha1",
        snapshot_id="snap1",
        canonical_floor_id="floor1",
        physical_room_id="room1",
        source_room_face_record_id="face1",
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        marks=marks,
        **obs,
    )
    assert cr.status == EvidenceResolutionStatus.ABSTAINED
    assert DIMENSION_WITNESS_UNAVAILABLE in cr.reason_codes
    assert not cr.commercial_projection_allowed


def test_foreign_revision_resolution_abstains():
    """Verify resolve_cross_sheet_floor_correspondence_for_claim fails closed if revision or SHA mismatches."""
    from types import SimpleNamespace
    store = SimpleNamespace(
        source_bytes_by_revision={
            "rev1": b"%PDF-foreign-content",
        }
    )
    source = SimpleNamespace(_store=store)
    area_rec = SimpleNamespace(
        source_room_face_record_id="face1",
        physical_room_id="room1",
        source_dimension_page_id="11",
        room_label="OFFICE",
    )
    cross_view_area = SimpleNamespace(records=(area_rec,))
    floor = SimpleNamespace(
        source_room_face_record_id="face1",
        room_entity_id="room1",
        canonical_floor_id="floor1",
        page_id="7",
        revision_id="rev1",
        source_sha256="expected_sha_that_does_not_match",
        document_id="doc1",
        snapshot_id="snap1",
    )
    canonical_floors = SimpleNamespace(floors=(floor,))
    result = resolve_cross_sheet_floor_correspondence_for_claim(
        source=source,
        cross_view_area=cross_view_area,
        canonical_floors=canonical_floors,
    )
    assert result == ()


def test_no_consumer_constructed_authority_in_maryborough_or_floor_finish_modules():
    """Verify consumer modules do not import _RECORD_SEAL or fabricate upstream records."""
    auth_src = Path(authority.__file__).read_text(encoding="utf-8")
    assert "_RECORD_SEAL" not in auth_src
    assert "CrossViewRoomAreaRecord(" not in auth_src

    import pb_cross_view_floor_finish_authority as finish_mod
    finish_src = Path(finish_mod.__file__).read_text(encoding="utf-8")
    assert "SourceMaterialOccurrenceRecord(" not in finish_src
    assert "SourceMaterialDefinitionRecord(" not in finish_src


def test_d15_door_schedule_off_table_mention_alone_abstains(maryborough_pdf_path, monkeypatch):
    """Removing the structured D15 schedule row (Block 139) while keeping off-table D15 notes abstains."""
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if (kwargs.get("text") == "words" or (args and args[0] == "words")) and page_self.number == 27:
            # Remove only the structured schedule table row for D15 (x >= 970, block 139),
            # leaving the off-table 'D14, D15, D28' note at x=849.5 intact.
            return [
                w for w in words
                if not (float(w[0]) >= 970.0 and int(w[5]) == 139)
            ]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_d15_physical_doorway_threshold_or_tile_boundary_missing_abstains(maryborough_pdf_path, monkeypatch):
    """Removing physical doorway threshold/leaf on Page 7 or tile termination on Page 11 abstains."""
    original_get_drawings = fitz.Page.get_drawings

    def strip_p7_doorway_threshold_and_leaf(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 6:
            return drawings
        filtered = []
        for d in drawings:
            items = d.get("items", ())
            drop = False
            for it in items:
                if it and it[0] == "l":
                    p1, p2 = it[1:3]
                    # Drop the D15 door leaf at x=179.28, y=[1324.64, 1376.72]
                    if abs(float(p1.x) - 179.28) < 0.5 and abs(float(p2.x) - 179.28) < 0.5:
                        drop = True
                        break
            if not drop:
                filtered.append(d)
        return filtered

    monkeypatch.setattr(fitz.Page, "get_drawings", strip_p7_doorway_threshold_and_leaf)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_dimension_words_without_witness_lines_abstain(maryborough_pdf_path, monkeypatch):
    """Keeping '3570' and '2536' words while removing their witness/shaft lines on Page 11 abstains."""
    original_get_drawings = fitz.Page.get_drawings

    def strip_p11_dimension_shaft(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 10:
            return drawings
        filtered = []
        for d in drawings:
            items = d.get("items", ())
            drop = False
            for it in items:
                if it and it[0] == "l":
                    p1, p2 = it[1:3]
                    # Drop vertical dimension shaft at x=156.96
                    if abs(float(p1.x) - 156.96) < 0.5 and abs(float(p2.x) - 156.96) < 0.5:
                        drop = True
                        break
            if not drop:
                filtered.append(d)
        return filtered

    monkeypatch.setattr(fitz.Page, "get_drawings", strip_p11_dimension_shaft)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_authenticated_d15_doorway_transition_details_on_genuine_pdf(maryborough_pdf_path):
    """Verify full D15 schedule and physical doorway boundary attributes on genuine Maryborough PDF."""
    with fitz.open(maryborough_pdf_path) as doc:
        cr = authenticate_maryborough_office_cross_sheet_correspondence(
            document_id=authority.MARYBOROUGH_DOCUMENT_ID,
            revision_id=authority.MARYBOROUGH_REVISION_ID,
            source_sha256=authority.MARYBOROUGH_SOURCE_SHA256,
            snapshot_id="snap_verify",
            canonical_floor_id=authority.OFFICE_PHYSICAL_FLOOR_ID,
            physical_room_id=authority.OFFICE_PHYSICAL_ROOM_ID,
            source_room_face_record_id=authority.OFFICE_SOURCE_ROOM_FACE_ID,
            doc=doc,
        )
    assert cr.status is EvidenceResolutionStatus.CORROBORATED
    assert len(cr.doorway_transitions) == 1
    d15 = cr.doorway_transitions[0]
    assert d15.door_callout == "D15"
    assert d15.scheduled_room_name == "OFFICE"
    assert d15.door_leaf_type == "SINGLE SWING"
    assert d15.door_width_mm == 920.0
    assert d15.door_height_mm == 2040.0
    assert d15.door_thickness_mm == 40.0
    assert d15.clear_opening_width_pdf_pt == pytest.approx(52.08, abs=0.05)
    assert d15.jamb_gap_target_pdf_pts == pytest.approx((177.12, 233.76), abs=0.05)
    assert d15.jamb_gap_support_pdf_pts == pytest.approx((254.88, 311.76), abs=0.05)
    assert d15.threshold_inside_face_y_pdf_pt == pytest.approx(1383.2, abs=0.05)
    assert d15.threshold_aligned_with_internal_face is True
    assert d15.threshold_deduction_m2 == 0.0


def test_claim_with_zero_canonical_walls_fails_closed():
    """Prove that a LivePhysicalNetWallClaim with canonical_walls=() cannot project rows or seal."""
    from copy import copy
    from dataclasses import replace
    from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
    from pb_live_canonical_room_composition import LiveCanonicalRoomObject
    from pb_live_floor_finish_area_source_closed_export import seal_live_floor_finish_area_run
    from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    from pb_migration_contracts import QuantityEvidence
    from pb_source_closed_run_export import SourceClosedRunConflictError
    from tests.test_live_floor_finish_area_source_closed_export import _claim, _floor, _quantity

    floor = _floor()
    qty = _quantity()
    room = LiveCanonicalRoomObject(
        canonical_room_id=floor.room_entity_id,
        physical_room_id=floor.room_entity_id,
        document_id=floor.document_id,
        revision_id=floor.revision_id,
        source_sha256=floor.source_sha256,
        snapshot_id=floor.snapshot_id,
        page_id=floor.page_id,
        viewport_id=floor.viewport_id,
        decision_scope_id="scope-1",
        polygon_pdf_pts=floor.polygon_pdf_pts,
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=("w1", "w2", "w3", "w4"),
        wall_relationships_complete=True,
        area_page_pts2=floor.area_page_pts2,
        source_room_face_record_id=floor.source_room_face_record_id,
        evidence_ids=("ev-1",),
        geometry_complete=True,
        metric_geometry_complete=False,
    )
    bad_claim = replace(
        _claim(floor),
        status=EvidenceResolutionStatus.CORROBORATED,
        canonical_rooms=(room,),
        canonical_walls=(),
        floor_finish_quantity_evidence=(qty,),
    )
    with pytest.raises(SourceClosedRunConflictError, match="canonical walls missing"):
        project_live_floor_finish_customer_rows(bad_claim, workspace_id=1, project_id="project-1")
    with pytest.raises(SourceClosedRunConflictError, match="canonical walls missing"):
        seal_live_floor_finish_area_run(bad_claim, workspace_id=1, project_id="project-1")


@pytest.mark.parametrize("side_name", ["x0", "x1", "y0", "y1"])
def test_missing_any_single_finished_wall_face_abstains(maryborough_pdf_path, monkeypatch, side_name):
    """Prove that missing even one of the 4 internal finished wall faces on Page 7 prevents a FIRM quantity."""
    original_get_drawings = fitz.Page.get_drawings

    def strip_single_face_drawings(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 6:
            return drawings
        filtered = []
        for d in drawings:
            items = d.get("items", ())
            drop = False
            for it in items:
                if not it:
                    continue
                op = it[0]
                if op == "l":
                    p1, p2 = it[1:3]
                    x_min, x_max = min(float(p1.x), float(p2.x)), max(float(p1.x), float(p2.x))
                    y_min, y_max = min(float(p1.y), float(p2.y)), max(float(p1.y), float(p2.y))
                elif op == "re":
                    r = it[1]
                    x_min, x_max = min(float(r.x0), float(r.x1)), max(float(r.x0), float(r.x1))
                    y_min, y_max = min(float(r.y0), float(r.y1)), max(float(r.y0), float(r.y1))
                else:
                    continue

                if side_name == "x0" and (abs(x_min - 173.04) < 1.0 or abs(x_max - 173.04) < 1.0):
                    if not (y_max < 1382.72 or y_min > 1585.04):
                        drop = True
                        break
                elif side_name == "x1" and (abs(x_min - 316.80) < 1.0 or abs(x_max - 316.80) < 1.0):
                    if not (y_max < 1382.72 or y_min > 1585.04):
                        drop = True
                        break
                elif side_name == "y0" and (abs(y_min - 1382.72) < 1.0 or abs(y_max - 1382.72) < 1.0):
                    if not (x_max < 173.04 or x_min > 316.80):
                        drop = True
                        break
                elif side_name == "y1" and (abs(y_min - 1585.04) < 1.0 or abs(y_max - 1585.04) < 1.0):
                    if not (x_max < 173.04 or x_min > 316.80):
                        drop = True
                        break
            if not drop:
                filtered.append(d)
        return filtered

    monkeypatch.setattr(fitz.Page, "get_drawings", strip_single_face_drawings)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_valid_d15_schedule_row_without_physical_threshold_line_abstains(maryborough_pdf_path, monkeypatch):
    """Prove that a valid D15 schedule entry without a physically authenticated threshold also ABSTAINS."""
    original_get_drawings = fitz.Page.get_drawings

    def strip_p7_threshold_line(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 6:
            return drawings
        filtered = []
        for d in drawings:
            items = d.get("items", ())
            drop = False
            for it in items:
                if not it:
                    continue
                op = it[0]
                if op == "l":
                    p1, p2 = it[1:3]
                    if abs(float(p1.y) - 1383.20) < 0.15 and abs(float(p2.y) - 1383.20) < 0.15:
                        xlo, xhi = min(float(p1.x), float(p2.x)), max(float(p1.x), float(p2.x))
                        if 176.0 <= xlo and xhi <= 235.0:
                            drop = True
                            break
                elif op == "re":
                    r = it[1]
                    if abs(float(r.y0) - 1383.20) < 0.15 or abs(float(r.y1) - 1383.20) < 0.15:
                        xlo, xhi = min(float(r.x0), float(r.x1)), max(float(r.x0), float(r.x1))
                        if 176.0 <= xlo and xhi <= 235.0:
                            drop = True
                            break
            if not drop:
                filtered.append(d)
        return filtered

    monkeypatch.setattr(fitz.Page, "get_drawings", strip_p7_threshold_line)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_ambiguous_dimension_witness_shafts_abstains(maryborough_pdf_path, monkeypatch):
    """Prove that two plausible vertical dimension shafts on Page 11 cause witness ambiguity and ABSTAIN."""
    original_get_drawings = fitz.Page.get_drawings

    def inject_second_vertical_shaft(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 10:
            return drawings
        injected = []
        for d in drawings:
            injected.append(d)
            for it in d.get("items", ()):
                if it and it[0] == "l":
                    p1, p2 = it[1:3]
                    if abs(float(p1.x) - 156.96) < 0.2 and abs(float(p2.x) - 156.96) < 0.2:
                        injected.append({
                            "items": [("l", fitz.Point(157.50, p1.y), fitz.Point(157.50, p2.y))],
                            "rect": fitz.Rect(157.0, min(p1.y, p2.y), 158.0, max(p1.y, p2.y)),
                        })
        return injected

    monkeypatch.setattr(fitz.Page, "get_drawings", inject_second_vertical_shaft)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_inconsistent_dimension_witness_scale_abstains(maryborough_pdf_path, monkeypatch):
    """Prove that mutually inconsistent vertical and horizontal shaft lengths fail scale check and ABSTAIN."""
    original_get_drawings = fitz.Page.get_drawings

    def alter_vertical_shaft_length(page_self, *args, **kwargs):
        drawings = original_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 10:
            return drawings
        modified = []
        for d in drawings:
            new_items = []
            for it in d.get("items", ()):
                if it and it[0] == "l":
                    p1, p2 = it[1:3]
                    if abs(float(p1.x) - 156.96) < 0.2 and abs(float(p2.x) - 156.96) < 0.2:
                        y_min = min(p1.y, p2.y)
                        y_max = max(p1.y, p2.y) - 15.0
                        new_items.append(("l", fitz.Point(p1.x, y_min), fitz.Point(p1.x, y_max)))
                    else:
                        new_items.append(it)
                else:
                    new_items.append(it)
            modified.append({**d, "items": new_items})
        return modified

    monkeypatch.setattr(fitz.Page, "get_drawings", alter_vertical_shaft_length)
    result = authority.issue_all_original_maryborough_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


