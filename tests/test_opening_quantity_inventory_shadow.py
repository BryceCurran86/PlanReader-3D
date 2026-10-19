"""Inventory shadow: first gates, signed retention, duplicate/stale rejection."""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_opening_quantity_inventory_shadow import (
    audit_opening_quantity_inventory,
    reject_duplicate_and_stale_quantity_rows,
    retain_signed_quantity_identities,
)
from test_gptmax_lot16_host_frame_gpt1_handoff import ROOT, VIEW, fixture


def test_clean_inventory_preserves_first_gates_and_never_publishes():
    rows, canonical = fixture()
    rows[2]["quantity_id"] = "signed-area-3"
    before = deepcopy((rows, canonical))
    report = audit_opening_quantity_inventory(
        rows,
        canonical,
        VIEW,
        source_root=ROOT,
        expected_physical_opening_ids=["physical-1", "physical-2", "physical-3"],
        required_signed_quantity_ids=["signed-area-3"],
    )
    assert report["shadow_only"] is True
    assert report["measurement_published"] is False
    assert report["customer_seal_granted"] is False
    assert report["opening_count_granted"] is False
    assert report["benchmark_score_granted"] is False
    assert report["identity_gate"]["status"] == "INVENTORY_IDENTITY_CLEAN"
    assert report["signed_retention"]["retained"] is True
    assert report["inventory_completeness"]["status"] == "INVENTORY_COMPLETE"
    assert report["first_gate_counts"]["structural_host_unavailable"] == 1
    assert (rows, canonical) == before


def test_duplicate_physical_opening_blocks_before_gpt1_queue():
    rows, canonical = fixture()
    rows.append(deepcopy(rows[0]))
    report = audit_opening_quantity_inventory(
        rows, canonical, VIEW, source_root=ROOT
    )
    assert report["status"] == "UNPUBLISHED_OPENING_INVENTORY_BLOCKED"
    assert report["gpt1_queue"] is None
    assert any(
        b["blocker"] == "duplicate_physical_opening_identity"
        for b in report["identity_gate"]["blockers"]
    )


def test_duplicate_signed_quantity_id_is_rejected():
    rows, _canonical = fixture()
    rows[1]["quantity_id"] = "same-signed"
    rows[2]["quantity_id"] = "same-signed"
    gate = reject_duplicate_and_stale_quantity_rows(rows, expected_source_root=ROOT)
    assert gate["status"] == "INVENTORY_DUPLICATE_OR_STALE_BLOCKED"
    assert any(b["blocker"] == "duplicate_signed_quantity_identity" for b in gate["blockers"])
    assert gate["publication_allowed"] is False


def test_stale_source_root_on_row_is_rejected():
    rows, _canonical = fixture()
    rows[0]["snapshot_id"] = "foreign-snapshot"
    gate = reject_duplicate_and_stale_quantity_rows(rows, expected_source_root=ROOT)
    assert any(b["blocker"] == "stale_signed_quantity_source_root_mismatch" for b in gate["blockers"])


def test_missing_required_signed_quantity_fails_retention():
    rows, _canonical = fixture()
    rows[2]["quantity_id"] = "other"
    retention = retain_signed_quantity_identities(
        rows, required_signed_quantity_ids=["must-keep"]
    )
    assert retention["retained"] is False
    assert retention["missing_signed_quantity_ids"] == ["must-keep"]


def test_inventory_mismatch_reports_missing_and_unexpected():
    rows, canonical = fixture()
    report = audit_opening_quantity_inventory(
        rows,
        canonical,
        VIEW,
        source_root=ROOT,
        expected_physical_opening_ids=["physical-1", "physical-9"],
    )
    completeness = report["inventory_completeness"]
    assert completeness["status"] == "INVENTORY_MISMATCH"
    assert completeness["missing_physical_opening_ids"] == ["physical-9"]
    assert "physical-2" in completeness["unexpected_physical_opening_ids"]


def test_required_signed_ids_must_themselves_be_unique():
    rows, _canonical = fixture()
    with pytest.raises(ValueError, match="unique"):
        retain_signed_quantity_identities(
            rows, required_signed_quantity_ids=["a", "a"]
        )
