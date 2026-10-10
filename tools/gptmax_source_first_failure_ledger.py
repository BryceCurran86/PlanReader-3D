"""Read-only physical-opening first-failure and raster candidate audit.

Consumes the *real production* JSON output from diag_gptmax_source_authority_stages.
Opening existence identities, source-backed host evidence, source-frame evidence,
and registered *raw* raster gap candidates are DISTINCT universes. In
particular, unresolved raw candidates must never be joined to physical opening
ids by labels, physical distance, index, or matching counts.

This ledger NEVER certifies whole-building opening-count completeness,
creates physical openings, invents host geometry, deduces scale, publishes
QuantityEvidence, or scores frozen V2 denominators.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def _rows_by_identity(records, name):
    if not isinstance(records, list):
        raise ValueError(f"{name}: source record array missing")
    result = {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError(f"{name}: malformed record")
        key = row.get("opening_identity_id")
        if not isinstance(key, str) or not key.strip() or key in result:
            raise ValueError(f"{name}: missing/duplicated physical identity")
        result[key] = row
    return result


def _reason_codes(row):
    reason = row.get("reason_codes", ())
    if not isinstance(reason, (list, tuple)) or any(
        not isinstance(k, str) or not k for k in reason
    ):
        raise ValueError("invalid source reason codes")
    return tuple(reason)


def _raster_closures(data):
    scope = data.get("raster_candidate_closures")
    if scope is None:
        return {"available": False, "registered_candidate_complete": False,
                "total_registered_raw_candidates": None,
                "total_resolved_raw_candidates": None,
                "unresolved_raw_candidate_ids": [],
                "unresolved_raw_source_observation_ids": [],
                "pages": []}
    if not isinstance(scope, list):
        raise ValueError("raster closure inventory must be a source array")
    pages = []
    unresolved = set()
    unresolved_observations = set()
    raw_total = resolved_total = 0
    seen_pages = set()
    for record in scope:
        if not isinstance(record, dict):
            raise ValueError("invalid raster closure receipt")
        page = str(record.get("page_id") or "").strip()
        raw = record.get("raw_candidate_count")
        resolved = record.get("resolved_candidate_count")
        complete = record.get("candidate_universe_complete")
        raw_ids = record.get("unresolved_candidate_ids")
        observation_ids = record.get("unresolved_observation_ids")
        if (not page or page in seen_pages or
                type(raw) is not int or type(resolved) is not int or
                raw < 0 or resolved < 0 or resolved > raw or
                type(complete) is not bool or
                not isinstance(raw_ids, (list, tuple)) or
                not isinstance(observation_ids, (list, tuple))):
            raise ValueError("untrustworthy raster candidate closure scope")
        if (any(not isinstance(v, str) or not v for v in (*raw_ids, *observation_ids))
                or len(set(raw_ids)) != len(raw_ids)
                or len(set(observation_ids)) != len(observation_ids)
                or len(raw_ids) > raw - resolved
                or (complete and (raw_ids or raw != resolved))):
            raise ValueError("contradictory raster candidate closure receipt")
        if unresolved.intersection(raw_ids):
            raise ValueError("raw candidate reused by separate page scope")
        seen_pages.add(page)
        raw_total += raw
        resolved_total += resolved
        unresolved.update(raw_ids)
        unresolved_observations.update(observation_ids)
        pages.append({
            "page_id": page,
            "registered_raw_candidate_count": raw,
            "resolved_raw_candidate_count": resolved,
            "unresolved_raw_candidate_ids": sorted(raw_ids),
            "registered_family_closure_claim": complete,
            "closure_reason_codes": _reason_codes(record),
        })
    return {
        "available": True,
        # Even all-true pages close only the *registered detector family*, NOT
        # semantic opening or whole-building count completeness.
        "registered_candidate_complete": bool(pages) and all(
            p["registered_family_closure_claim"] for p in pages),
        "total_registered_raw_candidates": raw_total,
        "total_resolved_raw_candidates": resolved_total,
        "unresolved_raw_candidate_ids": sorted(unresolved),
        "unresolved_raw_source_observation_ids": sorted(unresolved_observations),
        "pages": sorted(pages, key=lambda v: v["page_id"]),
    }


def build_first_failure_ledger(report):
    """Fail closed on malformed source scope; return identity-keyed source gates."""
    if not isinstance(report, dict):
        raise ValueError("source report must be JSON object")
    sha = report.get("source_sha256")
    pages = report.get("selected_geometry_page_ids")
    cap = report.get("primitive_safety_cap")
    if (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)
            or not isinstance(pages, (list, tuple)) or not pages
            or any(not str(page).isdigit() for page in pages)
            or len(set(map(str, pages))) != len(pages)
            or type(cap) is not int or cap != 20000):
        raise ValueError("invalid source provenance or changed 20,000 primitive bound")
    physical = _rows_by_identity(report.get("opening_bindings"), "opening_bindings")
    frame = _rows_by_identity(report.get("host_frame_traces"), "host_frame_traces")
    if set(physical) != set(frame):
        raise ValueError("host-frame scope differs from physical existence scope")
    stat = report.get("summary")
    if not isinstance(stat, dict):
        raise ValueError("missing original-source summary")
    host_count = sum(bool(row.get("host_wall_id")) for row in physical.values())
    frame_count = sum(bool(row.get("record_id")) for row in frame.values())
    if any(stat.get(k) != v for k,v in {
        "physical_existence_claims": len(physical),
        "authenticated_hosts": host_count,
        "resolved_source_frames": frame_count,
    }.items()):
        raise ValueError("source summary/physical identity count mismatch")
    out = []
    stages = Counter()
    for physical_id in sorted(physical):
        binding, receipt = physical[physical_id], frame[physical_id]
        selected_page_ids = set(map(str, pages))
        if (str(binding.get("page_id") or "") not in selected_page_ids
                or (receipt.get("page_id") is not None
                    and str(receipt["page_id"]) != str(binding["page_id"]))):
            raise ValueError(f"physical opening or host-frame page scope mismatch: {physical_id}")
        reasons = _reason_codes(binding)
        frame_reasons = _reason_codes(receipt)
        host = binding.get("host_wall_id")
        host_receipt = binding.get("record_id")
        frame_receipt = receipt.get("record_id")
        if frame_receipt and (not host or not host_receipt):
            raise ValueError(f"frame without source-proven host: {physical_id}")
        if bool(host) != bool(host_receipt):
            raise ValueError(f"host wall missing matching authority receipt: {physical_id}")
        state = str(binding.get("status") or "").lower()
        if not host:
            gate = ("HOST_EQUIVALENCE_CONFLICT" if "conflict" in state or
                    any("ambiguous_physical_wall_equivalence" in r for r in reasons)
                    else "HOST_AUTHORITY_UNRESOLVED")
        elif not frame_receipt:
            gate = "HOST_FRAME_GEOMETRY_UNRESOLVED"
        else:
            gate = "DOWNSTREAM_WITNESS_AND_COUNT_UNVERIFIED"
        stages[gate] += 1
        out.append({
            "physical_opening_id": physical_id,
            "page_id": binding.get("page_id"),
            "first_unresolved_authority_stage": gate,
            "host_wall_id": host,
            "host_authority_receipt": host_receipt,
            "host_frame_authority_receipt": frame_receipt,
            "host_reason_codes": list(reasons),
            "frame_reason_codes": list(frame_reasons),
            "count_quantity_metric_authentication": "NOT_AUTHENTICATED_BY_LEDGER",
        })
    candidate = _raster_closures(report)
    if candidate["available"]:
        page_ids = set(map(str, pages))
        if any(entry["page_id"] not in page_ids for entry in candidate["pages"]):
            raise ValueError("raster gap scope outside selected source geometry pages")
    return {
        "source_sha256": sha,
        "selected_geometry_page_ids": list(map(str, pages)),
        "source_all_pages_requested": report.get("all_source_pages_requested"),
        "source_primitive_safety_cap": cap,
        "physical_opening_source_identity_count": len(physical),
        "authenticated_host_receipt_count": host_count,
        "authenticated_frame_receipt_count": frame_count,
        "first_unresolved_stage_counts": dict(sorted(stages.items())),
        "physical_opening_first_failures": out,
        "registered_raster_candidate_family": candidate,
        "raw_candidate_to_physical_identity_join": "UNPROVEN_NOT_ATTEMPTED",
        "whole_building_opening_universe_complete": False,
        "count_quantity_publication_allowed": False,
        "frozen_benchmark_reconciliation": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_first_failure_ledger(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({
        "physical": result["physical_opening_source_identity_count"],
        "hosts": result["authenticated_host_receipt_count"],
        "frames": result["authenticated_frame_receipt_count"],
        "stages": result["first_unresolved_stage_counts"],
        "count_allowed": False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
