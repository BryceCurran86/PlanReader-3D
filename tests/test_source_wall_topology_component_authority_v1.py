from __future__ import annotations

from types import SimpleNamespace

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_wall_topology_authority import (
    _derive_component_local_records,
    _derive_scope_records,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


def _record(
    wall_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
):
    raw_id=f"raw:{wall_id}"
    wall=WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:viewport:1:view",
        representation="single_line",
        centerline_pts=(start,end),
        face_a_segment_ids=(raw_id,),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}:a",f"{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT,JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        confidence=0.5,
    )
    identity=PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"identity:{wall_id}",
        path_fingerprint=(start,end),
        source_primitive_ids=(raw_id,),
        edge_ids=(raw_id,),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _records():
    return (
        _record("top",(50,50),(250,50)),
        _record("right",(250,50),(250,250)),
        _record("bottom",(250,250),(50,250)),
        _record("left",(50,250),(50,50)),
        _record("divider",(150,50),(150,250)),
    )


def _scope(records=None, *, equivalence=None):
    rows=tuple(records or _records())
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=False,
        records=rows,
        source_observation_ids=(),
        document_id="doc",
        revision_id="rev",
        source_sha256="a"*64,
        snapshot_id="snap",
        page_id="1",
        decision_scope_id="wall-source:viewport:1:view:test",
        reason_codes=(
            "physical_wall_candidate_scope_resolved",
            "physical_wall_candidate_scope_cropped_at_viewport_boundary",
        ),
        equivalence=equivalence,
        proposition="physical_wall_candidate_scope_resolved",
        scope_kind="viewport",
        viewport_id="view",
        viewport_bbox=(0,0,500,500),
        viewport_view_type="floor_plan",
        viewport_status="derived",
        viewport_boundary_source="title_partition",
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


def test_incomplete_scope_without_component_authority_stays_closed() -> None:
    assert _derive_scope_records(_scope(), None) == {}


def test_corroborated_component_can_publish_local_two_room_topology() -> None:
    scope=_scope()
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in scope.records)
    )
    result=_derive_component_local_records(scope,authority)

    assert len(result)==5
    divider=next(v for k,v in result.items() if k[-1]=="divider")
    assert divider.is_ambiguous is False
    assert divider.enclosed_space_count==2
    assert divider.bounds_exterior is False
    assert divider.corroborating_evidence_ids==("component-proof-1",)

    one_sided=[
        v for v in result.values()
        if v.enclosed_space_count==1 and not v.is_ambiguous
    ]
    assert one_sided
    assert all(v.bounds_exterior for v in one_sided)
    assert all(
        v.corroborating_evidence_ids==("component-proof-1",)
        for v in result.values()
    )


def test_abstained_component_authority_does_not_promote_topology() -> None:
    scope=_scope()
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in scope.records),
        corroborated=False,
    )
    assert _derive_component_local_records(scope,authority)=={}


def test_positive_same_group_collapses_to_same_representative_as_callout() -> None:
    rows=list(_records())
    rows.append(_record("top-z",(50,50),(250,50)))
    equivalence=SimpleNamespace(
        equivalence_groups=(("top","top-z"),),
        abstained_wall_ids=(),
    )
    scope=_scope(tuple(rows),equivalence=equivalence)
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in rows)
    )
    result=_derive_component_local_records(scope,authority)

    ids={key[-1] for key in result}
    assert "top" in ids
    assert "top-z" not in ids
    assert len(result)==5


def test_ungrouped_abstained_identity_keeps_component_fail_closed() -> None:
    scope=_scope(equivalence=SimpleNamespace(
        equivalence_groups=(),
        abstained_wall_ids=("divider",),
    ))
    authority=_FakeCompletenessAuthority(
        member_wall_ids=tuple(r.wall_candidate_id for r in scope.records)
    )
    assert _derive_component_local_records(scope,authority)=={}
