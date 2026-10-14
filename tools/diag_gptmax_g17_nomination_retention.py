"""Read-only source-authority retention risk audit for a G17 nomination change.

Consumes original before/after production stage reports; never grants W4 wall
equivalence, host, opening frame, quantity, customer output, or benchmark score.
It preserves every changed stable receipt and refuses malformed inventories.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def _rows(report: Mapping[str, Any], key: str, identity: str) -> dict[str, dict]:
    collection = report.get(key)
    if type(collection) is not list:
        raise ValueError(f"{key} missing")
    result: dict[str, dict] = {}
    for row in collection:
        if not isinstance(row, dict):
            raise ValueError(f"{key} row not a dict")
        value = row.get(identity)
        if not isinstance(value, str) or not value or value in result:
            raise ValueError(f"{key} has absent/duplicate {identity}")
        result[value] = row
    return result


def _wall_records(report: Mapping[str, Any]) -> dict[str, dict]:
    scopes = report.get("source_owned_wall_scopes")
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("source W4 scopes unavailable")
    result: dict[str, dict] = {}
    for scope in scopes:
        for row in scope.get("records", ()):
            wall = row.get("wall_candidate_id") if isinstance(row, dict) else None
            if not isinstance(wall, str) or not wall or wall in result:
                raise ValueError("duplicate/invalid W4 wall address")
            result[wall] = row
    return result


def audit_g17_nomination_retention(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Report all original source changes; never pronounce a promotion safe."""
    sha = baseline.get("source_sha256")
    if not isinstance(sha, str) or len(sha) != 64 or candidate.get("source_sha256") != sha:
        raise ValueError("source PDF SHA mismatch")
    cap = baseline.get("primitive_safety_cap")
    if type(cap) is not int or cap <= 0 or candidate.get("primitive_safety_cap") != cap:
        raise ValueError("source primitive safety cap mismatch")
    old_hosts = _rows(baseline, "opening_bindings", "opening_identity_id")
    new_hosts = _rows(candidate, "opening_bindings", "opening_identity_id")
    old_frames = _rows(baseline, "host_frame_traces", "opening_identity_id")
    new_frames = _rows(candidate, "host_frame_traces", "opening_identity_id")
    old_canon = _rows(baseline, "canonical_openings", "canonical_opening_id")
    new_canon = _rows(candidate, "canonical_openings", "canonical_opening_id")
    old_walls, new_walls = _wall_records(baseline), _wall_records(candidate)
    if set(old_hosts) != set(new_hosts) or set(old_frames) != set(new_frames):
        raise ValueError("physical opening identity universe changed")
    if set(old_canon) != set(new_canon):
        raise ValueError("canonical opening identity universe changed")

    gained_hosts = sorted(k for k in old_hosts if not old_hosts[k].get("host_wall_id")
                          and new_hosts[k].get("host_wall_id"))
    lost_hosts = sorted(k for k in old_hosts if old_hosts[k].get("host_wall_id")
                        and not new_hosts[k].get("host_wall_id"))
    changed_existing_host_receipts = sorted(
        k for k in old_hosts if old_hosts[k].get("host_wall_id") and (
            old_hosts[k].get("host_wall_id") != new_hosts[k].get("host_wall_id")
            or old_hosts[k].get("record_id") != new_hosts[k].get("record_id")
            or old_hosts[k].get("member_wall_candidate_ids")
            != new_hosts[k].get("member_wall_candidate_ids")
        )
    )
    changed_existing_frame_receipts = sorted(
        k for k in old_frames if old_frames[k].get("record_id") and (
            old_frames[k].get("host_wall_id") != new_frames[k].get("host_wall_id")
            or old_frames[k].get("record_id") != new_frames[k].get("record_id")
        )
    )
    changed_existing_area_evidence = sorted(
        k for k in old_canon if old_canon[k].get("area_m2") is not None
        and old_canon[k].get("evidence_ids") != new_canon[k].get("evidence_ids")
    )
    changed_existing_area_values = sorted(
        k for k in old_canon if old_canon[k].get("area_m2")
        != new_canon[k].get("area_m2")
    )
    changed_w4_records = sorted(
        k for k in old_walls.keys() | new_walls.keys()
        if old_walls.get(k) != new_walls.get(k)
    )
    room_scopes = baseline.get("source_room_face_scopes"), candidate.get("source_room_face_scopes")
    if any(not isinstance(v, list) or not v for v in room_scopes):
        raise ValueError("source room-face scope absent")
    old_room, new_room = room_scopes
    room_changed = old_room != new_room
    # Snapshot IDs are not themselves proof of physical change; unlike ordinary
    # rekeys, host, frame and quantity evidence changes are listed explicitly.
    observed_change = bool(
        gained_hosts or lost_hosts or changed_existing_host_receipts
        or changed_existing_frame_receipts or changed_existing_area_evidence
        or changed_existing_area_values or changed_w4_records or room_changed
    )
    return {
        "source_sha256": sha,
        "primitive_safety_cap": cap,
        "baseline_snapshot_id": baseline.get("snapshot_id"),
        "candidate_snapshot_id": candidate.get("snapshot_id"),
        "physical_opening_count": len(old_hosts),
        "baseline_authenticated_host_count": sum(bool(v.get("host_wall_id")) for v in old_hosts.values()),
        "candidate_authenticated_host_count": sum(bool(v.get("host_wall_id")) for v in new_hosts.values()),
        "new_candidate_host_ids": gained_hosts,
        "lost_authenticated_host_ids": lost_hosts,
        "changed_existing_host_receipt_ids": changed_existing_host_receipts,
        "changed_existing_frame_receipt_ids": changed_existing_frame_receipts,
        "changed_existing_canonical_area_evidence_ids": changed_existing_area_evidence,
        "changed_existing_canonical_area_value_ids": changed_existing_area_values,
        "baseline_w4_record_count": len(old_walls),
        "candidate_w4_record_count": len(new_walls),
        "changed_w4_record_ids": changed_w4_records,
        "room_scope_changed": room_changed,
        "source_authority_changed": observed_change,
        "source_only_diagnostic": True,
        "physical_host_granted": False,
        "measurement_or_count_granted": False,
        "customer_quantity_granted": False,
        "benchmark_score_granted": False,
        "ready_for_production_promotion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.baseline.read_text(encoding="utf-8"))
    after = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = audit_g17_nomination_retention(before, after)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
