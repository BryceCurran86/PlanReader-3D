"""Real original area producer -> exact source floor -> finish candidate.

Synthetic producer records use their test-only issuance seal; the production
path never creates producer records from caller strings.
"""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status,QuantityEvidence
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,SourceMaterialDefinitionResult,
    SourceMaterialOccurrenceRecord,SourceMaterialOccurrenceScopeResult,
)
from pb_gpt1_original_two_view_wall_frame_shadow import SourceWallRingFrameShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,
)
from pb_gpt1_original_material_producer_finish_bridge_shadow import (
    OriginalAuthenticatedTextPaintClipReceipt,
)
from pb_gpt1_source_producer_floor_finish_pipeline_shadow import (
    diagnose_source_producer_floor_finish_handoff_shadow,
    reconcile_source_producer_finish_batch_shadow,
)
from test_gpt1_producer_figured_area_ring_bridge_shadow import (
    original_ring,original_producer_area,original_canonical_floor,
)

SHA="a"*64


def source_finish_definition():
    record=SourceMaterialDefinitionRecord(
        "auth-definition","document","rev",SHA,"snapshot","TEST_FLOOR",
        "Floor tile","floor substrate","floor tile","tile",
        ("original-definition-observation",),("11",),("original-schedule",),
    )
    return SourceMaterialDefinitionResult(Status.CORROBORATED,("auth",),record)


def original_scope():
    record=SourceMaterialOccurrenceRecord(
        "source-plan-occurrence","document","rev",SHA,"snapshot",
        "11","floor-finish-plan","TEST_FLOOR","tile",
        "auth-definition",(3,1,4,2),"TEST_FLOOR",
        "native-source-observation",
        ("native-text-observation-1",),
    )
    return SourceMaterialOccurrenceScopeResult(
        Status.CORROBORATED,("scope-complete",),True,(record,),
    )


def original_paint():
    return OriginalAuthenticatedTextPaintClipReceipt(
        "source-plan-occurrence",("native-text-observation-1",),
        "glyph-receipt","clip-receipt","native-partition",
        SHA,"rev","11","floor-finish-plan",
        "original_visible_native_glyph_and_clip_authenticated",
    )


def original_area_quantity():
    return QuantityEvidence(
        quantity_id="original-existing-signed-area-id",
        family="room_area",semantic_key="room_area:canonical-room",
        value=10.,unit="m2",input_entity_ids=("canonical-room",),
        evidence_ids=("original-area-receipt",),
        formula="original figured dimension product",formula_version="1.0.0",
        authority="documented_dimension",status="FIRM",confidence=1.,
        metadata={"source_sha256":SHA,"revision_id":"rev",
                  "source_room_face_record_id":"original-room-face-one"},
    )


def original_floor_correspondence():
    canonical_id=original_canonical_floor().floors[0].canonical_floor_id
    return PhysicalFloorFinishCorrespondenceShadow(
        Status.CANDIDATE,("original-physical-wall-ownership",),
        "physical-room-one",canonical_id,("original-wall-issuer",),
        ((0,0),(10,0),(10,5),(0,5)),"11",SHA,"rev",
        "snapshot","decision-scope",True,
        "original-room-face-one","7",
    )


def valid_kwargs():
    return dict(
        physical_ring=original_ring(),
        original_room_face_id="original-room-face-one",
        same_view_areas=original_producer_area(),
        cross_view_areas=None,
        canonical_floors=original_canonical_floor(),
        original_signed_room_area=original_area_quantity(),
        structural_frame=SourceWallRingFrameShadow(
            Status.CANDIDATE,("original-wall-frame",),(1.,0.,0.,0.),0.,
            ("wall-one","wall-two","wall-three","wall-four"),
            ("original-wall-issuer",)
        ),
        crosssheet_floor=original_floor_correspondence(),
        finish_definition=source_finish_definition(),
        complete_finish_occurrences=original_scope(),
        native_paint_clip_receipts=(original_paint(),),
    )


def test_full_existing_original_area_plus_material_source_pipeline_remains_candidate():
    result=diagnose_source_producer_floor_finish_handoff_shadow(**valid_kwargs())
    assert result.status is Status.CANDIDATE
    assert result.first_failure_code is None
    assert result.existing_room_area_quantity_id=="original-existing-signed-area-id"
    assert result.existing_room_area_m2==10.
    assert result.candidate_finish_area_m2==10.
    assert result.source_finish_occurrence_id=="source-plan-occurrence"
    assert result.source_finish_definition_id=="auth-definition"
    assert result.diagnostic_only
    assert not hasattr(result,"quantity_id")


def test_crosssheet_physical_face_scope_is_distinct_from_canonical_room_alias():
    kwargs=valid_kwargs()
    kwargs["crosssheet_floor"]=replace(
        kwargs["crosssheet_floor"],source_room_face_record_id="rival-face"
    )
    out=diagnose_source_producer_floor_finish_handoff_shadow(**kwargs)
    assert out.status is Status.ABSTAINED
    assert out.first_failure_code == (
        "gpt1_source_crosssheet_physical_wall_equivalence_unavailable"
    )


def test_original_ceiling_or_cladding_material_cannot_launder_floor_finish():
    kwargs=valid_kwargs()
    wrong=replace(kwargs["finish_definition"].record,
                  semantic_finish="signage_cladding",
                  description="Facade sign",finish="signage")
    kwargs["finish_definition"]=replace(kwargs["finish_definition"],record=wrong)
    out=diagnose_source_producer_floor_finish_handoff_shadow(**kwargs)
    assert out.status is Status.ABSTAINED
    assert out.candidate_finish_area_m2 is None


def test_source_finish_and_signed_area_ids_cannot_be_reissued():
    kwargs=valid_kwargs()
    kwargs["original_signed_room_area"]=replace(
        kwargs["original_signed_room_area"],quantity_id="new-unsigned-area"
    )
    out=diagnose_source_producer_floor_finish_handoff_shadow(**kwargs)
    assert out.status is Status.ABSTAINED
    assert out.first_failure_code == (
        "gpt1_source_original_firm_room_area_handoff_unavailable"
    )


def test_a_missing_room_issuer_produces_first_failure_not_an_invented_number():
    kwargs=valid_kwargs()
    kwargs["same_view_areas"]=None
    out=diagnose_source_producer_floor_finish_handoff_shadow(**kwargs)
    assert out.status is Status.ABSTAINED
    assert out.candidate_finish_area_m2 is None
    assert out.first_failure_code == (
        "source_producer_figured_ring_inputs_unavailable"
    )


def test_one_original_ft_plan_occurrence_cannot_be_used_for_two_rooms():
    first=diagnose_source_producer_floor_finish_handoff_shadow(**valid_kwargs())
    assert first.status is Status.CANDIDATE
    second=replace(
        first,physical_room_id="another-physical-room",
        source_room_face_record_id="another-source-face",
        canonical_floor_id="another-floor",
        existing_room_area_quantity_id="another-original-signed-room-area",
    )
    for order in ((first,second),(second,first)):
        batch=reconcile_source_producer_finish_batch_shadow(order)
        assert batch.status is Status.CONFLICT
        assert len(batch.records)==2
        assert all(r.status is Status.ABSTAINED for r in batch.records)
        assert all(r.candidate_finish_area_m2 is None for r in batch.records)
        assert batch.quarantined_physical_room_ids==(
            "another-physical-room","physical-room-one",
        )


def test_one_source_signed_area_cannot_fund_two_different_ft_occurrences():
    first=diagnose_source_producer_floor_finish_handoff_shadow(**valid_kwargs())
    second=replace(
        first,physical_room_id="another-physical-room",
        source_room_face_record_id="another-source-face",
        canonical_floor_id="another-floor",
        source_finish_occurrence_id="independently-painted-mark",
    )
    batch=reconcile_source_producer_finish_batch_shadow((first,second))
    assert batch.status is Status.CONFLICT
    assert all(r.status is Status.ABSTAINED for r in batch.records)


def test_distinct_original_area_and_material_receipts_keep_independent_candidates():
    first=diagnose_source_producer_floor_finish_handoff_shadow(**valid_kwargs())
    second=replace(
        first,physical_room_id="another-physical-room",
        source_room_face_record_id="another-source-face",
        canonical_floor_id="another-floor",
        existing_room_area_quantity_id="another-original-signed-room-area",
        source_finish_occurrence_id="independently-painted-mark",
    )
    batch=reconcile_source_producer_finish_batch_shadow((second,first))
    assert batch.status is Status.CANDIDATE
    assert len(batch.records)==2
    assert all(r.status is Status.CANDIDATE for r in batch.records)
    assert batch.quarantined_physical_room_ids==()
    assert batch.diagnostic_only
