"""External incremental scoreboard: frozen scorer and 120 truth remain untouched."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from tools import gpt3_incremental_120_development_wrapper as live

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "engineering" / "lot16_original_signed_eight_row_20261015"
LOT16 = "au_qld_lot16_power"


def _inputs(tmp_path: Path, *, with_seal: bool = True, with_map: bool = True):
    sealed = tmp_path / "sealed"
    maps = tmp_path / "maps"
    sealed.mkdir()
    maps.mkdir()
    if with_seal:
        shutil.copyfile(
            ARCHIVE / "production" / "source_sealed_run.json",
            sealed / f"{LOT16}.json",
        )
    if with_map:
        shutil.copyfile(
            ARCHIVE / "identity_map_with_1215.json",
            maps / f"{LOT16}.identity_map.json",
        )
    return sealed, maps


def _run(tmp_path: Path, sealed: Path, maps: Path):
    score = tmp_path / "score.json"
    failures = tmp_path / "failures.json"
    rc = live.main([
        "--sealed-dir", str(sealed),
        "--identity-map-dir", str(maps),
        "--output", str(score),
        "--failure-ledger-output", str(failures),
    ])
    return rc, json.loads(score.read_text()), json.loads(failures.read_text())


def test_authenticated_archived_original_eight_yields_only_provisional_eight_of_120(
    tmp_path: Path,
):
    sealed, maps = _inputs(tmp_path)
    rc, result, ledger = _run(tmp_path, sealed, maps)
    assert rc == 2  # 3 missing projects still block complete release.
    assert result["schema_version"] == "gpt3-provisional-frozen120-development-v1"
    assert result["status"] == "PARTIAL_OR_BLOCKED"
    assert result["official_score_published"] is False
    assert result["official_four_project_accuracy"] is None
    assert result["source_closed_truth_items"] == 120
    assert result["executed_projects"] == 1
    assert result["executed_denominator"] == 27
    assert result["unexecuted_denominator"] == 93
    assert result["matched_within_tolerance"] == 8
    assert result["observed_accuracy"] == pytest.approx(8/27)
    assert result["coverage_accuracy"] == pytest.approx(8/120)
    assert result["development_accuracy"] == pytest.approx(8/120)
    assert result["precision_adjusted_accuracy"] is None
    assert result["execution_coverage"] == pytest.approx(27/120)
    assert result["missed"] == 19
    assert len(ledger["failure_items"]) == 19
    assert all(row["state"] == "MISSED" for row in ledger["failure_items"])
    assert len(ledger["not_executed_items"]) == 93
    assert ledger["unexecuted_denominator"] == 93
    assert {row["state"] for row in ledger["not_executed_items"]} == {"NOT_EXECUTED"}
    assert all(row["produced_quantity_id"] is None for row in ledger["not_executed_items"])
    assert len(ledger["missing_execution_project_ids"]) == 3


def test_missing_all_source_runs_never_yield_a_claimed_score(tmp_path: Path):
    sealed, maps = _inputs(tmp_path, with_seal=False, with_map=False)
    rc, result, ledger = _run(tmp_path, sealed, maps)
    assert rc == 2
    assert result["status"] == "PARTIAL_OR_BLOCKED"
    assert result["executed_denominator"] == 0
    assert result["unexecuted_denominator"] == 120
    assert result["matched_within_tolerance"] == 0
    assert result["development_accuracy"] is None
    assert result["coverage_accuracy"] is None
    assert result["official_score_published"] is False
    assert ledger["failure_items"] == []
    assert len(ledger["not_executed_items"]) == 120


def test_existing_seal_without_exact_identity_map_refuses_provisional_score(
    tmp_path: Path,
):
    sealed, maps = _inputs(tmp_path, with_map=False)
    with pytest.raises(ValueError, match="unchanged frozen scorer rejected"):
        _run(tmp_path, sealed, maps)
    assert not (tmp_path / "score.json").exists()
    assert not (tmp_path / "failures.json").exists()


def test_tampered_sealed_receipt_must_not_be_counted(tmp_path: Path):
    sealed, maps = _inputs(tmp_path)
    path = sealed / f"{LOT16}.json"
    data = json.loads(path.read_text())
    data["quantities"][0]["value"] = 999999
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="unchanged frozen scorer rejected"):
        _run(tmp_path, sealed, maps)
    assert not (tmp_path / "score.json").exists()


def test_provisional_wrapper_never_overwrites_source_or_prior_customer_artifact(
    tmp_path: Path,
):
    sealed, maps = _inputs(tmp_path)
    customer = tmp_path / "customer.json"
    customer.write_text('{"previous_signed_customer":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="provisional output must be new"):
        live.main([
            "--sealed-dir", str(sealed),
            "--identity-map-dir", str(maps),
            "--output", str(customer),
            "--failure-ledger-output", str(tmp_path / "ledger.json"),
        ])
    assert customer.read_text() == '{"previous_signed_customer":true}'


def test_provisional_wrapper_rejects_output_under_immutable_truth(tmp_path: Path):
    sealed, maps = _inputs(tmp_path)
    with pytest.raises(ValueError, match="provisional output must be new"):
        live.main([
            "--sealed-dir", str(sealed),
            "--identity-map-dir", str(maps),
            "--output", str(live._FROZEN_ROOT / "unwanted-score.json"),
            "--failure-ledger-output", str(tmp_path / "ledger.json"),
        ])


def test_provisional_wrapper_rejects_alt_frozen_truth_root(tmp_path):
    sealed, maps = _inputs(tmp_path)
    fake_root = tmp_path / "altered-source-truth"
    fake_root.mkdir()
    with pytest.raises(ValueError, match="immutable Full Plan V2"):
        live.main([
            "--root", str(fake_root),
            "--sealed-dir", str(sealed),
            "--identity-map-dir", str(maps),
            "--output", str(tmp_path / "score.json"),
            "--failure-ledger-output", str(tmp_path / "ledger.json"),
        ])
    assert not (tmp_path / "score.json").exists()
