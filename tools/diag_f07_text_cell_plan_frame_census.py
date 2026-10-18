"""All-page census of the default-off F.07 ``source_connected_text_cell_plan_frame_shadow``.

``segment_page_viewports(..., source_connected_text_cell_plan_frame_shadow=...)``
is opt-in and unwired. For every page of every supplied PDF this tool shows

* that the output with the flag absent equals the output with ``False`` and,
  when a copy of the pre-change module is supplied (``--baseline-module``),
  equals that module's output (fingerprints of every field incl. provenance);
* which pages the flag changes when it is True, and exactly how;
* how every vector frame the legacy table predicate calls a table fares under
  the shadow's connected-and-text-bearing evidence, family by family;
* how the flag composes with the two existing opt-in shadows.

Counts, statuses, view types and frame coordinates only: no page text, drawing
titles, file names or expected quantities enter the report, and none is a
classifier input. This is a diagnostic; it cannot publish a viewport or a
quantity, and nothing here is evidence for a threshold on its own: the report
lists how many sources actually contribute a cell-family table frame so the
reader can see how much any cut rests on.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import fitz

import pb_viewport_segmentation as vs

FLAG = "source_connected_text_cell_plan_frame_shadow"
_GPT2_FLAGS = {
    "source_connected_table_cell_shadow": True,
    "source_native_multipath_semantic_frame_shadow": True,
}


def _round_box(box: Optional[Sequence[float]]) -> Optional[list[float]]:
    return None if box is None else [round(float(v), 2) for v in box]


def _digest(module: Any, viewports: Sequence[Any]) -> str:
    """One hash over every field of every viewport (incl. provenance), in order."""
    payload = [module.segmented_viewport_producer_fingerprint(v) for v in viewports]
    return hashlib.sha256(json.dumps(payload).encode("ascii")).hexdigest()[:16]


def _viewport_row(page: Any, viewport: Any) -> dict[str, Any]:
    box = viewport.bounding_box
    row: dict[str, Any] = {
        "view_id": viewport.view_id,
        "view_type": str(viewport.view_type),
        "status": str(viewport.status),
        "native_bbox": _round_box(box),
        "visual_bbox": None if box is None else _round_box(vs._to_visual_bbox(page, tuple(box))),
    }
    receipt = (viewport.provenance or {}).get(FLAG)
    if receipt:
        row["shadow_receipt_counts"] = {
            "table_veto_lifted_frames": len(receipt.get("table_veto_lifted_frames", ())),
            "near_nested_rival_frames": len(receipt.get("near_nested_rival_frames", ())),
        }
    return row


def _load_baseline(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("pb_viewport_segmentation_baseline", path)
    if spec is None or spec.loader is None:
        raise ValueError("baseline module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _segment(module: Any, doc: Any, index: int, **flags: bool) -> list[Any]:
    # A fresh Page object per run: the module's page parse cache lives on the
    # Page, so no run can borrow another run's parsed drawings or text.
    page = doc.load_page(index)
    return module.segment_page_viewports(page, page_number=index + 1, **flags)


def _family_rows(frame: Sequence[float], page: Any, calibration: Any, fragments: Sequence[Any]) -> list[dict[str, Any]]:
    """Every family that passes the legacy STRUCTURAL tests, with the shadow's two evidences."""
    centres = sorted(vs._bbox_center(bbox) for bbox, _text in fragments)
    centre_xs = [c[0] for c in centres]
    live_text = any(vs._point_in_bbox(c, frame) for c in centres)
    mesh = vs._frame_source_edge_mesh(frame, page)
    rows: list[dict[str, Any]] = []

    def record(family: Sequence[Sequence[float]]) -> bool:
        first = family[0]
        rows.append({
            "cells": len(family),
            "cell_wh": [round(first[2] - first[0], 2), round(first[3] - first[1], 2)],
            "edge_connected_fraction": round(sum(1 for cell in family if cell in mesh) / len(family), 3),
            "text_bearing_fraction": round(vs._cells_text_bearing_fraction(family, centres, centre_xs), 3),
            "live_text_in_frame": live_text,
        })
        return False  # never accept: we only want to enumerate the families

    vs._frame_looks_like_table(frame, page, calibration, allow_line_grid_only=False, family_filter=record)
    return rows


def _largest_family_row(frame: Sequence[float], page: Any, fragments: Sequence[Any]) -> Optional[dict[str, Any]]:
    """The largest same-size rectangle family in the frame, whether or not it passes the structural tests.

    This is the statistic a "text-bearing fraction of the largest family" measurement reports; it is listed
    beside the QUALIFYING families because they are not always the same family.
    """
    width = float(frame[2]) - float(frame[0])
    height = float(frame[3]) - float(frame[1])
    area = width * height
    families: dict[tuple[float, float], list[tuple[float, float, float, float]]] = {}
    for rect in vs._page_rectangle_primitives(page):
        if not vs._bbox_contains(frame, rect, margin=1.0) or not 4.0 < vs._bbox_area(rect) < 0.15 * area:
            continue
        key = (
            round((rect[2] - rect[0]) / width, vs._TABLE_CELL_DIMENSION_ROUND_DIGITS),
            round((rect[3] - rect[1]) / height, vs._TABLE_CELL_DIMENSION_ROUND_DIGITS),
        )
        families.setdefault(key, []).append(rect)
    if not families:
        return None
    family = max(families.values(), key=len)
    centres = sorted(vs._bbox_center(bbox) for bbox, _text in fragments)
    mesh = vs._frame_source_edge_mesh(frame, page)
    return {
        "cells": len(family),
        "cell_wh": [round(family[0][2] - family[0][0], 2), round(family[0][3] - family[0][1], 2)],
        "text_bearing_fraction": round(vs._cells_text_bearing_fraction(family, centres, [c[0] for c in centres]), 3),
        "edge_connected_fraction": round(sum(1 for cell in family if cell in mesh) / len(family), 3),
    }


def _table_frame_rows(doc: Any, index: int) -> list[dict[str, Any]]:
    page = doc.load_page(index)
    calibration = vs.calibrate_viewport_layout(page)
    frames = vs.extract_vector_frames(page, calibration)
    fragments = vs._text_fragments(page)
    rows: list[dict[str, Any]] = []
    for frame in frames:
        if not vs._frame_looks_like_table(frame, page, calibration):
            continue
        shadow_table = vs._frame_looks_like_source_connected_text_cell_table(frame, page, calibration, fragments)
        rows.append({
            "native_frame": _round_box(frame),
            "legacy_table": True,
            "cell_family_branch": bool(vs._frame_looks_like_table(frame, page, calibration, allow_line_grid_only=False)),
            "line_grid_branch": bool(vs._frame_looks_like_line_grid_table(frame, page, calibration)),
            "shadow_table": bool(shadow_table),
            "shadow_lifts_table_status": not shadow_table,
            "qualifying_families": _family_rows(frame, page, calibration, fragments),
            "largest_same_size_family": _largest_family_row(frame, page, fragments),
        })
    return rows


def _changes(page: Any, before: Sequence[Any], after: Sequence[Any]) -> list[dict[str, Any]]:
    by_id = {v.view_id: v for v in before}
    rows = []
    for view in after:
        other = by_id.get(view.view_id)
        if other is None:
            rows.append({"view_id": view.view_id, "change": "new_viewport", "after": _viewport_row(page, view)})
            continue
        if (other.status, other.bounding_box) != (view.status, view.bounding_box):
            rows.append({
                "view_id": view.view_id,
                "view_type": str(view.view_type),
                "before": _viewport_row(page, other),
                "after": _viewport_row(page, view),
            })
    for view in before:
        if view.view_id not in {v.view_id for v in after}:
            rows.append({"view_id": view.view_id, "change": "viewport_removed", "before": _viewport_row(page, view)})
    return rows


def census_page(doc: Any, index: int, baseline: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {"page": index + 1}
    page = doc.load_page(index)
    row["rotation"] = int(page.rotation)
    try:
        absent = _segment(vs, doc, index)
        explicit_false = _segment(vs, doc, index, **{FLAG: False})
        shadow = _segment(vs, doc, index, **{FLAG: True})
        row["viewport_count"] = len(absent)
        row["default_equals_flag_false"] = _digest(vs, absent) == _digest(vs, explicit_false)
        row["default_digest"] = _digest(vs, absent)
        if baseline is not None:
            before = _segment(baseline, doc, index)
            row["default_equals_baseline_module"] = _digest(baseline, before) == _digest(vs, absent)
        row["shadow_changes_viewports"] = _digest(vs, absent) != _digest(vs, shadow)
        row["shadow_changes"] = _changes(page, absent, shadow)
        if row["shadow_changes"]:
            row["default_viewports"] = [_viewport_row(page, v) for v in absent]
            row["shadow_viewports"] = [_viewport_row(page, v) for v in shadow]
        # Composition with the two existing opt-in shadows.
        gpt2 = _segment(vs, doc, index, **_GPT2_FLAGS)
        both = _segment(vs, doc, index, **_GPT2_FLAGS, **{FLAG: True})
        row["composition_changes_viewports"] = _digest(vs, gpt2) != _digest(vs, both)
        row["composition_changes"] = _changes(page, gpt2, both)
        # Receipts must never appear without the flag.
        row["receipt_without_flag"] = any(
            FLAG in (v.provenance or {}) for v in [*absent, *explicit_false, *gpt2]
        )
    except Exception as exc:  # noqa: BLE001 - a census records, it does not abort
        row["error"] = type(exc).__name__
        return row
    try:
        row["legacy_table_frames"] = _table_frame_rows(doc, index)
    except Exception as exc:  # noqa: BLE001
        row["table_frame_error"] = type(exc).__name__
    return row


def census_pdf(path: Path, baseline: Any = None, label: Optional[str] = None) -> dict[str, Any]:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    with fitz.open(stream=data, filetype="pdf") as doc:
        pages = [census_page(doc, index, baseline) for index in range(doc.page_count)]
        return {
            "source_id": label or f"{path.parent.name}/{sha[:12]}",
            "sha256_prefix": sha[:12],
            "page_count": doc.page_count,
            "pages": pages,
        }


def summarise(sources: Sequence[dict[str, Any]], with_baseline: bool) -> dict[str, Any]:
    pages = [(s["source_id"], p) for s in sources for p in s["pages"]]
    errors = [(sid, p["page"], p.get("error") or p.get("table_frame_error")) for sid, p in pages if "error" in p or "table_frame_error" in p]
    ok = [(sid, p) for sid, p in pages if "error" not in p]
    frames = [(sid, p["page"], f) for sid, p in ok for f in p.get("legacy_table_frames", ())]
    cell_frames = [x for x in frames if x[2]["cell_family_branch"]]
    summary: dict[str, Any] = {
        "sources": len(sources),
        "pages": len(pages),
        "pages_with_errors": len(errors),
        "pages_default_equals_flag_false": sum(1 for _s, p in ok if p["default_equals_flag_false"]),
        "pages_shadow_changes_viewports": sum(1 for _s, p in ok if p["shadow_changes_viewports"]),
        "pages_composition_changes_viewports": sum(1 for _s, p in ok if p["composition_changes_viewports"]),
        "pages_with_receipt_without_flag": sum(1 for _s, p in ok if p["receipt_without_flag"]),
        "legacy_table_frames": len(frames),
        "legacy_table_frames_cell_family_branch": len(cell_frames),
        "legacy_table_frames_line_grid_only": len(frames) - len(cell_frames),
        "legacy_table_frames_lifted_by_shadow": sum(1 for x in frames if x[2]["shadow_lifts_table_status"]),
        "sources_with_any_cell_family_table_frame": sorted({sid for sid, _p, _f in cell_frames}),
        "changed_pages": [
            {"source_id": sid, "page": p["page"], "changes": p["shadow_changes"]}
            for sid, p in ok if p["shadow_changes_viewports"]
        ],
        "error_pages": [list(e) for e in errors],
    }
    if with_baseline:
        summary["pages_default_equals_baseline_module"] = sum(
            1 for _s, p in ok if p.get("default_equals_baseline_module")
        )
    return summary


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "| source | pages | default == flag False | default == baseline | pages changed by flag | legacy table frames | cell-family | lifted by flag |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source in report["sources"]:
        ok = [p for p in source["pages"] if "error" not in p]
        frames = [f for p in ok for f in p.get("legacy_table_frames", ())]
        baseline_cell = (
            f"{sum(1 for p in ok if p.get('default_equals_baseline_module'))}/{len(ok)}"
            if report["has_baseline"] else "n/a"
        )
        lines.append(
            f"| {source['source_id']} | {source['page_count']} "
            f"| {sum(1 for p in ok if p['default_equals_flag_false'])}/{len(ok)} "
            f"| {baseline_cell} "
            f"| {sum(1 for p in ok if p['shadow_changes_viewports'])} "
            f"| {len(frames)} "
            f"| {sum(1 for f in frames if f['cell_family_branch'])} "
            f"| {sum(1 for f in frames if f['shadow_lifts_table_status'])} |"
        )
    lines.append(
        f"| **total** | **{summary['pages']}** "
        f"| **{summary['pages_default_equals_flag_false']}/{summary['pages'] - summary['pages_with_errors']}** "
        f"| **{summary.get('pages_default_equals_baseline_module', 'n/a')}** "
        f"| **{summary['pages_shadow_changes_viewports']}** "
        f"| **{summary['legacy_table_frames']}** "
        f"| **{summary['legacy_table_frames_cell_family_branch']}** "
        f"| **{summary['legacy_table_frames_lifted_by_shadow']}** |"
    )
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, action="append", default=[], help="a PDF to census (repeatable)")
    parser.add_argument("--sources-dir", type=Path, help="a directory holding <project>/*.pdf")
    parser.add_argument("--baseline-module", type=Path, help="a copy of the pre-change pb_viewport_segmentation.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    pdfs = list(args.pdf)
    if args.sources_dir:
        pdfs.extend(sorted(args.sources_dir.glob("*/*.pdf")))
    if not pdfs:
        parser.error("no PDF supplied")
    baseline = _load_baseline(args.baseline_module) if args.baseline_module else None
    sources = [census_pdf(path, baseline) for path in pdfs]
    report = {
        "tool": "diag_f07_text_cell_plan_frame_census",
        "flag": FLAG,
        "pymupdf": fitz.VersionBind,
        "constants": {
            "table_cell_shared_edge_tolerance_pt": vs._TABLE_CELL_SHARED_EDGE_TOLERANCE_PT,
            "table_family_majority_fraction": vs._TABLE_FAMILY_MAJORITY_FRACTION,
            "near_nested_band_containment_fraction": vs._NEAR_NESTED_BAND_CONTAINMENT_FRACTION,
        },
        "has_baseline": baseline is not None,
        "sources": sources,
    }
    report["summary"] = summarise(sources, baseline is not None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print("F07_TEXT_CELL_PLAN_FRAME_SHADOW_CENSUS", json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
