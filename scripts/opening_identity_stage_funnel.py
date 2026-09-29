from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_item35_production_authority_shadow import collect_item35_authority_shadow
from pb_opening_identity_stage_funnel import build_opening_identity_stage_funnel


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print gold-free stage-wise diagnostics from the existing Item35 shadow chain."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf", type=Path)
    group.add_argument("--shadow-json", type=Path)
    parser.add_argument("--document-id")
    parser.add_argument("--pages", nargs="*", type=int)
    args = parser.parse_args()

    if args.shadow_json is not None:
        shadow = json.loads(args.shadow_json.read_text(encoding="utf-8"))
    else:
        shadow = collect_item35_authority_shadow(
            args.pdf,
            document_id=args.document_id,
            pages=args.pages,
        )

    report = build_opening_identity_stage_funnel(shadow)
    print(json.dumps(report, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
