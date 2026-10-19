"""G17 semantic enumeration cannot infer original page identity via int(...).

Generated PDF controls exercise the real SourceVisibilityProducer path.
No quantity, count, wall host or customer file is produced by these tests.
"""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
    SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_semantic_opening_enumeration_authority_v1 import (
    _ingest, _pdf, _two_page_pdf,
)


def _corrupt_original_coverage(*, total, decoded, failed=(), two_pages=False):
    source = SourceVisibilityProducer(
        producer_method="semantic-typed-source-test", producer_version="1",
    )
    published = _ingest(
        source, _two_page_pdf() if two_pages else _pdf(),
        "typed-semantic-original",
    )
    source._published_by_revision[published.revision.revision_id] = replace(
        published,
        coverage=replace(
            published.coverage,
            total_pages=total, decoded_pages=decoded,
            failed_pages=failed,
        ),
    )
    return source, published.revision.revision_id


@pytest.mark.parametrize("total,decoded,failed", [
    (True, (1,), ()), (1.9, (1,), ()), ("1", (1,), ()),
    (1, (True,), ()), (1, ("1",), ()), (1, (1.8,), ()),
    (1, (1, 1), ()), (1, (1,), (1,)),
    (1, (1,), (False,)), (1, (2,), ()),
])
def test_untyped_or_conflicting_original_page_inventory_never_enumerates(
        total, decoded, failed):
    source, revision_id = _corrupt_original_coverage(
        total=total, decoded=decoded, failed=failed,
    )
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    result = producer.publish_document_scope(
        revision_id=revision_id,
        decision_scope_id="semantic-enumeration:all-pages",
    )
    assert result.status is Status.ABSTAINED
    assert result.record is None
    assert SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE in result.reason_codes


def test_original_unmodified_native_source_positive_is_still_enumerated():
    source = SourceVisibilityProducer(
        producer_method="semantic-typed-source-test", producer_version="1",
    )
    published = _ingest(source, _pdf(), "semantic-intact-original-control")
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    result = producer.publish_document_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="semantic-enumeration:complete-original",
    )
    assert result.status is Status.CORROBORATED
    assert result.record is not None
    assert len(result.record.physical_opening_record_ids) == 1


def test_page_scope_can_still_reconcile_valid_partial_source_receipt():
    source, revision_id = _corrupt_original_coverage(
        total=2, decoded=(1,), failed=(2,), two_pages=True,
    )
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    result = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="semantic-enumeration:one-authenticated-page",
        page_ids=("1",),
    )
    assert result.status is Status.CORROBORATED
    assert result.record is not None
    assert result.record.page_ids == ("1",)
    assert result.record.physical_opening_universe_complete
