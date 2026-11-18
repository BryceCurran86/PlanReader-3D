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


def test_original_acacia_trace_receipt_excludes_courts_and_stays_review_only():
    from tests.test_gpt1_acacia_cross_sheet_review import _package

    scope = runner._acacia_source_scope_review(
        _package(),
        {
            "status": "ABSTAINED",
            "reason": "source_exterior_perimeter_not_unique_and_closed",
            "physical_wall_authenticated": False,
        },
    )
    assert scope["indoor_candidate_key_ids"] == list(range(2, 11))
    assert scope["outdoor_or_service_excluded_key_ids"] == [1, 11, 12, 13, 14, 15]
    assert scope["source_exterior_first_failing_gate"] == (
        "outside_original_wall_ink_not_physically_accepted"
    )
    assert len(scope["scheduled_prototype_codes_not_installed_count"]) == 16
    assert scope["installed_opening_instances_count_verified"] is False
    assert scope["floor_wall_ceiling_finish_authorized"] is False
    assert scope["commercial_quantity_rows"] == 0
    assert scope["official_frozen120_score_change"] == 0


def test_source_exterior_witness_still_needs_inside_finished_face():
    from tests.test_gpt1_acacia_cross_sheet_review import _package

    accepted_walker_ink = {"physical_wall_authenticated": True}
    scope = runner._acacia_source_scope_review(_package(), accepted_walker_ink)
    assert scope["source_exterior_first_failing_gate"] == (
        "finished_inside_face_and_opening_host_not_verified"
    )
    assert scope["physical_room_face_authorized"] is False
    assert scope["commercial_quantity_rows"] == 0


@pytest.mark.parametrize("untrusted_outer", [
    None,
    1,
    "true",
    {},
    {"physical_wall_authenticated": "True"},
    {"physical_wall_authenticated": "false"},
    {"physical_wall_authenticated": 1},
    {"physical_wall_authenticated": []},
    {"physical_wall_authenticated": True, "status": "ABSTAINED"},
])
def test_acacia_outer_source_review_never_promotes_truthy_or_abstained_ink(
    untrusted_outer,
):
    from tests.test_gpt1_acacia_cross_sheet_review import _package

    scope = runner._acacia_source_scope_review(_package(), untrusted_outer)
    assert scope["source_exterior_first_failing_gate"] == (
        "outside_original_wall_ink_not_physically_accepted"
    )
    assert scope["physical_room_face_authorized"] is False
    assert scope["commercial_quantity_rows"] == 0
    assert scope["official_frozen120_score_change"] == 0
