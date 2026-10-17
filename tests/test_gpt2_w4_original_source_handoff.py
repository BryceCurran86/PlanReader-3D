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
