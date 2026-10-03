#!/usr/bin/env python3
"""CONTROL ONLY: how many compact source callouts coincide with a raster-proven opening.

This is a read-only comparison for reviewers. It never feeds anything back: the raster
authority (pb_raster_opening_existence_shadow) reads no text, and a callout can neither
create nor move a physical opening. The association below restates the label-binding
rule of pb_opening_label_dimension_authority (label centre inside the gap along the
wall, and within max(3 x glyph height, 2 x wall thickness) across it) purely to count
which callouts would find exactly one independently proven opening.

    python scripts/raster_opening_callout_control.py --pdf plan.pdf --page 3
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

import pb_raster_opening_existence_shadow as shadow  # noqa: E402
import pb_source_plan_opening_callout as callouts  # noqa: E402

COORD_TOL = 1e-3


def _label_vs_opening(
    bbox: tuple[float, float, float, float], record: shadow.RasterOpeningExistenceRecord
) -> tuple[bool, float, float, float]:
    """(binds, distance outside the span along the wall, cross offset, cross allowance)."""
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    gx0, gy0, gx1, gy1 = record.gap_box_pt
    glyph = max(COORD_TOL, min(abs(x1 - x0), abs(y1 - y0)))
    if record.axis == "horizontal":
        lo, hi, along, cross, centre, spread = gx0, gx1, cx, cy, (gy0 + gy1) / 2.0, gy1 - gy0
    else:
        lo, hi, along, cross, centre, spread = gy0, gy1, cy, cx, (gx0 + gx1) / 2.0, gx1 - gx0
    outside = max(lo - along, along - hi, 0.0)
    allowance = max(3.0 * glyph, 2.0 * spread)
    offset = abs(cross - centre)
    return outside <= COORD_TOL and offset <= allowance + COORD_TOL, outside, offset, allowance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True, help="1-based page number")
    args = parser.parse_args(argv)

    payload = args.pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        result = shadow.propose_raster_opening_existence(doc, args.page - 1, source_sha256=sha)
        found = callouts.extract_source_plan_opening_callouts(
            doc[args.page - 1], source_sha256=sha, source_page=args.page
        )
    finally:
        doc.close()
    print(f"CONTROL ONLY: {len(found)} compact callouts, {len(result.records)} raster-proven openings")
    exactly_one = 0
    for callout in found:
        matches = []
        nearest = None
        for record in result.records:
            binds, outside, offset, allowance = _label_vs_opening(callout.bbox, record)
            if binds:
                matches.append(record)
            else:
                gx0, gy0, gx1, gy1 = record.gap_box_pt
                cx, cy = (callout.bbox[0] + callout.bbox[2]) / 2.0, (callout.bbox[1] + callout.bbox[3]) / 2.0
                distance = math.hypot(max(gx0 - cx, 0.0, cx - gx1), max(gy0 - cy, 0.0, cy - gy1))
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, outside, offset, allowance, record)
        exactly_one += len(matches) == 1
        if len(matches) == 1:
            record = matches[0]
            detail = (
                f"opening {record.record_id[-8:]} {record.axis} gap={record.gap_length_pt:.1f}pt "
                f"{[e.kind for e in record.symbol_evidence]}"
            )
        elif matches:
            detail = f"{len(matches)} openings on the label axis"
        elif nearest is not None:
            distance, outside, offset, allowance, record = nearest
            detail = (
                f"no binding; nearest proven opening {record.record_id[-8:]} {record.axis} "
                f"gap={record.gap_length_pt:.1f}pt is {distance:.1f}pt from the label centre "
                f"({outside:.1f}pt outside the span along the wall, {offset:.1f}pt across, "
                f"allowance {allowance:.1f}pt)"
            )
        else:
            detail = "no proven opening on the page"
        print(f"  {callout.raw_callout:<22} -> {detail}")
    print(f"callouts with exactly one raster-proven opening under the label-binding rule: {exactly_one} of {len(found)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
