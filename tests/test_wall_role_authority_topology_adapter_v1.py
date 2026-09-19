"""End-to-end test for WallTopologyProducer.from_physical_wall_candidate_authority
(Item 26 Phase 2: W2-W6 -> WallTopologyEvidence -> WallRoleAuthority).

Builds a real two-room rectangular building (four perimeter walls + one
internal partition, all real drawn vector geometry -- no benchmark project
involved) and proves the full chain end-to-end: perimeter walls resolve
EXTERNAL, the partition resolves INTERNAL, and nothing is guessed from
candidate metadata/caller labels.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
    WallTopologyProducer,
)

_PAGE_W, _PAGE_H = 400.0, 400.0


def _ingest(pdf_bytes: bytes, *, document_id: str):
    source = SourceVisibilityProducer(
        producer_method="wall-role-topology-adapter-v1", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=pdf_bytes,
        source_locator=f"memory://{document_id}.pdf",
    )
    return source, published


def _two_room_rectangle_pdf() -> bytes:
    """Two rooms side by side: outer perimeter (4 separate lines, so PyMuPDF
    never serializes it as a native 'rects' primitive) plus one internal
    partition wall splitting it into a left and right room."""
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
    x0, xm, x1 = 40.0, 120.0, 200.0
    y0, y1 = 40.0, 160.0
    for start, end in (
        ((x0, y0), (x1, y0)),  # top
        ((x1, y0), (x1, y1)),  # right
        ((x1, y1), (x0, y1)),  # bottom
        ((x0, y1), (x0, y0)),  # left
    ):
        page.draw_line(fitz.Point(*start), fitz.Point(*end))
    page.draw_line(fitz.Point(xm, y0), fitz.Point(xm, y1))  # internal partition
    data = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return data


def test_perimeter_external_and_partition_internal_resolve_end_to_end() -> None:
    source, published = _ingest(_two_room_rectangle_pdf(), document_id="two-room-rect")

    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(source)
    wall_authority = wall_producer.authority()

    cand_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    cand_result = wall_authority.resolve_scope(cand_selector)
    assert cand_result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(cand_result.records) >= 5  # 4 perimeter + 1 partition (post-T-junction split)

    topology_producer = WallTopologyProducer.from_physical_wall_candidate_authority(
        source_visibility_producer=source,
        physical_wall_candidate_authority=wall_authority,
    )
    topology_authority = topology_producer.authority()

    role_producer = WallRoleProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        wall_topology_authority=topology_authority,
    )

    resolved_roles: dict[str, WallRoleClassification] = {}
    for rec in cand_result.records:
        role_sel = WallRoleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
            physical_wall_id=rec.wall_candidate_id,
        )
        res = role_producer.publish(role_sel)
        if res.status is EvidenceResolutionStatus.CORROBORATED:
            resolved_roles[rec.wall_candidate_id] = res.record.role

    role_authority = role_producer.authority()
    for wall_id, role in resolved_roles.items():
        role_sel = WallRoleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
            physical_wall_id=wall_id,
        )
        looked_up = role_authority.resolve(role_sel)
        assert looked_up.status is EvidenceResolutionStatus.CORROBORATED
        assert looked_up.record.role == role

    roles_found = set(resolved_roles.values())
    assert WallRoleClassification.EXTERNAL in roles_found
    assert WallRoleClassification.INTERNAL in roles_found
    external_count = sum(1 for r in resolved_roles.values() if r == WallRoleClassification.EXTERNAL)
    internal_count = sum(1 for r in resolved_roles.values() if r == WallRoleClassification.INTERNAL)
    assert external_count >= 1
    assert internal_count >= 1


def test_no_topology_authority_still_abstains() -> None:
    """Without wiring the topology adapter in, WallRoleProducer must still
    abstain -- proving the positive result above genuinely depends on the
    adapter, not on some other latent path."""
    source, published = _ingest(_two_room_rectangle_pdf(), document_id="two-room-rect-2")
    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(source)
    wall_authority = wall_producer.authority()
    cand_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    cand_result = wall_authority.resolve_scope(cand_selector)
    role_producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=wall_authority)
    for rec in cand_result.records:
        role_sel = WallRoleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
            physical_wall_id=rec.wall_candidate_id,
        )
        res = role_producer.publish(role_sel)
        assert res.status is EvidenceResolutionStatus.ABSTAINED
