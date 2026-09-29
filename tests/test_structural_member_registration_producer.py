from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberDefinition,
    StructuralMemberSelector,
)
from pb_structural_member_registration_producer import (
    STRUCTURAL_REGISTRATION_ANCHOR_AMBIGUOUS,
    STRUCTURAL_REGISTRATION_ANCHOR_CONFLICT,
    STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED,
    STRUCTURAL_REGISTRATION_OBSERVATION_EQUIVOCATION,
    STRUCTURAL_REGISTRATION_SCHEMA_VERSION,
    STRUCTURAL_REGISTRATION_VIEW_COMPLETENESS_UNAUTHENTICATED,
    STRUCTURAL_REGISTRATION_VIEW_OWNERSHIP_CONFLICT,
    AuthenticatedStructuralMemberObservation,
    AuthenticatedStructuralMemberView,
    StructuralMemberRegistrationEvidenceProducer,
    StructuralRegistrationAnchor,
    StructuralRegistrationAnchorKind,
    _build_structural_member_registration_authority,
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


def producer(sel: StructuralMemberSelector | None = None):
    return StructuralMemberRegistrationEvidenceProducer.create_for_tests(
        selector=sel or selector()
    )


def anchor(
    value: str,
    *,
    namespace: str = "grid-main",
    kind: StructuralRegistrationAnchorKind = (
        StructuralRegistrationAnchorKind.GRID_INTERSECTION
    ),
    evidence: tuple[str, ...] | None = None,
) -> StructuralRegistrationAnchor:
    return StructuralRegistrationAnchor(
        kind=kind,
        namespace_id=namespace,
        value_id=value,
        source_evidence_ids=evidence or (f"anchor:{namespace}:{value}",),
    )


def obs(
    p,
    name: str,
    view_name: str,
    *,
    page: str = "1",
    primitive: str | None = None,
    anchors: tuple[StructuralRegistrationAnchor, ...] = (),
    proposition: bool = True,
    kind: str = "masonry_pier",
    source_evidence_ids: tuple[str, ...] | None = None,
    member_proposition_evidence_ids: tuple[str, ...] | None = None,
):
    return p.observation(
        member_kind=kind,
        page_id=page,
        view_id=view_name,
        view_type=view_name,
        source_evidence_ids=source_evidence_ids or (f"source:{name}",),
        source_primitive_ids=(primitive or f"primitive:{name}",),
        member_proposition_evidence_ids=(
            member_proposition_evidence_ids
            if member_proposition_evidence_ids is not None
            else ((f"member-proof:{name}",) if proposition else ())
        ),
        registration_anchors=anchors,
        geometry_signature="same-shape",
    )


def view(p, name: str, *, page: str = "1", complete: bool = True):
    return p.view(
        page_id=page,
        view_id=name,
        view_type=name,
        complete=complete,
        source_evidence_ids=(f"view-proof:{name}",),
        reason_codes=(() if complete else ("cropped_view",)),
    )


def build(observations, views, *, definitions=(), sel=None):
    return _build_structural_member_registration_authority(
        selector=sel or selector(),
        source_observations=observations,
        source_views=views,
        definitions=definitions,
        allow_synthetic_inputs=True,
    )


def test_positive_cross_view_registration_collapses_one_physical_member() -> None:
    p = producer()
    result = build(
        (
            obs(p, "plan-a1", "plan", anchors=(anchor("A|1"),)),
            obs(p, "elev-a1", "elevation", page="2", anchors=(anchor("A|1"),)),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1
    assert len(result.resolution.members[0].observation_ids) == 2


def test_equal_counts_without_registration_abstain() -> None:
    p = producer()
    result = build(
        (
            obs(p, "p1", "plan"),
            obs(p, "p2", "plan"),
            obs(p, "e1", "elevation", page="2"),
            obs(p, "e2", "elevation", page="2"),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_partial_registration_abstains() -> None:
    p = producer()
    result = build(
        (
            obs(p, "p1", "plan", anchors=(anchor("A|1"),)),
            obs(p, "p2", "plan", anchors=(anchor("A|2"),)),
            obs(p, "e1", "elevation", page="2", anchors=(anchor("A|1"),)),
            obs(p, "e2", "elevation", page="2"),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_same_view_anchor_values_never_establish_identity_or_distinctness() -> None:
    p = producer()
    result = build(
        (
            obs(p, "a", "plan", anchors=(anchor("A|1"),)),
            obs(p, "b", "plan", anchors=(anchor("A|2"),)),
        ),
        (view(p, "plan"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 2
    assert result.relations == ()


def test_duplicate_anchor_value_in_one_view_fails_closed() -> None:
    p = producer()
    result = build(
        (
            obs(p, "p1", "plan", anchors=(anchor("A|1"),)),
            obs(p, "p2", "plan", anchors=(anchor("A|1"),)),
            obs(p, "e1", "elevation", page="2", anchors=(anchor("A|1"),)),
            obs(p, "e2", "elevation", page="2", anchors=(anchor("A|2"),)),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_REGISTRATION_ANCHOR_AMBIGUOUS in result.resolution.reason_codes


def test_one_observation_claiming_two_values_in_same_namespace_conflicts() -> None:
    p = producer()
    result = build(
        (
            obs(p, "p", "plan", anchors=(anchor("A|1"), anchor("A|2"))),
            obs(p, "e", "elevation", page="2", anchors=(anchor("A|1"),)),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_REGISTRATION_ANCHOR_CONFLICT in result.resolution.reason_codes


def test_contradictory_cross_view_anchor_families_conflict() -> None:
    p = producer()
    mark = StructuralRegistrationAnchorKind.SOURCE_INSTANCE_MARK
    result = build(
        (
            obs(
                p,
                "plan",
                "plan",
                anchors=(
                    anchor("A|1"),
                    anchor("P1", namespace="marks", kind=mark),
                ),
            ),
            obs(
                p,
                "elev",
                "elevation",
                page="2",
                anchors=(
                    anchor("A|1"),
                    anchor("P2", namespace="marks", kind=mark),
                ),
            ),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_MEMBER_RELATION_CONFLICT in result.resolution.reason_codes


def test_duplicate_anchor_evidence_is_unioned_deterministically() -> None:
    p = producer()
    result = build(
        (
            obs(
                p,
                "p",
                "plan",
                anchors=(
                    anchor("A|1", evidence=("plan:a",)),
                    anchor("A|1", evidence=("plan:b",)),
                ),
            ),
            obs(
                p,
                "e",
                "elevation",
                page="2",
                anchors=(anchor("A|1", evidence=("elev:a",)),),
            ),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 1
    evidence = set(result.relations[0].source_evidence_ids)
    assert {"plan:a", "plan:b", "elev:a"} <= evidence


def test_shared_primitive_collapses_only_inside_same_exact_view() -> None:
    p = producer()
    same = build(
        (
            obs(p, "a", "plan", primitive="cad:17"),
            obs(p, "b", "plan", primitive="cad:17"),
        ),
        (view(p, "plan"),),
    )
    assert same.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert same.resolution.quantity == 1

    cross = build(
        (
            obs(p, "p", "plan", primitive="cad:17"),
            obs(p, "e", "elevation", page="2", primitive="cad:17"),
        ),
        (view(p, "plan"), view(p, "elevation", page="2")),
    )
    assert cross.relations == ()
    assert cross.resolution.status is EvidenceResolutionStatus.ABSTAINED


def test_page_view_ownership_mismatch_fails_closed() -> None:
    p = producer()
    result = build(
        (obs(p, "a", "plan", page="1"),),
        (view(p, "plan", page="2"),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_REGISTRATION_VIEW_OWNERSHIP_CONFLICT in result.resolution.reason_codes


def test_directly_constructed_inputs_are_not_authenticated() -> None:
    direct_obs = AuthenticatedStructuralMemberObservation(
        member_kind="masonry_pier",
        page_id="1",
        view_id="plan",
        view_type="plan",
        source_evidence_ids=("invented",),
        source_primitive_ids=("invented-primitive",),
        member_proposition_evidence_ids=("invented-proof",),
    )
    direct_view = AuthenticatedStructuralMemberView(
        page_id="1",
        view_id="plan",
        view_type="plan",
        complete=True,
        source_evidence_ids=("invented-view-proof",),
    )
    result = build((direct_obs,), (direct_view,))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED in result.resolution.reason_codes


def test_public_authority_builder_rejects_synthetic_factory_records() -> None:
    p = producer()
    result = build_structural_member_registration_authority(
        selector=selector(),
        source_observations=(obs(p, "a", "plan"),),
        source_views=(view(p, "plan", complete=True),),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED in result.resolution.reason_codes


def test_mutated_producer_record_is_not_authenticated() -> None:
    p = producer()
    original = obs(p, "a", "plan")
    mutated = replace(original, page_id="999")
    result = build((mutated,), (view(p, "plan"),))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED in result.resolution.reason_codes


def test_mutated_record_schema_versions_fail_closed() -> None:
    p = producer()
    observation = obs(p, "a", "plan")
    scope = view(p, "plan")
    for observations, views in (
        ((replace(observation, schema_version="1.0.0"),), (scope,)),
        ((observation,), (replace(scope, schema_version="1.0.0"),)),
    ):
        result = build(observations, views)
        assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
        assert STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED in result.resolution.reason_codes
    assert observation.schema_version == STRUCTURAL_REGISTRATION_SCHEMA_VERSION


def test_mutated_anchor_schema_version_fails_closed() -> None:
    p = producer()
    original = obs(p, "a", "plan", anchors=(anchor("A|1"),))
    mutated_anchor = replace(original.registration_anchors[0], schema_version="1.0.0")
    mutated_observation = replace(original, registration_anchors=(mutated_anchor,))
    result = build((mutated_observation,), (view(p, "plan"),))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED in result.resolution.reason_codes


def test_same_source_proposition_with_different_anchor_claims_conflicts() -> None:
    p = producer()
    common = dict(
        member_kind="masonry_pier",
        page_id="1",
        view_id="plan",
        view_type="plan",
        source_evidence_ids=("source:shared",),
        source_primitive_ids=("primitive:shared",),
        member_proposition_evidence_ids=("member-proof:shared",),
    )
    first = p.observation(**common, registration_anchors=(anchor("A|1"),))
    second = p.observation(**common, registration_anchors=(anchor("A|2"),))
    result = build((first, second), (view(p, "plan"),))
    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_REGISTRATION_OBSERVATION_EQUIVOCATION in result.resolution.reason_codes


def test_cropped_and_unproven_views_abstain() -> None:
    p = producer()
    result = build((obs(p, "a", "plan"),), (view(p, "plan", complete=False),))
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.resolution.reason_codes
    assert "cropped_view" in result.resolution.reason_codes


def test_raw_geometry_without_member_proposition_cannot_mint_member() -> None:
    p = producer()
    result = build(
        (obs(p, "wall-end", "plan", primitive="wall:4", proposition=False),),
        (view(p, "plan"),),
    )
    assert result.observations == ()
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None


def test_schedule_definition_cannot_create_quantity() -> None:
    p = producer()
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
        (view(p, "schedule", page="3"),),
        definitions=(definition,),
    )
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None


def test_replay_and_input_order_are_deterministic() -> None:
    p = producer()
    observations = (
        obs(p, "p1", "plan", anchors=(anchor("A|1"),)),
        obs(p, "p2", "plan", anchors=(anchor("A|2"),)),
    )
    views = (view(p, "plan"),)
    first = build(observations, views)
    second = build(tuple(reversed(observations)), tuple(reversed(views)))
    assert first.observations == second.observations
    assert first.relations == second.relations
    assert first.resolution == second.resolution


def _source_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((20, 20), (180, 20), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_production_source_factory_rejects_invented_evidence_and_complete_view() -> None:
    visibility = SourceVisibilityProducer(
        producer_method="structural-registration-test",
        producer_version="1",
    )
    published = visibility.ingest_native_pdf_bytes(
        document_id="source-doc",
        source_bytes=_source_pdf_bytes(),
        source_locator="memory://source.pdf",
    )
    sel = StructuralMemberSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="building-a",
        member_kind="masonry_pier",
    )
    p = StructuralMemberRegistrationEvidenceProducer.from_source_visibility(
        selector=sel,
        source_visibility_producer=visibility,
    )
    allowed = (
        published.visible_observation_ids[0]
        if published.visible_observation_ids
        else published.text_observation_ids[0]
    )
    p.observation(
        member_kind="masonry_pier",
        page_id="1",
        view_id="plan",
        view_type="plan",
        source_evidence_ids=(allowed,),
        source_primitive_ids=("page:1:primitive:1",),
        member_proposition_evidence_ids=(allowed,),
        registration_anchors=(),
    )
    with pytest.raises(ValueError, match=STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED):
        p.observation(
            member_kind="masonry_pier",
            page_id="1",
            view_id="plan",
            view_type="plan",
            source_evidence_ids=("invented",),
            source_primitive_ids=("page:1:primitive:1",),
            member_proposition_evidence_ids=("invented",),
        )
    with pytest.raises(
        ValueError,
        match=STRUCTURAL_REGISTRATION_VIEW_COMPLETENESS_UNAUTHENTICATED,
    ):
        p.view(
            page_id="1",
            view_id="plan",
            view_type="plan",
            complete=True,
            source_evidence_ids=(allowed,),
        )


def test_production_dependency_closure_has_no_benchmark_or_gold_imports() -> None:
    tree = ast.parse(
        Path("pb_structural_member_registration_producer.py").read_text(
            encoding="utf-8"
        )
    )
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


def test_registration_producer_is_not_live_wired_before_promotion_review() -> None:
    module_name = "pb_structural_member_registration_producer"
    for path in (
        Path("pb_planreader_pdf_extractor.py"),
        Path("pb_planreader_jobhub_publish_contract.py"),
    ):
        assert module_name not in path.read_text(encoding="utf-8")
