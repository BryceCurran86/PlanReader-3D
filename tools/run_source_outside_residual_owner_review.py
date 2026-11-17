"""Private SHA-locked original PDF outside-wall residual receipt.

Reviewer diagnostic only, never physical or commercial authority. Keep the
original and this report OUTSIDE a public repository checkout. This uses the
existing PlanReader source-native outer-wall preflight, not a new tracer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first


def _receipt(attempt: Any, source_sha256: str, page_index: int) -> dict[str, Any]:
    walk = attempt.source_outside_face_walk
    if walk is None:
        return {
            "source_sha256": source_sha256,
            "page_index_0based": page_index,
            "status": "ABSTAINED",
            "reason": "source_outside_face_walk_unavailable",
            "bands": [],
            "building_footprint_authenticated": False,
            "measurement_authorized": False,
        }
    rows = walk.to_dict()
    return {
        "source_sha256": source_sha256,
        "page_index_0based": page_index,
        "status": walk.status,
        "reason": walk.reason,
        "enclosed_dwelling_zone_count": walk.enclosed_dwelling_zone_count,
        "unresolved_band_count": walk.other_source_wall_band_count,
        "unresolved_local_native_path_ids": rows.get(
            "unresolved_outside_native_path_id_sample", []
        ),
        "bands": rows.get("unresolved_outside_band_review_sample", []),
        "all_unresolved_bands_in_sample": (
            walk.other_source_wall_band_count <= 32
            and len(rows.get("unresolved_outside_band_review_sample", []))
                == walk.other_source_wall_band_count
        ),
        "building_footprint_authenticated": False,
        "measurement_authorized": False,
        "commercial_quantity_rows": 0,
        "source_owned_candidate_only": True,
    }


def _outside_checkout(path: Path, checkout: Path) -> bool:
    candidate = path.resolve(strict=False)
    root = checkout.resolve()
    return candidate != root and root not in candidate.parents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--page-index", type=int, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if (
        len(args.expected_sha256) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in args.expected_sha256)
        or args.page_index < 0
    ):
        parser.error("SHA must be 64 hex digits and page index nonnegative")
    repo = Path(__file__).resolve().parents[1]
    if not _outside_checkout(args.pdf, repo) or not _outside_checkout(args.private_output, repo):
        parser.error("private original PDF and output must remain outside public repo checkout")
    raw = args.pdf.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != args.expected_sha256.lower():
        parser.error("SHA-256 mismatch; original source not authenticated")
    import fitz

    with fitz.open(stream=raw, filetype="pdf") as original:
        if args.page_index >= len(original):
            parser.error("page index outside original PDF")
        page = original[args.page_index]
        drawings = tuple(page.get_drawings())
        words = tuple(page.get_text("words"))
        attempt = attempt_source_native_outer_wall_first(
            drawings, source_words=words,
            window_source_drawings=drawings,
            source_page_index=args.page_index,
        )
    report = _receipt(attempt, digest, args.page_index)
    target = args.private_output.resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    print(json.dumps({
        "status": report["status"],
        "unresolved_band_count": report.get("unresolved_band_count", 0),
        "all_unresolved_bands_in_sample": report.get("all_unresolved_bands_in_sample", False),
        "private_output": str(target),
        "measurement_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
