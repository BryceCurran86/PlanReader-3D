"""Source-neutral regression for duplicate signed-family identity admission.

These tests intentionally use synthetic quantity objects rather than private PDFs.
"""
from pathlib import Path
from types import SimpleNamespace

import tools.run_source_closed_project_handoff as handoff


SHA = "a" * 64


def _case(monkeypatch, ids):
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
    sealed = SimpleNamespace(quantities=quantities, source_sha256s=(SHA,))
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
            verified_quantity_ids=tuple(row["quantity_id"] for row in rows),
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
