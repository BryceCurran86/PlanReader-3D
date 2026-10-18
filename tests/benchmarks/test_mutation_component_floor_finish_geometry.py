"""Synthetic mutation/red-team coverage for F.22 component floor finishes.

All project geometry and dimensions in this file are invented.  No benchmark IDs,
expected quantities, project names, source filenames, or gold values are used.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_component_floor_finish_geometry import derive_component_aware_floor_finish_area
from pb_multi_space_footprint_geometry import (
    MultiSpaceFootprintBuilder,
    MultiSpaceFootprintEngine,
    SpaceComponent,
    SpaceType,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _confirmed_main_and_verandah(*, thickness_m: float = 0.20):
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=12.0, width_m=8.0)
    builder.add_verandah(length_m=12.0, width_m=2.0, adjacency="front")
    footprint = builder.build()
    return footprint, derive_component_aware_floor_finish_area(footprint, thickness_m)


def test_enclosed_main_shrinks_to_clear_faces_but_verandah_stays_full_area() -> None:
    footprint, result = _confirmed_main_and_verandah(thickness_m=0.20)
    assert result is not None
    assert footprint.gross_floor_area_m2 == pytest.approx(120.0)
    assert result.structural_footprint_area_m2 == pytest.approx(120.0)
    assert result.main_clear_length_m == pytest.approx(11.6)
    assert result.main_clear_width_m == pytest.approx(7.6)
    assert result.main_clear_area_m2 == pytest.approx(88.16)
    assert result.open_verandah_area_m2 == pytest.approx(24.0)
    assert result.floor_finish_area_m2 == pytest.approx(112.16)


def test_wall_thickness_mutation_changes_only_clear_enclosed_component() -> None:
    footprint, thin = _confirmed_main_and_verandah(thickness_m=0.10)
    thick = derive_component_aware_floor_finish_area(footprint, 0.25)
    assert thin is not None and thick is not None
    assert thin.open_verandah_area_m2 == thick.open_verandah_area_m2 == pytest.approx(24.0)
    assert thick.main_clear_area_m2 < thin.main_clear_area_m2
    assert thick.floor_finish_area_m2 < thin.floor_finish_area_m2
    assert thin.structural_footprint_area_m2 == thick.structural_footprint_area_m2 == pytest.approx(120.0)


@pytest.mark.parametrize("bad_thickness", [None, 0.0, -0.1, float("inf"), float("nan")])
def test_missing_or_invalid_thickness_fails_closed(bad_thickness: float | None) -> None:
    footprint, _ = _confirmed_main_and_verandah()
    assert derive_component_aware_floor_finish_area(footprint, bad_thickness) is None


def test_partial_verandah_geometry_fails_closed() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=12.0, width_m=8.0)
    builder.add_verandah(length_m=12.0, width_m=None, adjacency="front")
    footprint = builder.build()
    assert derive_component_aware_floor_finish_area(footprint, 0.20) is None


def test_unsupported_ancillary_component_fails_closed() -> None:
    components = [
        SpaceComponent(
            space_id="main",
            space_type=SpaceType.MAIN_BUILDING.value,
            label="Main",
            length_m=12.0,
            width_m=8.0,
        ),
        SpaceComponent(
            space_id="annex",
            space_type=SpaceType.ANCILLARY.value,
            label="Annex",
            length_m=3.0,
            width_m=2.0,
        ),
    ]
    footprint = MultiSpaceFootprintEngine.evaluate(components)
    assert derive_component_aware_floor_finish_area(footprint, 0.20) is None


def test_void_geometry_fails_closed_instead_of_guessing_clear_face_offsets() -> None:
    components = [
        SpaceComponent(
            space_id="main",
            space_type=SpaceType.MAIN_BUILDING.value,
            label="Main",
            length_m=12.0,
            width_m=8.0,
        ),
        SpaceComponent(
            space_id="court",
            space_type=SpaceType.COURTYARD_VOID.value,
            label="Court",
            length_m=2.0,
            width_m=2.0,
            is_void=True,
        ),
    ]
    footprint = MultiSpaceFootprintEngine.evaluate(components)
    assert derive_component_aware_floor_finish_area(footprint, 0.20) is None


def test_physically_consuming_thickness_fails_closed() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=0.6, width_m=0.5)
    footprint = builder.build()
    assert derive_component_aware_floor_finish_area(footprint, 0.30) is None


def _synthetic_pdf(
    tmp_path: Path,
    *,
    wall_rows: tuple[str, str] | None,
    include_substructure_specs: bool = False,
) -> Path:
    lines = [
        "GROUND FLOOR PLAN",
        "SCALE 1:100",
        "12,000",
        "8,000",
        "2,000mm wide verandah finished in screed",
    ]
    if wall_rows is not None:
        lines.extend(wall_rows)
    if include_substructure_specs:
        lines.extend((
            "D.P.M. under floor bed",
            "A142 mesh reinforcement to floor bed",
            "100mm R.C. slab on well compacted hardcore",
        ))

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    y = 50
    for line in lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 22
    path = tmp_path / "synthetic_component_floor.pdf"
    doc.save(path)
    doc.close()
    return path


def _pred_map(path: Path):
    return {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(path)}


def test_extractor_uses_clear_main_plus_full_verandah_when_thickness_corroborates(tmp_path: Path) -> None:
    preds = _pred_map(_synthetic_pdf(
        tmp_path,
        wall_rows=("200 11,600 200", "200 7,600 200"),
    ))
    floor = preds["floor_screed"]
    assert floor.quantity == pytest.approx(112.16)
    assert floor.metadata["structural_bed_area_m2"] == pytest.approx(120.0)
    assert floor.metadata["main_clear_floor_area_m2"] == pytest.approx(88.16)
    assert floor.metadata["open_verandah_floor_area_m2"] == pytest.approx(24.0)
    assert floor.metadata["floor_finish_area_derivation"] == "component_clear_main_plus_evidenced_verandah"


def test_extractor_without_corroborated_thickness_preserves_existing_outer_area(tmp_path: Path) -> None:
    preds = _pred_map(_synthetic_pdf(tmp_path, wall_rows=None))
    floor = preds["floor_screed"]
    assert floor.quantity == pytest.approx(120.0)
    assert "floor_finish_area_derivation" not in floor.metadata


def test_conflicting_thickness_chains_preserve_existing_outer_area(tmp_path: Path) -> None:
    preds = _pred_map(_synthetic_pdf(
        tmp_path,
        wall_rows=("150 11,700 150", "250 7,500 250"),
    ))
    assert preds["floor_screed"].quantity == pytest.approx(120.0)


def test_substructure_siblings_keep_structural_footprint_not_clear_finish(tmp_path: Path) -> None:
    preds = _pred_map(_synthetic_pdf(
        tmp_path,
        wall_rows=("200 11,600 200", "200 7,600 200"),
        include_substructure_specs=True,
    ))
    assert preds["floor_screed"].quantity == pytest.approx(112.16)
    assert preds["substructure_bed_dpm"].quantity == pytest.approx(120.0)
    assert preds["substructure_a142_mesh"].quantity == pytest.approx(120.0)
    assert preds["substructure_surface_bed"].quantity == pytest.approx(120.0)


def test_overlapping_verandah_does_not_double_count_floor_finish() -> None:
    # Both individually measured rectangles can appear CONFIRMED even though
    # their physical areas overlap; additivity is not geometry authority.
    components = [
        SpaceComponent(
            space_id="main", space_type=SpaceType.MAIN_BUILDING.value,
            label="Enclosed", length_m=8.0, width_m=6.0,
            polygon=[(0, 0), (8, 0), (8, 6), (0, 6)],
        ),
        SpaceComponent(
            space_id="porch", space_type=SpaceType.VERANDAH.value,
            label="Covered external", length_m=8.0, width_m=2.0,
            polygon=[(0, 5), (8, 5), (8, 7), (0, 7)],
        ),
    ]
    footprint = MultiSpaceFootprintEngine.evaluate(components)
    assert footprint.status == "partial_missing_components"
    assert "overlapping_source_solid_areas" in footprint.metadata["source_geometry_conflicts"]
    assert footprint.gross_floor_area_m2 == pytest.approx(64.0)
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None
    reversed_footprint = MultiSpaceFootprintEngine.evaluate(list(reversed(components)))
    assert derive_component_aware_floor_finish_area(reversed_footprint, 0.2) is None


def test_shared_threshold_boundary_is_not_area_overlap() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=8.0, width_m=6.0)
    builder.add_verandah(length_m=8.0, width_m=2.0, adjacency="front")
    result = derive_component_aware_floor_finish_area(builder.build(), 0.2)
    assert result is not None
    # At a shared doorway, coverings finish at their own face boundaries;
    # the two separate areas are not a duplicated 2m strip of floor.
    assert result.main_clear_area_m2 == pytest.approx(7.6 * 5.6)
    assert result.open_verandah_area_m2 == pytest.approx(16.0)
    assert result.floor_finish_area_m2 == pytest.approx(58.56)


def test_forged_rectangular_dimensions_against_source_polygon_abstain() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=8.0, width_m=6.0)
    footprint = builder.build()
    footprint.components[0].length_m = 9.0
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None


def test_forged_area_against_exact_dimension_product_abstains() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=8.0, width_m=6.0)
    footprint = builder.build()
    footprint.components[0].area_m2 = 50.0
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None


def test_parallelogram_is_not_a_verified_rectangular_clear_floor() -> None:
    comp = SpaceComponent(
        space_id="main", space_type=SpaceType.MAIN_BUILDING.value,
        label="Skewed", length_m=8.0, width_m=6.0,
        polygon=[(0, 0), (8, 0), (9, 6), (1, 6)],
    )
    footprint = MultiSpaceFootprintEngine.evaluate([comp])
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None


def test_duplicate_source_component_identity_cannot_mint_two_finish_areas() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=8.0, width_m=6.0)
    builder.add_verandah(length_m=8.0, width_m=2.0, adjacency="front")
    footprint = builder.build()
    footprint.components[1].space_id = footprint.components[0].space_id
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None


def test_missing_original_component_placement_prevents_compound_area() -> None:
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=8.0, width_m=6.0)
    builder.add_verandah(length_m=8.0, width_m=2.0, adjacency="front")
    footprint = builder.build()
    footprint.components[1].polygon = []
    assert derive_component_aware_floor_finish_area(footprint, 0.2) is None


def test_rotated_evidenced_rectangle_keeps_clear_face_area() -> None:
    # A physical orthogonal room need not align with the PDF axes.
    import math
    theta = math.radians(29)
    ux, uy = math.cos(theta), math.sin(theta)
    vx, vy = -uy, ux
    poly = [
        (0.0, 0.0),
        (8.0 * ux, 8.0 * uy),
        (8.0 * ux + 6.0 * vx, 8.0 * uy + 6.0 * vy),
        (6.0 * vx, 6.0 * vy),
    ]
    comp = SpaceComponent(
        space_id="main", space_type=SpaceType.MAIN_BUILDING.value,
        label="Rotated", length_m=8.0, width_m=6.0, polygon=poly,
    )
    footprint = MultiSpaceFootprintEngine.evaluate([comp])
    result = derive_component_aware_floor_finish_area(footprint, 0.2)
    assert result is not None
    assert result.floor_finish_area_m2 == pytest.approx(7.6 * 5.6)
