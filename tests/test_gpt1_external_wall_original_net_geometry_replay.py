"""Recompute original gross-minus-all-voids before external per-wall seal.

Source-shaped adversarial fixtures exercise the actual publisher and sealed
consumer. They grant no original PDF, material finish or customer FIRM authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from shapely import wkb
from shapely.affinity import translate

from pb_live_external_wall_surface_area_quantity_publication import (
    publish_live_per_wall_surface_area_quantities,
    seal_live_per_wall_surface_area_run,
)
from tests.test_gpt1_source_closed_external_per_wall_surface_m2 import _produced


def _mutated_wall(publication, **changes):
    wall = publication.canonical_walls[0]
    return replace(
        publication, canonical_walls=(replace(wall, **changes),)
    )


def _same_area_translated_wkb(hex_wkb: str) -> str:
    geometry = wkb.loads(bytes.fromhex(hex_wkb))
    shifted = translate(geometry, xoff=100.0, yoff=100.0)
    assert shifted.is_valid
    assert shifted.area == pytest.approx(geometry.area)
    assert not shifted.equals(geometry)
    return shifted.wkb_hex


@pytest.mark.parametrize("tamper", (
    "net_polygon_same_area_displaced",
    "gross_polygon_same_area_displaced",
    "void_same_area_shifted",
    "void_nan_coordinate",
    "gross_wkb_invalid",
    "gross_net_and_void_frame_displaced",
    "gross_length_metric_mismatch",
))
def test_original_net_wall_geometry_cannot_be_reissued_from_changed_face(
    tamper,
):
    original = _produced()
    wall = original.canonical_walls[0]
    assert len(wall.opening_voids) == 1
    baseline = publish_live_per_wall_surface_area_quantities(original)
    assert len(baseline) == 1
    if tamper == "net_polygon_same_area_displaced":
        changed = _mutated_wall(
            original,
            net_polygon_wkb_hex=_same_area_translated_wkb(
                wall.net_polygon_wkb_hex
            ),
        )
    elif tamper == "gross_polygon_same_area_displaced":
        changed = _mutated_wall(
            original,
            gross_polygon_wkb_hex=_same_area_translated_wkb(
                wall.gross_polygon_wkb_hex
            ),
        )
    elif tamper == "void_same_area_shifted":
        void = wall.opening_voids[0]
        shifted = replace(void, u0=void.u0 + 0.05, u1=void.u1 + 0.05)
        changed = _mutated_wall(original, opening_voids=(shifted,))
    elif tamper == "void_nan_coordinate":
        void = wall.opening_voids[0]
        changed = _mutated_wall(
            original, opening_voids=(replace(void, u0=float("nan")),)
        )
    elif tamper == "gross_net_and_void_frame_displaced":
        # Gross-minus-void replay alone accepts this coordinated shift:
        # all three geometries still agree, but the original producer fixes
        # the wall-local gross domain to box(0,0,length_m,height_m).
        void = wall.opening_voids[0]
        changed = _mutated_wall(
            original,
            gross_polygon_wkb_hex=_same_area_translated_wkb(
                wall.gross_polygon_wkb_hex
            ),
            net_polygon_wkb_hex=_same_area_translated_wkb(
                wall.net_polygon_wkb_hex
            ),
            opening_voids=(replace(
                void,
                u0=void.u0 + 100.0, u1=void.u1 + 100.0,
                z0=void.z0 + 100.0, z1=void.z1 + 100.0,
            ),),
        )
    elif tamper == "gross_length_metric_mismatch":
        changed = _mutated_wall(original, length_m=wall.length_m + 1.0)
    else:
        changed = _mutated_wall(
            original, gross_polygon_wkb_hex="01030000"
        )

    # The original aggregate receipt roster and numeric total have not
    # changed. That is precisely why the real downstream geometry replay
    # must refuse to mint a new source-closed per-wall quantity.
    assert changed.quantity_evidence == original.quantity_evidence
    assert changed.external_wall_ids == original.external_wall_ids
    assert changed.opening_universe_record_ids == original.opening_universe_record_ids
    assert publish_live_per_wall_surface_area_quantities(changed) == ()
    with pytest.raises(
        ValueError, match="no source-complete original external wall surfaces"
    ):
        seal_live_per_wall_surface_area_run(
            changed, workspace_id=7, project_id="source-wall-replay",
        )
    assert publish_live_per_wall_surface_area_quantities(original) == baseline


def test_original_gross_minus_union_source_wall_seal_stays_byte_identical():
    original = _produced()
    wall_before = original.canonical_walls
    aggregate_before = original.quantity_evidence
    quantities_before = publish_live_per_wall_surface_area_quantities(original)
    assert len(quantities_before) == 1
    first = seal_live_per_wall_surface_area_run(
        original, workspace_id=7, project_id="source-wall-replay",
    )
    second = seal_live_per_wall_surface_area_run(
        original, workspace_id=7, project_id="source-wall-replay",
    )
    assert first.to_json() == second.to_json()
    assert len(first.quantities) == len(quantities_before) == 1
    assert first.quantities[0].lineage_ok
    assert not first.quantities[0].abstained
    assert quantities_before[0].metadata["commercial_finish_permission"] is False
    assert original.canonical_walls == wall_before
    assert original.quantity_evidence == aggregate_before
    assert publish_live_per_wall_surface_area_quantities(original) == quantities_before


@pytest.mark.parametrize("tamper", (
    "wall_local_frame",
    "wall_coordinate_unit",
    "opening_identity_roster",
    "void_wall_local_frame",
    "void_coordinate_unit",
    "void_profile_kind",
    "void_opening_identity",
    "coordinated_frame_substitution",
    "coordinated_unit_substitution",
))
def test_original_opening_identity_and_metric_frame_cannot_be_reissued(
    tamper,
):
    original = _produced()
    wall = original.canonical_walls[0]
    assert len(wall.opening_voids) == 1
    void = wall.opening_voids[0]
    baseline = publish_live_per_wall_surface_area_quantities(original)
    assert len(baseline) == 1

    if tamper == "wall_local_frame":
        changed = _mutated_wall(original, wall_local_frame_id="foreign-frame")
    elif tamper == "wall_coordinate_unit":
        changed = _mutated_wall(original, coordinate_unit="feet")
    elif tamper == "opening_identity_roster":
        changed = _mutated_wall(
            original, opening_identity_ids=("foreign-opening",)
        )
    elif tamper == "void_wall_local_frame":
        changed = _mutated_wall(
            original, opening_voids=(replace(
                void, wall_local_frame_id="foreign-frame",
            ),),
        )
    elif tamper == "void_coordinate_unit":
        changed = _mutated_wall(
            original, opening_voids=(replace(
                void, coordinate_unit="feet",
            ),),
        )
    elif tamper == "void_profile_kind":
        changed = _mutated_wall(
            original, opening_voids=(replace(
                void, profile_kind="unsupported-shape",
            ),),
        )
    elif tamper == "void_opening_identity":
        changed = _mutated_wall(
            original, opening_voids=(replace(
                void, opening_identity_id="foreign-opening",
            ),),
        )
    elif tamper == "coordinated_frame_substitution":
        changed = _mutated_wall(
            original,
            wall_local_frame_id="foreign-frame",
            opening_voids=(replace(
                void, wall_local_frame_id="foreign-frame",
            ),),
        )
    else:
        changed = _mutated_wall(
            original,
            coordinate_unit="feet",
            opening_voids=(replace(void, coordinate_unit="feet"),),
        )

    # A source identity swap does not change either geometry, area, receipt
    # roster or original aggregate contract; the real issuer must catch it.
    altered_wall = changed.canonical_walls[0]
    assert changed.quantity_evidence == original.quantity_evidence
    assert altered_wall.gross_polygon_wkb_hex == wall.gross_polygon_wkb_hex
    assert altered_wall.net_polygon_wkb_hex == wall.net_polygon_wkb_hex
    assert altered_wall.net_area_m2 == wall.net_area_m2
    assert changed.physical_void_record_ids == original.physical_void_record_ids
    assert publish_live_per_wall_surface_area_quantities(changed) == ()
    with pytest.raises(
        ValueError, match="no source-complete original external wall surfaces"
    ):
        seal_live_per_wall_surface_area_run(
            changed, workspace_id=7, project_id="source-wall-replay",
        )
    assert publish_live_per_wall_surface_area_quantities(original) == baseline
