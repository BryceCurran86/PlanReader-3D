"""A source text hit never substitutes for actual physical room authority."""
from types import SimpleNamespace as NS
from tools.diag_gpt2_native_room_viewport_candidates import classify_native_label_viewport as classify

def vp(vtype="floor_plan",bbox=(0.,0.,100.,100.),status="resolved",id="physical-view-1"):
    return NS(view_type=vtype,bounding_box=bbox,status=status,view_id=id)

def test_unique_bounded_native_floorplan_hit_is_still_only_candidate():
    row=classify((10.,10.,20.,20.),(vp(),))
    assert row["first_gate"]=="floor_plan_viewport_candidate_only"
    assert row["candidate_viewport_ids"]==["physical-view-1"]
    assert row["physical_room_proven"] is False
    assert row["metric_area_proven"] is False

def test_centerpoint_without_full_bbox_containment_cannot_grant_view_owner():
    row=classify((90.,20.,110.,30.),(vp(),))
    assert row["first_gate"]=="native_label_outside_authenticated_source_viewports"

def test_native_title_schedule_rcp_cannot_mint_floor_room():
    for vtype in ("reflected_ceiling_plan","schedule","legend","detail"):
        row=classify((10.,10.,20.,20.),(vp(vtype=vtype),))
        assert row["first_gate"]=="native_label_in_nonfloor_viewport_only"
        assert row["physical_room_proven"] is False

def test_competing_owners_abstain_even_if_floorplan_present():
    row=classify((10.,10.,20.,20.),(
        vp(id="floor-1"),vp(vtype="schedule",id="schedule-1")
    ))
    assert row["first_gate"]=="competing_source_viewport_owners"

def test_unbounded_plan_title_is_no_floorplan_owner():
    row=classify((10.,10.,20.,20.),(
        vp(status="ambiguous",bbox=None,id="ambiguous-1"),
    ))
    assert row["first_gate"]=="source_floor_plan_viewport_boundary_unresolved"

def test_unbounded_floor_does_not_hide_an_independent_resolved_owner():
    row=classify((10.,10.,20.,20.),(
        vp(status="unsupported",bbox=None,id="other"),
        vp(id="owned"),
    ))
    assert row["first_gate"]=="floor_plan_viewport_candidate_only"

def test_malformed_native_text_bbox_abstains_not_crashes():
    for bbox in (None,(),(0,0,0,1),(0,0,1),("bad",0,1,2),(float("nan"),0,1,1)):
        row=classify(bbox,(vp(),))
        assert row["first_gate"]=="malformed_source_native_label_bbox"
        assert row["physical_room_proven"] is False
