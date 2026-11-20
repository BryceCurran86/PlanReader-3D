"""Diff actual prior and current sealed/customer ORIGINAL opening-area runs.

An old development match is not retained merely because a new source-native
candidate exists. Both runs must pass the existing cryptographic source seal and
customer bijection before a count-only comparison is allowed. No benchmark
identity, expected value, or customer quantity is inferred.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import SealedSourceClosedRun, sealed_source_closed_run_from_dict


class OpeningRetentionError(ValueError):
    """A compared original source/customer release is unavailable or inconsistent."""


def _source_checked(run: SealedSourceClosedRun, rows: Sequence[Mapping]):
    if type(run) is not SealedSourceClosedRun:
        raise OpeningRetentionError("source-verified sealed original run required")
    source_run = sealed_source_closed_run_from_dict(run.to_dict())
    verified = verify_sealed_customer_output(source_run, rows)
    if not (verified.valid_quantity_count == verified.customer_row_count
            == len(verified.verified_quantity_ids)):
        raise OpeningRetentionError("source-closed customer bijection incomplete")
    return source_run


def _opening_rows(run: SealedSourceClosedRun):
    result = {}
    for q in run.quantities:
        if q.family != "opening_area" or q.abstained:
            continue
        if (
            q.lineage_ok is not True
            or q.value is None
            or len(q.object_identity_refs) != 1
            or type(q.object_identity_refs[0]) is not str
            or not q.object_identity_refs[0]
        ):
            raise OpeningRetentionError("unverified source opening area cannot be retained")
        key = (q.document_id, q.revision_id, q.source_sha256,
               q.object_identity_refs[0], q.family)
        if key in result:
            raise OpeningRetentionError("duplicate signed physical opening area")
        result[key] = q
    return result


def compare_signed_original_opening_retention(
    before: SealedSourceClosedRun, before_customer: Sequence[Mapping],
    after: SealedSourceClosedRun, after_customer: Sequence[Mapping],
) -> dict[str, object]:
    """Observed opening retention only. Does not grant any benchmark result."""
    prior = _source_checked(before, before_customer)
    latest = _source_checked(after, after_customer)
    if (
        prior.project_id != latest.project_id
        or not prior.source_sha256s
        or prior.source_sha256s != latest.source_sha256s
        or prior.revision_ids != latest.revision_ids
    ):
        raise OpeningRetentionError("original signed project source/revision changed")
    old, new = _opening_rows(prior), _opening_rows(latest)
    shared = old.keys() & new.keys()
    retained = sum(old[key].to_dict() == new[key].to_dict() for key in shared)
    changed = len(shared) - retained
    missing = len(old.keys() - new.keys())
    added = len(new.keys() - old.keys())
    return {
        "status": "ORIGINAL_SIGNED_OPENING_RETENTION_AUDIT",
        "official_score_granted": False,
        "opening_area_before": len(old),
        "opening_area_after": len(new),
        "identically_retained": retained,
        "changed_existing_physical_openings": changed,
        "missing_existing_physical_openings": missing,
        "new_physical_opening_areas": added,
        "complete_previous_receipt_retention": missing == 0 and changed == 0,
    }


def _strict_json(path: Path):
    from pb_strict_evidence_json import parse_strict_evidence_json
    if not path.is_file() or path.is_symlink():
        raise OpeningRetentionError("private sealed/customer receipt file missing")
    return parse_strict_evidence_json(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-seal", type=Path, required=True)
    parser.add_argument("--before-customer", type=Path, required=True)
    parser.add_argument("--after-seal", type=Path, required=True)
    parser.add_argument("--after-customer", type=Path, required=True)
    parser.add_argument("--require-retention", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compare_signed_original_opening_retention(
            sealed_source_closed_run_from_dict(_strict_json(args.before_seal)),
            _strict_json(args.before_customer),
            sealed_source_closed_run_from_dict(_strict_json(args.after_seal)),
            _strict_json(args.after_customer),
        )
    except (OpeningRetentionError, RuntimeError, TypeError, ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(json.dumps(report, sort_keys=True))
    if args.require_retention and not report["complete_previous_receipt_retention"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
