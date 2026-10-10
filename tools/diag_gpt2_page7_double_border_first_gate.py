"""Shadow first-gate inventory for the strict native double-border owner test."""
from collections import defaultdict
import json
from pathlib import Path
import hashlib

import fitz
import pb_viewport_segmentation as vp

SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def inspect(page):
    calibration=vp.calibrate_viewport_layout(page)
    anchors=vp.extract_view_title_anchors(page)
    fragments=vp._text_fragments(page)
    all_frames=vp.extract_vector_frames(page,calibration)
    result={"calibrated_word_height_pt":calibration.median_word_height_pt,
            "anchors":[],"mode":"READ_ONLY_FIRST_REJECTING_GATE"}
    for anchor in anchors:
        if anchor.view_type!="floor_plan":
            continue
        candidates=vp._frame_candidates_for_title(
            page,anchor,all_frames,calibration,anchors=anchors
        )
        usable=[f for f in candidates if not vp._rejected_ownership_frame(
            page,f,calibration,fragments,view_type=anchor.view_type
        )]
        usable=vp._collapse_nested_band_frames(usable)
        usable=vp._collapse_equivalent_nested_frames(usable,calibration)
        gate={"title":anchor.text,"candidate_frames":candidates,
              "after_standard_rejections_and_collapse":usable}
        if len(usable)!=2:
            gate["first_failure"]="not_exactly_two_remaining_frame_candidates"
            result["anchors"].append(gate)
            continue
        inner,outer=sorted(usable,key=vp._bbox_area)
        differences=[abs(outer[i]-inner[i]) for i in range(4)]
        edge_tol=max(calibration.median_word_height_pt*0.1,0.75)
        aligned=[i for i,x in enumerate(differences) if x<=edge_tol]
        gate.update({"inner":inner,"outer":outer,"edge_deltas":differences,
                     "aligned_edges":aligned})
        if len(aligned)!=3:
            gate["first_failure"]="three_edge_alignment_unproven"
            result["anchors"].append(gate)
            continue
        side=next(i for i in range(4) if i not in aligned)
        if side==0:
            strip=(outer[0],outer[1],inner[0],outer[3])
        elif side==1:
            strip=(outer[0],outer[1],outer[2],inner[1])
        elif side==2:
            strip=(inner[2],outer[1],outer[2],outer[3])
        else:
            strip=(outer[0],inner[3],outer[2],outer[3])
        strip=vp._normalized_bbox(*strip)
        colliding_text=[text[:100] for bbox,text in fragments
                        if vp._bbox_overlap_area(bbox,strip)>1e-6]
        foreign_rects=[]
        source_nonlines=[]
        signatures=defaultdict(set)
        major_crossings=[]
        all_strokes=0
        for k,drawing in enumerate(vp._page_drawings(page)):
            style=(str(drawing.get("type") or ""),
                   str(drawing.get("color") or ""),
                   round(float(drawing.get("width") or 0.0),3),
                   round(float(drawing.get("stroke_opacity") or 1.0),3))
            for index,item in enumerate(drawing.get("items",()) or ()):
                if not item:
                    continue
                if item[0]=="re":
                    rec=item[1]
                    bbox=vp._normalized_bbox(
                        float(rec.x0),float(rec.y0),float(rec.x1),float(rec.y1)
                    )
                    if vp._bbox_overlap_area(bbox,strip)<=1e-6:
                        continue
                    if any(all(abs(bbox[i]-f[i])<=edge_tol for i in range(4))
                           for f in (outer,inner)):
                        continue
                    foreign_rects.append({
                        "native_drawing_seqno":drawing.get("seqno",k),
                        "path_index":k,
                        "bbox":bbox,
                        "source_item_index":index,
                        "rectangle_instructions":str(item[0]),
                        "native_paint_type":drawing.get("type"),
                        "source_stroke_color":drawing.get("color"),
                        "source_fill_color":drawing.get("fill"),
                        "source_stroke_width":drawing.get("width"),
                        "source_stroke_opacity":drawing.get("stroke_opacity"),
                        "source_fill_opacity":drawing.get("fill_opacity"),
                        "source_layer":drawing.get("layer"),
                        "source_path_item_count":len(drawing.get("items",()) or ()),
                        "source_path_rect":str(drawing.get("rect")),
                    })
                    continue
                if item[0]!="l" or len(item)<3:
                    if item[0] in ("c","qu"):
                        points=[p for p in item[1:]
                                if hasattr(p,"x") and hasattr(p,"y")]
                        bounds=None
                        if item[0]=="qu" and len(item)>=2:
                            quad=vp._axis_aligned_quad_bbox(item[1],tol=edge_tol)
                            bounds=quad
                        elif len(points)==len(item)-1 and points:
                            bounds=vp._normalized_bbox(
                                min(float(p.x) for p in points),
                                min(float(p.y) for p in points),
                                max(float(p.x) for p in points),
                                max(float(p.y) for p in points),
                            )
                        if bounds is None or vp._bbox_overlap_area(bounds,strip)>1e-6:
                            source_nonlines.append({
                                "native_drawing_seqno":drawing.get("seqno",k),
                                "item_kind":item[0],
                                "native_bounds":bounds,
                                "source_path_item_count":len(drawing.get("items",()) or ()),
                                "paint_type":drawing.get("type"),
                                "source_layer":drawing.get("layer"),
                            })
                    continue
                a,b=item[1],item[2]
                x0,y0,x1,y1=float(a.x),float(a.y),float(b.x),float(b.y)
                if (
                    max(x0,x1)<strip[0] or min(x0,x1)>strip[2]
                    or max(y0,y1)<strip[1] or min(y0,y1)>strip[3]
                ):
                    continue
                if side in (0,2) and abs(x0-x1)<=.25 and (
                    abs(x0-outer[side])<=.25 or abs(x0-inner[side])<=.25
                ):
                    continue
                if side in (1,3) and abs(y0-y1)<=.25 and (
                    abs(y0-outer[side])<=.25 or abs(y0-inner[side])<=.25
                ):
                    continue
                all_strokes+=1
                a1=(round(x0,3),round(y0,3))
                b1=(round(x1,3),round(y1,3))
                signatures[(tuple(sorted((a1,b1))),style)].add(
                    drawing.get("seqno",k)
                )
                limit=inner[side]
                if side in (0,2):
                    crosses=min(x0,x1)<limit<max(x0,x1)
                    penetration=max(x0,x1)-limit if side==0 else limit-min(x0,x1)
                else:
                    crosses=min(y0,y1)<limit<max(y0,y1)
                    penetration=max(y0,y1)-limit if side==1 else limit-min(y0,y1)
                if crosses and penetration>max(.25,calibration.median_word_height_pt*.05):
                    major_crossings.append([x0,y0,x1,y1])
        bad_signatures=[{"geometry":key[0],"style":key[1],"copies":len(v)}
                        for key,v in signatures.items() if len(v)!=2]
        gate.update({
            "differential_strip":strip,
            "text_overlap_count":len(colliding_text),
            "first_text_overlaps":colliding_text[:10],
            "foreign_source_rectangle_count":len(foreign_rects),
            "first_foreign_rectangles":foreign_rects[:20],
            "curve_quad_overlap_or_unknown_count":len(source_nonlines),
            "first_curve_quads":source_nonlines[:10],
            "native_line_occurrences":all_strokes,
            "distinct_geometry_plus_paint_style":len(signatures),
            "nondouble_geometry_style_count":len(bad_signatures),
            "first_nondouble_signatures":bad_signatures[:15],
            "meaningful_frame_crossing_count":len(major_crossings),
            "first_meaningful_crossings":major_crossings[:10],
            "fallback_output":vp._collapse_source_repeated_plan_border_pair(
                page,usable,calibration,fragments
            ),
        })
        result["anchors"].append(gate)
    return result


def main():
    path=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:
        raise ValueError("immutable Maryborough source SHA mismatch")
    pdf=fitz.open(stream=raw,filetype="pdf")
    try:
        assert len(pdf)==31
        result=inspect(pdf.load_page(6))
        result["source_sha256"]=SOURCE_SHA
    finally:
        pdf.close()
    print("GPT2_DOUBLE_BORDER_FIRST_GATE",json.dumps(result,default=str,sort_keys=True))
    target=Path("artifacts/gpt2-double-plan-border/first_rejecting_gate.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,default=str,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
