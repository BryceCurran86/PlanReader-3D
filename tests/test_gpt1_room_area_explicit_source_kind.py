"""Wrong source family can never be laundered into FIRM plain room m²."""
from dataclasses import replace
import pytest
from pb_room_area_quantity import build_room_area_quantity
from tests.test_room_area_quantity_v2 import (
    _room,_context,_document,_viewport,_entity,_explicit_area,
)


def _quantity(evidence):
    return build_room_area_quantity(
        room=_room(),context=_context(),document=_document(),
        viewport=_viewport(),entity=_entity(),page_no=1,
        explicit_area_evidence=evidence,
    )


def test_real_producer_explicit_room_area_kind_retains_plain_area():
    q=_quantity(_explicit_area(25.0))
    assert not q.abstained and q.value == 25.0


@pytest.mark.parametrize("foreign_kind", [
    "ceiling_finish","opening_area","wall_length","floor_finish_area",
    "dimension",None,True,"explicit_room_area ",
])
def test_unrelated_source_dimension_or_finish_cannot_publish_plain_room_area(foreign_kind):
    fake=_explicit_area(25.0)
    # The original constructor already rejects an empty source kind; a
    # corrupted downstream source packet must still fail the quantity gate.
    object.__setattr__(fake,"kind",foreign_kind)
    q=_quantity(fake)
    assert q.abstained
    assert "explicit_area_source_kind_mismatch" in q.blocking_reasons
