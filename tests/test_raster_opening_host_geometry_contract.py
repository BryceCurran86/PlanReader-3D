from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
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
