"""Optional isolated-runner full-suite sharding; never a release-gate waiver."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import pytest


def digest(ids: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(ids), ensure_ascii=True,
                                    separators=(",", ":")).encode()).hexdigest()


# Conservative lower bounds (milliseconds per file) from Python 3.13
# shard logs of successful run 45807089738, 2026-11-26. These affect only
# scheduling, never collection, selection eligibility or release criteria.
_FILE_TIME_FLOORS_MS = {
    "tests/test_three_laurel_source_scope_negative_audit.py": 62830,
    "tests/test_migration_control_plane.py": 34190,
    "tests/test_automatic_rerun_stress.py": 20820,
    "tests/test_workspace_state_matrix.py": 17960,
    "tests/test_three_laurel_open_bottom_fifth_generation_negative.py": 14430,
    "tests/test_migration_control_plane_seven_blockers.py": 16110,
    "tests/test_preview_entry_cap_evidence_v1.py": 10720,
    "tests/test_autopilot_model_rerun_stability.py": 9120,
    "tests/test_page_frame_wall_boundary_shadow_diff_v1.py": 7590,
    "tests/test_u1_lineage_architecture_review.py": 8140,
    "tests/test_composition_smoke.py": 6390,
    "tests/test_legacy_workspace_compat.py": 6470,
    "tests/test_takeoff_row_contract_drift.py": 6380,
    "tests/test_page_frame_shadow_v1.py": 6430,
    "tests/test_opening_quantity_first_fail_shadow.py": 6110,
    "tests/test_physical_opening_viewport_scope_shadow_adversarial.py": 5930,
    "tests/test_physical_opening_seeded_existence_v1.py": 5930,
    "tests/test_review_merge_survives_auto_rerun.py": 5760,
    "tests/test_source_join_readiness_shadow.py": 5310,
    "tests/test_annotation_cycle_shadow.py": 5210,
}


def partition(nodeids: list[str], count: int, *,
              time_floors_ms: dict[str, int] | None = None) -> list[list[str]]:
    """Keep file fixtures together; balance estimated execution cost."""
    if time_floors_ms is None:
        time_floors_ms = _FILE_TIME_FLOORS_MS
    if any(type(v) is not int or v < 0 for v in time_floors_ms.values()):
        raise ValueError("invalid test duration floor")
    if count < 1 or count > 16 or not nodeids or len(set(nodeids)) != len(nodeids):
        raise ValueError("invalid shard count or duplicate/empty collection")
    groups: dict[str, list[str]] = defaultdict(list)
    for nodeid in nodeids:
        groups[nodeid.split("::", 1)[0]].append(nodeid)
    bins: list[list[str]] = [[] for _ in range(count)]
    weights = {path: max(25 * len(group), time_floors_ms.get(path, 0))
               for path, group in groups.items()}
    loads = [0] * count
    for path, group in sorted(groups.items(), key=lambda pair: (-weights[pair[0]], pair[0])):
        target = min(range(count), key=lambda i: (loads[i], len(bins[i]), i))
        bins[target].extend(sorted(group))
        loads[target] += weights[path]
    if any(not part for part in bins):
        raise ValueError("empty shard")
    return [sorted(part) for part in bins]


def receipt(nodeids: list[str], count: int, index: int) -> dict:
    if not 0 <= index < count:
        raise ValueError("invalid shard index")
    return _partition_receipt(nodeids, count, index, partition(nodeids, count))


def _partition_receipt(nodeids, count, index, parts):
    return {"count": count, "index": index, "total": len(nodeids),
            "collection": digest(nodeids),
            "parts": [{"count": len(part), "digest": digest(part)} for part in parts],
            "selected": len(parts[index]), "selected_digest": digest(parts[index])}


def verify_receipts(rows: list[dict], count: int) -> int:
    """All runners must independently discover the same complete partition."""
    if len(rows) != count or sorted(row["index"] for row in rows) != list(range(count)):
        raise ValueError("missing or repeated shard receipt")
    baseline = rows[0]
    if len(baseline["parts"]) != count or not baseline["total"]:
        raise ValueError("invalid partition")
    for row in rows:
        if (row["count"] != count or row["total"] != baseline["total"]
                or row["collection"] != baseline["collection"]
                or row["parts"] != baseline["parts"] or row.get("exitstatus") != 0):
            raise ValueError("collection drift or failed shard")
        part = baseline["parts"][row["index"]]
        if part["count"] <= 0 or row["selected"] != part["count"] or row["selected_digest"] != part["digest"]:
            raise ValueError("shard selection mismatch")
        if (row.get("completed") != part["count"]
                or row.get("completed_digest") != part["digest"]):
            raise ValueError("shard execution incomplete or duplicated")
    if sum(part["count"] for part in baseline["parts"]) != baseline["total"]:
        raise ValueError("incomplete partition")
    return baseline["total"]


_RECORD: dict | None = None
_COMPLETED: list[str] = []


def pytest_runtest_logreport(report):
    # Teardown runs even for setup skips/xfails; count every item exactly once.
    if report.when == "teardown":
        _COMPLETED.append(report.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    global _RECORD
    count = int(os.environ["PLANREADER_CI_SHARDS"])
    index = int(os.environ["PLANREADER_CI_SHARD_INDEX"])
    ids = [item.nodeid for item in items]
    try:
        if not 0 <= index < count:
            raise ValueError("invalid shard index")
        parts = partition(ids, count)
        _RECORD = _partition_receipt(ids, count, index, parts)
        selected = set(parts[index])
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    excluded = [item for item in items if item.nodeid not in selected]
    items[:] = [item for item in items if item.nodeid in selected]
    config.hook.pytest_deselected(items=excluded)
    print(f"Full collection {_RECORD['total']}; shard {index + 1}/{count}: {len(items)} tests")


def pytest_sessionfinish(session, exitstatus):
    if _RECORD is None:
        return
    # The runner's temporary directory is outside source/evidence archives.
    target = Path(os.environ["PLANREADER_CI_SHARD_RECEIPT"])
    target.write_text(json.dumps({**_RECORD, "exitstatus": int(exitstatus),
                                 "completed": len(_COMPLETED),
                                 "completed_digest": digest(_COMPLETED)},
                                 sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    count = int(sys.argv[2])
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in folder.rglob("receipt.json")]
    total = verify_receipts(rows, count)
    print(f"All {count} successful shards account for {total} collected tests.")
