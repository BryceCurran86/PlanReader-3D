from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_cross_view_floor_finish_authority import _definition_is_floor_finish
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionSelector,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    with fitz.open(str(PDF)) as doc:
        page_ids = tuple(str(i + 1) for i in range(doc.page_count))

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_floor_finish_semantics",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-floor-finish-semantics",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=page_ids,
    )
    producer = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    authority = producer.publish(published.revision.revision_id)

    rows = []
    all_occurrence_count = 0
    page3_occurrence_count = 0
    for result in producer.published_occurrence_results():
        all_occurrence_count += len(result.records)
        for occurrence in result.records:
            if str(occurrence.page_id) != PAGE_ID:
                continue
            page3_occurrence_count += 1
            definition_result = authority.resolve_definition(
                SourceMaterialDefinitionSelector(
                    document_id=occurrence.document_id,
                    revision_id=occurrence.revision_id,
                    source_sha256=occurrence.source_sha256,
                    snapshot_id=occurrence.snapshot_id,
                    code=occurrence.code,
                )
            )
            definition = definition_result.record
            rows.append({
                "code": occurrence.code,
                "raw_text": occurrence.raw_text,
                "semantic_finish": occurrence.semantic_finish,
                "bbox_pdf_pts": list(occurrence.bbox_pdf_pts),
                "occurrence_record_id": occurrence.record_id,
                "occurrence_evidence_id": occurrence.source_evidence_id,
                "definition_status": str(getattr(definition_result.status, "value", definition_result.status)),
                "definition_record_id": None if definition is None else definition.record_id,
                "description": None if definition is None else definition.description,
                "substrate": None if definition is None else definition.substrate,
                "finish": None if definition is None else definition.finish,
                "definition_semantic_finish": None if definition is None else definition.semantic_finish,
                "is_floor_finish": False if definition is None else _definition_is_floor_finish(definition),
            })

    print(json.dumps({
        "source_sha256": source_sha,
        "decoded_page_count": len(page_ids),
        "all_occurrence_count": all_occurrence_count,
        "page3_occurrence_count": page3_occurrence_count,
        "page3_floor_finish_occurrences": [row for row in rows if row["is_floor_finish"]],
        "page3_all_occurrences": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
