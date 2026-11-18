"""Acacia original four-source-role gate executes BEFORE the trace or output."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
from types import SimpleNamespace

import fitz
import pytest

from tools import run_original_footprint_first as runner


def _synthetic_original(tmp_path):
    source = tmp_path / "synthetic_source.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 50),
            "Drawing title: Floor Plan\nScale: 1:100")
        doc.save(source)
    return source


def test_foreign_acacia_packet_rejected_before_geometry_and_disk(tmp_path, monkeypatch):
    source = _synthetic_original(tmp_path)
    invoked = []

    def never_trace(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("cannot trace wrong original")

    monkeypatch.setattr(runner, "trace_external_footprint_first", never_trace)
    dest = tmp_path / "rejected"
    with pytest.raises(ValueError, match="original_footprint_acacia_role_packet_unverified"):
        runner.run(source, 0, dest, acacia_region="Brisbane")
    assert invoked == []
    assert not dest.exists()


def test_non_floor_acacia_sheet_never_enters_geometry(tmp_path, monkeypatch):
    source = _synthetic_original(tmp_path)
    invoked = []
    monkeypatch.setattr(
        runner, "inspect_acacia_original_bytes",
        lambda *_args, **_kwargs: SimpleNamespace(
            original_byte_roles_verified=True,
            to_dict=lambda: {"status": "ORIGINAL_ROLES_AUTHENTICATED_REVIEW_ONLY"},
        ),
    )
    monkeypatch.setattr(
        runner, "trace_external_footprint_first",
        lambda *_args, **_kwargs: invoked.append(True),
    )
    dest = tmp_path / "wrong_floor_index"
    with pytest.raises(ValueError, match="original_footprint_acacia_floor_page_required"):
        runner.run(source, 0, dest, acacia_region="Brisbane")
    assert invoked == [] and not dest.exists()


def test_non_acacia_runner_does_not_gain_an_implicit_source_requirement(tmp_path):
    source = _synthetic_original(tmp_path)
    sha = sha256(source.read_bytes()).hexdigest()
    assert runner._enforce_original_source_sha_pin(sha, sha)
    # The default generic original trace accepts arbitrary source families,
    # retaining its existing explicit expected-SHA/title controls.
    assert runner.run.__kwdefaults__["acacia_region"] is None


def test_authenticated_private_acacia_packet_is_diagnostic_only():
    base = os.environ.get("PLANREADER_ACACIA_ORIGINAL_DIR")
    if not base:
        pytest.skip("private Acacia floor original not provisioned to public CI")
    from pb_gpt1_acacia_source_packet import inspect_acacia_original_file

    path = Path(base) / "03_acacia_brisbane.pdf"
    receipt = inspect_acacia_original_file(path, expected_region="Brisbane")
    assert receipt.original_byte_roles_verified
    assert receipt.to_dict()["customer_quantities_authorized"] is False
    assert receipt.to_dict()["physical_outer_wall_verified"] is False
    assert receipt.to_dict()["installed_door_window_hosts_verified"] is False
