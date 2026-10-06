from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGET = "FREEZER"
_NUMERIC_RE = re.compile(r"^[0-9][0-9\s.,'\"-]*$")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _line_rows(page) -> list[dict]:
    words = page.get_text("words") or []
    grouped: dict[tuple[int, int], list[tuple]] = {}
    for word in words:
        if len(word) < 8:
            continue
        key = (int(word[5]), int(word[6]))
        grouped.setdefault(key, []).append(word)

    rows = []
    for (block_no, line_no), items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: int(item[7]))
        text = " ".join(str(item[4]).strip() for item in ordered if str(item[4]).strip())
        if not text:
            continue
        rows.append(
            {
                "block_no": block_no,
                "line_no": line_no,
                "text": text,
                "normalized": _norm(text),
                "bbox": [
                    min(float(item[0]) for item in ordered),
                    min(float(item[1]) for item in ordered),
                    max(float(item[2]) for item in ordered),
                    max(float(item[3]) for item in ordered),
                ],
            }
        )
    return rows


def main() -> int:
    doc = fitz.open(SOURCE)
    try:
        selected = tuple(range(doc.page_count))
        scope = source_floor_plan_topology_scope(SOURCE, selected)
        if scope is None:
            raise RuntimeError("source floor-plan scope unavailable")

        decision_by_index = {item.page_index: item for item in scope.decisions}
        evidence_pages = tuple(scope.evidence_page_indices)
        results = []

        for page_index in evidence_pages:
            rows = _line_rows(doc[page_index])
            target_rows = [row for row in rows if row["normalized"] == TARGET]
            if not target_rows:
                continue

            nearby = []
            for target_row in target_rows:
                for row in rows:
                    same_block = row["block_no"] == target_row["block_no"]
                    close_line = abs(row["line_no"] - target_row["line_no"]) <= 3
                    numeric = bool(_NUMERIC_RE.fullmatch(row["normalized"]))
                    if row is target_row or (same_block and close_line) or numeric:
                        nearby.append(row)

            deduped = []
            seen = set()
            for row in nearby:
                key = (row["block_no"], row["line_no"], row["normalized"])
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(row)

            decision = decision_by_index[page_index]
            results.append(
                {
                    "page_index_zero_based": page_index,
                    "page_number_one_based": page_index + 1,
                    "title": decision.title,
                    "classification": decision.classification,
                    "reason_code": decision.reason_code,
                    "view_types": list(decision.view_types),
                    "exact_freezer_line_count": len(target_rows),
                    "exact_freezer_lines": target_rows,
                    "navigation_nearby_or_numeric_lines": deduped,
                }
            )

        print(
            json.dumps(
                {
                    "page_count": doc.page_count,
                    "topology_pages_one_based": [
                        index + 1
                        for index in (scope.topology_page_indices() or ())
                    ],
                    "classified_evidence_pages_one_based": [
                        index + 1 for index in evidence_pages
                    ],
                    "freezer_support_candidates": results,
                },
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
