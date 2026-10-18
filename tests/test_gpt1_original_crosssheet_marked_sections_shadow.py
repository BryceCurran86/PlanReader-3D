"""An original FT plan can mark material subzones of ONE physical room."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide,measure_figured_room_edge_chain_shadow
from pb_gpt1_figured_metric_plane_shadow import (
    OriginalInternalSourceSection,resolve_source_figured_metric_plane_shadow,
)
from pb_gpt1_original_two_view_wall_frame_shadow import SourceWallRingFrameShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,AuthenticatedFloorFinishPlanMark,
)
from pb_gpt1_original_crosssheet_marked_sections_shadow import (
    measure_original_crosssheet_marked_sections_shadow,
)

SHA="a"*64

def _parent():
    corners=((0,0),(10,0),(10,5),(0,5))
    sides=tuple(FiguredPhysicalSide(
        f"side-{i}",corners[i],corners[(i+1)%4],
        (f"ink-{i}",),{0:5000,1:2000}.get(i),
        f"figure-{i}" if i in (0,1) else None,
        (f"witness-{i}-a",f"witness-{i}-b") if i in (0,1) else (),
    ) for i in range(4))
    parent=measure_figured_room_edge_chain_shadow(
        sides,source_sha256=SHA,revision_id="rev",page_id="7",
        physical_room_id="one-room",
    )
    return parent,resolve_source_figured_metric_plane_shadow(parent)


def _sections():
    return (
        OriginalInternalSourceSection(
            "food-service",("part-wall-a","part-wall-b"),
            ((0,0),(5,0),(5,5),(0,5)),("food-service-source",)
        ),
        OriginalInternalSourceSection(
            "pos-counter",("part-wall-c","part-wall-d"),
            ((5,0),(10,0),(10,5),(5,5)),("pos-source",)
        ),
    )


def _frame():
    return SourceWallRingFrameShadow(
        Status.CANDIDATE,("original-source",),(1.,0.,-78.,0.),0.,
        ("wall-1","wall-2","wall-3","wall-4"),("source-wall-equivalence",),
    )


def _physical_floor():
    return PhysicalFloorFinishCorrespondenceShadow(
        Status.CANDIDATE,("crosssheet-source-closed",),"one-room",
        "physical-floor",("source-wall-equivalence",),
        ((0,0),(10,0),(10,5),(0,5)),"11",SHA,"rev",
        "snapshot","decision-scope",True,"source-face","7",
    )


def _mark(name,code,bbox):
    return AuthenticatedFloorFinishPlanMark(
        name,f"definition-{code}",f"paint-{name}",f"clip-{name}",
        "native-partition",code,"floor-finish",bbox,
        SHA,"rev","11","plan-view",True,
    )


def test_two_distinct_original_plan_marks_measure_one_room_without_false_rooms():
    parent,plane=_parent()
    result=measure_original_crosssheet_marked_sections_shadow(
        parent,plane,_sections(),_frame(),_physical_floor(),
        (_mark("ft3","FT3",(80,1,81,2)),
         _mark("ft2","FT2",(85,1,86,2)))
    )
    assert result.status is Status.CANDIDATE
    assert result.measured_material_totals_m2==(("FT2",5.),("FT3",5.))
    assert result.unallocated_parent_area_m2==0
    assert result.diagnostic_only


def test_missing_original_finish_mark_never_assumes_the_other_material():
    parent,plane=_parent()
    result=measure_original_crosssheet_marked_sections_shadow(
        parent,plane,_sections(),_frame(),_physical_floor(),
        (_mark("ft3","FT3",(80,1,81,2)),)
    )
    assert result.status is Status.ABSTAINED
    assert result.measured_material_totals_m2==()


def test_rival_crosssheet_registration_cannot_move_mark_to_closer_room():
    parent,plane=_parent()
    fake=replace(_frame(),original_finish_to_room_rigid_transform=(1,0,-43.92,0))
    result=measure_original_crosssheet_marked_sections_shadow(
        parent,plane,_sections(),fake,_physical_floor(),
        (_mark("ft3","FT3",(80,1,81,2)),_mark("ft2","FT2",(85,1,86,2)))
    )
    assert result.status is Status.ABSTAINED


def test_two_finish_marks_for_same_section_prove_ambiguity():
    parent,plane=_parent()
    result=measure_original_crosssheet_marked_sections_shadow(
        parent,plane,_sections(),_frame(),_physical_floor(),
        (_mark("first","FT3",(80,1,81,2)),
         _mark("second","FT2",(81,3,82,4)),
         _mark("third","FT2",(85,1,86,2)))
    )
    assert result.status is Status.ABSTAINED
