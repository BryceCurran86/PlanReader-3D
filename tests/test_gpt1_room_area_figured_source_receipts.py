"""Explicit printed room-area evidence must retain its original figured IDs."""
from __future__ import annotations

from copy import copy

import pytest

from pb_room_area_quantity import build_room_area_quantity
from tests.test_room_area_quantity_v2 import (
    _context, _document, _entity, _explicit_area, _room, _viewport,
)


def source_area(atom):
    return build_room_area_quantity(
        room=_room(), context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=atom,
    )


def test_authentic_direct_printed_area_does_not_require_figured_dimension_pair():
    value = source_area(_explicit_area(25.0))
    assert not value.abstained
    assert value.value == 25.0
    assert value.metadata["figured_dimension_ids"] == []


def test_two_genuine_figured_source_witnesses_remain_authoritative():
    source = _explicit_area(25.0, metadata={
        "figured_dimension_ids": ("dim-width", "dim-height"),
    })
    quantity = source_area(source)
    assert not quantity.abstained
    assert quantity.value == 25.0
    assert quantity.metadata["figured_dimension_ids"] == ["dim-height", "dim-width"]


@pytest.mark.parametrize("bad_dim_ids", [
    "ab", "horizontal", "dim-width", ("dim-width",), (),
    ("dim-width", "dim-width"), ("dim-width", ""), ("dim-width", True),
    ("dim-width", "dim-height", "unrelated"),
])
def test_untyped_or_ambiguous_figured_dimension_metadata_cannot_mint_firm_area(bad_dim_ids):
    quantity = source_area(_explicit_area(
        25.0, metadata={"figured_dimension_ids": bad_dim_ids},
    ))
    assert quantity.abstained
    assert "explicit_area_figured_receipts_invalid" in quantity.blocking_reasons


@pytest.mark.parametrize("bad_area", [True, False, "25.0", float("nan"), float("inf")])
def test_replayed_untyped_printed_area_does_not_mint_firm_room_metric(bad_area):
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "normalized_value", bad_area)
    quantity = source_area(atom)
    assert quantity.abstained
    assert "explicit_area_invalid" in quantity.blocking_reasons



@pytest.mark.parametrize("bad_confidence", [True, False, "0.95", float("nan"), 1.2, -0.5])
def test_source_explicit_area_with_invalid_confidence_cannot_be_firm(bad_confidence):
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "confidence", bad_confidence)
    quantity = source_area(atom)
    assert quantity.abstained is True
    assert "explicit_area_confidence_invalid" in quantity.blocking_reasons


@pytest.mark.parametrize("bad_confidence", [True, "0.95", float("nan"), -0.1, 1.1])
def test_original_room_geometry_confidence_is_not_a_boolean_or_unbounded_number(bad_confidence):
    room = copy(_room())
    object.__setattr__(room, "geometry_confidence", bad_confidence)
    result = build_room_area_quantity(
        room=room, context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert result.abstained is True
    assert "room_area_source_confidence_invalid" in result.blocking_reasons



def test_oversized_source_area_integer_fails_closed_instead_of_raising_overflow():
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "normalized_value", 10 ** 400)
    quantity = source_area(atom)
    assert quantity.abstained is True
    assert "explicit_area_invalid" in quantity.blocking_reasons


@pytest.mark.parametrize("bad", [10 ** 400, -10 ** 400])
def test_oversized_room_or_source_confidence_abstains_without_overflow(bad):
    room = copy(_room())
    object.__setattr__(room, "geometry_confidence", bad)
    result = build_room_area_quantity(
        room=room, context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert result.abstained is True
    assert "room_area_source_confidence_invalid" in result.blocking_reasons

    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "confidence", bad)
    other = source_area(atom)
    assert other.abstained is True
    assert "explicit_area_confidence_invalid" in other.blocking_reasons


@pytest.mark.parametrize("bad", [
    ("dim-h", " dim-v"), ("dim-h", "dim-v "), ("dim-h", "dim-h "),
])
def test_figured_dim_source_receipts_must_be_exact_original_tokens(bad):
    quantity = source_area(_explicit_area(
        25.0, metadata={"figured_dimension_ids": bad},
    ))
    assert quantity.abstained is True
    assert "explicit_area_figured_receipts_invalid" in quantity.blocking_reasons



@pytest.mark.parametrize("source_page", [True, 1.0, " 1", "1 ", "one", 10 ** 400])
def test_replayed_source_room_page_cannot_crash_or_reassign_documented_area(source_page):
    room = copy(_room())
    object.__setattr__(room, "source_page", source_page)
    result = build_room_area_quantity(
        room=room, context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert result.abstained
    assert "room_source_page_mismatch" in result.blocking_reasons


@pytest.mark.parametrize("invalid", [
    None, "room-ev", True, ("room-ev", ["nested"]),
    ("room-ev", "room-ev"), (" room-ev", "area-ev"),
])
def test_unhashable_or_coerced_source_room_entity_receipts_abstain_with_audit(invalid):
    entity = copy(_entity())
    object.__setattr__(entity, "evidence_ids", invalid)
    result = build_room_area_quantity(
        room=_room(), context=_context(), document=_document(),
        viewport=_viewport(), entity=entity, page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert result.abstained
    assert "entity_evidence_not_owned_by_document" in result.blocking_reasons
    assert all(type(source) is str for source in result.evidence_ids)


def test_original_source_room_page_and_receipts_still_allow_documented_area():
    result = source_area(_explicit_area(25.0))
    assert result.abstained is False
    assert result.value == 25.0



@pytest.mark.parametrize("corrupt_polygon", [
    ((0., 0.), (True, 0.), (10., 10.)),
    ((0., 0.), ("100", 0.), (100., 100.)),
    ((0., 0.), (10 ** 400, 0.), (100., 100.)),
    ((0., 0.), (float("nan"), 0.), (100., 100.)),
    ((0., 0.), (float("inf"), 0.), (100., 100.)),
    ((0., 0.), (100., 0.), (100., "100")),
])
def test_untyped_scaled_room_pdf_points_never_become_metric_area(corrupt_polygon):
    from tests.test_room_area_quantity_v2 import _scale, _scaled_qty
    # RoomCandidate construction itself converts normalizable PDF source
    # numerics and rejects NaN/huge values. Exercise the real quantity seam
    # against an imported/replayed record whose data has been changed since
    # construction, rather than incorrectly expecting the constructor to
    # preserve invalid original input.
    room = copy(_room())
    object.__setattr__(room, "polygon_pdf_pts", corrupt_polygon)
    result = _scaled_qty(room=room, scale=_scale())
    assert result.abstained is True
    assert result.value is None
    assert "room_polygon_area_invalid" in result.blocking_reasons


def test_bad_pdf_ring_signature_cannot_crash_batch_room_identity_detection():
    from pb_room_area_quantity import _canonical_ring, _polygon_area
    assert _canonical_ring(((0., 0.), (10 ** 400, 0.), (1., 1.))) == ()
    assert _polygon_area(((0., 0.), (10 ** 400, 0.), (1., 1.))) == 0.0


def test_genuine_pdf_scaled_room_with_trusted_scale_remains_firm():
    from tests.test_room_area_quantity_v2 import _scaled_qty
    measured = _scaled_qty()
    assert measured.abstained is False
    assert measured.value == 25.0


@pytest.mark.parametrize("source_page", [0, "", "0", None, -1, "01", "  ", "1.0"])
def test_falsy_or_noncanonical_room_source_page_cannot_publish_firm_printed_area(source_page):
    room = copy(_room())
    object.__setattr__(room, "source_page", source_page)
    quantity = build_room_area_quantity(
        room=room, context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert quantity.abstained
    assert quantity.value is None
    assert "room_source_page_mismatch" in quantity.blocking_reasons


@pytest.mark.parametrize("source_page", [1, "1"])
def test_exact_original_room_source_page_preserves_documented_area(source_page):
    room = copy(_room())
    object.__setattr__(room, "source_page", source_page)
    quantity = build_room_area_quantity(
        room=room, context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert not quantity.abstained
    assert quantity.value == 25.0


@pytest.mark.parametrize("native_text", [
    "ROOM 40 m2", "40m²", "4,000 sq m", "25 m2 40 m2",
])
def test_original_printed_room_area_conflict_cannot_be_laundered_to_firm(native_text):
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "raw_text", native_text)
    result = source_area(atom)
    assert result.abstained
    assert "explicit_area_printed_source_mismatch" in result.blocking_reasons


@pytest.mark.parametrize("native_text", [
    "ROOM 25 m2", "25m²", "ROOM 25.0 sq m",
])
def test_original_matching_printed_room_area_keeps_firm_source_measurement(native_text):
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "raw_text", native_text)
    result = source_area(atom)
    assert not result.abstained
    assert result.value == 25.0


def test_authenticated_cross_view_figured_m2_has_separate_original_dimension_receipts():
    atom = copy(_explicit_area(25.0))
    object.__setattr__(atom, "method", "authenticated_cross_view_figured_dimensions")
    object.__setattr__(atom, "raw_text", "ROOM 40 m2")
    # This source is authenticated by the independent pair of original
    # dimension receipts, not by an unrelated printed area text token.
    result = source_area(atom)
    assert not result.abstained
    assert result.value == 25.0
