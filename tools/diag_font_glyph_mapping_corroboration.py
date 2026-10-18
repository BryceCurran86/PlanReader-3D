"""Read-only: how few corroboration attempts verify every glyph of the fonts the text-integrity authority cannot verify?

``PdfTextIntegrityAuthority`` gives ``text_glyph_mapping_unverified`` to every word set in a font whose embedded program cannot answer "which glyph is
this Unicode?" (CID-keyed CFF subsets, symbolic TrueType subsets). ``pb_raster_text_corroboration_authority`` can corroborate one word at a time. A glyph
looks the same in every word, so words that corroboration has read are evidence about the glyphs in them. This tool ingests pages with the producer the
live chain uses, recovers the (font program, glyph id, character) of every glyph of every glyph-blocked word from the PDF's own text trace, spends corroboration
attempts in the order ``pb_font_glyph_mapping_corroboration_shadow.GlyphMappingLedger`` chooses (the word adding the most still-needed votes first), and reports
how many (font, glyph id) mappings end up verified, how many words are then fully verified, and what the next pages cost once earlier pages have verified the
shared fonts. It decides nothing, changes nothing and grants nothing: counts only, no word text, geometry or file name.

usage: python -m tools.diag_font_glyph_mapping_corroboration --pdf FILE --pages 3,4 [--budget 150] [--min-words 2] [--json OUT.json]
Needs the recogniser used by the corroboration authority; tests inject a stand-in.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from typing import Callable, Dict, List, Optional, Sequence

import fitz

import pb_font_glyph_mapping_corroboration_shadow as shadow
import pb_pdf_text_integrity_authority as authority
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"
_GLYPH_BLOCKERS = frozenset({authority.TEXT_GLYPH_MAPPING_UNVERIFIED, authority.TEXT_CLIP_STATE_UNRESOLVED})

Corroborator = Callable[[str], bool]


def font_program_key(document: "fitz.Document", xref: Optional[int]) -> Optional[str]:
    """Identity of a font's glyph shapes: the hash of its embedded program (None when nothing is embedded)."""
    if xref is None:
        return None
    try:
        extracted = document.extract_font(int(xref))
        program = extracted[3] if extracted and len(extracted) > 3 else b""
    except Exception:
        return None
    return hashlib.sha256(bytes(program)).hexdigest()[:24] if program else None


def raster_corroborator(svp: SourceVisibilityProducer, published) -> Corroborator:
    """The real corroboration (two-view recognition per word); imported lazily so the module loads without the recogniser."""
    from pb_raster_text_corroboration_authority import RasterTextCorroborationProducer, RasterTextCorroborationSelector

    producer = RasterTextCorroborationProducer.from_source_visibility_producer(svp)

    def run(observation_id: str) -> bool:
        result = producer.publish(RasterTextCorroborationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id, observation_id=observation_id))
        return result.status.value == "corroborated"

    return run


def analyse(payload: bytes, pages: Sequence[int], *, min_words: int = shadow.DEFAULT_MIN_WORDS, budget: int = 150,
            corroborator_factory: Callable[[SourceVisibilityProducer, object], Corroborator] = raster_corroborator) -> dict:
    document = fitz.open(stream=payload, filetype="pdf")
    ledger = shadow.GlyphMappingLedger(min_words=min_words)
    rows: List[dict] = []
    fonts: Dict[str, Counter] = {}
    for number in pages:
        if not 1 <= number <= document.page_count:
            raise ValueError(f"page {number} is outside 1..{document.page_count}")
        page = document[number - 1]
        spans_by_seqno: Dict[int, list] = {}
        for span in page.get_texttrace() or ():
            spans_by_seqno.setdefault(span.get("seqno"), []).append(span)
        svp = SourceVisibilityProducer(producer_method="font-glyph-mapping-corroboration",
                                       producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
        published = svp.ingest_native_pdf_bytes(document_id="glyph-map", source_bytes=payload, source_locator="memory://glyph-map.pdf", page_ids=(str(number),))
        text_authority = svp.text_integrity_authority()
        words: List[shadow.WordGlyphs] = []
        total = natively_trusted = blocked_other = glyph_blocked = 0
        for observation_id in published.text_observation_ids:
            selector = ObservationSelector(document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                                           source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                                           observation_id=observation_id)
            receipt = text_authority.resolve_text(selector).receipt
            total += 1
            if receipt is None or receipt.trusted:
                natively_trusted += receipt is not None
                continue
            reasons = set(receipt.reason_codes)
            if authority.TEXT_GLYPH_MAPPING_UNVERIFIED not in reasons or not reasons <= _GLYPH_BLOCKERS:
                blocked_other += 1
                continue
            glyph_blocked += 1
            key = font_program_key(document, receipt.font_xref)
            if key is None:
                continue
            seqnos = tuple(receipt.trace_sequence_numbers) or ((receipt.sequence_number,) if receipt.sequence_number is not None else ())
            spans = [s for q in seqnos for s in spans_by_seqno.get(q, ())]
            recovered = shadow.word_glyphs(observation_id, receipt.raw_text, key, receipt.geometry, spans)
            if recovered is not None:
                words.append(recovered)
                fonts.setdefault(key, Counter())["words"] += 1
        before = shadow.coverage(words, ledger.verification())
        corroborate = corroborator_factory(svp, published)
        attempts_before, corroborated_before = ledger.attempts, ledger.corroborated_count
        started = time.time()
        while ledger.attempts - attempts_before < budget:
            candidate = ledger.next_candidate(words)
            if candidate is None:
                break
            ledger.record(candidate, bool(corroborate(candidate.observation_id)))
        verification = ledger.verification()
        after = shadow.coverage(words, verification)
        rows.append({
            "page": number,
            "rotation": int(page.rotation),
            "words": total,
            "natively_trusted": natively_trusted,
            "blocked_only_by_glyph_mapping_or_clip": glyph_blocked,
            "blocked_by_other_reasons": blocked_other,
            "glyph_blocked_words_with_recovered_glyphs": len(words),
            "distinct_font_glyph_pairs": len({pair for w in words for pair, _c in w.pairs()}),
            "words_fully_verified_before_any_attempt_on_this_page": before[shadow.ALL_GLYPHS_VERIFIED],
            "attempts_on_this_page": ledger.attempts - attempts_before,
            "corroborated_on_this_page": ledger.corroborated_count - corroborated_before,
            "recogniser_seconds_on_this_page": round(time.time() - started, 1),
            "words_fully_verified_after": after[shadow.ALL_GLYPHS_VERIFIED],
            "words_with_an_unverified_glyph_after": after[shadow.GLYPH_NOT_YET_VERIFIED],
            "words_with_a_contradicted_glyph_after": after[shadow.GLYPH_CONTRADICTED],
            "fraction_of_recovered_words_fully_verified_after": round(after[shadow.ALL_GLYPHS_VERIFIED] / len(words), 3) if words else None,
        })
    verification = ledger.verification()
    return {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "shadow_only": True,
        "live_effect": False,
        "text_trust_granted": False,
        "glyph_shadow_schema_version": shadow.GLYPH_MAPPING_SHADOW_SCHEMA_VERSION,
        "pdf_sha256": hashlib.sha256(payload).hexdigest(),
        "min_words": min_words,
        "budget_per_page": budget,
        "verified_font_glyph_pairs": len(verification.verified),
        "contradicted_font_glyph_pairs": len(verification.contradicted),
        "under_supported_font_glyph_pairs": len(verification.under_supported),
        "font_programs_seen": len(fonts),
        "pages": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--pages", required=True, help="comma separated 1-based page numbers (a shared ledger carries over between them)")
    parser.add_argument("--budget", type=int, default=150, help="corroboration attempts allowed per page")
    parser.add_argument("--min-words", type=int, default=shadow.DEFAULT_MIN_WORDS)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    result = analyse(args.pdf.read_bytes(), [int(p) for p in args.pages.split(",") if p.strip()], min_words=args.min_words, budget=args.budget)
    for row in result["pages"]:
        print(f"page {row['page']}: {row['words']} words, {row['blocked_only_by_glyph_mapping_or_clip']} blocked by glyph mapping/clip; "
              f"fully verified {row['words_fully_verified_before_any_attempt_on_this_page']} -> {row['words_fully_verified_after']} "
              f"after {row['attempts_on_this_page']} attempts ({row['corroborated_on_this_page']} corroborated, {row['recogniser_seconds_on_this_page']} s)")
    print(f"verified (font, glyph) mappings {result['verified_font_glyph_pairs']}, contradicted {result['contradicted_font_glyph_pairs']}, "
          f"under-supported {result['under_supported_font_glyph_pairs']}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
