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


def partition(nodeids: list[str], count: int) -> list[list[str]]:
    """Keep file fixtures together; deterministic greedy balance by item count."""
    if count < 1 or count > 16 or not nodeids or len(set(nodeids)) != len(nodeids):
        raise ValueError("invalid shard count or duplicate/empty collection")
    groups: dict[str, list[str]] = defaultdict(list)
    for nodeid in nodeids:
        groups[nodeid.split("::", 1)[0]].append(nodeid)
    bins: list[list[str]] = [[] for _ in range(count)]
    for _, group in sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        target = min(range(count), key=lambda i: (len(bins[i]), i))
        bins[target].extend(sorted(group))
    if any(not part for part in bins):
        raise ValueError("empty shard")
    return [sorted(part) for part in bins]


def receipt(nodeids: list[str], count: int, index: int) -> dict:
    if not 0 <= index < count:
        raise ValueError("invalid shard index")
    parts = partition(nodeids, count)
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
    if sum(part["count"] for part in baseline["parts"]) != baseline["total"]:
        raise ValueError("incomplete partition")
    return baseline["total"]


_RECORD: dict | None = None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    global _RECORD
    count = int(os.environ["PLANREADER_CI_SHARDS"])
    index = int(os.environ["PLANREADER_CI_SHARD_INDEX"])
    ids = [item.nodeid for item in items]
    try:
        _RECORD = receipt(ids, count, index)
        selected = set(partition(ids, count)[index])
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
    target.write_text(json.dumps({**_RECORD, "exitstatus": int(exitstatus)},
                                 sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    count = int(sys.argv[2])
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in folder.rglob("receipt.json")]
    total = verify_receipts(rows, count)
    print(f"All {count} successful shards account for {total} collected tests.")
