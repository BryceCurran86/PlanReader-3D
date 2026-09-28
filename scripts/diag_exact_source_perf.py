#!/usr/bin/env python3
"""TEST-ONLY exact-source performance and authority-invariance diagnostic."""
from __future__ import annotations

import argparse
import cProfile
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import pstats
import resource
import time
from typing import Any, Mapping

from pb_live_external_physical_net_wall_publication import (
    compose_live_external_physical_net_wall_publication,
)
from pb_live_gross_wall_geometry_composition import compose_live_gross_wall_geometry
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_whole_wall_role_composition import compose_live_whole_wall_roles
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_scale_authority import _VisibleSegment, _coalesce_retraced_segments
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    VISIBLE_SOURCE_OBSERVATION_EXISTS,
)


def _status(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    raw = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _timed(fn):
    start = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - start


def _profiled(fn):
    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    value = fn()
    profiler.disable()
    elapsed = time.perf_counter() - start
    stats = pstats.Stats(profiler)
    rows = []
    for (filename, line, name), (cc, nc, tt, ct, _callers) in stats.stats.items():
        rows.append({
            "file": str(filename),
            "line": int(line),
            "function": str(name),
            "primitive_calls": int(cc),
            "total_calls": int(nc),
            "self_seconds": float(tt),
            "cumulative_seconds": float(ct),
        })
    rows.sort(key=lambda row: (-row["cumulative_seconds"], -row["self_seconds"], row["file"], row["line"]))
    return value, elapsed, rows[:80]


def _scale_profile(source, published, page_ids):
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot disappeared")
    authority = source.authority()
    wanted = set(page_ids)
    by_page = {page_id: [] for page_id in page_ids}

    started = time.perf_counter()
    for observation_id in current.visible_observation_ids:
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == VISIBLE_SOURCE_OBSERVATION_EXISTS
            and observation is not None
            and observation.page_id in wanted
            and len(observation.geometry) == 4
        ):
            x0, y0, x1, y1 = (float(v) for v in observation.geometry)
            by_page[observation.page_id].append(
                _VisibleSegment(
                    observation_id=observation_id,
                    source_primitive_ref=observation.source_primitive_ref,
                    start=(x0, y0),
                    end=(x1, y1),
                )
            )
    collection_s = time.perf_counter() - started

    pages = []
    total_normalization = 0.0
    for page_id in page_ids:
        raw = tuple(by_page[page_id])
        started = time.perf_counter()
        normalized = _coalesce_retraced_segments(raw)
        elapsed = time.perf_counter() - started
        total_normalization += elapsed
        pages.append({
            "page_id": page_id,
            "visible_segment_count": len(raw),
            "normalized_segment_count": len(normalized),
            "normalization_seconds": elapsed,
            "normalized_digest": _digest([
                (
                    s.observation_id,
                    s.source_primitive_ref,
                    s.start,
                    s.end,
                    s.duplicate_observation_ids,
                )
                for s in normalized
            ]),
        })
    return {
        "visibility_collection_seconds": collection_s,
        "normalization_seconds_total": total_normalization,
        "visible_segment_count_total": sum(p["visible_segment_count"] for p in pages),
        "normalized_segment_count_total": sum(p["normalized_segment_count"] for p in pages),
        "pages": pages,
    }


def _authority_snapshot(source, published, wall_opening, physical_void, gross, roles, publication):
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot disappeared")
    wall_authority = wall_opening.physical_wall_candidate_authority
    wall_pages = []
    for trace in wall_opening.wall_scopes:
        selector = wall_authority.selector_for_decision_scope(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=trace.page_id,
            decision_scope_id=f"wall-source:page-{trace.page_id}",
        )
        resolved = wall_authority.resolve_scope(selector) if selector is not None else None
        eq = None if resolved is None else resolved.equivalence
        wall_pages.append({
            "page_id": trace.page_id,
            "status": _status(trace.status),
            "reason_codes": list(trace.reason_codes),
            "scope_complete": bool(trace.scope_complete),
            "wall_candidate_ids": [] if resolved is None else [r.wall_candidate_id for r in resolved.records],
            "representative_wall_ids": [] if eq is None else list(eq.representative_wall_ids),
            "ambiguous_wall_ids": [] if eq is None else list(eq.ambiguous_wall_ids),
            "abstained_wall_ids": [] if eq is None else list(eq.abstained_wall_ids),
            "equivalence_groups": [] if eq is None else [list(g) for g in eq.equivalence_groups],
            "pair_classifications": [] if eq is None else [list(p) for p in eq.pair_classifications],
            "scope_reason_codes": [] if resolved is None else list(resolved.reason_codes),
        })

    snapshot = {
        "wall_opening": {
            "status": _status(wall_opening.status),
            "reason_codes": list(wall_opening.reason_codes),
            "pages": wall_pages,
            "opening_bindings": [
                {
                    "opening_identity_id": t.opening_identity_id,
                    "representative_observation_id": t.representative_observation_id,
                    "page_id": t.page_id,
                    "status": _status(t.status),
                    "reason_codes": list(t.reason_codes),
                    "record_id": t.record_id,
                    "host_wall_id": t.host_wall_id,
                    "member_wall_candidate_ids": list(t.member_wall_candidate_ids),
                }
                for t in wall_opening.opening_bindings
            ],
            "host_frames": [
                {
                    "opening_identity_id": t.opening_identity_id,
                    "status": _status(t.status),
                    "reason_codes": list(t.reason_codes),
                    "record_id": t.record_id,
                    "host_wall_id": t.host_wall_id,
                    "whole_wall_candidate_ids": list(t.whole_wall_candidate_ids),
                }
                for t in wall_opening.host_frames
            ],
        },
        "physical_void": {
            "status": _status(physical_void.status),
            "reason_codes": list(physical_void.reason_codes),
            "traces": [_jsonable(t) for t in physical_void.traces],
        },
        "gross": {
            "status": _status(gross.status),
            "reason_codes": list(gross.reason_codes),
            "traces": [_jsonable(t) for t in gross.traces],
        },
        "roles": {
            "status": _status(roles.status),
            "reason_codes": list(roles.reason_codes),
            "traces": [_jsonable(t) for t in roles.traces],
        },
        "publication": {
            "status": _status(publication.status),
            "reason_codes": list(publication.reason_codes),
            "external_wall_ids": list(publication.external_wall_ids),
            "gross_geometry_record_ids": list(publication.gross_geometry_record_ids),
            "whole_wall_role_record_ids": list(publication.whole_wall_role_record_ids),
            "physical_void_record_ids": list(publication.physical_void_record_ids),
            "opening_universe_record_ids": list(publication.opening_universe_record_ids),
            "quantity_evidence": _jsonable(publication.quantity_evidence),
        },
    }
    snapshot["digest"] = _digest(snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--page-start", required=True, type=int, help="1-based inclusive")
    parser.add_argument("--page-end", required=True, type=int, help="1-based inclusive")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    page_ids = tuple(str(i) for i in range(args.page_start, args.page_end + 1))
    page_indices = tuple(i - 1 for i in range(args.page_start, args.page_end + 1))
    document_id = f"diag:{args.project}:{source_sha[:24]}"

    source = SourceVisibilityProducer(
        producer_method="test-only-exact-source-performance-diagnostic",
        producer_version="1",
    )
    published, ingest_s = _timed(lambda: source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{path.name}",
        page_ids=page_ids,
    ))
    wall_opening, wall_opening_s = _timed(lambda: compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=page_ids,
    ))
    scale = _scale_profile(source, published, page_ids)
    physical_void, physical_void_s = _timed(lambda: compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    ))
    gross, gross_s = _timed(lambda: compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    ))
    roles, roles_s = _timed(lambda: compose_live_whole_wall_roles(
        gross_wall_composition=gross,
    ))
    publication, publication_s = _timed(lambda: compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=roles,
    ))
    authority_snapshot = _authority_snapshot(
        source, published, wall_opening, physical_void, gross, roles, publication
    )

    extractor = GenericPlanReaderExtractor()
    predictions, commercial_s, top_profile = _profiled(lambda: extractor.extract_from_pdf(
        path,
        pages=page_indices,
        collect_item35_shadow=False,
    ))
    prediction_payload = sorted(
        (_jsonable(p.to_dict()) for p in predictions),
        key=lambda row: (
            str(row.get("tag")),
            str(row.get("source_page")),
            str(row.get("description")),
        ),
    )

    result = {
        "project": args.project,
        "source_sha256": source_sha,
        "page_start": args.page_start,
        "page_end": args.page_end,
        "timings_seconds": {
            "source_ingest": ingest_s,
            "wall_opening_composition": wall_opening_s,
            "scale_visibility_collection": scale["visibility_collection_seconds"],
            "scale_normalization": scale["normalization_seconds_total"],
            "physical_opening_void": physical_void_s,
            "gross_wall": gross_s,
            "role": roles_s,
            "net_wall_publication": publication_s,
            "commercial_extraction": commercial_s,
        },
        "scale": scale,
        "authority_snapshot": authority_snapshot,
        "authority_digest": authority_snapshot["digest"],
        "commercial_prediction_count": len(prediction_payload),
        "commercial_predictions": prediction_payload,
        "commercial_prediction_digest": _digest(prediction_payload),
        "extractor_physical_net_wall_live": _jsonable(extractor.physical_net_wall_live),
        "extractor_status": _jsonable(extractor.extraction_status),
        "profile_top_cumulative": top_profile,
        "process_peak_rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "project": result["project"],
        "source_sha256": result["source_sha256"],
        "visible_segment_count_total": scale["visible_segment_count_total"],
        "normalized_segment_count_total": scale["normalized_segment_count_total"],
        "scale_normalization_seconds": scale["normalization_seconds_total"],
        "wall_opening_seconds": wall_opening_s,
        "commercial_extraction_seconds": commercial_s,
        "authority_digest": result["authority_digest"],
        "commercial_prediction_digest": result["commercial_prediction_digest"],
        "peak_rss_kb": result["process_peak_rss_kb"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
