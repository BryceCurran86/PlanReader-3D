"""Audit nine unresolved original G17 raw candidates and six hosted-side W4 ancestry traces.

Read-only ORIGINAL producer receipts; never repair, bind or count openings.
Source observation overlap cannot establish physical identity or multiplicity.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path


def raw_and_w4_ancestry_audit(source: dict, hostless: dict,
                             *, source_sha256: str, snapshot_id: str) -> dict:
    if (source.get("source_sha256") != source_sha256 or
            source.get("snapshot_id") != snapshot_id or
            hostless.get("source_sha256") != source_sha256 or
            hostless.get("snapshot_id") != snapshot_id):
        raise ValueError("exact original source SHA and selected snapshot required")
    old = source["baseline_source_audit"]["raster_candidate_closure"]
    shadow = source["candidate_source_audit"]["raster_candidate_closure"]
    wall_scopes = source["baseline_receipts"]["walls"]
    if len(wall_scopes) != 1:
        raise ValueError("single sealed original wall scope required")
    wall = wall_scopes[0]
    if (not wall["scope_complete"] or wall["source_sha256"] != source_sha256
            or wall["snapshot_id"] != snapshot_id
            or hostless["decision_scope_id"] != wall["decision_scope_id"]):
        raise ValueError("source scope or source-owned wall decision mismatch")
    if (old["candidate_universe_complete"] or shadow["candidate_universe_complete"]
            or old["raw_candidate_count"] != shadow["raw_candidate_count"]):
        raise ValueError("only incomplete original/shadow raw universes may be compared")
    records = {
        record["wall_candidate_id"]: record for record in wall["records"]
    }
    if len(records) != len(wall["records"]):
        raise ValueError("duplicate W4 identity")
    raw = {
        g["raw_candidate_id"]: g
        for g in source["baseline_source_audit"]["raw_registered_gaps"]
        if g["source_scope"]["source_sha256"] == source_sha256
        and g["source_scope"]["snapshot_id"] == snapshot_id
        and g["source_scope"]["document_id"] == wall["document_id"]
        and g["source_scope"]["revision_id"] == wall["revision_id"]
        and g["source_scope"]["page_id"] == wall["page_id"]
    }
    if len(raw) != old["raw_candidate_count"]:
        raise ValueError("incomplete or duplicated original raw producer receipts")
    originals = tuple(old["unresolved_candidate_ids"])
    remaining = tuple(shadow["unresolved_candidate_ids"])
    if (len(set(originals)) != len(originals) or
            len(set(remaining)) != len(remaining) or
            not set(remaining).issubset(set(originals)) or
            len(originals) + old["resolved_candidate_count"] != len(raw) or
            len(remaining) + shadow["resolved_candidate_count"] != len(raw)):
        raise ValueError("unresolved raw closure cardinality inconsistent")
    union: set[str] = set()
    source_owners: dict[str, set[str]] = {}
    cases = []
    for rid in sorted(originals):
        if rid not in raw:
            raise ValueError("missing original raw candidate in selected root")
        gap = raw[rid]
        observations = tuple(gap["source_observation_ids"])
        if len(set(observations)) != len(observations) or not observations:
            raise ValueError("duplicate/missing raw source observation membership")
        for oid in observations:
            source_owners.setdefault(oid, set()).add(rid)
        union.update(observations)
        cases.append({
            "raw_candidate_id": rid,
            "source_bbox_pt": gap["aperture_bbox_pt"],
            "source_observation_ids": sorted(observations),
            "isolated_shadow_still_unresolved": rid in remaining,
            "physical_instance_proven": False,
            "global_opening_count_granted": False,
        })
    if union != set(old["unresolved_observation_ids"]):
        raise ValueError("unresolved observation coverage not reproduced")
    overlaps = [
        {"source_observation_id": obs, "raw_candidate_ids": sorted(owners)}
        for obs, owners in sorted(source_owners.items())
        if len(owners) > 1
    ]
    six = hostless["cases"]
    if len({c["physical_opening_id"] for c in six}) != len(six):
        raise ValueError("duplicate hostless physical opening")
    chain_results = []
    for c in sorted(six, key=lambda x: x["physical_opening_id"]):
        if (c["first_stage"] != "UNPROVEN_ORIGINAL_SOURCE_W4_STRUCTURAL_SIDE_MEMBERSHIP"
                or c["host_granted"] or c["matched_source_observation_count"] < 6):
            raise ValueError("hostless input claims unearned W4 authority")
        chains = []
        candidate_ids = sorted(set(
            x["wall_candidate_id"] for x in c["source_w4_endpoint_shortlist"]
        ))
        for wid in candidate_ids:
            record = records.get(wid)
            if record is None:
                raise ValueError("candidate has no actual same-root W4 wall receipt")
            identity = record["physical_identity"]
            fragments = record["source_edge_fragments"]
            path = record["wall_candidate"]["centerline_pts"]
            if (identity["viewport_id"] != wall["decision_scope_id"]
                    or not identity["source_primitive_ids"]
                    or not identity["edge_ids"] or
                    len(fragments) != len(path) - 1):
                raise ValueError("candidate original split-fragment ancestry unavailable")
            deltas = []
            for (start, end), fragment in zip(zip(path, path[1:]), fragments):
                if (fragment["edge_id"] not in identity["edge_ids"] or
                        not set(fragment["source_primitive_ids"]).issubset(
                            identity["source_primitive_ids"])):
                    raise ValueError("W4 source-edge/primitive identity conflict")
                original = fragment["geometry"]
                if len(original) != 4:
                    raise ValueError("original source edge geometry missing")
                deltas.extend((
                    math.hypot(float(start[0]) - float(original[0]),
                               float(start[1]) - float(original[1])),
                    math.hypot(float(end[0]) - float(original[2]),
                               float(end[1]) - float(original[3])),
                ))
            chains.append({
                "wall_candidate_id": wid,
                "original_source_primitive_ids": identity["source_primitive_ids"],
                "original_split_edge_ids": [f["edge_id"] for f in fragments],
                "split_edge_count": len(fragments),
                "max_original_source_to_w4_centerline_offset_pt": round(max(deltas), 6),
                "source_primitive_ancestry_internally_consistent": True,
                "missing_flank_membership_proven": False,
            })
        chain_results.append({
            "physical_opening_id": c["physical_opening_id"],
            "missing_host_first_stage": c["first_stage"],
            "source_w4_candidate_count": len(chains),
            "w4_source_chains": chains,
            "host_or_frame_granted": False,
        })
    return {
        "status": "UNPUBLISHED_ORIGINAL_RAW_AND_W4_ANCESTRY_AUDIT",
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "decision_scope_id": wall["decision_scope_id"],
        "original_raw_total": len(raw),
        "original_unresolved_count": len(cases),
        "isolated_shadow_unresolved_count": len(remaining),
        "original_unresolved_observation_memberships": sum(
            len(c["source_observation_ids"]) for c in cases
        ),
        "original_unique_unresolved_observations": len(union),
        "shared_unresolved_source_observations": overlaps,
        "unresolved_raw_cases": cases,
        "hostless_source_chains": chain_results,
        "authority_grants": {
            key: False for key in ("physical_opening", "host", "frame",
                                   "metric", "quantity", "customer", "count")
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-replay", required=True, type=Path)
    p.add_argument("--hostless-report", required=True, type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = raw_and_w4_ancestry_audit(
        json.loads(args.original_replay.read_text()),
        json.loads(args.hostless_report.read_text()),
        source_sha256=args.sha256, snapshot_id=args.snapshot,
    )
    result["original_replay_sha256"] = sha256(args.original_replay.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print({"nine_raw_unresolved": result["original_unresolved_count"],
           "source_observation_overlap": len(result["shared_unresolved_source_observations"]),
           "hostless": len(result["hostless_source_chains"])})


if __name__ == "__main__":
    main()
