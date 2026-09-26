from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_component_local_wall_topology_authority import (
    _equivalence_owner_map,
    build_component_local_source_wall_topology_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)


def _write_viewport_plan(
    path: Path,
    *,
    crossing: str = "none",
    title: str = "GROUND FLOOR PLAN",
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520, height=400)
    frame = fitz.Rect(40, 30, 420, 330)
    page.draw_rect(frame, color=(0, 0, 0), width=1)
    page.insert_text((80, 310), title, fontsize=11)

    # Closed two-room wall component, fully inside the authenticated viewport.
    for first, second in (
        ((90, 80), (330, 80)),
        ((330, 80), (330, 230)),
        ((330, 230), (90, 230)),
        ((90, 230), (90, 80)),
        ((210, 80), (210, 230)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)

    if crossing == "unrelated":
        # Crosses the viewport boundary but never touches the room component.
        page.draw_line((350, 150), (450, 150), color=(0, 0, 0), width=1)
    elif crossing == "touching":
        # Same ownership ambiguity, but it touches the internal partition.
        page.draw_line((210, 150), (450, 150), color=(0, 0, 0), width=1)

    doc.save(path)
    doc.close()


def _setup(path: Path):
    source = SourceVisibilityProducer(
        producer_method="component-local-topology-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
        page_ids=("1",),
    )
    wall_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=("1",),
    )
    authority = wall_producer.authority()

    doc = fitz.open(path)
    try:
        candidates = [
            viewport
            for viewport in segment_page_viewports(doc[0], page_number=1)
            if viewport.status == ViewportSegmentationStatus.RESOLVED.value
            and viewport.bounding_box is not None
        ]
    finally:
        doc.close()
    assert candidates
    viewport = candidates[0]
    selector = authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=source.published_snapshot_for_revision(
            published.revision.revision_id
        ).snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport.view_id,
    )
    assert selector is not None
    scope = authority.resolve_scope(selector)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    return source, published, authority, selector, scope


def _roles(source, published, authority, selector, scope):
    topology = build_component_local_source_wall_topology_authority(
        source_visibility_producer=source,
        physical_wall_candidate_authority=authority,
    )
    producer = WallRoleProducer.from_authorities(
        physical_wall_candidate_authority=authority,
        wall_topology_authority=topology,
    )
    results = []
    for record in scope.records:
        results.append(
            producer.publish(
                WallRoleSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=scope.snapshot_id,
                    page_id="1",
                    decision_scope_id=selector.decision_scope_id,
                    physical_wall_id=record.wall_candidate_id,
                )
            )
        )
    return topology, results


def test_unrelated_viewport_crop_does_not_poison_isolated_two_room_component(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unrelated-crop.pdf"
    _write_viewport_plan(path, crossing="unrelated")
    source, published, authority, selector, scope = _setup(path)

    assert scope.scope_complete is False
    assert scope.scope_boundary_observation_ids

    # Legacy source topology correctly refuses the globally incomplete scope.
    legacy = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=authority
    )
    legacy_results = [
        legacy.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id="1",
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=record.wall_candidate_id,
            )
        )
        for record in scope.records
    ]
    assert all(
        result.status is EvidenceResolutionStatus.ABSTAINED
        for result in legacy_results
    )

    topology, results = _roles(
        source, published, authority, selector, scope
    )
    print("DEBUG_SCOPE", {
        "complete": scope.scope_complete,
        "records": [r.wall_candidate_id for r in scope.records],
        "equivalence": None if scope.equivalence is None else {
            "groups": scope.equivalence.equivalence_groups,
            "ambiguous": scope.equivalence.ambiguous_wall_ids,
        },
        "topology_records": list(topology._records),
        "proofs": list(getattr(topology, "_component_local_topology_proofs")),
        "results": [
            (result.status.value, result.reason_codes, None if result.record is None else result.record.role.value)
            for result in results
        ],
    })
    resolved = [
        result.record
        for result in results
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    ]
    roles = {record.role for record in resolved}
    assert WallRoleClassification.EXTERNAL in roles
    assert WallRoleClassification.INTERNAL in roles
    proofs = getattr(topology, "_component_local_topology_proofs")
    assert proofs
    assert any(
        not proof.scope_was_globally_complete
        and proof.withheld_observation_ids_checked
        for proof in proofs.values()
    )


def test_withheld_structural_primitive_touching_component_blocks_local_topology(
    tmp_path: Path,
) -> None:
    path = tmp_path / "touching-crop.pdf"
    _write_viewport_plan(path, crossing="touching")
    source, published, authority, selector, scope = _setup(path)
    assert scope.scope_complete is False

    topology, results = _roles(
        source, published, authority, selector, scope
    )
    assert all(
        result.status is EvidenceResolutionStatus.ABSTAINED
        for result in results
    )
    assert getattr(topology, "_component_local_topology_proofs") == {}


def test_complete_scope_keeps_external_internal_role_structure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "complete.pdf"
    _write_viewport_plan(path, crossing="none")
    source, published, authority, selector, scope = _setup(path)
    assert scope.scope_complete is True

    _topology, results = _roles(
        source, published, authority, selector, scope
    )
    print("DEBUG_COMPLETE", {
        "records": [r.wall_candidate_id for r in scope.records],
        "equivalence": None if scope.equivalence is None else {
            "groups": scope.equivalence.equivalence_groups,
            "ambiguous": scope.equivalence.ambiguous_wall_ids,
        },
        "topology_records": list(_topology._records),
        "proofs": list(getattr(_topology, "_component_local_topology_proofs")),
        "results": [
            (result.status.value, result.reason_codes, None if result.record is None else result.record.role.value)
            for result in results
        ],
    })
    resolved = [
        result.record
        for result in results
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    ]
    assert {record.role for record in resolved} >= {
        WallRoleClassification.EXTERNAL,
        WallRoleClassification.INTERNAL,
    }


def test_non_floor_plan_viewport_cannot_mint_room_topology(
    tmp_path: Path,
) -> None:
    path = tmp_path / "elevation.pdf"
    _write_viewport_plan(path, crossing="none", title="ELEVATION E-01")
    source, published, authority, selector, scope = _setup(path)
    assert scope.viewport_view_type != "floor_plan"

    topology, results = _roles(
        source, published, authority, selector, scope
    )
    assert all(
        result.status is EvidenceResolutionStatus.ABSTAINED
        for result in results
    )
    assert getattr(topology, "_component_local_topology_proofs") == {}


def test_positive_equivalence_groups_map_to_one_canonical_physical_owner() -> None:
    scope = SimpleNamespace(
        records=(
            SimpleNamespace(wall_candidate_id="face-a"),
            SimpleNamespace(wall_candidate_id="face-b"),
            SimpleNamespace(wall_candidate_id="other"),
        ),
        equivalence=SimpleNamespace(
            equivalence_groups=(("face-b", "face-a"),),
            ambiguous_wall_ids=(),
        ),
    )
    owner, ambiguous, groups = _equivalence_owner_map(scope)
    assert owner["face-a"] == owner["face-b"] == "face-a"
    assert owner["other"] == "other"
    assert ambiguous == set()
    assert groups == (("face-a", "face-b"),)


def test_ambiguous_equivalence_ids_remain_explicitly_ambiguous() -> None:
    scope = SimpleNamespace(
        records=(
            SimpleNamespace(wall_candidate_id="face-a"),
            SimpleNamespace(wall_candidate_id="face-b"),
        ),
        equivalence=SimpleNamespace(
            equivalence_groups=(),
            ambiguous_wall_ids=("face-a", "face-b"),
        ),
    )
    owner, ambiguous, groups = _equivalence_owner_map(scope)
    assert owner == {"face-a": "face-a", "face-b": "face-b"}
    assert ambiguous == {"face-a", "face-b"}
    assert groups == ()
