from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_source_material_semantic_authority import SourceMaterialSemanticProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_page_viewports

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _status(value):
    return str(getattr(value, "value", value))


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    with fitz.open(str(PDF)) as doc:
        page_ids = tuple(str(i + 1) for i in range(doc.page_count))
        viewport_rows = []
        for i in range(doc.page_count):
            rows = []
            for vp in segment_page_viewports(doc[i], page_number=i + 1):
                rows.append({
                    "view_id": vp.view_id,
                    "view_type": vp.view_type,
                    "status": vp.status,
                    "label": vp.label,
                    "bbox": None if vp.bounding_box is None else list(vp.bounding_box),
                })
            viewport_rows.append({
                "page_number": i + 1,
                "viewports": rows,
            })

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_material_semantic_dropout",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-material-semantic-dropout",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=page_ids,
    )
    producer = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    producer.publish(published.revision.revision_id)

    definitions = []
    for key, result in sorted(producer._definition_results.items()):
        record = result.record
        definitions.append({
            "key": list(key),
            "status": _status(result.status),
            "reason_codes": list(result.reason_codes),
            "record": None if record is None else {
                "record_id": record.record_id,
                "code": record.code,
                "description": record.description,
                "substrate": record.substrate,
                "finish": record.finish,
                "semantic_finish": record.semantic_finish,
                "source_page_ids": list(record.source_page_ids),
                "source_viewport_ids": list(record.source_viewport_ids),
            },
        })

    scopes = []
    for key, result in sorted(producer._occurrence_results.items()):
        scopes.append({
            "key": list(key),
            "status": _status(result.status),
            "reason_codes": list(result.reason_codes),
            "scope_complete": bool(result.scope_complete),
            "record_count": len(result.records),
            "records": [
                {
                    "record_id": r.record_id,
                    "page_id": r.page_id,
                    "viewport_id": r.viewport_id,
                    "code": r.code,
                    "semantic_finish": r.semantic_finish,
                    "raw_text": r.raw_text,
                    "bbox_pdf_pts": list(r.bbox_pdf_pts),
                }
                for r in result.records
            ],
        })

    payload = {
        "source_sha256": source_sha,
        "definition_result_count": len(definitions),
        "definition_record_count": sum(1 for row in definitions if row["record"] is not None),
        "occurrence_scope_count": len(scopes),
        "occurrence_record_count": sum(row["record_count"] for row in scopes),
        "definitions": definitions,
        "occurrence_scopes": scopes,
        "page_viewports": viewport_rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
