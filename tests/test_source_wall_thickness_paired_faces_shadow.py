"""Comprehensive unit and regression tests for pb_source_wall_thickness_paired_faces_shadow (Item 6)."""
from __future__ import annotations

import math
import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_thickness_paired_faces_shadow import (
    DEGENERATE_SEGMENT_GEOMETRY,
    NEGATIVE_DRAFTING_MOTIF_REJECTED,
    PAIRED_FACES_GAP_OUT_OF_RANGE,
    PAIRED_FACES_NON_PARALLEL,
    PAIRED_FACES_OVERLAP_INSUFFICIENT,
    PAIRED_WALL_FACES_RESOLVED,
    SOURCE_WALL_THICKNESS_SCHEMA_VERSION,
    WALL_THICKNESS_CONFLICT,
    WALL_THICKNESS_RECORD_UNAVAILABLE,
    WALL_THICKNESS_ZERO_REJECTED,
    SourcePairedFaceGeometryRecord,
    SourcePairedWallFacesSelector,
    SourceWallThicknessPairedFacesAuthority,
    SourceWallThicknessPairedFacesProducer,
    SourceWallThicknessPairedFacesResult,
)

DOC = "doc-thick-001"
REV = "rev-001"
SHA = "a" * 64
SNAP = "snap-001"
PAGE = "1"
SCOPE = f"wall-source:page-{PAGE}"
WALL_1 = "wall-phys-001"


def _make_selector(wall_id: str = WALL_1) -> SourcePairedWallFacesSelector:
    return SourcePairedWallFacesSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        wall_candidate_id=wall_id,
    )


def test_positive_scaled_horizontal_wall_pairing() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # 100 pt long horizontal segments separated by 10 pt gap
    seg_a = {"id": "seg-a1", "p1": (100.0, 200.0), "p2": (200.0, 200.0)}
    seg_b = {"id": "seg-b1", "p1": (100.0, 210.0), "p2": (200.0, 210.0)}

    # Scale: 100 pt per meter -> 10 pt gap = 0.10 m (100 mm)
    scale = 100.0

    res = producer.evaluate_and_publish(
        selector, seg_a, seg_b, scale_px_per_m=scale
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert PAIRED_WALL_FACES_RESOLVED in res.reason_codes
    assert res.record is not None

    rec = res.record
    assert rec.wall_candidate_id == WALL_1
    assert rec.face_a_primitive_id == "seg-a1"
    assert rec.face_b_primitive_id == "seg-b1"
    assert rec.gap_pt == 10.0
    assert rec.thickness_m == 0.10
    assert rec.thickness_mm == 100.0
    assert rec.thickness_authority == "PDF_SCALED"
    assert rec.overlap_pt == 100.0
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    # Check centerline: medial line at y = 205.0
    assert rec.centerline_pts == ((100.0, 205.0), (200.0, 205.0))

    # Test WKB geometry deserialization
    center_geom = wkb.loads(bytes.fromhex(rec.centerline_wkb_hex))
    assert center_geom.geom_type == "LineString"
    assert center_geom.length == pytest.approx(100.0)

    poly_geom = wkb.loads(bytes.fromhex(rec.polygon_wkb_hex))
    assert poly_geom.geom_type == "Polygon"
    assert poly_geom.area == pytest.approx(1000.0)  # 100 * 10


def test_positive_figured_thickness_vertical_wall() -> None:
    selector = _make_selector("wall-vert-002")
    producer = SourceWallThicknessPairedFacesProducer.create()

    # 150 pt long vertical segments separated by 9 pt gap
    seg_a = {"id": "seg-va", "p1": (300.0, 100.0), "p2": (300.0, 250.0)}
    seg_b = {"id": "seg-vb", "p1": (309.0, 100.0), "p2": (309.0, 250.0)}

    # Scale: 100 pt/m -> calibrated = 0.09 m (90 mm). Figured = 0.09 m (90 mm stud).
    scale = 100.0
    figured = 0.09

    res = producer.evaluate_and_publish(
        selector, seg_a, seg_b, scale_px_per_m=scale, figured_thickness_m=figured
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    rec = res.record
    assert rec is not None
    assert rec.thickness_m == 0.09
    assert rec.thickness_mm == 90.0
    assert rec.thickness_authority == "DOCUMENTED_DIMENSION"


def test_positive_angled_wall_pairing() -> None:
    selector = _make_selector("wall-diag-003")
    producer = SourceWallThicknessPairedFacesProducer.create()

    # 45 degree angle: (0, 0) to (100, 100)
    # normal is (-1/sqrt(2), 1/sqrt(2)). Gap = 10 pt
    d = 10.0 / math.sqrt(2)
    seg_a = {"id": "seg-d1", "p1": (0.0, 0.0), "p2": (100.0, 100.0)}
    seg_b = {"id": "seg-d2", "p1": (-d, d), "p2": (100.0 - d, 100.0 + d)}

    res = producer.evaluate_and_publish(selector, seg_a, seg_b)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.record is not None
    assert res.record.gap_pt == pytest.approx(10.0, abs=0.01)


def test_reversing_point_order_preserves_left_right_face_identities() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Forward direction
    seg_a = {"id": "seg-a", "p1": (50.0, 100.0), "p2": (150.0, 100.0)}
    seg_b = {"id": "seg-b", "p1": (50.0, 110.0), "p2": (150.0, 110.0)}
    res1 = producer.evaluate_and_publish(selector, seg_a, seg_b)

    # Reversed direction on both strokes
    seg_a_rev = {"id": "seg-a", "p1": (150.0, 100.0), "p2": (50.0, 100.0)}
    seg_b_rev = {"id": "seg-b", "p1": (150.0, 110.0), "p2": (50.0, 110.0)}
    res2 = producer.evaluate_and_publish(selector, seg_a_rev, seg_b_rev)

    assert res1.record is not None
    assert res2.record is not None

    # Canonical centerline and faces must match exactly
    assert res1.record.centerline_pts == res2.record.centerline_pts
    assert res1.record.face_left_pts == res2.record.face_left_pts
    assert res1.record.face_right_pts == res2.record.face_right_pts
    assert res1.record.centerline_wkb_hex == res2.record.centerline_wkb_hex


def test_non_parallel_faces_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Stroke A is horizontal, Stroke B is skewed by 5 degrees
    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 10.0), "p2": (100.0, 20.0)}

    res = producer.evaluate_and_publish(selector, seg_a, seg_b)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert PAIRED_FACES_NON_PARALLEL in res.reason_codes
    assert res.record is None


def test_insufficient_overlap_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Stroke A from 0 to 100, Stroke B from 95 to 195 (overlap is only 5 pt < 12 pt)
    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (95.0, 10.0), "p2": (195.0, 10.0)}

    res = producer.evaluate_and_publish(selector, seg_a, seg_b)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert PAIRED_FACES_OVERLAP_INSUFFICIENT in res.reason_codes
    assert res.record is None


def test_gap_out_of_range_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Gap = 0.2 pt (below uncalibrated minimum 0.8 pt)
    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 0.2), "p2": (100.0, 0.2)}

    res = producer.evaluate_and_publish(selector, seg_a, seg_b)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert PAIRED_FACES_GAP_OUT_OF_RANGE in res.reason_codes

    # Gap = 50 pt (above uncalibrated maximum 18.0 pt)
    seg_c = {"id": "seg-c", "p1": (0.0, 50.0), "p2": (100.0, 50.0)}
    res2 = producer.evaluate_and_publish(selector, seg_a, seg_c)
    assert res2.status == EvidenceResolutionStatus.ABSTAINED
    assert PAIRED_FACES_GAP_OUT_OF_RANGE in res2.reason_codes


def test_negative_drafting_motif_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    seg_a = {"id": "seg-hatch-1", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-wall-1", "p1": (0.0, 10.0), "p2": (100.0, 10.0)}

    neg_motifs = {"seg-hatch-1", "tick-001"}

    res = producer.evaluate_and_publish(
        selector, seg_a, seg_b, negative_motif_ids=neg_motifs
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NEGATIVE_DRAFTING_MOTIF_REJECTED in res.reason_codes
    assert res.record is None


def test_figured_thickness_conflict_with_scaled_gap() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Calibrated thickness is 0.10 m (100 pt / 1000 pt/m). Figured is 0.23 m (230 mm).
    # Deviation is (0.23 - 0.10) / 0.23 = 56% > 15% tolerance.
    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 10.0), "p2": (100.0, 10.0)}

    scale = 100.0  # 10 pt gap = 0.10 m
    figured = 0.23  # 230 mm cavity brick

    res = producer.evaluate_and_publish(
        selector, seg_a, seg_b, scale_px_per_m=scale, figured_thickness_m=figured
    )

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_THICKNESS_CONFLICT in res.reason_codes
    assert res.record is None


def test_zero_or_negative_thickness_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 10.0), "p2": (100.0, 10.0)}

    res = producer.evaluate_and_publish(
        selector, seg_a, seg_b, figured_thickness_m=-0.10
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_ZERO_REJECTED in res.reason_codes


def test_degenerate_segment_geometry_rejected() -> None:
    selector = _make_selector()
    producer = SourceWallThicknessPairedFacesProducer.create()

    # Zero length segment
    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (0.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 10.0), "p2": (100.0, 10.0)}

    res = producer.evaluate_and_publish(selector, seg_a, seg_b)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert DEGENERATE_SEGMENT_GEOMETRY in res.reason_codes


def test_authority_lookup_and_unknown_selector() -> None:
    selector = _make_selector("wall-known")
    producer = SourceWallThicknessPairedFacesProducer.create()

    seg_a = {"id": "seg-a", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    seg_b = {"id": "seg-b", "p1": (0.0, 10.0), "p2": (100.0, 10.0)}
    producer.evaluate_and_publish(selector, seg_a, seg_b)

    auth = producer.authority()
    assert type(auth) is SourceWallThicknessPairedFacesAuthority

    # Known lookup
    res_known = auth.resolve(selector)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert res_known.record is not None

    # Unknown selector
    unknown_sel = _make_selector("wall-unknown")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_RECORD_UNAVAILABLE in res_unknown.reason_codes


def test_sealed_record_and_authority_forbids_direct_construction() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SourcePairedFaceGeometryRecord(
            record_id="r1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            wall_candidate_id=WALL_1,
            face_a_primitive_id="a",
            face_b_primitive_id="b",
            gap_pt=10.0,
            thickness_m=0.1,
            thickness_mm=100.0,
            thickness_authority="PDF_SCALED",
            overlap_pt=100.0,
            centerline_pts=((0.0, 5.0), (100.0, 5.0)),
            face_left_pts=((0.0, 10.0), (100.0, 10.0)),
            face_right_pts=((0.0, 0.0), (100.0, 0.0)),
            centerline_wkb_hex="01",
            face_left_wkb_hex="01",
            face_right_wkb_hex="01",
            polygon_wkb_hex="01",
            corroborating_evidence_ids=("a", "b"),
        )

    with pytest.raises(TypeError, match="producer-owned"):
        SourceWallThicknessPairedFacesAuthority({})

    with pytest.raises(TypeError, match="create()"):
        SourceWallThicknessPairedFacesProducer()
