"""Canonical wire byte parity for ordinary and nonstandard contract payloads."""
from collections import UserDict
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import random

import pytest

from pb_migration_contracts import (
    _direct_json_eligible, _plain, canonical_contract_json, stable_contract_id,
)


def reference(value):
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class Tag(str, Enum):
    A = "a"


@dataclass(frozen=True)
class Record:
    value: object


class CustomString(str):
    pass


class CustomList(list):
    pass


@pytest.mark.parametrize("value", [
    None, True, 5, -0.0, 1e-30, "café\x00",
    {"z": [1, 2.5, None, False], "a": ("mm", {"nested": 3})},
    {"1": "string", 1: "int"},
    {1: "int", "1": "string"},
    UserDict({"z": [Tag.A, Record({"z": 2, "a": 1})]}),
    {"x": CustomString("a"), "y": CustomList([1, 2])},
])
def test_canonical_bytes_and_ids_match_existing_normalizer(value):
    expected = reference(value)
    assert canonical_contract_json(value) == expected
    assert stable_contract_id("evidence", value) == (
        "evidence_" + hashlib.sha256(expected.encode("utf-8")).hexdigest()[:20]
    )


def test_direct_path_only_accepts_exact_json_types():
    assert _direct_json_eligible({"z": [1, (True, None)], "a": 2.5})
    for value in (Tag.A, CustomString("a"), UserDict({"a": 1}),
                  {1: "x"}, CustomList([1]), Record(1)):
        assert not _direct_json_eligible(value)


@pytest.mark.parametrize("value", [float("nan"), {"a": float("inf")}, [float("-inf")]])
def test_non_finite_values_keep_original_rejection(value):
    assert not _direct_json_eligible(value)
    with pytest.raises(ValueError, match="contract payload contains a non-finite float"):
        canonical_contract_json(value)


def test_seeded_nested_payloads_preserve_wire_bytes_and_mutation_semantics():
    rng = random.Random(71)
    for _ in range(1000):
        keys = list("abcdefghijklmnop")
        rng.shuffle(keys)
        payload = {key: [rng.random(), rng.randint(-999, 999),
                         {"unit": "mm", "page": 2, "a": "abc"}]
                   for key in keys[:rng.randint(1, 16)]}
        assert canonical_contract_json(payload) == reference(payload)
        first = canonical_contract_json(payload)
        payload["changed"] = 1
        assert canonical_contract_json(payload) == reference(payload)
        assert canonical_contract_json(payload) != first


def test_stable_id_prefix_fast_path_preserves_original_normalization():
    import re
    from hashlib import sha256
    from pb_migration_contracts import stable_contract_id, canonical_contract_json

    payload = {"b": 4, "a": [2, "wall"]}
    digest = sha256(canonical_contract_json(payload).encode("utf-8")).hexdigest()
    for prefix in ("source_observation", "a", "0", "a__b", " A-B ",
                   "_a_", "Éwall", "Ａ", "x\n", "x y", 123):
        expected = re.sub(r"[^a-z0-9_]+", "_",
                          str(prefix or "").strip().lower()).strip("_")
        if expected:
            for width in (8, 20, 64):
                assert stable_contract_id(prefix, payload, digest_chars=width) == f"{expected}_{digest[:width]}"
        else:
            with pytest.raises(ValueError, match="prefix"):
                stable_contract_id(prefix, payload)
