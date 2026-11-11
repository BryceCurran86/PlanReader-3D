"""Cross-API Windows metadata and inode-race guards for frozen V2 integrity."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import check_full_plan_v2_integrity as gate


def test_platform_ctime_policy():
    fields = gate._cross_descriptor_identity_fields()
    assert {'st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns'} <= set(fields)
    assert ('st_ctime_ns' not in fields) == (os.name == 'nt')


def test_real_temporary_json_and_source(tmp_path):
    path = tmp_path / 'frozen.json'
    path.write_bytes(b'{"value":1}')
    assert gate._json(path) == {'value': 1}
    digest = gate._present_source_digest(path)
    assert digest is not None and digest[1] == len(path.read_bytes())


def test_changed_inode_even_with_identical_bytes(tmp_path, monkeypatch):
    path = tmp_path / 'frozen.json'
    path.write_bytes(b'{"value":1}')
    actual = Path.lstat
    count = 0
    def replaced_final_stat(self):
        nonlocal count
        result = actual(self)
        if self == path:
            count += 1
            if count >= 2:
                values = {field:getattr(result,field) for field in gate._SOURCE_IDENTITY_FIELDS}
                values['st_ino'] += 1
                return SimpleNamespace(**values)
        return result
    monkeypatch.setattr(Path,'lstat',replaced_final_stat)
    with pytest.raises(ValueError, match='changed during verification'):
        gate._json(path)


def test_windows_only_ctime_disagreement_on_same_inode(tmp_path, monkeypatch):
    path = tmp_path / 'frozen.json'
    path.write_bytes(b'{"value":1}')
    actual = Path.lstat
    count = 0
    def changed_ctime(self):
        nonlocal count
        result = actual(self)
        if self == path:
            count += 1
            if count >= 2:
                values = {field:getattr(result,field) for field in gate._SOURCE_IDENTITY_FIELDS}
                values['st_ctime_ns'] += 100000
                return SimpleNamespace(**values)
        return result
    monkeypatch.setattr(Path,'lstat',changed_ctime)
    with pytest.raises(ValueError, match='changed during verification'):
        gate._json(path)


def test_windows_cross_api_ctime_disagreement_is_not_a_race(tmp_path, monkeypatch):
    path = tmp_path / 'frozen.json'
    path.write_bytes(b'{"value":1}')
    original = os.fstat
    def different_api_ctime(fd):
        result = original(fd)
        values = {field: getattr(result, field) for field in gate._SOURCE_IDENTITY_FIELDS}
        values['st_ctime_ns'] += 100000
        return SimpleNamespace(**values)
    monkeypatch.setattr(os, 'fstat', different_api_ctime)
    if os.name == 'nt':
        assert gate._json(path) == {'value': 1}
        assert gate._present_source_digest(path) is not None
    else:
        with pytest.raises(ValueError, match='changed during verification'):
            gate._json(path)


def test_same_api_descriptor_ctime_change_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'frozen.json'
    path.write_bytes(b'{"value":1}')
    original = os.fstat
    count = 0
    def changing_descriptor_ctime(fd):
        nonlocal count
        count += 1
        result = original(fd)
        values = {field: getattr(result, field) for field in gate._SOURCE_IDENTITY_FIELDS}
        if count >= 2:
            values['st_ctime_ns'] += 100000
        return SimpleNamespace(**values)
    monkeypatch.setattr(os, 'fstat', changing_descriptor_ctime)
    with pytest.raises(ValueError, match='changed during verification'):
        gate._json(path)
