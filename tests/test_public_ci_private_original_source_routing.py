"""Mandatory negative tests for owner-only real-source CI routing.

Does not read or ship client source drawings.
"""
from __future__ import annotations

import pytest
import conftest as routing


class _Item:
    def __init__(self, nodeid: str):
        self.nodeid = nodeid
        self.name = nodeid.split("::", 1)[-1]
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)


def test_public_ci_only_skips_explicit_original_pdf_positive(tmp_path, monkeypatch):
    monkeypatch.setattr(routing, "_OWNER_MARYBOROUGH_PDF", tmp_path / "absent-original.pdf")
    original = _Item(
        "tests/test_gpt2_a120_opposed_source_wall_ink.py::"
        "test_original_a120_black_native_top_double_wall_is_exact_contiguous_source"
    )
    negative = _Item("tests/test_fake_source_rejection.py::test_missing_original_must_abstain")
    different_test = _Item("tests/test_gpt2_a120_opposed_source_wall_ink.py::test_synthetic_wall_negative")
    routing.pytest_collection_modifyitems([original, negative, different_test])
    assert len(original.markers) == 1
    assert original.markers[0].name == "skip"
    assert negative.markers == []
    assert different_test.markers == []


def test_owner_original_source_present_does_not_skip_real_source_positive(tmp_path, monkeypatch):
    source = tmp_path / "owner-original.pdf"
    source.write_bytes(b"synthetic-dummy-file-exists-not-an-authenticated-original")
    monkeypatch.setattr(routing, "_OWNER_MARYBOROUGH_PDF", source)
    original = _Item(
        "tests/test_gpt2_a120_opposed_source_wall_ink.py::"
        "test_original_a120_black_native_top_double_wall_is_exact_contiguous_source"
    )
    routing.pytest_collection_modifyitems([original])
    assert original.markers == []


def test_owner_source_selection_does_not_skip_entire_modules():
    assert len(routing._OWNER_ONLY_MARYBOROUGH_TESTS) == 38
    assert all(x.startswith("tests/test_gpt2_") and "::" in x
               for x in routing._OWNER_ONLY_MARYBOROUGH_TESTS)
    assert all("test_gpt3" not in x for x in routing._OWNER_ONLY_MARYBOROUGH_TESTS)
