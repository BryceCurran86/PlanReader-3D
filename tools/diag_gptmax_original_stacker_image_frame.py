"""Read-only original source image-frame witness for 2127 STACKER.

One native image placement can cover both authentic wall ink flanks, the
physical G17 aperture and its native text address. This proves common PIXEL
registration only; no structural host, kind, frame, count or area is issued.
"""
from __future__ import annotations

from hashlib import sha256
import math
from pathlib import Path
from typing import Mapping, Sequence
import json

import fitz

SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
# Source-only diagnostic fixture addresses. They are never prediction inputs.
STACKER_REGIONS = {
    "left_original_ink_bbox_pt": (716.16, 426.48, 760.32, 429.36),
    "g17_aperture_bbox_pt": (760.56, 426.48, 835.44, 429.36),
    "right_original_ink_bbox_pt": (836.4, 426.48, 949.68, 429.36),
    "native_2127_text_bbox_pt": (783.594849, 435.174072, 813.601257, 440.850464),
}


def unique_native_image_frame(
    image_placements: Sequence[Mapping[str, object]],
    regions: Mapping[str, Sequence[float]],
) -> dict[str, object] | None:
    """Require exactly ONE unrotated, source-owned image for every region."""
    if not isinstance(regions, Mapping) or len(regions) < 2:
        return None
    boxes = []
    for raw in regions.values():
        try:
            vals = tuple(float(v) for v in raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if (len(vals) != 4 or not all(math.isfinite(v) for v in vals)
                or vals[2] <= vals[0] or vals[3] <= vals[1]):
            return None
        boxes.append(vals)

    candidates = []
    for row in image_placements:
        if not isinstance(row, Mapping):
            return None
        try:
            xref, width, height = (row[x] for x in ("xref", "width", "height"))
            bbox = tuple(float(v) for v in row["bbox"])
            transform = tuple(float(v) for v in row["transform"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if (any(type(v) is not int or v <= 0 for v in (xref, width, height))
                or len(bbox) != 4 or len(transform) != 6
                or not all(math.isfinite(v) for v in (*bbox, *transform))):
            return None
        a, b, c, d, e, f = transform
        if (a <= 0 or d <= 0 or abs(b) > 1e-6 or abs(c) > 1e-6
                or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]
                or not math.isclose(a, bbox[2]-bbox[0], rel_tol=0, abs_tol=1e-3)
                or not math.isclose(d, bbox[3]-bbox[1], rel_tol=0, abs_tol=1e-3)
                or not math.isclose(e, bbox[0], rel_tol=0, abs_tol=1e-3)
                or not math.isclose(f, bbox[1], rel_tol=0, abs_tol=1e-3)):
            continue
        if all(
            bbox[0] <= box[0] and bbox[1] <= box[1]
            and box[2] <= bbox[2] and box[3] <= bbox[3]
            for box in boxes
        ):
            candidates.append({
                "source_image_xref": xref,
                "native_pixel_dimensions": [width, height],
                "source_image_bbox_pt": list(bbox),
                "source_image_transform": list(transform),
                "native_pixel_scales_pt": [a / width, d / height],
            })
    return candidates[0] if len(candidates) == 1 else None


def source_verified_stacker_image_frame(original_pdf: bytes) -> dict[str, object]:
    """SHA-verified original page 3 placement; NOT a W4 wall or area grant."""
    if type(original_pdf) is not bytes or sha256(original_pdf).hexdigest() != SOURCE_SHA:
        raise ValueError("exact original Lot16 REV E PDF is required")
    with fitz.open(stream=original_pdf, filetype="pdf") as doc:
        if len(doc) != 13 or doc[2].rotation != 0:
            raise ValueError("original source page count or orientation changed")
        evidence = unique_native_image_frame(
            doc[2].get_image_info(xrefs=True), STACKER_REGIONS,
        )
    if evidence is None:
        raise ValueError("same original image-frame source ownership unproved")
    return {
        "status": "original_stacker_single_native_image_frame_witness",
        "source_sha256": SOURCE_SHA,
        "page_id": "3",
        "source_regions": {k: list(v) for k, v in STACKER_REGIONS.items()},
        "image_frame": evidence,
        "single_native_image_frame_proven": True,
        "independent_original_ink_flanks_required": True,
        "physical_wall_host_proven": False,
        "wall_candidate_equivalence_proven": False,
        "connected_whole_wall_frame_proven": False,
        "opening_count_or_area_publication_granted": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.pdf.resolve() == args.output.resolve():
        raise ValueError("original PDF must not be overwritten")
    report = source_verified_stacker_image_frame(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+"\n")
    print("Original same-image source frame proven; no host or quantity promoted")


if __name__ == "__main__":
    main()
