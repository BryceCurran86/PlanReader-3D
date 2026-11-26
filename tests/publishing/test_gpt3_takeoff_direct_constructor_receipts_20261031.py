"""GPT3: direct TakeoffOutputRow construction cannot mint source/FIRM evidence.

Synthetic customer-boundary tests. No original PDF, true FIRM issuer, signed
archive, V2 benchmark truth or verified physical geometry is used.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_takeoff_output_authority import (
    TakeoffOutputRow, create_takeoff_output_row,
)
from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubQuantityRow, PublishMode,
    build_jobhub_payload, run_jobhub_publish_preflight,
)


PROJECT = {"project_id": "synthetic-original-scope", "identity_confirmed": True}
REVISION = {"revision_hash": "synthetic-revision"}


def _direct(**receipts):
    return TakeoffOutputRow(
        quantity_id="synthetic-typed-area-1",
        description="Synthetic documented wall quantity",
        value=12.75,
        unit="m2",
        trade="painting",
        source_page=3,
        dimension_text_id="synthetic-dimension-id",
        revision_hash=REVISION["revision_hash"],
        is_publishable=True,
        **receipts,
    )


def _preflight(row):
    return run_jobhub_publish_preflight(
        [row], PROJECT, REVISION, mode=PublishMode.COMMERCIAL_PUBLISH,
    )


@pytest.mark.parametrize("receipts", [
    {},
    {"source_type": "documented_dimension"},
    {"authority_status": "firm"},
])
def test_missing_modern_constructor_receipt_cannot_become_jobhub_firm(receipts):
    # These fake source-page / figured-ID tokens cannot authenticate omitted
    # source_type or authority_status; the typed branch sees only defaults.
    row = _direct(**receipts)
    before = deepcopy(row.to_dict())
    assert row.source_type == receipts.get("source_type", "blocked")
    assert row.authority_status == receipts.get("authority_status", "blocked")
    for candidate in (
        row,
        row.to_dict(),
        TakeoffOutputRow.from_dict(row.to_dict()),
        PlanReaderJobHubQuantityRow.from_takeoff_output_row(row),
    ):
        verdict = _preflight(candidate)
        assert verdict.is_valid is False
        assert verdict.publishable_row_count == 0
        assert verdict.blocked_row_count == 1
        with pytest.raises(ValueError, match="Cannot build commercial payload"):
            build_jobhub_payload(
                [candidate], PROJECT, REVISION,
                publish_mode=PublishMode.COMMERCIAL_PUBLISH,
            )
    assert row.to_dict() == before


def test_direct_unclaimed_takeoff_remains_a_draft_not_saleable():
    row = TakeoffOutputRow(
        quantity_id="synthetic-draft-1",
        description="No source dimension",
        value=4.25,
        unit="m2",
    )
    assert (row.source_type, row.authority_status) == ("blocked", "blocked")
    assert row.is_publishable is False
    before = deepcopy(row.to_dict())
    draft = build_jobhub_payload(
        [row], PROJECT, REVISION,
        publish_mode=PublishMode.DRAFT_PUBLISH,
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert draft.is_commercial_ready is False
    assert draft.quantities[0].source_type == "blocked"
    assert draft.quantities[0].authority_status == "blocked"
    assert row.to_dict() == before


def test_explicit_issuer_owned_modern_constructor_keeps_typed_customer_positive():
    original = _direct(source_type="documented_dimension", authority_status="firm")
    before = deepcopy(original.to_dict())
    for row in (original, TakeoffOutputRow.from_dict(original.to_dict())):
        assert _preflight(row).is_valid
        assert _preflight(row).publishable_row_count == 1
        package = build_jobhub_payload(
            [row], PROJECT, REVISION,
            publish_mode=PublishMode.COMMERCIAL_PUBLISH,
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert package.is_commercial_ready is True
        assert len(package.quantities) == 1
        assert package.quantities[0].source_type == "documented_dimension"
        assert package.quantities[0].authority_status == "firm"
        assert row.to_dict() == before
    assert original.to_dict() == before


def test_existing_factory_resolved_documented_dimension_is_not_downgraded():
    # The real factory sets both authority fields explicitly based on its
    # own policy matrix; changing a direct dataclass default must not
    # downgrade that separate caller or manufacture a new FIRM measurement.
    row = create_takeoff_output_row(
        quantity_id="synthetic-factory-area",
        description="Factory policy positive",
        value=12.75,
        unit="m2",
        source_page=3,
        dimension_text_id="synthetic-figured-axis",
        revision_hash=REVISION["revision_hash"],
        current_revision_hash=REVISION["revision_hash"],
    )
    before = deepcopy(row.to_dict())
    assert row.source_type == "documented_dimension"
    assert row.authority_status == "firm"
    assert row.is_publishable is True
    assert _preflight(row).is_valid
    assert row.to_dict() == before
