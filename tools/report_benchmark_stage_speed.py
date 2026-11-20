"""Summarize crash-persistent PlanReader source-stage journals without opening PDFs.

Diagnostic-only: never runs a benchmark, changes scoring, or invents results.
Usage: python tools/report_benchmark_stage_speed.py journal1.jsonl [journal2.jsonl ...]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


def summarize(paths: list[Path]) -> dict:
    reports = []
    for path in paths:
        entered = {}
        stages = defaultdict(lambda: {"completed_calls": 0, "inclusive_ms": 0.0, "failed_calls": 0})
        peak_rss_kb = 0
        samples = defaultdict(lambda: {"calls": 0, "cumulative_ms": 0.0})
        lines = 0
        source_sha_verified = False
        producer_returned = False
        with path.open(encoding="utf-8") as source:
            for line_no, line in enumerate(source, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if type(record) is not dict or record.get("diagnostic_only") is not True:
                    raise ValueError(f"untrusted stage journal row: {path}:{line_no}")
                stage, event, call_id = record.get("stage"), record.get("event"), record.get("call_id")
                if type(stage) is not str or not stage or type(call_id) is not int or type(event) is not str:
                    raise ValueError(f"invalid stage journal row: {path}:{line_no}")
                if producer_returned:
                    raise ValueError(f"events after original producer terminal receipt: {path}:{line_no}")
                if type(record.get("peak_rss_kb")) is int:
                    peak_rss_kb = max(peak_rss_kb, record["peak_rss_kb"])
                key = (stage, call_id)
                if event == "entered":
                    if key in entered:
                        raise ValueError(f"duplicate stage entry: {path}:{line_no}")
                    entered[key] = record.get("monotonic_ns")
                elif event == "sha_verified":
                    if stage != "source_input" or call_id != 0 or source_sha_verified:
                        raise ValueError(f"invalid or duplicate source event: {path}:{line_no}")
                    source_sha_verified = True
                elif event == "producer_returned":
                    if (stage != "source_handoff" or call_id != 0
                            or not source_sha_verified or entered):
                        raise ValueError(f"invalid original producer terminal receipt: {path}:{line_no}")
                    producer_returned = True
                elif event == "failed" and key not in entered and "observation_calls" in record:
                    stages[stage]["failed_calls"] += 1
                elif event in ("completed", "failed"):
                    if key not in entered:
                        raise ValueError(f"stage ended without entry: {path}:{line_no}")
                    entered.pop(key)
                    if event == "completed":
                        stages[stage]["completed_calls"] += 1
                        ms = record.get("elapsed_ms")
                        if type(ms) not in (int, float) or not 0 <= ms < float("inf"):
                            raise ValueError(f"invalid stage duration: {path}:{line_no}")
                        stages[stage]["inclusive_ms"] += ms
                    else:
                        stages[stage]["failed_calls"] += 1
                elif event == "sample":
                    calls, cumulative = record.get("observation_calls"), record.get("cumulative_ms")
                    if type(calls) is int and calls >= samples[stage]["calls"] and type(cumulative) in (int, float) and 0 <= cumulative < float("inf"):
                        samples[stage] = {"calls": calls, "cumulative_ms": cumulative}
                else:
                    raise ValueError(f"unknown stage event: {path}:{line_no}")
                lines += 1
        rows = [{"stage": name, **{k: round(v, 3) if k == "inclusive_ms" else v for k, v in values.items()}} for name, values in stages.items()]
        rows.sort(key=lambda x: (-x["inclusive_ms"], x["stage"]))
        reports.append({"journal": str(path), "rows_read": lines, "peak_rss_kb": peak_rss_kb,
                        "stage_totals_inclusive_nested": True, "source_sha_verified": source_sha_verified,
                        "original_producer_returned_after_source_recheck": producer_returned,
                        "stages": rows,
                        "unfinished_stage_calls": [{"stage": k[0], "call_id": k[1]} for k in sorted(entered)],
                        "sampled_hotpaths": dict(sorted(samples.items())),
                        "complete": source_sha_verified and producer_returned and not bool(entered)
                        and not any(v["failed_calls"] for v in stages.values())})
    return {"diagnostic_only": True, "reports": reports,
            "notice": "Inclusive stage totals may overlap for nested calls; do not sum them as whole-run time. A complete journal is not proof of a complete signed benchmark."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journals", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    data = summarize(args.journals)
    output = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(output)
    else:
        sys.stdout.write(output)
    return 0 if all(report["complete"] for report in data["reports"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
