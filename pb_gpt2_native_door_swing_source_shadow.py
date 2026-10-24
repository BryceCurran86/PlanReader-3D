"""Default-unwired original native door leaf/swing evidence; no door authority.

All drawing indices refer to one SHA-pinned PDF page. The caller does not
supply door geometry, a claimed radius, a scale, or a metric measurement.
This source-only diagnostic never grants W4 host, count, floor threshold or FIRM.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import re

import fitz


@dataclass(frozen=True)
class NativeDoorSwingSourceShadow:
    source_sha256: str
    page_number: int
    word_address: tuple[int, int, int]
    native_door_label: str
    leaf_path_ids: tuple[int, ...]
    swing_path_ids: tuple[int, ...]
    jamb_path_ids: tuple[int, ...]
    hinge_pt: tuple[float, float]
    leaf_length_pt: float
    swing_radius_pt: float
    status: str = "source_door_swing_ink_candidate_only"
    shadow_only: bool = True
    physical_door_identity_issued: bool = False
    structural_wall_host_issued: bool = False
    doorway_threshold_issued: bool = False
    source_metric_dimension_issued: bool = False
    floor_finish_area_issued: bool = False
    opening_count_issued: bool = False
    commercial_projection_allowed: bool = False


def _line(drawings, index):
    if type(index) is not int or not 0 <= index < len(drawings):
        raise ValueError("original native path missing")
    row = drawings[index]
    color = row.get("color")
    opacity = row.get("stroke_opacity")
    if (type(opacity) not in (int, float) or not math.isfinite(opacity)
            or opacity != 1.0):
        raise ValueError("original source ink opacity is not finite opaque")
    if (row.get("type") != "s" or row.get("fill") is not None
            or row.get("dashes") != "[] 0"
            or type(color) not in (tuple, list) or len(color) != 3
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   or not 0 <= v <= .04 for v in color)
            or row.get("stroke_opacity") != 1.0):
        raise ValueError("original line is not visible opaque black source ink")
    items = row.get("items", ())
    if len(items) != 1 or items[0][0] != "l":
        raise ValueError("original source path is not one independent stroke")
    a, b = items[0][1:3]
    result = ((float(a.x), float(a.y)), (float(b.x), float(b.y)))
    width = row.get("width")
    if (type(width) not in (int, float) or not math.isfinite(width)
            or width <= 0 or not all(math.isfinite(c) for p in result for c in p)
            or math.dist(*result) <= 0):
        raise ValueError("non-finite/degenerate original source line")
    return result[0], result[1], float(width)


def _distinct_paths(leaf, swing, jamb):
    if (type(leaf) is not tuple or type(swing) is not tuple
            or type(jamb) is not tuple or len(leaf) < 2 or len(swing) < 4
            or len(jamb) != 2):
        raise ValueError("complete typed native leaf/swing/jamb path groups required")
    ids = leaf + swing + jamb
    if any(type(n) is not int for n in ids) or len(set(ids)) != len(ids):
        raise ValueError("duplicate or noninteger native source path")


def inspect_native_door_swing_source_shadow(
    original_pdf_bytes: bytes, *, expected_source_sha256: str,
    page_number: int, word_address: tuple[int, int, int],
    leaf_path_ids: tuple[int, ...], swing_path_ids: tuple[int, ...],
    jamb_path_ids: tuple[int, int], tolerance_pt: float = 0.5,
) -> NativeDoorSwingSourceShadow:
    """Prove native leaf and quarter-swing topology, never a physical doorway."""
    if (type(original_pdf_bytes) is not bytes or not original_pdf_bytes
            or sha256(original_pdf_bytes).hexdigest() != expected_source_sha256):
        raise ValueError("original source SHA mismatch")
    if (type(page_number) is not int or type(word_address) is not tuple
            or len(word_address) != 3 or any(type(x) is not int or x < 0 for x in word_address)
            or type(tolerance_pt) not in (int, float) or not math.isfinite(tolerance_pt)
            or not 0.001 <= tolerance_pt <= 0.5):
        raise ValueError("invalid source scope or native float tolerance")
    _distinct_paths(leaf_path_ids, swing_path_ids, jamb_path_ids)
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError("original source page unavailable")
        page = doc[page_number-1]
        all_words = page.get_text("words")
        hits = [w for w in all_words if tuple(w[5:8]) == word_address]
        if len(hits) != 1 or not re.fullmatch(r"D[0-9]+", str(hits[0][4])):
            raise ValueError("original door code word address not unique or eligible")
        label_bbox = tuple(float(v) for v in hits[0][:4])
        drawings = page.get_drawings()
        leaves = tuple(_line(drawings, n) for n in leaf_path_ids)
        arcs = tuple(_line(drawings, n) for n in swing_path_ids)
        jambs = tuple(_line(drawings, n) for n in jamb_path_ids)
    lengths = tuple(math.dist(a, b) for a, b, _ in leaves)
    max_length = max(lengths)
    mains = [i for i, length in enumerate(lengths)
             if abs(length-max_length) <= tolerance_pt]
    short = [i for i in range(len(leaves)) if i not in mains]
    # A framed leaf has TWO long parallel strokes and two short end caps.
    if (len(leaves) != 4 or len(mains) != 2 or len(short) != 2
            or max_length <= 4*max(lengths[i] for i in short)):
        raise ValueError("original two-face door leaf is not a closed thin rectangle")
    if any(abs(row[2]-leaves[0][2]) > 0.0001 for row in leaves):
        raise ValueError("original thick door leaf stroke family inconsistent")
    # A pair of long equal-length segments need not be parallel: a
    # tapered wedge may close with short caps yet still not be a door leaf.
    # Require the long painted faces to share one physical source axis.
    (a0,b0,_),(a1,b1,_)=tuple(leaves[i] for i in mains)
    v0=(b0[0]-a0[0],b0[1]-a0[1])
    v1=(b1[0]-a1[0],b1[1]-a1[1])
    if abs(v0[0]*v1[1]-v0[1]*v1[0])/(math.dist(a0,b0)*math.dist(a1,b1))>0.02:
        raise ValueError("original two-face door leaf is not parallel")
    for k in short:
        a, b, _ = leaves[k]
        if any(not any(math.dist(p, q) <= tolerance_pt
                       for q in leaves[m][:2])
               for p, m in ((a,mains[0]),(b,mains[1]))) and any(
                not any(math.dist(p,q) <= tolerance_pt
                        for q in leaves[m][:2])
                for p,m in ((a,mains[1]),(b,mains[0]))):
            raise ValueError("door leaf end caps do not join both long strokes")
    if any(row[2] >= leaves[0][2] for row in arcs):
        raise ValueError("door swing ink not distinct from thick leaf")
    def dist(a,b): return math.dist(a,b)
    options = []
    for i in mains:
        for leaf_tip, hinge in ((leaves[i][0], leaves[i][1]),
                                (leaves[i][1], leaves[i][0])):
            if not any(dist(leaf_tip,p) <= tolerance_pt
                       for row in arcs for p in row[:2]):
                continue
            radius = dist(leaf_tip,hinge)
            if all(abs(dist(p,hinge)-radius)<=tolerance_pt
                   for row in arcs for p in row[:2]):
                options.append((hinge,leaf_tip,radius))
    if len(options) != 1:
        raise ValueError("arc does not uniquely share door leaf tip and hinge radius")
    hinge, leaf_tip, radius = options[0]
    # This is a negative-only original word/door geometry check, not a
    # producer-issued text glyph or physical opening identity. A caller may
    # not associate any remote Dxx word on the same page with this swing.
    jamb_xs = [point[0] for a,b,_ in jambs for point in (a,b)]
    word_h = label_bbox[3] - label_bbox[1]
    if (not all(math.isfinite(v) for v in label_bbox) or word_h <= 0
            or label_bbox[2] < min(jamb_xs)
            or label_bbox[0] > max(jamb_xs)
            or label_bbox[1] > hinge[1] + 2*word_h
            or label_bbox[3] < hinge[1] - 2*word_h):
        raise ValueError("original D-code word is remote from the painted door")
    # Reject a second local D-code label; selecting the requested source word
    # must not silently discard a rival original door identity at this aperture.
    rivals = [w for w in all_words
              if re.fullmatch(r"D[0-9]+",str(w[4]))
              and (w[0]+w[2])/2 >= min(jamb_xs)-word_h
              and (w[0]+w[2])/2 <= max(jamb_xs)+word_h
              and abs((w[1]+w[3])/2-hinge[1])<=2*word_h]
    if len(rivals) != 1 or tuple(rivals[0][5:8]) != word_address:
        raise ValueError("competing original D-code words near painted door")
    # Every source arc must form ONE degree-2 chain with precisely 2 free tips.
    vertices: list[tuple[float,float]] = []
    degree: list[int] = []
    graph: list[tuple[int,int]] = []
    for a,b,_ in arcs:
        endpoints=[]
        for p in (a,b):
            matches=[i for i,q in enumerate(vertices) if dist(p,q)<=tolerance_pt]
            if len(matches)>1: raise ValueError("arc endpoint node ambiguous")
            if matches: index=matches[0]
            else:
                index=len(vertices);vertices.append(p);degree.append(0)
            endpoints.append(index)
        if endpoints[0]==endpoints[1]: raise ValueError("degenerate arc path")
        graph.append(tuple(endpoints))
        for index in endpoints:degree[index]+=1
    terminals=[i for i,d in enumerate(degree) if d==1]
    if len(terminals)!=2 or any(d>2 or d<1 for d in degree):
        raise ValueError("source arc is branched, circular or disconnected")
    visited={terminals[0]}; pending=[terminals[0]]
    while pending:
        v=pending.pop()
        for a,b in graph:
            if v in (a,b):
                u=b if a==v else a
                if u not in visited:visited.add(u);pending.append(u)
    if len(visited)!=len(vertices) or not any(dist(vertices[t],leaf_tip)<=tolerance_pt for t in terminals):
        raise ValueError("native arc is broken or does not finish at door leaf")
    other=vertices[next(t for t in terminals if dist(vertices[t],leaf_tip)>tolerance_pt)]
    da=(leaf_tip[0]-hinge[0],leaf_tip[1]-hinge[1])
    db=(other[0]-hinge[0],other[1]-hinge[1])
    if abs(da[0]*db[0]+da[1]*db[1])>0.05*radius*radius:
        raise ValueError("original door swing is not a quarter turn")
    # Endpoints alone do NOT prove a quarter swing: a continuous 270-degree
    # arc has the same perpendicular endpoint vectors. Reconstruct the source
    # chain in order and require strictly monotone angular progress spanning
    # a SINGLE quarter revolution, never a winding/backtracking label circle.
    leaf_node=next(i for i in terminals if dist(vertices[i],leaf_tip)<=tolerance_pt)
    adjacency={i:[] for i in range(len(vertices))}
    for a,b in graph:
        adjacency[a].append(b)
        adjacency[b].append(a)
    ordered=[leaf_node]
    while len(ordered)<len(vertices):
        prev=ordered[-2] if len(ordered)>1 else None
        neighbors=[n for n in adjacency[ordered[-1]] if n!=prev]
        if len(neighbors)!=1 or neighbors[0] in ordered:
            raise ValueError("original swing arc source chain cannot be ordered uniquely")
        ordered.append(neighbors[0])
    angles=[math.atan2(vertices[i][1]-hinge[1],vertices[i][0]-hinge[0])
            for i in ordered]
    steps=[]
    for a,b in zip(angles,angles[1:]):
        step=(b-a+math.pi)%(2*math.pi)-math.pi
        if not (math.isfinite(step) and 1e-4<abs(step)<=math.pi/2+0.01):
            raise ValueError("source arc has zero or oversized angular step")
        steps.append(step)
    sweep=sum(steps)
    if (any(s*sweep<=0 for s in steps)
            or abs(abs(sweep)-math.pi/2)>0.05):
        raise ValueError("source arc changes direction or is not one quarter sweep")
    # Distinct source-native painted jambs must witness each SIDE. A single
    # bridging wall stroke can touch hinge and far swing tip yet is not two
    # independent doorway termini; do not elect it over an unrelated stroke.
    hinge_jambs={i for i,(a,b,_) in enumerate(jambs)
                 if min(dist(hinge,a),dist(hinge,b))<=3.0}
    far_jambs={i for i,(a,b,_) in enumerate(jambs)
               if min(dist(other,a),dist(other,b))<=3.0}
    if not hinge_jambs:
        raise ValueError("door hinge is not source-adjacent to a painted jamb")
    if not far_jambs:
        raise ValueError("far end of source swing is not near opposite door jamb")
    if (hinge_jambs.intersection(far_jambs)
            or not any(i!=j for i in hinge_jambs for j in far_jambs)):
        raise ValueError("original doorway jamb source bridges both ends")

    return NativeDoorSwingSourceShadow(
        expected_source_sha256,page_number,word_address,str(hits[0][4]),
        leaf_path_ids,swing_path_ids,jamb_path_ids,hinge,radius,radius,
    )
