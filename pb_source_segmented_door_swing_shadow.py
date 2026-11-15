"""Original PlanReader: source-black segmented swing/leaf geometry witnesses.

Some CAD exports paint a door swing as several *independent* straight PDF
line paths, NOT one bezier/arc. Recognise a quarter-circle chord chain only
when a distinct real source line forms its radial door leaf. Emit SOURCE
CANDIDATES, never a physical opening, frame, metric quantity or customer row.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math

from pb_layered_wall_doorway_room_ring_shadow import _is_black, _xy


def _near(a: tuple[float, float], b: tuple[float, float], tol: float = 0.18) -> bool:
    return math.dist(a,b) <= tol


def _arc_quarter_candidate(
    chain: list[tuple[int, tuple[float,float], tuple[float,float]]],
) -> tuple[tuple[float,float], float] | None:
    if not 4 <= len(chain) <= 25:
        return None
    pts=[chain[0][1],*(s[2] for s in chain)]
    start,end=pts[0],pts[-1]
    dx=abs(start[0]-end[0])
    dy=abs(start[1]-end[1])
    radius=(dx+dy)*.5
    # A doorway can be quite small on paper, but tiny circular annotation
    # bubbles are not independently source-authenticated door swings.
    if not (18 <= radius <= 250 and abs(dx-dy) <= .055*radius):
        return None
    lengths=[math.dist(a,b) for _,a,b in chain]
    if any(x<=0.25 or x>radius*.3 for x in lengths):
        return None
    centers=((start[0],end[1]),(end[0],start[1]))
    compatible=[]
    for center in centers:
        radial=[math.dist(p,center) for p in pts]
        if any(abs(r-radius) > max(.35,.022*radius) for r in radial):
            continue
        angles=[math.atan2(y-center[1],x-center[0]) for x,y in pts]
        increments=[((a-b+math.pi)%(2*math.pi)-math.pi) for a,b in zip(angles[1:],angles)]
        # The original source points must run in one quarter-turn and not
        # reverse or cross another grid line.
        if not (all(a>0 for a in increments) or all(a<0 for a in increments)):
            continue
        if abs(abs(sum(increments))-math.pi/2)>0.07:
            continue
        compatible.append(center)
    if len(compatible)!=1:
        return None
    return compatible[0],radius


def collect_source_black_segmented_door_swings(
    drawings: Sequence[Mapping[str, Any]],
) -> tuple[dict[str,Any], ...]:
    """Return identified source swing strokes with a UNIQUE matching door leaf.

    Assumes the caller passed source-paint-excluded original-index drawing
    rows. The input must not be renumbered; every drawing index is the real
    PDF native path index. No gaps are constructed here.
    """
    strokes=[]
    for index,row in enumerate(drawings):
        if not isinstance(row,Mapping) or row.get("fill") is not None:
            continue
        if not _is_black(row.get("color")):
            continue
        items=row.get("items",())
        if len(items)!=1 or items[0][0]!="l":
            continue
        a,b=(_xy(items[0][1]),_xy(items[0][2]))
        if not all(math.isfinite(v) for v in (*a,*b)):
            continue
        length=math.dist(a,b)
        if .25 <= length <= 260:
            strokes.append((index,a,b))
    # CAD exports sequential chord paths with exactly shared endpoints. A
    # random assortment of black wall/furniture lines cannot be rearranged
    # into a circular arc or lose its original source ordering.
    groups=[]
    chain=[]
    for row in strokes:
        if chain and row[0]==chain[-1][0]+1 and _near(chain[-1][2],row[1]):
            chain.append(row)
        else:
            if chain:groups.append(chain)
            chain=[row]
    if chain:groups.append(chain)
    witnesses=[]
    used_ids=set()
    for group in groups:
        result=_arc_quarter_candidate(group)
        if result is None:
            continue
        center,radius=result
        first,last=group[0][1],group[-1][2]
        arc_indices=tuple(item[0] for item in group)
        leaf_options=[]
        for index,a,b in strokes:
            if index in arc_indices:
                continue
            # Door leaf is genuinely a separate ORIGINAL line from the
            # hinge/center to one endpoint of the original curved swing.
            for tip in (first,last):
                if ((_near(a,center) and _near(b,tip))
                        or (_near(b,center) and _near(a,tip))):
                    leaf_options.append((index,tip))
                    break
        if len(leaf_options)!=1:
            continue
        leaf_index,tip=leaf_options[0]
        # The leaf is DRAWN OPEN, and closes to the OTHER arc endpoint.
        # The open tip must never be projected as a threshold chord.
        closed_tip=last if _near(tip,first) else first
        ids=set(arc_indices)|{leaf_index}
        if used_ids.intersection(ids):
            continue
        used_ids.update(ids)
        witnesses.append({
            "arc_native_path_indices":arc_indices,
            "leaf_native_path_index":leaf_index,
            "source_hinge_point_pdf_pts":center,
            "source_open_leaf_tip_pdf_pts":tip,
            "source_closed_leaf_tip_pdf_pts":closed_tip,
            "radius_pdf_pts":round(radius,5),
            "native_source_path_indices":tuple(sorted(ids)),
            "ink_role":"BLACK_SEGMENTED_QUARTER_SWING_AND_RADIAL_LEAF",
            "source_segmented_polyline":True,
            "wall_host_authenticated":False,
            "door_schedule_identity_authenticated":False,
            "source_gap_both_ends_authenticated":False,
            "topology_doorway_closure_authorized":False,
            "physical_door_opening_authenticated":False,
            "commercial_publishable":False,
        })
    return tuple(witnesses)

def propose_source_owned_doorway_chords(
    drawings: Sequence[Mapping[str, Any]],
    swing_witnesses: Sequence[Mapping[str, Any]],
    original_wall_gaps: Sequence[Any],
) -> tuple[dict[str, Any], ...]:
    """General, source-positive doorway-to-wall proposal (never a quantity).

    One input representation is a segmented original PDF swing; the same
    normalized hinge/closed-tip receipt can later come from a native curve,
    schedule-backed opening frame, or sliding symbol. No door number,
    opening size or project coordinate is built into the algorithm.

    Source wall ends on BOTH sides, perpendicular source jamb returns, and
    an existing wall-band interruption must corroborate the local proposed
    chord. Long/wrong raw gaps are NEVER themselves closed by this method:
    only the independently supported, bounded doorway chord is proposed.
    """
    strokes=[]
    for idx,row in enumerate(drawings):
        if not isinstance(row,Mapping) or row.get("fill") is not None:
            continue
        if not _is_black(row.get("color")):
            continue
        items=row.get("items",())
        if len(items)!=1 or items[0][0]!="l":
            continue
        a,b=_xy(items[0][1]),_xy(items[0][2])
        if all(math.isfinite(v) for v in (*a,*b)):
            strokes.append((idx,a,b))
    proposed=[]
    used_intervals=set()
    for w in swing_witnesses:
        a=tuple(w["source_hinge_point_pdf_pts"])
        b=tuple(w["source_closed_leaf_tip_pdf_pts"])
        dx,dy=abs(a[0]-b[0]),abs(a[1]-b[1])
        horizontal=dy <= .12 and dx > 1
        vertical=dx <= .12 and dy > 1
        if horizontal == vertical:
            continue
        axis=0 if horizontal else 1
        perp_axis=1-axis
        lo,hi=sorted((a[axis],b[axis]))
        perp=(a[perp_axis]+b[perp_axis])/2
        support:dict[str,list[int]]={
            "left": [],"right": [],"jamb_left":[],"jamb_right":[],
            "threshold":[],
        }
        for idx,start,end in strokes:
            if idx in w["native_source_path_indices"]:
                continue
            along_delta=abs(start[axis]-end[axis])
            perp_delta=abs(start[perp_axis]-end[perp_axis])
            if perp_delta < .12 and along_delta >= 1.2:
                strand_lo,strand_hi=sorted((start[axis],end[axis]))
                if abs(start[perp_axis]-perp) <= 3.0:
                    if abs(strand_hi-lo) <= .18 and strand_lo < lo-1.0:
                        support["left"].append(idx)
                    if abs(strand_lo-hi) <= .18 and strand_hi > hi+1.0:
                        support["right"].append(idx)
                    if abs(strand_lo-lo) <= .18 and abs(strand_hi-hi) <= .18:
                        support["threshold"].append(idx)
            if along_delta < .12 and perp_delta >= 1.2:
                if max(abs(start[perp_axis]-perp),abs(end[perp_axis]-perp)) <= 14:
                    if abs(start[axis]-lo) <= .18:
                        support["jamb_left"].append(idx)
                    if abs(start[axis]-hi) <= .18:
                        support["jamb_right"].append(idx)
        if not all(support[k] for k in ("left","right","jamb_left","jamb_right")):
            continue
        parents=[]
        for gap in original_wall_gaps:
            if gap.horizontal != horizontal:
                continue
            thickness=gap.band[1]-gap.band[0]
            if not (gap.band[0]-max(.18,thickness)<=perp<=gap.band[1]+max(.18,thickness)):
                continue
            if not (gap.lo-.18<=lo and hi<=gap.hi+.18):
                continue
            # At least ONE original raw wall gap end must be an actual
            # chord endpoint. The second end is verified by DIFFERENT
            # real source strokes and its jamb.
            if min(abs(gap.lo-lo),abs(gap.hi-hi))>.18:
                continue
            parents.append(gap)
        if len(parents)!=1:
            continue
        parent=parents[0]
        key=(horizontal,round(perp,3),round(lo,3),round(hi,3))
        if key in used_intervals:
            continue
        used_intervals.add(key)
        source_ids=tuple(sorted(set(
            w["native_source_path_indices"]
            +tuple(i for collection in support.values() for i in collection)
            +parent.left_path_indices+parent.right_path_indices
        )))
        proposed.append({
            "horizontal":horizontal,
            "wall_band_pdf_pts":tuple(parent.band),
            "door_interval_pdf_pts":(lo,hi),
            "source_swing_native_path_indices":tuple(w["native_source_path_indices"]),
            "source_wall_end_left_path_indices":tuple(sorted(set(support["left"]))),
            "source_wall_end_right_path_indices":tuple(sorted(set(support["right"]))),
            "source_jamb_left_path_indices":tuple(sorted(set(support["jamb_left"]))),
            "source_jamb_right_path_indices":tuple(sorted(set(support["jamb_right"]))),
            "source_threshold_path_indices":tuple(sorted(set(support["threshold"]))),
            "source_native_path_indices":source_ids,
            "left_source_wall_path_indices":tuple(sorted(set(parent.left_path_indices+tuple(support["left"])+tuple(support["jamb_left"])))),
            "right_source_wall_path_indices":tuple(sorted(set(parent.right_path_indices+tuple(support["right"])+tuple(support["jamb_right"])))),
            "source_owned_local_wall_ends":True,
            "candidate_topology_doorway_closure":True,
            "source_physical_door_host_authenticated":False,
            "metric_area_issued":False,
            "commercial_publishable":False,
        })
    return tuple(proposed)
