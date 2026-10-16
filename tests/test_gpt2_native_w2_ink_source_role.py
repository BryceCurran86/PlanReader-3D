"""Fail-closed native W2 source ink identity tests (no physical-wall promotion)."""
from types import SimpleNamespace
import pytest

from tools.diag_gpt2_native_w2_ink_source_role import (
    decode_primitive_id, read_native_ink_receipt,
)

def point(x,y):
    return SimpleNamespace(x=x,y=y)

def draws():
    return [{
        "type":"s",
        "seqno":17,
        "width":0.25,
        "dashes":"[] 0",
        "layer":"CAD",
        "color":(0,0,0),
        "fill":None,
        "items":[("l",point(0,0),point(10,0))],
    }]

def test_exact_pdf_source_primitive_owns_candidate_source_line_not_wall_role():
    r=read_native_ink_receipt(draws(),"d0i0",((2,0),(8,0)))
    assert r["native_stroke_fully_covers_atomic_wall_candidate"]
    assert r["original_path_index"]==0 and r["original_item_index"]==0
    assert r["native_stroke_contains_candidate_only_not_wall_role"]
    assert not r["structural_wall_role_authenticated"]
    assert not r["source_room_face_closed_by_tool"]
    assert not r["quantity_or_metric_area_published"]
    assert r["original_native_paint_metadata_candidate_only"]["native_stroke_color"]==[0,0,0]

@pytest.mark.parametrize("atom",[
    ((2,1),(8,1)),((2,0),(12,0)),((-2,0),(8,0)),((10,0),(12,0)),
])
def test_different_or_only_partly_overlapping_stroke_cannot_prove_source_ancestry(atom):
    r=read_native_ink_receipt(draws(),"d0i0",atom)
    assert not r["native_stroke_fully_covers_atomic_wall_candidate"]
    assert not r["structural_wall_role_authenticated"]

@pytest.mark.parametrize("key",["x0i0","d-1i0","d0i-1","d0i0e3"," d0i0","d0i0 ","d0i0e5","","d0i0;delete"])
def test_foreign_or_invalid_pdf_primitive_reference_rejected(key):
    if key=="d0i0e3":
        with pytest.raises(ValueError):
            read_native_ink_receipt(draws(),key,((2,0),(8,0)))
    else:
        with pytest.raises(ValueError):
            decode_primitive_id(key)

def test_missing_path_or_native_item_fails_closed():
    for key in ("d1i0","d0i1"):
        with pytest.raises(ValueError):
            read_native_ink_receipt(draws(),key,((2,0),(8,0)))

def test_zero_or_nonfinite_native_edge_rejected():
    for e in [((2,0),(2,0)),((0,0),(float("nan"),0)),((0,0),(float("inf"),0))]:
        with pytest.raises(ValueError):
            read_native_ink_receipt(draws(),"d0i0",e)
