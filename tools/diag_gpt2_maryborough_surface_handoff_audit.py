from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

import pb_cross_view_ceiling_finish_authority as ceiling
from pb_cross_view_ceiling_finish_authority import CrossViewCeilingFinishProducer
from pb_cross_view_floor_finish_authority import CrossViewFloorFinishProducer
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceComposition
from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
from pb_live_ceiling_lining_source_closed_export import seal_live_ceiling_lining_run
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionSelector,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.run_source_closed_project_handoff import _source_page_scopes

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PROJECT = "au_qld_maryborough_service_station"
EXPECTED_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _status(value) -> str:
    return getattr(value, "value", str(value))


def _clean(value) -> str:
    return str(value or "").strip()


def _room_composition(claim) -> LiveCanonicalRoomComposition:
    return LiveCanonicalRoomComposition(
        status=claim.canonical_room_status,
        reason_codes=tuple(claim.canonical_room_reason_codes),
        rooms=tuple(claim.canonical_rooms),
        source_pages=tuple(claim.canonical_room_source_pages),
    )


def _floor_composition(claim) -> LiveCanonicalFloorSurfaceComposition:
    return LiveCanonicalFloorSurfaceComposition(
        status=claim.canonical_floor_status,
        reason_codes=tuple(claim.canonical_floor_reason_codes),
        floors=tuple(claim.canonical_floors),
        source_pages=tuple(claim.canonical_floor_source_pages),
    )


def _rebuild_exact_source(payload: bytes, page_count: int) -> SourceVisibilityProducer:
    sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{sha[:32]}"
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(str(index + 1) for index in range(page_count)),
    )
    return source


def _ceiling_relationship_audit(source, rooms, finish_result):
    eligible = tuple(
        room
        for room in rooms.rooms
        if (
            room.geometry_complete
            and _clean(room.room_label)
            and _clean(room.room_label_binding_record_id)
            and tuple(room.room_label_evidence_ids or ())
        )
    )
    by_label = defaultdict(list)
    for room in eligible:
        by_label[ceiling._norm(room.room_label)].append(room)
    unique_rooms = {
        label: rows[0]
        for label, rows in by_label.items()
        if label and len(rows) == 1
    }
    duplicate_room_ids = {
        room.physical_room_id
        for rows in by_label.values()
        if len(rows) != 1
        for room in rows
    }

    revision_id = rooms.rooms[0].revision_id if rooms.rooms else ""
    rcp_viewports = ceiling._rcp_viewports(source, revision_id=revision_id)
    page_ids = tuple(sorted({page_id for page_id, _ in rcp_viewports}))
    trusted = ceiling._trusted_room_labels_for_pages(
        source,
        revision_id=revision_id,
        page_ids=page_ids,
        candidate_labels=tuple(unique_rooms),
    ) if page_ids else {}

    label_rows_by_room = defaultdict(list)
    room_label_lines = defaultdict(list)
    for (page_id, viewport_id), viewport_bbox in rcp_viewports.items():
        for line in trusted.get(page_id, ()):
            label = ceiling._norm(line.text)
            if (
                label not in unique_rooms
                or not ceiling._bbox_fully_inside(line.bbox, viewport_bbox)
            ):
                continue
            room = unique_rooms[label]
            row = {
                "page_id": page_id,
                "viewport_id": viewport_id,
                "room_label": line.text,
                "source_partition_id": line.source_partition_id,
                "block_no": line.block_no,
                "line_no": line.line_no,
                "observation_ids": list(line.observation_ids),
                "receipt_ids": list(line.receipt_ids),
                "bbox": list(line.bbox),
            }
            label_rows_by_room[room.physical_room_id].append(row)
            room_label_lines[(page_id, viewport_id)].append((line, label))

    material_producer = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    material_authority = material_producer.publish(revision_id)
    occurrences = []
    qualified_occurrences = []
    for result in material_producer.published_occurrence_results():
        for occurrence in result.records:
            raw = {
                "scope_status": _status(result.status),
                "scope_complete": bool(result.scope_complete),
                "scope_reason_codes": list(result.reason_codes),
                "record_id": occurrence.record_id,
                "page_id": occurrence.page_id,
                "viewport_id": occurrence.viewport_id,
                "code": occurrence.code,
                "semantic_finish": occurrence.semantic_finish,
                "source_evidence_id": occurrence.source_evidence_id,
                "source_text_observation_ids": list(occurrence.source_text_observation_ids),
                "bbox": list(occurrence.bbox_pdf_pts),
            }
            occurrences.append(raw)
            key = (_clean(occurrence.page_id), _clean(occurrence.viewport_id))
            viewport_bbox = rcp_viewports.get(key)
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or not result.scope_complete
                or viewport_bbox is None
            ):
                continue
            definition_result = material_authority.resolve_definition(
                SourceMaterialDefinitionSelector(
                    document_id=occurrence.document_id,
                    revision_id=occurrence.revision_id,
                    source_sha256=occurrence.source_sha256,
                    snapshot_id=occurrence.snapshot_id,
                    code=occurrence.code,
                )
            )
            definition = definition_result.record
            if (
                definition_result.status is not EvidenceResolutionStatus.CORROBORATED
                or definition is None
                or definition.record_id != occurrence.definition_record_id
                or definition.semantic_finish != occurrence.semantic_finish
                or not ceiling._definition_is_ceiling_finish(definition)
                or not ceiling._bbox_fully_inside(occurrence.bbox_pdf_pts, viewport_bbox)
            ):
                continue
            occurrence_line = ceiling._occurrence_line(
                source,
                revision_id=revision_id,
                occurrence=occurrence,
            )
            if occurrence_line is None:
                continue
            qualified_occurrences.append({
                **raw,
                "definition_record_id": definition.record_id,
                "definition_evidence_ids": list(definition.source_definition_ids),
                "occurrence_source_partition_id": occurrence_line.source_partition_id,
                "occurrence_block_no": occurrence_line.block_no,
                "occurrence_line_no": occurrence_line.line_no,
                "occurrence_observation_ids": list(occurrence_line.observation_ids),
                "occurrence_receipt_ids": list(occurrence_line.receipt_ids),
                "_occurrence": occurrence,
                "_definition": definition,
                "_line": occurrence_line,
            })

    candidate_rows = defaultdict(list)
    conflict_rooms = set()
    for row in qualified_occurrences:
        key = (row["page_id"], row["viewport_id"])
        line = row["_line"]
        same_block_labels = [
            (label_line, label)
            for label_line, label in room_label_lines.get(key, ())
            if (
                label_line.source_partition_id == line.source_partition_id
                and label_line.block_no == line.block_no
            )
        ]
        labels = {label for _label_line, label in same_block_labels}
        if len(labels) > 1:
            for label in labels:
                if label in unique_rooms:
                    conflict_rooms.add(unique_rooms[label].physical_room_id)
            continue
        if len(labels) != 1:
            continue
        label = next(iter(labels))
        matching_label_lines = [
            label_line
            for label_line, candidate_label in same_block_labels
            if candidate_label == label
        ]
        room = unique_rooms[label]
        if len(matching_label_lines) != 1:
            conflict_rooms.add(room.physical_room_id)
            continue
        label_line = matching_label_lines[0]
        candidate_rows[room.physical_room_id].append({
            "page_id": row["page_id"],
            "viewport_id": row["viewport_id"],
            "source_partition_id": line.source_partition_id,
            "block_no": line.block_no,
            "room_label_line_no": label_line.line_no,
            "finish_line_no": line.line_no,
            "room_label_observation_ids": list(label_line.observation_ids),
            "room_label_receipt_ids": list(label_line.receipt_ids),
            "finish_code": row["code"],
            "semantic_finish": row["semantic_finish"],
            "finish_occurrence_record_id": row["record_id"],
            "finish_occurrence_evidence_id": row["source_evidence_id"],
            "finish_occurrence_observation_ids": list(line.observation_ids),
            "finish_occurrence_receipt_ids": list(line.receipt_ids),
            "definition_record_id": row["definition_record_id"],
            "definition_evidence_ids": row["definition_evidence_ids"],
        })

    finish_by_room = finish_result.records_by_physical_room_id
    audit = {}
    material_definition_count = sum(
        1 for result in material_producer._definition_results.values()
        if result.record is not None
    )
    for room in rooms.rooms:
        pid = room.physical_room_id
        normalized = ceiling._norm(room.room_label)
        label_rows = label_rows_by_room.get(pid, [])
        candidates = candidate_rows.get(pid, [])
        published_finish = finish_by_room.get(pid)

        if pid in duplicate_room_ids or pid in conflict_rooms or len(candidates) > 1:
            classification = "CONFLICT"
            first_gate = "CrossViewCeilingFinishProducer.publish.unique_source_owned_relationship"
        elif published_finish is not None and len(candidates) == 1:
            classification = "CORROBORATED"
            first_gate = None
        else:
            classification = "ABSTAIN"
            if room not in eligible:
                first_gate = "CrossViewCeilingFinishProducer.publish.eligible_rooms"
            elif normalized not in unique_rooms:
                first_gate = "CrossViewCeilingFinishProducer.publish.unique_rooms"
            elif not rcp_viewports:
                first_gate = "CrossViewCeilingFinishProducer._rcp_viewports"
            elif not label_rows:
                first_gate = "CrossViewCeilingFinishProducer._trusted_room_labels_for_pages"
            elif material_definition_count == 0:
                first_gate = "SourceMaterialSemanticProducer.publish.definition_authority"
            elif not qualified_occurrences:
                first_gate = "SourceMaterialSemanticProducer.publish.authenticated_rcp_occurrence"
            else:
                first_gate = "CrossViewCeilingFinishProducer.publish.same_native_block_relationship"

        audit[pid] = {
            "room_label": room.room_label,
            "canonical_room_id": room.canonical_room_id,
            "classification": classification,
            "first_failing_gate": first_gate,
            "rcp_label_lines": label_rows,
            "candidate_same_block_relationships": candidates,
            "published_finish": None if published_finish is None else {
                "record_id": published_finish.record_id,
                "support_page_id": published_finish.support_page_id,
                "support_viewport_id": published_finish.support_viewport_id,
                "support_source_partition_id": published_finish.support_source_partition_id,
                "support_block_no": published_finish.support_block_no,
                "room_label_observation_ids": list(published_finish.room_label_observation_ids),
                "room_label_receipt_ids": list(published_finish.room_label_receipt_ids),
                "finish_code": published_finish.finish_code,
                "semantic_finish": published_finish.semantic_finish,
                "definition_record_id": published_finish.definition_record_id,
                "definition_evidence_ids": list(published_finish.definition_evidence_ids),
                "occurrence_record_id": published_finish.occurrence_record_id,
                "occurrence_evidence_id": published_finish.occurrence_evidence_id,
            },
        }

    clean_qualified = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in qualified_occurrences
    ]
    return {
        "rcp_viewport_count": len(rcp_viewports),
        "rcp_viewports": [
            {"page_id": page_id, "viewport_id": viewport_id, "bbox": list(bbox)}
            for (page_id, viewport_id), bbox in sorted(rcp_viewports.items())
        ],
        "material_definition_record_count": material_definition_count,
        "material_occurrence_record_count": len(occurrences),
        "qualified_ceiling_occurrence_count": len(clean_qualified),
        "qualified_ceiling_occurrences": clean_qualified,
        "room_bindings": audit,
    }


def main() -> int:
    payload = PDF.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    topology, support, page_count = _source_page_scopes(PDF)
    all_pages = tuple(range(page_count))
    claim = collect_live_physical_net_wall_claim(
        PDF,
        pages=all_pages,
        topology_pages=(topology if topology and topology != all_pages else None),
        room_area_support_pages=(support if support else None),
    )

    rooms = _room_composition(claim)
    floors = _floor_composition(claim)
    source = _rebuild_exact_source(payload, page_count)
    published = source.published_snapshot_for_revision(
        rooms.rooms[0].revision_id if rooms.rooms else ""
    )

    lineage_matches = bool(
        rooms.rooms
        and published is not None
        and all(
            room.document_id == published.revision.document_id
            and room.revision_id == published.revision.revision_id
            and room.source_sha256.lower() == published.revision.source_sha256.lower()
            and room.snapshot_id == published.snapshot.snapshot_id
            for room in rooms.rooms
        )
    )

    area_result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish() if lineage_matches else None

    floor_result = CrossViewFloorFinishProducer.from_source(
        source=source,
        room_areas=area_result,
        floors=floors,
    ).publish() if area_result is not None else None

    finish_result = CrossViewCeilingFinishProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish() if lineage_matches else None

    relationship = (
        _ceiling_relationship_audit(source, rooms, finish_result)
        if finish_result is not None
        else {
            "room_bindings": {},
            "first_failure": "diagnostic_source_lineage_mismatch",
        }
    )

    seal = None
    firm_ceiling_quantities = tuple(
        q for q in claim.ceiling_lining_quantity_evidence
        if not q.abstained and q.value is not None
    )
    if firm_ceiling_quantities:
        seal = seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id=PROJECT,
        )
    sealed_ids = set()
    if seal is not None:
        sealed_ids = {row.quantity_id for row in seal.quantities}

    floor_by_room = {
        floor.room_entity_id: floor for floor in claim.canonical_floors
    }
    floor_qty_by_id = {
        str(q.metadata.get("canonical_floor_id") or ""): q
        for q in claim.floor_finish_quantity_evidence
        if not q.abstained and q.value is not None
    }
    ceiling_qty_by_room = {
        str(q.metadata.get("physical_room_id") or ""): q
        for q in firm_ceiling_quantities
        if str(q.metadata.get("physical_room_id") or "")
    }
    area_by_room = (
        {record.physical_room_id: record for record in area_result.records}
        if area_result is not None else {}
    )
    finish_by_room = (
        finish_result.records_by_physical_room_id
        if finish_result is not None else {}
    )

    stage_rows = []
    for room in sorted(
        claim.canonical_rooms,
        key=lambda r: (_clean(r.room_label), r.canonical_room_id),
    ):
        floor = floor_by_room.get(room.canonical_room_id)
        area_record = area_by_room.get(room.physical_room_id)
        floor_quantity = (
            None if floor is None
            else floor_qty_by_id.get(floor.canonical_floor_id)
        )
        ceiling_finish = finish_by_room.get(room.physical_room_id)
        ceiling_quantity = ceiling_qty_by_room.get(room.physical_room_id)
        sealed = (
            ceiling_quantity is not None
            and ceiling_quantity.quantity_id in sealed_ids
        )

        canonical = True
        area_ok = bool(
            floor is not None
            and floor.metric_geometry_complete
            and floor.metric_area_m2 is not None
        )
        floor_ok = floor is not None
        floor_finish_ok = bool(
            floor is not None and _clean(floor.finish_descriptor)
        )
        ceiling_finish_ok = ceiling_finish is not None
        ceiling_qty_ok = ceiling_quantity is not None

        if not floor_ok:
            first_failure = "pb_live_canonical_floor_surface.compose_live_canonical_floor_surfaces"
        elif not area_ok:
            first_failure = "pb_cross_view_room_area_authority.CrossViewRoomAreaProducer.publish"
        elif not floor_finish_ok:
            if relationship.get("material_definition_record_count", 0) == 0:
                first_failure = "pb_source_material_semantic_authority.SourceMaterialSemanticProducer.publish.definition_authority"
            else:
                first_failure = "pb_cross_view_floor_finish_authority.CrossViewFloorFinishProducer.publish"
        elif not ceiling_finish_ok:
            first_failure = relationship.get("room_bindings", {}).get(
                room.physical_room_id, {}
            ).get(
                "first_failing_gate",
                "pb_cross_view_ceiling_finish_authority.CrossViewCeilingFinishProducer.publish",
            )
        elif not ceiling_qty_ok:
            first_failure = "pb_cross_view_ceiling_quantity_authority.publish_cross_view_ceiling_quantities"
        elif not sealed:
            first_failure = "pb_live_ceiling_lining_source_closed_export.seal_live_ceiling_lining_run"
        else:
            first_failure = None

        stage_rows.append({
            "room": room.room_label,
            "physical_room_id": room.physical_room_id,
            "canonical_room_id": room.canonical_room_id,
            "canonical": canonical,
            "area": {
                "resolved": area_ok,
                "metric_area_m2": None if floor is None else floor.metric_area_m2,
                "cross_view_area_record": area_record is not None,
            },
            "floor": {
                "resolved": floor_ok,
                "canonical_floor_id": None if floor is None else floor.canonical_floor_id,
            },
            "floor_finish": {
                "resolved": floor_finish_ok,
                "finish_descriptor": None if floor is None else floor.finish_descriptor,
                "quantity_id": None if floor_quantity is None else floor_quantity.quantity_id,
            },
            "ceiling_finish": {
                "resolved": ceiling_finish_ok,
                "code": None if ceiling_finish is None else ceiling_finish.finish_code,
                "semantic_finish": None if ceiling_finish is None else ceiling_finish.semantic_finish,
            },
            "ceiling_quantity": {
                "resolved": ceiling_qty_ok,
                "quantity_id": None if ceiling_quantity is None else ceiling_quantity.quantity_id,
                "value_m2": None if ceiling_quantity is None else ceiling_quantity.value,
            },
            "sealed": sealed,
            "first_failure": first_failure,
        })

    print(json.dumps({
        "source_sha256": sha,
        "topology_pages_zero_based": list(topology),
        "support_pages_zero_based": list(support),
        "page_count": page_count,
        "diagnostic_source_lineage_matches_claim": lineage_matches,
        "claim": {
            "canonical_room_count": len(claim.canonical_rooms),
            "canonical_floor_count": len(claim.canonical_floors),
            "firm_room_area_quantity_count": sum(
                1 for q in claim.room_area_quantity_evidence
                if not q.abstained and q.value is not None
            ),
            "firm_floor_finish_quantity_count": sum(
                1 for q in claim.floor_finish_quantity_evidence
                if not q.abstained and q.value is not None
            ),
            "firm_ceiling_quantity_count": len(firm_ceiling_quantities),
            "sealed_ceiling_quantity_count": len(sealed_ids),
        },
        "cross_view_area": None if area_result is None else {
            "status": _status(area_result.status),
            "reason_codes": list(area_result.reason_codes),
            "record_count": len(area_result.records),
            "unresolved_physical_room_ids": list(area_result.unresolved_physical_room_ids),
            "records": [
                {
                    "physical_room_id": row.physical_room_id,
                    "room_label": row.room_label,
                    "source_dimension_page_id": row.source_dimension_page_id,
                    "source_label_observation_ids": list(row.source_label_observation_ids),
                    "source_label_receipt_ids": list(row.source_label_receipt_ids),
                    "horizontal_dimension_id": row.horizontal_dimension_id,
                    "vertical_dimension_id": row.vertical_dimension_id,
                    "area_m2": row.area_evidence.normalized_value,
                }
                for row in area_result.records
            ],
        },
        "cross_view_floor_finish": None if floor_result is None else {
            "status": _status(floor_result.status),
            "reason_codes": list(floor_result.reason_codes),
            "record_count": len(floor_result.records),
            "unresolved_canonical_floor_ids": list(floor_result.unresolved_canonical_floor_ids),
        },
        "cross_view_ceiling_finish": None if finish_result is None else {
            "status": _status(finish_result.status),
            "reason_codes": list(finish_result.reason_codes),
            "record_count": len(finish_result.records),
            "unresolved_physical_room_ids": list(finish_result.unresolved_physical_room_ids),
        },
        "ceiling_relationship_audit": relationship,
        "stage_rows": stage_rows,
        "sealed_run": None if seal is None else seal.to_dict(),
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
