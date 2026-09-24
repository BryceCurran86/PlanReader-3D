"""Real-source shadow harness for Item 19B KSTVET page 54.

Diagnostic only. The input PDF must match the repository-pinned KSTVET SHA.
No benchmark quantity, expected BOQ value, live extractor, or commercial output
is read or changed.
"""
from __future__ import annotations

import faulthandler
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_wall_finish_face_binding_authority import (
    WallFinishFaceBindingProducer,
    _authoritative_viewports,
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _trusted_finish_blocks,
)
from pb_source_visibility_authority import SourceVisibilityProducer

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"


def run(pdf_path: Path) -> list[dict]:
    faulthandler.dump_traceback_later(60, repeat=True)
    print("ITEM19B_STAGE read_source", flush=True)
    payload = pdf_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(
            f"KSTVET source SHA mismatch: expected {EXPECTED_SHA256}, got {actual}"
        )

    print("ITEM19B_STAGE source_sha_verified", flush=True)
    source = SourceVisibilityProducer(
        producer_method="item19b-kstvet-direct-finish-shadow",
        producer_version="1.0.0",
    )
    print("ITEM19B_STAGE ingest_page54_start", flush=True)
    published = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-shadow",
        source_bytes=payload,
        source_locator=f"sha256://{EXPECTED_SHA256}",
        page_ids=(PAGE_ID,),
    )
    print("ITEM19B_STAGE ingest_page54_done", flush=True)
    pdf = __import__("fitz").open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(int(PAGE_ID) - 1)
        blocks = _trusted_finish_blocks(source, published, PAGE_ID)
        viewports = _authoritative_viewports(page, int(PAGE_ID))
        lines = _page_visible_lines(source, published, PAGE_ID)
        preflight = {
            "trusted_finish_blocks": [
                {
                    "text": text,
                    "annotation_observation_ids": list(annotation_ids),
                    "bbox": list(annotation_bbox),
                    "semantics": [
                        {
                            "trade_scope_id": semantic.trade_scope_id,
                            "finish_material": semantic.finish_material,
                            "direction": semantic.direction,
                        }
                        for semantic in semantics
                    ],
                }
                for _, text, semantics, annotation_ids, annotation_bbox, _ in blocks
            ],
            "authoritative_viewports": [
                {
                    "view_id": viewport.view_id,
                    "label": viewport.label,
                    "status": viewport.status,
                    "bbox": list(viewport.bounding_box) if viewport.bounding_box else None,
                }
                for viewport in viewports
            ],
            "native_visible_line_count": len(lines),
            "callout_preflight": [],
        }
        from pb_viewport_segmentation import assign_bbox_to_viewport
        for _, text, semantics, annotation_ids, annotation_bbox, text_height in blocks:
            viewport = assign_bbox_to_viewport(annotation_bbox, viewports, allow_derived=True)
            terms = _filled_terminators(page, text_height)
            owned_lines = ()
            owned_terms = ()
            paths = ()
            if viewport is not None and viewport.bounding_box is not None:
                owned_lines = tuple(
                    line for line in lines
                    if all(
                        viewport.bounding_box[0] <= point[0] <= viewport.bounding_box[2]
                        and viewport.bounding_box[1] <= point[1] <= viewport.bounding_box[3]
                        for point in (
                            (line.geometry[0], line.geometry[1]),
                            (line.geometry[2], line.geometry[3]),
                        )
                    )
                )
                owned_terms = tuple(
                    term for term in terms
                    if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                    and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
                )
                epsilon = max(1e-6, text_height * 0.08)
                paths = _leader_paths(annotation_bbox, owned_lines, owned_terms, epsilon)
            preflight["callout_preflight"].append(
                {
                    "text": text,
                    "viewport_id": getattr(viewport, "view_id", None),
                    "owned_line_count": len(owned_lines),
                    "terminator_count": len(owned_terms),
                    "leader_paths": [
                        {
                            "leader_path_ids": list(ids),
                            "terminator_id": term.primitive_id,
                            "terminator_bbox": list(term.bbox),
                        }
                        for ids, term in paths
                    ],
                }
            )
        print("ITEM19B_PREFLIGHT " + json.dumps(preflight, sort_keys=True), flush=True)
    finally:
        pdf.close()
    print("ITEM19B_STAGE finish_producer_start", flush=True)
    producer = WallFinishFaceBindingProducer.from_source_visibility_producer(
        source,
        page_ids=(PAGE_ID,),
    )

    print("ITEM19B_STAGE finish_producer_done", flush=True)
    faulthandler.cancel_dump_traceback_later()
    rows: list[dict] = []
    for result in producer.published_results():
        for record in result.bindings:
            if record.page_id != PAGE_ID:
                continue
            rows.append(
                {
                    "annotation_observation_ids": list(record.annotation_observation_ids),
                    "leader_path_ids": list(record.leader_path_ids),
                    "terminator_primitive_ids": list(record.terminator_primitive_ids),
                    "physical_wall_id": record.physical_wall_id,
                    "wall_role_record_id": record.wall_role_record_id,
                    "wall_role": record.wall_role.value,
                    "semantic_face": record.physical_face_role.value,
                    "physical_face_id": record.physical_face_id,
                    "source_face_segment_ids": list(record.source_face_segment_ids),
                    "trade_scope_id": record.trade_scope_id,
                    "finish_material": record.finish_material,
                    "binding_status": record.status.value,
                    "scope_completeness": record.decision_scope_complete,
                    "reason_codes": list(record.reason_codes),
                }
            )
        for scope in result.scope_records:
            rows.append(
                {
                    "scope_record": True,
                    "scope_id": scope.scope_id,
                    "trade_scope_id": scope.trade_scope_id,
                    "finish_material": scope.finish_material,
                    "target_face_ids": list(scope.target_face_ids),
                    "covered_face_ids": list(scope.covered_face_ids),
                    "binding_ids": list(scope.binding_ids),
                    "scope_status": scope.scope_status.value,
                    "scope_completeness": scope.decision_scope_complete,
                    "reason_codes": list(scope.reason_codes),
                }
            )
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: wall_finish_face_binding_kstvet_shadow.py <canonical-kstvet.pdf>")
    rows = run(Path(sys.argv[1]))
    print(json.dumps(rows, indent=2, sort_keys=True))
    direct = [row for row in rows if not row.get("scope_record")]
    if not direct:
        raise SystemExit("KSTVET page 54 produced no accepted direct finish callout bindings")


if __name__ == "__main__":
    main()
