"""Read-only source-produced opening host and W4 identity first-gate census.

Input MUST be a report from tools/diag_opening_wall_face_preservation.py.
That tool obtains evidence through the original producer. A JSON report alone
cannot independently authenticate a PDF; use --expected-source-sha to verify
the report's asserted source lineage against a separately known SHA.

Never publish physical host, wall equivalence, count, dimensions or accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import re
from pathlib import Path


def source_first_gate_census(report: dict, *, expected_source_sha: str | None = None) -> dict:
    if not isinstance(report, dict):
        raise ValueError("original source report must be a JSON object")
    sha = report.get("source_sha256")
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError("missing or invalid original source SHA-256")
    if expected_source_sha is not None and expected_source_sha != sha:
        raise ValueError("original source SHA-256 mismatch")
    if report.get("primitive_safety_cap") != 20_000:
        raise ValueError("source safety cap is missing or altered")
    pages = report.get("selected_geometry_page_ids")
    if (not isinstance(pages, (list, tuple)) or not pages
            or any(not isinstance(p, str) or not p.isdigit() for p in pages)
            or len(set(pages)) != len(pages)):
        raise ValueError("invalid original source page scope")
    scopes = report.get("source_owned_wall_scope_results")
    bindings = report.get("opening_bindings")
    frames = report.get("host_frames")
    summary = report.get("summary")
    if not isinstance(scopes, list) or not isinstance(bindings, list) or not isinstance(frames, list):
        raise ValueError("original source wall/opening/frame receipts unavailable")
    if not isinstance(summary, dict):
        raise ValueError("source report has no producer summary")
    expected = {
        "physical_existence_claims": len(bindings),
        "host_bindings": sum(bool(b.get("host_wall_id")) for b in bindings),
        "host_frames": sum(bool(f.get("record_id")) for f in frames),
    }
    if any(summary.get(key) != count for key, count in expected.items()):
        raise ValueError("source report summary contradicts individual receipts")
    if len(scopes) != len(pages):
        raise ValueError("source wall scope and page cardinality mismatch")
    if {str(s.get("page_id")) for s in scopes} != set(pages):
        raise ValueError("wall scopes do not match requested original source pages")
    if any(s.get("source_sha256") != sha for s in scopes):
        raise ValueError("foreign source wall scope")
    scope_ids = [s.get("decision_scope_id") for s in scopes]
    if any(not isinstance(s, str) or not s for s in scope_ids) or len(set(scope_ids)) != len(scope_ids):
        raise ValueError("repeated or missing producer-owned wall decision scope")

    collisions = []
    sidecar_mismatches = []
    scope_census = []
    for scope in sorted(scopes, key=lambda s: (int(s["page_id"]), s["decision_scope_id"])):
        records = scope.get("records")
        if not isinstance(records, (list, tuple)):
            raise ValueError("missing original wall record inventory")
        by_id = defaultdict(list)
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("wall_candidate_id"), str):
                raise ValueError("invalid source wall record")
            candidate = record.get("wall_candidate")
            identity = record.get("physical_identity")
            if not isinstance(candidate, dict) or not isinstance(identity, dict):
                raise ValueError("missing W4 source candidate/physical identity")
            if candidate.get("candidate_id") != record["wall_candidate_id"]:
                raise ValueError("wall record and W4 address disagree")
            if identity.get("wall_candidate_id") != record["wall_candidate_id"]:
                raise ValueError("wall record and physical identity address disagree")
            by_id[record["wall_candidate_id"]].append(record)
            source_edges = tuple(candidate.get("face_a_segment_ids") or ()) + tuple(
                candidate.get("face_b_segment_ids") or ())
            identity_edges = tuple(identity.get("edge_ids") or ())
            if source_edges != identity_edges:
                sidecar_mismatches.append({
                    "page_id": scope["page_id"],
                    "wall_candidate_id": record["wall_candidate_id"],
                    "w4_source_edge_ids": list(source_edges),
                    "identity_sidecar_edge_ids": list(identity_edges),
                })
        for wall_id, group in sorted(by_id.items()):
            if len(group) < 2:
                continue
            collisions.append({
                "page_id": scope["page_id"],
                "wall_candidate_id": wall_id,
                "source_candidate_count": len(group),
                "source_edges_by_candidate": [
                    list(c["wall_candidate"].get("face_a_segment_ids") or ())
                    for c in group
                ],
                "w3_junctions_by_candidate": [
                    list(c["wall_candidate"].get("end_node_ids") or ())
                    for c in group
                ],
            })
        scope_census.append({
            "page_id": scope["page_id"],
            "decision_scope_id": scope["decision_scope_id"],
            "w4_source_candidate_records": len(records),
            "unique_w4_candidate_addresses": len(by_id),
            "collided_w4_address_count": sum(len(group) > 1 for group in by_id.values()),
        })

    seen = set()
    first_gates = Counter()
    unhosted = []
    for trace in sorted(bindings, key=lambda b: (str(b.get("page_id")), str(b.get("opening_identity_id")))):
        page = trace.get("page_id")
        opening_id = trace.get("opening_identity_id")
        if (page not in pages or not isinstance(opening_id, str) or not opening_id
                or (page, opening_id) in seen):
            raise ValueError("duplicate, missing, or foreign opening source identity")
        seen.add((page, opening_id))
        if trace.get("host_wall_id"):
            continue
        reasons = tuple(trace.get("reason_codes") or ())
        if any(not isinstance(code, str) or not code for code in reasons):
            raise ValueError("invalid original source host blockers")
        if "raster_source_band_left_source_primitive_unmapped" in reasons:
            stage = "left_original_raster_source_primitive_unmapped"
        elif "raster_source_band_right_source_primitive_unmapped" in reasons:
            stage = "right_original_raster_source_primitive_unmapped"
        elif "raster_source_band_left_local_wall_owner_unmapped" in reasons:
            stage = "left_source_local_w4_owner_unmapped"
        elif "raster_source_band_right_local_wall_owner_unmapped" in reasons:
            stage = "right_source_local_w4_owner_unmapped"
        elif "no_authenticated_host_wall_band" in reasons:
            stage = "source_host_wall_band_unproven"
        else:
            stage = "other_source_host_blocker"
        first_gates[stage] += 1
        unhosted.append({
            "page_id": page,
            "opening_identity_id": opening_id,
            "first_observed_host_gate": stage,
            "original_source_reason_codes": list(reasons),
        })
    return {
        "original_source_report_sha256": sha,
        "selected_geometry_page_ids": list(pages),
        "source_summary_verified": expected,
        "source_wall_scope_census": scope_census,
        "w4_candidate_address_collisions": collisions,
        "physical_identity_sidecar_edge_mismatches": sidecar_mismatches,
        "unhosted_original_openings": unhosted,
        "unhosted_first_gate_counts": dict(sorted(first_gates.items())),
        "source_report_only": True,
        "original_pdf_bytes_reauthenticated_by_this_report": False,
        "host_publication_allowed": False,
        "physical_wall_equivalence_proven": False,
        "opening_count_publication_allowed": False,
        "metric_quantity_publication_allowed": False,
        "benchmark_accuracy": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--expected-source-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    census = source_first_gate_census(
        json.loads(args.source_report.read_text()),
        expected_source_sha=args.expected_source_sha,
    )
    args.output.write_text(json.dumps(census, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_sha256": census["original_source_report_sha256"],
        "unhosted": len(census["unhosted_original_openings"]),
        "first_gates": census["unhosted_first_gate_counts"],
        "w4_candidate_address_collisions": len(census["w4_candidate_address_collisions"]),
        "physical_identity_edge_mismatches": len(census["physical_identity_sidecar_edge_mismatches"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
