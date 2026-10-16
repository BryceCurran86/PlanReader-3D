"""W4 source-side ancestry is read-only: no geometry alignment is wall truth."""
from copy import deepcopy

import pytest

from tools.diag_gpt2_ft3_cross_sheet_native_wall_pairs import (
    compare_indexed_original_side,
    source_fragments_on_documented_side,
)

BOX=(10.,10.,30.,30.)


def seg(x1,y1,x2,y2):
    return dict(x1=x1,y1=y1,x2=x2,y2=y2)


def test_source_native_side_original_ids_and_reverse_direction_stable():
    originals={
        "native-A":seg(10,10,10,20),
        "native-B":seg(10,30,10,20),
        "native-foreign":seg(11,10,11,30),
        "native-parallel-grid":seg(30,10,30,30),
    }
    before=deepcopy(originals)
    got=source_fragments_on_documented_side(
        BOX,"x0",originals,{"native-A":["w1"],"native-B":["w1"]},{"w1":False}
    )
    assert [r["native_primitive_id"] for r in got]==["native-A","native-B"]
    assert [r["source_clipped_interval_pdf_pts"] for r in got]==[
        [10.,20.],[20.,30.],
    ]
    assert originals==before
    assert all(not r["source_physical_wall_role_granted"] for r in got)


def test_complete_geometry_even_exact_identical_native_wall_does_not_seal_identity():
    original=source_fragments_on_documented_side(
        BOX,"x0",{"p11a":seg(10,10,10,20),"p11b":seg(10,20,10,30)},
        {"p11a":["owner11"],"p11b":["owner11"]},{"owner11":False}
    )
    mapped=source_fragments_on_documented_side(
        (4.,10.,24.,30.),"x0",
        {"p7":seg(4,10,4,30)},{"p7":["owner7"]},{"owner7":False}
    )
    receipt=compare_indexed_original_side(
        original,mapped,shift_along_side=0
    )
    assert receipt["source_native_ink_interval_iou"]==1
    assert len(receipt["all_original_native_ink_overlap_pairs"])==2
    assert "cross_page_physical_structural_wall_equivalence_unproven" in receipt[
        "source_role_first_failure_reasons"
    ]
    assert not receipt["physical_wall_or_room_equivalence_granted"]
    assert not receipt["new_metric_or_material_quantity"]


def test_unowned_duplicate_and_grid_opposed_sources_remain_negative():
    a=source_fragments_on_documented_side(
        BOX,"y0",
        {"x":seg(10,10,30,10),"unowned":seg(12,10,15,10)},
        {"x":["wall-one","wall-other"]},
        {"wall-one":True,"wall-other":False},
    )
    b=source_fragments_on_documented_side(
        BOX,"y0",{"y":seg(10,10,30,10)},{"y":["wall7"]},{"wall7":False}
    )
    report=compare_indexed_original_side(a,b,shift_along_side=0)
    assert report["native_unowned_ids"]["support"]==["unowned"]
    assert report["native_multiowner_ids"]["support"]==["x"]
    assert report["typed_grid_opposed_ids"]["support"]==["x"]
    assert "indexed_original_source_unowned_by_w4" in report["source_role_first_failure_reasons"]
    assert "indexed_original_source_multiowned_by_w4" in report["source_role_first_failure_reasons"]
    assert "typed_grid_opposition_present" in report["source_role_first_failure_reasons"]
    assert not report["physical_wall_or_room_equivalence_granted"]


def test_structural_native_ink_gap_preserved_without_replacement():
    a=source_fragments_on_documented_side(
        BOX,"y0",{"one":seg(10,10,20,10)},{"one":["p11"]},{"p11":False}
    )
    b=source_fragments_on_documented_side(
        BOX,"y0",{"different":seg(25,10,30,10)},
        {"different":["p7"]},{"p7":False}
    )
    report=compare_indexed_original_side(a,b,shift_along_side=0)
    assert report["all_original_native_ink_overlap_pairs"]==[]
    assert report["source_native_ink_interval_iou"]==0
    assert "no_exact_original_native_overlap_after_registration" in report[
        "source_role_first_failure_reasons"
    ]


@pytest.mark.parametrize("broken",[
    (10,10,10,10),(30,10,10,30),(10,float("nan"),30,30),
])
def test_invalid_figured_box_cannot_claim_source_wall(broken):
    with pytest.raises(ValueError,match="unresolved native figured box"):
        source_fragments_on_documented_side(broken,"x0",{}, {}, {})


def test_foreign_side_and_nonfinite_registration_fail_closed():
    with pytest.raises(ValueError,match="unknown figured side"):
        source_fragments_on_documented_side(BOX,"fake",{}, {}, {})
    with pytest.raises(ValueError,match="non-finite source registration"):
        compare_indexed_original_side([],[],shift_along_side=float("inf"))



def test_source_index_duplicate_ids_and_missing_source_addresses_abstain():
    from tools.diag_gpt2_ft3_cross_sheet_native_wall_pairs import (
        indexed_original_native_primitives,
    )
    one={"id":"d10i1", **seg(0,0,10,0)}
    two={"id":"d20i1", **seg(0,5,10,5)}
    assert sorted(indexed_original_native_primitives([two,one]))==["d10i1","d20i1"]
    with pytest.raises(ValueError,match="duplicate original"):
        indexed_original_native_primitives([one,{**one,"x2":42}])
    with pytest.raises(ValueError,match="duplicate original"):
        indexed_original_native_primitives([one,one])
    with pytest.raises(ValueError,match="missing or duplicate"):
        indexed_original_native_primitives([{"id":None,**seg(0,0,10,0)}])


# Full competing-registration audit; these are NOT physical wall identity.
from tools.diag_gpt2_ft3_cross_sheet_native_wall_pairs import (
    ranked_original_registrations,
    registration_side_geometry,
    compare_side_under_affine,
    audit_registration_candidate_sides,
)

def _hypothesis(orientation="identity", scale=1.0, dx=-6.0, dy=0.0):
    return dict(orientation=orientation, scale=scale, dx=dx, dy=dy,
                min_support_pt=100.0)


def _rows(box, *, owner="wall", grid=False):
    x0,y0,x1,y1=box
    original={
        "top":dict(id="top", **seg(x0,y0,x1,y0)),
        "bottom":dict(id="bottom", **seg(x0,y1,x1,y1)),
        "left":dict(id="left", **seg(x0,y0,x0,y1)),
        "right":dict(id="right", **seg(x1,y0,x1,y1)),
    }
    return original, {k:[owner] for k in original}, {owner:grid}


def test_ranked_source_competitors_are_all_retained_input_order_stable():
    rows=[
        {**_hypothesis(dx=-6), "next_distinct_translation":[-2,0],
         "next_distinct_min_support_pt":22.0},
        {**_hypothesis(orientation="mirror_y",dx=7), "min_support_pt":85.0,
         "next_distinct_translation":None},
    ]
    before=deepcopy(rows)
    a=ranked_original_registrations(rows)
    b=ranked_original_registrations(list(reversed(rows)))
    assert a==b and rows==before
    assert len(a)==3
    assert {(r["orientation"],r["dx"],r["dy"]) for r in a} == {
        ("identity",-6.0,0.0),("identity",-2.0,0.0),("mirror_y",7.0,0.0)
    }
    assert all(r["candidate_not_authenticated_registration"] for r in a)


@pytest.mark.parametrize("broken",[
    {"orientation":"unknown","scale":1,"dx":0,"dy":0,"min_support_pt":1},
    {"orientation":"identity","scale":0,"dx":0,"dy":0,"min_support_pt":1},
    {"orientation":"identity","scale":1,"dx":float("inf"),"dy":0,"min_support_pt":1},
    {"orientation":"identity","scale":1,"dx":0,"dy":0,"min_support_pt":float("nan")},
    {**_hypothesis(),"next_distinct_translation":[1.0],
     "next_distinct_min_support_pt":2},
    {**_hypothesis(),"next_distinct_translation":[0.0,float("inf")],
     "next_distinct_min_support_pt":2},
    {**_hypothesis(),"next_distinct_translation":[2.0,0.0],
     "next_distinct_min_support_pt":float("nan")},
])
def test_competing_source_registration_rejects_malformed_candidates(broken):
    with pytest.raises(ValueError,match="registration"):
        ranked_original_registrations([broken])


def test_ranked_candidate_universe_never_silently_truncated():
    many=[{**_hypothesis(dx=i), "min_support_pt":float(i)}
          for i in range(129)]
    with pytest.raises(ValueError,match="over safety bound"):
        ranked_original_registrations(many)


@pytest.mark.parametrize("orientation",[
    "identity","rot90","rot180","rot270",
    "mirror_x","mirror_y","transpose","anti_transpose",
])
@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0])
def test_all_d4_orientations_exactly_map_four_original_sides(orientation,scale):
    from tools.diag_ft3_p11_p7_floor_correspondence import D4
    box=(10.,20.,34.,50.)
    a,b,c,d=D4[orientation]
    def move(s):
        x,y=s
        return (scale*(a*x+b*y)+7.,scale*(c*x+d*y)-4.)
    corners=[move(p) for p in ((10,20),(10,50),(34,20),(34,50))]
    expected=(min(p[0] for p in corners),min(p[1] for p in corners),
              max(p[0] for p in corners),max(p[1] for p in corners))
    seen=set()
    for side in ("x0","x1","y0","y1"):
        tb, name,slope,offset=registration_side_geometry(
            box,side,_hypothesis(orientation=orientation,scale=scale,dx=7,dy=-4)
        )
        assert tb==pytest.approx(expected,abs=1e-9)
        assert abs(slope)==pytest.approx(scale)
        assert name not in seen
        seen.add(name)
    assert seen=={"x0","x1","y0","y1"}


@pytest.mark.parametrize("orientation",[
    "identity","rot90","rot180","rot270",
    "mirror_x","mirror_y","transpose","anti_transpose",
])
def test_all_rotated_original_native_sides_compare_without_loss(orientation):
    box=(10.,20.,34.,50.)
    candidate=_hypothesis(orientation=orientation,scale=1.0,dx=-6.0,dy=9.0)
    from tools.diag_ft3_p11_p7_floor_correspondence import D4
    a,b,c,d=D4[orientation]
    def move(p):
        x,y=p
        return (a*x+b*y-6,c*x+d*y+9)
    originals,owners,grid=_rows(box)
    target={}
    for name,s in originals.items():
        p=move((s["x1"],s["y1"]))
        q=move((s["x2"],s["y2"]))
        target[name]={"id":name,**seg(*p,*q)}
    before=deepcopy((originals,target,owners,grid))
    report=audit_registration_candidate_sides(
        box,candidate,
        native_support=originals,native_target=target,
        owners_support=owners,owners_target=owners,
        grid_support=grid,grid_target=grid,
    )
    assert (originals,target,owners,grid)==before
    sides=report["source_original_wall_side_provenance"]
    assert len(sides)==4
    assert all(g["source_native_ink_interval_iou"]==pytest.approx(1.0)
               for g in sides.values())
    assert all(len(g["all_original_native_ink_overlap_pairs"])==1
               for g in sides.values())
    assert all(not g["physical_wall_or_room_equivalence_granted"]
               for g in sides.values())
    assert not report["candidate_physical_registration_elected"]
    assert not report["cross_page_physical_room_equivalence_granted"]


def test_split_segments_and_reverse_direction_retain_all_native_lineage():
    box=(10.,20.,34.,50.)
    original,owners,grid=_rows(box)
    del original["left"]
    original.update({
        "a":dict(id="a",**seg(10,20,10,30)),
        "b":dict(id="b",**seg(10,50,10,30)),
    })
    owners["a"]=["wa"];owners["b"]=["wb"]
    target,target_owners,target_grid=_rows((4.,20.,28.,50.))
    report=audit_registration_candidate_sides(
        box,_hypothesis(),
        native_support=original,native_target=target,
        owners_support=owners,owners_target=target_owners,
        grid_support=grid,grid_target=target_grid,
    )
    lhs=report["source_original_wall_side_provenance"]["x0"]
    assert lhs["source_native_ink_interval_iou"]==1
    assert len(lhs["all_original_native_ink_overlap_pairs"])==2
    assert {r["native_primitive_id"] for r in lhs["original_support_native_fragments"]}=={"a","b"}
    assert "cross_page_physical_structural_wall_equivalence_unproven" in lhs[
        "source_role_first_failure_reasons"
    ]


def test_grid_opponents_and_multiple_wall_owners_never_elect_registration():
    box=(10.,20.,34.,50.)
    support,owners,grid=_rows(box,owner="w1",grid=True)
    owners["top"]=["w1","w2"]
    target,target_owners,target_grid=_rows((4.,20.,28.,50.))
    receipt=audit_registration_candidate_sides(
        box,_hypothesis(),
        native_support=support,native_target=target,
        owners_support=owners,owners_target=target_owners,
        grid_support=grid,grid_target=target_grid,
    )
    top=receipt["source_original_wall_side_provenance"]["y0"]
    assert top["native_multiowner_ids"]["support"]==["top"]
    assert top["typed_grid_opposed_ids"]["support"]==["top"]
    assert not receipt["candidate_physical_registration_elected"]


def test_reverse_affine_overlap_and_out_of_span_strictness():
    support=[{"native_primitive_id":"p11","source_clipped_interval_pdf_pts":[10.,30.],
              "source_w4_candidate_count":1,"typed_grid_opposed_owner_ids":[]}]
    target=[{"native_primitive_id":"p7","source_clipped_interval_pdf_pts":[-20.,0.],
             "source_w4_candidate_count":1,"typed_grid_opposed_owner_ids":[]}]
    out=compare_side_under_affine(support,target,slope=-1,offset=10)
    assert out["source_native_ink_interval_iou"]==1
    assert out["all_original_native_ink_overlap_pairs"][0][
        "exact_intersection_in_support_pdf_pts"]==[10.,30.]
    assert not out["physical_wall_or_room_equivalence_granted"]
    with pytest.raises(ValueError,match="noninvertible"):
        compare_side_under_affine(support,target,slope=0,offset=1)
    with pytest.raises(ValueError,match="noninvertible"):
        compare_side_under_affine(support,target,slope=float("nan"),offset=1)
