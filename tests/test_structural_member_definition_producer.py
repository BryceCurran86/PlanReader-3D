"""Structural specifications remain type evidence, never count authority."""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)
from pb_structural_member_definition_producer import (
    AuthenticatedStructuralDefinitionLink,
    SourceStructuralTextBlock,
    bind_structural_member_definitions,
    parse_structural_member_definitions,
)


def selector(**changes) -> StructuralMemberSelector:
    return replace(StructuralMemberSelector(
        document_id="source-document", revision_id="revision-1",
        source_sha256="a" * 64, snapshot_id="snapshot-1",
        decision_scope_id="building-a:verandah", member_kind="structural_support",
    ), **changes)


def source_blocks(count: int = 4, scope: str = "building-a"):
    return (
        SourceStructuralTextBlock(
            page_id="47", view_id="boq-page-47", block_id="11", reading_order=11,
            bbox=(102.4, 520.5, 603.0, 565.6),
            text="- Circular hollow sections painted and fixed with concrete",
            scope_id=scope,
        ),
        SourceStructuralTextBlock(
            page_id="47", view_id="boq-page-47", block_id="12", reading_order=12,
            bbox=(76.0, 580.9, 617.1, 595.5),
            text=f"D 50mm dia x 1.5mm thick to pillars {count} NO 2,200 8,800",
            scope_id=scope,
        ),
    )


def physical_members():
    return tuple(StructuralMemberObservation(
        observation_id=f"member:{index}", member_kind="structural_support",
        page_id="54", view_id="plan-54", view_type="plan",
        source_evidence_ids=(f"physical-proof:{index}",),
        source_primitive_ids=(f"page:54:drawing:{index}",),
    ) for index in range(4))


def link(definition_id, observation, **changes):
    return replace(AuthenticatedStructuralDefinitionLink(
        selector=selector(), definition_id=definition_id,
        observation_id=observation.observation_id,
        source_primitive_id=observation.source_primitive_ids[0],
        scope_id="building-a", member_role="pillar",
        source_evidence_ids=(f"explicit-leader:{observation.observation_id}",),
        link_kind="source_leader",
    ), **changes)


def resolve(binding):
    return StructuralMemberProducer.from_authenticated_evidence(
        selector=selector(), definitions=binding.definitions,
        observations=binding.observations,
        view_scopes=(StructuralMemberViewScope(
            page_id="54", view_id="plan-54", view_type="plan", complete=True,
        ),),
    ).publish()


def test_adjacent_source_fragments_create_stable_count_free_definition():
    a = parse_structural_member_definitions(selector=selector(), blocks=source_blocks())
    b = parse_structural_member_definitions(selector=selector(), blocks=source_blocks(99))
    assert len(a) == 1
    assert a == b
    assert a[0].member_role == "pillar"
    assert a[0].definition.section_spec == (
        "circular hollow section; 50mm dia x 1.5mm thick; pillar"
    )
    assert a[0].definition.source_evidence_ids == (
        f"sha256:{'a' * 64}:page:47:block:11",
        f"sha256:{'a' * 64}:page:47:block:12",
    )
    assert "4 NO" not in a[0].definition.section_spec
    assert "99" not in a[0].definition.section_spec


def test_definition_or_explicit_count_text_alone_never_creates_quantity():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=source_blocks(99)
    )
    binding = bind_structural_member_definitions(
        selector=selector(), definitions=definitions, observations=(), links=(),
    )
    result = resolve(binding)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert result.members == ()


def test_four_physical_members_remain_four_with_one_shared_definition():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=source_blocks()
    )
    observations = physical_members()
    links = tuple(link(definitions[0].definition.definition_id, row) for row in observations)
    binding = bind_structural_member_definitions(
        selector=selector(), definitions=definitions,
        observations=observations, links=links,
    )
    result = resolve(binding)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 4
    assert len({row.physical_member_id for row in result.members}) == 4
    assert {row.definition_ids for row in result.members} == {
        (definitions[0].definition.definition_id,)
    }
    assert len({row.source_primitive_ids for row in result.members}) == 4
    assert resolve(bind_structural_member_definitions(
        selector=selector(), definitions=parse_structural_member_definitions(
            selector=selector(), blocks=source_blocks(99)
        ), observations=observations, links=links,
    )).quantity == 4


def test_no_link_and_unrelated_scope_do_not_relabel_physical_members():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=source_blocks()
    )
    observations = physical_members()
    d_id = definitions[0].definition.definition_id
    for links in ((), (link(d_id, observations[0], scope_id="building-b"),)):
        binding = bind_structural_member_definitions(
            selector=selector(), definitions=definitions,
            observations=observations, links=links,
        )
        result = resolve(binding)
        assert result.quantity == 4
        assert all(row.definition_ids == () for row in result.members)
        assert binding.bound_observation_ids == ()


def test_ambiguous_definitions_preserve_instances_without_type_claim():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=source_blocks()
    )
    competing = replace(definitions[0], definition=replace(
        definitions[0].definition, definition_id="competing-source-definition"
    ))
    observation = physical_members()[0]
    binding = bind_structural_member_definitions(
        selector=selector(), definitions=(*definitions, competing),
        observations=(observation,),
        links=(
            link(definitions[0].definition.definition_id, observation),
            link(competing.definition.definition_id, observation),
        ),
    )
    result = resolve(binding)
    assert result.quantity == 1
    assert result.members[0].definition_ids == ()
    assert binding.unresolved_observation_ids == (observation.observation_id,)


def test_stale_lineage_and_unowned_primitive_cannot_bind():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=source_blocks()
    )
    observation = physical_members()[0]
    definition_id = definitions[0].definition.definition_id
    for bad_link in (
        link(definition_id, observation, selector=selector(revision_id="revision-2")),
        link(definition_id, observation, selector=selector(snapshot_id="snapshot-2")),
        link(definition_id, observation, selector=selector(source_sha256="b" * 64)),
        link(definition_id, observation, source_primitive_id="unrelated-symbol"),
        link(definition_id, observation, link_kind="nearest_text"),
    ):
        binding = bind_structural_member_definitions(
            selector=selector(), definitions=definitions,
            observations=(observation,), links=(bad_link,),
        )
        assert resolve(binding).quantity == 1
        assert resolve(binding).members[0].definition_ids == ()
    revised = parse_structural_member_definitions(
        selector=selector(revision_id="revision-2"), blocks=source_blocks()
    )
    assert revised[0].definition.definition_id != definition_id
    stale_definitions = parse_structural_member_definitions(
        selector=selector(source_sha256="b" * 64), blocks=source_blocks()
    )
    forged_current_link = link(
        stale_definitions[0].definition.definition_id, observation
    )
    stale_binding = bind_structural_member_definitions(
        selector=selector(), definitions=stale_definitions,
        observations=(observation,), links=(forged_current_link,),
    )
    assert stale_binding.definitions == ()
    assert resolve(stale_binding).members[0].definition_ids == ()


def test_parser_rejects_nonadjacent_fragments_and_mixed_member_kind():
    material, member = source_blocks()
    assert parse_structural_member_definitions(
        selector=selector(), blocks=(material, replace(member, reading_order=14))
    ) == ()
    assert parse_structural_member_definitions(
        selector=selector(member_kind="masonry_pier"), blocks=source_blocks()
    ) == ()


def test_production_definition_module_has_no_benchmark_imports():
    tree = ast.parse(Path("pb_structural_member_definition_producer.py").read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not any("benchmark" in name or "gold" in name for name in names)
