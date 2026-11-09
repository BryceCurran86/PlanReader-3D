"""Read-only, counts-only diagnostic for the elevation vertical witness SHADOW.

``extract_views`` is pure: it takes plain lines, filled rects and words (page points) and returns one view per
figured datum chain (FFL line shared by at least two figured vertical dimensions) with its drawn outlines.
``run`` reads one original in place (SHA-checked), composes the plan page with the existing producers, and asks the
shadow about every plan opening span on every elevation view. It writes ids, reason codes and counts only and
never writes a host, kind, frame, quantity or customer row.

    python -m tools.diag_elevation_door_vertical_witness_shadow --pdf <original.pdf> --plan-page 3 \
        --elevation-pages 4 5 --expected-source-sha256 <hex> --output out.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Sequence

from pb_elevation_source_owned_witness_adapter import extract_views, read_source_owned_page, source_owned_views  # noqa: F401
from pb_elevation_door_vertical_witness_shadow import (
    DatumLevel, ElevOutline, ElevationDatum, PlanSpan, Scope, aggregate_across_views, register_plan_to_elevation,
    resolve_vertical_witness,
)



def page_primitives(page) -> tuple[list, list, list]:
    lines, rects = [], []
    for d in page.get_drawings():
        fill = d.get("fill")
        for it in d["items"]:
            if it[0] == "l":
                lines.append((it[1].x, it[1].y, it[2].x, it[2].y))
        r = d.get("rect")
        if fill is not None and r is not None:
            rects.append((r.x0, r.y0, r.x1, r.y1, tuple(fill)))
    words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
    return lines, rects, words


def plan_spans_from_composition(comp, poa, axis_name: str) -> list[PlanSpan]:
    import pb_opening_host_binding_authority as hb
    from pb_source_observation_authority import ObservationSelector

    spans = []
    for trace in comp.opening_bindings:
        sel = comp.binding_selectors.get(trace.opening_identity_id)
        if sel is None:
            continue
        rec = poa.prove_existence(ObservationSelector(
            document_id=sel.document_id, revision_id=sel.revision_id, source_sha256=sel.source_sha256,
            snapshot_id=sel.snapshot_id, observation_id=trace.representative_observation_id)).existence_record
        if rec is None:
            continue
        geometry = hb._opening_geometry(poa, rec)
        if geometry is None:
            continue
        i = 0 if axis_name == "x" else 1
        if abs(geometry.axis[i]) < 0.9:
            continue
        a, b = geometry.origin[i], geometry.origin[i] + geometry.axis[i] * geometry.length
        spans.append(PlanSpan(str(trace.opening_identity_id), min(a, b), max(a, b)))
    return spans


def run(pdf: Path, plan_page: int, elevation_pages: Sequence[int], expected_sha: str, focus: Sequence[str] = (),
        source_owned: bool = False) -> dict:
    import fitz
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != expected_sha:
        raise SystemExit("original source SHA-256 mismatch")
    pages = tuple(sorted({plan_page, *elevation_pages}))
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        raster_paired_outer_faces_shadow=True,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=pages,
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=initial.revision.revision_id, page_ids=(str(plan_page),),
        include_unmeasured_ink_closed_flanks_shadow=True, source_fragment_roles_shadow=True,
    )
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    scope = Scope(published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
                  published.snapshot.snapshot_id)
    poa = comp.physical_opening_authority
    spans = {axis: plan_spans_from_composition(comp, poa, axis) for axis in ("x", "y")}
    doc = fitz.open(stream=payload, filetype="pdf")
    views_out, per_view_results = [], []
    for page_no in elevation_pages:
        if source_owned:
            page = read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id=str(page_no))
            page_views, view_scope = (source_owned_views(page), page.scope) if page is not None else ([], scope)
        else:
            page_views, view_scope = extract_views(*page_primitives(doc[page_no - 1])), scope
        for view_no, view in enumerate(page_views):
            successes = []
            for axis in ("x", "y"):
                reg, why = register_plan_to_elevation(spans[axis], view["outlines"])
                if reg is not None:
                    successes.append((axis, reg))
            row = {"page": page_no, "view": view_no, "outlines": len(view["outlines"]),
                   "levels": [(lv.name, lv.figured_mm) for lv in view["datum"].levels], "registered_axes": [a for a, _ in successes]}
            if len(successes) == 1:
                axis, reg = successes[0]
                row.update({"axis": axis, "sign": reg.sign, "offset": round(reg.offset, 3), "anchor_widths_pt": list(reg.anchor_widths_pt)})
                for span in sorted(spans[axis], key=lambda s: s.record_id):
                    per_view_results.append(resolve_vertical_witness(
                        span.record_id, spans[axis], view["outlines"], view["datum"], plan_scope=scope, elevation_scope=view_scope))
            views_out.append(row)
    # one result per record across ALL views: competing views or values never become a candidate by cherry-picking
    aggregated = aggregate_across_views(per_view_results)
    reasons = Counter(r.reason_codes[0] for r in aggregated)
    candidates = [{"record": r.record_id[-8:], "opening_height_mm": r.opening_height_mm, "leaf_height_mm": r.leaf_height_mm,
                   "head_level": r.head_level_name, "receipt_count": len(r.source_observation_ids), "result_id": r.result_id}
                  for r in aggregated if r.is_candidate]
    focus_rows = [{"record": r.record_id[-8:], "status": r.status.value, "reasons": list(r.reason_codes), "outline": r.outline_id,
                   "competing_plan_records": [c[-8:] for c in r.competing_plan_record_ids]}
                  for r in aggregated if any(r.record_id.endswith(f) for f in focus)]
    return {
        "schema_version": "1.2.0", "source_sha256": sha, "input_path": "source_owned" if source_owned else "pymupdf_diagnostic", "shadow_only": True, "benchmark_score_granted": False,
        "plan_page": plan_page, "elevation_pages": list(elevation_pages),
        "views": views_out, "candidates": sorted(candidates, key=lambda c: c["record"]),
        "first_remaining_gate_counts": dict(sorted(reasons.items())),
        "focus_rows": focus_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--plan-page", type=int, required=True)
    parser.add_argument("--elevation-pages", type=int, nargs="+", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--focus", nargs="*", default=[], help="record id suffixes to explain")
    parser.add_argument("--source-owned", action="store_true", help="read elevation facts only from producer-owned authorities")
    args = parser.parse_args()
    report = run(args.pdf, args.plan_page, args.elevation_pages, args.expected_source_sha256, args.focus, args.source_owned)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"views": len(report["views"]), "candidates": len(report["candidates"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
