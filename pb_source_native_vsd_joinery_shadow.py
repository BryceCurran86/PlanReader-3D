"""Native sliding robe/linen VSD joinery frame matches, never a room-access wall.

A real VSD requires the original label+figured width, two black framed wall
end hosts, white jamb returns and TWO overlapping black sliding-leaf strokes.
Short original wall-end segments may be physically continuous (two source
primitives), but a space between segments is never automatically bridged.
These fixtures prove joinery OPENING topology only: no wall deduction, floor
room closure, physical wall area or customer quantity is emitted.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_source_native_cavity_slider_jamb_shadow import _box, _filled, _line, _word


@dataclass(frozen=True)
class SourceNativeVSDJoineryWitness:
    vsd_word_index: int
    width_word_index: int
    printed_width_mm: int
    horizontal: bool
    band_pdf_pts: tuple[float, float]
    clear_interval_pdf_pts: tuple[float, float]
    wall_host_path_ids: tuple[int, ...]
    jamb_cap_path_ids: tuple[int, int]
    sliding_leaf_path_ids: tuple[int, int]
    page_index: int
    physical_opening_authenticated: bool = False
    customer_quantity_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "native_vertical_sliding_joinery",
            "vsd_word_index": self.vsd_word_index,
            "width_word_index": self.width_word_index,
            "printed_width_mm": self.printed_width_mm,
            "horizontal": self.horizontal,
            "band_pdf_pts": list(self.band_pdf_pts),
            "clear_interval_pdf_pts": list(self.clear_interval_pdf_pts),
            "wall_host_path_ids": list(self.wall_host_path_ids),
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "sliding_leaf_path_ids": list(self.sliding_leaf_path_ids),
            "page_index": self.page_index,
            "physical_opening_authenticated": False,
            "customer_quantity_authorized": False,
        }


def _axis_line(line):
    (x,y),(u,v)=line
    if abs(y-v)<=.15 and abs(x-u)>12:
        return True,min(x,u),max(x,u),(y+v)/2
    if abs(x-u)<=.15 and abs(y-v)>12:
        return False,min(y,v),max(y,v),(x+u)/2
    return None


def _axis_box(box, horizontal):
    return (box[0],box[2],box[1],box[3]) if horizontal else (
        box[1],box[3],box[0],box[2],
    )


def match_source_native_vsd_joinery(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Sequence[Any] | Mapping[str, Any]],
    *, page_index: int,
) -> tuple[SourceNativeVSDJoineryWitness, ...]:
    """Accept only six *distinct* native frame owners per source-labelled VSD.

    The original top/bottom host may comprise more than one contiguous black
    filled segment. Every added source segment must actually touch its neighbour
    and have matching wall-face thickness. Competing owners cause abstention.
    """
    if type(page_index) is not int or page_index < 0:
        raise ValueError("source_page_index_invalid")
    words=[(i,b,t) for i,w in enumerate(source_words)
           if (v:=_word(w)) is not None for b,t in (v,)]
    lines=[]
    dark=[]
    white=[]
    for index,row in enumerate(drawings):
        if not isinstance(row,Mapping):
            continue
        stroke=_line(row)
        if stroke is not None:
            axis=_axis_line(stroke)
            if axis is not None:
                lines.append((index,*axis))
        if _filled(row,False) and (box:=_box(row)) is not None:
            dark.append((index,box))
        if _filled(row,True) and (box:=_box(row)) is not None:
            white.append((index,box))
    proposed=[]
    for word_index,bbox,text in words:
        if text!="VSD":
            continue
        cx,cy=(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2
        widths=[]
        for idx,wb,token in words:
            numeric=token.replace(",","")
            if not numeric.isdecimal() or int(numeric) not in (1200,1800):
                continue
            wx,wy=(wb[0]+wb[2])/2,(wb[1]+wb[3])/2
            distance=math.hypot(cx-wx,cy-wy)
            if distance<=25:
                widths.append((distance,idx,int(numeric)))
        widths.sort()
        if not widths or (
            len(widths)>1 and widths[1][0]-widths[0][0]<=2
        ):
            continue
        _distance,width_index,width_mm=widths[0]
        nearest=[]
        for index,horizontal,lo,hi,cross in lines:
            px,py=((lo+hi)/2,cross) if horizontal else (cross,(lo+hi)/2)
            if math.hypot(px-cx,py-cy)<85:
                nearest.append((index,horizontal,lo,hi,cross))
        candidates=[]
        for first_index,axis0,lo0,hi0,p0 in nearest:
            for second_index,axis1,lo1,hi1,p1 in nearest:
                if first_index>=second_index or axis0!=axis1:
                    continue
                if not .8<=abs(p0-p1)<=5:
                    continue
                lo,hi=min(lo0,lo1),max(hi0,hi1)
                span=hi-lo
                overlap=min(hi0,hi1)-max(lo0,lo1)
                if not (
                    .021*width_mm<=span<=.043*width_mm
                    and .45<=overlap<=5
                    and .35*span<=hi0-lo0<=.75*span
                    and .35*span<=hi1-lo1<=.75*span
                ):
                    continue
                band=min(p0,p1),max(p0,p1)
                middle=((lo+hi)/2,(band[0]+band[1])/2) if axis0 else (
                    (band[0]+band[1])/2,(lo+hi)/2,
                )
                dist=math.hypot(middle[0]-cx,middle[1]-cy)
                if dist>32:
                    continue
                end_caps=[]
                for end,is_lower in ((lo,True),(hi,False)):
                    matches=[]
                    for idx,rect in white:
                        a,z,q0,q1=_axis_box(rect,axis0)
                        if not .7<=z-a<=3.2:
                            continue
                        if min(q1,band[1])-max(q0,band[0]) < .6*(band[1]-band[0]):
                            continue
                        if abs((z if is_lower else a)-end)<=.3:
                            matches.append((idx,a,z,q0,q1))
                    if len(matches)!=1:
                        break
                    end_caps.append(matches[0])
                if len(end_caps)!=2 or end_caps[0][0]==end_caps[1][0]:
                    continue

                hosts=[]
                for cap,is_lower in zip(end_caps,(True,False)):
                    _cid,caplo,caphi,cross0,cross1=cap
                    touches=[]
                    for idx,rect in dark:
                        a,z,q0,q1=_axis_box(rect,axis0)
                        if z<=a:
                            continue
                        if min(q1,cross1)-max(q0,cross0)<.65*min(
                            q1-q0,cross1-cross0,
                        ):
                            continue
                        if abs((z if is_lower else a)-
                               (caplo if is_lower else caphi))<=.06:
                            touches.append((idx,a,z))
                    if len(touches)!=1:
                        break
                    primary=touches[0]
                    owners=[primary[0]]
                    length=primary[2]-primary[1]
                    if length<.5:
                        frontier=primary[1] if is_lower else primary[2]
                        neighbours=[]
                        for idx,rect in dark:
                            if idx==primary[0]:
                                continue
                            a,z,q0,q1=_axis_box(rect,axis0)
                            if min(q1,cross1)-max(q0,cross0)<.65*min(
                                q1-q0,cross1-cross0,
                            ):
                                continue
                            if abs((z if is_lower else a)-frontier)<=.06 and (
                                a<frontier-.3 if is_lower else z>frontier+.3
                            ):
                                neighbours.append((idx,a,z))
                        if len(neighbours)!=1:
                            break
                        owners.append(neighbours[0][0])
                        length+=neighbours[0][2]-neighbours[0][1]
                    if length<.5:
                        break
                    hosts.append(tuple(owners))
                if len(hosts)!=2 or set(hosts[0])&set(hosts[1]):
                    continue
                host_ids=tuple(i for group in hosts for i in group)
                cap_ids=end_caps[0][0],end_caps[1][0]
                leaf_ids=tuple(sorted((first_index,second_index)))
                all_ids=(*host_ids,*cap_ids,*leaf_ids)
                if len(set(all_ids))!=len(all_ids):
                    continue
                scopes={
                    str(drawings[i].get("source_viewport_id")
                        or drawings[i].get("viewport_id") or "").strip()
                    for i in all_ids
                }
                if len(scopes)>1:
                    continue
                candidates.append((dist,SourceNativeVSDJoineryWitness(
                    word_index,width_index,width_mm,axis0,band,
                    (end_caps[0][1],end_caps[1][2]),
                    host_ids,cap_ids,leaf_ids,page_index,
                )))
        candidates.sort(key=lambda x:x[0])
        if candidates and (
            len(candidates)==1 or candidates[1][0]-candidates[0][0]>2
        ):
            proposed.append(candidates[0][1])
    owners={}
    for item in proposed:
        for idx in (
            *item.wall_host_path_ids,*item.jamb_cap_path_ids,
            *item.sliding_leaf_path_ids,
        ):
            owners[idx]=owners.get(idx,0)+1
    return tuple(
        item for item in proposed
        if all(owners[idx]==1 for idx in (
            *item.wall_host_path_ids,*item.jamb_cap_path_ids,
            *item.sliding_leaf_path_ids,
        ))
    )
