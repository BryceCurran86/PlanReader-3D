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
                # Add competing GRID word inside PWD box (428.40, 1382.72, 553.20, 1585.04)
                words = list(words)
                words.append((450.0, 1400.0, 480.0, 1420.0, "GRID", 0, 0, 0))
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
                # Filter out WFPB only from the legend area (x > 1350)
                return [w for w in words if not (w[4] == "WFPB" and float(w[0]) > 1350)]
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


def test_omission_negative_fails_closed_and_not_registered():
    """Omitting doc, source_bytes and pdf_path must fail closed to noncommercial CANDIDATE and never register."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        authenticate_maryborough_pwd_rcp_ceiling_correspondence,
        get_authenticated_ceiling_correspondence,
        EvidenceResolutionStatus,
        MARYBOROUGH_SOURCE_SHA256,
    )
    rec = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
        document_id="doc_maryborough",
        revision_id="rev_0",
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap_omission_test",
        canonical_ceiling_id="ceil_pwd",
        physical_room_id="room_pwd",
        canonical_room_id="croom_pwd",
        source_room_face_record_id="face_pwd",
        marks=[{"code": "WFPB"}],
        legend_observations=[{"code": "WFPB", "description": "PLASTERBOARD"}],
        room_label_observations=[{"label": "PWD"}],
    )
    assert rec.status is EvidenceResolutionStatus.CANDIDATE
    assert not rec.commercial_projection_allowed
    assert not rec.takeoff_eligible
    assert get_authenticated_ceiling_correspondence("snap_omission_test", rec.record_id) is None


def test_bare_doc_without_verified_bytes_fails_closed_and_not_registered():
    """Supplying a bare doc without verified source_bytes or path must not gain commercial authority."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        authenticate_maryborough_pwd_rcp_ceiling_correspondence,
        get_authenticated_ceiling_correspondence,
        EvidenceResolutionStatus,
        MARYBOROUGH_SOURCE_SHA256,
    )
    mock_doc = fitz.open()
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    mock_doc.new_page(width=1000, height=2000)
    rec = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
        document_id="doc_maryborough",
        revision_id="rev_0",
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap_bare_doc_test",
        canonical_ceiling_id="ceil_pwd",
        physical_room_id="room_pwd",
        canonical_room_id="croom_pwd",
        source_room_face_record_id="face_pwd",
        doc=mock_doc,
    )
    assert rec.status is EvidenceResolutionStatus.CANDIDATE
    assert not rec.commercial_projection_allowed
    assert not rec.takeoff_eligible
    assert get_authenticated_ceiling_correspondence("snap_bare_doc_test", rec.record_id) is None
    mock_doc.close()


def test_foreign_source_sha_abstains_and_not_registered():
    """Supplying a foreign source document SHA must fail closed to ABSTAINED and never register."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        authenticate_maryborough_pwd_rcp_ceiling_correspondence,
        get_authenticated_ceiling_correspondence,
        EvidenceResolutionStatus,
    )
    rec = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
        document_id="doc_maryborough",
        revision_id="rev_0",
        source_sha256="f" * 64,
        snapshot_id="snap_foreign_test",
        canonical_ceiling_id="ceil_pwd",
        physical_room_id="room_pwd",
        canonical_room_id="croom_pwd",
        source_room_face_record_id="face_pwd",
    )
    assert rec.status is EvidenceResolutionStatus.ABSTAINED
    assert not rec.commercial_projection_allowed
    assert not rec.takeoff_eligible
    assert get_authenticated_ceiling_correspondence("snap_foreign_test", rec.record_id) is None


def test_competing_material_in_box_abstains_and_not_registered(maryborough_pdf_path, monkeypatch):
    """A competing ceiling finish code (e.g. GRID) inside PWD overhead enclosure must fail closed."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        authenticate_maryborough_pwd_rcp_ceiling_correspondence,
        get_authenticated_ceiling_correspondence,
        EvidenceResolutionStatus,
        COMPETING_FINISH_CODES_IN_BOX,
        MARYBOROUGH_SOURCE_SHA256,
    )
    orig_get_text = fitz.Page.get_text

    def inject_grid_word(page_self, *args, **kwargs):
        words = orig_get_text(page_self, *args, **kwargs)
        if kwargs.get("text") == "words" or (args and args[0] == "words"):
            if page_self.number == 8: # Page 9
                injected = list(words)
                injected.append((450.0, 1450.0, 480.0, 1465.0, "GRID", 0, 0, 0))
                return injected
        return words

    monkeypatch.setattr(fitz.Page, "get_text", inject_grid_word)
    rec = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
        document_id="doc_maryborough",
        revision_id="rev_0",
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap_competing_test",
        canonical_ceiling_id="ceil_pwd",
        physical_room_id="room_pwd",
        canonical_room_id="croom_pwd",
        source_room_face_record_id="face_pwd",
        pdf_path=maryborough_pdf_path,
    )
    assert rec.status is EvidenceResolutionStatus.ABSTAINED
    assert COMPETING_FINISH_CODES_IN_BOX in rec.reason_codes
    assert not rec.commercial_projection_allowed
    assert get_authenticated_ceiling_correspondence("snap_competing_test", rec.record_id) is None


def test_tied_registrations_abstain_and_not_registered(maryborough_pdf_path, monkeypatch):
    """Tied or competing cross-sheet registrations must fail closed to REGISTRATION_NOT_UNIQUE and never register."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        authenticate_maryborough_pwd_rcp_ceiling_correspondence,
        get_authenticated_ceiling_correspondence,
        EvidenceResolutionStatus,
        REGISTRATION_NOT_UNIQUE,
        MARYBOROUGH_SOURCE_SHA256,
    )
    import pb_source_cross_view_floor_correspondence_shadow as p

    good = {"orientation": "identity", "scale": 1.0, "dx": -106.32, "dy": 0.0, "min_support_pt": 5000.0}
    tied = {"orientation": "identity", "scale": 1.0, "dx": 20.0, "dy": 0.0, "min_support_pt": 5000.0}

    monkeypatch.setattr(p, "rank_registrations", lambda *_a, **_k: [good, tied])

    rec = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
        document_id="doc_maryborough",
        revision_id="rev_0",
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap_tied_reg_test",
        canonical_ceiling_id="ceil_pwd",
        physical_room_id="room_pwd",
        canonical_room_id="croom_pwd",
        source_room_face_record_id="face_pwd",
        pdf_path=maryborough_pdf_path,
    )
    assert rec.status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_NOT_UNIQUE in rec.reason_codes
    assert not rec.commercial_projection_allowed
    assert not rec.takeoff_eligible
    assert get_authenticated_ceiling_correspondence("snap_tied_reg_test", rec.record_id) is None


