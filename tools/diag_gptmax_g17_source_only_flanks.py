"""Shadow-only closed G17 flank inventory from *already authenticated* receipts.

Input is the original source-verified G17-to-parent audit sidecar. It does not
render, mutate source snapshots, select walls, publish hosts, assume dimensions,
or infer construction quantities.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping




from pb_raster_g17_source_shadow import source_only_closed_flanks


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    original = json.loads(args.source_report.read_text(encoding="utf-8"))
    receipts = original.get("unhosted_raster_flank_source_receipts")
    if not isinstance(receipts, list):
        raise ValueError("authenticated source flank sidecar missing")
    result = [source_only_closed_flanks(r) for r in receipts]
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
