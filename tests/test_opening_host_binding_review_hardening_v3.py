"""Focused regressions from the independent #381 multi-angle review.

These tests are production-successor coverage only. Frozen PR #372 remains
byte-for-byte unchanged.
"""
from __future__ import annotations

from dataclasses import replace
import fitz
import pytest
from types import SimpleNamespace

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    BOUNDARY_EVALUATION_EVALUATED,
    ExcludedBoundaryPrimitive,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallScopeBoundaryEvaluation,
)
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
)
from pb_source_observation_authority import SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT
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
    source_primitive_ids: tuple[str, ...] | None = None,
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
        source_primitive_ids=(
            (f"source:{wall_id}",)
            if source_primitive_ids is None
            else source_primitive_ids
        ),
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


def _incomplete_scope(
    records: tuple[PhysicalWallCandidateRecord, ...],
    *,
    tainted_ids: tuple[str, ...] = (),
    excluded_primitives: tuple[ExcludedBoundaryPrimitive, ...] = (),
    equivalence: PhysicalWallEquivalenceResolution | None = None,
) -> PhysicalWallCandidateScopeResult:
    ids = tuple(record.wall_candidate_id for record in records)
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=False,
        records=records,
        source_observation_ids=tuple(f"obs:{wall_id}" for wall_id in ids),
        document_id="doc-local-host",
        revision_id="rev-local-host",
        source_sha256="sha-local-host",
        snapshot_id="snap-local-host",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        reason_codes=(
            "physical_wall_candidate_scope_resolved",
            "physical_wall_candidate_scope_cropped_at_page_boundary",
        ),
        equivalence=equivalence or _equivalence(records),
        proposition="physical_wall_candidate_scope_resolved",
        boundary_evaluation=PhysicalWallScopeBoundaryEvaluation(
            status=BOUNDARY_EVALUATION_EVALUATED,
            reason_code=None,
            evaluated_wall_candidate_ids=ids,
            boundary_tainted_wall_candidate_ids=tuple(sorted(tainted_ids)),
            boundary_taint_reason_codes=tuple(
                (wall_id, ("scope_boundary_dangling_end",))
                for wall_id in sorted(tainted_ids)
            ),
            excluded_boundary_primitives=excluded_primitives,
            authenticated_frame_edge_primitive_count=0,
            contact_tolerance_pt=float(DEFAULT_GAP_SNAP_TOLERANCE_PT),
        ),
    )


def test_local_host_scope_ignores_unrelated_boundary_taint() -> None:
    host_records = _band_records(center_offset=0.0)
    unrelated = _record("unrelated-tainted", ((200.0, 80.0), (260.0, 80.0)))
    scope = _incomplete_scope(
        host_records + (unrelated,),
        tainted_ids=(unrelated.wall_candidate_id,),
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is not None
    assert reasons == (host.HOST_LOCAL_BOUNDARY_CLEAN_SCOPE_RESOLVED,)
    assert {record.wall_candidate_id for record in local.records} == {
        record.wall_candidate_id for record in host_records
    }
    resolved = host._resolve_host_bands(
        local.records,
        OPENING,
        local.equivalence,
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert len(resolved.bands) == 1


def test_local_host_scope_includes_clean_raster_spanning_candidate() -> None:
    # Whole-wall host resolution itself does not require raw source-primitive
    # lineage. Local-scope admission must therefore not require it either.
    spanning = _record(
        "raster-spanning-host",
        ((-100.0, 0.0), (140.0, 0.0)),
        source_primitive_ids=(),
    )
    scope = _incomplete_scope((spanning,))

    local, reasons = host._local_boundary_clean_host_scope(
        scope,
        OPENING,
        include_spanning_raster_candidates=True,
    )

    assert local is not None
    assert reasons == (host.HOST_LOCAL_BOUNDARY_CLEAN_SCOPE_RESOLVED,)
    assert tuple(record.wall_candidate_id for record in local.records) == (
        spanning.wall_candidate_id,
    )
    resolved = host._resolve_raster_whole_wall_host(
        local.records,
        OPENING,
        local.equivalence,
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert len(resolved.bands) == 1
    assert resolved.bands[0].member_ids == (spanning.wall_candidate_id,)


def test_local_host_scope_does_not_add_spanning_candidate_outside_raster_mode() -> None:
    spanning = _record(
        "non-raster-spanning-wall",
        ((-100.0, 0.0), (140.0, 0.0)),
    )
    scope = _incomplete_scope((spanning,))

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "no_local_host_wall_candidates" in reasons


def test_local_host_scope_blocks_tainted_raster_spanning_candidate() -> None:
    spanning = _record(
        "tainted-raster-spanning-host",
        ((-100.0, 0.0), (140.0, 0.0)),
    )
    scope = _incomplete_scope(
        (spanning,),
        tainted_ids=(spanning.wall_candidate_id,),
    )

    local, reasons = host._local_boundary_clean_host_scope(
        scope,
        OPENING,
        include_spanning_raster_candidates=True,
    )

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "host_relevant_wall_boundary_tainted" in reasons


def test_local_host_scope_blocks_excluded_raster_spanning_primitive() -> None:
    spanning = _record(
        "clean-raster-spanning-host",
        ((-100.0, 0.0), (140.0, 0.0)),
        source_primitive_ids=(),
    )
    excluded = ExcludedBoundaryPrimitive(
        category="crosses_scope_boundary",
        source_observation_id="obs:excluded-raster-span",
        x1=-100.0,
        y1=0.0,
        x2=140.0,
        y2=0.0,
    )
    scope = _incomplete_scope(
        (spanning,),
        excluded_primitives=(excluded,),
    )

    local, reasons = host._local_boundary_clean_host_scope(
        scope,
        OPENING,
        include_spanning_raster_candidates=True,
    )

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "host_relevant_excluded_boundary_primitive" in reasons


def test_local_host_scope_ignores_excluded_span_outside_raster_wall_band() -> None:
    spanning = _record(
        "clean-raster-spanning-host",
        ((-100.0, 0.0), (140.0, 0.0)),
        source_primitive_ids=(),
    )
    excluded = ExcludedBoundaryPrimitive(
        category="crosses_scope_boundary",
        source_observation_id="obs:excluded-raster-span-unrelated",
        x1=-100.0,
        y1=40.0,
        x2=140.0,
        y2=40.0,
    )
    scope = _incomplete_scope(
        (spanning,),
        excluded_primitives=(excluded,),
    )

    local, reasons = host._local_boundary_clean_host_scope(
        scope,
        OPENING,
        include_spanning_raster_candidates=True,
    )

    assert local is not None
    assert reasons == (host.HOST_LOCAL_BOUNDARY_CLEAN_SCOPE_RESOLVED,)
    assert tuple(record.wall_candidate_id for record in local.records) == (
        spanning.wall_candidate_id,
    )


def test_local_host_scope_abstains_when_relevant_wall_is_boundary_tainted() -> None:
    host_records = _band_records(center_offset=0.0)
    tainted = host_records[0].wall_candidate_id
    scope = _incomplete_scope(host_records, tainted_ids=(tainted,))

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "host_relevant_wall_boundary_tainted" in reasons


def test_local_host_scope_abstains_when_excluded_boundary_primitive_can_host() -> None:
    host_records = _band_records(center_offset=0.0)
    excluded = ExcludedBoundaryPrimitive(
        category="crosses_scope_boundary",
        source_observation_id="obs:excluded-host-role",
        x1=-100.0,
        y1=15.0,
        x2=0.0,
        y2=15.0,
    )
    scope = _incomplete_scope(
        host_records,
        excluded_primitives=(excluded,),
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "host_relevant_excluded_boundary_primitive" in reasons


def _unsafe_bridge_scope(
    *,
    classification: PhysicalEquivalenceClass,
    unsafe: PhysicalWallCandidateRecord,
    share_lineage: bool = False,
) -> PhysicalWallCandidateScopeResult:
    host_records = _band_records(center_offset=0.0)
    relevant = host_records[0]
    relevant_id = relevant.wall_candidate_id
    if share_lineage:
        unsafe = replace(
            unsafe,
            physical_identity=replace(
                unsafe.physical_identity,
                source_primitive_ids=(
                    relevant.physical_identity.source_primitive_ids[0],
                ),
            ),
        )
    records = host_records + (unsafe,)
    base = _equivalence(records)
    same_group = (
        (tuple(sorted((relevant_id, unsafe.wall_candidate_id))),)
        if classification is PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
        else ()
    )
    equivalence = replace(
        base,
        equivalence_groups=same_group,
        same_wall_ids=(
            tuple(sorted((relevant_id, unsafe.wall_candidate_id)))
            if same_group
            else ()
        ),
        ambiguous_wall_ids=(
            tuple(sorted((relevant_id, unsafe.wall_candidate_id)))
            if classification
            is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
            else ()
        ),
        pair_classifications=(
            (
                min(relevant_id, unsafe.wall_candidate_id),
                max(relevant_id, unsafe.wall_candidate_id),
                classification.value,
            ),
        ),
    )
    return _incomplete_scope(
        records,
        tainted_ids=(unsafe.wall_candidate_id,),
        equivalence=equivalence,
    )


def test_nonhost_unsafe_same_bridge_still_blocks_local_host() -> None:
    unsafe = _record("unsafe-same-remote", ((200.0, 80.0), (260.0, 80.0)))
    scope = _unsafe_bridge_scope(
        classification=PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
        unsafe=unsafe,
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert host.HOST_LOCAL_BOUNDARY_SCOPE_UNAVAILABLE in reasons
    assert "host_equivalence_bridges_unsafe_boundary_evidence" in reasons


def test_remote_lineage_independent_ambiguous_bridge_is_not_local_contamination() -> None:
    # Page-wide equivalence intentionally keeps unscaled overlapping parallel
    # paths ambiguous. This wall is both longitudinally and laterally remote
    # from the opening and shares no immutable identity evidence with its host.
    unsafe = _record(
        "unsafe-ambiguous-remote",
        ((200.0, 80.0), (260.0, 80.0)),
    )
    scope = _unsafe_bridge_scope(
        classification=PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        unsafe=unsafe,
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is not None
    assert reasons == (host.HOST_LOCAL_BOUNDARY_CLEAN_SCOPE_RESOLVED,)
    assert unsafe.wall_candidate_id not in {
        record.wall_candidate_id for record in local.records
    }


def test_remote_ambiguous_bridge_with_shared_lineage_still_blocks() -> None:
    unsafe = _record(
        "unsafe-ambiguous-shared-source",
        ((200.0, 80.0), (260.0, 80.0)),
    )
    scope = _unsafe_bridge_scope(
        classification=PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        unsafe=unsafe,
        share_lineage=True,
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert "host_equivalence_bridges_unsafe_boundary_evidence" in reasons


def test_ambiguous_unsafe_candidate_inside_opening_wall_band_still_blocks() -> None:
    # Spans the aperture rather than ending at a host edge, so it is not one of
    # the ordinary left/right local records. It nevertheless occupies the
    # opening's own source-proven wall band and must remain contamination.
    unsafe = _record(
        "unsafe-ambiguous-local-band",
        ((-20.0, 4.0), (60.0, 4.0)),
    )
    scope = _unsafe_bridge_scope(
        classification=PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        unsafe=unsafe,
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert "host_equivalence_bridges_unsafe_boundary_evidence" in reasons


def test_non_evaluable_ambiguous_unsafe_candidate_stays_fail_closed() -> None:
    unsafe_base = _record(
        "unsafe-ambiguous-curved",
        ((200.0, 80.0), (260.0, 80.0)),
    )
    unsafe = replace(
        unsafe_base,
        wall_candidate=replace(unsafe_base.wall_candidate, is_curved=True),
    )
    scope = _unsafe_bridge_scope(
        classification=PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        unsafe=unsafe,
    )

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is None
    assert "host_equivalence_bridges_unsafe_boundary_evidence" in reasons



def test_local_host_scope_recomputes_canonical_equivalence_invariants() -> None:
    host_records = _band_records(center_offset=0.0)
    scope = _incomplete_scope(host_records)

    local, reasons = host._local_boundary_clean_host_scope(scope, OPENING)

    assert local is not None
    assert reasons == (host.HOST_LOCAL_BOUNDARY_CLEAN_SCOPE_RESOLVED,)
    assert set(local.equivalence.representative_wall_ids).isdisjoint(
        local.equivalence.abstained_wall_ids
    )
    for group in local.equivalence.equivalence_groups:
        assert len(set(group) & set(local.equivalence.representative_wall_ids)) == 1


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


def _obs(line):
    return SimpleNamespace(geometry=tuple(float(value) for value in line))


def test_window_jamb_pair_reconstructs_two_face_opening_geometry_from_topology_only() -> None:
    records = (
        _obs((20.0, 80.0, 120.0, 80.0)),
        _obs((160.0, 80.0, 280.0, 80.0)),
        _obs((120.0, 80.0, 120.0, 100.0)),
        _obs((160.0, 80.0, 160.0, 100.0)),
    )
    geometry = host._window_jamb_pair_geometry(records)
    assert geometry is not None
    assert geometry.origin == pytest.approx((120.0, 90.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(20.0)
    assert abs(geometry.axis[0]) == pytest.approx(1.0)
    assert abs(geometry.axis[1]) == pytest.approx(0.0)


def test_window_jamb_pair_rejects_unattached_nearby_parallel_jamb() -> None:
    records = (
        _obs((20.0, 80.0, 120.0, 80.0)),
        _obs((160.0, 80.0, 280.0, 80.0)),
        _obs((120.0, 80.0, 120.0, 100.0)),
        _obs((161.0, 80.0, 161.0, 100.0)),
    )
    assert host._window_jamb_pair_geometry(records) is None


def test_window_jamb_pair_rejects_jambs_on_opposite_wall_sides() -> None:
    records = (
        _obs((20.0, 80.0, 120.0, 80.0)),
        _obs((160.0, 80.0, 280.0, 80.0)),
        _obs((120.0, 80.0, 120.0, 100.0)),
        _obs((160.0, 80.0, 160.0, 60.0)),
    )
    assert host._window_jamb_pair_geometry(records) is None


def _source_obs(line, raw_id: str):
    return SimpleNamespace(
        geometry=tuple(float(value) for value in line),
        source_primitive_ref="visible:" + raw_id,
    )


def test_generic_gap_host_binds_exact_source_lineage_not_nearest_wall() -> None:
    left = _record("left", ((-100.0, 0.0), (0.0, 0.0)))
    right = _record("right", ((40.0, 0.0), (140.0, 0.0)))
    unrelated = _record("unrelated", ((-5.0, 1.0), (45.0, 1.0)))
    records = (left, right, unrelated)

    opening_records = (
        _source_obs((-100.0, 0.0, 0.0, 0.0), "source:left"),
        _source_obs((40.0, 0.0, 140.0, 0.0), "source:right"),
        _source_obs((0.0, 0.0, 0.0, 40.0), "source:leaf"),
    )
    result = host._resolve_gap_lineage_host_from_records(
        opening_records,
        records,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == ("left", "right")
    assert "unrelated" not in result.bands[0].member_ids


def test_generic_gap_host_abstains_when_source_wall_lineage_is_unmapped() -> None:
    left = _record("left", ((-100.0, 0.0), (0.0, 0.0)))
    records = (left,)
    opening_records = (
        _source_obs((-100.0, 0.0, 0.0, 0.0), "source:left"),
        _source_obs((40.0, 0.0, 140.0, 0.0), "source:right"),
        _source_obs((0.0, 0.0, 0.0, 40.0), "source:leaf"),
    )
    result = host._resolve_gap_lineage_host_from_records(
        opening_records,
        records,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.bands == ()
    assert host.HOST_GAP_LINEAGE_UNMAPPED in result.reason_codes


def test_generic_gap_host_conflicts_when_one_source_role_has_multiple_unproved_owners() -> None:
    left_a = _record("left-a", ((-100.0, 0.0), (0.0, 0.0)))
    left_b_base = _record("left-b", ((-100.0, 0.0), (0.0, 0.0)))
    left_b = replace(
        left_b_base,
        physical_identity=replace(
            left_b_base.physical_identity,
            source_primitive_ids=("source:left-a",),
        ),
    )
    right = _record("right", ((40.0, 0.0), (140.0, 0.0)))
    records = (left_a, left_b, right)
    opening_records = (
        _source_obs((-100.0, 0.0, 0.0, 0.0), "source:left-a"),
        _source_obs((40.0, 0.0, 140.0, 0.0), "source:right"),
        _source_obs((0.0, 0.0, 0.0, 40.0), "source:leaf"),
    )
    result = host._resolve_gap_lineage_host_from_records(
        opening_records,
        records,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_GAP_LINEAGE_AMBIGUOUS in result.reason_codes
