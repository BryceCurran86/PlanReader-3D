from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import pb_opening_label_dimension_authority as labels
import pb_opening_label_semantic_authority as semantics
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"

def state(value):
    return str(getattr(value,"value",value))

def metrics(line,gap):
    x0,y0,x1,y1=line.bbox
    corners=((x0,y0),(x0,y1),(x1,y0),(x1,y1))
    along=tuple(labels._dot(point,gap.axis) for point in corners)
    amin,amax=min(along),max(along)
    if amax < gap.along_min:
        along_distance=gap.along_min-amax
    elif amin > gap.along_max:
        along_distance=amin-gap.along_max
    else:
        along_distance=0.0
    center=((x0+x1)/2.0,(y0+y1)/2.0)
    cross=labels._dot(center,gap.normal)
    cross_delta=abs(cross-gap.cross_center)
    glyph_height=max(labels._COORD_TOL,min(abs(x1-x0),abs(y1-y0)))
    cross_allowance=max(3.0*glyph_height,2.0*gap.cross_spread)
    return {
        "along_min":amin,
        "along_max":amax,
        "along_distance":along_distance,
        "cross_center":cross,
        "cross_delta":cross_delta,
        "cross_allowance":cross_allowance,
        "axis_overlap":along_distance <= labels._COORD_TOL,
        "cross_allowed":cross_delta <= cross_allowance + labels._COORD_TOL,
        "current_match":labels._label_matches_gap(line,gap),
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
    if semantic is None:
        raise SystemExit("semantic opening enumeration unavailable")

    physical=composition.physical_opening_authority
    openings={}
    selectors={}
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
            selectors[result.existence_record.record_id]=selector

    host_by_id={
        trace.opening_identity_id:trace
        for trace in composition.opening_bindings
        if trace.opening_identity_id and trace.host_wall_id
    }
    if not host_by_id:
        raise SystemExit("no host-bound openings")

    producer=labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    trusted=producer._trusted_text_lines_for_opening(next(iter(openings.values())))
    parsed_870=[]
    for line in trusted:
        parsed=labels.parse_opening_label_dimensions(line.text)
        if parsed is not None and tuple(parsed.dimension_values_mm)==(870.0,):
            parsed_870.append(line)

    category=Counter()
    pattern=Counter()
    rows=[]
    for opening_id in sorted(host_by_id):
        opening=openings.get(opening_id)
        if opening is None:
            continue
        gap=labels._gap_span_for_opening(source,opening)
        label_result=producer.publish_scope(selectors[opening_id])
        semantic_result=semantics.OpeningLabelSemanticProducer.from_source_visibility_producer(
            source
        ).publish_scope(selectors[opening_id])

        if gap is None:
            category["gap_unavailable"]+=1
            rows.append({
                "opening_id":opening_id,
                "host_wall_id":host_by_id[opening_id].host_wall_id,
                "structural_pattern":opening.structural_pattern,
                "aperture_bbox_pt":None if opening.aperture_bbox_pt is None else list(opening.aperture_bbox_pt),
                "category":"gap_unavailable",
                "label_status":state(label_result.status),
                "label_reasons":list(label_result.reason_codes),
                "semantic_status":state(semantic_result.status),
                "semantic_reasons":list(semantic_result.reason_codes),
                "nearest_870":[],
            })
            continue

        candidates=[]
        for line in parsed_870:
            m=metrics(line,gap)
            candidates.append({
                "text":line.text,
                "bbox":list(line.bbox),
                "observation_ids":list(line.observation_ids),
                **m,
                "diagnostic_score":m["along_distance"]+max(0.0,m["cross_delta"]-m["cross_allowance"]),
            })
        candidates.sort(key=lambda r:(r["diagnostic_score"],r["along_distance"],r["cross_delta"],r["bbox"]))
        exact=[row for row in candidates if row["current_match"]]
        if exact:
            cat="current_match"
        elif any(r["axis_overlap"] and not r["cross_allowed"] for r in candidates):
            cat="cross_only_miss"
        elif any((not r["axis_overlap"]) and r["cross_allowed"] for r in candidates):
            cat="axis_only_miss"
        else:
            cat="both_miss"
        category[cat]+=1
        pattern[opening.structural_pattern]+=1
        rows.append({
            "opening_id":opening_id,
            "host_wall_id":host_by_id[opening_id].host_wall_id,
            "structural_pattern":opening.structural_pattern,
            "aperture_bbox_pt":None if opening.aperture_bbox_pt is None else list(opening.aperture_bbox_pt),
            "gap":{
                "axis":list(gap.axis),
                "normal":list(gap.normal),
                "along_min":gap.along_min,
                "along_max":gap.along_max,
                "cross_center":gap.cross_center,
                "cross_spread":gap.cross_spread,
                "along_length":gap.along_max-gap.along_min,
            },
            "category":cat,
            "label_status":state(label_result.status),
            "label_reasons":list(label_result.reason_codes),
            "semantic_status":state(semantic_result.status),
            "semantic_reasons":list(semantic_result.reason_codes),
            "nearest_870":candidates[:3],
        })

    print(json.dumps({
        "source_sha256":actual,
        "snapshot_id":current.snapshot.snapshot_id,
        "physical_opening_count":len(openings),
        "host_bound_count":len(host_by_id),
        "parsed_870_line_count":len(parsed_870),
        "category_counts":dict(category),
        "structural_pattern_counts":dict(pattern),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
