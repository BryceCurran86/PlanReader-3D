"""Read-only original G17/W4 hostless source lineage candidates, no authority grants."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path


def original_hostless_source_census(
    report: dict, *, source_sha256: str, snapshot_id: str,
    physical_opening_ids: tuple[str, ...], radius_pt: float = 8.0,
) -> dict:
    if (not source_sha256 or not snapshot_id
            or report.get("source_sha256") != source_sha256
            or report.get("snapshot_id") != snapshot_id):
        raise ValueError("exact source SHA/snapshot required")
    if (not physical_opening_ids or len(set(physical_opening_ids)) != len(physical_opening_ids)
            or not math.isfinite(radius_pt) or not 0 < radius_pt <= 8):
        raise ValueError("explicit unique openings and bounded positive radius required")
    baseline = report["baseline_receipts"]
    if len(baseline["walls"]) != 1:
        raise ValueError("exactly one original wall scope required")
    scope = baseline["walls"][0]
    if (not scope["scope_complete"] or scope["source_sha256"] != source_sha256
            or scope["snapshot_id"] != snapshot_id):
        raise ValueError("unsealed or foreign wall source scope")
    walls = scope["records"]
    if len({r["wall_candidate_id"] for r in walls}) != len(walls):
        raise ValueError("duplicate W4 candidate identity")
    can = {r["physical_opening_id"]: r for r in baseline["canonical"]}
    hosts = {r["opening_identity_id"]: r for r in baseline["hosts"]}
    if len(can) != len(baseline["canonical"]) or len(hosts) != len(baseline["hosts"]):
        raise ValueError("duplicate physical opening identity")
    gaps = [
        g for g in report["baseline_source_audit"]["raw_registered_gaps"]
        if g["source_scope"]["snapshot_id"] == snapshot_id
        and g["source_scope"]["source_sha256"] == source_sha256
        and g["source_scope"]["document_id"] == scope["document_id"]
        and g["source_scope"]["revision_id"] == scope["revision_id"]
        and g["source_scope"]["page_id"] == scope["page_id"]
    ]
    results = []
    for identity in sorted(physical_opening_ids):
        c = can.get(identity)
        host = hosts.get(identity)
        if (c is None or host is None or c["snapshot_id"] != snapshot_id
                or c["source_sha256"] != source_sha256
                or host["record_id"] is not None or host["host_wall_id"] is not None
                or "no_authenticated_host_wall_band" not in host["reason_codes"]):
            raise ValueError("opening not genuine source-hostless original")
        observations = set(c["source_observation_ids"])
        scored = [(len(observations.intersection(g["source_observation_ids"])), g) for g in gaps]
        best = max((n for n, _ in scored), default=0)
        matches = [g for n, g in scored if n == best]
        if best < 6 or len(matches) != 1:
            raise ValueError("source gap missing or competing original identity")
        gap = matches[0]
        x0, y0, x1, y1 = map(float, gap["aperture_bbox_pt"])
        if (not all(math.isfinite(v) for v in (x0, y0, x1, y1))
                or x1 <= x0 or y1 <= y0):
            raise ValueError("invalid original source geometry")
        horizontal = (x1 - x0) > (y1 - y0)
        endpoints = (((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2))
                     if horizontal else (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)))
        candidates = []
        for wall in walls:
            p = wall["physical_identity"]
            if (p["viewport_id"] != scope["decision_scope_id"]
                    or not p["source_primitive_ids"] or not p["edge_ids"]):
                continue
            points = wall["wall_candidate"]["centerline_pts"]
            for a, b in zip(points, points[1:]):
                dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
                length = math.hypot(dx, dy)
                if length <= 1e-6:
                    continue
                if (horizontal and abs(dy / length) > math.sin(math.radians(8))
                        or not horizontal and abs(dx / length) > math.sin(math.radians(8))):
                    continue
                for side, (ex, ey) in zip(("first", "second"), endpoints):
                    distance = min(math.hypot(v[0] - ex, v[1] - ey) for v in (a, b))
                    if distance <= radius_pt:
                        candidates.append({
                            "side": side,
                            "wall_candidate_id": wall["wall_candidate_id"],
                            "source_primitive_ids": p["source_primitive_ids"],
                            "w4_edge_ids": p["edge_ids"],
                            "source_segment_pt": [list(a), list(b)],
                            "endpoint_distance_pt": round(distance, 6),
                            "source_side_membership_granted": False,
                            "structural_host_granted": False,
                        })
        candidates.sort(key=lambda v: (v["side"], v["endpoint_distance_pt"],
                                       v["wall_candidate_id"], v["w4_edge_ids"]))
        results.append({
            "physical_opening_id": identity,
            "source_raw_candidate_id": gap["raw_candidate_id"],
            "source_gap_bbox_pt": [x0, y0, x1, y1],
            "matched_source_observation_count": best,
            "original_host_reason_codes": host["reason_codes"],
            "source_w4_endpoint_shortlist": candidates,
            "shortlist_count": len(candidates),
            "first_stage": "UNPROVEN_ORIGINAL_SOURCE_W4_STRUCTURAL_SIDE_MEMBERSHIP",
            "host_granted": False,
        })
    return {
        "status": "UNPUBLISHED_SOURCE_HOSTLESS_DIAGNOSTIC",
        "source_sha256": source_sha256, "snapshot_id": snapshot_id,
        "decision_scope_id": scope["decision_scope_id"],
        "original_w4_record_count": len(walls),
        "original_selected_root_raw_candidate_count": len(gaps),
        "diagnostic_radius_pt": radius_pt,
        "cases": results,
        "authority_grants": {n: False for n in
            ("host", "frame", "metric", "quantity", "customer", "count")},
        "limitation": "Source-owned endpoint geometry can NOMINATE only; it never proves "
                      "original G17 flank membership, structural W4 identity or a host.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--physical-id", required=True, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = args.source_report.read_bytes()
    result = original_hostless_source_census(
        json.loads(payload), source_sha256=args.sha256,
        snapshot_id=args.snapshot, physical_opening_ids=tuple(args.physical_id),
    )
    result["original_report_sha256"] = sha256(payload).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print({"cases": len(result["cases"]), "authority_grants": result["authority_grants"]})


if __name__ == "__main__":
    main()
