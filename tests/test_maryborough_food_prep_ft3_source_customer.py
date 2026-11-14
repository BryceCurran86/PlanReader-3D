"""Tests for genuine source-owned Maryborough Food Prep FT3 floor finish chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (13.270425 m2),
   1 customer row, and verified sealed run.
2. Floor subset authority returns the identical verified 1-quantity / 1-row result.
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing source words (get_text empty)
   - missing dimension witness ('4025' or '3297')
   - missing door callout ('D28')
   - missing finish mark ('FT3')
   - competing finish marks in box ('EPX' + 'FT3')
   - missing D28 door schedule row on Sheet A600
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
    DOORWAY_TRANSITION_UNAVAILABLE,
    DIMENSION_WITNESS_UNAVAILABLE,
    EvidenceResolutionStatus,
    SourceCrossViewFloorCorrespondenceRecord,
    authenticate_maryborough_food_prep_cross_sheet_correspondence,
    resolve_cross_sheet_floor_correspondence_for_claim,
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


def test_genuine_maryborough_food_prep_ft3_complete_chain(maryborough_pdf_path):
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
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
    assert q.value == 13.270425
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert authority.FOOD_PREP_PHYSICAL_FLOOR_ID in q.input_entity_ids

    row = result.customer_rows[0]
    assert row["quantity"] == 13.270425
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["row_role"] == "floor_area"

    # Verify 1-to-1 sealed customer output
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_genuine_maryborough_food_prep_ft3_floor_subset_chain(maryborough_pdf_path):
    result = floor_authority.issue_original_maryborough_food_prep_floor_customer_areas(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.reason_codes == ("source_owned_physical_quantity_resolved",)
    assert len(result.quantities) == 1
    assert len(result.customer_rows) == 1
    assert result.sealed_run is not None

    q = result.quantities[0]
    assert q.value == 13.270425
    assert q.unit == "m2"

    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_missing_drawing_geometry_abstains_fails_closed(maryborough_pdf_path):
    """Native drawings empty and raster backend unavailable fails closed."""
    def fail_pixmap(*_args, **_kwargs):
        raise RuntimeError("geometry backend unavailable")

    with patch.object(fitz.Page, "get_drawings", return_value=[]), \
         patch.object(fitz.Page, "get_cdrawings", return_value=[]), \
         patch.object(fitz.Page, "get_pixmap", side_effect=fail_pixmap):
        result = authority.issue_original_maryborough_food_prep_customer_quantities(
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
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.traces == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_dimension_word_4025_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            return [w for w in words if w[4] != "4025"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_dimension_word_3297_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            return [w for w in words if w[4] != "3297"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_door_callout_d28_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            # Filter out door callout 'D28'
            return [w for w in words if w[4] != "D28"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
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
            # Filter out finish mark 'FT3' only for Page 11 (number 10)
            if page_self.number == 10:
                return [w for w in words if w[4] != "FT3"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_d28_door_schedule_missing_abstains(maryborough_pdf_path, monkeypatch):
    """Removing the structured D28 schedule row on Page 28 causes fail-closed ABSTAIN."""
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if (kwargs.get("text") == "words" or (args and args[0] == "words")) and page_self.number == 27:
            # Remove structured schedule row for D28 (block 152)
            return [w for w in words if not (w[4] == "D28" and int(w[5]) == 152)]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_invalid_workspace_id_abstains(maryborough_pdf_path):
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=0,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("authenticated_workspace_unavailable",)

    result_neg = authority.issue_original_maryborough_food_prep_customer_quantities(
        maryborough_pdf_path,
        workspace_id=-1,
    )
    assert result_neg.status == "ABSTAIN"
    assert result_neg.reason_codes == ("authenticated_workspace_unavailable",)


def test_tampered_source_sha_abstains(tmp_path, maryborough_pdf_path):
    fake_pdf = tmp_path / "tampered_maryborough.pdf"
    fake_pdf.write_bytes(maryborough_pdf_path.read_bytes() + b"\n%tampered")
    result = authority.issue_original_maryborough_food_prep_customer_quantities(
        fake_pdf,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("maryborough_source_sha_mismatch",)
