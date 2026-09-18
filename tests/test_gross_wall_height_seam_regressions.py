"""Adversarial regression test suite for wall-height authority minting seam fixes in Item 17.

Verifies:
1. Duck-typed resolvers (objects with .resolve()) are rejected by GrossWallGeometryProducer.
2. Plain Mappings are rejected by GrossWallGeometryProducer.
3. Attempting to use WallHeightAuthority.from_quantities (former public factory) raises AttributeError.
4. Attempting to construct WallHeightAuthority directly without _HEIGHT_AUTHORITY_SEAL raises TypeError.
5. Wrong-wall / cross-lineage wrapped quantities fail closed when resolved.
6. Legitimate WallHeightProducer positive path emits valid WallHeightAuthority.
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_opening_host_frame_authority import (
    OpeningHostFrameAuthority,
    OpeningHostFrameEvidence,
    OpeningHostFrameResult,
    OpeningHostFrameSelector,
    _AUTHORITY_SEAL as FRAME_SEAL,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleEvidence,
    PhysicalScaleResult,
    PhysicalScaleSelector,
    _AUTHORITY_SEAL as SCALE_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_height_authority import (
    WALL_HEIGHT_FAMILY,
    WallHeightAuthority,
    WallHeightProducer,
    _HEIGHT_AUTHORITY_SEAL as HEIGHT_SEAL,
)
from pb_gross_wall_geometry_authority import (
    GrossWallGeometryProducer,
    GrossWallGeometrySelector,
)

SHA = "a" * 64
DOC = "doc-seam-test"
REV = "R1"
SNAP = "snap-1"
PAGE = "page-1"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-1"
WALL = "WALL-SEAM-1"
FRAME_ID = "frame-seam-1"


def _setup_deps():
    cand_sel = PhysicalWallCandidateSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=WALL, viewport_id=VP, candidate_identity_id=None,
        path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    cand_rec = PhysicalWallCandidateRecord(
        wall_candidate_id=WALL, wall_candidate=None, physical_identity=ident,
    )
    cand_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    cand_auth = PhysicalWallCandidateAuthority(
        {cand_key: PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=(cand_rec,), source_observation_ids=(), document_id=DOC,
            revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            decision_scope_id=SCOPE, reason_codes=(),
        )}, _seal=CANDIDATE_SEAL,
    )

    frame_sel = OpeningHostFrameSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
        opening_identity_id="op-1",
    )
    frame_ev = OpeningHostFrameEvidence(
        selector=frame_sel, record_id="rec-frame", opening_identity_id="op-1",
        host_binding_record_id="host-1", host_wall_id=WALL, whole_wall_frame_id=FRAME_ID,
        whole_wall_candidate_ids=(WALL,), source_observation_ids=(),
        origin_pt=(0.0, 0.0), axis_unit=(1.0, 0.0), normal_unit=(0.0, 1.0),
        u0_pt=0.0, u1_pt=100.0, wall_thickness_pt=10.0,
    )
    frame_auth = OpeningHostFrameAuthority(
        {frame_sel.key: OpeningHostFrameResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=frame_ev,
        )}, _seal=FRAME_SEAL,
    )

    scale_sel = PhysicalScaleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE,
    )
    scale_ev = PhysicalScaleEvidence(
        selector=scale_sel, record_id="rec-scale", source_kind="graphic_scale",
        source_span_pt=100.0, physical_span_mm=1000.0, points_per_mm=0.1,
        mm_per_point=10.0, source_segment_observation_ids=(),
        source_text_observation_ids=(), viewport_id=None,
    )
    scale_auth = PhysicalScaleAuthority(
        {scale_sel.key: PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=scale_ev,
        )}, _seal=SCALE_SEAL,
    )
    return cand_auth, frame_auth, scale_auth


def test_duck_resolver_rejected() -> None:
    cand_auth, frame_auth, scale_auth = _setup_deps()

    class FakeDuckResolver:
        def resolve(self, selector):
            return None

    fake_duck = FakeDuckResolver()

    with pytest.raises(TypeError, match="wall_height_authority must be a producer-owned WallHeightAuthority"):
        GrossWallGeometryProducer.from_authorities(
            physical_wall_candidate_authority=cand_auth,
            host_frame_authority=frame_auth,
            physical_scale_authority=scale_auth,
            wall_height_authority=fake_duck,  # type: ignore[arg-type]
        )


def test_plain_mapping_rejected() -> None:
    cand_auth, frame_auth, scale_auth = _setup_deps()
    plain_dict = {WALL: "fake"}

    with pytest.raises(TypeError, match="wall_height_authority must be a producer-owned WallHeightAuthority"):
        GrossWallGeometryProducer.from_authorities(
            physical_wall_candidate_authority=cand_auth,
            host_frame_authority=frame_auth,
            physical_scale_authority=scale_auth,
            wall_height_authority=plain_dict,  # type: ignore[arg-type]
        )


def test_from_quantities_factory_removed() -> None:
    assert not hasattr(WallHeightAuthority, "from_quantities")


def test_direct_constructor_without_seal_raises() -> None:
    with pytest.raises(TypeError, match="WallHeightAuthority is producer-owned"):
        WallHeightAuthority({})


def test_legitimate_wall_height_producer_positive_path() -> None:
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_wall_height_authority import WallHeightSelector

    src_vis_prod = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    producer = WallHeightProducer.from_authorities(src_vis_prod)
    h_sel = WallHeightSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
        physical_wall_id=WALL,
    )
    # Manually populate published quantity in producer for positive path testing
    qty_evidence = QuantityEvidence(
        quantity_id="qty-height-1",
        family=WALL_HEIGHT_FAMILY,
        semantic_key=f"wall_height:{WALL}",
        value=3.0,
        unit="m",
        input_entity_ids=(WALL,),
        formula="authoritative_explicit_wall_height",
        formula_version="1.4.0",
        evidence_ids=("ev-1", "registration-wall-1"),
        authority="documented_dimension",
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        metadata={
            "source_sha256": SHA,
            "revision_id": REV,
            "evidence_snapshot_id": SNAP,
            "source_page_id": PAGE,
            "height_evidence_page_id": "page-2",
            "target_entity_id": WALL,
            "target_physical_element_id": "elevation-wall-1",
            "cross_sheet_registration_record_id": "registration-wall-1",
            "identity_binding_kind": "cross_sheet_registration",
        },
    )
    producer._quantities[h_sel.key] = qty_evidence
    producer._quantities[WALL] = qty_evidence

    height_auth = producer.authority()
    assert type(height_auth) is WallHeightAuthority

    cand_auth, frame_auth, scale_auth = _setup_deps()
    gross_producer = GrossWallGeometryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        host_frame_authority=frame_auth,
        physical_scale_authority=scale_auth,
        wall_height_authority=height_auth,
    )
    g_sel = GrossWallGeometrySelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
        physical_wall_id=WALL,
    )
    result = gross_producer.publish(g_sel)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.height_m == 3.0


def test_firm_height_without_exact_cross_sheet_binding_is_rejected() -> None:
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_wall_height_authority import WallHeightSelector

    source = SourceVisibilityProducer(
        producer_method="test", producer_version="1.0"
    )
    height_producer = WallHeightProducer.from_authorities(source)
    h_sel = WallHeightSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=WALL,
    )
    forged = QuantityEvidence(
        quantity_id="qty-forged-height",
        family=WALL_HEIGHT_FAMILY,
        semantic_key=f"wall_height:{WALL}",
        value=3.0,
        unit="m",
        input_entity_ids=(WALL,),
        formula="authoritative_explicit_wall_height",
        formula_version="1.4.0",
        evidence_ids=("ev-forged",),
        authority="documented_dimension",
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        metadata={
            "source_sha256": SHA,
            "revision_id": REV,
            "evidence_snapshot_id": SNAP,
            "source_page_id": PAGE,
            "target_entity_id": WALL,
        },
    )
    height_producer._quantities[h_sel.key] = forged
    height_auth = height_producer.authority()

    cand_auth, frame_auth, scale_auth = _setup_deps()
    gross_producer = GrossWallGeometryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        host_frame_authority=frame_auth,
        physical_scale_authority=scale_auth,
        wall_height_authority=height_auth,
    )
    result = gross_producer.publish(
        GrossWallGeometrySelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL,
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert "wall_height_exact_identity_binding_unavailable" in result.reason_codes
