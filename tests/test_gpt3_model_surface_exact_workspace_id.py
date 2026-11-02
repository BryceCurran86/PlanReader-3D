"""Exact source SQLite workspace binding in model-surface approval and JobHub.

Source-neutral producer -> fingerprint -> verifier -> commercial recipient.
No original PDF, signed original 9, or frozen Full Plan V2 accuracy is asserted.
"""
from __future__ import annotations

import pytest

from pb_takeoff_authority_v164 import (
    approve_model_surface_row,
    compute_model_surface_authority_fingerprint,
    is_jobhub_eligible_row,
    model_surface_authority,
    takeoff_row_pricing_authority,
)


def _surface(workspace_id=7):
    return {
        "workspace_id": workspace_id,
        "row_role": "model_surface",
        "source_reference": "PB 3D surface editor 2026 trace",
        "source_page": "3D_MODEL",
        "section": "Internal walls",
        "element": "Wall 1",
        "location": "Unit 1",
        "substrate": "Plasterboard",
        "finish_system": "Paint",
        "quantity": 12.5,
        "unit": "m²",
        "quantity_status": "Measured",
        "inclusion_status": "INCLUDED",
        "coats": 2,
        "coverage_m2_per_litre": 10.0,
        "productivity_m2_per_hour": 6.0,
        "rate_per_unit": 25.0,
        "confidence": "Estimator verified",
        "notes": "Synthetic model surface source authority",
    }


def _approve(row):
    return approve_model_surface_row(
        row, source="Original model surface source evidence",
        reviewed_by="Source Estimator",
        reviewed_at="2026-10-29T00:00:00Z",
    )


@pytest.mark.parametrize("forged", [
    None, False, True, 0, -7, 7.0, 7.9, "7", "07", " 7 ",
    "", " ", -7.9, 1e308, float("nan"), float("inf"),
    b"7", [7], {"workspace": 7},
])
def test_aliased_workspace_cannot_mint_commercial_model_approval(forged):
    row = _surface(workspace_id=forged)
    with pytest.raises(ValueError, match="exact positive integer workspace identity"):
        _approve(row)


@pytest.mark.parametrize("forged", [
    None, False, True, 0, -7, 7.0, 7.9, "7", "07", " 7 ",
    "", " ", -7.9, 1e308, float("nan"), float("inf"),
    b"7", [7], {"workspace": 7},
])
def test_rehashed_approval_cannot_cross_source_workspace_identity(forged):
    approved = _approve(_surface(workspace_id=7))
    approved["workspace_id"] = forged
    # Even attacker-recomputed row seal cannot authorize an invalid caller ID.
    approved["commercial_authority_fingerprint"] = (
        compute_model_surface_authority_fingerprint(approved)
    )
    verdict, reason = model_surface_authority(approved)
    assert not verdict
    assert "workspace identity" in reason
    assert not takeoff_row_pricing_authority(approved)[0]
    assert not is_jobhub_eligible_row(approved)[0]


def test_native_positive_source_identity_preserved_across_full_model_gate():
    approved = _approve(_surface(workspace_id=7))
    assert type(approved["workspace_id"]) is int
    assert approved["workspace_id"] == 7
    assert approved["commercial_authority_fingerprint"] == (
        compute_model_surface_authority_fingerprint(approved)
    )
    assert model_surface_authority(approved) == (True, "APPROVED")
    assert takeoff_row_pricing_authority(approved)[0]
    assert is_jobhub_eligible_row(approved)[0]


def test_approved_model_cannot_be_retargeted_to_another_canonical_workspace():
    approved = _approve(_surface(workspace_id=7))
    approved["workspace_id"] = 8
    verdict, reason = model_surface_authority(approved)
    assert verdict is False
    assert "no longer matches" in reason
