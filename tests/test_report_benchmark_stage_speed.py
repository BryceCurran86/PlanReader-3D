"""Tests for diagnostic-only original benchmark stage journal summary."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from report_benchmark_stage_speed import summarize, main


def row(stage, event, call_id, **kw):
    return {"diagnostic_only": True, "stage": stage, "event": event, "call_id": call_id, **kw}


def write(path, rows):
    path.write_text("".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8")


def test_nested_durations_and_samples(tmp_path):
    path = tmp_path / "stages.jsonl"
    write(path, [row("source_input", "sha_verified", 0),
                 row("outer", "entered", 1, monotonic_ns=1, peak_rss_kb=10),
                 row("inner", "entered", 2, monotonic_ns=2, peak_rss_kb=20),
                 row("inner", "completed", 2, elapsed_ms=5.1),
                 row("opening", "sample", 3, observation_calls=512, cumulative_ms=12),
                 row("outer", "completed", 1, elapsed_ms=8.1),
                 row("source_handoff", "producer_returned", 0)])
    result = summarize([path])["reports"][0]
    assert result["complete"]
    assert result["peak_rss_kb"] == 20
    assert result["stages"] == [{"stage": "outer", "completed_calls": 1, "inclusive_ms": 8.1, "failed_calls": 0},
                                {"stage": "inner", "completed_calls": 1, "inclusive_ms": 5.1, "failed_calls": 0}]
    assert result["sampled_hotpaths"]["opening"]["calls"] == 512


def test_timeout_retains_unfinished(tmp_path):
    path = tmp_path / "stages.jsonl"
    write(path, [row("outer", "entered", 10, monotonic_ns=1)])
    result = summarize([path])["reports"][0]
    assert result["unfinished_stage_calls"] == [{"stage": "outer", "call_id": 10}]
    assert not result["complete"]
    assert main([str(path)]) == 2


def test_fail_closed_bad_journal(tmp_path):
    import pytest
    path = tmp_path / "bad.jsonl"
    write(path, [row("outer", "completed", 2, elapsed_ms=1)])
    with pytest.raises(ValueError, match="without entry"):
        summarize([path])


def test_real_journal_sampled_failure(tmp_path):
    path = tmp_path / "real.jsonl"
    write(path, [row("source_input", "sha_verified", 0),
                 row("PhysicalOpeningAuthority.prove_existence", "failed", 1,
                     observation_calls=20, cumulative_ms=4, error_type="ValueError")])
    result = summarize([path])["reports"][0]
    assert not result["complete"]
    assert result["stages"][0]["failed_calls"] == 1


def test_empty_or_missing_source_receipt_never_complete(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert not summarize([empty])["reports"][0]["complete"]
    unverified = tmp_path / "unverified.jsonl"
    write(unverified, [row("outer", "entered", 1),
                       row("outer", "completed", 1, elapsed_ms=1)])
    assert not summarize([unverified])["reports"][0]["complete"]


def test_partial_journal_with_closed_early_stages_is_not_full_producer(tmp_path):
    """A crash can occur between any stages; no stage left open is insufficient."""
    path = tmp_path / "stopped_after_first_stage.jsonl"
    write(path, [row("source_input", "sha_verified", 0),
                 row("native_decode", "entered", 1),
                 row("native_decode", "completed", 1, elapsed_ms=0.4)])
    report = summarize([path])["reports"][0]
    assert report["source_sha_verified"] is True
    assert report["unfinished_stage_calls"] == []
    assert report["original_producer_returned_after_source_recheck"] is False
    assert report["complete"] is False
    assert main([str(path)]) == 2


def test_terminal_producer_receipt_requires_original_source_and_final_event(tmp_path):
    import pytest
    scenarios = (
        [row("source_handoff", "producer_returned", 0)],
        [row("source_input", "sha_verified", 0),
         row("ongoing", "entered", 9),
         row("source_handoff", "producer_returned", 0)],
        [row("source_input", "sha_verified", 0),
         row("source_handoff", "producer_returned", 1)],
        [row("source_input", "sha_verified", 0),
         row("source_handoff", "producer_returned", 0),
         row("extra", "entered", 2)],
        [row("source_input", "sha_verified", 0),
         row("source_handoff", "producer_returned", 0),
         row("source_handoff", "producer_returned", 0)],
    )
    for i, entries in enumerate(scenarios):
        path = tmp_path / f"invalid_terminal_{i}.jsonl"
        write(path, entries)
        with pytest.raises(ValueError):
            summarize([path])


def test_original_producer_terminal_is_diagnostic_only_not_customer_score(tmp_path):
    path = tmp_path / "complete_source_handoff.jsonl"
    write(path, [row("source_input", "sha_verified", 0),
                 row("source_handoff", "producer_returned", 0)])
    report = summarize([path])["reports"][0]
    assert report["original_producer_returned_after_source_recheck"] is True
    assert report["complete"] is True
    assert "benchmark_score_granted" not in report
