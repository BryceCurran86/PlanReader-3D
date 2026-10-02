"""Deterministic fixtures for the hardened opening/surface authority contract.

These fixtures intentionally test authority boundaries rather than project-specific
coordinates or expected benchmark quantities.
"""
from __future__ import annotations

import pytest

from pb_hardened_authority_contract import (
    InternalElevationViewport,
    PhysicalWallFace,
    TileExtent,
    WallViewIdentity,
    build_opening_evidence_fingerprint,
    build_physical_opening_identity_fingerprint,
    normalize_geometry_for_identity,
    resolve_internal_elevation_wall_surface,
    resolve_opening_measurement,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_cross_trade_geometry_reuse import derive_wall_trade_quantities


def _opening_geometry():
    return ((100.0, 70.0), (140.0, 70.0), (140.0, 110.0), (100.0, 110.0))


def _wall():
    return {
        "canonical_wall_id": "wall_01",
        "length_m": 10.0,
        "net_area_m2": 23.4,
        "role": "internal",
        "physical_identity_resolved": True,
        "quantity_complete": True,
        "evidence_ids": ["wall-authority-1"],
    }


def test_fixture_1_physical_identity_is_stable_across_detector_versions():
    geometry = _opening_geometry()
    physical_a = build_physical_opening_identity_fingerprint(
        document_id="doc",
        source_sha256="a" * 64,
        page_id="3",
        viewport_id="plan-vp",
        geometry=geometry,
    )
    physical_b = build_physical_opening_identity_fingerprint(
        document_id="doc",
        source_sha256="a" * 64,
        page_id="3",
        viewport_id="plan-vp",
        geometry=geometry,
    )
    evidence_a = build_opening_evidence_fingerprint(
        physical_identity_fingerprint=physical_a,
        observation_ids=("obs-1", "obs-2"),
        producer_method="opening-detector",
        producer_version="1.0",
        producer_generation=1,
    )
    evidence_b = build_opening_evidence_fingerprint(
        physical_identity_fingerprint=physical_b,
        observation_ids=("obs-1b", "obs-2b"),
        producer_method="opening-detector",
        producer_version="2.0",
        producer_generation=2,
    )

    assert physical_a == physical_b
    assert evidence_a != evidence_b


def test_fixture_2_reordered_vertices_keep_the_same_physical_identity():
    original = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))
    reordered = ((4.0, 2.0), (0.0, 2.0), (0.0, 0.0), (4.0, 0.0))

    assert normalize_geometry_for_identity(original) == normalize_geometry_for_identity(reordered)

    left = build_physical_opening_identity_fingerprint(
        document_id="doc",
        source_sha256="b" * 64,
        page_id="1",
        viewport_id="plan-vp",
        geometry=original,
    )
    right = build_physical_opening_identity_fingerprint(
        document_id="doc",
        source_sha256="b" * 64,
        page_id="1",
        viewport_id="plan-vp",
        geometry=reordered,
    )
    assert left == right


def test_fixture_3_missing_scale_never_invents_geometry_derived_dimensions():
    result = resolve_opening_measurement(
        figured_dimension_mm=None,
        geometry_extent_points=72.0,
        scale_status=EvidenceResolutionStatus.ABSTAINED,
        points_per_mm=None,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.value_mm is None
    assert result.measurement_source is None


@pytest.mark.parametrize(
    "scale_status,points_per_mm",
    [
        (EvidenceResolutionStatus.ABSTAINED, None),
        (EvidenceResolutionStatus.CONFLICT, None),
        (EvidenceResolutionStatus.CONFLICT, 0.25),
    ],
)
def test_fixture_4_authenticated_figured_dimension_survives_missing_or_conflicting_scale(
    scale_status,
    points_per_mm,
):
    result = resolve_opening_measurement(
        figured_dimension_mm=900.0,
        geometry_extent_points=72.0,
        scale_status=scale_status,
        points_per_mm=points_per_mm,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.value_mm == pytest.approx(900.0)
    assert result.measurement_source == "figured_dimension"


def test_fixture_5_internal_elevation_text_cannot_tile_a_plan_room_by_spatial_containment():
    plan_viewport = "plan-vp"
    elevation_viewport = InternalElevationViewport(
        viewport_id="elev-vp",
        page_id="7",
        evidence_ids=("viewport-evidence",),
    )

    # The text/fill happens to use coordinates numerically inside the plan-room
    # polygon, but it belongs to a different viewport and has no wall-view/face.
    result = resolve_internal_elevation_wall_surface(
        viewport=elevation_viewport,
        wall_view=None,
        wall_face=None,
        tile_extent=None,
        plan_room_viewport_id=plan_viewport,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.canonical_wall_surface is None
    assert result.quantity_m2 is None


def test_fixture_6_tile_quantity_requires_authenticated_internal_elevation_wall_face_extent():
    viewport = InternalElevationViewport(
        viewport_id="elev-vp",
        page_id="7",
        evidence_ids=("viewport-evidence",),
    )
    wall_view = WallViewIdentity(
        wall_view_id="wall-view-01",
        viewport_id="elev-vp",
        canonical_wall_id="wall_01",
        evidence_ids=("wall-view-evidence",),
    )
    wall_face = PhysicalWallFace(
        physical_wall_face_id="face-01",
        wall_view_id="wall-view-01",
        canonical_wall_id="wall_01",
        evidence_ids=("wall-face-evidence",),
    )
    tile_extent = TileExtent(
        tile_extent_id="tile-extent-01",
        viewport_id="elev-vp",
        wall_view_id="wall-view-01",
        physical_wall_face_id="face-01",
        area_m2=3.6,
        evidence_ids=("tile-extent-evidence",),
    )

    resolved = resolve_internal_elevation_wall_surface(
        viewport=viewport,
        wall_view=wall_view,
        wall_face=wall_face,
        tile_extent=tile_extent,
        plan_room_viewport_id="plan-vp",
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.quantity_m2 == pytest.approx(3.6)
    assert resolved.canonical_wall_surface is not None

    # A bare face id no longer authorizes whole-wall tiling.
    unsafe_specs = {
        "tiling": {
            "material": "Ceramic wall tile",
            "section": "Internal",
            "physical_face_ids": ["face-01"],
            "evidence_ids": ["spec-tile"],
        }
    }
    assert derive_wall_trade_quantities(_wall(), unsafe_specs) == []

    safe_specs = {
        "tiling": {
            "material": "Ceramic wall tile",
            "section": "Internal",
            "evidence_ids": ["spec-tile"],
            "authenticated_wall_face_extents": [
                resolved.canonical_wall_surface.to_dict(),
            ],
        }
    }
    quantities = derive_wall_trade_quantities(_wall(), safe_specs)
    assert len(quantities) == 1
    assert quantities[0].trade_scope == "tiling"
    assert quantities[0].quantity == pytest.approx(3.6)
    assert quantities[0].quantity != pytest.approx(_wall()["net_area_m2"])
