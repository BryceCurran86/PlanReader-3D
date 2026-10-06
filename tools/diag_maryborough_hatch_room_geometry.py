from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import fitz

from pb_cross_view_room_area_authority import _trusted_lines_for_page
from pb_hatch_detection_v160 import detect_hatch_patterns
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "11"
TARGETS = (
    "FOOD PREP",
    "COLD ROOM",
    "FREEZER",
    "DRY STORE",
    "SALES",
    "WASH UP",
    "FOOD SERVICE",
    "POS COUNTER",
    "M-AMB",
    "F-AMB",
    "TRUCK DRIVER LOUNGE",
    "PWD",
    "AIRLOCK",
    "LAUNDRY",
    "OFFICE",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _inside(point: tuple[float, float], polygon) -> bool:
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = map(float, polygon[i])
        xj, yj = map(float, polygon[j])
        if ((yi > y) != (yj > y)):
            denom = yj - yi
            if abs(denom) > 1e-12:
                hit_x = (xj - xi) * (y - yi) / denom + xi
                if x < hit_x:
                    inside = not inside
        j = i
    return inside


def _area_page_pts2(polygon) -> float:
    if not polygon or len(polygon) < 3:
        return 0.0
    total = 0.0
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        total += float(x1) * float(y2) - float(x2) * float(y1)
    return abs(total) * 0.5


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()

    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-hatch-room-geometry",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diag-maryborough-source.pdf",
        page_ids=(PAGE_ID,),
    )

    trusted = _trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_labels=TARGETS,
    )
    trusted = tuple(line for line in trusted if _norm(line.text) in TARGETS)

    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(int(PAGE_ID) - 1)
        evidence, clusters, diagnostics = detect_hatch_patterns(
            page,
            scale_info=None,
            words=None,
        )
    finally:
        pdf.close()

    usable = [
        item
        for item in evidence
        if item.polygon_pdf_pts
        and item.geometry_method != "bbox_fallback"
        and math.isfinite(float(item.geometry_confidence))
        and float(item.geometry_confidence) > 0.0
    ]

    rows = {}
    for label in TARGETS:
        lines = [line for line in trusted if _norm(line.text) == label]
        label_rows = []
        for line in lines:
            center = (
                (float(line.bbox[0]) + float(line.bbox[2])) * 0.5,
                (float(line.bbox[1]) + float(line.bbox[3])) * 0.5,
            )
            containing = [
                {
                    "surface_id": item.surface_id,
                    "geometry_method": item.geometry_method,
                    "geometry_confidence": float(item.geometry_confidence),
                    "source_geometry_type": item.source_geometry_type,
                    "bbox": list(item.bbox),
                    "polygon_vertex_count": len(item.polygon_pdf_pts),
                    "area_page_pts2": _area_page_pts2(item.polygon_pdf_pts),
                }
                for item in usable
                if _inside(center, item.polygon_pdf_pts)
            ]
            label_rows.append(
                {
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "center": list(center),
                    "source_partition_id": line.source_partition_id,
                    "block_no": line.block_no,
                    "line_no": line.line_no,
                    "containing_hatch_count": len(containing),
                    "containing_hatches": sorted(
                        containing,
                        key=lambda row: (
                            row["area_page_pts2"],
                            row["surface_id"],
                        ),
                    ),
                }
            )
        rows[label] = {
            "trusted_line_count": len(lines),
            "lines": label_rows,
            "unique_single_hatch_line_count": sum(
                row["containing_hatch_count"] == 1 for row in label_rows
            ),
        }

    print(
        json.dumps(
            {
                "source_sha256": source_sha,
                "page_id": PAGE_ID,
                "mode": "DIAGNOSTIC_ONLY_AUTHENTICATED_LABEL_TO_HATCH_REGION",
                "trusted_target_line_count": len(trusted),
                "hatch_diagnostics": diagnostics,
                "hatch_evidence_count": len(evidence),
                "usable_non_bbox_hatch_count": len(usable),
                "targets": rows,
                "elapsed_seconds": time.perf_counter() - started,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
