from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import fitz
import numpy as np

import pb_raster_opening_source_primitives as primitives
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI,
    SourceVisibilityProducer,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _primitive_set(items):
    return set(items)


def _count_page(png_bytes: bytes) -> dict[str, int]:
    encoded = np.frombuffer(png_bytes, dtype=np.uint8)
    gray = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise RuntimeError("unreadable page render")

    mass = (gray < primitives.MASS_THRESHOLD).astype(np.uint8)
    line_mask = (gray < primitives.LINE_THRESHOLD).astype(np.uint8)
    solid = primitives._odd(
        primitives._px(primitives.POCHE_MIN_PT, RASTER_OPENING_PRIMITIVE_RENDER_DPI)
    )
    thick = cv2.morphologyEx(
        mass,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (solid, solid)),
    )
    halo = cv2.dilate(thick, np.ones((3, 3), np.uint8))
    thin_mask = (line_mask & (halo == 0)).astype(np.uint8)
    nonthick_mask = (line_mask & (thick == 0)).astype(np.uint8)

    band = _primitive_set(
        primitives._band_edge_primitives(
            thick,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
        )
    )
    raw_h = _primitive_set(
        primitives._raw_axis_line_run_primitives(
            line_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="horizontal",
        )
    )
    raw_v = _primitive_set(
        primitives._raw_axis_line_run_primitives(
            line_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="vertical",
        )
    )
    raw_nonthick_h = _primitive_set(
        primitives._raw_axis_line_run_primitives(
            nonthick_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="horizontal",
        )
    )
    raw_nonthick_v = _primitive_set(
        primitives._raw_axis_line_run_primitives(
            nonthick_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="vertical",
        )
    )
    thin_h = _primitive_set(
        primitives._axis_run_primitives(
            thin_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="horizontal",
        )
    )
    thin_v = _primitive_set(
        primitives._axis_run_primitives(
            thin_mask,
            dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
            axis="vertical",
        )
    )

    current = band | raw_h | raw_v | thin_h | thin_v
    nonthick = band | raw_nonthick_h | raw_nonthick_v | thin_h | thin_v

    return {
        "image_height_px": int(gray.shape[0]),
        "image_width_px": int(gray.shape[1]),
        "ink_pixels": int(np.count_nonzero(line_mask)),
        "thick_pixels": int(np.count_nonzero(thick)),
        "nonthick_ink_pixels": int(np.count_nonzero(nonthick_mask)),
        "band_primitives": len(band),
        "raw_horizontal": len(raw_h),
        "raw_vertical": len(raw_v),
        "raw_total": len(raw_h | raw_v),
        "raw_nonthick_horizontal": len(raw_nonthick_h),
        "raw_nonthick_vertical": len(raw_nonthick_v),
        "raw_nonthick_total": len(raw_nonthick_h | raw_nonthick_v),
        "thin_horizontal": len(thin_h),
        "thin_vertical": len(thin_v),
        "thin_total": len(thin_h | thin_v),
        "current_total_unique": len(current),
        "nonthick_total_unique": len(nonthick),
        "current_over_bound": int(len(current) > primitives.MAX_PRIMITIVES),
        "nonthick_over_bound": int(len(nonthick) > primitives.MAX_PRIMITIVES),
    }


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(
            f"source sha mismatch: expected {EXPECTED_SOURCE_SHA}, got {source_sha}"
        )

    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        page_ids = tuple(str(i + 1) for i in range(doc.page_count))

    producer = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_primitive_explosion",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-primitive-explosion",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=page_ids,
    )

    source_observation_producer = producer._producer
    rows = []
    for page_id in page_ids:
        image_regions = source_observation_producer.native_page_image_regions(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
        )
        if not image_regions:
            continue
        png_bytes, _page_parent = source_observation_producer.render_native_page_png(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
            images_only=True,
        )
        counts = _count_page(png_bytes)
        rows.append(
            {
                "page_id": page_id,
                "embedded_image_regions": len(image_regions),
                **counts,
            }
        )

    payload = {
        "source_sha256": source_sha,
        "render_dpi": RASTER_OPENING_PRIMITIVE_RENDER_DPI,
        "max_primitives": primitives.MAX_PRIMITIVES,
        "pages_with_images": len(rows),
        "pages_over_bound_current": [
            row["page_id"] for row in rows if row["current_over_bound"]
        ],
        "pages_over_bound_nonthick": [
            row["page_id"] for row in rows if row["nonthick_over_bound"]
        ],
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
