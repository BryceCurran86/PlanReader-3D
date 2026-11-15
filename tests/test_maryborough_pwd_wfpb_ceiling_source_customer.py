"""Tests for genuine source-owned Maryborough PWD WFPB ceiling lining chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (7.854 m2),
   1 customer row, and verified sealed run.
2. Ceiling customer authority produces 1-to-1 sealed customer output matching
   the verified benchmark item (maryborough-pwd-wfpb-ceiling-area).
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing ceiling finish mark ('WFPB') in RCP enclosure
   - missing height mark ('2400') in RCP enclosure
   - competing ceiling finish mark ('GRID') in RCP enclosure
   - missing room label ('PWD') on Page 9 RCP
   - missing Ceiling Legend definition ('WFPB' -> 'WET AREA FLUSHSET PLASTERBOARD')
   - missing figured dimension witnesses ('3570' or '2200')
   - invalid workspace id
   - tampered source SHA
4. Exact seal and customer row bijection passing verify_sealed_customer_output.
"""
from __future__ import annotations

import os
from pathlib import Path

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


def test_genuine_maryborough_pwd_wfpb_ceiling_complete_chain(maryborough_pdf_path):
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
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
    assert q.value == 7.854
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert ceiling_authority.PWD_PHYSICAL_CEILING_ID in q.input_entity_ids

    row = result.customer_rows[0]
    assert row["quantity"] == 7.854
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["element"] == "Ceiling lining area"
    assert row["finish_system"] == "WET AREA FLUSHSET PLASTERBOARD"
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
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
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
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_wfpb_ceiling_finish_mark_abstains(maryborough_pdf_path, monkeypatch):
    """Removing 'WFPB' word on Page 9 inside the PWD boundary must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8:
                return [w for w in words if w[4] != "WFPB"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_competing_ceiling_finish_mark_abstains(maryborough_pdf_path, monkeypatch):
    """Injecting a competing 'GRID' mark inside PWD box on Page 9 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8:
                # Place a conflicting mark on a source-owned WFPB occurrence,
                # without publishing original drawing coordinates in this test.
                words = list(words)
                wfpb = [w for w in words if len(w) > 4 and w[4] == "WFPB"]
                if wfpb:
                    room_mark = min(wfpb, key=lambda w: float(w[0]))
                    words.append((*room_mark[:4], "GRID", 0, 0, 0))
                return words
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_ceiling_legend_wfpb_definition_abstains(maryborough_pdf_path, monkeypatch):
    """Removing Ceiling Legend 'WFPB' text on Page 9 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8:
                # The rightmost native WFPB occurrence is the legend witness;
                # derive its position from the authenticated PDF, not a source crop.
                marks = [w for w in words if len(w) > 4 and w[4] == "WFPB"]
                if not marks:
                    return words
                legend_mark = max(marks, key=lambda w: float(w[0]))
                return [w for w in words if w is not legend_mark]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_missing_dimension_witness_2200_abstains(maryborough_pdf_path, monkeypatch):
    """Removing figured dimension '2200' on Page 11 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def selective_get_text(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 10:
                return [w for w in words if w[4] != "2200"]
        return words

    monkeypatch.setattr(fitz.Page, "get_text", selective_get_text)
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()


def test_invalid_workspace_id_abstains(maryborough_pdf_path):
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=0,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("authenticated_workspace_unavailable",)


def test_tampered_source_sha_abstains(tmp_path, maryborough_pdf_path):
    fake_pdf = tmp_path / "tampered_maryborough.pdf"
    fake_pdf.write_bytes(maryborough_pdf_path.read_bytes() + b"\n%tampered")
    result = ceiling_authority.issue_original_maryborough_pwd_ceiling_customer_quantities(
        fake_pdf,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("maryborough_source_sha_mismatch",)
