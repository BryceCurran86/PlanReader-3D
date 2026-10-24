"""A rehashed source-neutral scenario report is not a verified client rate replay."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from test_gpt3_customer_quote_scenarios import fixture, bundle
from tools.gpt3_customer_quote_scenarios import build_scenario_comparison
from tools.gpt3_verify_client_scenario_replay import (
    verify_scenario_source_rate_replay, build_scenario_replay_report, main,
)


def _setup(tmp_path):
    source, customer, rates = fixture()
    book = bundle(rates)
    candidate = build_scenario_comparison(source, customer, book)
    files = {}
    for name, data in (
        ("sealed", source), ("customer", customer),
        ("book", book), ("candidate", candidate),
    ):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        files[name] = path
    return source, customer, book, candidate, files


def test_original_eight_quantity_scenario_bundle_replays_exactly(tmp_path):
    signed, rows, book, candidate, files = _setup(tmp_path)
    result = build_scenario_replay_report(
        sealed_path=files["sealed"], customer_path=files["customer"],
        book_path=files["book"], candidate_path=files["candidate"],
    )
    assert result["scenario_count"] == 2
    assert result["verified_status"] == "EXACT_CLIENT_SCENARIO_RATE_SOURCE_REPLAY"
    assert result["source_run_fingerprint"] == candidate["signed_run_fingerprint"]
    assert result["original_pdf_reverified"] is False
    assert result["budget_approval_granted"] is False
    assert result["official_v2_accuracy"] is None


def test_rehashed_fake_scenario_budget_does_not_pass_original_rate_replay(tmp_path):
    signed, rows, book, candidate, files = _setup(tmp_path)
    fake = deepcopy(candidate)
    fake["comparison"][0]["client_budget_shortfall"] = "0.01"
    body = dict(fake)
    body.pop("comparison_fingerprint")
    fake["comparison_fingerprint"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="do not reproduce"):
        verify_scenario_source_rate_replay(signed, rows, book, fake)


def test_new_rate_scenario_requires_a_new_price_report(tmp_path):
    signed, rows, book, candidate, files = _setup(tmp_path)
    book["scenarios"][0]["client_rates"]["rates"][0]["material"] = "999"
    with pytest.raises(ValueError, match="do not reproduce"):
        verify_scenario_source_rate_replay(signed, rows, book, candidate)


def test_create_only_cli_never_changes_signed_client_inputs(tmp_path):
    signed, rows, book, candidate, files = _setup(tmp_path)
    before = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in files.items()}
    output = tmp_path / "scenario-audit.json"
    args = [
        "--sealed-run", str(files["sealed"]),
        "--customers", str(files["customer"]),
        "--client-scenarios", str(files["book"]),
        "--candidate-report", str(files["candidate"]),
        "--output", str(output),
    ]
    assert main(args) == 0
    assert json.loads(output.read_text())["publication_status"] == "UNPUBLISHED"
    assert before == {name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for name, path in files.items()}
    with pytest.raises(FileExistsError):
        main(args)
    for path in files.values():
        args[-1] = str(path)
        with pytest.raises(ValueError, match="protected evidence"):
            main(args)


def test_duplicate_source_scenario_json_keys_rejected_before_replay(tmp_path):
    signed, rows, book, candidate, files = _setup(tmp_path)
    path = files["book"]
    path.write_text(
        path.read_text().replace(
            '"baseline":', '"baseline":"fake", "baseline":', 1,
        ), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        build_scenario_replay_report(
            sealed_path=files["sealed"], customer_path=files["customer"],
            book_path=files["book"], candidate_path=files["candidate"],
        )
