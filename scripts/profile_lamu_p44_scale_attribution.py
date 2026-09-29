#!/usr/bin/env python3
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--pdf", required=True)
args = parser.parse_args()

repo = Path(args.repo).resolve()
sys.path.insert(0, str(repo))

import pb_physical_scale_authority as scale_module
import pb_viewport_segmentation as viewport_module
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_visibility_authority import SourceVisibilityProducer

pdf = Path(args.pdf)
payload = pdf.read_bytes()
source_sha = hashlib.sha256(payload).hexdigest()
page_id = "44"
calls: dict[str, dict[str, float | int]] = {}


def emit(kind: str, **extra) -> None:
    print(
        "LAMU_SCALE_ATTR_JSON="
        + json.dumps({"kind": kind, "page_id": page_id, **extra}, sort_keys=True, default=str),
        flush=True,
    )


def timed(name, fn, *, sample_every: int | None = None):
    def wrapper(*a, **k):
        row = calls.setdefault(name, {"calls": 0, "total_s": 0.0, "max_s": 0.0})
        call_no = int(row["calls"]) + 1
        sampled = sample_every is None or call_no == 1 or call_no % sample_every == 0
        if sampled:
            emit("stage_start", name=name, call=call_no)
        started = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            elapsed = time.perf_counter() - started
            row["calls"] = call_no
            row["total_s"] = float(row["total_s"]) + elapsed
            row["max_s"] = max(float(row["max_s"]), elapsed)
            if sampled:
                emit(
                    "stage_end",
                    name=name,
                    call=call_no,
                    elapsed_s=elapsed,
                    total_s=row["total_s"],
                    max_s=row["max_s"],
                )
    return wrapper


for attr in (
    "calibrate_viewport_layout",
    "_text_fragments",
    "extract_view_title_anchors",
    "extract_vector_frames",
    "_frame_resolved_viewports",
    "_derived_partitions",
    "_extract_scales_for_bbox",
):
    original = getattr(viewport_module, attr)
    setattr(viewport_module, attr, timed(f"viewport.{attr}", original))

viewport_module._frame_looks_like_table = timed(
    "viewport._frame_looks_like_table",
    viewport_module._frame_looks_like_table,
    sample_every=100,
)
scale_module.segment_page_viewports = timed(
    "scale.segment_page_viewports",
    scale_module.segment_page_viewports,
)

faulthandler.enable(file=sys.stderr, all_threads=True)
faulthandler.dump_traceback_later(60, repeat=True, file=sys.stderr)

source = SourceVisibilityProducer(
    producer_method="diag-lamu-p44-scale-attribution",
    producer_version="1",
)
emit("source_ingest_start")
started = time.perf_counter()
published = source.ingest_native_pdf_bytes(
    document_id=f"diag:{source_sha[:24]}",
    source_bytes=payload,
    source_locator=f"memory://{pdf.name}",
    page_ids=(page_id,),
)
emit(
    "source_ingest_done",
    elapsed_s=time.perf_counter() - started,
    visible_observation_count=len(published.visible_observation_ids),
)

producer = PhysicalScaleProducer.from_source_visibility_producer(source)
selector = PhysicalScaleSelector(
    document_id=published.revision.document_id,
    revision_id=published.revision.revision_id,
    source_sha256=published.revision.source_sha256,
    snapshot_id=published.snapshot.snapshot_id,
    page_id=page_id,
)

emit("publish_scope_start")
started = time.perf_counter()
result = producer.publish_scope(selector)
elapsed = time.perf_counter() - started
emit(
    "publish_scope_done",
    elapsed_s=elapsed,
    status=getattr(result.status, "value", str(result.status)),
    reason_codes=list(result.reason_codes),
    calls=calls,
)
faulthandler.cancel_dump_traceback_later()
