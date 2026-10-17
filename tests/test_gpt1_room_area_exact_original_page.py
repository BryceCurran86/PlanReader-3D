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
