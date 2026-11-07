"""Tests for genuine source-owned Maryborough Office FT3 floor finish chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (9.05352 m2),
   1 customer row, and verified sealed run.
2. Floor subset authority returns the identical verified 1-quantity / 1-row result.
3. Fail-closed regressions: missing source words, empty observation mock, unavailable backend,
   or uncorroborated correspondence immediately return ABSTAIN with zero quantities and rows.
4. Exact seal and customer row bijection passing verify_sealed_customer_output.
"""
from __future__ import annotations

import os
from pathlib import Path
import fitz
import pytest

import pb_maryborough_customer_authority as authority
import pb_maryborough_floor_area_customer as floor_authority
from pb_customer_output_verification import verify_sealed_customer_output


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
    assert row["element"] == "FT3"
    assert row["quantity"] == 9.05352
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"

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


def test_conflicting_correspondence_abstains(maryborough_pdf_path, monkeypatch):
    import pb_maryborough_customer_authority as auth_mod
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewFloorCorrespondenceRecord,
        EvidenceResolutionStatus,
    )

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
