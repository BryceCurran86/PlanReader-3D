"""Counterfactual, NOT a repository change: run the unchanged source-authority stage tool under a swapped rule.

usage: python counterfactual_stage.py <repo_checkout> <pdf_path> <page_number> <mode> <out.json> [walls_meta.json]

modes
  baseline            production behaviour
  eligible            free ends are contained by F.07-eligible viewports (RESOLVED, or authoritative-derived with a
                      non-overlapping sibling set) via the existing _authenticated_viewports_from_rows
  eligible_wall_layer same, but only for candidates whose source layers are all wall-named (needs walls_meta.json)
  scale               PhysicalScaleProducer accepts the single eligible viewport (page-wide and by id)
  boundary_scale      eligible + scale

Only module attributes in the running process are swapped; nothing is written to the checkout.
"""
import re
import runpy
import sys

sys.dont_write_bytecode = True
repo, pdf, page_no, mode, out = sys.argv[1:6]
walls_meta = sys.argv[6] if len(sys.argv) > 6 else None
sys.path.insert(0, repo)

import pb_physical_wall_candidate_authority as pw  # noqa: E402

_LAYERS = {}
if mode == "eligible_wall_layer":
    import json
    for row in json.load(open(walls_meta, encoding="utf-8")):
        _LAYERS[row["id"]] = row["layers"]


def _wall_layers_only(wall_id):
    named = [layer for layer in (_LAYERS.get(wall_id) or []) if str(layer)]
    return bool(named) and all(re.search("wall", str(layer), re.I) for layer in named)


if mode in ("eligible", "eligible_wall_layer", "boundary_scale"):
    def patched(wall, *, all_viewports, page_width, page_height):
        dangling = pw._dangling_ends(wall)
        if not dangling:
            return None
        if mode == "eligible_wall_layer" and not _wall_layers_only(wall.candidate_id):
            return pw.PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED
        rows = pw._authenticated_viewports_from_rows(all_viewports)
        for point in dangling:
            if pw._on_rect_boundary(point, x0=0.0, y0=0.0, x1=page_width, y1=page_height):
                return pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
            if all_viewports is None or rows is None:
                return pw.PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED
            relevant = pw._wall_scope_relevant_viewports(all_viewports)
            if not relevant:
                continue
            relevant_ids = {id(v) for v in relevant}
            eligible = [v for v in rows[1] if id(v) in relevant_ids]
            containing = [
                vp for vp in eligible
                if pw._inside_rect(point, x0=vp.bounding_box[0], y0=vp.bounding_box[1],
                                   x1=vp.bounding_box[2], y1=vp.bounding_box[3])
            ]
            if not containing:
                return pw.PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED
            if any(pw._on_rect_boundary(point, x0=vp.bounding_box[0], y0=vp.bounding_box[1],
                                        x1=vp.bounding_box[2], y1=vp.bounding_box[3])
                   for vp in containing):
                return pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY
        return None

    pw._scope_boundary_reason_from_viewports = patched

if mode in ("scale", "boundary_scale"):
    import fitz
    import pb_physical_scale_authority as ps
    from pb_viewport_segmentation import segment_page_viewports

    original_bbox = ps.PhysicalScaleProducer._scope_bbox

    def scope_bbox(selector, source_bytes):
        document = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            page = document.load_page(int(selector.page_id) - 1)
            rows = segment_page_viewports(page, page_number=int(selector.page_id))
            authenticated = pw._authenticated_viewports_from_rows(rows)
            eligible = list(authenticated[1]) if authenticated else []
            if selector.viewport_id is None:
                if len(rows) == 1 and len(eligible) == 1:
                    return tuple(float(v) for v in eligible[0].bounding_box), None
                return original_bbox(selector, source_bytes)
            matches = [v for v in eligible if v.view_id == selector.viewport_id]
            if len(matches) == 1:
                return tuple(float(v) for v in matches[0].bounding_box), None
            return original_bbox(selector, source_bytes)
        finally:
            document.close()

    ps.PhysicalScaleProducer._scope_bbox = staticmethod(scope_bbox)

sys.argv = ["diag_gptmax_source_authority_stages.py", "--pdf", pdf, "--page-id", str(page_no), "--output", out]
runpy.run_path(repo + "/tools/diag_gptmax_source_authority_stages.py", run_name="__main__")
