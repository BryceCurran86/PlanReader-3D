"""Derived snapshots store new records only.

A later generation must still read every inherited record, and a write or
delete on one generation must leave every other generation unchanged.
Translation, rotation, and scale do not apply: this map holds records, not
geometry.
"""
from __future__ import annotations

from pb_source_observation_authority import _SnapshotChainMap


def _chain(generations: int = 8, width: int = 20_000) -> _SnapshotChainMap:
    store = _SnapshotChainMap()
    store.open_snapshot("s0")
    for index in range(width):
        store[("s0", f"id{index}")] = index
    for generation in range(1, generations):
        store.fork(f"s{generation}", f"s{generation - 1}")
        store[(f"s{generation}", f"new{generation}")] = generation
    return store


def test_forked_generations_store_each_value_once() -> None:
    store = _chain()
    assert store.stored_entry_count() == 20_000 + 7
    assert len(store) == sum(20_000 + generation for generation in range(8))
    assert store[("s7", "id0")] == 0
    assert store[("s7", "id19999")] == 19999
    assert store[("s3", "new3")] == 3
    assert ("s2", "new3") not in store
    assert ("s7", "new3") in store


def test_a_write_after_fork_does_not_change_another_generation() -> None:
    store = _chain(generations=5, width=32)
    store[("s0", "id0")] = "root"
    store[("s2", "id1")] = "middle"
    assert store[("s0", "id0")] == "root"
    assert store[("s4", "id0")] == 0
    assert store[("s1", "id1")] == 1
    assert store[("s2", "id1")] == "middle"
    assert store[("s4", "id1")] == 1


def test_pop_hides_a_record_in_one_generation_only() -> None:
    store = _chain(generations=4, width=8)
    removed = store.pop(("s2", "id3"))
    assert removed == 3
    assert ("s2", "id3") not in store
    assert store[("s1", "id3")] == 3
    assert store[("s3", "id3")] == 3
    store[("s2", "id3")] = removed
    assert store[("s2", "id3")] == 3
