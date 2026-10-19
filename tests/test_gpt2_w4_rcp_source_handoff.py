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
        "original_document_id":"source-document",
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
        "original_document_id":"source-document",
        "original_rcp_page":9,
        "original_rcp_viewport_id":"source-a120-rcp",
        "source_ceiling_ink_polygon_pdf_pts":
            ((98.,20.),(198.,20.),(198.,120.),(98.,120.)),
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


# Test the remaining independently source-issued RCP/material checks using a
# fixture in place of W4 only. The production module must still call and verify
# its real source-closed W4 room-face producer before issuing this handoff.
from copy import deepcopy
import pytest
import pb_gpt2_w4_rcp_source_handoff as original_rcp_bridge


def _source_owned_w4():
    return {
        "status": "source_original_floor_W4_face_candidate_only",
        "w4_room_face_source_identity_proven": True,
        "source_w4_wall_ownership_authenticated": True,
        "original_source_sha256": "a" * 64,
        "original_floor_page": "7",
        "original_revision_id": "revision-one",
        "original_snapshot_id": "snapshot-one",
        "original_document_id": "source-document",
        "original_physical_room_id": "physical-room",
        "original_source_room_face_record_id": "source-room-face",
        "original_source_floor_polygon_pdf_pts":
            ((20.,20.),(120.,20.),(120.,120.),(20.,120.)),
    }


def _authenticated_upstream_result(monkeypatch, *, w4=None, registration=None,
                                   ink=None, material=None):
    monkeypatch.setattr(
        original_rcp_bridge, "audit_gpt2_w4_bound_original_floor",
        lambda *args, **kwargs: _source_owned_w4() if w4 is None else w4,
    )
    return original_rcp_bridge.audit_gpt2_w4_original_rcp_ceiling_handoff(
        independently_registered_rcp=_registration() if registration is None
                                      else registration,
        original_rcp_ink=_rcp() if ink is None else ink,
        original_rcp_material=_material() if material is None else material,
        canonical_rooms=None, physical_room_id="physical-room",
    )


def test_source_positive_rcp_material_room_handoff_still_requires_gpt1_metric(monkeypatch):
    result=_authenticated_upstream_result(monkeypatch)
    assert result["status"]=="original_A120_RCP_material_on_W4_room_candidate_for_GPT1"
    assert result["original_ceiling_source_mark_ids"]==("source-A120-CL03-mark",)
    assert result["original_rcp_code"]=="CL03"
    assert result["ceiling_quantity_m2_issued"] is False
    assert result["floor_metric_area_copied_to_ceiling"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("where,key,value",[
    ("registration","original_floor_page","7"),
    ("registration","original_finish_page","9"),
    ("registration","original_floor_page",True),
    ("registration","original_floor_page",0),
    ("registration","original_finish_page",7),
    ("ink","original_rcp_page","9"),
    ("ink","original_rcp_page",True),
    ("w4","original_floor_page","07"),
    ("w4","original_floor_page",7),
])
def test_rcp_source_page_must_match_original_producer_type_and_identity(
    monkeypatch,where,key,value,
):
    receipts={
        "registration":_registration(),"ink":_rcp(),
        "w4":_source_owned_w4(),
    }
    receipts[where][key]=value
    result=_authenticated_upstream_result(
        monkeypatch,w4=receipts["w4"],
        registration=receipts["registration"],ink=receipts["ink"],
    )
    assert result["first_failure"]=="A120_original_source_page_identity_invalid"
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    "source-A120-CL03-mark",
    ["source-A120-CL03-mark"],
    (),
    ("source-A120-CL03-mark", "foreign-mark"),
    ("source-A120-CL03-mark", "source-A120-CL03-mark"),
    (" source-A120-CL03-mark ",),
    (None,),
    (12,),
])
def test_reconstructed_ceiling_material_mark_must_be_single_immutable_source_id(
    monkeypatch,bad,
):
    material=_material()
    material["original_source_finish_record_ids"]=bad
    result=_authenticated_upstream_result(monkeypatch,material=material)
    assert result["first_failure"]=="A120_original_issuers_or_mark_missing"
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("change",[
    {"source_ceiling_ink_polygon_pdf_pts":None},
    {"source_ceiling_ink_polygon_pdf_pts":"other zone"},
])
def test_rcp_material_must_carry_its_independent_native_ink_geometry(
    monkeypatch,change,
):
    material={**_material(),**change}
    result=_authenticated_upstream_result(monkeypatch,material=material)
    assert result["first_failure"]=="A120_material_ink_polygon_missing"


def test_original_material_mark_cannot_be_transferred_from_other_ceiling_polygon(
    monkeypatch,
):
    material=_material()
    material["source_ceiling_ink_polygon_pdf_pts"]=(
        (198.,20.),(298.,20.),(298.,120.),(198.,120.)
    )
    result=_authenticated_upstream_result(monkeypatch,material=material)
    assert result["first_failure"]=="A120_ceiling_area_cannot_borrow_floor_perimeter"
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("key,val",[
    ("original_material_definition_record_id"," other-material "),
    ("original_material_definition_record_id",None),
    ("original_rcp_scope_ownership_id",17),
    ("original_source_finish_code","CL03 "),
    ("original_source_finish_code",None),
])
def test_original_ceiling_material_scope_cannot_be_reconstructed_with_invalid_ids(
    monkeypatch,key,val,
):
    material=_material()
    material[key]=val
    result=_authenticated_upstream_result(monkeypatch,material=material)
    assert result["first_failure"]=="A120_original_issuers_or_mark_missing"
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("where,key,wrong",[
    ("material","original_rcp_page","9"),
    ("material","original_rcp_page",True),
    ("material","original_rcp_page",8),
    ("material","original_rcp_viewport_id","foreign-viewport"),
    ("material","original_rcp_viewport_id"," source-a120-rcp "),
    ("material","original_rcp_viewport_id",None),
    ("material","original_document_id","foreign-document"),
    ("material","original_document_id"," source-document "),
    ("material","original_document_id",None),
    ("ink","original_rcp_viewport_id","foreign-viewport"),
    ("ink","original_document_id","foreign-document"),
    ("w4","original_document_id","foreign-document"),
])
def test_rcp_ceiling_material_mark_cannot_reuse_foreign_page_view_or_document(
    monkeypatch,where,key,wrong,
):
    rcp=_rcp()
    material=_material()
    room=_source_owned_w4()
    candidate={"material":material,"ink":rcp,"w4":room}[where]
    candidate[key]=wrong
    result=_authenticated_upstream_result(
        monkeypatch,w4=room,ink=rcp,material=material,
    )
    assert result["first_failure"]==(
        "A120_material_original_page_view_or_document_conflict")
    assert result["ceiling_quantity_m2_issued"] is False
    assert result["new_firm_quantities"]==0


def test_same_authenticated_rcp_material_view_page_and_document_stays_candidate(
    monkeypatch,
):
    result=_authenticated_upstream_result(monkeypatch)
    assert result["status"]=="original_A120_RCP_material_on_W4_room_candidate_for_GPT1"
    assert result["original_rcp_page"]==9
    assert result["original_rcp_viewport_id"]=="source-a120-rcp"
    assert result["original_document_id"]=="source-document"
    assert result["new_firm_quantities"]==0
