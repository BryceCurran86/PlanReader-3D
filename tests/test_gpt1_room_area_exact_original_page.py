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
    (), ("page-2",), ("page-1", "page-1"), ("",), (" page-1",),
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

