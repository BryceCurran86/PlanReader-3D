"""A canonical wall cannot mint more than its two physical finish faces."""
from pb_cross_trade_geometry_reuse import derive_wall_trade_quantities
import pytest

WALL = dict(canonical_wall_id="wall-a",role="internal",net_area_m2=12.5,
 physical_identity_resolved=True,quantity_complete=True,evidence_ids=["ev-wall"])
def _items(faces):
    return [r for r in derive_wall_trade_quantities(WALL, {
        "tiling":{"material":"ceramic tile","section":"Internal",
          "physical_face_ids":faces,"evidence_ids":["ev-tile"]}
    }) if r.trade_scope=="tiling"]

def test_one_physical_face_is_single_layer_area():
    assert [r.quantity for r in _items(["face-left"])]==[12.5]

def test_two_independent_source_faces_can_each_use_wall_net_area():
    assert [r.quantity for r in _items(["face-left","face-right"])]==[25.0]

@pytest.mark.parametrize("faces",[
 [],["face-left","face-left"],["face-left","face-right","face-third"],
 [" face-left"],["face-left "],[True],[5],[None],
 "face-left",["face-left",None],["face-left","face-right","face-third","face-fourth"],
])
def test_ambiguous_duplicate_or_three_wall_faces_cannot_mint_tiling(faces):
    assert _items(faces)==[]

def test_inverted_source_face_order_does_not_change_counted_area():
    assert _items(["face-left","face-right"])[0].quantity == _items(["face-right","face-left"])[0].quantity
