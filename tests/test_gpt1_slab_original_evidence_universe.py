"""Concrete, formwork and DPM must share the original slab source."""
from pb_cross_trade_geometry_reuse import derive_slab_trade_quantities
from tests.test_cross_trade_geometry_reuse import _slab

SPECS={"concrete":{"material":"25MPa","evidence_ids":["ev-mix"]},
       "edge_formwork":{"material":"timber","evidence_ids":["ev-form"]}}

def test_original_slab_receipts_are_preserved_on_actual_m3():
    rows=derive_slab_trade_quantities(_slab(),SPECS)
    assert len(rows)==2
    assert rows[0].unit=="m³"
    assert rows[0].quantity==18.0
    assert "source-150mm-slab-geometry" in rows[0].host_evidence_ids

def test_visible_thickness_annotation_is_not_a_source_geometry_receipt():
    slab=_slab()
    slab["provenance"]={"annotation_raw_text":"150mm RC slab",
      "boundary_id":"some-id-with-no-original-receipt"}
    assert derive_slab_trade_quantities(slab,SPECS)==[]

def test_unowned_slab_geometry_not_turned_into_customer_concrete():
    slab=_slab()
    slab["provenance"]={}
    assert derive_slab_trade_quantities(slab,SPECS)==[]

def test_untyped_and_duplicated_original_slab_receipts_abstain():
    for corrupt in [["ev-a","ev-a"],[True],[" ev"],"ev",[],None]:
        slab=_slab()
        slab["provenance"]={"evidence_ids":corrupt}
        assert derive_slab_trade_quantities(slab,SPECS)==[]
