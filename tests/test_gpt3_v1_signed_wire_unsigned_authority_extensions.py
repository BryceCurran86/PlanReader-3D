"""Source-closed V1 signed JSON must not accept unsealed added authority."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    sealed_source_closed_run_from_dict,
    seal_source_closed_run,
)
from tests.test_source_closed_run_export import quantity, trace


ARCHIVE = Path(
    "docs/engineering/lot16_original_signed_eight_row_20261015/"
    "production/source_sealed_run.json"
)


def _valid_wire():
    q = quantity()
    return seal_source_closed_run(
        [q], project_id="project-a",
        traces_by_quantity_id={q.quantity_id: trace()},
    ).to_dict()


@pytest.mark.parametrize("field,value", [
    ("snapshot_id", "source_snapshot_forged"),
    ("decision_scope_id", "wall-source:page-3"),
    ("trade_category", "doors"),
    ("benchmark_score_granted", True),
    ("customer_approved", True),
    ("source_manifest_verified", True),
    ("producer_source_sha256", "a" * 64),
    ("quantity_count", 1),
])
def test_top_level_v1_unknown_fields_never_become_signed_authority(field, value):
    wire = _valid_wire()
    original = wire["fingerprint"]
    wire[field] = value
    assert wire["fingerprint"] == original
    with pytest.raises(SourceClosedRunConflictError, match="unsigned additional wire"):
        sealed_source_closed_run_from_dict(wire)


@pytest.mark.parametrize("field,value", [
    ("snapshot_id", "source_snapshot_forged"),
    ("decision_scope_id", "wall-source:page-3"),
    ("source_scope_record_id", "opening-host:invented"),
    ("host_binding_record_id", "forged"),
    ("verified_trade", "tiling"),
    ("benchmark_matched", True),
    ("commercial_customer_approved", True),
    ("v2_quantity_fingerprint", "f" * 64),
])
def test_signed_row_rejects_extra_scope_authority_even_when_fingerprint_is_unchanged(
    field, value,
):
    wire = _valid_wire()
    original_row = wire["quantities"][0]["fingerprint"]
    original_parent = wire["fingerprint"]
    wire["quantities"][0][field] = value
    assert wire["quantities"][0]["fingerprint"] == original_row
    assert wire["fingerprint"] == original_parent
    with pytest.raises(SourceClosedRunConflictError, match="unsigned additional wire"):
        sealed_source_closed_run_from_dict(wire)


def test_unsigned_nested_scope_extension_in_v1_quantity_is_not_silent():
    original = _valid_wire()
    bad = deepcopy(original)
    bad["quantities"][0]["source_scope"] = {
        "snapshot_id": "source_snapshot_claimed",
        "decision_scope_id": "source_scope_claimed",
        "signed": True,
    }
    with pytest.raises(SourceClosedRunConflictError, match="unsigned additional wire"):
        sealed_source_closed_run_from_dict(bad)


def test_missing_original_signed_v1_field_rejected_before_normalized_fingerprint():
    wire = _valid_wire()
    del wire["quantities"][0]["source_page"]
    with pytest.raises(SourceClosedRunConflictError, match="unsigned additional wire"):
        sealed_source_closed_run_from_dict(wire)


def test_unmodified_original_lot16_eight_signed_receipts_still_verify_byte_for_byte():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    loaded = sealed_source_closed_run_from_dict(payload)
    assert len(loaded.quantities) == 8
    assert loaded.fingerprint == payload["fingerprint"]
    assert loaded.to_dict() == payload
    assert loaded.fingerprint == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )


def test_signed_v1_json_remains_deterministic_after_strict_key_validation():
    wire = _valid_wire()
    expected = sealed_source_closed_run_from_dict(wire)
    clone = sealed_source_closed_run_from_dict(expected.to_dict())
    assert clone.fingerprint == expected.fingerprint
    assert clone.run_id == expected.run_id
    assert clone.to_dict() == wire
