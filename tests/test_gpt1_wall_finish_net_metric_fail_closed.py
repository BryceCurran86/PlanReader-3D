"""Net wall source m² must be native, finite and complete before finish FIRM.

These tests exercise the actual source-bound wall-finish producer and its
QuantityEvidence/customer bridge; no synthetic result grants original PDF
measurement authority or a frozen V2 accuracy match.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_bound_wall_finish_customer_bridge import build_bound_wall_finish_rows
from pb_bound_wall_finish_quantity_authority import (
    FINISH_QUANTITY_INVALID_AREA,
    FINISH_QUANTITY_RESOLVED,
)
from pb_live_wall_finish_quantity_publication import publish_bound_wall_finish_quantity
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import NetWallBooleanUnionSelector
from tests.test_bound_wall_finish_quantity_authority_v1 import (
    DOC, REV, SHA, SNAP, PAGE, SCOPE, TRADE,
    _binding, _finish_authority, _net_authority, _producer, _selector,
)


def _net_record(net, wall_id="wall-1"):
    selector = NetWallBooleanUnionSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
        physical_wall_id=wall_id, trade_scope_id=TRADE,
    )
    return net.resolve(selector).record


def _customer(result):
    app = SimpleNamespace(
        resolve_bound_wall_finishes=lambda workspace_id: (result,),
    )
    return build_bound_wall_finish_rows(app, 7, ())


@pytest.mark.parametrize("bad_area", (
    True, False, "12.5", " 12.5 ", None, object(),
    float("nan"), float("inf"), float("-inf"), 0.0, -0.5,
    10 ** 400,
))
def test_original_net_wall_invalid_metric_abstains_before_finish_customer(bad_area):
    binding = _binding("binding-1", "face-1", "wall-1")
    net = _net_authority({"wall-1": bad_area})
    source_record = _net_record(net)
    original_area = source_record.net_area_m2

    producer = _producer(_finish_authority((binding,)), net)
    result = producer.publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_INVALID_AREA in result.reason_codes
    assert producer.authority().resolve(_selector()) == result
    assert _net_record(net) is source_record
    assert source_record.net_area_m2 is original_area  # no source mutation
    assert _customer(result) == ([], [])


def test_later_invalid_face_abstains_entire_original_finish_universe():
    bindings = (
        _binding("binding-a", "face-a", "wall-1"),
        _binding("binding-z", "face-z", "wall-2"),
    )
    net = _net_authority({"wall-1": 5.25, "wall-2": "3.5"})
    result = _producer(_finish_authority(bindings), net).publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_INVALID_AREA in result.reason_codes
    assert _customer(result) == ([], [])


def test_two_finite_original_net_areas_cannot_overflow_finish_quantity():
    bindings = (
        _binding("binding-a", "face-a", "wall-1"),
        _binding("binding-z", "face-z", "wall-2"),
    )
    net = _net_authority({"wall-1": 1e308, "wall-2": 1e308})
    producer = _producer(_finish_authority(bindings), net)

    result = producer.publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_INVALID_AREA in result.reason_codes
    assert "aggregate_net_finish_area_not_finite" in result.reason_codes
    assert producer.authority().resolve(_selector()) == result
    assert _customer(result) == ([], [])


def test_native_positive_source_net_area_still_reaches_real_customer_bridge():
    b1 = _binding("binding-a", "face-a", "wall-1")
    b2 = _binding("binding-b", "face-b", "wall-2")
    net = _net_authority({"wall-1": 2.25, "wall-2": 3.5})
    first = _producer(_finish_authority((b1, b2)), net).publish(_selector())
    reversed_result = _producer(
        _finish_authority((b2, b1)), net,
    ).publish(_selector())

    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.reason_codes == (FINISH_QUANTITY_RESOLVED,)
    assert first.record is not None and reversed_result.record is not None
    assert first.record.record_id == reversed_result.record.record_id
    assert first.record.quantity_m2 == 5.75
    quantity = publish_bound_wall_finish_quantity(first.record)
    assert quantity.value == 5.75
    assert quantity.abstained is False
    assert quantity.input_entity_ids == first.record.physical_surface_ids

    rows, records = _customer(first)
    assert len(rows) == len(records) == 1
    assert rows[0][6] == 5.75
    assert records[0]["quantity_id"] == quantity.quantity_id
    assert records[0]["record_id"] == first.record.record_id
