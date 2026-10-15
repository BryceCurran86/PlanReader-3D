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
