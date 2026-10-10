"""Compare source-first GPT MAX runs by exact physical identity, not totals.

Read-only diagnostic. Never authenticates hosts, counts, geometry or quantities.
Run against two SHA-verified JSON reports from
tools/diag_gptmax_source_authority_stages.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _by_identity(rows, label):
    if not isinstance(rows, list):
        raise ValueError(f"{label} must be a list")
    result = {}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError(f"{label}: non-object record")
        identity = item.get("opening_identity_id")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError(f"{label}: missing opening_identity_id")
        if identity in result:
            raise ValueError(f"{label}: duplicate opening_identity_id {identity}")
        result[identity] = item
    return result


def _receipt(row):
    return None if not row else (row.get("record_id") or None)


def _host(row):
    return None if not row else (row.get("host_wall_id") or None)


def _reasons(row):
    return tuple(row.get("reason_codes") or ()) if row else ()


def compare_reports(before, after):
    """Return strict identity-level retention audit, independent of aggregate gains.

    Legitimate owner/frame rekeying is flagged for explicit source review, not
    silently classified as parity. This is not a benchmark reconciliation.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("reports must be JSON objects")
    for field in ("source_sha256", "selected_geometry_page_ids",
                  "all_source_pages_requested", "primitive_safety_cap"):
        if field not in before or field not in after or before[field] != after[field]:
            raise ValueError(f"incomparable report scope or provenance: {field}")
    source_sha = before["source_sha256"]
    if not isinstance(source_sha, str) or len(source_sha) != 64:
        raise ValueError("invalid source_sha256")
    b = _by_identity(before.get("opening_bindings"), "before.opening_bindings")
    a = _by_identity(after.get("opening_bindings"), "after.opening_bindings")
    bf = _by_identity(before.get("host_frame_traces"), "before.host_frame_traces")
    af = _by_identity(after.get("host_frame_traces"), "after.host_frame_traces")
    if set(bf) != set(b) or set(af) != set(a):
        raise ValueError("host frame trace universe differs from physical existence universe")

    missing = sorted(set(b) - set(a))
    added = sorted(set(a) - set(b))
    losses, changes, gains = [], [], []
    for key in sorted(set(b) & set(a)):
        old, new = b[key], a[key]
        old_frame, new_frame = bf[key], af[key]
        # Check both receipt and physical owner: a nonempty but foreign host is
        # not preservation of the prior proven source wall.
        old_h, new_h = _host(old), _host(new)
        old_r, new_r = _receipt(old), _receipt(new)
        old_f, new_f = _receipt(old_frame), _receipt(new_frame)
        flags = []
        if old_h and not new_h: flags.append("host_lost")
        if old_r and not new_r: flags.append("host_receipt_lost")
        if old_f and not new_f: flags.append("source_frame_lost")
        if old_h and new_h and old_h != new_h: flags.append("host_owner_changed")
        if old_r and new_r and old_r != new_r: flags.append("host_receipt_changed")
        if old_f and new_f and old_f != new_f: flags.append("source_frame_changed")
        if flags:
            row = {
                "physical_opening_id": key,
                "changes": flags,
                "old_host_wall_id": old_h,
                "new_host_wall_id": new_h,
                "old_host_receipt": old_r,
                "new_host_receipt": new_r,
                "old_frame_receipt": old_f,
                "new_frame_receipt": new_f,
                "new_host_reason_codes": _reasons(new),
                "new_frame_reason_codes": _reasons(new_frame),
            }
            (changes if any(v.endswith("_changed") for v in flags) else losses).append(row)
        elif (not old_h and new_h) or (not old_r and new_r) or (not old_f and new_f):
            gains.append({
                "physical_opening_id": key,
                "new_host_wall_id": new_h,
                "new_host_receipt": new_r,
                "new_frame_receipt": new_f,
            })

    counts = {
        "baseline_physical_openings": len(b),
        "candidate_physical_openings": len(a),
        "baseline_hosts": sum(bool(_host(v)) for v in b.values()),
        "candidate_hosts": sum(bool(_host(v)) for v in a.values()),
        "baseline_frames": sum(bool(_receipt(v)) for v in bf.values()),
        "candidate_frames": sum(bool(_receipt(v)) for v in af.values()),
    }
    return {
        "source_sha256": source_sha,
        "scope_page_ids": before["selected_geometry_page_ids"],
        "count_summary": counts,
        "missing_physical_openings": missing,
        "added_physical_openings": added,
        "lost_proof_records": losses,
        "changed_proof_records_needing_review": changes,
        "new_proof_records": gains,
        "retention_pass": not (missing or losses or changes),
        "source_evidence_only": True,
        "benchmark_accuracy": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare_reports(json.loads(args.baseline.read_text()),
                                 json.loads(args.candidate.read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"retention_pass": report["retention_pass"],
                      **report["count_summary"]}, sort_keys=True))
    raise SystemExit(0 if report["retention_pass"] else 1)


if __name__ == "__main__":
    main()
