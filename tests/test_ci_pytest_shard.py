import copy

import pytest

from scripts.ci_pytest_shard import partition, receipt, verify_receipts


IDS = [f"tests/test_{file}.py::test_case_{case}"
       for file in range(12) for case in range(file + 1)]


def test_partition_is_exhaustive_disjoint_and_order_independent():
    parts = partition(IDS, 4)
    assert parts == partition(list(reversed(IDS)), 4)
    assert sorted(x for part in parts for x in part) == sorted(IDS)
    owners = {}
    for index, part in enumerate(parts):
        for nodeid in part:
            assert owners.setdefault(nodeid.split("::")[0], index) == index
    assert max(map(len, parts)) - min(map(len, parts)) <= 3


def rows():
    result = [receipt(IDS, 4, index) for index in range(4)]
    return [{**row, "exitstatus": 0, "completed": row["selected"],
             "completed_digest": row["selected_digest"]} for row in result]


def test_all_receipts_required():
    assert verify_receipts(rows(), 4) == len(IDS)
    with pytest.raises(ValueError):
        verify_receipts(rows()[:-1], 4)


@pytest.mark.parametrize("field,value", [
    ("collection", "different"), ("selected", 999), ("selected_digest", "different"),
    ("index", 0), ("exitstatus", 1), ("total", 999), ("parts", []),
    ("completed", 0), ("completed", 999), ("completed_digest", "different"),
])
def test_receipt_drift_or_failure_rejected(field, value):
    receipts = rows()
    receipts[1][field] = value
    with pytest.raises(ValueError):
        verify_receipts(receipts, 4)


def test_duplicate_empty_and_unbalanced_configuration_rejected():
    for ids, count in [([], 4), (IDS + IDS, 4), (IDS, 0), (IDS, 17), (IDS[:1], 4)]:
        with pytest.raises(ValueError):
            partition(ids, count)


def test_duration_weighted_partition_separates_expensive_files():
    ids = [f"tests/test_{i}.py::test_case_{j}" for i in range(8) for j in range(4)]
    weights = {"tests/test_0.py": 10000, "tests/test_2.py": 9000,
               "tests/test_4.py": 8000}
    parts = partition(ids, 3, time_floors_ms=weights)
    assert parts == partition(list(reversed(ids)), 3, time_floors_ms=weights)
    assert sorted(x for part in parts for x in part) == sorted(ids)
    assert all(sum(any(node.startswith(path + "::") for node in part)
                   for path in weights) == 1 for part in parts)
    with pytest.raises(ValueError, match="duration"):
        partition(ids, 3, time_floors_ms={"tests/test_0.py": -1})
