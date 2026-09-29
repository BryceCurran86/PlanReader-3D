from __future__ import annotations

import ast
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_DEFINITION_ONLY,
    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberDefinition,
    StructuralMemberRelation,
    StructuralMemberSelector,
)
from pb_structural_member_registration_producer import (
    StructuralMemberCandidateEvidence,
    StructuralMemberRegistrationAnchor,
    StructuralMemberRegistrationProof,
    StructuralMemberRegistrationProducer,
    StructuralMemberSourceLineage,
    StructuralMemberSourceView,
)


def selector(kind: str = "masonry_pier") -> StructuralMemberSelector:
    return StructuralMemberSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        decision_scope_id="structure",
        member_kind=kind,
    )


def lineage(
    *,
    document_id: str = "doc",
    revision_id: str = "rev",
    source_sha256: str = "a" * 64,
    snapshot_id: str = "snap",
) -> StructuralMemberSourceLineage:
    return StructuralMemberSourceLineage(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
    )


def view(
    view_id: str,
    view_type: str,
    *,
    page: str,
    complete: bool = True,
) -> StructuralMemberSourceView:
    return StructuralMemberSourceView(
        lineage=lineage(),
        page_id=page,
        view_id=view_id,
        view_type=view_type,
        complete=complete,
        source_evidence_ids=(f"view-evidence:{page}:{view_id}",),
        reason_codes=() if complete else ("cropped_view",),
    )


def anchor(
    key: str,
    *,
    kind: str = "grid_intersection",
    system: str = "grid:A",
) -> StructuralMemberRegistrationAnchor:
    return StructuralMemberRegistrationAnchor(
        anchor_kind=kind,
        system_id=system,
        key=key,
        source_evidence_ids=(f"anchor:{kind}:{system}:{key}",),
    )


def candidate(
    cid: str,
    view_id: str,
    view_type: str,
    *,
    page: str,
    kind: str = "masonry_pier",
    primitive: str | None = None,
    role: str = "registered_structural_symbol",
    anchors=(),
    definition_id: str | None = None,
) -> StructuralMemberCandidateEvidence:
    return StructuralMemberCandidateEvidence(
        lineage=lineage(),
        candidate_id=cid,
        member_kind=kind,
        page_id=page,
        view_id=view_id,
        view_type=view_type,
        source_evidence_ids=(f"source:{cid}",),
        source_primitive_ids=(primitive or f"primitive:{cid}",),
        role_evidence_kind=role,
        registration_anchors=tuple(anchors),
        definition_id=definition_id,
    )


def publish(*, candidates=(), views=(), proofs=(), definitions=(), kind="masonry_pier"):
    return StructuralMemberRegistrationProducer(
        selector=selector(kind),
        candidates=candidates,
        views=views,
        relation_proofs=proofs,
        definitions=definitions,
    ).publish()


def test_same_member_in_plan_and_elevation_collapses_once() -> None:
    shared = anchor("A/1")
    result = publish(
        candidates=(
            candidate("plan-a1", "plan", "floor_plan", page="1", anchors=(shared,)),
            candidate("elev-a1", "elev", "elevation", page="2", anchors=(shared,)),
        ),
        views=(
            view("plan", "floor_plan", page="1"),
            view("elev", "elevation", page="2"),
        ),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1
    assert len(result.relations) == 1
    assert result.relations[0].relation is StructuralMemberRelation.SAME_PHYSICAL_MEMBER


def test_equal_counts_without_registration_abstain() -> None:
    result = publish(
        candidates=(
            candidate("p1", "plan", "floor_plan", page="1"),
            candidate("p2", "plan", "floor_plan", page="1"),
            candidate("e1", "elev", "elevation", page="2"),
            candidate("e2", "elev", "elevation", page="2"),
        ),
        views=(
            view("plan", "floor_plan", page="1"),
            view("elev", "elevation", page="2"),
        ),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_partial_registration_abstains() -> None:
    shared = anchor("A/1")
    result = publish(
        candidates=(
            candidate("p1", "plan", "floor_plan", page="1", anchors=(shared,)),
            candidate("p2", "plan", "floor_plan", page="1"),
            candidate("e1", "elev", "elevation", page="2", anchors=(shared,)),
            candidate("e2", "elev", "elevation", page="2"),
        ),
        views=(
            view("plan", "floor_plan", page="1"),
            view("elev", "elevation", page="2"),
        ),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_conflicting_same_and_distinct_registration_conflicts() -> None:
    shared = anchor("A/1")
    result = publish(
        candidates=(
            candidate("p1", "plan", "floor_plan", page="1", anchors=(shared,)),
            candidate("e1", "elev", "elevation", page="2", anchors=(shared,)),
        ),
        views=(
            view("plan", "floor_plan", page="1"),
            view("elev", "elevation", page="2"),
        ),
        proofs=(
            StructuralMemberRegistrationProof(
                lineage=lineage(),
                left_candidate_id="p1",
                right_candidate_id="e1",
                relation=StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS,
                proof_kind="distinct_registered_grid_positions",
                source_evidence_ids=("explicit-distinct-proof",),
            ),
        ),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_RELATION_CONFLICT in result.resolution.reason_codes


def test_repeated_same_size_members_remain_distinct_without_identity_evidence() -> None:
    result = publish(
        candidates=tuple(
            candidate(
                f"p{i}",
                "plan",
                "floor_plan",
                page="1",
                primitive=f"same-size-square:{i}",
            )
            for i in range(4)
        ),
        views=(view("plan", "floor_plan", page="1"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 4
    assert result.relations == ()


def test_duplicate_primitive_collapses_only_with_positive_same_proof() -> None:
    candidates = (
        candidate("raw-a", "plan", "floor_plan", page="1", primitive="cad:path:17"),
        candidate("raw-b", "plan", "floor_plan", page="1", primitive="cad:path:17"),
    )
    unresolved = publish(
        candidates=candidates,
        views=(view("plan", "floor_plan", page="1"),),
    )
    assert unresolved.resolution.quantity == 2

    resolved = publish(
        candidates=candidates,
        views=(view("plan", "floor_plan", page="1"),),
        proofs=(
            StructuralMemberRegistrationProof(
                lineage=lineage(),
                left_candidate_id="raw-a",
                right_candidate_id="raw-b",
                relation=StructuralMemberRelation.SAME_PHYSICAL_MEMBER,
                proof_kind="same_source_primitive",
                source_evidence_ids=("primitive-lineage-proof",),
            ),
        ),
    )
    assert resolved.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.resolution.quantity == 1


def test_cropped_view_abstains() -> None:
    result = publish(
        candidates=(
            candidate("p1", "plan", "floor_plan", page="1"),
        ),
        views=(view("plan", "floor_plan", page="1", complete=False),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.resolution.reason_codes
    assert "cropped_view" in result.resolution.reason_codes


def test_unrelated_square_geometry_cannot_mint_members() -> None:
    result = publish(
        candidates=(
            candidate(
                "wall-jamb-square",
                "plan",
                "floor_plan",
                page="1",
                role="geometry_only",
            ),
            candidate(
                "foundation-square",
                "plan",
                "floor_plan",
                page="1",
                role="geometry_only",
            ),
        ),
        views=(view("plan", "floor_plan", page="1"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert set(result.rejected_candidate_ids) == {
        "wall-jamb-square",
        "foundation-square",
    }


def test_schedule_definition_cannot_create_quantity() -> None:
    definition = StructuralMemberDefinition(
        definition_id="def:chs",
        member_kind="chs_pillar",
        section_spec="50 mm CHS",
        source_evidence_ids=("schedule-definition",),
        page_id="3",
        view_id="schedule",
    )
    result = publish(
        kind="chs_pillar",
        definitions=(definition,),
        views=(view("schedule", "schedule", page="3"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_DEFINITION_ONLY in result.resolution.reason_codes


def test_duplicate_anchor_ownership_in_one_view_does_not_auto_register() -> None:
    shared = anchor("A/1")
    result = publish(
        candidates=(
            candidate("p1", "plan", "floor_plan", page="1", anchors=(shared,)),
            candidate("p2", "plan", "floor_plan", page="1", anchors=(shared,)),
            candidate("e1", "elev", "elevation", page="2", anchors=(shared,)),
        ),
        views=(
            view("plan", "floor_plan", page="1"),
            view("elev", "elevation", page="2"),
        ),
    )
    assert result.relations == ()
    assert result.resolution.quantity is None


def test_observation_ids_are_deterministic_under_input_permutation() -> None:
    shared = anchor("A/1")
    candidates = (
        candidate("p1", "plan", "floor_plan", page="1", anchors=(shared,)),
        candidate("e1", "elev", "elevation", page="2", anchors=(shared,)),
    )
    views = (
        view("plan", "floor_plan", page="1"),
        view("elev", "elevation", page="2"),
    )
    first = publish(candidates=candidates, views=views)
    second = publish(candidates=tuple(reversed(candidates)), views=tuple(reversed(views)))
    assert {row.observation_id for row in first.observations} == {
        row.observation_id for row in second.observations
    }
    assert first.resolution.quantity == second.resolution.quantity == 1


def test_foreign_revision_snapshot_evidence_cannot_cross_selector_boundary() -> None:
    foreign = StructuralMemberSourceLineage(
        document_id="doc",
        revision_id="other-rev",
        source_sha256="b" * 64,
        snapshot_id="other-snapshot",
    )
    result = publish(
        candidates=(
            StructuralMemberCandidateEvidence(
                lineage=foreign,
                candidate_id="foreign",
                member_kind="masonry_pier",
                page_id="1",
                view_id="plan",
                view_type="floor_plan",
                source_evidence_ids=("foreign-evidence",),
                source_primitive_ids=("foreign-primitive",),
                role_evidence_kind="registered_structural_symbol",
            ),
        ),
        views=(
            StructuralMemberSourceView(
                lineage=foreign,
                page_id="1",
                view_id="plan",
                view_type="floor_plan",
                complete=True,
                source_evidence_ids=("foreign-view",),
            ),
        ),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert result.rejected_candidate_ids == ("foreign",)


def test_production_module_has_no_benchmark_or_gold_imports() -> None:
    path = Path(__file__).resolve().parents[1] / "pb_structural_member_registration_producer.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(
        "benchmark" in name.lower() or "gold" in name.lower()
        for name in imports
    )
