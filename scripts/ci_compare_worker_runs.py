"""Source-free CI worker-count timing comparison; not a release gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def junit_receipt(path: Path, workers: int) -> dict:
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter("testcase"):
        # Include outcome and identity but never retain captured output or paths
        # as plaintext in the published receipt.
        identity = (case.attrib["classname"], case.attrib["name"])
        outcome = tuple(sorted(c.tag for c in case if c.tag in {"failure", "error", "skipped"}))
        # pytest reports xfail as skipped and xpass as pass or failure.
        kind = tuple(sorted((c.tag, c.attrib.get("type", "")) for c in case
                            if c.tag in {"failure", "error", "skipped"}))
        cases.append((identity, outcome, kind))
    if not cases or len(set(c[0] for c in cases)) != len(cases):
        raise ValueError("missing or duplicate test identity")
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise ValueError("missing suite")
    if any("failure" in c[1] or "error" in c[1] for c in cases):
        raise ValueError("failed test")
    digest = hashlib.sha256(json.dumps(sorted(cases), separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return {"workers": workers, "count": len(cases), "outcomes_sha256": digest,
            "seconds": float(suite.attrib["time"])}


def compare(rows: list[dict]) -> str:
    if sorted(r["workers"] for r in rows) != [0, 2, 4, 8]:
        raise ValueError("missing or duplicate worker configuration")
    baseline = next(r for r in rows if r["workers"] == 0)
    lines = ["| Workers | Full tests | Pytest seconds | Relative speed |",
             "|---:|---:|---:|---:|"]
    for r in sorted(rows, key=lambda r: r["workers"]):
        if r["count"] != baseline["count"] or r["outcomes_sha256"] != baseline["outcomes_sha256"]:
            raise ValueError("worker execution outcome mismatch")
        if not 0 < r["seconds"] < 86400:
            raise ValueError("invalid timing")
        lines.append(f'| {r["workers"]} | {r["count"]} | {r["seconds"]:.2f} | {baseline["seconds"]/r["seconds"]:.2f}x |')
    return "\n".join(lines)


if __name__ == "__main__":
    if sys.argv[1] == "receipt":
        row = junit_receipt(Path(sys.argv[2]), int(sys.argv[3]))
        Path(sys.argv[4]).write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
    elif sys.argv[1] == "compare":
        rows = [json.loads(p.read_text(encoding="utf-8")) for p in Path(sys.argv[2]).rglob("worker-receipt.json")]
        print(compare(rows))
    else:
        raise SystemExit("Expected receipt or compare")
