#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_visibility_authority import SourceVisibilityProducer

page_ids = ("41", "42", "43", "44", "45")
pdf = Path(args.pdf)
payload = pdf.read_bytes()
source_sha = hashlib.sha256(payload).hexdigest()

def emit(stage, **extra):
    print("LAMU_SCALE_CACHE_JSON=" + json.dumps({
        "stage": stage,
        "source_sha256": source_sha,
        "pages": list(page_ids),
        **extra,
    }, sort_keys=True, default=str), flush=True)

source = SourceVisibilityProducer(
    producer_method="diag-lamu-scale-page-input-cache",
    producer_version="1",
)

started = time.perf_counter()
published = source.ingest_native_pdf_bytes(
    document_id=f"diag:{source_sha[:24]}",
    source_bytes=payload,
    source_locator=f"memory://{pdf.name}",
    page_ids=page_ids,
)
emit(
    "source_ingest_done",
    elapsed_s=time.perf_counter() - started,
    visible_observation_count=len(published.visible_observation_ids),
    text_observation_count=len(published.text_observation_ids),
)

def selector(page_id):
    return PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
    )

shared = PhysicalScaleProducer.from_source_visibility_producer(source)
shared_rows = []
shared_results = {}
shared_started = time.perf_counter()
for page_id in page_ids:
    t = time.perf_counter()
    result = shared.publish_scope(selector(page_id))
    elapsed = time.perf_counter() - t
    shared_results[page_id] = result
    row = {
        "page_id": page_id,
        "elapsed_s": elapsed,
        "status": getattr(result.status, "value", str(result.status)),
        "reason_codes": list(result.reason_codes),
    }
    shared_rows.append(row)
    emit("shared_page_done", **row)
shared_total = time.perf_counter() - shared_started

fresh_rows = []
fresh_started = time.perf_counter()
for page_id in page_ids:
    t = time.perf_counter()
    result = PhysicalScaleProducer.from_source_visibility_producer(source).publish_scope(
        selector(page_id)
    )
    elapsed = time.perf_counter() - t
    if result != shared_results[page_id]:
        raise AssertionError(f"shared/fresh scale result mismatch on page {page_id}")
    row = {
        "page_id": page_id,
        "elapsed_s": elapsed,
        "status": getattr(result.status, "value", str(result.status)),
        "reason_codes": list(result.reason_codes),
    }
    fresh_rows.append(row)
    emit("fresh_page_done", **row)
fresh_total = time.perf_counter() - fresh_started

emit(
    "complete",
    shared_total_s=shared_total,
    fresh_total_s=fresh_total,
    speedup=(fresh_total / shared_total if shared_total > 0 else None),
    shared_rows=shared_rows,
    fresh_rows=fresh_rows,
)
