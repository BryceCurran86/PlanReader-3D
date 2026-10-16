"""Read-only: how much of a PDF's native text does the producer-owned text-integrity authority trust, page by page?

Every label, dimension, scale text, schedule and room name enters the quantity chains through
``PdfTextIntegrityAuthority`` (``TRUSTED_PDF_TEXT``). A word it abstains on is invisible to those chains. This tool
ingests the pages with the same producer the live chain uses and reports, per page: the word count, the status of every
word, the reason codes (counted per word), and for each font on the page whether the embedded font program offers the
Unicode lookup the authority needs (``fitz.Font.has_glyph`` on the digits and capitals the page uses). It decides nothing,
changes nothing and grants nothing.

usage: python -m tools.diag_text_integrity_coverage --pdf FILE --pages 3,7 [--json OUT.json]
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import fitz

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

_PROBE_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPRSTUVWXYZabcdefghijklmnoprstuvwxyz"


def _bare(name: object) -> str:
    """Font name without a subset tag (``ABCDEF+Arial`` -> ``Arial``)."""
    text = str(name or "")
    return text.split("+", 1)[1] if len(text) > 7 and text[6] == "+" and text[:6].isalpha() and text[:6].isupper() else text


def font_table(page: "fitz.Page", document: "fitz.Document") -> list[dict]:
    rows = []
    used = Counter()
    for block in page.get_text("dict", flags=fitz.TEXTFLAGS_WORDS)["blocks"]:
        for line in block.get("lines", ()):
            for span in line.get("spans", ()):
                used[_bare(span.get("font"))] += len(str(span.get("text") or ""))
    for font in page.get_fonts(full=True):
        xref, subtype, base_font, name, encoding = font[0], font[2], font[3], font[4], font[5]
        try:
            description = document.xref_object(xref, compressed=False)
        except Exception:
            description = ""
        try:
            extracted = document.extract_font(xref)
            program = extracted[3] if extracted and len(extracted) > 3 else b""
        except Exception:
            program = b""
        unicode_lookup = None
        if program:
            try:
                view = fitz.Font(fontbuffer=program)
                present = sum(1 for ch in _PROBE_CHARACTERS if view.has_glyph(ord(ch), fallback=0) > 0)
                unicode_lookup = f"{present}/{len(_PROBE_CHARACTERS)}"
            except Exception:
                unicode_lookup = "unreadable_font_program"
        rows.append({
            "xref": xref, "subtype": subtype, "base_font": base_font, "alias": name, "encoding": encoding,
            "has_to_unicode": "/ToUnicode" in description, "embedded_program_bytes": len(program),
            "unicode_lookup_in_embedded_program": unicode_lookup,
            "characters_on_page": used.get(_bare(base_font), 0),
        })
    rows.sort(key=lambda r: (-r["characters_on_page"], r["xref"]))
    return rows


def coverage(pdf: Path, pages: list[int]) -> list[dict]:
    payload = pdf.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    document = fitz.open(stream=payload, filetype="pdf")
    out = []
    for number in pages:
        producer = SourceVisibilityProducer(
            producer_method="text-integrity-coverage",
            producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        )
        published = producer.ingest_native_pdf_bytes(
            document_id=f"coverage:{digest[:32]}", source_bytes=payload,
            source_locator="memory://coverage.pdf", page_ids=(str(number),),
        )
        authority = producer.text_integrity_authority()
        status = Counter()
        reasons = Counter()
        for observation_id in published.text_observation_ids:
            selector = ObservationSelector(
                document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
            result = authority.resolve_text(selector)
            status[str(result.status).rsplit(".", 1)[-1]] += 1
            for code in result.reason_codes or ():
                reasons[str(code)] += 1
        total = len(published.text_observation_ids)
        trusted = status.get("CORROBORATED", 0)
        out.append({
            "page": number,
            "words": total,
            "trusted_words": trusted,
            "trusted_fraction": round(trusted / total, 4) if total else None,
            "status_counts": dict(sorted(status.items())),
            "reason_counts_per_word": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
            "fonts": font_table(document[number - 1], document),
        })
    document.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="comma-separated 1-based page numbers")
    parser.add_argument("--json", type=Path, dest="json_path")
    args = parser.parse_args()
    pages = [int(p) for p in args.pages.split(",") if p.strip()]
    result = coverage(args.pdf, pages)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(text + "\n", encoding="utf-8")
    for row in result:
        print(f"page {row['page']}: {row['trusted_words']}/{row['words']} words trusted; reasons {list(row['reason_counts_per_word'].items())[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
