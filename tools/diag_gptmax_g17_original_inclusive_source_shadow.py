"""Compare original G17 terminal paint in default vs opt-in shadow, per source flank.

Original-SHA authenticated opening faces/ends nominate source boxes. The exact
private SourceVisibilityProducer original 300-DPI image/full rendering and
registered source pixels feed the production detector twice. No resulting
observation enters the canonical published source snapshot; no wall/host/area.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from scripts.gptmax_raster_flank_paint_audit import pixel_paint_profile
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT
from pb_source_visibility_authority import _axis_aligned_geometry_fully_covered_by_rect_union
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_raster_unchanged_band_segments import detect_unchanged_terminal_band_segments
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI, SourceVisibilityProducer,
    _unchanged_segment_inside_flank,
)
from tools.diag_gptmax_g17_source_only_flanks import source_only_closed_flanks


from pb_raster_g17_source_shadow import authenticated_one_end_g17_paint_shadow


def original_g17_inclusive_shadow_comparison(
    original_pdf: bytes, original_report: Mapping[str, Any], *, page_id: str,
) -> dict[str, Any]:
    sha = hashlib.sha256(original_pdf).hexdigest()
    if (original_report.get("source_sha256") != sha
            or original_report.get("primitive_safety_cap") != 20_000):
        raise ValueError("foreign PDF source or modified 20k safety bound")
    rows = original_report.get("unhosted_raster_flank_source_receipts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("authenticated source G17 flank receipts required")
    selected = [row for row in rows if row.get("page_id") == page_id]
    if not selected:
        raise ValueError("authenticated original G17 opening page not present")
    if any(row.get("source_sha256") != sha or
           row.get("snapshot_id") != original_report.get("snapshot_id")
           for row in selected):
        raise ValueError("original G17 receipt source ownership changed")
    known = [source_only_closed_flanks(row) for row in selected]
    if any(not row["closed_source_flank_nomination"] for row in known):
        raise ValueError("incomplete actual face/end source topology")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=original_pdf,
        source_locator="memory://gptmax-original-G17-ink-shadow.pdf",
        page_ids=(page_id,),
    )
    pub = source.augment_with_raster_opening_primitives(
        pub.revision.revision_id, page_ids=(page_id,),
    )
    args = {
        "document_id": pub.revision.document_id,
        "revision_id": pub.revision.revision_id,
        "source_sha256": pub.revision.source_sha256,
        "snapshot_id": pub.snapshot.snapshot_id,
        "page_id": page_id,
        "dpi": float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
        "include_native_frame": True,
    }
    image_png, iparent, iframe = source._producer.render_native_page_png(
        **args, images_only=True,
    )
    full_png, fparent, fframe = source._producer.render_native_page_png(**args)
    if iparent != fparent or iframe != fframe or int(iframe.rotation) != 0:
        raise RuntimeError("original source frame/parent mismatch")
    registration = (
        source.raster_opening_registration_scale(pub.revision.revision_id, page_id)
        or (1.0, 1.0)
    )
    dpi = RASTER_OPENING_PRIMITIVE_RENDER_DPI
    ordinary = detect_unchanged_terminal_band_segments(
        image_png, full_png, dpi=dpi, registration_scale=registration,
    )
    inclusive = detect_unchanged_terminal_band_segments(
        image_png, full_png, dpi=dpi, registration_scale=registration,
        shadow_inclusive_source_cells=True,
    )
    # The opt-in only adds original painted cells. It never removes an accepted
    # ordinary observation or elects a structural source wall.
    ordinary_map = {(x.pixel_support_bounds,x.geometry_pt,x.orientation) for x in ordinary}
    inclusive_map = {(x.pixel_support_bounds,x.geometry_pt,x.orientation) for x in inclusive}
    if not ordinary_map <= inclusive_map:
        raise RuntimeError("opt-in shadow lost original detector candidates")
    def rgb(png):
        decoded=cv2.imdecode(np.frombuffer(png,dtype=np.uint8),cv2.IMREAD_COLOR)
        if decoded is None:
            raise RuntimeError("immutable source original render unavailable")
        return cv2.cvtColor(decoded,cv2.COLOR_BGR2RGB)

    raw_source_rgb, full_rgb = rgb(image_png), rgb(full_png)
    original_image_regions=tuple(source._producer.native_page_image_regions(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id=page_id,
    ))
    output=[]
    for row in known:
        flanks=[]
        for flank in row["source_flank_boxes"]:
            box=(flank["orientation"],tuple(float(v) for v in flank["source_bbox_pdf_pts"]))
            old=[x for x in ordinary if _unchanged_segment_inside_flank(x,box,dpi=dpi)]
            new=[x for x in inclusive if _unchanged_segment_inside_flank(x,box,dpi=dpi)]
            added=[x for x in new if (x.pixel_support_bounds,x.geometry_pt,x.orientation)
                   not in ordinary_map]
            source_paint=authenticated_one_end_g17_paint_shadow(
                raw_source_rgb, full_rgb, flank, dpi=dpi,
                image_regions=original_image_regions,
            )
            flanks.append({
                "one_ended_G17_original_source_paint":source_paint,
                "source_observation_ids":flank["source_observation_ids"],
                "source_bbox_pdf_pts":flank["source_bbox_pdf_pts"],
                "original_default_count":len(old),
                "inclusive_source_shadow_count":len(new),
                "new_original_painted_cell_candidate_count":len(added),
                "new_source_pixel_support_bounds":[list(x.pixel_support_bounds) for x in added],
                "new_source_geometry_pt":[list(x.geometry_pt) for x in added],
                "source_wall_role_granted":False,
                "new_host_granted":False,
                "new_area_granted":False,
            })
        output.append({"physical_opening_id":row["physical_opening_id"],"flanks":flanks})
    return {
        "source_sha256":sha,"page_id":page_id,
        "original_default_terminal_count":len(ordinary),
        "original_inclusive_shadow_terminal_count":len(inclusive),
        "source_openings":output,
        "canonical_snapshot_modified":False,
        "original_w4_modified":False,
        "physical_host_granted":False,
        "metric_area_or_count_granted":False,
        "customer_quantity_granted":False,
        "benchmark_score_granted":False,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--source-report",type=Path,required=True)
    parser.add_argument("--page-id",default="3")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=original_g17_inclusive_shadow_comparison(
        args.pdf.read_bytes(),
        json.loads(args.source_report.read_text(encoding="utf-8")),
        page_id=args.page_id,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "original_default":result["original_default_terminal_count"],
        "source_only_inclusive":result["original_inclusive_shadow_terminal_count"],
        "new_host_granted":False,"new_area_granted":False},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
