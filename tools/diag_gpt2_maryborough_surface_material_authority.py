from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import fitz

import pb_source_material_semantic_authority as material
from pb_drawing_evidence_binding import DrawingViewType
from pb_material_schedule_v1222 import (
    parse_schedule_text,
    semantic_finish_from_schedule_entry,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
EXPECTED_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
TOKENS = ("FPB", "WFPB", "GRID")
TOKEN_RE = re.compile(r"(?<![A-Z0-9])(?:FPB|WFPB|GRID)(?![A-Z0-9])", re.I)


def _status(value) -> str:
    return getattr(value, "value", str(value))


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _receipt_payload(source, published, observation_ids):
    authority = source.text_integrity_authority()
    rows = []
    for observation_id in observation_ids:
        result = authority.resolve_text(_selector(published, observation_id))
        receipt = result.receipt
        rows.append({
            "observation_id": observation_id,
            "status": _status(result.status),
            "trusted_text": result.trusted_text,
            "reason_codes": list(result.reason_codes or ()),
            "receipt_id": None if receipt is None else str(receipt.receipt_id),
            "page_id": None if receipt is None else str(receipt.page_id),
            "source_partition_id": None if receipt is None else str(receipt.source_partition_id),
            "block_no": None if receipt is None else receipt.block_no,
            "line_no": None if receipt is None else receipt.line_no,
            "word_no": None if receipt is None else receipt.word_no,
            "raw_text": None if receipt is None else str(receipt.raw_text or ""),
            "bbox": None if receipt is None else [float(v) for v in receipt.geometry],
        })
    return rows


def _raw_candidate_blocks(words):
    grouped = defaultdict(list)
    for word in words:
        grouped[(word.source_partition_id, int(word.block_no))].append(word)
    out = []
    for (partition_id, block_no), block_words in sorted(grouped.items()):
        by_line = defaultdict(list)
        for word in block_words:
            by_line[int(word.line_no)].append(word)
        lines = []
        for line_no, line_words in sorted(by_line.items()):
            ordered = sorted(line_words, key=lambda r: (r.word_no, r.bbox[0], r.observation_id))
            text = " ".join(w.text.strip() for w in ordered if w.text.strip()).strip()
            if not text:
                continue
            lines.append({
                "line_no": line_no,
                "text": text,
                "trusted": all(w.trusted for w in ordered),
                "reason_codes": sorted({r for w in ordered for r in w.reason_codes}),
                "observation_ids": [w.observation_id for w in ordered],
            })
        joined = " ".join(row["text"] for row in lines).upper()
        if (
            ("FINISH" in joined and "SCHEDULE" in joined)
            or TOKEN_RE.search(joined)
        ):
            out.append({
                "page_id": block_words[0].page_id if block_words else None,
                "source_partition_id": partition_id,
                "block_no": block_no,
                "all_words_trusted": all(w.trusted for w in block_words),
                "lines": lines,
            })
    return out


def main() -> int:
    payload = PDF.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-surface-authority-support",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
    )

    words_by_page = material._trusted_words_by_page(source, published)

    # Independent native-block schedule ownership, before the material publisher.
    native_blocks = []
    raw_candidate_blocks = []
    for page_id in sorted(words_by_page, key=lambda x: int(x)):
        page_words = words_by_page[page_id]
        raw_candidate_blocks.extend(_raw_candidate_blocks(page_words))
        for block in material._trusted_native_material_schedule_blocks(page_words):
            parsed = []
            for item in parse_schedule_text(
                block.text,
                page_id=int(page_id),
                page_label=f"page:{page_id}",
            ):
                entry = {
                    "status": "Confirmed",
                    "code": str(item.get("code") or ""),
                    "description": str(item.get("description") or ""),
                    "substrate": str(item.get("substrate") or ""),
                    "finish": str(item.get("finish") or ""),
                }
                parsed.append({
                    **item,
                    "semantic_finish": semantic_finish_from_schedule_entry(entry),
                })
            native_blocks.append({
                "page_id": block.page_id,
                "source_partition_id": block.source_partition_id,
                "block_no": block.block_no,
                "scope_id": block.scope_id,
                "text": block.text,
                "line_evidence": {k: list(v) for k, v in block.line_evidence.items()},
                "parsed_rows": parsed,
            })

    producer = material.SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    authority = producer.publish(published.revision.revision_id)

    definitions = []
    for key, result in sorted(producer._definition_results.items()):
        record = result.record
        definitions.append({
            "selector_key": list(key),
            "status": _status(result.status),
            "reason_codes": list(result.reason_codes),
            "code": None if record is None else record.code,
            "description": None if record is None else record.description,
            "semantic_finish": None if record is None else record.semantic_finish,
            "source_page_ids": [] if record is None else list(record.source_page_ids),
            "source_viewport_ids": [] if record is None else list(record.source_viewport_ids),
            "source_definition_ids": [] if record is None else list(record.source_definition_ids),
        })

    occurrence_scopes = []
    occurrence_lookup = defaultdict(list)
    for result in producer.published_occurrence_results():
        scope = {
            "status": _status(result.status),
            "scope_complete": bool(result.scope_complete),
            "reason_codes": list(result.reason_codes),
            "records": [],
        }
        for record in result.records:
            receipt_rows = _receipt_payload(
                source,
                published,
                tuple(record.source_text_observation_ids or ()),
            )
            row = {
                "record_id": record.record_id,
                "page_id": record.page_id,
                "viewport_id": record.viewport_id,
                "code": record.code,
                "semantic_finish": record.semantic_finish,
                "definition_record_id": record.definition_record_id,
                "bbox": list(record.bbox_pdf_pts),
                "raw_text": record.raw_text,
                "source_evidence_id": record.source_evidence_id,
                "source_text_observation_ids": list(record.source_text_observation_ids),
                "source_receipts": receipt_rows,
            }
            scope["records"].append(row)
            occurrence_lookup[(record.page_id, record.viewport_id, record.code.upper())].append(row)
        occurrence_scopes.append(scope)

    # RCP exact trusted/raw line census. Tokens are reported as source text only;
    # no semantic meaning is assigned here.
    rcp_lines = []
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        for page_number in sorted(int(v) for v in published.coverage.decoded_pages):
            page = pdf.load_page(page_number - 1)
            viewports = tuple(segment_page_viewports(page, page_number=page_number))
            if not viewports:
                continue
            siblings_ok = validate_non_overlapping_viewports(viewports)
            page_words = words_by_page.get(str(page_number), ())
            for viewport in viewports:
                if (
                    viewport.view_type != DrawingViewType.REFLECTED_CEILING_PLAN.value
                    or not material._viewport_is_authoritative(
                        viewport,
                        sibling_non_overlapping=siblings_ok,
                    )
                    or viewport.bounding_box is None
                ):
                    continue
                scoped = material._recover_admissible_viewport_words(
                    source=source,
                    published=published,
                    raster=producer._raster,
                    words=page_words,
                    viewport=viewport,
                )
                scoped = material._recover_admissible_viewport_lines(
                    source=source,
                    published=published,
                    raster=producer._raster,
                    words=scoped,
                    viewport=viewport,
                )
                lines, complete, reasons = material._trusted_lines_for_viewport(scoped, viewport)
                for text, bbox, observation_ids in lines:
                    matched = sorted({m.group(0).upper() for m in TOKEN_RE.finditer(text)})
                    if not matched:
                        continue
                    receipts = _receipt_payload(source, published, observation_ids)
                    block_keys = sorted({
                        (
                            row["source_partition_id"],
                            row["block_no"],
                            row["line_no"],
                        )
                        for row in receipts
                        if row["source_partition_id"] is not None
                    })
                    for code in matched:
                        definition = authority.resolve_definition(
                            material.SourceMaterialDefinitionSelector(
                                document_id=published.revision.document_id,
                                revision_id=published.revision.revision_id,
                                source_sha256=published.revision.source_sha256,
                                snapshot_id=published.snapshot.snapshot_id,
                                code=code,
                            )
                        )
                        published_rows = occurrence_lookup.get(
                            (str(page_number), viewport.view_id, code),
                            (),
                        )
                        if definition.record is None:
                            first_failure = {
                                "gate": "SourceMaterialSemanticProducer.publish.definition",
                                "reason_codes": list(definition.reason_codes),
                            }
                        elif not complete:
                            first_failure = {
                                "gate": "SourceMaterialSemanticProducer.publish.rcp_viewport_text_complete",
                                "reason_codes": list(reasons),
                            }
                        elif not published_rows:
                            first_failure = {
                                "gate": "SourceMaterialSemanticProducer.publish.occurrence_scan",
                                "reason_codes": ["authenticated_definition_exists_but_occurrence_not_published"],
                            }
                        else:
                            first_failure = None
                        rcp_lines.append({
                            "page_id": str(page_number),
                            "viewport_id": viewport.view_id,
                            "viewport_label": viewport.label,
                            "viewport_bbox": list(viewport.bounding_box),
                            "viewport_text_complete": complete,
                            "viewport_text_reason_codes": list(reasons),
                            "code_token": code,
                            "raw_line": text,
                            "bbox": list(bbox),
                            "source_text_observation_ids": list(observation_ids),
                            "source_receipts": receipts,
                            "source_block_keys": [list(v) for v in block_keys],
                            "definition_status": _status(definition.status),
                            "definition_reason_codes": list(definition.reason_codes),
                            "definition_semantic_finish": (
                                None if definition.record is None
                                else definition.record.semantic_finish
                            ),
                            "published_occurrence_count": len(published_rows),
                            "first_failure": first_failure,
                        })
    finally:
        pdf.close()

    blocked_scopes = [
        {
            "status": _status(result.status),
            "scope_complete": bool(result.scope_complete),
            "reason_codes": list(result.reason_codes),
        }
        for result in producer.published_occurrence_results()
        if not result.scope_complete or result.status is not EvidenceResolutionStatus.CORROBORATED
    ]

    print(json.dumps({
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "native_material_schedule_block_count": len(native_blocks),
        "native_material_schedule_blocks": native_blocks,
        "raw_finish_or_code_block_count": len(raw_candidate_blocks),
        "raw_finish_or_code_blocks": raw_candidate_blocks,
        "definition_result_count": len(definitions),
        "definition_record_count": sum(1 for row in definitions if row["code"] is not None),
        "definitions": definitions,
        "occurrence_scope_count": len(occurrence_scopes),
        "occurrence_record_count": sum(len(s["records"]) for s in occurrence_scopes),
        "occurrence_scopes": occurrence_scopes,
        "blocked_scope_count": len(blocked_scopes),
        "blocked_scopes": blocked_scopes,
        "rcp_expected_looking_line_count": len(rcp_lines),
        "rcp_expected_looking_lines": rcp_lines,
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
