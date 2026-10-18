"""Read-only census: what changes when native text blocks are word-aligned?

``pb_figured_dimension_evidence`` looks a word's native text direction up by the (block, line) numbers of
``page.get_text("words")``, but reads the directions from ``page.get_text("dict")`` whose default profile also
numbers image blocks. Any image earlier in the content stream shifts every later key. This tool compares, per page
of a PDF given on the command line (never committed, never uploaded), the direction hints the binder receives with
the default numbering and with ``word_aligned_text_blocks=True`` and, only for pages where a hint differs, the
resulting evidence bundles.

It reports counts and binding changes only. It reads no benchmark data, produces no quantity, changes no module
state and writes nothing unless ``--output`` names a JSON file.

    python -m tools.diag_figured_text_flag_alignment_census path/to/plans.pdf [--pages 1,2,3] [--output out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence

import pb_figured_dimension_evidence as fde


def _binding_row(binding: Any) -> tuple[str, str, Optional[str]]:
    status = getattr(binding.status, "value", binding.status)
    return (str(binding.observation_id), str(status), binding.dimension_line_id)


def census_page(page: Any, *, page_num: int) -> dict[str, Any]:
    """Compare default and word-aligned direction hints (and, if they differ, bundles) for one page."""
    native = fde.extract_native_dimension_observations(page, page_num=page_num)
    words = list(fde._native_words(page))
    default_hints = fde._native_word_orientations(page)
    aligned_hints = fde._native_word_orientations(page, word_aligned=True)
    prefix = f"native_dim_p{page_num}_"
    hint_changed = 0
    for observation in native:
        if not observation.dimension_id.startswith(prefix):
            continue
        try:
            word = words[int(observation.dimension_id[len(prefix):])]
            key = (int(word[5]), int(word[6]))
        except (IndexError, TypeError, ValueError):
            continue
        if default_hints.get(key) != aligned_hints.get(key):
            hint_changed += 1
    row: dict[str, Any] = {
        "page": page_num,
        "native_observations": len(native),
        "hint_changed": hint_changed,
        "bindings_changed": 0,
        "observations_equal": True,
        "chains_equal": True,
        "binding_changes": [],
    }
    if hint_changed:
        before = fde.extract_dimension_evidence_bundle(page, page_num=page_num)
        after = fde.extract_dimension_evidence_bundle(page, page_num=page_num, word_aligned_text_blocks=True)
        changes = [
            {"before": _binding_row(a), "after": _binding_row(b)}
            for a, b in zip(before.bindings, after.bindings)
            if a != b
        ]
        row["bindings_changed"] = len(changes)
        row["binding_changes"] = changes
        row["observations_equal"] = before.observations == after.observations
        row["chains_equal"] = before.chains == after.chains
    return row


def census_pdf(data: bytes, *, pages: Optional[Sequence[int]] = None) -> dict[str, Any]:
    """Census of a whole PDF (1-based ``pages`` optional). Counts only; the bytes are not retained."""
    import fitz

    with fitz.open(stream=data, filetype="pdf") as document:
        indexes = range(document.page_count) if pages is None else [p - 1 for p in pages]
        rows = [census_page(document.load_page(i), page_num=i + 1) for i in indexes]
    totals = {
        "pages": len(rows),
        "native_observations": sum(r["native_observations"] for r in rows),
        "hint_changed": sum(r["hint_changed"] for r in rows),
        "pages_with_hint_change": sum(1 for r in rows if r["hint_changed"]),
        "bindings_changed": sum(r["bindings_changed"] for r in rows),
        "pages_with_evidence_change": sum(
            1 for r in rows if r["bindings_changed"] or not r["observations_equal"] or not r["chains_equal"]
        ),
    }
    return {"sha256": hashlib.sha256(data).hexdigest(), "totals": totals, "pages": rows}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", help="comma-separated 1-based page numbers (default: all)")
    parser.add_argument("--output", type=Path, help="write the JSON report here")
    args = parser.parse_args(argv)
    pages = None if not args.pages else [int(item) for item in args.pages.split(",")]
    report = census_pdf(args.pdf.read_bytes(), pages=pages)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["totals"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
