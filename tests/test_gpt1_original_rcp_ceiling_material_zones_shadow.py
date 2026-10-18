"""Original RCP ceiling roles distinguish GRID/IPF1 from signage cladding."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_original_crosssheet_marked_sections_shadow import OriginalSourceMarkedSectionsShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,AuthenticatedFloorFinishPlanMark,
)
from pb_gpt1_original_rcp_ceiling_material_zones_shadow import (
    OriginalCeilingSurfaceRoleReceipt,reconcile_source_rcp_ceiling_material_zones_shadow,
)
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,SourceMaterialDefinitionResult,
)

SHA="a"*64

def physical():
    return PhysicalFloorFinishCorrespondenceShadow(
        Status.CANDIDATE,("original-source",),"room","floor",
        ("wall-equivalence",),((0,0),(10,0),(10,5),(0,5)),
        "9",SHA,"rev","snapshot","scope",True,"face","7",
    )

def role():
    return OriginalCeilingSurfaceRoleReceipt(
        "ceiling","room","9",("original-rcp-viewport",),
        "original_flat_horizontal_ceiling",SHA,"rev","snapshot",
    )

def definition(code,semantic):
    record=SourceMaterialDefinitionRecord(
        f"definition-{code}","doc","rev",SHA,"snapshot",code,
        code,"lining","finish",semantic,
        (f"source-text-{code}",),("9",),("schedule",),
    )
    return SourceMaterialDefinitionResult(Status.CORROBORATED,("source",),record)

def marks():
    return tuple(AuthenticatedFloorFinishPlanMark(
        f"occ-{code}",f"definition-{code}",f"paint-{code}",f"clip-{code}",
        "source-partition",code,semantic,(i,1,i+1,2),
        SHA,"rev","9","rcp-plan",True,
    ) for i,(code,semantic) in enumerate(
        (("GRID","ceiling_grid"),("IPF1","plasterboard")),start=1,
    ))

def zones():
    return OriginalSourceMarkedSectionsShadow(
        Status.CANDIDATE,("source-sections",),
        (("a","GRID","occ-GRID",5.),("b","IPF1","occ-IPF1",5.)),
        (("GRID",5.),("IPF1",5.)),0.,
        ("occ-GRID","occ-IPF1"),
    )


def test_original_rcp_grid_and_plasterboard_remain_distinct_metric_areas():
    result=reconcile_source_rcp_ceiling_material_zones_shadow(
        zones(),physical(),role(),
        (definition("GRID","ceiling_grid"),definition("IPF1","plasterboard")),
        marks(),
    )
    assert result.status is Status.CANDIDATE
    assert result.candidate_ceiling_lining_m2_by_code==( ("GRID",5.),("IPF1",5.) )
    assert result.candidate_ceiling_lining_m2_by_semantic==(
        ("ceiling_grid",5.),("plasterboard",5.)
    )
    assert result.diagnostic_only


def test_signage_cladding_cannot_be_promoted_to_ceiling_lining():
    excluded=definition("CLD3","signage_cladding")
    result=reconcile_source_rcp_ceiling_material_zones_shadow(
        zones(),physical(),role(),(excluded,),marks(),
    )
    assert result.status is Status.ABSTAINED
    assert result.candidate_ceiling_lining_m2_by_code==()


def test_no_flat_source_ceiling_role_means_no_normal_plan_area_claim():
    result=reconcile_source_rcp_ceiling_material_zones_shadow(
        zones(),physical(),
        replace(role(),original_surface_plane_semantic="unresolved_raked"),
        (definition("GRID","ceiling_grid"),definition("IPF1","plasterboard")),
        marks(),
    )
    assert result.status is Status.ABSTAINED


def test_an_unlisted_original_finish_mark_cannot_reuse_a_ceiling_qty():
    result=reconcile_source_rcp_ceiling_material_zones_shadow(
        zones(),physical(),role(),
        (definition("GRID","ceiling_grid"),definition("IPF1","plasterboard")),
        marks()[:1],
    )
    assert result.status is Status.ABSTAINED
