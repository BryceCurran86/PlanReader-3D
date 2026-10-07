from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution, PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
    PhysicalOpeningExistenceRecord,
)


def _opening(
    bbox: tuple[float, float, float, float] | None,
    *,
    pattern: str = RASTER_FRAMED_WALL_BAND_INTERRUPTION,
) -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id="physical-opening:raster-contract",
        source_observation_ids=("raster-source-1",),
        source_lineage_root_ids=("raster-root-1",),
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        viewport_id=None,
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern=pattern,
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=("structural_opening_existence_resolved",),
        producer_method="contract",
        producer_version="1",
        producer_generation=1,
        aperture_bbox_pt=bbox,
    )


class _NoVisibleAuthority:
    """Proves the raster bridge cannot depend on ordinary visible observations."""

    @staticmethod
    def source_visibility_authority():
        return None


def test_horizontal_raster_aperture_reconstructs_host_geometry_from_sealed_bbox() -> None:
    geometry = host._opening_geometry(
        _NoVisibleAuthority(),
        _opening((120.0, 80.0, 160.0, 100.0)),
    )
    assert geometry is not None
    assert geometry.origin == pytest.approx((120.0, 90.0))
    assert geometry.axis == pytest.approx((1.0, 0.0))
    assert geometry.normal == pytest.approx((0.0, 1.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(20.0)


def test_raster_swing_aperture_reuses_same_sealed_wall_band_geometry() -> None:
    geometry = host._opening_geometry(
        _NoVisibleAuthority(),
        _opening(
            (120.0, 80.0, 160.0, 100.0),
            pattern=RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
        ),
    )
    assert geometry is not None
    assert geometry.origin == pytest.approx((120.0, 90.0))
    assert geometry.axis == pytest.approx((1.0, 0.0))
    assert geometry.normal == pytest.approx((0.0, 1.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(20.0)


def test_vertical_raster_aperture_reconstructs_host_geometry_from_sealed_bbox() -> None:
    geometry = host._opening_geometry(
        _NoVisibleAuthority(),
        _opening((80.0, 120.0, 100.0, 160.0)),
    )
    assert geometry is not None
    assert geometry.origin == pytest.approx((90.0, 120.0))
    assert geometry.axis == pytest.approx((0.0, 1.0))
    assert geometry.normal == pytest.approx((-1.0, 0.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(20.0)


@pytest.mark.parametrize(
    "bbox",
    [
        None,
        (0.0, 0.0, 20.0, 20.0),
        (10.0, 10.0, 10.0, 30.0),
        (10.0, 10.0, 30.0, 10.0),
        (float("nan"), 0.0, 40.0, 20.0),
    ],
)
def test_raster_aperture_geometry_abstains_when_bbox_cannot_prove_axis(
    bbox: tuple[float, float, float, float] | None,
) -> None:
    assert host._opening_geometry(_NoVisibleAuthority(), _opening(bbox)) is None


def test_non_raster_pattern_cannot_reuse_raster_bbox_shortcut() -> None:
    opening = _opening(
        (120.0, 80.0, 160.0, 100.0),
        pattern="jamb_bounded_two_face_interruption",
    )
    assert host._opening_geometry(_NoVisibleAuthority(), opening) is None


def _wall_record(
    wall_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> PhysicalWallCandidateRecord:
    wall = WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=(start, end),
        face_a_segment_ids=(f"edge:{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"node:{wall_id}:a", f"node:{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.5,
        reason_codes=(),
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"candidate-identity:{wall_id}",
        path_fingerprint=(start, end),
        source_primitive_ids=(f"source:{wall_id}",),
        edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _equivalence(
    records: tuple[PhysicalWallCandidateRecord, ...],
) -> PhysicalWallEquivalenceResolution:
    ids = tuple(record.wall_candidate_id for record in records)
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=ids,
        abstained_wall_ids=(),
        equivalence_groups=(),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


def _band(
    *,
    center_y: float,
) -> tuple[PhysicalWallCandidateRecord, ...]:
    return (
        _wall_record(
            f"left-top:{center_y}",
            (20.0, center_y - 10.0),
            (120.0, center_y - 10.0),
        ),
        _wall_record(
            f"right-top:{center_y}",
            (160.0, center_y - 10.0),
            (280.0, center_y - 10.0),
        ),
        _wall_record(
            f"left-bottom:{center_y}",
            (20.0, center_y + 10.0),
            (120.0, center_y + 10.0),
        ),
        _wall_record(
            f"right-bottom:{center_y}",
            (160.0, center_y + 10.0),
            (280.0, center_y + 10.0),
        ),
    )


def test_raster_aperture_uses_existing_unique_host_band_resolution() -> None:
    geometry = host._opening_geometry(
        _NoVisibleAuthority(),
        _opening((120.0, 80.0, 160.0, 100.0)),
    )
    assert geometry is not None
    records = _band(center_y=90.0)
    resolution = host._resolve_host_bands(
        records,
        geometry,
        _equivalence(records),
    )
    assert resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert len(resolution.bands) == 1
    assert resolution.bands[0].center_offset == pytest.approx(0.0)


def test_raster_aperture_does_not_delete_off_center_host_competitor() -> None:
    geometry = host._opening_geometry(
        _NoVisibleAuthority(),
        _opening((120.0, 80.0, 160.0, 100.0)),
    )
    assert geometry is not None
    records = _band(center_y=90.0) + _band(center_y=120.0)
    resolution = host._resolve_host_bands(
        records,
        geometry,
        _equivalence(records),
    )
    assert resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert len(resolution.bands) >= 2
    centers = tuple(band.center_offset for band in resolution.bands)
    assert any(abs(value) <= 1e-9 for value in centers)
    assert any(abs(value - 30.0) <= 1e-9 for value in centers)
