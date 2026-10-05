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


def masonry_pier_blocks():
    return (
        SourceStructuralTextBlock(
            page_id="183", view_id="boq-page-183", block_id="21", reading_order=21,
            bbox=(80.0, 410.0, 650.0, 432.0),
            text=(
                "Extra over for 300 x 300mm masonry piers, "
                "4,500mm high (Including 1,200mm below ground)"
            ),
            scope_id="building-a",
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


def test_masonry_pier_definition_parses_without_minting_instances():
    definitions = parse_structural_member_definitions(
        selector=selector(), blocks=masonry_pier_blocks()
    )
    assert len(definitions) == 1
    assert definitions[0].member_role == "pier"
    assert definitions[0].definition.section_spec == "masonry; 300 x 300mm; pier"
    assert "4,500" not in definitions[0].definition.section_spec
    assert "1,200" not in definitions[0].definition.section_spec

    binding = bind_structural_member_definitions(
        selector=selector(), definitions=definitions, observations=(), links=(),
    )
    result = resolve(binding)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert result.members == ()


def test_hot_rolled_beam_and_lintel_definitions_are_source_semantics_only():
    beam_selector = selector(member_kind="beam", decision_scope_id="building-a:frame")
    blocks = (
        SourceStructuralTextBlock(
            page_id="201",
            view_id="structural-s201",
            block_id="beam-1",
            reading_order=1,
            bbox=(50.0, 50.0, 250.0, 70.0),
            text="310UB40.4 beam",
            scope_id="building-a",
        ),
        SourceStructuralTextBlock(
            page_id="201",
            view_id="structural-s201",
            block_id="beam-2",
            reading_order=2,
            bbox=(50.0, 80.0, 250.0, 100.0),
            text="200PFC lintel",
            scope_id="building-a",
        ),
    )
    beam_defs = parse_structural_member_definitions(
        selector=beam_selector,
        blocks=blocks,
    )
    assert len(beam_defs) == 1
    assert beam_defs[0].member_role == "beam"
    assert beam_defs[0].definition.section_spec == (
        "universal beam; 310ub40.4; beam"
    )

    lintel_defs = parse_structural_member_definitions(
        selector=selector(member_kind="lintel", decision_scope_id="building-a:lintels"),
        blocks=blocks,
    )
    assert len(lintel_defs) == 1
    assert lintel_defs[0].member_role == "lintel"
    assert lintel_defs[0].definition.section_spec == (
        "parallel flange channel; 200pfc; lintel"
    )

    # Definition text remains type evidence only and cannot mint instances.
    empty = bind_structural_member_definitions(
        selector=beam_selector,
        definitions=beam_defs,
        observations=(),
        links=(),
    )
    result = StructuralMemberProducer.from_authenticated_evidence(
        selector=beam_selector,
        definitions=empty.definitions,
        observations=empty.observations,
        view_scopes=(),
    ).publish()
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None


def test_cold_formed_purlin_definition_requires_matching_member_kind():
    block = SourceStructuralTextBlock(
        page_id="202",
        view_id="roof-framing",
        block_id="purlin-1",
        reading_order=1,
        bbox=(40.0, 40.0, 240.0, 60.0),
        text="C15015 purlins",
        scope_id="building-a",
    )
    purlin_defs = parse_structural_member_definitions(
        selector=selector(member_kind="purlin", decision_scope_id="building-a:roof"),
        blocks=(block,),
    )
    assert len(purlin_defs) == 1
    assert purlin_defs[0].definition.section_spec == (
        "cold formed c section; c15015; purlin"
    )
    assert parse_structural_member_definitions(
        selector=selector(member_kind="column", decision_scope_id="building-a:columns"),
        blocks=(block,),
    ) == ()


def test_masonry_size_without_member_role_or_material_is_not_a_definition():
    material = masonry_pier_blocks()[0]
    assert parse_structural_member_definitions(
        selector=selector(),
        blocks=(replace(material, text="Window opening 300 x 300mm"),),
    ) == ()
    assert parse_structural_member_definitions(
        selector=selector(),
        blocks=(replace(material, text="300 x 300mm piers"),),
    ) == ()
    assert parse_structural_member_definitions(
        selector=selector(),
        blocks=(replace(material, text="300 x 300mm masonry wall"),),
    ) == ()


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
