"""Authenticated viewport-scoped physical-wall authority tests.

These tests exercise only generic source/view ownership. No project names,
benchmark IDs, expected quantities, caller bboxes, or semantic text shortcuts
enter production wall authority.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE,
    PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS,
    PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_wall_topology_authority import build_source_wall_topology_authority
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)
from pb_wall_room_topology_stage_a import is_structural_candidate_segment


def _save(doc: fitz.Document, path: Path) -> None:
    doc.save(path)
    doc.close()


def test_authoritative_derived_requires_whole_sibling_non_overlap_while_resolved_survives(
    monkeypatch,
) -> None:
    import pb_physical_wall_candidate_authority as module

    resolved = SimpleNamespace(
        view_id="resolved",
        bounding_box=(0.0, 0.0, 100.0, 100.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
    )
    derived = SimpleNamespace(
        view_id="derived",
        bounding_box=(50.0, 0.0, 150.0, 100.0),
        status=ViewportSegmentationStatus.DERIVED.value,
    )

    monkeypatch.setattr(
        module,
        "_all_viewports",
        lambda page, *, page_number: [resolved, derived],
    )
    monkeypatch.setattr(
        module,
        "is_segment_page_viewports_product",
        lambda viewport: True,
    )
    monkeypatch.setattr(
        module,
        "is_authoritative_derived_viewport",
        lambda viewport: viewport is derived,
    )
    monkeypatch.setattr(
        module,
        "validate_non_overlapping_viewports",
        lambda rows: False,
    )

    authenticated = module._authenticated_viewports(object(), page_number=1)
    assert authenticated is not None
    rows, eligible = authenticated
    assert rows == (resolved, derived)
    assert eligible == (resolved,)


def _draw_plan(
    path: Path,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
    crossing: bool = False,
    dashed_annotation_lines: bool = False,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520.0 * scale + dx, height=400.0 * scale + dy)
    frame = fitz.Rect(
        (40.0 + dx) * scale,
        (30.0 + dy) * scale,
        (420.0 + dx) * scale,
        (330.0 + dy) * scale,
    )
    page.draw_rect(frame, color=(0, 0, 0), width=1)
    page.insert_text(
        ((80.0 + dx) * scale, (310.0 + dy) * scale),
        "GROUND FLOOR PLAN",
        fontsize=max(8.0, 11.0 * scale),
    )

    lines = [
        ((90.0, 80.0), (330.0, 80.0)),
        ((330.0, 80.0), (330.0, 230.0)),
        ((330.0, 230.0), (90.0, 230.0)),
        ((90.0, 230.0), (90.0, 80.0)),
        ((210.0, 80.0), (210.0, 230.0)),
    ]
    for first, second in lines:
        page.draw_line(
            ((first[0] + dx) * scale, (first[1] + dy) * scale),
            ((second[0] + dx) * scale, (second[1] + dy) * scale),
            color=(0, 0, 0),
            width=1,
        )

    if crossing:
        page.draw_line(
            ((350.0 + dx) * scale, (150.0 + dy) * scale),
            ((450.0 + dx) * scale, (150.0 + dy) * scale),
            color=(0, 0, 0),
            width=1,
        )

    if dashed_annotation_lines:
        page.draw_line(
            ((120.0 + dx) * scale, (260.0 + dy) * scale),
            ((260.0 + dx) * scale, (260.0 + dy) * scale),
            color=(0, 0, 0),
            dashes="[3 2] 0",
            width=0.5,
        )
        page.draw_line(
            ((350.0 + dx) * scale, (100.0 + dy) * scale),
            ((350.0 + dx) * scale, (220.0 + dy) * scale),
            color=(0, 0, 0),
            dashes="[2 2] 0",
            width=0.5,
        )
    _save(doc, path)


def _draw_two_adjacent_viewports(path: Path, *, partial_shared_line: bool) -> None:
    doc = fitz.open()
    page = doc.new_page(width=620, height=360)
    left = fitz.Rect(20, 20, 300, 320)
    right = fitz.Rect(300, 20, 600, 320)
    page.draw_rect(left, color=(0, 0, 0), width=1)
    page.draw_rect(right, color=(0, 0, 0), width=1)
    page.insert_text((70, 300), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((365, 300), "FIRST FLOOR PLAN", fontsize=11)

    for x0, x1 in ((60, 260), (340, 560)):
        for first, second in (
            ((x0, 70), (x1, 70)),
            ((x1, 70), (x1, 220)),
            ((x1, 220), (x0, 220)),
            ((x0, 220), (x0, 70)),
        ):
            page.draw_line(first, second, color=(0, 0, 0), width=1)
    if partial_shared_line:
        page.draw_line((300, 90), (300, 210), color=(0, 0, 0), width=1)
    _save(doc, path)


def _draw_competing_frames(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520, height=400)
    page.draw_rect(fitz.Rect(30, 30, 420, 330))
    page.draw_rect(fitz.Rect(55, 50, 395, 305))
    page.insert_text((90, 300), "GROUND FLOOR PLAN", fontsize=11)
    _save(doc, path)


def _draw_page_border_only(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(fitz.Rect(2, 2, 398, 298))
    page.insert_text((80, 160), "GROUND FLOOR PLAN", fontsize=11)
    _save(doc, path)


def _ingest(path: Path):
    source = SourceVisibilityProducer(
        producer_method="viewport-wall-authority-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=("1",),
    ).authority()
    return source, published, authority


def _viewport_id(path: Path, *, view_type: str = "floor_plan") -> str:
    doc = fitz.open(path)
    try:
        rows = [
            viewport
            for viewport in segment_page_viewports(doc[0], page_number=1)
            if viewport.view_type == view_type
            and viewport.status == ViewportSegmentationStatus.RESOLVED.value
        ]
    finally:
        doc.close()
    assert len(rows) == 1
    return rows[0].view_id


def _viewport_scope(path: Path):
    source, published, authority = _ingest(path)
    viewport_id = _viewport_id(path)
    selector = authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport_id,
    )
    assert selector is not None
    scope = authority.resolve_scope(selector)
    return source, published, authority, selector, scope


def test_authenticated_viewport_constructor_does_not_materialize_legacy_page_scope(
    tmp_path: Path,
) -> None:
    path = tmp_path / "viewport-only.pdf"
    _draw_plan(path)
    _source, published, authority = _ingest(path)

    result = authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=source_snapshot.snapshot.snapshot_id
            if (source_snapshot := _source.published_snapshot_for_revision(
                published.revision.revision_id
            ))
            else published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE,)


def test_valid_authenticated_viewport_materializes_complete_wall_scope(tmp_path: Path) -> None:
    path = tmp_path / "framed-two-room.pdf"
    _draw_plan(path)
    _source, _published, _authority, selector, scope = _viewport_scope(path)

    assert selector.decision_scope_id.startswith("wall-source:viewport:1:")
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_kind == "viewport"
    assert scope.viewport_id
    assert scope.viewport_view_type == "floor_plan"
    assert scope.viewport_producer_fingerprint
    assert scope.viewport_sibling_set_fingerprint
    assert scope.scope_complete is True
    assert scope.records


def test_caller_arbitrary_bbox_and_scope_complete_are_not_api_inputs(tmp_path: Path) -> None:
    path = tmp_path / "no-caller-geometry.pdf"
    _draw_plan(path)
    source = SourceVisibilityProducer(
        producer_method="viewport-wall-no-caller-geometry",
        producer_version="1.0",
    )
    source.ingest_native_pdf_bytes(
        document_id="test:no-caller-geometry",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=("1",),
            bbox=(0, 0, 10, 10),
        )
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=("1",),
            scope_complete=True,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("viewport_id", "forged-view"),
        ("revision_id", "stale-revision"),
        ("source_sha256", "0" * 64),
        ("snapshot_id", "wrong-snapshot"),
        ("page_id", "2"),
    ],
)
def test_forged_or_stale_viewport_address_cannot_resolve(
    tmp_path: Path, field: str, value: str
) -> None:
    path = tmp_path / f"stale-{field}.pdf"
    _draw_plan(path)
    _source, published, authority = _ingest(path)
    values = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": "1",
        "viewport_id": _viewport_id(path),
    }
    values[field] = value
    assert authority.selector_for_viewport(**values) is None


def test_segment_crossing_authenticated_viewport_makes_scope_incomplete(
    tmp_path: Path,
) -> None:
    path = tmp_path / "crossing.pdf"
    _draw_plan(path, crossing=True)
    _source, _published, _authority, _selector, scope = _viewport_scope(path)

    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY in scope.reason_codes
    assert scope.scope_boundary_observation_ids


def test_partial_structural_primitive_on_shared_boundary_is_ambiguous(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shared-boundary.pdf"
    _draw_two_adjacent_viewports(path, partial_shared_line=True)
    source, published, authority = _ingest(path)
    doc = fitz.open(path)
    try:
        viewports = [
            v for v in segment_page_viewports(doc[0], page_number=1)
            if v.status == ViewportSegmentationStatus.RESOLVED.value
        ]
    finally:
        doc.close()
    assert len(viewports) == 2
    scopes = []
    for viewport in viewports:
        selector = authority.selector_for_viewport(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=viewport.view_id,
        )
        assert selector is not None
        scopes.append(authority.resolve_scope(selector))

    assert any(
        PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS
        in scope.reason_codes
        for scope in scopes
    )
    assert any(scope.scope_complete is False for scope in scopes)


def test_overlapping_or_competing_viewport_does_not_mint_wall_scope(tmp_path: Path) -> None:
    path = tmp_path / "competing.pdf"
    _draw_competing_frames(path)
    _source, published, authority = _ingest(path)
    doc = fitz.open(path)
    try:
        viewports = segment_page_viewports(doc[0], page_number=1)
    finally:
        doc.close()
    assert viewports
    target = next(v for v in viewports if v.view_type == "floor_plan")
    assert target.status != ViewportSegmentationStatus.RESOLVED.value
    assert authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=target.view_id,
    ) is None


def test_page_border_is_not_promoted_to_viewport_authority(tmp_path: Path) -> None:
    path = tmp_path / "page-border.pdf"
    _draw_page_border_only(path)
    _source, published, authority = _ingest(path)
    doc = fitz.open(path)
    try:
        viewport = next(
            v for v in segment_page_viewports(doc[0], page_number=1)
            if v.view_type == "floor_plan"
        )
    finally:
        doc.close()
    assert viewport.status != ViewportSegmentationStatus.RESOLVED.value
    assert authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport.view_id,
    ) is None


def test_dashed_leader_and_dimension_geometry_do_not_change_wall_candidates(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base.pdf"
    annotated = tmp_path / "annotated.pdf"
    _draw_plan(base)
    _draw_plan(annotated, dashed_annotation_lines=True)
    *_unused, base_scope = _viewport_scope(base)
    *_unused2, annotated_scope = _viewport_scope(annotated)

    assert base_scope.scope_complete is True
    assert annotated_scope.scope_complete is True
    assert len(base_scope.records) == len(annotated_scope.records)


def test_untagged_solid_leader_or_grid_is_not_semantically_discarded() -> None:
    keep, reasons = is_structural_candidate_segment(
        {
            "dashes": "",
            "layer": "",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 100.0,
            "y2": 0.0,
        }
    )
    assert keep is True
    assert reasons == []


@pytest.mark.parametrize(
    "dx,dy,scale",
    [
        (35.0, 20.0, 1.0),
        (0.0, 0.0, 1.35),
    ],
)
def test_translated_or_scaled_equivalent_keeps_scope_and_role_structure(
    tmp_path: Path, dx: float, dy: float, scale: float
) -> None:
    base = tmp_path / "base-equiv.pdf"
    changed = tmp_path / f"equiv-{dx}-{dy}-{scale}.pdf"
    _draw_plan(base)
    _draw_plan(changed, dx=dx, dy=dy, scale=scale)

    def signature(path: Path):
        _source, published, authority, selector, scope = _viewport_scope(path)
        roles = WallRoleProducer.from_source_topology(
            physical_wall_candidate_authority=authority
        )
        resolved = []
        for record in scope.records:
            result = roles.publish(
                WallRoleSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id="1",
                    decision_scope_id=selector.decision_scope_id,
                    physical_wall_id=record.wall_candidate_id,
                )
            )
            if result.status is EvidenceResolutionStatus.CORROBORATED and result.record:
                resolved.append(result.record.role)
        return scope.scope_complete, len(scope.records), sorted(role.value for role in resolved)

    assert signature(base) == signature(changed)


def test_deterministic_replay_reuses_same_viewport_scope_id(tmp_path: Path) -> None:
    path = tmp_path / "replay.pdf"
    _draw_plan(path)
    _s1, _p1, _a1, selector1, scope1 = _viewport_scope(path)
    _s2, _p2, _a2, selector2, scope2 = _viewport_scope(path)

    assert selector1.decision_scope_id == selector2.decision_scope_id
    assert scope1.viewport_producer_fingerprint == scope2.viewport_producer_fingerprint
    assert scope1.viewport_sibling_set_fingerprint == scope2.viewport_sibling_set_fingerprint


def test_complete_viewport_scope_produces_topology_and_wall_roles(tmp_path: Path) -> None:
    path = tmp_path / "topology.pdf"
    _draw_plan(path)
    _source, published, authority, selector, scope = _viewport_scope(path)
    assert scope.scope_complete is True

    topology = build_source_wall_topology_authority(authority)
    role_producer = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=authority
    )
    roles = []
    for record in scope.records:
        result = role_producer.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=record.wall_candidate_id,
            )
        )
        if result.status is EvidenceResolutionStatus.CORROBORATED and result.record:
            roles.append(result.record.role)

    assert topology is not None
    assert WallRoleClassification.EXTERNAL in roles
    assert WallRoleClassification.INTERNAL in roles


def test_source_topology_retains_exact_viewport_decision_scope(tmp_path: Path) -> None:
    path = tmp_path / "scoped-topology.pdf"
    _draw_two_adjacent_viewports(path, partial_shared_line=False)
    _source, published, authority = _ingest(path)

    doc = fitz.open(path)
    try:
        viewports = [
            viewport
            for viewport in segment_page_viewports(doc[0], page_number=1)
            if viewport.status == ViewportSegmentationStatus.RESOLVED.value
        ]
    finally:
        doc.close()
    assert len(viewports) == 2

    selectors = []
    for viewport in viewports:
        selector = authority.selector_for_viewport(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=viewport.view_id,
        )
        assert selector is not None
        selectors.append(selector)

    topology = build_source_wall_topology_authority(authority)
    assert topology._records
    scoped_keys = tuple(topology._records)
    assert all(len(key) == 7 for key in scoped_keys)
    stored_scope_ids = {key[5] for key in scoped_keys}
    assert {selector.decision_scope_id for selector in selectors} <= stored_scope_ids
    for key, evidence in topology._records.items():
        assert evidence.decision_scope_id == key[5]


def test_incomplete_viewport_scope_still_refuses_source_topology(tmp_path: Path) -> None:
    path = tmp_path / "incomplete-topology.pdf"
    _draw_plan(path, crossing=True)
    _source, published, authority, selector, scope = _viewport_scope(path)
    assert scope.scope_complete is False

    role_producer = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=authority
    )
    results = [
        role_producer.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=record.wall_candidate_id,
            )
        )
        for record in scope.records
    ]
    assert results
    assert all(result.status is EvidenceResolutionStatus.ABSTAINED for result in results)


def test_manually_forged_viewport_scope_id_is_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "forged-scope-id.pdf"
    _draw_plan(path)
    _source, published, authority = _ingest(path)
    result = authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:viewport:1:forged:deadbeef",
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID,
    )


def test_wall_role_does_not_fall_back_from_viewport_scope_to_page_scope(tmp_path: Path) -> None:
    path = tmp_path / "no-page-fallback.pdf"
    _draw_plan(path)
    _source, published, authority, selector, scope = _viewport_scope(path)
    assert scope.records

    role_producer = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=authority
    )
    record = scope.records[0]
    result = role_producer.publish(
        WallRoleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id=selector.decision_scope_id + ":forged",
            physical_wall_id=record.wall_candidate_id,
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_valid_viewport_selector_cannot_be_retargeted_with_recomputed_public_fingerprint(
    tmp_path: Path,
) -> None:
    import pb_physical_wall_candidate_authority as module

    path = tmp_path / "selector-retarget.pdf"
    _draw_two_adjacent_viewports(path, partial_shared_line=False)
    _source, published, authority = _ingest(path)

    doc = fitz.open(path)
    try:
        viewports = [
            viewport
            for viewport in segment_page_viewports(doc[0], page_number=1)
            if viewport.status == ViewportSegmentationStatus.RESOLVED.value
        ]
    finally:
        doc.close()
    assert len(viewports) == 2

    selectors = []
    for viewport in viewports:
        selector = authority.selector_for_viewport(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=viewport.view_id,
        )
        assert selector is not None
        selectors.append(selector)

    original, target = selectors
    retargeted = replace(
        original,
        decision_scope_id=target.decision_scope_id,
    )
    recomputed = replace(
        retargeted,
        _viewport_selector_fingerprint=module._viewport_selector_payload_fingerprint(
            document_id=retargeted.document_id,
            revision_id=retargeted.revision_id,
            source_sha256=retargeted.source_sha256,
            snapshot_id=retargeted.snapshot_id,
            page_id=retargeted.page_id,
            decision_scope_id=retargeted.decision_scope_id,
        ),
    )
    result = authority.resolve_scope(recomputed)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        module.PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID,
    )


def test_viewport_selector_address_does_not_accept_caller_bbox(tmp_path: Path) -> None:
    path = tmp_path / "selector-no-bbox.pdf"
    _draw_plan(path)
    _source, published, authority = _ingest(path)
    with pytest.raises(TypeError):
        authority.selector_for_viewport(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=_viewport_id(path),
            bbox=(0.0, 0.0, 10.0, 10.0),
        )


def test_page_local_scoped_decode_can_materialize_authenticated_viewport(tmp_path: Path) -> None:
    path = tmp_path / "page-local-source.pdf"
    # Two-page source: only page 1 is decoded, proving that unrelated page 2
    # coverage is not required for a page-1 authenticated viewport scope.
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
    doc.new_page(width=300, height=200)
    _save(doc, path)

    source = SourceVisibilityProducer(
        producer_method="viewport-page-local-coverage-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="test:page-local-coverage",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
        page_ids=("1",),
    )
    assert published.coverage.state == "partial"
    assert published.coverage.decoded_pages == (1,)

    authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=("1",),
    ).authority()
    viewport_id = _viewport_id(path)
    selector = authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=source.published_snapshot_for_revision(
            published.revision.revision_id
        ).snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport_id,
    )
    assert selector is not None
    scope = authority.resolve_scope(selector)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert scope.records


@pytest.mark.parametrize(
    "layer,expected_reason",
    [
        ("A-GRID", None),
        ("A-DIMENSION", "dimension_layer_excluded"),
        ("A-ANNOTATION", "dimension_layer_excluded"),
        ("A-LEADER", "text_frame_layer_excluded"),
    ],
)
def test_source_metadata_controls_nonwall_exclusion_not_geometry(
    layer: str,
    expected_reason: str | None,
) -> None:
    keep, reasons = is_structural_candidate_segment(
        {
            "dashes": "",
            "layer": layer,
            "x1": 0.0,
            "y1": 0.0,
            "x2": 100.0,
            "y2": 0.0,
        }
    )
    if expected_reason is None:
        # "GRID" by name alone is not currently authoritative non-wall
        # metadata. The wall authority must keep it rather than invent a
        # semantic exclusion from its apparent purpose.
        assert keep is True
        assert reasons == []
    else:
        assert keep is False
        assert expected_reason in reasons
