"""Read-only, counts-only diagnostic for the internal door aperture review.

Reads ONE original PDF in place (SHA-checked), runs the real live collector for one page, then asks
``review_internal_door_apertures`` which canonical opening records lie inside each source-native internal door
aperture and which existing gate stops each aperture first. It never writes a kind, host, frame, area or quantity
and never seals, scores or publishes anything. The public output holds counts only; the full review (ids and
aperture boxes) goes only to an explicit private path outside the repository.

    python -m tools.diag_internal_door_aperture_review --pdf <original.pdf> --page-index 2 \
        --expected-source-sha256 <hex> --output counts.json [--private-output <path outside the repo>]

The collector can take several minutes on a dense page; run one heavy job at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import fitz

from pb_source_internal_door_aperture_review import (
    InternalDoorApertureReview,
    review_internal_door_apertures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def issuer_census(canonical_openings: Sequence[Any], published_quantities: Sequence[Any]) -> dict[str, Any]:
    """Counts from the existing issuer audit, or an explicit reason it could not be produced."""
    try:
        from pb_original_opening_area_gate_diagnostics import (
            audit_original_opening_area_gates,
        )

        audit = audit_original_opening_area_gates(canonical_openings, published_quantities)
    except Exception as exc:  # noqa: BLE001 - a diagnostic reports, it never raises past the caller
        return {"status": "UNAVAILABLE", "reason": type(exc).__name__}
    return {
        key: audit.get(key)
        for key in (
            "status", "source_opening_candidate_count", "published_opening_area_count",
            "observable_gate_counts", "source_kind_counts", "source_metric_basis_counts",
        )
    }


def run(
    pdf_path: Path,
    *,
    page_index: int,
    expected_source_sha256: str,
) -> tuple[InternalDoorApertureReview, dict[str, Any]]:
    raw = pdf_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_source_sha256:
        raise ValueError("original_source_sha256_mismatch")
    from pb_live_physical_net_wall_integration import (
        collect_live_physical_net_wall_claim,
    )

    with fitz.open(stream=raw, filetype="pdf") as document:
        page = document[page_index]
        drawings, words = tuple(page.get_drawings()), tuple(page.get_text("words"))
    claim = collect_live_physical_net_wall_claim(
        pdf_path, pages=(page_index,), recover_supported_opening_areas=True,
    )
    openings = tuple(claim.canonical_openings)
    review = review_internal_door_apertures(
        drawings, words, openings, page_index=page_index, expected_source_sha256=expected_source_sha256,
    )
    census = issuer_census(openings, tuple(claim.opening_quantity_evidence))
    census["canonical_opening_count"] = len(openings)
    census["claim_status"] = getattr(getattr(claim, "status", None), "value", str(getattr(claim, "status", "")))
    return review, census


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-index", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True, help="counts-only JSON")
    parser.add_argument("--private-output", type=Path, default=None, help="full review; must be outside the repo")
    args = parser.parse_args(argv)
    if args.private_output is not None and _is_inside(args.private_output, REPO_ROOT):
        print("refused: --private-output must be outside the repository", file=sys.stderr)
        return 2
    if _is_inside(args.output, REPO_ROOT) and "private" in args.output.name.lower():
        print("refused: a private-looking output path inside the repository", file=sys.stderr)
        return 2
    try:
        review, census = run(
            args.pdf, page_index=args.page_index, expected_source_sha256=args.expected_source_sha256,
        )
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    payload = {"review": review.to_public_summary(), "issuer_census": census}
    args.output.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    if args.private_output is not None:
        args.private_output.write_text(json.dumps(review.to_dict(), indent=1), encoding="utf-8")
    print(json.dumps(payload["review"]["state_counts"]), json.dumps(payload["review"]["first_open_gate_counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
