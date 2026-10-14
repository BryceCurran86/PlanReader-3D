"""Independent original-PDF native-ink witnesses for W2/W4 face conflicts.

A SourceEdgeFragment is a W2 graph fragment retaining source primitive IDs,
not original native PDF paint. This *shadow only* tool addresses every claimed
native path/item directly in immutable PDF bytes. No label, wall identity,
room face, FIRM measurement, finish, or benchmark claim is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from tools.diag_gpt2_native_source_edge_span_census import (
    inspect_source_room_report,
)
from tools.diag_gpt2_native_w2_ink_source_role import (
    read_native_ink_receipt,
)


def _page_no(value):
    if type(value) is not str or not value.isdecimal() or str(int(value)) != value or int(value) < 1:
        raise ValueError("untrusted_original_pdf_page_address")
    return int(value)


def _source_refs(candidate):
    values = candidate.get("source_primitive_ids")
    if not isinstance(values, (tuple, list)) or not values or any(
        type(v) is not str or not v or v != v.strip() for v in values
    ) or len(values) != len(set(values)):
        return None
    return tuple(sorted(values))


def inspect_native_ink_against_w2(report, pdf_bytes: bytes) -> dict:
    """Separate original PDF paint from W2 lineage; never infer physical walls."""
    if type(pdf_bytes) is not bytes:
        raise TypeError("original_pdf_bytes_required")
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    if not isinstance(report, dict) or report.get("source_sha256") != sha:
        raise ValueError("source_sha_mismatch")
    # The existing diagnostic report validates source scope lineage and that
    # no commercial rows were made. It does NOT certify raw JSON as a producer.
    previous = inspect_source_room_report(report)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        rows = []
        pages_seen = set()
        for scope in report["scopes"]:
            page_no = _page_no(scope.get("page_id"))
            if page_no > document.page_count:
                raise ValueError("original_pdf_source_page_unavailable")
            key = (
                scope.get("revision_id"), scope.get("snapshot_id"),
                scope.get("decision_scope_id"), page_no,
            )
            if key in pages_seen:
                raise ValueError("original_source_scope_replayed")
            pages_seen.add(key)
            drawings = document.load_page(page_no - 1).get_drawings()
            audit_edges = []
            for edge_row in scope["competing_source_edges"]:
                contenders = edge_row.get("candidate_walls")
                if not isinstance(contenders, (tuple, list)) or len(contenders) < 2:
                    raise ValueError("original_source_edge_contenders_incomplete")
                candidate_ids = set()
                candidate_rows = []
                for candidate in contenders:
                    if not isinstance(candidate, dict):
                        raise ValueError("original_source_wall_record_malformed")
                    wall_id = candidate.get("wall_id")
                    if type(wall_id) is not str or not wall_id or wall_id in candidate_ids:
                        raise ValueError("original_source_wall_id_invalid_or_duplicate")
                    candidate_ids.add(wall_id)
                    originals = _source_refs(candidate)
                    observed = []
                    if originals is None:
                        observed.append({
                            "native_primitive_id": None,
                            "status": "native_source_primitive_unavailable",
                            "source_ink_span_covered": None,
                        })
                    else:
                        for primitive_id in originals:
                            try:
                                ink = read_native_ink_receipt(
                                    drawings, primitive_id,
                                    edge_row["competing_planar_edge"],
                                )
                            except (ValueError, TypeError, OverflowError, IndexError) as exc:
                                observed.append({
                                    "native_primitive_id": primitive_id,
                                    "status": "native_source_primitive_unavailable",
                                    "error_type": type(exc).__name__,
                                    "source_ink_span_covered": None,
                                })
                            else:
                                observed.append({
                                    "native_primitive_id": primitive_id,
                                    "status": "original_pdf_native_item_read",
                                    "source_ink_span_covered": bool(
                                        ink["native_stroke_fully_covers_atomic_wall_candidate"]
                                    ),
                                    "original_pdf_source_edge": ink["native_source_edge_pdf_pts"],
                                    "original_pdf_paint_metadata": ink[
                                        "original_native_paint_metadata_candidate_only"
                                    ],
                                    "native_ink_not_structural_wall_proof": True,
                                })
                    unknown = any(row["source_ink_span_covered"] is None for row in observed)
                    positive = any(row["source_ink_span_covered"] is True for row in observed)
                    # "False" means no indexed native *line* yet covering, not
                    # absence of other original paint or a raster wall.
                    candidate_rows.append({
                        "w4_candidate_wall_id": wall_id,
                        "original_pdf_native_primitive_receipts": observed,
                        "direct_indexed_native_ink_witness": (
                            None if unknown else positive
                        ),
                        "wall_role_authenticated": False,
                        "physical_wall_equivalence_granted": False,
                    })
                candidate_rows.sort(key=lambda v: v["w4_candidate_wall_id"])
                positive_native_id_sets = [
                    {
                        ink["native_primitive_id"]
                        for ink in candidate["original_pdf_native_primitive_receipts"]
                        if ink["source_ink_span_covered"] is True
                    }
                    for candidate in candidate_rows
                    if candidate["direct_indexed_native_ink_witness"] is True
                ]
                positives = len(positive_native_id_sets)
                unavailable = any(v["direct_indexed_native_ink_witness"] is None
                                  for v in candidate_rows)
                shared_original_native_ids = sorted({
                    primitive
                    for i, left in enumerate(positive_native_id_sets)
                    for right in positive_native_id_sets[i + 1:]
                    for primitive in left & right
                })
                # Shared source address across two W4 graph candidates is ONE
                # original indexed native item, not two independent native
                # walls. Never use this to override typed W4 equivalence.
                classification = (
                    "original_pdf_native_ink_unavailable" if unavailable else
                    "original_pdf_w4_candidates_share_same_native_ink" if
                    positives > 1 and shared_original_native_ids else
                    "original_pdf_distinct_w4_candidates_have_native_ink" if
                    positives > 1 else
                    "original_pdf_one_w4_candidate_has_native_ink" if positives == 1 else
                    "original_pdf_no_indexed_candidate_native_ink_span"
                )
                audit_edges.append({
                    "face_id": edge_row["face_id"],
                    "original_competing_planar_edge_pdf_pts": edge_row["competing_planar_edge"],
                    "indexed_native_ink_status": classification,
                    "shared_original_native_source_ids": shared_original_native_ids,
                    "w4_candidate_original_ink_evidence": candidate_rows,
                    "source_native_wall_role_authenticated": False,
                    "source_room_boundary_closed": False,
                    "metric_or_material_published": False,
                    "customer_output_published": False,
                    "diagnostic_only": True,
                })
            rows.append({
                "page_id": scope["page_id"],
                "revision_id": scope["revision_id"],
                "snapshot_id": scope["snapshot_id"],
                "decision_scope_id": scope["decision_scope_id"],
                "w4_scope_complete_unchanged": scope["w4_scope_complete"],
                "previous_surviving_w2_diagnostic": previous["scopes"][
                    len(rows)
                ]["contested_source_edges"],
                "original_pdf_native_drawing_path_count": len(drawings),
                "edges": audit_edges,
                "physical_room_published": False,
            })
    return {
        "source_sha256": sha,
        "source_snapshot_preserved_as_reported": True,
        "native_ink_independently_read_from_source_pdf": True,
        "scopes": rows,
        "new_commercial_quantities": [],
        "physical_wall_or_room_authority_granted": False,
        "frozen_benchmark_scored": False,
        "diagnostic_only": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pdf = args.pdf.read_bytes()
    if hashlib.sha256(pdf).hexdigest() != args.sha:
        raise ValueError("original_pdf_sha_check_failed")
    report = json.loads(args.source_report.read_text())
    out = inspect_native_ink_against_w2(report, pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_sha256": out["source_sha256"],
        "native_span_statuses": [
            e["indexed_native_ink_status"]
            for scope in out["scopes"] for e in scope["edges"]
        ],
        "new_commercial_quantities": out["new_commercial_quantities"],
        "physical_room_authority_granted": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
