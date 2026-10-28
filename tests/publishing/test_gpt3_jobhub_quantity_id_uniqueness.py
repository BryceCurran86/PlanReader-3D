"""Fail-closed physical quantity identity at the actual JobHub payload builder.

Source-neutral commercial/draft consumer regressions only. These tests do not
authenticate original drawings, sign quantities or alter frozen V2 truth.
"""
from __future__ import annotations

from itertools import permutations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubQuantityRow,
    PublishMode,
    build_jobhub_payload,
    run_jobhub_publish_preflight,
)
from pb_takeoff_output_authority import TakeoffSourceType


IDENTITY = {"project_id": "synthetic-project", "identity_confirmed": True}
REVISION = {"revision_hash": "synthetic-source-revision"}


def _row(quantity_id="Q-1", **changes):
    data = {
        "quantity_id": quantity_id,
        "description": "Source-neutral measured wall",
        "value": 12.0,
        "unit": "m²",
        "trade": "painting",
        "source_type": TakeoffSourceType.DOCUMENTED_DIMENSION.value,
        "authority_status": AuthorityStatus.FIRM.value,
        "source_page": 1,
        "dimension_text_id": "synthetic-dimension",
        "revision_hash": REVISION["revision_hash"],
        "is_publishable": True,
    }
    data.update(changes)
    return PlanReaderJobHubQuantityRow(**data)


def _preflight(rows, mode=PublishMode.COMMERCIAL_PUBLISH):
    return run_jobhub_publish_preflight(
        rows, IDENTITY, REVISION, mode=mode
    )


def _customer_payload(rows, mode=PublishMode.COMMERCIAL_PUBLISH):
    return build_jobhub_payload(
        rows, IDENTITY, REVISION,
        created_by="Synthetic Estimator",
        publish_mode=mode,
    )


@pytest.mark.parametrize("serialized", [False, True])
def test_two_distinct_quantities_on_same_source_page_remain_commercial(serialized):
    rows = [_row("Q-1"), _row("Q-2", value=3.5)]
    if serialized:
        rows = [row.to_dict() for row in rows]
    for order in permutations(rows):
        result = _preflight(order)
        assert result.is_valid
        assert result.publishable_row_count == 2
        assert result.blocked_row_count == 0
        payload = _customer_payload(order)
        assert payload.is_commercial_ready is True
        assert len(payload.quantities) == 2
        assert {row.quantity_id for row in payload.quantities} == {"Q-1", "Q-2"}
        assert payload.to_dict()["is_commercial_ready"] is True


@pytest.mark.parametrize("serialized", [False, True])
@pytest.mark.parametrize("alias", ["Q-1", " Q-1 ", "\tQ-1\n"])
def test_duplicate_physical_identity_blocks_real_commercial_payload(serialized, alias):
    rows = [
        _row("Q-1"),
        _row(alias, description="Conflicting second line", value=22.0,
             dimension_text_id="different-synthetic-dimension"),
    ]
    if serialized:
        rows = [row.to_dict() for row in rows]
    for order in permutations(rows):
        result = _preflight(order)
        assert not result.is_valid
        assert result.publishable_row_count == 1
        assert result.blocked_row_count == 1
        assert any("duplicate physical quantity_id" in reason
                   for reason in result.blocking_reasons)
        with pytest.raises(ValueError, match="Cannot build commercial payload"):
            _customer_payload(order)


@pytest.mark.parametrize("bad_id", ["", "  ", None, 42])
@pytest.mark.parametrize("serialized", [False, True])
def test_missing_or_nonstring_physical_identity_cannot_be_sold(bad_id, serialized):
    row = _row(bad_id)
    data = row.to_dict() if serialized else row
    result = _preflight([data])
    assert not result.is_valid
    assert result.publishable_row_count == 0
    assert result.blocked_row_count == 1
    assert any("missing stable physical quantity_id" in reason
               for reason in result.blocking_reasons)
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        _customer_payload([data])


def test_duplicate_id_is_not_cured_by_different_authority_or_fingerprint():
    first = _row("Q-1")
    second = _row(
        "Q-1", source_type=TakeoffSourceType.USER_APPROVED.value,
        authority_status=AuthorityStatus.USER_APPROVED.value,
        approved_by="Synthetic Estimator",
        description="Estimator-approved second claim",
    )
    assert first.compute_row_fingerprint() != second.compute_row_fingerprint()
    result = _preflight([first, second])
    assert not result.is_valid
    assert result.blocked_row_count == 1
    with pytest.raises(ValueError, match="duplicate physical quantity_id"):
        _customer_payload([first, second])


def test_draft_retains_duplicate_candidate_with_explicit_noncommercial_warning():
    rows = [_row("Q-1"), _row(" Q-1 ", value=7.0), _row("  ")]
    result = _preflight(rows, PublishMode.DRAFT_PUBLISH)
    assert result.is_valid
    assert any("duplicate physical quantity_id" in w for w in result.warnings)
    assert any("missing stable physical quantity_id" in w for w in result.warnings)
    payload = _customer_payload(rows, PublishMode.DRAFT_PUBLISH)
    assert payload.is_commercial_ready is False
    assert payload.publish_mode == PublishMode.DRAFT_PUBLISH.value
    assert len(payload.quantities) == 3
    assert any("duplicate physical quantity_id" in w for w in payload.warnings)
    assert any("missing stable physical quantity_id" in w for w in payload.warnings)


def test_duplicate_identity_does_not_remove_other_valid_quantity():
    rows = [_row("A"), _row("B"), _row("A", value=2.0), _row("C")]
    result = _preflight(rows)
    assert not result.is_valid
    assert result.publishable_row_count == 3
    assert result.blocked_row_count == 1
    assert any("duplicate physical quantity_id" in reason
               for reason in result.blocking_reasons)
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        _customer_payload(rows)
