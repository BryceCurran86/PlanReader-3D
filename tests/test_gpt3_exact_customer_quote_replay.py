"""Quote approval depends on ORIGINAL V1 + ORIGINAL CLIENT RATE, not rehashed JSON."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from tools import gpt3_verified_customer_quote as pricing
from tools.gpt3_replay_client_quote_from_signed_source import (
    verify_client_quote_source_replay, build_quote_replay_report, main,
)
from test_gpt3_verified_customer_quote import fixture


def _inputs(tmp_path):
    signed, customer, rates = fixture()
    quote = pricing.build_verified_customer_quote(signed, customer, rates)
    values = {"sealed": signed, "customers": customer, "rates": rates, "quote": quote}
    paths = {key: tmp_path / f"{key}.json" for key in values}
    for key, value in values.items():
        paths[key].write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return values, paths


def test_exact_archived_eight_original_quote_reconstructs_with_same_customer_rates(tmp_path):
    values, paths = _inputs(tmp_path)
    report = build_quote_replay_report(
        sealed_path=paths["sealed"], customer_path=paths["customers"],
        rate_path=paths["rates"], quote_path=paths["quote"],
    )
    assert report["customer_quote_replay_status"] == "EXACT_SIGNED_V1_CUSTOMER_RATE_REPLAY"
    assert report["signed_quantity_count"] == 8
    assert report["project_id"] == values["sealed"]["project_id"]
    assert report["quote_fingerprint"] == values["quote"]["quote_fingerprint"]
    assert report["official_v2_accuracy"] is None
    assert report["source_authenticated"] is False


def test_forged_source_amount_and_rehashed_quote_are_not_replay_approved():
    signed, customer, rates = fixture()
    actual = pricing.build_verified_customer_quote(signed, customer, rates)
    forged = deepcopy(actual)
    forged["items"][0]["physical_quantity"] = "99"
    data = dict(forged)
    data.pop("quote_fingerprint")
    forged["quote_fingerprint"] = hashlib.sha256(json.dumps(
        data, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="does not reproduce"):
        verify_client_quote_source_replay(signed, customer, rates, forged)


def test_valid_quote_fails_when_original_client_rate_changed():
    signed, customer, rates = fixture()
    quote = pricing.build_verified_customer_quote(signed, customer, rates)
    rates["rates"][0]["material"] = "999.00"
    with pytest.raises(ValueError, match="does not reproduce"):
        verify_client_quote_source_replay(signed, customer, rates, quote)


def test_original_customer_provenance_mismatch_fails_before_quote_matching():
    signed, customer, rates = fixture()
    quote = pricing.build_verified_customer_quote(signed, customer, rates)
    customer[0]["ai_baseline_quantity"] = 999
    with pytest.raises(Exception):
        verify_client_quote_source_replay(signed, customer, rates, quote)


def test_quote_replay_cli_protects_all_original_evidence_and_existing_output(tmp_path):
    values, paths = _inputs(tmp_path)
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest()
              for k, p in paths.items()}
    output = tmp_path / "audit.json"
    args = [
        "--sealed-run", str(paths["sealed"]),
        "--customers", str(paths["customers"]),
        "--client-rates", str(paths["rates"]),
        "--client-quote", str(paths["quote"]),
        "--output", str(output),
    ]
    assert main(args) == 0
    assert json.loads(output.read_text())["publication_status"] == "UNPUBLISHED"
    assert hashes == {k: hashlib.sha256(p.read_bytes()).hexdigest()
                      for k, p in paths.items()}
    with pytest.raises(FileExistsError):
        main(args)
    for p in paths.values():
        args[-1] = str(p)
        with pytest.raises(ValueError, match="protected evidence"):
            main(args)


def test_duplicate_raw_quote_json_keys_rejected_before_replay(tmp_path):
    values, paths = _inputs(tmp_path)
    path = paths["quote"]
    path.write_text(
        path.read_text().replace('"project_id":', '"project_id":"wrong", "project_id":', 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        build_quote_replay_report(
            sealed_path=paths["sealed"], customer_path=paths["customers"],
            rate_path=paths["rates"], quote_path=paths["quote"],
        )
