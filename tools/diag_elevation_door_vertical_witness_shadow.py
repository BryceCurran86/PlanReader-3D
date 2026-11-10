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

from pb_elevation_source_owned_witness_adapter import (  # noqa: F401
    extract_views, kind_proposal_for_outline, plan_label_width, read_source_owned_page, rectangle_components,
    source_owned_views,
)
from pb_elevation_door_vertical_witness_shadow import (
    DatumLevel, ElevOutline, ElevationDatum, PlanSpan, Scope, aggregate_across_views, compose_opening_measurement,
    register_plan_to_elevation, resolve_vertical_witness,
)



def _drawn_edges(item) -> list[tuple]:
    """The straight edges one PyMuPDF drawing item paints: a line, or the four sides of a ``re`` / ``qu`` item (curves paint none)."""
    kind = item[0]
    if kind == "l":
        return [(item[1].x, item[1].y, item[2].x, item[2].y)]
    if kind == "re":
        r = item[1]
        corners = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
    elif kind == "qu":
        q = item[1]
        corners = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
    else:
        return []
    return [(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]


def page_primitives(page) -> tuple[list, list, list]:
    """Plain lines, filled rectangles and words of one page through PyMuPDF (the diagnostic path, no receipts).

    A filled rectangle is one the path actually DRAWS: the edges of a filled drawing go through the same
    ``rectangle_components`` rule as the source-owned path, so a compound path never becomes the bounding box of its
    parts and an L-shaped or open outline is no rectangle. (The old reading took ``drawing["rect"]``, the bounding box of the
    whole path, which invents a rectangle across the gap between two subpaths.)
    """
    lines, rects = [], []
    for d in page.get_drawings():
        fill = d.get("fill")
        edges = [e for it in d["items"] for e in _drawn_edges(it)]
        for it in d["items"]:
            if it[0] == "l":
                lines.append((it[1].x, it[1].y, it[2].x, it[2].y))
        if fill is not None and edges:
            rounded = tuple(round(c, 2) for c in fill)
            for x0, y0, x1, y1, f, _ids in rectangle_components([(*e, rounded, "") for e in edges]):
                rects.append((x0, y0, x1, y1, f))
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
        source_owned: bool = False, glyph_ledger: bool = False) -> dict:
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
        **({"source_glyph_ledger_text_trust": True} if glyph_ledger else {}),
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
    views_out, per_view_results, outlines_of, page_inputs_of = [], [], {}, {}
    for page_no in elevation_pages:
        if source_owned:
            page = read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id=str(page_no))
            page_views, view_scope = (source_owned_views(page), page.scope) if page is not None else ([], scope)
            page_inputs = (page.strokes, page.words) if page is not None else ((), ())
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
                    witness = resolve_vertical_witness(
                        span.record_id, spans[axis], view["outlines"], view["datum"], plan_scope=scope, elevation_scope=view_scope)
                    per_view_results.append(witness)
                    outlines_of[id(witness)] = view["outlines"]
                    if source_owned:
                        page_inputs_of[id(witness)] = page_inputs
            views_out.append(row)
    # one result per record across ALL views: competing views or values never become a candidate by cherry-picking
    aggregated = aggregate_across_views(per_view_results)
    reasons = Counter(r.reason_codes[0] for r in aggregated)
    candidates = [{"record": r.record_id[-8:], "opening_height_mm": r.opening_height_mm, "leaf_height_mm": r.leaf_height_mm,
                   "head_level": r.head_level_name, "receipt_count": len(r.source_observation_ids),
                   "text_trust": r.text_trust, "result_id": r.result_id}
                  for r in aggregated if r.is_candidate]
    kind_rows = []
    if source_owned:
        for r in aggregated:
            if not r.is_candidate or id(r) not in page_inputs_of:
                continue
            strokes, words = page_inputs_of[id(r)]
            k = kind_proposal_for_outline(r.record_id, r.outline_id, outlines_of[id(r)], strokes, words)
            kind_rows.append({"record": r.record_id[-8:], "status": k.status.value, "reasons": list(k.reason_codes), "kind": k.kind,
                              "label_block": k.label_block_id, "text_trust": k.text_trust, "nested_outlines": len(k.nested_outline_ids),
                              "receipt_count": len(k.source_observation_ids), "result_id": k.result_id})
    measurements = []
    for r in aggregated:
        if not r.is_candidate:
            continue
        width_mm, label_trust, label_receipts = plan_label_width(source, comp, r.record_id)
        m = compose_opening_measurement(r, outlines_of.get(id(r), ()), plan_width_mm=width_mm,
                                        plan_label_text_trust=label_trust, plan_label_receipt_ids=label_receipts)
        measurements.append({"record": r.record_id[-8:], "status": m.status.value, "reasons": list(m.reason_codes),
                             "width_mm": m.width_mm, "height_mm": m.height_mm, "area_m2": m.area_m2,
                             "elevation_width_mm": m.elevation_width_mm, "leaf_height_mm": m.leaf_height_mm,
                             "text_trust": m.text_trust, "remaining_gates": list(m.remaining_gates),
                             "first_remaining_gate": m.first_remaining_gate, "receipt_count": len(m.source_observation_ids),
                             "result_id": m.result_id})
    focus_rows = [{"record": r.record_id[-8:], "status": r.status.value, "reasons": list(r.reason_codes), "outline": r.outline_id,
                   "competing_plan_records": [c[-8:] for c in r.competing_plan_record_ids]}
                  for r in aggregated if any(r.record_id.endswith(f) for f in focus)]
    return {
        "schema_version": "1.4.0", "source_sha256": sha, "input_path": "source_owned" if source_owned else "pymupdf_diagnostic", "glyph_ledger_text_trust": bool(glyph_ledger), "shadow_only": True, "benchmark_score_granted": False,
        "plan_page": plan_page, "elevation_pages": list(elevation_pages),
        "views": views_out, "candidates": sorted(candidates, key=lambda c: c["record"]),
        "first_remaining_gate_counts": dict(sorted(reasons.items())),
        "focus_rows": focus_rows,
        "measurements": sorted(measurements, key=lambda m: m["record"]),
        "kind_proposals": sorted(kind_rows, key=lambda k: k["record"]),
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
    parser.add_argument("--glyph-ledger", action="store_true", help="opt-in glyph-ledger text trust (slow: raster corroboration at ingest)")
    args = parser.parse_args()
    report = run(args.pdf, args.plan_page, args.elevation_pages, args.expected_source_sha256, args.focus, args.source_owned, args.glyph_ledger)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"views": len(report["views"]), "candidates": len(report["candidates"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
