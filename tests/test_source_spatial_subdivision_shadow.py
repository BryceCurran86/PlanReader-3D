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
    REASON_DISCONNECTED_DECOY,
    REASON_INSUFFICIENT_WALLS,
    REASON_SPATIAL_OK,
    SpatialRegionKind,
    build_source_spatial_subdivision,
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


def test_closed_detached_wall_cycle_is_decoy_only_not_conditioned_interior():
    """A complete detached structure is not also a primary enclosed room."""
    bars = [
        # Four genuinely connected source-owned primary building wall bars.
        _strip(1, (100.0, 100.0, 300.0, 110.0)),
        _strip(2, (100.0, 290.0, 300.0, 300.0)),
        _strip(3, (100.0, 100.0, 110.0, 300.0)),
        _strip(4, (290.0, 100.0, 300.0, 300.0)),
        # Four fully closed, isolated decoy wall bars. Unlike two detached
        # strokes these make a second free-space polygon and previously
        # leaked into INTERIOR_ENCLOSED_ROOM candidates.
        _strip(5, (750.0, 750.0, 850.0, 760.0)),
        _strip(6, (750.0, 840.0, 850.0, 850.0)),
        _strip(7, (750.0, 750.0, 760.0, 850.0)),
        _strip(8, (840.0, 750.0, 850.0, 850.0)),
    ]
    res = build_source_spatial_subdivision(
        [_drawing() for _ in bars],
        bars=bars,
        page_rect=(0.0, 0.0, 1000.0, 1000.0),
    )
    rooms = [r for r in res.regions if r.kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM]
    decoys = [r for r in res.regions if r.kind == SpatialRegionKind.DISCONNECTED_STRUCTURE_OR_DECOY]
    assert res.primary_building_body_count == 4
    assert res.interior_room_count == 1
    assert res.disconnected_decoy_count == 1
    assert len(rooms) == 1 and len(decoys) == 1
    # A detached CLOSED geometry still has a reviewable polygon; its wall
    # owners must not become another conditioned room or customer area.
    unverified = [
        item for item in res.regions
        if item.kind == SpatialRegionKind.UNVERIFIED_ENCLOSED_CANDIDATE
    ]
    assert res.unverified_enclosed_count == 1
    assert len(unverified) == 1
    assert set(unverified[0].bounding_native_path_ids) == {5, 6, 7, 8}
    assert unverified[0].status == EvidenceResolutionStatus.ABSTAINED
    assert unverified[0].is_conditioned_living is False
    assert unverified[0].measurement_authorized is False
    assert set(rooms[0].bounding_native_path_ids) == {1, 2, 3, 4}
    assert set(decoys[0].bounding_native_path_ids) == {5, 6, 7, 8}
    assert not set(rooms[0].bounding_native_path_ids) & set(decoys[0].bounding_native_path_ids)
    assert rooms[0].measurement_authorized is False
    assert decoys[0].measurement_authorized is False
    assert res.official_frozen120_score_change == 0


def test_tiny_enclosed_wall_ink_void_is_not_room_sized_candidate():
    """Scale-relative wall-thickness filter preserves source without claiming room."""
    bars = [
        _strip(1, (100, 100, 300, 110)),
        _strip(2, (100, 290, 300, 300)),
        _strip(3, (100, 100, 110, 300)),
        _strip(4, (290, 100, 300, 300)),
        _strip(5, (750, 750, 780, 753)),
        _strip(6, (750, 777, 780, 780)),
        _strip(7, (750, 750, 753, 780)),
        _strip(8, (777, 750, 780, 780)),
    ]
    result = build_source_spatial_subdivision(
        [_drawing() for _ in bars],
        bars=bars,
        page_rect=(0, 0, 1000, 1000),
    )
    tiny = [
        record for record in result.regions
        if record.kind == SpatialRegionKind.NATIVE_SOURCE_MICRO_VOID
    ]
    assert result.interior_room_count == 1
    assert result.disconnected_decoy_count == 1
    assert result.micro_source_void_count == 1
    assert result.unverified_enclosed_count == 0
    assert len(tiny) == 1
    assert set(tiny[0].bounding_native_path_ids) == {5, 6, 7, 8}
    assert tiny[0].status == EvidenceResolutionStatus.ABSTAINED
    assert tiny[0].is_conditioned_living is False
    assert tiny[0].measurement_authorized is False
    assert result.commercial_publishable is False
    assert result.official_frozen120_score_change == 0


def test_partial_building_ring_with_adjacent_outside_walls_abstains_and_emits_no_rooms():
    """Unclosed building cycle with adjacent outside walls abstains and emits zero rooms."""
    # Left ring (bars 1..4): x100..300, y100..300
    # Right wing (bars 5..8): x325..525, y100..300 (gap = 25 pt, doorway scale)
    bars = [
        _strip(1, (100.0, 100.0, 300.0, 110.0)),
        _strip(2, (100.0, 290.0, 300.0, 300.0)),
        _strip(3, (100.0, 100.0, 110.0, 300.0)),
        _strip(4, (290.0, 100.0, 300.0, 300.0)),
        _strip(5, (325.0, 100.0, 525.0, 110.0)),
        _strip(6, (325.0, 290.0, 525.0, 300.0)),
        _strip(7, (325.0, 100.0, 335.0, 300.0)),
        _strip(8, (515.0, 100.0, 525.0, 300.0)),
    ]
    res = build_source_spatial_subdivision(
        [_drawing() for _ in bars],
        bars=bars,
        page_rect=(0.0, 0.0, 1000.0, 1000.0),
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.reason == "source_exterior_other_wall_ink_outside_candidate"
    assert res.interior_room_count == 0
    assert res.unverified_enclosed_count >= 1
    assert res.commercial_publishable is False
    assert res.official_frozen120_score_change == 0
    for r in res.regions:
        assert r.physical_space_authenticated is False
        assert r.measurement_authorized is False
        if r.kind == SpatialRegionKind.UNVERIFIED_ENCLOSED_CANDIDATE:
            assert r.is_conditioned_living is False
            assert r.status == EvidenceResolutionStatus.ABSTAINED


def test_alfresco_classified_as_attached_outdoor_and_excluded_from_living():
    """Outdoor alfresco is classified as attached outdoor and excluded from living footprint."""
    # Main living room (bars 1..4): x100..300, y100..300
    # Attached alfresco (bars 2, 5, 6, 7): x100..300, y300..450 sharing wall 2 at y=290..300
    bars = [
        _strip(1, (100.0, 100.0, 300.0, 110.0)),
        _strip(2, (100.0, 295.0, 300.0, 305.0)),  # shared wall
        _strip(3, (100.0, 100.0, 110.0, 305.0)),
        _strip(4, (290.0, 100.0, 300.0, 305.0)),
        _strip(5, (100.0, 440.0, 300.0, 450.0)),  # outer alfresco edge
        _strip(6, (100.0, 305.0, 110.0, 450.0)),
        _strip(7, (290.0, 305.0, 300.0, 450.0)),
    ]
    words = [
        (150.0, 180.0, 220.0, 200.0, "LIVING"),
        (150.0, 360.0, 230.0, 380.0, "ALFRESCO"),
    ]
    res = build_source_spatial_subdivision(
        [_drawing() for _ in bars],
        bars=bars,
        page_rect=(0.0, 0.0, 1000.0, 1000.0),
        text_words=words,
    )
    outdoor = [
        r for r in res.regions
        if r.kind == SpatialRegionKind.ATTACHED_OUTDOOR_REGION
    ]
    assert len(outdoor) == 1
    assert outdoor[0].label == "ALFRESCO"
    assert outdoor[0].is_conditioned_living is False
    assert outdoor[0].is_hole_in_building is False
    assert outdoor[0].measurement_authorized is False
    # The dividing wall between living and alfresco is an exterior thermal envelope wall
    shared_face = next(
        f for f in res.boundary_faces if "body:2:" in f.wall_body_id  # bar 2
    )
    assert shared_face.is_exterior_envelope is True


def test_isolated_freestanding_post_excluded_from_wall_bars_and_exterior_cycle():
    """Isolated timber post (e.g. 140x140 post path 4102) is excluded and does not pollute walls."""
    bars = [
        _strip(1, (100.0, 100.0, 300.0, 110.0)),
        _strip(2, (100.0, 290.0, 300.0, 300.0)),
        _strip(3, (100.0, 100.0, 110.0, 300.0)),
        _strip(4, (290.0, 100.0, 300.0, 300.0)),
        # Isolated 4x4 pt timber post located 100 pt away in the porch/alfresco
        _strip(5, (400.0, 400.0, 404.0, 404.0)),
    ]
    res = build_source_spatial_subdivision(
        [_drawing() for _ in bars],
        bars=bars,
        page_rect=(0.0, 0.0, 1000.0, 1000.0),
    )
    assert res.primary_building_body_count == 4
    assert res.interior_room_count == 1
    assert res.disconnected_decoy_count == 0
    assert res.status == EvidenceResolutionStatus.CANDIDATE
    # Path 5 (the timber post) must NOT appear in any building room or boundary face
    for r in res.regions:
        assert 5 not in r.bounding_native_path_ids
    for f in res.boundary_faces:
        assert 5 not in f.native_path_ids
