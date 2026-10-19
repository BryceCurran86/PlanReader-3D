"""Source-decoder completeness must match ORIGINAL page addresses, not length.

Source-neutral enumeration controls: these can never authenticate a physical
opening or mint count=1, quantity, host, frame or frozen benchmark score.
"""
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessProducer,
    OpeningUniverseSelector,
    SOURCE_DECODE_INCOMPLETE,
)
from pb_source_observation_authority import SourceDecodeCoverageRecord


def _publication(pages, *, total=2, kind="document"):
    producer = OpeningUniverseCompletenessProducer(
        producer_method="source-page-identity-control",
        producer_version="1",
    )
    source = SourceDecodeCoverageRecord(
        document_id="original-document", revision_id="sha-revision",
        total_pages=total, decoded_pages=tuple(range(1, total + 1)),
        failed_pages=(), state="complete",
    )
    record = producer.publish_enumeration(
        decision_scope_id="whole-source",
        decision_scope_kind=kind,
        document_id="original-document",
        revision_id="sha-revision",
        source_sha256="a" * 64,
        snapshot_id="source-snapshot",
        page_ids=pages,
        viewport_id=None,
        coverage=source,
        source_primitives=(),
        enumerated_primitives=(),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )
    result = producer.authority().resolve(OpeningUniverseSelector(
        document_id="original-document",
        revision_id="sha-revision",
        source_sha256="a" * 64,
        snapshot_id="source-snapshot",
        decision_scope_id="whole-source",
    ))
    assert result.record == record
    return record, result


@pytest.mark.parametrize("pages", [
    ("1", "3"), ("2", "9"), ("alpha", "beta"), ("0", "2"),
    ("01", "2"), ("-1", "2"),
])
def test_complete_document_cannot_use_equal_count_of_wrong_page_ids(pages):
    record, result = _publication(pages)
    assert record.source_decode_complete is False
    assert record.decision_scope_complete is False
    assert SOURCE_DECODE_INCOMPLETE in record.reason_codes
    assert result.status is Status.ABSTAINED


@pytest.mark.parametrize("pages", [("1", "2"), ("2", "1")])
def test_exact_original_document_pages_are_source_decoded(pages):
    record, result = _publication(pages)
    assert record.source_decode_complete is True
    assert record.semantic_enumeration_complete is True
    assert record.decision_scope_complete is True
    assert result.status is Status.CORROBORATED


def test_legacy_page_scope_keeps_historical_named_page_contract():
    # Old "page_scope" sources were intentionally not typed document IDs;
    # this strict source-identity check is limited to new document scopes.
    record, result = _publication(("page_1", "page_2"), kind="page_scope")
    assert record.source_decode_complete
    assert result.status is Status.CORROBORATED
