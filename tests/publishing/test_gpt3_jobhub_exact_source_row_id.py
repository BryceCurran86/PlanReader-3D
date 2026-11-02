"""Exact physical takeoff row identity at the real JobHub commercial gate.

Synthetic source-neutral FIRM fixtures test consumer validation only. They do
not establish original PDF FIRM authority or frozen development V2 coverage.
"""
from copy import deepcopy

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


class _NoConnect:
    def connect(self):
        raise AssertionError("Noncanonical source row ID reached JobHub")


@pytest.mark.parametrize("bad_id", [
    "1", "01", " 1 ", "", True, False, 1.0, 1.25,
    0, -1, None, {"source": 1}, [1],
])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value, PublishingMode.DRAFT.value,
])
def test_noncanonical_row_identity_blocks_full_customer_write(
    test_dbs, bad_id, mode,
):
    _, hub, _ = test_dbs
    package = _approved_package()
    package.mode = mode
    package.quantities[0].row_id = bad_id
    package.payload_hash = package.compute_payload_hash()
    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("exact positive integer source identities" in s
               for s in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="exact positive integer"):
        execute_jobhub_publishing(package, _NoConnect(), "Source Estimator")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value, PublishingMode.DRAFT.value,
])
def test_two_aliases_of_one_physical_row_cannot_be_billed_twice(test_dbs, mode):
    _, hub, _ = test_dbs
    package = _approved_package()
    package.mode = mode
    original = package.quantities[0]
    original.row_id = "1"
    duplicate = deepcopy(original)
    duplicate.row_id = "01"
    package.quantities.append(duplicate)
    package.payload_hash = package.compute_payload_hash()
    assert len({q.row_id for q in package.quantities}) == 2
    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("exact positive integer" in s for s in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="exact positive integer"):
        execute_jobhub_publishing(package, _NoConnect(), "Source Estimator")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


def test_two_distinct_positive_original_row_ids_remain_publishable(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    second = deepcopy(package.quantities[0])
    second.row_id = 2
    package.quantities.append(second)
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    old_hash = package.payload_hash
    before = package.to_dict()

    receipt = execute_jobhub_publishing(package, bridge, "Source Estimator")
    assert receipt["status"] == "Published"
    assert receipt["total_lines"] == 2
    assert receipt["payload_hash"] == old_hash
    assert package.to_dict() == before
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 2
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Source Estimator")


def test_repeated_integer_row_id_remains_blocked_in_commercial_and_draft():
    for mode in (PublishingMode.COMMERCIAL, PublishingMode.DRAFT):
        package = _approved_package()
        package.mode = mode.value
        package.quantities.append(deepcopy(package.quantities[0]))
        package.payload_hash = package.compute_payload_hash()
        gate = validate_publishing_gate(package)
        assert not gate.is_publishable
        assert any("Duplicate physical takeoff row IDs" in s
                   for s in gate.blocking_reasons)
