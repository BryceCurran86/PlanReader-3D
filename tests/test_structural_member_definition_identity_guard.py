"""A definition link must identify exactly one source-owned observation."""
from __future__ import annotations

from dataclasses import replace
from itertools import permutations

import pytest

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


def source_fixture():
    selector = StructuralMemberSelector(
        document_id="source-document", revision_id="revision-1",
        source_sha256="a" * 64, snapshot_id="snapshot-1",
        decision_scope_id="building-a:supports", member_kind="structural_support",
    )
    definitions = parse_structural_member_definitions(selector=selector, blocks=(
        SourceStructuralTextBlock(
            page_id="1", view_id="specification", block_id="block-1", reading_order=1,
            bbox=(0, 0, 100, 20), scope_id="building-a",
            text="50mm dia x 1.5mm thick circular hollow section pillar",
        ),
    ))
    observation = StructuralMemberObservation(
        observation_id="member-a", member_kind="structural_support",
        page_id="2", view_id="plan", view_type="plan",
        source_evidence_ids=("physical-proof-a",), source_primitive_ids=("primitive-a",),
    )
    link = AuthenticatedStructuralDefinitionLink(
        selector=selector, definition_id=definitions[0].definition.definition_id,
        observation_id=observation.observation_id, source_primitive_id="primitive-a",
        scope_id="building-a", member_role="pillar",
        source_evidence_ids=("explicit-leader-a",), link_kind="source_leader",
    )
    return selector, definitions, observation, link


@pytest.mark.parametrize("duplicate_kind", ("different_primitive", "identical", "different_member_kind"))
@pytest.mark.parametrize("reverse", (False, True))
def test_duplicate_ids_cannot_spread_a_source_owned_definition(duplicate_kind, reverse):
    selector, definitions, observation, link = source_fixture()
    duplicate = observation
    if duplicate_kind == "different_primitive":
        duplicate = replace(observation, source_evidence_ids=("physical-proof-b",),
                            source_primitive_ids=("primitive-b",))
    elif duplicate_kind == "different_member_kind":
        duplicate = replace(observation, member_kind="masonry_pier")
    observations = (duplicate, observation) if reverse else (observation, duplicate)
    before = tuple(replace(row) for row in observations)

    with pytest.raises(ValueError, match="duplicate structural observation id"):
        bind_structural_member_definitions(
            selector=selector, definitions=definitions, observations=observations, links=(link,),
        )

    assert observations == before
    assert all(row.definition_id is None for row in observations)


def test_duplicate_ids_are_rejected_even_without_definitions_or_links():
    selector, _, observation, _ = source_fixture()
    with pytest.raises(ValueError, match="duplicate structural observation id"):
        bind_structural_member_definitions(
            selector=selector, definitions=(), observations=(observation, observation), links=(),
        )


def test_unique_ids_keep_binding_and_physical_authority_order_independent():
    selector, definitions, observation, link = source_fixture()
    unrelated = replace(
        observation, observation_id="member-b", source_evidence_ids=("physical-proof-b",),
        source_primitive_ids=("primitive-b",),
    )
    stale_link = replace(link, selector=replace(selector, snapshot_id="stale-snapshot"))
    expected_resolution = None
    for observations in permutations((observation, unrelated)):
        for links in permutations((link, stale_link)):
            binding = bind_structural_member_definitions(
                selector=selector, definitions=definitions, observations=observations, links=links,
            )
            assert tuple(row.observation_id for row in binding.observations) == tuple(
                row.observation_id for row in observations
            )
            assert {row.observation_id: row.definition_id for row in binding.observations} == {
                "member-a": link.definition_id, "member-b": None,
            }
            assert binding.bound_observation_ids == ("member-a",)
            assert binding.unresolved_observation_ids == ("member-b",)
            resolution = StructuralMemberProducer.from_authenticated_evidence(
                selector=selector, definitions=binding.definitions, observations=binding.observations,
                view_scopes=(StructuralMemberViewScope("2", "plan", "plan", complete=True),),
            ).publish()
            assert resolution.status is EvidenceResolutionStatus.CORROBORATED
            assert resolution.quantity == 2
            if expected_resolution is None:
                expected_resolution = resolution
            else:
                assert resolution == expected_resolution
    assert observation.definition_id is None
    assert unrelated.definition_id is None
