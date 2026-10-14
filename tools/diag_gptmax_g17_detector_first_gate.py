"""Reproduce every raster-G17 terminal source gate without publishing any wall.

Inputs are an original-SHA stage report with *authenticated* G17 source receipts
and its exact original PDF. This process independently re-renders the PDF with
the existing source producer, then audits 144-DPI raster capture, 300-DPI
terminal paint, image tile containment and ordinary-segment suppression.

It never calls an opening-host publisher, changes an accepted source snapshot
outside this diagnostic process, publishes a W4 wall, or produces a quantity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_raster_unchanged_band_segments import (
    band_segment_already_observed,
    detect_unchanged_terminal_band_segments,
)
from pb_raster_visible_segment_detector import detect_axis_aligned_raster_segments
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI,
    RASTER_RENDER_DPI,
    SourceVisibilityProducer,
    _axis_aligned_geometry_fully_covered_by_rect_union,
    _unchanged_segment_inside_flank,
)
from tools.diag_gptmax_g17_source_only_flanks import source_only_closed_flanks


def detector_source_first_gate_report(
    *,
    original_pdf: bytes,
    source_report: Mapping[str, Any],
    page_id: str,
) -> dict[str, Any]:
    """Return all candidates, fail-closed, without choosing an opening host."""
    sha = hashlib.sha256(original_pdf).hexdigest()
    if (source_report.get("source_sha256") != sha
            or source_report.get("primitive_safety_cap") != 20_000):
        raise ValueError("source report must match immutable original PDF and cap")
    if not isinstance(page_id, str) or not page_id.isdigit() or int(page_id) < 1:
        raise ValueError("original source page ID invalid")
    originals = source_report.get("unhosted_raster_flank_source_receipts")
    if not isinstance(originals, list) or not originals:
        raise ValueError("original authenticated G17 sidecar missing")
    original_rows = [row for row in originals if str(row.get("page_id")) == page_id]
    if not original_rows:
        raise ValueError("no authenticated unhosted G17 openings on source page")
    if any(row.get("snapshot_id") != source_report.get("snapshot_id")
           or row.get("source_sha256") != sha for row in original_rows):
        raise ValueError("G17 source receipt contradicts report snapshot")

    shadow = [source_only_closed_flanks(row) for row in original_rows]
    if len({row["physical_opening_id"] for row in shadow}) != len(shadow):
        raise ValueError("duplicate source opening identity")
    if any(not row["closed_source_flank_nomination"] for row in shadow):
        raise ValueError("unclosed original G17 source band must stay unavailable")

    # A NEW, private producer instance replays original bytes for this audit.
    # No accepted source snapshot, W4 scope or customer quantity is modified.
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=original_pdf,
        source_locator="memory://gptmax-original-source-detector-audit.pdf",
        page_ids=(page_id,),
    )
    pub = source.augment_with_raster_opening_primitives(
        pub.revision.revision_id, page_ids=(page_id,),
    )
    if pub.revision.source_sha256 != sha:
        raise RuntimeError("fresh source producer decoded a different PDF")
    args = dict(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id=page_id,
    )
    regions = source._producer.native_page_image_regions(**args)
    if not regions:
        raise ValueError("original source page has no image tile ownership")
    ordinary_png, _ = source._producer.render_native_page_png(
        **args, dpi=float(RASTER_RENDER_DPI),
    )
    ordinary = tuple(
        segment for segment in detect_axis_aligned_raster_segments(
            ordinary_png, dpi=RASTER_RENDER_DPI,
        )
        if _axis_aligned_geometry_fully_covered_by_rect_union(
            segment.geometry_pt, regions,
        )
    )
    g17_args = dict(args, dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                    include_native_frame=True)
    image_png, image_parent, image_frame = source._producer.render_native_page_png(
        **g17_args, images_only=True,
    )
    full_png, full_parent, full_frame = source._producer.render_native_page_png(
        **g17_args,
    )
    if image_parent != full_parent or image_frame != full_frame:
        raise RuntimeError("original image-only/full source render ownership changed")
    if int(image_frame.rotation) != 0:
        raise ValueError("rotated original source frame unsupported by terminal detector")
    raw = detect_unchanged_terminal_band_segments(
        image_png, full_png, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
        registration_scale=(
            source.raster_opening_registration_scale(
                pub.revision.revision_id, page_id,
            ) or (1.0, 1.0)
        ),
    )
    area_evidence = {
        row["opening_identity_id"]: row["result"]["evidence"]
        for row in source_report.get("opening_figured_label_traces", ())
        if isinstance(row, Mapping)
        and isinstance(row.get("result"), Mapping)
        and isinstance(row.get("opening_identity_id"), str)
    }
    stage_rows = []
    for opening in shadow:
        identity = opening["physical_opening_id"]
        for flank in opening["source_flank_boxes"]:
            box = (
                flank["orientation"],
                tuple(float(v) for v in flank["source_bbox_pdf_pts"]),
            )
            detected = [segment for segment in raw if
                _unchanged_segment_inside_flank(
                    segment, box, dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                )
            ]
            covered = [segment for segment in detected if
                _axis_aligned_geometry_fully_covered_by_rect_union(
                    segment.geometry_pt, regions,
                )
            ]
            retained = [segment for segment in covered if not
                band_segment_already_observed(
                    segment, ordinary,
                    dpi=RASTER_OPENING_PRIMITIVE_RENDER_DPI,
                    ordinary_dpi=RASTER_RENDER_DPI,
                )
            ]
            if not detected:
                first = "original_300dpi_terminal_candidate_unavailable"
            elif not covered:
                first = "source_image_region_ownership_unavailable"
            elif not retained:
                first = "suppressed_by_original_144dpi_ordinary_raster_candidate"
            else:
                first = "pixel_and_image_source_nomination_eligible"
            evidence = area_evidence.get(identity)
            has_area = isinstance(evidence, Mapping) and evidence.get("area_m2") is not None
            stage_rows.append({
                "physical_opening_id": identity,
                "source_flank": flank,
                "original_300dpi_terminal_candidates": len(detected),
                "source_image_region_owned_candidates": len(covered),
                "not_ordinary_deduplicated_candidates": len(retained),
                "figured_area_evidence_available": has_area,
                "first_detector_gate": first,
                "metric_area_not_required_for_source_shadow": True,
                "source_stage_only": True,
                "physical_host_granted": False,
                "opening_height_or_count_granted": False,
                "customer_quantity_granted": False,
                "benchmark_score_granted": False,
            })
    return {
        "source_sha256": sha,
        "original_page_id": page_id,
        "original_source_snapshot_id": source_report["snapshot_id"],
        "private_detector_snapshot_id": pub.snapshot.snapshot_id,
        "opening_count_observed": len(shadow),
        "source_flank_count_observed": len(stage_rows),
        "original_144dpi_source_candidate_count": len(ordinary),
        "original_300dpi_terminal_candidate_count": len(raw),
        "first_detector_gate_counts": dict(sorted(
            Counter(row["first_detector_gate"] for row in stage_rows).items(),
        )),
        "source_flank_stage_rows": stage_rows,
        "canonical_wall_or_host_granted": False,
        "metric_quantity_granted": False,
        "benchmark_score_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = detector_source_first_gate_report(
        original_pdf=args.pdf.read_bytes(),
        source_report=json.loads(args.source_report.read_text(encoding="utf-8")),
        page_id=args.page_id,
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_sha256": result["source_sha256"],
        "original_page_id": result["original_page_id"],
        "source_flank_count_observed": result["source_flank_count_observed"],
        "first_detector_gate_counts": result["first_detector_gate_counts"],
        "new_hosts_granted": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
