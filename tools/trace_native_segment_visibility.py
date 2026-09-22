from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import fitz

from pb_source_visibility_authority import classify_native_segment_visibility
from pb_vector_geometry_v130 import extract_native_page


def page_stats(page, page_number: int):
    native = extract_native_page(page)
    segments = list(native.get("segments") or ())
    reasons = collections.Counter()
    visible = 0
    clip_known = collections.Counter()
    clip_present = collections.Counter()
    samples = []
    for seg in segments:
        decision = classify_native_segment_visibility(seg)
        if decision.visible:
            visible += 1
        else:
            reasons.update(decision.reason_codes)
        clip_known[str(seg.get("clip_known"))] += 1
        clip_present[str(seg.get("clip_present"))] += 1
        if len(samples) < 12:
            samples.append({
                "id": seg.get("id"),
                "clip_known": seg.get("clip_known"),
                "clip_present": seg.get("clip_present"),
                "clip": seg.get("clip"),
                "geometry": [seg.get("x1"), seg.get("y1"), seg.get("x2"), seg.get("y2")],
                "visible": decision.visible,
                "reason_codes": list(decision.reason_codes),
            })
    return {
        "page_number": page_number,
        "segment_count": len(segments),
        "visible_segment_count": visible,
        "rejected_segment_count": len(segments) - visible,
        "reason_counts": dict(reasons),
        "clip_known_counts": dict(clip_known),
        "clip_present_counts": dict(clip_present),
        "xobject_count": len(page.get_xobjects() or ()),
        "sample_segments": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", required=True)
    args = parser.parse_args()
    doc = fitz.open(str(args.pdf))
    try:
        pages = [int(v.strip()) for v in args.pages.split(",") if v.strip()]
        print(json.dumps({"pages": [page_stats(doc[p-1], p) for p in pages]}, indent=2, sort_keys=True, default=str))
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
