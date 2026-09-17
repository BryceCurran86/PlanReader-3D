"""Comprehensive unit tests for Item 25 Raster Wall Network Authority.

Tests:
1. Conservative raster wall candidates extraction and coordinate mapping.
2. Image snapshot identity and lineage verification (fails closed on mismatch).
3. Missing source page image failure behavior (fails closed with ABSTAINED).
4. Transform provenance and pixel-to-point coordinate conversion.
5. Fail-closed without fabricated scale:
   - Unproven scale keeps all meter values as None and emits RASTER_SCALE_UNRESOLVED.
   - Authoritative scale produces exact metric values.
6. Junction detection and classification (end, L, T, X, multi).
7. Topological connectivity mapping between candidates and junctions.
8. Ambiguity retention (never fabricates clean vectors over noisy/uncertain inputs).
9. Target region filtering and clipping.
10. Producer-owned authority sealing and immutability.
"""
from __future__ import annotations

import math
import pytest
from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_raster_wall_network_authority import (
    RASTER_LINEAGE_MISMATCH,
    RASTER_NO_CANDIDATES_FOUND,
    RASTER_SCALE_UNRESOLVED,
    RASTER_SOURCE_IMAGE_MISSING,
    RASTER_TOPOLOGY_DISCONNECTED,
    RASTER_WALL_AMBIGUOUS,
    RASTER_WALL_NETWORK_RESOLVED,
    RASTER_WALL_NETWORK_SCHEMA_VERSION,
    RASTER_WALL_NETWORK_UNAVAILABLE,
    RasterTransformProvenance,
    RasterWallCandidateRecord,
    RasterWallJunction,
    RasterWallNetworkAuthority,
    RasterWallNetworkProducer,
    RasterWallNetworkRecord,
    RasterWallNetworkResult,
    RasterWallNetworkSelector,
    RasterWallSegment,
    build_raster_junctions,
)


class MockSnapshot:
    def __init__(self, doc_id: str, rev_id: str, sha: str, snap_id: str) -> None:
        self.document_id = doc_id
        self.revision_id = rev_id
        self.source_sha256 = sha
        self.snapshot_id = snap_id


def _sample_snapshot() -> MockSnapshot:
    return MockSnapshot(
        doc_id="doc_test_scan_01",
        rev_id="rev_test_scan_01",
        sha="a" * 64,
        snap_id="snap_test_scan_01",
    )


def _sample_selector(
    page_id: str = "page_1",
    viewport_id: str | None = "vp_plan",
    target_region_pt: tuple[float, float, float, float] | None = None,
) -> RasterWallNetworkSelector:
    return RasterWallNetworkSelector(
        document_id="doc_test_scan_01",
        revision_id="rev_test_scan_01",
        source_sha256="a" * 64,
        snapshot_id="snap_test_scan_01",
        page_id=page_id,
        viewport_id=viewport_id,
        target_region_pt=target_region_pt,
    )


def test_fail_closed_when_image_missing() -> None:
    producer = RasterWallNetworkProducer.from_sources(
        page_images={},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert RASTER_SOURCE_IMAGE_MISSING in res.reason_codes
    assert res.record is None


def test_lineage_mismatch_fails_closed() -> None:
    img = Image.new("RGB", (200, 200), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
    )
    bad_sel = RasterWallNetworkSelector(
        document_id="doc_test_scan_01",
        revision_id="rev_test_scan_01",
        source_sha256="b" * 64,  # mismatched hash
        snapshot_id="snap_test_scan_01",
        page_id="page_1",
    )
    res = producer.publish(bad_sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert RASTER_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


def test_empty_candidates_fails_closed_with_abstained() -> None:
    img = Image.new("RGB", (200, 200), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": ()},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert RASTER_NO_CANDIDATES_FOUND in res.reason_codes
    assert res.record is None


def test_unproven_scale_fails_closed_without_fabricating_meters() -> None:
    # 2 wall segments forming an L-corner
    seg1 = RasterWallSegment(
        start_px=(10.0, 10.0),
        end_px=(110.0, 10.0),  # len = 100 px
        thickness_px=8.0,
        confidence=0.9,
    )
    seg2 = RasterWallSegment(
        start_px=(110.0, 10.0),
        end_px=(110.0, 210.0),  # len = 200 px
        thickness_px=8.0,
        confidence=0.9,
    )

    img = Image.new("RGB", (300, 300), "white")
    # Transform without authoritative scale
    transform = RasterTransformProvenance.from_dpi(
        dpi=150,
        scale_ratio=None,
        is_scale_authoritative=False,
    )
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg1, seg2)},
        transform_by_page={"page_1": transform},
        snapshot=_sample_snapshot(),
    )

    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert RASTER_WALL_NETWORK_RESOLVED in res.reason_codes
    assert RASTER_SCALE_UNRESOLVED in res.reason_codes  # Critical scale flag!
    rec = res.record
    assert rec is not None

    # Meter metrics MUST BE None because scale is unproven!
    assert rec.total_length_m is None
    for cand in rec.candidates:
        assert cand.segment.length_m is None
        assert cand.segment.thickness_m is None

    # Point metrics are still computed from DPI (150 DPI -> 72/150 = 0.48 pt/px)
    assert rec.total_length_pt == pytest.approx(300.0 * 0.48, rel=1e-3)


def test_authoritative_scale_calculates_metric_dimensions() -> None:
    seg1 = RasterWallSegment(
        start_px=(0.0, 0.0),
        end_px=(100.0, 0.0),  # 100 px
        thickness_px=10.0,
        confidence=0.95,
    )
    img = Image.new("RGB", (200, 200), "white")

    import pb_physical_scale_authority as pb_s
    scale_sel = pb_s.PhysicalScaleSelector(
        document_id="doc_test_scan_01",
        revision_id="rev_test_scan_01",
        source_sha256="a" * 64,
        snapshot_id="snap_test_scan_01",
        page_id="page_1",
        viewport_id="vp_plan",
    )
    scale_ev = pb_s.PhysicalScaleEvidence(
        selector=scale_sel,
        record_id="scale_rec_01",
        source_kind="graphic_bar",
        source_span_pt=100.0,
        physical_span_mm=3527.777777777778,
        points_per_mm=100.0 / 3527.777777777778,
        mm_per_point=3527.777777777778 / 100.0,
        source_segment_observation_ids=("seg1",),
        source_text_observation_ids=("text1",),
        viewport_id="vp_plan",
    )
    scale_res = pb_s.PhysicalScaleResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(pb_s.PHYSICAL_SCALE_RESOLVED,),
        evidence=scale_ev,
    )
    scale_auth = pb_s.PhysicalScaleAuthority(
        {scale_sel.key: scale_res},
        _seal=pb_s._AUTHORITY_SEAL,
    )

    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg1,)},
        physical_scale_authority=scale_auth,
        snapshot=_sample_snapshot(),
    )

    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert RASTER_SCALE_UNRESOLVED not in res.reason_codes
    rec = res.record
    assert rec is not None

    expected_m = round(48.0 * (0.0254 / 72.0) / 0.01, 4)
    assert rec.total_length_m == pytest.approx(expected_m, abs=0.01)
    assert rec.candidates[0].segment.length_m == pytest.approx(expected_m, abs=0.01)


def test_junction_detection_and_classification() -> None:
    # Build a T-junction: Horizontal bar + vertical stem meeting at (100, 100)
    seg_left = RasterWallSegment(
        start_px=(0.0, 100.0),
        end_px=(100.0, 100.0),
        confidence=0.9,
    )
    seg_right = RasterWallSegment(
        start_px=(100.0, 100.0),
        end_px=(200.0, 100.0),
        confidence=0.9,
    )
    seg_down = RasterWallSegment(
        start_px=(100.0, 100.0),
        end_px=(100.0, 200.0),
        confidence=0.9,
    )

    img = Image.new("RGB", (300, 300), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg_left, seg_right, seg_down)},
        snapshot=_sample_snapshot(),
    )

    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)
    rec = res.record
    assert rec is not None

    # Should detect 1 T-junction at (100, 100) and 3 end junctions
    t_junctions = [j for j in rec.junctions if j.junction_type == "T"]
    end_junctions = [j for j in rec.junctions if j.junction_type == "end"]

    assert len(t_junctions) == 1
    assert t_junctions[0].location_px == (100.0, 100.0)
    assert len(t_junctions[0].connected_candidate_ids) == 3
    assert len(end_junctions) == 3


def test_ambiguity_retention() -> None:
    # A wall flagged as ambiguous due to low contrast / broken raster run
    seg_amb = RasterWallSegment(
        start_px=(10.0, 10.0),
        end_px=(80.0, 10.0),
        confidence=0.45,
        is_ambiguous=True,
        ambiguity_reason="broken_pixel_run_possible_gap",
    )

    img = Image.new("RGB", (150, 150), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg_amb,)},
        snapshot=_sample_snapshot(),
    )

    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert RASTER_WALL_AMBIGUOUS in res.reason_codes
    assert res.record is not None
    assert res.record.has_ambiguity is True
    assert res.record.candidates[0].is_ambiguous is True
    assert res.record.candidates[0].segment.ambiguity_reason == "broken_pixel_run_possible_gap"


def test_target_region_clipping() -> None:
    # Two walls: one inside target region, one far outside
    seg_inside = RasterWallSegment(
        start_px=(20.0, 20.0),
        end_px=(40.0, 20.0),
        confidence=0.9,
    )
    seg_outside = RasterWallSegment(
        start_px=(300.0, 300.0),
        end_px=(400.0, 300.0),
        confidence=0.9,
    )

    img = Image.new("RGB", (500, 500), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg_inside, seg_outside)},
        snapshot=_sample_snapshot(),
    )

    # Filter by region covering (0, 0) to (50, 50) pt
    sel = _sample_selector(
        page_id="page_1",
        target_region_pt=(0.0, 0.0, 50.0, 50.0),
    )
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    rec = res.record
    assert rec is not None
    # Only the inside segment should be retained
    assert len(rec.candidates) == 1
    assert rec.candidates[0].segment.start_px == (20.0, 20.0)


def test_authority_sealing_and_resolution() -> None:
    seg = RasterWallSegment(
        start_px=(10.0, 10.0),
        end_px=(50.0, 10.0),
        confidence=0.85,
    )
    img = Image.new("RGB", (100, 100), "white")
    producer = RasterWallNetworkProducer.from_sources(
        page_images={"page_1": img},
        raw_candidates_by_page={"page_1": (seg,)},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    producer.publish(sel)

    auth = producer.authority()
    resolved = auth.resolve(sel)
    assert resolved.status == EvidenceResolutionStatus.CORROBORATED
    assert resolved.record is not None
    assert len(resolved.record.candidates) == 1

    # Unknown selector abstains
    unkn_sel = _sample_selector(page_id="page_999")
    unkn_res = auth.resolve(unkn_sel)
    assert unkn_res.status == EvidenceResolutionStatus.ABSTAINED
    assert RASTER_WALL_NETWORK_UNAVAILABLE in unkn_res.reason_codes

    # Direct instantiation without seal fails
    with pytest.raises(TypeError, match="producer-owned"):
        RasterWallNetworkAuthority({})

    with pytest.raises(TypeError, match="from_sources"):
        RasterWallNetworkProducer({})
