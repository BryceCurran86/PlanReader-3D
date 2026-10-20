"""Comprehensive unit and regression tests for pb_source_structural_identity_fragment_provenance_shadow (Items 9 & 25)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_structural_identity_fragment_provenance_shadow import (
    DEGENERATE_FRAGMENT_GEOMETRY,
    FRAGMENT_LINEAGE_UNMAPPED,
    FRAGMENT_NON_COLLINEAR,
    SOURCE_STRUCTURAL_IDENTITY_SCHEMA_VERSION,
    STRUCTURAL_IDENTITY_RECORD_UNAVAILABLE,
    STRUCTURAL_RUN_RESOLVED,
    STRUCTURAL_RUN_UNRESOLVED,
    SourceStructuralIdentityAuthority,
    SourceStructuralIdentityProducer,
    SourceStructuralIdentityResult,
    SourceStructuralIdentitySelector,
    SourceStructuralRunRecord,
)

DOC = "doc-lot16"
REV = "rev-001"
SHA = "d" * 64
SNAP = "snap-001"
PAGE = "1"
SCOPE = f"wall-source:page-{PAGE}"
PARENT_1 = "d10i0"


def _make_selector(parent_id: str = PARENT_1) -> SourceStructuralIdentitySelector:
    return SourceStructuralIdentitySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        parent_primitive_id=parent_id,
    )


def test_positive_complete_structural_run() -> None:
    selector = _make_selector()
    producer = SourceStructuralIdentityProducer.create()

    # Parent is a 300 pt horizontal line from (100, 200) to (400, 200)
    parent = {"id": PARENT_1, "p1": (100.0, 200.0), "p2": (400.0, 200.0)}

    # 3 contiguous child fragments from split operations
    frag1 = {"id": "e1", "p1": (100.0, 200.0), "p2": (200.0, 200.0)}
    frag2 = {"id": "e2", "p1": (200.0, 200.0), "p2": (300.0, 200.0)}
    frag3 = {"id": "e3", "p1": (300.0, 200.0), "p2": (400.0, 200.0)}

    res = producer.evaluate_and_publish(
        selector,
        parent_primitive=parent,
        child_fragments=[frag1, frag2, frag3],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert STRUCTURAL_RUN_RESOLVED in res.reason_codes
    assert res.record is not None

    rec = res.record
    assert rec.parent_primitive_id == PARENT_1
    assert rec.parent_length_pt == 300.0
    assert rec.coverage_ratio == 1.0
    assert rec.is_complete_extent is True
    assert rec.covered_intervals == ((0.0, 300.0),)
    assert rec.gap_intervals == ()
    assert rec.child_edge_ids == ("e1", "e2", "e3")
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    # WKB validation
    geom = wkb.loads(bytes.fromhex(rec.reconstructed_run_wkb_hex))
    assert geom.geom_type == "LineString"
    assert geom.length == pytest.approx(300.0)


def test_positive_partial_run_with_opening_gap() -> None:
    selector = _make_selector()
    producer = SourceStructuralIdentityProducer.create()

    # Parent 300 pt line: 100..400
    parent = {"id": PARENT_1, "p1": (100.0, 200.0), "p2": (400.0, 200.0)}

    # Two fragments with an 80 pt door opening void between 180 and 260
    frag1 = {"id": "e1", "p1": (100.0, 200.0), "p2": (180.0, 200.0)}  # len 80
    frag2 = {"id": "e2", "p1": (260.0, 200.0), "p2": (400.0, 200.0)}  # len 140

    res = producer.evaluate_and_publish(
        selector,
        parent_primitive=parent,
        child_fragments=[frag1, frag2],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.record is not None

    rec = res.record
    assert rec.is_complete_extent is False
    assert rec.coverage_ratio == pytest.approx((80.0 + 140.0) / 300.0, abs=1e-4)
    assert rec.covered_intervals == ((0.0, 80.0), (160.0, 300.0))
    assert rec.gap_intervals == ((80.0, 160.0),)

    # WKB multi-line validation
    geom = wkb.loads(bytes.fromhex(rec.reconstructed_run_wkb_hex))
    assert geom.geom_type == "MultiLineString"
    assert geom.length == pytest.approx(220.0)


def test_non_collinear_fragment_rejected() -> None:
    selector = _make_selector()
    producer = SourceStructuralIdentityProducer.create()

    parent = {"id": PARENT_1, "p1": (100.0, 200.0), "p2": (400.0, 200.0)}
    # Fragment offset perpendicular to parent line by 5 pt (> 0.5 pt tol)
    frag_offset = {"id": "e_bad", "p1": (100.0, 205.0), "p2": (200.0, 205.0)}

    res = producer.evaluate_and_publish(
        selector,
        parent_primitive=parent,
        child_fragments=[frag_offset],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert FRAGMENT_NON_COLLINEAR in res.reason_codes
    assert res.record is None


def test_degenerate_fragment_geometry_rejected() -> None:
    selector = _make_selector()
    producer = SourceStructuralIdentityProducer.create()

    # Parent with 0 length
    parent = {"id": PARENT_1, "p1": (100.0, 200.0), "p2": (100.0, 200.0)}
    frag = {"id": "e1", "p1": (100.0, 200.0), "p2": (200.0, 200.0)}

    res = producer.evaluate_and_publish(
        selector,
        parent_primitive=parent,
        child_fragments=[frag],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert DEGENERATE_FRAGMENT_GEOMETRY in res.reason_codes


def test_unmapped_fragment_lineage_rejected() -> None:
    selector = _make_selector()
    producer = SourceStructuralIdentityProducer.create()

    parent = {"id": PARENT_1, "p1": (100.0, 200.0), "p2": (400.0, 200.0)}
    # Missing fragment id
    frag = {"p1": (100.0, 200.0), "p2": (200.0, 200.0)}

    res = producer.evaluate_and_publish(
        selector,
        parent_primitive=parent,
        child_fragments=[frag],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert FRAGMENT_LINEAGE_UNMAPPED in res.reason_codes


def test_authority_lookup_and_unknown_selector() -> None:
    selector = _make_selector("parent-known")
    producer = SourceStructuralIdentityProducer.create()

    parent = {"id": "parent-known", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    frag = {"id": "e1", "p1": (0.0, 0.0), "p2": (100.0, 0.0)}
    producer.evaluate_and_publish(selector, parent_primitive=parent, child_fragments=[frag])

    auth = producer.authority()
    assert type(auth) is SourceStructuralIdentityAuthority

    res_known = auth.resolve(selector)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert res_known.record is not None

    unknown_sel = _make_selector("parent-unknown")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_IDENTITY_RECORD_UNAVAILABLE in res_unknown.reason_codes


def test_sealed_record_and_authority_forbids_direct_construction() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SourceStructuralRunRecord(
            record_id="r1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            parent_primitive_id=PARENT_1,
            structural_identity_id="s1",
            parent_extent_pts=((0.0, 0.0), (100.0, 0.0)),
            parent_length_pt=100.0,
            child_edge_ids=("e1",),
            coverage_ratio=1.0,
            is_complete_extent=True,
            covered_intervals=((0.0, 100.0),),
            gap_intervals=(),
            reconstructed_run_wkb_hex="01",
            corroborating_evidence_ids=(),
        )

    with pytest.raises(TypeError, match="producer-owned"):
        SourceStructuralIdentityAuthority({})

    with pytest.raises(TypeError, match="create()"):
        SourceStructuralIdentityProducer()
