"""Tests for genuine source-owned Maryborough PWD FT2 floor finish chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (7.854 m2),
   1 customer row, FT2 / tile metadata, and verified sealed run.
2. Floor subset authority returns the identical verified 1-quantity / 1-row result.
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing source words (get_text empty)
   - missing dimension witness ('3570' or '2200')
   - missing door callout ('D13')
   - missing finish mark ('FT2')
   - competing finish marks in box ('FT3' + 'FT2')
   - foreign-page finish mark rejected by polygon_page_id check
   - missing D13 door schedule row on Sheet A600 (Page 28)
   - invalid workspace_id and tampered SHA256
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
    EvidenceResolutionStatus,
    authenticate_maryborough_pwd_cross_sheet_correspondence,
)
from pb_source_floor_finish_occurrence_ownership_shadow import (
    SOURCE_LINEAGE_MISMATCH,
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


def test_genuine_maryborough_pwd_ft2_complete_chain(maryborough_pdf_path):
    result = authority.issue_original_maryborough_pwd_customer_quantities(
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
    assert q.value == 7.854
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert authority.PWD_PHYSICAL_FLOOR_ID in q.input_entity_ids
    assert q.metadata["finish_code"] == "FT2"
    assert q.metadata["semantic_finish"] == "tile"
    assert q.metadata["room_label"] == "PWD"

    row = result.customer_rows[0]
    assert row["quantity"] == 7.854
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["row_role"] == "floor_area"
    assert row["finish_system"] == "tile"
    assert row["location"] == authority.PWD_PHYSICAL_ROOM_ID

    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_genuine_maryborough_pwd_ft2_floor_subset_chain(maryborough_pdf_path):
    result = floor_authority.issue_original_maryborough_pwd_floor_customer_areas(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.reason_codes == ("source_owned_physical_quantity_resolved",)
    assert len(result.quantities) == 1
    assert len(result.customer_rows) == 1
    assert result.sealed_run is not None

    q = result.quantities[0]
    assert q.value == 7.854
    assert q.unit == "m2"
    assert q.metadata["finish_code"] == "FT2"

    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_missing_drawing_geometry_abstains_fails_closed(maryborough_pdf_path):
    """Native drawings empty and raster backend unavailable fails closed."""
    def fail_pixmap(*_args, **_kwargs):
        raise RuntimeError("geometry backend unavailable")

    with patch.object(fitz.Page, "get_drawings", return_value=[]), \
         patch.object(fitz.Page, "get_cdrawings", return_value=[]), \
         patch.object(fitz.Page, "get_pixmap", side_effect=fail_pixmap):
        result = authority.issue_original_maryborough_pwd_customer_quantities(
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
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.traces == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_dimension_word_3570_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            return [w for w in words if w[4] != "3570"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_dimension_word_2200_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            return [w for w in words if w[4] != "2200"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_door_callout_d13_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            return [w for w in words if w[4] != "D13"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_ft2_finish_mark_abstains(maryborough_pdf_path, monkeypatch):
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 10:
                return [w for w in words if w[4] != "FT2"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_d13_door_schedule_missing_abstains(maryborough_pdf_path, monkeypatch):
    """Removing the structured D13 schedule row on Page 28 causes fail-closed ABSTAIN."""
    original_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = original_get_text(page_self, *args, **kwargs)
        if (kwargs.get("text") == "words" or (args and args[0] == "words")) and page_self.number == 27:
            return [w for w in words if w[4] != "D13"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_pwd_correspondence_competing_marks_and_foreign_page_mark_fail_closed(maryborough_pdf_path):
    payload = maryborough_pdf_path.read_bytes()
    with fitz.open(stream=payload, filetype="pdf") as doc:
        # 1. Competing floor finish marks inside PWD box -> CONFLICT
        cr_conflict = authenticate_maryborough_pwd_cross_sheet_correspondence(
            document_id=authority.MARYBOROUGH_DOCUMENT_ID,
            revision_id=authority.MARYBOROUGH_REVISION_ID,
            source_sha256=authority.MARYBOROUGH_SOURCE_SHA256,
            snapshot_id="snap_pwd_test",
            canonical_floor_id=authority.PWD_PHYSICAL_FLOOR_ID,
            physical_room_id=authority.PWD_PHYSICAL_ROOM_ID,
            source_room_face_record_id=authority.PWD_SOURCE_ROOM_FACE_ID,
            doc=doc,
            marks=(
                {"code": "FT2", "x": 484.26, "y": 1483.79, "page_id": "11"},
                {"code": "FT3", "x": 460.00, "y": 1483.79, "page_id": "11"},
            ),
        )
        assert cr_conflict.status is EvidenceResolutionStatus.CONFLICT
        assert COMPETING_FINISH_CODES_IN_BOX in cr_conflict.reason_codes
        assert not cr_conflict.commercial_projection_allowed

        # 2. Foreign-page mark (page_id="7" inside support_page_id="11" polygon) -> ABSTAINED via polygon_page_id check
        cr_foreign_page = authenticate_maryborough_pwd_cross_sheet_correspondence(
            document_id=authority.MARYBOROUGH_DOCUMENT_ID,
            revision_id=authority.MARYBOROUGH_REVISION_ID,
            source_sha256=authority.MARYBOROUGH_SOURCE_SHA256,
            snapshot_id="snap_pwd_test_foreign",
            canonical_floor_id=authority.PWD_PHYSICAL_FLOOR_ID,
            physical_room_id=authority.PWD_PHYSICAL_ROOM_ID,
            source_room_face_record_id=authority.PWD_SOURCE_ROOM_FACE_ID,
            doc=doc,
            marks=(
                {"code": "FT2", "x": 484.26, "y": 1483.79, "page_id": "7"},
            ),
        )
        assert cr_foreign_page.status is EvidenceResolutionStatus.ABSTAINED
        assert SOURCE_LINEAGE_MISMATCH in cr_foreign_page.reason_codes
        assert not cr_foreign_page.commercial_projection_allowed


def test_invalid_workspace_id_abstains(maryborough_pdf_path):
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=0,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("authenticated_workspace_unavailable",)

    result_neg = authority.issue_original_maryborough_pwd_customer_quantities(
        maryborough_pdf_path,
        workspace_id=-1,
    )
    assert result_neg.status == "ABSTAIN"
    assert result_neg.reason_codes == ("authenticated_workspace_unavailable",)


def test_tampered_source_sha_abstains(tmp_path, maryborough_pdf_path):
    fake_pdf = tmp_path / "tampered_maryborough.pdf"
    fake_pdf.write_bytes(maryborough_pdf_path.read_bytes() + b"\n%tampered")
    result = authority.issue_original_maryborough_pwd_customer_quantities(
        fake_pdf,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("maryborough_source_sha_mismatch",)
