"""Physical opening void authority -- production acceptance tests.

Reuses the real PDF-ingestion fixture pattern from
``test_opening_dimension_production_v1.py`` (a genuine synthetic PDF with
real vector geometry and real text, not a mock) so that width resolution and
height non-resolution are both exercised through the actual producer-owned
authorities, not doubles.

IMPORTANT: ``OpeningDimensionAuthority.resolve_height`` unconditionally
returns unresolved on current main (there is no opening-level height
evidence source yet -- see module docstring on
``pb_physical_opening_void_authority``). ``test_synthetic_positive_path_*``
below is the one place a height result is injected via ``monkeypatch``,
clearly to prove the void arithmetic/record-construction logic is correct in
isolation -- it is not a claim that real height resolution exists.
"""
from __future__ import annotations

import fitz
import pytest

from pb_hosted_opening_geometry import HostedOpeningSpan
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_dimension_authority import OpeningDimensionResult
from pb_opening_host_binding_authority import OpeningHostBindingProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_opening_void_authority import (
    OPENING_VOID_HEIGHT_UNRESOLVED,
    OPENING_VOID_HOST_BINDING_UNRESOLVED,
    OPENING_VOID_OPENING_RECORD_ID_MISMATCH,
    OPENING_VOID_PAGE_SCOPE_MISMATCH,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidProducer,
    PhysicalOpeningVoidSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY


SCOPE = "void-scope:page-1"


def _opening_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    page.draw_line(fitz.Point(100, 70), fitz.Point(140, 70), color=(0, 0, 0), width=0.5)
    page.draw_line(fitz.Point(100, 70), fitz.Point(100, 100), color=(0, 0, 0), width=0.5)
    page.draw_line(fitz.Point(140, 70), fitz.Point(140, 100), color=(0, 0, 0), width=0.5)
    page.insert_text(fitz.Point(112, 65), "900", color=(0, 0, 0))
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(document_id: str):
    producer = SourceVisibilityProducer(producer_method="ovoid-test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_opening_pdf(),
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def _positive_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        if physical.prove_existence(selector).proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("fixture must prove one opening")


def _host_wall(wall_id: str = "host-wall") -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id="vp_1",
        representation="single_line",
        centerline_pts=((20.0, 105.0), (220.0, 105.0)),
        face_a_segment_ids=(f"seg:{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}:n0", f"{wall_id}:n1"),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.8,
    )


def _host_span(*, page: int) -> HostedOpeningSpan:
    return HostedOpeningSpan(
        page=page,
        host_orientation_deg=0.0,
        jamb_start=(100.0, 105.0),
        jamb_end=(140.0, 105.0),
        span_pt=40.0,
        width_m=None,
        wall_thickness_pt=10.0,
        subtype="door_like",
        evidence_flags=("host_wall_band", "aligned_two_face_gap", "jamb_boundaries_confirmed"),
        reason="synthetic_fixture",
    )


def _edges(wall: WallCandidate) -> dict[str, dict[str, object]]:
    start, end = wall.centerline_pts[0], wall.centerline_pts[-1]
    edge_id = wall.face_a_segment_ids[0]
    return {
        edge_id: {
            "id": edge_id,
            "x1": start[0],
            "y1": start[1],
            "x2": end[0],
            "y2": end[1],
            LINEAGE_KEY: {"source_primitive_ids": (f"src:{wall.candidate_id}",)},
        }
    }


def _host_binding_authority(*, existence, page_id: str, opening_record_id: str):
    wall = _host_wall()
    host_producer = OpeningHostBindingProducer()
    host_producer.publish_scope(
        document_id=existence.document_id,
        revision_id=existence.revision_id,
        source_sha256=existence.source_sha256,
        snapshot_id=existence.snapshot_id,
        page_id=page_id,
        viewport_id=None,
        decision_scope_id=SCOPE,
        opening_record_id=opening_record_id,
        opening_span=_host_span(page=int(page_id)),
        walls=(wall,),
        edges_by_id=_edges(wall),
        source_complete=True,
        host_universe_complete=True,
        traversal_truncated=False,
    )
    return host_producer.authority()


def _existence_for(published, visibility):
    selector = _positive_selector(published, visibility)
    existence_result = PhysicalOpeningAuthority(visibility).prove_existence(selector)
    assert existence_result.status is EvidenceResolutionStatus.CORROBORATED
    return selector, existence_result.existence_record


def test_void_authority_is_producer_minted_and_selector_only() -> None:
    producer = PhysicalOpeningVoidProducer()
    authority = producer.authority()
    assert isinstance(authority, PhysicalOpeningVoidAuthority)
    with pytest.raises(ValueError):
        PhysicalOpeningVoidAuthority({}, _seal=object())
    with pytest.raises(TypeError):
        PhysicalOpeningVoidSelector(
            document_id="d", revision_id="r", source_sha256="s",
            snapshot_id="n", decision_scope_id="sc",
        )  # type: ignore[call-arg]


def test_real_opening_today_always_abstains_on_missing_height() -> None:
    """Honest current-state test: real existence, real host binding, real
    width (900mm), and a real (non-mocked) resolve_height call -- which
    cannot corroborate on current main. The void authority must abstain,
    not fabricate a height."""
    producer, published, visibility = _ingest("ovoid-real")
    selector, existence = _existence_for(published, visibility)
    dim_authority = _dimension_authority_for(producer)

    width_probe = dim_authority.resolve_width(selector)
    height_probe = dim_authority.resolve_height(selector)
    assert width_probe.status is EvidenceResolutionStatus.CORROBORATED
    assert width_probe.value_mm == pytest.approx(900.0)
    assert height_probe.status is not EvidenceResolutionStatus.CORROBORATED
    assert height_probe.value_mm is None

    host_authority = _host_binding_authority(
        existence=existence, page_id=existence.page_id, opening_record_id=existence.record_id
    )
    void_producer = PhysicalOpeningVoidProducer()
    result = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id=existence.record_id,
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=host_authority,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_VOID_HEIGHT_UNRESOLVED in result.reason_codes
    assert result.record is None

    resolved = void_producer.authority().resolve(
        PhysicalOpeningVoidSelector(
            document_id=existence.document_id,
            revision_id=existence.revision_id,
            source_sha256=existence.source_sha256,
            snapshot_id=existence.snapshot_id,
            decision_scope_id=SCOPE,
            opening_record_id=existence.record_id,
        )
    )
    assert resolved == result


def _dimension_authority_for(producer: SourceVisibilityProducer):
    return producer.opening_dimension_authority()


def test_opening_record_id_must_match_proven_existence() -> None:
    producer, published, visibility = _ingest("ovoid-mismatch")
    selector, existence = _existence_for(published, visibility)
    dim_authority = _dimension_authority_for(producer)
    host_authority = _host_binding_authority(
        existence=existence, page_id=existence.page_id, opening_record_id="caller-invented-opening-id"
    )
    void_producer = PhysicalOpeningVoidProducer()
    result = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id="caller-invented-opening-id",
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=host_authority,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_VOID_OPENING_RECORD_ID_MISMATCH in result.reason_codes


def test_host_binding_unresolved_blocks_void() -> None:
    producer, published, visibility = _ingest("ovoid-nohost")
    selector, existence = _existence_for(published, visibility)
    dim_authority = _dimension_authority_for(producer)
    empty_host_authority = OpeningHostBindingProducer().authority()  # nothing ever published
    void_producer = PhysicalOpeningVoidProducer()
    result = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id=existence.record_id,
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=empty_host_authority,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_VOID_HOST_BINDING_UNRESOLVED in result.reason_codes


def test_page_scope_mismatch_blocks_void() -> None:
    producer, published, visibility = _ingest("ovoid-pagemismatch")
    selector, existence = _existence_for(published, visibility)
    dim_authority = _dimension_authority_for(producer)
    wrong_page = "2" if existence.page_id != "2" else "3"
    host_authority = _host_binding_authority(
        existence=existence, page_id=wrong_page, opening_record_id=existence.record_id
    )
    void_producer = PhysicalOpeningVoidProducer()
    result = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id=existence.record_id,
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=host_authority,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_VOID_PAGE_SCOPE_MISMATCH in result.reason_codes


def test_synthetic_positive_path_computes_area_correctly(monkeypatch) -> None:
    """The one synthetic case: real existence/width/host binding, with ONLY
    resolve_height monkeypatched to a fixed value, since current main cannot
    corroborate a real opening height. Proves the arithmetic and record
    construction, not that height evidence exists."""
    producer, published, visibility = _ingest("ovoid-synthetic")
    selector, existence = _existence_for(published, visibility)
    dim_authority = _dimension_authority_for(producer)
    host_authority = _host_binding_authority(
        existence=existence, page_id=existence.page_id, opening_record_id=existence.record_id
    )

    synthetic_height = OpeningDimensionResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition="opening_height_resolved_SYNTHETIC_TEST_ONLY",
        value_mm=2100.0,
        axis="height",
        reason_codes=("synthetic_test_injected_height",),
        opening_existence_record=existence,
    )
    monkeypatch.setattr(dim_authority, "resolve_height", lambda _selector: synthetic_height)

    void_producer = PhysicalOpeningVoidProducer()
    result = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id=existence.record_id,
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=host_authority,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.width_mm == pytest.approx(900.0)
    assert result.record.height_mm == pytest.approx(2100.0)
    assert result.record.void_area_m2 == pytest.approx(0.9 * 2.1, abs=1e-6)
    assert result.record.host_wall_id == "host-wall"
    assert result.void_area_m2 == result.record.void_area_m2

    # Equivocation guard: republishing the identical scope is idempotent.
    again = void_producer.publish_scope(
        decision_scope_id=SCOPE,
        opening_record_id=existence.record_id,
        observation_selector=selector,
        dimension_authority=dim_authority,
        visibility_authority=visibility,
        host_binding_authority=host_authority,
    )
    assert again == result


def test_firewall_stays_closed() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    assert caps["host_binding"] is False
