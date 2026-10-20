"""GPT3 archived Lot16 original-eight V2 *baseline* replay, not live accuracy.

Reads only immutable, previously source-authenticated signed/customer originals
and independently pre-certified exact physical→frozen identity map. Invokes
the UNCHANGED exact project V2 reconciliation process. This does not access
the owner's private PDF or issue any new construction quantity.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015"
ORIGINAL_V1 = ARCHIVE / "production/source_sealed_run.json"
ORIGINAL_CUSTOMER = ARCHIVE / "production/verified_customer_rows.json"
ORIGINAL_MAP = ARCHIVE / "identity_map_with_1215.json"
FROZEN = ROOT / "benchmarks/frozen_holdout/full_plan_v2"
MANIFEST = FROZEN / "projects/au_qld_lot16_power/source_manifest.json"
EXACT_SCORER = FROZEN / "run_exact_project_reconciliation.py"
SOURCE_SHA256 = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
ORIGINAL_EIGHT_FINGERPRINT = "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
PROJECT = "au_qld_lot16_power"
ORIGINAL_DENOMINATOR = 27


def _load_json(path: Path):
    def no_duplicate(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate key in immutable GPT3 input {path.name}: {key}")
            out[key] = value
        return out
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate)


def _checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def replay_archived_original_eight_v2_baseline() -> dict:
    """Prove historical archived eight, not present-day source producer output."""
    inputs = (ORIGINAL_V1, ORIGINAL_CUSTOMER, ORIGINAL_MAP, MANIFEST)
    before = tuple(_checksum(path) for path in inputs)
    original = _load_json(ORIGINAL_V1)
    customers = _load_json(ORIGINAL_CUSTOMER)
    identity_map = _load_json(ORIGINAL_MAP)
    if (
        type(original) is not dict
        or original.get("project_id") != PROJECT
        or original.get("fingerprint") != ORIGINAL_EIGHT_FINGERPRINT
        or original.get("source_sha256s") != [SOURCE_SHA256]
        or type(original.get("quantities")) is not list
        or len(original["quantities"]) != 8
        or any(
            type(quantity) is not dict
            or quantity.get("project_id") != PROJECT
            or quantity.get("source_sha256") != SOURCE_SHA256
            for quantity in original["quantities"]
        )
    ):
        raise ValueError("immutable Lot16 historical eight signed run is not exact")
    signed = sealed_source_closed_run_from_dict(original)
    if signed.fingerprint != ORIGINAL_EIGHT_FINGERPRINT:
        raise ValueError("original signed eight fingerprint failed source verification")
    if type(customers) is not list:
        raise ValueError("archived original signed customer projection must be an array")
    checked = verify_sealed_customer_output(signed, customers)
    if (len(checked.verified_quantity_ids) != 8
            or len(set(checked.verified_quantity_ids)) != 8
            or checked.customer_row_count != 8):
        raise ValueError("historical eight customer source correspondence incomplete")
    if (
        type(identity_map) is not dict
        or identity_map.get("project_id") != PROJECT
        or identity_map.get("source_sha256s") != [SOURCE_SHA256]
        or type(identity_map.get("bindings")) is not list
        or len(identity_map["bindings"]) != 8
    ):
        raise ValueError("historical original independently certified V2 identity map unavailable")

    # Invoke the ACTUAL frozen evaluator and exact physical mapper by process
    # boundary. It alone owns benchmark identifiers and expected quantities.
    with tempfile.TemporaryDirectory(prefix="gpt3-original-eight-v2-") as tmp:
        output = Path(tmp) / "unchanged-official-exact-reconciliation.json"
        proc = subprocess.run(
            [sys.executable, str(EXACT_SCORER),
             "--manifest", str(MANIFEST),
             "--sealed-run", str(ORIGINAL_V1),
             "--identity-map", str(ORIGINAL_MAP),
             "--output", str(output)],
            cwd=ROOT, check=False, capture_output=True, text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not output.is_file():
            raise RuntimeError(
                "unchanged frozen V2 exact source scorer did not complete: "
                + proc.stderr[-2000:]
            )
        score = _load_json(output)

    if tuple(_checksum(path) for path in inputs) != before:
        raise ValueError("immutable original signed/customer/map/manifest inputs changed")
    if (
        score.get("project_id") != PROJECT
        or score.get("source_sha_verified") is not True
        or score.get("reconciliation_complete") is not True
        or score.get("denominator") != ORIGINAL_DENOMINATOR
        or score.get("sealed_run_fingerprint") != ORIGINAL_EIGHT_FINGERPRINT
    ):
        raise ValueError("official exact historical eight report differs from source")
    result = {
        "project_id": PROJECT,
        "report_kind": "IMMUTABLE_ARCHIVED_ORIGINAL_EIGHT_V2_BASELINE",
        "current_main_live_source_verified": False,
        "new_firm_quantity_issued": False,
        "customer_release_approved": False,
        "current_full_120_benchmark_scored": False,
        "source_sha256": SOURCE_SHA256,
        "original_eight_fingerprint": ORIGINAL_EIGHT_FINGERPRINT,
        "source_customer_eight_verified": True,
        "historical_identity_binding_count": 8,
        "original_input_sha256s": {
            path.relative_to(ROOT).as_posix(): digest
            for path, digest in zip(inputs, before)
        },
        "frozen_project_reconciliation_complete": True,
        "original_frozen_denominator": score["denominator"],
        "original_matched_within_tolerance": score["matched_within_tolerance"],
        "original_matched_outside_tolerance": score["matched_outside_tolerance"],
        "original_unresolved": score["unresolved"],
        "original_missed": score["missed"],
        "original_coverage_accuracy": score["coverage_accuracy"],
        "original_precision_adjusted_accuracy": score["precision_adjusted_accuracy"],
    }
    # Unlike source issuance, it is safe to pin a HISTORICAL already-approved
    # frozen baseline as a regression. Never promote this into today's score.
    if result["original_matched_within_tolerance"] != 8:
        raise ValueError("historical original-eight V2 baseline score regressed")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    preflight_new_diagnostic(
        args.output,
        protected_roots=(FROZEN, ARCHIVE, ORIGINAL_V1, ORIGINAL_MAP,
                         ORIGINAL_CUSTOMER, MANIFEST),
    )
    report = replay_archived_original_eight_v2_baseline()
    write_new_diagnostic(
        args.output,
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=(FROZEN, ARCHIVE, ORIGINAL_V1, ORIGINAL_MAP,
                         ORIGINAL_CUSTOMER, MANIFEST),
    )
    print(json.dumps({
        "historical_original_matched": report["original_matched_within_tolerance"],
        "historical_original_denominator": report["original_frozen_denominator"],
        "current_main_live_source_verified": False,
        "new_firm_quantity_issued": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
