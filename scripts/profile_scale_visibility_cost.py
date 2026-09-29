#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector

ap=argparse.ArgumentParser()
ap.add_argument("--pdf",required=True)
ap.add_argument("--pages",required=True)
ap.add_argument("--label",required=True)
args=ap.parse_args()

def pagespec(text):
    out=[]
    for part in text.split(","):
        if "-" in part:
            a,b=map(int,part.split("-",1)); out.extend(range(a,b+1))
        else: out.append(int(part))
    return tuple(out)

payload=Path(args.pdf).read_bytes()
sha=hashlib.sha256(payload).hexdigest()
page_ids=tuple(str(x) for x in pagespec(args.pages))
source=SourceVisibilityProducer(producer_method="scale-visibility-cost",producer_version="1")
t=time.perf_counter()
published=source.ingest_native_pdf_bytes(
    document_id=f"scale-diag:{sha[:24]}",source_bytes=payload,
    source_locator="memory://scale-diag.pdf",page_ids=page_ids)
print(json.dumps({"event":"ingest","label":args.label,"elapsed_s":time.perf_counter()-t,
                  "visible_total":len(published.visible_observation_ids)}),flush=True)
producer=PhysicalScaleProducer.from_source_visibility_producer(source)
for page_id in page_ids:
    refreshed=source.published_snapshot_for_revision(published.revision.revision_id)
    sel=PhysicalScaleSelector(
        document_id=refreshed.revision.document_id,
        revision_id=refreshed.revision.revision_id,
        source_sha256=refreshed.revision.source_sha256,
        snapshot_id=refreshed.snapshot.snapshot_id,
        page_id=page_id)
    t=time.perf_counter()
    rows=producer._visible_segments(sel,refreshed)
    print(json.dumps({"event":"visible_segments","label":args.label,"page_id":page_id,
                      "elapsed_s":time.perf_counter()-t,"normalized_count":len(rows)}),flush=True)
