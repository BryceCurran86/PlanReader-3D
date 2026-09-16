"""Focused regressions from the independent #381 multi-angle review.

These tests are production-successor coverage only. Frozen PR #372 remains
byte-for-byte unchanged.
"""
from __future__ import annotations

import fitz
import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateRecord,
)
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution, PhysicalWallIdentity
from pb_source_observation_authority import SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


OPENING = host._OpeningGeometry(
    origin=(0.0, 0.0),
    axis=(1.0, 0.0),
    normal=(0.0, 1.0),
    length=40.0,
    thickness=10.0,
)


def _record(
    wall_id: str,
    points: tuple[tuple[float, float], ...],
    *,
    reason_codes: tuple[str, ...] = (),
) -> PhysicalWallCandidateRecord:
    wall = WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=points,
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
        reason_codes=reason_codes,
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"candidate-identity:{wall_id}",
        path_fingerprint=(points[0], points[-1]),
        source_primitive_ids=(f"source:{wall_id}",),
        edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _equivalence(records: tuple[PhysicalWallCandidateRecord, ...]) -> PhysicalWallEquivalenceResolution:
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


def _band_records(*, center_offset: float) -> tuple[PhysicalWallCandidateRecord, ...]:
    top = center_offset - OPENING.thickness / 2.0
    bottom = center_offset + OPENING.thickness / 2.0
    return (
        _record(f"left-top:{center_offset}", ((-100.0, top), (0.0, top))),
        _record(f"right-top:{center_offset}", ((40.0, top), (140.0, top))),
        _record(f"left-bottom:{center_offset}", ((-100.0, bottom), (0.0, bottom))),
        _record(f"right-bottom:{center_offset}", ((40.0, bottom), (140.0, bottom))),
    )


def _real_wall_authority():
    doc = fitz.open()
    try:
        page = doc.new_page(width=200.0, height=160.0)
        shape = page.new_shape()
        for start, end in (
            ((20.0, 60.0), (180.0, 60.0)),
            ((20.0, 80.0), (180.0, 80.0)),
            ((20.0, 60.0), (20.0, 80.0)),
            ((180.0, 60.0), (180.0, 80.0)),
        ):
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        payload = bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="host-review-wall-authority",
        producer_version="1",
    )
    source.ingest_native_pdf_bytes(
        document_id="host-review-wall-authority",
        source_bytes=payload,
        source_locator="memory://host-review-wall-authority.pdf",
    )
    return PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()


def test_host_factory_rejects_raw_mode_physical_opening_authority() -> None:
    universe = host.OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        _real_wall_authority()
    ).authority()
    raw_source = SourceObservationProducer(
        producer_method="host-review-raw-mode",
        producer_version="1",
    ).authority()
    raw_opening = PhysicalOpeningAuthority(raw_source)

    assert raw_opening.source_visibility_authority() is None
    with pytest.raises(TypeError, match="SourceVisibilityAuthority"):
        host.OpeningHostBindingProducer.from_authorities(
            physical_opening_authority=raw_opening,
            host_wall_universe_authority=universe,
        )


def test_multi_segment_wall_uses_upstream_drafting_tolerance_not_exact_pdf_equality() -> None:
    record = _record(
        "slightly-snapped-wall",
        ((-100.0, -5.0), (-50.0, -4.5), (0.0, -5.0)),
    )
    data = host._candidate_axis_data(record, OPENING)
    assert data is not None
    along_min, along_max, offset = data
    assert along_min < 0.0
    assert abs(along_max) <= 1e-9
    assert -5.0 <= offset <= -4.5


def test_non_simple_fallback_point_order_is_never_used_for_host_geometry() -> None:
    record = _record(
        "fallback-wall",
        ((-100.0, -5.0), (-20.0, -5.0), (-60.0, -5.0), (0.0, -5.0)),
        reason_codes=("non_simple_chain_topology_fallback_ordering",),
    )
    assert host._candidate_axis_data(record, OPENING) is None


def test_offset_clustering_does_not_chain_across_more_than_role_tolerance() -> None:
    a = _record("cluster-a", ((-10.0, 0.0), (0.0, 0.0)))
    b = _record("cluster-b", ((-10.0, 0.4), (0.0, 0.4)))
    c = _record("cluster-c", ((-10.0, 0.8), (0.0, 0.8)))
    clusters = host._clusters_by_offset(((0.0, a), (0.4, b), (0.8, c)), 0.5)
    assert tuple(len(cluster) for cluster in clusters) == (2, 1)


def test_unique_off_center_parallel_band_cannot_corrobate_host() -> None:
    records = _band_records(center_offset=20.0)
    result = host._resolve_host_bands(records, OPENING, _equivalence(records))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.bands == ()
    assert host.HOST_BAND_CENTER_MISMATCH in result.reason_codes


def test_off_center_band_remains_visible_as_competitor_when_centered_host_exists() -> None:
    centered = _band_records(center_offset=0.0)
    competitor = _band_records(center_offset=20.0)
    records = centered + competitor
    result = host._resolve_host_bands(records, OPENING, _equivalence(records))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    # The complete geometry can also form a mixed face pairing whose thickness
    # matches the opening. Without independent physical proof that this mixed
    # pairing is impossible, fail-closed host authority must retain it rather
    # than delete it by center/nearest/first preference. All we require here is
    # that the genuine centered and off-centre competitors both remain visible,
    # which guarantees publish() cannot manufacture a unique host.
    assert len(result.bands) >= 2
    centers = tuple(band.center_offset for band in result.bands)
    assert any(abs(center) <= 1e-9 for center in centers)
    assert any(abs(center - 20.0) <= 1e-9 for center in centers)
