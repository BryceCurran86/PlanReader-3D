"""Original page coverage and semantic truth may not use Python coercion.

These synthetic checks are source-completeness only; they never issue a
construction quantity, opening host, connected wall frame or benchmark score.
"""
import pytest

from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessProducer,
    SOURCE_DECODE_INCOMPLETE,
)
from pb_source_observation_authority import SourceDecodeCoverageRecord


def _report(*, total=2, decoded=(1, 2), failed=(), state="complete",
            page_ids=("1", "2"), scope_kind="document",
            semantic=True, traversal=False):
    producer = OpeningUniverseCompletenessProducer(
        producer_method="typed-native-decode", producer_version="1",
    )
    return producer.publish_enumeration(
        decision_scope_id="typed-original-scope",
        decision_scope_kind=scope_kind,
        document_id="source-doc",
        revision_id="source-revision",
        source_sha256="a" * 64,
        snapshot_id="authenticated-snapshot",
        page_ids=page_ids,
        viewport_id=None,
        coverage=SourceDecodeCoverageRecord(
            document_id="source-doc", revision_id="source-revision",
            total_pages=total, decoded_pages=decoded,
            failed_pages=failed, state=state,
        ),
        source_primitives=(), enumerated_primitives=(),
        optional_content_state="known_visible",
        xobject_traversal_truncated=traversal,
        semantic_enumeration_proven=semantic,
    )


@pytest.mark.parametrize("total,decoded,failed", (
    (True, (1,), ()), (1.9, (1,), ()), ("2", (1, 2), ()),
    (2, (True, 2), ()), (2, (1.8, 2), ()),
    (2, ("1", 2), ()), (2, (1, 1, 2), ()),
    (2, (1, 2), (2,)), (2, (1, 2), (False,)),
))
def test_untyped_or_duplicate_original_decode_inventory_cannot_certify_source(
        total, decoded, failed):
    report = _report(total=total, decoded=decoded, failed=failed)
    assert report.source_decode_complete is False
    assert report.decision_scope_complete is False
    assert SOURCE_DECODE_INCOMPLETE in report.reason_codes


@pytest.mark.parametrize("untrusted", ("false", "true", 1, 0, None, []))
def test_truthy_or_falsey_string_cannot_claim_semantic_proof(untrusted):
    with pytest.raises(TypeError, match="semantic enumeration"):
        _report(semantic=untrusted)


@pytest.mark.parametrize("untrusted", ("false", "true", 1, 0, None))
def test_untyped_xobject_traversal_claim_cannot_be_coerced(untrusted):
    with pytest.raises(TypeError, match="xobject traversal"):
        _report(traversal=untrusted)


def test_source_native_complete_control_retains_proof():
    report = _report()
    assert report.source_decode_complete and report.semantic_enumeration_complete
    assert report.decision_scope_complete
    assert report.reason_codes == ()


def test_genuine_partial_page_scope_may_prove_only_its_decoded_page():
    report = _report(
        decoded=(1,), failed=(2,), state="partial",
        page_ids=("1",), scope_kind="pages",
    )
    assert report.source_decode_complete is True
    assert report.semantic_enumeration_complete is True
    assert report.decision_scope_complete is True


def test_explicitly_unproven_semantic_enumeration_always_abstains():
    report = _report(semantic=False)
    assert report.source_decode_complete is True
    assert report.semantic_enumeration_complete is False
    assert report.decision_scope_complete is False
