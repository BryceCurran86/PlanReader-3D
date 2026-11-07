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
    EvidenceResolutionStatus,
    SourceCrossViewFloorCorrespondenceRecord,
    authenticate_maryborough_office_cross_sheet_correspondence,
)


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
    assert q.status == "FIRM"
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
