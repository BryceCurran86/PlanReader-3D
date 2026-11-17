"""Native VSD robe/linen source frames: two leaves, two caps, two hosts.

The original laundry/linen upper black host is two contiguous source segments.
No unpainted gap may be joined and a VSD label alone cannot create an opening.
"""
from copy import deepcopy

import fitz

from pb_source_native_vsd_joinery_shadow import match_source_native_vsd_joinery
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
import hashlib


def _scene():
    fill=lambda b,c: {
        "layer":"Enclosure_WallInternal", "type":"f",
        "fill":(c,)*3, "rect":fitz.Rect(*b),
    }
    line=lambda p,q: {
        "layer":"Enclosure_WallInternal", "type":"s",
        "fill":None,"color":(0,0,0),
        "items":(("l",fitz.Point(*p),fitz.Point(*q)),),
    }
    return [
        fill((100,9.75,102.3,10),0),
        fill((100,7,102.3,9.75),0),
        fill((100,44,102.3,47),0),
        fill((99.8,10,102.7,11),1),
        fill((99.8,43,102.7,44),1),
        line((100,11),(100,27.5)),
        line((102.3,26.5),(102.3,43)),
    ],[
        (101,20,111,28,"1,200",0,0,0),
        (105,30,113,38,"VSD",0,0,1),
    ]


def test_real_multi_piece_black_wall_end_is_source_host_not_virtual_wall():
    d,w=_scene()
    result=match_source_native_vsd_joinery(d,w,page_index=2)
    assert len(result)==1
    r=result[0]
    assert r.vsd_word_index==1
    assert r.width_word_index==0 and r.printed_width_mm==1200
    assert r.wall_host_path_ids==(0,1,2)
    assert r.jamb_cap_path_ids==(3,4)
    assert r.sliding_leaf_path_ids==(5,6)
    assert r.clear_interval_pdf_pts==(10,44)
    assert r.horizontal is False
    assert not r.customer_quantity_authorized
    assert not r.physical_opening_authenticated


def test_label_only_or_missing_any_painted_frame_witness_abstains():
    d,w=_scene()
    assert match_source_native_vsd_joinery([],w,page_index=2)==()
    for removed in range(len(d)):
        subset=deepcopy(d)
        subset.pop(removed)
        assert match_source_native_vsd_joinery(subset,w,page_index=2)==()


def test_physical_short_host_without_touched_extension_must_not_be_inferred():
    d,w=_scene()
    d[1]["rect"]=fitz.Rect(100,5,102.3,9.5)
    assert match_source_native_vsd_joinery(d,w,page_index=2)==()


def test_vsd_requires_original_width_and_a_unique_leaf_pair():
    d,w=_scene()
    assert match_source_native_vsd_joinery(d,w[:1],page_index=2)==()
    d,w=_scene()
    w[0]=(101,20,111,28,"870",0,0,0)
    assert match_source_native_vsd_joinery(d,w,page_index=2)==()
    d,w=_scene()
    d.append(deepcopy(d[5]))
    assert match_source_native_vsd_joinery(d,w,page_index=2)==()
    d,w=_scene()
    d[6]["layer"]="Annotation_FloorPlan"
    assert match_source_native_vsd_joinery(d,w,page_index=2)==()


def test_original_four_vsd_joinery_have_real_host_capped_double_leaves():
    p=require_original_3laurel()
    raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA256
    with fitz.open(stream=raw,filetype="pdf") as pdf:
        drawing=pdf[2].get_drawings()
        words=pdf[2].get_text("words")
    found=match_source_native_vsd_joinery(drawing,words,page_index=2)
    assert len(found)==4
    assert sorted(r.printed_width_mm for r in found)==[1200,1800,1800,1800]
    assert {r.vsd_word_index for r in found}=={312,316,318,344}
    assert len({r.width_word_index for r in found})==4
    assert len({pid for r in found for pid in r.sliding_leaf_path_ids})==8
    assert all(len(r.jamb_cap_path_ids)==2 for r in found)
    laundry=next(r for r in found if r.vsd_word_index==312)
    assert set(laundry.wall_host_path_ids)=={2211,2213,2150}
    assert all(not r.physical_opening_authenticated and not r.customer_quantity_authorized
               for r in found)
