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


@pytest.mark.parametrize("method", [
    "authenticated_same_view_figured_dimensions",
    "authenticated_cross_view_figured_dimensions",
    "vector_text",
])
def test_known_original_room_area_issuers_remain_valid(method):
    original=_explicit_area(25.0)
    object.__setattr__(original,"method",method)
    qty=_quantity(original)
    assert not qty.abstained
    assert qty.value == 25.0


@pytest.mark.parametrize("untrusted", [
    "caller_supplied", "ocr_guess", "model_derived",
    "image_proximity", "manual_estimate", "vector_text ", None, True,
])
def test_unknown_original_source_methods_cannot_issue_firm_room_area(untrusted):
    evidence=_explicit_area(25.0)
    object.__setattr__(evidence,"method",untrusted)
    q=_quantity(evidence)
    assert q.abstained
    assert "explicit_area_source_method_untrusted" in q.blocking_reasons
