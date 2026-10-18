"""Original material producer scope, exact word paint/clip and floor finish."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,SourceMaterialDefinitionResult,
    SourceMaterialOccurrenceRecord,SourceMaterialOccurrenceScopeResult,
)
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,
)
from pb_gpt1_original_material_producer_finish_bridge_shadow import (
    OriginalAuthenticatedTextPaintClipReceipt,
    use_original_semantic_producer_for_finish_shadow,
)

SHA="a"*64


def scope():
    return PhysicalFloorFinishCorrespondenceShadow(
        Status.CANDIDATE,("source-physical-wall-equivalence",),
        "room","floor",("wall-proof",),((0,0),(10,0),(10,5),(0,5)),
        "11",SHA,"rev","snapshot","scope",True,"face","7",
    )


def area():
    return FiguredPolygonMetricShadow(
        Status.CANDIDATE,("documented-source-figure",),10.,
        ((0,0),(5000,0),(5000,2000),(0,2000)),
        ("witness-1","witness-2"),(),
        SHA,"rev","7","room",
    )


def definition():
    row=SourceMaterialDefinitionRecord(
        "source-definition","doc","rev",SHA,"snapshot","FT3",
        "Floor finish three","concrete","floor coating","epoxy",
        ("source-definition-text",),("11",),("schedule-viewport",),
    )
    return SourceMaterialDefinitionResult(Status.CORROBORATED,("source",),row)


def occurrence(code="FT3",box=(2,1,3,2),identifier="occ"):
    return SourceMaterialOccurrenceRecord(
        identifier,"doc","rev",SHA,"snapshot","11","plan-viewport",
        code,"epoxy","source-definition",
        box,code,"material-observation",
        ("source-text-1",),
    )


def scope_records(*rows):
    return SourceMaterialOccurrenceScopeResult(
        Status.CORROBORATED,("source-complete",),True,tuple(rows),
    )


def paint(id="occ"):
    return OriginalAuthenticatedTextPaintClipReceipt(
        id,("source-text-1",),"glyph-paint","pdf-clip","partition",
        SHA,"rev","11","plan-viewport",
        "original_visible_native_glyph_and_clip_authenticated",
    )


def test_exact_original_material_definition_plan_mark_and_paint_scope_candidate():
    result=use_original_semantic_producer_for_finish_shadow(
        area(),scope(),definition(),scope_records(occurrence()),(paint(),))
    assert result.status is Status.CANDIDATE
    assert result.original_occurrence_id=="occ"
    assert result.original_definition_id=="source-definition"
    assert result.original_finish_code=="FT3"
    assert result.candidate_area_m2==10.
    assert result.diagnostic_only


def test_unproved_native_clip_or_partial_occurrence_universe_abstains():
    wrong=replace(paint(),original_paint_and_clip_status="unverified")
    for original_scope,proof in (
        (scope_records(occurrence()),(wrong,)),
        (replace(scope_records(occurrence()),scope_complete=False),(paint(),)),
    ):
        result=use_original_semantic_producer_for_finish_shadow(
            area(),scope(),definition(),original_scope,proof)
        assert result.status is Status.ABSTAINED


def test_other_source_room_mark_does_not_veto_this_physical_floor():
    other=replace(occurrence(
        "FT2",(20,20,21,21),"outside"
    ),definition_record_id="other-definition",
        source_text_observation_ids=("outside-text",))
    result=use_original_semantic_producer_for_finish_shadow(
        area(),scope(),definition(),scope_records(occurrence(),other),(paint(),))
    assert result.status is Status.CANDIDATE


def test_competing_real_plan_mark_inside_exact_same_floor_must_abstain():
    other=replace(occurrence("FT2",(5,1,6,2),"other"),
        definition_record_id="another-definition",
        source_text_observation_ids=("other-text",))
    result=use_original_semantic_producer_for_finish_shadow(
        area(),scope(),definition(),scope_records(occurrence(),other),(paint(),))
    assert result.status is Status.ABSTAINED


def test_original_material_snapshot_drift_cannot_restore_finish():
    bad=replace(definition().record,snapshot_id="another-run")
    changed=replace(definition(),record=bad)
    result=use_original_semantic_producer_for_finish_shadow(
        area(),scope(),changed,scope_records(occurrence()),(paint(),))
    assert result.status is Status.ABSTAINED


def test_actual_source_material_semantics_reject_wall_or_signage_cladding():
    same=definition()
    cladding=replace(
        same.record,
        description="External signage cladding",
        finish="wall panel",
        semantic_finish="signage_cladding",
    )
    result=use_original_semantic_producer_for_finish_shadow(
        area(),scope(),replace(same,record=cladding),
        scope_records(occurrence()),(paint(),),
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("original_finish_definition_not_floor_finish",)
