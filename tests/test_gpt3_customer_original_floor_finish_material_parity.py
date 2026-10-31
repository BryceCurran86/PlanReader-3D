"""A signed tile source floor can never be displayed as vinyl in customer output."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_customer_output_verification import (
    CustomerOutputVerificationError, verify_sealed_customer_output,
)
from pb_live_floor_finish_area_source_closed_export import seal_live_floor_finish_area_run
from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from test_live_floor_finish_area_source_closed_export import _claim


def _real_floor_finish_receipt():
    source = _claim()
    run = seal_live_floor_finish_area_run(
        source, workspace_id=1, project_id="project-1",
    )
    rows = project_live_floor_finish_customer_rows(
        source, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == len(run.quantities) == 1
    return run, rows


def test_actual_source_tile_customer_finish_retains_original_signed_material():
    run, rows = _real_floor_finish_receipt()
    assert run.quantities[0].semantic_key == "floor_finish_area:floor-1:FT1:tile"
    assert rows[0]["finish_system"] == "tile"
    verified = verify_sealed_customer_output(run, rows)
    assert verified.verified_quantity_ids == ("floor-finish-q1",)


@pytest.mark.parametrize("wrong_display", [
    "vinyl", "epoxy", "TILE", "tile ", "", None, True,
])
def test_forged_customer_display_material_cannot_retype_signed_floor(wrong_display):
    run, original_rows = _real_floor_finish_receipt()
    forged = [deepcopy(original_rows[0])]
    forged[0]["finish_system"] = wrong_display
    with pytest.raises(CustomerOutputVerificationError,
                       match="finish_system differs"):
        verify_sealed_customer_output(run, forged)


@pytest.mark.parametrize("field,value", [
    ("semantic_finish", "vinyl"),
    ("finish_code", "FT3"),
    ("canonical_floor_id", "foreign-floor"),
    ("semantic_finish", ""),
    ("finish_code", None),
])
def test_modified_machine_material_provenance_not_authenticated_by_original_seal(
    field, value,
):
    run, original_rows = _real_floor_finish_receipt()
    forged = [deepcopy(original_rows[0])]
    forged[0]["commercial_projection_provenance"]["quantity"]["metadata"][field] = value
    with pytest.raises(CustomerOutputVerificationError):
        verify_sealed_customer_output(run, forged)


def test_signed_source_code_display_matches_customer_provenance(monkeypatch):
    import pb_live_floor_finish_customer_projection as projection

    monkeypatch.setattr(
        projection, "_source_finish_system",
        lambda metadata: "{} ({})".format(metadata["finish_code"], metadata["semantic_finish"]),
    )
    run, rows = _real_floor_finish_receipt()
    assert rows[0]["finish_system"] == "FT1 (tile)"
    assert verify_sealed_customer_output(run, rows).verified_quantity_ids == (
        "floor-finish-q1",
    )
    stored = deepcopy(rows)
    stored[0].pop("commercial_projection_provenance")
    assert verify_sealed_customer_output(run, stored).verified_quantity_ids == (
        "floor-finish-q1",
    )


@pytest.mark.parametrize("wrong_display", ["FT2 (tile)", "FT3 (tile)", "tile", "FT1 (vinyl)"])
def test_source_code_label_tamper_is_rejected(monkeypatch, wrong_display):
    import pb_live_floor_finish_customer_projection as projection

    monkeypatch.setattr(
        projection, "_source_finish_system",
        lambda metadata: "{} ({})".format(metadata["finish_code"], metadata["semantic_finish"]),
    )
    run, rows = _real_floor_finish_receipt()
    forged = [deepcopy(rows[0])]
    forged[0]["finish_system"] = wrong_display
    with pytest.raises(CustomerOutputVerificationError, match="finish_system differs"):
        verify_sealed_customer_output(run, forged)


def test_extra_customer_fields_do_not_affect_unrelated_original_lot16_eight():
    archive = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production")
    sealed = sealed_source_closed_run_from_dict(
        json.loads((archive / "source_sealed_run.json").read_text())
    )
    rows = json.loads((archive / "verified_customer_rows.json").read_text())
    verified = verify_sealed_customer_output(sealed, rows)
    assert len(verified.verified_quantity_ids) == 8
    assert sealed.fingerprint == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )


def test_source_floor_finish_material_check_never_reissues_quantity():
    run, rows = _real_floor_finish_receipt()
    original_signed = run.to_dict()
    original_customer = deepcopy(rows)
    verify_sealed_customer_output(run, rows)
    assert run.to_dict() == original_signed
    assert rows == original_customer
