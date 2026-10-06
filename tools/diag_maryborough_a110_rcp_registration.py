from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_PAGE = "7"   # A110 diagnostic address only
TARGET_PAGE = "9"   # RCP diagnostic address only


def _length(g):
    x1,y1,x2,y2 = map(float,g)
    return math.hypot(x2-x1,y2-y1)


def _orientation(g):
    x1,y1,x2,y2 = map(float,g)
    dx=x2-x1; dy=y2-y1
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    angle=abs(math.degrees(math.atan2(dy,dx))) % 180.0
    if min(angle, 180.0-angle) <= 1.0:
        return "H"
    if abs(angle-90.0) <= 1.0:
        return "V"
    return "O"


def _midpoint(g):
    x1,y1,x2,y2 = map(float,g)
    return ((x1+x2)*0.5,(y1+y2)*0.5)


def _page_records(source, published, page_id):
    auth=source.authority()
    rows=[]
    for oid in published.visible_observation_ids:
        res=auth.resolve_visible(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        ))
        rec=res.observation
        if (
            res.status is EvidenceResolutionStatus.CORROBORATED
            and rec is not None
            and str(rec.page_id)==str(page_id)
            and rec.observation_kind=="native_pdf_segment"
            and len(rec.geometry)==4
        ):
            rows.append(rec)
    return rows


def _long_axis(rows):
    axis=[r for r in rows if _orientation(r.geometry) in {"H","V"}]
    if not axis:
        return []
    lengths=sorted(_length(r.geometry) for r in axis)
    q_index=max(0,min(len(lengths)-1,int(0.70*(len(lengths)-1))))
    threshold=max(24.0,lengths[q_index])
    keep=[r for r in axis if _length(r.geometry)>=threshold]
    keep.sort(key=lambda r:(-_length(r.geometry),r.observation_id))
    return keep[:300]


def _candidate_scales(src,tgt):
    src_by=defaultdict(list); tgt_by=defaultdict(list)
    for r in src: src_by[_orientation(r.geometry)].append(r)
    for r in tgt: tgt_by[_orientation(r.geometry)].append(r)
    counts=Counter()
    for orient in ("H","V"):
        for a in src_by[orient][:160]:
            la=_length(a.geometry)
            for b in tgt_by[orient][:160]:
                lb=_length(b.geometry)
                if la<=0 or lb<=0: continue
                ratio=lb/la
                if 0.5 <= ratio <= 2.0:
                    counts[round(ratio,3)] += 1
    # Always test identity scale because architectural plan/RCP sheets often
    # share the same printed scale. It still has to earn its match score.
    counts[1.0] += 1
    return [scale for scale,_ in counts.most_common(12)]


def _candidate_transforms(src,tgt,scale):
    by_t=defaultdict(list)
    for r in tgt:
        by_t[_orientation(r.geometry)].append(r)
    buckets=Counter()
    for a in src[:220]:
        oa=_orientation(a.geometry)
        la=_length(a.geometry)*scale
        amx,amy=_midpoint(a.geometry)
        for b in by_t[oa][:220]:
            lb=_length(b.geometry)
            if max(la,lb) <= 0:
                continue
            if abs(la-lb) > max(1.5,0.01*max(la,lb)):
                continue
            bmx,bmy=_midpoint(b.geometry)
            tx=bmx-scale*amx
            ty=bmy-scale*amy
            buckets[(round(tx,1),round(ty,1))]+=1
    return [(scale,tx,ty,c) for (tx,ty),c in buckets.most_common(10)]


def _score(src,tgt,scale,tx,ty):
    # One-to-one greedy match over long axis-aligned primitives.
    remaining=set(range(len(tgt)))
    matched=[]
    for si,a in enumerate(src):
        oa=_orientation(a.geometry)
        amx,amy=_midpoint(a.geometry)
        al=_length(a.geometry)*scale
        x=scale*amx+tx; y=scale*amy+ty
        best=None
        for ti in tuple(remaining):
            b=tgt[ti]
            if _orientation(b.geometry)!=oa:
                continue
            bl=_length(b.geometry)
            if abs(al-bl)>max(1.5,0.01*max(al,bl)):
                continue
            bx,by=_midpoint(b.geometry)
            dist=math.hypot(x-bx,y-by)
            if dist>1.5:
                continue
            key=(dist,abs(al-bl),ti)
            if best is None or key<best[0]:
                best=(key,ti)
        if best is not None:
            ti=best[1]
            remaining.remove(ti)
            matched.append((si,ti))
    return {
        "matched_count":len(matched),
        "source_fraction":len(matched)/max(1,len(src)),
        "target_fraction":len(matched)/max(1,len(tgt)),
    }


def main():
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="gpt2-a110-rcp-registration-diag",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(SOURCE_PAGE,TARGET_PAGE),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    src_all=_page_records(source,current,SOURCE_PAGE)
    tgt_all=_page_records(source,current,TARGET_PAGE)
    src=_long_axis(src_all)
    tgt=_long_axis(tgt_all)

    candidates=[]
    for scale in _candidate_scales(src,tgt):
        for s,tx,ty,votes in _candidate_transforms(src,tgt,scale):
            score=_score(src,tgt,s,tx,ty)
            candidates.append({
                "scale":s,
                "tx":tx,
                "ty":ty,
                "translation_votes":votes,
                **score,
            })
    candidates.sort(
        key=lambda row:(
            -row["matched_count"],
            -row["translation_votes"],
            abs(row["scale"]-1.0),
            abs(row["tx"])+abs(row["ty"]),
        )
    )
    top=candidates[:12]
    unique=False
    if top:
        first=top[0]["matched_count"]
        second=top[1]["matched_count"] if len(top)>1 else 0
        unique=(
            first >= 12
            and top[0]["source_fraction"] >= 0.08
            and first >= second + 3
        )

    print(json.dumps({
        "source_sha256":sha,
        "mode":"DIAGNOSTIC_ONLY_NATIVE_VECTOR_PLAN_TO_RCP_REGISTRATION",
        "source_page":SOURCE_PAGE,
        "target_page":TARGET_PAGE,
        "source_segment_count":len(src_all),
        "target_segment_count":len(tgt_all),
        "source_long_axis_count":len(src),
        "target_long_axis_count":len(tgt),
        "candidate_transform_count":len(candidates),
        "unique_transform_by_diagnostic_rule":unique,
        "top_candidates":top,
    },indent=2,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
