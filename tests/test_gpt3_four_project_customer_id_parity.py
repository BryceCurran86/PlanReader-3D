"""Source-neutral GPT3 four-project customer quantity-ID compatibility gates.

These are diagnostic reader tests: they cannot mint signed quantities, grant
approval, change a commercial projection or publish benchmark accuracy.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import report_gpt3_four_project_evidence as report


def _read_rows(tmp_path, rows):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return report._json_customer_rows(path)


@pytest.mark.parametrize(
    "row",
    [
        {"quantity_id": "q-a"},
        {"quantity_id": "q-a", "notes": "human estimator note"},
        {"commercial_projection_provenance": {"quantity": {"quantity_id": "q-a"}}},
        {"quantity_id": None, "commercial_projection_provenance": {
            "quantity": {"quantity_id": "q-a"}
        }},
        {"quantity_id": "", "commercial_projection_provenance": {
            "quantity": {"quantity_id": "q-a"}
        }},
        {"notes": json.dumps({"adapter": "commercial_takeoff",
                              "quantity": {"quantity_id": "q-a"}})},
        {"quantity_id": "", "notes": json.dumps({
            "adapter": "commercial_takeoff", "quantity": {"quantity_id": "q-a"}
        })},
    ],
)
def test_diagnostic_reader_preserves_authoritative_v1_identity_sources(tmp_path, row):
    assert _read_rows(tmp_path, [row]) == [row]
    assert report._customer_quantity_id(row) == "q-a"


@pytest.mark.parametrize(
    "row",
    [
        {},
        {"quantity_id": ""},
        {"quantity_id": None},
        {"quantity_id": False},
        {"quantity_id": 17},
        {"quantity_id": []},
        {"notes": "manual estimator only"},
        {"notes": json.dumps({"adapter": "not-commercial", "quantity": {
            "quantity_id": "q-a"
        }})},
        {"commercial_projection_provenance": {"quantity": {}}},
        {"commercial_projection_provenance": {"quantity": {"quantity_id": ""}}},
    ],
)
def test_diagnostic_reader_rejects_missing_or_untyped_identity(tmp_path, row):
    with pytest.raises((RuntimeError, ValueError)):
        _read_rows(tmp_path, [row])


def _receipt(ids):
    sealed = SimpleNamespace(
        project_id="synthetic-only",
        quantities=tuple(
            SimpleNamespace(quantity_id=qid, abstained=False) for qid in ids
        ),
    )
    verified = SimpleNamespace(
        project_id="synthetic-only",
        sealed_quantity_count=len(ids),
        valid_quantity_count=len(ids),
        abstained_quantity_count=0,
        customer_row_count=len(ids),
        verified_quantity_ids=tuple(ids),
    )
    return sealed, verified


def test_bijection_handles_mixed_id_storage_without_rewriting_rows():
    sealed, verified = _receipt(("q-a", "q-b", "q-c"))
    rows = [
        {"quantity_id": "q-a"},
        {"commercial_projection_provenance": {"quantity": {
            "quantity_id": "q-b"
        }}},
        {"notes": json.dumps({"adapter": "commercial_takeoff", "quantity": {
            "quantity_id": "q-c"
        }})},
    ]
    before = deepcopy(rows)
    assert report._verify_customer_counts(sealed, verified, rows) is None
    assert rows == before


def test_duplicate_same_id_across_direct_and_persisted_notes_is_rejected():
    sealed, verified = _receipt(("q-a", "q-b"))
    rows = [
        {"quantity_id": "q-a"},
        {"notes": json.dumps({"adapter": "commercial_takeoff", "quantity": {
            "quantity_id": "q-a"
        }})},
    ]
    with pytest.raises(ValueError, match="cardinality or identity mismatch"):
        report._verify_customer_counts(sealed, verified, rows)


def test_wrong_id_in_persisted_notes_fails_signed_bijection():
    sealed, verified = _receipt(("q-a",))
    rows = [{"notes": json.dumps({
        "adapter": "commercial_takeoff",
        "quantity": {"quantity_id": "unrelated-q"},
    })}]
    with pytest.raises(ValueError, match="cardinality or identity mismatch"):
        report._verify_customer_counts(sealed, verified, rows)


def test_archived_eight_row_customer_v1_still_matches_sealed_id_set():
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from pb_customer_output_verification import verify_sealed_customer_output

    root = (
        Path(__file__).resolve().parents[1]
        / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    )
    sealed = sealed_source_closed_run_from_dict(json.loads(
        (root / "source_sealed_run.json").read_text(encoding="utf-8")
    ))
    rows = report._json_customer_rows(root / "verified_customer_rows.json")
    verified = verify_sealed_customer_output(sealed, rows)
    assert len(rows) == 8
    assert report._verify_customer_counts(sealed, verified, rows) is None
