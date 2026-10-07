from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pb_opening_label_dimension_authority as labels
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"

def state(v): return str(getattr(v,"value",v))

def metric(line,gap):
    x0,y0,x1,y1=line.bbox
    corners=((x0,y0),(x0,y1),(x1,y0),(x1,y1))
    along=[labels._dot(p,gap.axis) for p in corners]
    amin,amax=min(along),max(along)
    if amax < gap.along_min:
        ad=gap.along_min-amax
    elif amin > gap.along_max:
        ad=amin-gap.along_max
    else:
        ad=0.0
    center=((x0+x1)/2.0,(y0+y1)/2.0)
    cross=labels._dot(center,gap.normal)
    cd=abs(cross-gap.cross_center)
    glyph=max(labels._COORD_TOL,min(abs(x1-x0),abs(y1-y0)))
    allow=max(3.0*glyph,2.0*gap.cross_spread)
    return {
        "along_distance":ad,
        "cross_delta":cd,
        "cross_allowance":allow,
        "axis_overlap":ad <= labels._COORD_TOL,
        "cross_allowed":cd <= allow + labels._COORD_TOL,
        "current_match":labels._label_matches_gap(line,gap),
        "diagnostic_score":ad+max(0.0,cd-allow),
    }

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    assert actual==EXPECTED_SHA
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{actual[:32]}",
        source_bytes=data,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    assert current is not None
    semantic=composition.semantic_enumeration_result.record
    if semantic is None: raise SystemExit("semantic enumeration unavailable")
    physical=composition.physical_opening_authority
    openings={}
    for obs_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        result=physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.existence_record is not None
            and str(result.existence_record.page_id)==PAGE_ID
        ):
            openings[result.existence_record.record_id]=result.existence_record
    host_by_id={
        trace.opening_identity_id:trace
        for trace in composition.opening_bindings
        if trace.opening_identity_id
    }
    producer=labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    trusted=producer._trusted_text_lines_for_opening(next(iter(openings.values())))
    lines=[]
    for line in trusted:
        parsed=labels.parse_opening_label_dimensions(line.text)
        if parsed is not None and tuple(parsed.dimension_values_mm)==(870.0,):
            lines.append(line)

    rows=[]
    match_count_hist=Counter()
    for line in sorted(lines,key=lambda x:(x.bbox,x.observation_ids)):
        candidates=[]
        for opening_id,opening in openings.items():
            gap=labels._gap_span_for_opening(source,opening)
            if gap is None:
                continue
            m=metric(line,gap)
            trace=host_by_id.get(opening_id)
            candidates.append({
                "opening_id":opening_id,
                "structural_pattern":opening.structural_pattern,
                "aperture_bbox_pt":None if opening.aperture_bbox_pt is None else list(opening.aperture_bbox_pt),
                "host_bound":bool(trace is not None and trace.host_wall_id),
                "host_status":None if trace is None else state(trace.status),
                "host_reason_codes":[] if trace is None else list(trace.reason_codes),
                **m,
            })
        candidates.sort(key=lambda r:(r["diagnostic_score"],r["along_distance"],r["cross_delta"],r["opening_id"]))
        exact=[r for r in candidates if r["current_match"]]
        match_count_hist[len(exact)]+=1
        rows.append({
            "text":line.text,
            "bbox":list(line.bbox),
            "observation_ids":list(line.observation_ids),
            "exact_physical_owner_count":len(exact),
            "exact_physical_owners":exact,
            "closest_physical_candidates":candidates[:6],
        })
    print(json.dumps({
        "source_sha256":actual,
        "physical_opening_count":len(openings),
        "host_bound_count":sum(1 for t in composition.opening_bindings if t.host_wall_id),
        "parsed_870_line_count":len(lines),
        "label_exact_owner_count_histogram":dict(sorted(match_count_hist.items())),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
