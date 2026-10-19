"""Exact client rate binding provenance must not accept replayed evidence."""
import pytest
from pb_cross_trade_geometry_reuse import DerivedTradeQuantity,bind_derived_quantity_rate_key
def _q():
    return DerivedTradeQuantity(
        trade_scope="painting",section="Internal",element="Wall painting",
        location="wall-1",substrate="Acrylic",quantity=12.5,unit="m²",
        host_object_id="wall-1",host_object_type="WALL",
        derivation_formula="source wall area 12.5",
        host_evidence_ids=("ev-wall-area",),spec_evidence_ids=("ev-paint-spec",))

@pytest.mark.parametrize("ids",[
    ("rate-1","rate-1"),(" rate-1",),("rate-1 ",),("",),
    (True,),(123,),(None,),("rate-1","rate-2","rate-1")
])
def test_rate_binding_fails_on_duplicate_padded_nonstring_original_receipt(ids):
    with pytest.raises((TypeError,ValueError)):
        bind_derived_quantity_rate_key(_q(),rate_key="paint",evidence_ids=ids)

def test_genuine_two_original_rate_receipts_preserve_quantity():
    q=_q()
    b=bind_derived_quantity_rate_key(q,rate_key="paint",evidence_ids=("rate-1","scope-1"))
    assert b.quantity == q.quantity == 12.5
    assert b.rate_binding_evidence_ids==("rate-1","scope-1")
    assert q.rate_binding_evidence_ids==()

def test_unbound_source_quantity_can_have_empty_rate_evidence():
    assert _q().rate_binding_evidence_ids==()
