"""Read-only source native double-frame gutter/content audit, not authority."""
import hashlib
import json
from pathlib import Path

import fitz
import pb_viewport_segmentation as vp

SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def inspect(pdf_data: bytes) -> dict:
    sha = hashlib.sha256(pdf_data).hexdigest()
    if sha != SHA:
        raise ValueError("source SHA mismatch")
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    try:
        assert doc.page_count == 31
        page = doc.load_page(6)
        cal = vp.calibrate_viewport_layout(page)
        anchors = vp.extract_view_title_anchors(page)
        frames = vp.extract_vector_frames(page, cal)
        fragments = vp._text_fragments(page)
        pairs = []
        for anchor in anchors:
            if anchor.view_type != "floor_plan":
                continue
            candidates = vp._frame_candidates_for_title(
                page, anchor, frames, cal, anchors=anchors
            )
            usable = vp._collapse_nested_band_frames(
                [f for f in candidates if not vp._rejected_ownership_frame(
                    page, f, cal, fragments, view_type=anchor.view_type
                )]
            )
            for outer in usable:
                for inner in usable:
                    if outer == inner:
                        continue
                    if not vp._bbox_contains(outer, inner, margin=0.5):
                        continue
                    delta = [abs(outer[i]-inner[i]) for i in range(4)]
                    align_tol=max(cal.median_word_height_pt * 0.1, 0.75)
                    aligned=[i for i in range(4) if delta[i] <= align_tol]
                    if len(aligned) != 3:
                        continue
                    side=next(i for i in range(4) if i not in aligned)
                    if side == 0:
                        strip=(outer[0],outer[1],inner[0],outer[3])
                    elif side == 1:
                        strip=(outer[0],outer[1],outer[2],inner[1])
                    elif side == 2:
                        strip=(inner[2],outer[1],outer[2],outer[3])
                    else:
                        strip=(outer[0],inner[3],outer[2],outer[3])
                    strip=(
                        min(strip[0],strip[2]),min(strip[1],strip[3]),
                        max(strip[0],strip[2]),max(strip[1],strip[3])
                    )
                    center=lambda b: ((b[0]+b[2])/2.0,(b[1]+b[3])/2.0)
                    words=[{
                        "text":str(w[4]), "bbox":list(map(float,w[:4]))
                    } for w in page.get_text("words")
                        if vp._point_in_bbox(center(w[:4]),strip)
                    ]
                    # Shadow geometry census only, not physical wall ownership.
                    # Check native line strokes intersecting the differential
                    # strip, excluding candidate frame boundaries themselves.
                    line_crossings=[]
                    for drawing in page.get_drawings():
                        for item in drawing.get("items",()):
                            if not item or item[0] != "l" or len(item) < 3:
                                continue
                            a,b=item[1],item[2]
                            x0,y0=float(a.x),float(a.y)
                            x1,y1=float(b.x),float(b.y)
                            if (
                                max(x0,x1) < strip[0] or min(x0,x1) > strip[2]
                                or max(y0,y1) < strip[1] or min(y0,y1) > strip[3]
                            ):
                                continue
                            # A framing line coincident with the two established
                            # border sides is not interior evidence.
                            if side in (0,2) and abs(x0-x1) <= 0.25 and (
                                abs(x0-outer[side]) <= .25
                                or abs(x0-inner[side]) <= .25
                            ):
                                continue
                            if side in (1,3) and abs(y0-y1) <= 0.25 and (
                                abs(y0-outer[side]) <= .25
                                or abs(y0-inner[side]) <= .25
                            ):
                                continue
                            line_crossings.append([x0,y0,x1,y1])
                    pairs.append({
                        "source_title": anchor.text,
                        "outer_native_frame":outer,
                        "inner_native_frame":inner,
                        "aligned_edge_indices":aligned,
                        "separate_edge_index":side,
                        "differential_band_native_pdf_pts":strip,
                        "band_width_pt":delta[side],
                        "native_text_center_hits":len(words),
                        "source_text_examples":words[:20],
                        "nonframe_native_line_intersections":len(line_crossings),
                        "source_line_examples":line_crossings[:20],
                    })
        return {
            "source_sha256":sha,
            "page":7,
            "candidate_nested_frame_pairs":pairs,
            "mode":"READ_ONLY_SOURCE_FRAME_STRIP_CENSUS",
            "asserted_equivalence":False,
            "created_room_or_metric":False,
        }
    finally:
        doc.close()


if __name__ == "__main__":
    raw=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf").read_bytes()
    report=inspect(raw)
    destination=Path("artifacts/gpt2-b01-residual-rcp/page7_double_frame_strip.json")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2,sort_keys=True,default=str))
    print("B01_SOURCE_FRAME_GUTTER",json.dumps(report,sort_keys=True,default=str))
