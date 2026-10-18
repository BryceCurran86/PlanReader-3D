"""Public ceiling projections must never reissue a canonical surface identity.

No original PDF, benchmark target, numeric measurement or additional producer
source authority is introduced here. Start from the existing FIRM producer
fixtures, and forge output record aliases only in source-negative tests.
"""
from dataclasses import replace

import pytest

from pb_cross_view_ceiling_quantity_authority import (
    publish_cross_view_ceiling_quantities,
)
from tests.test_cross_view_ceiling_quantity_authority import (
    _bridge, _finish, _room, _rooms, _second_ceiling_source_scope,
)


def _published():
    report = publish_cross_view_ceiling_quantities(
        rooms=_rooms(), room_area_bridges=(_bridge(),), finishes=_finish(),
    )
    assert len(report.records) == 1
    return report


def _assert_no_customer_projection(report):
    assert not report.records_by_ceiling_id
    assert report.quantities == ()
    assert report.canonical_ceilings == ()


def test_authentic_unique_ceiling_still_projects_exact_existing_signed_quantity():
    report = _published()
    assert len(report.records_by_ceiling_id) == 1
    assert report.quantities == tuple(r.quantity for r in report.records)
    assert report.canonical_ceilings == tuple(r.canonical_ceiling for r in report.records)


@pytest.mark.parametrize("reverse", [False, True])
def test_competing_original_ceiling_quantity_id_rekey_rejected_from_every_projection(reverse):
    report = _published()
    original = report.records[0]
    duplicate = replace(
        original,
        quantity=replace(original.quantity, quantity_id="reissued-ceiling-quantity"),
    )
    rows = (original, duplicate) if not reverse else (duplicate, original)
    _assert_no_customer_projection(replace(report, records=rows))


def test_exact_same_original_ceiling_receipt_cannot_be_published_twice():
    report = _published()
    original = report.records[0]
    _assert_no_customer_projection(replace(report, records=(original, original)))


@pytest.mark.parametrize("invalid", [True, 123, "", " padded", "padded ", ["unhashable"]])
def test_malformed_canonical_ceiling_source_ids_cannot_be_projected(invalid):
    report = _published()
    compromised = replace(report.records[0], canonical_ceiling_id=invalid)
    _assert_no_customer_projection(replace(report, records=(compromised,)))


@pytest.mark.parametrize("owner_field", [
    "record_physical_surface",
    "nested_canonical_surface",
    "signed_surface_quantity",
    "signed_input_ceiling",
])
def test_rekeyed_embedded_original_ceiling_source_cannot_borrow_other_issuer(owner_field):
    report = _published()
    row = report.records[0]
    if owner_field == "record_physical_surface":
        row = replace(row, physical_ceiling_surface_id="alias-physical-ceiling")
    elif owner_field == "nested_canonical_surface":
        row = replace(
            row,
            canonical_ceiling=replace(row.canonical_ceiling, canonical_ceiling_id="alias-ceiling"),
        )
    elif owner_field == "signed_surface_quantity":
        row = replace(
            row,
            canonical_ceiling=replace(row.canonical_ceiling, ceiling_quantity_id="alias-quantity"),
        )
    else:
        row = replace(
            row,
            quantity=replace(row.quantity, input_entity_ids=("other-ceiling",)),
        )
    _assert_no_customer_projection(replace(report, records=(row,)))


def test_two_authentic_separately_sourced_ceilings_both_project():
    other_room, other_finish = _second_ceiling_source_scope(face_id="face-2")
    report = publish_cross_view_ceiling_quantities(
        rooms=replace(_rooms(), rooms=(_room(), other_room)),
        room_area_bridges=(_bridge(), _bridge(face_id="face-2", quantity_id="room-area-qty-2")),
        finishes=replace(_finish(), records=(_finish().records[0], other_finish)),
    )
    assert len(report.records) == 2
    assert len(report.quantities) == len(report.canonical_ceilings) == 2
    assert set(report.records_by_ceiling_id) == {
        row.canonical_ceiling_id for row in report.records
    }
