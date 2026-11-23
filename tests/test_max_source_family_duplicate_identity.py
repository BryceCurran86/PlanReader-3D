"""Source-neutral regressions for signed-family handoff identity and ownership."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from pb_quantity_takeoff_adapter import quantities_to_takeoff_output_rows
from pb_source_closed_run_export import combine_source_closed_runs, seal_source_closed_run
from test_customer_output_verification import authority, quantity, trace
import tools.run_source_closed_project_handoff as handoff


SHA = "a" * 64


def _case(monkeypatch, ids, sealed_ids=None, verified_ids=None):
    class Quantity:
        def __init__(self, identity):
            self.quantity_id = identity
            self.family = "floor_finish"
            self.abstained = False
            self.status = "firm"
            self.metadata = {
                "source_sha256": SHA,
                "commercial_projection_allowed": True,
            }

    monkeypatch.setattr(handoff, "QuantityEvidence", Quantity)
    quantities = tuple(Quantity(identity) for identity in ids)
    sealed = SimpleNamespace(quantities=tuple(Quantity(identity) for identity in (sealed_ids if sealed_ids is not None else ids)), source_sha256s=(SHA,))
    issued = SimpleNamespace(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        sealed_run=sealed,
        quantities=quantities,
        customer_rows=tuple({"quantity_id": identity} for identity in ids),
    )
    monkeypatch.setattr(
        handoff,
        "verify_sealed_customer_output",
        lambda run, rows: SimpleNamespace(
            customer_row_count=len(rows),
            verified_quantity_ids=tuple(verified_ids if verified_ids is not None else (row["quantity_id"] for row in rows)),
        ),
    )
    return handoff._verified_source_family_handoff(
        Path("synthetic.pdf"),
        workspace_id=1,
        source_sha256=SHA,
        issuer=lambda path, workspace_id: issued,
        family="floor_finish",
        expected_count=2,
    )


def test_distinct_signed_quantity_ids_preserved(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b")) is not None


def test_duplicate_signed_quantity_ids_rejected(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-a")) is None


def test_duplicate_sealed_ids_rejected_even_when_issued_distinct(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b"), sealed_ids=("floor-a", "floor-a")) is None


def test_duplicate_customer_verified_ids_rejected_even_when_sealed_distinct(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b"), verified_ids=("floor-a", "floor-a")) is None


def test_mismatched_customer_verified_ids_rejected(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b"), verified_ids=("floor-a", "floor-c")) is None


def test_reordered_sealed_ids_preserve_identity_not_position(monkeypatch):
    # Independently sealed customer quantities may be ordered differently.
    assert _case(monkeypatch, ("floor-a", "floor-b"), sealed_ids=("floor-b", "floor-a")) is not None


def test_missing_sealed_identity_rejected_even_with_matching_row_count(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b"), sealed_ids=("floor-a", "floor-c")) is None


def test_missing_verified_identity_rejected_even_with_matching_row_count(monkeypatch):
    assert _case(monkeypatch, ("floor-a", "floor-b"), verified_ids=("floor-a", "floor-c")) is None


@pytest.mark.parametrize("tile_owner, accepted", [("floor-b", True), ("floor-a", False)])
def test_independently_sealed_finish_issuers_need_distinct_floor_owners(tile_owner, accepted):
    quantities = []
    for finish, owner in (("vinyl", "floor-a"), ("tile", tile_owner)):
        floor = quantity(f"quantity-{finish}", owner)
        quantities.append(replace(
            floor,
            family="floor_finish_area",
            semantic_key=f"floor_finish_area:{owner}:{finish}:{finish}",
            status="firm",
            metadata={**floor.metadata, "commercial_projection_allowed": True},
        ))
    quantities = tuple(quantities)
    traces = {floor.quantity_id: trace(floor) for floor in quantities}
    authorities = {floor.quantity_id: authority() for floor in quantities}
    runs = tuple(
        seal_source_closed_run(
            (floor,), project_id="project-7", traces_by_quantity_id=traces,
        )
        for floor in quantities
    )
    sealed = combine_source_closed_runs(runs)
    rows = quantities_to_takeoff_output_rows(
        quantities, traces_by_quantity_id=traces, authorities_by_quantity_id=authorities,
    )
    issued = SimpleNamespace(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW", sealed_run=sealed,
        quantities=quantities, customer_rows=rows,
    )

    result = handoff._verified_source_family_handoff(
        Path("synthetic.pdf"), workspace_id=7, source_sha256=SHA,
        issuer=lambda path, workspace_id: issued, family="floor_finish_area", expected_count=2,
    )

    assert (result is not None) is accepted
    if accepted:
        assert result == (quantities, sealed, tuple(rows))
