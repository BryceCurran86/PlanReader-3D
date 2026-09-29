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
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer

pdf = Path(args.pdf)
payload = pdf.read_bytes()
source_sha = hashlib.sha256(payload).hexdigest()
page_id = "44"

stats = {
    "tick_queries": 0,
    "tick_query_candidates": 0,
    "tick_query_max": 0,
    "bar_calls": 0,
    "bar_total_s": 0.0,
}


def emit(stage: str, **extra) -> None:
    print(
        "LAMU_P44_SCALE_TICK_JSON="
        + json.dumps(
            {
                "stage": stage,
                "page_id": page_id,
                "source_sha256": source_sha,
                "stats": dict(stats),
                **extra,
            },
            sort_keys=True,
            default=str,
        ),
        flush=True,
    )


original_candidates = scale_module._TickEndpointIndex.candidates


def counted_candidates(self, baseline, endpoint):
    result = original_candidates(self, baseline, endpoint)
    stats["tick_queries"] += 1
    stats["tick_query_candidates"] += len(result)
    stats["tick_query_max"] = max(stats["tick_query_max"], len(result))
    return result


scale_module._TickEndpointIndex.candidates = counted_candidates

original_bars = scale_module._bar_candidates


def timed_bars(segments, words):
    stats["bar_calls"] += 1
    emit("bar_candidates_start", segment_count=len(segments), word_count=len(words))
    started = time.perf_counter()
    result = original_bars(segments, words)
    elapsed = time.perf_counter() - started
    stats["bar_total_s"] += elapsed
    emit(
        "bar_candidates_done",
        segment_count=len(segments),
        word_count=len(words),
        candidate_count=len(result),
        elapsed_s=elapsed,
    )
    return result


scale_module._bar_candidates = timed_bars

faulthandler.enable(file=sys.stderr, all_threads=True)
faulthandler.dump_traceback_later(60, repeat=True, file=sys.stderr)

source = SourceVisibilityProducer(
    producer_method="diag-lamu-p44-scale-tick-gate",
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

emit("scale_publish_start")
started = time.perf_counter()
scale_result = producer.publish_scope(selector)
emit(
    "scale_publish_done",
    elapsed_s=time.perf_counter() - started,
    status=getattr(scale_result.status, "value", str(scale_result.status)),
    reason_codes=list(scale_result.reason_codes),
)

emit("wall_candidate_start")
started = time.perf_counter()
wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
    source,
    page_ids=(page_id,),
)
emit(
    "wall_candidate_done",
    elapsed_s=time.perf_counter() - started,
)

authority = wall_producer.authority()
refreshed = source.published_snapshot_for_revision(published.revision.revision_id)
if refreshed is None:
    raise RuntimeError("published snapshot disappeared")

wall_selector = authority.selector_for_decision_scope(
    document_id=refreshed.revision.document_id,
    revision_id=refreshed.revision.revision_id,
    source_sha256=refreshed.revision.source_sha256,
    snapshot_id=refreshed.snapshot.snapshot_id,
    page_id=page_id,
    decision_scope_id=f"wall-source:page-{page_id}",
)
wall_result = authority.resolve_scope(wall_selector) if wall_selector is not None else None
equivalence = getattr(wall_result, "equivalence", None)
audit = getattr(equivalence, "candidate_pair_audit", None)

emit(
    "complete",
    refreshed_snapshot_id=refreshed.snapshot.snapshot_id,
    visible_observation_count=len(refreshed.visible_observation_ids),
    authority_type=type(authority).__name__,
    wall_candidate_count=(len(wall_result.records) if wall_result is not None else None),
    equivalence_total_pairs=(getattr(audit, "total_pairs", None) if audit is not None else None),
    equivalence_excluded_pairs=(getattr(audit, "excluded_pairs", None) if audit is not None else None),
    equivalence_classified_pairs=(
        len(getattr(equivalence, "pair_classifications", ()) or ())
        if equivalence is not None
        else None
    ),
)
faulthandler.cancel_dump_traceback_later()
