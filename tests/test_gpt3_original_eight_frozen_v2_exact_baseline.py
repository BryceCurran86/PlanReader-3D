"""GPT3 signed customer/source eight → unchanged frozen Lot16 V2 regression."""
from __future__ import annotations

import json

import pytest

import tools.replay_gpt3_immutable_lot16_eight_original_v2 as replay


def test_full_original_signed_eight_score_uses_unchanged_exact_v2_evaluator():
    result = replay.replay_archived_original_eight_v2_baseline()
    assert result["source_customer_eight_verified"] is True
    assert result["historical_identity_binding_count"] == 8
    assert result["historical_identity_map_git_blob_sha1"] == (
        "e4cfa9a1270c608d0683ec2cba051b78b12dd573"
    )
    assert result["original_matched_within_tolerance"] == 8
    assert result["original_frozen_denominator"] == 27
    assert result["frozen_project_reconciliation_complete"] is True
    assert result["current_main_live_source_verified"] is False
    assert result["new_firm_quantity_issued"] is False
    assert result["customer_release_approved"] is False
    assert result["current_full_120_benchmark_scored"] is False
    assert result["source_sha256"] == replay.SOURCE_SHA256
    assert result["original_eight_fingerprint"] == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )


def test_original_source_customer_score_export_create_only(tmp_path):
    output = tmp_path / "historical-original-eight.json"
    assert replay.main(["--output", str(output)]) == 0
    contents = json.loads(output.read_text(encoding="utf-8"))
    assert contents["original_matched_within_tolerance"] == 8
    assert contents["original_frozen_denominator"] == 27
    assert contents["new_firm_quantity_issued"] is False
    with pytest.raises(FileExistsError):
        replay.main(["--output", str(output)])


@pytest.mark.parametrize("field", ["wrong_signed_fingerprint", "wrong_source_sha"])
def test_immutable_source_fingerprint_cannot_be_replaced(monkeypatch, field):
    if field == "wrong_signed_fingerprint":
        monkeypatch.setattr(replay, "ORIGINAL_EIGHT_FINGERPRINT", "0" * 64)
    else:
        monkeypatch.setattr(replay, "SOURCE_SHA256", "f" * 64)
    with pytest.raises(ValueError, match="historical eight signed run is not exact"):
        replay.replay_archived_original_eight_v2_baseline()


def test_fake_eight_identity_map_cannot_create_original_match(monkeypatch, tmp_path):
    original = json.loads(replay.ORIGINAL_MAP.read_text(encoding="utf-8"))
    original["bindings"] = original["bindings"][:-1]
    forged = tmp_path / "forged-map.json"
    forged.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(replay, "ORIGINAL_MAP", forged)
    with pytest.raises(ValueError, match="identity map unavailable"):
        replay.replay_archived_original_eight_v2_baseline()


def test_never_overwrite_frozen_or_immutable_source_inputs():
    with pytest.raises(ValueError, match="protected evidence"):
        replay.main(["--output", str(replay.ORIGINAL_V1)])
    with pytest.raises(ValueError, match="protected evidence"):
        replay.main(["--output", str(replay.MANIFEST)])


def test_pinned_historical_identity_map_matches_original_archive_blob():
    # This pins the exact archived map, not any present-day new activation.
    assert replay._git_blob_sha1(replay.ORIGINAL_MAP) == (
        "e4cfa9a1270c608d0683ec2cba051b78b12dd573"
    )


def test_same_count_but_swapped_original_membership_cannot_score(monkeypatch, tmp_path):
    original = json.loads(replay.ORIGINAL_MAP.read_text(encoding="utf-8"))
    assert len(original["bindings"]) == 8
    # Preserve all eight item IDs, physical IDs, source SHA and the project,
    # but falsely exchange which original source object owns two frozen items.
    first = original["bindings"][0]["production_object_identity_refs"]
    second = original["bindings"][1]["production_object_identity_refs"]
    original["bindings"][0]["production_object_identity_refs"] = second
    original["bindings"][1]["production_object_identity_refs"] = first
    forged = tmp_path / "eight-map-swapped-but-still-valid-JSON.json"
    forged.write_text(json.dumps(original, indent=2), encoding="utf-8")
    monkeypatch.setattr(replay, "ORIGINAL_MAP", forged)
    with pytest.raises(ValueError, match="identity map bytes differ from pinned archive"):
        replay.replay_archived_original_eight_v2_baseline()


def test_reformatted_historical_map_is_not_independently_certified(monkeypatch, tmp_path):
    original = json.loads(replay.ORIGINAL_MAP.read_text(encoding="utf-8"))
    # Same eight physical bindings, byte-different serialization:
    # "some valid JSON" is not equal to the independently archived map.
    forged = tmp_path / "alternate-serialization.json"
    forged.write_text(json.dumps(original, sort_keys=True), encoding="utf-8")
    assert len(original["bindings"]) == 8
    monkeypatch.setattr(replay, "ORIGINAL_MAP", forged)
    with pytest.raises(ValueError, match="identity map bytes differ from pinned archive"):
        replay.replay_archived_original_eight_v2_baseline()


def test_original_map_must_match_pinned_archive_before_exact_scorer(
    monkeypatch, tmp_path,
):
    original = json.loads(replay.ORIGINAL_MAP.read_text(encoding="utf-8"))
    original["bindings"][0]["production_family"] = "opening_count"
    forged = tmp_path / "eight-map-untrusted-family.json"
    forged.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(replay, "ORIGINAL_MAP", forged)

    def scorer_must_not_run(*_args, **_kwargs):
        raise AssertionError("the frozen scorer should never see a forged archived map")

    monkeypatch.setattr(replay.subprocess, "run", scorer_must_not_run)
    with pytest.raises(ValueError, match="identity map bytes differ from pinned archive"):
        replay.replay_archived_original_eight_v2_baseline()
