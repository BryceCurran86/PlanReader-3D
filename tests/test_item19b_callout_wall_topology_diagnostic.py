"""TEST-ONLY diagnostic: does finish-callout geometry alter physical wall topology?"""
from __future__ import annotations

from pathlib import Path
import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_role_authority import WallRoleProducer, WallRoleSelector


def _write_plan(path: Path, *, with_callout: bool) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300.0, height=200.0)
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
        ((150.0, 50.0), (150.0, 150.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    if with_callout:
        page.insert_text(
            fitz.Point(80.0, 100.0),
            "wall key to finish externally",
            fontsize=8,
            color=(0, 0, 0),
        )
        page.draw_line(
            fitz.Point(80.0, 100.0),
            fitz.Point(52.0, 100.0),
            color=(0, 0, 0),
            width=0.5,
        )
        page.draw_circle(
            fitz.Point(50.0, 100.0),
            2.0,
            color=(0, 0, 0),
            fill=(0, 0, 0),
            width=0.5,
        )
    doc.save(path)
    doc.close()


def _audit(path: Path) -> dict:
    source = SourceVisibilityProducer(
        producer_method="item19b-callout-topology-diagnostic",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source, page_ids=("1",)
    ).authority()
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    scope = wall_authority.resolve_scope(selector)
    roles = []
    if scope.status is EvidenceResolutionStatus.CORROBORATED:
        role_producer = WallRoleProducer.from_source_topology(
            physical_wall_candidate_authority=wall_authority
        )
        for record in scope.records:
            result = role_producer.publish(
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
            roles.append(
                {
                    "wall_id": record.wall_candidate_id,
                    "status": result.status.value,
                    "role": result.record.role.value if result.record else None,
                    "reason_codes": list(result.reason_codes),
                    "source_primitive_ids": list(record.physical_identity.source_primitive_ids),
                    "centerline_pts": list(record.wall_candidate.centerline_pts),
                }
            )
    return {
        "scope_status": scope.status.value,
        "scope_complete": scope.scope_complete,
        "scope_reason_codes": list(scope.reason_codes),
        "wall_count": len(scope.records),
        "roles": roles,
    }


def test_item19b_callout_geometry_topology_diagnostic(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.pdf"
    callout_path = tmp_path / "with-callout.pdf"
    _write_plan(baseline_path, with_callout=False)
    _write_plan(callout_path, with_callout=True)
    baseline = _audit(baseline_path)
    callout = _audit(callout_path)

    baseline_resolved_roles = sorted(
        row["role"] for row in baseline["roles"] if row["role"] is not None
    )
    callout_resolved_roles = sorted(
        row["role"] for row in callout["roles"] if row["role"] is not None
    )

    diagnostic = {
        "baseline": baseline,
        "with_callout": callout,
        "baseline_resolved_roles": baseline_resolved_roles,
        "callout_resolved_roles": callout_resolved_roles,
    }

    import json
    print("ITEM19B_CALLOUT_TOPOLOGY_DIAGNOSTIC=" + json.dumps(diagnostic, sort_keys=True))
    assert False, diagnostic
