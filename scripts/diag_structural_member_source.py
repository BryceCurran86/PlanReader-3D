#!/usr/bin/env python3
"""TEST-ONLY source diagnosis for structural member evidence.

The probe reads drawing evidence only. It never loads benchmark expected values.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import fitz

from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_secondary_area_support_evidence import (
    extract_secondary_area_support_evidence_from_page,
)
from pb_viewport_segmentation import segment_page_viewports


SUPPORT_RE = re.compile(
    r"\b(?:masonry\s+piers?|piers?|pillars?|columns?|posts?|"
    r"CHS|RHS|SHS|circular\s+hollow|square\s+hollow|structural\s+steel)\b",
    re.IGNORECASE,
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, fitz.Rect):
        return [float(value.x0), float(value.y0), float(value.x1), float(value.y1)]
    if isinstance(value, fitz.Point):
        return [float(value.x), float(value.y)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _matching_text_blocks(page):
    out = []
    for block in page.get_text("blocks") or ():
        text = " ".join(str(block[4]).split()).strip()
        if text and SUPPORT_RE.search(text):
            out.append({
                "text": text,
                "bbox": [float(v) for v in block[:4]],
            })
    return out


def _small_closed_geometry(page):
    page_scale = max(1.0, min(float(page.rect.width), float(page.rect.height)))
    max_side = page_scale * 0.08
    rows = []
    for index, drawing in enumerate(page.get_drawings() or ()):
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if width <= 0.0 or height <= 0.0 or width > max_side or height > max_side:
            continue
        items = tuple(drawing.get("items") or ())
        kinds = [str(item[0]) for item in items if item]
        is_closedish = (
            bool(drawing.get("closePath"))
            or kinds == ["re"]
            or (len(kinds) >= 3 and all(kind in {"l", "c", "re"} for kind in kinds))
        )
        if not is_closedish:
            continue
        rows.append({
            "drawing_index": index,
            "bbox": [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
            "width": width,
            "height": height,
            "aspect_ratio": max(width, height) / min(width, height),
            "fill": _jsonable(drawing.get("fill")),
            "color": _jsonable(drawing.get("color")),
            "line_width": drawing.get("width"),
            "close_path": bool(drawing.get("closePath")),
            "item_kinds": kinds,
        })
    return rows


def _dimension_summary(page, page_num):
    try:
        chains = extract_dimension_chains_from_page(
            page,
            page_num=page_num,
            view_id=f"page_{page_num}",
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}", "chains": []}
    rows = []
    for chain in chains:
        rows.append({
            "chain_id": str(chain.chain_id),
            "view_id": str(chain.view_id),
            "source_page": int(chain.source_page),
            "orientation": str(chain.orientation),
            "values_m": [float(obs.value_m) for obs in chain.observations],
            "texts": [str(obs.raw_text) for obs in chain.observations],
            "bboxes": [
                None if obs.bbox is None else [float(v) for v in obs.bbox]
                for obs in chain.observations
            ],
        })
    return {"chains": rows}


def _viewport_summary(page, page_num):
    try:
        viewports = segment_page_viewports(page, page_number=page_num)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}", "viewports": []}
    return {
        "viewports": [
            {
                "view_id": str(v.view_id),
                "view_type": str(v.view_type),
                "status": str(v.status),
                "bounding_box": (
                    None if v.bounding_box is None else [float(x) for x in v.bounding_box]
                ),
                "boundary_source": str(v.boundary_source),
            }
            for v in viewports
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--page-start", required=True, type=int)
    parser.add_argument("--page-end", required=True, type=int)
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()

    doc = fitz.open(stream=payload, filetype="pdf")
    pages = []
    try:
        for page_num in range(args.page_start, args.page_end + 1):
            page = doc.load_page(page_num - 1)
            text_blocks = _matching_text_blocks(page)
            dimensions = _dimension_summary(page, page_num)
            physical_support = None
            try:
                physical_support = extract_secondary_area_support_evidence_from_page(
                    page,
                    source_page=page_num,
                )
            except Exception as exc:
                physical_support = {"error": f"{type(exc).__name__}:{exc}"}
            pages.append({
                "page": page_num,
                "support_text_blocks": text_blocks,
                "support_keyword_count": len(text_blocks),
                "small_closed_geometry": _small_closed_geometry(page),
                "dimensions": dimensions,
                "viewports": _viewport_summary(page, page_num),
                "existing_secondary_support_evidence": _jsonable(physical_support),
            })
    finally:
        doc.close()

    structural_predictions = []
    extractor_status = {"diagnostic_mode": "source_only"}
    if not args.source_only:
        extractor = GenericPlanReaderExtractor()
        predictions = extractor.extract_from_pdf(
            path,
            pages=tuple(range(args.page_start - 1, args.page_end)),
            collect_item35_shadow=False,
        )
        for prediction in predictions:
            row = prediction.to_dict()
            haystack = " ".join(
                [
                    str(row.get("tag") or ""),
                    str(row.get("trade_type") or ""),
                    str(row.get("description") or ""),
                ]
            )
            if (
                str(row.get("trade_type") or "").lower() == "structure"
                or SUPPORT_RE.search(haystack)
            ):
                structural_predictions.append(row)
        extractor_status = _jsonable(extractor.extraction_status)

    result = {
        "project": args.project,
        "source_sha256": source_sha,
        "page_start": args.page_start,
        "page_end": args.page_end,
        "pages": pages,
        "structural_predictions": structural_predictions,
        "extractor_status": extractor_status,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "project": args.project,
        "source_sha256": source_sha,
        "pages_with_support_text": [
            row["page"] for row in pages if row["support_text_blocks"]
        ],
        "structural_prediction_tags": [
            row.get("tag") for row in structural_predictions
        ],
        "closed_geometry_counts": {
            str(row["page"]): len(row["small_closed_geometry"])
            for row in pages
            if row["small_closed_geometry"]
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
