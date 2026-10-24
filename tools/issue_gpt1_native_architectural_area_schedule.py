"""Private-original architectural schedule area issuer: SOURCE handoff only.

Usage:
  python -m tools.issue_gpt1_native_architectural_area_schedule \
    --pdf /private/owner/original.pdf \
    --sha256 <exact immutable SHA> \
    --project-id <project-source-scope> \
    --workspace-id 1 \
    --sealed-output /private/output/source_scheduled_area_run.json

It is never a customer quotation, floor area finish, or V2 score.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from pb_gpt1_native_architectural_area_schedule import issue_native_scheduled_areas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--workspace-id", type=int, required=True)
    p.add_argument("--sealed-output", type=Path, required=True)
    args = p.parse_args()
    if not args.pdf.is_file():
        raise ValueError("original PDF unavailable")
    output = issue_native_scheduled_areas(
        args.pdf.read_bytes(),
        expected_sha256=args.sha256,
        project_id=args.project_id,
        workspace_id=args.workspace_id,
    )
    if output.status != "SOURCE_FIRM_HANDOFF_ONLY" or output.sealed_run is None:
        raise RuntimeError("original source schedule FIRM handoff unavailable: "
                           + ", ".join(output.reason_codes))
    if output.customer_release_allowed or output.canonical_physical_floor_bound:
        raise RuntimeError("source-only handoff attempted commercial promotion")
    # Do not create or replace output unless the source scope and entire
    # authoritative issuer/sealed run have passed.
    if args.sealed_output.exists():
        raise FileExistsError("refusing to overwrite existing sealed quantities")
    args.sealed_output.parent.mkdir(parents=True, exist_ok=True)
    args.sealed_output.write_text(output.sealed_run.to_json(), encoding="utf-8")
    print({"source_sha256": output.source_sha256,
           "source_only_firm_area_count": len(output.quantities),
           "source_pages": output.repeated_source_pages,
           "signed_run_fingerprint": output.sealed_run.fingerprint,
           "customer_or_frozen_score_granted": False})


if __name__ == "__main__":
    main()
