"""Independent SOURCE-to-reference correspondence of fourteen 3Laurel doors.

The draft physical reference is not the frozen scoring denominator and is never
read by any production detector. This test proves one-to-one native word/host
and source-declared 2100 joinery height against independently authored draft.
"""
import hashlib
import json
import math
from pathlib import Path

import fitz

from pb_source_native_cavity_slider_jamb_shadow import match_source_native_cavity_sliders
from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

REF = (
    Path(__file__).resolve().parents[1] /
    "benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_3laurel/reference_truth_draft.json"
)


def _near(a, b, tol=.28):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _union(a, b):
    return (min(a[0],b[0]), min(a[1],b[1]),
            max(a[2],b[2]), max(a[3],b[3]))


def test_original_fourteen_native_door_labels_match_independent_reference_one_to_one():
    source = require_original_3laurel()
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as document:
        page3 = document[2]
        drawings, words = tuple(page3.get_drawings()), tuple(page3.get_text("words"))
        assert "JOINERY HEIGHTS TO BE 2100 AFL U.N.O." in document[3].get_text("text")
        assert "JOINERY HEIGHTS TO BE 2100 AFL U.N.O." in document[4].get_text("text")
    hinges = detect_source_internal_swing_room_barriers(drawings, words, page_index=2)
    sliders = match_source_native_cavity_sliders(drawings, words, page_index=2)
    observed = []
    for r in hinges:
        b=r.bounds_pdf_pts
        cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
        choices=[]
        for idx,w in enumerate(words):
            token=str(w[4]).replace(",","")
            if not token.isdigit() or not 600<=int(token)<=1400:
                continue
            x,y=(w[0]+w[2])/2,(w[1]+w[3])/2
            dist=math.hypot(x-cx,y-cy)
            if dist<15:
                choices.append((dist,idx,int(token)))
        choices.sort()
        assert choices and (len(choices)==1 or choices[1][0]-choices[0][0]>2)
        _,idx,mm=choices[0]
        observed.append(("hinged_swing",mm,idx,tuple(words[idx][:4]),r.swing_arc_path_id))
    for r in sliders:
        wb=tuple(words[r.width_word_index][:4])
        cb=tuple(words[r.cs_word_index][:4])
        observed.append(("cavity_slider",r.printed_width_mm,r.width_word_index,
                         wb,r.leaf_path_id, _union(wb,cb)))
    reference=json.loads(REF.read_text(encoding="utf-8"))
    expected=[
        x for x in reference["verified_physical_candidates"]
        if x.get("object_family")=="internal_room_access_opening"
    ]
    assert len(expected)==14
    assert len(observed)==14
    matched=set()
    for obj in expected:
        attrs=obj["attributes"]
        kind=attrs["opening_type"]
        width_mm=round(attrs["width_m"]*1000)
        bbox=attrs["source_bbox_pdf_pt"]
        eligible=[
            i for i,source in enumerate(observed)
            if i not in matched and source[0]==kind and source[1]==width_mm
            and (_near(source[3],bbox) or (
                len(source)>5 and _near(source[5],bbox)))
        ]
        assert len(eligible)==1, obj["object_ref"]
        matched.add(eligible[0])
        # Independent dimensioned reference never changes from PlanReader.
        assert attrs["height_m"]==2.1
        assert abs(float(obj["expected_quantity"])-
                   attrs["width_m"]*attrs["height_m"])<=1e-9
    assert len(matched)==14
