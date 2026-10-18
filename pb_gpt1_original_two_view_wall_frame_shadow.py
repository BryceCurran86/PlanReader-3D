"""Source-witnessed two-view physical wall ring consistency (shadow).

One PDF page cannot claim the same physical room as another merely by label,
bounding box, grid translation or higher geometric overlap. Every independently
source-owned physical wall pair must form a complete ring on both sheets.

This validation never creates wall equivalence; that must be established
upstream by GPT2/W4. It checks whether already-owned wall pairs are mutually
consistent under one rigid, non-scaling original-PDF transform.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalCrossSheetWallPair:
    independently_authenticated_physical_wall_id: str
    room_page_source_stroke_ids: tuple[str,...]
    finish_page_source_stroke_ids: tuple[str,...]
    room_page_start: tuple[float,float]
    room_page_end: tuple[float,float]
    finish_page_start: tuple[float,float]
    finish_page_end: tuple[float,float]
    wall_equivalence_receipt_id: str


@dataclass(frozen=True)
class SourceWallRingFrameShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    original_finish_to_room_rigid_transform: tuple[float,float,float,float] | None
    maximum_native_source_endpoint_disagreement_pt: float | None
    matched_original_wall_ids: tuple[str,...]
    matched_wall_equivalence_receipts: tuple[str,...]
    diagnostic_only: bool = True


def _point(raw):
    if type(raw) not in (tuple,list) or len(raw)!=2:
        return None
    if any(type(c) not in (int,float) for c in raw):
        return None
    try:p=tuple(float(c) for c in raw)
    except (TypeError,ValueError,OverflowError):return None
    return p if all(math.isfinite(x) for x in p) else None


def _ids(values):
    return (type(values) in (tuple,list) and bool(values)
            and len(set(values))==len(values)
            and all(type(v) is str and v and v==v.strip() for v in values))


def verify_source_wall_pair_rigid_frame_shadow(
    pairs: tuple[OriginalCrossSheetWallPair,...],
    *,
    original_native_precision_pt: float = 0.06,
) -> SourceWallRingFrameShadow:
    """No best translation search: every wall/endpoint is explicitly paired."""
    def block(reason):
        return SourceWallRingFrameShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),None,None,(),()
        )
    if (
        type(pairs) not in (tuple,list) or len(pairs)<3
        or type(original_native_precision_pt) not in (int,float)
        or not math.isfinite(float(original_native_precision_pt))
        or not 0<=original_native_precision_pt<=0.1
    ):
        return block("original_source_crosssheet_wall_universe_unavailable")
    walls=set();receipts=set();room_ink=set();finish_ink=set()
    room_edges=[];finish_edges=[]
    for pair in pairs:
        if (
            type(pair) is not OriginalCrossSheetWallPair
            or not _ids((pair.independently_authenticated_physical_wall_id,
                         pair.wall_equivalence_receipt_id))
            or pair.independently_authenticated_physical_wall_id in walls
            or pair.wall_equivalence_receipt_id in receipts
            or not _ids(pair.room_page_source_stroke_ids)
            or not _ids(pair.finish_page_source_stroke_ids)
            or room_ink.intersection(pair.room_page_source_stroke_ids)
            or finish_ink.intersection(pair.finish_page_source_stroke_ids)
        ):
            return block("original_source_crosssheet_wall_pair_identity_conflict")
        a,b=_point(pair.room_page_start),_point(pair.room_page_end)
        x,y=_point(pair.finish_page_start),_point(pair.finish_page_end)
        if a is None or b is None or x is None or y is None or a==b or x==y:
            return block("original_source_crosssheet_wall_endpoint_unavailable")
        room_edges.append((a,b));finish_edges.append((x,y))
        walls.add(pair.independently_authenticated_physical_wall_id)
        receipts.add(pair.wall_equivalence_receipt_id)
        room_ink.update(pair.room_page_source_stroke_ids)
        finish_ink.update(pair.finish_page_source_stroke_ids)
    n=len(pairs)
    for edges in (room_edges,finish_edges):
        if any(edges[i][1]!=edges[(i+1)%n][0] for i in range(n)):
            return block("original_source_crosssheet_structural_ring_not_closed")
        if len(set(a for a,b in edges))!=n:
            return block("original_source_crosssheet_structural_ring_self_touching")
    (a,b),(x,y)=room_edges[0],finish_edges[0]
    room=(b[0]-a[0],b[1]-a[1])
    finish=(y[0]-x[0],y[1]-x[1])
    m=math.hypot(*room);f=math.hypot(*finish)
    if not all(math.isfinite(v) and v>0 for v in (m,f)):
        return block("original_source_crosssheet_structural_frame_unavailable")
    if abs(m-f)>original_native_precision_pt:
        return block("original_source_crosssheet_structural_scale_conflict")
    cos=(room[0]*finish[0]+room[1]*finish[1])/(m*f)
    sin=(room[1]*finish[0]-room[0]*finish[1])/(m*f)
    scale=math.hypot(cos,sin)
    if not math.isfinite(scale) or abs(scale-1)>1e-10:
        return block("original_source_crosssheet_structural_frame_unavailable")
    cos/=scale;sin/=scale
    tx=a[0]-(cos*x[0]-sin*x[1])
    ty=a[1]-(sin*x[0]+cos*x[1])
    def transform(p):
        return (cos*p[0]-sin*p[1]+tx,sin*p[0]+cos*p[1]+ty)
    max_residual=max(
        math.dist(room_point,transform(finish_point))
        for (ra,rb),(fa,fb) in zip(room_edges,finish_edges)
        for room_point,finish_point in ((ra,fa),(rb,fb))
    )
    if max_residual>original_native_precision_pt+1e-9:
        return block("original_source_crosssheet_structural_wall_competition")
    return SourceWallRingFrameShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_source_full_structural_wall_frame_shadow_only",),
        (cos,sin,tx,ty),max_residual,
        tuple(sorted(walls)),tuple(sorted(receipts)),
    )
