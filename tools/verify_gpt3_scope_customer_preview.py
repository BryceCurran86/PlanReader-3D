"""Read-only GPT3 preview audit: source-scope ↔ signed V1 ↔ customer rows.

This optional diagnostic NEVER authenticates original PDF source issuer scope,
publishes construction quantities, edits customer output or claims V2 accuracy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from pb_source_scope_sidecar_v2_preview import (
    verify_v2_preview_scope_customer_receipts,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, _json_customer_rows,
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_scope_customer_preview_report(
    *, sealed_path: Path, sidecar_path: Path, customer_path: Path,
) -> dict:
    """Validate exact original bytes, V1 signatures and all optional scope IDs.

    No original/producer/customer fixture is modified, re-signed or inferred.
    """
    paths = (sealed_path, sidecar_path, customer_path)
    before = tuple(_digest(path) for path in paths)
    sealed = sealed_source_closed_run_from_dict(_json_object(sealed_path))
    sidecar = _json_object(sidecar_path)
    customer_rows = _json_customer_rows(customer_path, allow_manual=True)
    verify_v2_preview_scope_customer_receipts(sidecar, sealed, customer_rows)
    after = tuple(_digest(path) for path in paths)
    if after != before:
        raise ValueError("signed source scope or customer input changed during verification")
    return {
        "schema_version": "gpt3_scope_customer_preview_report.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "source_scope_parity_verified": True,
        "original_pdf_issuer_scope_authenticated": False,
        "sealed_run_fingerprint": sealed.fingerprint,
        "project_id": sealed.project_id,
        "sealed_quantity_count": len(sealed.quantities),
        "preview_scope_record_count": len(sidecar["scope_records"]),
        "input_artifact_sha256s": {
            "sealed_v1": before[0],
            "preview_sidecar": before[1],
            "customer_rows": before[2],
        },
        "official_v2_coverage_accuracy": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--scope-sidecar", type=Path, required=True)
    parser.add_argument("--customer-rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (
        FROZEN_ROOT, args.sealed_run, args.scope_sidecar, args.customer_rows,
    )
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_scope_customer_preview_report(
        sealed_path=args.sealed_run,
        sidecar_path=args.scope_sidecar,
        customer_path=args.customer_rows,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
