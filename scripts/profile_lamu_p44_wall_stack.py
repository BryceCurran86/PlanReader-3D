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
parser.add_argument("--page", default="44")
args = parser.parse_args()

repo = Path(args.repo).resolve()
sys.path.insert(0, str(repo))

from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer

pdf = Path(args.pdf)
payload = pdf.read_bytes()
source_sha = hashlib.sha256(payload).hexdigest()
page_id = str(args.page)

def emit(stage: str, **extra) -> None:
    row = {
        "stage": stage,
        "page_id": page_id,
        "source_sha256": source_sha,
        **extra,
    }
    print("LAMU_P44_STACK_JSON=" + json.dumps(row, sort_keys=True, default=str), flush=True)

faulthandler.enable(file=sys.stderr, all_threads=True)
faulthandler.dump_traceback_later(60, repeat=True, file=sys.stderr)

source = SourceVisibilityProducer(
    producer_method="diag-lamu-p44-wall-stack",
    producer_version="1",
)

emit("source_ingest_start")
t0 = time.perf_counter()
published = source.ingest_native_pdf_bytes(
    document_id=f"diag:{source_sha[:24]}",
    source_bytes=payload,
    source_locator=f"memory://{pdf.name}",
    page_ids=(page_id,),
)
emit(
    "source_ingest_done",
    elapsed_s=time.perf_counter() - t0,
    visible_observation_count=len(published.visible_observation_ids),
    revision_id=published.revision.revision_id,
    snapshot_id=published.snapshot.snapshot_id,
)

emit("wall_producer_start")
t0 = time.perf_counter()
wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
    source,
    page_ids=(page_id,),
)
emit("wall_producer_done", elapsed_s=time.perf_counter() - t0)

emit("wall_authority_start")
t0 = time.perf_counter()
wall_authority = wall_producer.authority()
emit("wall_authority_done", elapsed_s=time.perf_counter() - t0)

refreshed = source.published_snapshot_for_revision(published.revision.revision_id)
if refreshed is None:
    raise RuntimeError("published snapshot disappeared")

emit(
    "complete",
    refreshed_snapshot_id=refreshed.snapshot.snapshot_id,
)

faulthandler.cancel_dump_traceback_later()
