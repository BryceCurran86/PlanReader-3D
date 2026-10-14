"""Exact-source only native parallel companion geometry remains non-authoritative."""
from types import SimpleNamespace
import pytest

from tools.diag_gpt2_native_parallel_wall_band_candidates import (
    _parallel_overlap,candidate_parallel_native_strokes,
)

def point(x,y):
    return SimpleNamespace(x=x,y=y)

def draw(a,b,color=(0,0,0)):
    return {"type":"s","color":color,"width":0.24,
        "dashes":"[] 0","layer":"","seqno":8,
        "items":[("l",point(*a),point(*b))]}

ATOM=((2.,0.),(8.,0.))

def test_independently_sourced_opposite_parallel_ink_is_only_a_candidate():
    d=[
        draw((0.,0.),(10.,0.)),
        draw((10.,2.),(0.,2.)),
        draw((0.,4.),(10.,4.)),
        draw((0.,0.),(10.,0.)),
    ]
    report=candidate_parallel_native_strokes(d,"d0i0",ATOM)
    assert report["source_parallel_candidate_count"]==2
    assert [v["native_source_primitive_id"] for v in
            report["source_parallel_candidate_first_receipts"]]==["d1i0","d2i0"]
    assert report["source_parallel_candidate_first_receipts"][0][
        "original_atom_fully_parallel_covered"
    ]
    assert report["selected_physical_wall_band_companion"] is None
    assert report["source_wall_role_authenticated"] is False
    assert report["metric_room_area_published"] is False
    assert report["benchmark_accuracy_granted"] is False

def test_source_universe_permutation_keeps_geometric_counts_without_promotion():
    d=[
        draw((0.,0.),(10.,0.)),
        draw((0.,2.),(10.,2.)),
        draw((0.,4.),(10.,4.)),
    ]
    a=candidate_parallel_native_strokes(d,"d0i0",ATOM)
    b=candidate_parallel_native_strokes([d[0],d[2],d[1]],"d0i0",ATOM)
    assert a["source_parallel_candidate_count"]==b["source_parallel_candidate_count"]
    assert [x["source_positive_parallel_abs_offset_pdf_pts"]
            for x in a["source_parallel_candidate_first_receipts"]]==[
                x["source_positive_parallel_abs_offset_pdf_pts"]
                for x in b["source_parallel_candidate_first_receipts"]
            ]
    assert not a["source_wall_role_authenticated"]
    assert not b["source_wall_role_authenticated"]

@pytest.mark.parametrize("edge",[
    ((3.,2.),(3.,8.)),
    ((3.,2.),(9.,3.)),
    ((0.,2.),(2.,2.)),
    ((2.,0.),(8.,0.)),
])
def test_perpendicular_diagonal_nonoverlapping_collinear_lines_not_wall_band(edge):
    assert _parallel_overlap(ATOM,edge) is None

def test_partial_parallel_source_is_not_full_companion():
    r=_parallel_overlap(ATOM,((5.,2.),(7.,2.)))
    assert r is not None
    assert not r["original_atom_fully_parallel_covered"]
    assert r["overlap_with_original_wall_atom_pdf_pts"]==2.

@pytest.mark.parametrize("bad",[
    ((0.,0.),(0.,0.)),
    ((float("nan"),0.),(4.,1.)),
    ((float("inf"),0.),(4.,1.)),
])
def test_invalid_source_atom_geometry_fails_closed(bad):
    with pytest.raises(ValueError):
        candidate_parallel_native_strokes([draw((0,0),(10,0))],"d0i0",bad)

def test_missing_original_path_fails_closed():
    with pytest.raises(ValueError):
        candidate_parallel_native_strokes([draw((0,0),(10,0))],"d1i0",ATOM)

def test_partial_source_seed_fails_closed():
    with pytest.raises(ValueError):
        candidate_parallel_native_strokes([draw((0,0),(10,0))],"d0i0",((2.,1.),(8.,1.)))

def test_bounded_report_prevents_unbounded_original_stroke_dump():
    with pytest.raises(ValueError):
        candidate_parallel_native_strokes([draw((0,0),(10,0))],"d0i0",ATOM,output_limit=100000)
