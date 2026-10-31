"""GPT3 — legacy typed JobHub rows cannot invent missing source authority.

Source-neutral regression. This test creates no original PDF, FIRM issuer receipt
or customer-approved benchmark quantity.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubPayload,
    PlanReaderJobHubQuantityRow,
    PublishMode,
    build_jobhub_payload,
    run_jobhub_publish_preflight,
)


PROJECT = {"project_id": "synthetic-project", "identity_confirmed": True}
REVISION = {"revision_hash": "synthetic-revision"}


def _source_row():
    return {
        "quantity_id": "synthetic-physical-Q1",
        "description": "Synthetic figured wall",
        "value": 12.75,
        "unit": "m2",
        "trade": "plastering",
        "source_type": "documented_dimension",
        "authority_status": "firm",
        "is_publishable": True,
        "source_page": 3,
        "dimension_text_id": "synthetic-dimension",
        "revision_hash": "synthetic-revision",
    }


def _preflight(rows, mode=PublishMode.COMMERCIAL_PUBLISH):
    return run_jobhub_publish_preflight(
        rows, project_identity=PROJECT, drawing_revision=REVISION, mode=mode,
    )


@pytest.mark.parametrize("which", ["source_type", "authority_status", "both"])
def test_missing_source_fields_cannot_be_hydrated_into_firm_commercial_rows(which):
    bad = _source_row()
    for key in ("source_type", "authority_status"):
        if which == key or which == "both":
            del bad[key]
    before = deepcopy(bad)
    # A raw mapping is already rejected at the final commercial preflight.
    assert _preflight([bad]).is_valid is False
    # A typed hydration must not erase that same negative evidence.
    with pytest.raises(ValueError, match="requires explicit source_type and authority_status"):
        PlanReaderJobHubQuantityRow.from_dict(bad)
    with pytest.raises(ValueError, match="requires explicit source_type and authority_status"):
        PlanReaderJobHubPayload.from_dict({"quantities": [bad]})
    assert bad == before


@pytest.mark.parametrize(("field", "invalid"), [
    ("source_type", None),
    ("source_type", ""),
    ("source_type", "  "),
    ("source_type", True),
    ("source_type", 1),
    ("source_type", ["documented_dimension"]),
    ("authority_status", None),
    ("authority_status", ""),
    ("authority_status", "\t"),
    ("authority_status", True),
    ("authority_status", 1),
    ("authority_status", ["firm"]),
])
def test_false_source_receipt_types_cannot_mint_typed_firm(field, invalid):
    bad = _source_row()
    bad[field] = invalid
    snapshot = deepcopy(bad)
    with pytest.raises(ValueError, match="requires explicit source_type and authority_status"):
        PlanReaderJobHubQuantityRow.from_dict(bad)
    assert bad == snapshot


def test_absent_legacy_draft_receipts_remain_hydratable_but_blocked():
    legacy = _source_row()
    legacy["is_publishable"] = False
    legacy.pop("source_type")
    legacy.pop("authority_status")
    before = deepcopy(legacy)
    first = PlanReaderJobHubQuantityRow.from_dict(legacy)
    second = PlanReaderJobHubQuantityRow.from_dict(legacy)
    assert first == second
    assert first.source_type == "blocked"
    assert first.authority_status == "blocked"
    assert first.is_publishable is False
    assert _preflight([first]).is_valid is False
    draft = build_jobhub_payload(
        [first], PROJECT, REVISION, publish_mode=PublishMode.DRAFT_PUBLISH,
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert draft.is_commercial_ready is False
    assert draft.quantities[0].source_type == "blocked"
    assert draft.quantities[0].authority_status == "blocked"
    assert legacy == before


def test_partially_present_unpublished_receipt_blocks_both_axes():
    for missing in ("source_type", "authority_status"):
        legacy = _source_row()
        legacy["is_publishable"] = False
        legacy.pop(missing)
        row = PlanReaderJobHubQuantityRow.from_dict(legacy)
        assert (row.source_type, row.authority_status) == ("blocked", "blocked")


def test_complete_synthetic_source_receipt_retains_real_legacy_consumer_path():
    complete = _source_row()
    before = deepcopy(complete)
    hydrated = PlanReaderJobHubQuantityRow.from_dict(complete)
    assert hydrated.source_type == "documented_dimension"
    assert hydrated.authority_status == "firm"
    assert hydrated.is_publishable is True
    assert _preflight([complete]).is_valid is True
    assert _preflight([hydrated]).is_valid is True
    assert _preflight([hydrated]).publishable_row_count == 1

    payload = build_jobhub_payload(
        [hydrated], PROJECT, REVISION,
        publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        created_by="synthetic-estimator", created_at="2026-01-01T00:00:00+00:00",
    )
    assert payload.is_commercial_ready is True
    assert len(payload.quantities) == 1
    assert payload.quantities[0].authority_status == "firm"
    assert PlanReaderJobHubQuantityRow.from_dict(hydrated.to_dict()).to_dict() == hydrated.to_dict()
    assert complete == before


@pytest.mark.parametrize("explicit_receipts", [
    {},
    {"source_type": "documented_dimension"},
    {"authority_status": "firm"},
])
def test_direct_typed_legacy_construction_without_both_receipts_cannot_be_sold(explicit_receipts):
    # The dataclass constructor is a separate entry seam from from_dict.
    # A source page and dimension text alone do not prove FIRM authority.
    row = PlanReaderJobHubQuantityRow(
        quantity_id="synthetic-direct-without-authority",
        description="Unverified direct legacy wall",
        value=12.75,
        unit="m2",
        trade="painting",
        source_page=3,
        dimension_text_id="synthetic-dimension",
        revision_hash=REVISION["revision_hash"],
        is_publishable=True,
        **explicit_receipts,
    )
    before = deepcopy(row.to_dict())
    assert row.source_type == explicit_receipts.get("source_type", "blocked")
    assert row.authority_status == explicit_receipts.get("authority_status", "blocked")
    for candidate in (row, row.to_dict(), PlanReaderJobHubQuantityRow.from_dict(row.to_dict())):
        result = _preflight([candidate])
        assert result.is_valid is False
        assert result.publishable_row_count == 0
        assert result.blocked_row_count == 1
        with pytest.raises(ValueError, match="Cannot build commercial payload"):
            build_jobhub_payload(
                [candidate], PROJECT, REVISION,
                publish_mode=PublishMode.COMMERCIAL_PUBLISH,
            )
    assert row.to_dict() == before


def test_direct_typed_legacy_explicit_source_and_firm_receipts_keep_customer_path():
    row = PlanReaderJobHubQuantityRow(
        quantity_id="synthetic-direct-fully-owned",
        description="Synthetic documented wall",
        value=12.75,
        unit="m2",
        trade="painting",
        source_type="documented_dimension",
        authority_status="firm",
        source_page=3,
        dimension_text_id="synthetic-dimension",
        revision_hash=REVISION["revision_hash"],
        is_publishable=True,
    )
    before = deepcopy(row.to_dict())
    assert _preflight([row]).is_valid is True
    payload = build_jobhub_payload(
        [row], PROJECT, REVISION,
        publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert payload.is_commercial_ready is True
    assert payload.quantities[0].to_dict() == before
    assert row.to_dict() == before


def test_unclaimed_direct_legacy_row_remains_draft_only():
    row = PlanReaderJobHubQuantityRow(
        quantity_id="synthetic-direct-draft",
        description="No original measurement",
        value=4.0,
        unit="m2",
    )
    assert (row.source_type, row.authority_status) == ("blocked", "blocked")
    assert row.is_publishable is False
    draft = build_jobhub_payload(
        [row], PROJECT, REVISION, publish_mode=PublishMode.DRAFT_PUBLISH,
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert draft.is_commercial_ready is False
    assert draft.quantities[0].authority_status == "blocked"
