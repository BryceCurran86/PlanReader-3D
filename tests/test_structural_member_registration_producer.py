from __future__ import annotations

import ast
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberDefinition,
    StructuralMemberSelector,
)
from pb_structural_member_registration_producer import (
    AuthenticatedStructuralMemberObservation,
    AuthenticatedStructuralMemberView,
    StructuralRegistrationAnchor,
    StructuralRegistrationAnchorKind,
    build_structural_member_registration_authority,
)


def selector(kind: str = "masonry_pier") -> StructuralMemberSelector:
    return StructuralMemberSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        decision_scope_id="building-a",
        member_kind=kind,
    )


def anchor(
    value: str,
    *,
    namespace: str = "grid-main",
    kind: StructuralRegistrationAnchorKind = (
        StructuralRegistrationAnchorKind.GRID_INTERSECTION
    ),
) -> StructuralRegistrationAnchor:
    return StructuralRegistrationAnchor(
        kind=kind,
        namespace_id=namespace,
        value_id=value,
        source_evidence_ids=(f"anchor:{namespace}:{value}",),
    )


def obs(
    name: str,
    view_name: str,
    *,
    page: str = "1",
    primitive: str | None = None,
    anchors: tuple[StructuralRegistrationAnchor, ...] = (),
    proposition: bool = True,
    geometry_signature: str = "square-300x300",
    kind: str = "masonry_pier",
) -> AuthenticatedStructuralMemberObservation:
    return AuthenticatedStructuralMemberObservation(
        member_kind=kind,
        page_id=page,
        view_id=view_name,
        view_type=view_name,
        source_evidence_ids=(f"source:{name}",),
        source_primitive_ids=((primitive or f"primitive:{name}"),),
        member_proposition_evidence_ids=(
            (f"member-proof:{name}",) if proposition else ()
        ),
        registration_anchors=anchors,
        geometry_signature=geometry_signature,
    )


def view(
    name: str,
    *,
    page: str = "1",
    complete: bool = True,
) -> AuthenticatedStructuralMemberView:
    return AuthenticatedStructuralMemberView(
        page_id=page,
        view_id=name,
        view_type=name,
        complete=complete,
        source_evidence_ids=(f"view-proof:{name}",),
        reason_codes=(() if complete else ("cropped_view",)),
    )


def build(observations, views, *, definitions=()):
    return build_structural_member_registration_authority(
        selector=selector(),
        source_observations=observations,
        source_views=views,
        definitions=definitions,
    )


def test_same_member_in_plan_and_elevation_collapses_to_one_member() -> None:
    result = build(
        (
            obs("plan-a1", "plan", anchors=(anchor("A|1"),)),
            obs(
                "elev-a1",
                "elevation",
                page="2",
                anchors=(anchor("A|1"),),
            ),
        ),
        (view("plan"), view("elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1
    assert len(result.resolution.members[0].observation_ids) == 2


def test_equal_counts_across_views_without_registration_abstain() -> None:
    result = build(
        (
            obs("p1", "plan"),
            obs("p2", "plan"),
            obs("e1", "elevation", page="2"),
            obs("e2", "elevation", page="2"),
        ),
        (view("plan"), view("elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_partial_registration_abstains() -> None:
    result = build(
        (
            obs("p1", "plan", anchors=(anchor("A|1"),)),
            obs("p2", "plan", anchors=(anchor("A|2"),)),
            obs(
                "e1",
                "elevation",
                page="2",
                anchors=(anchor("A|1"),),
            ),
            obs("e2", "elevation", page="2"),
        ),
        (view("plan"), view("elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_contradictory_same_and_distinct_registration_conflicts() -> None:
    shared_primitive = "source-path:77"
    result = build(
        (
            obs(
                "p",
                "plan",
                primitive=shared_primitive,
                anchors=(anchor("A|1"),),
            ),
            obs(
                "e",
                "elevation",
                page="2",
                primitive=shared_primitive,
                anchors=(anchor("A|2"),),
            ),
        ),
        (view("plan"), view("elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_MEMBER_RELATION_CONFLICT in result.resolution.reason_codes


def test_repeated_same_size_members_stay_distinct() -> None:
    result = build(
        (
            obs("a", "plan", geometry_signature="same-square"),
            obs("b", "plan", geometry_signature="same-square"),
            obs("c", "plan", geometry_signature="same-square"),
        ),
        (view("plan"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 3


def test_duplicate_primitive_representations_collapse_only_with_evidence() -> None:
    result = build(
        (
            obs("raw-a", "plan", primitive="cad:17"),
            obs("raw-b", "plan", primitive="cad:17"),
        ),
        (view("plan"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1


def test_cropped_view_abstains() -> None:
    result = build(
        (obs("a", "plan", anchors=(anchor("A|1"),)),),
        (view("plan", complete=False),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.resolution.reason_codes
    assert "cropped_view" in result.resolution.reason_codes


def test_unrelated_square_wall_jamb_geometry_cannot_mint_member() -> None:
    result = build(
        (
            obs(
                "square-wall-end",
                "plan",
                primitive="wall:path:4",
                proposition=False,
            ),
        ),
        (view("plan"),),
    )
    assert result.observations == ()
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None


def test_schedule_definition_cannot_create_quantity() -> None:
    definition = StructuralMemberDefinition(
        definition_id="def:pier",
        member_kind="masonry_pier",
        section_spec="masonry pier",
        source_evidence_ids=("schedule:def:pier",),
        page_id="3",
        view_id="schedule",
    )
    result = build(
        (),
        (view("schedule", page="3"),),
        definitions=(definition,),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None


def test_different_positive_grid_locations_publish_distinct_relation() -> None:
    result = build(
        (
            obs("a", "plan", anchors=(anchor("A|1"),)),
            obs("b", "plan", anchors=(anchor("A|2"),)),
        ),
        (view("plan"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 2
    assert {row.relation.value for row in result.relations} == {
        "distinct_physical_members"
    }


def test_production_dependency_closure_has_no_benchmark_or_gold_imports() -> None:
    path = Path("pb_structural_member_registration_producer.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(
        "benchmark" in name.lower() or "gold" in name.lower()
        for name in imported
    )


def test_replay_and_input_order_are_deterministic() -> None:
    observations = (
        obs("p1", "plan", anchors=(anchor("A|1"),)),
        obs("p2", "plan", anchors=(anchor("A|2"),)),
    )
    views = (view("plan"),)
    first = build(observations, views)
    second = build(tuple(reversed(observations)), tuple(reversed(views)))
    assert first.observations == second.observations
    assert first.relations == second.relations
    assert first.resolution == second.resolution


def test_source_lineage_changes_structural_observation_ids() -> None:
    source = (obs("p1", "plan", anchors=(anchor("A|1"),)),)
    views = (view("plan"),)
    first = build_structural_member_registration_authority(
        selector=selector(),
        source_observations=source,
        source_views=views,
    )
    changed = StructuralMemberSelector(
        document_id="doc",
        revision_id="rev-2",
        source_sha256="b" * 64,
        snapshot_id="snap-2",
        decision_scope_id="building-a",
        member_kind="masonry_pier",
    )
    second = build_structural_member_registration_authority(
        selector=changed,
        source_observations=source,
        source_views=views,
    )
    assert first.observations[0].observation_id != second.observations[0].observation_id
    assert first.resolution.members[0].physical_member_id != (
        second.resolution.members[0].physical_member_id
    )


def test_same_definition_can_bind_many_distinct_members_without_collapsing() -> None:
    definition = StructuralMemberDefinition(
        definition_id="def:pier",
        member_kind="masonry_pier",
        section_spec="masonry pier",
        source_evidence_ids=("schedule:def:pier",),
        page_id="3",
        view_id="schedule",
    )
    observations = tuple(
        AuthenticatedStructuralMemberObservation(
            member_kind="masonry_pier",
            page_id="1",
            view_id="plan",
            view_type="plan",
            source_evidence_ids=(f"source:{index}",),
            source_primitive_ids=(f"primitive:{index}",),
            member_proposition_evidence_ids=(f"member-proof:{index}",),
            definition_id="def:pier",
            geometry_signature="same-square",
        )
        for index in range(4)
    )
    result = build(observations, (view("plan"),), definitions=(definition,))
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 4
    assert all(
        member.definition_ids == ("def:pier",)
        for member in result.resolution.members
    )


def test_other_member_kind_cannot_enter_selector_scope() -> None:
    result = build(
        (
            obs("pier", "plan"),
            obs("column", "plan", kind="column"),
        ),
        (view("plan"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1
    assert len(result.observations) == 1
    assert result.observations[0].member_kind == "masonry_pier"


def test_registration_producer_is_not_live_wired_before_promotion_review() -> None:
    module_name = "pb_structural_member_registration_producer"
    live_files = (
        Path("pb_planreader_pdf_extractor.py"),
        Path("pb_planreader_jobhub_publish_contract.py"),
    )
    for path in live_files:
        assert module_name not in path.read_text(encoding="utf-8")


def test_complete_flag_without_source_evidence_fails_closed() -> None:
    observation = obs("a", "plan", anchors=(anchor("A|1"),))
    unproven_view = AuthenticatedStructuralMemberView(
        page_id="1",
        view_id="plan",
        view_type="plan",
        complete=True,
        source_evidence_ids=(),
    )
    result = build((observation,), (unproven_view,))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert "structural_view_completeness_unproven" in result.resolution.reason_codes


def test_conflicting_duplicate_view_scope_fails_closed() -> None:
    observation = obs("a", "plan", anchors=(anchor("A|1"),))
    first = view("plan")
    second = AuthenticatedStructuralMemberView(
        page_id="1",
        view_id="plan",
        view_type="plan",
        complete=False,
        source_evidence_ids=("view-proof:plan",),
        reason_codes=("cropped_view",),
    )
    result = build((observation,), (first, second))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert "structural_view_scope_conflict" in result.resolution.reason_codes
