"""W4 producer-face ownership gates for GPT2 source floor finish handoff.

Synthetic-only: no private Maryborough drawing, quantities or benchmark gold.
"""
from pb_migration_contracts import EvidenceResolutionStatus
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition, LiveCanonicalRoomObject,
)
from pb_gpt2_w4_original_floor_handoff import (
    audit_gpt2_w4_bound_original_floor,
    audit_gpt2_w4_material_to_gpt1,
)


SHA = "a" * 64
BOX = ((20.,20.),(120.,20.),(120.,100.),(20.,100.))


def _room(*,polygon=BOX,physical_room_id="room-one",sha=SHA):
    return LiveCanonicalRoomObject(
        canonical_room_id="canonical-room-one",
        physical_room_id=physical_room_id,
        document_id="source-drawing",
        revision_id="first-native-revision",
        source_sha256=sha,
        snapshot_id="original-snapshot",
        page_id="7",
        viewport_id="real-plan-view-id",
        decision_scope_id="producer-decision-scope",
        polygon_pdf_pts=polygon,
        bounding_wall_ids=("wall-left","wall-right","wall-bottom","wall-top"),
        canonical_bounding_wall_ids=("wall-left","wall-right","wall-bottom","wall-top"),
        wall_relationships_complete=True,
        area_page_pts2=8000.,
        source_room_face_record_id="room-face-issuer-owned",
        evidence_ids=("source-real-face",),
        geometry_complete=True,
        metric_geometry_complete=False,
    )


def _composition(room):
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("source-geometry",),
        rooms=(room,),
        source_pages=(7,),
    )


def _receipt(*,polygon=BOX,sha=SHA):
    return {
        "status":"original_source_ink_ring_translation_candidate",
        "original_source_sha256":sha,
        "original_floor_page":7,
        "geometric_ink_correspondence_only":True,
        "source_floor_perimeter_polygon_pdf_pts":polygon,
    }


def test_matching_caller_copied_polygon_still_lacks_the_sealed_W4_room_face_issuer():
    result=audit_gpt2_w4_bound_original_floor(
        _receipt(), canonical_rooms=_composition(_room()),
        physical_room_id="room-one")
    assert result["first_failure"]=="sealed_W4_room_face_issuer_missing"
    assert not result["w4_room_face_source_identity_proven"]
    assert result["new_firm_quantities"]==0


def test_matching_source_label_does_not_override_physical_room_mismatch():
    result=audit_gpt2_w4_bound_original_floor(
        _receipt(), canonical_rooms=_composition(_room()),
        physical_room_id="room-unregistered")
    assert result["first_failure"]=="original_physical_room_missing_or_duplicate"
    assert not result["w4_room_face_source_identity_proven"]


def test_mismatched_sha_or_floor_page_cannot_bind_to_source_room():
    outcome=audit_gpt2_w4_bound_original_floor(
        _receipt(sha="b"*64),canonical_rooms=_composition(_room()),
        physical_room_id="room-one")
    assert outcome["first_failure"]=="original_pdf_room_root_or_page_mismatch"
    assert outcome["new_firm_quantities"]==0


def test_nearby_source_polygon_never_snaps_to_W4_room():
    almost=((20.0001,20.),(120.,20.),(120.,100.),(20.,100.))
    result=audit_gpt2_w4_bound_original_floor(
        _receipt(polygon=almost),canonical_rooms=_composition(_room()),
        physical_room_id="room-one")
    assert result["first_failure"]=="source_floor_ink_vs_W4_face_geometry_conflict"
    assert result["new_firm_quantities"]==0


def test_room_duplicate_even_with_same_source_label_cannot_elect_first_owner():
    c=LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,reason_codes=(),
        rooms=(_room(),_room()),source_pages=(7,))
    result=audit_gpt2_w4_bound_original_floor(
        _receipt(),canonical_rooms=c,physical_room_id="room-one")
    assert result["first_failure"]=="original_physical_room_missing_or_duplicate"


def test_ft3_original_mark_without_independently_proven_W4_cannot_enter_measurement():
    w4=audit_gpt2_w4_bound_original_floor(
        _receipt(),canonical_rooms=_composition(_room()),
        physical_room_id="room-one")
    claimed_mark={
        "status":"source_owned_material_on_original_ink_ring_candidate",
        "original_source_sha256":SHA,
        "original_finish_code":"FT3",
        "original_material_definition_id":"schedule-ft3",
        "original_mark_source_record_ids":("page11-ft3",),
    }
    handoff=audit_gpt2_w4_material_to_gpt1(w4,claimed_mark)
    assert handoff["status"]=="gpt2_source_to_gpt1_handoff_abstained"
    assert handoff["new_firm_quantities"]==0
    assert not handoff["source_finish_area_quantity_issued"]



def _w4_source_positive_candidate():
    # These dicts are handoff-level synthetic fixtures, NOT sealed W4 issuers.
    return {
        "status":"source_original_floor_W4_face_candidate_only",
        "w4_room_face_source_identity_proven":True,
        "original_source_sha256":SHA,
        "original_document_id":"source-drawing",
        "original_revision_id":"source-revision",
        "original_snapshot_id":"source-snapshot",
        "original_floor_page":"7",
        "original_source_floor_polygon_pdf_pts":BOX,
        "original_physical_room_id":"pwd",
        "original_canonical_room_id":"canonical-pwd",
        "original_source_room_face_record_id":"real-w4-face",
        "original_source_w4_wall_ids":("w1","w2","w3","w4"),
    }


def _material_source_positive_candidate():
    return {
        "status":"source_owned_material_on_original_ink_ring_candidate",
        "original_source_sha256":SHA,
        "original_document_id":"source-drawing",
        "original_revision_id":"source-revision",
        "original_snapshot_id":"source-snapshot",
        "original_floor_page":7,
        "original_finish_page":11,
        "original_source_floor_perimeter_polygon_pdf_pts":BOX,
        "original_source_finish_perimeter_polygon_pdf_pts":
            ((30.,20.),(130.,20.),(130.,100.),(30.,100.)),
        "original_source_scope_ownership_id":"original-finish-scope",
        "original_finish_viewport_id":"original-a140",
        "original_finish_code":"FT2",
        "original_material_definition_id":"source-a140-ft2",
        "original_mark_source_record_ids":("actual-mark-1",),
    }


def test_source_material_mark_must_be_same_original_physical_floor_polygon():
    from copy import deepcopy
    owner=_w4_source_positive_candidate()
    material=_material_source_positive_candidate()
    accepted=audit_gpt2_w4_material_to_gpt1(owner,material)
    assert accepted["status"]=="gpt2_W4_source_finished_floor_ready_for_GPT1_measurement"
    assert accepted["new_firm_quantities"]==0
    assert accepted["source_quantity_sealing_authority_granted"] is False
    assert accepted["FT2_exclude_wall_footprint"] is True
    assert accepted["FT2_92mm_wall_widths_already_outside_clear_figures"] is None
    assert accepted["original_dimension_terminal_to_finished_W4_face_proven"] is False
    for change in (
        {"original_source_floor_perimeter_polygon_pdf_pts":
            ((20.001,20.),(120.,20.),(120.,100.),(20.,100.))},
        {"original_source_floor_perimeter_polygon_pdf_pts":
            ((30.,20.),(130.,20.),(130.,100.),(30.,100.))},
        {"original_floor_page":8},
        {"original_floor_page":"07"},
        {"original_finish_page":7},
        {"original_finish_page":"not-a-page"},
        {"original_source_finish_perimeter_polygon_pdf_pts":()},
    ):
        rival=deepcopy(material)
        rival.update(change)
        result=audit_gpt2_w4_material_to_gpt1(owner,rival)
        assert result["first_failure"]=="original_finish_mark_and_W4_physical_floor_mismatch"
        assert result["new_firm_quantities"]==0


def test_missing_original_mark_source_scope_or_multiple_marks_never_publish():
    material=_material_source_positive_candidate()
    for field,value in (
        ("original_source_scope_ownership_id",None),
        ("original_finish_viewport_id",None),
        ("original_material_definition_id",None),
        ("original_mark_source_record_ids",("mark1","mark2")),
        ("original_mark_source_record_ids",()),
    ):
        rival={**material,field:value}
        result=audit_gpt2_w4_material_to_gpt1(
            _w4_source_positive_candidate(),rival)
        assert result["first_failure"]=="original_finish_scope_or_unique_source_mark_unproven"
        assert result["source_finish_area_quantity_issued"] is False


def test_all_laid_floor_finishes_stop_at_internal_faces_and_door_thresholds():
    original=_material_source_positive_candidate()
    for code in ("FT2", "FT3", "VINYL", "FT5"):
        candidate={**original,"original_finish_code":code}
        result=audit_gpt2_w4_material_to_gpt1(
            _w4_source_positive_candidate(),candidate)
        assert result["status"]=="gpt2_W4_source_finished_floor_ready_for_GPT1_measurement"
        assert result["floor_finish_measurement_boundary_basis"]==(
            "inside_finished_wall_faces_required_unverified")
        assert result["all_floor_finishes_exclude_wall_footprint"] is True
        assert result["floor_finish_doorway_transition_boundary_required"] is True
        assert result["original_finished_wall_face_boundary_authenticated"] is False
        assert result["original_doorway_finish_transition_boundary_authenticated"] is False
        assert result["original_dimension_terminal_to_finished_W4_face_proven"] is False
        assert result["original_D13_threshold_finish_area_verified"] is False
        assert result["source_quantity_sealing_authority_granted"] is False
        assert result["new_firm_quantities"]==0


def test_different_floor_finish_code_does_not_change_source_measured_area():
    original=_material_source_positive_candidate()
    owner=_w4_source_positive_candidate()
    issued=[
        audit_gpt2_w4_material_to_gpt1(owner,{**original,"original_finish_code":code})
        for code in ("FT2","FT3")
    ]
    assert all(r["source_metric_room_area_not_minted_here"] is True for r in issued)
    assert all(r["source_finish_area_quantity_issued"] is False for r in issued)
    assert issued[0]["floor_finish_measurement_boundary_basis"]==(
        issued[1]["floor_finish_measurement_boundary_basis"])
