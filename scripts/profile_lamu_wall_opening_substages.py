#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--pdf", required=True)
parser.add_argument("--page", default="44")
args = parser.parse_args()

repo = Path(args.repo).resolve()
sys.path.insert(0, str(repo))

from pb_source_visibility_authority import SourceVisibilityProducer
import pb_physical_wall_candidate_authority as pwc
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_opening_authority import PhysicalOpeningAuthority

pdf = Path(args.pdf)
payload = pdf.read_bytes()
source_sha = hashlib.sha256(payload).hexdigest()
page_id = str(args.page)

totals = defaultdict(float)
calls = defaultdict(int)

def emit(event, **extra):
    row = {
        "event": event,
        "page_id": page_id,
        "source_sha256": source_sha,
        "totals_s": {k: round(v, 6) for k, v in sorted(totals.items())},
        "calls": dict(sorted(calls.items())),
        **extra,
    }
    print("WALL_OPENING_PROFILE=" + json.dumps(row, sort_keys=True, default=str), flush=True)

def wrap_module(name):
    original = getattr(pwc, name)
    def wrapped(*a, **kw):
        t = time.perf_counter()
        try:
            return original(*a, **kw)
        finally:
            elapsed = time.perf_counter() - t
            totals[name] += elapsed
            calls[name] += 1
            emit(name, elapsed_s=round(elapsed, 6))
    setattr(pwc, name, wrapped)

for name in (
    "_source_page_segments",
    "_producer_owned_points_per_mm",
    "_proven_filled_wall_strips",
    "_filter_proven_wall_strip_geometry",
    "build_wall_graph_for_viewport",
    "classify_junctions",
    "assemble_wall_topology",
    "collect_physical_wall_identities",
    "resolve_physical_wall_equivalence",
    "_producer_wall_strip_relation_overrides",
    "_producer_shared_source_face_relation_overrides",
    "_producer_opening_relation_overrides",
    "_apply_trusted_relation_overrides",
    "_scope_boundary_reason_from_viewports",
):
    if hasattr(pwc, name):
        wrap_module(name)

original_prove = PhysicalOpeningAuthority.prove_existence
def prove_wrapped(self, *a, **kw):
    t = time.perf_counter()
    try:
        return original_prove(self, *a, **kw)
    finally:
        elapsed = time.perf_counter() - t
        totals["PhysicalOpeningAuthority.prove_existence"] += elapsed
        calls["PhysicalOpeningAuthority.prove_existence"] += 1
        if elapsed >= 0.05 or calls["PhysicalOpeningAuthority.prove_existence"] % 1000 == 0:
            emit("PhysicalOpeningAuthority.prove_existence", elapsed_s=round(elapsed, 6))
PhysicalOpeningAuthority.prove_existence = prove_wrapped

source = SourceVisibilityProducer(
    producer_method="lamu-wall-opening-substage-profile",
    producer_version="1",
)

t = time.perf_counter()
published = source.ingest_native_pdf_bytes(
    document_id=f"diag:{source_sha[:24]}",
    source_bytes=payload,
    source_locator=f"memory://{pdf.name}",
    page_ids=(page_id,),
)
emit(
    "source_ingest",
    elapsed_s=round(time.perf_counter() - t, 6),
    visible_observation_count=len(published.visible_observation_ids),
)

t = time.perf_counter()
result = compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=(page_id,),
)
total = time.perf_counter() - t

emit(
    "compose_complete",
    elapsed_s=round(total, 6),
    status=getattr(result.status, "value", str(result.status)),
    reason_codes=list(result.reason_codes),
    wall_scope_count=len(result.wall_scopes),
    opening_binding_count=len(result.opening_bindings),
    host_frame_count=len(result.host_frames),
)
