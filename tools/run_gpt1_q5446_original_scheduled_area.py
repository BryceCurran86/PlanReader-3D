"""Replay five source-declared Q5446 scheduled m2 receipts on owner-private PDF.

Use outside the public checkout for output artifacts. Source remains private:
    python tools/run_gpt1_q5446_original_scheduled_area.py \
      --source-pdf "/private/Q5446_Standard_Plans_V1_20220320.pdf" \
      --workspace-id 1 \
      --output "/private/receipts/q5446_architectural_area_source_seal.json"

Output: original source V1 SHA fingerprinted sealed run, not a customer BOQ
or official four-project benchmark score. No PDFs or rendering are exported.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pdf", required=True, type=str)
    parser.add_argument("--workspace-id", type=int, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    # The tools directory is nested under the public repo: allow invoking
    # with python tools/... from an arbitrary private owner working folder.
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from pb_gpt1_q5446_source_declared_area_firm_handoff import (
        issue_original_q5446_scheduled_area_handoff,
    )

    result = issue_original_q5446_scheduled_area_handoff(
        args.source_pdf, workspace_id=args.workspace_id
    )
    if result.status != "SOURCE_FIRM_HANDOFF_ONLY" or result.sealed_run is None:
        print(
            "ABSTAIN: " + ", ".join(result.reason_codes),
            file=sys.stderr,
        )
        return 2
    sealed = result.sealed_run
    if len(sealed.quantities) != 5 or any(
        not row.lineage_ok or row.abstained
        for row in sealed.quantities
    ):
        print("ABSTAIN: sealed_source_lineage_invalid", file=sys.stderr)
        return 2

    if args.output is not None:
        target = args.output.expanduser().resolve()
        # The owner must consciously select a PRIVATE destination. Never
        # write any source-derived receipt into the public repo checkout.
        if target.is_relative_to(root):
            print("ABSTAIN: refusing to save receipts inside public repo", file=sys.stderr)
            return 2
        if not target.parent.is_dir():
            print("ABSTAIN: output parent directory does not exist", file=sys.stderr)
            return 2
        if target.exists():
            print("ABSTAIN: output already exists; no overwrites", file=sys.stderr)
            return 2
        target.write_text(sealed.to_json(), encoding="utf-8")
    print(
        f"SOURCE_FIRM_HANDOFF_ONLY 5 architectural_scheduled_area m2 records; "
        f"sealed_fingerprint={sealed.fingerprint}; "
        "customer=false benchmark=UNPUBLISHED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
