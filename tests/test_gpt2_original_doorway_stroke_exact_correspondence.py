"""Source-native wall ink pair census without asserting W4 or D15 threshold."""
from math import dist

import pytest

from tools.diag_gpt2_original_room_doorway_ancestry_shadow import (
    _independently_reissued_exact_native_stroke_pairs as audit,
)


BASE=(
    ((0.,0.),(0.,100.)),
    ((0.,100.),(100.,100.)),
    ((100.,100.),(100.,0.)),
    ((0.,0.),(40.,0.)),
    ((60.,0.),(100.,0.)),
)


def graph(parts, shift=0., *, extra=()):
    edges=[]
    for i,(a,b) in enumerate((*parts,*extra)):
        left=(a[0]+shift,a[1])
        right=(b[0]+shift,b[1])
        edges.append({
            "source_id":f"source-line-{i}",
            "endpoints_pdf_pts":(left,right),
            "source_ink_length_pdf_pt":dist(left,right),
        })
    return {"original_native_edges":tuple(edges)}


def test_five_exact_open_wall_source_strokes_survive_cross_page_registration():
    a=graph(BASE)
    b=graph(BASE,106.32)
    matches,rivals,complete=audit(a,b,translation=(106.32,0.))
    assert len(matches)==5
    assert rivals==()
    assert complete is True
    assert all(p["source_exact_native_stroke_geometry_only"] for p in matches)
    assert all(not p["physical_wall_face_issuer_granted"] for p in matches)


def test_realistic_shifted_D15_short_stub_preserves_four_uncontested_walls():
    a=graph(BASE)
    changed=list(BASE)
    changed[3]=((0.,0.),(40.24,0.))
    b=graph(changed,78.)
    matches,rivals,complete=audit(a,b,translation=(78.,0.))
    assert len(matches)==4
    assert rivals==()
    assert complete is True
    assert all(not row["physical_wall_face_issuer_granted"] for row in matches)
    assert all(row["original_floor_source_edge_id"]!="source-line-3"
               for row in matches)


def test_duplicate_original_source_ink_never_elects_a_one_to_one_wall():
    a=graph(BASE)
    b=graph(BASE,78.,extra=(BASE[0],))
    pairs,rivals,complete=audit(a,b,translation=(78.,0.))
    assert len(pairs)==4
    assert rivals==("source-line-0","source-line-5")
    assert complete is False


@pytest.mark.parametrize("bad",[
    None,
    {"original_native_edges":()},
    {"original_native_edges":(42,)},
    {"original_native_edges":(
        {"source_id":"a","endpoints_pdf_pts":((0.,0.),(True,1.)),
         "source_ink_length_pdf_pt":1.},
        {"source_id":"b","endpoints_pdf_pts":((0.,0.),(1.,1.)),
         "source_ink_length_pdf_pt":1.},
    )},
    {"original_native_edges":(
        {"source_id":"a","endpoints_pdf_pts":((0.,0.),(float("nan"),1.)),
         "source_ink_length_pdf_pt":1.},
        {"source_id":"b","endpoints_pdf_pts":((0.,0.),(1.,1.)),
         "source_ink_length_pdf_pt":1.},
    )},
])
def test_incomplete_native_wall_ink_census_cannot_emit_exact_source_pairs(bad):
    pairs,rivals,complete=audit(bad or {},graph(BASE),translation=(78.,0.))
    assert pairs==()
    assert complete is False
    assert rivals==("original_source_stroke_inventory_invalid",)
