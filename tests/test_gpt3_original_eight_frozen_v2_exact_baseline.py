"""GPT3 signed customer/source eight → unchanged frozen Lot16 V2 regression."""
from __future__ import annotations

import json

import pytest

import tools.replay_gpt3_immutable_lot16_eight_original_v2 as replay


def test_full_original_signed_eight_score_uses_unchanged_exact_v2_evaluator():
    result = replay.replay_archived_original_eight_v2_baseline()
    assert result["source_customer_eight_verified"] is True
    assert result["historical_identity_binding_count"] == 8
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
