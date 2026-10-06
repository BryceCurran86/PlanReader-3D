from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fitz

from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGETS = (
    "AIRLOCK",
    "LAUNDRY",
    "OFFICE",
    "PWD",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _lines(page) -> tuple[dict, ...]:
    grouped = defaultdict(list)
    for word in page.get_text("words") or ():
        if len(word) < 8:
            continue
        grouped[(int(word[5]), int(word[6]))].append(word)
    out = []
    for (block, line), words in sorted(grouped.items()):
        ordered = sorted(words, key=lambda item: int(item[7]))
        text = " ".join(
            str(item[4]).strip() for item in ordered if str(item[4]).strip()
        )
        if not text:
            continue
        out.append({
            "block_no": block,
            "line_no": line,
            "text": text,
            "normalized": _norm(text),
            "bbox": [
                min(float(item[0]) for item in ordered),
                min(float(item[1]) for item in ordered),
                max(float(item[2]) for item in ordered),
                max(float(item[3]) for item in ordered),
            ],
        })
    return tuple(out)


def main() -> int:
    doc = fitz.open(SOURCE)
    try:
        scope = source_floor_plan_topology_scope(
            SOURCE, tuple(range(doc.page_count))
        )
        if scope is None:
            raise RuntimeError("source page scope unavailable")
        decisions = {d.page_index: d for d in scope.decisions}
        support = tuple(scope.evidence_page_indices)
        result = {target: [] for target in TARGETS}
        for page_index in support:
            page_lines = _lines(doc[page_index])
            exact = defaultdict(list)
            for row in page_lines:
                if row["normalized"] in result:
                    exact[row["normalized"]].append(row)
            if not exact:
                continue
            decision = decisions[page_index]
            for target, rows in sorted(exact.items()):
                result[target].append({
                    "page_number_one_based": page_index + 1,
                    "title": decision.title,
                    "classification": decision.classification,
                    "view_types": list(decision.view_types),
                    "exact_line_count": len(rows),
                    "lines": rows,
                })

        print(json.dumps({
            "topology_pages_one_based": [
                i + 1 for i in (scope.topology_page_indices() or ())
            ],
            "classified_evidence_pages_one_based": [
                i + 1 for i in support
            ],
            "targets": result,
        }, indent=2, sort_keys=True))
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
