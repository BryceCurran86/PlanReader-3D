"""Opening identity graph integrity authority tests."""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_identity_graph_authority import (
    OPENING_IDENTITY_GRAPH_CONTRADICTION,
    OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED,
    OPENING_IDENTITY_GRAPH_RESOLVED,
    OpeningIdentityGraphAuthority,
    OpeningIdentityGraphProducer,
    OpeningIdentityGraphSelector,
    _validate_identity_relations,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
    PhysicalOpeningAuthority,
    PhysicalOpeningIdentityResult,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


SCOPE = "identity-graph:document"


def _draw_opening(page: fitz.Page, *, y: float, x0: float = 20.0) -> None:
    left = x0 + 80.0
    right = x0 + 120.0
    far = x0 + 200.0
    y1 = y + 10.0
    for first, second in (
        ((x0, y), (left, y)),
        ((right, y), (far, y)),
        ((x0, y1), (left, y1)),
        ((right, y1), (far, y1)),
        ((left, y), (left, y1)),
        ((right, y), (right, y1)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )


def _fixture(*, opening_ys: tuple[float, ...] = (100.0, 250.0, 400.0)):
    doc = fitz.open()
    page = doc.new_page(width=800, height=700)
    for y in opening_ys:
        _draw_opening(page, y=y)
    payload = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="identity-graph-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="identity-graph-doc",
        source_bytes=payload,
        source_locator="memory://identity-graph.pdf",
    )
    semantic_producer = (
        SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    )
    semantic_result = semantic_producer.publish_document_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=SCOPE,
    )
    assert semantic_result.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic_result.record is not None
    physical = PhysicalOpeningAuthority(source.authority())
    selector = OpeningIdentityGraphSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id=SCOPE,
    )
    producer = OpeningIdentityGraphProducer.from_authorities(
        semantic_enumeration_authority=semantic_producer.authority(),
        physical_opening_authority=physical,
    )
    return semantic_result.record, physical, producer, selector


def test_public_surface_accepts_selector_only_not_caller_edges() -> None:
    params = set(inspect.signature(OpeningIdentityGraphProducer.publish).parameters)
    assert params == {"self", "selector"}
    forbidden = {
        "same_edges",
        "distinct_edges",
        "relations",
        "candidate_ids",
        "opening_ids",
        "expected_count",
    }
    assert not (params & forbidden)


def test_authority_is_producer_owned() -> None:
    with pytest.raises(TypeError):
        OpeningIdentityGraphAuthority({})


def test_three_real_openings_resolve_as_three_distinct_components() -> None:
    semantic, _physical, producer, selector = _fixture()
    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert OPENING_IDENTITY_GRAPH_RESOLVED in result.reason_codes
    assert len(result.record.physical_opening_record_ids) == 3
    assert len(result.record.identity_components) == 3
    assert all(len(component) == 1 for component in result.record.identity_components)
    assert len(result.record.proven_distinct_pairs) == 3
    assert set(result.record.physical_opening_record_ids) == set(
        semantic.physical_opening_record_ids
    )


def test_transitive_same_same_distinct_triad_is_conflict() -> None:
    semantic, physical, producer, selector = _fixture()
    opening_ids = tuple(sorted(semantic.physical_opening_record_ids))
    assert len(opening_ids) == 3
    rep_to_opening = {
        rep: opening_id
        for opening_id, rep in zip(
            semantic.physical_opening_record_ids,
            semantic.representative_observation_ids,
        )
    }
    a, b, c = opening_ids

    def _forced_compare(left_selector, right_selector):
        left = rep_to_opening[left_selector.observation_id]
        right = rep_to_opening[right_selector.observation_id]
        pair = frozenset((left, right))
        if pair in (frozenset((a, b)), frozenset((b, c))):
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=min(left, right),
                proven_same=True,
                reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
            )
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
            proven_same=False,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
        )

    object.__setattr__(physical, "compare_identity", _forced_compare)
    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert OPENING_IDENTITY_GRAPH_CONTRADICTION in result.reason_codes


def test_unresolved_pair_abstains_entire_graph() -> None:
    semantic, physical, producer, selector = _fixture(opening_ys=(100.0, 300.0))
    reps = set(semantic.representative_observation_ids)

    def _unresolved(left_selector, right_selector):
        assert left_selector.observation_id in reps
        assert right_selector.observation_id in reps
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_UNRESOLVED,),
        )

    object.__setattr__(physical, "compare_identity", _unresolved)
    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED in result.reason_codes


def test_private_relation_validator_detects_exact_requested_triad() -> None:
    contradiction, components, distinct = _validate_identity_relations(
        nodes=("A", "B", "C"),
        same_edges=(("A", "B"), ("B", "C")),
        distinct_edges=(("A", "C"),),
    )
    assert contradiction is True
    assert components == (("A", "B", "C"),)
    assert distinct == (("A", "C"),)


def test_relation_validator_unresolved_is_not_guessed_here() -> None:
    """The pure graph validator consumes only resolved edges.

    Unresolved relations are stopped by the producer before graph commitment,
    proven by test_unresolved_pair_abstains_entire_graph.
    """
    contradiction, components, distinct = _validate_identity_relations(
        nodes=("A", "B"),
        same_edges=(),
        distinct_edges=(("A", "B"),),
    )
    assert contradiction is False
    assert components == (("A",), ("B",))
    assert distinct == (("A", "B"),)
