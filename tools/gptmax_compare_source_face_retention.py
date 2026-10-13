"""Strict physical-opening identity retention across original source-face reports.

Adapter for tools/diag_opening_wall_face_preservation.py to the existing
tools.gptmax_compare_opening_authority source-first retention checker.
No geometry, host, frame, counts, benchmark source truth or tolerances mutate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tools.gptmax_compare_opening_authority import compare_reports
from tools.declared_additive_source_retention import (
    REKEY_FLAGS,
    approve_declared_additive_rekeys,
)


def _canonicalize(report):
    if not isinstance(report, dict):
        raise ValueError("source-face report must be an object")
    pages = report.get("selected_geometry_page_ids")
    if not isinstance(pages, (tuple, list)) or not pages:
        raise ValueError("missing selected geometry page source scope")
    if "host_frame_traces" in report:
        raise ValueError("ambiguous source-face report shape")
    if "host_frames" not in report:
        raise ValueError("missing source host frame receipts")
    if "opening_bindings" not in report:
        raise ValueError("missing physical opening bindings")
    return {
        "source_sha256": report.get("source_sha256"),
        "selected_geometry_page_ids": pages,
        "all_source_pages_requested": False,
        "primitive_safety_cap": report.get("primitive_safety_cap"),
        "opening_bindings": report["opening_bindings"],
        "host_frame_traces": report["host_frames"],
    }


def compare_source_face_reports(baseline, candidate, *, declarations=None):
    """Reject loss or rekey of ANY prior source-backed identity/host/frame.

    ``declarations`` (default: the committed file, empty unless a reviewed
    additive-source event is declared) can only turn a receipt rekey of a
    retained host whose physical source proposition is proven unchanged into an
    explicitly accepted record.  Losses, owner changes of other kinds and every
    undeclared event still fail exactly as before.
    """
    before = _canonicalize(baseline)
    after = _canonicalize(candidate)
    for original, current in ((baseline, candidate),):
        if original.get("source_sha256") != current.get("source_sha256"):
            raise ValueError("source SHA mismatch")
        if original.get("selected_geometry_page_ids") != current.get("selected_geometry_page_ids"):
            raise ValueError("source geometry pages mismatch")
        if original.get("primitive_safety_cap") != current.get("primitive_safety_cap"):
            raise ValueError("primitive cap mismatch")
    result = compare_reports(before, after)
    approval = approve_declared_additive_rekeys(baseline, candidate, declarations)
    if approval is not None:
        rekeyed = set(approval["rekeyed_host_ids"])
        accepted, remaining = [], []
        for record in result["changed_proof_records_needing_review"]:
            if (record["physical_opening_id"] in rekeyed
                    and set(record["changes"]) <= REKEY_FLAGS):
                accepted.append(record)
            else:
                remaining.append(record)
        result["changed_proof_records_needing_review"] = remaining
        result["declared_additive_source_retention"] = approval
        result["declared_rekeys_accepted"] = accepted
        result["retention_pass"] = not (
            result["missing_physical_openings"]
            or result["lost_proof_records"]
            or remaining
        )
    result["source_report_kind"] = "real_physical_source_wall_faces"
    result["quantity_publication_permitted"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_source_face_reports(
            json.loads(args.baseline.read_text()),
            json.loads(args.candidate.read_text()),
        )
    except (ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"retention_pass": result["retention_pass"],
                      "baseline": result["count_summary"]["baseline_hosts"],
                      "candidate": result["count_summary"]["candidate_hosts"],
                      "lost_proofs": len(result["lost_proof_records"]),
                      "changed_proofs": len(result["changed_proof_records_needing_review"])},
                     sort_keys=True))
    raise SystemExit(0 if result["retention_pass"] else 1)


if __name__ == "__main__":
    main()
