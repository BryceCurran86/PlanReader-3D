"""A positive original net-wall finish area must never become a measured zero row.

Exercises real source-owned finish/net-wall producer, QuantityEvidence issuer,
and the 21-field customer bridge. Synthetic inputs are not original-source FIRM.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_bound_wall_finish_customer_bridge import (
    bound_wall_finish_record_to_takeoff_row,
    build_bound_wall_finish_rows,
)
from pb_live_wall_finish_quantity_publication import publish_bound_wall_finish_quantity
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_bound_wall_finish_quantity_authority_v1 import (
    _binding,
    _finish_authority,
    _net_authority,
    _producer,
    _selector,
)


def _source_result(area: float):
    binding = _binding("binding-original", "face-original", "wall-original")
    producer = _producer(
        _finish_authority((binding,)),
        _net_authority({"wall-original": area}),
    )
    result = producer.publish(_selector())
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    return result


def _customer(result):
    app = SimpleNamespace(
        resolve_bound_wall_finishes=lambda workspace_id: (result,),
    )
    return build_bound_wall_finish_rows(app, 7, ())


@pytest.mark.parametrize("source_m2", (0.004, 0.0001))
def test_source_positive_but_customer_zero_m2_abstains_without_fabricating_minimum(
    source_m2,
):
    original = _source_result(source_m2)
    record = original.record
    assert record is not None
    quantity = publish_bound_wall_finish_quantity(record)
    assert quantity.abstained is False
    assert quantity.value == source_m2
    assert round(quantity.value, 2) == 0.0

    # The direct real customer adapter must not mint a measured zero row.
    with pytest.raises(ValueError, match="unrepresentable in customer"):
        bound_wall_finish_record_to_takeoff_row(7, record)
    # The batch entrypoint must never expose a partial/zero customer quantity.
    assert _customer(original) == ([], [])
    assert _customer(original) == ([], [])  # deterministic replay
    assert original.record is record
    assert record.quantity_m2 == source_m2
    assert publish_bound_wall_finish_quantity(record).quantity_id == quantity.quantity_id


@pytest.mark.parametrize("source_m2,expected_customer_m2", (
    (0.006, 0.01),
    (12.5, 12.5),
))
def test_representable_positive_source_area_retains_existing_customer_contract(
    source_m2, expected_customer_m2,
):
    original = _source_result(source_m2)
    record = original.record
    assert record is not None
    quantity = publish_bound_wall_finish_quantity(record)
    direct = bound_wall_finish_record_to_takeoff_row(7, record)
    rows, reports = _customer(original)

    assert len(direct) == 21
    assert direct[6] == expected_customer_m2
    assert direct[7] == "m²"
    assert len(rows) == len(reports) == 1
    assert rows[0] == direct
    assert reports[0]["quantity_id"] == quantity.quantity_id
    assert reports[0]["quantity_m2"] == source_m2
    assert reports[0]["record_id"] == record.record_id
    assert record.quantity_m2 == source_m2


def test_positive_small_area_source_record_identity_survives_input_replay():
    first = _source_result(0.004)
    second = _source_result(0.004)
    assert first.record is not None and second.record is not None
    assert first.record.record_id == second.record.record_id
    assert publish_bound_wall_finish_quantity(first.record).quantity_id == (
        publish_bound_wall_finish_quantity(second.record).quantity_id
    )
    assert _customer(first) == _customer(second) == ([], [])
