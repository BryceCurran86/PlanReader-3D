"""Two independently signed projects: source-byte-verifiable development audit.

Does not modify the frozen V2 evaluator, discover identity bindings, infer any
quantity or publish the four-project suite. Every project must supply original
PDF bytes, a cryptographically intact source seal, its complete commercial
customer projection, an independent identity map and the frozen exact report.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)
from tools.report_gpt3_four_project_evidence import _json_customer_rows, _json_object
from tools.run_gpt3_original_byte_gated_exact_project import (
    FROZEN_ROOT, _original_sha_gate, _sha256, _unchanged_frozen_exact_report,
)

_ENTRY_KEYS = frozenset({
    "manifest", "original_files", "sealed", "customer", "identity_map",
    "exact_report",
})
_COUNT_FIELDS = (
    "denominator", "matched_within_tolerance", "matched_outside_tolerance",
    "missed", "partial", "unresolved", "unsupported_extra",
    "abstained_outputs", "lineage_conflicts",
)


def _checked_one(raw: Mapping[str, Any]) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != _ENTRY_KEYS:
        raise ValueError("selected project entry must name all six original evidence fields")
    paths = {}
    for field in _ENTRY_KEYS - {"original_files"}:
        value = raw[field]
        if type(value) is not str or not value or value != value.strip():
            raise ValueError("project evidence paths must be exact nonempty strings")
        paths[field] = Path(value)
    original_values = raw["original_files"]
    if (
        type(original_values) is not list or not original_values
        or any(type(value) is not str or not value or value != value.strip()
               for value in original_values)
    ):
        raise ValueError("original source path universe must be an exact nonempty list")
    originals = [Path(value) for value in original_values]
    raw_manifest = _json_object(paths["manifest"])
    project_id = raw_manifest.get("project_id")
    if type(project_id) is not str or not project_id or project_id != project_id.strip():
        raise ValueError("frozen project identity is invalid")
    canonical_manifest = (
        FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    ).resolve()
    if paths["manifest"].resolve() != canonical_manifest:
        raise ValueError("cannot substitute a noncanonical frozen V2 manifest")

    source_ok, source_reasons, source_hashes = _original_sha_gate(
        raw_manifest, originals
    )
    if not source_ok:
        raise ValueError("original source SHA evidence unavailable: " + ",".join(source_reasons))
    expected_source_hashes = set(source_hashes)

    # Hash the original *file bytes* before processing; any in-place rewrite
    # during scoring invalidates the entire selected comparison.
    input_files = (
        [paths[name] for name in ("manifest", "sealed", "customer", "identity_map", "exact_report")]
        + originals
    )
    digests = {path.resolve(): _sha256(path) for path in input_files}
    sealed = sealed_source_closed_run_from_dict(_json_object(paths["sealed"]))
    rows = _json_customer_rows(paths["customer"])
    verified = verify_sealed_customer_output(sealed, rows)
    mapping = _json_object(paths["identity_map"])
    if (
        sealed.project_id != project_id
        or set(sealed.source_sha256s) != expected_source_hashes
        or type(mapping.get("source_sha256s")) is not list
        or len(mapping["source_sha256s"]) != len(expected_source_hashes)
        or len(set(mapping["source_sha256s"])) != len(mapping["source_sha256s"])
        or set(mapping["source_sha256s"]) != expected_source_hashes
        or mapping.get("project_id") != project_id
        or verified.project_id != project_id
        or verified.customer_row_count != len(rows)
        or len(rows) != verified.valid_quantity_count
    ):
        raise ValueError("original signed/customer/map source envelope or bijection mismatch")

    require_signed_v2_family_trade_integrity(
        verified_items=raw_manifest.get("verified_takeoff_items") or (),
        sealed_quantities=sealed.quantities,
        identity_bindings=mapping.get("bindings") or (),
    )
    recomputed = _unchanged_frozen_exact_report(
        paths["manifest"], paths["sealed"], paths["identity_map"],
    )
    stored = _json_object(paths["exact_report"])
    if stored != recomputed:
        raise ValueError("persisted frozen exact-project result differs from unchanged scorer")
    if (
        recomputed.get("project_id") != project_id
        or recomputed.get("source_sha_verified") is not True
        or recomputed.get("reconciliation_complete") is not True
        or recomputed.get("sealed_run_id") != sealed.run_id
        or recomputed.get("sealed_run_fingerprint") != sealed.fingerprint
        or any(type(recomputed.get(field)) is not int or recomputed[field] < 0
               for field in _COUNT_FIELDS)
    ):
        raise ValueError("exact-project source/scoring receipt incomplete")

    source_ok_after, _, source_hashes_after = _original_sha_gate(raw_manifest, originals)
    if not source_ok_after or source_hashes_after != source_hashes or any(
        _sha256(path) != digest for path, digest in digests.items()
    ):
        raise ValueError("original source or signed evidence bytes changed during reconciliation")

    return {
        "project_id": project_id,
        "original_source_sha_verified": True,
        "source_sha256s": source_hashes,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "customer_quantity_ids": list(verified.verified_quantity_ids),
        "customer_bijection_verified": True,
        "reconciliation_complete": True,
        **{field: recomputed[field] for field in _COUNT_FIELDS},
        "coverage_accuracy": recomputed["coverage_accuracy"],
        "precision_adjusted_accuracy": recomputed["precision_adjusted_accuracy"],
        "produced_items": recomputed["produced_items"],
    }


def build_selected_two_project_development_evidence(
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require precisely two actual source executions; never publish full V2."""
    if type(entries) not in (list, tuple) or len(entries) != 2:
        raise ValueError("selected development audit requires exactly two source-executed projects")
    projects = sorted((_checked_one(entry) for entry in entries),
                      key=lambda report: report["project_id"])
    project_ids = [r["project_id"] for r in projects]
    if len(set(project_ids)) != 2:
        raise ValueError("two selected projects cannot reuse one source identity")

    seen_quantities: set[str] = set()
    for project in projects:
        ids = project["customer_quantity_ids"]
        if any(qid in seen_quantities for qid in ids):
            raise ValueError("source quantity identity reused across independent projects")
        seen_quantities.update(ids)
    sums = {field: sum(p[field] for p in projects) for field in _COUNT_FIELDS}
    denom = sums["denominator"]
    if denom <= 0:
        raise ValueError("selected frozen development denominator must be positive")

    return {
        "publication_status": "SELECTED_PROJECT_DEVELOPMENT_ONLY",
        "selected_project_count": len(projects),
        "selected_denominator": denom,
        "selected_coverage_accuracy": sums["matched_within_tolerance"] / denom,
        "selected_precision_adjusted_accuracy": None,
        **{key: value for key, value in sums.items() if key != "denominator"},
        "projects": projects,
        "official_four_project_suite_result": None,
        "official_four_project_accuracy": None,
        "full_four_project_publication_allowed": False,
        "no_source_quantity_or_benchmark_binding_created": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    entries = [_json_object(path) for path in args.entry]
    report = build_selected_two_project_development_evidence(entries)
    output = args.output
    if output.is_symlink() or output.exists() or any(
        output.resolve() == Path(value).resolve()
        for entry in entries for key, value in entry.items()
        if key != "original_files"
    ):
        raise FileExistsError("source development report must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, prefix=".selected-v2.",
            suffix=".tmp", delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, output)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    print(json.dumps({
        "publication_status": report["publication_status"],
        "selected_denominator": report["selected_denominator"],
        "matched_within_tolerance": report["matched_within_tolerance"],
        "selected_coverage_accuracy": report["selected_coverage_accuracy"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
