"""Native original callout ink is NOT a physical-opening binding receipt."""
import random

import pytest

from tools.diag_gpt1_source_hex_callout_ink_shadow import (
    diagnose_hex_ink_for_text_bbox, native_line_segments,
)


def _hex(center=(0,0), *, scale=1, duplicate=False):
    cx,cy=center
    polygon=[(-10,-5),(0,-12),(10,-5),(10,5),(0,12),(-10,5)]
    points=[(cx+scale*x,cy+scale*y) for x,y in polygon]
    edges=[(i+1,*points[i],*points[(i+1)%6]) for i in range(6)]
    if duplicate:
        edges += [(i+101,*points[i],*points[(i+1)%6]) for i in range(6)]
    return edges


def _word(center=(0,0), *, scale=1):
    x,y=center
    return (x-4*scale,y-5*scale,x+4*scale,y+5*scale)


def test_unique_six_source_edges_enclose_native_word_without_granting_area():
    got=diagnose_hex_ink_for_text_bbox(_word(),_hex(duplicate=True))
    assert got['status']=='SOURCE_NATIVE_HEX_INK_ONLY'
    assert got['source_seqnos']==[1,2,3,4,5,6,101,102,103,104,105,106]
    assert got['physical_opening_bound'] is False
    assert got['measurement_granted'] is False
    assert got['customer_seal_granted'] is False


def test_order_and_duplicate_invariance_and_unrelated_ink():
    lines=_hex(duplicate=True)+[(500,200,200,210,210)]
    expected=diagnose_hex_ink_for_text_bbox(_word(),lines)
    random.Random(42).shuffle(lines)
    assert diagnose_hex_ink_for_text_bbox(_word(),lines)==expected


@pytest.mark.parametrize('center,scale', [((200,300),1),((-100,50),1.7),((0,0),0.6)])
def test_translation_and_uniform_scale_invariance(center,scale):
    got=diagnose_hex_ink_for_text_bbox(_word(center,scale=scale),_hex(center,scale=scale))
    assert got['status']=='SOURCE_NATIVE_HEX_INK_ONLY'


def test_rotation_90_degrees_invariance():
    def rot(x,y):return (-y,x)
    original=_hex()
    lines=[(s,*rot(x0,y0),*rot(x1,y1)) for s,x0,y0,x1,y1 in original]
    assert diagnose_hex_ink_for_text_bbox(_word(),lines)['status']=='SOURCE_NATIVE_HEX_INK_ONLY'


def test_missing_ink_edge_abstains_without_geometric_gap_completion():
    got=diagnose_hex_ink_for_text_bbox(_word(),_hex()[:-1])
    assert got['status']=='ABSTAIN'
    assert got['source_seqnos']==[]


def test_conflicting_second_source_hex_does_not_elect_nearest():
    got=diagnose_hex_ink_for_text_bbox(_word(),_hex()+_hex(scale=1.35))
    assert got['status']=='CONFLICT'
    assert got['source_seqnos']==[]


def test_nearby_hex_not_enclosing_text_cannot_bind_by_proximity():
    assert diagnose_hex_ink_for_text_bbox(_word(),_hex(center=(18,0)))['status']=='ABSTAIN'


def test_door_circle_like_eight_segment_polygon_not_hex():
    import math
    pts=[(11*math.cos(i*math.pi/4),11*math.sin(i*math.pi/4)) for i in range(8)]
    lines=[(i,*pts[i],*pts[(i+1)%8]) for i in range(8)]
    assert diagnose_hex_ink_for_text_bbox(_word(),lines)['status']=='ABSTAIN'


def test_empty_and_invalid_original_word_bbox_fail_closed():
    assert diagnose_hex_ink_for_text_bbox(_word(),[])['status']=='ABSTAIN'
    with pytest.raises(ValueError):
        diagnose_hex_ink_for_text_bbox((0,0,0,0),_hex())


def test_actual_fitz_native_segment_extraction_and_synthetic_pdf():
    fitz=pytest.importorskip('fitz')
    doc=fitz.open();page=doc.new_page(width=250,height=250)
    page.insert_text((120,120),'W01',fontsize=10)
    word=next(w for w in page.get_text('words') if w[4]=='W01')
    x=(word[0]+word[2])/2;y=(word[1]+word[3])/2
    scale=max(word[2]-word[0],word[3]-word[1])/7
    for _,x0,y0,x1,y1 in _hex(center=(x,y),scale=scale):
        page.draw_line(fitz.Point(x0,y0),fitz.Point(x1,y1),width=0.48)
    assert diagnose_hex_ink_for_text_bbox(word[:4],native_line_segments(page))['status']=='SOURCE_NATIVE_HEX_INK_ONLY'
    doc.close()


def test_sha_pinned_owner_original_four_plan_hexes_when_private_source_provisioned():
    from hashlib import sha256
    from pathlib import Path
    fitz=pytest.importorskip('fitz')
    source=Path('documents/sources/Arch_Combined_Maryborough_Service_Station.pdf')
    if not source.is_file():
        pytest.skip('private original source unavailable; not a source-positive pass')
    data=source.read_bytes()
    assert sha256(data).hexdigest()=='b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007'
    with fitz.open(stream=data,filetype='pdf') as pdf:
        plan=pdf[6]
        words=plan.get_text('words')
        lines=native_line_segments(plan)
        for mark in ('W01','W02','W05','W06'):
            matches=[w for w in words if w[4]==mark]
            assert len(matches)==1
            proof=diagnose_hex_ink_for_text_bbox(matches[0][:4],lines)
            assert proof['status']=='SOURCE_NATIVE_HEX_INK_ONLY'
            assert len(proof['source_seqnos'])==12
            assert proof['physical_opening_bound'] is False
