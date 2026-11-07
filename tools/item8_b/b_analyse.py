"""Study B step 2: relation rows for the owner-picked structures of ONE document. Read-only. Counts only in the output.

usage: python tools/item8_b/b_analyse.py <label> <pdf> <page_number> <labels_json> <structures_json> <out_json>

<labels_json> is the file the owner downloads from the viewer; <structures_json> is step 1's output for the same page. The labels
are checked against a fresh enumeration (same ids, same fingerprint) and refused otherwise. The output holds the A5 counts and
per-structure relation rows WITHOUT ids or coordinates. Pre-registration:
docs/engineering/claude_item8_labelled_window_study_20261103.md."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.item8_b.b_core import label_counts, picked_ids, structures_digest, summarise_rows, validate_labels  # noqa: E402
from tools.item8_b.b_pipeline import enumerate_page, relation_rows  # noqa: E402


def analyse(label: str, pdf: Path, page_no: int, labels: dict, recorded: dict) -> dict:
    t0 = time.time()
    page = enumerate_page(label, pdf, page_no)
    fresh = structures_digest([dict(id=cid) for cid in page.extents])
    problems = validate_labels(labels, page.extents, recorded["structures_sha256"])
    if fresh != recorded["structures_sha256"]:
        problems.append("fresh_enumeration_differs_from_viewer_enumeration")
    result = dict(label=label, page=page_no, pdf_sha256_prefix=page.pdf_sha256[:8], problems=problems,
                  label_counts=label_counts(labels))
    if problems:
        result["status"] = "refused"
        return result
    rows = relation_rows(page, picked_ids(labels))
    result.update(status="complete", rows=rows, stats=summarise_rows(rows), seconds=round(time.time() - t0, 1))
    return result


if __name__ == "__main__":
    label, pdf_path, page, labels_path, structures_path, out_json = sys.argv[1:7]
    outcome = analyse(label, Path(pdf_path), int(page), json.loads(Path(labels_path).read_text(encoding="utf-8")),
                      json.loads(Path(structures_path).read_text(encoding="utf-8")))
    Path(out_json).write_text(json.dumps(outcome), encoding="utf-8")
    print(label, page, outcome["status"], outcome["label_counts"], outcome.get("stats"))
