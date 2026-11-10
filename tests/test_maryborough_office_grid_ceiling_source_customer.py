"""Tests for genuine source-owned Maryborough Office GRID ceiling lining chain.

Verifies:
1. Genuine source PDF yields FIRM_SOURCE_CUSTOMER_TO_REVIEW with exactly 1 quantity (9.05352 m2),
   1 customer row, and verified sealed run.
2. Ceiling customer authority produces 1-to-1 sealed customer output matching
   the exact verified ceiling benchmark item (maryborough-office-grid-ceiling-area).
3. Fail-closed regressions:
   - missing drawing observations (get_drawings return empty list)
   - unavailable geometry backend (get_pixmap raises RuntimeError)
   - missing ceiling finish mark ('GRID') in RCP enclosure
   - competing ceiling finish mark ('WFPB' + 'GRID') in RCP enclosure
   - missing room label ('OFFICE') on Page 9 RCP
   - missing Ceiling Legend definition ('GRID' -> 'VINYL FACED PLASTER TILE')
   - missing figured dimension witnesses ('3570' or '2536')
   - unclosed RCP drawing boundary vector
   - shifted / un-unique registration translation
   - wall role not internal finished wall face
   - unresolved wall candidates
   - consumer-authored CORROBORATED status attempting to override unresolved evidence
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
from pb_source_cross_view_floor_correspondence_shadow import (
    COMPETING_FINISH_CODES_IN_BOX,
    NO_FINISH_MARK_IN_BOX,
    REGISTRATION_NOT_UNIQUE,
    BOX_NOT_WALL_BOUNDED,
    DIMENSION_WITNESS_UNAVAILABLE,
    EvidenceResolutionStatus,
    SourceCrossViewCeilingCorrespondenceRecord,
    authenticate_maryborough_office_rcp_ceiling_correspondence,
    compose_authenticated_cross_sheet_physical_claim,
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
)
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError


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


def test_genuine_maryborough_office_grid_ceiling_complete_chain(maryborough_pdf_path):
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
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
    assert q.value == 9.05352
    assert q.unit == "m2"
    assert q.status.lower() == "firm"
    assert not q.abstained
    assert ceiling_authority.OFFICE_PHYSICAL_CEILING_ID in q.input_entity_ids

    row = result.customer_rows[0]
    assert row["quantity"] == 9.05352
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["element"] == "Ceiling lining area"
    assert row["finish_system"] == "GRID"
    assert row["section"] == "Internal"

    # Verify 1-to-1 sealed customer output
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_missing_rcp_drawing_observations_abstains(maryborough_pdf_path, monkeypatch):
    """Empty get_drawings on Page 9 must fail closed to ABSTAIN."""
    orig_get_drawings = fitz.Page.get_drawings

    def mock_get_drawings(page_self, *args, **kwargs):
        if page_self.number == 8:
            return []
        return orig_get_drawings(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_drawings", mock_get_drawings)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_unavailable_geometry_backend_abstains(maryborough_pdf_path, monkeypatch):
    """RuntimeError in get_pixmap on Page 9 must fail closed to ABSTAIN."""
    orig_get_pixmap = fitz.Page.get_pixmap

    def mock_get_pixmap(page_self, *args, **kwargs):
        if page_self.number == 8:
            raise RuntimeError("mupdf render device unavailable")
        return orig_get_pixmap(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", mock_get_pixmap)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_grid_mark_in_rcp_enclosure_abstains(maryborough_pdf_path, monkeypatch):
    """Dropping 'GRID' from the Office enclosure on Page 9 must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def mock_get_text(page_self, *args, **kwargs):
        if page_self.number == 8 and args and args[0] == "words":
            words = orig_get_text(page_self, *args, **kwargs)
            filtered = []
            for w in words:
                if len(w) >= 5 and str(w[4]).strip().upper() == "GRID":
                    # Drop GRID in Office box
                    if 279.0 <= float(w[0]) <= 425.0 and 1380.0 <= float(w[1]) <= 1585.0:
                        continue
                filtered.append(w)
            return filtered
        return orig_get_text(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_text", mock_get_text)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_competing_ceiling_marks_in_rcp_enclosure_conflicts(maryborough_pdf_path, monkeypatch):
    """Adding a competing finish mark 'WFPB' inside the Office enclosure on Page 9 must fail closed."""
    orig_get_text = fitz.Page.get_text

    def mock_get_text(page_self, *args, **kwargs):
        if page_self.number == 8 and args and args[0] == "words":
            words = list(orig_get_text(page_self, *args, **kwargs))
            # Inject WFPB inside the Office box
            words.append((350.0, 1450.0, 380.0, 1465.0, "WFPB", 999, 0, 0))
            return words
        return orig_get_text(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_text", mock_get_text)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_office_label_on_rcp_abstains(maryborough_pdf_path, monkeypatch):
    """Dropping 'OFFICE' word inside Page 9 enclosure must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def mock_get_text(page_self, *args, **kwargs):
        if page_self.number == 8 and args and args[0] == "words":
            words = orig_get_text(page_self, *args, **kwargs)
            return [w for w in words if "OFFICE" not in str(w[4]).upper() or float(w[0]) < 279.0]
        return orig_get_text(page_self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_text", mock_get_text)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_ceiling_legend_definition_abstains(maryborough_pdf_path, monkeypatch):
    """Removing 'VINYL FACED PLASTER TILE' from Page 9 text must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def mock_get_text(page_self, *args, **kwargs):
        text = orig_get_text(page_self, *args, **kwargs)
        if page_self.number == 8 and isinstance(text, str):
            return text.replace("VINYL FACED PLASTER TILE", "CORRUPTED_DEFINITION")
        return text

    monkeypatch.setattr(fitz.Page, "get_text", mock_get_text)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_missing_dimension_witnesses_abstains(maryborough_pdf_path, monkeypatch):
    """Dropping '3570' from Page 11 text must fail closed to ABSTAIN."""
    orig_get_text = fitz.Page.get_text

    def mock_get_text(page_self, *args, **kwargs):
        res = orig_get_text(page_self, *args, **kwargs)
        if page_self.number == 10:
            if isinstance(res, str):
                return res.replace("3570", "0000")
            elif isinstance(res, list):
                out = []
                for w in res:
                    if len(w) >= 5 and "3570" in str(w[4]):
                        w = list(w)
                        w[4] = str(w[4]).replace("3570", "0000")
                        out.append(tuple(w))
                    else:
                        out.append(w)
                return out
        return res

    monkeypatch.setattr(fitz.Page, "get_text", mock_get_text)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_unclosed_rcp_drawing_boundary_abstains(maryborough_pdf_path, monkeypatch):
    """Removing top boundary lines of the Office enclosure on Page 9 must fail closed to ABSTAIN."""
    orig_get_drawings = fitz.Page.get_drawings

    def mock_get_drawings(page_self, *args, **kwargs):
        drawings = orig_get_drawings(page_self, *args, **kwargs)
        if page_self.number != 8:
            return drawings
        return [
            d for d in drawings
            if not (
                (abs(d.get("rect", fitz.Rect()).y0 - 1383.20) < 2.0 or abs(d.get("rect", fitz.Rect()).y1 - 1383.20) < 2.0)
                and d.get("rect", fitz.Rect()).x0 <= 285.0
                and d.get("rect", fitz.Rect()).x1 >= 415.0
            )
        ]

    monkeypatch.setattr(fitz.Page, "get_drawings", mock_get_drawings)
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(
        maryborough_pdf_path,
        workspace_id=1,
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (ceiling_authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,)
    assert result.quantities == ()
    assert result.customer_rows == ()
    assert result.sealed_run is None


def test_shifted_registration_translation_abstains(maryborough_pdf_path):
    """Shifted translation must reject correspondence with REGISTRATION_NOT_UNIQUE and ABSTAIN."""
    cr = authenticate_maryborough_office_rcp_ceiling_correspondence(
        document_id=ceiling_authority.MARYBOROUGH_DOCUMENT_ID,
        revision_id=ceiling_authority.MARYBOROUGH_REVISION_ID,
        source_sha256=ceiling_authority.MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap_test",
        canonical_ceiling_id=ceiling_authority.OFFICE_PHYSICAL_CEILING_ID,
        physical_room_id=ceiling_authority.OFFICE_PHYSICAL_ROOM_ID,
        canonical_room_id=ceiling_authority.OFFICE_PHYSICAL_ROOM_ID,
        source_room_face_record_id=ceiling_authority.OFFICE_SOURCE_ROOM_FACE_ID,
        registration_translation=(95.0, 0.0),
        pdf_path=maryborough_pdf_path,
    )
    assert cr.status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_NOT_UNIQUE in cr.reason_codes
    assert cr.commercial_projection_allowed is False


def test_missing_finished_wall_face_abstains_in_claim():
    """Wall without role 'internal_finished_wall_face' must prevent claim corroboration."""
    from types import SimpleNamespace

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_wall_test_1",
        snapshot_id="snap_wall_test_1",
        canonical_ceiling_id="c_1",
        physical_room_id="r_1",
        canonical_room_id="r_1",
        source_room_face_record_id="f_1",
        support_page_id="9",
        support_viewport_id="vp9",
        target_page_id="7",
        target_viewport_id="vp7",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(corr.snapshot_id, corr.record_id)] = corr
    # Wall with generic role instead of internal_finished_wall_face
    bad_wall = SimpleNamespace(
        role="generic_partition",
        physical_identity_resolved=True,
        identity_status="physical_resolved",
    )
    good_wall = SimpleNamespace(
        role="internal_finished_wall_face",
        physical_identity_resolved=True,
        identity_status="physical_resolved",
    )
    walls = SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        walls=(bad_wall, good_wall, good_wall, good_wall),
        source_pages=(7,),
        reason_codes=(),
        unresolved_wall_candidate_ids=(),
    )
    rooms = SimpleNamespace(status=EvidenceResolutionStatus.CORROBORATED, rooms=(SimpleNamespace(),), source_pages=(7,))
    qty = SimpleNamespace(status="firm", blocking_reasons=(), abstained=False)
    ceiling_obj = SimpleNamespace()

    claim = compose_authenticated_cross_sheet_physical_claim(
        published=None,
        correspondence=corr,
        rooms=rooms,
        walls=walls,
        canonical_ceilings=(ceiling_obj,),
        ceiling_lining_quantity_evidence=(qty,),
    )
    assert claim.status is EvidenceResolutionStatus.ABSTAINED
    assert claim.confidence == 0.0
    assert "wall_not_internal_finished_face" in claim.reason_codes


def test_consumer_authored_corroborated_cannot_override_upstream_unresolved_ceiling_evidence():
    """Prove that consumer-authored claim with ABSTAINED wall status cannot produce customer rows."""
    from types import SimpleNamespace
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    from pb_migration_contracts import QuantityEvidence

    room = SimpleNamespace(
        canonical_room_id="r1",
        physical_room_id="r1",
        source_room_face_record_id="f1",
        source_room_index_id="",
        document_id="doc1",
        revision_id="rev1",
        snapshot_id="snap1",
        page_id="7",
        source_sha256="a" * 64,
        polygon_pdf_pts=((100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)),
        viewport_id="vp1",
    )
    ceiling = SimpleNamespace(
        canonical_ceiling_id="c1",
        document_id="doc1",
        snapshot_id="snap1",
        room_entity_id="r1",
        source_page=7,
        viewport_id="vp1",
        source_sha256="a" * 64,
        revision_id="rev1",
        polygon_pdf_pts=((100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)),
        area_m2=9.05352,
        finish_descriptor="GRID",
        room_area_quantity_id="aq1",
        ceiling_quantity_id="cq1",
        source_room_index_id="",
        evidence_ids=("mark1",),
        physical_scale_record_id="",
        measurement_authority="documented_dimension",
        figured_dimension_ids=("dim_2536", "dim_3570"),
    )
    qty = QuantityEvidence(
        quantity_id="cq1",
        family="ceiling_lining",
        unit="m2",
        value=9.05352,
        status="firm",
        authority="documented_dimension",
        confidence=1.0,
        evidence_ids=("mark1",),
        input_entity_ids=("c1",),
        semantic_key="ceiling_lining:c1:GRID:GRID",
        metadata={
            "document_id": "doc1",
            "revision_id": "rev1",
            "snapshot_id": "snap1",
            "source_sha256": "a" * 64,
            "page_no": "7",
            "viewport_id": "vp1",
            "canonical_ceiling_id": "c1",
            "physical_ceiling_surface_id": "c1",
            "canonical_room_id": "r1",
            "physical_room_id": "r1",
            "source_room_face_record_id": "f1",
            "source_room_index_id": "",
            "upstream_room_area_quantity_id": "aq1",
            "room_area_quantity_id": "aq1",
            "finish_code": "GRID",
            "semantic_finish": "GRID",
            "figured_dimension_ids": ("dim_2536", "dim_3570"),
            "finish_occurrence_record_id": "occ1",
            "finish_occurrence_evidence_id": "mark1",
            "finish_definition_record_id": "def1",
            "support_page_id": "9",
            "support_viewport_id": "VIEWPORT_P09_A120_RCP",
            "support_snapshot_id": "snap1",
            "row_role": "ceiling_area",
            "commercial_projection_allowed": True,
        },
    )

    # Claim with quantity marked numeric but with blocking reasons
    bad_qty = QuantityEvidence(
        quantity_id="cq1",
        family="ceiling_lining",
        unit="m2",
        value=9.05352,
        status="firm",
        authority="documented_dimension",
        confidence=1.0,
        evidence_ids=("mark1",),
        input_entity_ids=("c1",),
        semantic_key="ceiling_lining:c1:GRID:GRID",
        blocking_reasons=("unresolved_producer_blocker",),
    )
    claim_blocked = LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        quantity_m2=None,
        source_pages=(7, 9),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(room,),
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(7,),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=1.0,
        publication=None,
        canonical_ceilings=(ceiling,),
        ceiling_lining_quantity_evidence=(bad_qty,),
    )
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        project_live_ceiling_customer_rows(claim_blocked, workspace_id=1, project_id="proj1")


def test_missing_original_and_untrusted_workspace_remain_abstained(tmp_path):
    path = tmp_path / "missing.pdf"
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(path)
    assert result.status == "ABSTAIN"
    assert result.quantities == result.traces == result.customer_rows == ()
    assert result.sealed_run is None

    bad = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(path, workspace_id=True)
    assert bad.status == "ABSTAIN"
    assert bad.reason_codes == ("authenticated_workspace_unavailable",)


def test_foreign_pdf_sha_mismatch_abstains(tmp_path):
    foreign_pdf = tmp_path / "foreign.pdf"
    foreign_pdf.write_bytes(b"%PDF-1.4 foreign content not maryborough")
    result = ceiling_authority.issue_original_maryborough_ceiling_customer_quantities(foreign_pdf)
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("maryborough_source_sha_mismatch",)



def test_rcp_segments_with_corner_gaps_abstain():
    """Defect 2 regression: synthetic RCP segments with corner gaps must fail closed with rcp_enclosure_unclosed."""
    from pb_source_cross_view_floor_correspondence_shadow import (
        BOX_NOT_WALL_BOUNDED,
        EvidenceResolutionStatus,
        authenticate_maryborough_office_rcp_ceiling_correspondence,
    )

    # Segments that cover spans but leave gaps at all 4 corners (e.g. y starts at 1390 instead of 1383.20)
    gap_segments = [
        {"x1": 279.84, "y1": 1390.0, "x2": 279.84, "y2": 1580.0},  # left
        {"x1": 422.64, "y1": 1390.0, "x2": 422.64, "y2": 1580.0},  # right
        {"x1": 285.0, "y1": 1383.20, "x2": 415.0, "y2": 1383.20},  # top
        {"x1": 285.0, "y1": 1584.56, "x2": 415.0, "y2": 1584.56},  # bottom
    ]

    cr = authenticate_maryborough_office_rcp_ceiling_correspondence(
        document_id="doc1",
        revision_id="rev1",
        source_sha256=ceiling_authority.MARYBOROUGH_SOURCE_SHA256,
        snapshot_id="snap1",
        canonical_ceiling_id=ceiling_authority.OFFICE_PHYSICAL_CEILING_ID,
        physical_room_id=ceiling_authority.OFFICE_PHYSICAL_ROOM_ID,
        canonical_room_id=ceiling_authority.OFFICE_PHYSICAL_ROOM_ID,
        source_room_face_record_id=ceiling_authority.OFFICE_SOURCE_ROOM_FACE_ID,
        rcp_segments=gap_segments,
        marks=[{"code": "GRID"}],
        room_label_observations=[{"label": "OFFICE"}],
        legend_observations=[{"code": "GRID", "desc": "VINYL FACED PLASTER TILE"}],
        dimension_witness_observations=[{"code": "3570", "witness_bound": True}, {"code": "2536", "witness_bound": True}],
    )
    assert cr.status is EvidenceResolutionStatus.ABSTAINED
    assert BOX_NOT_WALL_BOUNDED in cr.reason_codes
    assert "rcp_enclosure_unclosed" in cr.authority_blockers
    assert cr.commercial_projection_allowed is False


def test_compose_office_ceiling_with_mismatched_room_or_unissued_area_raises():
    """Defect 2 regression: compose ceiling with mismatched room entity or unissued area evidence must raise ValueError."""
    from types import SimpleNamespace
    from pb_source_cross_view_floor_correspondence_shadow import (
        EvidenceResolutionStatus,
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id="room_office_1",
        canonical_room_id="room_office_1",
        source_room_face_record_id="f_1",
        support_page_id="9",
        support_viewport_id="vp9",
        target_page_id="7",
        target_viewport_id="vp7",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="snap1",
    )

    # 1. Mismatched room physical ID
    bad_room = SimpleNamespace(
        canonical_room_id="wrong_room",
        physical_room_id="wrong_room",
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="snap1",
        page_id="7",
    )
    good_evidence = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        family="floor_area",
        unit="m2",
    )
    with pytest.raises(ValueError, match="room entity mismatch"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=bad_room,
            area_evidence=good_evidence,
            room_area_qty_id="area_qty_1",
        )

    # 2. Mismatched snapshot ID
    bad_snap_room = SimpleNamespace(
        canonical_room_id="room_office_1",
        physical_room_id="room_office_1",
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="FOREIGN_SNAP_999",
        page_id="7",
    )
    with pytest.raises(ValueError, match="room and ceiling correspondence document/revision/snapshot mismatch"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=bad_snap_room,
            area_evidence=good_evidence,
            room_area_qty_id="area_qty_1",
        )

    # 3. Unissued / mismatched area quantity evidence ID
    good_room = SimpleNamespace(
        canonical_room_id="room_office_1",
        physical_room_id="room_office_1",
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="snap1",
        page_id="7",
    )
    bad_qty_evidence = SimpleNamespace(
        quantity_id="fake_unissued_area_qty",
        value=9.05352,
        status="firm",
    )
    with pytest.raises(ValueError, match="unissued or mismatched room area quantity evidence"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=good_room,
            area_evidence=bad_qty_evidence,
            room_area_qty_id="area_qty_1",
        )

    # 4. Mismatched area value
    bad_value_evidence = SimpleNamespace(
        quantity_id="area_qty_1",
        value=15.000,
        status="firm",
    )
    with pytest.raises(ValueError, match="room area value mismatch with ceiling area"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=good_room,
            area_evidence=bad_value_evidence,
            room_area_qty_id="area_qty_1",
        )

def test_adversarial_wrong_family_foreign_snapshot_blocked_area_evidence_raises():
    """Defect 2 regression (PR review 5837411122): unissued, wrong-family, wrong-unit, foreign-snapshot, or blocked area evidence raises ValueError."""
    from types import SimpleNamespace
    from pb_source_cross_view_floor_correspondence_shadow import (
        EvidenceResolutionStatus,
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id="room_office_1",
        canonical_room_id="room_office_1",
        source_room_face_record_id="f_1",
        support_page_id="9",
        support_viewport_id="vp9",
        target_page_id="7",
        target_viewport_id="vp7",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="snap1",
    )
    room = SimpleNamespace(
        canonical_room_id="room_office_1",
        physical_room_id="room_office_1",
        document_id="doc1",
        revision_id="rev1",
        source_sha256="abc12345",
        snapshot_id="snap1",
        page_id="7",
        evidence_ids=("ev_room",),
        polygon_pdf_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        viewport_id="vp7",
    )

    # 1. Exact reproduction from GPT MAX review 5837411122: wrong family + wrong unit + blockers + foreign snapshot
    adv_evidence = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        evidence_id="foreign-unissued-evidence",
        family="opening_count",
        unit="each",
        blocking_reasons=("unresolved_metric",),
        metadata={"snapshot_id": "FOREIGN"},
    )
    with pytest.raises(ValueError, match="invalid room area evidence family"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            area_evidence=adv_evidence,
            room_area_qty_id="area_qty_1",
        )

    # 2. Wrong unit ("each")
    adv_unit = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        family="floor_area",
        unit="each",
    )
    with pytest.raises(ValueError, match="invalid room area evidence unit"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            area_evidence=adv_unit,
            room_area_qty_id="area_qty_1",
        )

    # 3. Unresolved blockers
    adv_blocked = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        family="floor_area",
        unit="m2",
        blocking_reasons=("unresolved_metric",),
    )
    with pytest.raises(ValueError, match="unresolved authority blockers"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            area_evidence=adv_blocked,
            room_area_qty_id="area_qty_1",
        )

    # 4. Foreign snapshot in metadata
    adv_foreign = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        family="floor_area",
        unit="m2",
        metadata={"snapshot_id": "FOREIGN_SNAP_XYZ"},
    )
    with pytest.raises(ValueError, match="snapshot_id FOREIGN_SNAP_XYZ does not match"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            area_evidence=adv_foreign,
            room_area_qty_id="area_qty_1",
        )



def test_unissued_area_simplenamespace_does_not_create_firm_ceiling_raises():
    """Defect 2 regression: caller SimpleNamespace without producer authority must fail closed (raise ValueError)."""
    from types import SimpleNamespace
    from pb_source_cross_view_floor_correspondence_shadow import (
        EvidenceResolutionStatus,
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )

    doc_id = "doc1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev1"
    snap_id = "snap1"
    room_id = "room_office_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id="face_1",
        support_page_id="10",
        support_viewport_id="VIEWPORT_P10_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id="face_1",
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    unissued_evidence = SimpleNamespace(
        quantity_id="area_qty_1",
        value=9.05352,
        status="firm",
        evidence_id="unissued_area",
        family="floor_area",
        unit="m2",
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
        },
    )

    with pytest.raises(ValueError, match="unissued|unauthorized|EvidenceAtom"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="area_qty_1",
            area_evidence=unissued_evidence,
        )


def test_fabricated_typed_evidence_atom_does_not_create_firm_ceiling_raises():
    """GPT MAX P1 regression: caller-constructed EvidenceAtom without producer authority must raise ValueError."""
    from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )
    from types import SimpleNamespace

    doc_id = "doc1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev1"
    snap_id = "snap1"
    room_id = "room_office_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id="face_1",
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id="face_1",
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    forged_atom = EvidenceAtom(
        evidence_id="area_qty_1",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )

    with pytest.raises(ValueError, match="unissued|unauthorized|not issued|caller-created|not registered"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="area_qty_1",
            area_evidence=forged_atom,
        )


def test_fabricated_quantity_evidence_does_not_create_firm_ceiling_raises():
    """GPT MAX P1 regression: caller-constructed QuantityEvidence without producer authority must raise ValueError."""
    from pb_migration_contracts import QuantityEvidence, EvidenceResolutionStatus
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )
    from types import SimpleNamespace

    doc_id = "doc1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev1"
    snap_id = "snap1"
    room_id = "room_office_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id="face_1",
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id="face_1",
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    forged_qty = QuantityEvidence(
        quantity_id="area_qty_1",
        family="floor_area",
        semantic_key="floor_area:room_office_1",
        value=9.05352,
        unit="m2",
        status="firm",
        evidence_ids=("area_qty_1",),
        authority="documented_dimension",
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
        },
    )

    with pytest.raises(ValueError, match="unissued|unauthorized|not issued|caller-created|not registered"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="area_qty_1",
            area_evidence=forged_qty,
        )


def test_missing_dimension_lineage_does_not_create_firm_ceiling_raises():
    """GPT MAX P1 regression: area evidence missing dimension lineage must raise ValueError."""
    from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )
    from types import SimpleNamespace

    doc_id = "doc1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev1"
    snap_id = "snap1"
    room_id = "room_office_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id="face_1",
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id="face_1",
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    no_lineage_atom = EvidenceAtom(
        evidence_id="area_qty_1",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
        },
    )

    with pytest.raises(ValueError, match="unissued|unauthorized|not issued|caller-created|not registered|dimension lineage|dimension IDs"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="area_qty_1",
            area_evidence=no_lineage_atom,
        )


def test_caller_created_ceiling_correspondence_raises():
    """GPT MAX P1 regression: caller-instantiated correspondence without producer authority must raise ValueError."""
    from pb_migration_contracts import EvidenceResolutionStatus, EvidenceAtom
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )
    from types import SimpleNamespace

    doc_id = "doc1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev1"
    snap_id = "snap1"
    room_id = "room_office_1"

    caller_corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="caller_forged_corr_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id="face_1",
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id="face_1",
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    forged_atom = EvidenceAtom(
        evidence_id="area_qty_1",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )

    with pytest.raises(ValueError, match="unissued|unauthorized|not issued|caller-created|not registered"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=caller_corr,
            room=room,
            room_area_qty_id="area_qty_1",
            area_evidence=forged_atom,
        )


def test_fabricated_quantity_id_with_registered_room_area_raises():
    """GPT MAX P1 review: caller's fabricated quantity_id must not self-authorize; must reject."""
    from pb_migration_contracts import QuantityEvidence, EvidenceAtom, EvidenceResolutionStatus
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
        _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
    )
    from pb_cross_view_room_area_authority import (
        CrossViewRoomAreaRecord,
        _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT,
    )
    from types import SimpleNamespace

    doc_id = "doc_auth_1"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev_auth_1"
    snap_id = "snap_auth_1"
    room_id = "room_office_1"
    face_id = "face_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_auth_1",
        canonical_ceiling_id="c_1",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id=face_id,
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(snap_id, corr.record_id)] = corr

    atom = EvidenceAtom(
        evidence_id="authentic_atom_1",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )
    from pb_cross_view_room_area_authority import _RECORD_SEAL
    area_rec = CrossViewRoomAreaRecord(
        physical_room_id=room_id,
        source_room_face_record_id=face_id,
        room_label="OFFICE",
        source_dimension_page_id="11",
        source_label_observation_ids=(),
        source_label_receipt_ids=(),
        horizontal_dimension_id="dim_2536",
        vertical_dimension_id="dim_3570",
        area_evidence=atom,
        _seal=_RECORD_SEAL,
    )
    _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT[(snap_id, atom.evidence_id)] = area_rec
    _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT[(snap_id, room_id)] = area_rec

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id=face_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    # Fabricate a quantity ID that the caller passes as area_evidence.quantity_id
    # Caller attempts to self-authorize with fabricated_qty_self_authorized
    fabricated_qty = QuantityEvidence(
        quantity_id="fabricated_qty_self_authorized",
        family="floor_area",
        semantic_key="floor_area:room_office_1",
        value=9.05352,
        unit="m2",
        status="firm",
        evidence_ids=(atom.evidence_id,),
        authority="documented_dimension",
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )

    with pytest.raises(ValueError, match="unauthorized quantity evidence id|unissued or mismatched"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="fabricated_qty_self_authorized",
            area_evidence=fabricated_qty,
        )


def test_untyped_room_area_evidence_raises():
    """GPT MAX P1 review: untyped area object must be rejected in else branch."""
    from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
        _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
    )
    from pb_cross_view_room_area_authority import (
        CrossViewRoomAreaRecord,
        _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT,
    )
    from types import SimpleNamespace

    doc_id = "doc_auth_2"
    sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    rev_id = "rev_auth_2"
    snap_id = "snap_auth_2"
    room_id = "room_office_1"
    face_id = "face_1"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_auth_2",
        canonical_ceiling_id="c_2",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id=face_id,
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="SUSPENDED ACOUSTIC GRID CEILING",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(snap_id, corr.record_id)] = corr

    atom = EvidenceAtom(
        evidence_id="authentic_atom_2",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )
    from pb_cross_view_room_area_authority import _RECORD_SEAL
    area_rec = CrossViewRoomAreaRecord(
        physical_room_id=room_id,
        source_room_face_record_id=face_id,
        room_label="OFFICE",
        source_dimension_page_id="11",
        source_label_observation_ids=(),
        source_label_receipt_ids=(),
        horizontal_dimension_id="dim_2536",
        vertical_dimension_id="dim_3570",
        area_evidence=atom,
        _seal=_RECORD_SEAL,
    )
    _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT[(snap_id, atom.evidence_id)] = area_rec

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id=face_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    untyped_area = SimpleNamespace(
        quantity_id="authentic_atom_2",
        evidence_id="authentic_atom_2",
        value=9.05352,
        unit="m2",
        status="firm",
        family="floor_area",
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "dim_2536",
            "vertical_dimension_id": "dim_3570",
        },
    )

    with pytest.raises(ValueError, match="unauthorized room area evidence type"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=corr,
            room=room,
            room_area_qty_id="authentic_atom_2",
            area_evidence=untyped_area,
        )


def test_compose_office_ceiling_figured_dimension_linkage_and_foreign_dimension_rejection_raises():
    """Verify that independent view dimension IDs link via authenticated physical axis correspondence,
    and foreign/mismatched dimension IDs or areas fail closed with ValueError."""
    from types import SimpleNamespace
    from pb_source_cross_view_floor_correspondence_shadow import (
        EvidenceResolutionStatus,
        SourceCrossViewCeilingCorrespondenceRecord,
        _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
    )
    from pb_cross_view_room_area_authority import (
        CrossViewRoomAreaRecord,
        _RECORD_SEAL,
        _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT,
    )
    from pb_migration_contracts import EvidenceAtom, QuantityEvidence

    doc_id = "doc_dim_test"
    rev_id = "rev_dim_test"
    sha = "sha_dim_test"
    snap_id = "snap_dim_test"
    room_id = "OFFICE"
    face_id = "f_office"

    corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_ceiling_dim",
        canonical_ceiling_id="c_office",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id=face_id,
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(snap_id, corr.record_id)] = corr

    atom = EvidenceAtom(
        evidence_id="authentic_atom_dim",
        document_id=doc_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimension",
        normalized_value=9.05352,
        unit="m2",
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata={
            "document_id": doc_id,
            "source_sha256": sha,
            "snapshot_id": snap_id,
            "entity_id": room_id,
            "horizontal_dimension_id": "cross_view_native_dimension_h1",
            "vertical_dimension_id": "cross_view_native_dimension_v1",
            "horizontal_value_mm": 2536,
            "vertical_value_mm": 3570,
        },
    )

    room_area_rec = CrossViewRoomAreaRecord(
        physical_room_id=room_id,
        source_room_face_record_id=face_id,
        room_label=room_id,
        source_dimension_page_id="11",
        source_label_observation_ids=(),
        source_label_receipt_ids=(),
        horizontal_dimension_id="cross_view_native_dimension_h1",
        vertical_dimension_id="cross_view_native_dimension_v1",
        area_evidence=atom,
        _seal=_RECORD_SEAL,
    )
    _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT[(snap_id, atom.evidence_id)] = room_area_rec
    _REGISTERED_ROOM_AREA_RECORDS_BY_SNAPSHOT[(snap_id, room_id)] = room_area_rec

    room = SimpleNamespace(
        canonical_room_id=room_id,
        physical_room_id=room_id,
        room_label=room_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        source_room_face_record_id=face_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04)),
        evidence_ids=("ev_room",),
    )

    # 1. Authentic physical axis linkage succeeds
    ceil, qty = compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
        correspondence=corr,
        room=room,
        room_area_qty_id="authentic_atom_dim",
        area_evidence=atom,
    )
    assert qty.value == 9.05352

    # 2. Foreign / mismatched dimension IDs reject with ValueError
    bad_dim_corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_bad_dim",
        canonical_ceiling_id="c_office",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id=face_id,
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=9.05352,
        figured_dimension_ids=("dim_foreign_1", "dim_foreign_2"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(snap_id, bad_dim_corr.record_id)] = bad_dim_corr
    import pytest
    with pytest.raises(ValueError, match="do not match ceiling correspondence figured dimensions"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=bad_dim_corr,
            room=room,
            room_area_qty_id="authentic_atom_dim",
            area_evidence=atom,
        )

    # 3. Mismatched area product rejects with ValueError
    bad_area_corr = SourceCrossViewCeilingCorrespondenceRecord(
        record_id="rec_bad_area",
        canonical_ceiling_id="c_office",
        physical_room_id=room_id,
        canonical_room_id=room_id,
        source_room_face_record_id=face_id,
        support_page_id="9",
        support_viewport_id="VIEWPORT_P09_A120_RCP",
        target_page_id="7",
        target_viewport_id="VIEWPORT_P07_A110_PLAN",
        support_dimension_box_pdf_pts=(279.84, 1383.20, 422.64, 1584.56),
        target_box_pdf_pts=(173.04, 1382.72, 316.80, 1585.04),
        registration_translation_pdf_pts=(106.32, 0.0),
        finish_code="GRID",
        semantic_finish="GRID",
        ceiling_height_mm=2400.0,
        area_m2=15.00000,
        figured_dimension_ids=("dim_2536", "dim_3570"),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        definition_record_id="def_1",
        occurrence_record_id="occ_1",
        occurrence_evidence_id="ev_occ_1",
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
    )
    _REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[(snap_id, bad_area_corr.record_id)] = bad_area_corr
    with pytest.raises(ValueError, match="room area value mismatch with ceiling area|does not match physical room area"):
        compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=bad_area_corr,
            room=room,
            room_area_qty_id="authentic_atom_dim",
            area_evidence=atom,
        )
