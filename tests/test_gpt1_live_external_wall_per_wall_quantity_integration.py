"""The live original external wall result exposes measured per-wall m².

This is a native synthetic source producer chain; no frozen truth used.
"""
from dataclasses import replace

from pb_live_external_physical_net_wall_publication import (
    compose_live_external_physical_net_wall_publication,
)
from tests.test_live_external_physical_net_wall_publication import _chain


def _result():
    wall_opening, physical_void, gross, role, *_ = _chain()
    return compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=role,
    )


def test_source_qualified_external_wall_is_available_as_individual_m2():
    result = _result()
    quantities = result.physical_wall_net_area_quantities
    assert len(quantities) == len(result.canonical_walls) == 1
    original = result.canonical_walls[0]
    quantity = quantities[0]
    assert quantity.value == original.net_area_m2
    assert quantity.unit == "m2"
    assert quantity.family == "wall_net_area"
    assert quantity.semantic_key == f"wall_net_area:{original.physical_wall_id}"
    assert quantity.metadata["commercial_finish_permission"] is False
    assert quantity.metadata["face_multiplicity"] == 1
    assert quantity.metadata["aggregate_quantity_id"] == result.quantity_evidence.quantity_id


def test_unresolved_or_replayed_wall_cannot_reuse_original_measured_child():
    original = _result()
    assert len(original.physical_wall_net_area_quantities) == 1
    assert replace(original, quantity_evidence=None).physical_wall_net_area_quantities == ()
    assert replace(original, canonical_walls=original.canonical_walls * 2).physical_wall_net_area_quantities == ()
    wall = original.canonical_walls[0]
    assert replace(
        original,
        canonical_walls=(replace(wall, net_area_m2=wall.net_area_m2 + 1.0),),
    ).physical_wall_net_area_quantities == ()


def test_wall_output_does_not_publish_second_face_or_material_from_geometry():
    result = _result()
    wall_qty = result.physical_wall_net_area_quantities
    assert len(wall_qty) == 1
    assert all(q.metadata["commercial_finish_permission"] is False for q in wall_qty)
    assert all(q.metadata["face_multiplicity"] == 1 for q in wall_qty)
