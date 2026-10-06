from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    import fitz
    with fitz.open(str(PDF)) as doc:
        selected = tuple(range(doc.page_count))

    scope = source_floor_plan_topology_scope(PDF, selected)
    if scope is None:
        raise SystemExit("source floor-plan scope unavailable")

    payload = {
        "source_sha256": source_sha,
        "page_count": len(selected),
        **scope.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
