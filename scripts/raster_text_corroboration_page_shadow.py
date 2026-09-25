"""Real-source shadow: raster corroboration of one page's native words.

Diagnostic only. Ingests one page of a PDF through the production
``SourceVisibilityProducer``, then asks the production
``RasterTextCorroborationProducer`` (exact RapidOCR backend) to corroborate every
native word. No benchmark quantity, expected BOQ value, live extractor or
commercial output is read or changed, and nothing here is wired into Item 19B.

usage: raster_text_corroboration_page_shadow.py <pdf> <1-based page> [--limit N] [--out FILE]
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import re
import sys
import time

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_raster_text_corroboration_authority import (  # noqa: E402
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_observation_authority import ObservationSelector  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402

_FINISH = re.compile(r"plaster|paint|key to|finish|redoxide|screed", re.IGNORECASE)


def run(pdf_path: Path, page_number: int, limit: int | None) -> dict[str, object]:
    payload = pdf_path.read_bytes()
    svp = SourceVisibilityProducer(producer_method="raster-text-shadow", producer_version="1")
    published = svp.ingest_native_pdf_bytes(
        document_id="shadow-doc",
        source_bytes=payload,
        source_locator=f"file://{pdf_path.name}",
        page_ids=[str(page_number)],
    )
    text_authority = svp.text_integrity_authority()
    producer = RasterTextCorroborationProducer.from_source_visibility_producer(svp)

    def observation_selector(oid: str) -> ObservationSelector:
        return ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )

    integrity_reasons: collections.Counter[str] = collections.Counter()
    outcome_reasons: collections.Counter[str] = collections.Counter()
    words: list[dict[str, object]] = []
    trusted_natively = glyph_only = corroborated = 0
    started = time.time()
    oids = list(published.text_observation_ids)
    if limit:
        oids = oids[:limit]
    for oid in oids:
        integrity = text_authority.resolve_text(observation_selector(oid))
        receipt = integrity.receipt
        if receipt is None:
            continue
        integrity_reasons.update(receipt.reason_codes)
        record: dict[str, object] = {
            "text": receipt.raw_text,
            "bbox": [round(v, 2) for v in receipt.geometry],
            "integrity_reasons": list(receipt.reason_codes),
        }
        if receipt.trusted:
            trusted_natively += 1
            record["outcome"] = "already_trusted"
        elif tuple(receipt.reason_codes) == ("text_glyph_mapping_unverified",):
            glyph_only += 1
            result = producer.publish(
                RasterTextCorroborationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=oid,
                )
            )
            outcome_reasons.update(result.reason_codes)
            record["outcome"] = result.status.value
            record["reasons"] = list(result.reason_codes)
            if result.record is not None:
                corroborated += 1
                record["readings"] = [v.ocr_reading for v in result.record.views]
                record["confidence"] = [v.ocr_confidence for v in result.record.views]
            else:
                # Diagnostic only: what did each view read, if the producer got that far?
                record["note"] = "no record"
        else:
            record["outcome"] = "not_glyph_only"
        words.append(record)

    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]
    finish_blocks = []
    by_text_bbox = {(w["text"], tuple(w["bbox"])): w for w in words}
    for block in page.get_text("blocks"):
        if not _FINISH.search(block[4]):
            continue
        bx0, by0, bx1, by1 = block[:4]
        members = [
            w
            for w in page.get_text("words")
            if bx0 - 0.5 <= w[0] and w[2] <= bx1 + 0.5 and by0 - 0.5 <= w[1] and w[3] <= by1 + 0.5
        ]
        states = collections.Counter()
        for w in members:
            key = (w[4], tuple(round(v, 2) for v in (w[0], w[1], w[2], w[3])))
            rec = next(
                (r for r in words if r["text"] == w[4] and all(abs(a - b) < 0.05 for a, b in zip(r["bbox"], key[1]))),
                None,
            )
            states["missing" if rec is None else str(rec["outcome"])] += 1
        finish_blocks.append(
            {
                "text": " ".join(block[4].split())[:70],
                "words": len(members),
                "outcomes": dict(states),
            }
        )
    return {
        "page": page_number,
        "words_examined": len(words),
        "already_trusted": trusted_natively,
        "glyph_mapping_unverified_only": glyph_only,
        "corroborated": corroborated,
        "integrity_reason_counts": dict(integrity_reasons),
        "raster_outcome_reason_counts": dict(outcome_reasons),
        "finish_blocks": finish_blocks,
        "seconds": round(time.time() - started, 1),
        "words": words,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("page", type=int)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    summary = run(Path(args.pdf), args.page, args.limit)
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    brief = {k: v for k, v in summary.items() if k != "words"}
    print(json.dumps(brief, indent=2, sort_keys=True))
