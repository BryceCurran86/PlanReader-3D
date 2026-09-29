"""TEST-ONLY exact KSTVET C47-A finish-callout wall gate trace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_execution_callout_authority import SourceExecutionCalloutProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_wall_finish_callout_wall_authority import (
    _local_owner_universe_safe,
    _target_provenance,
)
from pb_wall_finish_face_binding_authority import (
    _authoritative_viewports,
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _segment_intersects_bbox,
    _target_from_terminator,
    _viewport_owned_lines,
)

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"


def main(pdf_path: Path) -> None:
    payload = pdf_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(f"source sha mismatch: {actual}")

    source = SourceVisibilityProducer(
        producer_method="kstvet-c47a-wall-gate-trace",
        producer_version="1.0",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="kstvet-c47a-wall-gate-trace",
        source_bytes=payload,
        source_locator=f"sha256://{EXPECTED_SHA256}",
        page_ids=(PAGE_ID,),
    )

    wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=(PAGE_ID,),
    ).authority()

    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    callout_authority = SourceExecutionCalloutProducer.from_source_visibility_producer(
        source,
        page_ids=(PAGE_ID,),
    ).authority()
    published = source.published_snapshot_for_revision(initial.revision.revision_id)

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page = doc.load_page(int(PAGE_ID) - 1)
        viewports = _authoritative_viewports(page, int(PAGE_ID))
        page_lines = _page_visible_lines(source, published, PAGE_ID)
        callout_page = callout_authority.resolve_page(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=PAGE_ID,
        )

        rows = []
        for callout in callout_page.records:
            external_semantics = [
                semantic for semantic in callout.semantics
                if semantic.trade_scope_id == "external_key_pointing"
            ]
            if not external_semantics:
                continue

            row = {
                "callout_record_id": callout.record_id,
                "sequence": [callout.sequence_start, callout.sequence_end],
                "bbox": list(callout.source_bbox),
                "semantics": [
                    {
                        "trade": semantic.trade_scope_id,
                        "material": semantic.finish_material,
                        "direction": semantic.direction,
                    }
                    for semantic in external_semantics
                ],
            }
            viewport = assign_bbox_to_viewport(
                callout.source_bbox,
                viewports,
                allow_derived=True,
            )
            row["viewport_id"] = None if viewport is None else viewport.view_id
            if viewport is None or viewport.bounding_box is None:
                row["gate"] = "viewport_unavailable"
                rows.append(row)
                continue

            wall_selector = wall_authority.selector_for_viewport(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=PAGE_ID,
                viewport_id=viewport.view_id,
            )
            row["wall_selector_available"] = wall_selector is not None
            if wall_selector is None:
                row["gate"] = "wall_selector_unavailable"
                rows.append(row)
                continue

            wall_scope = wall_authority.resolve_scope(wall_selector)
            row.update({
                "wall_scope_status": wall_scope.status.value,
                "wall_scope_complete": wall_scope.scope_complete,
                "wall_scope_reasons": list(wall_scope.reason_codes),
                "wall_candidate_count": len(wall_scope.records),
                "boundary_observation_count": len(
                    tuple(wall_scope.scope_boundary_observation_ids or ())
                ),
                "ambiguous_observation_count": len(
                    tuple(wall_scope.ambiguous_source_observation_ids or ())
                ),
            })
            if wall_scope.status is not EvidenceResolutionStatus.CORROBORATED:
                row["gate"] = "wall_scope_unresolved"
                rows.append(row)
                continue

            leader_lines = _viewport_owned_lines(page_lines, viewport, viewports)
            wall_observation_ids = set(wall_scope.source_observation_ids)
            wall_lines = tuple(
                line for line in page_lines
                if line.observation_id in wall_observation_ids
            )
            terminators = tuple(
                term for term in _filled_terminators(page, callout.text_height)
                if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
            )
            paths = _leader_paths(callout.source_bbox, leader_lines, terminators)
            row.update({
                "leader_line_count": len(leader_lines),
                "wall_line_count": len(wall_lines),
                "terminator_count": len(terminators),
                "leader_path_count": len(paths),
                "paths": [],
            })
            if not paths:
                row["gate"] = "leader_path_unavailable"
                rows.append(row)
                continue

            questionable = tuple(dict.fromkeys((
                *tuple(wall_scope.scope_boundary_observation_ids or ()),
                *tuple(wall_scope.ambiguous_source_observation_ids or ()),
            )))
            by_observation = {}
            for line in page_lines:
                by_observation.setdefault(str(line.observation_id), []).append(line)

            any_positive = False
            for leader_ids, terminator in paths:
                local_safe = _local_owner_universe_safe(
                    terminator=terminator,
                    page_lines=page_lines,
                    wall_scope=wall_scope,
                )
                target, source_segments, target_status = _target_from_terminator(
                    terminator,
                    wall_lines,
                    wall_scope,
                )
                blockers = []
                for observation_id in questionable:
                    candidates = by_observation.get(str(observation_id), ())
                    if not candidates:
                        blockers.append({
                            "observation_id": observation_id,
                            "reason": "withheld_primitive_not_replayable",
                        })
                    elif any(
                        _segment_intersects_bbox(line.geometry, terminator.bbox)
                        for line in candidates
                    ):
                        blockers.append({
                            "observation_id": observation_id,
                            "reason": "withheld_primitive_intersects_terminator",
                            "raw_ids": sorted({line.raw_id for line in candidates}),
                            "geometries": [list(line.geometry) for line in candidates],
                        })

                path_row = {
                    "leader_path_ids": list(leader_ids),
                    "terminator_id": terminator.primitive_id,
                    "terminator_bbox": list(terminator.bbox),
                    "local_owner_universe_safe": local_safe,
                    "local_owner_blockers": blockers,
                    "target_status": target_status.value,
                    "target_wall_id": (
                        None if target is None else target.wall_candidate_id
                    ),
                    "source_segments": list(source_segments),
                }
                if target is not None:
                    raw_owners, group, pairs = _target_provenance(
                        terminator=terminator,
                        wall_lines=wall_lines,
                        wall_scope=wall_scope,
                        target=target,
                    )
                    path_row.update({
                        "raw_owner_wall_ids": list(raw_owners),
                        "equivalence_group_wall_ids": list(group),
                        "equivalence_pair_classifications": [list(x) for x in pairs],
                    })
                if local_safe and target_status is EvidenceResolutionStatus.CORROBORATED and target is not None:
                    any_positive = True
                row["paths"].append(path_row)

            row["gate"] = "positive_wall_binding_possible" if any_positive else "local_or_target_gate_blocked"
            rows.append(row)

        print("KSTVET_C47A_WALL_GATE_TRACE " + json.dumps(rows, sort_keys=True), flush=True)
    finally:
        doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: diag_kstvet_finish_callout_wall_gate.py <kstvet.pdf>")
    main(Path(sys.argv[1]))
