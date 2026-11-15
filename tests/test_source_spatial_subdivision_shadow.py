"""Tests for source-owned spatial subdivision (P4 shadow).

Validates:
- Explicit outside face resolution.
- Internal courtyard hole classification (open-to-sky void).
- Attached carport / outdoor region separation.
- Disconnected decoy structure rejection.
- Zero FIRM customer quantities, zero frozen120 score changes.
"""
from __future__ import annotations

from types import SimpleNamespace
from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_numbered_space_key import NumberedSpaceKeyResult, SpaceKeyEntry
from pb_source_spatial_subdivision_shadow import (
    SpatialRegionKind,
    build_source_spatial_subdivision,
    REASON_DISCONNECTED_DECOY,
    REASON_INSUFFICIENT_WALLS,
    REASON_SPATIAL_OK,
)


def _strip(
    source_id: int, bounds: tuple[float, float, float, float]
) -> SimpleNamespace:
    return SimpleNamespace(
        polygon=box(*bounds),
        path_index=source_id,
        native_path_indices=lambda: (source_id,),
    )


def _drawing(layer: str = "Enclosure_WallExternal") -> dict:
    return {"layer": layer, "fill": (0.0, 0.0, 0.0)}


def test_explicit_outside_face_resolved_with_one_unbounded_region():
    """A 4-wall room creates an outside face and an interior room."""
    # Outer box: left 100, top 100, right 300, bottom 300, thickness 10
    bars = [
        _strip(1, (100.0, 100.0, 300.0, 110.0)),  # top
        _strip(2, (100.0, 290.0, 300.0, 300.0)),  # bottom
        _strip(3, (100.0, 100.0, 110.0, 300.0)),  # left
        _strip(4, (290.0, 100.0, 300.0, 300.0)),  # right
    ]
    drawings = [_drawing() for _ in bars]
    res = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0.0, 0.0, 500.0, 500.0)
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.reason == REASON_SPATIAL_OK
    assert res.has_explicit_outside_face is True
    assert res.outside_region_id != ""
    assert res.interior_room_count == 1
    assert res.courtyard_hole_count == 0
    assert res.attached_outdoor_count == 0
    assert res.disconnected_decoy_count == 0
    assert res.measurement_authorized is False
    assert res.commercial_publishable is False
    assert res.official_frozen120_score_change == 0

    outside = next(
        r for r in res.regions
        if r.kind == SpatialRegionKind.OUTSIDE_UNBOUNDED
    )
    assert outside.label == "OUTSIDE"

    # All 4 wall faces are exterior envelope
    for face in res.boundary_faces:
        assert face.is_exterior_envelope is True
        assert face.is_interior_partition is False


def test_internal_courtyard_hole_classified_and_excluded_from_living():
    """An internal courtyard hole enclosed by walls is recognized as a void."""
    # Outer ring: 50..350 x 50..350 (thickness 10)
    # Inner ring: 150..250 x 150..250 (thickness 10)
    bars = [
        # Outer walls
        _strip(1, (50.0, 50.0, 350.0, 60.0)),
        _strip(2, (50.0, 340.0, 350.0, 350.0)),
        _strip(3, (50.0, 50.0, 60.0, 350.0)),
        _strip(4, (340.0, 50.0, 350.0, 350.0)),
        # Inner courtyard walls
        _strip(5, (150.0, 150.0, 250.0, 160.0)),
        _strip(6, (150.0, 240.0, 250.0, 250.0)),
        _strip(7, (150.0, 150.0, 160.0, 250.0)),
        _strip(8, (240.0, 150.0, 250.0, 250.0)),
    ]
    drawings = [_drawing() for _ in bars]
    # Space key identifies space inside 150..250 as COURTYARD
    space_key = NumberedSpaceKeyResult(
        status="CANDIDATE",
        reason="test_key",
        page_index=0,
        source_sha256="test_sha",
        entries=(
            SpaceKeyEntry(
                number=12,
                name="LIVING COURT",
                semantic_role="outdoor_or_nonroom_candidate",
                key_label_bbox_pdf_pts=(10.0, 10.0, 40.0, 20.0),
                number_markers_pdf_pts=((200.0, 200.0),),
            ),
        ),
    )
    res = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0.0, 0.0, 500.0, 500.0), space_key=space_key
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.courtyard_hole_count == 1
    courtyard = next(
        r for r in res.regions
        if r.kind == SpatialRegionKind.INTERNAL_COURTYARD_HOLE
    )
    assert courtyard.label == "LIVING COURT"
    assert courtyard.is_hole_in_building is True
    assert courtyard.is_conditioned_living is False

    # Check that courtyard boundary faces are marked is_courtyard_envelope
    ct_faces = [f for f in res.boundary_faces if f.is_courtyard_envelope]
    assert len(ct_faces) >= 4


def test_attached_carport_outdoor_region_and_thermal_envelope_wall():
    """An attached carport region creates an attached outdoor region."""
    # House: 100..250 x 100..250
    # Carport attached on right: 250..350 x 100..250 (sharing wall at x=250)
    bars = [
        # House walls
        _strip(1, (100.0, 100.0, 250.0, 110.0)),  # top house
        _strip(2, (100.0, 240.0, 250.0, 250.0)),  # bottom house
        _strip(3, (100.0, 100.0, 110.0, 250.0)),  # left house
        _strip(4, (240.0, 100.0, 250.0, 250.0)),  # shared party wall
        # Carport outer walls
        _strip(5, (250.0, 100.0, 350.0, 110.0)),  # top carport
        _strip(6, (250.0, 240.0, 350.0, 250.0)),  # bottom carport
        _strip(7, (340.0, 100.0, 350.0, 250.0)),  # right carport
    ]
    drawings = [_drawing() for _ in bars]
    space_key = NumberedSpaceKeyResult(
        status="CANDIDATE",
        reason="test_key",
        page_index=0,
        source_sha256="test_sha",
        entries=(
            SpaceKeyEntry(
                number=11,
                name="CARPORT",
                semantic_role="outdoor_or_nonroom_candidate",
                key_label_bbox_pdf_pts=(10.0, 10.0, 40.0, 20.0),
                number_markers_pdf_pts=((290.0, 180.0),),
            ),
        ),
    )
    res = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0.0, 0.0, 500.0, 500.0), space_key=space_key
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.attached_outdoor_count == 1
    carport = next(
        r for r in res.regions
        if r.kind == SpatialRegionKind.ATTACHED_OUTDOOR_REGION
    )
    assert carport.label == "CARPORT"
    assert carport.is_conditioned_living is False

    # The shared wall at path_id=4 separates interior living from carport
    shared_face = next(f for f in res.boundary_faces if 4 in f.native_path_ids)
    assert shared_face.is_exterior_envelope is True


def test_disconnected_structure_or_decoy_isolated_and_abstains():
    """Disconnected decoy wall bodies are segregated and marked ABSTAINED."""
    # Main house: 4 walls at 100..200
    # Disconnected decoy: 2 detached lines far away at 800..900
    bars = [
        _strip(1, (100.0, 100.0, 200.0, 110.0)),
        _strip(2, (100.0, 190.0, 200.0, 200.0)),
        _strip(3, (100.0, 100.0, 110.0, 200.0)),
        _strip(4, (190.0, 100.0, 200.0, 200.0)),
        # Disconnected decoy strokes far away
        _strip(99, (800.0, 800.0, 850.0, 810.0)),
        _strip(100, (800.0, 850.0, 850.0, 860.0)),
    ]
    drawings = [_drawing() for _ in bars]
    res = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0.0, 0.0, 1000.0, 1000.0)
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.disconnected_decoy_count == 1
    decoy = next(
        r for r in res.regions
        if r.kind == SpatialRegionKind.DISCONNECTED_STRUCTURE_OR_DECOY
    )
    assert decoy.status == EvidenceResolutionStatus.ABSTAINED
    assert decoy.reason == REASON_DISCONNECTED_DECOY
    assert set(decoy.bounding_native_path_ids) == {99, 100}
    assert res.primary_building_body_count == 4


def test_insufficient_wall_bars_abstains_without_crashing():
    """Fewer than 4 wall bars fails closed."""
    bars = [
        _strip(1, (100.0, 100.0, 200.0, 110.0)),
        _strip(2, (100.0, 190.0, 200.0, 200.0)),
    ]
    drawings = [_drawing() for _ in bars]
    res = build_source_spatial_subdivision(drawings, bars=bars)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == REASON_INSUFFICIENT_WALLS
    assert res.total_region_count == 0


def test_zero_quantities_and_zero_frozen120_score():
    """Strict fail-closed safety guarantees on all results."""
    bars = [
        _strip(1, (100.0, 100.0, 300.0, 110.0)),
        _strip(2, (100.0, 290.0, 300.0, 300.0)),
        _strip(3, (100.0, 100.0, 110.0, 300.0)),
        _strip(4, (290.0, 100.0, 300.0, 300.0)),
    ]
    drawings = [_drawing() for _ in bars]
    res = build_source_spatial_subdivision(drawings, bars=bars)
    d = res.to_dict()
    assert d["physical_space_authenticated"] is False
    assert d["measurement_authorized"] is False
    assert d["commercial_publishable"] is False
    assert d["official_frozen120_score_change"] == 0
    for r in d["regions"]:
        assert r["physical_space_authenticated"] is False
        assert r["measurement_authorized"] is False
