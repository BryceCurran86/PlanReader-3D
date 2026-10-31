"""A malformed positive existence wrapper supplies no separation witness."""
from dataclasses import replace

import pytest

from pb_physical_opening_authority import PhysicalOpeningAuthority
from test_plan_tag_opening_occupancy_shadow_producer import (
    SINGLE, S, M, _anchor, _inventory, _publish,
)


@pytest.mark.parametrize("change", [
    None, {"document_id": "foreign"}, {"revision_id": "foreign"},
    {"source_sha256": "0" * 64}, {"snapshot_id": "foreign"},
    {"page_id": "2"}, {"proposition": "other"}, {"status": S.ABSTAINED},
])
def test_malformed_positive_record_abstains_without_crashing_or_mutating(monkeypatch, change):
    source, published = _publish(SINGLE)
    anchors = [_anchor("word", 120., 105.)]
    before = _inventory(source, published, anchors)
    assert len(before.occupancies) == 1
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    original = PhysicalOpeningAuthority.prove_existence
    calls = []

    def malformed(self, selector):
        result = original(self, selector)
        if result.status is S.CORROBORATED:
            calls.append(selector.observation_id)
            record = None if change is None else replace(result.existence_record, **change)
            return replace(result, existence_record=record)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "prove_existence", malformed)
        result = _inventory(source, published, anchors)
    assert len(calls) == 6
    assert result.status is S.CANDIDATE and result.occupancies == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.outcome == M.OUTCOME_NOT_CORROBORATED
    assert all(status == S.ABSTAINED.value for _, status in diagnostic.containing_existence)
    assert source.published_snapshot_for_revision(published.revision.revision_id) == snapshot
    assert _inventory(source, published, anchors) == before
