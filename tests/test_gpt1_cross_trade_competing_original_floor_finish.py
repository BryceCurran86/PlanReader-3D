"""Competing original full-area floor finish semantics fail closed."""
from pb_cross_trade_geometry_reuse import derive_floor_surface_trade_quantities
from tests.test_cross_trade_geometry_reuse import _floor_surface

SPEC_A={"flooring":{"material":"vinyl sheet","section":"Internal","evidence_ids":["spec-vinyl"]}}
SPEC_B={"tiling":{"material":"ceramic tile","section":"Internal","evidence_ids":["spec-tile"]}}
SPEC_C={"coating":{"material":"epoxy paint","section":"Internal","evidence_ids":["spec-coating"]}}

def test_one_unopposed_source_floor_covering_publishes_one_area():
    assert [q.quantity for q in derive_floor_surface_trade_quantities(_floor_surface(),SPEC_A)] == [24.0]

def test_one_unopposed_source_floor_tile_publishes_one_area():
    assert [q.quantity for q in derive_floor_surface_trade_quantities(_floor_surface(),SPEC_B)] == [24.0]

def test_competing_whole_floor_covers_abstain_rather_than_mint_double_coverage():
    for specs in ({**SPEC_A,**SPEC_B},{**SPEC_B,**SPEC_A},{**SPEC_A,**SPEC_B,**SPEC_C}):
        assert derive_floor_surface_trade_quantities(_floor_surface(),specs)==[]

def test_layered_coating_without_competing_tile_and_vinyl_can_remain_visible():
    items=derive_floor_surface_trade_quantities(_floor_surface(),{**SPEC_A,**SPEC_C})
    assert {r.trade_scope for r in items}=={"flooring","painting"}
