"""Strict shared signed-evidence reader: no non-JSON numbers or duplicate IDs.

This is an ingest-only guard. Fixtures are synthetic; they authenticate no
original source bytes, quantities, or Full Plan V2 benchmark identities.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as four
from tools import report_gpt3_selected_two_project_original_evidence as selected


@pytest.mark.parametrize("number", [
    "NaN", "Infinity", "-Infinity", "1e10000", "-1e10000",
])
def test_nonfinite_signed_numeric_literal_cannot_reach_evidence_consumer(
    tmp_path: Path, number: str,
):
    path = tmp_path / "sealed.json"
    raw = '{"project_id":"genuine-address","quantities":[{"area":' + number + '}]}'
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="non-finite"):
        four._json_object(path)
    with pytest.raises(ValueError, match="non-finite"):
        selected._json_object(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("number", [
    "NaN", "Infinity", "-Infinity", "1e10000",
])
def test_nonfinite_nested_customer_rows_fail_before_customer_projection(
    tmp_path: Path, number: str,
):
    path = tmp_path / "customer.json"
    path.write_text(
        '[{"quantity_id":"original-q1","projection":{"source_value":'
        + number + '}}]', encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-finite"):
        four._json_customer_rows(path)
    with pytest.raises(ValueError, match="non-finite"):
        selected._json_customer_rows(path)


@pytest.mark.parametrize("signed_payload", [
    '{"quantity_id":"q1","sources":{"original_sha":"a","original_sha":"b"}}',
    '[{"quantity_id":"q1","provenance":{"source":"a","source":"b"}}]',
])
def test_duplicate_source_key_nested_inside_evidence_or_customer_refused(
    tmp_path: Path, signed_payload: str,
):
    path = tmp_path / "signed.json"
    path.write_text(signed_payload, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        four._read_json_without_duplicate_keys(path)
    with pytest.raises(ValueError, match="duplicate key"):
        selected._json_object(path) if signed_payload.startswith("{") else selected._json_customer_rows(path)


@pytest.mark.parametrize("oversized", [
    "9" * 400, "-" + "9" * 400,
])
def test_large_signed_integer_rejected_without_conversion_or_rounding(
    tmp_path: Path, oversized: str,
):
    path = tmp_path / "original.json"
    path.write_text('{"source_numeric_id":' + oversized + '}', encoding="utf-8")
    with pytest.raises(ValueError, match="out-of-range"):
        four._json_object(path)


def test_excessive_array_or_object_depth_rejected(tmp_path: Path):
    path = tmp_path / "original.json"
    path.write_text('{"receipt":' + "[" * 513 + "0" + "]" * 513 + "}", encoding="utf-8")
    with pytest.raises(ValueError, match="nesting"):
        four._json_object(path)


def test_malformed_escape_does_not_mint_customer_row(tmp_path: Path):
    path = tmp_path / "customer.json"
    path.write_text('[{"quantity_id":"q1","note":"bad\\q"}]', encoding="utf-8")
    with pytest.raises(ValueError):
        four._json_customer_rows(path)


def test_exact_valid_numbers_boolean_null_and_escaped_brackets_remain_unchanged(
    tmp_path: Path,
):
    path = tmp_path / "signed.json"
    evidence = {
        "original_numeric_id": 12345678901234567890,
        "area": 1.25,
        "small": 0.00000001,
        "admitted": True,
        "missing": None,
        "note": '[real] {source} "quoted" \\ literal',
        "labels": ["BED 1", "BED 2", "BED 3"],
    }
    raw = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()
    assert four._json_object(path) == evidence
    assert selected._json_object(path) == evidence
    assert path.read_bytes() == before


def test_valid_customer_projection_and_shared_ingress_identity(tmp_path: Path):
    assert selected._json_object is four._json_object
    assert selected._json_customer_rows is four._json_customer_rows
    path = tmp_path / "customer.json"
    rows = [
        {"quantity_id": "original-firm-id", "unit": "m2", "area": 12.64,
         "notes": "Source [literal] {provenance}"},
    ]
    path.write_text(json.dumps(rows, allow_nan=False), encoding="utf-8")
    assert four._json_customer_rows(path) == rows
    assert selected._json_customer_rows(path) == rows
