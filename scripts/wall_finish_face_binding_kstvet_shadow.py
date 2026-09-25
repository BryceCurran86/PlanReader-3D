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
    _finish_semantics,
    _leader_paths,
    _page_visible_lines,
    _segment_intersects_bbox,
    _trusted_finish_blocks,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_wall_topology_authority import build_source_wall_topology_authority
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_role_authority import WallRoleProducer, WallRoleSelector

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"


def _observation_details(
    source: SourceVisibilityProducer,
    published,
    observation_ids,
) -> list[dict]:
    authority = source.authority()
    rows = []
    for observation_id in sorted(set(str(value) for value in observation_ids if str(value))):
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        rows.append(
            {
                "observation_id": observation_id,
                "status": getattr(result.status, "value", str(result.status)),
                "observation_kind": (
                    None if observation is None else observation.observation_kind
                ),
                "source_primitive_ref": (
                    None if observation is None else observation.source_primitive_ref
                ),
                "geometry": (
                    None
                    if observation is None
                    else [float(value) for value in observation.geometry]
                ),
            }
        )
    return rows


def run(pdf_path: Path) -> tuple[list[dict], dict]:
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
        raw_blocks: dict[int, list[tuple[int, str, tuple[float, float, float, float]]]] = {}
        for word in page.get_text("words") or ():
            if len(word) < 8:
                continue
            block_no = int(word[5])
            line_no = int(word[6])
            word_no = int(word[7])
            raw_blocks.setdefault(block_no, []).append(
                (
                    line_no * 10000 + word_no,
                    str(word[4] or ""),
                    tuple(float(value) for value in word[:4]),
                )
            )
        raw_semantic_finish_blocks = []
        for block_no, items in sorted(raw_blocks.items()):
            ordered_items = sorted(items, key=lambda item: item[0])
            raw_text = " ".join(text for _, text, _ in ordered_items)
            semantics = _finish_semantics(raw_text)
            if semantics:
                boxes = [bbox for _, _, bbox in ordered_items]
                raw_bbox = (
                    min(box[0] for box in boxes),
                    min(box[1] for box in boxes),
                    max(box[2] for box in boxes),
                    max(box[3] for box in boxes),
                )
                raw_semantic_finish_blocks.append(
                    {
                        "block_no": block_no,
                        "text": raw_text,
                        "bbox": list(raw_bbox),
                        "text_height": sorted(max(0.1, box[3] - box[1]) for box in boxes)[len(boxes) // 2],
                        "semantics": [
                            {
                                "trade_scope_id": semantic.trade_scope_id,
                                "finish_material": semantic.finish_material,
                                "direction": semantic.direction,
                            }
                            for semantic in semantics
                        ],
                        "authority": "diagnostic_raw_native_text_only",
                    }
                )

        text_authority = source.text_integrity_authority()
        target_sequence_ranges = {
            "external_e02": (10061, 10065),
            "internal_ground_plan": (10070, 10078),
        }
        target_sequence_callouts = []
        for target_name, (seq_start, seq_end) in target_sequence_ranges.items():
            words = []
            for observation_id in published.text_observation_ids:
                resolved = text_authority.resolve_text(
                    ObservationSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                receipt = resolved.receipt
                if (
                    receipt is None
                    or receipt.page_id != PAGE_ID
                    or receipt.sequence_number is None
                    or not seq_start <= int(receipt.sequence_number) <= seq_end
                ):
                    continue
                words.append(
                    (
                        int(receipt.sequence_number),
                        -1 if receipt.block_no is None else int(receipt.block_no),
                        -1 if receipt.line_no is None else int(receipt.line_no),
                        -1 if receipt.word_no is None else int(receipt.word_no),
                        observation_id,
                        receipt,
                        resolved,
                    )
                )
            words.sort(key=lambda item: item[:5])
            if not words:
                continue
            boxes = [tuple(float(v) for v in item[5].geometry) for item in words]
            text = " ".join(str(item[5].raw_text or "") for item in words)
            bbox = (
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
                max(box[2] for box in boxes),
                max(box[3] for box in boxes),
            )
            heights = sorted(max(0.1, box[3] - box[1]) for box in boxes)
            target_sequence_callouts.append(
                {
                    "target": target_name,
                    "sequence_range": [seq_start, seq_end],
                    "text": text,
                    "bbox": list(bbox),
                    "text_height": heights[len(heights) // 2],
                    "semantics": [
                        {
                            "trade_scope_id": semantic.trade_scope_id,
                            "finish_material": semantic.finish_material,
                            "direction": semantic.direction,
                        }
                        for semantic in _finish_semantics(text)
                    ],
                    "word_count": len(words),
                    "all_native_text_corroborated": all(
                        item[6].status.value == "corroborated"
                        for item in words
                    ),
                    "words": [
                        {
                            "observation_id": item[4],
                            "receipt_id": item[5].receipt_id,
                            "sequence_number": item[5].sequence_number,
                            "trace_sequence_numbers": list(item[5].trace_sequence_numbers),
                            "block_no": item[5].block_no,
                            "line_no": item[5].line_no,
                            "word_no": item[5].word_no,
                            "raw_text": item[5].raw_text,
                            "status": item[6].status.value,
                            "reason_codes": list(item[6].reason_codes),
                        }
                        for item in words
                    ],
                    "authority": "diagnostic_sequence_range_only_not_callout_authority",
                }
            )

        preflight = {
            "target_sequence_callouts_diagnostic": target_sequence_callouts,
            "raw_semantic_finish_blocks_diagnostic": raw_semantic_finish_blocks,
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
        native_page = extract_native_page(page)
        native_segments_by_id = {
            str(segment.get("id") or ""): dict(segment)
            for segment in (native_page.get("segments") or ())
            if str(segment.get("id") or "")
        }
        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=(PAGE_ID,),
        ).authority()
        # Raster-visible augmentation advances the immutable source snapshot.
        # Refresh lineage before issuing any wall/topology selectors; retaining
        # the pre-augmentation snapshot would make valid viewport scopes appear
        # unavailable in this diagnostic.
        published = source.published_snapshot_for_revision(
            published.revision.revision_id
        )
        topology_authority = build_source_wall_topology_authority(wall_authority)
        role_producer = WallRoleProducer.from_source_topology(
            physical_wall_candidate_authority=wall_authority
        )

        preflight["page_wall_scope"] = {
            "materialized": False,
            "reason": "viewport_only_authority_avoids_full_page_wall_graph",
        }
        preflight["viewport_wall_scopes"] = []
        for viewport in viewports:
            wall_selector = wall_authority.selector_for_viewport(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=PAGE_ID,
                viewport_id=viewport.view_id,
            )
            if wall_selector is None:
                preflight["viewport_wall_scopes"].append(
                    {
                        "viewport_id": viewport.view_id,
                        "label": viewport.label,
                        "wall_scope": "unavailable",
                    }
                )
                continue
            wall_scope = wall_authority.resolve_scope(wall_selector)
            topology_count = 0
            role_counts: dict[str, int] = {}
            role_reasons: dict[str, int] = {}
            for record in wall_scope.records:
                role_selector = WallRoleSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=PAGE_ID,
                    decision_scope_id=wall_scope.decision_scope_id,
                    physical_wall_id=record.wall_candidate_id,
                )
                if topology_authority.get_evidence(role_selector) is not None:
                    topology_count += 1
                role_result = role_producer.publish(role_selector)
                if role_result.record is not None:
                    key = role_result.record.role.value
                    role_counts[key] = role_counts.get(key, 0) + 1
                else:
                    for reason in role_result.reason_codes:
                        role_reasons[reason] = role_reasons.get(reason, 0) + 1
            preflight["viewport_wall_scopes"].append(
                {
                    "viewport_id": viewport.view_id,
                    "label": viewport.label,
                    "view_type": viewport.view_type,
                    "decision_scope_id": wall_scope.decision_scope_id,
                    "wall_candidate_count": len(wall_scope.records),
                    "scope_complete": wall_scope.scope_complete,
                    "reason_codes": list(wall_scope.reason_codes),
                    "owned_source_observation_count": len(wall_scope.source_observation_ids),
                    "boundary_source_observation_count": len(wall_scope.scope_boundary_observation_ids),
                    "boundary_source_observations": _observation_details(
                        source,
                        published,
                        wall_scope.scope_boundary_observation_ids,
                    ),
                    "ambiguous_source_observation_count": len(wall_scope.ambiguous_source_observation_ids),
                    "ambiguous_source_observations": _observation_details(
                        source,
                        published,
                        wall_scope.ambiguous_source_observation_ids,
                    ),
                    "topology_record_count": topology_count,
                    "resolved_role_counts": role_counts,
                    "abstained_role_reason_counts": role_reasons,
                }
            )

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
        # Diagnostic-only raw native text path: lets the wall/terminator side
        # be inspected even while SourceExecutionCalloutAuthority remains owned
        # by another agent. Raw text never enters production binding authority.
        preflight["raw_callout_wall_hits"] = []
        for raw in target_sequence_callouts:
            annotation_bbox = tuple(float(value) for value in raw["bbox"])
            text_height = float(raw["text_height"])
            viewport = assign_bbox_to_viewport(
                annotation_bbox,
                viewports,
                allow_derived=True,
            )
            if viewport is None or viewport.bounding_box is None:
                continue
            wall_selector = wall_authority.selector_for_viewport(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=PAGE_ID,
                viewport_id=viewport.view_id,
            )
            if wall_selector is None:
                continue
            wall_scope = wall_authority.resolve_scope(wall_selector)
            owned_ids = set(wall_scope.source_observation_ids)
            owned_lines = tuple(
                line for line in lines if line.observation_id in owned_ids
            )
            owned_terms = tuple(
                term for term in _filled_terminators(page, text_height)
                if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
            )
            for leader_ids, term in _leader_paths(
                annotation_bbox,
                owned_lines,
                owned_terms,
            ):
                raw_hits = sorted(
                    {
                        line.raw_id
                        for line in owned_lines
                        if _segment_intersects_bbox(line.geometry, term.bbox)
                    }
                )
                matching = [
                    record for record in wall_scope.records
                    if set(raw_hits) & set(record.physical_identity.source_primitive_ids)
                ]
                representative_for = {}
                for group in tuple(
                    getattr(wall_scope.equivalence, "equivalence_groups", ()) or ()
                ):
                    representative = sorted(group)[0]
                    for wall_id in group:
                        representative_for[wall_id] = representative
                normalized_ids = sorted(
                    {
                        representative_for.get(
                            record.wall_candidate_id,
                            record.wall_candidate_id,
                        )
                        for record in matching
                    }
                )
                preflight["raw_callout_wall_hits"].append(
                    {
                        "text": raw["text"],
                        "semantics": raw["semantics"],
                        "viewport_id": viewport.view_id,
                        "leader_path_ids": list(leader_ids),
                        "terminator_id": term.primitive_id,
                        "terminator_bbox": list(term.bbox),
                        "raw_source_primitive_hits": raw_hits,
                        "raw_source_primitive_provenance": [
                            {
                                "raw_id": raw_id,
                                "path_index": native_segments_by_id.get(raw_id, {}).get("path_index"),
                                "item_index": native_segments_by_id.get(raw_id, {}).get("item_index"),
                                "kind": native_segments_by_id.get(raw_id, {}).get("kind"),
                                "layer": native_segments_by_id.get(raw_id, {}).get("layer"),
                                "width": native_segments_by_id.get(raw_id, {}).get("width"),
                                "dashes": native_segments_by_id.get(raw_id, {}).get("dashes"),
                                "geometry": [
                                    native_segments_by_id.get(raw_id, {}).get("x1"),
                                    native_segments_by_id.get(raw_id, {}).get("y1"),
                                    native_segments_by_id.get(raw_id, {}).get("x2"),
                                    native_segments_by_id.get(raw_id, {}).get("y2"),
                                ],
                            }
                            for raw_id in raw_hits
                        ],
                        "wall_candidate_sources": [
                            {
                                "wall_candidate_id": record.wall_candidate_id,
                                "source_primitive_ids": list(
                                    record.physical_identity.source_primitive_ids
                                ),
                                "source_paths": sorted(
                                    {
                                        native_segments_by_id.get(raw_id, {}).get("path_index")
                                        for raw_id in record.physical_identity.source_primitive_ids
                                        if native_segments_by_id.get(raw_id, {}).get("path_index") is not None
                                    }
                                ),
                            }
                            for record in sorted(matching, key=lambda item: item.wall_candidate_id)
                        ],
                        "wall_candidate_ids": sorted(
                            record.wall_candidate_id for record in matching
                        ),
                        "physical_wall_ids": sorted(
                            {
                                str(
                                    getattr(
                                        record.physical_identity,
                                        "physical_wall_id",
                                        record.wall_candidate_id,
                                    )
                                )
                                for record in matching
                            }
                        ),
                        "normalized_wall_ids": normalized_ids,
                        "wall_scope_complete": wall_scope.scope_complete,
                    }
                )

        print("ITEM19B_PREFLIGHT " + json.dumps(preflight, sort_keys=True), flush=True)
    finally:
        pdf.close()
    if not preflight.get("trusted_finish_blocks"):
        print(
            "ITEM19B_STAGE finish_producer_skipped_text_authority_pending",
            flush=True,
        )
        faulthandler.cancel_dump_traceback_later()
        return [], preflight

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
    return rows, preflight


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: wall_finish_face_binding_kstvet_shadow.py <canonical-kstvet.pdf>")
    rows, preflight = run(Path(sys.argv[1]))
    print(json.dumps(rows, indent=2, sort_keys=True))
    direct = [row for row in rows if not row.get("scope_record")]
    raw_semantic_count = len(
        preflight.get("raw_semantic_finish_blocks_diagnostic", ())
    )
    trusted_semantic_count = len(preflight.get("trusted_finish_blocks", ()))
    leader_path_count = sum(
        len(item.get("leader_paths", ()))
        for item in preflight.get("callout_preflight", ())
    )
    if direct:
        real_source_status = "CORROBORATED"
    elif raw_semantic_count and not trusted_semantic_count:
        real_source_status = "FINISH_BINDING_SOURCE_PRESENT_TEXT_AUTHORITY_PENDING"
    elif trusted_semantic_count and not leader_path_count:
        real_source_status = "FINISH_BINDING_SOURCE_PRESENT_GEOMETRY_PENDING"
    else:
        real_source_status = "FINISH_BINDING_SOURCE_PRESENT_DOWNSTREAM_AUTHORITY_PENDING"

    print(
        "ITEM19B_REAL_SOURCE_STATUS "
        + json.dumps(
            {
                "page_id": PAGE_ID,
                "status": real_source_status,
                "accepted_direct_binding_count": len(direct),
                "raw_semantic_finish_block_count_diagnostic": raw_semantic_count,
                "trusted_semantic_finish_block_count": trusted_semantic_count,
                "leader_path_count": leader_path_count,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
