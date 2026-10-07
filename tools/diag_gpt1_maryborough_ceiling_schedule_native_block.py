from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    payload = PDF.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt1-ceiling-schedule-native-block",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag:{hashlib.sha256(payload).hexdigest()[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
    )
    authority = source.text_integrity_authority()

    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for observation_id in published.text_observation_ids:
        result = authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if (
            receipt is None
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        groups[
            (
                str(receipt.page_id),
                str(receipt.source_partition_id),
                int(receipt.block_no),
            )
        ].append(
            {
                "observation_id": str(observation_id),
                "receipt_id": str(receipt.receipt_id),
                "line_no": int(receipt.line_no),
                "word_no": int(receipt.word_no),
                "raw_text": str(receipt.raw_text or ""),
                "trusted_text": (
                    str(result.trusted_text)
                    if (
                        result.status is EvidenceResolutionStatus.CORROBORATED
                        and result.trusted_text is not None
                    )
                    else None
                ),
                "status": getattr(result.status, "value", str(result.status)),
                "reason_codes": list(result.reason_codes or ()),
                "bbox": [float(value) for value in receipt.geometry],
            }
        )

    block_rows = []
    title_blocks = []
    code_blocks = []
    for (page_id, partition_id, block_no), words in sorted(groups.items()):
        by_line: dict[int, list[dict]] = defaultdict(list)
        for word in words:
            by_line[word["line_no"]].append(word)
        lines = []
        for line_no, line_words in sorted(by_line.items()):
            ordered = sorted(
                line_words,
                key=lambda item: (item["word_no"], item["bbox"][0]),
            )
            raw = " ".join(
                item["raw_text"].strip()
                for item in ordered
                if item["raw_text"].strip()
            )
            trusted = (
                " ".join(item["trusted_text"].strip() for item in ordered)
                if all(item["trusted_text"] for item in ordered)
                else None
            )
            lines.append(
                {
                    "line_no": line_no,
                    "raw_text": raw,
                    "trusted_text": trusted,
                    "word_count": len(ordered),
                    "all_words_trusted": all(
                        item["status"] == "corroborated"
                        for item in ordered
                    ),
                    "observation_ids": [
                        item["observation_id"] for item in ordered
                    ],
                    "receipt_ids": [
                        item["receipt_id"] for item in ordered
                    ],
                    "bbox": [
                        min(item["bbox"][0] for item in ordered),
                        min(item["bbox"][1] for item in ordered),
                        max(item["bbox"][2] for item in ordered),
                        max(item["bbox"][3] for item in ordered),
                    ],
                    "reason_codes": sorted(
                        {
                            reason
                            for item in ordered
                            for reason in item["reason_codes"]
                        }
                    ),
                }
            )
        joined = _norm(" ".join(line["raw_text"] for line in lines))
        block = {
            "page_id": page_id,
            "source_partition_id": partition_id,
            "block_no": block_no,
            "lines": lines,
        }
        if "CEILING" in joined and "FINISH" in joined and "SCHEDULE" in joined:
            title_blocks.append(block)
        if any(
            token in joined.split()
            for token in ("FPB", "WFPB", "GRID")
        ):
            code_blocks.append(block)

    print(
        json.dumps(
            {
                "source_sha256": published.revision.source_sha256,
                "revision_id": published.revision.revision_id,
                "title_block_count": len(title_blocks),
                "title_blocks": title_blocks,
                "ceiling_code_block_count": len(code_blocks),
                "ceiling_code_blocks": code_blocks,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
