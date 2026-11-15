"""Read-only joined/outside/unresolved census for #4347 native exterior endpoints.

No customer quantities, no PDF copy, no 2.5 pt join.
Use: py -3.13 tools/run_source_native_exterior_endpoint_audit.py --pdf house.pdf --page 2 --out-dir C:\\private\\endpoint-audit
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_source_native_exterior_endpoint_authority_shadow import (  # noqa: E402
    audit_source_native_exterior_endpoints,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    raw = args.pdf.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    import fitz
    with fitz.open(stream=raw, filetype="pdf") as doc:
        drawings = doc[args.page].get_drawings()
    report = audit_source_native_exterior_endpoints(drawings)
    report["source_sha256"] = sha
    report["page_index_0based"] = args.page
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dest = args.out_dir / f"page_{args.page + 1}_exterior_endpoint_audit.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "wrote": str(dest),
        "sha": sha,
        "exterior": report["exterior_preflight_status"],
        "reason": report["exterior_preflight_reason"],
        "components": report["component_count"],
        "open_endpoints": report["open_endpoint_count"],
        "near_misses": report["near_miss_total"],
        "joined_candidates": report["joined_candidate_count"],
        "competing_non_wall": report["competing_non_wall_count"],
        "unresolved_near_miss": report["unresolved_near_miss_count"],
        "path_role_counts": report.get("path_role_counts") or {},
        "rejected_diagonals": report.get("rejected_diagonal_bridge_count") or 0,
        "exclusions": report.get("exclusion_count") or 0,
        "measurement_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
