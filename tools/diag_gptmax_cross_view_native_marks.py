"""Read-only native opening-mark cross-view census. NEVER binding/quantity authority."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

STATUS = "UNBOUND_NATIVE_CROSS_VIEW_MARK_CENSUS"

def _normalize(token):
    return str(token).strip().strip(".,:;").upper()

def _group_words(words):
    grouped = {}
    for word in words:
        if len(word) < 8:
            continue
        try:
            box = tuple(float(x) for x in word[:4])
            block, line, ordinal = (int(word[i]) for i in (5, 6, 7))
        except (ValueError, TypeError, OverflowError):
            continue
        if not all(math.isfinite(x) for x in box):
            continue
        token = _normalize(word[4])
        if token:
            grouped.setdefault((block, line), []).append((ordinal, token, box))
    for line in grouped.values():
        line.sort(key=lambda x: (x[0], x[2], x[1]))
    return grouped

def native_phrase_occurrences(words, phrase):
    """Only consecutive native SAME-LINE word ordinals; no nearest label joins."""
    tokens = tuple(_normalize(w) for w in phrase.split() if _normalize(w))
    if not tokens:
        raise ValueError("phrase must have at least one native word")
    result = []
    for (block, line), candidates in sorted(_group_words(words).items()):
        for offset in range(len(candidates) - len(tokens) + 1):
            group = candidates[offset:offset + len(tokens)]
            if tuple(w[1] for w in group) != tokens:
                continue
            if any(b[0] != a[0] + 1 for a, b in zip(group, group[1:])):
                continue
            boxes = [w[2] for w in group]
            result.append({
                "block_no": block, "line_no": line,
                "word_indices": [w[0] for w in group],
                "native_words": [w[1] for w in group],
                "word_bboxes_pdf_pt": [list(x) for x in boxes],
                "envelope_pdf_pt": [
                    min(b[0] for b in boxes), min(b[1] for b in boxes),
                    max(b[2] for b in boxes), max(b[3] for b in boxes),
                ],
                "source_text_only": True,
            })
    return tuple(sorted(result, key=lambda x: (
        x["block_no"], x["line_no"], x["word_indices"], x["envelope_pdf_pt"])))

def inventory_native_marks(document, *, page_ids, phrase, datum_tokens):
    if not page_ids or len(set(page_ids)) != len(page_ids):
        raise ValueError("page_ids must be nonempty and unique")
    pages, count = [], 0
    for page_id in sorted(page_ids):
        if page_id < 0 or page_id >= len(document):
            raise ValueError("source page index unavailable")
        # Reads immutable original-native PDF words, never injected OCR.
        words = tuple(document[page_id].get_text("words"))
        marks = native_phrase_occurrences(words, phrase)
        count += len(marks)
        datums = {
            token: list(native_phrase_occurrences(words, token))
            for token in sorted({_normalize(x) for x in datum_tokens if _normalize(x)})
        }
        pages.append({
            "source_page_index_zero_based": page_id,
            "mark_occurrences": list(marks),
            "datum_token_occurrences": datums,
        })
    return {
        "status": STATUS, "source_evidence_only": True,
        "native_text_only": True,
        "phrase": " ".join(_normalize(x) for x in phrase.split()),
        "requested_source_page_indices": sorted(page_ids),
        "occurrence_count": count, "pages": pages,
        "page_viewport_identity_proven": False,
        "cross_sheet_physical_identity_proven": False,
        "opening_kind_proven": False,
        "opening_host_proven": False,
        "ordered_width_height_proven": False,
        "datum_to_opening_alignment_proven": False,
        "opening_count_proven": False,
        "firm_quantity_granted": False,
    }

def original_pdf_mark_inventory(path, *, expected_sha256, page_ids, phrase,
                                datum_tokens):
    import fitz
    data = Path(path).read_bytes()
    source_sha = sha256(data).hexdigest()
    if not expected_sha256 or source_sha != expected_sha256.lower():
        raise ValueError("original source SHA256 mismatch (no census published)")
    with fitz.open(stream=data, filetype="pdf") as doc:
        report = inventory_native_marks(doc, page_ids=page_ids, phrase=phrase,
                                        datum_tokens=datum_tokens)
        report["source_sha256"] = source_sha
        report["source_total_pages"] = len(doc)
        return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page-ids", type=int, nargs="+", required=True)
    parser.add_argument("--phrase", required=True)
    parser.add_argument("--datum-tokens", nargs="*", default=())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = original_pdf_mark_inventory(
        args.pdf, expected_sha256=args.sha256, page_ids=args.page_ids,
        phrase=args.phrase, datum_tokens=args.datum_tokens)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Unbound native cross-view word occurrences:", report["occurrence_count"])

if __name__ == "__main__":
    main()
