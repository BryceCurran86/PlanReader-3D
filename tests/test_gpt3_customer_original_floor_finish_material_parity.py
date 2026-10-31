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


def _source_coded_element_receipt():
    """Exercise the REAL GPT1 projector, not a manually forged positive row."""
    signed, rows = _real_floor_finish_receipt()
    assert rows[0]["element"] == "Floor finish area (FT1)"
    assert rows[0]["finish_system"] == "tile"
    return signed, rows


def _legacy_element_receipt():
    """Reconstruct an authentic old-format row with a matching source receipt.

    Only this regression constructs the historical customer display. The
    coded-format positives above must go through the actual GPT1 projector.
    """
    from pb_migration_contracts import QuantityEvidence
    from pb_quantity_takeoff_adapter import (
        CommercialTakeoffSourceTrace,
        CommercialMeasurementAuthority,
        compute_commercial_projection_fingerprint,
    )

    signed, rows = _real_floor_finish_receipt()
    source = deepcopy(rows[0])
    provenance = deepcopy(source["commercial_projection_provenance"])
    source["element"] = "Floor finish area"
    provenance["quantity"]["metadata"]["element"] = "Floor finish area"
    source["commercial_projection_provenance"] = provenance
    source["notes"] = json.dumps(provenance)
    source["commercial_projection_fingerprint"] = (
        compute_commercial_projection_fingerprint(
            QuantityEvidence(**dict(provenance["quantity"])),
            trace=CommercialTakeoffSourceTrace(**dict(provenance["source_trace"])),
            authority=CommercialMeasurementAuthority(
                **dict(provenance["measurement_authority"])
            ),
        )
    )
    return signed, [source]

def test_original_floor_code_element_passes_without_changing_signed_quantity():
    signed, rows = _source_coded_element_receipt()
    original_seal = signed.to_dict()
    assert rows[0]["element"] == "Floor finish area (FT1)"
    assert rows[0]["finish_system"] == "tile"
    assert verify_sealed_customer_output(signed, rows).verified_quantity_ids == (
        "floor-finish-q1",
    )
    persisted = deepcopy(rows)
    persisted[0].pop("commercial_projection_provenance")
    assert verify_sealed_customer_output(signed, persisted).verified_quantity_ids == (
        "floor-finish-q1",
    )
    assert signed.to_dict() == original_seal


@pytest.mark.parametrize("wrong_element", [
    "Floor finish area (FT3)", "Floor finish area (FT9)",
    "Floor finish area (FT2)", "Floor finish area (FT1) ",
    "Floor finish area", "", None, True,
])
def test_customer_floor_code_element_tamper_rejected(wrong_element):
    signed, rows = _source_coded_element_receipt()
    forged = deepcopy(rows)
    forged[0]["element"] = wrong_element
    with pytest.raises(CustomerOutputVerificationError, match="element differs"):
        verify_sealed_customer_output(signed, forged)


@pytest.mark.parametrize("notes_only", [False, True])
def test_provenance_and_display_cannot_conspire_to_relabel_signed_finish_code(
    notes_only,
):
    signed, rows = _source_coded_element_receipt()
    forged = deepcopy(rows)
    forged[0]["element"] = "Floor finish area (FT3)"
    provenance = deepcopy(forged[0]["commercial_projection_provenance"])
    provenance["quantity"]["metadata"]["element"] = "Floor finish area (FT3)"
    forged[0]["notes"] = json.dumps(provenance)
    if notes_only:
        forged[0].pop("commercial_projection_provenance")
    else:
        forged[0]["commercial_projection_provenance"] = provenance
    with pytest.raises(CustomerOutputVerificationError, match="element differs"):
        verify_sealed_customer_output(signed, forged)


@pytest.mark.parametrize("notes_only", [False, True])
def test_recomputed_customer_fingerprint_cannot_resign_a_foreign_finish_code(
    notes_only,
):
    from pb_migration_contracts import QuantityEvidence
    from pb_quantity_takeoff_adapter import (
        CommercialTakeoffSourceTrace,
        CommercialMeasurementAuthority,
        compute_commercial_projection_fingerprint,
    )

    signed, rows = _source_coded_element_receipt()
    forged = deepcopy(rows)
    element = "Floor finish area (FT3)"
    forged[0]["element"] = element
    provenance = deepcopy(forged[0]["commercial_projection_provenance"])
    provenance["quantity"]["metadata"]["element"] = element
    forged[0]["notes"] = json.dumps(provenance)
    forged[0]["commercial_projection_fingerprint"] = (
        compute_commercial_projection_fingerprint(
            QuantityEvidence(**dict(provenance["quantity"])),
            trace=CommercialTakeoffSourceTrace(**dict(provenance["source_trace"])),
            authority=CommercialMeasurementAuthority(
                **dict(provenance["measurement_authority"])
            ),
        )
    )
    if notes_only:
        forged[0].pop("commercial_projection_provenance")
    else:
        forged[0]["commercial_projection_provenance"] = provenance
    # A fresh, internally consistent fingerprint cannot override signed FT1.
    with pytest.raises(CustomerOutputVerificationError, match="element differs"):
        verify_sealed_customer_output(signed, forged)


def test_legacy_original_floor_label_cannot_be_relabelled_as_source_coded():
    signed, rows = _legacy_element_receipt()
    assert rows[0]["element"] == "Floor finish area"
    assert verify_sealed_customer_output(signed, rows).verified_quantity_ids == (
        "floor-finish-q1",
    )
    forged = deepcopy(rows)
    forged[0]["element"] = "Floor finish area (FT1)"
    with pytest.raises(CustomerOutputVerificationError, match="element differs"):
        verify_sealed_customer_output(signed, forged)


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
