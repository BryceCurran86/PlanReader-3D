"""Added VR wall creates related construction scopes, never silent MEP amounts."""
from __future__ import annotations
from dataclasses import replace
import math

import pytest

from pb_vr_wall_assembly_dependencies import (
    NewWallDesign, ProposedOpening, WallAssemblySpecification,
    WallServiceItem, KnownServiceRoute, calculate_new_wall_construction_package,
)


def _wall(**changes):
    record=dict(
        workspace_id="work-1",source_sha256="a"*64,
        snapshot_id="snapshot-1",base_model_revision=2,
        proposal_id="new-wall-1",level_id="ground",
        start_pt=(-1.0,0.0),end_pt=(3.0,0.0),height_m=2.7,
        openings=(),
    )
    record.update(changes)
    return NewWallDesign(**record)


def _spec(**changes):
    record=dict(
        specification_id="signed-project-wall-profile-v1",
        framing_system="70 mm steel framed wall",
        stud_spacing_m=0.6,plate_runs=2,noggin_rows=1,
        bracing_system="specified sheet bracing",bracing_area_m2=2.0,
        lining_system="13 mm plasterboard",lining_face_ids=("left","right"),
        skirting_system="90 mm MDF skirting",skirting_face_ids=("left","right"),
    )
    record.update(changes)
    return WallAssemblySpecification(**record)


def _one(lines,element):
    return [l for l in lines if l.element==element]


def test_added_wall_creates_all_named_dependencies_and_unresolved_mep_holds():
    wall=_wall()
    result=calculate_new_wall_construction_package(wall,_spec())
    assert result.can_publish_commercial is False
    assert result.original_source_modified is False
    assert result.wall_length_m==4.0
    assert _one(result.quantities,"Wall framing plates")[0].value==8.0
    assert _one(result.quantities,"Preliminary wall stud count")[0].value==8.0
    assert _one(result.quantities,"Preliminary full-height stud stock")[0].value==21.6
    assert _one(result.quantities,"Noggin stock, preliminary")[0].value==4.0
    assert _one(result.quantities,"Specified wall bracing coverage")[0].value==2.0
    assert sorted(l.value for l in _one(result.quantities,"Wall plasterboard lining"))==[10.8,10.8]
    assert sorted(l.value for l in _one(result.quantities,"Wall skirting boards"))==[4,4]
    assert "electrical_new_wall_services_to_be_reviewed" in result.coordination_required
    assert "plumbing_new_wall_services_to_be_reviewed" in result.coordination_required
    assert all(q.status=="review_only" for q in result.quantities)
    assert len({q.line_id for q in result.quantities})==len(result.quantities)
    assert result==calculate_new_wall_construction_package(wall,_spec())


def test_adding_door_deducts_both_plasterboard_faces_and_only_floor_skirting():
    wall=_wall(openings=(
        ProposedOpening("door-1",offset_m=1.0,width_m=0.9,
                        height_m=2.1,sill_height_m=0,
                        opening_kind="door"),
        ProposedOpening("window-1",offset_m=2.0,width_m=0.6,
                        height_m=1.0,sill_height_m=1,
                        opening_kind="window"),
    ))
    result=calculate_new_wall_construction_package(wall,_spec())
    net=4*2.7-0.9*2.1-0.6*1
    assert sorted(q.value for q in _one(result.quantities,"Wall plasterboard lining"))==[
        round(net,6),round(net,6)
    ]
    assert sorted(q.value for q in _one(result.quantities,"Wall skirting boards"))==[3.1,3.1]
    assert "opening_jamb_lintel_and_stud_reinforcement_not_designed" in result.coordination_required
    assert "door_window_frame_and_trim_details_require_coordinated_schedule" in result.coordination_required


def test_electrical_and_plumbing_scope_only_from_explicit_fixture_or_route():
    spec=_spec(services=(
        WallServiceItem("socket-2","electrical","Twin GPO",2,"No.",
                        "elec-schedule-12",True),
        WallServiceItem("switch-3","electrical","Light switch",1,"No.",
                        "elec-schedule-22",True),
        WallServiceItem("basin-1","plumbing","Basin cold water branch",1.6,"lm",
                        "hydraulic-plan-3",True),
    ))
    crossing=(
        KnownServiceRoute("wire-4","electrical","ground",
                          (1.,-2.),(1.,2.),True),
        KnownServiceRoute("pipe-9","plumbing","ground",
                          (2.,-2.),(2.,2.),True),
    )
    out=calculate_new_wall_construction_package(_wall(),spec,
                                                known_service_routes=crossing)
    assert sorted(q.value for q in out.quantities if q.trade=="electrical")==[1,2]
    assert [q.value for q in out.quantities if q.trade=="plumbing"]==[1.6]
    assert "electrical_new_wall_services_to_be_reviewed" not in out.coordination_required
    assert "plumbing_new_wall_services_to_be_reviewed" not in out.coordination_required
    assert "electrical_route_conflict_wire-4_requires_redesign" in out.coordination_required
    assert "plumbing_route_conflict_pipe-9_requires_redesign" in out.coordination_required
    assert all("route" not in q.element.lower() for q in out.quantities)


def test_new_wall_replaces_dependent_quantities_without_duplicate_billings():
    original=calculate_new_wall_construction_package(_wall(),_spec())
    changed=calculate_new_wall_construction_package(
        _wall(end_pt=(4.,0.)),_spec())
    q1={q.line_id:q for q in original.quantities}
    q2={q.line_id:q for q in changed.quantities}
    assert q1.keys()==q2.keys()
    assert q1!=q2
    assert _one(changed.quantities,"Wall skirting boards")[0].value==5.0
    assert changed.revision_scope_key==original.revision_scope_key
    other_version=calculate_new_wall_construction_package(
        _wall(base_model_revision=3),_spec())
    assert other_version.revision_scope_key!=original.revision_scope_key


def test_no_default_assumptions_but_complete_explicit_to_do_register():
    no_specs=WallAssemblySpecification("project-assembly-unassigned")
    r=calculate_new_wall_construction_package(_wall(),no_specs)
    assert r.quantities==()
    assert set(r.coordination_required)>={
        "wall_framing_design_required",
        "structural_bracing_design_required",
        "plasterboard_lining_schedule_required",
        "skirting_face_or_finish_schedule_required",
        "electrical_new_wall_services_to_be_reviewed",
        "plumbing_new_wall_services_to_be_reviewed",
    }


def test_rejects_overlapping_doorways_bad_wall_geometry_and_invented_fittings():
    bad_door=ProposedOpening("D",0.2,0.9,2.1,0,"door")
    for opening in (
        ProposedOpening("D2",0.7,0.9,2.1,0,"door"),
        ProposedOpening("D",0.2,0.9,2.1,0,"door"),
    ):
        with pytest.raises(ValueError):
            _wall(openings=(bad_door,opening))
    with pytest.raises(ValueError):
        _wall(start_pt=(0.,0.),end_pt=(0.,0.))
    with pytest.raises(ValueError):
        _wall(height_m=math.nan)
    with pytest.raises(ValueError):
        _wall(source_sha256="untrusted")
    with pytest.raises(ValueError):
        _spec(stud_spacing_m=0)
    with pytest.raises(ValueError):
        _spec(lining_face_ids=("left","left"))
    with pytest.raises(ValueError):
        WallServiceItem("fake","electrical","Outlet",0.5,"No.","plan-2",True)
    with pytest.raises(ValueError):
        calculate_new_wall_construction_package(
            _wall(),_spec(services=(
                WallServiceItem("unhosted","electrical","Outlet",1,"No.","p1",False),
            ))
        )


def test_wall_cannot_invent_structural_bracing_or_count_unverified_route_as_rework():
    wall=_wall()
    without=_spec(bracing_system=None,bracing_area_m2=None)
    out=calculate_new_wall_construction_package(wall,without,
        known_service_routes=(KnownServiceRoute(
            "unproven-1","plumbing","ground",
            (1.,-1.),(1.,1.),False
        ),))
    assert not _one(out.quantities,"Specified wall bracing coverage")
    assert "structural_bracing_design_required" in out.coordination_required
    assert "plumbing_unverified_route_unproven-1" in out.coordination_required
    assert not [q for q in out.quantities if q.trade=="plumbing"]
    with pytest.raises(ValueError):
        calculate_new_wall_construction_package(wall,_spec(bracing_area_m2=100))
