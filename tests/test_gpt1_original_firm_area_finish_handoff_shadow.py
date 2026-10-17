"""Existing FIRM room area passes through finish bridge without reissuance."""
from dataclasses import replace
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_migration_contracts import QuantityEvidence,EvidenceResolutionStatus as Status
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,PhysicalFloorFinishCandidate,
)
from pb_gpt1_original_firm_area_finish_handoff_shadow import (
    reuse_authenticated_room_area_for_finish_shadow,
)

SHA="a"*64


def _floor():
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id="floor-id",physical_floor_surface_id="floor-id",
        room_entity_id="canonical-room-not-physical-room",document_id="doc",
        revision_id="rev",source_sha256=SHA,snapshot_id="original-snapshot",
        page_id="7",viewport_id="main-view",
        polygon_pdf_pts=((0,0),(1,0),(1,1),(0,1)),
        area_page_pts2=1,bounding_wall_ids=(),canonical_bounding_wall_ids=(),
        source_room_face_record_id="source-face-id",evidence_ids=("source-face-id",),
        geometry_complete=False,metric_geometry_complete=False,
        metric_area_m2=10.,metric_area_quantity_id="original-qty-id",
        metric_area_authority="documented_dimension",
        finish_descriptor=None,structural_slab_id=None,
        physical_floor_surface_identity_resolved=False,
        commercial_quantity_authority=False,
    )


def _area():
    return QuantityEvidence(
        quantity_id="original-qty-id",family="room_area",
        semantic_key="room_area:canonical-room-not-physical-room",
        value=10.,unit="m2",input_entity_ids=("canonical-room-not-physical-room",),
        formula="original-source-figured-axes",formula_version="1.0.0",
        evidence_ids=("source-face-id",),authority="documented_dimension",
        status="FIRM",confidence=1.,abstained=False,
        metadata={
            "source_sha256":SHA,"revision_id":"rev",
            "source_room_face_record_id":"source-face-id",
        },
    )


def _correspondence():
    return PhysicalFloorFinishCorrespondenceShadow(
        Status.CANDIDATE,("source-physical-correspondence",),
        "physical-room-id","floor-id",("wall-equivalence",),
        ((0,0),(10,0),(10,5),(0,5)),"11",SHA,"rev",
        "original-snapshot","decision-scope",True,
        "source-face-id","7",
    )


def _finish():
    return PhysicalFloorFinishCandidate(
        Status.CANDIDATE,("source-plan-mark",),"floor-id",
        "mark-FT3","definition-FT3","FT3",10.,
    )


def test_original_firm_area_reused_exactly_no_new_signed_quantity():
    a=_area();out=reuse_authenticated_room_area_for_finish_shadow(
        _floor(),a,_correspondence(),_finish())
    assert out.status is Status.CANDIDATE
    assert out.candidate_finish_area_m2==a.value
    assert out.original_room_area_quantity_id==a.quantity_id
    assert out.original_floor_finish_code=="FT3"
    assert out.diagnostic_only
    assert not hasattr(out,"quantity_id")


def test_old_firm_area_cannot_rebind_to_wrong_physical_room_face():
    other=replace(_correspondence(),source_room_face_record_id="different-face")
    out=reuse_authenticated_room_area_for_finish_shadow(_floor(),_area(),other,_finish())
    assert out.status is Status.ABSTAINED


def test_previous_figure_receipt_must_not_be_reissued_under_new_qty_id():
    old=replace(_area(),quantity_id="different-historical-ID")
    out=reuse_authenticated_room_area_for_finish_shadow(_floor(),old,_correspondence(),_finish())
    assert out.status is Status.ABSTAINED


def test_existing_plain_area_does_not_gain_firm_finish_from_candidate_mark():
    a=_area()
    for m in (replace(_finish(),status=Status.ABSTAINED),
              replace(_finish(),candidate_area_m2=12.),
              replace(_finish(),original_occurrence_id=None)):
        out=reuse_authenticated_room_area_for_finish_shadow(
            _floor(),a,_correspondence(),m)
        assert out.status is Status.ABSTAINED
