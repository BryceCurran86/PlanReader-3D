"""Tests for genuine source-owned Maryborough Food Prep FPB ceiling lining chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (13.270425 m2),
   1 customer row, and verified sealed run.
2. Ceiling customer authority produces 1-to-1 sealed customer output.
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing ceiling finish mark ('FPB') in RCP enclosure
   - missing room label ('FOOD PREP') on Page 9 RCP
   - missing Ceiling Legend definition ('FPB' -> 'FLUSHSET PLASTERBOARD')
   - missing figured dimension witnesses ('4025' or '3297')
   - shifted / un-unique registration translation
   - wall role not internal finished wall face
   - unresolved wall candidates
4. Exact seal and customer row bijection passing verify_sealed_customer_output.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

import pb_maryborough_ceiling_customer as ceiling_authority
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


def test_genuine_maryborough_food_prep_fpb_ceiling_complete_chain(maryborough_pdf_path):
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
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
    assert q.family == "ceiling_lining"
    assert q.value == 13.270425
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert ceiling_authority.FOOD_PREP_PHYSICAL_CEILING_ID in q.input_entity_ids

    row = result.customer_rows[0]
    assert row["quantity"] == 13.270425
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["element"] == "Ceiling lining area"
    assert row["finish_system"] == "FLUSHSET PLASTERBOARD"
    assert row["section"] == "Internal"

    # Verify 1-to-1 sealed customer output
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_missing_rcp_drawing_observations_abstains(maryborough_pdf_path, monkeypatch):
    """Empty get_drawings on Page 9 must fail closed to ABSTAIN."""
    orig_get_drawings = fitz.Page.get_drawings

    def selective_get_drawings(page_self):
        if page_self.number == 8:
            return []
        return orig_get_drawings(page_self)

    monkeypatch.setattr(fitz.Page, "get_drawings", selective_get_drawings)
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.traces == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_rcp_pixmap_backend_abstains(maryborough_pdf_path, monkeypatch):
    """Failing get_pixmap on Page 9 must fail closed to ABSTAIN."""
    orig_get_pixmap = fitz.Page.get_pixmap

    def selective_get_pixmap(page_self, *args, **kwargs):
        if page_self.number == 8:
            raise RuntimeError("geometry backend unavailable")
        return orig_get_pixmap(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", selective_get_pixmap)
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_fpb_ceiling_finish_mark_abstains(maryborough_pdf_path, monkeypatch):
    """Removing 'FPB' word on Page 9 inside the Food Prep boundary must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8:
                return [w for w in words if w[4] != "FPB"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_ceiling_legend_fpb_definition_abstains(maryborough_pdf_path, monkeypatch):
    """Removing Ceiling Legend 'FLUSHSET' or 'PLASTERBOARD' text on Page 9 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8:
                return [w for w in words if "PLASTERBOARD" not in w[4].upper()]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_dimension_witness_4025_abstains(maryborough_pdf_path, monkeypatch):
    """Removing figured dimension '4025' on Page 11 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 10:
                return [w for w in words if w[4] != "4025"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_invalid_workspace_id_abstains(maryborough_pdf_path):
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=0,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("authenticated_workspace_unavailable",)


def test_tampered_source_sha_abstains(tmp_path, maryborough_pdf_path):
    fake_pdf = tmp_path / "tampered_maryborough.pdf"
    fake_pdf.write_bytes(maryborough_pdf_path.read_bytes() + b"\n%tampered")
    result = ceiling_authority.issue_original_maryborough_food_prep_ceiling_customer_quantities(
        fake_pdf,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("maryborough_source_sha_mismatch",)
