"""Read-only W4 positive-source coverage losses across identical source PDF runs.

Measures missing *published W4 source-member coverage in PDF points*, never
missing physical wall geometry, an opening count, or a metric quantity.
Only compare fragments owned by the same physical opening, page and original
positive primitive ID. No gap is connected or new host identity accepted.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

_EPS = 1e-6


def _source_index(report):
    if not isinstance(report, dict):
        raise ValueError("source report required")
    sha = report.get("source_sha256")
    pages = report.get("selected_geometry_page_ids")
    if (not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
            or not isinstance(pages, list) or not pages
            or any(not isinstance(p, str) or not p.isdecimal() for p in pages)
            or len(set(pages)) != len(pages)
            or report.get("primitive_safety_cap") != 20000):
        raise ValueError("unproven source identity, page scope or safety bound")
    openings = {}
    for opening in report.get("opening_bindings", []):
        oid = opening.get("opening_identity_id")
        if not isinstance(oid, str) or not oid.startswith("physical_opening_existence_") or oid in openings:
            raise ValueError("invalid or repeated physical opening owner")
        if opening.get("page_id") not in pages:
            raise ValueError("physical opening outside selected source page")
        openings[oid] = opening
    if not openings:
        raise ValueError("missing physical openings")
    walls = {}
    seen_pages = set()
    for scope in report.get("source_owned_wall_scope_results", []):
        page = str(scope.get("page_id"))
        if (scope.get("source_sha256") != sha or page not in pages
                or scope.get("status") != "corroborated"
                or scope.get("scope_complete") is not True
                or page in seen_pages):
            raise ValueError("incomplete, duplicated or foreign source W4 scope")
        seen_pages.add(page)
        for row in scope.get("records", []):
            wid = row.get("wall_candidate_id")
            if not isinstance(wid, str) or not wid or wid in walls:
                raise ValueError("ambiguous W4 candidate owner")
            walls[wid] = (page, row)
    if seen_pages != set(pages):
        raise ValueError("incomplete selected page coverage")
    return sha, tuple(pages), openings, walls


def _positive_segments(opening, walls):
    if not opening.get("host_wall_id") or not opening.get("record_id"):
        return None
    source = set()
    for wid in opening.get("member_wall_candidate_ids", []):
        pair = walls.get(wid)
        if pair is None or pair[0] != opening["page_id"]:
            raise ValueError("missing source-owned W4 candidate on physical opening page")
        row = pair[1]
        physical = row.get("physical_identity") or {}
        parents = physical.get("source_primitive_ids")
        if (physical.get("status") != "corroborated" or physical.get("blocking_reasons")
                or not isinstance(parents, list) or not parents
                or any(not isinstance(x, str) or not x for x in parents)):
            raise ValueError("unproven W4 physical candidate ancestry")
        fragments = row.get("source_edge_fragments")
        if not isinstance(fragments, list) or not fragments:
            raise ValueError("missing positive source edge fragments")
        for edge in fragments:
            coords = edge.get("geometry")
            edge_parents = edge.get("source_primitive_ids")
            if (not isinstance(coords, list) or len(coords) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           for v in coords)
                    or math.dist(coords[:2], coords[2:]) <= _EPS
                    or not isinstance(edge_parents, list) or not edge_parents
                    or any(p not in parents for p in edge_parents)):
                raise ValueError("non-authenticated original PDF source fragment")
            for pid in edge_parents:
                source.add((pid, tuple(float(v) for v in coords), wid))
    return sorted(source)


def _missing_on_original_line(old, candidate):
    """Return portions of one old positive edge not covered on its exact line."""
    ax, ay, bx, by = old
    dx, dy = bx-ax, by-ay
    length = math.hypot(dx, dy)
    ux, uy = dx/length, dy/length
    intervals = []
    for cx, cy, ex, ey in candidate:
        if (abs((cx-ax)*uy-(cy-ay)*ux) > _EPS
                or abs((ex-ax)*uy-(ey-ay)*ux) > _EPS):
            continue
        t0 = (cx-ax)*ux+(cy-ay)*uy
        t1 = (ex-ax)*ux+(ey-ay)*uy
        low, high = max(0.0, min(t0, t1)), min(length, max(t0, t1))
        if high-low > _EPS:
            intervals.append((low, high))
    intervals.sort()
    gaps = []
    covered_end = 0.0
    for start, end in intervals:
        if start-covered_end > _EPS:
            gaps.append((covered_end, start))
        covered_end = max(covered_end, end)
    if length-covered_end > _EPS:
        gaps.append((covered_end, length))
    return [
        [round(ax+ux*s, 8), round(ay+uy*s, 8),
         round(ax+ux*e, 8), round(ay+uy*e, 8)]
        for s, e in gaps
    ]


def audit_positive_w4_coverage_delta(before, after):
    oldsha, oldpages, oldopen, oldwalls = _source_index(before)
    newsha, newpages, newopen, newwalls = _source_index(after)
    if (oldsha != newsha or oldpages != newpages
            or not set(oldopen).issubset(newopen)):
        raise ValueError("source SHA, pages or original physical owners changed")
    rows = []
    skipped = []
    for oid in sorted(oldopen):
        original = _positive_segments(oldopen[oid], oldwalls)
        if original is None:
            continue
        candidate = _positive_segments(newopen[oid], newwalls)
        if candidate is None:
            skipped.append(oid)
            continue
        by_parent = {}
        for pid, coords, _ in candidate:
            by_parent.setdefault(pid, set()).add(coords)
        for pid, coords, wid in original:
            missing = _missing_on_original_line(coords, by_parent.get(pid, ()))
            for lost in missing:
                rows.append({
                    "physical_opening_id": oid,
                    "original_w4_member": wid,
                    "positive_source_primitive_id": pid,
                    "original_source_edge_pdf_pt": list(coords),
                    "absent_original_coverage_pdf_pt": lost,
                    "conclusion": "W4_ASSEMBLY_COVERAGE_ABSENT_NOT_PHYSICAL_WALL_LOSS",
                })
    return {
        "source_sha256": oldsha,
        "selected_geometry_page_ids": list(oldpages),
        "absent_original_w4_source_fragment_count": len(rows),
        "missing_source_coverage_rows": rows,
        "candidate_host_absent_abstentions": skipped,
        "source_gap_closure_allowed": False,
        "physical_host_or_receipt_equivalence_allowed": False,
        "opening_count_or_metric_quantity_allowed": False,
        "benchmark_accuracy": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_positive_w4_coverage_delta(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "missing_source_coverage_rows": len(result["missing_source_coverage_rows"]),
        "candidate_host_absent_abstentions": len(result["candidate_host_absent_abstentions"]),
        "official_host_acceptance": False,
    }))


if __name__ == "__main__":
    main()
