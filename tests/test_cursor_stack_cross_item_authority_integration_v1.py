"""Cross-item integration test suite for Items 23, 25, 26, and 27.

Audits and enforces authority boundaries across the Cursor stack:
  Item 23 (Generic Opening Count Authority)
  Item 25 (Raster Wall Network Authority)
  Item 26 (Wall-Role Classification Authority)
  Item 27 (Wall Thickness and Authentic Face Geometry Authority)

Contracts verified:
  - Item 25 candidate geometry must NOT automatically become Item 26 wall role.
  - Item 25 candidate geometry must NOT automatically become Item 27 thickness.
  - Item 23 schedule row must NOT manufacture a physical opening identity.
  - Exact physical_wall_id survives all handoffs; caller cannot relabel Wall A as B.
  - Wrong document, revision, source SHA, snapshot, or page invalidates authority.
  - Unknown/Abstained status propagates; never converted into 0 or fallbacks.
  - Exact legitimate positive chain corroborates across all authorities.
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
    GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL,
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    OpeningCountDiagnosticRequest,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    SourceEnumerationState,
    _AUTHORITY_SEAL as UNIV_SEAL,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningExistenceResult,
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
    _AUTHORITY_SEAL as WALL_CAND_SEAL,
    _ScopeKey as WallScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_raster_wall_network_authority import (
    RASTER_LINEAGE_MISMATCH,
    RASTER_WALL_AMBIGUOUS,
    RASTER_WALL_NETWORK_RESOLVED,
    RasterPixelSegment,
    RasterTransformBinding,
    RasterWallNetworkProducer,
    RasterWallNetworkSelector,
    RasterWallObservationProducer,
    RasterWallObservationSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingResult,
    _AUTHORITY_SEAL as BIND_SEAL,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityAuthority,
    ScheduleRowQuantityProducer,
    ScheduleRowQuantitySelector,
)
from pb_source_observation_authority import (
    ObservationSelector,
    ProducerSnapshotRecord,
    PublishedSourceSnapshot,
    SourceDecodeCoverageRecord,
    SourceObservationProducer,
    SourceRevisionRecord,
)
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassAuthority,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)
from pb_wall_role_authority import (
    WALL_ROLE_AMBIGUOUS,
    WALL_ROLE_CANDIDATE_LABEL_REJECTED,
    WALL_ROLE_LINEAGE_MISMATCH,
    WALL_ROLE_RESOLVED,
    WALL_ROLE_STALE_EVIDENCE,
    WALL_ROLE_TOPOLOGY_WRONG_WALL,
    WALL_ROLE_UNRESOLVED,
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
    WallTopologyEvidence,
    WallTopologyProducer,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_thickness_face_authority import (
    WALL_THICKNESS_CANDIDATE_REJECTED,
    WALL_THICKNESS_DEFAULT_REJECTED,
    WALL_THICKNESS_FACE_RESOLVED,
    WALL_THICKNESS_LINEAGE_MISMATCH,
    WALL_THICKNESS_STALE_EVIDENCE,
    WALL_THICKNESS_UNRESOLVED,
    WALL_THICKNESS_WRONG_WALL,
    WallThicknessEvidence,
    WallThicknessFaceProducer,
    WallThicknessFaceSelector,
    WallThicknessProducer,
)

DOC = "doc-cross-audit-1"
REV = "R1"
SHA = "c" * 64
SNAP = "snap-cross-1"
PAGE = "page-1"
SCOPE = "scope-plan-1"
VP_PLAN = "vp-main"
WALL_A = "phys-wall-A"
WALL_B = "phys-wall-B"


def _snapshot(doc: str = DOC, rev: str = REV, sha: str = SHA, snap: str = SNAP) -> PublishedSourceSnapshot:
    rev_rec = SourceRevisionRecord(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        source_locator="mem://test",
        partition_ids=(PAGE,),
        producer_method="test",
        producer_version="1.0",
        producer_generation=1,
    )
    cov_rec = SourceDecodeCoverageRecord(
        document_id=doc,
        revision_id=rev,
        total_pages=1,
        decoded_pages=(1,),
        failed_pages=(),
        state="complete",
    )
    snap_rec = ProducerSnapshotRecord(
        snapshot_id=snap,
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        observation_ids=(),
        producer_method="test",
        producer_version="1.0",
        producer_generation=1,
    )
    return PublishedSourceSnapshot(revision=rev_rec, coverage=cov_rec, snapshot=snap_rec)


def _scale_auth(page: str = PAGE) -> PhysicalScaleAuthority:
    sel = PhysicalScaleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=page
    )
    evidence = PhysicalScaleEvidence(
        selector=sel,
        record_id="rec-scale-cross",
        source_kind="graphic_scale_bar",
        source_span_pt=100.0,
        physical_span_mm=1000.0,
        points_per_mm=0.1,
        mm_per_point=10.0,
        source_segment_observation_ids=(),
        source_text_observation_ids=(),
        viewport_id=None,
    )
    return PhysicalScaleAuthority(
        {sel.key: PhysicalScaleResult(status=EvidenceResolutionStatus.CORROBORATED, evidence=evidence, reason_codes=())},
        _seal=SCALE_SEAL,
    )


def _wall_cand_auth(*records: PhysicalWallCandidateRecord) -> PhysicalWallCandidateAuthority:
    key = WallScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}",
    )
    return PhysicalWallCandidateAuthority(
        {
            key: PhysicalWallCandidateScopeResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                scope_complete=True,
                records=tuple(records),
                source_observation_ids=(),
                document_id=DOC, revision_id=REV, source_sha256=SHA,
                snapshot_id=SNAP, page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}",
                reason_codes=(),
            )
        },
        _seal=WALL_CAND_SEAL,
    )


def _make_candidate_wall(wall_id: str, interior_exterior: str = "exterior", thickness_m: float = 0.2) -> PhysicalWallCandidateRecord:
    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=f"wall-source:page-{PAGE}",
        representation="single_line",
        centerline_pts=((0.0, 0.0), (10.0, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior=interior_exterior,
        level_id=None,
        supporting_evidence_ids=("s1",),
        metadata={},
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=f"wall-source:page-{PAGE}",
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=((0.0, 0.0), (10.0, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(wall_candidate_id=wall_id, wall_candidate=cand, physical_identity=ident)


def _setup_opening_count_producer(
    openings: tuple[PhysicalOpeningExistenceRecord, ...] = (),
    schedule_qty: dict | None = None,
    bindings: tuple[tuple[str, str, str], ...] = (),
    diagnostic: OpeningCountDiagnosticRequest | None = None,
) -> tuple[GenericOpeningCountProducer, GenericOpeningCountSelector]:
    member_ids = tuple(op.record_id for op in openings)
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-1",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=(PAGE,),
        viewport_id=VP_PLAN,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=member_ids,
        universe_fingerprint="fp-1",
        reason_codes=(),
    )
    univ_auth = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): univ_rec}, _seal=UNIV_SEAL
    )

    src_auth = SourceObservationProducer(
        producer_method="test", producer_version="1.0"
    ).authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    by_id = {op.record_id: op for op in openings}

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        rec = by_id.get(selector.observation_id)
        if rec is None:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                physical_opening_existence="unresolved",
                reason_codes=("not_found",),
            )
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence="exists",
            reason_codes=(),
            existence_record=rec,
        )

    object.__setattr__(phys_auth, "prove_existence", _prove)

    view_prod = ViewportViewClassProducer.create()
    view_prod.publish(
        ViewportViewClassSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            viewport_id=VP_PLAN,
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("view-obs-1",),
    )

    bind_results: dict = {}
    for op_id, mark, row_id in bindings:
        key = (DOC, REV, SHA, SNAP, SCOPE, op_id)
        bind_results[key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("binding_resolved",),
            record=ScheduleOpeningInstanceBindingRecord(
                record_id=f"bind-{op_id}",
                document_id=DOC,
                revision_id=REV,
                source_sha256=SHA,
                snapshot_id=SNAP,
                page_id=PAGE,
                decision_scope_id=SCOPE,
                opening_record_id=op_id,
                tag_observation_id=f"tag-{op_id}",
                tag_mark=mark,
                schedule_page_id=PAGE,
                schedule_row_observation_ids=(row_id,),
                schedule_row_type_mark=mark,
                schedule_row_width_mm=900,
                schedule_row_height_mm=2100,
            ),
        )
    bind_auth = (
        ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)
        if bindings
        else None
    )

    qty_auth = None
    if schedule_qty:
        qty_prod = ScheduleRowQuantityProducer.create()
        for row_ids, (mark, declared) in schedule_qty.items():
            qty_prod.publish(
                ScheduleRowQuantitySelector(
                    document_id=DOC,
                    revision_id=REV,
                    source_sha256=SHA,
                    snapshot_id=SNAP,
                    schedule_page_id=PAGE,
                    schedule_row_observation_ids=tuple(row_ids),
                ),
                declared_count=declared,
                type_mark=mark,
                universe_complete=True,
            )
        qty_auth = qty_prod.authority()

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=qty_auth,
        diagnostic_request=diagnostic,
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    return producer, sel


# ── Integration Contract 1: Item 25 candidate cannot become Item 26 wall role ──


def test_item25_candidate_cannot_launder_into_item26_wall_role() -> None:
    # Item 25 produces candidate geometry, but candidate claims exterior
    cand = _make_candidate_wall(WALL_A, interior_exterior="exterior")
    cand_auth = _wall_cand_auth(cand)

    # Item 26 wall role producer without independent topology/annotation evidence
    role_producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = WallRoleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
    )
    res = role_producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_CANDIDATE_LABEL_REJECTED in res.reason_codes
    assert res.record is None


# ── Integration Contract 2: Item 25 candidate cannot become Item 27 thickness ──


def test_item25_candidate_cannot_launder_into_item27_thickness() -> None:
    # Item 25 candidate geometry has thickness_m = 0.2
    cand = _make_candidate_wall(WALL_A, thickness_m=0.2)
    cand_auth = _wall_cand_auth(cand)
    scale_auth = _scale_auth()

    thick_producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    sel = WallThicknessFaceSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
    )
    res = thick_producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_UNRESOLVED in res.reason_codes
    assert WALL_THICKNESS_CANDIDATE_REJECTED in res.reason_codes
    assert res.record is None


# ── Integration Contract 3: Item 23 schedule row cannot manufacture physical opening ──


def test_item23_schedule_row_cannot_manufacture_physical_opening_identity() -> None:
    # Schedule row declares 8, but physical openings are 0
    producer, sel = _setup_opening_count_producer(
        openings=(),
        schedule_qty={("row-w1",): ("W1", 8)},
        diagnostic=OpeningCountDiagnosticRequest(schedule_declared_counts={"W1": 8}),
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL in res.reason_codes
    assert res.record is None


# ── Integration Contract 4: Exact physical_wall_id survives all handoffs ──────


def test_exact_physical_wall_id_survives_all_handoffs() -> None:
    cand_a = _make_candidate_wall(WALL_A)
    cand_b = _make_candidate_wall(WALL_B)
    cand_auth = _wall_cand_auth(cand_a, cand_b)
    scale_auth = _scale_auth()

    # Publish thickness for WALL_A only
    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="thick-ev-1",
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, physical_wall_id=WALL_A, thickness_m=0.15, source_kind="annotation",
        )
    )
    thick_face_prod = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )

    # WALL_A resolves
    res_a = thick_face_prod.publish(
        WallThicknessFaceSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert res_a.status is EvidenceResolutionStatus.CORROBORATED
    assert res_a.record.physical_wall_id == WALL_A
    assert res_a.record.thickness_m == 0.15

    # WALL_B fails closed (cannot use WALL_A's thickness)
    res_b = thick_face_prod.publish(
        WallThicknessFaceSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_B,
        )
    )
    assert res_b.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_UNRESOLVED in res_b.reason_codes
    assert res_b.record is None


# ── Integration Contract 5: Stale lineage fails closed across all producers ───────────


def test_stale_lineage_fails_closed_across_all_producers() -> None:
    cand = _make_candidate_wall(WALL_A)
    cand_auth = _wall_cand_auth(cand)

    # 1. Stale topology evidence lineage
    stale_topo = WallTopologyEvidence(
        evidence_id="topo-stale",
        document_id=DOC,
        revision_id="OLD_REV",
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        physical_wall_id=WALL_A,
        bounds_exterior=True,
        enclosed_space_count=1,
    )
    from pb_wall_role_authority import _AUTHORITY_SEAL as ROLE_SEAL, WallTopologyAuthority
    stale_topo_auth = WallTopologyAuthority(
        {(DOC, REV, SHA, SNAP, PAGE, WALL_A): stale_topo},
        _seal=ROLE_SEAL,
    )
    role_prod = WallRoleProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_topology_authority=stale_topo_auth,
    )
    role_res = role_prod.publish(
        WallRoleSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert role_res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_STALE_EVIDENCE in role_res.reason_codes
    assert WALL_ROLE_LINEAGE_MISMATCH in role_res.reason_codes
    assert role_res.record is None

    # 2. Stale thickness evidence lineage
    stale_thick = WallThicknessEvidence(
        evidence_id="thick-stale",
        document_id=DOC,
        revision_id="OLD_REV",
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        physical_wall_id=WALL_A,
        thickness_m=0.20,
        source_kind="figured_dimension",
    )
    from pb_wall_thickness_face_authority import _AUTHORITY_SEAL as THICK_SEAL, WallThicknessAuthority
    stale_thick_auth = WallThicknessAuthority(
        {(DOC, REV, SHA, SNAP, PAGE, WALL_A): stale_thick},
        _seal=THICK_SEAL,
    )
    thick_prod = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=_scale_auth(),
        wall_thickness_authority=stale_thick_auth,
    )
    thick_res = thick_prod.publish(
        WallThicknessFaceSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert thick_res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_STALE_EVIDENCE in thick_res.reason_codes
    assert WALL_THICKNESS_LINEAGE_MISMATCH in thick_res.reason_codes
    assert thick_res.record is None

    # 3. Stale snapshot lineage in raster network producer
    obs_producer = RasterWallObservationProducer.create()
    obs_producer.publish(
        RasterWallObservationSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        ),
        transform=RasterTransformBinding(dpi=300, px_to_pt_ratio=72.0 / 300.0, source_image_sha256="f" * 64),
        segments=(),
        snapshot=_snapshot(),
    )
    raster_net_prod = RasterWallNetworkProducer.from_authorities(
        observation_authority=obs_producer.authority(),
        physical_scale_authority=_scale_auth(),
        snapshot=_snapshot(snap="snap-other"),
    )
    raster_res = raster_net_prod.publish(
        RasterWallNetworkSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        )
    )
    assert raster_res.status is EvidenceResolutionStatus.CONFLICT
    assert RASTER_LINEAGE_MISMATCH in raster_res.reason_codes


# ── Integration Contract 6: Ambiguous raster geometry fails closed ─────────────


def test_ambiguous_raster_geometry_fails_closed() -> None:
    snapshot = _snapshot()
    obs_producer = RasterWallObservationProducer.create()
    img_sha = "f" * 64
    binding = RasterTransformBinding(dpi=300, px_to_pt_ratio=72.0 / 300.0, source_image_sha256=img_sha)

    # Segment flagged as ambiguous
    ambig_seg = RasterPixelSegment(
        start_px=(100.0, 100.0),
        end_px=(500.0, 100.0),
        thickness_px=20.0,
        is_ambiguous=True,
        ambiguity_reason="raster_clutter_overlap",
    )
    obs_producer.publish(
        RasterWallObservationSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
        ),
        transform=binding,
        segments=(ambig_seg,),
        snapshot=snapshot,
    )
    obs_auth = obs_producer.authority()
    scale_auth = _scale_auth()

    net_producer = RasterWallNetworkProducer.from_authorities(
        observation_authority=obs_auth,
        physical_scale_authority=scale_auth,
        snapshot=snapshot,
    )
    net_sel = RasterWallNetworkSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
    )
    net_res = net_producer.publish(net_sel)
    # Ambiguous raster segment abstains
    assert net_res.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_WALL_AMBIGUOUS in net_res.reason_codes
    assert net_res.record is None


# ── Integration Contract 7: Unresolved role and thickness stay unresolved ────


def test_unresolved_role_and_thickness_do_not_fallback() -> None:
    cand_a = _make_candidate_wall(WALL_A, interior_exterior="unresolved", thickness_m=0.0)
    cand_auth = _wall_cand_auth(cand_a)
    scale_auth = _scale_auth()

    # Role without topology
    role_prod = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    role_res = role_prod.publish(
        WallRoleSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert role_res.status is EvidenceResolutionStatus.ABSTAINED
    assert role_res.record is None

    # Thickness without evidence
    thick_prod = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    thick_res = thick_prod.publish(
        WallThicknessFaceSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert thick_res.status is EvidenceResolutionStatus.ABSTAINED
    assert thick_res.record is None


# ── Integration Contract 8: Exact legitimate positive chain ───────────────────


def test_exact_legitimate_positive_chain() -> None:
    cand_a = _make_candidate_wall(WALL_A)
    cand_auth = _wall_cand_auth(cand_a)
    scale_auth = _scale_auth()

    # 1. Independent Topology Evidence → Proves EXTERNAL
    topo_prod = WallTopologyProducer.create()
    topo_prod.publish(
        WallTopologyEvidence(
            evidence_id="topo-pos-1",
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, physical_wall_id=WALL_A, bounds_exterior=True, enclosed_space_count=1,
            enclosed_space_ids=("room-lab",),
        )
    )
    role_prod = WallRoleProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_topology_authority=topo_prod.authority(),
    )
    role_res = role_prod.publish(
        WallRoleSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert role_res.status is EvidenceResolutionStatus.CORROBORATED
    assert role_res.record is not None
    assert role_res.record.role == WallRoleClassification.EXTERNAL
    assert role_res.record.physical_wall_id == WALL_A

    # 2. Independent Thickness Evidence → Proves 200mm thickness + authentic face geometry
    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="thick-pos-1",
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, physical_wall_id=WALL_A, thickness_m=0.20, source_kind="figured_dimension",
        )
    )
    thick_face_prod = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    thick_res = thick_face_prod.publish(
        WallThicknessFaceSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=f"wall-source:page-{PAGE}", physical_wall_id=WALL_A,
        )
    )
    assert thick_res.status is EvidenceResolutionStatus.CORROBORATED
    assert thick_res.record is not None
    assert thick_res.record.thickness_m == 0.20
    assert thick_res.record.thickness_mm == 200.0
    assert thick_res.record.physical_wall_id == WALL_A
    assert thick_res.record.centerline_wkb_hex.startswith("0102000000")  # Little-endian LineString
