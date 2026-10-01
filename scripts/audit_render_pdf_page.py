#!/usr/bin/env python3
"""Cold-run + clean/audit render for one PDF page (diagnostic, shadow-only).

Runs the existing viewport segmentation and W2-W10 topology seam, adapts the
result to ``CanonicalLevel`` through W10 (``takeoff_eligible=False``), then builds
the clean/audit scene with ``pb_audit_render``.  Where the canonical object has
no metre geometry (scale not firm), a display-only projection at the viewport's
own bound scale is supplied and every affected object is marked so; it never
becomes quantity authority.  No project-specific logic, no expected values.

usage: audit_render_pdf_page.py PDF PAGE_1BASED OUT_DIR
Writes scene.json, summary.json and clean/audit HTML for each camera preset.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

from pb_audit_coverage_record import DefaultCoverageProvider  # noqa: E402
from pb_audit_render import CAMERA_PRESETS, build_audit_scene, render_audit_html  # noqa: E402
from pb_viewport_scale_binding import bind_viewport_scale  # noqa: E402
from pb_viewport_segmentation import segment_page_viewports  # noqa: E402
from pb_wall_topology_diagnostics import (  # noqa: E402
    adapt_snapshot_to_canonical_level,
    collect_topology_from_page,
    list_page_viewports,
)


def _display_geometry(snapshot, px_per_m, basis):
    if not px_per_m or px_per_m <= 0:
        return {}
    k = 1.0 / px_per_m
    out = {}
    for w in snapshot.walls:
        pts = w.centerline_pts
        if len(pts) >= 2:
            out[w.candidate_id] = {"pts": [[pts[0][0] * k, -pts[0][1] * k], [pts[-1][0] * k, -pts[-1][1] * k]], "basis": basis}
    for r in snapshot.rooms:
        if len(r.polygon_pdf_pts) >= 3:
            out[r.room_ref] = {"pts": [[x * k, -y * k] for x, y in r.polygon_pdf_pts], "basis": basis}
    return out


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    pdf, page_no, out_dir = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf))
    page = doc[page_no - 1]
    listing = list_page_viewports(page, page_number=page_no, allow_derived=True)
    viewports = {v.view_id: v for v in segment_page_viewports(page, page_number=page_no)}
    levels, display, stats = [], {}, []
    for row in listing:
        if not row["safe_floor_plan"]:
            continue
        vp = viewports[row["view_id"]]
        snap = collect_topology_from_page(page, page_number=page_no, document_id="doc",
                                          allow_derived=True, viewport_id=row["view_id"])
        level = adapt_snapshot_to_canonical_level(snap)
        binding = bind_viewport_scale(vp, page_no=page_no, revision_id="audit-run", sheet_label="", source_sha256="")
        cal = binding.calibration
        px_per_m = getattr(cal, "px_per_m", None)
        basis = "display_only_" + str(getattr(cal, "source_type", "scale"))
        display.update(_display_geometry(snap, px_per_m, basis))
        levels.append(level)
        stats.append({"viewport": row["view_id"], "bbox": row["bounding_box"], "walls": len(snap.walls),
                      "rooms": len(snap.rooms), "opening_hosts": len(snap.opening_hosts),
                      "canonical_walls_with_metre_geometry": sum(1 for w in level.walls if w.start_point.is_valid()),
                      "scale": {"ratio": getattr(cal, "ratio_str", None), "source_type": getattr(cal, "source_type", None),
                                "status": getattr(cal, "status", None), "px_per_m": px_per_m}})
    scene = build_audit_scene(levels, DefaultCoverageProvider(), display, title=f"{pdf.name} p{page_no}")
    (out_dir / "scene.json").write_text(json.dumps(scene, sort_keys=True))
    (out_dir / "summary.json").write_text(json.dumps({"viewports": listing, "topology": stats,
                                                       "audit_summary": scene["summary"],
                                                       "drawn": len(scene["objects"]), "not_drawn": len(scene["not_drawn"])}, indent=1))
    for preset in CAMERA_PRESETS:
        for mode in ("clean", "audit"):
            (out_dir / f"{mode}_{preset}.html").write_text(render_audit_html(scene, mode=mode, camera_preset=preset))
    print(json.dumps({"drawn": len(scene["objects"]), "not_drawn": len(scene["not_drawn"]), "summary": scene["summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
