from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_wall_topology_authority import (
    _component_topology_records,
    _derive_component_local_records,
    _derive_scope_records,
)
from pb_wall_role_authority import WallRoleClassification


def _write_two_room_plan(path: Path) -> None:
    doc=fitz.open()
    page=doc.new_page(width=300,height=200)
    for first,second in (
        ((50.0,50.0),(250.0,50.0)),
        ((250.0,50.0),(250.0,150.0)),
        ((250.0,150.0),(50.0,150.0)),
        ((50.0,150.0),(50.0,50.0)),
        ((150.0,50.0),(150.0,150.0)),
    ):
        page.draw_line(fitz.Point(*first),fitz.Point(*second),color=(0,0,0),width=1)
    doc.save(path)
    doc.close()


def _complete_source_scope(path: Path):
    payload=path.read_bytes()
    source=SourceVisibilityProducer(
        producer_method="component-topology-integration-test",
        producer_version="1.0",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=payload,
        source_locator=str(path),
    )
    authority=PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    selector=PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    scope=authority.resolve_scope(selector)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    return scope


def _as_incomplete_viewport(scope):
    return replace(
        scope,
        scope_complete=False,
        scope_kind="viewport",
        viewport_id="view-test",
        viewport_bbox=(0.0,0.0,300.0,200.0),
        viewport_view_type="floor_plan",
        viewport_status="derived",
        viewport_boundary_source="title_partition",
        reason_codes=(
            PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
            PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
        ),
    )


class _FakeCompletenessAuthority:
    def __init__(self, *, member_wall_ids, corroborated=True):
        self._member_wall_ids=tuple(member_wall_ids)
        self._corroborated=corroborated

    def resolve(self, selector):
        if not self._corroborated:
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                record=None,
            )
        record=SimpleNamespace(
            record_id="component-proof-1",
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            member_wall_ids=self._member_wall_ids,
        )
        return SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED,
            record=record,
        )


def test_incomplete_scope_without_component_authority_stays_closed(
    tmp_path: Path,
) -> None:
    path=tmp_path/"two-room.pdf"
    _write_two_room_plan(path)
    scope=_as_incomplete_viewport(_complete_source_scope(path))
    assert _derive_scope_records(scope,None)=={}


def test_corroborated_component_reuses_exact_source_topology(
    tmp_path: Path,
) -> None:
    path=tmp_path/"two-room-local.pdf"
    _write_two_room_plan(path)
    scope=_as_incomplete_viewport(_complete_source_scope(path))
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in scope.records)
    )
    result=_derive_component_local_records(scope,authority)

    assert result
    resolved=[e for e in result.values() if not e.is_ambiguous]
    assert resolved
    assert any(
        e.enclosed_space_count==2 and not e.bounds_exterior
        for e in resolved
    )
    assert any(
        e.enclosed_space_count==1 and e.bounds_exterior
        for e in resolved
    )
    assert all(
        e.corroborating_evidence_ids==("component-proof-1",)
        for e in result.values()
    )


def test_abstained_component_authority_does_not_promote_topology(
    tmp_path: Path,
) -> None:
    path=tmp_path/"two-room-blocked.pdf"
    _write_two_room_plan(path)
    scope=_as_incomplete_viewport(_complete_source_scope(path))
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in scope.records),
        corroborated=False,
    )
    assert _derive_component_local_records(scope,authority)=={}


def test_positive_same_group_uses_same_canonical_representative_as_callout(
    tmp_path: Path,
) -> None:
    path=tmp_path/"two-room-equivalence.pdf"
    _write_two_room_plan(path)
    scope=_as_incomplete_viewport(_complete_source_scope(path))
    assert len(scope.records)>=2
    left,right=sorted(r.wall_candidate_id for r in scope.records)[:2]
    scope=replace(
        scope,
        equivalence=SimpleNamespace(
            equivalence_groups=((left,right),),
            abstained_wall_ids=(),
        ),
    )
    selected=_component_topology_records(
        scope,
        tuple(r.wall_candidate_id for r in scope.records),
    )
    selected_ids={r.wall_candidate_id for r in selected}
    assert min(left,right) in selected_ids
    assert max(left,right) not in selected_ids


def test_ungrouped_equivalence_abstention_does_not_delete_wall_candidate(
    tmp_path: Path,
) -> None:
    path=tmp_path/"two-room-abstained.pdf"
    _write_two_room_plan(path)
    scope=_as_incomplete_viewport(_complete_source_scope(path))
    blocked=scope.records[0].wall_candidate_id
    scope=replace(
        scope,
        equivalence=SimpleNamespace(
            equivalence_groups=(),
            abstained_wall_ids=(blocked,),
        ),
    )
    selected=_component_topology_records(
        scope,
        tuple(r.wall_candidate_id for r in scope.records),
    )
    assert {r.wall_candidate_id for r in selected} == {
        r.wall_candidate_id for r in scope.records
    }
