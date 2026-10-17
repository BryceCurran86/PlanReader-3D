"""Exact physical source wall correspondence precedes a plan finish candidate."""
from dataclasses import replace
from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide, measure_figured_room_edge_chain_shadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    OriginalTwoSheetBoundaryOwner,OriginalPhysicalFloorToFinishScope,
    AuthenticatedFloorFinishPlanMark,
    resolve_source_physical_floor_correspondence_shadow,
    bind_source_finish_mark_to_corresponded_floor_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status


def _room():
    pts=((0,0),(10,0),(10,5),(0,5))
    sides=tuple(FiguredPhysicalSide(
        f"side-{i}",pts[i],pts[(i+1)%4],(f"room-ink-{i}",),
        {0:5000,1:2000}.get(i),
        f"fig-{i}" if i in (0,1) else None,
        (f"witness-{i}-a",f"witness-{i}-b") if i in (0,1) else (),
    ) for i in range(4))
    return measure_figured_room_edge_chain_shadow(
        sides,source_sha256="a"*64,revision_id="rev",
        page_id="7",physical_room_id="room",
    )


def _scope():
    owners=tuple(OriginalTwoSheetBoundaryOwner(
        f"physical-wall-{i}",(f"room-ink-{i}",),(f"finish-ink-{i}",),
        f"equivalence-{i}","source_closed_physical_wall_equivalence"
    ) for i in range(4))
    return OriginalPhysicalFloorToFinishScope(
        "room","floor","a"*64,"rev","snapshot","decision-scope",
        "7","11",tuple(f"room-ink-{i}" for i in range(4)),
        tuple(f"finish-ink-{i}" for i in range(4)),
        owners,((0,0),(10,0),(10,5),(0,5)),
    )


def _mark(id="plan-occurrence"):
    return AuthenticatedFloorFinishPlanMark(
        id,"definition","glyph-paint","clip","partition","FT3",
        "polished-floor",(3,1,4,2),"a"*64,"rev","11",
        "plan-viewport",True,
    )


def test_four_independently_equivalent_walls_bind_source_plan_mark_candidate():
    r=_room()
    c=resolve_source_physical_floor_correspondence_shadow(r,_scope())
    assert c.status is Status.CANDIDATE
    result=bind_source_finish_mark_to_corresponded_floor_shadow(r,c,(_mark(),))
    assert result.status is Status.CANDIDATE
    assert result.original_floor_id=="floor"
    assert result.original_occurrence_id=="plan-occurrence"
    assert result.candidate_area_m2==10.0
    assert result.diagnostic_only and not hasattr(result,"quantity_id")


def test_weak_wall_candidate_or_competing_floors_cannot_promote_finish():
    scope=_scope()
    weak=replace(scope.wall_owners[0],
                 original_structural_wall_authority="candidate_wall")
    result=resolve_source_physical_floor_correspondence_shadow(
        _room(),replace(scope,wall_owners=(weak,*scope.wall_owners[1:]))
    )
    assert result.status is Status.ABSTAINED
    assert result.wall_equivalence_receipts==()


def test_source_boundary_universe_must_be_exhaustive_before_binding():
    scope=_scope()
    result=resolve_source_physical_floor_correspondence_shadow(
        _room(),replace(scope,finish_support_source_ids=("finish-ink-0",))
    )
    assert result.status is Status.ABSTAINED


def test_plan_finish_mark_is_not_legend_schedule_or_nearest_label():
    room=_room();scope=_scope()
    corr=resolve_source_physical_floor_correspondence_shadow(room,scope)
    for other in (
        replace(_mark(),is_original_plan_occurrence=False),
        replace(_mark(),page_id="7"),
        replace(_mark(),source_plan_bbox_pts=(40,40,42,42)),
    ):
        result=bind_source_finish_mark_to_corresponded_floor_shadow(
            room,corr,(other,)
        )
        assert result.status is Status.ABSTAINED


def test_two_competing_source_plan_marks_must_abstain_not_select_ft3():
    room=_room();corr=resolve_source_physical_floor_correspondence_shadow(room,_scope())
    result=bind_source_finish_mark_to_corresponded_floor_shadow(
        room,corr,(_mark(),replace(_mark("other"),source_material_code="FT2"))
    )
    assert result.status is Status.ABSTAINED


def test_same_label_on_crosssheet_can_never_replace_original_structural_proof():
    scope=_scope()
    missing=replace(scope,wall_owners=scope.wall_owners[:-1])
    result=resolve_source_physical_floor_correspondence_shadow(_room(),missing)
    assert result.status is Status.ABSTAINED
