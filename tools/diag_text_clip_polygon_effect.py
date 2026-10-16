"""Read-only: what would the clip shadow change for the final trust verdict of each native word of a PDF's pages?

``PdfTextIntegrityAuthority`` blocks a word with ``text_clip_state_unresolved`` on every rotated page and wherever the clip that may apply is
a polygon of straight segments. ``pb_text_clip_polygon_shadow`` answers only the clip question for those words. This tool ingests the pages with
the same producer the live chain uses, records the shadow clip verdict of every word during that ingestion (the authority's own result is
returned untouched), and reports per page how many words are trusted today, how many would be trusted if the clip reason alone were lifted by
a proven ``unclipped_proven`` verdict, and which reasons keep every other word blocked. It decides nothing, changes nothing and grants nothing:
no word text, geometry or file name is written, only counts and the SHA-256 of the input.

usage: python -m tools.diag_text_clip_polygon_effect --pdf FILE --pages 3,7 [--json OUT.json]
"""
from __future__ import annotations

import argparse
from collections import Counter
import contextlib
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterator, List, Sequence

import fitz

import pb_pdf_text_integrity_authority as authority
import pb_text_clip_polygon_shadow as shadow
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"


def _key(text: object, bbox: Sequence[object]) -> tuple:
    return (str(text), tuple(round(float(v), 3) for v in tuple(bbox)[:4]))


@contextlib.contextmanager
def recording_shadow_verdicts(store: Dict[tuple, str]) -> Iterator[None]:
    """While active, every clip decision the authority makes also records the shadow verdict of the same word; the authority's result is unchanged."""
    original = authority._text_clip_reasons

    def recording(page, subject_bbox, seqno, *, native_word=None):
        real = original(page, subject_bbox, seqno, native_word=native_word)
        if native_word:
            verdict = shadow.text_clip_verdict(page, subject_bbox, seqno, native_word=native_word)
            store[_key(native_word.get("text"), native_word.get("bbox") or subject_bbox)] = verdict.verdict
        return real

    authority._text_clip_reasons = recording
    try:
        yield
    finally:
        authority._text_clip_reasons = original


def effect(payload: bytes, pages: Sequence[int]) -> List[dict]:
    document = fitz.open(stream=payload, filetype="pdf")
    rows: List[dict] = []
    for number in pages:
        if not 1 <= number <= document.page_count:
            raise ValueError(f"page {number} is outside 1..{document.page_count}")
        verdicts: Dict[tuple, str] = {}
        producer = SourceVisibilityProducer(producer_method="text-clip-polygon-effect",
                                            producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
        with recording_shadow_verdicts(verdicts):
            published = producer.ingest_native_pdf_bytes(document_id="clip-effect", source_bytes=payload,
                                                         source_locator="memory://clip-effect.pdf", page_ids=(str(number),))
        text_authority = producer.text_integrity_authority()
        trusted = newly = unmatched = 0
        blocked: Counter = Counter()
        shadow_counts: Counter = Counter()
        words = 0
        for observation_id in published.text_observation_ids:
            selector = ObservationSelector(document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                                           source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                                           observation_id=observation_id)
            receipt = text_authority.resolve_text(selector).receipt
            words += 1
            if receipt is None:
                blocked["no_receipt"] += 1
                continue
            if receipt.trusted:
                trusted += 1
                continue
            verdict = verdicts.get(_key(receipt.raw_text, receipt.geometry))
            shadow_counts[verdict or "not_recorded"] += 1
            if verdict is None:
                unmatched += 1
            lifted = verdict == shadow.UNCLIPPED
            remaining = tuple(r for r in receipt.reason_codes if not (r == authority.TEXT_CLIP_STATE_UNRESOLVED and lifted))
            if not remaining:
                newly += 1
            else:
                blocked["+".join(remaining)] += 1
        rows.append({
            "page": number,
            "rotation": int(document[number - 1].rotation),
            "words": words,
            "trusted_now": trusted,
            "newly_trusted_by_clip_proof_alone": newly,
            "trusted_if_clip_proof_adopted": trusted + newly,
            "shadow_clip_verdicts_of_blocked_words": dict(sorted(shadow_counts.items())),
            "still_blocked_after_clip_reason_lifted": dict(sorted(blocked.items(), key=lambda kv: (-kv[1], kv[0]))),
            "words_without_a_recorded_shadow_verdict": unmatched,
        })
    return rows


def report(payload: bytes, pages: Sequence[int]) -> dict:
    return {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "shadow_only": True,
        "live_effect": False,
        "text_trust_granted": False,
        "clip_shadow_schema_version": shadow.TEXT_CLIP_SHADOW_SCHEMA_VERSION,
        "pdf_sha256": hashlib.sha256(payload).hexdigest(),
        "pages": effect(payload, pages),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--pages", required=True, help="comma separated 1-based page numbers")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    pages = [int(p) for p in args.pages.split(",") if p.strip()]
    result = report(args.pdf.read_bytes(), pages)
    for row in result["pages"]:
        print(f"page {row['page']} (rotation {row['rotation']}): words {row['words']}, trusted now {row['trusted_now']}, "
              f"newly trusted by the clip proof alone {row['newly_trusted_by_clip_proof_alone']}")
        for reasons, count in row["still_blocked_after_clip_reason_lifted"].items():
            print(f"    still blocked {count:6d}  {reasons}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
