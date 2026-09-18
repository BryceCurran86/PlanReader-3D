"""Item 17/18 cross-sheet wall-height positive-path regressions."""

from __future__ import annotations

import fitz
import pytest

from pb_cross_sheet_registration_authority import (
    CROSS_SHEET_RESOLVED,
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationRecord,
    CrossSheetRegistrationResult,
    _AUTHORITY_SEAL as CROSS_SEAL,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_height_authority import WallHeightProducer, WallHeightSelector
from pb_wall_room_topology_contracts import JunctionType, WallCandidate

DOC = "doc-wall-height-cross-sheet"
WALL = "wall-plan-1"
TARGET_WALL = "wall-elevation-1"


def _draw_witness_dim(
    page: fitz.Page, *, x: float, y0: float, y1: float, text: str
) -> None:
    page.draw_line((x, y0), (x, y1))
    page.draw_line((x - 18, y0), (x + 18, y0))
    page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text(
        (x + 5, (y0 + y1) / 2.0),
        text,
        fontsize=10,
        rotate=90,
    )


def _pdf(
    *,
    sheet_title: str = "ELEVATION",
    height_text: str = "2700",
    second_height_text: str | None = None,
) -> bytes:
    doc = fitz.open()

    plan = doc.new_page(width=640, height=460)
    plan.draw_rect(fitz.Rect(30, 30, 310, 310))
    plan.insert_text((60, 300), "GROUND FLOOR PLAN", fontsize=10)

    page = doc.new_page(width=640, height=460)
    fx0, fy0, fx1, fy1 = 30.0, 30.0, 310.0, 310.0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((58, 302), sheet_title, fontsize=10)

    label_x, label_y = 114.0, 142.0
    page.insert_text((label_x, label_y), "HEIGHT", fontsize=10)
    label_cx = label_x + fitz.get_text_length("HEIGHT", fontsize=10) / 2.0
    label_cy = label_y - 3.5
    y1 = label_cy - 4.0
    y0 = y1 - 36.0
    _draw_witness_dim(
        page, x=label_cx, y0=y0, y1=y1, text=height_text
    )
    if second_height_text is not None:
        _draw_witness_dim(
            page,
            x=label_cx + 22.0,
            y0=y0,
            y1=y1,
            text=second_height_text,
        )

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(
        producer_method="item17_cross_sheet_test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=DOC,
        source_bytes=pdf_bytes,
        source_locator="memory:item17-cross-sheet.pdf",
    )
    return source, published


def _wall_candidate(
    *,
    candidate_id: str,
    scope: str,
    points: tuple[tuple[float, float], ...],
) -> PhysicalWallCandidateRecord:
    candidate = WallCandidate(
        candidate_id=candidate_id,
        viewport_id=scope,
        representation="single_line",
        centerline_pts=points,
        face_a_segment_ids=("seg-1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior=None,
        level_id=None,
        supporting_evidence_ids=("source-seg",),
        metadata={},
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=candidate_id,
        viewport_id=scope,
        candidate_identity_id=f"identity-{candidate_id}",
        path_fingerprint=points,
        source_primitive_ids=("seg-1",),
        edge_ids=("seg-1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=candidate_id,
        wall_candidate=candidate,
        physical_identity=identity,
    )


def _candidate_authority(published) -> PhysicalWallCandidateAuthority:
    page1_scope = "wall-source:page-1"
    page2_scope = "wall-source:page-2"
    page1 = _wall_candidate(
        candidate_id=WALL,
        scope=page1_scope,
        points=((60.0, 200.0), (240.0, 200.0)),
    )
    # Geometry is deliberately near the HEIGHT callout on the elevation.
    page2 = _wall_candidate(
        candidate_id=TARGET_WALL,
        scope=page2_scope,
        points=((80.0, 150.0), (190.0, 150.0)),
    )

    def result(page_id: str, scope: str, record):
        return PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            scope_complete=True,
            records=(record,),
            source_observation_ids=("obs",),
            document_id=DOC,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=scope,
            reason_codes=(),
        )

    return PhysicalWallCandidateAuthority(
        {
            _ScopeKey(
                document_id=DOC,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id=page1_scope,
            ): result("1", page1_scope, page1),
            _ScopeKey(
                document_id=DOC,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="2",
                decision_scope_id=page2_scope,
            ): result("2", page2_scope, page2),
        },
        _seal=CANDIDATE_SEAL,
    )


def _cross_sheet_authority(
    published,
) -> CrossSheetRegistrationAuthority:
    key = (
        DOC,
        published.revision.revision_id,
        published.revision.source_sha256,
        published.snapshot.snapshot_id,
        "1",
        "2",
        WALL,
    )
    record = CrossSheetRegistrationRecord(
        record_id="registration-wall-1",
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_page_id="1",
        target_page_id="2",
        physical_element_id=WALL,
        target_physical_element_id=TARGET_WALL,
        source_view_type="plan",
        target_view_type="elevation",
        callout_mark="W-01",
        referenced_sheet_code="A-02",
    )
    return CrossSheetRegistrationAuthority(
        {
            key: CrossSheetRegistrationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(CROSS_SHEET_RESOLVED,),
                record=record,
            )
        },
        _seal=CROSS_SEAL,
    )


def _selector(published, wall_id: str = WALL) -> WallHeightSelector:
    return WallHeightSelector(
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id=wall_id,
    )


def _producer(pdf_bytes: bytes):
    source, published = _ingest(pdf_bytes)
    producer = WallHeightProducer.from_authorities(
        source,
        cross_sheet_registration_authority=_cross_sheet_authority(
            published
        ),
        physical_wall_candidate_authority=_candidate_authority(published),
    )
    return producer, published


def test_registered_elevation_height_resolves_firm_for_exact_plan_wall() -> None:
    producer, published = _producer(_pdf())
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.abstained is False
    assert qty.value == pytest.approx(2.7)
    assert qty.input_entity_ids == (WALL,)
    assert qty.metadata["target_entity_id"] == WALL
    assert qty.metadata["source_page_id"] == "1"
    assert qty.metadata["height_evidence_page_id"] == "2"
    assert (
        qty.metadata["identity_binding_kind"]
        == "cross_sheet_registration"
    )
    assert (
        qty.metadata["cross_sheet_registration_record_id"]
        == "registration-wall-1"
    )


def test_source_bytes_without_exact_identity_binding_stay_blocked() -> None:
    source, published = _ingest(_pdf())
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None
    assert (
        "wall_height_exact_identity_binding_unavailable"
        in qty.blocking_reasons
    )


def test_first_caller_cannot_mint_wall_identity_and_call_order_is_irrelevant() -> None:
    producer, published = _producer(_pdf())

    wrong_first = producer.publish_scope(
        _selector(published, wall_id="wall-attacker")
    )
    assert wrong_first.status == AuthorityStatus.BLOCKED.value
    assert wrong_first.value is None

    real_second = producer.publish_scope(_selector(published, wall_id=WALL))
    assert real_second.status == AuthorityStatus.FIRM.value
    assert real_second.value == pytest.approx(2.7)

    producer2, published2 = _producer(_pdf())
    real_first = producer2.publish_scope(_selector(published2, wall_id=WALL))
    wrong_second = producer2.publish_scope(
        _selector(published2, wall_id="wall-attacker")
    )
    assert real_first.status == AuthorityStatus.FIRM.value
    assert wrong_second.status == AuthorityStatus.BLOCKED.value


def test_plan_view_height_text_cannot_become_cross_sheet_wall_height() -> None:
    producer, published = _producer(_pdf(sheet_title="GROUND FLOOR PLAN"))
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_conflicting_height_dimensions_fail_closed() -> None:
    producer, published = _producer(
        _pdf(second_height_text="3000")
    )
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None
