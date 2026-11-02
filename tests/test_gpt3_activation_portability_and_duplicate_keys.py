"""Activation tooling must behave the same on Windows and POSIX, and reject duplicate JSON keys.

Source-neutral synthetic inputs only. Nothing here reads an original PDF, grants authority or
publishes a quantity.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.gpt3_atomic_pending_activation_pair as pair
import tools.prepare_gpt3_pending_floor_surface_identity_activation as floor
import tools.prepare_gpt3_pending_identity_activation as opening
from tools.gpt3_atomic_pending_activation_pair import (
    publish_new_activation_pair,
    read_committed_active_identity_map,
    source_input_snapshot,
)

PARSERS = [
    pytest.param(opening, id="opening-activation"),
    pytest.param(floor, id="floor-surface-activation"),
]


def _inputs(tmp_path: Path):
    files = tuple(tmp_path / f"immutable-{i}.json" for i in range(3))
    for i, path in enumerate(files):
        path.write_text(json.dumps({"source_owned": i}), encoding="utf-8")
    return files


# --- directory durability is POSIX only; nothing else is relaxed -----------------------------------


def test_directory_fsync_is_a_noop_only_where_windows_cannot_open_a_directory(monkeypatch, tmp_path):
    def refuse(*_args, **_kwargs):
        raise PermissionError("Windows cannot open a directory for fsync")

    monkeypatch.setattr(pair.os, "open", refuse)
    monkeypatch.setattr(pair, "_IS_WINDOWS", True)
    assert pair._fsync_directory(tmp_path) is None
    # On POSIX a failure to make the link durable must never be mistaken for success.
    monkeypatch.setattr(pair, "_IS_WINDOWS", False)
    with pytest.raises(PermissionError):
        pair._fsync_directory(tmp_path)


# --- the committed digest covers the bytes that are on disk -----------------------------------------


def test_published_pair_is_the_exact_bytes_the_digest_covers(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = (tmp_path / "activated-map.json", tmp_path / "activated-receipt.json")
    first = {"schema_version": "1.0.0", "project_id": "synthetic", "source_sha256s": ["0" * 64],
             "bindings": [{"original": True}]}
    second = {"source_authority": "verified", "benchmark_score_granted": False}
    publish_new_activation_pair(
        outputs, (first, second), inputs=inputs, source_snapshot=source_input_snapshot(inputs),
    )
    on_disk = outputs[0].read_bytes()
    assert on_disk == pair._serialized(first)
    assert b"\r" not in on_disk and b"\r" not in outputs[1].read_bytes()
    marker = json.loads(outputs[1].read_bytes())
    import hashlib

    assert marker["identity_map_sha256"] == hashlib.sha256(on_disk).hexdigest()
    # and the receipt-last reader accepts exactly what the publisher produced
    assert read_committed_active_identity_map(outputs[0], receipt_path=outputs[1]) == first


# --- duplicate JSON keys never reach the source/identity proof --------------------------------------

DUPLICATE_TOP_LEVEL = '{"schema_version": "1.0.0", "project_id": "a", "project_id": "b"}'
DUPLICATE_NESTED = (
    '{"pending_identities": [{"physical_opening_id": "a", "physical_opening_id": "b", '
    '"benchmark_item_id": "x", "status": "IDENTITY_READY_QUANTITY_UNSEALED"}]}'
)
DUPLICATE_IN_ROW = '[{"quantity_id": "q1", "quantity_id": "q2"}]'


@pytest.mark.parametrize("module", PARSERS)
@pytest.mark.parametrize("text", [DUPLICATE_TOP_LEVEL, DUPLICATE_NESTED])
def test_standalone_object_reader_rejects_duplicate_keys_at_every_depth(module, text, tmp_path):
    path = tmp_path / "input.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        module._object(path)


@pytest.mark.parametrize("module", PARSERS)
def test_standalone_rows_reader_rejects_duplicate_keys_in_a_row(module, tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(DUPLICATE_IN_ROW, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        module._rows(path)


@pytest.mark.parametrize("module", PARSERS)
def test_standalone_readers_keep_accepting_ordinary_json_and_reject_wrong_shapes(module, tmp_path):
    obj, rows, wrong = tmp_path / "o.json", tmp_path / "r.json", tmp_path / "w.json"
    obj.write_text(json.dumps({"a": {"b": [1, 2]}}), encoding="utf-8")
    rows.write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
    wrong.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert module._object(obj) == {"a": {"b": [1, 2]}}
    assert module._rows(rows) == [{"a": 1}, {"b": 2}]
    with pytest.raises(TypeError):
        module._object(wrong)
    with pytest.raises(TypeError):
        module._rows(obj)


def test_the_guarded_scorer_and_both_standalone_cli_parse_identically_on_duplicates(tmp_path):
    import tools.run_gpt3_guarded_pending_reconciliation as guarded

    path = tmp_path / "input.json"
    path.write_text(DUPLICATE_NESTED, encoding="utf-8")
    messages = set()
    for module in (opening, floor, guarded):
        with pytest.raises(ValueError) as caught:
            module._object(path)
        messages.add(str(caught.value))
    assert len(messages) == 1  # one parser, one error contract; no second vocabulary
