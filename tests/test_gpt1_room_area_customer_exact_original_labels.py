"""GPT1 original room-area customer labels cannot be repaired from source receipts.

These tests exercise the actual native-PDF producer, authenticated room/floor
source traces, customer adapter and existing source-closed verifier. They never
read benchmark truth or confer new FIRM/physical room authority.
"""
from dataclasses import replace

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_room_area_customer_projection import project_live_room_area_customer_rows
from pb_live_room_area_source_closed_export import (
    build_live_room_area_source_traces,
    seal_live_room_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_room_area_source_closed_export import _cross_view_room_area_pdf


class ImportedSourceLabel(str):
    """Lookalike non-native original PDF label."""


@pytest.fixture
def original_claim(tmp_path):
    path = tmp_path / "room-source-label-authority.pdf"
    path.write_bytes(_cross_view_room_area_pdf())
    return collect_live_physical_net_wall_claim(
        path, pages=(0,), room_area_support_pages=(1,),
    )


def _firm(original_claim):
    firm = tuple(
        q for q in original_claim.room_area_quantity_evidence
        if not q.abstained and q.value is not None
    )
    assert len(firm) == 1
    return firm[0]


def _alter(original_claim, field, value):
    original = _firm(original_claim)
    altered = replace(
        original,
        metadata={**dict(original.metadata), field: value},
    )
    return replace(
        original_claim,
        room_area_quantity_evidence=tuple(
            altered if q.quantity_id == original.quantity_id else q
            for q in original_claim.room_area_quantity_evidence
        ),
    )


def _customer(claim):
    return project_live_room_area_customer_rows(
        claim, workspace_id=7, project_id="original-room-source",
    )


def test_original_native_pdf_room_area_reaches_sealed_customer_unchanged(original_claim):
    source = _firm(original_claim)
    traces = build_live_room_area_source_traces(
        original_claim, workspace_id=7, project_id="original-room-source",
    )
    assert source.quantity_id in traces
    rows = _customer(original_claim)
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == source.quantity_id
    assert rows[0]["quantity"] == pytest.approx(source.value)
    assert rows[0]["quantity_status"] == "To review"
    assert rows[0]["origin"] == "AI"
    if "location" in source.metadata:
        assert rows[0]["location"] == source.metadata["location"]
    sealed = seal_live_room_area_run(
        original_claim, workspace_id=7, project_id="original-room-source",
    )
    verified = verify_sealed_customer_output(sealed, rows)
    assert verified.verified_quantity_ids == (source.quantity_id,)


@pytest.mark.parametrize("field,value", [
    ("location", " OFFICE "),
    ("location", "OFFICE "),
    ("location", " "),
    ("location", 17),
    ("location", None),
    ("location", ImportedSourceLabel("OFFICE")),
    ("room_label", " OFFICE"),
    ("room_label", ""),
    ("room_label", False),
    ("room_label", ImportedSourceLabel("OFFICE")),
])
def test_source_valid_metric_cannot_launder_original_room_customer_label(
    original_claim, field, value,
):
    forged = _alter(original_claim, field, value)
    original = _firm(original_claim)
    # The genuine source metric and physical room/floor lineage still exist:
    # the first failing gate is the final customer source-label boundary.
    assert original.quantity_id in build_live_room_area_source_traces(
        forged, workspace_id=7, project_id="original-room-source",
    )
    before = forged.room_area_quantity_evidence
    with pytest.raises(
        SourceClosedRunConflictError,
        match=f"room-area customer original {field}",
    ):
        _customer(forged)
    assert forged.room_area_quantity_evidence == before
    assert _firm(original_claim) == original


def test_missing_optional_room_labels_are_not_invented(original_claim):
    source = _firm(original_claim)
    metadata = dict(source.metadata)
    metadata.pop("room_label", None)
    metadata.pop("location", None)
    altered = replace(source, metadata=metadata)
    claim = replace(
        original_claim,
        room_area_quantity_evidence=tuple(
            altered if q.quantity_id == source.quantity_id else q
            for q in original_claim.room_area_quantity_evidence
        ),
    )
    rows = _customer(claim)
    assert len(rows) == 1
    assert rows[0]["location"] == ""
    assert rows[0]["quantity"] == pytest.approx(source.value)


def test_genuine_abstention_does_not_create_customer_row(original_claim):
    claim = replace(
        original_claim,
        room_area_quantity_evidence=tuple(
            q for q in original_claim.room_area_quantity_evidence if q.abstained
        ),
    )
    assert claim.room_area_quantity_evidence
    assert _customer(claim) == ()
