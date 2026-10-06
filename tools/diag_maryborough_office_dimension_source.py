from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import fitz

from pb_figured_dimension_evidence import extract_dimension_evidence_bundle
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "11"
TARGET_RAW = {"3570", "2536"}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    payload = SOURCE.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()

    source = SourceVisibilityProducer(
        producer_method="gpt2-office-dimension-source-diag",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(int(PAGE_ID) - 1)
        words = list(page.get_text("words") or ())
        bundle = extract_dimension_evidence_bundle(
            page,
            page_num=int(PAGE_ID),
        )
    finally:
        pdf.close()

    native_hits = []
    block_lines: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for index, word in enumerate(words):
        if len(word) < 8:
            continue
        row = {
            "word_index": index,
            "text": str(word[4]),
            "bbox": [float(word[0]), float(word[1]), float(word[2]), float(word[3])],
            "block_no": int(word[5]),
            "line_no": int(word[6]),
            "word_no": int(word[7]),
        }
        block_lines[(row["block_no"], row["line_no"])].append(row)
        if _norm(row["text"]) in TARGET_RAW:
            native_hits.append(row)

    text_authority = source.text_integrity_authority()
    integrity_hits = []
    for observation_id in current.text_observation_ids:
        result = text_authority.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if receipt is None or str(receipt.page_id) != PAGE_ID:
            continue
        if _norm(receipt.raw_text) not in TARGET_RAW:
            continue
        integrity_hits.append(
            {
                "observation_id": observation_id,
                "raw_text": receipt.raw_text,
                "geometry": list(receipt.geometry or ()),
                "status": getattr(result.status, "value", str(result.status)),
                "reason_codes": list(result.reason_codes),
                "trusted_text": result.trusted_text,
                "block_no": receipt.block_no,
                "line_no": receipt.line_no,
                "word_no": receipt.word_no,
            }
        )

    binding_by_id = {binding.dimension_id: binding for binding in bundle.bindings}
    dimension_hits = []
    for observation in bundle.observations:
        if _norm(observation.raw_text) not in TARGET_RAW:
            continue
        binding = binding_by_id.get(observation.dimension_id)
        dimension_hits.append(
            {
                "dimension_id": observation.dimension_id,
                "raw_text": observation.raw_text,
                "value": observation.value,
                "unit": observation.unit,
                "orientation": observation.orientation,
                "bbox": list(observation.bbox or ()),
                "endpoints": None
                if observation.endpoints is None
                else [list(observation.endpoints[0]), list(observation.endpoints[1])],
                "witness_targets": list(observation.witness_targets or ()),
                "extraction_method": observation.extraction_method,
                "binding_status": None if binding is None else binding.status,
                "binding_notes": [] if binding is None else list(binding.notes),
                "dimension_line_id": None if binding is None else binding.dimension_line_id,
                "witness_line_ids": [] if binding is None else list(binding.witness_line_ids),
            }
        )

    office_context = []
    for key, rows in sorted(block_lines.items()):
        line_text = _norm(" ".join(
            row["text"] for row in sorted(rows, key=lambda item: item["word_no"])
        ))
        if "OFFICE" in line_text or any(_norm(row["text"]) in TARGET_RAW for row in rows):
            office_context.append(
                {
                    "block_no": key[0],
                    "line_no": key[1],
                    "line_text": line_text,
                    "words": rows,
                }
            )

    print(json.dumps({
        "source_sha256": sha,
        "page_id": PAGE_ID,
        "mode": "DIAGNOSTIC_ONLY_OFFICE_DIMENSION_SOURCE_TRACE",
        "native_word_hits": native_hits,
        "text_integrity_hits": integrity_hits,
        "dimension_bundle_hits": dimension_hits,
        "office_and_target_line_context": office_context,
        "bundle_observation_count": len(bundle.observations),
        "bundle_binding_count": len(bundle.bindings),
        "bundle_witness_bound_count": sum(
            1 for binding in bundle.bindings
            if str(binding.status) == "witness_bound"
        ),
    }, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
