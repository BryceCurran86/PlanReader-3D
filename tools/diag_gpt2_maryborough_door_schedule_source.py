"""Owner-private original Maryborough A110/A600 door source cross-check.

Writes review-only source rows to a create-only local JSON file. Do NOT upload
original PDF, source coordinates, or this report to the public GitHub repo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_gpt2_maryborough_door_schedule_source import (
    audit_original_maryborough_door_schedule,
)
from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-pdf", type=Path, required=True)
    parser.add_argument("--output-private-json", type=Path, required=True)
    args = parser.parse_args()
    if args.original_pdf.is_symlink() or not args.original_pdf.is_file():
        parser.error("original source must be a regular owner-private file")
    if args.output_private_json.exists() or args.output_private_json.is_symlink():
        parser.error("refusing to replace an existing private evidence packet")
    report = audit_original_maryborough_door_schedule(
        args.original_pdf.read_bytes(), expected_sha256=MARYBOROUGH_SOURCE_SHA256,
    )
    args.output_private_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_private_json.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    rows = report.get("source_door_receipts", {})
    print(json.dumps({
        "status": report["status"],
        "source_sha256": MARYBOROUGH_SOURCE_SHA256,
        "source_only_rows": sorted(k for k,v in rows.items()
                                   if v.get("status") == "source_schedule_and_plan_words_only"),
        "new_firm_quantities": 0,
        "measurement_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
