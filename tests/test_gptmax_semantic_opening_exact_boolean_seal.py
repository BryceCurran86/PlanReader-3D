"""Physical opening count completeness cannot be supplied by truthy strings.

Run against the genuine fitz-authored G17 source-enumeration producer with its
independent source visibility and candidate-closure proofs. Does not issue a
new opening count, source quantity or benchmark point.
"""
from dataclasses import replace

import pytest

from pb_generic_opening_count_authority import _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_semantic_opening_enumeration_authority_v1 import (
    SCOPE, _ingest, _pdf,
)


@pytest.mark.parametrize("field,invalid", [
    ("physical_opening_universe_complete", "false"),
    ("physical_opening_universe_complete", "true"),
    ("physical_opening_universe_complete", 1),
    ("physical_opening_universe_complete", None),
    ("structural_enumeration_complete", "false"),
    ("structural_enumeration_complete", 1),
])
def test_reconstructed_semantic_completeness_fails_literal_type(field, invalid):
    source = SourceVisibilityProducer(
        producer_method="typed-semantic-universe", producer_version="1",
    )
    pub = _ingest(source, _pdf(), "semantic-typed-complete-reconstruction")
    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    result = semantic.publish_document_scope(
        revision_id=pub.revision.revision_id, decision_scope_id=SCOPE,
    )
    assert result.record is not None
    with pytest.raises(TypeError, match="typed booleans"):
        replace(result.record, **{field: invalid})


@pytest.mark.parametrize("field,invalid", [
    ("physical_opening_universe_complete", "false"),
    ("physical_opening_universe_complete", "true"),
    ("structural_enumeration_complete", "false"),
    ("structural_enumeration_complete", 1),
])
def test_untyped_mutated_producer_record_cannot_gain_commercial_seal(field, invalid):
    source = SourceVisibilityProducer(
        producer_method="typed-semantic-universe", producer_version="1",
    )
    pub = _ingest(source, _pdf(), "semantic-typed-seal-attack")
    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    result = semantic.publish_document_scope(
        revision_id=pub.revision.revision_id, decision_scope_id=SCOPE,
    )
    assert result.record is not None
    # Faked internal packet simulates a corrupt producer result bypassing its
    # dataclass constructor; consumer must independently recheck exact types.
    object.__setattr__(result.record, field, invalid)
    authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        decision_scope_id=SCOPE,
        _semantic_opening_producer=semantic,
    )
    assert getattr(authority, "_source_authentication_seal", None) is not (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )


def test_genuine_complete_semantic_source_still_binds_count_seal():
    source = SourceVisibilityProducer(
        producer_method="typed-semantic-universe", producer_version="1",
    )
    pub = _ingest(source, _pdf(), "semantic-typed-original-positive")
    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    result = semantic.publish_document_scope(
        revision_id=pub.revision.revision_id, decision_scope_id=SCOPE,
    )
    assert result.record is not None
    assert result.record.physical_opening_universe_complete is True
    authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        decision_scope_id=SCOPE,
        _semantic_opening_producer=semantic,
    )
    assert getattr(authority, "_source_authentication_seal", None) is (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )
