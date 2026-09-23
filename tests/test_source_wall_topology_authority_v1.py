"""End-to-end source-derived wall-role topology authority tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_role_authority import (
    WALL_ROLE_AMBIGUOUS,
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)


def _write_plan(path: Path, *, with_partition: bool) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    lines = [
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
    ]
    if with_partition:
        lines.append(((150.0, 50.0), (150.0, 150.0)))
    for first, second in lines:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    doc.save(path)
    doc.close()


def _source_wall_scope(path: Path):
    payload = path.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="source-wall-role-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=payload,
        source_locator=str(path),
    )
    producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    )
    authority = producer.authority()
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    scope = authority.resolve_scope(selector)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert scope.records
    return published, authority, scope


def _role_results(published, wall_authority, scope):
    producer = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=wall_authority
    )
    return [
        producer.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id="wall-source:page-1",
                physical_wall_id=record.wall_candidate_id,
            )
        )
        for record in scope.records
    ]


def test_two_room_source_topology_resolves_external_and_internal_roles(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-plan.pdf"
    _write_plan(path, with_partition=True)
    published, wall_authority, scope = _source_wall_scope(path)

    results = _role_results(published, wall_authority, scope)
    resolved = [
        result
        for result in results
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    ]

    assert resolved
    roles = [result.record.role for result in resolved if result.record is not None]
    assert WallRoleClassification.EXTERNAL in roles
    assert WallRoleClassification.INTERNAL in roles
    assert all(
        result.record is not None
        and result.record.physical_wall_id
        and result.record.corroborating_evidence_ids
        for result in resolved
    )


def test_single_closed_loop_cannot_mint_exterior_wall_role(tmp_path: Path) -> None:
    path = tmp_path / "single-loop.pdf"
    _write_plan(path, with_partition=False)
    published, wall_authority, scope = _source_wall_scope(path)

    results = _role_results(published, wall_authority, scope)

    assert results
    assert all(result.status is EvidenceResolutionStatus.ABSTAINED for result in results)
    assert all(result.record is None for result in results)
    assert all(WALL_ROLE_AMBIGUOUS in result.reason_codes for result in results)
