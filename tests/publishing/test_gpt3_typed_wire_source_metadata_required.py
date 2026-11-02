"""Serialized takeoff row must never invent a documented FIRM source.

Real typed wire hydration -> legacy preflight -> commercial JobHub builder.
Synthetic authority examples only; not original-source/Full Plan V2 proof.
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_takeoff_output_authority import TakeoffOutputRow, TakeoffSourceType
from pb_planreader_jobhub_publish_contract import (
    PublishMode, build_jobhub_payload, run_jobhub_publish_preflight,
)
from test_planreader_jobhub_preflight_gate import (
    _valid_approved_row, _valid_drawing_revision, _valid_project_identity,
)


@pytest.mark.parametrize("missing_field", [
    "source_type", "authority_status",
])
@pytest.mark.parametrize("invalid", [
    None, "", " ", "\t", True, False, 1, 1.0, [], {},
])
def test_published_wire_cannot_invent_documented_firm_receipt(
    missing_field, invalid,
):
    wire = _valid_approved_row().to_dict()
    assert wire["is_publishable"] is True
    wire[missing_field] = invalid
    with pytest.raises(ValueError, match="requires explicit source_type"):
        TakeoffOutputRow.from_dict(wire)


@pytest.mark.parametrize("missing_field", [
    "source_type", "authority_status",
])
def test_absent_commercial_metadata_never_mints_typed_authority(missing_field):
    wire = _valid_approved_row().to_dict()
    wire.pop(missing_field)
    with pytest.raises(ValueError, match="requires explicit source_type"):
        TakeoffOutputRow.from_dict(wire)


@pytest.mark.parametrize("missing_field", [
    "source_type", "authority_status",
])
@pytest.mark.parametrize("invalid", [
    None, "", " ", True, 1, {}, [],
])
def test_unapproved_legacy_wire_can_be_inspected_but_not_sold(
    missing_field, invalid,
):
    wire = _valid_approved_row().to_dict()
    wire["is_publishable"] = False
    wire[missing_field] = invalid
    typed = TakeoffOutputRow.from_dict(wire)
    assert typed.is_publishable is False
    assert typed.source_type == TakeoffSourceType.BLOCKED.value
    assert typed.authority_status == AuthorityStatus.BLOCKED.value
    gate = run_jobhub_publish_preflight(
        [typed], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not gate.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload(
            [typed], _valid_project_identity(), _valid_drawing_revision(),
            publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        )


def test_complete_named_approved_source_wire_keeps_commercial_consumer():
    row = _valid_approved_row()
    typed = TakeoffOutputRow.from_dict(row.to_dict())
    assert typed.is_publishable is True
    assert typed.source_type == row.source_type
    assert typed.authority_status == row.authority_status
    gate = run_jobhub_publish_preflight(
        [typed], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert gate.is_valid
    package = build_jobhub_payload(
        [typed], _valid_project_identity(), _valid_drawing_revision(),
        publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        created_by="Source Estimator",
    )
    assert package.is_commercial_ready
    assert len(package.quantities) == 1
    assert package.quantities[0].source_type == row.source_type


def test_missing_metadata_with_absent_publishability_stays_blocked():
    wire = _valid_approved_row().to_dict()
    for field in ("source_type", "authority_status", "is_publishable"):
        wire.pop(field)
    typed = TakeoffOutputRow.from_dict(wire)
    assert not typed.is_publishable
    assert typed.source_type == TakeoffSourceType.BLOCKED.value
    assert typed.authority_status == AuthorityStatus.BLOCKED.value
