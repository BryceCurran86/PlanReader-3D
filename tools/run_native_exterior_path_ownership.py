"""Read-only native path ownership for footprint-first exterior edges.

Does not issue customer quantities, close unproved gaps, or copy original PDFs.
Use: py -3.13 tools/run_native_exterior_path_ownership.py --pdf house.pdf --page 1 --out-dir C:\\private\\native-owners
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_external_footprint_first_trace import (  # noqa: E402
    bound_native_drawings_to_footprint,
    refine_external_footprint_against_wall_ink,
    trace_external_footprint_first,
)
from pb_layered_wall_doorway_room_ring_shadow import (  # noqa: E402
    build_layered_wall_doorway_room_rings,
)
from pb_native_page_frame import (  # noqa: E402
    NativePageFrameUnresolved,
    effective_pdf_rotation,
)
from pb_source_native_exterior_edge_path_ownership import (  # noqa: E402
    enrich_open_to_exterior_span,
    own_exterior_contour_native_paths,
)
from pb_source_native_wall_role_and_junction_shadow import (  # noqa: E402
    identify_source_wall_junctions_and_roles,
)


def _page_rotation_for_roles(page) -> int | None:
    """The page's effective /Rotate from the production frame seam, or None when it cannot be established.

    None makes the role classifier fail closed: the title band is never tested in the wrong coordinate space.
    180 and 270 are reported as they are; the classifier abstains on them.
    """
    try:
        return effective_pdf_rotation(page)
    except NativePageFrameUnresolved:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    raw = args.pdf.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    (trace,) = trace_external_footprint_first(
        raw, source_sha256=sha, page_indices=(args.page,),
    )
    import fitz
    with fitz.open(stream=raw, filetype="pdf") as doc:
        drawings = doc[args.page].get_drawings()
    trace, detour_receipt = refine_external_footprint_against_wall_ink(
        trace, drawings,
    )
    scope = bound_native_drawings_to_footprint(
        drawings, trace=trace, expected_source_sha256=sha,
    )
    ring = None
    if scope.status == "CANDIDATE":
        ring = build_layered_wall_doorway_room_rings(
            scope.drawings, source_sha256=sha, page_index=args.page,
            sliding_leaf_frame_closure=True,
            dark_painted_wall_source=True,
            wall_end_stroke_closures=False,
            source_heavy_stroke_wall_bands=True,
        )
    owned = own_exterior_contour_native_paths(
        scope.drawings if scope.status == "CANDIDATE" else drawings,
        trace,
        closures=() if ring is None else ring.closures,
    )
    first_span = None
    if ring is not None and ring.unresolved_gap_witnesses:
        first_span = enrich_open_to_exterior_span(
            scope.drawings, ring.unresolved_gap_witnesses[0],
            closures=ring.closures,
        )
    page_rect = None
    page_rotation = None
    import fitz as _fitz
    with _fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[args.page]
        rect = page.rect
        page_rect = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
        page_rotation = _page_rotation_for_roles(page)
    roles = identify_source_wall_junctions_and_roles(
        scope.drawings if scope.status == "CANDIDATE" else drawings,
        source_sha256=sha,
        page_index=args.page,
        trace=trace,
        page_bounds=page_rect,
        page_rotation=page_rotation,
    )
    payload = {
        "source_sha256": sha,
        "page_index_0based": args.page,
        "exterior_trace_status": trace.status,
        "unsupported_rectangular_detour": dict(detour_receipt),
        "edge_ownership": [edge.to_dict() for edge in owned],
        "classification_counts": _counts(owned),
        "first_open_to_exterior_span": None if first_span is None else first_span.to_dict(),
        "temporary_doorway_closures": 0 if ring is None else len(ring.closures),
        "candidate_room_rings": 0 if ring is None else len(ring.rings),
        "wall_roles_and_junctions": roles.to_dict(),
        "title_band_page_rotation": page_rotation,
        "commercial_quantity_rows": 0,
        "official_frozen120_score_change": 0,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"page_{args.page + 1}_native_exterior_owners.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _draw_overlay(raw, args.page, trace, owned, first_span, args.out_dir)
    print(json.dumps({
        "wrote": str(out_json),
        "sha": sha,
        "classifications": payload["classification_counts"],
        "first_span_reason": None if first_span is None else first_span.reason,
        "first_span_paths": None if first_span is None else list(
            first_span.adjacent_wall_native_path_indices
        ),
        "role_counts": payload["wall_roles_and_junctions"]["role_counts"],
        "unresolved_spans": len(payload["wall_roles_and_junctions"]["unresolved_open_spans"]),
        "rejected_diagonals": payload["wall_roles_and_junctions"]["rejected_diagonal_bridge_count"],
        "invented_door_bridges": payload["wall_roles_and_junctions"]["invented_door_bridge_count"],
    }, indent=2))
    return 0


def _counts(owned) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in owned:
        counts[edge.classification] = counts.get(edge.classification, 0) + 1
    return counts


def _draw_overlay(raw, page_index, trace, owned, first_span, out_dir: Path) -> None:
    import fitz
    from pb_external_footprint_first_trace import native_points_to_display_space

    source = fitz.open(stream=raw, filetype="pdf")
    overlay = fitz.open()
    page = overlay.new_page(width=source[page_index].rect.width, height=source[page_index].rect.height)
    page.show_pdf_page(page.rect, source, page_index)
    for edge in owned:
        color = {
            "source_native_wall_ink_candidate": (0.0, 0.55, 0.2),
            "incorrect_geometric_bridge": (0.85, 0.15, 0.1),
            "unmatched_contour_segment": (0.7, 0.0, 0.65),
            "topology_only_opening_closure": (1.0, 0.45, 0.0),
            "competing_exterior_path_owners": (0.9, 0.7, 0.0),
        }.get(edge.classification, (0.4, 0.4, 0.4))
        # Edges and span endpoints are in NATIVE page space; the overlay page is the DISPLAYED page.
        shown = native_points_to_display_space(trace, (edge.start_pdf_pts, edge.end_pdf_pts))
        if shown is not None:
            page.draw_line(shown[0], shown[1], color=color, width=1.2)
    if first_span is not None:
        shown = native_points_to_display_space(trace, first_span.endpoints_pdf_pts)
        if shown is not None:
            page.draw_line(shown[0], shown[1], color=(0.55, 0.0, 0.55), width=2.4)
    dest = out_dir / f"page_{page_index + 1}_native_exterior_owners.png"
    pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
    pix.save(dest)
    overlay.close()
    source.close()


if __name__ == "__main__":
    raise SystemExit(main())
