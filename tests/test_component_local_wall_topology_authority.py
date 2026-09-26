from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_component_local_wall_topology_authority import (
    _publication_groups,
    build_component_local_source_wall_topology_authority,
    component_local_topology_proofs,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)


def _write_two_room_plan(
    path: Path,
    *,
    crossing: str | None = None,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520, height=400)
    frame = fitz.Rect(40, 30, 420, 330)
    page.draw_rect(frame, color=(0, 0, 0), width=1)
    page.insert_text((80, 310), "GROUND FLOOR PLAN", fontsize=11)

    for first, second in (
        ((90, 80), (330, 80)),
        ((330, 80), (330, 230)),
        ((330, 230), (90, 230)),
        ((90, 230), (90, 80)),
        ((210, 80), (210, 230)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)

    if crossing == "far":
        # Exact structural primitive crosses the authenticated viewport but is
        # disconnected from the building component.
        page.draw_line((350, 260), (450, 260), color=(0, 0, 0), width=1)
    elif crossing == "touch":
        # Exact omitted primitive crosses the viewport and intersects the
        # building component at the internal wall.
        page.draw_line((210, 150), (450, 150), color=(0, 0, 0), width=1)

    doc.save(path)
    doc.close()


def _authority(path: Path):
    source = SourceVisibilityProducer(
        producer_method="component-local-topology-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
        page_ids=("1",),
    )
    walls = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=("1",),
    ).authority()

    doc = fitz.open(path)
    try:
        viewport = next(
            item
            for item in segment_page_viewports(doc[0], page_number=1)
            if item.view_type == "floor_plan"
            and item.status == ViewportSegmentationStatus.RESOLVED.value
        )
    finally:
        doc.close()

    selector = walls.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport.view_id,
    )
    assert selector is not None
    scope = walls.resolve_scope(selector)
    return source, published, walls, selector, scope


def _role_results(
    published,
    walls,
    selector,
    topology,
    scope,
    *,
    publication_only: bool = False,
):
    producer = WallRoleProducer.from_authorities(
        physical_wall_candidate_authority=walls,
        wall_topology_authority=topology,
    )
    wall_ids = tuple(record.wall_candidate_id for record in scope.records)
    if publication_only and scope.equivalence is not None:
        wall_ids = tuple(scope.equivalence.representative_wall_ids)
    results = []
    for wall_id in wall_ids:
        result = producer.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=wall_id,
            )
        )
        results.append((wall_id, result))
    return results


def test_unrelated_viewport_crop_does_not_poison_closed_component(tmp_path: Path) -> None:
    path = tmp_path / "unrelated-crop.pdf"
    _write_two_room_plan(path, crossing="far")
    source, published, walls, selector, scope = _authority(path)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is False

    groups = _publication_groups(scope)
    assert groups, {
        "representatives": tuple(
            scope.equivalence.representative_wall_ids
            if scope.equivalence is not None else ()
        ),
        "ambiguous": tuple(
            scope.equivalence.ambiguous_wall_ids
            if scope.equivalence is not None else ()
        ),
        "record_count": len(scope.records),
    }

    topology = build_component_local_source_wall_topology_authority(
        source_visibility_producer=source,
        physical_wall_candidate_authority=walls,
    )
    results = _role_results(
        published, walls, selector, topology, scope, publication_only=True
    )
    roles = {
        result.record.role
        for _wall_id, result in results
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    }
    assert WallRoleClassification.INTERNAL in roles
    assert WallRoleClassification.EXTERNAL in roles

    proofs = component_local_topology_proofs(topology)
    assert proofs
    assert all(proof.scope_was_globally_complete is False for proof in proofs)
    assert any(proof.checked_withheld_observation_ids for proof in proofs)


def test_boundary_primitive_touching_component_keeps_topology_fail_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "touching-crop.pdf"
    _write_two_room_plan(path, crossing="touch")
    source, published, walls, selector, scope = _authority(path)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is False

    topology = build_component_local_source_wall_topology_authority(
        source_visibility_producer=source,
        physical_wall_candidate_authority=walls,
    )
    results = _role_results(published, walls, selector, topology, scope)
    assert all(
        result.status is not EvidenceResolutionStatus.CORROBORATED
        for _wall_id, result in results
    )


def test_complete_scope_preserves_existing_source_topology_roles(tmp_path: Path) -> None:
    path = tmp_path / "complete.pdf"
    _write_two_room_plan(path)
    source, published, walls, selector, scope = _authority(path)
    assert scope.scope_complete is True

    topology = build_component_local_source_wall_topology_authority(
        source_visibility_producer=source,
        physical_wall_candidate_authority=walls,
    )
    results = _role_results(
        published, walls, selector, topology, scope, publication_only=False
    )
    roles = {
        result.record.role
        for _wall_id, result in results
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    }
    assert WallRoleClassification.INTERNAL in roles
    assert WallRoleClassification.EXTERNAL in roles
    assert component_local_topology_proofs(topology) == ()


def test_publication_groups_use_one_equivalence_representative_only() -> None:
    rec_a = SimpleNamespace(wall_candidate_id="wall-a")
    rec_b = SimpleNamespace(wall_candidate_id="wall-b")
    rec_c = SimpleNamespace(wall_candidate_id="wall-c")
    scope = SimpleNamespace(
        records=(rec_a, rec_b, rec_c),
        equivalence=SimpleNamespace(
            representative_wall_ids=("wall-a", "wall-c"),
            equivalence_groups=(("wall-a", "wall-b"),),
        ),
    )
    assert _publication_groups(scope) == {
        "wall-a": ("wall-a", "wall-b"),
        "wall-c": ("wall-c",),
    }


def test_equivalence_group_without_unique_representative_is_not_promoted() -> None:
    rec_a = SimpleNamespace(wall_candidate_id="wall-a")
    rec_b = SimpleNamespace(wall_candidate_id="wall-b")
    scope = SimpleNamespace(
        records=(rec_a, rec_b),
        equivalence=SimpleNamespace(
            representative_wall_ids=(),
            equivalence_groups=(("wall-a", "wall-b"),),
        ),
    )
    assert _publication_groups(scope) == {}
