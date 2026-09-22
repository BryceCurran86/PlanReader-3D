from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


TARGET_TAGS = {
    "perimeter_walling",
    "internal_plaster",
    "internal_paint",
    "external_key_pointing",
    "external_render",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page-indexes", required=True)
    args = parser.parse_args()

    # Item35 is a shadow-only diagnostic and is owned by PR #612. Disable it
    # in this trace harness only; it never mutates pred_dict/F.9 wall output.
    import pb_item35_production_authority_shadow as item35_shadow

    original_collect = item35_shadow.collect_item35_authority_shadow
    item35_shadow.collect_item35_authority_shadow = lambda *a, **k: {
        "status": "abstained",
        "reason": "disabled_in_wall_lane_diagnostic",
        "commercial_count_unlocked": False,
    }
    try:
        extractor = GenericPlanReaderExtractor()
        pages = [int(x.strip()) for x in args.page_indexes.split(",") if x.strip()]
        predictions = extractor.extract_from_pdf(args.pdf, pages=pages)
    finally:
        item35_shadow.collect_item35_authority_shadow = original_collect

    rows = []
    for pred in predictions:
        if pred.tag not in TARGET_TAGS:
            continue
        rows.append(
            {
                "tag": pred.tag,
                "quantity": pred.quantity,
                "unit": pred.unit,
                "source_page": pred.source_page,
                "dimensions": pred.dimensions,
                "metadata": pred.metadata,
                "description": pred.description,
            }
        )

    payload = {
        "target_predictions": rows,
        "extraction_status": extractor.extraction_status,
        "hosted_opening_shadow": extractor.hosted_opening_shadow,
        "opening_provenance_shadow": extractor.opening_provenance_shadow,
        "opening_authority_shadow": extractor.opening_authority_shadow,
        "item35_authority_shadow": extractor.item35_authority_shadow,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
