"""Item 25 fail-closed raster wall-network authority attacks."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleEvidence,
    PhysicalScaleResult,
    PhysicalScaleSelector,
    _AUTHORITY_SEAL as SCALE_SEAL,
)
from pb_source_observation_authority import (
    ProducerSnapshotRecord,
    PublishedSourceSnapshot,
    SourceDecodeCoverageRecord,
    SourceRevisionRecord,
)

from pb_raster_wall_network_authority import (
    RASTER_LINEAGE_MISMATCH,
    RASTER_NO_OBSERVATIONS,
    RASTER_SCALE_UNRESOLVED,
    RASTER_SOURCE_OBSERVATION_NOT_AUTHENTICATED,
    RASTER_TRANSFORM_AMBIGUOUS,
    RASTER_WALL_AMBIGUOUS,
    RASTER_WALL_NETWORK_RESOLVED,
    RasterPixelSegment,
    RasterTransformBinding,
    RasterWallNetworkProducer,
    RasterWallNetworkSelector,
    RasterWallObservationAuthority,
    RasterWallObservationProducer,
    RasterWallObservationRecord,
    RasterWallObservationResult,
    RasterWallObservationSelector,
    _OBS_AUTHORITY_SEAL,
    _SOURCE_AUTHENTICATED_RASTER_SEAL,
)

DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "1"
IMG_SHA = "b" * 64


def _snapshot(
    *,
    doc: str = DOC,
    rev: str = REV,
    sha: str = SHA,
    snap: str = SNAP,
) -> PublishedSourceSnapshot:
    revision = SourceRevisionRecord(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        source_locator="mem://test",
        partition_ids=("1",),
        producer_method="test",
        producer_version="1.0",
        producer_generation=1,
    )
    coverage = SourceDecodeCoverageRecord(
        document_id=doc,
        revision_id=rev,
        total_pages=1,
        decoded_pages=(1,),
        failed_pages=(),
        state="complete",
    )
    snapshot = ProducerSnapshotRecord(
        snapshot_id=snap,
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        observation_ids=(),
        producer_method="test",
        producer_version="1.0",
        producer_generation=1,
    )
    return PublishedSourceSnapshot(
        revision=revision, coverage=coverage, snapshot=snapshot
    )


def _scale_auth(
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    page: str = PAGE,
    snap: str = SNAP,
    sha: str = SHA,
) -> PhysicalScaleAuthority:
    sel = PhysicalScaleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
    )
    if status is EvidenceResolutionStatus.CORROBORATED:
        evidence = PhysicalScaleEvidence(
            selector=sel,
            record_id="scale-1",
            source_kind="scale_bar",
            source_span_pt=72.0,  # 1 inch paper
            physical_span_mm=1000.0,  # 1 m
            points_per_mm=72.0 / 1000.0,
            mm_per_point=1000.0 / 72.0,
            source_segment_observation_ids=("seg-1",),
            source_text_observation_ids=(),
            viewport_id=None,
        )
        result = PhysicalScaleResult(
            status=status, reason_codes=("physical_scale_resolved",), evidence=evidence
        )
    else:
        result = PhysicalScaleResult(
            status=status, reason_codes=("physical_scale_scope_unavailable",), evidence=None
        )
    return PhysicalScaleAuthority({sel.key: result}, _seal=SCALE_SEAL)


def _obs_auth(
    segments: tuple[RasterPixelSegment, ...],
    *,
    dpi: int = 150,
    page: str = PAGE,
    snap: PublishedSourceSnapshot | None = None,
) -> object:
    snap = snap or _snapshot()
    transform = RasterTransformBinding(
        dpi=dpi,
        px_to_pt_ratio=72.0 / float(dpi),
        source_image_sha256=IMG_SHA,
    )
    selector = RasterWallObservationSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page,
    )
    record = RasterWallObservationRecord(
        record_id=f"trusted-raster-{page}",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page,
        transform=transform,
        segments=segments,
    )
    auth = RasterWallObservationAuthority(
        {
            selector.key: RasterWallObservationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(RASTER_WALL_NETWORK_RESOLVED,),
                record=record,
            )
        },
        _seal=_OBS_AUTHORITY_SEAL,
    )
    object.__setattr__(
        auth,
        "_source_authentication_seal",
        _SOURCE_AUTHENTICATED_RASTER_SEAL,
    )
    return auth


def _segs() -> tuple[RasterPixelSegment, ...]:
    return (
        RasterPixelSegment(start_px=(10.0, 10.0), end_px=(110.0, 10.0), thickness_px=4.0),
        RasterPixelSegment(start_px=(110.0, 10.0), end_px=(110.0, 110.0), thickness_px=4.0),
    )


def test_caller_raw_candidates_kwargs_rejected() -> None:
    with pytest.raises(TypeError, match="not authority"):
        RasterWallNetworkProducer.from_authorities(
            observation_authority=_obs_auth(_segs()),
            physical_scale_authority=_scale_auth(),
            snapshot=_snapshot(),
            raw_candidates_by_page={"1": _segs()},
        )


def test_caller_transform_and_page_images_kwargs_rejected() -> None:
    with pytest.raises(TypeError, match="not authority"):
        RasterWallNetworkProducer.from_authorities(
            observation_authority=_obs_auth(_segs()),
            physical_scale_authority=_scale_auth(),
            snapshot=_snapshot(),
            transform_by_page={"1": object()},
            page_images={"1": object()},
        )


def test_forged_segment_path_requires_observation_authority() -> None:
    """Segments only reach the network through sealed observation publish."""
    # Empty observation authority → ABSTAIN even if caller has segments locally.
    empty = RasterWallObservationProducer.create().authority()
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=empty,
        physical_scale_authority=_scale_auth(),
        snapshot=_snapshot(),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        )
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_NO_OBSERVATIONS in res.reason_codes
    assert res.record is None


def test_forged_transform_dpi_mismatch_fails() -> None:
    prod = RasterWallObservationProducer.create()
    bad = RasterTransformBinding(
        dpi=150,
        px_to_pt_ratio=1.0,
        source_image_sha256=IMG_SHA,
    )
    res = prod.publish(
        RasterWallObservationSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        ),
        transform=bad,
        segments=_segs(),
        snapshot=_snapshot(),
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_SOURCE_OBSERVATION_NOT_AUTHENTICATED in res.reason_codes
    assert res.record is None

def test_wrong_page_observations_do_not_serve_other_page() -> None:
    obs = _obs_auth(_segs(), page="1")
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=obs,
        physical_scale_authority=_scale_auth(page="2"),
        snapshot=_snapshot(),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id="2",
        )
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_NO_OBSERVATIONS in res.reason_codes


def test_stale_snapshot_lineage_conflicts() -> None:
    obs = _obs_auth(_segs())
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=obs,
        physical_scale_authority=_scale_auth(),
        snapshot=_snapshot(snap="snap-other"),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        )
    )
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert RASTER_LINEAGE_MISMATCH in res.reason_codes


def test_scale_from_unresolved_authority_abstains() -> None:
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=_obs_auth(_segs()),
        physical_scale_authority=_scale_auth(
            status=EvidenceResolutionStatus.ABSTAINED
        ),
        snapshot=_snapshot(),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        )
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_SCALE_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_ambiguous_segment_abstains_instead_of_cleaning() -> None:
    segs = (
        RasterPixelSegment(
            start_px=(0.0, 0.0),
            end_px=(50.0, 0.0),
            is_ambiguous=True,
            ambiguity_reason="noisy_raster",
        ),
    )
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=_obs_auth(segs),
        physical_scale_authority=_scale_auth(),
        snapshot=_snapshot(),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        )
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_WALL_AMBIGUOUS in res.reason_codes


def test_non_wall_drafting_line_excluded_from_observations() -> None:
    prod = RasterWallObservationProducer.create()
    res = prod.publish(
        RasterWallObservationSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        ),
        transform=RasterTransformBinding(
            dpi=150, px_to_pt_ratio=72.0 / 150.0, source_image_sha256=IMG_SHA
        ),
        segments=(RasterPixelSegment(
            start_px=(0.0, 0.0), end_px=(40.0, 0.0), is_wall_candidate=False
        ),),
        snapshot=_snapshot(),
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_SOURCE_OBSERVATION_NOT_AUTHENTICATED in res.reason_codes

def test_duplicate_raster_observation_deduped() -> None:
    prod = RasterWallObservationProducer.create()
    res = prod.publish(
        RasterWallObservationSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        ),
        transform=RasterTransformBinding(
            dpi=150, px_to_pt_ratio=72.0 / 150.0, source_image_sha256=IMG_SHA
        ),
        segments=(
            RasterPixelSegment(start_px=(0.0, 0.0), end_px=(100.0, 0.0)),
            RasterPixelSegment(start_px=(0.0, 0.0), end_px=(100.0, 0.0)),
        ),
        snapshot=_snapshot(),
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_SOURCE_OBSERVATION_NOT_AUTHENTICATED in res.reason_codes
    assert res.record is None

def test_fake_snapshot_type_rejected() -> None:
    with pytest.raises(TypeError, match="PublishedSourceSnapshot"):
        RasterWallNetworkProducer.from_authorities(
            observation_authority=_obs_auth(_segs()),
            physical_scale_authority=_scale_auth(),
            snapshot=object(),  # type: ignore[arg-type]
        )


def test_legitimate_source_derived_positive_case() -> None:
    producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=_obs_auth(_segs()),
        physical_scale_authority=_scale_auth(),
        snapshot=_snapshot(),
    )
    res = producer.publish(
        RasterWallNetworkSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        )
    )
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert RASTER_WALL_NETWORK_RESOLVED in res.reason_codes
    assert res.record is not None
    assert res.record.total_length_m > 0.0
    assert all(c.segment.length_m is not None for c in res.record.candidates)
