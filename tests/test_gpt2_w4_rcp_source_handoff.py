"""Source-only original A120 RCP cross-sheet W4 acceptance negatives.

A source material schedule, a floor footprint, copied canonical room flags or
equivalent ink-box areas never create a ceiling square metre measurement.
"""
from pb_gpt2_w4_rcp_source_handoff import (
    audit_gpt2_w4_original_rcp_ceiling_handoff as audit,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition, LiveCanonicalRoomObject,
)


def _rcp():
    return {
        "status":"original_rcp_source_ink_ceiling_polygon_candidate",
        "original_source_sha256":"a"*64,
        "original_revision_id":"revision-one",
        "original_snapshot_id":"snapshot-one",
        "original_rcp_page":9,
        "original_rcp_viewport_id":"source-a120-rcp",
        "source_ceiling_ink_polygon_pdf_pts":
            ((98.,20.),(198.,20.),(198.,120.),(98.,120.)),
        "source_ceiling_polygon_area_pdf_pt2_not_m2":10000.,
    }


def _registration():
    return {
        "status":"original_source_ink_ring_translation_candidate",
        "geometric_ink_correspondence_only":True,
        "original_source_sha256":"a"*64,
        "original_floor_page":7,
        "original_finish_page":9,
        "source_floor_perimeter_polygon_pdf_pts":
            ((20.,20.),(120.,20.),(120.,120.),(20.,120.)),
        "source_finishes_perimeter_polygon_pdf_pts":
            ((98.,20.),(198.,20.),(198.,120.),(98.,120.)),
        "source_cross_sheet_translation_pdf_pts":[78.,0.],
    }


def _material():
    return {
        "status":"original_rcp_material_in_ceiling_ink_candidate",
        "original_source_sha256":"a"*64,
        "original_revision_id":"revision-one",
        "original_snapshot_id":"snapshot-one",
        "original_source_finish_record_ids":("source-A120-CL03-mark",),
        "original_material_definition_record_id":"source-A120-CL03-schedule",
        "original_rcp_scope_ownership_id":"F07-source-viewport-receipt",
        "original_source_finish_code":"CL03",
    }


def test_original_ceiling_requires_published_W4_face_not_copied_fields():
    r=audit(
        independently_registered_rcp=_registration(),
        original_rcp_ink=_rcp(),
        original_rcp_material=_material(),
        canonical_rooms=None,physical_room_id="office-physical-room",
    )
    assert r["status"]=="original_W4_RCP_ceiling_handoff_abstained"
    assert r["first_failure"]=="canonical_source_room_authority_unavailable"
    assert not r["ceiling_quantity_m2_issued"]
    assert not r["floor_metric_area_copied_to_ceiling"]
    assert r["new_firm_quantities"]==0


def test_copied_original_floor_area_cannot_be_substituted_for_ceiling_measurement():
    source=_registration()
    source["source_floor_area_m2"]=9.05352
    source["floor_area_metric_ready"]=True
    source["W4_authenticated"]=True
    fake=LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(),rooms=(),source_pages=(7,))
    result=audit(
        independently_registered_rcp=source,
        original_rcp_ink=_rcp(),original_rcp_material=_material(),
        canonical_rooms=fake,physical_room_id="office-physical-room")
    assert result["first_failure"]=="original_physical_room_missing_or_duplicate"
    assert not result["ceiling_quantity_m2_issued"]
    assert result["new_firm_quantities"]==0


def test_original_rcp_missing_material_never_enters_gpt1_area_pipeline():
    receipt=audit(
        independently_registered_rcp=_registration(),
        original_rcp_ink=_rcp(),
        original_rcp_material={"status":"no-original-source-cl03-definition"},
        canonical_rooms=None,physical_room_id="office-physical-room",
    )
    assert receipt["status"]=="original_W4_RCP_ceiling_handoff_abstained"
    assert receipt["new_firm_quantities"]==0
