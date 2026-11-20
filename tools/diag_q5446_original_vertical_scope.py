"""Private-original Q5446 vertical/insulation/tiling scope review only.

Only original SHA-approved roles are read; emitted JSON contains no PDF pages,
source drawings, client data, customer quantities or guessed installed heights.
Use: python -m tools.diag_q5446_original_vertical_scope
    --plan PRIVATE_PLAN.pdf --inclusions PRIVATE_INCLUSIONS.pdf
    --sales PRIVATE_SALES.pdf --out PRIVATE_NEW_REPORT.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_q5446_original_vertical_scope_authority import (
    inspect_original_q5446_vertical_scope,
)


def write_review(
    original_plan: Path,
    inclusions: Path,
    sales: Path,
    out: Path,
) -> dict[str, object]:
    """Strict append-only private-source review, no signed/customer publication."""
    source_paths = tuple(
        Path(path).resolve(strict=False)
        for path in (original_plan, inclusions, sales)
    )
    target = Path(out)
    # Output never replaces an input (including symlink/path aliases), a
    # frozen benchmark file, or another earlier signed/diagnostic report.
    if target.exists() or target.is_symlink():
        raise ValueError("vertical_scope_review_output_must_be_new")
    destination = target.resolve(strict=False)
    if any(destination == path for path in source_paths):
        raise ValueError("vertical_scope_review_cannot_replace_source")
    if destination.suffix.casefold() != ".json":
        raise ValueError("vertical_scope_review_requires_json_destination")
    if any(destination.is_relative_to(path.parent) for path in source_paths):
        raise ValueError("vertical_scope_review_output_inside_source_folder")
    review = inspect_original_q5446_vertical_scope(
        original_plan, inclusions, sales,
    )
    result: dict[str, object] = {
        "schema_version": "q5446-original-vertical-scope-review-v1",
        "source_review": review.to_dict(),
        "original_customer_quantities_emitted": 0,
        "benchmark_score_granted": False,
        "official_four_project_accuracy": None,
    }
    # The parent directory must exist; fail closed if symlink alias changes.
    if not target.parent.is_dir():
        raise ValueError("vertical_scope_review_output_parent_unavailable")
    with target.open("x", encoding="utf8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--inclusions", type=Path, required=True)
    parser.add_argument("--sales", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = write_review(args.plan, args.inclusions, args.sales, args.out)
    print(json.dumps({
        "status": result["source_review"]["status"],
        "benchmark_score_granted": False,
        "original_customer_quantities_emitted": 0,
    }, sort_keys=True))
    return 0 if result["source_review"]["status"] == (
        "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
