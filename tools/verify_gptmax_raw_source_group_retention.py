"""Fail-closed source-group equivalence across two original source snapshots.

Compares actual producer-authenticated *unresolved* candidate groups, NOT raw
snapshot-scoped candidate IDs, aggregate source counts, or benchmark names.
Passing does not grant candidate existence, opening counts, W4 hosts, metric
measurements, customer rows, frozen scoring, or raw-universe completeness.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any


def _must(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("raw source candidate group retention refused: " + reason)


def _group_signature(group: Mapping[str, Any], family: str) -> str:
    _must(set(group) == {
        "candidate_id", "source_observation_ids", "aperture_bbox_pt",
        "candidate_status", "structural_pattern",
    }, "unrecognized group schema")
    ids = group["source_observation_ids"]
    _must(isinstance(ids, list) and bool(ids)
          and all(isinstance(x, str) and bool(x) for x in ids)
          and ids == sorted(set(ids)), "unproven or repeated source observation ownership")
    _must(group["candidate_status"] == "unresolved_source_only",
          "a raw source group was promoted to physical existence")
    pattern = group["structural_pattern"]
    _must(isinstance(pattern, str) and bool(pattern),
          "native structural pattern unavailable")
    aperture = group["aperture_bbox_pt"]
    if family == "raster":
        _must(pattern == "raster_gap_candidate",
              "raster candidate source pattern changed")
        _must(isinstance(aperture, list) and len(aperture) == 4
              and all(type(v) in (int, float) for v in aperture),
              "raster aperture source geometry missing or invalid")
    else:
        _must(aperture is None, "native candidate gained inferred aperture")
    return json.dumps(
        (pattern, ids, aperture), sort_keys=True, separators=(",", ":"),
    )


def _page_index(report: Mapping[str, Any], family: str):
    sidecar = report.get("unresolved_candidate_source_groups")
    _must(isinstance(sidecar, Mapping) and set(sidecar) == {"native", "raster"},
          "source-group sidecar missing or incomplete")
    pages = sidecar.get(family)
    _must(isinstance(pages, list), "missing candidate family")
    indexed = {}
    for page in pages:
        _must(isinstance(page, Mapping) and set(page) == {"page_id", "groups"},
              "malformed page group")
        pid = page["page_id"]
        _must(isinstance(pid, str) and bool(pid) and pid not in indexed,
              "duplicate page or invalid page ID")
        indexed[pid] = page["groups"]
    return indexed


def verify_raw_source_candidate_group_retention(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove same original source pattern/members/aperture for EVERY raw group.

    The opaque candidate record ID may change only when its complete original
    individually owned source proposition has a unique one-to-one match.
    """
    source = baseline.get("source_sha256")
    _must(isinstance(source, str) and len(source) == 64
          and source == candidate.get("source_sha256"), "original source SHA changed")
    _must(baseline.get("primitive_safety_cap")
          == candidate.get("primitive_safety_cap") == 20_000,
          "primitive safety bound changed")
    _must(baseline.get("snapshot_id") != candidate.get("snapshot_id"),
          "no distinct source snapshot event")
    totals = {}
    for family, key in (("native", "native_candidate_closures"),
                        ("raster", "raster_candidate_closures")):
        old_page = _page_index(baseline, family)
        new_page = _page_index(candidate, family)
        _must(set(old_page) == set(new_page),
              f"{family} original page ownership changed")
        old_closure = {str(r["page_id"]):r for r in baseline[key]}
        new_closure = {str(r["page_id"]):r for r in candidate[key]}
        _must(set(old_closure) == set(new_closure) == set(old_page),
              f"{family} source closure scope changed")
        total = 0
        for page_id in sorted(old_page):
            a, b = old_closure[page_id], new_closure[page_id]
            for k in ("candidate_universe_complete", "raw_candidate_count",
                      "resolved_candidate_count", "status", "reason_codes",
                      "unresolved_observation_ids"):
                _must(a[k] == b[k], f"{family} source closure {k} changed")
            _must(a["candidate_universe_complete"] is False,
                  "source candidate population unexpectedly complete")
            for rows, closure in ((old_page[page_id], a), (new_page[page_id], b)):
                _must(isinstance(rows, list), "groups are not an array")
                id_list=[r["candidate_id"] for r in rows]
                _must(len(id_list)==len(set(id_list)) and
                      set(id_list)==set(closure["unresolved_candidate_ids"]),
                      "raw candidate ID ownership does not cover closure")
                union=set()
                for row in rows:
                    _must(isinstance(row, Mapping), "malformed candidate group")
                    _group_signature(row, family)
                    union.update(row["source_observation_ids"])
                _must(union <= set(closure["unresolved_observation_ids"]),
                      "unowned raw source observation")
            old_sig = Counter(_group_signature(r,family) for r in old_page[page_id])
            new_sig = Counter(_group_signature(r,family) for r in new_page[page_id])
            _must(old_sig == new_sig,
                  f"{family} per-candidate original geometry/ancestry changed")
            _must(all(count == 1 for count in old_sig.values()),
                  f"{family} ambiguous duplicate original physical source group")
            total += len(old_page[page_id])
        totals[family + "_unresolved_groups"] = total
    return {
        "source_sha256": source,
        "verified_raw_source_membership": True,
        **totals,
        "physical_hosts_granted": 0,
        "opening_counts_granted": 0,
        "benchmark_matches_claimed": 0,
    }


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--candidate",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    old=json.loads(args.baseline.read_text())
    new=json.loads(args.candidate.read_text())
    receipt=verify_raw_source_candidate_group_retention(old,new)
    if args.output:
        args.output.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":
    main()
