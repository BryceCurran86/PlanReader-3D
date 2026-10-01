"""SHADOW DIFF: page-frame descriptor vs the wall page-boundary consumer.

Diagnostic only. Drives the REAL, unmodified ingest -> wall-candidate pipeline
read-only and, for every dangling wall end on every page, records:

* the native endpoint coordinates (as the pipeline produced them),
* the page width/height exactly as the existing consumer sees them
  (``pb_physical_wall_candidate_authority._source_page_segments``, i.e. the
  rotated ``page.rect``),
* the declared native page-frame extent from ``pb_page_frame_shadow``,
* the CURRENT page-boundary decision (existing predicate, consumer dimensions),
* the SHADOW decision (the same existing predicate, declared native extent
  substituted), reported twice: at the predicate's own default tolerance, and
  with the descriptor's derived float32 edge-quantisation bound passed through
  the predicate's existing ``tol`` keyword,
* divergence flags.

SCOPE OF "current": it is the consumer's page-boundary predicate recomputed per
dangling end with ``all_viewports=[]``, i.e. with viewport structure switched off,
so only the page-edge test is isolated. The real consumer passes the page's actual
segmented viewports and returns on the FIRST non-clean dangling end of a wall
(``BOUNDS_UNRESOLVED`` / viewport-cropped can come before a page-edge end), so on a
page with viewport structure the public reason can legitimately differ from this
recomputation. That is what the ``cross_check`` field reports (``mismatch``); it
is not hidden. Observed in the committed fixtures: the 2383.94 x 1683.78 cm-authored
sheet at /Rotate 270.

It changes no authority, publishes no quantity, writes nothing (the CLI prints
JSON to stdout only) and is imported by no production module. Synthetic
validation only: see the PROMOTION GATE in ``pb_page_frame_shadow``.

CLI:  python scripts/page_frame_wall_boundary_shadow_diff.py --pdf FILE --document-id ID [--pages 1,2]
The document id is an explicit input; it is never derived from the file name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fitz  # noqa: E402

import pb_physical_wall_candidate_authority as pw  # noqa: E402
from pb_page_frame_shadow import describe_page_frame  # noqa: E402
from pb_physical_wall_candidate_authority import (  # noqa: E402
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402

SHADOW_DIFF_SCHEMA_VERSION = "1.0.0"
DECISION_BOUNDARY = "at_page_boundary"
DECISION_INTERIOR = "interior"
PRODUCER_METHOD = "page_frame_wall_boundary_shadow_diff"
SOURCE_LOCATOR = "memory://page_frame_wall_boundary_shadow_diff"


def _decision(flag: bool) -> str:
    return DECISION_BOUNDARY if flag else DECISION_INTERIOR


def _native_boundary(point, *, width: float, height: float, tol: Optional[float]) -> bool:
    """The EXISTING predicate, called unchanged; only the extent (and optionally tol) differ."""
    kwargs = {} if tol is None else {"tol": tol}
    return bool(pw._on_rect_boundary(point, x0=0.0, y0=0.0, x1=width, y1=height, **kwargs))


def _wall_ends(wall) -> list:
    """(end_index, (x, y), dangling) for both ends; dangling == JunctionType.ENDPOINT,
    cross-checked against the consumer's own ``_dangling_ends``."""
    pts = wall.centerline_pts
    if not pts or len(pts) < 2 or len(wall.junction_types) != 2:
        return []
    ends = []
    for index, (point, junction) in enumerate(zip((pts[0], pts[-1]), wall.junction_types)):
        ends.append((index, (float(point[0]), float(point[1])), junction == pw.JunctionType.ENDPOINT))
    if sum(1 for _i, _p, d in ends if d) != len(pw._dangling_ends(wall)):
        raise RuntimeError("dangling-end bookkeeping disagrees with the consumer")
    return ends


def _page_report(*, src, pub, pdf_bytes: bytes, document, page_no: int, auth) -> dict:
    page_id = str(page_no)
    scope_id = f"wall-source:page-{page_no}"
    frame = describe_page_frame(
        document[page_no - 1],
        document_id=pub.revision.document_id,
        source_sha256=pub.revision.source_sha256,
        revision=pub.revision.revision_id,
        page_no=page_no,
    )
    report: dict = {
        "page_no": page_no,
        "frame": frame.to_plain(),
        "pipeline_status": "ok",
    }
    try:
        selector = PhysicalWallCandidateSelector(
            document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,
            source_sha256=pub.revision.source_sha256,
            snapshot_id=pub.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=scope_id,
        )
        result = auth.resolve_scope(selector)
        _segments, _ids, consumer_w, consumer_h = pw._source_page_segments(
            source_producer=src,
            published=pub,
            source_bytes=pdf_bytes,
            page_id=page_id,
            decision_scope_id=scope_id,
        )
    except Exception as exc:  # report, never raise: diagnostic tool
        report.update(
            pipeline_status=f"pipeline_error:{type(exc).__name__}",
            consumer_width=None,
            consumer_height=None,
            scope_complete=None,
            scope_reason_codes=[],
            cross_check="not_run",
            walls=[],
            summary=_summarise([]),
        )
        return report

    native = frame.native_extent
    quant = frame.edge_quantisation_pt
    walls = []
    any_current_cropped = False
    for record in sorted(result.records, key=lambda r: r.wall_candidate_id):
        wall = record.wall_candidate
        current_reason = pw._scope_boundary_reason_from_viewports(
            wall, all_viewports=[], page_width=consumer_w, page_height=consumer_h
        )
        shadow_reason = (
            None
            if native is None
            else pw._scope_boundary_reason_from_viewports(
                wall, all_viewports=[], page_width=native.width, page_height=native.height
            )
        )
        any_current_cropped = any_current_cropped or (
            current_reason == pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
        )
        ends = []
        for index, point, dangling in _wall_ends(wall):
            row: dict = {"end_index": index, "point": [point[0], point[1]], "dangling": dangling}
            if dangling:
                cur = _native_boundary(point, width=consumer_w, height=consumer_h, tol=None)
                row["current_decision"] = _decision(cur)
                if native is None:
                    row.update(
                        shadow_decision_default_tol=None,
                        shadow_decision_quantised_tol=None,
                        diverges_default_tol=None,
                        diverges_quantised_tol=None,
                    )
                else:
                    sd = _native_boundary(point, width=native.width, height=native.height, tol=None)
                    sq = _native_boundary(point, width=native.width, height=native.height, tol=quant)
                    row.update(
                        shadow_decision_default_tol=_decision(sd),
                        shadow_decision_quantised_tol=_decision(sq),
                        diverges_default_tol=cur != sd,
                        diverges_quantised_tol=cur != sq,
                    )
            else:
                row.update(
                    current_decision=None,
                    shadow_decision_default_tol=None,
                    shadow_decision_quantised_tol=None,
                    diverges_default_tol=None,
                    diverges_quantised_tol=None,
                )
            ends.append(row)
        walls.append(
            {
                "wall_candidate_id": record.wall_candidate_id,
                "current_wall_reason": current_reason,
                "shadow_wall_reason_default_tol": shadow_reason,
                "ends": ends,
            }
        )
    cropped_code = pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
    public_cropped = cropped_code in tuple(result.reason_codes)
    report.update(
        consumer_width=float(consumer_w),
        consumer_height=float(consumer_h),
        scope_complete=bool(result.scope_complete),
        scope_reason_codes=sorted(str(c) for c in result.reason_codes),
        cross_check="match" if public_cropped == any_current_cropped else "mismatch",
        walls=walls,
    )
    report["summary"] = _summarise(walls)
    return report


def _summarise(walls: Sequence[Mapping[str, Any]]) -> dict:
    rows = [e for w in walls for e in w["ends"] if e["dangling"]]
    return {
        "dangling_ends": len(rows),
        "current_at_boundary": sum(1 for e in rows if e["current_decision"] == DECISION_BOUNDARY),
        "shadow_default_tol_at_boundary": sum(1 for e in rows if e["shadow_decision_default_tol"] == DECISION_BOUNDARY),
        "shadow_quantised_tol_at_boundary": sum(1 for e in rows if e["shadow_decision_quantised_tol"] == DECISION_BOUNDARY),
        "divergent_default_tol": sum(1 for e in rows if e["diverges_default_tol"]),
        "divergent_quantised_tol": sum(1 for e in rows if e["diverges_quantised_tol"]),
        "walls": len(walls),
    }


def run_shadow_diff(
    pdf_bytes: bytes,
    *,
    document_id: str,
    page_numbers: Optional[Iterable[int]] = None,
) -> dict:
    """Run the diff on PDF bytes. Pure function of its inputs; touches no files."""
    if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes:
        raise ValueError("pdf_bytes must be non-empty bytes")
    data = bytes(pdf_bytes)
    src = SourceVisibilityProducer(producer_method=PRODUCER_METHOD, producer_version="1")
    pub = src.ingest_native_pdf_bytes(document_id=document_id, source_bytes=data, source_locator=SOURCE_LOCATOR)
    auth = PhysicalWallCandidateProducer.from_source_visibility_producer(src).authority()
    document = fitz.open(stream=data, filetype="pdf")
    try:
        wanted = sorted(set(page_numbers)) if page_numbers is not None else list(range(1, document.page_count + 1))
        pages = [
            _page_report(src=src, pub=pub, pdf_bytes=data, document=document, page_no=n, auth=auth)
            for n in wanted
            if 1 <= n <= document.page_count
        ]
    finally:
        document.close()
    return {
        "schema_version": SHADOW_DIFF_SCHEMA_VERSION,
        "shadow_only": True,
        "measurement_authority": False,
        "commercial_output_changed": False,
        "document_id": pub.revision.document_id,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "revision": pub.revision.revision_id,
        "pages": pages,
    }


# ---- fixture-label helpers (semantic labels, exact endpoint match, no nearest) ----
def label_page_report(page_report: Mapping[str, Any], expected_faces: Mapping[str, tuple], *, tol: float = 1e-3) -> dict:
    """Attach semantic labels and truth classes to every wall end.

    ``expected_faces``: {label: (native_end_0, native_end_1, "EI"-style classes)}
    where ``E`` is a true page-edge end and ``I`` an interior end. Each wall end
    must match exactly ONE expected (label, end) within ``tol`` (about 30 float32
    ulp at page scale); zero or several matches raise ValueError (fail closed).
    """
    targets = []
    for label, (p, q, classes) in expected_faces.items():
        targets.append((f"{label}:0", p, classes[0]))
        targets.append((f"{label}:1", q, classes[1]))
    out = json.loads(json.dumps(page_report))
    for wall in out["walls"]:
        for end in wall["ends"]:
            hits = [
                (key, cls)
                for key, pt, cls in targets
                if abs(end["point"][0] - pt[0]) < tol and abs(end["point"][1] - pt[1]) < tol
            ]
            if len(hits) != 1:
                raise ValueError(f"wall end {end['point']} matched {len(hits)} expected ends")
            end["label"], end["truth_class"] = hits[0]
    return out


def rotation_equivalence(labelled: Mapping[int, Mapping[str, Any]], *, column: str) -> dict:
    """Compare per-label dangling-end decisions across rotations.

    ``labelled``: {rotation: labelled page report}. ``column`` is one of
    ``current_decision``, ``shadow_decision_default_tol``,
    ``shadow_decision_quantised_tol``. Equivalent iff every rotation has the same
    set of dangling labelled ends with the same decision as every other rotation.
    """
    per_rotation = {
        int(rot): {
            e["label"]: e[column]
            for w in report["walls"]
            for e in w["ends"]
            if e["dangling"]
        }
        for rot, report in labelled.items()
    }
    keys = sorted({k for m in per_rotation.values() for k in m})
    mismatches = []
    for key in keys:
        values = {rot: m.get(key, "absent") for rot, m in sorted(per_rotation.items())}
        if len(set(values.values())) > 1:
            mismatches.append({"label": key, "decisions": {str(r): v for r, v in values.items()}})
    return {"column": column, "labels": len(keys), "equivalent": not mismatches, "mismatches": mismatches}


def render_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pdf", required=True, help="PDF file to read (read-only)")
    parser.add_argument("--document-id", required=True, help="explicit document id (never taken from the file name)")
    parser.add_argument("--pages", default="", help="comma separated 1-based page numbers (default: all)")
    args = parser.parse_args(argv)
    data = Path(args.pdf).read_bytes()
    pages = [int(p) for p in args.pages.split(",") if p.strip()] or None
    sys.stdout.write(render_json(run_shadow_diff(data, document_id=args.document_id, page_numbers=pages)) + "\n")
    return 0


__all__ = [
    "DECISION_BOUNDARY",
    "DECISION_INTERIOR",
    "label_page_report",
    "render_json",
    "rotation_equivalence",
    "run_shadow_diff",
]

if __name__ == "__main__":
    raise SystemExit(main())
