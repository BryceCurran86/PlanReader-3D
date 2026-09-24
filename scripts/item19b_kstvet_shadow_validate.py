from __future__ import annotations

from pathlib import Path
import json

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_finish_face_binding_authority import WallFinishFaceBindingProducer

PDF = Path("benchmarks/sources/1727358888238-bq-nd-drawing.pdf")
EXPECTED_SHA = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"


def main() -> None:
    payload = PDF.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="item19b-kstvet-shadow-validation",
        producer_version="1.0",
    )
    published_initial = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-shadow",
        source_bytes=payload,
        source_locator=str(PDF),
    )
    published = source.published_snapshot_for_revision(
        published_initial.revision.revision_id
    )
    assert published is not None
    assert published.revision.source_sha256 == EXPECTED_SHA

    producer = WallFinishFaceBindingProducer.from_source_visibility_producer(
        source,
        page_ids=("54",),
    )
    results = producer.published_results()

    print("LINEAGE", json.dumps({
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
    }, sort_keys=True))

    serial = []
    for result in results:
        item = {
            "status": result.status.value,
            "reason_codes": list(result.reason_codes),
            "scope_records": [
                {
                    "scope_id": scope.scope_id,
                    "trade_scope_id": scope.trade_scope_id,
                    "finish_material": scope.finish_material,
                    "scope_status": scope.scope_status.value,
                    "decision_scope_complete": scope.decision_scope_complete,
                    "target_face_ids": list(scope.target_face_ids),
                    "covered_face_ids": list(scope.covered_face_ids),
                    "binding_ids": list(scope.binding_ids),
                }
                for scope in result.scope_records
            ],
            "bindings": [
                {
                    "binding_id": record.binding_id,
                    "annotation_observation_ids": list(record.annotation_observation_ids),
                    "leader_path_ids": list(record.leader_path_ids),
                    "terminator_primitive_ids": list(record.terminator_primitive_ids),
                    "physical_wall_id": record.physical_wall_id,
                    "physical_face_id": record.physical_face_id,
                    "physical_face_role": record.physical_face_role.value,
                    "source_face_segment_ids": list(record.source_face_segment_ids),
                    "wall_role_record_id": record.wall_role_record_id,
                    "wall_role": record.wall_role.value,
                    "trade_scope_id": record.trade_scope_id,
                    "finish_material": record.finish_material,
                    "binding_status": record.status.value,
                    "scope_complete": record.decision_scope_complete,
                    "source_evidence_kind": record.source_evidence_kind,
                }
                for record in result.bindings
            ],
        }
        serial.append(item)
    print("ITEM19B_RESULTS", json.dumps(serial, sort_keys=True))

    trades = sorted({
        record.trade_scope_id
        for result in results
        for record in result.bindings
    })
    print("ITEM19B_TRADES", json.dumps(trades))


if __name__ == "__main__":
    main()
