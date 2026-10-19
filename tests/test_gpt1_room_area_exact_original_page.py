"""Exact original page identity is mandatory even for explicit FIRM area."""
import pytest
from pb_room_area_quantity import build_room_area_quantity
from tests.test_room_area_quantity_v2 import (
    _room,_context,_document,_viewport,_entity,_explicit_area,
)


def _quantity(page):
    return build_room_area_quantity(
        room=_room(),context=_context(),document=_document(),
        viewport=_viewport(),entity=_entity(),page_no=page,
        explicit_area_evidence=_explicit_area(25.0),
    )


def test_exact_native_integer_original_page_preserves_figured_area():
    q=_quantity(1)
    assert not q.abstained and q.value == 25.0


@pytest.mark.parametrize("bad", [True,1.0,1.9,"1",0,-1,None])
def test_page_aliases_and_invalid_pages_never_publish_firm_room_area(bad):
    q=_quantity(bad)
    assert q.abstained
    assert "page_not_owned" in q.blocking_reasons


@pytest.mark.parametrize("ownership", [
    (), (("vp", True),), (("vp", 1.0),), (("vp", "1"),),
    (("vp", 0),), (("vp", 2),), (("vp", 1), ("vp", 1)),
])
def test_room_area_requires_one_exact_original_viewport_page_binding(ownership):
    from dataclasses import replace
    context = replace(_context(), viewport_page_ownership=ownership)
    result = build_room_area_quantity(
        room=_room(), context=context, document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert result.abstained
    assert "viewport_page_mismatch" in result.blocking_reasons


def test_room_area_accepts_unique_native_integer_viewport_page_owner():
    result = build_room_area_quantity(
        room=_room(), context=_context(), document=_document(),
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert not result.abstained
    assert result.value == 25.0


@pytest.mark.parametrize("page_ids", [
    ("page-2",), ("page-1", "page-1"), ("",), (" page-1",),
])
def test_missing_duplicate_or_foreign_document_pages_never_seal_room_area(page_ids):
    from copy import copy
    # DocumentEvidence construction itself rejects duplicate pages. This
    # adversarial replay bypasses the constructor to exercise the production
    # FIRM-publication boundary against a tampered original manifest.
    document = copy(_document())
    object.__setattr__(document, "page_ids", page_ids)
    quantity = build_room_area_quantity(
        room=_room(), context=_context(), document=document,
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert quantity.abstained
    assert "viewport_page_not_owned_by_document" in quantity.blocking_reasons



@pytest.mark.parametrize("page_ids", [
    ("page-2",), ("page-1", "page-1"), ("",), (" page-1",),
])
def test_missing_duplicate_or_foreign_document_pages_never_seal_room_area(page_ids):
    from copy import copy
    # DocumentEvidence construction itself rejects duplicate pages. This
    # adversarial replay bypasses the constructor to exercise the production
    # FIRM-publication boundary against a tampered original manifest.
    document = copy(_document())
    object.__setattr__(document, "page_ids", page_ids)
    quantity = build_room_area_quantity(
        room=_room(), context=_context(), document=document,
        viewport=_viewport(), entity=_entity(), page_no=1,
        explicit_area_evidence=_explicit_area(25.0),
    )
    assert quantity.abstained
    assert "viewport_page_not_owned_by_document" in quantity.blocking_reasons



def test_optional_original_document_page_manifest_keeps_existing_issued_room_area():
    from dataclasses import replace
    # This is how the live SHA-owned producer actually constructs the
    # DocumentEvidence; the exact viewport ownership and one-based page
    # count independently prove the physical page.
    document=replace(_document(),page_ids=())
    quantity=build_room_area_quantity(
        room=_room(),context=_context(),document=document,
        viewport=_viewport(),entity=_entity(),page_no=1,
        explicit_area_evidence=_explicit_area(25.0))
    assert not quantity.abstained
    assert quantity.value==25.0
    assert quantity.authority=="documented_dimension"


@pytest.mark.parametrize("forged_page", [2,0,-1,True,1.0])
def test_empty_manifest_never_waives_document_bounds_or_typed_original_page(forged_page):
    from dataclasses import replace
    document=replace(_document(),page_ids=())
    result=build_room_area_quantity(
        room=_room(),context=_context(),document=document,
        viewport=_viewport(),entity=_entity(),page_no=forged_page,
        explicit_area_evidence=_explicit_area(25.0))
    assert result.abstained
    assert "page_not_owned" in result.blocking_reasons or "viewport_page_not_owned_by_document" in result.blocking_reasons


def test_empty_manifest_never_waives_missing_or_forged_viewport_page_ownership():
    from dataclasses import replace
    document=replace(_document(),page_ids=())
    context=replace(_context(),viewport_page_ownership=())
    result=build_room_area_quantity(
        room=_room(),context=context,document=document,
        viewport=_viewport(),entity=_entity(),page_no=1,
        explicit_area_evidence=_explicit_area(25.0))
    assert result.abstained
    assert "viewport_page_mismatch" in result.blocking_reasons
