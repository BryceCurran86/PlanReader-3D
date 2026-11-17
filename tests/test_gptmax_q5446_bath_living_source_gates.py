"""Q5446 bathroom/Living source gate regressions; no private PDF or gold data.

The positive source-to-customer checks require the independently authenticated
original PDFs and are not replaced by these parameter/negative tests.
"""
from pathlib import Path
from unittest.mock import Mock

import pytest

import pb_gptmax_q5446_original_tiled_floor_customer as issuer


@pytest.mark.parametrize(
    ("function", "page", "label", "scope", "finish", "location"),
    (
        (
            issuer.issue_original_q5446_first_bathroom_tiled_floor,
            2, "BATH", "bathroom_and_ensuite_floor_tiles", "tile",
            "First-floor bathroom",
        ),
        (
            issuer.issue_original_q5446_ground_living_porcelain_floor,
            1, "LIVING", "entry_kitchen_living_porcelain_tiles",
            "porcelain_tile", "Ground-floor Living",
        ),
    ),
)
def test_each_new_room_uses_independent_original_source_gates(
    monkeypatch, function, page, label, scope, finish, location,
):
    observed = []

    def protected(*args, **kwargs):
        observed.append((args, kwargs))
        return issuer._blocked("original_source_not_provided")

    monkeypatch.setattr(issuer, "_issue_original_q5446_native_tiled_floor", protected)
    result = function(
        "source-plan.pdf", "source-inclusions.pdf", "source-sales.pdf",
        workspace_id=7,
    )
    assert result.status == "ABSTAIN"
    assert result.quantity is None
    assert result.customer_rows == ()
    assert len(observed) == 1
    args, kwargs = observed[0]
    assert args == ("source-plan.pdf", "source-inclusions.pdf", "source-sales.pdf")
    assert kwargs["workspace_id"] == 7
    assert kwargs["page_number"] == page
    assert kwargs["room_label"] == label
    assert kwargs["required_material_scope"] == scope
    assert kwargs["location"] == location
    assert kwargs.get("finish_code", "tile") == finish
    assert kwargs.get("finish_system", "tile") == finish


@pytest.mark.parametrize(
    "function",
    (
        issuer.issue_original_q5446_first_bathroom_tiled_floor,
        issuer.issue_original_q5446_ground_living_porcelain_floor,
    ),
)
def test_missing_original_sources_cannot_create_customer_quantities(function):
    result = function(
        Path("/no-original/architecture.pdf"),
        Path("/no-original/inclusions.pdf"),
        Path("/no-original/sales.pdf"),
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("original_source_role_missing",)
    assert result.quantity is None
    assert result.trace is None
    assert result.sealed_run is None
    assert result.customer_rows == ()


def test_missing_living_scope_cannot_fall_back_to_bathroom_tiles(monkeypatch):
    observed = []

    def source_fail(*args, **kwargs):
        observed.append(kwargs["required_material_scope"])
        return issuer._blocked("authentic_living_porcelain_material_scope_unavailable")

    monkeypatch.setattr(issuer, "_issue_original_q5446_native_tiled_floor", source_fail)
    result = issuer.issue_original_q5446_ground_living_porcelain_floor(
        "plan", "inc", "sales"
    )
    assert observed == ["entry_kitchen_living_porcelain_tiles"]
    assert result.status == "ABSTAIN"
    assert result.customer_rows == ()


def test_existing_ensuite_and_laundry_authority_unchanged(monkeypatch):
    observed = []
    def source_fail(*args, **kwargs):
        observed.append((kwargs["page_number"], kwargs["room_label"], kwargs["required_material_scope"]))
        return issuer._blocked("source_face_unavailable")
    monkeypatch.setattr(issuer, "_issue_original_q5446_native_tiled_floor", source_fail)
    issuer.issue_original_q5446_ground_ensuite_tiled_floor("p", "i", "s")
    issuer.issue_original_q5446_ground_laundry_tiled_floor("p", "i", "s")
    issuer.issue_original_q5446_first_ensuite_tiled_floor("p", "i", "s")
    assert observed == [
        (1, "ENS", "bathroom_and_ensuite_floor_tiles"),
        (1, "LDRY", "laundry_floor_tiles"),
        (2, "ENS", "bathroom_and_ensuite_floor_tiles"),
    ]
